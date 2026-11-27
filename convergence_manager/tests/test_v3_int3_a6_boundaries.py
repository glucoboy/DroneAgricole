"""Rejoue les refus entre un plan C.3 mesuré et une revue A.6 Workholding."""

import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import shutil
import subprocess
import sys

PROJECT = Path.cwd().resolve()
sys.path.insert(0, str(PROJECT / "convergence_manager/tests"))

from test_v3_a6_transactions import A6Fixture, ROOT, SigningFixtures, read, save, sha


def digest(path):
    return sha(path.read_bytes())


def snapshot(root):
    return {path.relative_to(root).as_posix(): digest(path)
            for path in root.rglob("*.FCStd") if path.is_file()}


def c3_native_witness(root, plan):
    assert root.is_relative_to(ROOT / ".runtime")
    campaign = root / "campaign.json"
    receipt = read(campaign)
    assert receipt["status"] == "PASS" and receipt["candidate_state"] == "CANDIDATE", receipt
    assert receipt["execution_scope"] == "BENCH_TEST_ONLY" and receipt["plan_schema"] == "v3.mutation_plan/4", receipt
    assert receipt["plan_sha256"] == digest(plan), receipt
    job_path = root / "candidate-job.json"
    job = read(job_path)
    assert "spatial_contract" in job and "authorized_effect" not in job, job
    assert "authority_schema" not in receipt and "authorized_effect" not in receipt, receipt
    assert all(row["execution_scope"] == "BENCH_TEST_ONLY" for row in receipt["admissions"]), receipt
    measurement = root / "candidate-validation.json"
    checked = read(measurement)
    assert checked["status"] == "PASS" and checked["reopened"] and checked["documents_closed"], checked
    assert snapshot(root / "cad") == receipt["native_sha256"] == checked["inputs_sha256"]
    t0 = root / "t0-crosscheck.json"
    assert read(t0)["exit_code"] == 0
    return {"status": "PASS", "execution_scope": receipt["execution_scope"],
            "campaign_sha256": digest(campaign), "candidate_job_sha256": digest(job_path),
            "candidate_validation_sha256": digest(measurement), "t0_crosscheck_sha256": digest(t0),
            "native_sha256": receipt["native_sha256"]}


def boundary_refusal(fixture, name, reason, *, request=None, request_path=None,
                     sandbox=None, trust_path=None, trust_sha=None, options=(), cli=False):
    command, output = fixture.command(name, request, request_path=request_path, sandbox=sandbox,
                                      trust_path=trust_path, trust_sha=trust_sha)
    input_path = Path(command[command.index("--request") + 1])
    safety = (fixture.review, fixture.registry, fixture.journal, fixture.state, input_path)
    before = {path: digest(path) for path in safety}
    sandbox = sandbox or fixture.sandbox
    sandbox_before = snapshot(sandbox)
    reference_before = fixture.snapshot()
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen"}
    env.pop("L5_A6_TEST_FAULT", None)
    process = subprocess.run([*command, *map(str, options)], capture_output=True, timeout=45, env=env)
    receipt_path = output / "admission.json"
    assert reference_before == fixture.snapshot() and snapshot(sandbox) == sandbox_before
    assert all(digest(path) == fingerprint for path, fingerprint in before.items())
    assert fixture.journal_states() == [] and not snapshot(output)
    row = {"status": "PASS", "exit_code": process.returncode, "reason": reason,
           "request_sha256": before[input_path], "signed_workholding_review_sha256": before[fixture.review],
           "registry_unchanged": True, "journal_unchanged": True,
           "consumption_unchanged": True, "xlink_unchanged": True,
           "construction": "NOT_RUN", "candidate_transactions": 0}
    if cli:
        stderr = process.stderr.decode("utf-8", errors="replace")
        assert process.returncode == 1 and reason in stderr, (name, stderr)
        assert not output.exists() or not any(output.iterdir()), (name, output)
        row.update(decision="REJECTED_BY_CLI", transaction_state="NOT_RESERVED")
    else:
        assert process.returncode == 2 and receipt_path.is_file(), (name, process.stderr)
        report = read(receipt_path)
        assert report["finalized"] and report["admission"]["decision"] == "DENY", report
        assert report["reason"] == reason and report["transaction_state"] == "NOT_RESERVED", report
        assert report["construction_result"] == "NOT_RUN" and report["candidate_transactions"] == 0, report
        assert report["cartographer_mutation"] == "DENY" and report["physical_reception"] == "NOT_RUN", report
        assert report["request_sha256"] == before[input_path] and "publication" not in report, report
        row.update(decision="DENY", transaction_state=report["transaction_state"], receipt_sha256=digest(receipt_path))
    return row


def run(args):
    assert ROOT == PROJECT
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    assert head == args.tested_commit, (head, args.tested_commit)
    subprocess.run(["git", "diff", "--quiet", "HEAD", "--"], cwd=ROOT, check=True)
    output = args.output.resolve()
    assert output.is_relative_to(ROOT / ".runtime") and not output.exists()
    plan_path = args.c3_plan.resolve(strict=True)
    assert plan_path.is_relative_to(ROOT / ".runtime")
    plan = read(plan_path)
    assert plan["schema"] == "v3.mutation_plan/4" and plan["domain"] == "SYNTHETIC_BENCH"
    assert len(plan["values"]["harnesses"]) == 2
    transaction = args.c3_transaction.resolve(strict=True)
    c3_native_before = c3_native_witness(transaction, plan_path)

    output.mkdir(parents=True)
    keys = output / "keys"
    keys.mkdir()
    signing = SigningFixtures(args.openssl.resolve(strict=True), keys)
    fixture = A6Fixture(args.core.resolve(strict=True), output / "workholding", signing)
    c3_profile_path = ROOT / "docs/electromechanical_v3/bench_c3_spatial/profile.json"
    c3_profile = read(c3_profile_path)
    source = ROOT / c3_profile["source"]
    c3_sandbox = output / "c3-copy"
    for name in c3_profile["dependencies"]:
        copy = c3_sandbox / name
        copy.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / name, copy)
    c3_reference = snapshot(source)
    assert snapshot(c3_sandbox) == c3_reference == c3_profile["dependencies"]
    c3_request = output / "c3-plan-request.json"
    shutil.copyfile(plan_path, c3_request)
    assert digest(c3_request) == digest(plan_path)

    result = {}
    result["c3-plan-on-a6-entry"] = boundary_refusal(
        fixture, "c3-plan-on-a6-entry", "v3-build requiert FreeCAD Python et le validateur T0 indépendant",
        request_path=c3_request, sandbox=c3_sandbox, cli=True)
    result["c3-plan-with-a6-trust-and-native-options"] = boundary_refusal(
        fixture, "c3-plan-with-a6-trust-and-native-options", "Contrat d'admission A.5 requis",
        request_path=c3_request, sandbox=c3_sandbox,
        options=("--freecad-python", args.freecad, "--t0-validator", args.t0), cli=True)

    c3_bindings = {**fixture.request["bindings"], "model_version": c3_profile["model_version"],
                   "profile_sha256": digest(c3_profile_path), "xlink_dependencies": c3_profile["dependencies"]}
    c3_bound_request = {**fixture.request, "bindings": c3_bindings}
    result["c3-profile-with-workholding-trust"] = boundary_refusal(
        fixture, "c3-profile-with-workholding-trust", "TRUST_BINDING_MISMATCH",
        request=c3_bound_request, sandbox=c3_sandbox)
    c3_trust = fixture.trusted / "c3-trust.json"
    c3_trust_sha = save(c3_trust, {**fixture.trust, "bindings": c3_bindings,
                                  "profile": c3_profile_path.relative_to(ROOT).as_posix(),
                                  "source_root": c3_profile["source"]})
    result["c3-profile-with-workholding-review"] = boundary_refusal(
        fixture, "c3-profile-with-workholding-review", "SIGNED_REVIEW_BINDING_MISMATCH",
        request=c3_bound_request, sandbox=c3_sandbox, trust_path=c3_trust, trust_sha=c3_trust_sha)

    for field, value in (("model_version", "test-modified-model"), ("occurrence", "anchor:other"),
                         ("lot_sha256", "0" * 64)):
        request = {**fixture.request, "bindings": {**fixture.request["bindings"], field: value}}
        name = f"changed-{field.replace('_', '-')}"
        result[name] = boundary_refusal(fixture, name, "TRUST_BINDING_MISMATCH", request=request)
    for field, value, reason in (
            ("carrier", "P66", "CARRIER_EVIDENCE_MISMATCH"),
            ("size_mm", [7.9, 8, 3], "SIGNED_NATIVE_EFFECT_OR_PACKAGE_MISMATCH"),
            ("harnesses", plan["values"]["harnesses"], "SIGNED_NATIVE_EFFECT_OR_PACKAGE_MISMATCH")):
        request = {**fixture.request, "effect": {**fixture.request["effect"], field: value}}
        name = f"changed-effect-{field.replace('_', '-')}"
        result[name] = boundary_refusal(fixture, name, reason, request=request)

    bounds_trust = fixture.trusted / "bounds-trust.json"
    bounds_trust_sha = save(bounds_trust, {**fixture.trust, "bounds": {**fixture.bounds,
                                                                    "min_translation_mm": [-2, 0, 0]}})
    result["replaced-trusted-bounds"] = boundary_refusal(
        fixture, "replaced-trusted-bounds", "SIGNED_NATIVE_EFFECT_OR_PACKAGE_MISMATCH",
        trust_path=bounds_trust, trust_sha=bounds_trust_sha)
    for option, path in (("freecad-python", args.freecad), ("t0-validator", args.t0)):
        name = f"a6-override-{option}"
        result[name] = boundary_refusal(fixture, name, "A6_TOOL_OVERRIDE_DENIED", options=(f"--{option}", path), cli=True)

    physical = {**fixture.request, "evidence_class": "PHYSICAL_MEASURED", "domain": "CARTOGRAPHER_PRIVATE_CAD"}
    result["physical-request-with-test-trust"] = boundary_refusal(
        fixture, "physical-request-with-test-trust", "PHYSICAL_ADMISSION_NOT_CONFIGURED", request=physical)
    assert c3_reference == snapshot(source) == snapshot(c3_sandbox)
    assert digest(plan_path) == digest(c3_request)
    assert c3_native_witness(transaction, plan_path) == c3_native_before
    published = {"schema": "v3.int3.a6_boundaries/1", "status": "PASS", "tested_commit": args.tested_commit,
                 "executed_at_utc": datetime.now(timezone.utc).isoformat(),
                 "binary_sha256": digest(args.core), "c3_source_xlink_sha256": c3_reference,
                 "c3_plan_sha256": digest(plan_path), "cases": result,
                 "c3_native_transaction_without_a6": c3_native_before,
                 "c3_build_using_a6_authority": {"status": "NOT_RUN", "reason": "UNSUPPORTED"}}
    save(output / "boundaries.json", published)
    print(f"A.6 et C.3 : {len(result)} refus vérifiés.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("core", "openssl", "freecad", "t0", "c3-plan", "c3-transaction", "output"):
        parser.add_argument(f"--{name}", required=True, type=Path)
    parser.add_argument("--tested-commit", required=True)
    run(parser.parse_args())
