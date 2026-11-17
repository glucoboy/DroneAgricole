"""Comparer trois jeux de capture axiale sur les colonnes existantes."""
import argparse
import json
from pathlib import Path

from rf_p70 import (
    App, Reader, box, cylinder, describe,
    make_band_rf1, make_clamp, make_socket_rf0, measure, read, sha256,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("copy", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    construction = args.copy / "verification/construction_prototype.json"
    routes = args.copy / "verification/routes_prototype.json"
    reader = Reader(args.copy)
    scene = {row["parent"] + "#" + row["occurrence"]: reader.occurrence(row)
             for row in read(construction)["occurrences"]
             if row["parent"].startswith("sous_assemblages/")}
    cable_ids = {row["id"] for row in read(routes)["routes"]}
    cable_keys = {key for key in scene if "SA07_" in key and key.split("#")[-1] in cable_ids}
    nav = "sous_assemblages/SA06_Prototype_Navigation.FCStd#"
    avionics = "sous_assemblages/SA05_Prototype_Avionique.FCStd#"
    outputs = []
    for index, cy in enumerate((37, -37)):
        support = nav + f"SupportRF{index}"
        antenna = nav + f"AntenneRF{index}"
        column = avionics + f"ColonnePorteuse_{1 - index}"
        ymin, ymax = (29, 37) if index == 0 else (-37, -24)
        base = scene[support].fuse([make_clamp(cy), box(-69, -64.2, ymin, ymax, 103, 106)]).removeSplitter()
        if index == 0:
            base = base.fuse(make_socket_rf0()).removeSplitter()
        for radius in (3.7, 4.2, 4.5):
            outer = cylinder(radius, 28.2, (-60, cy, 99.7))
            bore = cylinder(3.1, 28.5, (-60, cy, 99.55))
            mouth = box(-60, -54, cy - 2.5, cy + 2.5, 99.5, 128.1)
            captured = base.fuse(outer.cut(bore).cut(mouth)).removeSplitter()
            forbidden = measure(captured, scene, {support}, .05)
            result = {"support": support, "radius_mm": radius, "form": describe(captured),
                      "nominal": forbidden, "assembly_translation": {}, "stops": {}}
            outputs.append(result)
            for z in (-.3, .3):
                shifted = captured.copy()
                shifted.translate(App.Vector(0, 0, z))
                result["stops"][str(z)] = measure(shifted, scene, {support, antenna} | cable_keys)
            if not forbidden["erreurs"] and not any(r["volume_intersection_mm3"] > 1e-4
                                                     for r in forbidden["observations"]):
                removed = {support, antenna, column} | cable_keys
                for offset in (0, 2, 4, 6, 8, 10):
                    moved = captured.copy()
                    moved.translate(App.Vector(-offset, 0, 0))
                    result["assembly_translation"][str(offset)] = measure(moved, scene, removed)
                if index == 1:
                    result["band"] = measure(make_band_rf1(), {**scene, support: captured}, clearance=.1)
            print(support, radius, [(r["occurrence"], r["volume_intersection_mm3"])
                                    for r in forbidden["observations"]], flush=True)
    args.output.write_text(json.dumps({"construction_sha256": sha256(construction),
                                      "results": outputs}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
