"""Planches avant/après à partir des BRep sauvegardés, sans écriture CAO."""

import argparse
from pathlib import Path

from audit_baseline import ORANGE, ROUTE_CONNECTORS, occurrence_role
from valider_modules import Scene, metadata_for, read
from controles_geometrie import sha, write
from controles_vues import (
    BACKGROUND, MUTED, NAVY, Patch, dimension_scale, footer, heading,
    np, plt, projection, render, save, set_panel,
)


HERE = Path(__file__).resolve().parent
COLORS = {
    "structure": "#71869a", "cable": "#526f94", "gaine": "#203850",
    "fixation": "#758397", "retire": "#c76b24", "repris": "#0b8475",
    "F41": "#953f9c",
}


def scene_layers(scene, before, changed, cache, hashes):
    layers = {}
    for item in scene.items.values():
        if before:
            role = {
                "support_fabrique": "fixation", "collier_equipement": "fixation",
                "quincaillerie_support": "fixation", "enveloppe_liaison": "cable",
                "gaine_candidate": "gaine", "chassis_equipement_interface": "structure",
            }[occurrence_role(item)]
            if item.name in {"SupportRF0", "SupportRF1"}:
                role = "fixation"
        else:
            role = "cable" if item.name in ROUTE_CONNECTORS else item.role
        source = item.row["source"]
        # Réutiliser seulement les maillages d'une même forme et pose.
        key = (hashes[source], item.row["objet_source"], tuple(item.pose.toMatrix().A), role)
        if key not in cache:
            vertices, faces = item.shape.tessellate(1.8 if role == "structure" else .22)
            if not faces:
                raise RuntimeError("Forme non tessellée " + item.key)
            cache[key] = np.array([(v.x, v.y, v.z) for v in vertices])[np.array(faces)]
        tag = "retire" if before and item.name in ORANGE else role
        if not before and role == "fixation" and item.name in changed:
            tag = "repris"
        layers[item.key] = (item.name, role, tag, cache[key])
    return layers


def plate(output, layers, spec):
    figure, axes = plt.subplots(1, 2, figsize=(13.5, 7.8), facecolor=BACKGROUND)
    figure.subplots_adjust(left=.045, right=.955, top=.79, bottom=.185, wspace=.095)
    heading(figure, spec["title"], spec["subtitle"])
    view = projection(*spec["orientation"])
    for ax, objects, label, metric in zip(
            axes, layers, ("AVANT   ·   CANDIDAT PRÉCÉDENT", "APRÈS   ·   COPIE MODULAIRE"), spec["metrics"]):
        set_panel(ax, label)
        meshes = []
        for key, (name, role, tag, triangles) in objects.items():
            if role not in spec["roles"]:
                continue
            color = COLORS["F41" if name == "F41" and spec.get("highlight_f41") else tag]
            meshes.append((key, role, color, color, triangles))
        render(ax, meshes, view, crop=spec["crop"])
        dimension_scale(ax, spec["scale"])
        ax.text(.5, -.085, metric, transform=ax.transAxes, color=NAVY,
                fontsize=10, fontweight="bold", ha="center")
    handles = [Patch(facecolor=COLORS[key], label=label) for key, label in spec["legend"]]
    figure.legend(handles=handles, loc="lower center", bbox_to_anchor=(.5, .056),
                  frameon=False, ncol=len(handles), labelcolor=MUTED, fontsize=9)
    footer(figure, "Projections orthographiques à échelle identique · Géométries nominales sauvegardées dans FreeCAD")
    path = output / spec["file"]
    save(figure, path)
    return {**spec, "sha256": sha(path)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("before", type=Path)
    parser.add_argument("after", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    old = Scene(args.before)
    new = Scene(args.after, metadata_for(args.after))
    hashes = [scene.hashes() for scene in (old, new)]
    audit = read(HERE / "audit_baseline.json")
    generation = read(HERE / "generation.json")
    if hashes[0] != audit["natifs_et_registres_sha256"] or any(
            hashes[1].get(path) != value for path, value in generation["native_sha256"].items()):
        raise RuntimeError("Les natifs diffèrent du périmètre de comparaison contrôlé")
    if set(old.routes) != set(new.routes):
        raise RuntimeError("Identifiants de parcours différents")
    changed = {row["occurrence"] for row in generation["added"]}
    changed.update(generation.get("radio", {}).get("changed_occurrences", []))
    cache = {}
    layers = [scene_layers(scene, index == 0, changed, cache, hashes[index])
              for index, scene in enumerate((old, new))]
    core = ((-143, 143), (-122, 125), (-109, 182))
    support_legend = [("retire", "Cinq pièces déposées"), ("repris", "Retenues ajoutées ou reprises"),
                      ("fixation", "Autres fixations")]
    specs = [
        {
            "file": "01_integration_avant_apres.png",
            "title": "Intégration des faisceaux",
            "subtitle": "Zone centrale du cartographe · Châssis en transparence",
            "orientation": (-52, 27), "crop": core, "scale": 50,
            "roles": ["structure", "cable", "gaine", "fixation"],
            "legend": [*support_legend, ("cable", "Câbles"), ("gaine", "Gaines")],
            "metrics": ["3 grands cadres ou guides · 4 gaines", "0 grand cadre ou guide · 2 gaines"],
        },
        {
            "file": "02_retenues_avant_apres.png",
            "title": "Supports et retenues",
            "subtitle": "Les structures continues cèdent la place à des ancrages locaux",
            "orientation": (-52, 27), "crop": core, "scale": 50,
            "roles": ["structure", "fixation"], "legend": support_legend,
            "metrics": ["222,0 cm³ de matière dans les supports SA07",
                        "30,5 cm³ de matière dans les supports SA07"],
        },
        {
            "file": "03_faisceaux_avant_apres.png",
            "title": "Cheminement des câbles",
            "subtitle": "Côté ouest et baie centrale · Le cordon de diagnostic F41 est mis en évidence",
            "orientation": (-147, 24), "crop": ((-147, 202), (-128, 121), (-123, 182)), "scale": 50,
            "roles": ["structure", "cable", "gaine"], "highlight_f41": True,
            "legend": [("F41", "Cordon F41"), ("cable", "Autres câbles"), ("gaine", "Gaines")],
            "metrics": ["F41 · 1 181 mm d’axe", "F41 · 340 mm d’axe"],
        },
    ]
    outputs = [plate(args.output, layers, spec) for spec in specs]
    if [scene.hashes() for scene in (old, new)] != hashes:
        raise RuntimeError("Les fichiers natifs ont changé pendant le rendu")
    write(args.output / "index_comparatif.json", {
        "avant": hashes[0], "apres": hashes[1], "parcours_communs": len(new.routes),
        "script_sha256": sha(Path(__file__)), "planches": outputs,
    })


if __name__ == "__main__":
    main()
