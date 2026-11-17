"""Criblage de réorientations et de leurs incidences dans le repère de A."""
import math
import os
import sys

from essayer_faces import App, COPY, HERE, PAIRS, Scene, V, bounds, load, require, sha, write
from adapter_implantation import report_pairs

CA01_PORTS = {
    "F08_AVAL": -1, "F09": 0, "AIRY_PWR": -1, "AIRY_SYNC": -1,
    "F12": 0, "F24A": 0, "F24B": 0, "F24C": 0, "F36": -1,
    "F33": 0, "F35": 0, "F13A": 0, "F13B": 0, "F_M8": -1,
}


def rotated(item, angle, center):
    rotation = App.Rotation(V(0,0,1), angle)
    pose = App.Placement(center - rotation.multVec(center), rotation)
    shape = item.shape.copy()
    shape.Placement = pose.multiply(shape.Placement)
    return shape, pose


def main():
    scene = Scene(COPY)
    items = {r.name:r for r in scene.items.values()}
    original = scene.hashes()
    candidate, placement = rotated(items["CA01"], 180, V(0,0,98))
    other = {name:obj.shape for name,obj in items.items() if name != "CA01" and name not in CA01_PORTS}
    routes = []
    for key, index in CA01_PORTS.items():
        record = scene.routes[key]
        a, b = [V(*record["points_mm"][i]) for i in (index, -1 if index == 0 else 0)]
        moved = placement.multVec(a)
        routes.append({"route":key,"former_terminal":list(a),"projected_terminal":list(moved),
                       "former_chord_mm":(a-b).Length,"projected_chord_mm":(moved-b).Length})
    results = {
      "complete":True, "source_sha256":original,"script_sha256":sha(__file__),
      "CA01_180":{"axis":"Z","center_mm":[0,0,98],"fit":report_pairs(candidate, other, 0.6),
                  "bbox_mm":bounds(candidate),"chords":routes,
                  "delta_chords_mm":sum(r["projected_chord_mm"]-r["former_chord_mm"] for r in routes),
                  "limit":"Positions nominales des anciennes réservations. Les routes affectées ne participent qu’au calcul de cordes et sont exclues du contrôle du corps, puisqu’elles seraient reconstruites. Vérifier porteuse, radio, alimentation, refroidissement et prise de vis."}
    }
    require(scene.hashes()==original,"Copie modifiée pendant le criblage")
    write(HERE / "essais_reimplantation.json", results)


if __name__ == "__main__":
    try:
        main()
    finally:
        PAIRS.close()
    sys.stdout.flush()
    os._exit(0)
