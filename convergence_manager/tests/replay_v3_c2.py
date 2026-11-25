"""Rejoue les campagnes C.2 et contrôle le gel avant toute perturbation externe."""

import argparse
from datetime import datetime, timezone
from pathlib import Path
import subprocess

from replay_v3_b1 import ROOT, digest, load, write
from replay_v3_b2 import artifact, invoke, measurement
from replay_v3_c import run_campaign, source_commit


V3 = ROOT / "docs/electromechanical_v3"
BENCHES = {"T1": "c2_multiharness", "T2": "c2_multiharness", "T3": "c2_multiharness_secondary"}
SEED = 2026
BUDGET = {"max_proposals": 80, "max_native": 10, "max_seconds": 540, "max_counterchecks": 10}
OBJECTIVES = [
    {"metric": "route_length_mm", "direction": "MIN", "tolerance": 1e-6},
    {"metric": "minimum_inter_harness_gap_mm", "direction": "MAX", "tolerance": 1e-6},
    {"metric": "minimum_support_bearing_area_mm2", "direction": "MAX", "tolerance": 1e-6},
]


def utc():
    return datetime.now(timezone.utc).isoformat()


def authority(phase):
    name = BENCHES[phase]
    domain_path = V3 / "domains" / f"{name}.json"
    profile_path = V3 / f"bench_{name}/profile.json"
    domain, profile = load(domain_path), load(profile_path)
    if (domain["schema"] != "v3.parametric_domain/2" or domain["domain"] != "SYNTHETIC_BENCH"
            or digest(profile_path) != domain["profile_sha256"]
            or digest(ROOT / profile["graph"]) != profile["graph_sha256"]):
        raise ValueError(f"Autorité de banc divergente pour {phase}")
    return domain_path, domain, profile_path, profile


def freeze(args):
    artifacts = [args.core, args.l3, args.t0, args.freecad, args.python, Path(__file__).resolve()]
    artifacts.extend(ROOT.glob("convergence_manager/native/v3_*.py"))
    artifacts.extend(ROOT / name for name in ("convergence_manager/tests/replay_v3_b1.py",
                     "convergence_manager/tests/replay_v3_b2.py", "convergence_manager/tests/replay_v3_c.py",
                     "electromechanical_engine/freecad_worker.py", "electromechanical_engine/v3_native.py",
                     "electromechanical_engine/xlink_native.py"))
    artifacts.extend(V3.glob("*.schema.json"))
    for phase in ("T1", "T3"):
        domain, _, profile_path, profile = authority(phase)
        artifacts.extend((domain, profile_path, ROOT / profile["graph"]))
        artifacts.extend(ROOT / profile["source"] / name for name in profile["dependencies"])
    return {"schema": "v3.c2.freeze/1", "scope": "SYNTHETIC_BENCH", "source_commit": source_commit(),
            "budget": BUDGET, "objectives": OBJECTIVES, "seed": SEED,
            "files_sha256": {path.as_posix(): digest(path) for path in sorted(set(artifacts))}}


def reseal(args, freeze_path):
    stored = load(freeze_path)
    if {key: value for key, value in stored.items() if key != "frozen_at_utc"} != freeze(args):
        raise ValueError("Le code, le modèle ou les règles ont changé depuis le gel C.2")


def restrict(perturbation_path, expected, freeze_path, base, initial):
    if (not perturbation_path.is_relative_to(ROOT / ".runtime") or digest(perturbation_path) != expected):
        raise ValueError("Empreinte ou emplacement de perturbation invalide")
    payload = load(perturbation_path)
    fields = {"schema", "freeze_sha256", "base_problem_sha256", "evaluated_candidate_sha256",
              "issued_at_utc", "narrowing"}
    if (set(payload) != fields or payload["schema"] != "v3.c2.external_perturbation/1"
            or payload["freeze_sha256"] != digest(freeze_path) or payload["base_problem_sha256"] != digest(base)
            or not datetime.fromisoformat(initial["completed_at_utc"]) < datetime.fromisoformat(payload["issued_at_utc"])
                <= datetime.now(timezone.utc)):
        raise ValueError("Perturbation hors gel ou antérieure à T1")
    winner = initial["retained"]
    if not winner or winner["result_sha256"] != payload["evaluated_candidate_sha256"]:
        raise ValueError("Perturbation hors du candidat retenu en T1")
    return payload["narrowing"]


def includes(narrowing, values):
    translation = narrowing["translation_mm"]
    return (values["support_option"] in narrowing["support_zones"]
            and all(low <= value <= high for low, value, high in zip(
                translation["min"], values["translation_mm"], translation["max"], strict=True)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("core", "l3", "t0", "freecad", "python", "output"):
        parser.add_argument(f"--{name}", required=True, type=Path)
    parser.add_argument("--phase", choices=BENCHES, required=True)
    parser.add_argument("--perturbation", type=Path)
    parser.add_argument("--perturbation-sha256")
    args = parser.parse_args()
    for name in ("core", "l3", "t0", "freecad", "python"):
        setattr(args, name, getattr(args, name).resolve(strict=True))
    area = args.output.resolve()
    if not area.is_relative_to(ROOT / ".runtime") or area == ROOT / ".runtime":
        parser.error("La sortie doit être dans un nouveau dossier de campagne sous .runtime")
    phase = args.phase
    needs_perturbation = phase == "T2"
    if bool(args.perturbation) != needs_perturbation or bool(args.perturbation_sha256) != needs_perturbation:
        parser.error("T2 seul exige une perturbation externe et son empreinte")
    freeze_path = area / "freeze.json"
    if phase == "T1":
        subprocess.run(["git", "diff", "--quiet", "HEAD"], cwd=ROOT, check=True)
        area.mkdir(parents=True)
        write(freeze_path, {**freeze(args), "frozen_at_utc": utc()})
    reseal(args, freeze_path)
    case = area / phase.lower()
    case.mkdir()
    domain_path, domain, profile_path, profile = authority(phase)
    model = ROOT / profile["source"] / profile["entry"]
    placement = domain["placement"]
    narrowing = {"translation_mm": {"min": placement["translation_min_mm"], "max": placement["translation_max_mm"]},
                 "support_zones": sorted(domain["support_options"])}
    base = None
    external = None
    if phase == "T2":
        base = area / "t1/T1-problem.json"
        initial = load(area / "t1/summary.json")
        perturbation = args.perturbation.resolve(strict=True)
        narrowing = restrict(perturbation, args.perturbation_sha256, freeze_path, base, initial)
        if includes(narrowing, initial["retained"]["values"]):
            raise ValueError("La perturbation ne réfute pas le candidat T1")
        observation = area / "t1/reference-observation.json"
        external = artifact(perturbation)
    else:
        _, observation = measurement(args.freecad, case, "reference", ROOT / profile["source"],
                                     profile["dependencies"], profile_path)
    request = {"schema": "v3.problem_spec/2", "phase": phase, "domain_sha256": digest(domain_path),
               "model_sha256": digest(model), "observation_sha256": digest(observation), "seed": SEED,
               "budget": BUDGET, "objectives": OBJECTIVES, "narrowing": narrowing}
    if phase == "T3":
        initial_spec = load(area / "t1/T1-problem.json")
        if any(request[name] == initial_spec[name] for name in ("domain_sha256", "model_sha256")):
            raise ValueError("T3 exige un autre domaine et une autre géométrie XLink")
    request_path, validated = case / f"{phase}-request.json", case / f"{phase}-problem.json"
    l3_argv = [args.l3, "v3-problem", "--root", ROOT, "--request", request_path,
               "--domain", domain_path, "--model", model, "--observation", observation, "--output", validated]
    if base:
        request["base_problem_sha256"] = digest(base)
        l3_argv.extend(("--base-problem", base))
    write(request_path, request)
    result = invoke(case, "L3", list(map(str, l3_argv)))
    if result.returncode != 0 or not validated.is_file():
        raise RuntimeError(f"Le problème {phase} a été refusé par L3 (code {result.returncode})")
    report = run_campaign(args, case, phase, validated, observation, base)
    reseal(args, freeze_path)
    if external and digest(perturbation) != external["sha256"]:
        raise ValueError("La perturbation a changé pendant T2")
    if external and report["retained"]:
        winner = report["retained"]
        if not includes(narrowing, winner["values"]) or winner["native_sha256"] == initial["retained"]["native_sha256"]:
            raise ValueError("Le résultat T2 ne constitue pas une adaptation native dans la restriction")
    directory = case / phase
    counter = load(directory / "t0-crosscheck.json")
    if not report["finalized"] or counter["exit_code"] != 0:
        raise RuntimeError("Campagne partielle ou contrôle T0 sans succès")
    write(case / "summary.json", {**report, "completed_at_utc": utc(), "freeze": artifact(freeze_path),
          "problem": artifact(validated), "campaign": artifact(directory / "campaign.json"),
          "t0": artifact(directory / "t0-crosscheck.json"), "external_perturbation": external})
    return 0 if report["qualified_candidates"] else 4


if __name__ == "__main__":
    raise SystemExit(main())
