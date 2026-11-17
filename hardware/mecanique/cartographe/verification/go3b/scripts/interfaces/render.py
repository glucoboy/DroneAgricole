"""Vues des BRep sauvegardés GO3B, avec empreintes de chaque fermeture XLink."""

import argparse
import os
from pathlib import Path
import sys

from electromechanical_engine.freecad import guard
from electromechanical_engine.qualification.native_replay import ENTRY, MEC, write

sys.path[:0] = [str(MEC / "cartographe/verification/refonte_faisceaux"),
               str(MEC / "cartographe/verification")]
from controles_geometrie import App, Scene
from controles_vues import (BACKGROUND, NAVY, Patch, dimension_scale, footer,
                            heading, np, plt, projection, render, save, set_panel)


BAY = ((-206, 143), (-125, 135), (29, 183))
DIAGNOSTIC = ((-203, 30), (-108, 105), (29, 130))
CAMERA = ((-110, 215), (-123, 123), (-108, 151))
COLORS = {"structure": "#7589a4", "câble": "#197b8f", "interface": "#356c49",
          "modifié": "#bc6431", "assumed": "#ab3c72", "service": "#7547af"}
SERVICE_DOCUMENT = "pieces/fabriquees/ASSUMED_GO3B_Service.FCStd"


class SavedScene(Scene):
    def group_matches(self, path, rows):
        types, _ = self.reader.xml(path)
        saved = {name for name, kind in types.items() if kind == "App::Link"}
        if saved != {row["occurrence"] for row in rows}:
            raise ValueError(f"Registre incomplet : {path}")


def capture(root):
    return {p.relative_to(root).as_posix(): guard.sha256(p) for p in guard.dependencies(root, [ENTRY])}


def shape_center(shape):
    return tuple(shape.BoundBox.Center)


def label_point(scene, item):
    wire = scene.wires.get(item.name)
    if wire is not None and item.name in {"F40", "F41"}:
        module = next(x for x in scene.items.values() if x.name == "UART_isole")
        return tuple(min((v.Point for v in wire.Vertexes), key=lambda v: (v-module.shape.BoundBox.Center).Length))
    return shape_center(item.shape)


def is_inside(shape, crop):
    b = shape.BoundBox
    return not any(getattr(b, axis + "Min") > high or getattr(b, axis + "Max") < low
                   for axis, (low, high) in zip("XYZ", crop))


def role_of(name, shape_role, changed):
    low = name.casefold()
    if name == "ASSUMED_ServiceGO3B":
        return "assumed"
    if any(term in low for term in ("retrait", "outil", "service", "withdraw", "tool")) and "assumed" in low:
        return "service"
    if any(term in low for term in ("assumed", "gabarit", "enveloppe")):
        return "assumed"
    if name in changed:
        return "modifié"
    if shape_role in {"cable", "gaine"}:
        return "câble"
    if any(term in low for term in ("uart", "connecteur", "pdb", "pm08", "retenue", "guide")):
        return "interface"
    return "structure"


def mesh_scene(scene, changed, state, cache):
    meshes, tags, empty = [], {}, []
    for item in scene.items.values():
        shape = item.shape
        if not any(is_inside(shape, crop) for crop in (BAY, DIAGNOSTIC, CAMERA)):
            continue
        role = role_of(item.name, item.role, changed)
        key = (state[item.row["source"]], item.row["objet_source"], tuple(item.pose.toMatrix().A), role)
        if key not in cache:
            vertices, faces = shape.tessellate(1.5 if role == "structure" else .3)
            if not faces:
                empty.append(item.key)
                continue
            cache[key] = np.asarray([tuple(v) for v in vertices])[np.asarray(faces)]
        meshes.append((item.name, "structure" if role == "structure" else "solid",
                       COLORS[role], COLORS[role], cache[key]))
        tags[item.name] = {"role": role, "source": item.key, "center_mm": shape_center(shape),
                           "label_point_mm": label_point(scene, item)}
    if SERVICE_DOCUMENT in state:
        types, objects = scene.reader.xml(SERVICE_DOCUMENT)
        for name, type_id in types.items():
            if type_id != "Part::Box" or name == "ASSUMED_SupportIsolateur":
                continue
            prop = objects[name].get("Statut")
            if prop is None or prop.find("String").get("value") != "service":
                continue
            shape = scene.reader.shape(SERVICE_DOCUMENT, name)
            if not any(is_inside(shape, crop) for crop in (BAY, DIAGNOSTIC, CAMERA)):
                continue
            # The boxes carry the same native global reference as the two branches.
            # Their siblings can overlap by construction. Draw the range as overlays.
            vertices, faces = shape.tessellate(.3)
            meshes.append((name, "fixation", COLORS["service"], COLORS["service"],
                           np.asarray([tuple(v) for v in vertices])[np.asarray(faces)]))
            tags[name] = {"role": "service", "source": f"{SERVICE_DOCUMENT}#{name}",
                          "center_mm": shape_center(shape)}
    return meshes, tags, empty


def figure(name, reference, candidate, layers, label, specs, title, message):
    fig, axes = plt.subplots(len(specs), 2, squeeze=False, figsize=(12.8, 4.1*len(specs)), facecolor=BACKGROUND)
    fig.subplots_adjust(left=.055, right=.945, top=.815, bottom=.105, wspace=.08, hspace=.31)
    heading(fig, title, "Cartographe sans dock · projection des surfaces natives sauvegardées")
    for row, (view_label, angles, crop, emphasized) in zip(axes, specs):
        view = projection(*angles)
        for ax, model, side in zip(row, (reference, candidate), ("Témoin", label)):
            set_panel(ax, f"{view_label} · {side}")
            selected = None
            if emphasized:
                selected = set(emphasized) | {name for name, v in model[1].items() if v["role"] in {"assumed", "service"}}
            meshes = model[0] if emphasized else [mesh for mesh in model[0] if model[1][mesh[0]]["role"] != "service"]
            render(ax, meshes, view, crop=crop, highlighted=selected)
            dimension_scale(ax, 25 if crop == DIAGNOSTIC else 50)
            if emphasized and side == label:
                for index, key in enumerate(emphasized):
                    tag = model[1].get(key)
                    if not tag:
                        continue
                    point = tag["label_point_mm"]
                    if all(lo <= v <= hi for v, (lo, hi) in zip(point, crop)):
                        left = index % 2 == 0
                        label_x = .025 if left else .975
                        label_y = .95 - .1 * (index // 2)
                        loc = (np.asarray(point) @ view)[:2]
                        ax.annotate(key, loc, xytext=(label_x, label_y), textcoords="axes fraction",
                                    ha="left" if left else "right", va="top", fontsize=8,
                                    color=NAVY, fontweight="semibold", zorder=5,
                                    bbox={"fc": "#ffffff", "ec": "#e3eaf2", "pad": 2},
                                    arrowprops={"arrowstyle": "-", "color": NAVY, "lw": .7})
    fig.legend(handles=[Patch(color=COLORS[key], label=caption) for key, caption in layers],
               loc="lower center", bbox_to_anchor=(.5, .059), ncol=4,
               frameon=False, fontsize=8)
    footer(fig, message)
    save(fig, name)


def run(source, target, output, label):
    snapshots = [capture(source), capture(target)]
    native_service = target / SERVICE_DOCUMENT
    auxiliary = {SERVICE_DOCUMENT: guard.sha256(native_service)} if native_service.is_file() else {}
    scenes = [SavedScene(source), SavedScene(target)]
    changed = {item.name for item in scenes[1].items.values()
               if snapshots[0].get(item.row["source"]) != snapshots[1].get(item.row["source"])
               or item.key not in scenes[0].items
               or tuple(item.pose.toMatrix().A) != tuple(scenes[0].items[item.key].pose.toMatrix().A)}
    cache = {}
    witness = mesh_scene(scenes[0], set(), snapshots[0], cache)
    trial = mesh_scene(scenes[1], changed, snapshots[1] | auxiliary, cache)
    output.mkdir(parents=True, exist_ok=False)
    layers = [("câble", "Faisceau"), ("interface", "Interface ou maintien"),
              ("modifié", "Objet modifié"), ("assumed", "Enveloppe supposée"),
              ("service", "Volume de service supposé")]
    files = {
        "01_dessus_dessous_profil.png": (
            [("Dessus", (-90,90), BAY, ()), ("Dessous", (-90,-90), BAY, ()), ("Profil sud", (-90,0), BAY, ())],
            "Implantation de la baie",
            "Échelle commune par paire. Structure en transparence."),
        "02_service_et_camera.png": (
            [("Baie transparente", (-65,38), BAY, ()),
             ("Service ouest", (157,22), DIAGNOSTIC, ("UART_isole", "F40", "F41", "PDB", "PM08")),
             ("Interfaces caméra et CAN", (-73,38), CAMERA, ("F16", "F_M8", "F31", "F35", "RetenueP85F25"))],
            "Faisceaux et accès de service",
            "Les gabarits dessinés sont des hypothèses. Une projection ne mesure aucun jeu."),
    }
    for name, (specs, title, note) in files.items():
        figure(output/name, witness, trial, layers, label, specs, title, note)
        print(name, flush=True)
    if snapshots != [capture(source), capture(target)]:
        raise RuntimeError("Empreinte modifiée pendant l'export")
    if auxiliary and auxiliary[SERVICE_DOCUMENT] != guard.sha256(native_service):
        raise RuntimeError("Enveloppes modifiées pendant l'export")
    write(output / "vues.json", {"freecad": App.Version(), "baseline": source.as_posix(),
                                  "candidate": target.as_posix(), "label": label,
                                  "method": "Tessellation des BRep sauvegardés. Vue orthographique, transparence de contexte.",
                                  "closures_sha256": snapshots, "service_auxiliary_sha256": auxiliary,
                                  "objects_by_role": [witness[1], trial[1]],
                                  "unrendered_empty": [witness[2], trial[2]],
                                  "images_sha256": {name: guard.sha256(output / name) for name in files}})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("baseline", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("label")
    args = parser.parse_args()
    run(args.baseline.resolve(strict=True), args.candidate.resolve(strict=True), args.output, args.label)
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0)
