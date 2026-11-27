"""Vérifie les refus C.4 et injecte des défauts dans des natifs privés."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timedelta
import os
from pathlib import Path
import sys
from types import SimpleNamespace

from replay_v3_b1 import setup
from replay_v3_b2 import artifact, invoke
from replay_v3_c4 import ROOT, authority, external_input, require
from replay_v3_b1 import digest, load, write
from test_v3_c3_adversarial import native_case
from test_v3_b2_native_faults import PROJECT, closure, guard, private_path
from test_v3_c2_native_faults import WORKERS, invoke as freecad_invoke
from test_v3_int3_a6_boundaries import boundary_refusal
from test_v3_a6_transactions import A6Fixture, SigningFixtures


FAULTS = {"outside-corridor": "L4_SPATIAL_CONTRACT", "blocked-tool": "L4_SERVICE",
          "false-bearing-face": "L4_SUPPORT_ANCHOR"}


def build(args, case, profile, plan, expected=None):
    sandbox = setup(case, profile, plan)
    target = case / "output"
    argv = [args.core, "v3-build", "--root", ROOT, "--request", case / "plan.json",
            "--sandbox", sandbox, "--output", target, "--freecad-python", args.freecad, "--t0-validator", args.t0]
    performed = invoke(case, "l5", list(map(str, argv)), timeout=90)
    receipt = target / ("transaction/campaign.json" if expected is None else "refusal.json")
    result = load(receipt)
    require(closure(sandbox, profile["entry"]) == profile["dependencies"], "Source de banc altérée")
    if expected is None:
        require(performed.returncode == 0 and result["status"] == "PASS", f"Équivalence refusée : {result}")
    else:
        require(performed.returncode == 2 and expected in result["reason"]
                and result["construction_result"] == "NOT_RUN" and result["candidate_transactions"] == 0
                and not (target / "transaction").exists(), f"Refus avant construction non démontré : {result}")
    return {"status": "PASS", "reason": result.get("reason"), "receipt": artifact(receipt),
            "invocation": artifact(case / "l5-invocation.json")}


def ordered_records(args, area, profile, original, transaction):
    changed = {
        "zero-quaternion": ("rotation_xyzw", [0, 0, 0, 0], "Quaternion non unitaire"),
        "non-unit-quaternion": ("rotation_xyzw", [0, 0, 0, 2], "Quaternion non unitaire"),
        "outside-rotation": ("rotation_xyzw", [0, 0, 0, 1], "Orientation hors domaine"),
        "outside-support-patch": ("support_offset_mm", [21, 0, 0], "Appui hors patch"),
    }
    records = {}
    for case, (key, value, expectation) in changed.items():
        plan = deepcopy(original)
        plan["values"][key] = value
        records[case] = build(args, area / case, profile, plan, expectation)
    plan = deepcopy(original)
    plan["values"]["harnesses"]["cordon"]["route_points_mm"][-1][2] += 0.01
    records["terminal-outside-tolerance"] = build(
        args, area / "terminal-outside-tolerance", profile, plan, "Extrémité de parcours incompatible")
    plan = {**original, "domain": "CARTOGRAPHER_PRIVATE_CAD"}
    records["physical-domain"] = build(args, area / "physical-domain", profile, plan, "MUTATION_DOMAIN_DENIED")
    opposite = deepcopy(original)
    opposite["values"]["rotation_xyzw"] = [-value for value in original["values"]["rotation_xyzw"]]
    case = area / "opposite-quaternion-sign"
    checked = build(args, case, profile, opposite)
    same = load(case / "output/transaction/expanded-plan.json")["actions"] == load(transaction / "expanded-plan.json")["actions"]
    require(same, "Les deux signes du quaternion doivent produire mêmes actions et tangentes")
    records["opposite-quaternion-sign"] = {**checked, "identical_expanded_actions": same}
    return records


def rejected_t2(args, area, profile_path, profile):
    freeze_path = args.campaign / "freeze.json"
    snapshot = load(freeze_path)
    sample = load(args.campaign / "T2-HANDOFF.json")["external_input"]
    sample["issued_at_utc"] = (datetime.fromisoformat(snapshot["frozen_at_utc"]) - timedelta(seconds=1)).isoformat()
    sample["obstacle"] = {"id": "SyntheticRejected", "min_mm": [0, 0, 0], "max_mm": [1, 1, 1]}
    evaluation = area / "rejected-t2.json"
    write(evaluation, sample)
    cases = {"tampered-t2": ("0" * 64, "emplacement indépendant ou SHA incorrect"),
             "t2-before-freeze": (digest(evaluation), "émis en UTC après le gel")}
    records = {}
    for case, (sha, expected) in cases.items():
        sandbox = area / "refusals" / case
        sandbox.mkdir(parents=True)
        witness = SimpleNamespace(perturbation=evaluation, perturbation_sha256=sha)
        try:
            external_input(witness, sandbox, freeze_path, snapshot, profile_path, profile)
        except ValueError as error:
            require(expected in str(error) and not any(sandbox.iterdir()), f"Refus T2 divergent : {error}")
            records[case] = {"status": "PASS", "reason": str(error), "candidate_transactions": 0}
        else:
            raise RuntimeError(f"Entrée périmée ou altérée acceptée : {case}")
    return records


def inject(args):
    from convergence_manager.native.v3_mutate import Assembly, install_obstacle, native, update_route

    root, job_path, result = map(private_path, (args.root, args.job, args.result))
    require(root.name == "injected-cad" and root.parent == job_path.parent == result.parent,
            "Le témoin doit rester dans le dossier de scénario")
    job = load(job_path)
    before = closure(root, job["entry"])
    require(before == job["dependencies"], "Fermeture du témoin non reconnue")
    native.cables_environment(gui=True)
    app = native.App
    doc = app.openDocument(str(root / job["entry"]))
    effects = {}
    try:
        native.complete_dependencies(doc, root)
        native.recalculate(doc, root)
        assembly = Assembly(doc, job["model"]["occurrences"])
        if args.inject == "blocked-tool":
            action = job["actions"][-1]
            spec = next(row for row in job["model"]["validation"]["service"] if row.get("required_action") == action["id"])
            support = app.Placement(assembly.world(action["occurrence"]))
            tip = support.multVec(app.Vector(*spec["offset_local_mm"]) + app.Vector(0, 0, spec["stroke_mm"] / 2))
            bounds = app.Vector(0.5, 0.5, 0.5)
            obstacle = {"id": "C4BlockedTool", "min_mm": list(tip - bounds), "max_mm": list(tip + bounds)}
            install_obstacle(doc, obstacle)
            effects["external_obstacle"] = obstacle
        elif args.inject == "false-bearing-face":
            name = job["actions"][-1]["parameters"]["carrier"]
            pose = app.Placement(assembly.world(name))
            pose.Base += app.Vector(0, 0, -1)
            assembly.set_world(name, pose.toMatrix())
        else:
            action = job["actions"][1]
            params = action["parameters"]
            points = [native.vector(point) for point in params["points_mm"]]
            middle = len(points) // 2
            points[middle].z = 30
            cable = assembly.occurrence(action["occurrence"])
            update_route(assembly, action["occurrence"], cable, points, params["diameter_mm"], params["bend_radius_mm"])
            rebuilt = native.geometry.rebuild_cable_in_isolated_document(doc, cable)
            require(rebuilt["status"] == "pass", "Le témoin doit conserver un câble BRep")
        require(doc.recompute() is not False, "Recalcul de témoin incomplet")
        doc.save()
    finally:
        for name in reversed(list(app.listDocuments())):
            app.closeDocument(name)
    after = closure(root, job["entry"])
    require(before.keys() == after.keys() and before[job["entry"]] != after[job["entry"]]
            and all(before[name] == after[name] for name in before if name != job["entry"]),
            "Le défaut doit changer uniquement la tête de fermeture")
    write(result, {"pid": os.getpid(), "after_sha256": after, "effects": effects})


def detect(args, area, candidate, job, fault):
    case = area / fault
    cad = case / "injected-cad"
    guard.stage(candidate, job["entry"], cad)
    initial, injected = case / "original-job.json", case / "injection.json"
    write(initial, job)
    a = freecad_invoke(args, case, "inject", Path(__file__), {0}, inject=fault, root=cad, job=initial, result=injected)
    witness = load(injected)
    rewritten, output = case / "candidate-job.json", case / "verification.json"
    write(rewritten, {**job, **witness["effects"], "dependencies": witness["after_sha256"]})
    b = freecad_invoke(args, case, "verify", WORKERS / "v3_verify.py", {0}, root=cad, job=rewritten, output=output)
    result = load(output)
    check = next(row for row in result["checks"] if row["id"] == FAULTS[fault])
    require(result["status"] == "FAIL" and result["documents_closed"] and result["reopened"]
            and result["pid"] != witness["pid"] and result["inputs_sha256"] == witness["after_sha256"]
            and check["status"] == "FAIL", f"Défaut non détecté : {fault}")
    if fault == "outside-corridor":
        measured = next(row for row in check["details"] if row["id"] == job["actions"][1]["occurrence"])
        require(measured["details"]["outside_corridor_mm"] > 0, "Axe natif hors corridor non mesuré")
    return {"status": "PASS", "check": check["id"], "verified": artifact(output), "invocations": [a, b]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("core", "t0", "freecad", "openssl", "campaign", "output", "root", "job", "result"):
        parser.add_argument(f"--{name}", type=Path)
    parser.add_argument("--inject", choices=tuple(FAULTS))
    args = parser.parse_args()
    if args.inject:
        inject(args)
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(0)
    for name in ("core", "t0", "freecad", "openssl", "campaign", "output"):
        path = getattr(args, name)
        if path is None:
            parser.error(f"--{name} requis")
        setattr(args, name, path.resolve(strict=name != "output"))
    area = args.output
    require(PROJECT == ROOT and area.is_relative_to(ROOT / ".runtime"), "Campagne hors dossier privé .runtime")
    _, _, args.profile, profile = authority()
    t1 = load(args.campaign / "freeze.json")["t1"]
    candidate = (ROOT / t1["candidate"]["path"]).parent
    transaction = candidate.parent
    source_job = load(transaction / "candidate-job.json")
    original = load(transaction / "mutation-plan.json")
    before = closure(candidate, source_job["entry"])
    require(before == source_job["dependencies"] and load(transaction / "campaign.json")["status"] == "PASS",
            "Témoin T1 qualifié requis")
    area.mkdir(parents=True)
    results = ordered_records(args, area, profile, original, transaction)
    results.update(rejected_t2(args, area, args.profile, profile))
    keys = area / "keys"
    keys.mkdir()
    fixture = A6Fixture(args.core, area / "workholding", SigningFixtures(args.openssl, keys))
    results["c4-on-a6-entry"] = boundary_refusal(
        fixture, "c4-on-a6-entry", "Contrat d'admission A.5 requis", request_path=transaction / "mutation-plan.json",
        sandbox=candidate, options=("--freecad-python", args.freecad, "--t0-validator", args.t0), cli=True)
    physical = {**fixture.request, "evidence_class": "PHYSICAL_MEASURED", "domain": "CARTOGRAPHER_PRIVATE_CAD"}
    results["test-authority-on-cartographer"] = boundary_refusal(
        fixture, "test-authority-on-cartographer", "PHYSICAL_ADMISSION_NOT_CONFIGURED", request=physical)
    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs = {name: pool.submit(native_case, args, area, candidate, source_job, name)
                for name in ("harnesses-collide", "false-datum-across-plane")}
        jobs.update({name: pool.submit(detect, args, area, candidate, source_job, name) for name in FAULTS})
        for name, outcome in jobs.items():
            try:
                results[name] = outcome.result()
            except (RuntimeError, ValueError, KeyError, OSError, StopIteration) as error:
                results[name] = {"status": "FAIL", "reason": str(error)}
    require(closure(candidate, source_job["entry"]) == before, "Candidat T1 modifié")
    passed = all(value["status"] in {"PASS", "DETECTED"} for value in results.values())
    write(area / "adversarial.json", {"schema": "v3.c4.adversarial/1", "status": "PASS" if passed else "FAIL",
          "scope": "SYNTHETIC_BENCH", "tester": artifact(Path(__file__).resolve()), "cases": results})
    return 0 if passed else 4


if __name__ == "__main__":
    raise SystemExit(main())
