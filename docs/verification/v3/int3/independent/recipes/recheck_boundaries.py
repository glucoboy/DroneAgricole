"""Contrôles de refus INT.3, uniquement sur copies et signatures synthétiques neuves."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timezone
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from xml.etree import ElementTree
from zipfile import ZIP_DEFLATED, ZipFile


CHECKOUT = Path.cwd().resolve()
sys.path.insert(0, str(CHECKOUT / "convergence_manager/tests"))

from test_v3_a6_transactions import A6Fixture, ROOT, STATES, SigningFixtures, check_commit
from test_v3_a5_authority import read, save, sha, stamp


def hash_file(path):
    return sha(path.read_bytes())


def now():
    return datetime.now(timezone.utc).isoformat()


def files(root, pattern="*"):
    return {p.relative_to(root).as_posix(): hash_file(p)
            for p in sorted(root.rglob(pattern)) if p.is_file()}


def input_map(fixture, request, sandbox, trust):
    inputs = {"request": request, "trust": trust, "review": fixture.review,
              "registry": fixture.registry, "packet": fixture.packet,
              "journal": fixture.journal, "consumption": fixture.state}
    submission = read(request).get("submission", {})
    if submission.get("review"):
        submitted = ROOT / submission["raw_root"] / submission["review"]
        assert submitted.is_relative_to(fixture.raw)
        inputs["submitted_review"] = submitted
    return {name: hash_file(path) for name, path in inputs.items()} | {
        "sandbox": files(sandbox, "*.FCStd"), "source": fixture.snapshot()}


def execute(logs, name, command, output, fault=None):
    started = now()
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen"}
    env.pop("L5_A6_TEST_FAULT", None)
    if fault:
        env["L5_A6_TEST_FAULT"] = fault
    result = subprocess.run(command, capture_output=True, timeout=210, env=env)
    record = {"argv": command, "cwd": ROOT.as_posix(), "fault": fault, "started_utc": started,
              "finished_utc": now(), "exit_code": result.returncode}
    for label, data in (("stdout", result.stdout), ("stderr", result.stderr)):
        path = logs / f"{name}.{label}.log"
        path.write_bytes(data)
        record[label] = {"path": path.relative_to(ROOT).as_posix(), "sha256": sha(data), "bytes": len(data)}
    save(logs / f"{name}.command.json", record)
    receipt = output / "admission.json"
    return record, read(receipt) if receipt.is_file() else None, result.stderr.decode("utf-8", "replace")


def reject(logs, fixture, name, reason, *, cli=False, request=None, path=None,
           sandbox=None, output=None, trust=None, pin=None, extra=()):
    sandbox = sandbox or fixture.sandbox
    trust = trust or fixture.trust_path
    command, directory = fixture.command(name, request, request_path=path, sandbox=sandbox,
                                         output=output, trust_path=trust, trust_sha=pin)
    path = Path(command[command.index("--request") + 1])
    before = input_map(fixture, path, sandbox, trust)
    states = fixture.journal_states()
    existing = files(directory)
    record, report, stderr = execute(logs, name, command + list(map(str, extra)), directory)
    assert before == input_map(fixture, path, sandbox, trust), (name, "input modified")
    assert fixture.journal_states() == states, (name, "unexpected state")
    observed = files(directory)
    if cli:
        assert record["exit_code"] == 1 and reason in stderr, (name, record, stderr, report)
        assert observed == existing, (name, existing, observed)
    else:
        assert record["exit_code"] == 2 and report["admission"]["decision"] == "DENY", (name, record, report)
        assert report["finalized"] is True and report["transaction_state"] == "NOT_RESERVED", report
        assert report["reason"] == reason and report["construction_result"] == "NOT_RUN", (name, report)
        assert report["candidate_transactions"] == 0 and report["cartographer_mutation"] == "DENY", report
        assert report["physical_reception"] == "NOT_RUN" and "publication" not in report, report
        assert report["request_sha256"] == before["request"], report
        assert set(observed) == {"admission.json"}, (name, observed)
    return {"status": "PASS", "reason": reason, "command": record, "inputs_unchanged": before,
            "journal_states_before_and_after": states, "new_authorized_native_execution": False,
            "new_private_native_files": 0, "receipt_sha256": observed.get("admission.json")}


def substitute_support(path):
    """Déplace le datum AnchorNew dans une copie du natif Workholding."""
    temporary = path.with_suffix(".review.zip")
    with ZipFile(path) as source, ZipFile(temporary, "x", compression=ZIP_DEFLATED) as changed:
        for name in source.namelist():
            data = source.read(name)
            if name == "Document.xml":
                tree = ElementTree.fromstring(data)
                placement = tree.find("./ObjectData/Object[@name='AnchorNew']/Properties/"
                                      "Property[@name='Placement']/PropertyPlacement")
                assert placement is not None
                old_x = float(placement.get("Px"))
                placement.set("Px", str(old_x + 0.125))
                data = ElementTree.tostring(tree, encoding="utf-8", xml_declaration=True)
            changed.writestr(name, data)
    temporary.replace(path)
    return {"datum": "AnchorNew", "x_before_mm": old_x, "x_after_mm": old_x + 0.125}


def wait_for_reservation(fixture, running):
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline and not running.done():
        if fixture.issue["id"] in read(fixture.state)["consumed"] and not (fixture.trusted / "a5-consumption.lock").exists():
            return
        time.sleep(0.025)
    raise AssertionError("Aucune réservation observée")


def race_or_revoke(logs, fixture, scenario):
    command, output = fixture.command("primary")
    checked = Path(command[command.index("--request") + 1])
    before = input_map(fixture, checked, fixture.sandbox, fixture.trust_path)
    with ThreadPoolExecutor(max_workers=1) as executor:
        pending = executor.submit(execute, logs, scenario + "-primary", command, output, "hold-after-reserve")
        wait_for_reservation(fixture, pending)
        at_reservation = hash_file(fixture.journal)
        consumption = read(fixture.state)["consumed"]
        if scenario == "concurrent":
            command2, output2 = fixture.command("challenger", request_path=checked)
            second, denied, _ = execute(logs, scenario + "-challenger", command2, output2)
            assert second["exit_code"] == 2 and denied["reason"] in {"AUTHORITY_STATE_BUSY", "DECISION_ALREADY_USED"}, denied
            assert denied["request_sha256"] == before["request"] and denied["candidate_transactions"] == 0, denied
            assert denied["construction_result"] == "NOT_RUN" and "publication" not in denied, denied
            assert set(files(output2)) == {"admission.json"}, output2
        else:
            fixture.set_events([fixture.issue, {**fixture.issue, "kind": "REVOKED", "at_utc": stamp()}])
        first, result, stderr = pending.result()
    after = input_map(fixture, checked, fixture.sandbox, fixture.trust_path)
    assert all(before[key] == after[key] for key in ("request", "trust", "review", "packet", "sandbox", "source"))
    assert read(fixture.state)["consumed"] == consumption and len(consumption) == 1, consumption
    states = fixture.journal_states()
    evidence = {"status": "PASS", "command": first, "inputs_at_start": before,
                "journal_sha256_at_reservation": at_reservation, "journal_states": states,
                "journal_sha256_final": after["journal"], "consumption_count": 1,
                "receipt_sha256": hash_file(output / "admission.json")}
    if scenario == "concurrent":
        transaction, _ = check_commit(fixture, {"code": first["exit_code"], "report": result,
                                                "output": output, "stderr": stderr})
        assert states.count("AUTHORIZED_RESERVED") == states.count("COMMITTED_PRIVATE") == 1, states
        evidence.update(denied_reason=denied["reason"], denied_command=second,
                        denied_receipt_sha256=hash_file(output2 / "admission.json"),
                        new_authorized_native_execution_for_challenger=False,
                        transaction=transaction)
    else:
        assert first["exit_code"] == 2 and result["reason"] == "A6_FINAL_AUTHORITY_DENIED/DECISION_REVOKED", result
        assert states == STATES[:-1] + ["QUARANTINED"] and "publication" not in result, states
        assert result["cartographer_mutation"] == "DENY" and result["admission"]["decision"] == "DENY", result
        evidence.update(reason=result["reason"], committed=0, registry_sha256_final=after["registry"],
                        native_execution="AUTORISÉ AVANT RÉVOCATION, PREUVES EN QUARANTAINE")
    return evidence, output / "admission.json"


def run(args):
    assert ROOT == CHECKOUT
    out = args.output.resolve()
    assert out.is_relative_to(ROOT / ".runtime") and not out.exists()
    args.c3_plan = args.c3_plan.resolve(strict=True)
    args.c3_transaction = args.c3_transaction.resolve(strict=True)
    assert args.c3_plan.is_relative_to(ROOT / ".runtime") and args.c3_transaction.is_relative_to(ROOT / ".runtime")
    logs = out / "logs"
    logs.mkdir(parents=True)
    keys = out / "keys"
    keys.mkdir()
    signing = SigningFixtures(args.openssl.resolve(strict=True), keys)
    fixture = A6Fixture(args.core.resolve(strict=True), out / "signed", signing)
    campaign = args.c3_transaction / "campaign.json"
    witness = read(campaign)
    candidate_job = args.c3_transaction / "candidate-job.json"
    candidate_validation = args.c3_transaction / "candidate-validation.json"
    crosscheck = args.c3_transaction / "t0-crosscheck.json"
    witness_files = (campaign, candidate_job, candidate_validation, crosscheck, args.c3_plan)
    witness_hashes = {path.name: hash_file(path) for path in witness_files}
    job = read(candidate_job)
    validation = read(candidate_validation)
    native = files(args.c3_transaction / "cad", "*.FCStd")
    assert witness["status"] == "PASS" and witness["execution_scope"] == "BENCH_TEST_ONLY", witness
    assert witness["native_sha256"] == native and witness["plan_sha256"] == hash_file(args.c3_plan), witness
    assert "authorized_effect" not in job and "spatial_contract" in job, job
    assert validation["status"] == "PASS" and validation["reopened"] and validation["documents_closed"], validation
    assert validation["inputs_sha256"] == native
    assert read(crosscheck)["exit_code"] == 0
    plan = read(args.c3_plan)
    assert plan["schema"] == "v3.mutation_plan/4" and plan["domain"] == "SYNTHETIC_BENCH", plan
    profile_path = ROOT / "docs/electromechanical_v3/bench_c3_spatial/profile.json"
    profile = read(profile_path)
    closure = out / "spatial-baseline"
    shutil.copytree(ROOT / profile["source"], closure)
    assert files(closure, "*.FCStd") == profile["dependencies"]
    candidate_copy = out / "spatial-candidate"
    shutil.copytree(args.c3_transaction / "cad", candidate_copy)
    assert files(candidate_copy, "*.FCStd") == native
    cases = {}
    partial = out / "cases.json"

    def keep(name, row):
        cases[name] = row
        save(partial, cases)

    def check(name, reason, **kwargs):
        keep(name, reject(logs, fixture, name, reason, **kwargs))

    explicit_tools = ("--freecad-python", args.freecad, "--t0-validator", args.t0)
    check("plan-v4-avec-confiance-a6", "Contrat d'admission A.5 requis", cli=True,
          path=args.c3_plan, sandbox=closure, extra=explicit_tools)
    check("plan-v4-option-heritee", "Option incompatible avec V3 : receipt", cli=True,
          path=args.c3_plan, sandbox=closure, extra=explicit_tools + ("--receipt", campaign))
    bindings = {**fixture.request["bindings"], "model_version": profile["model_version"],
                "profile_sha256": hash_file(profile_path), "xlink_dependencies": profile["dependencies"]}
    crossed = {**fixture.request, "bindings": bindings}
    alternate = fixture.trusted / "spatial-trust.json"
    pin = save(alternate, {**fixture.trust, "bindings": bindings,
                          "profile": profile_path.relative_to(ROOT).as_posix(), "source_root": profile["source"]})
    check("revue-workholding-avec-fermeture-c3", "SIGNED_REVIEW_BINDING_MISMATCH",
          request=crossed, sandbox=closure, trust=alternate, pin=pin)

    workholding = A6Fixture(args.core.resolve(), out / "archive-alteree", signing)
    dependency = workholding.sandbox / read(workholding.profile)["entry"]
    original = hash_file(dependency)
    alteration = substitute_support(dependency)
    assert hash_file(dependency) != original
    row = reject(logs, workholding, "support-modifie-apres-signature", "XLINK_DEPENDENCY_SHA256_MISMATCH")
    keep("support-modifie-apres-signature", {**row, "original_sha256": original,
         "modified_file": dependency.name, "datum_change": alteration})
    pose = deepcopy(fixture.request)
    pose["effect"]["translation_mm"][0] = -0.25
    check("pose-modifiee-apres-signature", "SIGNED_NATIVE_EFFECT_OR_PACKAGE_MISMATCH", request=pose)

    check("sortie-dans-fermeture-c3-jetable", "A6_OUTPUT_NOT_PRIVATE_OR_OVERLAPPING", cli=True,
          sandbox=candidate_copy, output=candidate_copy / "publication")
    check("sortie-parent-de-soumission", "A6_OUTPUT_NOT_PRIVATE_OR_OVERLAPPING", cli=True, output=fixture.work)
    alias = out / "sortie-redirigee"
    if os.name == "nt":
        subprocess.run(["cmd.exe", "/d", "/c", "mklink", "/j", str(alias), str(candidate_copy)],
                       check=True, capture_output=True, timeout=10)
    else:
        alias.symlink_to(candidate_copy, target_is_directory=True)
    check("sortie-jonction-fermeture-c3", "A6_PATH_REDIRECTED", cli=True, output=alias / "publication")

    physical = {**fixture.request, "evidence_class": "PHYSICAL_MEASURED", "domain": "CARTOGRAPHER_PRIVATE_CAD"}
    check("physique-avec-confiance-test", "PHYSICAL_ADMISSION_NOT_CONFIGURED", request=physical)
    unsupported = {**fixture.request, "effect": {**fixture.request["effect"], "carrier": "P66"}}
    check("porteur-p66-hors-workholding", "CARRIER_EVIDENCE_MISMATCH", request=unsupported)

    concurrent = A6Fixture(args.fault_core.resolve(), out / "concurrent", signing)
    row, final_receipt = race_or_revoke(logs, concurrent, "concurrent")
    keep("meme-identifiant-concurrent", row)
    revoked = A6Fixture(args.fault_core.resolve(), out / "revocation", signing)
    row, _ = race_or_revoke(logs, revoked, "revoked")
    keep("revoque-avant-commit", row)

    reused = fixture.raw / "receipt-workholding.json"
    shutil.copyfile(final_receipt, reused)
    assert read(reused)["transaction_state"] == "COMMITTED_PRIVATE"
    check("recu-committe-utilise-comme-requete-c3", "Contrat d'admission A.5 requis",
          cli=True, path=reused, sandbox=candidate_copy, extra=explicit_tools)
    unauthorized = {**fixture.request, "submission": {**fixture.request["submission"], "review": reused.name}}
    check("recu-committe-a-la-place-de-la-revue", "CONTRACT_FIELDS_MISMATCH", request=unauthorized)

    assert files(candidate_copy, "*.FCStd") == native == files(args.c3_transaction / "cad", "*.FCStd")
    assert files(closure, "*.FCStd") == profile["dependencies"]
    assert witness_hashes == {path.name: hash_file(path) for path in witness_files}
    save(out / "report.json", {"schema": "v3.int3.independent.boundaries/1", "status": "PASS",
         "observed_utc": now(), "tested_commit": args.tested_commit,
         "checkout_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
         "binaries": {"nominal_sha256": hash_file(args.core), "faults_sha256": hash_file(args.fault_core)},
         "ordinary_c3": {"scope": witness["execution_scope"], "witness_sha256_before_and_after": witness_hashes,
                         "native_sha256_before_and_after": native, "reopened_and_closed": True},
         "native_execution_observation": "Sortie, état authentifié du journal et absence de réservation/stockage privé, rapprochés du point d'appel A6Transaction.cpp; aucune trace ETW.",
         "cartographer_candidate_count": 0, "cases": cases})
    print(f"{len(cases)} cas de jonction finalisés et documentés")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for option in ("core", "fault-core", "openssl", "freecad", "t0", "c3-plan", "c3-transaction", "output"):
        parser.add_argument("--" + option, required=True, type=Path)
    parser.add_argument("--tested-commit", required=True)
    run(parser.parse_args())
