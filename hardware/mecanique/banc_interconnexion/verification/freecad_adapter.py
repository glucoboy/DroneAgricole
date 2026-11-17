"""Adaptateur FreeCAD du banc synthétique L2. Le noyau C++ possède le graphe."""

import argparse
import hashlib
import importlib.metadata
import inspect
import json
import math
import os
from pathlib import Path
import platform
import socket
import subprocess
import sys
import xmlrpc.client


ROOT = Path(__file__).resolve().parents[4]
BUILDER = ROOT / "hardware/mecanique/cartographe/verification/cable_workbench_prototype.py"
POSITION_TOL_MM = 1e-6
VOLUME_TOL_MM3 = 1e-6
POSE_TOL = 1e-8
MODEL = "Banc_Interconnexion.FCStd"


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def publish_json(path, data):
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(data, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")
    temporary.replace(path)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def check_shape(obj, solids):
    shape = obj.Shape
    require(not shape.isNull() and shape.isValid() and len(shape.Solids) == solids,
            f"Forme invalide ou incomplète : {obj.Name}")
    return shape


def recompute(doc):
    require(doc.recompute() is not False, "Échec du recalcul FreeCAD")
    errors = [obj.Name for obj in doc.Objects if {"Invalid", "Error"} & set(obj.State)]
    require(not errors, f"Objets natifs en erreur : {errors}")


def initialize():
    global App, Gui, Part, archCableConnector, archElectricalDevice, cableTerminal
    global cableutils, wireFlex, builder
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    import FreeCAD as App
    import FreeCADGui as Gui
    import Part

    Gui.showMainWindow()
    Gui.getMainWindow().hide()
    sys.path.insert(0, str(BUILDER.parent))
    import cable_workbench_prototype as builder

    provenance = builder.bootstrap_paths()
    from freecad.cables import archCableConnector, archElectricalDevice
    from freecad.cables import cableTerminal, cableutils, wireFlex

    return {
        "freecad": list(App.Version()),
        "cables": provenance["version"],
        "system": platform.system(),
        "architecture": platform.machine(),
        "python": platform.python_version(),
        "qt_platform": os.environ["QT_QPA_PLATFORM"],
        "sha256_modules": {**provenance["sha256_modules"], **{
            Path(module.__file__).name: sha256(Path(module.__file__))
            for module in (archCableConnector, archElectricalDevice, cableTerminal, cableutils)
        }},
        "factories": {
            factory.__module__ + "." + factory.__name__: str(inspect.signature(factory))
            for factory in (archCableConnector.makeCableConnector,
                            archElectricalDevice.makeElectricalDevice,
                            cableTerminal.makeCableTerminal, wireFlex.make_wireflex,
                            cableutils.attach_in_place)
        },
    }


def position(matrix):
    return App.Placement(App.Matrix(*matrix))


def vector_list(vector):
    return [vector.x, vector.y, vector.z]


def values_close(left, right, tol):
    return len(left) == len(right) and all(math.isclose(a, b, rel_tol=0, abs_tol=tol)
                                           for a, b in zip(left, right))


def box(bounds):
    return Part.makeBox(*(bounds[i + 3] - bounds[i] for i in range(3)),
                        App.Vector(*bounds[:3]))


def set_l2(obj, prop, value, property_type="String"):
    obj.addProperty("App::Property" + property_type, prop, "Interconnexion L2")
    setattr(obj, prop, value)
    obj.setEditorMode(prop, 1)


def feature(doc, name, shape, color, transparency=0, attachable=False):
    obj = doc.addObject("Part::FeaturePython" if attachable else "Part::Feature", name)
    if attachable:
        obj.addExtension("Part::AttachExtensionPython")
    obj.Shape = shape
    obj.ViewObject.ShapeColor = color
    obj.ViewObject.LineColor = color
    obj.ViewObject.Transparency = transparency
    return obj


def frame(doc, name, placement, support):
    origin = App.Vector()
    axes = Part.makeCompound([Part.makeLine(origin, App.Vector(*endpoint))
                              for endpoint in [(3, 0, 0), (0, 3, 0), (0, 0, 5)]])
    obj = feature(doc, name, axes, (0.12, 0.62, 0.81), attachable=True)
    obj.Placement = placement
    cableutils.attach_in_place([obj, support])
    return obj


def attach_terminal(parent, identifier, cavity, pin, contact_placement):
    terminal = cableTerminal.makeCableTerminal()
    terminal.Label = identifier
    terminal.Length = 0.5
    terminal.PinName = str(pin or cavity)
    terminal.Placement = contact_placement
    cableutils.attach_in_place([terminal, parent])
    set_l2(terminal, "L2Id", identifier)
    return terminal


def interface_geometry(doc, spec, index):
    mount = position(spec["mount"])
    mating = position(spec["receptacle_mating"])
    plug_mating = position(spec["mate_mating"])
    exit_frame = position(spec["exit"])
    # Enveloppes propres au banc, dans les repères locaux des corps.
    device_base = feature(doc, f"DeviceGeometry{index}", box([-6, -6, -8, 6, 6, 0]),
                          (0.31, 0.36, 0.42))
    device = archElectricalDevice.makeElectricalDevice(
        baseobj=device_base, preset="Customized", placement=mount,
        name=spec.get("equipment_id", "Équipement synthétique " + spec["port_id"]))
    receptacle_base = feature(doc, f"ReceptacleGeometry{index}",
                              box([-3, -3, -4, 3, 3, 0]), (0.28, 0.67, 0.83))
    receptacle = archCableConnector.makeCableConnector(
        baseobj=receptacle_base, preset="Customized", placement=mating,
        name="Embase " + spec["receptacle_id"])
    plug_length = (exit_frame.Base - plug_mating.Base).Length
    require(plug_length > 3, "Le banc attend une longueur de fiche supérieure à 3 mm")
    hood = box([-3, -3, 0, 3, 3, plug_length - 3])
    strain_relief = Part.makeCylinder(2, 3, App.Vector(0, 0, plug_length - 3))
    plug_base = feature(doc, f"PlugGeometry{index}", hood.fuse(strain_relief), (0.92, 0.57, 0.18))
    plug = archCableConnector.makeCableConnector(
        baseobj=plug_base, preset="Customized",
        placement=App.Placement(plug_mating.Base, exit_frame.Rotation),
        name="Fiche et serre-câble " + spec["mate_id"])
    cableutils.attach_in_place([receptacle, device])
    cableutils.attach_in_place([plug, receptacle])
    device.ViewObject.ShapeColor = (0.31, 0.36, 0.42)
    receptacle.ViewObject.ShapeColor = (0.28, 0.67, 0.83)
    plug.ViewObject.ShapeColor = (0.92, 0.57, 0.18)
    receptacle.ViewObject.Transparency = 45
    plug.ViewObject.Transparency = 60
    for obj, identifier in ((device, spec.get("equipment_id", spec["port_id"])),
                            (receptacle, spec["receptacle_id"]), (plug, spec["mate_id"])):
        set_l2(obj, "L2Id", identifier)
        set_l2(obj, "L2End", spec["end_id"])
        set_l2(obj, "L2Port", spec["port_id"])
        obj.Visibility = True

    frames = {name: frame(doc, name + str(index), placement, support) for name, placement, support in (
        ("Mount", mount, device), ("ReceptacleMating", mating, receptacle),
        ("MateMating", plug_mating, plug), ("WireExit", exit_frame, plug),
    )}
    envelope = feature(doc, f"Extraction{index}", box(spec["extraction_box_mm"]),
                       (0.16, 0.68, 0.39), transparency=86)
    envelope.Label = "Retrait « " + spec["end_id"] + " »"
    if spec.get("tool_box_mm") is not None:
        tooling = feature(doc, f"ToolAccess{index}", box(spec["tool_box_mm"]),
                          (0.36, 0.27, 0.72), transparency=86)
        tooling.Label = "Accès outillage « " + spec["end_id"] + " »"
        tooling.Visibility = False
    recompute(doc)
    contacts = {}
    offsets = [(-0.9, -0.9), (-0.9, 0.9), (0.9, -0.9), (0.9, 0.9)]
    for contact, (x, y) in zip(sorted(spec["contacts"], key=lambda item: item["cavity"]), offsets):
        contact_placement = mating.multiply(App.Placement(App.Vector(x, y, 0), App.Rotation()))
        terminal = attach_terminal(receptacle, contact["receptacle_contact_id"],
                                   contact["cavity"], contact.get("pin_id"), contact_placement)
        plug_terminal = attach_terminal(plug, contact["mate_contact_id"],
                                        contact["cavity"], contact.get("pin_id"), contact_placement)
        set_l2(plug_terminal, "L2MatedContact", terminal, "Link")
        contacts[contact["mate_contact_id"]] = plug_terminal
    recompute(doc)
    return {"device": device, "receptacle": receptacle, "plug": plug,
            "frames": frames, "envelope": envelope, "contacts": contacts}


def linksub(obj, vertex="Vertex1"):
    return (obj, vertex)


def add_cable(doc, spec, interfaces):
    contacts = {identifier: terminal for interface in interfaces
                for identifier, terminal in interface["contacts"].items()}
    points = spec["points_mm"]
    start = interfaces[0]["frames"]["WireExit"]
    finish = interfaces[1]["frames"]["WireExit"]
    if not values_close(vector_list(start.Placement.Base), points[0], POSITION_TOL_MM):
        start, finish = finish, start
    radius = spec.get("bend_radius_mm") or max(spec["diameter_mm"], 5)
    jacket, route = builder.make_native_cable(doc, None, "Cordon_L2", points,
                                              spec["diameter_mm"], radius)
    jacket.ViewObject.Transparency = 78
    set_l2(jacket, "L2Id", spec["id"])
    route.Vrtx_start, route.Vrtx_end = linksub(start), linksub(finish)
    wires = []
    colors = [(0.80, 0.22, 0.16), (0.29, 0.40, 0.72), (0.17, 0.62, 0.34), (0.73, 0.39, 0.74)]
    for conductor, color in zip(spec["conductors"], colors):
        first, last = (contacts[identifier] for identifier in conductor["mate_contact_ids"])
        wire = wireFlex.make_wireflex([linksub(first), linksub(last)])
        wire.Label = "Conducteur " + conductor["id"]
        wire.ViewObject.LineColor = color
        wire.ViewObject.LineWidth = 3
        set_l2(wire, "L2Id", conductor["id"])
        wires.append(wire)
    set_l2(jacket, "L2Conductors", wires, "LinkList")
    for terminal in contacts.values():
        terminal.touch()
    recompute(doc)
    return jacket


def probe_step(doc, connector, device, directory):
    step_path = directory / "forme_synthetique.step"
    box([0, 0, 0, 1, 2, 3]).exportStep(str(step_path))
    imported = {}
    before = {obj.Name for obj in doc.Objects}
    for native in (connector, device):
        shape, colors = native.Proxy.readExtShape(native, step_path.name, libdirs=[str(directory)])
        require(shape.isValid() and len(shape.Solids) == 1
                and abs(shape.Volume - 6) <= VOLUME_TOL_MM3,
                f"STEP synthétique mal importé par {type(native.Proxy).__name__}")
        require(before == {obj.Name for obj in doc.Objects}, "Import STEP temporaire non nettoyé")
        imported[type(native.Proxy).__name__] = {"solids": len(shape.Solids),
                                                 "volume_mm3": shape.Volume,
                                                 "color_entries": len(colors)}
    return {"status": "PASS", "sha256": sha256(step_path), "native_proxy_imports": imported,
            "source": "Boîte synthétique FreeCAD 1 × 2 × 3 mm exportée en STEP"}


def create(plan, digest, directory):
    doc = App.newDocument("BancInterconnexion")
    doc.Label = "Banc synthétique L2 — deux interfaces et un cordon"
    receipt = doc.addObject("App::FeaturePython", "BancL2")
    set_l2(receipt, "ProjectionSha256", digest)
    set_l2(receipt, "ConfigurationId", plan["configuration_id"])
    set_l2(receipt, "StateId", plan["state_id"])
    interfaces = [interface_geometry(doc, spec, index)
                  for index, spec in enumerate(plan["interfaces"], start=1)]
    for obstacle in plan["obstacles"]:
        obj = feature(doc, "Obstacle", box(obstacle["box_mm"]), (0.71, 0.16, 0.15))
        obj.Label = obstacle["id"]
        set_l2(obj, "L2ObstacleId", obstacle["id"])
    add_cable(doc, plan["cables"][0], interfaces)
    step = probe_step(doc, interfaces[0]["plug"], interfaces[0]["device"], directory)
    recompute(doc)
    Gui.activeDocument().activeView().viewAxonometric()
    Gui.activeDocument().activeView().fitAll()
    target = directory / MODEL
    doc.saveAs(str(target))
    App.closeDocument(doc.Name)
    require(target.is_file() and target.stat().st_size > 0, "Natif non finalisé")
    return {"pid": os.getpid(), "fcstd_sha256": sha256(target), "step_probe": step}


def object_by_id(doc, identifier, proxy_name, end_id=None):
    objects = [obj for obj in doc.Objects if getattr(obj, "L2Id", None) == identifier
               and type(getattr(obj, "Proxy", None)).__name__ == proxy_name
               and (end_id is None or getattr(obj, "L2End", None) == end_id)]
    require(len(objects) == 1, f"Occurrence native absente ou ambiguë : {identifier} ({proxy_name})")
    return objects[0]


def vertex_from(link):
    require(link and len(link[1]) == 1 and link[1][0].startswith("Vertex"),
            "Liaison à un sommet natif absente")
    return link[0].getSubObject(link[1][0]).Point


def wire_endpoints(wire):
    shape = check_shape(wire, 0)
    require(len(shape.Wires) == 1 and not shape.Wires[0].isClosed(), "Fil natif ouvert attendu")
    vertices = shape.Wires[0].OrderedVertexes
    return vertices[0].Point, vertices[-1].Point


def check_wire(wire, expected_contacts, check_terminal_type):
    links = (wire.Vrtx_start, wire.Vrtx_end)
    endpoint_errors = [(vertex_from(link) - point).Length
                       for link, point in zip(links, wire_endpoints(wire))]
    observed_contacts = [getattr(link[0], "L2Id", None) for link in links]
    is_terminal = [type(getattr(link[0], "Proxy", None)).__name__ == "CableTerminal" for link in links]
    backed_by_terminals = (all(is_terminal) and observed_contacts == expected_contacts
                           and all(f"1:{wire.Name}" in link[0].ConnectedWires for link in links))
    matched = max(endpoint_errors) <= POSITION_TOL_MM
    return {"status": "PASS" if matched and (backed_by_terminals or not check_terminal_type) else "FAIL",
            "wire": wire.Name, "endpoint_errors_mm": endpoint_errors,
            "targets": [link[0].Name for link in links], "subelements": [link[1][0] for link in links],
            "contact_ids": observed_contacts, "terminal_types": is_terminal,
            "reciprocal_terminal_links": backed_by_terminals}


def box_bounds(shape):
    bound = shape.BoundBox
    return [bound.XMin, bound.YMin, bound.ZMin, bound.XMax, bound.YMax, bound.ZMax]


def extraction(envelope, obstacles):
    shape = check_shape(envelope, 1)
    pairs = []
    for obstacle in obstacles:
        physical = check_shape(obstacle, 1)
        volume = shape.common(physical).Volume
        distance = shape.distToShape(physical)[0]
        pairs.append({"obstacle": obstacle.Name, "volume_mm3": volume, "distance_mm": distance})
    return {"status": "FAIL" if any(p["volume_mm3"] > VOLUME_TOL_MM3 for p in pairs) else "PASS",
            "bounds_mm": box_bounds(shape), "pairs": pairs}


def check_pull_envelope(plug, envelope, exit_frame, travel_mm):
    # L'enveloppe est une boîte convexe. Elle couvre toute la translation si
    # les boîtes initiale et finale de la fiche lui sont incluses.
    require(math.isfinite(travel_mm) and travel_mm > 0, "Course de retrait positive attendue")
    shift = vector_list(exit_frame.Placement.Rotation.multVec(App.Vector(0, 0, travel_mm)))
    before = box_bounds(check_shape(plug, 1))
    after = [bound + shift[i % 3] for i, bound in enumerate(before)]
    sweep = [min(a, b) if i < 3 else max(a, b) for i, (a, b) in enumerate(zip(before, after))]
    reservation = box_bounds(envelope.Shape)
    inside = all(reservation[i] - POSITION_TOL_MM <= sweep[i] for i in range(3)) and all(
        sweep[i] <= reservation[i] + POSITION_TOL_MM for i in range(3, 6))
    return {"status": "PASS" if inside else "FAIL", "translation_mm": shift,
            "swept_bounds_mm": sweep}


def check_pose(obj, expected):
    measured = list(obj.Placement.toMatrix().A)
    return {"status": "PASS" if values_close(measured, expected, POSE_TOL) else "FAIL",
            "matrix": measured, "object": obj.Name}


def attached_to(obj, parent):
    return (obj.MapMode == "ObjectXY" and len(obj.AttachmentSupport) == 1
            and obj.AttachmentSupport[0][0] == parent)


def revalidate(plan, digest, directory):
    model = directory / MODEL
    before = sha256(model)
    doc = App.openDocument(str(model))
    require(doc.BancL2.ProjectionSha256 == digest, "Projection native différente de celle du banc")
    jacket = object_by_id(doc, plan["cables"][0]["id"], "ArchCable")
    # Invalider le cache ArchCable : une ancienne Shape valide peut masquer un échec OCC.
    jacket.Shape = Part.Shape()
    jacket.Base.touch()
    jacket.touch()
    recompute(doc)
    jacket_geometry = builder.cable_geometry(jacket)
    check_shape(jacket, 1)
    route = check_wire(jacket.Base, [], check_terminal_type=False)
    expected_exits = {f"WireExit{index}" for index in range(1, len(plan["interfaces"]) + 1)}
    require(jacket.Visibility and route["status"] == "PASS" and set(route["targets"]) == expected_exits,
            "Gaine désynchronisée de ses sorties")
    obstacles = [obj for obj in doc.Objects if hasattr(obj, "L2ObstacleId")]
    solids = []
    interfaces = []
    for index, spec in enumerate(plan["interfaces"], start=1):
        device = object_by_id(doc, spec.get("equipment_id", spec["port_id"]),
                              "ArchElectricalDevice", spec["end_id"])
        receptacle = object_by_id(doc, spec["receptacle_id"], "ArchCableConnector", spec["end_id"])
        plug = object_by_id(doc, spec["mate_id"], "ArchCableConnector", spec["end_id"])
        require(attached_to(receptacle, device) and attached_to(plug, receptacle),
                "Chaîne mécanique native rompue")
        solids.extend((device, receptacle, plug))
        for obj in (device, receptacle, plug):
            check_shape(obj, 1)
            require(obj.Visibility, f"Corps du banc masqué : {obj.Name}")
        frames = {}
        for key, name, parent in (("mount", "Mount", device),
                                  ("receptacle_mating", "ReceptacleMating", receptacle),
                                  ("mate_mating", "MateMating", plug), ("exit", "WireExit", plug)):
            obj = doc.getObject(name + str(index))
            require(attached_to(obj, parent), f"Repère détaché : {obj.Name}")
            frames[key] = {**check_pose(obj, spec[key]), "attachment": parent.Name}
        require(all(result["status"] == "PASS" for result in frames.values()), "Repères natifs divergents")
        contacts = []
        for item in spec["contacts"]:
            female = object_by_id(doc, item["receptacle_contact_id"], "CableTerminal")
            male = object_by_id(doc, item["mate_contact_id"], "CableTerminal")
            gap = (female.Placement.Base - male.Placement.Base).Length
            require(female.ParentElement == receptacle and male.ParentElement == plug
                    and attached_to(female, receptacle) and attached_to(male, plug)
                    and male.L2MatedContact == female and gap <= POSITION_TOL_MM
                    and female.Visibility and male.Visibility,
                    "Contacts natifs mal accouplés")
            contacts.append({"mate_contact_id": male.L2Id, "receptacle_contact_id": female.L2Id,
                             "native_pair": [female.Name, male.Name], "gap_mm": gap,
                             "position_mm": vector_list(male.Placement.Base)})
        envelope = doc.getObject(f"Extraction{index}")
        exit_frame = doc.getObject(f"WireExit{index}")
        require(envelope.Visibility and exit_frame.Visibility,
                "Enveloppe ou sortie de câble masquée")
        pull = check_pull_envelope(plug, envelope, exit_frame, spec["extraction_travel_mm"])
        require(pull["status"] == "PASS", "Retrait de la fiche hors de l'enveloppe")
        interfaces.append({"end_id": spec["end_id"], "port_id": spec["port_id"],
                           "device": device.Name, "receptacle": receptacle.Name, "plug": plug.Name,
                           "frames": frames, "contacts": contacts, "envelope": envelope.Name,
                           "pull_envelope": pull})
    for index, (interface, spec) in enumerate(zip(interfaces, plan["interfaces"]), start=1):
        envelope = doc.getObject(interface["envelope"])
        # La fiche retirée et son cordon mobile sont exclus du contrôle d'obstacles fixes.
        fixed = [obj for obj in solids + obstacles if obj.Name != interface["plug"]]
        check = extraction(envelope, fixed)
        require(check["status"] == "PASS" and values_close(check["bounds_mm"],
                spec["extraction_box_mm"], POSITION_TOL_MM), "Volume de retrait invalide")
        interface["extraction"] = check
        if spec.get("tool_box_mm") is not None:
            tooling = extraction(doc.getObject(f"ToolAccess{index}"), obstacles)
            require(tooling["status"] == "PASS" and values_close(tooling["bounds_mm"],
                    spec["tool_box_mm"], POSITION_TOL_MM), "Volume d'outillage invalide")
            interface["tooling"] = tooling
    conductors = []
    expected_wires = plan["cables"][0]["conductors"]
    for spec in expected_wires:
        wire = object_by_id(doc, spec["id"], "WireFlex")
        result = check_wire(wire, spec["mate_contact_ids"], check_terminal_type=True)
        require(wire.Visibility and result["status"] == "PASS" and wire in jacket.L2Conductors,
                f"Conducteur natif {spec['id']} non raccordé : {result}")
        conductors.append({"id": spec["id"], **result})
    require(len(jacket.L2Conductors) == len(expected_wires), "Liste de conducteurs incomplète")

    # Défauts dans la copie réouverte, sans réécriture du natif positif.
    first = interfaces[0]
    envelope = doc.getObject(first["envelope"])
    bounds = box_bounds(envelope.Shape)
    center = [(bounds[i] + bounds[i + 3]) / 2 for i in range(3)]
    blocker = feature(doc, "BlockerTest", Part.makeBox(1, 1, 1, App.Vector(*center)), (1.0, 0.0, 0.0))
    obstructed = extraction(envelope, [blocker])
    require(obstructed["status"] == "FAIL", "Obstacle de retrait ignoré")
    wire = object_by_id(doc, expected_wires[0]["id"], "WireFlex")
    original_start = wire.Vrtx_start
    point = feature(doc, "GenericVertex", Part.Vertex(vertex_from(original_start)), (1.0, 0.0, 0.0))
    wire.Vrtx_start = linksub(point)
    wire.AttachmentSupport = [linksub(point)]
    recompute(doc)
    generic = check_wire(wire, expected_wires[0]["mate_contact_ids"], check_terminal_type=True)
    require(generic["status"] == "FAIL" and max(generic["endpoint_errors_mm"]) <= POSITION_TOL_MM,
            "Le rejet d'un sommet générique doit être indépendant de sa coïncidence")
    wire.Vrtx_start = original_start
    wire.AttachmentSupport = [original_start]
    original_start[0].touch()
    recompute(doc)

    device = doc.getObject(first["device"])
    previous_position = vertex_from(wire.Vrtx_start)
    previous_links = tuple(wire.Vrtx_start[1])
    device.Placement = App.Placement(device.Placement.Base,
        App.Rotation(App.Vector(0, 0, 1), 15).multiply(device.Placement.Rotation))
    recompute(doc)
    mount_after = check_pose(doc.Mount1, plan["interfaces"][0]["mount"])
    displacement = (vertex_from(wire.Vrtx_start) - previous_position).Length
    moved_wire = check_wire(wire, expected_wires[0]["mate_contact_ids"], check_terminal_type=True)
    require(mount_after["status"] == "FAIL" and displacement > POSITION_TOL_MM
            and tuple(wire.Vrtx_start[1]) == previous_links and moved_wire["status"] == "PASS",
            "Réorientation non propagée ou divergence non détectée")
    App.closeDocument(doc.Name)
    require(sha256(model) == before, "La réouverture a modifié le fichier du banc")
    return {"status": "PASS", "pid": os.getpid(), "fcstd_sha256": before,
            "interfaces": interfaces, "jacket": jacket_geometry, "jacket_endpoints": route,
            "conductors": conductors, "faults": {"extraction_blocked": obstructed,
            "generic_endpoint_same_position": generic,
            "rotated_equipment": {"frozen_pose": mount_after, "wire": moved_wire,
                                  "terminal_displacement_mm": displacement}}}


def load_plan(path):
    report = read_json(path)
    require(report.get("mode") == "SYNTHETIC_BENCH" and
            all(report.get(field) == "PASS" for field in ("status", "compatibility", "electrical", "geometry")),
            "Le banc natif exige un rapport C++ synthétique recevable")
    plan = report["native_plan"]
    require(report.get("configuration_id") == plan["configuration_id"] == "banc-l2" and
            report.get("state_id") == plan["state_id"], "Ce banc ne lit que la projection synthétique L2")
    require(len(plan["interfaces"]) == 2 and all(len(i["contacts"]) == 4 for i in plan["interfaces"])
            and len(plan["cables"]) == 1 and len(plan["cables"][0]["conductors"]) == 4,
            "Deux interfaces de quatre contacts et un cordon de quatre conducteurs sont requis")
    return plan, sha256(path)


def rpc_status():
    metadata_source = None
    try:
        metadata = importlib.metadata.distribution("freecad-mcp")
        metadata_source = "python_distribution"
    except importlib.metadata.PackageNotFoundError:
        cache_dirs = [Path.home() / "AppData/Local/uv/cache"]
        if os.environ.get("UV_CACHE_DIR"):
            cache_dirs.insert(0, Path(os.environ["UV_CACHE_DIR"]))
        archive = next((path for cache in cache_dirs
                        for path in sorted((cache / "archive-v0").glob("*/freecad_mcp-*.dist-info"))), None)
        metadata = importlib.metadata.PathDistribution(archive) if archive else None
        if metadata:
            metadata_source = "uv_package_metadata"
    before = socket.getdefaulttimeout()
    try:
        socket.setdefaulttimeout(3)
        with xmlrpc.client.ServerProxy("http://localhost:9875") as client:
            response = client.get_rpc_status()
            result = {"outcome": "AVAILABLE" if response.get("success") else "INCONCLUSIVE",
                      "response": response}
    except (OSError, xmlrpc.client.Error) as error:
        result = {"outcome": "INCONCLUSIVE", "error": type(error).__name__,
                  "winerror": getattr(error, "winerror", None)}
    finally:
        socket.setdefaulttimeout(before)
    return {"endpoint": "localhost:9875", "method": "get_rpc_status",
            "package_version": metadata.version if metadata else None,
            "metadata_source": metadata_source, **result}


def run(args):
    projection = args.projection.resolve()
    load_plan(projection)
    adapter = Path(__file__).resolve()
    sources = {path: sha256(path) for path in (projection, adapter, BUILDER)}
    args.directory.mkdir(parents=True, exist_ok=False)
    rpc = rpc_status()
    executable = str(args.freecad.resolve())
    directory = args.directory.resolve()
    phases = {}
    for phase in ("build", "reopen"):
        with (directory / f"{phase}.log").open("wb") as log:
            process = subprocess.run([executable, "-B", str(adapter),
                                      phase, str(projection), str(directory)],
                                     stdout=log, stderr=subprocess.STDOUT, timeout=45, check=False)
        require(process.returncode == 0, f"Échec de {phase} : consulter {phase}.log")
        phases[phase] = read_json(directory / f"{phase}.json")
    build, reopen = phases["build"], phases["reopen"]
    require(build["pid"] != reopen["pid"] and build["fcstd_sha256"] == reopen["fcstd_sha256"]
            and build["environment"] == reopen["environment"], "Phases natives non réconciliées")
    require(all(sha256(path) == expected for path, expected in sources.items()), "Source native modifiée")
    publish_json(directory / "native_l2.json", {"status": "PASS", "scope": "SYNTHETIC",
                 "projection_sha256": sources[projection], "adapter_sha256": sources[adapter],
                 "builder_sha256": sources[BUILDER], "rpc": rpc,
                 "tolerances": {"position_mm": POSITION_TOL_MM, "volume_mm3": VOLUME_TOL_MM3,
                                "pose_matrix_components": POSE_TOL},
                 "phases": phases, "interactive": "NOT_EXECUTED", "physical": "NOT_EXECUTED"})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("run", "build", "reopen"))
    parser.add_argument("projection", type=Path)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--freecad", type=Path)
    args = parser.parse_args()
    if args.phase == "run":
        require(args.freecad, "--freecad attend le Python embarqué de FreeCAD")
        run(args)
        return
    plan, digest = load_plan(args.projection)
    environment = initialize()
    worker = create if args.phase == "build" else revalidate
    result = worker(plan, digest, args.directory)
    publish_json(args.directory / f"{args.phase}.json", {**result, "environment": environment})
    # Éviter de bloquer sur l'arrêt de la GUI cachée du processus dédié.
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0)


if __name__ == "__main__":
    main()
