"""Mesures indépendantes des deux bancs XLink V3 B.1, sans consulter les plans."""

from __future__ import annotations

import argparse
import hashlib
from itertools import combinations
import json
import math
import os
from pathlib import Path
import re
import sys
from uuid import uuid4
from xml.etree.ElementTree import ParseError
from zipfile import BadZipFile

import FreeCAD as App
import Part

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from electromechanical_engine.freecad import PROJECT, guard


SCHEMA = "v3.cross_measurement/1"
PROFILES = {
    PROJECT / "docs/electromechanical_v3/bench_b1_c4/profile.json",
    PROJECT / "docs/electromechanical_v3/bench_b1_workholding/profile.json",
    PROJECT / "docs/electromechanical_v3/bench_c1_coupled/profile.json",
    PROJECT / "docs/electromechanical_v3/bench_c1_coupled_secondary/profile.json",
    PROJECT / "docs/electromechanical_v3/bench_b2_variations.json",
}
GROUPS = {"App::Part", "App::DocumentObjectGroup"}
ERRORS = (AttributeError, BadZipFile, IndexError, KeyError, OSError, ParseError, RuntimeError, TypeError, ValueError)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def private(path):
    absolute = path.absolute()
    runtime = PROJECT / ".runtime"
    verified = guard.inside(runtime, absolute)
    require(verified != runtime and verified == absolute, f"Chemin privé et canonique requis : {path}")
    for component in (absolute, *absolute.parents):
        reparse = getattr(component.lstat(), "st_reparse_tag", 0) if component.exists() else 0
        require(not component.is_symlink() and not reparse,
                f"Chemin redirigé : {component}")
        if component == PROJECT:
            break
    return verified


def native_hashes(root, entry):
    result = {}
    for file in guard.dependencies(root, [entry]):
        require(file.suffix.lower() == ".fcstd" and file.stat().st_nlink == 1,
                f"Dépendance native invalide ou partagée : {file}")
        result[file.relative_to(root).as_posix()] = guard.sha256(file)
    return result


def setup_cables():
    stock = Path(App.getResourceDir()) / "Mod"
    user = Path(App.getUserAppDataDir()) / "Mod"
    addon = next((path for path in (user / "Cables", stock / "Cables")
                  if (path / "freecad/cables/archCable.py").is_file()), None)
    require(addon is not None, "Cables Workbench absent")
    sys.path[:0] = [str(path) for path in (addon, stock / "Draft", stock / "BIM")]
    import Draft
    from draftviewproviders.view_wire import ViewProviderWire
    from freecad.cables import version

    Draft.ViewProviderWire = ViewProviderWire
    return {"FreeCAD": ".".join(App.Version()[:3]), "OCCT": Part.OCC_VERSION, "Cables": version.__version__}


def reopen(root, entry, expected):
    require(not App.listDocuments(), "Processus FreeCAD déjà occupé")
    doc = App.openDocument(str(root / entry))
    for name, document in list(App.listDocuments().items()):
        if document.Partial:
            opened = guard.inside(root, document.FileName)
            require(opened.relative_to(root).as_posix() in expected,
                    f"Dépendance partielle hors fermeture : {name}")
            require(not App.openDocument(str(opened), True).Partial, f"Document partiel : {name}")
    documents = {guard.inside(root, item.FileName).relative_to(root).as_posix(): item
                 for item in App.listDocuments().values()}
    require(documents.keys() == expected.keys() and not any(item.Partial for item in documents.values()),
            "Fermeture réellement ouverte différente")
    for item in doc.getDependentDocuments():
        require(item.recompute() >= 0, f"Recalcul FreeCAD en échec : {item.Name}")
    invalid = [f"{path}#{obj.Name}" for path, item in documents.items() for obj in item.Objects
               if {"Invalid", "Error"}.intersection(obj.State) or
               obj.TypeId == "App::Link" and obj.getLinkedObject() == obj]
    return doc, sorted(documents), invalid


def shape_hash(shape):
    return hashlib.sha256(shape.exportBrepToString().encode("utf-8")).hexdigest()


def bounds(shape):
    box = shape.BoundBox
    return [[box.XMin, box.YMin, box.ZMin], [box.XMax, box.YMax, box.ZMax]]


def point(vector):
    return list(vector)


def solid(shape):
    return not shape.isNull() and bool(shape.Solids) and shape.isValid() and shape.Volume > 0


def overlap(a, b):
    intersection = a.common(b)
    require(intersection.isNull() or intersection.isValid(), "Intersection BRep indéterminée")
    require(math.isfinite(intersection.Volume) and intersection.Volume >= 0, "Volume commun invalide")
    return intersection.Volume


def relation(a, b):
    require(solid(a) and solid(b), "Solide de mesure invalide")
    return {"intersection_mm3": overlap(a, b), "gap_mm": a.distToShape(b)[0]}


class Observation:
    def __init__(self, root, doc, model):
        self.root = root
        self.doc = doc
        self.identities = model["occurrences"]
        self.rules = model["validation"]
        self.paths = {member.Name: group.Name for group in doc.Objects if group.TypeId in GROUPS
                      for member in group.Group}

    def selector(self, identifier):
        path = self.identities.get(identifier, identifier)
        top, *children = path.split("/")
        return self.doc.getObject(top), ".".join(children) + ("." if children else "")

    def occurrence(self, identifier):
        top, child = self.selector(identifier)
        return top.getSubObject(child, 1) if top is not None else None

    def shape(self, identifier):
        top, child = self.selector(identifier)
        return Part.getShape(top, child)

    def ref(self, obj):
        file = Path(obj.Document.FileName).relative_to(self.root).as_posix()
        return f"{file}#{obj.Name}"

    def occurrence_path(self, obj):
        path = obj.Name
        visited = {path}
        while (parent := self.paths.get(path.split("/")[0])) is not None:
            require(parent not in visited, f"Cycle de conteneurs : {path}")
            visited.add(parent)
            path = f"{parent}/{path}"
        return path

    def pose(self, identifier):
        top, child = self.selector(identifier)
        obj = self.occurrence(identifier)
        require(obj is not None, f"Occurrence absente : {identifier}")
        if obj.TypeId == "App::Link":
            _, matrix, _ = Part.getShape(top, child, retType=2)
            return App.Placement(matrix)
        return obj.getGlobalPlacement()

    def world(self):
        reported, shapes = {}, {}
        excluded = {self.identities.get(name, name) for name in self.rules["non_physical"]}

        def record(path, visible, nested=False):
            top, child = self.selector(path)
            obj, occurrence_matrix = top.getSubObject(child, 1, App.Matrix(), True)
            shape = Part.getShape(top, child)
            definition = obj.getLinkedObject(True) if obj.TypeId == "App::Link" else obj
            children = obj.getSubObjects() if definition.TypeId in GROUPS else ()
            if not children and definition.TypeId in GROUPS:
                children = definition.getSubObjects()
            matrix = occurrence_matrix if nested and obj.TypeId != "App::Link" else self.pose(path).toMatrix()
            row = {"matrix": list(matrix.A), "definition": self.ref(definition),
                   "type": obj.TypeId, "visible": visible}
            if not shape.isNull() and shape.Solids:
                require(solid(shape), f"Solide invalide : {path}")
                row.update(shape_sha256=shape_hash(shape), bounds_mm=bounds(shape), volume_mm3=shape.Volume)
                if not children and visible and path not in excluded:
                    shapes[path] = shape
            reported[path] = row
            for child_name in children:
                member = child_name.rstrip(".")
                child_obj = top.getSubObject(child + child_name, 1)
                occurrence_visibility = obj.isElementVisible(member)
                shown = bool(occurrence_visibility) if occurrence_visibility >= 0 else child_obj.Visibility
                record(path + "/" + member, visible and shown, nested=True)

        for obj in self.doc.Objects:
            if obj.TypeId in GROUPS or not (obj.TypeId == "App::Link" or hasattr(obj, "getGlobalPlacement")):
                continue
            path = self.occurrence_path(obj)
            if path.startswith("Origin"):
                continue
            chain = [self.doc.getObject(name) for name in path.split("/")]
            record(path, all(item.Visibility for item in chain))
        require(0 < len(shapes) <= 128, "Nombre de solides hors périmètre")
        pairs = [{"pair": [left, right], **relation(shapes[left], shapes[right])}
                 for left, right in combinations(sorted(shapes), 2)]
        for rule in self.rules.get("forbidden_volumes", []):
            start, end = App.Vector(*rule["min_mm"]), App.Vector(*rule["max_mm"])
            span = end - start
            zone = Part.makeBox(span.x, span.y, span.z, start)
            pairs.extend({"pair": [path, rule["id"]], **relation(shape, zone)}
                         for path, shape in sorted(shapes.items()))
        return reported, pairs

    def contacts(self):
        def attached(obj):
            support = obj.AttachmentSupport
            return support[0][0] if obj.MapMode == "ObjectXY" and len(support) == 1 else None

        contacts = {}
        for obj in self.doc.Objects:
            if type(getattr(obj, "Proxy", None)).__name__ != "CableTerminal":
                continue
            identifier = obj.L2Id
            require(identifier and identifier not in contacts, "Identifiant de contact absent ou dupliqué")
            mate = getattr(obj, "L2MatedContact", None)
            connector = obj.ParentElement
            port = getattr(connector, "L2Port", None)
            rule = self.rules["ports"].get(port)
            equipment = self.occurrence(rule.get("attachment_equipment", rule["equipment"])) if rule else None
            current, visited = attached(obj), set()
            if current != connector:
                port = None
            while current is not None and current != equipment and current not in visited:
                if type(getattr(current, "Proxy", None)).__name__ != "ArchCableConnector" or current.L2Port != port:
                    break
                visited.add(current)
                current = attached(current)
            if not visited or current != equipment or equipment is None:
                port = None
            contacts[identifier] = {
                "object": self.ref(obj), "pin": str(obj.PinName), "port": port,
                "position_mm": point(obj.getGlobalPlacement().Base), "mate": getattr(mate, "L2Id", None),
                "mating_gap_mm": (obj.getGlobalPlacement().Base - mate.getGlobalPlacement().Base).Length if mate else None,
                "connected_wires": sorted(binding.split(":", 1)[-1] for binding in obj.ConnectedWires),
            }
        return contacts

    def conductors(self, route, cable):
        result = {}
        for wire in cable.L2Conductors:
            require(wire.L2Id and wire.L2Id not in result, "Identifiant de conducteur invalide")
            path = wire.Shape
            require(path.isValid() and len(path.Wires) == 1 and not path.Wires[0].isClosed(),
                    f"Faisceau invalide : {wire.Name}")
            vertices = path.Wires[0].OrderedVertexes
            endpoints = []
            for link, end in zip((wire.Vrtx_start, wire.Vrtx_end), (vertices[0], vertices[-1])):
                obj, fields = link
                require(len(fields) == 1 and fields[0].startswith("Vertex"), f"Ancrage absent : {wire.Name}")
                endpoint = obj.getSubObject(fields[0]).Point
                endpoints.append({"contact": getattr(obj, "L2Id", None), "gap_mm": (endpoint - end.Point).Length,
                                  "reciprocal": wire.Name in [ref.split(":", 1)[-1] for ref in obj.ConnectedWires]})
            result[wire.L2Id] = {"route": route, "object": self.ref(wire), "endpoints": endpoints,
                                 "length_mm": path.Length, "shape_sha256": shape_hash(path)}
        return result

    def native_datum(self, spec, equipment, attachment):
        identifier, name = spec["equipment"], spec["datum"]
        require(isinstance(name, str) and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name),
                f"Nom de repère natif invalide : {name}")
        owner = self.occurrence(identifier)
        definition = owner.getLinkedObject(True) if owner.TypeId == "App::Link" else owner
        if definition.TypeId == "App::Part":
            path = f"{self.identities.get(identifier, identifier)}/{name}"
            datum = self.occurrence(path)
            require(datum is not None and datum.TypeId == "PartDesign::CoordinateSystem" and
                    datum in definition.Group and datum.MapMode == "Deactivated" and not datum.AttachmentSupport,
                    f"Repère {path} sans placement rigide dans l’équipement.")
            frame = equipment.multiply(datum.Placement)
        else:
            path = name
            datum = self.occurrence(path)
            require(datum is not None and datum.TypeId == "PartDesign::CoordinateSystem" and owner == definition and
                    datum.MapMode == "ObjectXY" and tuple(datum.AttachmentSupport) == ((owner, ("",)),),
                    f"Repère {path} sans attache rigide à l’équipement.")
            frame = datum.getGlobalPlacement()
        require(datum != attachment, f"Le repère {path} provient de l’attache WireFlex.")
        return frame, {"datum": path, "datum_definition": self.ref(datum)}

    def ports(self):
        records = {}
        for identifier, spec in self.rules["ports"].items():
            equipment = self.pose(spec["equipment"])
            attachment_pose = self.pose(spec["frame"])
            frame, evidence = attachment_pose, {}
            if "datum" in spec:
                frame, evidence = self.native_datum(spec, equipment, self.occurrence(spec["frame"]))
                normal = App.Vector(*spec["outward_local"])
                tangent = App.Vector(*spec.get("tangent_local", spec["outward_local"]))
                require(abs(normal.Length - 1) <= 1e-8 and abs(tangent.Length - 1) <= 1e-8,
                        f"Normale ou tangente non unitaire : {identifier}")
                evidence.update(attachment_matrix=list(attachment_pose.toMatrix().A),
                                normal=point(frame.Rotation.multVec(normal)))
            else:
                tangent = App.Vector(0, 0, 1)
            records[identifier] = {
                "equipment_matrix": list(equipment.toMatrix().A),
                "frame": spec["frame"],
                "matrix": list(frame.toMatrix().A),
                "outward": point(frame.Rotation.multVec(tangent)),
                "mating_frames": {datum["path"]: list(self.pose(datum["path"]).toMatrix().A)
                                  for datum in spec.get("mating_frames", [])},
                **evidence,
            }
        return records

    def route(self, identifier, cable):
        path = Part.getShape(cable.Base)
        require(path.isValid() and len(path.Wires) == 1 and not path.Wires[0].isClosed(),
                f"Parcours ouvert unique requis : {identifier}")
        wire = path.Wires[0]
        start, end = (vertex.Point for vertex in (wire.OrderedVertexes[0], wire.OrderedVertexes[-1]))
        edges = []
        current = start
        for edge in wire.OrderedEdges:
            first, last = edge.FirstParameter, edge.LastParameter
            if (edge.valueAt(last) - current).Length < (edge.valueAt(first) - current).Length:
                first, last = last, first
            direction = 1 if first < last else -1
            curve = edge.Curve
            edge_start, current = edge.valueAt(first), edge.valueAt(last)
            edges.append({"type": type(curve).__name__, "length_mm": edge.Length,
                          "radius_mm": curve.Radius if isinstance(curve, Part.Circle) else None,
                          "start_mm": point(edge_start), "end_mm": point(current),
                          "start_tangent": point(edge.tangentAt(first) * direction),
                          "end_tangent": point(edge.tangentAt(last) * direction)})
        analytic = all(edge["type"] in {"Line", "LineSegment", "Circle"} for edge in edges)
        radii = [edge["radius_mm"] for edge in edges if edge["radius_mm"] is not None]
        diameter = cable.ProfilExterieur.DiametreExterieur.Value
        section = Part.Wire([Part.makeCircle(diameter / 2, start, App.Vector(*edges[0]["start_tangent"]))])
        swept = wire.makePipeShell([section], True, False)
        saved = self.shape(identifier)
        require(solid(swept) and solid(saved), f"Balayage ou gaine BRep invalide : {identifier}")
        common = overlap(swept, saved)
        return {
            "length_mm": wire.Length, "edges": edges, "endpoints_mm": [point(start), point(end)],
            "minimum_radius_mm": min(radii) if analytic and radii else None,
            "radius_evidence": "ANALYTIC" if analytic else "UNBOUNDED",
            "diameter_mm": diameter, "conductor_sections_mm2": list(getattr(cable, "B1_ConductorSections", [])),
            "saved_shape_sha256": shape_hash(saved), "sweep_shape_sha256": shape_hash(swept),
            "sweep_difference_mm3": abs(saved.Volume + swept.Volume - 2 * common),
            "native_endpoint_refs": [self.ref(getattr(cable.Base, key)[0]) for key in ("Vrtx_start", "Vrtx_end")],
        }

    def service(self, ports):
        records = []
        for spec in self.rules["service"]:
            name = spec.get("anchor") or spec.get("port") or spec["object"]
            if "anchor" in spec:
                frame = self.pose(name)
                origin = frame.multVec(App.Vector(*spec["offset_local_mm"]))
                axis = frame.Rotation.multVec(App.Vector(0, 0, 1))
                zone = Part.makeCylinder(spec["radius_mm"], spec["stroke_mm"], origin, axis)
            elif "port" in spec:
                port = ports[name]
                axis = App.Vector(*port["outward"])
                matrix = port["matrix"]
                origin = App.Vector(matrix[3], matrix[7], matrix[11]) + axis * spec.get("offset_mm", 0)
                zone = Part.makeCylinder(spec["radius_mm"], spec["stroke_mm"], origin, axis)
            else:
                zone = self.shape(name)
            for obstacle in spec["obstacles"]:
                records.append({"pair": [name, obstacle], "required_action": spec.get("required_action"),
                                "clearance_mm": spec["clearance_mm"],
                                **relation(zone, self.shape(obstacle))})
        return records

    def supports(self):
        records = {}
        for identifier, spec in self.rules["supports"].items():
            obj = self.occurrence(identifier)
            if obj is None:
                continue
            shape, carrier = self.shape(identifier), self.shape(spec["carrier"])
            touch = relation(shape, carrier)
            area = None
            if touch["intersection_mm3"] == 0:
                fused = shape.fuse(carrier)
                require(solid(fused), f"Union BRep invalide : {identifier}")
                area = max(0.0, (shape.Area + carrier.Area - fused.Area) / 2)
            records[identifier] = {
                "bearing_area_mm2": area, **touch,
                "anchor": self.occurrence_path(obj.B1_Anchor) if obj.B1_Anchor else None,
                "carrier": self.occurrence_path(obj.B1_Carrier) if obj.B1_Carrier else None,
                "retains": sorted(self.occurrence_path(item) for item in obj.B1_Retains),
                "retention_gaps_mm": {name: shape.distToShape(self.shape(name))[0] for name in spec["retains"]},
                "fasteners": [{**relation(self.shape(self.occurrence_path(item)), carrier),
                               "name": self.occurrence_path(item),
                               "support_gap_mm": shape.distToShape(self.shape(self.occurrence_path(item)))[0]}
                              for item in obj.B1_Fasteners],
            }
            if face_name := spec.get("carrier_face"):
                require(re.fullmatch(r"Face[1-9][0-9]*", face_name), f"Face porteuse invalide : {face_name}")
                face = getattr(carrier, face_name)
                require(isinstance(face.Surface, Part.Plane), f"Face porteuse non plane : {face_name}")
                normal = face.normalAt(*face.Surface.parameter(face.CenterOfMass))
                anchor = self.pose(self.occurrence_path(obj.B1_Anchor))
                vertical = anchor.Rotation.multVec(App.Vector(0, 0, 1))
                records[identifier]["carrier_face"] = {
                    "face": face_name, "gap_mm": face.distToShape(Part.Vertex(anchor.Base))[0],
                    "normal_error_deg": math.degrees(normal.getAngle(vertical)),
                    "bearing_area_mm2": sum(foot.common(face).Area for foot in shape.Faces
                                            if isinstance(foot.Surface, Part.Plane)),
                }
        return records

    def measure(self):
        occurrences, pairs = self.world()
        parents = {self.occurrence_path(obj): list(obj.getGlobalPlacement().toMatrix().A)
                   for obj in self.doc.Objects if obj.TypeId == "App::Part"}
        routes, conductors = {}, {}
        for identifier in self.rules["routes"]:
            cable = self.occurrence(identifier)
            routes[identifier] = self.route(identifier, cable)
            observed = self.conductors(identifier, cable)
            require(not conductors.keys() & observed.keys(), "Identifiant de conducteur partagé")
            conductors.update(observed)
        ports = self.ports()
        return dict(occurrences=occurrences, parent_matrices=parents, pairs=pairs, contacts=self.contacts(),
                    conductors=conductors, ports=ports, routes=routes,
                    service=self.service(ports), supports=self.supports())


def run(root, profile_path, result):
    profile_bytes = profile_path.read_bytes()
    profile = json.loads(profile_bytes)
    entry, expected = profile["entry"], profile["dependencies"]
    source = PROJECT / profile["source"]
    before = native_hashes(root, entry)
    source_before = native_hashes(source, entry)
    require(source_before == expected and before.keys() == expected.keys() and
            all(before[name] == expected[name] for name in expected if name != entry),
            "Fermeture ou dépendance hors profil de banc")
    result.update(entry=entry, model_id=profile["model_id"],
                  profile_sha256=hashlib.sha256(profile_bytes).hexdigest(),
                  inputs_sha256=before, source_sha256=source_before, environment=setup_cables())
    try:
        doc, documents, invalid = reopen(root, entry, before)
        result.update(documents=documents, invalid_objects=invalid)
        require(not invalid, "Objets natifs invalides")
        result.update(Observation(root, doc, profile["model"]).measure())
    finally:
        for name in reversed(list(App.listDocuments())):
            App.closeDocument(name)
        require(not App.listDocuments() and native_hashes(root, entry) == before and
                native_hashes(source, entry) == source_before and profile_path.read_bytes() == profile_bytes,
                "Sources, copie, profil ou fermeture modifiés durant la mesure")
        result.update(documents_closed=True, sources_unchanged=True, copy_unchanged=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--profile", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        root, output = private(args.root), private(args.output)
        profile = args.profile.absolute()
        require(profile in PROFILES and profile.resolve() == profile, "Profil de banc scellé requis")
        require(root.is_dir() and output.parent.is_dir() and not output.exists() and not output.is_relative_to(root),
                "Entrée privée existante et sortie neuve hors fermeture requises")
    except ERRORS as error:
        parser.exit(1, f"{error}\n")
    result = {"schema": SCHEMA, "pid": os.getpid(), "worker_id": uuid4().hex,
              "worker_sha256": guard.sha256(__file__), "status": "INCONCLUSIVE"}
    try:
        run(root, profile, result)
        result["status"] = "MEASURED"
    except ERRORS as error:
        result["error"] = str(error)
    payload = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    staged = output.with_name(f".{output.name}.{result['worker_id']}.tmp")
    with staged.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(payload)
    staged.rename(output)
    return 0 if result["status"] == "MEASURED" else 4


if __name__ == "__main__":
    raise SystemExit(main())
