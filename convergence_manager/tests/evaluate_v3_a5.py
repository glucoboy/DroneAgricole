"""Recalcule les deux dispositions de la campagne A.5 à partir des reçus."""

import argparse
from hashlib import sha256
import json
from pathlib import Path


REQUIRED_CASES = {
    "before-review", "fake-signer", "self-issued-trust", "signature-unverified", "wrong-trust-pin",
    "raw-sha-changed", "manufacturer-not-applicable", "different-lot", "different-revision",
    "expired", "clock-rollback", "signed-revocation", "double-use", "datum-matrix-altered",
    "normal-inverted", "wrong-rotation", "tolerance-document-missing", "uncertainty-covers-limit",
    "nc-connected", "j2-j3-ambiguous", "floating-anchor", "fraudulent-carrier", "test-only-domain-escalation",
    "outside-pose", "xlink-profile-revised-after-review", "try-construction-on-active-reference",
}


def read(directory, name):
    content = (directory / name).read_bytes()
    return json.loads(content), {"path": name, "sha256": sha256(content).hexdigest()}


def evaluate(directory):
    adversarial, adversarial_ref = read(directory, "adversarial.json")
    regressions, regressions_ref = read(directory, "regressions.json")
    physical, physical_ref = read(directory, "authority_decisions.json")
    matrix, matrix_ref = read(directory, "lot_and_measurement_matrix.json")
    readiness, readiness_ref = read(directory, "create_support_iso_readiness.json")
    cases = adversarial["cases"]
    positive = [entry for entry in cases if entry["exit_code"] == 0]
    refused = {entry["case"] for entry in cases if entry["exit_code"] == 2 and entry["receipt"]["authority"] == "DENY"}
    scope = (len(cases) > 0 and all(entry["receipt"]["cartographer_mutation"] == "DENY"
             and entry["receipt"]["candidate_transactions"] == 0 for entry in cases)
             and physical["cartographer_mutation"] == readiness["decision"] == "DENY"
             and physical["authorized_pairs"] == 0 and not physical["decisions"])
    checks = {
        "physical_scope_denied": scope,
        "signed_test_admissions": len(positive) == 2 and all(
            entry["receipt"]["authority"] == "TEST_ONLY"
            and entry["receipt"]["review"]["status"] == "SIGNATURE_VERIFIED"
            and entry["receipt"]["admission"]["consumed"] for entry in positive),
        "adversarial_cases": (adversarial["status"] == "PASS" and adversarial["case_count"] == len(cases)
                              and len(refused) + len(positive) == len(cases) and REQUIRED_CASES <= refused),
        "compiled_core": regressions["checks"].get("compiled_core") == "PASS",
        "a4_import": regressions["checks"].get("a4_import") == "PASS",
        "l5_regressions": regressions["checks"].get("l5_regressions") == "PASS",
        "without_crypto": regressions["checks"].get("without_crypto") == "PASS",
    }
    if not scope or not checks["compiled_core"]:
        result = "V3_A5_AUTHORITY_PIPELINE_NO_GO"
    elif all(checks.values()):
        result = "V3_A5_AUTHORITY_PIPELINE_GO"
    else:
        result = "V3_A5_AUTHORITY_PIPELINE_CONDITIONAL"
    if matrix["lot_inspected"] or matrix["physical_approvals"] or readiness["candidate_count"]:
        raise ValueError("Une donnée physique nouvelle requiert une décision d'acceptation distincte")
    return {"schema": "v3.a5.acceptance/1", "tested_commit": regressions["tested_commit"],
            "software_verdict": result, "software_scope": "TEST_ONLY", "checks": checks,
            "physical_verdict": "V3_A5_EVIDENCE_CONDITIONAL", "physical_reception": "NOT_RUN",
            "lot_inspected": matrix["lot_inspected"], "authorized_pairs": physical["authorized_pairs"],
            "cartographer_mutation": physical["cartographer_mutation"], "d1_scope": "READ_ONLY_IMPACT",
            "adversarial_counts": {"refused": len(refused), "test_admissions": len(positive)},
            "evidence": [adversarial_ref, regressions_ref, physical_ref, matrix_ref, readiness_ref]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipts", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = evaluate(args.receipts)
    with args.output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(result["software_verdict"], result["physical_verdict"])


if __name__ == "__main__":
    main()
