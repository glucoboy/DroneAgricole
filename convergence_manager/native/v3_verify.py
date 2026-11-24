"""Measure a private, re-opened L5 XLink candidate independently of its builder."""

from __future__ import annotations

import argparse
import itertools
import json
import math
import os
from pathlib import Path
import re
import sys
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from electromechanical_engine.freecad import PROJECT, guard
from electromechanical_engine.v3_native import serialized_dependencies, target_placement
from electromechanical_engine.xlink_native import collect, measurement_identity, publish, route_measurement


NATIVE_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
GEOMETRY_ERRORS = (AttributeError, IndexError, KeyError, OSError, RuntimeError, TypeError, ValueError)
WORKER_SCHEMA = "v3.native_validation/1"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def finite(value, lower=0):
    require(type(value) in (int, float) and math.isfinite(value) and value >= lower,
            f"Mesure ou tolérance invalide : {value!r}")
    return value


def file_hashes(root, entry, expected):
    paths = guard.dependencies(root, [entry])
    require(len(paths) <= 128, "Fermeture XLink hors budget du banc")
    files = {}
    for path in paths:
        require(path.suffix.lower() == ".fcstd" and path.stat().st_nlink == 1,
                f"Dépendance hébergée ou partagée : {path}")
        files[path.relative_to(root).as_posix()] = guard.sha256(path)
    require(files == expected, "Fermeture XLink différente des empreintes de mesure")
    return files


def summarize(*statuses):
    for state in ("FAIL", "INCONCLUSIVE", "NOT_RUN"):
        if state in statuses:
            return state
    return "PASS"


def proof(identifier, status, details):
    return {"id": identifier, "status": status, "details": details}


class Measurement:
    def __init__(self, native, doc, inventory, shapes, objects, job):
        self.native = native
        self.app, self.part = native.App, native.Part
        self.doc, self.rows, self.shapes, self.objects = doc, inventory, shapes, objects
        self.entry = job["entry"]
        self.model = job["model"]
        self.rules = self.model.get("validation", {})
        self.stage = job["stage"]
        self.actions = job["actions"]
        self.baseline = job.get("baseline", {})
        tolerances = self.rules.get("tolerances", {})
        self.position = finite(tolerances.get("position_mm", 1e-5), 1e-10)
        self.angle = finite(tolerances.get("direction_deg", 0.01), 1e-9)
        self.volume = finite(tolerances.get("volume_mm3", 1e-6))
        self.distance = finite(tolerances.get("distance_mm", 1e-6))

    def key(self, identifier):
        path = self.model["occurrences"].get(identifier, identifier)
        require(isinstance(path, str) and all(NATIVE_NAME.fullmatch(part) for part in path.split("/")),
                f"Chemin d’occurrence natif invalide : {path!r}")
        return f"{self.entry}#{path}"

    def occurrence(self, identifier):
        key = self.key(identifier)
        if key in self.objects:
            return self.objects[key]
        return self.instance(identifier)

    def instance(self, identifier):
        path = self.key(identifier).split("#", 1)[1].split("/")
        top = self.doc.getObject(path[0])
        require(top is not None, f"Objet natif absent : {identifier}")
        subname = "".join(part + "." for part in path[1:])
        obj = top.getSubObject(subname, 1)
        require(obj is not None, f"Occurrence non résolue : {identifier}")
        return obj

    def transform(self, identifier, records=None):
        key = self.key(identifier)
        row = self.rows.get(key, {}) if records is None else records[key]
        if row.get("matrix"):
            matrix = self.app.Matrix()
            matrix.A = tuple(row["matrix"])
            if row["type"] == "App::Link" and not row["terminal_shape"]:
                matrix = matrix.multiply(target_placement(self.instance(identifier), self.app))
            return self.app.Placement(matrix)
        return self.instance(identifier).getGlobalPlacement()

    def shape(self, identifier):
        key = self.key(identifier)
        if key in self.shapes:
            return self.shapes[key]
        path = key.split("#", 1)[1].split("/")
        top = self.doc.getObject(path[0])
        require(top is not None, f"Objet de mesure absent : {identifier}")
        subname = ".".join(path[1:]) + "." if len(path) > 1 else ""
        return self.part.getShape(top, subname)

    def pose(self, spec):
        if isinstance(spec, list):
            require(len(spec) == 16 and all(math.isfinite(value) for value in spec),
                    "Matrice de pose 4×4 finie attendue")
            matrix = self.app.Matrix()
            matrix.A = tuple(spec)
            return self.app.Placement(matrix)
        return self.app.Placement(self.native.vector(spec["translation_mm"]),
                                  self.app.Rotation(*spec["rotation_xyzw"]))

    def pose_error(self, expected, observed):
        delta = expected.inverse().multiply(observed)
        position = delta.Base.Length
        degrees = math.degrees(delta.Rotation.Angle)
        direction = min(degrees, 360 - degrees)
        return {"status": "PASS" if position <= self.position and direction <= self.angle else "FAIL",
                "position_error_mm": position, "direction_error_deg": direction,
                "observed_matrix": list(observed.toMatrix().A), "expected_matrix": list(expected.toMatrix().A)}

    def native_datum(self, spec):
        name = spec["datum"]
        require(isinstance(name, str) and NATIVE_NAME.fullmatch(name), "Nom de repère natif invalide")
        owner = self.instance(spec["equipment"])
        definition = owner.getLinkedObject(True) if owner.TypeId == "App::Link" else owner
        grouped = definition.TypeId == "App::Part"
        equipment_path = self.key(spec["equipment"]).split("#", 1)[1]
        path = f"{equipment_path}/{name}" if grouped else name
        datum = self.instance(path)
        independent = datum.TypeId == "PartDesign::CoordinateSystem" and datum != self.instance(spec["frame"])
        if grouped:
            independent &= (datum in definition.Group and datum.MapMode == "Deactivated"
                            and not datum.AttachmentSupport)
        else:
            independent &= (owner == definition and datum.MapMode == "ObjectXY"
                            and tuple(datum.AttachmentSupport) == ((owner, ("",)),))
        return path, self.transform(path), independent

    def independent_frames(self):
        ports = {}
        for identifier, spec in self.rules.get("ports", {}).items():
            equipment = self.transform(spec["equipment"])
            expected = equipment.multiply(self.pose(spec["local_pose"]))
            measured, datum_path = expected, None
            measurements = []
            if "datum" in spec:
                datum_path, measured, independent = self.native_datum(spec)
                measurements.append({"status": "PASS" if independent else "FAIL", "native_datum": datum_path})
                measurements.append(self.pose_error(expected, measured))
            normal = measured.Rotation.multVec(self.native.vector(spec["outward_local"]))
            axis = measured.Rotation.multVec(self.native.vector(spec.get("tangent_local", spec["outward_local"])))
            require(abs(normal.Length - 1) < 1e-7 and abs(axis.Length - 1) < 1e-7,
                    f"Normale ou tangente de port non unitaire : {identifier}")
            if "frame" in spec:
                measurements.append(self.pose_error(measured, self.transform(spec["frame"])))
            else:
                # A datum-less model can establish a port on a native planar face.
                face_matches = []
                vertex = self.part.Vertex(expected.Base)
                for face in self.shape(spec["equipment"]).Faces:
                    if isinstance(face.Surface, self.part.Plane) and face.distToShape(vertex)[0] <= self.position:
                        uv = face.Surface.parameter(expected.Base)
                        face_matches.append(math.degrees(face.normalAt(*uv).getAngle(axis)))
                suitable = sum(angle <= self.angle for angle in face_matches)
                measurements.append({"status": "PASS" if suitable == 1 else "FAIL",
                                     "matching_planar_faces": suitable, "face_errors_deg": face_matches})
            for datum in spec.get("mating_frames", []):
                expected_datum = equipment.multiply(self.pose(datum["local_pose"]))
                measurements.append(self.pose_error(expected_datum, self.transform(datum["path"])))
            if pair := spec.get("mating_pair"):
                measurements.append(self.pose_error(self.transform(pair[0]), self.transform(pair[1])))
            if keying := spec.get("keying"):
                observed_keys = [getattr(self.instance(path), keying["property"], None)
                                 for path in keying["occurrences"]]
                measurements.append({"status": "PASS" if observed_keys == keying["expected"] else "FAIL",
                                     "keying": observed_keys})
            ports[identifier] = {
                "status": summarize(*(row["status"] for row in measurements)),
                "origin_mm": self.native.coordinates(measured.Base),
                "outward": self.native.coordinates(axis), "measurements": measurements,
            }
            if datum_path is not None:
                ports[identifier].update(matrix=list(measured.toMatrix().A), datum=datum_path,
                                         normal=self.native.coordinates(normal))
        return ports

    def contact_checks(self):
        mapping = {}
        for key, obj in self.objects.items():
            terminal = self.rows[key].get("native_terminal", {}).get("id")
            if terminal:
                require(terminal not in mapping, f"Contact natif non bijectif : {terminal}")
                mapping[terminal] = (self.rows[key].get("contact"), obj)
        contacts = {}
        for identifier, spec in self.rules.get("contacts", {}).items():
            plug_record, plug = mapping.get(identifier, (None, None))
            socket_record, socket = mapping.get(spec["receptacle"], (None, None))
            errors = ["contact_missing"] if not (plug_record and socket_record and plug and socket) else []
            gap = None
            if not errors:
                gap = (plug.getGlobalPlacement().Base - socket.getGlobalPlacement().Base).Length
                if gap > self.position or plug.L2MatedContact != socket:
                    errors.append("mating_contact_divergent")
                if any(str(item.PinName) != str(spec["pin"]) for item in (plug, socket)):
                    errors.append("pinout_divergent")
                if any(item["port"] != spec["port"] for item in (plug_record, socket_record)):
                    errors.append("port_attachment_divergent")
            contacts[identifier] = {"status": "FAIL" if errors else "PASS", "errors": errors,
                                    "mating_gap_mm": gap, "receptacle": spec["receptacle"],
                                    "observed_pin": str(plug.PinName) if plug is not None else None}
        expected = set(contacts) | {spec["receptacle"] for spec in self.rules.get("contacts", {}).values()}
        return contacts, sorted(mapping.keys() - expected)

    def conductor_checks(self):
        expected = self.rules.get("nets", {})
        observed = {}
        bindings = {}
        route_ids = set(self.rules.get("routes", {}))
        for route_id in route_ids:
            jacket = self.occurrence(route_id)
            for wire in getattr(jacket, "L2Conductors", []):
                wire_id = getattr(wire, "L2Id", None)
                if not wire_id or wire_id in observed:
                    raise ValueError("Identité de conducteur native absente ou dupliquée")
                links = [wire.Vrtx_start, wire.Vrtx_end]
                targets = [getattr(link[0], "L2Id", None) if link else None for link in links]
                checks = [link and len(link[1]) == 1 and link[1][0].startswith("Vertex") and
                          type(getattr(link[0], "Proxy", None)).__name__ == "CableTerminal" and
                          any(binding.split(":", 1)[-1] == wire.Name for binding in link[0].ConnectedWires)
                          for link in links]
                path = wire.Shape
                mismatch = None
                if all(checks) and path.isValid() and len(path.Wires) == 1 and not path.Wires[0].isClosed():
                    vertices = path.Wires[0].OrderedVertexes
                    points = [link[0].getSubObject(link[1][0]).Point for link in links]
                    mismatch = max((reference - vertex.Point).Length
                                   for reference, vertex in zip(points, [vertices[0], vertices[-1]]))
                spec = expected.get(wire_id, {})
                status = ("PASS" if mismatch is not None and mismatch <= self.position
                          and set(targets) == set(spec.get("contacts", [])) and route_id == spec.get("route")
                          else "FAIL")
                observed[wire_id] = {"status": status, "contacts": targets, "route": route_id,
                                     "endpoint_error_mm": mismatch, "reciprocal_links": bool(all(checks))}
                for target in targets:
                    if target is not None:
                        bindings.setdefault(target, set()).add(wire.Name)
        missing = sorted(expected.keys() - observed.keys())
        nc = sorted({pin for row in observed.values() for pin in row["contacts"]
                     if pin in self.rules.get("nc", [])})
        domains = self.rules.get("isolated_domains", [])
        ports, contacts = self.rules.get("ports", {}), self.rules.get("contacts", {})
        bridges = []
        for identifier, row in observed.items():
            ends = [ports.get(contacts.get(pin, {}).get("port"), {}).get("domain") for pin in row["contacts"]]
            if any(set(ends) == set(pair) for pair in domains):
                bridges.append(identifier)
        unexpected = {}
        for key, obj in self.objects.items():
            terminal = self.rows[key].get("native_terminal", {}).get("id")
            if terminal and type(getattr(obj, "Proxy", None)).__name__ == "CableTerminal":
                native_wires = {binding.split(":", 1)[-1] for binding in obj.ConnectedWires}
                undeclared = native_wires - bindings.get(terminal, set())
                if undeclared:
                    unexpected[terminal] = sorted(undeclared)
        return {"status": summarize(*[row["status"] for row in observed.values()],
                                    "FAIL" if missing or nc or bridges or unexpected else "PASS",
                                    "PASS" if expected else "INCONCLUSIVE"),
                "conductors": observed, "missing": missing, "nc_connected": nc, "isolation_bridges": bridges,
                "undeclared_terminal_wires": unexpected}

    def routes(self, ports):
        result = {}
        for identifier, spec in self.rules.get("routes", {}).items():
            key = self.key(identifier)
            cable = self.occurrence(identifier)
            if type(getattr(cable, "Proxy", None)).__name__ != "ArchCable":
                result[identifier] = {"status": "INCONCLUSIVE", "reason": "Câble Workbench natif absent"}
                continue
            start, end = (ports[name] for name in spec["ports"])
            criteria = {"start_mm": start["origin_mm"], "end_mm": end["origin_mm"],
                        "start_axis": start["outward"], "end_axis": end["outward"],
                        "minimum_radius_mm": spec["minimum_radius_mm"],
                        "position_tolerance_mm": self.position, "tangent_tolerance_deg": self.angle}
            observation = route_measurement(self.rows[key], cable, criteria)
            proxy = type(getattr(cable.Base, "Proxy", None)).__name__
            frames = [self.rules["ports"][port].get("frame") for port in spec["ports"]]
            endpoints = [getattr(cable.Base, prop, None) for prop in ("Vrtx_start", "Vrtx_end")]
            bound = all(
                frame is None or link and link[0] == self.instance(frame) and list(link[1]) == ["Vertex1"]
                for frame, link in zip(frames, endpoints))
            saved_shape = cable.Shape.copy()
            previous_solid = self.native.geometry.shape_sha256(cable.Shape)
            regenerated = self.native.geometry.rebuild_cable_in_isolated_document(cable.Document, cable)
            fresh_solid = self.native.geometry.shape_sha256(cable.Shape)
            # Equivalent reconstructions need not serialize OCC entities in
            # the same order. Compare their actual occupied material.
            rebuilt_shape = cable.Shape
            difference = None
            if regenerated["status"] == "pass":
                difference = saved_shape.cut(rebuilt_shape).Volume + rebuilt_shape.cut(saved_shape).Volume
                finite(difference)
            shape_ok = difference is not None and difference <= self.volume
            diameter = cable.ProfilExterieur.DiametreExterieur.Value
            expected_sections = spec.get("conductor_sections_mm2")
            native_sections = list(getattr(cable, "B1_ConductorSections", []))
            size_ok = abs(diameter - spec["diameter_mm"]) <= self.position and (
                expected_sections is None or expected_sections == native_sections)
            length_ok = True
            if "minimum_length_mm" in spec or "maximum_length_mm" in spec:
                lower = finite(spec["minimum_length_mm"])
                upper = finite(spec["maximum_length_mm"], lower)
                length = observation.get("length_mm")
                length_ok = length is not None and lower - self.distance <= length <= upper + self.distance
                observation["native_length_bounds_mm"] = [lower, upper]
            observation.update(diameter_mm=diameter, conductor_sections_mm2=native_sections,
                               cache_cleared_rebuild=regenerated, saved_brep_sha256=previous_solid,
                               rebuilt_brep_sha256=fresh_solid, symmetric_difference_mm3=difference,
                               native_ends_bound=bool(bound), route_proxy=proxy, scope="NOMINAL_SAVED_GEOMETRY",
                               status=summarize(native_status(observation["status"]),
                                                native_status(regenerated["status"]),
                                                "PASS" if size_ok and bound and shape_ok and length_ok and
                                                proxy in {"Wire", "WireFlex", "_Wire"} else "FAIL"))
            result[identifier] = observation
        return result

    def pairs(self):
        allowed = {}
        for rule in self.rules.get("allowed_interferences", []):
            pair = tuple(sorted(self.key(identifier) for identifier in rule["parts"]))
            require(len(pair) == 2 and pair[0] != pair[1] and pair not in allowed and rule["reason"].strip(),
                    "Autorisation d’interférence ambiguë")
            allowed[pair] = rule
        excluded = {self.key(identifier) for identifier in self.rules.get("non_physical", [])}
        shapes = sorted(self.shapes.keys() - excluded)
        require(0 < len(shapes) <= 128, "Nombre de solides du banc hors budget")
        result = []
        for left, right in itertools.combinations(shapes, 2):
            permission = allowed.get((left, right))
            limit = self.volume + (finite(permission["max_volume_mm3"]) if permission else 0)
            report = self.native.geometry.inspect_pair(self.shapes[left], self.shapes[right], left, right,
                                                       volume_tolerance_mm3=limit)
            if permission:
                report["sealed_overlap_permission"] = permission
            result.append(report)
        for bounds in self.rules.get("forbidden_volumes", []):
            lower = self.native.vector(bounds["min_mm"])
            extent = self.native.vector(bounds["max_mm"]) - lower
            zone = self.part.makeBox(extent.x, extent.y, extent.z, lower)
            for key in shapes:
                result.append(self.native.geometry.inspect_pair(
                    self.shapes[key], zone, key, bounds["id"], volume_tolerance_mm3=self.volume))
        return result

    def service_checks(self, ports):
        measurements = []
        applied = {action["id"] for action in self.actions} if self.stage == "candidate" else set()
        for spec in self.rules.get("service", []):
            if spec.get("required_action") and spec["required_action"] not in applied:
                continue
            if "anchor" in spec:
                label = spec["anchor"]
                transform = self.transform(label)
                origin = transform.multVec(self.native.vector(spec["offset_local_mm"]))
                direction = transform.multVec(self.native.vector([0, 0, 1])) - transform.Base
                zone = self.part.makeCylinder(spec["radius_mm"], spec["stroke_mm"], origin, direction)
            elif "port" in spec:
                port = ports[spec["port"]]
                direction = self.native.vector(port["outward"])
                origin = self.native.vector(port["origin_mm"]) + direction * spec.get("offset_mm", 0)
                zone = self.part.makeCylinder(spec["radius_mm"], spec["stroke_mm"], origin, direction)
                label = spec["port"]
            else:
                zone = self.shape(spec["object"])
                label = spec["object"]
            expected = spec.get("required_box_mm")
            if expected:
                origin = self.native.vector(expected[0])
                extent = self.native.vector(expected[1]) - origin
                required = self.part.makeBox(extent.x, extent.y, extent.z, origin)
                missing = required.cut(zone).Volume
                measurements.append({"status": "fail" if missing > self.volume else "pass",
                                     "subject": label, "sweep_missing_volume_mm3": missing})
            for name in spec["obstacles"]:
                measurements.append(self.native.geometry.inspect_pair(
                    zone, self.shape(name), label, name, finite(spec["clearance_mm"]),
                    volume_tolerance_mm3=self.volume, distance_tolerance_mm=self.distance))
        return measurements

    def bearing_area(self, support, carrier, surface=None):
        overlap = 0.0
        surfaces = [surface] if surface is not None else carrier.Faces
        for foot in support.Faces:
            if not isinstance(foot.Surface, self.part.Plane):
                continue
            foot_dir = foot.normalAt(*foot.Surface.parameter(foot.CenterOfMass))
            for surface in surfaces:
                if isinstance(surface.Surface, self.part.Plane) and foot.distToShape(surface)[0] <= self.position:
                    surf_dir = surface.normalAt(*surface.Surface.parameter(surface.CenterOfMass))
                    if math.degrees(foot_dir.getAngle(-surf_dir)) <= self.angle:
                        overlap += foot.common(surface).Area
        return overlap

    def anchor_surface(self, spec, carrier):
        face_name = spec["carrier_face"]
        require(re.fullmatch(r"Face[1-9][0-9]*", face_name), f"Nom de face porteuse invalide : {face_name}")
        face = carrier.getElement(face_name)
        require(isinstance(face.Surface, self.part.Plane), "Face d'ancrage non plane")
        anchor = self.transform(spec["anchor"])
        gap = face.distToShape(self.part.Vertex(anchor.Base))[0]
        normal = face.normalAt(*face.Surface.parameter(face.CenterOfMass))
        axis = anchor.Rotation.multVec(self.app.Vector(0, 0, 1))
        angle = math.degrees(normal.getAngle(axis))
        return face, {"face": face_name, "gap_mm": gap, "normal_error_deg": angle,
                      "status": "PASS" if gap <= self.position and angle <= self.angle else "FAIL"}

    def supports(self):
        contracts = dict(self.rules.get("supports", {}))
        changed = set()
        if self.stage == "candidate":
            for action in self.actions:
                if action["operation"] in {"CREATE_SUPPORT", "RELOCATE_SUPPORT"}:
                    parameters = action["parameters"]
                    identifier = parameters.get("support", action["occurrence"])
                    contract = dict(contracts.get(identifier, {}))
                    contract.update({key: parameters[key] for key in ("anchor", "carrier", "retains")})
                    contract["anchor_pose"] = parameters["placement"]
                    if action["operation"] == "CREATE_SUPPORT":
                        contract["min_fasteners"] = max(1, contract.get("min_fasteners", 0))
                    contracts[identifier] = contract
                    changed.add(identifier)
        observed = {}
        for identifier, spec in contracts.items():
            if spec.get("created_only") and identifier not in changed:
                continue
            support = self.instance(identifier)
            solid, carrier = self.shape(identifier), self.shape(spec["carrier"])
            anchor = self.instance(spec["anchor"])
            links = (getattr(support, "B1_Anchor", None) == anchor and
                     getattr(support, "B1_Carrier", None) == self.instance(spec["carrier"]))
            retains = [self.instance(item) for item in spec.get("retains", [])]
            retained = set(getattr(support, "B1_Retains", [])) == set(retains)
            engagement = {name: self.shape(name).distToShape(solid)[0] for name in spec.get("retains", [])}
            max_gap = finite(spec.get("retention_max_gap_mm", self.position))
            surface, surface_check = self.anchor_surface(spec, carrier) if "carrier_face" in spec else (None, None)
            area = self.bearing_area(solid, carrier, surface)
            gap = solid.distToShape(carrier)[0]
            fasteners = []
            for fastener in getattr(support, "B1_Fasteners", []):
                keys = [key for key, row in self.rows.items()
                        if row.get("native_id") == fastener.ID and
                        row.get("object") == f"{self.entry}#{fastener.Name}" and key in self.shapes]
                require(len(keys) == 1, f"Occurrence de fixation ambiguë ou absente : {fastener.Name}")
                fastener_shape = self.shapes[keys[0]]
                embed = fastener_shape.common(carrier).Volume
                bearing_distance = fastener_shape.distToShape(solid)[0]
                fasteners.append({"name": fastener.Name, "engagement_mm3": embed,
                                  "support_gap_mm": bearing_distance,
                                  "status": "PASS" if embed > self.volume and
                                  bearing_distance <= self.position else "FAIL"})
            fastened = len(fasteners) >= spec.get("min_fasteners", 0) and all(
                item["status"] == "PASS" for item in fasteners)
            anchor_pose = None
            if "anchor_pose" in spec:
                expected = self.transform(spec["anchor"]).multiply(self.pose(spec["anchor_pose"]))
                anchor_pose = self.pose_error(expected, self.transform(identifier))
            status = "PASS" if (links and retained and fastened and gap <= self.position
                                and area >= spec.get("min_contact_area_mm2", self.position)
                                and (anchor_pose is None or anchor_pose["status"] == "PASS")
                                and (surface_check is None or surface_check["status"] == "PASS")
                                and all(distance <= max_gap for distance in engagement.values())) else "FAIL"
            observed[identifier] = {"status": status, "bearing_area_mm2": area, "gap_mm": gap,
                                    "native_anchor_carrier_links": links, "native_retention_links": retained,
                                    "retention_gaps_mm": engagement, "fasteners": fasteners,
                                    "anchor_pose": anchor_pose}
            if surface_check is not None:
                observed[identifier]["carrier_face"] = surface_check
        return observed

    def pose_checks(self):
        decisions = []
        affected = set()
        for action in self.actions:
            operation = action["operation"]
            if operation == "REPOSITION_DEVICE":
                affected.add(self.key(action["occurrence"]))
                expected_spec = action["expected_after" if self.stage == "candidate" else "expected_before"]
                if "placement" in expected_spec:
                    expected = self.pose(expected_spec["placement"])
                    decisions.append({"occurrence": action["occurrence"],
                                      **self.pose_error(expected, self.transform(action["occurrence"]))})
        if self.stage == "candidate":
            before = self.baseline["occurrences"]
            for key in sorted(affected):
                # An instance move must leave any other occurrence of the same
                # definition unchanged, unless the plan explicitly moves it.
                definition = before[key]["definition"]
                for sibling, row in before.items():
                    if sibling not in affected and row.get("definition") == definition:
                        fields = ("definition", "matrix", "shape_sha256", "bounds_mm", "visible")
                        original = {name: [record.get(field) for field in fields]
                                    for name, record in before.items() if name == sibling or name.startswith(sibling + "/")}
                        actual = {name: [record.get(field) for field in fields]
                                  for name, record in self.rows.items() if name == sibling or name.startswith(sibling + "/")}
                        unchanged = original == actual
                        decisions.append({"occurrence": sibling, "independent_instance": True,
                                          "status": "PASS" if unchanged else "FAIL"})
            for action in self.actions:
                if action["operation"] != "REPOSITION_DEVICE":
                    continue
                target = action["occurrence"]
                for companion in self.model.get("moving_with", {}).get(target, []):
                    before_target = self.transform(target, before)
                    before_companion = self.transform(companion, before)
                    expected = self.transform(target).multiply(before_target.inverse()).multiply(before_companion)
                    decisions.append({"occurrence": companion, "attached_volume": True,
                                      **self.pose_error(expected, self.transform(companion))})
        return decisions

    def analyze(self):
        ports = self.independent_frames()
        contacts, extra_contacts = self.contact_checks()
        topology = self.conductor_checks()
        poses, pairs = self.pose_checks(), self.pairs()
        service, supports = self.service_checks(ports), self.supports()
        # Rebuild last so every other check used the saved, re-opened assembly.
        routes = self.routes(ports)
        topology_status = summarize(topology["status"], "FAIL" if extra_contacts else "PASS",
                                    "PASS" if contacts and ports else "INCONCLUSIVE",
                                    *(row["status"] for row in [*contacts.values(), *ports.values()]))
        pair_status = summarize(*(native_status(row["status"]) for row in pairs))
        pose_status = summarize(*(row["status"] for row in poses))
        service_status = summarize(*(native_status(row["status"]) for row in service)) if service else "NOT_RUN"
        support_status = summarize(*(row["status"] for row in supports.values())) if supports else "NOT_RUN"
        route_status = summarize(*(row["status"] for row in routes.values())) if routes else "NOT_RUN"
        return [proof("L2_TOPOLOGY", topology_status, {"ports": ports, "contacts": contacts,
                       "extra_native_contacts": extra_contacts, **topology, "status": topology_status}),
                proof("L4_GEOMETRY", summarize(pair_status, pose_status), {"pairs": pairs, "poses": poses,
                            "cache": "UNUSED_MEASURED_FRESH"}),
                proof("L4_SERVICE", service_status, service),
                proof("L4_SUPPORT_ANCHOR", support_status, supports),
                proof("L4_DYNAMIC_BEND_RADIUS", route_status, routes)]


def native_status(value):
    return {"pass": "PASS", "fail": "FAIL", "unknown": "INCONCLUSIVE"}[value]


def measure(root, job, report):
    before = file_hashes(root, job["entry"], job["dependencies"])
    _, _, broken, order, _ = serialized_dependencies(root, before)
    require(not broken, "La fermeture contient des liens natifs rompus")
    from electromechanical_engine import freecad_worker as native

    app = native.App
    report["environment"] = {"FreeCAD": ".".join(app.Version()[:3]),
                             "OCCT": native.Part.OCC_VERSION, "Cables": native.cables_environment(False)}
    require(not app.listDocuments(), "La validation exige un processus FreeCAD neuf")
    try:
        doc = app.openDocument(str(root / job["entry"]))
        native.complete_dependencies(doc, root)
        documents, recomputes = native.recalculate(doc, root)
        opened = {guard.inside(root, document.FileName).relative_to(root).as_posix(): document
                  for document in documents}
        require(opened.keys() == before.keys() and not any(item.Partial for item in opened.values()),
                "Documents ouverts hors fermeture ou partiels")
        invalid = [f"{name}#{obj.Name}" for name, document in opened.items() for obj in document.Objects
                   if {"Invalid", "Error"} & set(obj.State) or
                   obj.TypeId == "App::Link" and obj.LinkedObject is None and not obj.ElementCount]
        records, shapes, objects = collect(doc, root, before)
        invalid.extend(key for key, row in records.items() if row["status"] != "PASS")
        report.update(reopened=True, open_documents=sorted(opened), occurrences=records, inputs_sha256=before,
                      measurement_identity_sha256=measurement_identity(records))
        report["checks"].append(proof("REOPEN_XLINK", "INCONCLUSIVE" if invalid else "PASS",
                                      {"documents": order, "recomputed": recomputes, "invalid_objects": invalid}))
        if not invalid:
            report["checks"].extend(Measurement(native, doc, records, shapes, objects, job).analyze())
    finally:
        for name in reversed(list(app.listDocuments())):
            app.closeDocument(name)
        file_hashes(root, job["entry"], before)
        require(not app.listDocuments(), "La fermeture FreeCAD est restée ouverte après mesure")
        report["documents_closed"] = True


def private_path(path):
    absolute = path.absolute()
    safe = guard.inside(PROJECT, absolute)
    require(safe == absolute and safe.relative_to(PROJECT).parts[0] in {".runtime", "results"},
            f"Chemin hors périmètre privé : {path}")
    for parent in (safe, *safe.parents):
        if parent == PROJECT:
            break
        require(not parent.is_symlink() and not getattr(parent, "is_junction", lambda: False)(),
                f"Chemin de travail redirigé : {parent}")
    return safe


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for argument in ("root", "job", "output"):
        parser.add_argument(f"--{argument}", type=Path, required=True)
    opts = parser.parse_args()
    try:
        root, job_path, output = map(private_path, (opts.root, opts.job, opts.output))
        require(root.is_dir() and len(root.relative_to(PROJECT).parts) > 1
                and job_path.is_file() and job_path.stat().st_nlink == 1
                and output.parent.is_dir() and not output.exists()
                and not output.is_relative_to(root) and not job_path.is_relative_to(root),
                "Répertoire privé et chemins de mesure disjoints requis")
        job = json.loads(job_path.read_bytes())
        require(job["stage"] in {"baseline", "candidate"}, "Phase de mesure inconnue")
        job_hash = guard.sha256(job_path)
        report = {"schema": WORKER_SCHEMA, "plan_id": job["plan_id"], "stage": job["stage"],
                  "job_sha256": job_hash, "pid": os.getpid(), "worker_id": uuid4().hex,
                  "reopened": False, "checks": []}
        try:
            measure(root, job, report)
        except GEOMETRY_ERRORS as error:
            report["checks"].append(proof("NATIVE_MEASUREMENT", "INCONCLUSIVE", str(error)))
        mandatory = {"REOPEN_XLINK", "L2_TOPOLOGY", "L4_GEOMETRY", "L4_SERVICE",
                     "L4_DYNAMIC_BEND_RADIUS", *job.get("mandatory_checks", [])}
        if job["stage"] == "candidate" and any(action["operation"] in {"CREATE_SUPPORT", "RELOCATE_SUPPORT"}
                                               for action in job["actions"]):
            mandatory.add("L4_SUPPORT_ANCHOR")
        mandatory -= {"VERIFY_IMMUTABLE_SOURCES", "VALIDATE_T0"}
        observed = {row["id"]: row["status"] for row in report["checks"]}
        for identifier in sorted(mandatory - observed.keys()):
            report["checks"].append(proof(identifier, "NOT_RUN", "Mesure indisponible"))
        if not report["reopened"]:
            mandatory.add("NATIVE_MEASUREMENT")
        result = summarize(*(row["status"] for row in report["checks"] if row["id"] in mandatory or
                            row["id"] == "NATIVE_MEASUREMENT"))
        report.update(finalized=True, status="INCONCLUSIVE" if result == "NOT_RUN" else result)
        require(guard.sha256(job_path) == job_hash, "Contrat de mesure modifié pendant le rejeu")
        publish(output, report)
    except GEOMETRY_ERRORS as error:
        print(f"Validation XLink non finalisée : {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
