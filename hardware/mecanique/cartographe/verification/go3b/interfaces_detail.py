"""Détails des sondes d'interfaces sauvegardées, sans mutation FreeCAD."""

import argparse
import json
import os
from pathlib import Path
import sys

from electromechanical_engine.freecad import guard
from electromechanical_engine.qualification.native_replay import ENTRY, MEC, write

sys.path[:0] = [str(MEC / "cartographe/verification/refonte_faisceaux"),
               str(MEC / "cartographe/verification")]
from controles_geometrie import App
from read_brep_prototype import Reader
from controles_vues import (BACKGROUND, NAVY, dimension_scale, footer, heading,
                            np, plt, projection, render, save, set_panel)


SERVICE = "pieces/fabriquees/ASSUMED_GO3B_Service.FCStd"
ENERGY = "sous_assemblages/SA03_Prototype_Energie.FCStd"
HARNESSES = "sous_assemblages/SA07_Prototype_Faisceaux.FCStd"
AVIONICS = "sous_assemblages/SA05_Prototype_Avionique.FCStd"
COLORS = ("#bc75c6", "#a14fb7", "#6f2f92")


def sha_tree(cad):
    return {p.relative_to(cad).as_posix(): guard.sha256(p) for p in guard.dependencies(cad, [ENTRY])}


def bounds(shape):
    box = shape.BoundBox
    return [box.XMin, box.YMin, box.ZMin, box.XMax, box.YMax, box.ZMax]


def tessellate(name, shape, role, color, coarse):
    vertices, faces = shape.tessellate(coarse)
    return (name, role, color, color, np.asarray([tuple(v) for v in vertices])[np.asarray(faces)])


def plot(cad, output):
    before = sha_tree(cad)
    service_before = guard.sha256(cad / SERVICE)
    reader = Reader(cad)
    objects = {}
    for parent, names in ((ENERGY, ("UART_isole", "PDB", "PM08", "Isolation")),
                          (HARNESSES, ("F40", "F41", "F31", "F35", "F25", "P72_Guide", "P73_Guide", "RetenueP85F25")),
                          (AVIONICS, ("Holybro6XOrin",))):
        for name in names:
            objects[name] = reader.shape(parent, name)
    cases = [
        ("TTL", ["ASSUMED_TTL_3", "ASSUMED_TTL_5", "ASSUMED_TTL_15"],
         ((-10, 42), (-3, 44), (37, 69)), ("UART_isole", "PDB", "F40"), [3, 5, 15]),
        ("USB-B", ["ASSUMED_USB_5", "ASSUMED_USB_15", "ASSUMED_USB_50"],
         ((-126, -53), (-47, -7), (38, 66)), ("UART_isole", "F40", "F41", "P72_Guide"), [5, 15, 50]),
        ("CAN1", ["ASSUMED_CAN1_5p7", "ASSUMED_CAN1_9p95", "ASSUMED_CAN1_17p7"],
         ((39, 67), (-32, 1), (129, 157)), ("Holybro6XOrin", "F31", "F35", "F25"), [5.7, 9.95, 17.7]),
    ]
    probes = {name: reader.shape(SERVICE, name) for _, names, _, _, _ in cases for name in names}
    fig, axes = plt.subplots(3, 2, figsize=(12, 12.6), facecolor=BACKGROUND)
    fig.subplots_adjust(left=.05, right=.95, top=.82, bottom=.10, hspace=.38, wspace=.15)
    heading(fig, "Volumes réservés aux interfaces", "Copie consolidée · gabarits ASSUMED sauvegardés · coordonnées globales en mm")
    for row, (label, names, crop, context, lengths) in zip(axes, cases):
        meshes = [tessellate(name, objects[name], "structure", "#6f8aa3", 1.6) for name in context]
        for name, color in zip(names, COLORS):
            meshes.append(tessellate(name, probes[name], "fixation", color, .2))
        for ax, view_name, angle in zip(row, ("Dessus", "Profil"), ((-90, 90), (-90, 0))):
            set_panel(ax, f"{label} · {view_name}")
            render(ax, meshes, projection(*angle), crop=crop)
            dimension_scale(ax, 10)
            ax.text(.025, .96, "Portées " + " / ".join(str(v).replace(".", ",") for v in lengths) + " mm",
                    transform=ax.transAxes, va="top", fontsize=8, color=NAVY,
                    bbox={"facecolor": "white", "edgecolor": "#dae3ed", "pad": 3}, zorder=6)
    footer(fig, "Hypothèses de corps et de service. Les surfaces, verrous, contacts et courses réels restent à valider.")
    save(fig, output)
    if before != sha_tree(cad) or service_before != guard.sha256(cad / SERVICE):
        raise RuntimeError("Source CAO modifiée pendant la projection")
    write(output.with_suffix(".json"), {"date": "2026-11-17", "freecad": App.Version(),
          "scope": cad.as_posix(), "image_sha256": guard.sha256(output), "native_sha256_unchanged": before,
          "service_document_sha256": service_before,
          "status": "INCONCLUSIVE", "render_status": "PASS",
          "method": "Tessellation des volumes sauvegardés, vues orthographiques. Les portées constituent des hypothèses distinctes.",
          "boxes_mm": {name: bounds(shape) for name, shape in probes.items()},
          "screening_note": "Les gabarits se recouvrent entre eux par construction. Leur transparence représente la plage étudiée."})
    print(output.as_posix(), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("copy", type=Path)
    parser.add_argument("image", type=Path)
    args = parser.parse_args()
    plot(args.copy.resolve(strict=True), args.image)
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0)
