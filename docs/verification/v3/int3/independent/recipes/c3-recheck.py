"""Rejoue la géométrie et recalcule les fronts C.3 depuis les natifs privés."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys


ROOT = Path.cwd().resolve()
RUNTIME = ROOT / ".runtime"
V3 = ROOT / "docs/electromechanical_v3"
FREECAD = Path("C:/Program Files/FreeCAD 1.1/bin/python.exe")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read(path):
    return json.loads(path.read_bytes())


def write(path, data):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(data, stream, ensure_ascii=False, allow_nan=False, indent=2)
        stream.write("\n")


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def artifact(path):
    return {"path": path.relative_to(ROOT).as_posix(), "sha256": digest(path)}


def verify_path(ref):
    path = (ROOT / ref["path"]).resolve(strict=True)
    require(path.is_relative_to(RUNTIME) and digest(path) == ref["sha256"], f"Preuve divergente : {path}")
    return path


def closure(root):
    return {file.relative_to(root).as_posix(): digest(file) for file in root.rglob("*.FCStd")}


def utc():
    return datetime.now(timezone.utc).isoformat()


def run(worker, output, *args):
    command = [str(FREECAD), "-B", str(worker), "worker", *map(str, args)]
    started = utc()
    log = output / "freecad.log"
    log_path = output / "command.json"
    with log.open("xb") as stream:
        process = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT, timeout=120,
                                 env=dict(os.environ, QT_QPA_PLATFORM="offscreen", PYTHONUTF8="1"))
    write(log_path, {"argv": command, "cwd": str(ROOT), "started_utc": started, "finished_utc": utc(),
                     "exit_code": process.returncode, "log": artifact(log)})
    require(process.returncode == 0, f"Mesure FreeCAD en échec : {log}")
    return artifact(log_path)


def corridor_edges(wire, corridors, position):
    import FreeCAD as App
    import Part

    boxes = []
    for limits in corridors:
        low, high = (list(limits[key]) for key in ("min_mm", "max_mm"))
        for index in range(3):
            if low[index] == high[index]:
                low[index] -= position
                high[index] += position
        boxes.append(Part.makeBox(*(right - left for left, right in zip(low, high)), App.Vector(*low)))
    corridor = boxes[0] if len(boxes) == 1 else boxes[0].fuse(boxes[1:])
    rows = []
    for edge in wire.OrderedEdges:
        curve = type(edge.Curve).__name__
        require(curve in {"Line", "LineSegment", "Circle"}, f"Arête non analytique : {curve}")
        clipped = edge.common(corridor)
        require(clipped.isNull() or clipped.isValid(), f"Intersection BRep invalide : {curve}")
        covered = math.fsum(patch.Length for patch in clipped.Edges)
        require(0 <= covered <= edge.Length + position, f"Longueur BRep invalide : {curve}")
        rows.append({"type": curve, "length_mm": edge.Length, "covered_mm": covered,
                     "outside_mm": max(0, edge.Length - covered)})
    return rows


def corridor_probe(output):
    import FreeCAD as App
    import Part

    start, end, crest = App.Vector(-1, 0, 0), App.Vector(1, 0, 0), App.Vector(0, 1, 0)
    whole = {"min_mm": [-1.1, -0.1, -0.1], "max_mm": [1.1, 1.1, 0.1]}
    ends = [{"min_mm": [-1.1, -0.1, -0.1], "max_mm": [-0.8, 0.45, 0.1]},
            {"min_mm": [0.8, -0.1, -0.1], "max_mm": [1.1, 0.45, 0.1]}]
    tolerance = 1e-6
    results = {}
    for name, edge in {"line": Part.makeLine(start, end), "arc": Part.Arc(start, crest, end).toShape()}.items():
        wire = Part.Wire([edge])
        inside, = corridor_edges(wire, [whole], tolerance)
        gap, = corridor_edges(wire, ends, tolerance)
        require(inside["outside_mm"] <= tolerance < gap["outside_mm"], f"Sonde de recoupement invalide : {name}")
        results[name] = {"full_coverage": inside, "endpoints_only": gap}
    write(output, {"status": "PASS", "FreeCAD": ".".join(App.Version()[:3]), "OCCT": Part.OCC_VERSION,
                   "position_tolerance_mm": tolerance, "cases": results})


def native_worker(copy, profile_path, contract_path, obstacle_path, output):
    sys.path.insert(0, str(ROOT))
    import FreeCAD as App
    import Part
    from convergence_manager.native import v3_cross_measure as native

    copy, contract_path, output = (native.private(path) for path in (copy, contract_path, output))
    profile_path = profile_path.resolve(strict=True)
    obstacle_path = native.private(obstacle_path) if obstacle_path else None
    require(profile_path in native.SPATIAL_PROFILES and output.parent.is_dir() and not output.is_relative_to(copy),
            "Profil scellé et sortie privée hors fermeture requis")
    profile = read(profile_path)
    contract = read(contract_path)
    external = read(obstacle_path) if obstacle_path else None
    protected = ROOT / profile["source"]
    before, protected_before = closure(copy), closure(protected)
    require(protected_before == profile["dependencies"] and before.keys() == protected_before.keys() and
            all(value == before[name] for name, value in protected_before.items() if name != profile["entry"]),
            "Fermeture ou dépendance scellée divergente")
    environment = native.setup_cables()
    try:
        document, documents, invalid = native.reopen(copy, profile["entry"], before)
        require(not invalid, f"Objets natifs invalides : {invalid}")
        reader = native.Observation(copy, document, profile["model"], spatial_profile=True,
                                    contract=contract, external=external)
        evidence = reader.measure()
        if external:
            evidence["external_obstacle"] = reader.external_obstacle(external, False)
        else:
            require(document.getObject(native.OBSTACLE_OBJECT) is None, "Obstacle sans entrée évaluateur")

        # OCCT découpe chaque arc et chaque segment sur l'union, en plus du témoin agrégé du moteur.
        position = profile["model"]["validation"]["tolerances"]["position_mm"]
        for identifier, rule in contract["routes"].items():
            top, child = reader.selector(identifier)
            _, world, _ = Part.getShape(top, child, retType=2)
            cable = reader.occurrence(identifier)
            wire, = cable.Base.Shape.copy().transformShape(world.multiply(cable.Placement.inverse().toMatrix()),
                                                          True, True).Wires
            evidence["routes"][identifier]["individual_corridor_edges"] = corridor_edges(wire, rule["corridors_mm"], position)
    finally:
        for name in reversed(list(App.listDocuments())):
            App.closeDocument(name)
        require(not App.listDocuments() and closure(copy) == before and closure(protected) == protected_before,
                "Fermeture, sources ou copie modifiées pendant la mesure")
    evidence.update(schema="v3.cross_measurement/1", status="MEASURED", pid=os.getpid(), environment=environment,
                    documents=documents, invalid_objects=invalid, inputs_sha256=before,
                    sources_unchanged=True, copy_unchanged=True, documents_closed=True)
    write(output, evidence)


def angle(vector, reference):
    cosine = sum(a * b for a, b in zip(vector, reference, strict=True))
    return math.degrees(math.acos(min(1.0, max(-1.0, cosine))))


def measure_metrics(observation, profile, domain, spatial, actions):
    rules = profile["model"]["validation"]
    identities = profile["model"]["occurrences"]
    service = [row["gap_mm"] for row in observation["service"]
               if row["required_action"] in {None, *(action["id"] for action in actions)}]
    picked = spatial["support"]["occurrence"]
    support = observation["supports"][picked]
    classification = observation["interference_classification"]
    cross = classification["cross_harness"]
    require(cross["gap_mm"] + 1e-7 >= domain["minimum_clearance_mm"], "Garde inter-faisceaux hors domaine")
    metrics = {"route_length_mm": 0, "service_clearance_mm": min(service), "support_count": 1,
               "minimum_support_bearing_area_mm2": support["bearing_area_mm2"],
               "maximum_forbidden_interference_mm3": classification["maximum_forbidden_interference_mm3"],
               "minimum_inter_harness_gap_mm": cross["gap_mm"]}
    indexed_pairs = {frozenset(row["pair"]): row["gap_mm"] for row in observation["pairs"]}
    clearances = []
    for name, route in observation["routes"].items():
        rule = rules["routes"][name]
        endpoint_gaps, tangent_errors = [], []
        for index, identifier in enumerate(rule["ports"]):
            port = observation["ports"][identifier]
            origin = [port["matrix"][component] for component in (3, 7, 11)]
            tangent = route["edges"][0]["start_tangent"] if index == 0 else [-n for n in route["edges"][-1]["end_tangent"]]
            endpoint_gaps.append(math.dist(route["endpoints_mm"][index], origin))
            tangent_errors.append(angle(tangent, port["outward"]))
        gaps = [indexed_pairs[frozenset((identities[name], identities[obstacle]))] for obstacle in rule["clearance_obstacles"]]
        prefix = f"harness/{name}/"
        metrics[prefix + "length_mm"] = route["length_mm"]
        metrics[prefix + "minimum_radius_mm"] = route["minimum_radius_mm"]
        metrics[prefix + "maximum_endpoint_gap_mm"] = max(endpoint_gaps)
        metrics[prefix + "maximum_tangent_error_deg"] = max(tangent_errors)
        metrics[prefix + "clearance_mm"] = min(gaps)
        metrics["route_length_mm"] += route["length_mm"]
        clearances.append(min(gaps))
    metrics["route_clearance_mm"] = min(clearances)
    return metrics


def verify_candidate(row, result_root, output, profile_path, domain_path, previous, external):
    from replay_v3_b2 import assessment

    name = row["candidate"]
    profile, domain = read(profile_path), read(domain_path)
    trial = result_root / "candidates" / name
    proposal_path = trial / "proposal.json"
    anchor = trial / "construction/transaction"
    accepted_path = trial / "cross" / name / "candidate-result.json"
    expanded_path = anchor / "expanded-plan.json"
    receipt_path = anchor / "campaign.json"
    proposal, expanded, receipt, accepted = map(read, (proposal_path, expanded_path, receipt_path, accepted_path))
    require(proposal["schema"] == "v3.mutation_plan/4" and proposal["domain_sha256"] == digest(domain_path) and
            accepted["candidate_id"] == name and accepted["final_verdict"] == "PASS" and
            receipt["plan_sha256"] == accepted["proposal_sha256"] == digest(proposal_path) and
            receipt["expanded_plan_sha256"] == digest(expanded_path) and verify_path(accepted["native_receipt"]) == receipt_path,
            f"Identité de proposition/fermeture divergente : {name}")
    if external:
        require(expanded["external_obstacle"] == external, "Obstacle natif différent du volume de l’évaluateur")
    else:
        require("external_obstacle" not in expanded, "Obstacle inattendu dans le plan")

    option = expanded["support_option"]
    holder = domain["support_options"][option]
    spatial = {"minimum_clearance_mm": domain["minimum_clearance_mm"],
               "support": {"id": option, "occurrence": holder["occurrence"], "anchor_zone": holder["anchor_zone"]},
               "routes": {key: {"corridors_mm": rule["route"]["polycorridors"], "nominal_plane": rule["route"]["nominal_plane"]}
                          for key, rule in domain["harnesses"].items()}}
    require(spatial == expanded["spatial_contract"] and domain["profile_sha256"] == digest(profile_path),
            "Contrat spatial différent du domaine scellé")
    private = output / name
    copy = private / "cad"
    copy.mkdir(parents=True, exist_ok=False)
    native_source = anchor / "cad"
    expected = receipt["native_sha256"]
    require(closure(native_source) == expected, f"Fermeture native divergente : {name}")
    for file in expected:
        target = copy / file
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(native_source / file, target)
        target.chmod(stat.S_IREAD)
    require(closure(copy) == expected, f"Copie privée différente : {name}")

    contract_path, external_path = private / "contract.json", private / "external.json"
    measure_path = private / "remeasured.json"
    write(contract_path, spatial)
    args = [copy, profile_path, contract_path, measure_path]
    if external:
        write(external_path, external)
        args += ["--obstacle", external_path]
    command = run(Path(__file__).resolve(), private, *args)
    observed = read(measure_path)
    initial = read(verify_path(accepted["measurements"]))
    require(observed["inputs_sha256"] == expected == closure(native_source) == initial["inputs_sha256"] and
            set(observed["documents"]) == set(expected) and observed["pid"] != initial["pid"],
            f"Provenance de contre-mesure divergente : {name}")
    baseline = read(verify_path(previous))
    assessments = assessment(profile, baseline, observed, expanded["actions"], spatial, external)
    write(private / "assessments.json", assessments)
    blocking = [row["id"] for row in assessments if row["status"] not in {"PASS", "NOT_APPLICABLE"}]
    require(not blocking, f"Contraintes géométriques : {name} {blocking}")

    geometry = {}
    position = profile["model"]["validation"]["tolerances"]["position_mm"]
    for key, route in observed["routes"].items():
        individual = route["individual_corridor_edges"]
        outside = math.fsum(edge["outside_mm"] for edge in individual)
        require(outside <= position and abs(outside - route["outside_corridor_mm"]) <= position,
                f"Segment ou arc hors corridor : {name}/{key} ({outside} mm)")
        internal_gaps = [math.dist(first["end_mm"], second["start_mm"])
                         for first, second in zip(route["edges"], route["edges"][1:])]
        internal_tangencies = [angle(first["end_tangent"], second["start_tangent"])
                              for first, second in zip(route["edges"], route["edges"][1:])]
        direction = profile["model"]["validation"]["tolerances"]["direction_deg"]
        require(max(internal_gaps, default=0) <= position and max(internal_tangencies, default=0) <= direction,
                f"Discontinuité interne : {name}/{key}")
        geometry[key] = {"axis_sha256": route["axis_sha256"], "departure_mm": route["vertex_departure_mm"],
                         "line_count": sum(edge["type"] != "Circle" for edge in individual),
                         "arc_count": sum(edge["type"] == "Circle" for edge in individual),
                         "outside_corridors_mm": outside, "maximum_joint_gap_mm": max(internal_gaps, default=0),
                         "maximum_joint_tangent_error_deg": max(internal_tangencies, default=0)}

    metrics = measure_metrics(observed, profile, domain, spatial, expanded["actions"])
    require(metrics.keys() == row["metrics"].keys(), f"Couverture de métriques divergente : {name}")
    mismatches = [key for key, value in metrics.items() if not math.isclose(
        value, row["metrics"][key], rel_tol=0, abs_tol=2e-6 if "tangent" in key else 1e-7)]
    require(not mismatches, f"Métriques réexécutées divergentes : {name} {mismatches}")
    return {"id": name, "measurement": artifact(measure_path), "command": command,
            "checks": len(assessments), "assessment": artifact(private / "assessments.json"),
            "candidate_receipt": artifact(receipt_path), "native_sha256": expected,
            "geometry": geometry, "metrics": metrics, "ports": {key: port["datum"] for key, port in observed["ports"].items()},
            "parents": sorted(observed["parent_matrices"]),
            "anchor": observed["spatial_support_zone"], "external": observed.get("external_obstacle"),
            "process_id": observed["pid"], "previous_process_id": initial["pid"], "environment": observed["environment"]}


def objective_vector(metrics, objectives):
    positive = [math.floor(metrics[item["metric"]] / item["tolerance"] + 0.5) for item in objectives]
    return tuple(value if item["direction"] == "MIN" else -value for value, item in zip(positive, objectives, strict=True))


def dominates(a, b):
    return a != b and all(left <= right for left, right in zip(a, b, strict=True))


def check_phase(campaign, phase, output):
    card = campaign / phase.lower()
    summary_path = card / "summary.json"
    summary = read(summary_path)
    require(summary["phase"] == phase and summary["finalized"] and summary["phase_pass"], f"Campagne incomplète : {phase}")
    report_path, ranking_path = (verify_path(summary[key]) for key in ("campaign", "pareto"))
    final, ranking = read(report_path), read(ranking_path)
    problem_path, t0_path = (verify_path(summary[key]) for key in ("problem", "t0"))
    problem = read(problem_path)
    require(read(t0_path)["exit_code"] == 0, "Validation T0 absente ou en échec")
    require(summary["scope"] == "SYNTHETIC_BENCH" and final["budget"] == problem["budget"], "Portée ou budget divergent")
    result = {"summary": artifact(summary_path), "campaign": artifact(report_path), "problem": artifact(problem_path),
              "pareto": artifact(ranking_path), "t0": artifact(t0_path),
              **{key: final[key] for key in ("verdict", "reason", "proposals", "native_attempts", "counterchecks",
                                           "qualified_candidates", "elapsed_ms", "elapsed_budget_reached", "budget")}}
    if phase == "T4":
        require(final["reason"] == "INCONCLUSIVE" and final["elapsed_budget_reached"] and
                final["verdict"] == "V3_C_CONDITIONAL" and not final["retained"] and
                all(final[key] == 0 for key in ("proposals", "native_attempts", "counterchecks", "qualified_candidates")) and
                not ranking["admissible"] and not ranking["front"], "T4 n’a pas fermé l’admission à l’épuisement")
        return result

    bench = "c3_spatial_secondary" if phase == "T3" else "c3_spatial"
    domain_path, profile_path = V3 / f"domains/{bench}.json", V3 / f"bench_{bench}/profile.json"
    require(problem["domain_sha256"] == digest(domain_path), f"Domaine de campagne divergent : {phase}")
    external = None
    if phase == "T2":
        perturbation = verify_path(summary["external_perturbation"]["input"])
        external = read(perturbation)["obstacle"]
        result["perturbation"] = artifact(perturbation)
    attestations = list((card / phase / "candidates").glob("*/cross/*/candidate-result.json"))
    declared_pass = {read(path)["candidate_id"] for path in attestations if read(path)["final_verdict"] == "PASS"}
    require(ranking["comparison"] == "ROUND_MEASURE_TO_NEAREST_TOLERANCE_BIN" and
            set(row["candidate"] for row in ranking["admissible"]) == declared_pass and
            len(declared_pass) == len(ranking["admissible"]) == final["qualified_candidates"],
            "Candidats ou règle Pareto non réconciliés")
    output.mkdir(parents=True, exist_ok=False)
    sys.path.insert(0, str(ROOT / "convergence_manager/tests"))
    # Limite deux processus de mesure simultanés, sans modifier les budgets de campagne.
    with ThreadPoolExecutor(max_workers=2) as pool:
        candidates = list(pool.map(lambda row: verify_candidate(row, card / phase, output, profile_path,
                                                                domain_path, summary["observation"], external),
                                   ranking["admissible"]))
    binned = {row["id"]: objective_vector(row["metrics"], problem["objectives"]) for row in candidates}
    front = {identifier for identifier, score in binned.items() if not any(dominates(other, score) for other in binned.values())}
    require(front == {row["candidate"] for row in ranking["front"]}, "Front Pareto recalculé différent")
    retained = min(front, key=lambda identifier: (binned[identifier], identifier))
    require(retained == final["retained"]["candidate_id"], "Gagnant Pareto différent")
    require(any(sum(1 for other in front if binned[key] != binned[other]) for key in front),
            "Front Pareto sans variation de compromis")
    result.update(admissible=candidates, front_recalculated=sorted(front), retained=retained,
                  objective_bins=binned, model_profile=artifact(profile_path), domain=artifact(domain_path))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="mode", required=True)
    run_worker = subparsers.add_parser("worker")
    for name in ("copy", "profile", "contract", "output"):
        run_worker.add_argument(name, type=Path)
    run_worker.add_argument("--obstacle", type=Path)
    run_probe = subparsers.add_parser("probe")
    run_probe.add_argument("output", type=Path)
    run_phase = subparsers.add_parser("phase")
    run_phase.add_argument("phase", choices=("T1", "T2", "T3", "T4"))
    run_phase.add_argument("campaign", type=Path)
    run_phase.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.mode == "worker":
        native_worker(args.copy, args.profile, args.contract, args.obstacle, args.output)
    elif args.mode == "probe":
        corridor_probe(args.output)
    else:
        result = check_phase(args.campaign.resolve(), args.phase, args.output.resolve() / args.phase.lower())
        args.output.mkdir(parents=True, exist_ok=True)
        write(args.output / f"{args.phase.lower()}-recheck.json", result)
        print(args.phase, result["reason"], result["qualified_candidates"], flush=True)


if __name__ == "__main__":
    main()
