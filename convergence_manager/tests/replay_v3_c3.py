"""Gèle les autorités C.3 et rejoue les quatre phases sur copies privées."""

import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import subprocess

from replay_v3_b1 import ROOT, digest, load, write
from replay_v3_b2 import MEASURER, artifact, closure, invoke, measurement
from replay_v3_c import run_campaign, source_commit


V3 = ROOT / "docs/electromechanical_v3"
BUDGET = {"max_proposals": 64, "max_native": 12, "max_seconds": 540, "max_counterchecks": 12}
T4_BUDGET = {"max_proposals": 1, "max_native": 1, "max_seconds": 1, "max_counterchecks": 1}
SEED = 2026
OBJECTIVES = [
    {"metric": "route_length_mm", "direction": "MIN", "tolerance": 0.01},
    {"metric": "route_clearance_mm", "direction": "MAX", "tolerance": 0.01},
    {"metric": "minimum_inter_harness_gap_mm", "direction": "MAX", "tolerance": 0.01},
]


def require(ok, message):
    if not ok:
        raise ValueError(message)


def utc():
    return datetime.now(timezone.utc).isoformat()


def unique_object(pairs):
    result = {}
    for name, value in pairs:
        require(name not in result, "Champ dupliqué : " + name)
        result[name] = value
    return result


def authority(phase):
    name = "c3_spatial_secondary" if phase == "T3" else "c3_spatial"
    domain_path = V3 / "domains" / f"{name}.json"
    profile_path = V3 / f"bench_{name}/profile.json"
    domain, profile = load(domain_path), load(profile_path)
    require(domain["schema"] == "v3.parametric_domain/3" and domain["domain"] == "SYNTHETIC_BENCH"
            and digest(profile_path) == domain["profile_sha256"]
            and digest(ROOT / profile["graph"]) == profile["graph_sha256"],
            "Autorités C.3 divergentes")
    closure(ROOT / profile["source"], profile["dependencies"])
    return domain_path, domain, profile_path, profile


def sealed_inputs(args):
    tools = {name: str(getattr(args, name)) for name in ("core", "l3", "t0", "freecad", "python")}
    paths = [Path(value) for value in tools.values()]
    paths += [Path(__file__).resolve(), *ROOT.glob("convergence_manager/native/v3_*.py")]
    paths += [ROOT / name for name in (
        "convergence_manager/tests/replay_v3_b1.py", "convergence_manager/tests/replay_v3_b2.py",
        "convergence_manager/tests/replay_v3_c.py", "electromechanical_engine/freecad_worker.py",
        "electromechanical_engine/v3_native.py", "electromechanical_engine/xlink_native.py",
        "electromechanical_engine/freecad.py", "electromechanical_engine/contracts.py",
        "electromechanical_engine/native_motion.py", "electromechanical_engine/native_retention.py",
        "hardware/mecanique/cartographe/verification/cable_workbench_prototype.py",
        ".agents/skills/electromechanical-integration/scripts/freecad_geometry.py",
        ".agents/skills/electromechanical-integration/scripts/workspace_guard.py",
        "interconnection_engine/src/Reconcile.cpp")]
    paths += [V3 / name for name in ("problem_spec_v3.schema.json", "mutation_plan_v4.schema.json",
                                     "parametric_domain_v3.schema.json", "candidate_result.schema.json")]
    for phase in ("T1", "T3"):
        domain_path, _, profile_path, profile = authority(phase)
        paths += [domain_path, profile_path, ROOT / profile["graph"]]
        paths += [ROOT / profile["source"] / name for name in profile["dependencies"]]
    return {"scope": "SYNTHETIC_BENCH", "source_commit": source_commit(), "tools": tools,
            "seed": SEED, "budget": BUDGET, "t4_budget": T4_BUDGET, "objectives": OBJECTIVES,
            "criteria": {"T1": "Deux candidats contre-validés et au moins un câble hors du plan nominal",
                         "T2": "Collision BRep T1 et nouvelle géométrie 3D du câble touché, les deux câbles conformes",
                         "T3": "Autre hiérarchie native de port et câble hors du plan nominal",
                         "T4": "Aucune admission au dépassement du budget"},
            "files_sha256": {str(path): digest(path) for path in sorted(set(paths))}}


def frozen_artifact(entry):
    path = ROOT / entry["path"]
    require(digest(path) == entry["sha256"], f"Artefact gelé modifié : {path}")
    return path


def read_freeze(args, freeze_path):
    snapshot = load(freeze_path)
    current = sealed_inputs(args)
    expected = snapshot["inputs"]
    # Un commit documentaire peut suivre le commit source testé.
    current["source_commit"] = expected["source_commit"]
    require(current == expected, "Binaires, outils ou autorités modifiés depuis le gel C.3")
    for record in snapshot["t1"].values():
        frozen_artifact(record)
    return snapshot


def prove_collision(args, case, freeze_path, perturbation, expected_digest, profile_path, profile):
    require(perturbation.absolute() == perturbation.resolve(strict=True) and
            perturbation.is_relative_to(ROOT / ".runtime") and
            not perturbation.is_relative_to(case.parent) and
            digest(perturbation) == expected_digest and perturbation.stat().st_nlink == 1,
            "Entrée évaluateur, emplacement indépendant ou SHA incorrect")
    snapshot = load(freeze_path)
    with perturbation.open(encoding="utf-8") as stream:
        payload = json.load(stream, object_pairs_hook=unique_object)
    require(set(payload) == {"schema", "issued_at_utc", "evaluator", "freeze_sha256",
                             "t1_root_sha256", "t1_problem_sha256", "obstacle"} and
            payload["schema"] == "v3.c3.external_perturbation/1" and
            isinstance(payload["evaluator"], str) and bool(payload["evaluator"].strip()) and
            payload["freeze_sha256"] == digest(freeze_path) and
            payload["t1_root_sha256"] == snapshot["t1"]["candidate"]["sha256"] and
            payload["t1_problem_sha256"] == snapshot["t1"]["problem"]["sha256"],
            "Reçu indépendant non lié au gel et à la T1 exacte")
    issued = datetime.fromisoformat(payload["issued_at_utc"])
    require(issued.utcoffset() == timezone.utc.utcoffset(issued) and
            datetime.fromisoformat(snapshot["frozen_at_utc"]) < issued <= datetime.now(timezone.utc),
            "Le reçu indépendant doit être émis en UTC après le gel")
    obstacle = case / "obstacle.json"
    write(obstacle, payload["obstacle"])
    candidate = frozen_artifact(snapshot["t1"]["candidate"])
    retained = load(frozen_artifact(snapshot["t1"]["summary"]))["retained"]
    closure(candidate.parent, retained["native_sha256"])
    measured = case / "t1-obstacle-collision.json"
    argv = [args.freecad, "-B", MEASURER, "--root", candidate.parent, "--profile", profile_path,
            "--output", measured, "--external-obstacle", obstacle,
            "--expected-entry-sha256", payload["t1_root_sha256"], "--require-absent"]
    result = invoke(case, "external-collision", list(map(str, argv)))
    require(result.returncode == 0, f"Mesure BRep T1 non finalisée : {result.stderr}")
    observation = load(measured)
    volume_limit = profile["model"]["validation"]["tolerances"]["volume_mm3"]
    exact = observation["external_obstacle"]
    require(exact["presence"] == "HYPOTHETICAL" and observation["status"] == "MEASURED" and
            observation["copy_unchanged"] and observation["documents_closed"] and
            observation["inputs_sha256"] == retained["native_sha256"] and observation["external_sha256"] == digest(obstacle),
            "Collision T1 sans provenance de mesure")
    impacted = sorted(name for name, row in exact["harnesses"].items() if row["intersection_mm3"] > volume_limit)
    require(impacted, "L'obstacle évaluateur ne réfute aucun câble de la T1")
    receipt = {"input": artifact(perturbation), "verified_payload": payload, "collision": artifact(measured),
               "invalidated_harnesses": impacted, "t1_volume_mm3": {name: row["intersection_mm3"]
                 for name, row in exact["harnesses"].items()}}
    write(case / "external_perturbation_receipt.json", receipt)
    return payload["obstacle"], receipt


def interior_route_delta(old, new, plane, tolerance):
    """Distance mesurée entre un nouveau sommet hors plan et les sommets T1."""
    axis = "XYZ".index(plane["axis"])
    coordinate = plane["coordinate_mm"]
    vertices = lambda route: [edge["end_mm"] for edge in route["edges"][:-1]]
    old_vertices = [old["edges"][0]["start_mm"], *vertices(old), old["edges"][-1]["end_mm"]]
    distances = [(min(math.dist(vertex, other) for other in old_vertices), vertex)
                 for vertex in vertices(new) if abs(vertex[axis] - coordinate) > tolerance]
    distance, vertex = max(distances, default=(0, None))
    return {"nearest_t1_vertex_distance_mm": distance, "t2_interior_vertex_mm": vertex}


def run_phase(args, area, freeze_path):
    phase = args.phase
    domain_path, domain, profile_path, profile = authority(phase)
    case = area / phase.lower()
    case.mkdir()
    model = ROOT / profile["source"] / profile["entry"]
    placement = domain["placement"]
    base, external = None, None
    if phase == "T2":
        snapshot = read_freeze(args, freeze_path)
        base = frozen_artifact(snapshot["t1"]["problem"])
        observation = frozen_artifact(snapshot["t1"]["observation"])
        request = {**load(base), "phase": phase, "base_problem_sha256": digest(base)}
        request["external_obstacle"], external = prove_collision(args, case, freeze_path, args.perturbation,
                                                                  args.perturbation_sha256, profile_path, profile)
    else:
        _, observation = measurement(args.freecad, case, "reference", model.parent,
                                     profile["dependencies"], profile_path)
        request = {"schema": "v3.problem_spec/3", "phase": phase, "domain_sha256": digest(domain_path),
                   "model_sha256": digest(model), "observation_sha256": digest(observation), "seed": SEED,
                   "budget": T4_BUDGET if phase == "T4" else BUDGET, "objectives": OBJECTIVES,
                   "narrowing": {"translation_mm": {"min": placement["translation_min_mm"],
                                                      "max": placement["translation_max_mm"]}}}
    request_path = case / f"{phase}-request.json"
    problem = case / f"{phase}-problem.json"
    write(request_path, request)
    argv = [args.l3, "v3-problem", "--root", ROOT, "--request", request_path, "--domain", domain_path,
            "--model", model, "--observation", observation, "--output", problem]
    if base:
        argv.extend(("--base-problem", base))
    proc = invoke(case, "L3", list(map(str, argv)))
    require(proc.returncode == 0 and problem.is_file(), f"L3 {phase} a refusé le problème : {proc.stderr}")
    report = run_campaign(args, case, phase, problem, observation, base)
    directory = case / phase
    t0 = directory / "t0-crosscheck.json"
    require(report["finalized"] and load(t0)["exit_code"] == 0, "Campagne ou validation T0 incomplète")
    retained = report["retained"]
    summary = {**report, "campaign": artifact(directory / "campaign.json"), "problem": artifact(problem),
               "observation": artifact(observation), "pareto": artifact(directory / "pareto.json"),
               "t0": artifact(t0), "completed_at_utc": utc(), "external_perturbation": external}
    if retained:
        result_path = directory / retained["result"]
        require(digest(result_path) == retained["result_sha256"], "Reçu candidat divergent")
        result = load(result_path)
        observed_path = frozen_artifact(result["measurements"])
        observed = load(observed_path)
        candidate = directory / "candidates" / retained["candidate_id"] / "construction/transaction/cad" / profile["entry"]
        require(digest(candidate) == retained["native_sha256"][profile["entry"]], "Natif candidat divergent")
        summary.update(candidate=artifact(candidate), routes=artifact(observed_path), countercheck=artifact(result_path))
        tol = profile["model"]["validation"]["tolerances"]
        departures = {name: row["vertex_departure_mm"] for name, row in observed["routes"].items()}
        summary["nominal_departure_mm"] = departures
        changed = [name for name, departure in departures.items() if departure > tol["position_mm"]]
        verdict_ok = bool(changed)
        if external:
            first = load(frozen_artifact(snapshot["t1"]["routes"]))
            exact = observed["external_obstacle"]
            saved = exact["presence"] == "SAVED_NATIVE" and all(
                row["intersection_mm3"] <= tol["volume_mm3"] for row in exact["harnesses"].values())
            deltas = {name: interior_route_delta(first["routes"][name], observed["routes"][name],
                                               domain["harnesses"][name]["route"]["nominal_plane"], tol["position_mm"])
                      for name in external["invalidated_harnesses"]}
            adapted = sorted(name for name in external["invalidated_harnesses"] if name in changed and
                             observed["routes"][name]["axis_sha256"] != first["routes"][name]["axis_sha256"] and
                             deltas[name]["nearest_t1_vertex_distance_mm"] > tol["position_mm"])
            summary["native_delta"] = {"adapted_harnesses": adapted, "interior_vertex_delta": deltas,
                                       "t1": first["routes"], "t2": observed["routes"], "t2_obstacle": exact}
            verdict_ok = saved and bool(adapted)
        elif phase == "T3":
            first = load(frozen_artifact(load(freeze_path)["t1"]["routes"])) if freeze_path.is_file() else None
            if first:
                changed_ports = sorted(name for name, port in observed["ports"].items() if
                                       port["datum"] != first["ports"][name]["datum"])
                summary["different_datum_paths"] = changed_ports
                verdict_ok = verdict_ok and bool(changed_ports) and set(observed["parent_matrices"]) != set(first["parent_matrices"])
        summary["phase_pass"] = verdict_ok and (phase != "T1" or report["qualified_candidates"] >= 2)
    else:
        summary["phase_pass"] = phase == "T4" and report["reason"] in {
            "NO_FEASIBLE_CANDIDATE_FOUND_WITHIN_BUDGET", "INCONCLUSIVE"}
    if phase == "T2":
        read_freeze(args, freeze_path)
        frozen_artifact(external["input"])
    summary_path = case / "summary.json"
    write(summary_path, summary)
    return summary_path, summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("core", "l3", "t0", "freecad", "python", "output"):
        parser.add_argument(f"--{name}", required=True, type=Path)
    parser.add_argument("--phase", choices=("T1", "T2", "T3", "T4"), required=True)
    parser.add_argument("--perturbation", type=Path)
    parser.add_argument("--perturbation-sha256")
    parser.add_argument("--development", action="store_true")
    args = parser.parse_args()
    for name in ("core", "l3", "t0", "freecad", "python"):
        setattr(args, name, getattr(args, name).resolve(strict=True))
    private = ROOT / ".runtime"
    area = args.output.resolve()
    require(area != private and area.is_relative_to(private), "Campagne hors dossier privé .runtime")
    require((args.phase == "T2") == bool(args.perturbation) == bool(args.perturbation_sha256),
            "T2 exige un reçu externe et son empreinte communiquée indépendamment")
    freeze_path = area / "freeze.json"
    if not args.development:
        status = subprocess.check_output(["git", "status", "--porcelain=v1"], cwd=ROOT, text=True)
        require(not status, "Qualification C.3 exige un checkout propre")
    if args.phase == "T1":
        area.mkdir(parents=True)
        before = sealed_inputs(args)
    elif not args.development:
        read_freeze(args, freeze_path)
    summary_path, summary = run_phase(args, area, freeze_path)
    if args.phase == "T1" and not args.development and summary["phase_pass"]:
        require(before == sealed_inputs(args), "Entrées modifiées pendant T1")
        t1 = {name: summary[name] for name in ("candidate", "routes", "problem", "observation", "campaign", "countercheck")}
        t1["summary"] = artifact(summary_path)
        write(freeze_path, {"schema": "v3.c3.freeze/1", "frozen_at_utc": utc(), "inputs": before, "t1": t1})
        write(area / "T2-HANDOFF.json", {"freeze": artifact(freeze_path), **t1,
            "external_input": {"schema": "v3.c3.external_perturbation/1",
                "freeze_sha256": digest(freeze_path), "t1_root_sha256": t1["candidate"]["sha256"],
                "t1_problem_sha256": t1["problem"]["sha256"], "evaluator": "identifiant de l'évaluateur indépendant",
                "issued_at_utc": "horodatage UTC ISO 8601 après le gel",
                "obstacle": {"id": "identifiant ASCII", "min_mm": ["x", "y", "z"], "max_mm": ["x", "y", "z"]}},
            "contract": "Boîte ROOT en mm, bornes ±10000 mm, trois épaisseurs au moins 0,01 mm. Fournir hors du dossier de campagne, communiquer la SHA et viser une portion de câble T1 dont la réouverture OCCT permettra de vérifier la collision."})
    return 0 if summary["phase_pass"] else 4


if __name__ == "__main__":
    raise SystemExit(main())
