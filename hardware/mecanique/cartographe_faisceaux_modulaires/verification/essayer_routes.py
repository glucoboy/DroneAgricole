"""Mesures FreeCAD sur une copie isolée, sans sauvegarde de natif."""
import argparse
import json
import os
from pathlib import Path
import sys
import traceback

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
LEGACY = ROOT / "hardware/mecanique/cartographe/verification/refonte_faisceaux"
sys.path.insert(0, str(LEGACY))
from controles_geometrie import Scene, distance_bound
from adapter_freecad import App, Part, boot, cable_geometry, make_native_cable, read, require, write


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("copy", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--routes", type=Path, default=HERE / "routes_candidats.json")
    parser.add_argument("--integrated", type=Path, help="Essayer conjointement la sélection déclarée")
    args = parser.parse_args()
    scene = Scene(args.copy)
    design = read(args.routes)
    selected = read(args.integrated)["selected_routes"] if args.integrated else {}
    retained = {item.key: item.shape for item in scene.items.values()
                if not item.name.startswith(("VisGuide", "RondelleGuide", "EcrouGuide", "CollierAncrageRF"))
                and item.name not in {"P72_Guide", "P73_Guide", "P75_Cadre", "P77_BerceauReserveUSB",
                                      "P78_RetenueCameraM8", "ProtectionF38", "GaineNTC", "GaineMAIN",
                                      "GaineSignalNord"}}
    environment = boot()
    report = {"scope": "BRep des routes candidates contre la structure et les câbles retenus",
              "environment": environment, "results": [], "complete": False, "integrated_selection": selected}
    if selected:
        context_doc = App.newDocument("Contexte")
        for route_id, candidate_id in selected.items():
            route = scene.routes[route_id]
            spec = next(s for s in design["variantes"][route_id] if s["id"] == candidate_id)
            cable, _ = make_native_cable(context_doc, None, route_id, spec["points_mm"],
                                         route["diametre_mm"], route["rayon_demande_mm"])
            retained[scene.cables[route_id].key] = cable.Shape.copy()
        App.closeDocument(context_doc.Name)
    for route_id, variants in design["variantes"].items():
        route = scene.routes[route_id]
        for spec in variants:
            if selected and selected.get(route_id) != spec["id"]:
                continue
            points = spec["points_mm"]
            row = {"route": route_id, **spec, "collisions": [], "unknowns": []}
            report["results"].append(row)
            doc = App.newDocument("Essai")
            try:
                original = route["points_mm"]
                require(points[0] == original[0] and points[-1] == original[-1], "Extrémités modifiées")
                for a, b, c in ((points[0], points[1], original[1]), (points[-1], points[-2], original[-2])):
                    new = (App.Vector(*b) - App.Vector(*a)).normalize()
                    old = (App.Vector(*c) - App.Vector(*a)).normalize()
                    require(new.dot(old) >= 1 - 1e-8, "Direction terminale modifiée")
                cable, _ = make_native_cable(doc, None, route_id, points,
                                             route["diametre_mm"], route["rayon_demande_mm"])
                row["geometry"] = cable_geometry(cable)
                target = cable.Shape
                row["pairs_checked"] = 0
                for name, shape in retained.items():
                    if name == scene.cables[route_id].key or distance_bound(target.BoundBox, shape.BoundBox) > 1e-6:
                        continue
                    for solid in shape.Solids:
                        if distance_bound(target.BoundBox, solid.BoundBox) > 1e-6:
                            continue
                        row["pairs_checked"] += 1
                        try:
                            shared = target.common(solid)
                            require(shared.isNull() or shared.isValid(), "Booléen invalide")
                            if shared.Volume > 1e-4:
                                row["collisions"].append({"with": name, "volume_mm3": shared.Volume})
                        except (Part.OCCError, RuntimeError) as error:
                            row["unknowns"].append({"with": name, "error": str(error)})
            except (Part.OCCError, RuntimeError, ValueError) as error:
                row["generation_error"] = str(error)
            finally:
                App.closeDocument(doc.Name)
            write(args.output, report)
            print(spec["id"], row.get("generation_error", ""), len(row["collisions"]), len(row["unknowns"]), flush=True)
    report["complete"] = True
    write(args.output, report)


if __name__ == "__main__":
    try:
        main()
        sys.stdout.flush()
        os._exit(0)
    except Exception:
        traceback.print_exc()
        sys.stderr.flush()
        os._exit(2)
