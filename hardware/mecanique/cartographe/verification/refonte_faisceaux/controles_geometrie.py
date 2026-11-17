"""Contrôles techniques du câblage sur natifs sauvegardés, sans écriture CAO."""

import argparse
from collections import Counter
from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import traceback

ROOT = Path(__file__).resolve().parents[5]
REFERENCE = Path(__file__).resolve().parent.parent
SKILL = ROOT / ".agents/skills/electromechanical-integration/scripts"
sys.path[:0] = [str(REFERENCE), str(SKILL)]
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import FreeCAD as App
import Part
from freecad_geometry import inspect_route, inspect_solid, rebuild_cable_in_isolated_document
from read_brep_prototype import Reader
from workspace_guard import dependencies


ENTRY = "assemblages/Prototype_Cartographe.FCStd"
BUILD = "verification/construction_prototype.json"
ROUTES = "verification/routes_prototype.json"
VOLUME_TOLERANCE = 1e-4
DISTANCE_TOLERANCE = 1e-6
NEAR_DISTANCE = 1.0
AIRY = {"AIRY", "AIRY_ETH", "AIRY_PWR", "AIRY_SYNC"}


def read(path):
    return Path(path).read_text(encoding="utf-8")


def write(path, data):
    path = Path(path)
    pending = path.with_suffix(path.suffix + ".tmp")
    pending.write_text(json.dumps(data, ensure_ascii=False, allow_nan=False, indent=2) + "\n", encoding="utf-8")
    pending.replace(path)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(condition, detail):
    if not condition:
        raise RuntimeError(detail)


def same_placement(a, b):
    return max(abs(x - y) for x, y in zip(a.toMatrix().A, b.toMatrix().A)) < 1e-7


def distance_bound(a, b):
    return math.sqrt(sum(max(0, getattr(a, k+"Min") - getattr(b, k+"Max"),
                             getattr(b, k+"Min") - getattr(a, k+"Max"))**2 for k in "XYZ"))


def bounds(shape):
    box = shape.BoundBox
    return [getattr(box, axis + suffix) for suffix in ("Min", "Max") for axis in "XYZ"]


@dataclass
class Occurrence:
    row: dict
    pose: object
    shape: object
    role: str
    metadata: dict

    @property
    def name(self):
        return self.row["occurrence"]

    @property
    def key(self):
        return self.row["parent"] + "#" + self.name


class Scene:
    def __init__(self, root, metadata=None):
        self.root = Path(root).resolve(strict=True)
        self.reader = Reader(self.root)
        self.metadata = metadata or {}
        self.routes = {}
        self.items = {}
        self.top = {}
        self.groups = {}
        rows = json.loads(read(self.root / ROUTES))["routes"]
        for row in rows:
            require(row["id"] not in self.routes, "Route dupliquée " + row["id"])
            self.routes[row["id"]] = row
        for row in json.loads(read(self.root / BUILD))["occurrences"]:
            self.groups.setdefault(row["parent"], []).append(row)
        require(ENTRY in self.groups, "Assemblée racine sans occurrence enregistrée")
        for row in self.groups[ENTRY]:
            local = self.link_pose(row)
            parent = self.reader.placement(ENTRY, "Ensemble")
            child = self.reader.placement(row["source"], row["objet_source"])
            require(row["source"] not in self.top, "Sous-assemblage répété " + row["source"])
            self.top[row["source"]] = parent.multiply(local).multiply(child.inverse())
        require(set(self.groups) == set(self.top) | {ENTRY}, "Sous-assemblages et registre divergents")
        for parent, records in self.groups.items():
            self.group_matches(parent, records)
            if parent == ENTRY:
                continue
            group = self.top[parent].multiply(self.reader.placement(parent, "Ensemble"))
            for row in records:
                name = row["occurrence"]
                local = self.link_pose(row)
                pose = group.multiply(local)
                shape = self.reader.shape(parent, name)
                shape.Placement = group.multiply(shape.Placement)
                cable = row["parent"].split("/")[-1].startswith("SA07_") and name in self.routes
                default_role = "cable" if cable else "structure"
                if name in {"P73_Guide", "P75_Cadre"}:
                    default_role = "fixation"
                if name == "ProtectionF38":
                    default_role = "gaine"
                meta = self.native_sleeve_metadata(row)
                extra = self.metadata.get(name, {})
                if extra.get("source_file", row["source"]) == row["source"]:
                    meta.update(extra)
                item = Occurrence(row, pose, shape, meta.get("role", default_role), meta)
                self.items[item.key] = item
        self.cables = {item.name: item for item in self.items.values() if item.role == "cable"}
        require(set(self.cables) == set(self.routes), "Absence de bijection entre routes et occurrences")
        require(len(self.cables) == sum(item.role == "cable" for item in self.items.values()), "Occurrence câble dupliquée")
        require(set(self.metadata) <= {item.name for item in self.items.values()}, "Métadonnées d’occurrences sans objet")
        self.wires = {}
        for name, route in self.routes.items():
            item = self.cables[name]
            require(item.row["source"] == route["fichier"], "Source CAO divergente pour " + name)
            source = item.row["objet_source"]
            if source != route["objet_cable"]:
                members = self.visible_members(route["fichier"], source)
                require(route["objet_cable"] in members, "Câble absent du groupe lié " + name)
            self.wires[name] = self.source_shape(item, route["objet_parcours"])

    def native_sleeve_metadata(self, row):
        _, objects = self.reader.xml(row["source"])
        target = objects[row["objet_source"]]
        if "ParcoursCouverts" not in target:
            return {}
        members = [node.get("value") for node in target["ParcoursCouverts"].find("StringList")]
        require(members and len(members) == len(set(members)), "Membres de gaine natifs incohérents")
        axis = target["AxeReference"].find("Link").get("value")
        cavity = target["Tool"].find("Link").get("value")
        pending = [row["objet_source"]]
        traversed = set()
        while pending:
            name = pending.pop()
            if not name or name in traversed:
                continue
            traversed.add(name)
            for prop in objects[name].values():
                link = prop.find("Link")
                if link is not None:
                    pending.append(link.get("value"))
                links = prop.find("LinkList")
                if links is not None:
                    pending.extend(node.get("value") for node in links)
        return {"role": "gaine", "members": members, "axis_object": axis, "cavity_object": cavity,
                "window_from_straight_axis": True,
                "fresh_objects": sorted(name for name in traversed if "Shape" in objects[name])}

    def group_matches(self, path, rows):
        types, props = self.reader.xml(path)
        physical = {name for name in self.visible_members(path, "Ensemble") if types[name] == "App::Link"}
        registered = {row["occurrence"] for row in rows}
        require(physical == registered and len(registered) == len(rows),
                f"Occurrences divergentes dans {path}: CAO seule {sorted(physical - registered)}, registre seul {sorted(registered - physical)}")
        require(physical == {name for name, kind in types.items() if kind == "App::Link"},
                "Lien non visible ou hors de l’ensemble dans " + path)

    def visible_members(self, path, name):
        types, props = self.reader.xml(path)
        pending = [name]
        seen = set()
        result = set()
        while pending:
            member = pending.pop()
            require(member not in seen, "Membre de groupe répété " + member)
            seen.add(member)
            visibility = props[member].get("Visibility")
            if member != name and visibility is not None and visibility.find("Bool").get("value") == "false":
                continue
            group = props[member].get("Group")
            if group is None or types[member] not in {"App::Part", "App::DocumentObjectGroup"}:
                result.add(member)
            else:
                if member != name:
                    require(self.reader.placement(path, member).isIdentity(),
                            "Placement intermédiaire non pris en charge " + member)
                pending.extend(child.get("value") for child in group.find("LinkList"))
        return result

    def link_pose(self, row):
        parent, occurrence = row["parent"], row["occurrence"]
        types, props = self.reader.xml(parent)
        require(types.get(occurrence) == "App::Link", "Lien CAO absent " + occurrence)
        prop = props[occurrence]
        target = prop["LinkedObject"].find("XLink")
        require(target is not None and not list(target), "Lien CAO non pris en charge " + occurrence)
        source = (self.root / parent).parent.joinpath(target.get("file")).resolve()
        require(source.is_relative_to(self.root), "Source hors copie " + occurrence)
        require(source == self.root / row["source"] and target.get("name") == row["objet_source"],
                "Cible XLink divergente " + occurrence)
        require(prop["LinkTransform"].find("Bool").get("value") == "false",
                "Convention LinkTransform modifiée " + occurrence)
        pose = self.reader.placement(parent, occurrence)
        require(same_placement(pose, App.Placement(App.Matrix(*row["matrice"]))),
                "Placement natif divergent " + occurrence)
        return pose

    def source_shape(self, item, object_name):
        path, source = item.row["source"], item.row["objet_source"]
        shape = self.reader.shape(path, object_name)
        shape.Placement = item.pose.multiply(self.reader.placement(path, source).inverse()).multiply(shape.Placement)
        return shape

    def hashes(self):
        return {path.relative_to(self.root).as_posix(): sha(path)
                for path in sorted(set(dependencies(self.root, [ENTRY])) | {self.root / BUILD, self.root / ROUTES})}


def check_wire(shape, positions, expectation):
    if len(shape.Wires) != 1:
        return {"status": "fail", "wire_count": len(shape.Wires), "failures": ["expected_one_wire"]}
    return inspect_route(shape.Wires[0], start_position=positions[0], end_position=positions[-1],
                         start_axis=expectation.get("start_axis"), end_axis=expectation.get("end_axis"),
                         minimum_radius_mm=expectation.get("minimum_radius_mm"),
                         waypoints=expectation.get("required_waypoints_mm", []))


def check_routes(scene):
    result = {}
    for name, row in scene.routes.items():
        cable = scene.cables[name]
        solid = scene.source_shape(cable, row["objet_cable"])
        route = check_wire(scene.wires[name], row["points_mm"], cable.metadata)
        segments = {}
        for segment in cable.metadata.get("segments", []):
            shape = scene.source_shape(cable, segment["axis_object"])
            segments[segment["id"]] = check_wire(shape, segment["endpoints_mm"], segment)
        result[name] = {
            "route": route, "solid": inspect_solid(solid), "segments": segments,
            "expectation": cable.metadata or None,
            "diameter_register_mm": row["diametre_mm"], "envelope_volume_mm3": cable.shape.Volume,
            "occurrence": cable.key, "bom_ids": row["bom_ids"],
        }
    return result


def analytic_f16_metadata():
    path = REFERENCE / "reconstruction_faisceaux/selection_f16.json"
    choice = json.loads(read(path))
    return {
        "source_file": "verification/candidats/F16_R50_X200_Z0.FCStd",
        "minimum_radius_mm": 22, "start_axis": choice["start_axis"], "end_axis": [0, -1, 0],
        "scope": "Seuils et axes candidats issus de la sélection R50/R24",
        "segments": [
            {"id": "mobile", "axis_object": "Wire", "minimum_radius_mm": 48,
             "start_axis": choice["start_axis"], "end_axis": [0, 0, -1],
             "endpoints_mm": [choice["lower_points_mm"][0], choice["lower_points_mm"][-1]]},
            {"id": "fixe", "axis_object": "Wire001", "minimum_radius_mm": 22,
             "start_axis": [0, 0, 1], "end_axis": [0, -1, 0],
             "endpoints_mm": [choice["upper_points_mm"][0], choice["upper_points_mm"][-1]]},
        ],
    }


def baseline_metadata():
    return {"F16": analytic_f16_metadata(),
            "F_M8": {"source_file": "pieces/commerce/W_F_M8_Prototype.FCStd", "minimum_radius_mm": 52,
                     "scope": "Référence candidate 1522341, rayon de pose fixe et mobile. Axes de prise et fatigue de la suspension ouverts.",
                     "source": "https://www.phoenixcontact.com/en-us/products/sensoractuator-cable-sac-6p-m-8mr-15-pur-sh-1522341"},
            "ProtectionF38": {"source_file": "verification/candidats/F38_OVALE_L80.FCStd",
                              "role": "gaine", "members": ["F38_NEG", "F38_POS"], "axis_length_mm": 80,
                              "cavity_object": "Interieur", "window_x_mm": [-30, 50],
                              "fresh_objects": ["ExterieurBout0", "ExterieurBout1", "ExterieurMilieu", "Exterieur",
                                                "InterieurBout0", "InterieurBout1", "InterieurMilieu", "Interieur",
                                                "Protection"]}}


def item_shapes(scene):
    rows = {}
    for key, item in scene.items.items():
        shape = item.shape
        solids = [(solid, solid.BoundBox) for solid in shape.Solids]
        valid = not shape.isNull() and bool(solids) and math.isfinite(shape.Volume) and shape.Volume > 0
        valid = valid and (shape.isValid() if item.role != "structure" else all(s.isValid() for s, _ in solids))
        rows[key] = {"role": item.role, "source": item.row["source"], "objet": item.row["objet_source"],
                     "placement_global": item.pose.toMatrix().A, "volume_mm3": shape.Volume,
                     "bbox_mm": bounds(shape), "solids": len(solids), "valid": valid}
        item.parts = solids
        item.box = shape.BoundBox
        item.valid = valid
    return rows


def overlap(a, b):
    rows = []
    for ashape, abox in a.parts:
        for bshape, bbox in b.parts:
            if distance_bound(abox, bbox) > DISTANCE_TOLERANCE:
                continue
            common = ashape.common(bshape)
            require(common.isNull() or common.isValid(), "Intersection booléenne invalide")
            volume = common.Volume
            require(math.isfinite(volume) and volume >= 0, "Volume d’intersection indéfini")
            if volume > 0:
                rows.append(common)
    return rows


def clearance(a, b):
    choices = sorted((distance_bound(abox, bbox), i, j)
                     for i, (_, abox) in enumerate(a.parts) for j, (_, bbox) in enumerate(b.parts))
    distance = None
    for lower, i, j in choices:
        if distance is not None and lower > distance + DISTANCE_TOLERANCE:
            break
        value = a.parts[i][0].distToShape(b.parts[j][0])[0]
        require(math.isfinite(value) and value >= lower - DISTANCE_TOLERANCE,
                "Distance BRep incohérente avec la borne AABB")
        distance = value if distance is None else min(distance, value)
    return distance


def airy_junction(scene, a, b, overlaps):
    if a.name not in AIRY or b.name not in AIRY:
        return None
    ap = [v.Point for v in scene.wires[a.name].Vertexes]
    bp = [v.Point for v in scene.wires[b.name].Vertexes]
    shared = [p for p in (ap[0], ap[-1]) if any((p-q).Length < 1e-5 for q in (bp[0], bp[-1]))]
    if not shared:
        return None
    radius = max(scene.routes[a.name]["diametre_mm"], scene.routes[b.name]["diametre_mm"])
    outside = 0.0
    for section in overlaps:
        for center in shared:
            section = section.cut(Part.makeSphere(radius, center))
            require(section.isNull() or section.isValid(), "Découpe hors éclatement Airy invalide")
        outside += section.Volume
    require(math.isfinite(outside) and outside >= 0, "Volume hors éclatement Airy indéfini")
    return {
        "kind": "enveloppes_OEM_a_la_jonction",
        "centres_mm": [[p.x, p.y, p.z] for p in shared],
        "rayon_zone_mm": radius, "borne_sup_hors_zone_mm3": outside,
        "zone_nominale_confirmee": outside <= VOLUME_TOLERANCE,
        "qualification_interne": "unknown",
    }


def pair_result(scene, a, b, lower, measure_clearance):
    row = {"pair": [a.key, b.key], "roles": [a.role, b.role], "aabb_lower_bound_mm": lower}
    if not (a.valid and b.valid):
        return dict(row, intersection_status="unknown", clearance_status="unknown", error="solide source invalide")
    try:
        common = overlap(a, b) if lower <= DISTANCE_TOLERANCE else []
        upper = sum(s.Volume for s in common)
        measured_lower = max((s.Volume for s in common), default=0.0)
        status = "pass" if upper <= VOLUME_TOLERANCE else "fail" if measured_lower > VOLUME_TOLERANCE else "unknown"
        row.update(intersection_status=status, overlap_bounds_mm3=[measured_lower, upper])
        if status == "fail":
            relation = airy_junction(scene, a, b, common)
            if relation is not None:
                row["relation"] = relation
    except Exception as exc:
        row.update(intersection_status="unknown", intersection_error=str(exc))
    if not measure_clearance and row["intersection_status"] != "fail":
        return dict(row, clearance_status="bounded")
    try:
        distance = 0.0 if row["intersection_status"] == "fail" else clearance(a, b)
        row.update(clearance_mm=distance,
                   clearance_status="unknown" if distance is None else "measured",
                   zero_clearance=distance is not None and distance <= DISTANCE_TOLERANCE)
    except Exception as exc:
        row.update(clearance_status="unknown", clearance_error=str(exc))
    return row


class PairWorker:
    """Isole le noyau OCC pour qu’une opération bloquée reste un résultat inconnu."""

    def __init__(self, scene, timeout):
        self.scene = scene
        self.timeout = timeout
        self.process = None
        self.timeouts = 0

    def close(self):
        if self.process is not None:
            self.process.kill()
            self.process.wait(timeout=10)
            self.process = None

    def start(self):
        self.process = subprocess.Popen(
            [sys.executable, "-X", "utf8", "-B", str(Path(__file__).resolve()), str(self.scene.root), "--pair-worker"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            encoding="utf-8", text=True, bufsize=1)
        channel = queue.Queue()
        stdout = self.process.stdout

        def reader():
            for line in stdout:
                if line.startswith("RESULT "):
                    channel.put(json.loads(line[7:]))
            channel.put({"stopped": True})

        threading.Thread(target=reader, daemon=True).start()
        self.channel = channel
        self.send({"metadata": self.scene.metadata})
        require(self.channel.get(timeout=70).get("ready"), "Travailleur OCC non démarré")

    def send(self, data):
        print(json.dumps(data, ensure_ascii=False, allow_nan=False), file=self.process.stdin, flush=True)

    def check(self, a, b, lower, measure_clearance):
        pair = [a.key, b.key]
        try:
            if self.process is None:
                self.start()
            self.send({"pair": pair, "lower": lower, "clearance": measure_clearance, "valid": [a.valid, b.valid]})
            result = self.channel.get(timeout=self.timeout)
            require(result.get("pair") == pair, "Réponse OCC sans la paire attendue")
            return result
        except Exception as exc:
            self.timeouts += 1
            self.close()
            message = str(exc) or f"Délai borné OCC de {self.timeout} s"
            print("paire inconnue", pair, message, flush=True)
            return {"pair": pair, "roles": [a.role, b.role], "aabb_lower_bound_mm": lower,
                    "intersection_status": "unknown", "clearance_status": "unknown", "worker_error": message}


def worker_main(root):
    def send(data):
        print("RESULT " + json.dumps(data, ensure_ascii=False, allow_nan=False), flush=True)
    header = json.loads(sys.stdin.readline())
    scene = Scene(root, header["metadata"])
    send({"ready": True})
    for line in sys.stdin:
        spec = json.loads(line)
        a, b = [scene.items[key] for key in spec["pair"]]
        for item, valid in zip((a, b), spec["valid"]):
            item.valid = valid
            if not hasattr(item, "parts"):
                item.parts = [(solid, solid.BoundBox) for solid in item.shape.Solids]
        send(pair_result(scene, a, b, spec["lower"], spec["clearance"]))


def check_pairs(scene, baseline=None, before_hashes=None, worker=None, touched=None):
    considered = 0
    remote = 0
    close = []
    clearances = {item.key: {"measured_min_mm": None, "unmeasured_lower_bound_mm": None,
                            "unknown_pairs": 0} for item in scene.items.values() if item.role != "structure"}
    items = list(scene.items.values())
    cache = {}
    if baseline:
        # Les mesures antérieures ne sont réutilisées que si chaque source
        # native et chacune de ses dépendances gardent leur empreinte et pose.
        old = baseline["inputs_sha256"]
        unchanged = set()
        tested_sources = {}
        for item in items:
            previous = baseline["occurrences"].get(item.key)
            source = item.row["source"]
            if not previous or previous["role"] != item.role or previous["source"] != source or previous["objet"] != item.row["objet_source"]:
                continue
            if not same_placement(item.pose, App.Placement(App.Matrix(*previous["placement_global"]))):
                continue
            if source not in tested_sources:
                paths = [p.relative_to(scene.root).as_posix() for p in dependencies(scene.root, [source])]
                tested_sources[source] = all(old.get(path) == before_hashes[path] for path in paths)
            if tested_sources[source]:
                unchanged.add(item.key)
        for row in baseline["pairs"]["near_or_invalid_pairs"]:
            if set(row["pair"]) <= unchanged and row["intersection_status"] != "unknown":
                cache[tuple(sorted(row["pair"]))] = row
    reused = 0
    for i, a in enumerate(items):
        for b in items[i+1:]:
            if a.role == b.role == "structure":
                continue
            if touched is not None and a.key not in touched and b.key not in touched:
                continue
            considered += 1
            lower = distance_bound(a.box, b.box)
            row = None
            if lower > NEAR_DISTANCE and a.valid and b.valid:
                remote += 1
            else:
                tracked = [clearances[item.key]["measured_min_mm"] for item in (a, b) if item.key in clearances]
                needs_clearance = any(value is None or value > lower for value in tracked)
                previous = cache.get(tuple(sorted((a.key, b.key))))
                if previous and abs(previous["aabb_lower_bound_mm"] - lower) <= DISTANCE_TOLERANCE and (
                        previous["clearance_status"] == "measured" or not needs_clearance):
                    row = dict(previous, pair=[a.key, b.key], roles=[a.role, b.role], reused_from_baseline=True)
                    reused += 1
                elif worker and a.valid and b.valid and (lower <= DISTANCE_TOLERANCE or needs_clearance):
                    row = worker.check(a, b, lower, needs_clearance)
                else:
                    row = pair_result(scene, a, b, lower, needs_clearance)
                close.append(row)
            for item in (a, b):
                if item.key not in clearances:
                    continue
                summary = clearances[item.key]
                if row is not None and row["clearance_status"] == "measured":
                    key, value = "measured_min_mm", row["clearance_mm"]
                else:
                    key, value = "unmeasured_lower_bound_mm", lower
                    if row is not None and row["clearance_status"] == "unknown":
                        summary["unknown_pairs"] += 1
                summary[key] = value if summary[key] is None else min(summary[key], value)
        if i % 30 == 0:
            print("paires", i + 1, "/", len(items), flush=True)
    for summary in clearances.values():
        measured, lower = summary["measured_min_mm"], summary["unmeasured_lower_bound_mm"]
        summary["minimum_proven_mm"] = measured if measured is not None and (lower is None or measured <= lower) else None
    return {"considered_pairs": considered, "disjoint_by_AABB_above_near_threshold": remote,
            "reused_unchanged_pairs": reused,
            "bounded_worker_seconds": worker.timeout if worker else None,
            "bounded_worker_errors": worker.timeouts if worker else None,
            "scope": "all_cable_sleeve_guide_pairs" if touched is None else "pairs_involving_changed_occurrence",
            "touched": None if touched is None else sorted(touched),
            "near_threshold_mm": NEAR_DISTANCE, "near_or_invalid_pairs": close,
            "intersection_status_counts": dict(Counter(row["intersection_status"] for row in close)),
            "clearances_by_occurrence": clearances}


def check_protections(scene):
    result = {}
    for item in scene.items.values():
        if item.role != "gaine":
            continue
        meta = item.metadata
        row = {"members": meta.get("members", []), "inclusion": [], "axis": None, "length_mm": None}
        axis = None
        if meta.get("axis_object"):
            axis = scene.source_shape(item, meta["axis_object"])
            row["axis"] = check_wire(axis, meta.get("endpoints_mm", [None, None]), meta)
            row["length_mm"] = row["axis"].get("length_mm")
        elif meta.get("axis_length_mm"):
            row["length_mm"] = meta["axis_length_mm"]
            row["length_source"] = "valeur candidate documentée, sans axe reconstitué dans ce contrôle"
        cavity = scene.source_shape(item, meta["cavity_object"]) if meta.get("cavity_object") else None
        if cavity is not None:
            row["cavity_volume_mm3"] = cavity.Volume
        row["wall_volume_mm3"] = item.shape.Volume
        for member in row["members"]:
            outcome = {"member": member, "status": "unknown"}
            try:
                cable = scene.cables[member]
                if meta.get("cavity_object") and any(meta.get(key) for key in
                        ("window_object", "window_x_mm", "window_from_straight_axis")):
                    if meta.get("window_object"):
                        window = scene.source_shape(item, meta["window_object"])
                    elif meta.get("window_x_mm"):
                        x0, x1 = meta["window_x_mm"]
                        box = cable.shape.BoundBox
                        window = Part.makeBox(x1 - x0, box.YLength + 2, box.ZLength + 2,
                                              App.Vector(x0, box.YMin - 1, box.ZMin - 1))
                    else:
                        require(axis is not None and len(axis.Edges) == 1 and
                                axis.Edges[0].Curve.TypeId == "Part::GeomLine", "Fenêtre axiale non rectiligne")
                        start, end = [v.Point for v in axis.Vertexes]
                        vector = end - start
                        box = cable.shape.BoundBox
                        margin = (box.Center - start).Length + box.DiagonalLength + 1
                        window = Part.makeBox(2 * margin, 2 * margin, vector.Length,
                                              App.Vector(-margin, -margin, 0))
                        pose = App.Placement(start, App.Rotation(App.Vector(0, 0, 1), vector))
                        window.Placement = pose.multiply(window.Placement)
                    section = cable.shape.common(window)
                    outside = section.cut(cavity)
                    overlap_wall = section.common(item.shape)
                    volumes = [section.Volume, outside.Volume, overlap_wall.Volume]
                    require(all(shape.isNull() or shape.isValid() for shape in (section, outside, overlap_wall)),
                            "Opération d’inclusion invalide")
                    require(all(math.isfinite(v) and v >= 0 for v in volumes), "Volume d’inclusion indéfini")
                    outcome.update(section_mm3=volumes[0], outside_cavity_mm3=volumes[1],
                                   inside_wall_mm3=volumes[2], status="pass" if volumes[0] > VOLUME_TOLERANCE
                                   and max(volumes[1:]) <= VOLUME_TOLERANCE else "fail")
                    distance = section.distToShape(item.shape)[0]
                    if math.isfinite(distance) and distance >= 0:
                        outcome["wall_distance_mm"] = distance
                else:
                    outcome["error"] = "fenêtre de tronçon et volume de cavité indisponibles dans les métadonnées"
            except Exception as exc:
                outcome["error"] = str(exc)
            row["inclusion"].append(outcome)
        if cavity is not None and cavity.Volume > 0 and row["inclusion"] and all(
                "section_mm3" in member for member in row["inclusion"]):
            row["occupied_fraction_upper_bound"] = sum(member["section_mm3"] for member in row["inclusion"]) / cavity.Volume
        result[item.name] = row
    return result


def check_stations(scene):
    measurements = []
    for item in scene.items.values():
        _, objects = scene.reader.xml(item.row["source"])
        source = objects[item.row["objet_source"]]
        for name, prop in source.items():
            if not name.startswith("Retenue"):
                continue
            string = prop.find("String")
            if string is None or not string.get("value", "").startswith("{"):
                continue
            metadata = json.loads(string.get("value"))
            for station in metadata.get("stations", []):
                if not isinstance(station, dict):
                    continue
                point = station.get("point_mm")
                frame = station.get("repere") or metadata.get("repere")
                members = station.get("cables", [station.get("cable") or metadata.get("cable")])
                if not isinstance(members, list):
                    members = [members]
                vector = App.Vector(*point) if isinstance(point, list) and len(point) == 3 else None
                if vector is not None and frame and frame.casefold().startswith("local"):
                    vector = item.pose.multVec(vector)
                for member in members:
                    row = {"station": station.get("id"), "source_property": name, "occurrence": item.key,
                           "support": station.get("support"), "route": member,
                           "declared_frame": frame, "axis_distance_mm": None}
                    if vector is not None and member in scene.wires:
                        distance = Part.Vertex(vector).distToShape(scene.wires[member])[0]
                        if math.isfinite(distance):
                            row["axis_distance_mm"] = distance
                    measurements.append(row)
    return {"measurements": measurements,
            "scope": "Distance de site à l’axe, repère global implicite si absent. Le peigne MAIN décrit un site commun. Aucune tenue mécanique déduite."}


def compare(before, after):
    previous = before["occurrences"]
    current = after["occurrences"]
    shared = sorted(set(previous) & set(current))
    before_routes, after_routes = before["routes"], after["routes"]
    shared_routes = sorted(set(before_routes) & set(after_routes))
    def anomalies(report):
        return {tuple(sorted(row["pair"])): row for row in report["pairs"]["near_or_invalid_pairs"]
                if row["intersection_status"] == "fail"}
    old_bad, new_bad = anomalies(before), anomalies(after)
    old_sha = before["inputs_sha256"]
    new_sha = after["inputs_sha256"]
    return {
        "occurrences_before_after": [len(previous), len(current)],
        "new_occurrences": sorted(set(current) - set(previous)),
        "removed_occurrences": sorted(set(previous) - set(current)),
        "common_occurrences_with_changed_pose": [
            key for key in shared if max(abs(a-b) for a,b in zip(previous[key]["placement_global"], current[key]["placement_global"])) > 1e-7],
        "common_sources_with_changed_hash": sorted(path for path in set(old_sha) & set(new_sha) if old_sha[path] != new_sha[path]),
        "unchanged_route_ids": set(before_routes) == set(after_routes),
        "nominal_route_length_mm_before_after": [before["wire_length_mm"], after["wire_length_mm"]],
        "protection_length_mm_before_after": [{name: row["length_mm"] for name, row in report["protections"].items()}
                                                for report in (before, after)],
        "route_volume_mm3_before_after": [
            sum(row["envelope_volume_mm3"] for row in report["routes"].values()) for report in (before, after)],
        "mass_complete_g_before_after": [None, None],
        "length_mm_by_route_before_after": {name: [before_routes[name]["route"].get("length_mm"),
                                                     after_routes[name]["route"].get("length_mm")]
                                          for name in shared_routes},
        "added_intersections": [new_bad[key] for key in sorted(new_bad.keys() - old_bad.keys())],
        "removed_intersections": [old_bad[key] for key in sorted(old_bad.keys() - new_bad.keys())],
        "persistent_intersections": [{"pair": list(key), "before_mm3": old_bad[key]["overlap_bounds_mm3"],
                                      "after_mm3": new_bad[key]["overlap_bounds_mm3"]}
                                     for key in sorted(new_bad.keys() & old_bad.keys())],
    }


def delta_comparison(scene, result, root, timeout):
    reference = Scene(root, baseline_metadata())
    source_hashes = reference.hashes()
    current_hashes = result["inputs_sha256"]
    changed = set(scene.items) ^ set(reference.items)
    examined = {}
    for key in set(scene.items) & set(reference.items):
        old, new = reference.items[key], scene.items[key]
        if old.role != new.role or old.row["source"] != new.row["source"] or old.row["objet_source"] != new.row["objet_source"]:
            changed.add(key)
            continue
        source = new.row["source"]
        if source not in examined:
            paths = [p.relative_to(scene.root).as_posix() for p in dependencies(scene.root, [source])]
            examined[source] = all(source_hashes.get(path) == current_hashes[path] for path in paths)
        if not examined[source] or not same_placement(old.pose, new.pose):
            changed.add(key)
    old_routes = check_routes(reference)
    before = {"inputs_sha256": source_hashes, "occurrences": item_shapes(reference), "routes": old_routes,
              "protections": check_protections(reference), "wire_length_mm": sum(
                  row["route"].get("length_mm", 0.0) for row in old_routes.values())}
    for selected, report in ((reference, before), (scene, result)):
        worker = PairWorker(selected, timeout) if timeout > 0 else None
        try:
            report["pairs"] = check_pairs(selected, worker=worker, touched=changed)
        finally:
            if worker:
                worker.close()
    result["reference_pairs"] = before["pairs"]
    result["reference_inputs_sha256"] = source_hashes
    require(source_hashes == reference.hashes(), "Référence modifiée pendant le contrôle")
    return compare(before, result)


def fresh_checks(scene):
    require(scene.root.name not in {"cartographe", "cartographe_faisceaux", "cartographe_faisceaux_autonome"},
            "Le recalcul cache vidé doit se faire sur une nouvelle copie dédiée")
    import FreeCADGui as Gui
    import cable_workbench_prototype as builder
    Gui.showMainWindow()
    Gui.getMainWindow().hide()
    environment = builder.bootstrap_paths()
    result = {"environment": environment, "routes": {}, "protections": {}, "entry": {}}

    def isolated():
        for doc in App.listDocuments().values():
            require(doc.FileName and Path(doc.FileName).resolve().is_relative_to(scene.root),
                    "Dépendance chargée hors copie")

    def difference(saved, fresh):
        volumes = []
        for part in (saved.cut(fresh), fresh.cut(saved)):
            require(part.isNull() or part.isValid(), "Différence volumique invalide")
            volumes.append(part.Volume)
        return {"removed_mm3": volumes[0], "added_mm3": volumes[1],
                "status": "pass" if max(volumes) <= VOLUME_TOLERANCE else "fail"}

    def state_errors(doc):
        return [{"object": obj.Name, "states": list(obj.State)} for obj in doc.Objects
                if any(state in ("Error", "Invalid") for state in obj.State)]

    for name, row in scene.routes.items():
        doc = App.openDocument(str(scene.root / row["fichier"]))
        isolated()
        try:
            cable = doc.getObject(row["objet_cable"])
            saved = cable.Shape.copy()
            if hasattr(cable.Base, "Links"):
                for link in cable.Base.Links:
                    link.touch()
            fresh = rebuild_cable_in_isolated_document(doc, cable)
            result["routes"][name] = {"rebuild": fresh, "equivalence": difference(saved, cable.Shape)
                                      if fresh["status"] == "pass" else None, "errors": state_errors(doc)}
        except Exception as exc:
            result["routes"][name] = {"status": "unknown", "error": str(exc)}
        finally:
            App.closeDocument(doc.Name)
        print("recalcul", name, flush=True)
    for item in scene.items.values():
        if item.role not in {"gaine", "fixation"} or not item.metadata.get("fresh_objects"):
            continue
        doc = App.openDocument(str(scene.root / item.row["source"]))
        isolated()
        try:
            target = doc.getObject(item.row["objet_source"])
            if not hasattr(target, "Shape") and len(item.metadata["fresh_objects"]) == 1:
                target = doc.getObject(item.metadata["fresh_objects"][0])
            saved = target.Shape.copy()
            for name in item.metadata["fresh_objects"]:
                feature = doc.getObject(name)
                feature.Shape = Part.Shape()
                feature.touch()
            recompute = bool(doc.recompute())
            solid = inspect_solid(target.Shape)
            result["protections"][item.name] = {
                "recompute_return": recompute, "solid": solid, "errors": state_errors(doc),
                "equivalence": difference(saved, target.Shape) if solid["status"] == "pass" else None,
            }
        except Exception as exc:
            result["protections"][item.name] = {"status": "unknown", "error": str(exc)}
        finally:
            App.closeDocument(doc.Name)
    entry = App.openDocument(str(scene.root / ENTRY))
    isolated()
    recompute = bool(entry.recompute())
    result["entry"] = {"documents": [{"path": Path(doc.FileName).resolve().relative_to(scene.root).as_posix(),
                                       "errors": state_errors(doc)} for doc in App.listDocuments().values()],
                       "loaded_inside_copy": True, "recompute_return": recompute}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("copy", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--metadata", type=Path)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--delta-from", type=Path)
    parser.add_argument("--baseline-metadata", action="store_true")
    parser.add_argument("--fresh", action="store_true")
    parser.add_argument("--without-pairs", action="store_true")
    parser.add_argument("--pair-timeout", type=float, default=12.0)
    args = parser.parse_args()
    require(not (args.delta_from and (args.baseline or args.without_pairs)), "Modes de comparaison incompatibles")
    metadata = baseline_metadata() if args.baseline_metadata else {}
    if args.metadata:
        metadata.update(json.loads(read(args.metadata)))
    scene = Scene(args.copy, metadata)
    hashes = scene.hashes()
    baseline = json.loads(read(args.baseline)) if args.baseline else None
    if baseline:
        require(baseline["complete"] and "pairs" in baseline and not args.without_pairs, "Comparaison incomplète")
    print("scène", len(scene.items), "occurrences", flush=True)
    result = {
        "schema": "cartographe.controle-geometrie-faisceaux.v1", "complete": False,
        "scope": "BRep nominales sauvegardées des occurrences, repères globaux, aucun essai de montage ou physique",
        "environment": {"freecad": App.Version()[:3], "occ": Part.OCC_VERSION},
        "inputs_sha256": hashes,
        "metadata_sha256": sha(args.metadata) if args.metadata else None,
        "adapter_sha256": sha(__file__),
        "tolerances": {"volume_mm3": VOLUME_TOLERANCE, "distance_mm": DISTANCE_TOLERANCE,
                       "continuity_mm": 1e-5, "tangency_deg": .1},
        "gates": {"integrity": "pass", "fresh": "not_executed", "pairs": "not_executed",
                  "interactive": "not_executed", "physical": "not_executed"},
        "routes": check_routes(scene), "occurrences": item_shapes(scene),
        "protections": check_protections(scene), "stations": check_stations(scene),
    }
    if args.fresh:
        result["fresh"] = fresh_checks(scene)
        fresh = result["fresh"]
        checked = [*fresh["routes"].values(), *fresh["protections"].values()]
        invalid = [row for row in checked if row.get("errors") or row.get("recompute_return") is False
                   or row.get("rebuild", row.get("solid", {})).get("status") == "fail"
                   or (row.get("equivalence") or {}).get("status") == "fail"]
        if invalid or not fresh["entry"]["recompute_return"] or any(row["errors"] for row in fresh["entry"]["documents"]):
            result["gates"]["fresh"] = "fail"
        elif any(row.get("status") == "unknown" or row.get("equivalence") is None for row in checked):
            result["gates"]["fresh"] = "unknown"
        else:
            result["gates"]["fresh"] = "pass"
    write(args.output, result)
    print("géométries mesurées", len(result["routes"]), "routes", flush=True)
    if not args.without_pairs:
        if args.delta_from:
            result["wire_length_mm"] = sum(row["route"].get("length_mm", 0.0) for row in result["routes"].values())
            result["comparison"] = delta_comparison(scene, result, args.delta_from, args.pair_timeout)
        else:
            worker = PairWorker(scene, args.pair_timeout) if args.pair_timeout > 0 else None
            try:
                result["pairs"] = check_pairs(scene, baseline, hashes, worker)
            finally:
                if worker:
                    worker.close()
        pairs = result["pairs"]["near_or_invalid_pairs"]
        if any(row["intersection_status"] == "fail" and not row.get("relation", {}).get("zone_nominale_confirmee")
               for row in pairs):
            result["gates"]["pairs"] = "fail"
        elif any(row["intersection_status"] != "pass" or row["clearance_status"] == "unknown" for row in pairs):
            result["gates"]["pairs"] = "unknown"
        else:
            result["gates"]["pairs"] = "pass"
    result["wire_length_mm"] = sum(row["route"].get("length_mm", 0.0) for row in result["routes"].values())
    result["native_read_only"] = hashes == scene.hashes()
    require(result["native_read_only"], "Fichiers natifs modifiés pendant le contrôle")
    if baseline:
        result["comparison"] = compare(baseline, result)
        result["baseline_report_sha256"] = sha(args.baseline)
    result["complete"] = True
    write(args.output, result)
    print("rapport finalisé", args.output, flush=True)


if __name__ == "__main__":
    try:
        if len(sys.argv) == 3 and sys.argv[2] == "--pair-worker":
            worker_main(sys.argv[1])
        else:
            main()
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(0)
    except Exception:
        traceback.print_exc()
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(2)
