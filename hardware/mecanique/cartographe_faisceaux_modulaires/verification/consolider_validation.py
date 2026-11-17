"""Indexe les mesures FreeCAD et les décisions pour la copie livrée."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def hard_collision(row):
    return row["intersection_status"] == "fail" and not row.get("relation", {}).get("zone_nominale_confirmee")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("measurements", type=Path)
    parser.add_argument("--initial-fixtures", type=Path)
    args = parser.parse_args()
    scratch = args.measurements
    audit = read(HERE / "audit_baseline.json")
    integration = read(HERE / "integration.json")
    generation = read(HERE / "generation.json")
    modules = read(HERE / "modules_electriques.json")
    fixtures = read(HERE / "validation_retenues.json")
    fresh_path = scratch / "geometrie_reouverture_livree.json"
    if not fresh_path.is_file():
        fresh_path = scratch / "geometrie_reouverture.json"
    fresh = read(fresh_path)
    nominal = read(scratch / "geometrie_paires.json")
    initial = read(args.initial_fixtures or scratch / "fixtures_initial.json")
    radio = generation.get("radio")
    radio_definition = read(HERE / "integration_radio.json") if radio else {}
    volumes = read(HERE / "volumes_supports.json") if radio else {}
    reports = [generation, fixtures, fresh, nominal, initial]
    if not all(row["complete"] for row in reports):
        raise ValueError("Contrôle ou génération incomplète")
    if not all(all(row["inputs_sha256"].get(path) == digest for path, digest in generation["native_sha256"].items())
               for row in (fresh, nominal)) or fixtures["native_sha256"] != generation["native_sha256"]:
        raise ValueError("Contrôles et natifs différents")
    retry_path = HERE / "reprise_intersections.json"
    retry = read(retry_path)
    if not retry["complete"] or retry["source_sha256"] != sha(scratch / "geometrie_paires.json"):
        raise ValueError("Reprise d'intersections incomplète ou étrangère à l'essai")
    replacements = {tuple(row["pair"]): row for row in retry["results"]}
    pairs = [replacements.get(tuple(row["pair"]), row) for row in nominal["pairs"]["near_or_invalid_pairs"]]
    collisions = [row for row in pairs if hard_collision(row)]
    unknown = [row for row in pairs if row["intersection_status"] == "unknown"
               or row["clearance_status"] == "unknown" or tuple(row["pair"]) in replacements]
    local_pairs = fixtures["fixtures"]["contacts_intersections_unknowns"]
    local_collisions = [row for row in local_pairs if hard_collision(row)]
    local_unknown = [row for row in local_pairs
                     if row["intersection_status"] == "unknown" or row["clearance_status"] == "unknown"]
    before = audit["comptage"]
    support_specs = integration["pieces"] + radio_definition.get("f41_accessories", [])
    manufactured = [spec for spec in support_specs if spec["directory"] == "fabriquees"]
    new_parts = sum(len(spec["occurrences"]) for spec in manufactured)
    retained_saddles = integration["reused_saddles"]["count"]
    earlier_stations = audit["impact_retrait_des_cinq_occurrences_orange"]
    route_rows = read(HERE / "routes_prototype.json")["routes"]
    new_sites = {}
    for spec in support_specs:
        if spec["role"] == "fixation":
            for occurrence in spec["occurrences"]:
                for name in occurrence["routes"]:
                    new_sites.setdefault(name, []).append(occurrence["id"])
    invalid_routes = set(fresh["routes"]) - {name for name, row in fresh["routes"].items()
                                           if row["solid"]["status"] == "pass"}
    route_report = {}
    for row in route_rows:
        name = row["id"]
        checks = fresh["routes"][name]
        conflicts = [pair for pair in collisions if checks["occurrence"] in pair["pair"]]
        checks_open = [pair["pair"] for pair in unknown if checks["occurrence"] in pair["pair"]]
        route_report[name] = {
            "module": row["module"], "path_length_mm": checks["route"].get("length_mm"),
            "reconstructed_in_copy": name in generation["routes_installed"],
            "solid": checks["solid"]["status"], "axis_check": checks["route"]["status"],
            "axis_findings": checks["route"].get("failures"), "segments": checks["segments"],
            "retention_candidates": new_sites.get(name, []),
            "old_supports_removed": earlier_stations["routes_avec_station_historique_a_reexaminer"].get(name, []),
            "lost_all_historical_sites": name in earlier_stations["routes_sans_station_historique_residuelle"],
            "collisions": [pair["pair"] for pair in conflicts], "unknown_pairs": checks_open,
            "physical_status": ("NON_CONFORME" if name in invalid_routes or conflicts or (not radio and name in {"F13A", "F13B"})
                                else "À valider"),
        }
    reports_dir = scratch.as_posix()
    proof = {
        "schema": "cartographe.validation-faisceaux-modulaires.v1",
        "complete": True, "environment": fresh["environment"],
        "sources": {
            "baseline_unchanged": generation["source_check"],
            "fresh_report": {"path": fresh_path.as_posix(), "sha256": sha(fresh_path)},
            "pair_report": {"path": reports_dir + "/geometrie_paires.json", "sha256": sha(scratch / "geometrie_paires.json")},
            "fixtures_report": {"path": "validation_retenues.json", "sha256": sha(HERE / "validation_retenues.json")},
            "baseline_audit_sha256": sha(HERE / "audit_baseline.json"),
            "rf_attachment_report": "validation_radio.json" if radio else "rf_p70.json",
            "intersection_retry": {"path": retry_path.name, "sha256": sha(retry_path)},
            "script_sha256": sha(Path(__file__)),
        },
        "gates": {"integrity": fresh["gates"]["integrity"], "fresh": fresh["gates"]["fresh"],
                  "pairs": nominal["gates"]["pairs"], "interactive": "not_executed", "physical": "not_executed"},
        "fresh_route_results": dict(Counter(row["rebuild"]["status"] for row in fresh["fresh"]["routes"].values()
                                           if "rebuild" in row)),
        "native_doc_count_on_reopen": len(fresh["fresh"]["entry"]["documents"]),
        "native_doc_errors": [row for row in fresh["fresh"]["entry"]["documents"] if row["errors"]],
        "native_read_only": fresh["native_read_only"] and nominal["native_read_only"] and fixtures["native_read_only"],
        "pair_counts": {"considered": nominal["pairs"]["considered_pairs"],
                        "positive_except_airy_junction": len(collisions),
                        "unknown_intersections_after_retry": sum(row["intersection_status"] == "unknown" for row in pairs),
                        "unknown_clearances_after_retry": len(unknown),
                        "airy_zone_pairs": sum(row.get("relation", {}).get("zone_nominale_confirmee", False) for row in pairs),
                        "aabb_disjoint": nominal["pairs"]["disjoint_by_AABB_above_near_threshold"],
                        "reused_unchanged": nominal["pairs"]["reused_unchanged_pairs"]},
        "conflicts": collisions, "unknown_pairs": unknown, "protections": fixtures["protections"],
        "local_fixture_checks": {"pairs_within_0_9_mm": fixtures["fixtures"]["checked_pairs_within_AABB_0_9mm"],
                                 "positive": local_collisions, "unknown": local_unknown,
                                 "previous_failed_pairs": [r for r in initial["fixtures"]["contacts_intersections_unknowns"]
                                                           if hard_collision(r)]},
        "comparison": {
            "native_routes": [53, len(route_report)],
            "native_axis_lengths_mm": [before["axes_cumules_mm"], nominal["wire_length_mm"]],
            "manufactured_fixture_occurrences_sa07": [before["supports_fabriques_dedies_sa07"], retained_saddles + new_parts],
            "manufactured_fixture_refs_sa07": [before["references_distinctes_support_fabrique"] - 1, 2 + len(manufactured)],
            "manufactured_fixture_occurrences_global": [before["occurrences_par_role"]["support_fabrique"],
                                                        retained_saddles + new_parts + before["supports_fabriques_perception_p10"]],
            "large_frames": [before["cadres_ou_guides_massifs"], 0],
            "sleeve_occurrences": [before["gaines_physiques_candidates"], len(fixtures["protections"])],
            "fixation_occurrences_all_roles": [sum(before["occurrences_par_role"][key] for key in
                                                   ("support_fabrique", "quincaillerie_support", "collier_equipement")),
                                                fixtures["occurrences"]["fixation"] - (len(radio["changed_occurrences"]) if radio else 0)],
            "new_manufactured_pieces": new_parts,
            "redesigned_existing_antenna_mounts": len(radio["changed_occurrences"]) if radio else 0,
            "manufactured_fixture_material_volume_sa07_mm3": ([volumes["before_mm3"], volumes["after_mm3"]]
                                                              if volumes else None),
            "old_station_assignments_removed": earlier_stations["affectations_perdues"],
            "assembled_harness_mass_g": [None, None],
        },
        "modules": {m["id"]: {"paths": m["route_ids"],
                             "status": "NON_CONFORME" if m["id"] == "NAV_RF" and not radio else "À valider",
                             "open": m["open"]} for m in modules["modules"]},
        "routes": route_report,
        "decision": {
            "model_status": "Implémenté", "qualification": "À valider",
            "global_mounting_verdict": "CANDIDAT_CONDITIONNEL" if radio and not collisions else "NON_CONFORME",
            "mounting_failure": None if radio else "Les ensembles P70/antenne n'ont plus d'ancrage au châssis dans la copie.",
            "integration_released": False,
            "conditions": ([condition for condition in integration["points_non_resolus"]
                            if not (radio and condition.startswith(("Support RF de P70", "Entrée/sortie du cordon F41")))]
                           + (["F41. Le clip P84 reprend la sortie près de P64. Il reste à définir les retenues de la montée et de la traversée, le cordon de remplacement et ses fiches."] if radio else [])
                           + radio_definition.get("open", [])),
        },
    }
    path = HERE / "validation.json"
    path.write_text(json.dumps(proof, ensure_ascii=False, allow_nan=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
