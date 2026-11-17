"""Rejoue les BRep historiques dans des copies privées, en processus FreeCAD neufs.

python -B -m electromechanical_engine.qualification.native_replay FREECAD_PYTHON NOUVEAU_DOSSIER
"""
import json
import math
import os
from pathlib import Path
import subprocess
import sys

from electromechanical_engine.freecad import PROJECT, SKILL_SCRIPTS, guard

MEC = PROJECT / "hardware/mecanique"
ENTRY = "assemblages/Prototype_Cartographe.FCStd"
REGISTERS = ("verification/construction_prototype.json", "verification/routes_prototype.json")
F16 = {
    "initial": "pieces/commerce/W_F16_Prototype.FCStd",
    "K": "verification/essai_routage_f16/F16_copie.FCStd",
    "P": "verification/essai_wireflex/F16_copie.FCStd",
}
F31 = "verification/candidats/F31_Sous_P66.FCStd"
COMPARISON = MEC / "cartographe_faces/verification/comparaison_faces.json"
SUPPORTS = MEC / "cartographe_faisceaux_modulaires/verification/volumes_supports.json"
ZONE_DELTA_TOLERANCE_MM = 0.05
COLLISION_VOLUME_MM3 = 1e-4
AABB_MARGIN_MM = 1e-7


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, allow_nan=False, indent=2) + "\n", encoding="utf-8")


def clipped_length(points, bounds):
    result = 0.0
    for a, b in zip(points, points[1:]):
        left, right = 0.0, 1.0
        for start, finish, low, high in zip(a, b, *bounds):
            delta = finish - start
            if abs(delta) < 1e-12:
                if not low <= start <= high:
                    right = left
                    break
                continue
            x, y = sorted(((low-start)/delta, (high-start)/delta))
            left, right = max(left, x), min(right, y)
        result += (b-a).Length * max(0.0, right-left)
    return result


def axes(scene, zones):
    routes = {}
    for name, wire in sorted(scene.wires.items()):
        totals = {zone: [0.0, 0.0] for zone in zones}
        for edge in wire.Edges:
            lo, hi = edge.ParameterRange
            for index, density in enumerate((96, 384)):
                count = 2 if edge.Curve.TypeId == "Part::GeomLine" else density
                points = [edge.valueAt(lo + (hi-lo)*i/(count-1)) for i in range(count)]
                for zone, bounds in zones.items():
                    totals[zone][index] += clipped_length(points, bounds)
        shape = scene.cables[name].shape
        routes[name] = {"length_mm": wire.Length, "height_mm": shape.BoundBox.ZMax,
                        "zones_mm": {zone: lengths[0] for zone, lengths in totals.items()},
                        "zones_384_mm": {zone: lengths[1] for zone, lengths in totals.items()}}
    def totals(field):
        return {zone: math.fsum(row[field][zone] for row in routes.values()) for zone in zones}
    return {"count": len(routes), "axis_sum_mm": math.fsum(row["length_mm"] for row in routes.values()),
            "height_max_mm": max(row["height_mm"] for row in routes.values()),
            "zones_mm": totals("zones_mm"), "zones_384_mm": totals("zones_384_mm"),
            "routes": routes}


def reopened_f16(root, geometry, app):
    measurements = {}
    for name, relative in F16.items():
        print(f"Réouverture F16 {name}: {relative}", flush=True)
        document = app.openDocument(str(root / relative))
        try:
            cable, wire = document.getObject("Cable"), document.getObject("Wire")
            shape = cable.Shape
            radii = [abs(edge.curvatureAt(edge.FirstParameter + (edge.LastParameter-edge.FirstParameter)*i/2000))
                     for edge in wire.Shape.Edges for i in range(2001)]
            result = {"axis": geometry.inspect_route(wire.Shape, 22.0),
                      "solid": geometry.inspect_solid(shape),
                      "radius_uniform_2001_mm": 1 / max(radii), "path_type": str(wire.PathType),
                      "shape_sha256": geometry.shape_sha256(shape),
                      "status_on_open": list(cable.State), "solid_volume_mm3": shape.Volume}
            if name == "K":
                cable.touch()
                recomputed = document.recompute()
                result["forced_recompute"] = {
                    "count": recomputed, "state": list(cable.State), "status": cable.getStatusString(),
                    "solid": geometry.inspect_solid(cable.Shape),
                    "retained_same_brep": geometry.shape_sha256(cable.Shape) == result["shape_sha256"],
                }
                result["regeneration_after_cache_clear"] = geometry.rebuild_cable_in_isolated_document(
                    document, cable)
            measurements[name] = result
        finally:
            app.closeDocument(document.Name)
    return measurements


def collisions(target, obstacles, distance_bound, measure_pair):
    result = {"scope": len(obstacles), "excluded_aabb": 0, "tested": 0,
              "collisions": [], "unknown": [], "clear": []}
    for name, shape in sorted(obstacles.items()):
        lower = distance_bound(target.BoundBox, shape.BoundBox)
        if lower > AABB_MARGIN_MM:
            result["excluded_aabb"] += 1
            continue
        measurement = measure_pair(target, shape, lower)
        result["tested"] += 1
        if "error" in measurement:
            key = "unknown"
        elif measurement["volume_mm3"] > COLLISION_VOLUME_MM3:
            key = "collisions"
        else:
            key = "clear"
        result[key].append({"occurrence": name, **measurement})
    return result


def measure(copy_root, case, config):
    sys.path.insert(0, str(MEC / "cartographe/verification/refonte_faisceaux"))
    sys.path.insert(0, str(MEC / "cartographe_refonte_systeme/verification"))
    from adapter_implantation import BoundedPairs, Scene, distance_bound
    from electromechanical_engine.freecad_worker import App, Part, cables_environment, geometry

    output = {"pid": os.getpid(), "method": "saved_native_brep",
              "freecad": App.Version(), "occt": Part.OCC_VERSION, "python": sys.version}
    if case in {"a_reopen", "faces_reopen"}:
        output["cables"] = cables_environment(False)
        output["method"] = "FreeCAD App.openDocument, sans recompute ni sauvegarde"
        print(f"Réouverture de {ENTRY}", flush=True)
        document = App.openDocument(str(copy_root / ENTRY))
        actual = {Path(doc.FileName).resolve().relative_to(copy_root).as_posix()
                  for doc in App.listDocuments().values()}
        expected = {path.relative_to(copy_root).as_posix() for path in guard.dependencies(copy_root, [ENTRY])}
        output["closure"] = {"opened": len(actual), "expected": len(expected),
                             "missing": sorted(expected-actual), "unexpected": sorted(actual-expected),
                             "partial": sorted(doc.FileName for doc in App.listDocuments().values() if doc.Partial),
                             "root_objects": len(document.Objects)}
        return output
    if case == "f16_cache":
        output["cables"] = cables_environment(False)
        output["method"] = "FreeCAD App.openDocument ; recalcul sans sauvegarde après vidage du cache"
        output["f16"] = reopened_f16(copy_root, geometry, App)
        return output
    print(f"Lecture des BRep sauvegardés : {case}", flush=True)
    scene = Scene(copy_root)
    print(f"Registre réconcilié : {len(scene.items)} occurrences, {len(scene.wires)} axes", flush=True)
    pairs = BoundedPairs()
    try:
        if case == "f16_targeted":
            guide = next(item for item in scene.items.values() if item.name == "P73_Guide")
            output["method"] = "Seconde méthode : intersection directe du composé via le moteur ; paire P73 prédéfinie"
            output["engine_pair_checks"] = {
                name: geometry.inspect_pair(scene.reader.shape(F16[name], "Cable"), guide.shape,
                                            name, guide.key, volume_tolerance_mm3=COLLISION_VOLUME_MM3)
                for name in ("initial", "P")
            }
        elif case == "f16":
            output["cables"] = cables_environment(False)
            output["method"] = "FreeCAD App.openDocument pour F16 ; BRep d'assemblage lus depuis FCStd"
            output["f16"] = reopened_f16(copy_root, geometry, App)
            obstacles = {key: item.shape for key, item in scene.items.items() if key != scene.cables["F16"].key}
            for name in ("initial", "P"):
                shape = scene.reader.shape(F16[name], "Cable")
                observed = collisions(shape, obstacles, distance_bound, pairs.measure)
                output["f16"][name]["collisions"] = observed
            output["f16"]["K"]["collisions_skipped"] = "La régénération de gaine échoue ; BRep sauvegardé suspect."
        elif case in {"a", "faces"}:
            output["axes"] = axes(scene, config["zones_mm"])
            output["electrical_endpoints_mm"] = {
                key: [list(vertex.Point) for vertex in scene.wires[key].Vertexes
                      if sum(vertex.isSame(candidate) for edge in scene.wires[key].Edges
                             for candidate in edge.Vertexes) == 1]
                for key in ("F12", "F24A", "F25", "F31", "F41")
            }
            if case == "faces":
                shape = scene.reader.shape(F31, "Cable")
                obstacles = {key: item.shape for key, item in scene.items.items() if key != scene.cables["F31"].key}
                output["f31_lower"] = {"solid": geometry.inspect_solid(shape),
                                       "collisions": collisions(shape, obstacles, distance_bound, pairs.measure)}
        else:
            output["f41_length_mm"] = scene.wires["F41"].Length
            output["occurrences"] = len(scene.items)
            expected = config["supports"][case]
            output["registered_supports_mm3"] = {}
            for name in expected:
                match = [item for key, item in scene.items.items() if name in {key, item.name}]
                if len(match) != 1:
                    raise ValueError(f"Occurrence de maintien absente ou ambiguë : {name}")
                output["registered_supports_mm3"][name] = match[0].shape.Volume
            output["guide_candidates"] = [
                {"name": item.name, "role": item.role, "volume_mm3": item.shape.Volume,
                 "dimensions_mm": [item.shape.BoundBox.XLength, item.shape.BoundBox.YLength,
                                   item.shape.BoundBox.ZLength]}
                for item in scene.items.values()
                if any(word in item.name.casefold() for word in ("retenue", "guide", "support", "monolithe"))
            ]
    finally:
        pairs.close()
    return output


def replay(python, target, selected=()):
    target.mkdir(parents=True, exist_ok=False)
    supports = read(SUPPORTS)
    config = {"zones_mm": read(COMPARISON)["zones_mm"],
              "supports": {"monolithes": sorted(supports["before_parts_mm3"]),
                           "modulaire": sorted(supports["after_parts_mm3"])}}
    write(target / "criteria.json", config)
    env = dict(os.environ, PYTHONPATH=str(PROJECT), PYTHONUTF8="1", QT_QPA_PLATFORM="offscreen")
    cases = [
        ("f16", MEC / "cartographe", tuple(F16.values())),
        ("f16_targeted", MEC / "cartographe", tuple(F16.values())),
        ("a", MEC / "cartographe_refonte_systeme/A", ()),
        ("faces", MEC / "cartographe_faces/Candidat", (F31,)),
        ("a_reopen", MEC / "cartographe_refonte_systeme/A", ()),
        ("faces_reopen", MEC / "cartographe_faces/Candidat", ()),
        ("monolithes", MEC / "cartographe_faisceaux_refonte", ()),
        ("modulaire", MEC / "cartographe_faisceaux_modulaires", ()),
        ("f16_cache", MEC / "cartographe", ()),
    ]
    if selected:
        unknown = set(selected) - {case[0] for case in cases}
        if unknown:
            raise ValueError(f"Cas inconnus : {sorted(unknown)}")
        cases = [case for case in cases if case[0] in selected]
    result = {"schema_version": 1, "criteria_sha256": guard.sha256(target / "criteria.json"),
              "zone_reference_sha256": guard.sha256(COMPARISON),
              "supports_reference_sha256": guard.sha256(SUPPORTS),
              "script_sha256": guard.sha256(__file__), "zones_mm": config["zones_mm"],
              "collision_filter": {"aabb_separation_mm": AABB_MARGIN_MM, "volume_mm3": COLLISION_VOLUME_MM3,
                                   "rules": "Toute occurrence enregistrée, sauf la route remplacée. Une séparation de boîtes positive exclut un volume commun. Aucune dérogation de contact."},
              "zone_delta_tolerance_mm": ZONE_DELTA_TOLERANCE_MM,
              "validate_cli_scope": "Les FCStd historiques n'ont pas le reçu du constructeur ni un mapping gelé des ports, enveloppes et exigences ; les contrôles natifs du moteur sont appelés directement.",
              "radius_scope": "22 mm est le seuil historique de conception testé à titre diagnostique. Les exigences d'un cordon identifié, dont un rayon dynamique éventuel, restent à établir.",
              "cases": {}}
    for case, source, extra in cases:
        print(f"{case}: isolation", flush=True)
        copy = target / case
        attempts = []
        row = result["cases"][case] = {"source": source.relative_to(PROJECT).as_posix(), "attempts": attempts}
        try:
            entry, extras = (F16["K"], (F16["initial"], F16["P"])) if case == "f16_cache" else (ENTRY, (*REGISTERS, *extra))
            receipt = guard.stage(source, entry, copy, extras)
            row["before_sha256"] = receipt["inputs_sha256"]
            for iteration in (1, 2):
                print(f"{case}: mesure {iteration}", flush=True)
                report = copy / f"measure-{iteration}.json"
                log = copy / f"measure-{iteration}.log"
                command = [str(python), "-B", "-m", __spec__.name, "--worker", str(copy),
                           case, str(target / "criteria.json"), str(report)]
                attempt = {"iteration": iteration, "log": log.relative_to(target).as_posix()}
                attempts.append(attempt)
                with log.open("wb") as stream:
                    run = subprocess.run(command, cwd=copy, env=env, stdout=stream,
                                         stderr=subprocess.STDOUT, timeout=100, check=False)
                attempt["exit_code"] = run.returncode
                if run.returncode or not report.is_file():
                    attempt["tail"] = log.read_text(encoding="utf-8", errors="replace")[-4000:]
                    continue
                attempt["report"] = report.relative_to(target).as_posix()
                attempt["report_sha256"] = guard.sha256(report)
                measurement = read(report)
                attempt["pid"] = measurement.pop("pid")
                if "measurement" not in row:
                    row["measurement"] = measurement
                else:
                    row["repeat_exact"] = row["measurement"] == measurement
            row["after_sha256"] = {name: guard.sha256(source / name) for name in row["before_sha256"]}
            row["sources_unchanged"] = row["before_sha256"] == row["after_sha256"]
            row["copies_unchanged"] = all(guard.sha256(copy / name) == digest for name, digest in row["before_sha256"].items())
        except (ValueError, RuntimeError, OSError, subprocess.TimeoutExpired) as error:
            row["execution_error"] = str(error)
            if "before_sha256" in row:
                row["after_sha256"] = {name: guard.sha256(source / name) for name in row["before_sha256"]}
                row["sources_unchanged"] = row["before_sha256"] == row["after_sha256"]
        write(target / "native_replay.json", result)
    return 0 if all(row.get("repeat_exact") and row.get("sources_unchanged") and row.get("copies_unchanged")
                    for row in result["cases"].values()) else 3


if __name__ == "__main__":
    if sys.argv[1] == "--worker":
        root, case, criteria, report = sys.argv[2:]
        write(Path(report), measure(Path(root), case, read(Path(criteria))))
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(0)
    raise SystemExit(replay(Path(sys.argv[1]).resolve(strict=True), Path(sys.argv[2]).resolve(), sys.argv[3:]))

