"""Relire les trois interférences historiques et documenter leur localisation."""

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import sys
from time import perf_counter
from uuid import uuid4


REPO = Path(__file__).resolve().parents[3]


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def artifact(path):
    with path.open("rb") as stream:
        sha256 = hashlib.file_digest(stream, "sha256").hexdigest()
    return {"path": path.relative_to(REPO).as_posix(), "sha256": sha256}


def pinned(root, descriptor):
    path = root / descriptor["path"]
    if artifact(path)["sha256"] != descriptor["sha256"]:
        raise ValueError(f"Empreinte de la preuve divergente : {path}")
    return path


def render(output, pair, shape_a, shape_b, overlap, bounds, app, part):
    from matplotlib import pyplot as plt
    from matplotlib.patches import Patch
    from matplotlib.ticker import MaxNLocator
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    import numpy as np

    low, high = map(np.array, bounds)
    center = (low + high) / 2
    radius = float(max(12, max(high - low) / 2 + 7))
    corner = center - radius
    window = part.makeBox(2 * radius, 2 * radius, 2 * radius, app.Vector(*corner))
    colors = ("#3b81c5", "#ddb182", "#d5293e")
    fig = plt.figure(figsize=(10, 5.8), facecolor="white", layout="constrained")
    ax = fig.add_subplot(projection="3d", computed_zorder=False)
    for order, (shape, color, opacity) in enumerate(zip(
        (shape_a.common(window), shape_b.common(window), overlap), colors, (0.38, 0.38, 1.0)
    )):
        vertices, facets = shape.tessellate(0.08)
        mesh = np.array([tuple(vertex) for vertex in vertices])[facets]
        collection = Poly3DCollection(mesh, facecolors=color, alpha=opacity,
                                      linewidths=0, shade=True, zorder=order + 3)
        ax.add_collection3d(collection)
    for set_limits, label, c in zip((ax.set_xlim, ax.set_ylim, ax.set_zlim), ("X", "Y", "Z"), center):
        set_limits(c - radius, c + radius)
        getattr(ax, f"set_{label.lower()}label")(f"{label} (mm)")
    ax.set_box_aspect((1, 1, 1))
    ax.set_proj_type("ortho")
    ax.view_init(elev=25, azim=-58)
    for axis in (ax.xaxis, ax.yaxis, ax.zaxis):
        axis.set_major_locator(MaxNLocator(4))
        axis.set_tick_params(labelsize=8)
    ax.legend(handles=[Patch(facecolor=color, label=label) for color, label in
                       zip(colors, (*pair, "Intersection BRep"))], loc="upper left", frameon=False)
    fig.savefig(output, dpi=125)
    plt.close(fig)
    return {"projection": "Axonométrie orthographique dans le repère d’assemblage",
            "deviation_tessellation_mm": 0.08, "bounds_mm": [(center - radius).tolist(),
                                                            (center + radius).tolist()]}


def compare(prior, observed):
    for key in ("status", "authorized_relation", "failures", "unknowns"):
        if prior[key] != observed[key]:
            raise ValueError(f"Conclusion de la mesure différente : {key}")
    for key in ("intersection_mm3", "clearance_mm"):
        if not math.isclose(prior[key], observed[key], rel_tol=1e-10, abs_tol=1e-10):
            raise ValueError(f"Mesure différente : {key}")


def main(frozen, output):
    sys.path.insert(0, str(frozen))
    import matplotlib
    matplotlib.use("Agg")
    from electromechanical_engine import freecad_worker as native
    from electromechanical_engine import xlink_native as xlink

    authority = frozen / "docs/verification/v21_fix_b_coverage.json"
    history = read(authority)
    old = history["attempts"][-1]
    campaign_path = pinned(frozen, old["proof"]["campaign"])
    inventory_path = pinned(frozen, old["proof"]["inventory"])
    checkpoint_path = pinned(frozen, old["checkpoint"])
    pinned(frozen, history["validator"])
    pinned(frozen, history["worker"])
    campaign, inventory, checkpoint = map(read, (campaign_path, inventory_path, checkpoint_path))
    validator_sources = [artifact(pinned(frozen, {"path": name, "sha256": sha256}))
                         for name, sha256 in campaign["pins"].items() if "/" in name]
    configuration_path = pinned(frozen, {"path": "validation_engine/fixtures/xlink_cartographe.json",
                                         "sha256": campaign["pins"]["configuration"]})
    configuration = read(configuration_path)
    criteria = configuration["criteria"]
    requirements_path = pinned(frozen, {"path": criteria["source"], "sha256": campaign["pins"]["criteria"]})
    historical_ids = [row["task"]["id"] for row in campaign["geometry"]["checks"]
                      if row["task"]["kind"] == "pair" and row["status"] == "FAIL"
                      and "forbidden_interference" in row["native_evidence"]["observation"]["failures"]]
    if len(historical_ids) != 3 or len(set(historical_ids)) != 3:
        raise ValueError("Les trois interférences historiques ne sont pas réconciliées.")
    if criteria["contacts"] or criteria != campaign["criteria"]:
        raise ValueError("Référentiel de contacts ou critères différents de la campagne B.")

    copy = campaign_path.parent.parent / "copy"
    receipt = read(copy / "experiment.json")
    t0 = perf_counter()
    doc, native_proof = xlink.reopen(copy, receipt, False)
    open_seconds = perf_counter() - t0
    t0 = perf_counter()
    records, shapes, _ = xlink.collect(doc, copy, native_proof["before_sha256"])
    current_identity = xlink.measurement_identity(records)
    inventory_seconds = perf_counter() - t0
    if (not native_proof["recompute_ok"] or not native_proof["inventory_complete"]
            or native_proof["environment"] != inventory["environment"]
            or native_proof["before_sha256"] != campaign["closure"]["saved_sha256"]
            or receipt["inputs_sha256"] != campaign["closure"]["source_sha256"]
            or current_identity != inventory["measurement_identity_sha256"]
            or checkpoint["measurement_key"] != campaign["closure"]["cache_key"]):
        raise ValueError("La réouverture ne reproduit pas l’environnement, la fermeture ou les occurrences verrouillés.")

    results = []
    for ident in historical_ids:
        t0 = perf_counter()
        baseline = checkpoint["observations"][ident]
        task = baseline["task"]
        a, b = task["a"], task["b"]
        print(f"Contrôle {ident} · {a} · {b}", flush=True)
        shape_a, shape_b = shapes[a], shapes[b]
        fresh = xlink.measure([task], records, shapes, {}, criteria, checkpoint["measurement_key"])[0]
        compare(baseline["observation"], fresh["observation"])
        elapsed = perf_counter() - t0
        overlap = shape_a.common(shape_b)
        if overlap.isNull() or not overlap.isValid() or not overlap.Solids:
            raise ValueError(f"Intersection BRep inutilisable pour la localisation : {ident}")
        bounds = native.bounds(overlap)
        pair = [records[a]["label"], records[b]["label"]]
        view = output / f"collision_{pair[0]}_{pair[1]}.png"
        rendering = render(view, pair, shape_a, shape_b, overlap, bounds, native.App, native.Part)
        results.append({
            "task": task,
            "status": "FAIL",
            "classification": "COLLISION_INTERDITE",
            "justification": "Intersection de volume strictement positif entre deux solides de gaine. "
                             "Aucune relation d’inclusion ni de contact autorisée dans les critères gelés.",
            "occurrences": {side: {"xlink_occurrence": key, **records[key]} for side, key in (("a", a), ("b", b))},
            "historical_observation": baseline,
            "reopened_observation": fresh,
            "replay_matches": True,
            "duration_seconds": elapsed,
            "intersection_bounds_mm": bounds,
            "intersection_solid_count": len(overlap.Solids),
            "intersection_components": [{"center_of_mass_mm": list(solid.CenterOfMass),
                                         "bounds_mm": native.bounds(solid), "volume_mm3": solid.Volume}
                                        for solid in overlap.Solids],
            "visualization": {**artifact(view), **rendering},
        })

    native.App.closeDocument(doc.Name)
    if xlink.check_files(copy, receipt) != native_proof["after_sha256"]:
        raise ValueError("Les fichiers ont changé pendant la caractérisation.")
    xlink.publish(output / "interferences.json", {
        "schema": "drone-agricole.v21.b2.interferences.v1",
        "scope": "Les trois interférences issues du criblage de la mission B sur la fermeture nominale sauvegardée.",
        "status": "PASS",
        "prototype_status_for_these_pairs": "FAIL",
        "commands": [[sys.executable, "-B", str(Path(__file__).relative_to(REPO)),
                     "--frozen", frozen.relative_to(REPO).as_posix(),
                     "--output", output.relative_to(REPO).as_posix()]],
        "replay_script": artifact(Path(__file__)),
        "authority": artifact(authority),
        "frozen_configuration": artifact(configuration_path),
        "frozen_requirements": artifact(requirements_path),
        "historical_campaign": artifact(campaign_path),
        "historical_inventory": artifact(inventory_path),
        "historical_checkpoint": artifact(checkpoint_path),
        "validator_sources": validator_sources,
        "criteria": criteria,
        "method": {"volume": "TopoShape.common(A, B).Volume sur les deux solides relus via les occurrences XLink.",
                   "distance": "Distance minimale des formes via TopoShape.distToShape(A, B).",
                   "occt_boolean": "Tolérance native OCCT, aucun paramètre fuzzy ajouté.",
                   "matrix": "Matrice homogène 4×4 en ordre ligne, repère de la racine, translations en mm.",
                   "replay_comparison": {"relative_tolerance": 1e-10, "absolute_tolerance": 1e-10},
                   "render": "Cadrage par boîte locale, tessellation des portions des deux solides et du résultat d’intersection."},
        "independent_reopening": {"pid": os.getpid(), "worker_id": uuid4().hex,
                                  "native_files": len(native_proof["documents"]),
                                  "broken_links": native_proof["broken_links"], "invalid_objects": native_proof["invalid_objects"],
                                  "environment": native_proof["environment"], "open_recompute_seconds": open_seconds,
                                  "inventory_seconds": inventory_seconds, "measurement_identity_sha256": current_identity,
                                  "unchanged": True},
        "results": results,
    })
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frozen", type=Path, default=Path(".runtime/fix-b"))
    parser.add_argument("--output", type=Path, default=Path("docs/verification/v21_b2"))
    options = parser.parse_args()
    output_dir = (REPO / options.output).resolve()
    output_dir.relative_to(REPO)
    output_dir.mkdir(parents=True, exist_ok=True)
    main((REPO / options.frozen).resolve(), output_dir)
