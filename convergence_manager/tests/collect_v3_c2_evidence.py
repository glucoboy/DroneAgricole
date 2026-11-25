"""Vérifie les reçus natifs C.2 et publie les mesures légères du rejeu."""

import argparse
from itertools import combinations
import json
from math import ceil, dist, floor
from pathlib import Path
import subprocess

from replay_v3_b1 import ROOT, digest, load, write
from replay_v3_b2 import artifact
from replay_v3_c2 import BENCHES, authority


def checked(reference):
    path = (ROOT / reference["path"]).resolve(strict=True)
    if not path.is_relative_to(ROOT) or digest(path) != reference["sha256"]:
        raise ValueError(f"Empreinte de preuve divergente : {path}")
    return load(path)


def point(item):
    return item["matrix"][3:12:4]


def delta(after, before):
    return [target - initial for target, initial in zip(point(after), point(before), strict=True)]


def topology(observation):
    contacts = {key: tuple(item[name] for name in ("object", "pin", "port", "mate", "connected_wires"))
                for key, item in observation["contacts"].items()}
    conductors = {key: (item["route"], tuple((entry["contact"], entry["reciprocal"]) for entry in item["endpoints"]))
                  for key, item in observation["conductors"].items()}
    return contacts, conductors


def check_candidate(directory, entry, domain, profile, t0):
    identifier = entry["candidate"]
    trial = directory / "candidates" / identifier
    native = trial / "construction/transaction"
    cross = trial / "cross" / identifier
    transaction, build = load(native / "campaign.json"), load(native / "build.json")
    receipt = cross / "candidate-result.json"
    counter = load(receipt)
    measured = checked(counter["measurements"])
    reference = load(cross / "baseline-observation.json")
    assert counter["final_verdict"] == transaction["status"] == build["status"] == "PASS"
    assert not counter["blocking_issues"] and not counter["independent_disagreements"]
    assert checked(counter["native_receipt"]) == transaction
    assert counter["proposal_sha256"] == digest(trial / "proposal.json")
    for row in counter["validator_by_domain"].values():
        assert row["status"] == "PASS"
        checked(row["receipt"])
    assert transaction["execution_scope"] == "BENCH_TEST_ONLY" and transaction["source_integrity"]["status"] == "PASS"
    operations = [operation for admission in transaction["admissions"] for operation in admission["allowed_operations"]]
    assert sorted(operations) == ["RELOCATE_SUPPORT", "REPOSITION_DEVICE", "REROUTE_HARNESS", "REROUTE_HARNESS"]
    assert build["pid"] != measured["pid"] and build["worker_id"] != measured["worker_id"]
    assert measured["sources_unchanged"] and measured["copy_unchanged"] and measured["documents_closed"]
    assert not measured["invalid_objects"] and measured["source_sha256"] == profile["dependencies"]
    assert build["after_sha256"] == measured["inputs_sha256"] == transaction["native_sha256"]
    for path, fingerprint in build["after_sha256"].items():
        assert digest(native / "cad" / path) == digest(cross / "candidate-copy" / path) == fingerprint
    assert topology(measured) == topology(reference)
    device = domain["scene"]["device_occurrence"]
    movement = delta(measured["occurrences"][device], reference["occurrences"][device])
    assert dist(movement, [0, 0, 0]) > 1e-6
    plan = load(trial / "proposal.json")["values"]
    geometry = {"pose": plan["translation_mm"], "support": plan["support_option"], "routes": plan["harnesses"]}
    support = measured["supports"][geometry["support"]]
    cables = {}
    assert measured["routes"].keys() == domain["harnesses"].keys()
    for name, specification in domain["harnesses"].items():
        fixed, mobile = specification["ports"]
        route = measured["routes"][name]
        fixed_port, mobile_port = (measured["ports"][key] for key in (fixed, mobile))
        start_error = dist(route["endpoints_mm"][0], point(fixed_port))
        end_error = dist(route["endpoints_mm"][1], point(mobile_port))
        shift = delta(mobile_port, reference["ports"][mobile])
        assert dist(shift, movement) < 1e-6 and start_error < 1e-6 and end_error < 1e-6
        assert dist(point(fixed_port), point(reference["ports"][fixed])) < 1e-6
        assert route["diameter_mm"] == specification["diameter_mm"]
        prefix = f"harness/{name}/"
        cables[name] = {"electrical_id": specification["electrical_id"], "ports": [fixed, mobile],
                        "mobile_port_delta_mm": shift, "endpoint_error_mm": [start_error, end_error],
                        "length_mm": route["length_mm"], "minimum_radius_mm": route["minimum_radius_mm"],
                        "radius_evidence": route["radius_evidence"], "diameter_mm": route["diameter_mm"],
                        "clearance_mm": entry["metrics"][prefix + "clearance_mm"],
                        "maximum_tangent_error_deg": entry["metrics"][prefix + "maximum_tangent_error_deg"]}
    assert support["bearing_area_mm2"] > 0 and support["carrier_face"]["bearing_area_mm2"] > 0 and support["fasteners"]
    assert set(support["retains"]) == {row["occurrence_path"] for row in domain["harnesses"].values()}
    assert set(support["retention_gaps_mm"]) == set(cables)
    classification = measured["interference_classification"]
    assert classification["status"] == "PASS" and classification["cross_harness"]["status"] == "PASS"
    verify = subprocess.run([str(t0), "validate", str(native), str(ROOT)], cwd=ROOT, capture_output=True,
                            text=True, timeout=30, check=False)
    assert verify.returncode == 0 and verify.stdout.strip() == "T0 valid", (identifier, verify.stderr)
    return {"candidate": identifier, "geometry": geometry, "cables": cables, "device_delta_mm": movement,
            "support": support, "classification": classification, "roles_verified": counter["coverage"]["checks"],
            "builder_pid": build["pid"], "independent_pid": measured["pid"], "receipt": artifact(receipt),
            "observation": counter["measurements"], "native_sha256": build["after_sha256"],
            "t0_rechecked_exit_code": verify.returncode}


def pareto_check(pareto, objectives):
    def orient(row):
        scores = []
        for objective in objectives:
            value = row["metrics"][objective["metric"]]
            bins = value / objective["tolerance"]
            rounded = floor(bins + 0.5) if bins >= 0 else ceil(bins - 0.5)
            scores.append(rounded if objective["direction"] == "MIN" else -rounded)
        return tuple(scores)

    scores = {row["candidate"]: orient(row) for row in pareto["admissible"]}
    front = {key for key, score in scores.items() if not any(
        other != score and all(a <= b for a, b in zip(other, score, strict=True)) for other in scores.values())}
    assert front == {row["candidate"] for row in pareto["front"]}
    winner = min(front, key=lambda identifier: (scores[identifier], identifier)) if front else None
    return winner, any(scores[first] != scores[second] for first, second in combinations(front, 2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign", required=True, type=Path)
    parser.add_argument("--t0", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    campaign, out, t0 = (args.campaign.resolve(strict=True), args.output.resolve(), args.t0.resolve(strict=True))
    assert campaign.is_relative_to(ROOT / ".runtime") and out.is_relative_to(ROOT / ".runtime")
    out.mkdir(parents=True)
    freeze = load(campaign / "freeze.json")
    for name, expected in freeze["files_sha256"].items():
        assert digest(Path(name)) == expected, name
    coupling, collision, supports, phases, ranks, trace = {}, {}, {}, {}, {}, []
    for phase in BENCHES:
        case = campaign / phase.lower()
        directory = case / phase
        summary = load(case / "summary.json")
        assert checked(summary["freeze"]) == freeze
        assert checked(summary["campaign"])["qualified_candidates"] == summary["qualified_candidates"]
        assert checked(summary["problem"])["phase"] == phase
        if summary["external_perturbation"]:
            checked(summary["external_perturbation"])
        domain_path, domain, profile_path, profile = authority(phase)
        assert summary["scope"] == "SYNTHETIC_BENCH" and checked(summary["t0"])["exit_code"] == 0
        assert summary["proposals"] <= freeze["budget"]["max_proposals"]
        assert summary["native_attempts"] <= freeze["budget"]["max_native"]
        assert summary["counterchecks"] <= freeze["budget"]["max_counterchecks"]
        ranking = load(directory / "pareto.json")
        winner, tradeoff = pareto_check(ranking, freeze["objectives"])
        assert winner == (summary["retained"].get("candidate_id") or None)
        rows = [check_candidate(directory, entry, domain, profile, t0) for entry in ranking["admissible"]]
        assert len(rows) == summary["qualified_candidates"]
        geometry = {json.dumps(row["geometry"], sort_keys=True) for row in rows}
        assert len(rows) == len(geometry)
        ranks[phase] = {**ranking, "independent_winner": winner, "tradeoff": tradeoff}
        coupling[phase] = [{key: item for key, item in row.items() if key not in ("support", "classification")} for row in rows]
        collision[phase] = [{"candidate": row["candidate"], **row["classification"]} for row in rows]
        supports[phase] = [{"candidate": row["candidate"], "option": row["geometry"]["support"],
                            "observation": row["observation"], **row["support"]} for row in rows]
        phases[phase] = {key: summary[key] for key in ("verdict", "reason", "proposals", "native_attempts", "counterchecks",
                          "elapsed_ms", "elapsed_budget_scope", "qualified_candidates", "retained", "campaign", "t0",
                          "problem", "external_perturbation")}
        phases[phase].update(domain=artifact(domain_path), profile=artifact(profile_path), options=sorted({row["option"] for row in supports[phase]}))
        trace.extend({"phase": phase, **json.loads(line)} for line in (directory / "candidate_trace.jsonl").read_text(encoding="utf-8").splitlines())
    (out / "candidate_trace.jsonl").write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in trace), encoding="utf-8", newline="\n")
    write(out / "coupling_proofs.json", coupling)
    write(out / "cross_harness_checks.json", {phase: [{"candidate": row["candidate"], **row["cross_harness"]}
                                                      for row in rows] for phase, rows in collision.items()})
    write(out / "interference_classification.json", collision)
    write(out / "support_decisions.json", supports)
    write(out / "generalization.json", {"source_commit": freeze["source_commit"], "phases": phases})
    write(out / "pareto.json", ranks)
    checks = {"T1_two_variants": phases["T1"]["qualified_candidates"] >= 2,
              "two_support_options": len(phases["T1"]["options"]) >= 2,
              "T2_new_native": bool(phases["T2"]["retained"]) and bool(phases["T2"]["external_perturbation"])
                  and phases["T2"]["retained"]["native_sha256"] != phases["T1"]["retained"]["native_sha256"],
              "T3_other_bench": bool(phases["T3"]["retained"]) and phases["T3"]["domain"] != phases["T1"]["domain"],
              "measured_tradeoff": ranks["T1"]["tradeoff"]}
    write(out / "independent_review.json", {"schema": "v3.c2.independent_review/1", "source_commit": freeze["source_commit"],
          "checks": checks, "scope": "SYNTHETIC_BENCH", "verified_fingerprints": len(freeze["files_sha256"]),
          "generalization": artifact(out / "generalization.json")})
    print("PASS" if all(checks.values()) else "CONDITIONAL", checks)


if __name__ == "__main__":
    main()
