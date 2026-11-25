"""Recalcule le verdict INT.1 à partir des nouveaux reçus de vérification."""

import argparse
from hashlib import sha256
import json
from pathlib import Path


def verdict(regressions, adversarial):
    if regressions["checks"].keys() & adversarial["checks"].keys():
        raise ValueError("Les reçus INT.1 déclarent des contrôles en double")
    checks = regressions["checks"] | adversarial["checks"]
    critical = (
        "fresh_builds", "source_integrity", "c1_replay", "c1_independent_review",
        "a4_import", "cartographer_denied", "mandatory_refusals",
    )
    additional = ("legacy_regressions", "l3_broad_diagnosed", "direct_search", "native_faults")
    if any(checks.get(name) != "PASS" for name in critical):
        result = "V3_INT1_NO_GO"
    elif any(checks.get(name) != "PASS" for name in additional):
        result = "V3_INT1_CONDITIONAL"
    else:
        result = "V3_INT1_GO"
    return result, checks, [name for name in (*critical, *additional) if checks.get(name) != "PASS"]


def read(directory, name):
    path = directory / name
    content = path.read_bytes()
    return json.loads(content), {"path": name, "sha256": sha256(content).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipts", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    regression, regression_ref = read(args.receipts, "regressions.json")
    adversarial, adversarial_ref = read(args.receipts, "adversarial.json")
    manifest, manifest_ref = read(args.receipts, "merge_manifest.json")
    revisions = manifest["révisions"]
    if (regression["tested_commit"] != adversarial["tested_commit"]
            or regression["tested_commit"] != revisions["validated"]["commit"]
            or regression["merge_commit"] != revisions["merge"]["commit"]):
        raise ValueError("Les reçus INT.1 ne couvrent pas les mêmes sources")
    result, checks, blockers = verdict(regression, adversarial)
    go = result == "V3_INT1_GO"
    authority = adversarial["cartographer_mutation"]
    if go and authority != "DENY":
        raise ValueError("Mutation cartographe incompatible avec le périmètre INT.1")
    publication = {
        "schema": "v3.int1.acceptance/1",
        "branch": "codex/v3-int1-consolidation",
        "tested_commit": regression["tested_commit"],
        "merge_commit": regression["merge_commit"],
        "verdict": result,
        "checks": checks,
        "blockers": blockers,
        "qualified_scope": "SYNTHETIC_BENCH" if go else None,
        "a4_material_evidence": regression["a4"]["material_disposition"],
        "physical_reception": "NOT_RUN",
        "cartographer_mutation": authority,
        "next_stage": {"C.2": "OPEN" if go else "BLOCKED", "A.5": "OPEN" if go else "BLOCKED",
                       "D.1": "READ_ONLY_IMPACT"},
        "evidence": [manifest_ref, regression_ref, adversarial_ref],
    }
    with args.output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(publication, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(result)


if __name__ == "__main__":
    main()
