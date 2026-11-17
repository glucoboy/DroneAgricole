"""Rend les vues 3D du candidat à partir des formes sauvegardées."""
import argparse
from pathlib import Path
import sys

from valider_modules import Scene, metadata_for
from controles_geometrie import sha, write
from controles_vues import BACKGROUND, dimension_scale, footer, heading, np, plt, projection, render, save, set_panel


PALETTE = {
    "BAT": "#c27632", "PUISSANCE": "#bd3d27", "AVIONIQUE": "#5885c3",
    "PERCEPTION": "#148b9a", "NAV_RF": "#218363", "CAMERA": "#8057b3",
    "DIAGNOSTIC_ISOLE": "#cf8b2e", "BRAS_1": "#a95150", "BRAS_2": "#a95150",
    "BRAS_3": "#a95150", "BRAS_4": "#a95150",
}


def render_plate(output, filename, meshes, views, title, subtitle, note):
    figure, axes = plt.subplots(1, 2, figsize=(14, 7), facecolor=BACKGROUND)
    figure.subplots_adjust(left=.05, right=.96, top=.80, bottom=.12, wspace=.09)
    heading(figure, title, subtitle)
    for ax, (label, orientation, crop, scale) in zip(axes, views):
        set_panel(ax, label)
        render(ax, meshes, projection(*orientation), crop=crop)
        dimension_scale(ax, scale)
    footer(figure, note)
    path = output / filename
    save(figure, path)
    return {"file": filename, "sha256": sha(path), "occurrences": [mesh[0] for mesh in meshes]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("copy", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    scene = Scene(args.copy, metadata_for(args.copy))
    grouped = {"structure": [], "faisceaux": [], "retenues": []}
    for item in scene.items.values():
        role = item.role
        module = scene.routes.get(item.name, {}).get("module", "CAMERA")
        if role == "fixation":
            layer, color = "retenues", "#158679"
        elif role in {"cable", "gaine"} or item.name.startswith(("ConnecteurF16", "ConnecteurM8Camera")):
            layer, color = "faisceaux", "#203953" if role == "gaine" else PALETTE[module]
        else:
            layer, color = "structure", "#748ca2"
        vertices, triangles = item.shape.tessellate(1.8 if layer == "structure" else .22)
        if not triangles:
            raise RuntimeError("Forme non tessellée " + item.key)
        mesh = np.array([[v.x, v.y, v.z] for v in vertices])[np.array(triangles)]
        grouped[layer].append((item.key, role, color, color, mesh))
    overview = ("Vue d'ensemble", (-54, 28), None, 100)
    center = ("Zone centrale", (-54, 28), ((-145, 145), (-120, 120), (-140, 180)), 50)
    outputs = []
    for filename, layer, title, subtitle, note in (
        ("01_structure.png", "structure", "Structure et interfaces", "Châssis, équipements et montages existants",
         "Repère et géométries issus de la copie FreeCAD. Filtrage des faisceaux et retenues dédiées."),
        ("02_faisceaux.png", "faisceaux", "Onze modules de faisceau", "Axes et enveloppes extérieures, colorés par sous-ensemble",
         "Une enveloppe représente un trajet de définition. Les terminaisons, réserves et attaches restent à valider."),
        ("03_retenues.png", "retenues", "Retenues et fixations locales", "Selles des bras, retenues perception et nouveaux sites",
         "Les bandes sont des enveloppes nominales. La fermeture réelle, le serrage et la tenue restent à valider."),
    ):
        meshes = grouped[layer]
        if layer == "structure":
            meshes = [(key, "isolated", color, detail, triangles) for key, _, color, detail, triangles in meshes]
        outputs.append(render_plate(args.output, filename, meshes, (overview, center), title, subtitle, note))
    outputs.append(render_plate(
        args.output, "04_integration.png", sum(grouped.values(), []),
        (center, ("Chant sud P64 et gaine F38", (-104, 24), ((-48, 50), (-116, -70), (29, 60)), 20)),
        "Intégration sur les interfaces existantes", "Structure en transparence, retenues locales en vert",
        "Les positions et encombrements correspondent à la CAO nominale sauvegardée. Le montage réel reste à valider.",
    ))
    write(args.output / "index_vues.json", {"views": outputs, "native_sha256": scene.hashes()})


if __name__ == "__main__":
    main()
