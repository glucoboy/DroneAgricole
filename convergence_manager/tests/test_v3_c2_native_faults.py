"""Injecte des défauts C.2 sur des fermetures XLink privées et réouvre les BRep."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

from test_v3_b2_native_faults import PROJECT, closure, guard, private_path, proof, read, require, write


WORKERS = PROJECT / "convergence_manager/native"
FAILURES = {
    "harness-b-hits-obstacle": "L4_GEOMETRY",
    "stale-port-b": "L2_TOPOLOGY",
    "permuted-pins-b": "L2_TOPOLOGY",
    "lost-continuity-b": "L2_TOPOLOGY",
    "negative-service-clearance": "L4_SERVICE",
    "radius-under-limit-b": "L4_DYNAMIC_BEND_RADIUS",
    "floating-support": "L4_SUPPORT_ANCHOR",
    "harnesses-collide": "L4_GEOMETRY",
    "missing-fastener-engagement": "L4_SUPPORT_ANCHOR",
}


def invoke(args, case, label, worker, expected, **options):
    command = [str(args.freecad), "-B", str(worker)]
    for key, value in options.items():
        command.extend(["--" + key.replace("_", "-"), str(value)])
    log = case / f"{label}.log"
    with log.open("xb") as stream:
        performed = subprocess.run(command, cwd=PROJECT, stdout=stream, stderr=subprocess.STDOUT,
                                   timeout=75, check=False,
                                   env=dict(os.environ, PYTHONUTF8="1", QT_QPA_PLATFORM="offscreen"))
    invocation = case / f"{label}-invocation.json"
    write(invocation, {"argv": command, "exit_code": performed.returncode,
                       "freecad_python_sha256": guard.sha256(args.freecad), "log": proof(log)})
    require(performed.returncode in expected, f"Code inattendu : {invocation}")
    return proof(invocation)


def route_midpoint(native, assembly, identifier, other=None):
    cable = assembly.occurrence(identifier)
    path = native.Part.getShape(cable.Base)
    for edge in sorted(path.Edges, key=lambda item: item.Length, reverse=True):
        point = edge.valueAt((edge.FirstParameter + edge.LastParameter) / 2)
        if other is None or native.Part.getShape(assembly.occurrence(other)).distToShape(native.Part.Vertex(point))[0] > 5:
            return point
    raise RuntimeError(f"Tronçon discriminant introuvable : {identifier}")


def confine_obstacle(native, obstacle, position):
    obstacle.Length = obstacle.Width = obstacle.Height = 3
    obstacle.Placement = native.App.Placement(position - native.App.Vector(1.5, 1.5, 1.5), native.App.Rotation())


def modify(fault, native, assembly, job):
    app = native.App
    actions = job["actions"]
    rules = job["model"]["validation"]
    harness_b = actions[2]["occurrence"]
    cable_b = assembly.occurrence(harness_b)
    selected = actions[-1]
    if fault == "harness-b-hits-obstacle":
        point = route_midpoint(native, assembly, harness_b, actions[1]["occurrence"])
        confine_obstacle(native, assembly.occurrence("shared-obstacle"), point)
    elif fault == "stale-port-b":
        # Le second proxy de terminaison demeure attaché à un équipement
        # désynchronisé du repère indépendant mesuré dans le XLink mobile.
        owner = rules["ports"][rules["routes"][harness_b]["ports"][1]]["attachment_equipment"]
        placement = app.Placement(assembly.world(owner))
        placement.Base += app.Vector(1, 2, 0)
        assembly.set_world(owner, placement.toMatrix())
    elif fault == "permuted-pins-b":
        port = rules["routes"][harness_b]["ports"][1]
        names = {name for name, row in rules["contacts"].items() if row["port"] == port}
        one, two = [obj for obj in assembly.document.Objects if getattr(obj, "L2Id", None) in names]
        one.PinName, two.PinName = str(two.PinName), str(one.PinName)
    elif fault == "lost-continuity-b":
        cable_b.L2Conductors = list(cable_b.L2Conductors)[:-1]
    elif fault == "negative-service-clearance":
        envelope = assembly.occurrence("service-extraction-d")
        confine_obstacle(native, assembly.occurrence("shared-obstacle"), native.Part.getShape(envelope).BoundBox.Center)
    elif fault == "radius-under-limit-b":
        cable_b.Base.FilletRadius = rules["routes"][harness_b]["minimum_radius_mm"] - 0.5
    elif fault in {"floating-support", "missing-fastener-engagement"}:
        subject = selected["occurrence"] if fault == "floating-support" else selected["parameters"]["fasteners"][0]
        placement = app.Placement(assembly.world(subject))
        placement.Base += app.Vector(0, 0, 0.4 if fault == "floating-support" else -3)
        assembly.set_world(subject, placement.toMatrix())
    elif fault == "harnesses-collide":
        from convergence_manager.native.v3_mutate import update_route

        parameters = actions[2]["parameters"]
        start, end = [app.Vector(*parameters["points_mm"][index]) for index in (0, -1)]
        lead = start + app.Vector(*parameters["start_axis"]) * 14
        tail = end + app.Vector(*parameters["end_axis"]) * 14
        first_path = native.Part.getShape(assembly.occurrence(actions[1]["occurrence"]).Base)
        middle = (lead.x + tail.x) / 2
        samples = [edge.valueAt(edge.FirstParameter + fraction * (edge.LastParameter - edge.FirstParameter))
                   for edge in first_path.Edges for fraction in (0.2, 0.5, 0.8)]
        target = min(samples, key=lambda point: abs(point.x - middle))
        # Traverser le premier axe à angle non nul pour que le volume
        # commun des gaines soit discriminant près d’une jonction OCC.
        points = [start, lead, app.Vector(target.x - 9, target.y + 9, start.z),
                  app.Vector(target.x + 9, target.y - 9, start.z), tail, end]
        update_route(assembly, harness_b, cable_b, points,
                     rules["routes"][harness_b]["diameter_mm"], rules["routes"][harness_b]["minimum_radius_mm"])
    else:
        raise ValueError(f"Défaut inconnu : {fault}")
    if fault in {"radius-under-limit-b", "harnesses-collide"}:
        rebuilt = native.geometry.rebuild_cable_in_isolated_document(assembly.document, cable_b)
        require(rebuilt["status"] == "pass", f"Le témoin doit posséder une gaine BRep fraîche : {rebuilt}")


def inject(args):
    from convergence_manager.native.v3_mutate import Assembly, native

    root, job_path, output = map(private_path, (args.root, args.job, args.result))
    require(root.name == "injected-cad" and root.parent == output.parent == job_path.parent,
            "L’injection exige une fermeture privée distincte")
    job = read(job_path)
    entry = job["entry"]
    before = closure(root, entry)
    require(job["dependencies"] == before, "Fermeture divergente avant injection")
    native.cables_environment(gui=True)
    app = native.App
    doc = app.openDocument(str(root / entry))
    try:
        native.complete_dependencies(doc, root)
        native.recalculate(doc, root)
        modify(args.inject, native, Assembly(doc, job["model"]["occurrences"]), job)
        require(doc.recompute() is not False, "Recalcul du défaut natif non finalisé")
        doc.save()
    finally:
        for name in reversed(list(app.listDocuments())):
            app.closeDocument(name)
    after = closure(root, entry)
    require(before.keys() == after.keys() and before[entry] != after[entry]
            and all(before[name] == after[name] for name in before if name != entry),
            "Le défaut doit changer le document de tête seul")
    write(output, {"fault": args.inject, "pid": os.getpid(), "worker_id": uuid4().hex,
                   "before_sha256": before, "after_sha256": after})


def measure_fault(args, area, candidate, source_job, fault):
    case = area / fault
    cad = case / "injected-cad"
    guard.stage(candidate, source_job["entry"], cad)
    job, measured = case / "candidate-job.json", case / "verification.json"
    initial, injected = case / "original-job.json", case / "injection.json"
    write(initial, source_job)
    start = invoke(args, case, "inject", Path(__file__), {0}, inject=fault, root=cad, job=initial, result=injected)
    witness = read(injected)
    write(job, {**source_job, "dependencies": witness["after_sha256"]})
    verify = invoke(args, case, "verify", WORKERS / "v3_verify.py", {0}, root=cad, job=job, output=measured)
    observation = read(measured)
    statuses = {row["id"]: row for row in observation["checks"]}
    check = statuses[FAILURES[fault]]
    require(observation["status"] == "FAIL" and observation["reopened"] and observation["documents_closed"]
            and observation["inputs_sha256"] == witness["after_sha256"] and witness["pid"] != observation["pid"]
            and check["status"] == "FAIL", f"Défaut non mesuré : {measured}")
    result = {"status": "DETECTED", "check": check["id"], "injection": proof(injected),
              "verification": proof(measured), "invocations": [start, verify]}
    if fault in {"harness-b-hits-obstacle", "harnesses-collide", "missing-fastener-engagement"}:
        cross_path = case / "cross.json"
        result["invocations"].append(invoke(args, case, "cross", WORKERS / "v3_cross_measure.py", {0},
                                             root=cad, profile=args.profile, output=cross_path))
        cross = read(cross_path)
        geometry = cross["interference_classification"]
        require(cross["pid"] not in {observation["pid"], witness["pid"]} and cross["copy_unchanged"]
                and cross["inputs_sha256"] == witness["after_sha256"], "Contre-mesure indépendante requise")
        if fault == "harness-b-hits-obstacle":
            paths = source_job["model"]["occurrences"]
            hit = {paths[name] for name in ("cordon-b", "shared-obstacle")}
            require(geometry["status"] == "FAIL" and any(set(row["pair"]) == hit for row in geometry["forbidden_interferences"])
                    and all(paths["cordon"] not in row["pair"] for row in geometry["forbidden_interferences"]),
                    "Le cas différentiel doit heurter exclusivement le second câble")
        elif fault == "harnesses-collide":
            require(geometry["cross_harness"]["intersection_mm3"] > 0
                    and geometry["cross_harness"]["status"] == "FAIL", "Collision des deux gaines non démontrée")
        else:
            require(not any(row["status"] == "PASS" for row in geometry["authorized_engagements"]),
                    "Engagement inexistant déclaré autorisé")
        result["independent_brep"] = proof(cross_path)
    return result


def rollback(args, area, profile, transaction):
    case = area / "rollback-after-first-harness"
    cad = case / "rollback-cad"
    source = PROJECT / profile["source"]
    guard.stage(source, profile["entry"], cad)
    before = closure(cad, profile["entry"])
    job, result = case / "build-job.json", case / "build.json"
    build = deepcopy(read(transaction / "build-job.json"))
    build["actions"][2]["parameters"]["points_mm"][-1][1] += 3
    write(job, build)
    invocation = invoke(args, case, "rollback", WORKERS / "v3_mutate.py", {2}, root=cad, job=job, output=result)
    observed = read(result)
    operations = observed["operations"]
    require(observed["memory_transaction"] == "ABORTED" and not observed["save_performed"]
            and observed["documents_closed"] and operations[1]["status"] == "APPLIED_IN_MEMORY"
            and operations[2]["status"] == "STARTED" and operations[3]["status"] == "NOT_RUN"
            and "divergent du port natif" in observed["reason"]
            and before == closure(cad, profile["entry"]) == profile["dependencies"],
            "Annulation atomique non démontrée")
    return {"status": "DETECTED", "verification": proof(result), "invocations": [invocation]}


def forged_engagement(args, area, candidate, original):
    case = area / "forged-engagement-authority"
    cad = case / "native-cad"
    guard.stage(candidate, original["entry"], cad)
    job, result = case / "candidate-job.json", case / "verification.json"
    changed = deepcopy(original)
    selected = changed["actions"][-1]["id"]
    rules = changed["model"]["validation"]["allowed_interferences"]
    for row in rules:
        if row["required_action"] == selected:
            row["parts"] = ["cordon", "cordon-b"]
    write(job, changed)
    invocation = invoke(args, case, "reject", WORKERS / "v3_verify.py", {0}, root=cad, job=job, output=result)
    observation = read(result)
    require(observation["status"] == "INCONCLUSIVE" and any(
            row["id"] == "NATIVE_MEASUREMENT" and "sans engagement de fixation applicable" in row["details"]
            for row in observation["checks"])
            and observation["documents_closed"], "La justification seule ne peut autoriser un recoupement")
    return {"status": "DETECTED", "verification": proof(result), "invocations": [invocation]}


def run(args):
    transaction, area = map(private_path, (args.transaction, args.output))
    profile = read(args.profile)
    candidate, source = transaction / "cad", PROJECT / profile["source"]
    original = read(transaction / "candidate-job.json")
    original["model"] = profile["model"]
    before = closure(candidate, original["entry"])
    validation = transaction / "candidate-validation.json"
    require(read(validation)["status"] == "PASS" and before == original["dependencies"],
            "Un candidat C.2 rouvert et vérifié est requis")
    transaction_receipt = transaction / "campaign.json"
    if transaction_receipt.is_file():
        recorded = read(transaction_receipt)
        require(recorded["status"] == "PASS" and recorded["candidate_state"] == "CANDIDATE"
                and recorded["execution_scope"] == "BENCH_TEST_ONLY" and recorded["native_sha256"] == before,
                "Le reçu de transaction C.2 ne correspond pas au candidat vérifié")
    area.mkdir(parents=True)
    with ThreadPoolExecutor(max_workers=2) as pool:
        cases = {fault: pool.submit(measure_fault, args, area, candidate, original, fault) for fault in FAILURES}
        results = {fault: future.result() for fault, future in cases.items()}
    results["forged-engagement-authority"] = forged_engagement(args, area, candidate, original)
    results["rollback-after-first-harness"] = rollback(args, area, profile, transaction)
    require(closure(candidate, original["entry"]) == before and closure(source, profile["entry"]) == profile["dependencies"],
            "Fermeture admise ou source commune modifiée")
    write(area / "adversarial.json", {"schema": "v3.c2.native_faults/1", "status": "PASS", "cases": results,
                                      "profile": proof(args.profile), "candidate_validation": proof(validation),
                                      "transaction": proof(transaction_receipt) if transaction_receipt.is_file() else None,
                                      "candidate_sha256": before, "shared_source_sha256": profile["dependencies"]})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("freecad", "profile", "transaction", "output", "root", "job", "result"):
        parser.add_argument(f"--{name}", type=Path)
    parser.add_argument("--inject", choices=FAILURES, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.inject:
        inject(args)
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(0)
    for name in ("freecad", "profile", "transaction", "output"):
        if getattr(args, name) is None:
            parser.error(f"--{name} requis")
    args.freecad = args.freecad.resolve(strict=True)
    args.profile = args.profile.resolve(strict=True)
    run(args)
