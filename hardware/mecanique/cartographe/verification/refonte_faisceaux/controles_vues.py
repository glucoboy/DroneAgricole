"""Vues des solides FreeCAD sauvegardés, colorées par groupes de câblage."""

import argparse
import hashlib
import json
from pathlib import Path

import matplotlib
import numpy as np

from controles_geometrie import BUILD, ENTRY, REFERENCE, ROOT, Scene, baseline_metadata, read, sha, write

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection
from matplotlib.lines import Line2D
from matplotlib.patches import Patch


BACKGROUND = "#f4f7fa"
NAVY = "#1d3349"
MUTED = "#52677c"
PALETTE = {
    "Énergie": "#cc553e", "Vol": "#4b9f44", "Bras": "#9e5141",
    "Perception": "#1b9aa8", "Navigation": "#299e79", "Radio": "#a88427",
    "Avionique": "#5879c3", "Sécurité": "#d39629", "Calcul": "#cf834e",
}
GAINE = "#223b59"
FIXATION = "#df8234"


def projection(azimuth, elevation):
    a, e = np.deg2rad([azimuth, elevation])
    depth = np.array([np.cos(e) * np.cos(a), np.cos(e) * np.sin(a), np.sin(e)])
    horizontal = np.cross([0, 0, 1], depth)
    horizontal /= np.linalg.norm(horizontal)
    return np.array([horizontal, np.cross(depth, horizontal), depth]).T


def colors(architecture):
    by_route = {}
    families = {}
    for group in architecture["groupes"]:
        family = group["label"].split(" · ")[0]
        families[group["id"]] = family
        for route in group["routes"]:
            if route in by_route:
                raise ValueError("Route colorée dans deux groupes " + route)
            by_route[route] = (group["couleur"], family)
    return by_route, families


def mesh_scene(scene, architecture):
    by_route, _ = colors(architecture)
    if set(by_route) != set(scene.routes):
        raise ValueError("Couverture des couleurs différente de l’inventaire natif")
    previous = ROOT / "hardware/mecanique/cartographe_faisceaux_autonome" / BUILD
    cached_index = {}
    if previous.is_file():
        cached_index = {(row["parent"], row["occurrence"]): index
                        for index, row in enumerate(json.loads(read(previous))["occurrences"])}
    cache = REFERENCE / "reconstruction_faisceaux/vues"
    meshes = []
    hashes = {}
    for item in scene.items.values():
        role = item.role
        if item.name in {"P72_Guide", "P77_BerceauReserveUSB", "P78_RetenueCameraM8"}:
            role = "fixation"
        if role == "cable":
            detail_color, family = by_route[item.name]
            color = PALETTE.get(family, detail_color)
        elif role == "gaine":
            color = detail_color = GAINE
        elif role == "fixation":
            color = detail_color = FIXATION
        else:
            color = detail_color = "#748ca2"
        index = cached_index.get((item.row["parent"], item.name))
        cached = cache / f"mesh_{index}.npz"
        tri = None
        if role == "structure" and cached.is_file() and scene.top[item.row["parent"]].isIdentity():
            source = item.row["source"]
            if source not in hashes:
                hashes[source] = sha(scene.root / source)
            expected = hashlib.sha256((hashes[source] + json.dumps(item.row, sort_keys=True)).encode()).hexdigest()
            with np.load(cached) as previous_mesh:
                if str(previous_mesh["key"]) == expected:
                    tri = previous_mesh["tri"]
        if tri is None:
            vertices, faces = item.shape.tessellate(.20 if role != "structure" else 1.8)
            if not faces:
                raise ValueError("Tessellation vide " + item.key)
            tri = np.array([[v.x, v.y, v.z] for v in vertices])[np.array(faces)]
        meshes.append((item.name, role, color, detail_color, tri))
    print("maillages", len(meshes), flush=True)
    return meshes


def set_panel(ax, title):
    ax.set_facecolor("#ffffff")
    ax.set_title(title, color=NAVY, loc="left", pad=14, fontsize=12, fontweight="bold")
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])
    for side in ax.spines.values():
        side.set_color("#dce4ec")


def render(ax, meshes, view, crop=None, highlighted=None, detail=False):
    if crop is not None:
        crop_low, crop_high = np.array(crop).T
        xyz = np.array([[x, y, z] for x in crop[0] for y in crop[1] for z in crop[2]])
        flat_crop = (xyz @ view)[:, :2]
        low = flat_crop.min(axis=0)
        high = flat_crop.max(axis=0)
    for layer in ("context", "harness"):
        all_triangles, all_colors = [], []
        for name, role, color, detail_color, triangles in meshes:
            context = role == "structure" or (highlighted is not None and name not in highlighted)
            if (layer == "context") != context:
                continue
            if crop is not None:
                mask = np.all(triangles.max(axis=1) >= crop_low, axis=1) & np.all(
                    triangles.min(axis=1) <= crop_high, axis=1)
                triangles = triangles[mask]
            flat = triangles @ view
            if not len(flat):
                continue
            normal = np.cross(flat[:, 1] - flat[:, 0], flat[:, 2] - flat[:, 0])
            shade = .69 + .31 * np.abs(normal[:, 2]) / np.maximum(np.linalg.norm(normal, axis=1), 1e-12)
            rgb = np.array(matplotlib.colors.to_rgb(detail_color if detail else color))
            alpha = .15 if context else .72 if role == "fixation" else .99
            all_colors.append(np.c_[shade[:, None] * rgb, np.full(len(flat), alpha)])
            all_triangles.append(flat)
        if not all_triangles:
            continue
        triangles = np.concatenate(all_triangles)
        order = np.argsort(triangles[:, :, 2].mean(axis=1))
        ax.add_collection(PolyCollection(triangles[order, :, :2], facecolors=np.concatenate(all_colors)[order],
                                         edgecolors="none", antialiased=False, zorder=2 if layer == "harness" else 1))
    if crop is not None:
        ax.set_xlim(low[0], high[0])
        ax.set_ylim(low[1], high[1])
    else:
        ax.autoscale_view()


def annotate(ax, view, label, point, offset, color=NAVY):
    xy = (np.array(point) @ view)[:2]
    ax.annotate(label, xy, xytext=offset, textcoords="offset points", color=color, fontsize=9,
                fontweight="semibold", zorder=5, bbox={"fc": "#ffffff", "ec": "#e3eaf2", "pad": 3},
                arrowprops={"arrowstyle": "-", "color": color, "lw": .85})


def dimension_scale(ax, width=50):
    x0, x1 = ax.get_xlim()
    y0, y1 = ax.get_ylim()
    x = x0 + .045 * (x1 - x0)
    y = y0 + .065 * (y1 - y0)
    ax.plot([x, x + width], [y, y], color=NAVY, lw=2, zorder=5)
    ax.text(x + width / 2, y + .017 * (y1 - y0), f"{width} mm", color=NAVY, fontsize=8,
            ha="center", zorder=6)


def center(item):
    point = item.shape.BoundBox.Center
    return [point.x, point.y, point.z]


def heading(fig, title, subtitle):
    fig.text(.035, .938, title, color=NAVY, fontsize=24, fontweight="bold")
    fig.text(.036, .886, subtitle, color=MUTED, fontsize=11)


def footer(fig, message):
    fig.text(.036, .031, message, color=MUTED, fontsize=9)


def save(fig, path):
    fig.savefig(path, dpi=155, facecolor=BACKGROUND)
    plt.close(fig)


def overview(output, meshes, scene):
    fig, (a, b) = plt.subplots(1, 2, figsize=(15, 8), facecolor=BACKGROUND,
                              gridspec_kw={"width_ratios": [1.14, 1]})
    fig.subplots_adjust(left=.04, right=.96, top=.80, bottom=.20, wspace=.08)
    heading(fig, "Organisation des faisceaux du cartographe",
            "Assemblage candidat · Vue des solides sauvegardés · Prototype sans dock")
    set_panel(a, "Ensemble du drone")
    set_panel(b, "Châssis central, troncs et dérivations")
    v1, v2 = projection(-48, 30), projection(-63, 37)
    render(a, meshes, v1)
    render(b, meshes, v2, crop=((-110, 190), (-110, 145), (-100, 160)))
    dimension_scale(a, 100)
    dimension_scale(b)
    for name, label, offset in (("ProtectionF38", "Gaine F38", (-53, -21)),
                                ("P75_Cadre", "Retenue P75", (18, 24))):
        item = next((item for item in scene.items.values() if item.name == name), None)
        if item:
            annotate(b, v2, label, center(item), offset, GAINE if item.role == "gaine" else FIXATION)
    legends = [Line2D([0], [0], color=color, lw=3, label=key) for key, color in PALETTE.items()]
    legends.extend([Patch(color=GAINE, label="Gaine physique"), Patch(color=FIXATION, label="Guide ou retenue")])
    fig.legend(handles=legends, loc="lower center", bbox_to_anchor=(.5, .069), ncol=6,
               frameon=False, fontsize=9)
    footer(fig, "Structure en transparence et profondeur des câbles rendue par ombrage. Vue de lecture du réseau, sans mesure de dégagement.")
    save(fig, output / "01_ensemble.png")


def detail_avionique(output, meshes, scene):
    fig, (a, b) = plt.subplots(1, 2, figsize=(14, 7.8), facecolor=BACKGROUND)
    fig.subplots_adjust(left=.04, right=.96, top=.79, bottom=.13, wspace=.08)
    heading(fig, "Troncs, dérivations et retenues",
            "La gaine et les guides sont mis en évidence sur les volumes FreeCAD au nominal.")
    active = {item.name for item in scene.items.values() if item.role in {"gaine", "fixation"}}
    v1 = projection(-94, 23)
    set_panel(a, "Distribution et guides du bord droit")
    shown = active | {"F38_NEG", "F38_POS", "F05_NEG", "F05_POS", "F08_AMONT", "F08_AVAL", "F16"}
    render(a, meshes, v1, crop=((-90, 130), (-118, -45), (22, 120)), highlighted=shown, detail=True)
    for name, label, offset in (("ProtectionF38", "F38 · protection commune", (-100, -33)),
                                ("P73_Guide", "Guide P73", (28, 17))):
        item = next((item for item in scene.items.values() if item.name == name), None)
        if item:
            annotate(a, v1, label, center(item), offset, GAINE if item.role == "gaine" else FIXATION)
    v2 = projection(-40, 59)
    set_panel(b, "Avionique et répartition vers les bras")
    shown = active | {"F04_1", "F04_2", "F04_3", "F04_4", "F21", "F36", "F31", "F25"}
    render(b, meshes, v2, crop=((-85, 99), (-115, 79), (75, 151)), highlighted=shown, detail=True)
    annotate(b, v2, "Retenue P75", center(next(item for item in scene.items.values() if item.name == "P75_Cadre")),
             (19, 22), FIXATION)
    for ax in (a, b):
        dimension_scale(ax)
    footer(fig, "Les volumes de retenue apparaissent en orange. Les commandes ESC restent quatre câbles individuels.")
    save(fig, output / "02_troncs_retenues.png")


def detail_perception(output, meshes):
    fig, (a, b) = plt.subplots(1, 2, figsize=(14, 7.8), facecolor=BACKGROUND)
    fig.subplots_adjust(left=.04, right=.96, top=.79, bottom=.13, wspace=.08)
    heading(fig, "Perception et passages aux équipements",
            "Deux familles de cheminements distinctes, avec visibilité du support et des terminaisons.")
    v1 = projection(36, -19)
    set_panel(a, "Caméra suspendue et boucle de service")
    render(a, meshes, v1, crop=((62, 230), (-106, 74), (-113, 84)),
           highlighted={"F16", "F_M8", "P73_Guide", "P78_RetenueCameraM8"}, detail=True)
    annotate(a, v1, "Boucle mobile F16", [200, -30, -96.82], (6, -25), "#925ac7")
    v2 = projection(132, 33)
    set_panel(b, "Airy et branches Ethernet, 12 V et temps")
    render(b, meshes, v2, crop=((-150, 58), (13, 120), (-25, 155)),
           highlighted={"AIRY", "AIRY_ETH", "AIRY_PWR", "AIRY_SYNC"}, detail=True)
    annotate(b, v2, "Éclatement OEM", [-80, 64, 120], (-55, 23), "#139cab")
    for ax in (a, b):
        dimension_scale(ax)
    footer(fig, "La vue de la caméra représente la position nominale. La jonction Airy représente des enveloppes de cordons.")
    save(fig, output / "03_camera_airy.png")


def detail_sleeves(output, meshes, scene):
    sleeves = [item for item in scene.items.values() if item.role == "gaine"]
    if not sleeves:
        return
    fig, axes = plt.subplots(1, len(sleeves), figsize=(max(9, 5.6 * len(sleeves)), 6.6), facecolor=BACKGROUND,
                             squeeze=False)
    fig.subplots_adjust(left=.04, right=.96, top=.74, bottom=.15, wspace=.09)
    heading(fig, "Gaines communes et départs de branches",
            "Chaque panneau montre la gaine sauvegardée, ses câbles membres et la retenue voisine.")
    for ax, sleeve in zip(axes[0], sleeves):
        view = projection(-68, 32)
        box = sleeve.shape.BoundBox
        margin = min(max(10, box.DiagonalLength * .3), 27)
        crop = tuple((getattr(box, a + "Min") - margin, getattr(box, a + "Max") + margin) for a in "XYZ")
        members = set(sleeve.metadata.get("members", []))
        shown = {sleeve.name} | members
        shown.update(item.name for item in scene.items.values() if item.role == "fixation")
        set_panel(ax, sleeve.name)
        render(ax, meshes, view, crop=crop, highlighted=shown, detail=True)
        annotate(ax, view, "Paroi de gaine", center(sleeve), (-50, 24), GAINE)
        dimension_scale(ax, 20 if box.DiagonalLength > 24 else 10)
        ax.text(.03, -.10, " · ".join(sorted(members)), transform=ax.transAxes, color=MUTED, fontsize=9)
    footer(fig, "Les sorties restent distinctes et correspondent aux cordons individuels visibles au-delà de la paroi.")
    save(fig, output / "04_gaines.png")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("copy", type=Path)
    parser.add_argument("architecture", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--metadata", type=Path)
    args = parser.parse_args()
    metadata = baseline_metadata()
    if args.metadata:
        metadata.update(json.loads(read(args.metadata)))
    architecture = json.loads(read(args.architecture))
    scene = Scene(args.copy, metadata)
    args.output.mkdir(parents=True, exist_ok=True)
    hashes = scene.hashes()
    meshes = mesh_scene(scene, architecture)
    overview(args.output, meshes, scene)
    detail_avionique(args.output, meshes, scene)
    detail_perception(args.output, meshes)
    detail_sleeves(args.output, meshes, scene)
    if hashes != scene.hashes():
        raise RuntimeError("Les natifs ont changé pendant le rendu")
    write(args.output / "sources.json", {"complete": True, "entry": ENTRY, "native_and_register_sha256": hashes,
                                        "architecture_sha256": sha(args.architecture),
                                        "metadata_sha256": sha(args.metadata) if args.metadata else None,
                                        "renderer_sha256": sha(__file__),
                                        "png_sha256": {p.name: sha(p) for p in sorted(args.output.glob("*.png"))}})


if __name__ == "__main__":
    main()
