"""Calcule le verdict C.1 à partir des résultats et inventorie les preuves légères."""

import argparse
from itertools import combinations
import json
from pathlib import Path
import shutil

from replay_v3_b1 import ROOT, load, write
from replay_v3_b2 import artifact


def phase_status(phases, selected, name):
    phase = phases.get(name)
    proof = selected.get(name)
    if not phase:
        return "NOT_RUN"
    if not proof or phase["qualified_candidates"] == 0:
        return "FAIL"
    return "PASS" if phase["finalized"] and proof["endpoint_error_mm"] <= 1e-6 else "FAIL"


def tradeoff(pareto, objectives):
    def scores(row):
        return [row["metrics"][objective["metric"]] * (1 if objective["direction"] == "MIN" else -1)
                for objective in objectives]

    evidence = {}
    for name, phase in pareto.items():
        front = phase["front"]
        admissible = phase["admissible"]
        witnesses = {}
        for one, two in combinations(admissible, 2):
            deltas = [a - b for a, b in zip(scores(one), scores(two), strict=True)]
            pair = [one, two]
            if all(abs(value) <= 1e-6 for value in deltas):
                witnesses.setdefault("tie", pair)
            elif max(deltas) > 1e-6 and min(deltas) < -1e-6 and one in front and two in front:
                witnesses.setdefault("tradeoff", pair)
            elif (max(deltas) <= 1e-6 and min(deltas) < -1e-6) or (min(deltas) >= -1e-6 and max(deltas) > 1e-6):
                witnesses.setdefault("dominated", pair)
        evidence[name] = witnesses
    return evidence


def accepted(checks):
    if all(status == "PASS" for status in checks.values()):
        return "V3_C1_COUPLED_ENGINE_GO"
    if checks["T1"] == "NOT_RUN" and checks["T3"] == "NOT_RUN" and checks["T0"] == "NOT_RUN":
        return "V3_C1_NOT_RUN"
    if any(checks[name] == "FAIL" for name in ("T1", "T2", "T3", "perturbation", "sensitivity")):
        return "V3_C1_COUPLED_ENGINE_NO_GO"
    return "V3_C1_COUPLED_ENGINE_CONDITIONAL"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign", type=Path, required=True)
    parser.add_argument("--regressions", type=Path, required=True)
    parser.add_argument("--native-faults", type=Path)
    parser.add_argument("--review", type=Path,
                        help="Reçu de revue indépendante, lié au commit gelé et à la campagne")
    args = parser.parse_args()
    area, regressions = args.campaign.resolve(), args.regressions.resolve()
    dest = ROOT / "docs/verification/v3/c1"
    dest.mkdir(parents=True, exist_ok=True)
    for name in ("baseline_reconciliation.json", "domain_contract.json", "coupling_proofs.json", "sensitivity.json",
                 "candidate_trace.jsonl", "family_transitions.json", "pareto.json", "generalization.json",
                 "perturbation_freeze.json", "adversarial.json"):
        source = area / name
        if source.is_file():
            shutil.copyfile(source, dest / name)
    shutil.copyfile(regressions, dest / "regressions.json")
    generalization = load(area / "generalization.json")
    phases = generalization["phases"]
    selected = load(area / "coupling_proofs.json")
    freeze = load(area / "perturbation_freeze.json")
    contract = area / "domain_contract.json"
    contract_data = load(contract) if contract.is_file() else {}
    t0 = contract_data.get("T0", {})
    for record in t0.values():
        record["versions"] = load(ROOT / record["observation"]["path"])["environment"]
    if contract_data:
        write(dest / "domain_contract.json", contract_data)
    pareto_path = dest / "pareto.json"
    pareto = load(pareto_path)
    witnesses = tradeoff(pareto, freeze["objectives"])
    write(pareto_path, {"phases": pareto, "witnesses": witnesses})
    regressions_status = [row["status"] for row in load(regressions)["tests"].values()]
    faults = load(area / "adversarial.json")
    native_faults = args.native_faults.resolve() if args.native_faults else None
    native_faults_status = load(native_faults).get("status", "INCONCLUSIVE") if native_faults else "NOT_RUN"
    write(dest / "adversarial.json", {"plans": faults, "native_faults_status": native_faults_status,
                                     "native_faults": artifact(native_faults) if native_faults else None})
    checks = {name: phase_status(phases, selected, name) for name in ("T1", "T2", "T3")}
    checks["T0"] = "PASS" if len(t0) == 2 and all(row["status"] == "MEASURED" for row in t0.values()) else "NOT_RUN"
    exclusion = generalization["first_excluded_in_t2"]
    checks["perturbation"] = "PASS" if exclusion else "FAIL" if exclusion is False else "NOT_RUN"
    checks["sensitivity"] = load(area / "sensitivity.json")["status"]
    checks["pareto"] = "PASS" if any("tradeoff" in case for case in witnesses.values()) else "INCONCLUSIVE"
    checks["regressions"] = "PASS" if all(status == "PASS" for status in regressions_status) else "INCONCLUSIVE"
    checks["plan_faults"] = "PASS" if len(faults) == 7 else "INCONCLUSIVE"
    checks["native_faults"] = native_faults_status
    if args.review:
        review = args.review.resolve()
        record = load(review)
        if (record["source_commit"] != freeze["commit"] or
                record["generalization"] != artifact(area / "generalization.json")):
            raise ValueError("Revue indépendante hors de ce gel ou de cette campagne")
        shutil.copyfile(review, dest / "independent_review.json")
        checks["review"] = record["status"]
    else:
        checks["review"] = "NOT_RUN"
    refs = [artifact(path) for path in sorted(dest.iterdir())
            if path.name not in {"acceptance.json", "artifacts.json", "REPORT.md"}]
    for name, sha in freeze["files_sha256"].items():
        path = Path(name)
        refs.append({"path": path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else path.as_posix(),
                     "sha256": sha})
    write(dest / "artifacts.json", {"schema": "v3.c1.artifacts/1", "sources": refs})
    counts = {}
    for name, row in phases.items():
        trace = ROOT / row["trace"]["path"]
        events = [json.loads(line)["stage"] for line in trace.read_text(encoding="utf-8").splitlines()]
        counts[name] = {key: row[key] for key in ("proposals", "native_attempts", "qualified_candidates")}
        counts[name].update(constructed_and_reopened=events.count("REOPEN"),
                            independently_checked=events.count("VALIDATE"))
    write(dest / "acceptance.json", {
        "schema": "v3.c1.acceptance/1", "scope": "SYNTHETIC_BENCH", "verdict": accepted(checks),
        "source_commit": freeze["commit"], "checks": checks, "errors": generalization["errors"],
        "counts": counts,
        "physical_qualification": "NOT_RUN", "cartographer_mutation": "DENY",
        "unsupported": ["CHANGE_CONNECTOR_VARIANT", "CHANGE_INTERFACE_TOPOLOGY", "VARIABLE_ROTATION"],
        "artifacts": artifact(dest / "artifacts.json")
    })


if __name__ == "__main__":
    main()
