"""Criblage de réservations d'interfaces GO3B sur une copie isolée."""

import argparse
import json
import os
from pathlib import Path
import sys

from electromechanical_engine.freecad import guard
from electromechanical_engine.freecad_worker import App, Part, cables_environment, geometry
from electromechanical_engine.qualification.native_replay import ENTRY, MEC, collisions, read, write

sys.path[:0] = [str(MEC / "cartographe_refonte_systeme/verification"),
               str(MEC / "cartographe/verification/refonte_faisceaux")]
from adapter_implantation import BoundedPairs, Scene, distance_bound


class RegisteredScene(Scene):
    def group_matches(self, path, rows):
        types, _ = self.reader.xml(path)
        native = {name for name, kind in types.items() if kind == "App::Link"}
        registered = {row["occurrence"] for row in rows}
        if registered != native or len(registered) != len(rows):
            raise RuntimeError(f"Occurrences non réconciliées : {path}")


def box(lo, hi):
    return Part.makeBox(*(b - a for a, b in zip(lo, hi)), App.Vector(*lo))


def bounds(shape):
    b = shape.BoundBox
    return [b.XMin, b.YMin, b.ZMin, b.XMax, b.YMax, b.ZMax]


def capture(root):
    return {p.relative_to(root).as_posix(): guard.sha256(p) for p in guard.dependencies(root, [ENTRY])}


def assessment(shape, obstacles, worker):
    report = collisions(shape, obstacles, distance_bound, worker.measure)
    report.update({"bbox_mm": bounds(shape), "volume_mm3": shape.Volume})
    return report


def diagnostics(root, output, use_routes):
    receipt = read(root / "experiment.json")
    expected = receipt["inputs_sha256"]
    snapshot = capture(root)
    if snapshot != {name: expected[name] for name in snapshot}:
        raise RuntimeError("La copie criblée ne correspond pas au gel")
    model = RegisteredScene(root)
    probes = []
    for length in (3, 5, 15):
        for lateral_shift in (-6, 0, 6):
            y = 18.5 + lateral_shift
            probes.append((f"TTL-l{length}-y{lateral_shift:+}",
                           box((12, y-6, 46.5), (12+length, y+6, 54.5))))
    x, y, z = -68.8, -28.575, 51
    for length in (5, 15, 50):
        probes.append((f"USB-B-droit-l{length}", box((x-length, y-5.9, z-5.1), (x, y+5.9, z+5.1))))
        for direction, departure in {"Sud": ((x-length,y-20,z-5.1),(x,y+5.9,z+5.1)),
                                     "Nord": ((x-length,y-5.9,z-5.1),(x,y+20,z+5.1)),
                                     "Bas": ((x-length,y-5.9,z-20),(x,y+5.9,z+5.1)),
                                     "Haut": ((x-length,y-5.9,z-5.1),(x,y+5.9,z+20))}.items():
            probes.append((f"USB-B-ASSUMED-{direction}-l{length}", box(*departure)))
    obstacles = {f"{item.name}/{index}/{key}": solid
                 for key, item in model.items.items()
                 if item.name not in {"F40", "F41", "UART_isole"}
                 for index, solid in enumerate(item.shape.Solids, 1)}
    worker = BoundedPairs()
    proof = {"scope": "Cartographe CAO gel actif, criblage paramétrique, hors alimentation",
             "pid": os.getpid(), "cabling_reference": "GO3A_SYSTEM_MODEL.json W40/W41",
             "sources_reference": ["docs/verification/v21_go3a_evidence_gaps.json",
                                   "docs/verification/cartographe_action3_f41.json"],
             "freecad": App.Version(), "occt": Part.OCC_VERSION,
             "exclusions": ["UART_isole : équipement portant les interfaces ; contrôle interne à faire",
                            "F40/F41 : parcours à reconstituer, contrôler ensuite simultanément"],
             "obstacles": len(obstacles), "clearance_floor": None,
             "status": "INCONCLUSIVE",
             "parameters": {"units": "mm", "usb_reach": [5, 15, 50], "ttl_reach": [3, 5, 15],
                            "ttl_y_shift": [-6, 0, 6], "assumed_elbow_departure_reach": 20,
                            "usb_ferrite_geometry": None},
             "scope_limit": "Volumes ASSUMED, aucune qualification d'interface ou de retrait; le balayage n'est pas une cinématique physique.",
             "probes": {}, "routes": {}}
    try:
        for key, shape in probes:
            proof["probes"][key] = assessment(shape, obstacles, worker)
        if use_routes:
            proof["cables"] = cables_environment(False)
            cable_path = root / "pieces/commerce/W_F41_Prototype.FCStd"
            doc = App.openDocument(str(cable_path))
            cable = doc.getObject("Cable")
            path = cable.Base
            placements = path.Placement.inverse()
            fixed = [7, -42, 131.5]
            for start, sign in (([-83.8, -48.575, 51], -1), ([-83.8, -8.575, 51], 1)):
                far_y = -112 if sign < 0 else 100
                for control, z0 in (("edge", 51), ("below", 78)):
                    for west in (-112, -130, -145):
                        prefix = [start, [start[0], far_y, 51]]
                        if z0 != 51:
                            prefix.append([start[0], far_y, z0])
                        rows = prefix + [[west, far_y, z0], [west, far_y, 131.5], [west,-106,131.5],
                                         [7,-106,131.5], fixed]
                        if far_y == -112:
                            rows = prefix + [[west,far_y,z0],[west,far_y,131.5],[7,far_y,131.5],fixed]
                        key = f"{sign:+.0f}-{control}-{west}"
                        path.Points = [placements.multVec(App.Vector(*row)) for row in rows]
                        result = geometry.rebuild_cable_in_isolated_document(doc, cable)
                        proof["routes"][key] = {"points_mm": rows, "fresh": result}
                        if result["status"] == "pass":
                            proof["routes"][key].update(assessment(cable.Shape, obstacles, worker))
                            proof["routes"][key]["length_mm"] = path.Shape.Length
                        print(key, result["status"], flush=True)
            App.closeDocument(doc.Name)
    finally:
        worker.close()
        proof["copy_and_source_integrity"] = {"file_count": len(snapshot),
                                               "copy_unchanged": snapshot == capture(root),
                                               **guard.verify_sources(receipt)}
        write(output, proof)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("copy", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--routes", action="store_true")
    args = parser.parse_args()
    diagnostics(args.copy.resolve(strict=True), args.output, args.routes)
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0)
