import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[2]
VERIFICATION = ROOT / "docs/verification"


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def sha256(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def require(predicate, description):
    if not predicate:
        raise ValueError(description)


def verify_paths(inventory, l2, native):
    lines = {line["id"]: line for line in l2["lines"]}
    require(inventory.keys() == l2["interfaces"].keys() == native["interfaces"].keys(), "Clés interfaces divergentes")
    require(l2["axes"].keys() == native["axes"].keys(), "Axes divergents")
    for identifier, axis in l2["axes"].items():
        observation = native["axes"][identifier]
        occurrence = axis["assembly_occurrence"]
        require(axis["line_ids"] == observation["line_ids"] and occurrence == observation["occurrence"] and
                native["reverse_objects"][occurrence]["line_ids"] == axis["line_ids"], f"Association inverse {identifier}")
        active = axis["native_file"]
        require(sha256(ROOT / active["path"]) == active["sha256"], f"Empreinte de l’axe {identifier}")
    for key, row in inventory.items():
        interface = l2["interfaces"][key]
        native_side = native["interfaces"][key]
        line = lines[interface["line_id"]]
        path = line["path"]
        require((row["liaison_id"], row["extremite"], row["perimetre"], row["classe_l2"]) ==
                (interface["line_id"], interface["side"], line["scope"], line["class"]), f"Identité de {key}")
        require(row["axes_cao"] == "|".join(edge["route_id"] for edge in path) and path == native_side["path"] and
                row["parcours_axes_ordonnes"] == " | ".join(f"{edge['route_id']} ({edge['sense']})" for edge in path),
                f"Chemin orienté de {key}")
        require(row["topologie_du_parcours"] == (line["path_kind"] if path else "") and
                line["path_kind"] == native_side["path_kind"] and
                row["motif_absence_axe"] == line.get("scope_reason", ""), f"Topologie ou motif de {key}")
        require(row["port_fonctionnel"] == (native_side["port"] or ""), f"Port documentaire de {key}")
        require(row["port_fonctionnel"] and row["sources"] and row["action_suivante"], f"Traçabilité minimale de {key}")
        frame = native_side["device_mount_frame"]
        if frame:
            occurrence = frame["object"]
            require(occurrence == row["occurrence_cao"] and key in native["reverse_objects"][occurrence]["interface_ids"],
                    f"Occurrence équipement de {key}")
        require(not row["revision_physique"] and not row["lot_physique"] and
                row["etat_reception"] in {"INCONCLUSIVE", "OUT_OF_SCOPE"} and
                native_side["contacts_bound_to_occurrences"] is None, f"Réception physique indûment attribuée à {key}")
    return {"lines": len(lines), "axes": len(l2["axes"]), "endpoints": len(inventory),
            "off_axis_lines": sum(not line["path"] for line in lines.values()),
            "line_axis_pairs": sum(len(axis["line_ids"]) for axis in l2["axes"].values()),
            "native_equipment_poses": sum(bool(side["device_mount_frame"]) for side in native["interfaces"].values()),
            "native_cable_end_attachments": sum(bool(attached) for axis in native["axes"].values()
                                               for attached in axis["wire_attachments"])}


def verify_research(inventory, reports_directory, executable):
    catalog_path = VERIFICATION / "v21_connector_research_catalog.json"
    sources_path = VERIFICATION / "v21_connector_sources.json"
    catalog = read_json(catalog_path)
    catalog_fingerprint = {"path": catalog_path.relative_to(ROOT).as_posix(), "sha256": sha256(catalog_path)}
    register = read_json(sources_path)
    physical = {item["issue_id"] for item in register["investigations"]}
    require({row["recherche_l1"] for row in inventory.values()} == physical, "Couverture L1 des extrémités")
    local_sources = [item for item in register["sources"] if item["local_path"]]
    for source in local_sources:
        require(sha256(ROOT / source["local_path"]) == source["sha256"], f"Source L1 {source['id']}")

    outcomes = Counter()
    receipts = {}
    for question in catalog["questions"]:
        issue = question["issue_id"]
        issue_digest = hashlib.sha256(issue.encode("utf-8")).hexdigest()
        path = reports_directory / f"report-{issue_digest}.json"
        result = subprocess.run([executable.resolve(), "--root", ROOT, "--store", reports_directory.resolve(),
                                 "--catalog", catalog_path, "--issue", issue, "get"],
                                cwd=ROOT, capture_output=True, timeout=30)
        require(result.returncode == 0, f"Cache L1 invalide pour {issue}: {result.stderr.decode('utf-8', errors='replace')}")
        report = json.loads(result.stdout)
        require(report == read_json(path)["report"], f"Le cache L1 de {issue} a changé pendant la lecture")
        require(report["issue_id"] == issue and report["configuration_id"] == catalog["configuration_id"],
                f"Association rapport L1 de {issue}")
        require(catalog_fingerprint in report["local_inputs"], f"Catalogue L1 différent pour {issue}")
        if issue in physical:
            require(report["outcome"] in {"UNKNOWN", "INCONCLUSIVE", "CONDITIONAL"} and report["unknown_register"],
                    f"Applicabilité physique ouverte de {issue}")
        outcomes[report["outcome"]] += 1
        receipts[issue] = {"outcome": report["outcome"], "sha256": sha256(path)}
    return {"sources": len(register["sources"]), "local_sources_verified": len(local_sources),
            "physical_questions": len(physical), "outcomes": dict(outcomes), "receipts": receipts}


def main():
    parser = argparse.ArgumentParser(description="Contrôle croisé des preuves V2.1 du cartographe")
    parser.add_argument("l2", type=Path)
    parser.add_argument("native", type=Path)
    parser.add_argument("research", type=Path)
    parser.add_argument("l1_executable", type=Path)
    args = parser.parse_args()
    with (VERIFICATION / "v21_connector_inventory.csv").open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    inventory = {row["cle_interface"]: row for row in rows}
    require(len(inventory) == len(rows), "Clé d’inventaire dupliquée")
    l2 = read_json(args.l2)
    native = read_json(args.native)
    require(l2["status"] == native["status"] == "INCONCLUSIVE" and native["sources_unchanged"], "Périmètre de réception")
    paths = verify_paths(inventory, l2, native)
    research = verify_research(inventory, args.research, args.l1_executable)
    print(json.dumps({"status": "PASS", "coverage": paths, "research": research}, indent=2))


if __name__ == "__main__":
    main()
