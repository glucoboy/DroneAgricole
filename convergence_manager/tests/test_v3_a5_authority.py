"""Rejeu des admissions strictement TEST_ONLY et de la séparation du cartographe."""

import argparse
from base64 import b64encode
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[2]
PROFILE = ROOT / "docs/electromechanical_v3/bench_c1_coupled/profile.json"
CHECKS = ["REOPEN_XLINK", "L2_TOPOLOGY", "L4_GEOMETRY", "L4_SUPPORT_ANCHOR", "L4_SERVICE",
          "L4_DYNAMIC_BEND_RADIUS", "VERIFY_IMMUTABLE_SOURCES", "VALIDATE_T0"]
NOW = datetime.now(timezone.utc).replace(microsecond=0)


def stamp(minutes=0):
    return (NOW + timedelta(minutes=minutes)).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha(data):
    return sha256(data).hexdigest()


def data(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()


def save(path, value):
    raw = data(value)
    path.write_bytes(raw)
    return sha(raw)


def read(path):
    return json.loads(path.read_bytes())


class SigningFixtures:
    def __init__(self, openssl, work):
        self.openssl = openssl
        self.work = work
        self.keys = {}
        for role in ("review", "register", "untrusted"):
            path = work / f"TEST_ONLY_{role}.pem"
            self.run("genpkey", "-algorithm", "Ed25519", "-out", path)
            self.keys[role] = path

    def run(self, *args):
        return subprocess.run([self.openssl, *map(str, args)], capture_output=True, check=True, timeout=10).stdout

    def public_key(self, role):
        der = self.run("pkey", "-in", self.keys[role], "-pubout", "-outform", "DER")
        prefix = bytes.fromhex("302a300506032b6570032100")
        assert der.startswith(prefix) and len(der) == len(prefix) + 32
        return der[len(prefix):].hex()

    def envelope(self, path, domain, payload, role):
        content = data(payload)
        message = self.work / "TEST_ONLY_message.bin"
        message.write_bytes(content)
        signature = self.run("pkeyutl", "-sign", "-rawin", "-inkey", self.keys[role], "-in", message)
        return save(path, {"schema": f"v3.a5.signed_{domain}/1", "payload_b64": b64encode(content).decode(),
                           "signature_b64": b64encode(signature).decode()})


class AdmissionFixture:
    def __init__(self, core, work, signing):
        self.core, self.work, self.signing = core, work, signing
        self.raw, self.trusted, self.sandbox = (work / name for name in ("raw", "trusted", "copy"))
        for folder in (work, self.raw, self.trusted, self.sandbox):
            folder.mkdir()
        model = read(PROFILE)
        for name in model["dependencies"]:
            target = self.sandbox / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / model["source"] / name, target)
        self.profile = self.trusted / "profile.json"
        shutil.copyfile(PROFILE, self.profile)
        refs = {}
        for kind in ("raw", "photo", "identity_photo", "manufacturer_document", "tolerance_document", "alternate"):
            path = self.raw / f"{kind}.fixture"
            content = f"TEST_ONLY {kind}\n".encode()
            path.write_bytes(content)
            refs[kind] = {"path": path.name, "sha256": sha(content)}
        self.alternate = refs.pop("alternate")
        identity = {"manufacturer": "TEST_ONLY", "mpn": "TEST_ONLY", "variant": "Li-ion",
                    "revision": "TEST-CH343G", "lot_or_serial": "TEST-LOT"}
        tolerance = {"comparison": "LE", "limit": 0.1, "unit": "mm", "source": "TEST_ONLY §1"}
        facts = {"jbd_port": "J3", "nc_connected": False, "carrier": "P64", "measured_hole_present": True}
        binding = {"parent": "TEST_ONLY.FCStd#Plate", "datum": "test-two-datum-fixture"}
        matrix = [1, 0, 0, 8, 0, 1, 0, 4, 0, 0, 1, 1, 0, 0, 0, 1]
        inverse = [1, 0, 0, -8, 0, 1, 0, -4, 0, 0, 1, -1, 0, 0, 0, 1]
        subject = "anchor:fixture"
        self.record = {
            "record_id": "test-record", "evidence_class": "TEST_ONLY", "issue": "UART-MOUNT-001", "subject": subject,
            "check_id": "support-gap", "identity": identity, "facts": facts, "review": None,
            "sources": {**refs, "manufacturer_locator": "TEST_ONLY §1", "manufacturer_revision": "TEST-CH343G"},
            "capture": {"author": "test-operator", "measured_at": stamp(-5), "view": "face", "orientation": "trièdre TEST_ONLY",
                        "scale": "graduée", "power_state": "DEENERGIZED", "detached": True},
            "frame": {**binding, "local_to_parent": matrix, "parent_to_local": inverse},
            "measurement": {"kind": "GAP", "method": "TEST_ONLY", "instrument": "TEST_ONLY", "resolution": 0.01,
                            "value": 0.05, "unit": "mm", "uncertainty": 0.01, "tolerance": tolerance},
        }
        self.configuration = "TEST_ONLY_fixture"
        identities = {subject: {"identity": identity, "identity_photo_sha256": refs["identity_photo"]["sha256"],
                                "manufacturer_sha256": refs["manufacturer_document"]["sha256"],
                                "manufacturer_locator": "TEST_ONLY §1", "manufacturer_revision": "TEST-CH343G"}}
        self.policy = self.trusted / "policy.json"
        self.policy_sha = save(self.policy, {
            "schema": "v3.a4.review_policy/1", "configuration": self.configuration, "issues": [self.record["issue"]],
            "reviewer_ids": [], "identities": identities,
            "checks": {"support-gap": {"subject": subject, "issue": self.record["issue"], "kind": "GAP",
                "input_unit": "mm", "tolerance": tolerance, "plausible_min": 0, "plausible_max": 50,
                "tolerance_sha256": refs["tolerance_document"]["sha256"], "facts": facts,
                "frame": {**binding, "local_to_parent": matrix, "rotation_entry_tolerance": 0.001,
                          "position_tolerance_mm": 0.1}}},
        })
        bindings = {"configuration": self.configuration, "model_version": model["model_version"], "occurrence": subject,
                    "operation": "CREATE_SUPPORT", "lot_sha256": sha(data(identities)), "profile_sha256": sha(PROFILE.read_bytes()),
                    "xlink_dependencies": model["dependencies"], "required_checks": CHECKS}
        self.bounds = {"carrier": "P64", "min_translation_mm": [0, 0, 0], "max_translation_mm": [2, 2, 2],
                       "rotation_xyzw": [0, 0, 0, 1]}
        self.trust_path = self.trusted / "trust.json"
        self.trust = {"schema": "v3.a5.trust/1", "trusted_root": self.trusted.as_posix(), "evidence_class": "TEST_ONLY",
                      "domain": "SYNTHETIC_BENCH", "bindings": bindings, "bounds": self.bounds,
                      "material_policy": self.policy.name, "material_policy_sha256": self.policy_sha,
                      "profile": self.profile.relative_to(ROOT).as_posix(), "source_root": model["source"],
                      "reviewer_id": "test-reviewer", "reviewer_public_key_hex": signing.public_key("review"),
                      "registry": "registry.json", "registry_public_key_hex": signing.public_key("register"),
                      "required_record_checks": [self.record["check_id"]]}
        self.trust_sha = save(self.trust_path, self.trust)
        self.packet = self.raw / "packet.json"
        self.review = self.raw / "review.json"
        self.registry = self.trusted / "registry.json"
        self.state = self.trusted / "a5-consumption.json"
        save(self.state, {"schema": "v3.a5.consumption/1", "registry_events": 0,
                          "registry_prefix_sha256": sha(b"[]"), "last_seen_utc": stamp(-2), "consumed": {}})
        self.request = {"schema": "v3.a5.admission_request/1", "evidence_class": "TEST_ONLY", "domain": "SYNTHETIC_BENCH",
                        "bindings": bindings, "effect": {"carrier": "P64", "translation_mm": [1, 1, 1],
                                                        "rotation_xyzw": [0, 0, 0, 1]},
                        "submission": {"raw_root": self.raw.relative_to(ROOT).as_posix(),
                                       "packet": self.packet.name, "review": self.review.name}}
        self.review_fields = {"schema": "v3.a5.review/1", "id": "test-decision", "reviewer_id": "test-reviewer",
                              "evidence_class": "TEST_ONLY", "domain": "SYNTHETIC_BENCH", "bindings": bindings,
                              "policy_sha256": self.policy_sha, "issued_at_utc": stamp(-2), "expires_at_utc": stamp(15),
                              "disposition": "APPROVE_BOUNDED_EXPERIMENT", "bounds": self.bounds}
        self.prepare()

    def prepare(self, record=None, signature_role="review", **review_changes):
        packet_sha = save(self.packet, {"schema": "v3.a4.measurement_packet/1", "configuration": self.configuration,
                                        "records": [self.record if record is None else record]})
        review = {**self.review_fields, "packet_sha256": packet_sha, **review_changes}
        review_sha = self.signing.envelope(self.review, "review", review, signature_role)
        self.issue = {"kind": "ISSUED", "id": review["id"], "review_sha256": review_sha, "at_utc": stamp(-1)}
        self.set_events([self.issue])

    def set_events(self, events):
        self.signing.envelope(self.registry, "registry", {"schema": "v3.a5.registry/1", "evidence_class": "TEST_ONLY",
                                                         "events": events}, "register")

    def run(self, name, request=None, trust_path=None, trust_sha=None, sandbox=None, mutation=False, specify_trust=True):
        request_path = self.work / f"{name}.json"
        request_sha = save(request_path, self.request if request is None else request)
        output = self.work / f"result-{name}"
        command = [self.core, "v3-build" if mutation else "v3-admission", "--root", ROOT,
                   "--request", request_path, "--sandbox", sandbox or self.sandbox, "--output", output]
        if specify_trust:
            command.extend(["--a5-trust", trust_path or self.trust_path,
                            "--a5-trust-sha256", self.trust_sha if trust_sha is None else trust_sha])
        if mutation:
            command.extend(["--freecad-python", "UNUSED_TEST_ONLY", "--t0-validator", "UNUSED_TEST_ONLY"])
        result = subprocess.run(list(map(str, command)), capture_output=True, timeout=20)
        receipt = output / "admission.json"
        assert receipt.is_file(), (name, result.returncode, result.stderr.decode(errors="replace"))
        report = read(receipt)
        assert list(output.iterdir()) == [receipt] and report["finalized"]
        assert report["request_sha256"] == request_sha and report["candidate_transactions"] == 0
        assert report["construction_result"] == report["physical_reception"] == "NOT_RUN"
        assert report["cartographer_mutation"] == "DENY"
        return {"case": name, "exit_code": result.returncode, "request_sha256": request_sha,
                "receipt_sha256": sha(receipt.read_bytes()), "receipt": report}


def check(result, reason=None, technical_reason=None):
    report = result["receipt"]
    if reason is None:
        assert result["exit_code"] == 0 and report["admission"]["decision"] == "ALLOW" and report["authority"] == "TEST_ONLY", result
        assert report["admission"]["execution_scope"] == "TEST_ONLY" and report["admission"]["consumed"], result
        assert report["review"]["status"] == "SIGNATURE_VERIFIED" and report["review"]["signature_algorithm"] == "Ed25519", result
        assert report["technical"]["status"] == "PENDING_AUTHORIZED_REVIEW", result
    else:
        assert result["exit_code"] == 2 and report["reason"] == reason and report["authority"] == "DENY", result
        assert report["admission"]["decision"] == "DENY" and report["admission"]["execution_scope"] == "READ_ONLY_IMPACT", result
    if technical_reason is not None:
        assert report["technical"]["records"][0]["reason"] == technical_reason, result
    return result


def exercise(core, openssl, work):
    signing = SigningFixtures(openssl, work)
    fixture = AdmissionFixture(core, work / "authority", signing)
    results = []

    def reject(case, reason, technical_reason=None, **kwargs):
        results.append(check(fixture.run(case, **kwargs), reason, technical_reason))

    reject("not-configured", "REVIEW_NOT_CONFIGURED", specify_trust=False)
    reject("before-review", "SIGNED_REVIEW_REQUIRED", request={**fixture.request,
           "submission": {**fixture.request["submission"], "review": None}})
    reject("wrong-trust-pin", "TRUST_SHA256_MISMATCH", trust_sha="0" * 64)
    self_trust = fixture.raw / "self-issued-trust.json"
    trust_sha = save(self_trust, {**fixture.trust, "reviewer_id": "test-operator"})
    reject("self-issued-trust", "TRUST_INSIDE_SUBMISSION_OR_REDIRECTED", trust_path=self_trust, trust_sha=trust_sha)
    fixture.policy.write_bytes(fixture.policy.read_bytes() + b"\n")
    reject("tampered-material-policy", "MATERIAL_POLICY_SHA256_MISMATCH")
    fixture.policy.write_bytes(fixture.policy.read_bytes()[:-1])
    fixture.prepare(signature_role="untrusted")
    reject("fake-signer", "SIGNATURE_INVALID")
    fixture.prepare(reviewer_id="test-operator")
    reject("self-declared-reviewer", "REVIEWER_OR_DISPOSITION_NOT_APPROVED")
    fixture.prepare()
    base_envelope = read(fixture.review)
    save(fixture.review, {**base_envelope, "signature_b64": b64encode(bytes(64)).decode()})
    reject("signature-unverified", "SIGNATURE_INVALID")
    fixture.prepare(policy_sha256="0" * 64)
    reject("signed-wrong-policy", "SIGNED_REVIEW_BINDING_MISMATCH")
    fixture.prepare(issued_at_utc=stamp(1))
    reject("review-from-future", "REVIEW_EXPIRED_OR_IN_FUTURE")
    fixture.prepare(expires_at_utc=stamp(-1))
    reject("expired", "REVIEW_EXPIRED_OR_IN_FUTURE")

    for case, field, value in (("different-occurrence", "occurrence", "anchor:other"),
                               ("different-operation", "operation", "RELOCATE_SUPPORT"),
                               ("different-lot-binding", "lot_sha256", "0" * 64),
                               ("different-model-commit", "model_version", "new-model"),
                               ("omitted-receiving-check", "required_checks", CHECKS[:-1])):
        reject(case, "TRUST_BINDING_MISMATCH", request={**fixture.request,
               "bindings": {**fixture.request["bindings"], field: value}})

    ref = fixture.record
    technical_cases = [
        ("raw-sha-changed", "sources", "raw", {**ref["sources"]["raw"], "sha256": "0" * 64}, "SOURCE_SHA256_MISMATCH"),
        ("manufacturer-not-applicable", "sources", "manufacturer_document", fixture.alternate, "MANUFACTURER_DOCUMENT_MISMATCH"),
        ("different-lot", "identity", "lot_or_serial", "OTHER-LOT", "LOT_VARIANT_OR_REVISION_MISMATCH"),
        ("different-revision", "identity", "revision", "TEST-FT232RL", "LOT_VARIANT_OR_REVISION_MISMATCH"),
        ("datum-matrix-altered", "frame", "parent_to_local", ref["frame"]["local_to_parent"], "FRAME_INVERSE_MISMATCH"),
        ("nonrigid-matrix", "frame", "local_to_parent", [1, 1, 0, 8, 0, 1, 0, 4, 0, 0, 1, 1, 0, 0, 0, 1], "NON_RIGID_FRAME"),
        ("tolerance-document-missing", "sources", "tolerance_document",
         {**ref["sources"]["tolerance_document"], "path": "absent.fixture"}, "Fichier absent : absent.fixture"),
        ("nc-connected", "facts", "nc_connected", True, "TOPOLOGY_OR_APPLICABILITY_MISMATCH"),
        ("j2-j3-ambiguous", "facts", "jbd_port", "J2_OR_J3", "TOPOLOGY_OR_APPLICABILITY_MISMATCH"),
    ]
    for case, group, field, value, reason in technical_cases:
        fixture.prepare({**ref, group: {**ref[group], field: value}})
        reject(case, "TECHNICAL_REVIEW_REJECTED", reason)
    inverted = {**ref["frame"], "local_to_parent": [1, 0, 0, 8, 0, -1, 0, 4, 0, 0, -1, 1, 0, 0, 0, 1],
                "parent_to_local": [1, 0, 0, -8, 0, -1, 0, 4, 0, 0, -1, 1, 0, 0, 0, 1]}
    fixture.prepare({**ref, "frame": inverted})
    reject("normal-inverted", "TECHNICAL_REVIEW_REJECTED", "FRAME_ORIENTATION_MISMATCH")
    fixture.prepare({**ref, "capture": {**ref["capture"], "author": "test-reviewer"}})
    reject("reviewer-is-submitter", "REVIEWER_IS_SUBMITTER")
    fixture.prepare({**ref, "measurement": {**ref["measurement"], "value": 0.095}})
    reject("uncertainty-covers-limit", "TECHNICAL_REVIEW_INCONCLUSIVE", "TOLERANCE_INTERVAL")
    fixture.prepare({**ref, "measurement": {**ref["measurement"], "value": 0.3}})
    reject("floating-anchor", "TECHNICAL_REVIEW_REJECTED", "TOLERANCE_INTERVAL")

    fixture.prepare()
    for name, field, value, reason in (("fraudulent-carrier", "carrier", "P66", "CARRIER_NOT_APPROVED"),
                                       ("outside-pose", "translation_mm", [1, 2.1, 1], "TRANSLATION_OUTSIDE_BOUNDED_DOMAIN"),
                                       ("wrong-rotation", "rotation_xyzw", [1, 0, 0, 0], "ROTATION_NOT_APPROVED")):
        reject(name, reason, request={**fixture.request, "effect": {**fixture.request["effect"], field: value}})
    fixture.prepare(bounds={**fixture.bounds, "max_translation_mm": [3, 3, 3]})
    reject("signed-widened-pose", "TRANSLATION_OUTSIDE_BOUNDED_DOMAIN")
    fixture.prepare()
    fixture.profile.write_bytes(PROFILE.read_bytes() + b"\n")
    reject("xlink-profile-revised-after-review", "NATIVE_PROFILE_SHA256_MISMATCH")
    shutil.copyfile(PROFILE, fixture.profile)
    dependency_name = next(iter(fixture.request["bindings"]["xlink_dependencies"]))
    dependency = fixture.sandbox / dependency_name
    original = dependency.read_bytes()
    dependency.write_bytes(original + b"changed dependency")
    reject("xlink-copy-revised-after-review", "XLINK_DEPENDENCY_SHA256_MISMATCH")
    dependency.write_bytes(original)

    reject("try-construction-on-active-reference", "ACTIVE_REFERENCE_OR_NONPRIVATE_SANDBOX", mutation=True,
           sandbox=ROOT / "hardware/mecanique/cartographe")
    reject("test-only-domain-escalation", "EVIDENCE_CLASS_OR_DOMAIN_DENIED", request={**fixture.request,
           "domain": "CARTOGRAPHER_PRIVATE_CAD"})
    reject("test-key-as-physical-authority", "REVIEW_NOT_CONFIGURED", request={**fixture.request,
           "evidence_class": "PHYSICAL_MEASURED", "domain": "CARTOGRAPHER_PRIVATE_CAD"})
    fixture.set_events([fixture.issue, fixture.issue])
    reject("duplicate-signed-id", "DUPLICATE_DECISION_ID")
    fixture.set_events([])
    reject("signed-but-unregistered", "DECISION_NOT_REGISTERED")
    fixture.set_events([fixture.issue])
    original_state = fixture.state.read_bytes()
    fixture.state.unlink()
    reject("missing-consumption-state", "REPLAY_STATE_NOT_PROVISIONED")
    fixture.state.write_bytes(original_state)
    reject("test-admission-does-not-execute-native", "TEST_ONLY_ADMISSION_NO_CONSTRUCTION", mutation=True)
    approved = check(fixture.run("registered-synthetic-admission"))
    results.append(approved)
    consumption = read(fixture.state)["consumed"][fixture.issue["id"]]
    assert consumption["request_sha256"] == approved["request_sha256"]
    assert consumption["review_sha256"] == approved["receipt"]["review"]["sha256"]
    copied_admission = fixture.raw / "copied-test-only-admission.json"
    save(copied_admission, approved["receipt"])
    reject("copy-synthetic-admission-to-cartographer", "EVIDENCE_CLASS_OR_DOMAIN_DENIED", mutation=True,
           request={**fixture.request, "domain": "CARTOGRAPHER_PRIVATE_CAD",
                    "submission": {**fixture.request["submission"], "review": copied_admission.name}})
    reject("double-use", "DECISION_ALREADY_USED")
    fixture.set_events([fixture.issue, {**fixture.issue, "kind": "REVOKED", "at_utc": stamp()}])
    reject("signed-revocation", "DECISION_REVOKED")
    fixture.set_events([fixture.issue])
    reject("registry-rollback", "REGISTRY_ROLLBACK")
    state = read(fixture.state)
    save(fixture.state, {**state, "last_seen_utc": stamp(1)})
    reject("clock-rollback", "CLOCK_ROLLBACK")

    concurrent = AdmissionFixture(core, work / "concurrent", signing)
    with ThreadPoolExecutor(max_workers=2) as pool:
        simultaneous = list(pool.map(concurrent.run, ("concurrent-consumption-a", "concurrent-consumption-b")))
    assert sorted(result["exit_code"] for result in simultaneous) == [0, 2], simultaneous
    for result in simultaneous:
        reason = result["receipt"].get("reason")
        assert reason in (None, "AUTHORITY_STATE_BUSY", "DECISION_ALREADY_USED"), result
        results.append(check(result, reason))
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--core", required=True, type=Path)
    parser.add_argument("--openssl", required=True, type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    runtime = ROOT / ".runtime"
    runtime.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="a5-test-", dir=runtime) as temporary:
        checked = exercise(args.core.resolve(strict=True), args.openssl.resolve(strict=True), Path(temporary))
    if args.out:
        save(args.out, {"schema": "v3.a5.adversarial/1", "evidence_class": "TEST_ONLY", "case_count": len(checked),
                        "status": "PASS", "cases": checked, "core_sha256": sha(args.core.read_bytes()),
                        "cartographer_mutation": "DENY", "physical_reception": "NOT_RUN"})
    print(f"{len(checked)} cas A.5, portée TEST_ONLY et cartographe DENY")
