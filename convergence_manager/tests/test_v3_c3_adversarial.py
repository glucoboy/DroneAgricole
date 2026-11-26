"""Injecte et mesure les défauts C.3, sur copies privées seulement."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import os
from pathlib import Path
import sys
from uuid import uuid4

from replay_v3_b1 import setup
from replay_v3_b2 import invoke as invoke_core
from test_v3_b2_native_faults import PROJECT, closure, guard, private_path, proof, read, require, write
from test_v3_c2_native_faults import WORKERS, invoke, modify, route_midpoint


NATIVE_CASES = {
    "harnesses-collide": "L4_GEOMETRY",
    "false-datum-across-plane": "L2_TOPOLOGY",
    "reversed-port-tangent": "L4_DYNAMIC_BEND_RADIUS",
    "radius-under-limit-b": "L4_DYNAMIC_BEND_RADIUS",
    "floating-support": "L4_SUPPORT_ANCHOR",
    "external-obstacle-collision": "L4_GEOMETRY",
}


def inject(args):
    from convergence_manager.native.v3_mutate import Assembly, install_obstacle, native, update_route

    root, job_path, result = map(private_path, (args.root, args.job, args.result))
    require(root.name == "injected-cad" and root.parent == job_path.parent == result.parent,
            "Une copie privée confinée au scénario est requise")
    job = read(job_path)
    before = closure(root, job["entry"])
    require(before == job["dependencies"], "Entrée du défaut différente du candidat scellé")
    native.cables_environment(gui=True)
    app = native.App
    doc = app.openDocument(str(root / job["entry"]))
    effects = {}
    try:
        native.complete_dependencies(doc, root)
        native.recalculate(doc, root)
        assembly = Assembly(doc, job["model"]["occurrences"])
        if args.inject == "false-datum-across-plane":
            proxy = job["model"]["validation"]["ports"]["port-b"]["attachment_equipment"]
            pose = app.Placement(assembly.world(proxy))
            pose.Base += app.Vector(0, 0, 3)
            assembly.set_world(proxy, pose.toMatrix())
            effects["attachment_proxy_translation_mm"] = [0, 0, 3]
        elif args.inject == "reversed-port-tangent":
            action = job["actions"][1]
            params = action["parameters"]
            start = native.vector(params["points_mm"][0])
            reverse = native.vector(params["start_axis"]) * -9
            points = [start, start + reverse,
                      start + app.Vector(-11, -13, 0), start + app.Vector(10, -16, 0),
                      *[native.vector(point) for point in params["points_mm"][2:]]]
            cable = assembly.occurrence(action["occurrence"])
            update_route(assembly, action["occurrence"], cable, points, params["diameter_mm"], params["bend_radius_mm"])
            fresh = native.geometry.rebuild_cable_in_isolated_document(doc, cable)
            require(fresh["status"] == "pass", f"Témoin tangent invalide : {fresh}")
        elif args.inject == "external-obstacle-collision":
            first, second = (job["actions"][index]["occurrence"] for index in (1, 2))
            center = route_midpoint(native, assembly, first, second)
            obstacle = {"id": "C3AdversarialCollision",
                        "min_mm": list(center - app.Vector(1, 1, 1)),
                        "max_mm": list(center + app.Vector(1, 1, 1))}
            install_obstacle(doc, obstacle)
            effects["external_obstacle"] = obstacle
        else:
            modify(args.inject, native, assembly, job)
        require(doc.recompute() is not False, "Recalcul du défaut non finalisé")
        doc.save()
    finally:
        for name in reversed(list(app.listDocuments())):
            app.closeDocument(name)
    after = closure(root, job["entry"])
    require(before.keys() == after.keys() and before[job["entry"]] != after[job["entry"]]
            and all(before[name] == after[name] for name in before if name != job["entry"]),
            "Le défaut doit modifier le document de tête uniquement")
    write(result, {"pid": os.getpid(), "worker_id": uuid4().hex, "before_sha256": before,
                   "after_sha256": after, "effects": effects})


def exact_measurement(fault, checks, model):
    check = checks[NATIVE_CASES[fault]]
    require(check["status"] == "FAIL", f"Défaut sans contrôle FAIL : {fault}")
    if fault in {"harnesses-collide", "external-obstacle-collision"}:
        first, second = (model["occurrences"][name] for name in ("cordon", "cordon-b"))
        pair = {first, second if fault == "harnesses-collide" else "C3ExternalObstacle"}
        selected = next((row for row in check["details"]["pairs"]
                         if {item.split("#", 1)[-1] for item in row["pair"]} == pair), None)
        require(selected is not None and selected["intersection_volume_mm3"] > 1e-6 and selected["status"] == "fail",
                "Interférence volumique précise attendue")
        if fault == "external-obstacle-collision":
            obstacle = next(row for row in checks["L4_SPATIAL_CONTRACT"]["details"]
                            if row["id"] == "external_obstacle")
            require(obstacle["status"] == "PASS", "L’obstacle doit être authentifié, puis sa collision rejetée")
        return {"pair": sorted(pair), "intersection_volume_mm3": selected["intersection_volume_mm3"]}
    if fault == "reversed-port-tangent":
        error = check["details"]["cordon"]["start_axis_error_deg"]
        require(error >= 179.999, "Une tangente vraiment inversée est requise")
        return {"start_axis_error_deg": error}
    if fault == "radius-under-limit-b":
        observed = check["details"]["cordon-b"]
        require(observed["minimum_radius_mm"] < model["validation"]["routes"]["cordon-b"]["minimum_radius_mm"],
                "Un sous-rayon natif mesurable est requis")
        return {"minimum_radius_mm": observed["minimum_radius_mm"]}
    if fault == "false-datum-across-plane":
        port = check["details"]["ports"]["port-b"]
        require(port["status"] == "FAIL", "La route ne doit pas être autorisée via le faux datum")
        return port
    return check["details"]


def native_case(args, area, candidate, original, fault):
    case = area / fault
    cad = case / "injected-cad"
    guard.stage(candidate, original["entry"], cad)
    job, modified = case / "original-job.json", case / "injection.json"
    write(job, original)
    injections = [invoke(args, case, "inject", Path(__file__).resolve(), {0}, inject=fault,
                         root=cad, job=job, result=modified)]
    witness = read(modified)
    job, output = case / "candidate-job.json", case / "verification.json"
    write(job, {**original, "dependencies": witness["after_sha256"],
                **{name: value for name, value in witness["effects"].items() if name == "external_obstacle"}})
    injections.append(invoke(args, case, "verify", WORKERS / "v3_verify.py", {0},
                             root=cad, job=job, output=output))
    measured = read(output)
    checks = {row["id"]: row for row in measured["checks"]}
    require(measured["status"] == "FAIL" and measured["reopened"] and measured["documents_closed"]
            and measured["inputs_sha256"] == witness["after_sha256"] and witness["pid"] != measured["pid"],
            f"Défaut natif non démontré : {output}")
    evidence = {"status": "DETECTED", "check": NATIVE_CASES[fault], "injection": proof(modified),
                "verification": proof(output), "checks": {name: row["status"] for name, row in checks.items()},
                "measurements": exact_measurement(fault, checks, original["model"]), "invocations": injections}
    if fault in {"harnesses-collide", "external-obstacle-collision"}:
        cross = case / "cross.json"
        contract = case / "spatial-contract.json"
        write(contract, original["spatial_contract"])
        parameters = {"root": cad, "profile": args.profile, "output": cross, "spatial_contract": contract,
                      "expected_entry_sha256": witness["after_sha256"][original["entry"]]}
        if fault == "external-obstacle-collision":
            obstacle = case / "obstacle.json"
            write(obstacle, witness["effects"]["external_obstacle"])
            parameters["external_obstacle"] = obstacle
        injections.append(invoke(args, case, "cross", WORKERS / "v3_cross_measure.py", {0}, **parameters))
        report = read(cross)
        require(report["pid"] not in {witness["pid"], measured["pid"]} and report["copy_unchanged"] and
                report["inputs_sha256"] == witness["after_sha256"], "Contre-mesure BRep distincte requise")
        if fault == "harnesses-collide":
            exact = report["interference_classification"]["cross_harness"]
            require(exact["status"] == "FAIL", "Collision entre câbles sans échec de la contre-mesure")
        else:
            native = report["external_obstacle"]
            require(native["presence"] == "SAVED_NATIVE" and native["harnesses"]["cordon-b"]["intersection_mm3"] <= 1e-6,
                    "L’obstacle exact doit heurter uniquement le premier câble")
            exact = native["harnesses"]["cordon"]
        require(abs(exact["intersection_mm3"] - evidence["measurements"]["intersection_volume_mm3"]) <= 1e-6,
                "Volumes BRep divergents entre les deux vérificateurs")
        evidence["independent_brep"] = proof(cross)
    return evidence


def pseudo_contact(args, area, candidate, original):
    case = area / "pseudo-manufacturer-contact"
    cad = case / "input"
    guard.stage(candidate, original["entry"], cad)
    job, output = case / "candidate-job.json", case / "verification.json"
    forged = deepcopy(original)
    rule = next(row for row in forged["model"]["validation"]["allowed_interferences"]
                if row["required_action"] == forged["actions"][-1]["id"])
    rule.update(parts=["cordon", "cordon-b"], role="MANUFACTURER_CONTACT",
                reason="TEST_ONLY : prétendue autorisation fabricant")
    write(job, forged)
    invocation = invoke(args, case, "verify", WORKERS / "v3_verify.py", {0},
                        root=cad, job=job, output=output)
    verification = read(output)
    refusal = next(row for row in verification["checks"] if row["id"] == "NATIVE_MEASUREMENT")
    require(verification["status"] == "INCONCLUSIVE" and refusal["status"] == "INCONCLUSIVE"
            and "hors profils synthétiques C.3" in refusal["details"], "Le profil falsifié doit rester irrecevable")
    return {"status": "REJECTED", "reason": refusal["details"], "invocation": invocation,
            "verification": proof(output)}


def observation_case(args, area, profile, rehash):
    case = area / ("rehash-cache" if rehash else "forged-measurement-cache")
    case.mkdir()
    observation = read(args.observation)
    forged = case / "observation.json"
    observation["routes"]["cordon"]["length_mm"] += 1
    write(forged, observation)
    problem = args.problem
    invocations = []
    if rehash:
        edited = {**read(args.problem), "observation_sha256": guard.sha256(forged)}
        request, problem = case / "request.json", case / "problem.json"
        write(request, edited)
        model = PROJECT / profile["source"] / profile["entry"]
        run = invoke_core(case, "l3", list(map(str, [
            args.l3, "v3-problem", "--root", PROJECT, "--request", request, "--domain", args.domain,
            "--model", model, "--observation", forged, "--output", problem])))
        require(run.returncode == 0 and read(problem)["observation_sha256"] == guard.sha256(forged),
                "Le scénario requiert un problème L3 recalé sur le cache forgé")
        invocations.append(proof(case / "l3-invocation.json"))
    output = case / "output"
    run = invoke_core(case, "l5", list(map(str, [
        args.core, "v3-converge", "--root", PROJECT, "--request", problem, "--observation", forged,
        "--freecad-python", args.freecad, "--python", args.python, "--t0-validator", args.t0, "--output", output])))
    reason = "Observation L3 divergente : routes" if rehash else "L3 et la référence XLink divergent"
    require(run.returncode == 1 and reason in run.stderr and not (output / "candidates").exists(),
            f"Cache falsifié non refusé avant création : {run.stderr}")
    invocations.append(proof(case / "l5-invocation.json"))
    return {"status": "REJECTED", "reason": reason, "invocations": invocations,
            "forged_observation": proof(forged), "accepted_sha256_by_l3": proof(problem) if rehash else None,
            "candidate_transactions": 0}


def physical_case(args, area, profile, subject):
    name = f"cartographer-{subject}-without-physical-evidence"
    case = area / name
    domain_sha = guard.sha256(args.domain)
    request = {"schema": "v3.mutation_plan/4", "domain": "CARTOGRAPHER_PRIVATE_CAD",
               "plan_id": name, "authority_sha256": domain_sha, "domain_sha256": domain_sha,
               "values": {"occurrence": f"{subject}-reference", "operation": "CHANGE_CONNECTOR_VARIANT",
                          "claimed_authority": "PHYSICAL_MEASURED", "physical_evidence": []}}
    sandbox = setup(case, profile, request)
    output = case / "output"
    run = invoke_core(case, "l5", list(map(str, [
        args.core, "v3-build", "--root", PROJECT, "--request", case / "plan.json",
        "--sandbox", sandbox, "--freecad-python", args.freecad, "--t0-validator", args.t0, "--output", output])))
    receipt = output / "refusal.json"
    report = read(receipt)
    require(run.returncode == 2 and report["reason"] == "MUTATION_DOMAIN_DENIED"
            and report["construction_result"] == "NOT_RUN" and report["candidate_transactions"] == 0,
            "La mutation physique non prouvée doit rester DENY")
    return {"status": "DENY", "reason": report["reason"], "receipt": proof(receipt),
            "construction": report["construction_result"], "candidate_transactions": report["candidate_transactions"],
            "invocation": proof(case / "l5-invocation.json")}


def run(args):
    transaction, area = map(private_path, (args.transaction, args.output))
    profile = read(args.profile)
    candidate = transaction / "cad"
    validation = transaction / "candidate-validation.json"
    receipt = transaction / "campaign.json"
    original = read(transaction / "candidate-job.json")
    before = closure(candidate, original["entry"])
    result = read(receipt)
    require("spatial_contract" in original and "external_obstacle" not in original
            and result["status"] == "PASS" and result["candidate_state"] == "CANDIDATE"
            and result["execution_scope"] == "BENCH_TEST_ONLY" and result["native_sha256"] == before
            and before == original["dependencies"] and read(validation)["status"] == "PASS"
            and read(args.problem)["phase"] == "T1",
            "Un candidat T1 C.3 rouvert et validé est requis")
    cases = {}
    area.mkdir(parents=True)

    def record(name, fn):
        try:
            cases[name] = fn()
        except (RuntimeError, KeyError, OSError, StopIteration) as error:
            cases[name] = {"status": "ERROR", "reason": str(error)}

    with ThreadPoolExecutor(max_workers=2) as pool:
        native_cases = {fault: pool.submit(native_case, args, area, candidate, original, fault)
                        for fault in NATIVE_CASES}
        for fault, outcome in native_cases.items():
            record(fault, outcome.result)
    record("pseudo-manufacturer-contact", lambda: pseudo_contact(args, area, candidate, original))
    record("forged-measurement-cache", lambda: observation_case(args, area, profile, False))
    record("rehash-cache", lambda: observation_case(args, area, profile, True))
    for subject in ("ttl", "usb"):
        record(f"cartographer-{subject}-without-physical-evidence",
               lambda: physical_case(args, area, profile, subject))
    require(closure(candidate, original["entry"]) == before
            and closure(PROJECT / profile["source"], profile["entry"]) == profile["dependencies"],
            "Candidat ou source commune modifié")
    passed = all(row["status"] in {"DETECTED", "REJECTED", "DENY"} for row in cases.values())
    write(area / "adversarial.json", {"schema": "v3.c3.adversarial/1", "status": "PASS" if passed else "FAIL",
          "scope": "SYNTHETIC_BENCH", "profile": proof(args.profile), "candidate_validation": proof(validation),
          "transaction": proof(receipt), "candidate_sha256": before, "tester": proof(Path(__file__).resolve()),
          "validated_problem": proof(args.problem), "reference_observation": proof(args.observation),
          "external_perturbation_t2": "NON_APPLICABLE", "cases": cases})
    return 0 if passed else 4


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("freecad", "core", "l3", "python", "t0", "profile", "domain", "transaction", "problem",
                 "observation", "output", "root", "job", "result"):
        parser.add_argument(f"--{name}", type=Path)
    parser.add_argument("--inject", choices=NATIVE_CASES, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.inject:
        inject(args)
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(0)
    for name in ("freecad", "core", "l3", "python", "t0", "profile", "domain", "transaction", "problem",
                 "observation", "output"):
        path = getattr(args, name)
        if path is None:
            parser.error(f"--{name} requis")
        setattr(args, name, path.resolve(strict=name != "output"))
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
