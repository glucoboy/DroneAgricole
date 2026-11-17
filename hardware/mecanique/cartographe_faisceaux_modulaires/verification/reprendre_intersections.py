"""Isole l'intersection des paires dont la mesure combinée n'a pas abouti."""
import argparse
from pathlib import Path

from valider_modules import PairWorker, Scene, metadata_for, read, require, sha, write


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("copy", type=Path)
    parser.add_argument("nominal_report", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    nominal = read(args.nominal_report)
    require(nominal["complete"], "Contrôle initial incomplet")
    scene = Scene(args.copy, metadata_for(args.copy))
    require(scene.hashes() == nominal["inputs_sha256"], "Natifs différents du contrôle initial")
    results = []
    worker = PairWorker(scene, timeout=25)
    try:
        for row in nominal["pairs"]["near_or_invalid_pairs"]:
            if row["intersection_status"] != "unknown":
                continue
            a, b = [scene.items[name] for name in row["pair"]]
            for item in (a, b):
                item.valid = all(solid.isValid() for solid in item.shape.Solids)
            results.append(worker.check(a, b, row["aabb_lower_bound_mm"], False))
    finally:
        worker.close()
    write(args.output, {"complete": True, "source_sha256": sha(args.nominal_report),
                        "script_sha256": sha(Path(__file__)),
                        "scope": "Intersection volumique. Les dégagements des paires reprises restent ouverts.",
                        "results": results})


if __name__ == "__main__":
    main()
