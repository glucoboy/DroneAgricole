"""Exécute T0, T1, le gel puis T2 et T3 avec les points d'entrée L3/L5."""

import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import subprocess

from replay_v3_b1 import ROOT, digest, load, write
from replay_v3_b2 import artifact, invoke, measurement
from replay_v3_c import check_plan, proposal, qualification, run_campaign


V3 = ROOT / "docs/electromechanical_v3"
PROOF = ROOT / "docs/verification/v3"
PREREGISTRATION = V3 / "bench_c1_coupled/perturbation.json"
PREREGISTRATION_SHA = "596d7eeaf7112f9918c5927261e598f4771b7c26ee8849d085b5258c0d52d67c"
BASELINE = "551db0d9c9cda8a7717aa4aa99b407b2861417b8"
SEED = 2026
BUDGET = {"max_proposals": 30, "max_native": 6}
OBJECTIVES = [{"metric": "route_length_mm", "direction": "MIN"},
              {"metric": "route_clearance_mm", "direction": "MAX"}]


def utc():
    return datetime.now(timezone.utc).isoformat()


def authority(suffix):
    domain = V3 / "domains" / f"c1_coupled{suffix}.json"
    profile = V3 / f"bench_c1_coupled{suffix}" / "profile.json"
    spec = load(profile)
    placement = load(domain)["placement"]
    bounds = {"min": placement["translation_min_mm"], "max": placement["translation_max_mm"]}
    if digest(profile) != load(domain)["profile_sha256"] or digest(ROOT / spec["graph"]) != spec["graph_sha256"]:
        raise ValueError(f"Autorité incohérente : {profile}")
    return domain, profile, spec, bounds


def reconciliation():
    paths = {key: PROOF / directory / report for key, directory, report in [
        ("I", "i", "acceptance.json"), ("B.1", "b1", "acceptance.json"),
        ("B.2", "b2", "acceptance.json"), ("C", "c", "acceptance.json"),
        ("A.3", "a3", "acceptance.json"), ("D", "d", "admission.json")
    ]}
    records = {}
    for name, path in paths.items():
        entry = artifact(path)
        baseline_bytes = subprocess.check_output(["git", "show", f"{BASELINE}:{entry['path']}"], cwd=ROOT)
        if path.read_bytes() != baseline_bytes:
            raise ValueError(f"Reçu historique modifié : {entry['path']}")
        records[name] = entry
    workholding = load(V3 / "domains/workholding.json")
    pareto = load(PROOF / "c/pareto.json")["phases"]
    metrics = {phase: [row["metrics"] for row in pareto[phase]["admissible"]] for phase in ("T1", "T2")}
    return {"schema": "v3.c1.baseline/1", "base_commit": BASELINE,
            "parents": subprocess.check_output(["git", "log", "-2", "--format=%H %P", BASELINE], cwd=ROOT,
                                               text=True).splitlines(),
            "historical_receipts": records, "terminal_mode": workholding["route"]["terminal_mode"],
            "moving_with": workholding["scene"]["moving_with"], "historical_metrics": metrics}


def fingerprint(args, authorities):
    files = [args.core, args.l3, args.freecad, args.python, args.t0, Path(__file__).resolve()]
    files.extend(ROOT.glob("convergence_manager/native/v3_*.py"))
    files.extend(ROOT / path for path in ("convergence_manager/tests/replay_v3_c.py",
                                         "convergence_manager/tests/replay_v3_b1.py",
                                         "convergence_manager/tests/replay_v3_b2.py",
                                         "electromechanical_engine/freecad_worker.py",
                                         "electromechanical_engine/v3_native.py",
                                         "electromechanical_engine/xlink_native.py"))
    files.extend(V3.glob("*.schema.json"))
    for domain, profile, spec, _ in authorities:
        files.extend([domain, profile, ROOT / spec["graph"]])
        files.extend(ROOT / spec["source"] / name for name in spec["dependencies"])
    source_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    return {"commit": source_commit, "files_sha256": {str(path): digest(path) for path in files},
            "seed": SEED, "budget": BUDGET, "objectives": OBJECTIVES,
            "preregistration_sha256": PREREGISTRATION_SHA}


def problem(args, case, phase, domain, profile, observation, bounds, base=None):
    model = ROOT / profile["source"] / profile["entry"]
    data = {"schema": "v3.problem_spec/1", "phase": phase, "domain_sha256": digest(domain),
            "model_sha256": digest(model), "observation_sha256": digest(observation), "seed": SEED,
            "budget": BUDGET, "objectives": OBJECTIVES, "narrowing": {"translation_mm": bounds}}
    request, result = case / f"{phase}-request.json", case / f"{phase}-problem.json"
    argv = [str(args.l3), "v3-problem", "--root", str(ROOT), "--request", str(request), "--domain", str(domain),
            "--model", str(model), "--observation", str(observation), "--output", str(result)]
    if base:
        data["base_problem_sha256"] = digest(base)
        argv.extend(["--base-problem", str(base)])
    write(request, data)
    invoked = invoke(case, f"{phase}-l3", argv)
    if invoked.returncode or not result.is_file():
        raise RuntimeError(f"L3 {phase}, code {invoked.returncode} : {invoked.stderr}")
    return result


def selected_metrics(case, result, profile):
    if not result["retained"]:
        return {}
    retained = result["retained"]
    counter_file = case / retained["result"]
    if digest(counter_file) != retained["result_sha256"]:
        raise ValueError("Reçu B.2 modifié")
    counter = load(counter_file)
    observed_file = ROOT / counter["measurements"]["path"]
    if digest(observed_file) != counter["measurements"]["sha256"]:
        raise ValueError("Mesure B.2 modifiée")
    observed = load(observed_file)
    rules = profile["model"]["validation"]
    paths = profile["model"]["occurrences"]
    route = observed["routes"]["cordon"]
    moving_port = observed["ports"]["port-b"]
    return {"candidate": retained["candidate_id"], "measured": artifact(observed_file),
            "translation_mm": retained["values"]["translation_mm"], "rank_metrics": retained["metrics"],
            "port_a": observed["ports"]["port-a"], "port_b": moving_port,
            "endpoints_mm": route["endpoints_mm"], "diameter_mm": route["diameter_mm"],
            "minimum_radius_mm": route["minimum_radius_mm"], "radius_evidence": route["radius_evidence"],
            "length_mm": route["length_mm"],
            "endpoint_error_mm": math.dist(moving_port["matrix"][3:12:4], route["endpoints_mm"][1]),
            "support": {name: {"path": paths[name], **observed["supports"][name]}
                        for name in rules["supports"]},
            "sibling": observed["occurrences"][paths["sibling"]],
            "builder": artifact(case / "candidates" / retained["candidate_id"] /
                                "construction/transaction/build.json"),
            "independent_pid": observed["pid"], "independent_worker_id": observed["worker_id"]}


def sensitivity(selected):
    if not selected.get("T1") or not selected.get("T2"):
        return {"status": "INCONCLUSIVE", "reason": "Deux candidats admis sont nécessaires."}
    first, second = selected["T1"], selected["T2"]
    port_shift = math.dist(first["endpoints_mm"][1], second["endpoints_mm"][1])
    length_change = second["length_mm"] - first["length_mm"]
    flags = {key: second["rank_metrics"][key] - value for key, value in first["rank_metrics"].items()}
    return {"status": "PASS" if port_shift > 1e-6 and any(abs(value) > 1e-6 for value in flags.values()) else "FAIL",
            "endpoint_shift_mm": port_shift, "length_delta_mm": length_change, "metrics_delta": flags,
            "constant_support_count_reason": "La composition interrogée conserve un support."}


def summary(area, phases, selected, faults, errors, first_excluded):
    candidates, families, pareto = [], {}, {}
    for name, phase in phases.items():
        stage = Path(phase["campaign"]["path"]).parent
        candidates.extend({"phase": name, **json.loads(line)}
                          for line in (ROOT / stage / "candidate_trace.jsonl").read_text(encoding="utf-8").splitlines())
        families[name] = load(ROOT / stage / "family_transitions.json")
        pareto[name] = load(ROOT / stage / "pareto.json")
    trace = area / "candidate_trace.jsonl"
    trace.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in candidates), encoding="utf-8", newline="\n")
    write(area / "family_transitions.json", families)
    write(area / "pareto.json", pareto)
    write(area / "coupling_proofs.json", selected)
    write(area / "sensitivity.json", sensitivity(selected))
    write(area / "adversarial.json", faults)
    write(area / "generalization.json", {"phases": phases, "first_excluded_in_t2": first_excluded, "errors": errors})


def faults_before_build(args, area, domain, profile, values):
    area.mkdir()
    plans = {
        "translation": {"translation_mm": [999, 0, 0]},
        "stale-terminal": {"route_points_mm": [*values["route_points_mm"][:-1], [86, 0, 0]]},
        "radius": {"bend_radius_mm": 1},
        "bad-type": {"translation_mm": "104,2,0"},
        "claimed-cache": {"cache": {"status": "PASS"}},
        "wrong-parent": {"frame": "PARENT"},
    }
    cases = {name: check_plan(args, area / name, profile, proposal(domain, "deny-" + name, values | change), 2)
             for name, change in plans.items()}
    forged = proposal(domain, "deny-authority", values)
    forged["authority_sha256"] = "0" * 64
    cases["forged-authority"] = check_plan(args, area / "forged-authority", profile, forged, 2)
    return cases


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for option in ("core", "l3", "freecad", "python", "t0", "output"):
        parser.add_argument("--" + option, required=True, type=Path)
    args = parser.parse_args()
    for key in ("core", "l3", "freecad", "python", "t0"):
        setattr(args, key, getattr(args, key).resolve(strict=True))
    area = args.output.resolve()
    if not area.is_relative_to(ROOT / ".runtime") or area.exists():
        parser.error("Choisir une sortie neuve sous .runtime")
    area.mkdir(parents=True)
    authorities = [authority(""), authority("_secondary")]
    if digest(PREREGISTRATION) != PREREGISTRATION_SHA:
        raise RuntimeError("Empreinte de la perturbation préenregistrée divergente")
    write(area / "baseline_reconciliation.json", reconciliation())
    expected = fingerprint(args, authorities)
    checks, phases, selected, faults, errors = {}, {}, {}, {}, {}
    first_excluded = None
    original = None
    for phase, auth in [("T1", authorities[0]), ("T2", authorities[0]), ("T3", authorities[1])]:
        domain, profile_path, profile, bounds = auth
        case = area / phase.lower()
        case.mkdir()
        started = utc()
        try:
            if phase == "T2":
                if not original:
                    raise RuntimeError("Problème T1 indisponible")
                revealed = load(PREREGISTRATION)
                bounds = revealed["translation_mm"]
                first = selected.get("T1", {}).get("translation_mm")
                first_excluded = first is not None and not all(low <= coord <= high
                                     for coord, low, high in zip(first, bounds["min"], bounds["max"], strict=True))
                observation = area / "t1/reference-observation.json"
            else:
                report, observation = measurement(args.freecad, case, "reference", ROOT / profile["source"],
                                                  profile["dependencies"], profile_path)
                checks[phase] = {"observation": artifact(observation), "status": report["status"],
                                 "versions": report.get("versions"), "profile": artifact(profile_path),
                                 "domain": artifact(domain)}
                write(area / "domain_contract.json", {"T0": checks, "bounds": [row[3] for row in authorities],
                                                      "perturbation_sha256": PREREGISTRATION_SHA})
            request = problem(args, case, phase, domain, profile, observation, bounds,
                              original if phase == "T2" else None)
            if phase == "T1":
                original = request
            report = run_campaign(args, case, phase, request, observation, original if phase == "T2" else None)
            phases[phase] = {**qualification(case / phase, report), "started_utc": started, "completed_utc": utc()}
            selected[phase] = selected_metrics(case / phase, report, profile)
        except (OSError, ValueError, KeyError, RuntimeError, AssertionError, subprocess.SubprocessError) as error:
            errors[phase] = str(error) or type(error).__name__
        if fingerprint(args, authorities) != expected or digest(PREREGISTRATION) != PREREGISTRATION_SHA:
            raise RuntimeError(f"Le gel a changé pendant {phase}")
        if phase == "T1":
            write(area / "perturbation_freeze.json", {"schema": "v3.c1.freeze/1", "attested_utc": utc(), **expected,
                  "isolation": "L3/L5 ne reçoivent la restriction T2 qu'après ce gel. Le fichier préenregistré est visible dans le dépôt."})
    if phases.get("T1", {}).get("retained"):
        domain, _, profile, _ = authorities[0]
        try:
            faults = faults_before_build(args, area / "adversarial", domain, profile, phases["T1"]["retained"]["values"])
        except (OSError, ValueError, RuntimeError, AssertionError, subprocess.SubprocessError) as error:
            errors["adversarial"] = str(error) or type(error).__name__
    summary(area, phases, selected, faults, errors, first_excluded)
    return 0 if len(phases) == 3 and not errors and first_excluded and all(selected.values()) else 4


if __name__ == "__main__":
    raise SystemExit(main())
