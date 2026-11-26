"""Refus et invariants des admissions V3-A.6 sur des entrées de test privées."""

from base64 import b64encode
import os
import subprocess

from test_v3_a5_authority import read, save, sha, stamp


def exercise(factory, no_crypto):
    cases = {}

    def reject(fixture, name, reason, request=None, *, reserved=False, record_reason=None, **options):
        before = fixture.snapshot()
        observed = fixture.invoke(name, request, **options)
        report = observed["report"]
        assert observed["code"] == 2 and report and report["finalized"], observed
        assert report["reason"] == reason and report["admission"]["decision"] == "DENY", observed
        assert report["cartographer_mutation"] == "DENY" and report["physical_reception"] == "NOT_RUN", observed
        assert "publication" not in report and report["candidate_transactions"] == 0, observed
        assert fixture.snapshot() == before
        if not reserved:
            assert report["construction_result"] == "NOT_RUN" and fixture.journal_states() == [], observed
        if record_reason is not None:
            assert report["technical"]["records"][0]["reason"] == record_reason, observed
        cases[name] = {"status": "PASS", "reason": reason, "code": observed["code"],
                       "transaction_state": report["transaction_state"], "reference_integrity": "PASS",
                       "receipt_sha256": sha((observed["output"] / "admission.json").read_bytes())}
        if record_reason is not None:
            cases[name]["technical_reason"] = record_reason

    def reject_path(fixture, name, expected, **options):
        before = fixture.snapshot()
        observed = fixture.invoke(name, **options)
        assert observed["code"] == 1 and observed["report"] is None, observed
        assert expected in observed["stderr"], observed
        assert fixture.snapshot() == before and fixture.journal_states() == []
        cases[name] = {"status": "PASS", "reason": expected, "code": observed["code"],
                       "transaction_state": "NOT_RESERVED", "reference_integrity": "PASS"}

    fixture = factory("review-integrity")
    envelope = read(fixture.review)
    save(fixture.review, {**envelope, "signature_b64": b64encode(bytes(64)).decode()})
    reject(fixture, "modified-signature", "SIGNATURE_INVALID")
    fixture.prepare(signature_role="untrusted")
    reject(fixture, "unauthorized-signer", "SIGNATURE_INVALID")
    fixture.prepare(reviewer_id="test-operator")
    reject(fixture, "unapproved-reviewer", "REVIEWER_OR_DISPOSITION_NOT_APPROVED")
    fixture.prepare(expires_at_utc=stamp(-1))
    reject(fixture, "expired-review", "REVIEW_EXPIRED_OR_IN_FUTURE")
    fixture.prepare(evidence_package=None)
    reject(fixture, "missing-review-package", "SIGNED_NATIVE_EFFECT_OR_PACKAGE_MISMATCH")
    fixture.prepare()
    reject(fixture, "missing-signed-review", "SIGNED_REVIEW_REQUIRED",
           {**fixture.request, "submission": {**fixture.request["submission"], "review": None}})
    policy_content = fixture.policy.read_bytes()
    fixture.policy.unlink()
    reject(fixture, "missing-review-procedure", "Fichier absent : policy.json")
    fixture.policy.write_bytes(policy_content)
    reject(fixture, "changed-signed-pose", "SIGNED_NATIVE_EFFECT_OR_PACKAGE_MISMATCH",
           {**fixture.request, "effect": {**fixture.request["effect"], "translation_mm": [-0.5, 0, 0]}})
    reject(fixture, "changed-signed-size", "SIGNED_NATIVE_EFFECT_OR_PACKAGE_MISMATCH",
           {**fixture.request, "effect": {**fixture.request["effect"], "size_mm": [7.9, 8, 3]}})
    reject(fixture, "no-openssl", "REVIEW_NOT_CONFIGURED", core=no_crypto)
    reject(fixture, "test-trust-for-physical-domain", "PHYSICAL_ADMISSION_NOT_CONFIGURED",
           {**fixture.request, "evidence_class": "PHYSICAL_MEASURED", "domain": "CARTOGRAPHER_PRIVATE_CAD"})
    reject(fixture, "synthetic-domain-escalation", "EVIDENCE_CLASS_OR_DOMAIN_DENIED",
           {**fixture.request, "domain": "CARTOGRAPHER_PRIVATE_CAD"})

    fixture = factory("bounds-and-lot")
    outside = {**fixture.request["effect"], "translation_mm": [1, 0, 0]}
    fixture.prepare(authorized_effect=outside)
    reject(fixture, "signed-pose-outside-bounds", "TRANSLATION_OUTSIDE_BOUNDED_DOMAIN",
           {**fixture.request, "effect": outside})
    other_carrier = {**fixture.request["effect"], "carrier": "P66"}
    fixture.prepare(authorized_effect=other_carrier)
    reject(fixture, "signed-carrier-without-applicable-lot", "CARRIER_EVIDENCE_MISMATCH",
           {**fixture.request, "effect": other_carrier})
    fixture.prepare()
    reject(fixture, "unsupported-carrier", "CARRIER_NOT_APPROVED",
           {**fixture.request, "effect": {**fixture.request["effect"], "carrier": "P99"}})
    identity = {key: value for key, value in fixture.record["identity"].items() if key != "lot_or_serial"}
    fixture.prepare({**fixture.record, "identity": identity})
    reject(fixture, "missing-lot-identity", "TECHNICAL_REVIEW_REJECTED", record_reason="MISSING_FIELDS")

    fixture = factory("native-size-limit", size=(8.5, 8, 3))
    reject(fixture, "signed-size-outside-native-domain", "AUTHORIZED_NATIVE_EFFECT_OUTSIDE_FIXTURE", reserved=True)
    assert fixture.journal_states() == ["REQUESTED", "AUTHORIZED_RESERVED", "QUARANTINED"]
    reject(fixture, "quarantined-decision-replay", "DECISION_ALREADY_USED", reserved=True)
    assert fixture.journal_states()[-1] == "QUARANTINED"

    fixture = factory("p66-native-mapping")
    effect = {**fixture.request["effect"], "carrier": "P66"}
    fixture.bounds["carrier"] = "P66"
    fixture.record["facts"]["carrier"] = "P66"
    procedure = read(fixture.policy)
    procedure["checks"][fixture.record["check_id"]]["facts"]["carrier"] = "P66"
    fixture.policy_sha = save(fixture.policy, procedure)
    fixture.trust["material_policy_sha256"] = fixture.policy_sha
    fixture.trust_sha = save(fixture.trust_path, fixture.trust)
    fixture.request["effect"] = effect
    fixture.review_fields.update(authorized_effect=effect, policy_sha256=fixture.policy_sha,
                                 trust_sha256=fixture.trust_sha)
    fixture.prepare()
    reject(fixture, "p66-no-native-mapping", "AUTHORIZED_NATIVE_FIXTURE_UNSUPPORTED", reserved=True)
    assert fixture.journal_states() == ["REQUESTED", "AUTHORIZED_RESERVED", "QUARANTINED"]

    fixture = factory("registry")
    registry = read(fixture.registry)
    initial_state = fixture.state.read_bytes()
    save(fixture.registry, {**registry, "signature_b64": b64encode(bytes(64)).decode()})
    reject(fixture, "replaced-registry", "SIGNATURE_INVALID")
    events = [fixture.issue, {**fixture.issue, "kind": "REVOKED", "at_utc": stamp()}]
    fixture.set_events(events)
    reject(fixture, "registered-revocation", "DECISION_REVOKED")
    fixture.set_events([fixture.issue])
    reject(fixture, "registry-rollback", "REGISTRY_ROLLBACK")
    fixture.set_events([fixture.issue, {**events[-1], "at_utc": stamp(-1)}])
    reject(fixture, "registry-history-replaced", "REGISTRY_HISTORY_CHANGED")
    fixture.state.write_bytes(initial_state)
    fixture.set_events([fixture.issue])
    reject(fixture, "registry-rollback-with-stale-legacy-state", "REGISTRY_ROLLBACK")

    fixture = factory("consumed-decision")
    state = read(fixture.state)
    state["consumed"][fixture.issue["id"]] = {
        "review_sha256": fixture.issue["review_sha256"], "request_sha256": "0" * 64, "consumed_at_utc": stamp(-1)}
    save(fixture.state, state)
    reject(fixture, "already-consumed", "DECISION_ALREADY_USED")
    save(fixture.state, {**state, "last_seen_utc": stamp(1)})
    reject(fixture, "clock-rollback", "CLOCK_ROLLBACK")

    fixture = factory("xlink-and-paths")
    # Mutate only disposable copies. The sealed checkout is measured separately.
    profile_bytes = fixture.profile.read_bytes()
    assert fixture.profile.is_relative_to(fixture.trusted)
    fixture.profile.write_bytes(profile_bytes + b"\n")
    reject(fixture, "modified-profile", "NATIVE_PROFILE_SHA256_MISMATCH")
    fixture.profile.write_bytes(profile_bytes)
    dependency = fixture.sandbox / next(iter(fixture.request["bindings"]["xlink_dependencies"]))
    native_bytes = dependency.read_bytes()
    dependency.write_bytes(native_bytes + b"TEST_ONLY alteration")
    reject(fixture, "modified-xlink", "XLINK_DEPENDENCY_SHA256_MISMATCH")
    dependency.write_bytes(native_bytes)
    alias = fixture.work / "shared-native.FCStd"
    os.link(dependency, alias)
    reject(fixture, "hardlinked-xlink", "SHARED_FILE")
    alias.unlink()
    reject_path(fixture, "sandbox-traversal", "A6_PATH_NOT_CANONICAL",
                sandbox=fixture.sandbox / ".." / fixture.sandbox.name)
    redirect = fixture.work / "redirected-sandbox"
    if os.name == "nt":
        subprocess.run(["cmd.exe", "/d", "/c", "mklink", "/j", str(redirect), str(fixture.sandbox)],
                       check=True, capture_output=True, timeout=10)
    else:
        redirect.symlink_to(fixture.sandbox, target_is_directory=True)
    reject_path(fixture, "redirected-sandbox", "Chemin de sandbox XLink redirigé", sandbox=redirect)
    reject_path(fixture, "output-overlaps-trust", "A6_OUTPUT_NOT_PRIVATE_OR_OVERLAPPING",
                output=fixture.trusted / "overlapping-output")
    return cases
