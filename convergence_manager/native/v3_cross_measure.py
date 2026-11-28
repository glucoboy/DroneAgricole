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
from electromechanical_engine.contracts import decode
from convergence_manager.native.v3_spatial_contract import (
    C3_PROFILES, C4_PROFILES, OBSTACLE_OBJECT, box_limits, corridor_limits, nominal_axis, obstacle_spec,
)


SCHEMA = "v3.cross_measurement/1"
PROFILES = {
    PROJECT / "docs/electromechanical_v3/bench_b1_c4/profile.json",
    PROJECT / "docs/electromechanical_v3/bench_b1_workholding/profile.json",
    PROJECT / "docs/electromechanical_v3/bench_c1_coupled/profile.json",
    PROJECT / "docs/electromechanical_v3/bench_c1_coupled_secondary/profile.json",
    PROJECT / "docs/electromechanical_v3/bench_c2_multiharness/profile.json",
    PROJECT / "docs/electromechanical_v3/bench_c2_multiharness_secondary/profile.json",
    PROJECT / "docs/electromechanical_v3/bench_b2_variations.json",
}
SPATIAL_PROFILES = {PROJECT / path for path in C3_PROFILES + C4_PROFILES}
PROFILES.update(SPATIAL_PROFILES)
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
    gap = a.distToShape(b)[0]
    require(math.isfinite(gap) and gap >= 0, "Distance BRep invalide")
    return {"intersection_mm3": overlap(a, b), "gap_mm": gap}


class Observation:
    def __init__(self, root, doc, model, *, spatial_profile=False, contract=None, external=None):
        self.root = root
        self.doc = doc
        self.identities = model["occurrences"]
        self.rules = model["validation"]
        self.spatial_profile = spatial_profile
        self.contract, self.external = contract, external
        self.moving = {self.identities.get(identifier, identifier)
                       for device, companions in model.get("moving_with", {}).items()
                       for identifier in (device, *companions)}
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
        if self.spatial_profile:
            top, child = self.selector(identifier)
            _, world_matrix, _ = Part.getShape(top, child, retType=2)
            local = cable.Placement.inverse().toMatrix()
            path = cable.Base.Shape.copy().transformShape(world_matrix.multiply(local), True, True)
        else:
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
        record = {
            "length_mm": wire.Length, "edges": edges, "endpoints_mm": [point(start), point(end)],
            "minimum_radius_mm": min(radii) if analytic and radii else None,
            "radius_evidence": "ANALYTIC" if analytic else "UNBOUNDED",
            "diameter_mm": diameter, "conductor_sections_mm2": list(getattr(cable, "B1_ConductorSections", [])),
            "saved_shape_sha256": shape_hash(saved), "sweep_shape_sha256": shape_hash(swept),
            "sweep_difference_mm3": abs(saved.Volume + swept.Volume - 2 * common),
            "native_endpoint_refs": [self.ref(getattr(cable.Base, key)[0]) for key in ("Vrtx_start", "Vrtx_end")],
        }
        if self.spatial_profile:
            record.update(axis_bounds_mm=bounds(wire), axis_sha256=shape_hash(wire))
        if self.contract is not None:
            rule = self.contract["routes"][identifier]
            axis, coordinate = nominal_axis(rule["nominal_plane"])
            corridors = rule["corridors_mm"]
            require(set(rule) == {"corridors_mm", "nominal_plane"} and 0 < len(corridors) <= 32,
                    "Corridor spatial hors contrat")
            tolerance = self.rules["tolerances"]["position_mm"]
            boxes = [root_box(*corridor_limits(limits, tolerance)) for limits in corridors]
            union = boxes[0] if len(boxes) == 1 else boxes[0].fuse(boxes[1:])
            require(solid(union), "Union de corridors non mesurable")
            covered = wire.common(union)
            require(covered.isNull() or covered.isValid(), "Intersection corridor/axe non finalisée")
            covered_mm = sum(edge.Length for edge in covered.Edges)
            require(math.isfinite(covered_mm) and covered_mm <= wire.Length + self.rules["tolerances"]["position_mm"],
                    "Longueur d'axe couverte non mesurable")
            record.update(outside_corridor_mm=max(0, wire.Length - covered_mm), nominal_plane=rule["nominal_plane"],
                          vertex_departure_mm=max(abs(vertex.Point[axis] - coordinate) for vertex in wire.Vertexes))
        return record

    def service(self, ports):
        records, volumes, coverage = [], [], {}
        for spec in self.rules["service"]:
            name = spec.get("anchor") or spec.get("port") or spec["object"]
            if "anchor" in spec:
                frame = self.pose(spec.get("follow_support", name))
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
            if expected := spec.get("required_box_mm"):
                require(name not in coverage, f"Balayage de service dupliqué : {name}")
                remainder = root_box(*expected).cut(zone)
                require(remainder.isNull() or remainder.isValid(), f"Couverture de service non mesurable : {name}")
                coverage[name] = remainder.Volume
            if self.spatial_profile:
                owner = self.rules["ports"][name]["equipment"] if "port" in spec else name
                owner = self.identities.get(owner, owner)
                volumes.append({"id": name, "bounds_mm": bounds(zone), "obstacles": spec["obstacles"],
                                "clearance_mm": spec["clearance_mm"], "required_action": spec.get("required_action"),
                                "follows_device": any(owner == path or owner.startswith(path + "/") for path in self.moving)})
            obstacles = list(spec["obstacles"])
            if self.external is not None and self.doc.getObject(OBSTACLE_OBJECT) is not None:
                obstacles.append(OBSTACLE_OBJECT)
            for obstacle in obstacles:
                records.append({"pair": [name, obstacle], "required_action": spec.get("required_action"),
                                "clearance_mm": spec["clearance_mm"],
                                **relation(zone, self.shape(obstacle))})
        return records, volumes, coverage

    def external_obstacle(self, spec, require_absent):
        identifier, low, high = obstacle_spec(spec)
        reference = root_box(low, high)
        obj = self.doc.getObject(OBSTACLE_OBJECT)
        if require_absent:
            require(obj is None, "La candidate T1 contient déjà l’obstacle externe")
            obstacle, presence, difference = reference, "HYPOTHETICAL", None
        else:
            require(obj is not None and obj.TypeId == "Part::Feature" and obj.Visibility and
                    obj in self.doc.RootObjects and getattr(obj, "C3ExternalId", None) == identifier,
                    "Occurrence native de l’obstacle absente ou divergente")
            obstacle, presence = self.shape(OBSTACLE_OBJECT), "SAVED_NATIVE"
            require(solid(obstacle) and len(obstacle.Solids) == 1, "Obstacle sauvegardé sans solide unique valide")
            intersection = overlap(reference, obstacle)
            difference = abs(reference.Volume + obstacle.Volume - 2 * intersection)
            tolerances = self.rules["tolerances"]
            require(difference <= tolerances["volume_mm3"] and all(
                abs(actual - expected) <= tolerances["position_mm"]
                for corner, expected_corner in zip(bounds(obstacle), (low, high), strict=True)
                for actual, expected in zip(corner, expected_corner, strict=True)),
                "Obstacle sauvegardé différent du volume gelé")
        return {"id": identifier, "presence": presence, "bounds_mm": bounds(obstacle),
                "symmetric_difference_mm3": difference,
                "harnesses": {route: relation(self.shape(route), obstacle) for route in self.rules["routes"]}}

    def support_zone(self):
        selected = self.contract["support"]
        patch = selected.get("offset_patch_mm")
        require(set(selected) == ({"id", "occurrence", "anchor_zone", "offset_patch_mm", "min_carrier_thickness_mm"} if patch is not None
                                  else {"id", "occurrence", "anchor_zone"}), "Contrat d’ancrage mal formé")
        spec = self.rules["supports"][selected["occurrence"]]
        low, high = box_limits(selected["anchor_zone"], allow_surface=True)
        anchor_pose = self.pose(spec["anchor"])
        anchor = point(anchor_pose.Base)
        tolerance = self.rules["tolerances"]["position_mm"]
        inside = all(left - tolerance <= value <= right + tolerance for left, value, right in zip(low, anchor, high))
        measured_patch = {}
        if patch is not None:
            patch_low, patch_high = box_limits(patch, allow_surface=True)
            support_position = self.pose(selected["occurrence"]).Base
            offset = point(anchor_pose.inverse().multVec(support_position))
            inside = inside and all(left - tolerance <= value <= right + tolerance
                                    for left, value, right in zip(patch_low, offset, patch_high, strict=True))
            carrier = self.shape(spec["carrier"])
            normal = anchor_pose.Rotation.multVec(App.Vector(0, 0, 1))
            ray = Part.makeLine(support_position - normal * carrier.BoundBox.DiagonalLength, support_position + normal)
            intersection = ray.common(carrier)
            thickness = sum(edge.Length for edge in intersection.Edges)
            minimum = selected["min_carrier_thickness_mm"]
            require(type(minimum) in (int, float) and math.isfinite(minimum) and minimum > 0,
                    "Épaisseur du porteur hors contrat")
            inside = inside and thickness + tolerance >= minimum
            measured_patch = {"offset_patch_mm": patch, "observed_offset_mm": offset,
                              "observed_support_root_mm": point(support_position),
                              "carrier_thickness_mm": thickness, "min_carrier_thickness_mm": minimum}
        return {"id": selected["id"], "occurrence": selected["occurrence"], "anchor_mm": anchor,
                "bounds_mm": [low, high], "status": "PASS" if inside else "FAIL", **measured_patch}

    def supports(self):
        records = {}
        for identifier, spec in self.rules["supports"].items():
            obj = self.occurrence(identifier)
            if obj is None:
                continue
            shape, carrier = self.shape(identifier), self.shape(spec["carrier"])
            touch = relation(shape, carrier)
            area = None
            if spec.get("selected_only") and touch["gap_mm"] > self.rules["tolerances"]["distance_mm"]:
                area = 0.0
            elif touch["intersection_mm3"] == 0:
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

    def interference_classification(self, pairs, supports):
        thresholds = self.rules["tolerances"]
        epsilon, distance = thresholds["volume_mm3"], thresholds["distance_mm"]
        paths = lambda names: tuple(sorted(self.identities.get(name, name) for name in names))
        indexed = {tuple(row["pair"]): row for row in pairs}
        cross = self.rules["cross_harness"]
        cable_pair = paths(cross["harnesses"])
        require(len(cable_pair) == 2 and len(set(cable_pair)) == 2 and cable_pair in indexed,
                "Paire de faisceaux indépendante absente")
        interactions = indexed[cable_pair]
        clearance = cross["minimum_clearance_mm"]
        if self.contract is not None:
            spatial_clearance = self.contract["minimum_clearance_mm"]
            require(type(spatial_clearance) in (int, float) and math.isfinite(spatial_clearance) and spatial_clearance > 0,
                    "Garde inter-faisceaux spatiale non mesurable")
            clearance = max(clearance, spatial_clearance)
        require(math.isfinite(clearance) and clearance > 0, "Seuil de garde inter-faisceaux absent")
        cross_pass = interactions["gap_mm"] >= clearance - distance and interactions["intersection_mm3"] <= epsilon
        allowed, declared, engagement = set(), set(), []
        for rule in self.rules["allowed_interferences"]:
            name = rule["support"]
            spec = self.rules["supports"][name]
            pair = paths(rule["parts"])
            require(pair not in declared and pair in indexed and pair != cable_pair and rule["reason"].strip()
                    and rule["role"] == "FASTENER_CARRIER_ENGAGEMENT"
                    and pair in {paths([spec["carrier"], stud]) for stud in spec["fasteners"]}
                    and 0 < rule["min_volume_mm3"] <= rule["max_volume_mm3"],
                    "Autorité de recoupement sans paire mécanique scellée")
            declared.add(pair)
            measurement = indexed[pair]
            volume = measurement["intersection_mm3"]
            if volume <= epsilon:
                continue
            support = supports[name]
            fasteners = {stud["name"]: stud for stud in support["fasteners"]}
            carrier = self.identities[spec["carrier"]]
            engaged_stud = next(stud for stud in pair if stud != carrier)
            fastener = fasteners.get(engaged_stud)
            status = (support["bearing_area_mm2"] is not None
                      and support["bearing_area_mm2"] >= spec["min_contact_area_mm2"]
                      and support["gap_mm"] <= distance and support["anchor"] == self.identities[spec["anchor"]]
                      and support["carrier"] == carrier and tuple(support["retains"]) == paths(spec["retains"])
                      and all(gap <= spec["retention_max_gap_mm"] for gap in support["retention_gaps_mm"].values())
                      and fastener is not None and fastener["support_gap_mm"] <= distance
                      and abs(fastener["intersection_mm3"] - volume) <= epsilon
                      and rule["min_volume_mm3"] - epsilon <= volume <= rule["max_volume_mm3"] + epsilon)
            engagement.append({**measurement, "status": "PASS" if status else "FAIL", "role": rule["role"],
                               "support": name, "authority_reason": rule["reason"],
                               "min_volume_mm3": rule["min_volume_mm3"], "max_volume_mm3": rule["max_volume_mm3"],
                               "bearing_area_mm2": support["bearing_area_mm2"], "fastener": fastener})
            if status:
                allowed.add(pair)
        forbidden = [row for pair, row in indexed.items() if pair not in allowed and row["intersection_mm3"] > epsilon]
        active = {row["support"] for row in engagement if row["status"] == "PASS"}
        active_actions = {rule["required_action"] for rule in self.rules["allowed_interferences"] if rule["support"] in active}
        contacts = {}
        for rule in self.rules["allowed_surface_contacts"]:
            pair = paths(rule["parts"])
            require(pair not in contacts and pair in indexed and pair != cable_pair and rule["reason"].strip(),
                    "Contact de surface sans paire unique mesurable")
            if not rule.get("required_action") or rule["required_action"] in active_actions:
                contacts[pair] = rule
        measured, unexpected = [], []
        for pair, row in indexed.items():
            if row["intersection_mm3"] > epsilon or row["gap_mm"] > distance:
                continue
            rule = contacts.get(pair)
            if rule is None:
                unexpected.append(row)
            else:
                measured.append({**row, "role": rule["role"], "authority_reason": rule["reason"]})
        return {"status": "PASS" if not forbidden and not unexpected and cross_pass else "FAIL",
                "maximum_forbidden_interference_mm3": max((row["intersection_mm3"] for row in forbidden), default=0),
                "forbidden_interferences": forbidden, "authorized_engagements": engagement,
                "surface_contacts": measured, "unexpected_surface_contacts": unexpected,
                "cross_harness": {**interactions, "minimum_clearance_mm": clearance,
                                  "status": "PASS" if cross_pass else "FAIL"}}

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
        supports = self.supports()
        service, volumes, coverage = self.service(ports)
        classification = {"interference_classification": self.interference_classification(pairs, supports)} if "cross_harness" in self.rules else {}
        if self.spatial_profile:
            classification["service_volumes"] = volumes
        if coverage:
            classification["service_coverage_missing_mm3"] = coverage
        if self.contract is not None:
            classification["spatial_support_zone"] = self.support_zone()
        return dict(occurrences=occurrences, parent_matrices=parents, pairs=pairs, contacts=self.contacts(),
                    conductors=conductors, ports=ports, routes=routes,
                    service=service, supports=supports, **classification)


def root_box(low, high):
    origin = App.Vector(*low)
    extent = App.Vector(*high) - origin
    return Part.makeBox(extent.x, extent.y, extent.z, origin)


def run(root, profile_path, result, *, contract=None, external=None, expected_entry=None, require_absent=False):
    profile_bytes = profile_path.read_bytes()
    profile = json.loads(profile_bytes)
    entry, expected = profile["entry"], profile["dependencies"]
    source = PROJECT / profile["source"]
    before = native_hashes(root, entry)
    source_before = native_hashes(source, entry)
    require(source_before == expected and before.keys() == expected.keys() and
            all(before[name] == expected[name] for name in expected if name != entry),
            "Fermeture ou dépendance hors profil de banc")
    require(expected_entry is None or expected_entry == before[entry], "SHA de racine native différent du candidat évalué")
    spatial_profile = profile_path in SPATIAL_PROFILES
    if contract is not None:
        require(spatial_profile and set(contract) == {"routes", "minimum_clearance_mm", "support"} and
                set(contract["routes"]) == set(profile["model"]["validation"]["routes"]) and
                ("offset_patch_mm" in contract["support"]) ==
                (profile_path.relative_to(PROJECT).as_posix() in C4_PROFILES),
                "Contrat spatial hors profil autorisé")
    result.update(entry=entry, model_id=profile["model_id"],
                  profile_sha256=hashlib.sha256(profile_bytes).hexdigest(),
                  inputs_sha256=before, source_sha256=source_before, environment=setup_cables())
    try:
        doc, documents, invalid = reopen(root, entry, before)
        result.update(documents=documents, invalid_objects=invalid)
        require(not invalid, "Objets natifs invalides")
        observation = Observation(root, doc, profile["model"], spatial_profile=spatial_profile,
                                  contract=contract, external=external)
        if external is not None:
            result["external_obstacle"] = observation.external_obstacle(external, require_absent)
        elif spatial_profile:
            require(doc.getObject(OBSTACLE_OBJECT) is None, "Obstacle natif sans contrat externe")
        result.update(observation.measure())
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
    parser.add_argument("--spatial-contract", type=Path)
    parser.add_argument("--external-obstacle", type=Path)
    parser.add_argument("--expected-entry-sha256")
    parser.add_argument("--require-absent", action="store_true")
    args = parser.parse_args()
    try:
        root, output = private(args.root), private(args.output)
        profile = args.profile.absolute()
        require(profile in PROFILES and profile.resolve() == profile, "Profil de banc scellé requis")
        require(root.is_dir() and output.parent.is_dir() and not output.exists() and not output.is_relative_to(root),
                "Entrée privée existante et sortie neuve hors fermeture requises")
        require(not args.require_absent or args.external_obstacle is not None, "Contrat d’obstacle hypothétique absent")
        require(not (args.spatial_contract or args.external_obstacle) or (profile in SPATIAL_PROFILES and
                re.fullmatch(r"[0-9a-f]{64}", args.expected_entry_sha256 or "")),
                "Mesure C.3 avec contrat exigeant un profil scellé et la SHA de racine")
        paths = {"contract": args.spatial_contract, "external": args.external_obstacle}
        sealed = {}
        for name, path in paths.items():
            if path is not None:
                path = private(path)
                require(path.is_file() and path.stat().st_nlink == 1 and not path.is_relative_to(root),
                        "Entrée C.3 en fermeture ou partagée")
                sealed[name] = path, path.read_bytes()
    except ERRORS as error:
        parser.exit(1, f"{error}\n")
    result = {"schema": SCHEMA, "pid": os.getpid(), "worker_id": uuid4().hex,
              "worker_sha256": guard.sha256(__file__), "status": "INCONCLUSIVE"}
    try:
        inputs = {name: decode(path.name, data) for name, (path, data) in sealed.items()}
        run(root, profile, result, **inputs, expected_entry=args.expected_entry_sha256, require_absent=args.require_absent)
        for name, (path, data) in sealed.items():
            require(path.read_bytes() == data, "Entrée C.3 modifiée durant la mesure")
            result[f"{name}_sha256"] = hashlib.sha256(data).hexdigest()
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
