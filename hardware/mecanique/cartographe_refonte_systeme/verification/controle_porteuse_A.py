"""Contrôle ciblé des deux nouveaux axes au droit de la porteuse et entre eux."""
import os
import sys

from adapter_implantation import (
    App, COPY, HERE, PAIRS, Scene, boot, distance_bound, load, make_native_cable,
    report_pairs, sha, write,
)


def board_pairs(route, path, shape, board):
    boxes = []
    for edge in path.Shape.Edges:
        box = edge.BoundBox
        box.enlarge(route["diametre_mm"] / 2 + 0.01)
        boxes.append(box)
    solids = board.shape.Solids
    selected = [(i, solid) for i, solid in enumerate(solids)
                if any(distance_bound(box, solid.BoundBox) < 1e-7 for box in boxes)]
    return {"solids_total": len(solids), "pairs": [
        {"solid_index": index, **PAIRS.measure(shape, solid, 0.0)} for index, solid in selected
    ]}


def main():
    boot()
    scene = Scene(COPY)
    spec = load(HERE / "implantation.json")
    board = next(item for item in scene.items.values() if item.name == "Holybro6XOrin")
    candidates = {"F25": spec["security"][1]["paths"][0], "F31": spec["routing"]["F31"][0]}
    results = {}
    shapes = {}
    for key, candidate in candidates.items():
        route = scene.routes[key]
        results[key] = {}
        for mode, points in (("reference", route["points_mm"]), ("candidate", candidate)):
            doc = App.newDocument("Ciblage")
            cable, path = make_native_cable(doc, None, key, points,
                                           route["diametre_mm"], route["rayon_courbure_mm"])
            shape = cable.Shape.copy()
            results[key][mode] = {"points_mm": points, **board_pairs(route, path, shape, board)}
            if mode == "candidate":
                shapes[key] = shape
            App.closeDocument(doc.Name)
            print(key, mode, results[key][mode]["pairs"], flush=True)
    new_pair = report_pairs(shapes["F25"], {"F31": shapes["F31"]}, nearby=1)
    write(HERE / "controle_porteuse_A.json", {"complete": True, "source_sha256": scene.hashes(),
                                              "script_sha256": sha(__file__), "results": results,
                                              "f25_f31": new_pair,
                                              "method": "AABB arêtes élargies du rayon extérieur, intersections BRep par solide retenu."})


if __name__ == "__main__":
    try:
        main()
    finally:
        PAIRS.close()
    sys.stdout.flush()
    os._exit(0)
