"""Rejeu défensif du raccordement signé A.6 sur le banc synthétique."""

import argparse
from base64 import b64decode, b64encode
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from hashlib import sha256
import hmac
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import time

from test_v3_a5_authority import AdmissionFixture, ROOT, SigningFixtures, data, read, save, sha, stamp


PROFILE = ROOT / "docs/electromechanical_v3/bench_b1_workholding/profile.json"
MODEL = read(PROFILE)
PACKAGE = "v3.a6.private_evidence/1"
STATES = ["REQUESTED", "AUTHORIZED_RESERVED", "BUILDING_PRIVATE", "BUILT",
          "INDEPENDENTLY_VALIDATED", "COMMITTED_PRIVATE"]


class A6Fixture(AdmissionFixture):
    def __init__(self, core, work, signing, translation=(0, 0, 0), size=(8, 8, 3)):
        super().__init__(core, work, signing)
        self.journal = self.trusted / "a6-journal.jsonl"
        self.key_file = self.trusted / "a6-journal.key"
        self.key = secrets.token_bytes(32)
        self.key_file.write_bytes(self.key)
        payload = data({"schema": "v3.a6.journal_event/1", "sequence": 0, "previous_mac": "0" * 64,
                        "state": "GENESIS", "decision_id": "", "at_utc": stamp(-3).replace("Z", ".000Z"),
                        "detail": {}})
        self.journal.write_bytes(data({"event_b64": b64encode(payload).decode(),
                                       "mac": hmac.digest(self.key, payload, sha256).hex()}) + b"\n")
        for name, expected in MODEL["dependencies"].items():
            out = self.sandbox / name
            out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / MODEL["source"] / name, out)
            assert sha(out.read_bytes()) == expected

        shutil.copyfile(PROFILE, self.profile)
        subject = "anchor:iso-carrier"
        old_subject = self.record["subject"]
        self.record["subject"] = subject
        policy = read(self.policy)
        policy["identities"][subject] = policy["identities"].pop(old_subject)
        policy["checks"][self.record["check_id"]]["subject"] = subject
        self.policy_sha = save(self.policy, policy)
        self.bounds = {**self.bounds, "min_translation_mm": [-1, 0, 0], "max_translation_mm": [0, 0, 0]}
        bindings = {**self.request["bindings"], "model_version": MODEL["model_version"], "occurrence": subject,
                    "lot_sha256": sha(data(policy["identities"])), "profile_sha256": sha(PROFILE.read_bytes()),
                    "xlink_dependencies": MODEL["dependencies"]}
        self.trust = {**self.trust, "schema": "v3.a6.trust/1", "bindings": bindings,
                      "bounds": self.bounds, "source_root": MODEL["source"], "material_policy_sha256": self.policy_sha,
                      "journal_key_sha256": sha(self.key)}
        self.trust_sha = save(self.trust_path, self.trust)
        effect = {"carrier": "P64", "translation_mm": list(translation), "rotation_xyzw": [0, 0, 0, 1],
                  "size_mm": list(size)}
        self.request.update(schema="v3.a6.admission_request/1", bindings=bindings, effect=effect)
        self.review_fields.update(schema="v3.a6.review/1", bindings=bindings, policy_sha256=self.policy_sha,
                                  bounds=self.bounds, trust_sha256=self.trust_sha,
                                  authorized_effect=effect, evidence_package=PACKAGE)
        self.prepare()

    def command(self, name, request=None, *, sandbox=None, core=None, trust_path=None, trust_sha=None,
                request_path=None, output=None):
        if request_path is None:
            request_path = self.work / f"{name}.json"
            save(request_path, self.request if request is None else request)
        output = self.work / f"result-{name}" if output is None else output
        parts = [core or self.core, "v3-build", "--root", ROOT, "--request", request_path,
                 "--sandbox", sandbox or self.sandbox, "--output", output,
                 "--a5-trust", trust_path or self.trust_path,
                 "--a5-trust-sha256", self.trust_sha if trust_sha is None else trust_sha]
        return list(map(str, parts)), Path(output)

    def invoke(self, name, request=None, *, fault=None, **options):
        command, output = self.command(name, request, **options)
        env = {**os.environ, "QT_QPA_PLATFORM": "offscreen"}
        env.pop("L5_A6_TEST_FAULT", None)
        if fault:
            env["L5_A6_TEST_FAULT"] = fault
        process = subprocess.run(command, capture_output=True, timeout=210, env=env)
        receipt_path = output / "admission.json"
        return {"code": process.returncode, "report": read(receipt_path) if receipt_path.is_file() else None,
                "stdout": process.stdout.decode(errors="replace"), "stderr": process.stderr.decode(errors="replace"),
                "output": output}

    def journal_events(self):
        previous = "0" * 64
        events = []
        for line in self.journal.read_bytes().splitlines():
            envelope = json.loads(line)
            payload = b64decode(envelope["event_b64"], validate=True)
            assert hmac.compare_digest(envelope["mac"], hmac.digest(self.key, payload, sha256).hex())
            assert set(envelope) == {"event_b64", "mac"}
            event = json.loads(payload)
            assert event["sequence"] == len(events) and event["previous_mac"] == previous
            previous = envelope["mac"]
            events.append(event)
        return events

    def journal_states(self):
        return [event["state"] for event in self.journal_events() if event["decision_id"]]

    def snapshot(self):
        return {name: sha((ROOT / MODEL["source"] / name).read_bytes()) for name in MODEL["dependencies"]}


def assert_denied(result, reason=None):
    assert result["code"] == 2, result
    report = result["report"]
    assert report["admission"]["decision"] == "DENY" and report["cartographer_mutation"] == "DENY", result
    assert report["physical_reception"] == "NOT_RUN" and "publication" not in report, result
    if reason is not None:
        assert report["reason"] == reason, result
    return report


def check_commit(fixture, result):
    assert result["code"] == 0, result
    report = result["report"]
    assert report["transaction_state"] == "COMMITTED_PRIVATE" and report["admission"]["consumed"], result
    assert report["admission"]["decision"] == "ALLOW" and report["admission"]["execution_scope"] == "TEST_ONLY", result
    assert report["construction_result"] == report["native_validation"] == "PASS", result
    assert report["physical_reception"] == "NOT_RUN" and report["cartographer_mutation"] == "DENY", result
    assert fixture.journal_states() == STATES
    publication = report["publication"]
    native = result["output"] / publication["directory"]
    assert native.is_relative_to(result["output"]) and publication["schema"] == PACKAGE
    assert all(sha((native / name).read_bytes()) == value for name, value in publication["sha256"].items())
    build = read(native / "build.json")
    candidate = read(native / "candidate-validation.json")
    baseline = read(native / "baseline-validation.json")
    t0 = read(native / "t0-crosscheck.json")
    assert len({build["pid"], candidate["pid"], baseline["pid"]}) == 3
    assert len({build["worker_id"], candidate["worker_id"], baseline["worker_id"]}) == 3
    assert build["status"] == candidate["status"] == "PASS" and candidate["documents_closed"]
    assert t0["exit_code"] == 0
    checks = {check["id"]: check["status"] for check in candidate["checks"]}
    for check in fixture.request["bindings"]["required_checks"]:
        if check not in {"VERIFY_IMMUTABLE_SOURCES", "VALIDATE_T0"}:
            assert checks[check] == "PASS", checks
    audit = fixture.journal_events()[-1]["detail"]
    receipt_sha = sha((result["output"] / "admission.json").read_bytes())
    assert audit["receipt_sha256"] == receipt_sha and audit["receipt"] == report
    validation = {"separate_processes": True, "closed_documents": True, "checks": checks, "t0": "PASS",
                  "reference_and_input": "PASS",
                  "artifact_sha256": {name: publication["sha256"][name] for name in (
                      "build.json", "candidate-validation.json", "baseline-validation.json", "t0-crosscheck.json",
                      "t0_run_manifest.json")},
                  "native_sha256": {name: value for name, value in publication["sha256"].items()
                                    if name.startswith("cad/")}}
    transaction = {"status": "PASS", "effect": fixture.request["effect"], "states": STATES,
                   "receipt_sha256": receipt_sha, "journal_authenticated": True}
    return transaction, validation


def positive(factory):
    transactions = {}
    validation = {}
    for name, translation, size in (("nominal", (0, 0, 0), (8, 8, 3)),
                                    ("shifted", (-0.5, 0, 0), (7.9, 8, 3))):
        fixture = factory(name, translation=translation, size=size)
        before = fixture.snapshot()
        transactions[name], validation[name] = check_commit(fixture, fixture.invoke("first"))
        assert fixture.snapshot() == before == MODEL["dependencies"]
    entry = "cad/" + MODEL["entry"]
    assert validation["nominal"]["native_sha256"][entry] != validation["shifted"]["native_sha256"][entry]
    return transactions, validation


def fault_cases(factory):
    cases = {}
    for checkpoint, expected, code in (
            ("before-launch", STATES[:2], 86),
            ("during-native-save", STATES[:3] + ["QUARANTINED"], 2),
            ("after-build", STATES[:4], 86),
            ("during-publication", STATES, 86)):
        fixture = factory(checkpoint)
        before = fixture.snapshot()
        shadow = fixture.state.read_bytes()
        result = fixture.invoke("interrupted", fault=checkpoint)
        assert result["code"] == code, result
        assert fixture.journal_states() == expected, (checkpoint, fixture.journal_states(), result)
        receipt_missing = result["report"] is None
        if checkpoint == "during-native-save":
            assert "CRASH" in result["report"].get("native_reason", "") or "code 87" in str(result["report"]), result
        else:
            assert receipt_missing, result
        # A lost receipt and an older A.5 consumption copy cannot remove the A.6 fence.
        fixture.state.write_bytes(shadow)
        deny = assert_denied(fixture.invoke("replay"), "DECISION_ALREADY_USED")
        terminal = "COMMITTED_PRIVATE" if checkpoint == "during-publication" else "QUARANTINED"
        assert fixture.journal_states()[-1] == terminal and fixture.snapshot() == before
        cases[checkpoint] = {"status": "PASS", "code": code, "missing_receipt": receipt_missing,
                            "observed_before_reopen": expected, "terminal": terminal,
                            "replay": deny["reason"], "reference_integrity": "PASS"}

    fixture = factory("concurrent")
    before = fixture.snapshot()
    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(fixture.invoke, "first", fault="hold-after-reserve")
        until = time.monotonic() + 15
        while time.monotonic() < until and not first.done() and "AUTHORIZED_RESERVED" not in fixture.journal_states():
            time.sleep(0.05)
        second = executor.submit(fixture.invoke, "second")
        committed = first.result()
        denied = assert_denied(second.result())
    assert denied["reason"] in {"AUTHORITY_STATE_BUSY", "DECISION_ALREADY_USED"}, denied
    check_commit(fixture, committed)
    assert fixture.snapshot() == before
    cases["concurrency"] = {"status": "PASS", "commits": 1, "second_reason": denied["reason"],
                            "reference_integrity": "PASS"}
    return cases


def run(args):
    work = args.output.resolve()
    assert work.is_relative_to(ROOT / ".runtime") and not work.exists()
    work.mkdir(parents=True)
    keys = work / "keys"
    keys.mkdir()
    signing = SigningFixtures(args.openssl.resolve(), keys)

    def factory(name, **params):
        return A6Fixture(args.core.resolve(), work / name, signing, **params)

    if args.phase in ("all", "positive"):
        transactions, validation = positive(factory)
        save(work / "test_only_transactions.json", {"schema": "v3.a6.test_only_transactions/1",
            "binary_sha256": sha(args.core.read_bytes()), "results": transactions})
        save(work / "native_validation.json", {"schema": "v3.a6.native_validation/1", "results": validation})
    if args.phase in ("all", "faults"):
        faults = fault_cases(factory)
        save(work / "fault_injection.json", {"schema": "v3.a6.fault_injection/1",
            "binary_sha256": sha(args.core.read_bytes()), "results": faults})
    if args.phase in ("all", "adversarial"):
        from test_v3_a6_adversarial import exercise
        cases = exercise(factory, args.no_crypto.resolve())
        save(work / "adversarial.json", {"schema": "v3.a6.adversarial/1",
            "binary_sha256": sha(args.core.read_bytes()), "results": cases})
    print(f"A.6 {args.phase} PASS")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for argument in ("core", "openssl", "output"):
        parser.add_argument("--" + argument, required=True, type=Path)
    parser.add_argument("--no-crypto", type=Path)
    parser.add_argument("--phase", choices=("all", "positive", "faults", "adversarial"), default="all")
    options = parser.parse_args()
    if options.phase in ("all", "adversarial") and not options.no_crypto:
        parser.error("--no-crypto est requis")
    run(options)
