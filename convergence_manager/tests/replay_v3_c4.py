"""Gèle les bancs C.4 et mesure les quatre phases depuis des natifs rouverts."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess

from replay_v3_b1 import ROOT, digest, load, write
from replay_v3_b2 import MEASURER, artifact, closure, invoke, measurement, pose_errors
from replay_v3_c import run_campaign, source_commit
from replay_v3_c3 import OBJECTIVES, frozen_artifact, require, unique_object, utc


V3 = ROOT / "docs/electromechanical_v3"
BUDGET = {"max_proposals": 64, "max_native": 12, "max_seconds": 540, "max_counterchecks": 12}
SHORT = {"max_proposals": 1, "max_native": 1, "max_seconds": 1, "max_counterchecks": 1}
SEED = 2026
CRITERIA = {
    "T1": "Deux admissions natives distinctes, mouvement Z et rotation, quatre datums et appui hors centres prédéfinis.",
    "T2": "Collision native du témoin T1, puis nouvelles pose et route intéressée, sans collision.",
    "T3": "Autre hiérarchie native et datums distincts. Au moins une admission en Z et rotation.",
    "T4": "Aucune admission au budget de temps réduit.",
}
HANDOFF_SCHEMA = "v3.c4.external_perturbation/1"


def authority(secondary=False):
    name = "c4_sixdof_secondary" if secondary else "c4_sixdof"
    path, profile_path = V3 / "domains" / f"{name}.json", V3 / f"bench_{name}/profile.json"
    domain, profile = load(path), load(profile_path)
    require(domain["schema"] == "v3.parametric_domain/4" and domain["domain"] == "SYNTHETIC_BENCH"
            and domain["profile_sha256"] == digest(profile_path) and profile["graph_sha256"] == digest(ROOT / profile["graph"]),
            "Autorités C.4 divergentes")
    closure(ROOT / profile["source"], profile["dependencies"])
    return path, domain, profile_path, profile


def inputs(args):
    paths = {getattr(args, name) for name in ("core", "l3", "t0", "freecad", "python")}
    for pattern in ("convergence_manager/native/v3_*.py", "convergence_manager/tests/replay_v3_*.py",
                    "electromechanical_engine/*.py", ".agents/skills/electromechanical-integration/scripts/*.py"):
        paths.update(ROOT.glob(pattern))
    paths.update(V3 / name for name in ("parametric_domain_v4.schema.json", "mutation_plan_v5.schema.json",
                                        "problem_spec_v3.schema.json", "candidate_result.schema.json"))
    for secondary in (False, True):
        domain_path, _, profile_path, profile = authority(secondary)
        paths.update({domain_path, profile_path, ROOT / profile["graph"]})
        paths.update(ROOT / profile["source"] / name for name in profile["dependencies"])
    return {"tested_commit": source_commit(), "seed": SEED, "budget": BUDGET, "short_budget": SHORT,
            "criteria": CRITERIA, "objectives": OBJECTIVES,
            "sha256": {str(path.relative_to(ROOT) if path.is_relative_to(ROOT) else path): digest(path)
                       for path in sorted(paths)}}


def frozen(args, path):
    freeze = load(path)
    current = inputs(args)
    current["tested_commit"] = freeze["inputs"]["tested_commit"]
    require(current == freeze["inputs"], "Outils ou autorités modifiés depuis le gel C.4")
    for record in freeze["t1"].values():
        frozen_artifact(record)
    return freeze


def external_input(args, case, freeze_path, snapshot, profile_path, profile):
    supplied = args.perturbation
    require(supplied.is_file() and supplied.resolve() == supplied and supplied.is_relative_to(ROOT / ".runtime")
            and not supplied.is_relative_to(case.parent) and supplied.stat().st_nlink == 1
            and digest(supplied) == args.perturbation_sha256,
            "Entrée évaluateur, emplacement indépendant ou SHA incorrect")
    payload = json.loads(supplied.read_bytes(), object_pairs_hook=unique_object)
    t1 = snapshot["t1"]
    require(set(payload) == {"schema", "issued_at_utc", "evaluator", "freeze_sha256", "t1_root_sha256",
                             "t1_problem_sha256", "obstacle"}
            and payload["schema"] == HANDOFF_SCHEMA and isinstance(payload["evaluator"], str) and payload["evaluator"].strip()
            and payload["freeze_sha256"] == digest(freeze_path) and payload["t1_root_sha256"] == t1["candidate"]["sha256"]
            and payload["t1_problem_sha256"] == t1["problem"]["sha256"], "Reçu indépendant non lié au gel et à la T1 exacte")
    issued = datetime.fromisoformat(payload["issued_at_utc"])
    require(issued.utcoffset() == timezone.utc.utcoffset(issued)
            and datetime.fromisoformat(snapshot["frozen_at_utc"]) < issued <= datetime.now(timezone.utc),
            "Le reçu indépendant doit être émis en UTC après le gel")
    obstacle, output = case / "obstacle.json", case / "t1-obstacle-collision.json"
    write(obstacle, payload["obstacle"])
    candidate = frozen_artifact(t1["candidate"])
    expected = load(frozen_artifact(t1["observation"]))["inputs_sha256"]
    closure(candidate.parent, expected)
    argv = [args.freecad, "-B", MEASURER, "--root", candidate.parent, "--profile", profile_path,
            "--output", output, "--external-obstacle", obstacle, "--expected-entry-sha256",
            t1["candidate"]["sha256"], "--require-absent"]
    measured = invoke(case, "external-collision", list(map(str, argv)))
    require(measured.returncode == 0, f"Collision OCCT T1 non finalisée : {measured.stderr}")
    result = load(output)
    collision = result["external_obstacle"]
    tolerance = profile["model"]["validation"]["tolerances"]["volume_mm3"]
    names = [name for name, row in collision["harnesses"].items() if row["intersection_mm3"] > tolerance]
    require(result["status"] == "MEASURED" and collision["presence"] == "HYPOTHETICAL" and names
            and result["inputs_sha256"] == expected and result["external_sha256"] == digest(obstacle)
            and result["copy_unchanged"] and result["documents_closed"], "L'obstacle ne réfute aucun câble T1 authentifié")
    receipt = {"input": artifact(supplied), "verified_payload": payload, "hypothetical_measurement": artifact(output),
               "invalidated_harnesses": names, "native_relations": collision["harnesses"]}
    write(case / "external_perturbation_receipt.json", receipt)
    return receipt


def observed_result(case, profile, report):
    retained = report["retained"]
    result_file = case / retained["result"]
    require(digest(result_file) == retained["result_sha256"], "SHA de contre-mesure candidat divergent")
    result = load(result_file)
    observed_file = frozen_artifact(result["measurements"])
    candidate = case / "candidates" / retained["candidate_id"] / "construction/transaction/cad" / profile["entry"]
    require(digest(candidate) == retained["native_sha256"][profile["entry"]], "Natif candidat divergent")
    return {"observation": artifact(observed_file), "candidate": artifact(candidate),
            "countercheck": artifact(result_file)}, load(observed_file)


def run_phase(args, area, freeze_path):
    phase, case = args.phase, area / args.phase.lower()
    path, domain, profile_path, profile = authority(phase == "T3")
    fixture = ROOT / profile["source"] / profile["entry"]
    case.mkdir()
    base, external = None, None
    if phase == "T2":
        snapshot = frozen(args, freeze_path)
        base = frozen_artifact(snapshot["t1"]["problem"])
        baseline_path = frozen_artifact(snapshot["t1"]["baseline"])
        external = external_input(args, case, freeze_path, snapshot, profile_path, profile)
        request = {**load(base), "phase": phase, "base_problem_sha256": digest(base),
                   "external_obstacle": external["verified_payload"]["obstacle"]}
    else:
        _, baseline_path = measurement(args.freecad, case, "reference", fixture.parent, profile["dependencies"], profile_path)
        limits = domain["placement"]
        request = {"schema": "v3.problem_spec/3", "phase": phase, "domain_sha256": digest(path),
                   "model_sha256": digest(fixture), "observation_sha256": digest(baseline_path), "seed": SEED,
                   "budget": SHORT if phase == "T4" else BUDGET, "objectives": OBJECTIVES,
                   "narrowing": {"translation_mm": {"min": limits["translation_min_mm"], "max": limits["translation_max_mm"]}}}
    request_path, problem = case / "request.json", case / "problem.json"
    write(request_path, request)
    argv = [args.l3, "v3-problem", "--root", ROOT, "--request", request_path, "--domain", path,
            "--model", fixture, "--observation", baseline_path, "--output", problem]
    if base:
        argv.extend(("--base-problem", base))
    launched = invoke(case, "l3", list(map(str, argv)))
    require(launched.returncode == 0 and problem.is_file(), f"L3 {phase} a refusé le problème : {launched.stderr}")
    report = run_campaign(args, case, phase, problem, baseline_path, base)
    out = case / phase
    t0 = out / "t0-crosscheck.json"
    require(report["finalized"] and load(t0)["exit_code"] == 0, "Campagne ou validation T0 incomplète")
    summary = {**report, "problem": artifact(problem), "baseline": artifact(baseline_path),
               "campaign": artifact(out / "campaign.json"), "pareto": artifact(out / "pareto.json"), "t0": artifact(t0)}
    if report["retained"]:
        refs, observed = observed_result(out, profile, report)
        summary.update(refs)
        original = load(baseline_path)
        device = domain["scene"]["device_occurrence"]
        before, after = [entry["occurrences"][device]["matrix"] for entry in (original, observed)]
        tolerance = profile["model"]["validation"]["tolerances"]
        port_ids = [route["ports"][1] for route in domain["harnesses"].values()]
        port_changes = {name: pose_errors(observed["ports"][name]["matrix"], original["ports"][name]["matrix"])
                        for name in port_ids}
        offset = observed["spatial_support_zone"]["observed_offset_mm"]
        summary["native_pose"] = {"device": device, "baseline_matrix": before, "observed_matrix": after,
                                  "translation_z_delta_mm": after[11] - before[11],
                                  "rotation_delta_deg": pose_errors(after, before)[1], "port_changes_mm_deg": port_changes,
                                  "observed_support_offset_mm": offset}
        ok = (abs(after[11] - before[11]) > tolerance["position_mm"]
              and summary["native_pose"]["rotation_delta_deg"] > tolerance["direction_deg"]
              and all(dist > tolerance["position_mm"] and degrees > tolerance["direction_deg"]
                      for dist, degrees in port_changes.values())
              and observed["spatial_support_zone"]["status"] == "PASS"
              and max(abs(value) for value in offset) > tolerance["position_mm"])
        if phase == "T1":
            ok = ok and report["qualified_candidates"] >= 2
        elif phase == "T2":
            old = load(frozen_artifact(snapshot["t1"]["observation"]))
            old_pose = old["occurrences"][device]["matrix"]
            distance, angle = pose_errors(after, old_pose)
            new_solid = observed["external_obstacle"]
            mapping = {name: [old["routes"][name]["axis_sha256"], observed["routes"][name]["axis_sha256"]]
                       for name in external["invalidated_harnesses"]}
            summary["perturbation"] = {"receipt": external, "after": new_solid, "axes_before_after": mapping,
                                       "pose_change_mm_deg": [distance, angle]}
            ok = (ok and (distance > tolerance["position_mm"] or angle > tolerance["direction_deg"])
                  and new_solid["presence"] == "SAVED_NATIVE"
                  and all(row["intersection_mm3"] <= tolerance["volume_mm3"] for row in new_solid["harnesses"].values())
                  and all(first != second for first, second in mapping.values()))
            frozen(args, freeze_path)
            frozen_artifact(external["input"])
        elif phase == "T3" and freeze_path.is_file():
            old = load(frozen_artifact(load(freeze_path)["t1"]["observation"]))
            ok = (ok and set(old["parent_matrices"]) != set(observed["parent_matrices"])
                  and any(old["ports"][name]["datum"] != observed["ports"][name]["datum"] for name in port_ids))
    else:
        ok = (phase == "T4" and report["qualified_candidates"] == 0 and report["elapsed_budget_reached"]
              and report["verdict"] == "V3_C_CONDITIONAL")
    summary["phase_pass"] = ok
    summary_path = case / "summary.json"
    write(summary_path, summary)
    return summary_path, summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("core", "l3", "t0", "freecad", "python", "output"):
        parser.add_argument(f"--{name}", required=True, type=Path)
    parser.add_argument("--phase", choices=tuple(CRITERIA), required=True)
    parser.add_argument("--perturbation", type=Path)
    parser.add_argument("--perturbation-sha256")
    parser.add_argument("--development", action="store_true")
    args = parser.parse_args()
    for name in ("core", "l3", "t0", "freecad", "python"):
        setattr(args, name, getattr(args, name).resolve(strict=True))
    args.perturbation = args.perturbation.absolute() if args.perturbation else None
    area = args.output.resolve()
    require(area != ROOT / ".runtime" and area.is_relative_to(ROOT / ".runtime"), "Campagne hors dossier privé")
    require((args.phase == "T2") == bool(args.perturbation) == bool(args.perturbation_sha256),
            "T2 exige un reçu externe et sa SHA communiquée indépendamment")
    if not args.development:
        require(not subprocess.check_output(["git", "status", "--porcelain=v1"], cwd=ROOT, text=True),
                "Qualification C.4 exige un checkout propre")
    freeze_path = area / "freeze.json"
    if args.phase == "T1":
        area.mkdir(parents=True)
        before = inputs(args)
    elif not args.development:
        frozen(args, freeze_path)
    summary_path, summary = run_phase(args, area, freeze_path)
    if args.phase == "T1" and not args.development and summary["phase_pass"]:
        require(before == inputs(args), "Entrées modifiées pendant T1")
        t1 = {key: summary[key] for key in ("candidate", "baseline", "problem", "observation", "campaign", "countercheck")}
        t1["summary"] = artifact(summary_path)
        write(freeze_path, {"schema": "v3.c4.freeze/1", "frozen_at_utc": utc(), "inputs": before, "t1": t1})
        write(area / "T2-HANDOFF.json", {"freeze": artifact(freeze_path), **t1, "external_input": {
            "schema": HANDOFF_SCHEMA, "freeze_sha256": digest(freeze_path), "t1_root_sha256": t1["candidate"]["sha256"],
            "t1_problem_sha256": t1["problem"]["sha256"], "evaluator": "évaluateur indépendant",
            "issued_at_utc": "heure UTC après gel", "obstacle": {"id": "nom ASCII", "min_mm": [], "max_mm": []}}})
    return 0 if summary["phase_pass"] else 4


if __name__ == "__main__":
    raise SystemExit(main())
