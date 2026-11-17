"""Contrôles sur les BRep sauvegardés de la copie modulaire."""
import argparse
from collections import Counter
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
LEGACY = ROOT / "hardware/mecanique/cartographe/verification/refonte_faisceaux"
sys.path.insert(0, str(LEGACY))
from controles_geometrie import (
    App, Part, PairWorker, Scene, analytic_f16_metadata, distance_bound, item_shapes,
    check_protections, require, sha, write,
)
from adapter_freecad import read


def metadata_for(root):
    tags = read(root / "verification/roles_controle.json")
    tags["F16"] = analytic_f16_metadata()
    audit = read(HERE / "audit_baseline.json")
    for key, role in audit["occurrences_par_role"].items():
        if "SA04_" in key and role in {"support_fabrique", "quincaillerie_support"}:
            tags[key.split("#")[1]] = {"role": "fixation"}
    for row in read(root / "verification/routes_prototype.json")["routes"]:
        if row["id"] == "F16":
            continue
        points = [App.Vector(*value) for value in row["points_mm"]]
        tags[row["id"]] = {"source_file": row["fichier"],
                           "start_axis": list((points[1] - points[0]).normalize()),
                           "end_axis": list((points[-2] - points[-1]).normalize()),
                           "minimum_radius_mm": row["rayon_demande_mm"],
                           "scope": "Axes de sortie et rayon de définition géométrique. Exigence fournisseur à vérifier hors M8."}
    return tags


def fixture_checks(scene, generation):
    new_names = {row["occurrence"] for row in generation["added"]}
    new_names.update(generation.get("radio", {}).get("changed_occurrences", []))
    checked = 0
    relevant = []
    items = list(scene.items.values())
    worker = PairWorker(scene, timeout=6)
    try:
        for index, a in enumerate(items):
            for b in items[index + 1:]:
                if not {a.name, b.name} & new_names:
                    continue
                lower = distance_bound(a.box, b.box)
                if lower > .9:
                    continue
                row = worker.check(a, b, lower, True)
                checked += 1
                if row["intersection_status"] != "pass" or row["clearance_status"] == "unknown" or row.get("clearance_mm", 1) < .25:
                    relevant.append(row)
    finally:
        worker.close()
    return {"checked_pairs_within_AABB_0_9mm": checked, "contacts_intersections_unknowns": relevant,
            "worker_timeouts": worker.timeouts}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("copy", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--metadata", type=Path)
    args = parser.parse_args()
    root = args.copy.resolve()
    tags = metadata_for(root)
    if args.metadata:
        write(args.metadata, tags)
    scene = Scene(root, tags)
    hashes = scene.hashes()
    generation = read(root / "verification/generation.json")
    require(set(generation["native_sha256"]) <= set(hashes) and all(hashes[key] == digest
            for key, digest in generation["native_sha256"].items()), "Natifs différents de la génération")
    inventory = item_shapes(scene)
    fixtures = fixture_checks(scene, generation)
    report = {
        "complete": True, "native_sha256": generation["native_sha256"],
        "environment": {"FreeCAD": App.Version()[:3], "OCC": Part.OCC_VERSION},
        "input_hashes": {name: sha(HERE / name) for name in ("valider_modules.py", "integration.json")},
        "occurrences": dict(Counter(row["role"] for row in inventory.values())),
        "invalid_occurrences": [name for name, row in inventory.items() if not row["valid"]],
        "protections": check_protections(scene),
        "fixtures": fixtures,
        "native_read_only": hashes == scene.hashes(),
    }
    write(args.output, report)


if __name__ == "__main__":
    main()
