import os
import sys

from preparation import ROOT, RUN, read, write, require
from electromechanical_engine.freecad import guard
from electromechanical_engine.freecad_worker import App, cables_environment
from electromechanical_engine.qualification.native_replay import axes, MEC, ENTRY

sys.path[:0] = [str(MEC / "cartographe/verification/refonte_faisceaux"), str(MEC / "cartographe/verification")]
from controles_geometrie import Scene, bounds


def snapshot(case):
    target = RUN / case
    cad = target / "cad"
    receipt = read(cad / "experiment.json")
    before = {p.relative_to(cad).as_posix(): guard.sha256(p) for p in guard.dependencies(cad, [ENTRY])}
    if case == "baseline":
        require(all(before[name] == digest for name, digest in receipt["inputs_sha256"].items() if name in before),
                "Témoin modifié avant lecture.")
    version = cables_environment(False)
    require(version["version"] == "0.3.7" and version["freecad"][:3] == ["1", "1", "3"], "Version différente.")
    scene = Scene(cad)
    zones = read(ROOT / "docs/verification/go3a/GO3A_SYSTEM_MODEL.json")["zones_comparaison_mm"]
    metrics = axes(scene, zones)
    geometry = {}
    for name, item in sorted(scene.cables.items()):
        wire = scene.wires[name]
        vb = [list(v.Point) for v in wire.Vertexes if sum(v.isSame(p) for e in wire.Edges for p in e.Vertexes) == 1]
        geometry[name] = {"box_mm": bounds(item.shape), "solid_valid": item.shape.isValid(),
                          "solids": len(item.shape.Solids), "volume_mm3": item.shape.Volume,
                          "ends_mm": vb, "shapefile": item.row["source"],
                          "occurrence": item.key, "placement_matrix": list(item.pose.toMatrix().A)}
    equipment = {item.name: {"box_mm": bounds(item.shape), "placement_matrix": list(item.pose.toMatrix().A),
                             "source": item.row["source"], "occurrence": item.key}
                 for item in scene.items.values() if item.name in {
                     "UART_isole", "PDB", "PM08", "P73_Guide", "P75_Cadre", "Holybro6XOrin", "PlateauEnergie", "P66"}}
    routes = read(cad / "verification/routes_prototype.json")["routes"]
    raw = {row["id"]: {k: row.get(k) for k in ("points_mm", "rayon_demande_mm", "diametre_exterieur_mm",
             "objet_parcours", "objet_cable", "retentions", "supports")} for row in routes}
    require(len(geometry) == 53 and set(geometry) == set(raw), "Inventaire incohérent.")
    after = {p.relative_to(cad).as_posix(): guard.sha256(p) for p in guard.dependencies(cad, [ENTRY])}
    require(before == after, "Lecture a modifié un natif.")
    result = {"case": case, "pid": os.getpid(), "version": version, "native_sha256": before,
              "zones_mm": zones, "metrics": metrics, "axis_geometry": geometry, "axis_registry": raw,
              "equipment": equipment, "source_integrity": guard.verify_sources(receipt)}
    write(target / "snapshot.json", result)
    print(case, metrics["count"], metrics["axis_sum_mm"], metrics["height_max_mm"], flush=True)


if __name__ == "__main__":
    snapshot(sys.argv[1])
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0)
