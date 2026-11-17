"""Relevé indépendant des repères et de l'appui d'un isolateur sauvegardé GO3B."""

import argparse
import os
from pathlib import Path
import sys

from electromechanical_engine.freecad import guard
from electromechanical_engine.freecad_worker import App
from electromechanical_engine.qualification.native_replay import ENTRY, MEC, write

sys.path[:0] = [str(MEC / "cartographe/verification/refonte_faisceaux"),
               str(MEC / "cartographe/verification")]
from controles_geometrie import Scene


ISOLATOR = "pieces/commerce/EQ_Waveshare15817_UART_Isole.FCStd"
FACE_OBJECTS = {"TTL": ("ORCH_BornierTTL", "XMax"), "USB": ("ORCH_USB_B", "XMin")}
SUPPORT_NAME = "ASSUMED_ServiceGO3B"


def bnd(shape):
    b = shape.BoundBox
    return [b.XMin, b.YMin, b.ZMin, b.XMax, b.YMax, b.ZMax]


def digest(cad):
    return {p.relative_to(cad).as_posix(): guard.sha256(p) for p in guard.dependencies(cad, [ENTRY])}


def observe_port(scene, isolator, feature, boundary, linked_wire):
    local = scene.reader.shape(ISOLATOR, feature).BoundBox
    source = App.Vector(getattr(local, boundary), local.Center.y, local.Center.z)
    world = isolator.pose.multiply(scene.reader.placement(ISOLATOR, isolator.row["objet_source"]).inverse()).multVec(source)
    ends = [v.Point for v in linked_wire.Vertexes
            if sum(v.isSame(w) for e in linked_wire.Edges for w in e.Vertexes) == 1]
    if len(ends) != 2:
        raise RuntimeError("Extrémités d'axe non uniques")
    terminal = min(ends, key=lambda p: (p-world).Length)
    incident = next(e for e in linked_wire.Edges if any((v.Point-terminal).Length < 1e-7 for v in e.Vertexes))
    tangent = incident.tangentAt(incident.FirstParameter if (incident.valueAt(incident.FirstParameter)-terminal).Length < 1e-7
                                 else incident.LastParameter)
    return {"cae_feature": feature, "face_bound": boundary, "face_local_mm": list(source),
            "face_global_mm": list(world), "nearest_axis_end_mm": list(terminal), "axis_endpoints_mm": [list(p) for p in ends],
            "nearest_axis_end_gap_mm": (terminal-world).Length, "axis_tangent_unsigned": list(tangent),
            "status": "PASS" if (terminal-world).Length < 1e-7 else "INCONCLUSIVE",
            "scope": "Correspondance géométrique au proxy de face uniquement. Contacts et longueur d'embout INCONCLUSIVE."}


def measure(cad, output):
    before = digest(cad)
    scene = Scene(cad)
    by_name = {item.name: item for item in scene.items.values()}
    isolator = by_name["UART_isole"]
    ports = {key: observe_port(scene, isolator, feature, boundary, scene.wires[wire])
             for (key, (feature, boundary)), wire in zip(FACE_OBJECTS.items(), ("F40", "F41"))}
    supports = {}
    if SUPPORT_NAME in by_name:
        support = by_name[SUPPORT_NAME]
        pairs = {}
        for key in ("UART_isole", "Interface", "P72_Guide", "P73_Guide", "P75_Cadre", "Isolation"):
            obj = by_name[key]
            gap = support.shape.distToShape(obj.shape)[0]
            common = support.shape.common(obj.shape) if gap < 1e-7 else None
            volume = common.Volume if common is not None else 0
            pairs[key] = {"occurrence": obj.key, "gap_mm": gap,
                          "overlap_mm3": volume,
                          "bbox_mm": bnd(obj.shape)}
        supports = {"occurrence": support.key, "pairs": pairs, "volume_mm3": support.shape.Volume,
                    "bbox_mm": bnd(support.shape), "mass_g": None,
                    "status": "FAIL" if pairs["UART_isole"]["gap_mm"] > 1e-7
                    or any(p["overlap_mm3"] > 1e-4 for p in pairs.values()) else "INCONCLUSIVE",
                    "meaning": "Un appui exige contact avec le module et fixation identifiée. L'ancrage au porteur et la tenue restent ouverts."}
    after = digest(cad)
    if before != after:
        raise RuntimeError("Fermeture XLink mutée pendant la lecture")
    write(output, {"scope": cad.as_posix(), "version": App.Version(), "native_sha256_unchanged": after,
                   "isolator": {"bbox_mm": bnd(isolator.shape), "placement": list(isolator.pose.toMatrix().A)},
                   "ports": ports, "support": supports})
    print({"ports": {k: v["nearest_axis_end_gap_mm"] for k, v in ports.items()},
           "support": supports.get("status"), "native_files": len(after)}, flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("copy", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    measure(args.copy.resolve(strict=True), args.output)
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0)
