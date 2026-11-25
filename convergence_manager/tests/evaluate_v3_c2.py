"""Recalcule la disposition C.2 à partir des preuves de banc."""

import argparse
from hashlib import sha256
import json
from pathlib import Path


def read(directory, name):
    content = (directory / name).read_bytes()
    return json.loads(content), {"path": name, "sha256": sha256(content).hexdigest()}


def evaluate(directory):
    baseline, base_ref = read(directory, "baseline.json")
    review, review_ref = read(directory, "independent_review.json")
    adversarial, attack_ref = read(directory, "adversarial.json")
    regressions, regression_ref = read(directory, "regressions.json")
    campaign, campaign_ref = read(directory, "generalization.json")
    if len({row["source_commit"] for row in (baseline, review, campaign, regressions, adversarial)}) != 1:
        raise ValueError("Les preuves C.2 ne désignent pas le même gel")
    checks = {**review["checks"], "frozen_sources": baseline["source_integrity"] == "PASS",
              "admission_guard": adversarial["cartographer_mutation"] == "DENY",
              "adversarial": adversarial["status"] == "PASS",
              "regressions": regressions["status"] == "PASS",
              "builds": regressions["builds_status"] == "PASS"}
    critical = ("frozen_sources", "admission_guard", "builds")
    if any(not checks[name] for name in critical) or adversarial.get("critical_failure") is True:
        verdict = "V3_C2_NO_GO"
    elif all(checks.values()):
        verdict = "V3_C2_MULTIHARNESS_ENGINE_GO"
    else:
        verdict = "V3_C2_CONDITIONAL"
    counts = {phase: {key: row[key] for key in ("proposals", "native_attempts", "qualified_candidates", "options")}
              for phase, row in campaign["phases"].items()}
    return {"schema": "v3.c2.acceptance/1", "tested_commit": campaign["source_commit"], "verdict": verdict,
            "scope": "SYNTHETIC_BENCH", "checks": checks, "campaigns": counts,
            "blocked_checks": [key for key, result in checks.items() if not result],
            "cartographer_mutation": adversarial["cartographer_mutation"], "physical_reception": "NOT_RUN",
            "evidence": [base_ref, review_ref, attack_ref, regression_ref, campaign_ref]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipts", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    disposition = evaluate(args.receipts)
    with args.output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(disposition, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(disposition["verdict"])


if __name__ == "__main__":
    main()
