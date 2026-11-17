"""Adaptateur FreeCAD pour les essais et la réalisation A, uniquement sur la copie."""
import argparse
import json
import os
import queue
import subprocess
import threading
from pathlib import Path
import sys
import traceback

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
COPY = HERE.parent / "A"
LEGACY = REPO / "hardware/mecanique/cartographe/verification/refonte_faisceaux"
sys.path[:0] = [str(LEGACY), str(COPY / "verification")]
from controles_geometrie import App, Part, Scene, bounds, distance_bound, require, sha, write
from adapter_freecad import boot, cable_geometry, make_native_cable, rebuild_cable_in_isolated_document
from workspace_guard import verify_sources

ENTRY = "assemblages/Prototype_Cartographe.FCStd"
BUILD = "verification/construction_prototype.json"
ROUTES = "verification/routes_prototype.json"
P71 = "pieces/fabriquees/P71_Support_Securite_Prototype.FCStd"
V = App.Vector


def load(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def check_isolation():
    require(all(d.FileName and Path(d.FileName).resolve().is_relative_to(COPY)
                for d in App.listDocuments().values()), "Document chargé hors copie")


def move(shape, delta):
    result = shape.copy()
    result.translate(V(*delta))
    return result


def measure_pair(target, obstacle, lower):
    require(obstacle.isValid() and obstacle.Solids, "Obstacle sans BRep valide")
    volume = 0.0
    if lower < 1e-7:
        for solid in obstacle.Solids:
            if distance_bound(target.BoundBox, solid.BoundBox) < 1e-7:
                common = target.common(solid)
                require(common.isNull() or common.isValid(), "Intersection BRep invalide")
                volume += common.Volume
    return {"volume_mm3": volume, "gap_mm": target.distToShape(obstacle)[0]}


def pair_worker():
    for line in sys.stdin:
        try:
            a, b, lower = json.loads(line)
            shapes = []
            for brep in (a, b):
                shape = Part.Shape()
                shape.importBrepFromString(brep)
                shapes.append(shape)
            result = measure_pair(*shapes, lower)
        except Exception as error:
            result = {"error": str(error)}
        print(json.dumps(result), flush=True)


class BoundedPairs:
    def __init__(self):
        self.process = None

    def close(self):
        if self.process:
            self.process.kill()
            self.process.wait()
            self.process = None

    def measure(self, a, b, lower):
        if self.process is None:
            self.process = subprocess.Popen([sys.executable, "-B", __file__, "worker"],
                                            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                            stderr=subprocess.DEVNULL, text=True, encoding="ascii")
            channel = self.channel = queue.Queue()
            pipe = self.process.stdout

            def receive():
                for line in pipe:
                    channel.put(line)
                channel.put(None)

            threading.Thread(target=receive, daemon=True).start()
        try:
            print(json.dumps([a.exportBrepToString(), b.exportBrepToString(), lower]),
                  file=self.process.stdin, flush=True)
            reply = self.channel.get(timeout=5)
            require(reply is not None, "Travailleur OCC interrompu")
            return json.loads(reply)
        except (queue.Empty, OSError, ValueError, RuntimeError):
            self.close()
            return {"error": "Calcul OCC non résolu dans la limite de 5 s"}


PAIRS = BoundedPairs()


def report_pairs(target, shapes, nearby=0.5):
    result = {"collisions": [], "unknowns": [], "clearances": [], "tested": 0}
    require(target.isValid() and target.Solids, "Cible sans BRep valide")
    for name, obstacle in shapes.items():
        lower = distance_bound(target.BoundBox, obstacle.BoundBox)
        if lower > nearby:
            continue
        result["tested"] += 1
        row = PAIRS.measure(target, obstacle, lower)
        if "error" in row:
            key = "unknowns"
        elif row["volume_mm3"] > 1e-4:
            key = "collisions"
        else:
            key = "clearances"
        result[key].append({"name": name, **row})
    return result

def modify_p71(doc, x, y):
    for name in ("Percage", "Percage001", "BrasAppui", "RaccordBrasAncrage"):
        feature = doc.getObject(name)
        p = feature.Placement
        p.Base += V(x, y if name != "RaccordBrasAncrage" else 0, 0)
        feature.Placement = p
    doc.Plaque.setExpression("Placement.Base.x", f"{x} mm - Parametres.Longueur / 2")
    doc.Plaque.setExpression("Placement.Base.y", f"{y} mm - Parametres.Largeur / 2")
    doc.BrasAppui.Width = 65 - y
    # Joint volumique avec la traverse fixe et conservation des deux perçages châssis.
    doc.recompute()
    final = doc.getObject("SupportAncreM21")
    require(final.Shape.isValid() and len(final.Shape.Solids) == 1, "Support P71 disjoint ou invalide")
    return final.Shape.copy()


def support_trial(item, x, y):
    doc = App.openDocument(str(COPY / P71))
    check_isolation()
    try:
        shape = modify_p71(doc, x, y)
        shape.Placement = item.pose.multiply(shape.Placement)
        return shape
    finally:
        App.closeDocument(doc.Name)


def test_route(row, points, scene):
    doc = App.newDocument("Essai")
    try:
        cable, _ = make_native_cable(doc, None, row["id"], points,
                                     row["diametre_mm"], row["rayon_courbure_mm"])
        shape = cable.Shape.copy()
        return cable_geometry(cable), report_pairs(shape, scene)
    except Exception as error:
        return {"error": str(error)}, None
    finally:
        App.closeDocument(doc.Name)


def explore(scene, spec):
    shapes = {o.name: o.shape for o in scene.items.values()}
    lookup = {o.name: o for o in scene.items.values()}
    results = {"security": [], "routing": [], "diagnostics": [], "versions": boot(),
               "initial_cao_sha256": scene.hashes(), "spec_sha256": sha(HERE / "implantation.json"),
               "adapter_sha256": sha(__file__), "complete": False}
    for candidate in spec["security"]:
        x = candidate["x_mm"]
        y = candidate.get("y_mm", 0)
        switch = move(shapes["BoutonBuzzerLED"], (x, y, 0))
        support = support_trial(lookup["SupportSecurite"], x, y)
        obstacles = {name: shape for name, shape in shapes.items()
                     if name not in {"SupportSecurite", "BoutonBuzzerLED", "F25"}}
        switch_fit = report_pairs(switch, {**obstacles, "SupportSecurite": support})
        support_fit = report_pairs(support, obstacles)
        # Réservation exploratoire au-dessus de la façade, sans hypothèse de doigt ou d'outil OEM.
        access = Part.makeBox(30, 24, 35, V(x-15, y-112, 105))
        access_fit = report_pairs(access, obstacles)
        rows = []
        for points in candidate["paths"]:
            geometry, pairs = test_route(scene.routes["F25"], points, {**obstacles, "SupportSecurite": support,
                                                                     "BoutonBuzzerLED": switch})
            rows.append({"points_mm": points, "geometry": geometry, "pairs": pairs})
        results["security"].append({"x_mm": x, "y_mm": y, "support": support_fit, "switch": switch_fit,
                                    "access": access_fit, "support_volume_mm3": support.Volume,
                                    "switch_bbox_mm": bounds(switch), "routes": rows})
        write(HERE / "essais_implantation.json", results)
        print("F25 / P71", x, y, flush=True)
    for key, alternatives in spec["routing"].items():
        row = scene.routes[key]
        obstacles = {name: shape for name, shape in shapes.items() if name != key}
        before = report_pairs(shapes[key], obstacles)
        for points in alternatives:
            geometry, pairs = test_route(row, points, obstacles)
            results["routing"].append({"id": key, "points_mm": points, "geometry": geometry,
                                       "before_pairs": before, "pairs": pairs})
        write(HERE / "essais_implantation.json", results)
        print(key, flush=True)
    iso = lookup["UART_isole"]
    usb = scene.reader.shape(iso.row["source"], "ORCH_USB_B")
    ttl = scene.reader.shape(iso.row["source"], "ORCH_BornierTTL")
    port_b = iso.pose.multVec(V(usb.BoundBox.XMin, usb.BoundBox.Center.y, usb.BoundBox.Center.z))
    port_ttl = iso.pose.multVec(V(ttl.BoundBox.XMax, ttl.BoundBox.Center.y, ttl.BoundBox.Center.z))
    results["ports_cao"] = {"usb_b": list(port_b), "ttl_face": list(port_ttl),
                            "f41_start_offset_mm": (V(*scene.routes["F41"]["points_mm"][0]) - port_b).Length,
                            "f40_end_offset_mm": (V(*scene.routes["F40"]["points_mm"][-1]) - port_ttl).Length,
                            "scope": "Faces de blocs CAO reconstruits. Cotes d'accouplement et sortie de fils non mesurées sur matériel."}
    for candidate in spec["diagnostics"]:
        rotation = App.Rotation(V(0, 0, 1), candidate["angle_z_deg"])
        pivot = V(*spec["iso_pivot_mm"])
        transform = App.Placement(pivot + V(*candidate["shift_mm"]) - rotation.multVec(pivot), rotation)
        shape = iso.shape.copy()
        shape.Placement = transform.multiply(shape.Placement)
        b = transform.multVec(port_b)
        t = transform.multVec(port_ttl)
        axis = rotation.multVec(V(-1, 0, 0))
        # L'axe de Part.makeBox est la hauteur locale. Réservation USB orientée
        # par transformation explicite d'une boîte de départ vers l'axe de sortie.
        box = Part.makeBox(35, 17, 16, port_b + V(-35, -8.5, -8))
        box.Placement = transform.multiply(box.Placement)
        obstacles = {name: sh for name, sh in shapes.items() if name not in {"UART_isole", "F40", "F41"}}
        results["diagnostics"].append({**candidate, "module_bbox_mm": bounds(shape),
                                      "usb_b": list(b), "usb_axis": list(axis), "ttl_face": list(t),
                                      "module": report_pairs(shape, obstacles),
                                      "usb_extraction": report_pairs(box, obstacles)})
        print(candidate["id"], flush=True)
    results["complete"] = True
    write(HERE / "essais_implantation.json", results)


def no_interference(check):
    return check and not (check["collisions"] or check["unknowns"])


def rebuild_route(row, points, references):
    doc = App.openDocument(str(COPY / row["fichier"]))
    check_isolation()
    try:
        cable = doc.getObject(row["objet_cable"])
        route = cable.Base
        route.Points = [route.Placement.inverse().multVec(V(*point)) for point in points]
        rebuilt = rebuild_cable_in_isolated_document(doc, cable)
        require(rebuilt["status"] == "pass", str(rebuilt))
        geometry = cable_geometry(cable)
        doc.save()
        row.update(geometry, points_mm=points, longueur_trace_mm=round(geometry["longueur_courbe_mm"], 3))
        for ref in references:
            if ref["fichier"] == row["fichier"]:
                ref.update(sha256=sha(COPY / row["fichier"]), bbox_mm=bounds(cable.Shape))
        return geometry
    finally:
        App.closeDocument(doc.Name)


def install(scene, selection):
    experiment = load(COPY / "experiment.json")
    require(Path(experiment["copy_root"]).resolve() == COPY.resolve(), "Mauvaise copie")
    require(verify_sources(experiment)["sources_unchanged"], "Source altérée")
    require(all(sha(COPY / path) == digest for path, digest in experiment["inputs_sha256"].items()),
            "Repartir d'une copie non mutée")
    trials = load(HERE / "essais_implantation.json")
    require(trials["complete"] and trials["initial_cao_sha256"] == scene.hashes()
            and trials["adapter_sha256"] == sha(__file__) and trials["spec_sha256"] == sha(HERE / "implantation.json"),
            "Essais de placement non finalisés ou entrées différentes")
    candidate = next(row for row in trials["security"] if [row["x_mm"], row["y_mm"]] == selection["security_shift_xy_mm"])
    routed = candidate["routes"][selection["security_path_index"]]
    require(all(no_interference(check) for check in (candidate["support"], candidate["switch"],
                                                    candidate["access"])) and routed["pairs"] and not routed["pairs"]["collisions"]
            and {v["name"] for v in routed["pairs"]["unknowns"]} <= {"Holybro6XOrin"},
            "Candidat sécurité en conflit ou non résolu")
    environment = boot()
    reg = load(COPY / BUILD)
    routes = load(COPY / ROUTES)
    by_id = {r["id"]: r for r in routes["routes"]}
    ref = next(r for r in reg["references"] if r["fichier"] == P71)
    doc = App.openDocument(str(COPY / P71))
    check_isolation()
    support = modify_p71(doc, candidate["x_mm"], candidate["y_mm"])
    doc.save()
    ref.update(sha256=sha(COPY / P71), bbox_mm=bounds(support))
    App.closeDocument(doc.Name)
    changed = {"F25": rebuild_route(by_id["F25"], routed["points_mm"], reg["references"])}
    entry = App.openDocument(str(COPY / ENTRY))
    check_isolation()
    occurrence = next(r for r in reg["occurrences"] if r["occurrence"] == "BoutonBuzzerLED")
    parent = next(doc for doc in App.listDocuments().values() if Path(doc.FileName).resolve() == COPY / occurrence["parent"])
    switch = parent.getObject(occurrence["occurrence"])
    pose = switch.Placement
    pose.Base += V(candidate["x_mm"], candidate["y_mm"], 0)
    switch.Placement = pose
    occurrence["matrice"] = list(pose.toMatrix().A)
    parent.recompute()
    parent.save()
    entry.recompute()
    entry.save()
    for doc in App.listDocuments().values():
        require(not any(set(obj.State) & {"Error", "Invalid"} for obj in doc.Objects),
                "Objet invalide dans " + doc.Name)
    for doc in list(App.listDocuments().values()):
        if App.getDocument(doc.Name):
            App.closeDocument(doc.Name)
    reg["integration_systeme"] = {"variante": "A", "statut": "À valider",
                                 "controle": "../verification/validation_A.json",
                                 "reprise": ["BoutonBuzzerLED", "SupportSecurite", "F25"]}
    write(COPY / BUILD, reg)
    write(COPY / ROUTES, routes)
    manifest = load(COPY / "manifest.json")
    manifest.update(configuration="cartographe_refonte_systeme_A", promotion=False,
                    qualification="À valider", references=reg["references"], occurrences=reg["occurrences"],
                    controle="../verification/validation_A.json")
    write(COPY / "manifest.json", manifest)
    write(HERE / "installation_A.json", {"complete": True, "environment": environment, "changed_routes": changed,
                                        "selection_sha256": sha(HERE / "selection_A.json"),
                                        "tests_sha256": sha(HERE / "essais_implantation.json"),
                                        "reference_unchanged": verify_sources(experiment)["sources_unchanged"],
                                        "final_cao_sha256": Scene(COPY).hashes()})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("trial", "install", "worker"))
    args = parser.parse_args()
    if args.mode == "worker":
        pair_worker()
        sys.exit(0)
    try:
        scene = Scene(COPY)
        if args.mode == "trial":
            explore(scene, load(HERE / "implantation.json"))
        else:
            install(scene, load(HERE / "selection_A.json"))
        PAIRS.close()
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(0)
    except Exception:
        PAIRS.close()
        traceback.print_exc()
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(2)




