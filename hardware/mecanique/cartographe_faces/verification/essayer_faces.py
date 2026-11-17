"""Criblage de variantes par faces sur les BRep FreeCAD sauvegardés."""
import os
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
COPY = HERE.parent / "Candidat"
PREVIOUS = HERE.parents[1] / "cartographe_refonte_systeme/verification"
sys.path.insert(0, str(PREVIOUS))
from adapter_implantation import (
    App, PAIRS, Scene, V, boot, bounds, cable_geometry, distance_bound,
    load, make_native_cable, require, sha, write,
)
from comparer_A import clipped_axis

PARAMS = HERE / "parametres_essais.json"


def edge_boxes(wire, diameter, clearance):
    boxes = []
    for edge in wire.Edges:
        box = edge.BoundBox
        box.enlarge(diameter / 2 + clearance)
        boxes.append(box)
    return boxes


def near(boxes, bbox):
    return any(distance_bound(box, bbox) <= 1e-7 for box in boxes)


class Checks:
    def __init__(self, scene):
        self.items = {item.name: (item.shape, item.shape.BoundBox) for item in scene.items.values()}
        self.board = [(solid, solid.BoundBox) for solid in self.items["Holybro6XOrin"][0].Solids]

    def pairs(self, cable, wire, diameter, skip):
        output = {"tested":0, "collisions":[], "unknowns":[], "clearances":[]}
        boxes = edge_boxes(wire, diameter, 0.65)
        target = cable.BoundBox
        for name, (shape, bbox) in self.items.items():
            if name in skip or not near(boxes, bbox):
                continue
            parts = self.board if name == "Holybro6XOrin" else [(shape, bbox)]
            for i, (part, b) in enumerate(parts):
                if not near(boxes, b):
                    continue
                row = PAIRS.measure(cable, part, distance_bound(target, b))
                output["tested"] += 1
                key = ("unknowns" if "error" in row else
                       "collisions" if row["volume_mm3"] > 1e-4 else "clearances")
                if key != "clearances" or row["gap_mm"] <= 1.0:
                    output[key].append({"name":name,"subsolid_index":i,**row})
        return output


def metrics(shape, wire, zones):
    return {"length_mm":wire.Length,"height_mm":shape.BoundBox.ZMax,
            "length_by_zone_mm":{name:clipped_axis(wire, *xyz) for name,xyz in zones.items()}}


def main():
    spec = load(PARAMS)
    scene = Scene(COPY)
    checks = Checks(scene)
    environment = boot()
    output = {"complete":False, "source_sha256":scene.hashes(), "environment":environment,
              "script_sha256":sha(__file__), "parameters_sha256":sha(PARAMS), "cases":[]}
    for key, rows in spec["routes"].items():
        route = scene.routes[key]
        baseline = metrics(scene.cables[key].shape, scene.wires[key], spec["zones"])
        for candidate in rows:
            result = {"route":key, "baseline":baseline, **candidate}
            output["cases"].append(result)
            doc = App.newDocument("EssaiFaces")
            try:
                cable, path = make_native_cable(doc, None, key, candidate["points"],
                    route["diametre_mm"], route["rayon_courbure_mm"])
                result["geometry"] = cable_geometry(cable)
                result["metrics"] = metrics(cable.Shape, path.Shape, spec["zones"])
                result["checks"] = checks.pairs(cable.Shape,path.Shape,route["diametre_mm"], {key})
            except Exception as error:
                result["error"] = str(error)
            finally:
                App.closeDocument(doc.Name)
            if "checks" in result:
                print(key,candidate["id"],round(result["metrics"]["length_mm"],1),
                      [r["name"] for r in result["checks"]["collisions"]],
                      [r["name"] for r in result["checks"]["unknowns"]],flush=True)
            else:
                print(key,candidate["id"],result["error"],flush=True)
            write(HERE / "essais_faces.json", output)
    require(scene.hashes() == output["source_sha256"], "Copie altérée par le criblage")
    output["complete"] = True
    write(HERE / "essais_faces.json", output)


if __name__ == "__main__":
    try:
        main()
    finally:
        PAIRS.close()
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0)
