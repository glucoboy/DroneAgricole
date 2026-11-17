"""Matérialise et contrôle les enveloppes candidates B et C, sans modification de scène."""
import os
import sys

from adapter_implantation import App, COPY, HERE, PAIRS, Part, Scene, V, bounds, report_pairs, write


def main():
    scene = Scene(COPY)
    shapes = {item.name: item.shape for item in scene.items.values()}
    variants = {
        "B": [
            ("PDB18139CentreActuel", (2, -36, 39), (80, 80, 20), ["PDB"],
             "Holybro 18139 au centre du 18138, volume englobant nu"),
            ("PDB18139DecaleEst", (13, -36, 39), (80, 80, 20), ["PDB"],
             "Holybro 18139, +11 mm X, pistes et prises non représentées"),
            ("CarteSynchronisation", (43, -33, 114), (28, 20, 10), [],
             "Réservation hypothétique, platine passive et connecteurs")
        ],
        "C": [
            ("InjecteurPoE", (-102, -38, 165), (85, 76, 36), [],
             "Tycon TP-DCDC-1248GAD, au-dessus du flanc ouest, sans fiches"),
            ("CameraGigE", (63, -14.5, -136), (62.2, 29, 29), ["EQ_Basler_Occurrence"],
             "Basler GigE, enveloppe rectangulaire conservatrice sans objectif ni débattement")
        ]
    }
    reports = {}
    try:
        for name, candidates in variants.items():
            folder = HERE.parent / name / "assemblages"
            folder.mkdir(parents=True, exist_ok=True)
            native = folder / "Reservations_interfaces.FCStd"
            if native.exists():
                raise RuntimeError(f"Essai déjà présent : {native}")
            doc = App.newDocument("Reservation" + name)
            rows = []
            for identifier, origin, size, replaced, title in candidates:
                obj = doc.addObject("Part::Box", identifier)
                obj.Label = title
                obj.Length, obj.Width, obj.Height = size
                obj.Placement.Base = V(*origin)
                obj.Placement = App.Placement(V(*origin), App.Rotation())
                doc.recompute()
                checks = report_pairs(obj.Shape, {key: sh for key, sh in shapes.items() if key not in replaced})
                rows.append({"id": identifier, "bbox_mm": bounds(obj.Shape), "dimensions_mm": size,
                             "excluded_as_replaced": replaced, "checks": checks})
                obj.addProperty("App::PropertyString", "Maturite")
                obj.Maturite = "Réservation conceptuelle – À valider"
                print(identifier, [r["name"] for r in checks["collisions"]], flush=True)
            doc.saveAs(str(native))
            App.closeDocument(doc.Name)
            reports[name] = rows
            write(HERE / "enveloppes_BC.json", {"complete": len(reports) == len(variants),
                                               "comparison_scene_sha256": scene.hashes(),
                                               "variants": reports,
                                               "scope": "Réservations rectangulaires comparées au nominal, sans engagement ni service des prises."})
    finally:
        PAIRS.close()


if __name__ == "__main__":
    main()
