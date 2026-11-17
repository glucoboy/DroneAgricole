"""Frontière des échanges et gel du référentiel indépendant."""

import hashlib
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path


REFERENCE_FILES = ("system_model.json", "design_requirements.yaml")
STATUSES = {"MESUREE", "DOCUMENTEE", "CALCULEE", "ESTIMEE", "HYPOTHESE", "INCONNUE"}
FAMILIES = {"MATERIEL_CONSTANT", "IMPLANTATION_CONNECTIQUE", "REVISION_ELECTRONIQUE"}
IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}\Z")


class ContractError(ValueError):
    """Entrée mal formée, référence divergente ou preuve manquante."""


def require(condition, message):
    if not condition:
        raise ContractError(message)


def unique_mapping(pairs):
    result = {}
    for key, value in pairs:
        require(isinstance(key, str) and key not in result, f"clé invalide ou dupliquée: {key}")
        result[key] = value
    return result


def reject_constant(value):
    raise ContractError(f"nombre non fini: {value}")


def load(path):
    path = Path(path)
    return decode(path.name, path.read_bytes())


def decode(name, content):
    raw = content.decode("utf-8-sig")
    try:
        result = json.loads(raw, object_pairs_hook=unique_mapping, parse_constant=reject_constant)
    except json.JSONDecodeError as exc:
        if not name.endswith(".yaml") or raw.lstrip().startswith(("{", "[")):
            raise ContractError(f"{name}: JSON invalide: {exc}") from exc
        result = decode_yaml(raw)
    require(isinstance(result, dict), f"{name}: objet attendu")
    try:
        json.dumps(result, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ContractError(f"{name}: types incompatibles avec le modèle JSON: {exc}") from exc
    return result


def decode_yaml(raw):
    try:
        import yaml
    except ImportError as exc:
        raise ContractError("YAML non JSON: installer PyYAML ou utiliser le sous-ensemble JSON") from exc

    class UniqueLoader(yaml.SafeLoader):
        def construct_mapping(self, node, deep=False):
            return unique_mapping(self.construct_pairs(node, deep=deep))

    try:
        return yaml.load(raw, Loader=UniqueLoader)
    except yaml.YAMLError as exc:
        raise ContractError(f"YAML invalide: {exc}") from exc


def write(path, data):
    content = json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
    with Path(path).open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(content + "\n")


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def digest_value(data):
    encoded = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def identifier(value, name):
    require(isinstance(value, str) and IDENTIFIER.fullmatch(value), f"{name}: identifiant invalide")
    return value


def versioned(data, name):
    require(isinstance(data, dict) and type(data.get("version")) is int and data["version"] == 1,
            f"{name}: version de contrat attendue 1")


def nonempty_text(value, name):
    require(isinstance(value, str) and bool(value.strip()), f"{name}: texte obligatoire")


def number(value, name, minimum=None):
    try:
        finite = type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        finite = False
    require(finite, f"{name}: nombre fini attendu")
    require(minimum is None or value >= minimum, f"{name}: minimum {minimum}")


def vector(value, name):
    require(isinstance(value, list) and len(value) == 3, f"{name}: triplet XYZ attendu")
    for component in value:
        number(component, name)


def path_points(value, name):
    require(isinstance(value, list) and len(value) >= 2, f"{name}: au moins deux points")
    for point in value:
        vector(point, name)
    require(all(a != b for a, b in zip(value, value[1:])), f"{name}: points successifs identiques")


def identifier_list(value, name):
    require(isinstance(value, list), f"{name}: liste attendue")
    for item in value:
        identifier(item, name)
    require(len(set(value)) == len(value), f"{name}: identifiants dupliqués")


def indexed(records, name):
    require(isinstance(records, list), f"{name}: liste attendue")
    result = {}
    for record in records:
        require(isinstance(record, dict), f"{name}: objet attendu")
        key = identifier(record.get("id"), name)
        require(key not in result, f"{name}: doublon {key}")
        result[key] = record
    return result


def provenance(data, name):
    require(isinstance(data, dict) and isinstance(data.get("status"), str) and data["status"] in STATUSES,
            f"{name}: provenance invalide")
    if data["status"] != "INCONNUE":
        nonempty_text(data.get("source"), f"{name}.source")
    for key in ("source", "version", "date", "method", "unit", "frame"):
        if key in data and data[key] is not None:
            nonempty_text(data[key], f"{name}.{key}")
    if data.get("uncertainty") is not None:
        number(data["uncertainty"], f"{name}.uncertainty", 0)


def box_dimensions(box, name):
    vector(box.get("origin_mm"), f"{name}.origin_mm")
    vector(box.get("size_mm"), f"{name}.size_mm")
    require(all(size > 0 for size in box["size_mm"]), f"{name}: dimensions strictement positives")


def clearance_box(box, name, shape_ids):
    require(isinstance(box, dict), f"{name}: objet attendu")
    box_dimensions(box, name)
    excluded = box.get("ignore_ids", [])
    identifier_list(excluded, f"{name}.ignore_ids")
    require(set(excluded) <= shape_ids, f"{name}: exclusion hors inventaire")
    require(shape_ids - set(excluded), f"{name}: volume sans obstacle à contrôler")


def validate_geometry(geometry, links, ports):
    require(isinstance(geometry, dict), "system.geometry: objet attendu")
    boxes = indexed(geometry.get("boxes", []), "geometry.boxes")
    require(not boxes.keys() & links.keys(), "geometry.boxes: identifiant partagé avec une liaison")
    for key, box in boxes.items():
        box_dimensions(box, key)
        if "through_bore_x" in box:
            bore = box["through_bore_x"]
            require(isinstance(bore, dict) and set(bore) == {"center_yz_mm", "radius_mm"},
                    f"{key}.through_bore_x: centre YZ et rayon attendus")
            center = bore["center_yz_mm"]
            require(isinstance(center, list) and len(center) == 2, f"{key}.through_bore_x: couple YZ attendu")
            radius = bore["radius_mm"]
            number(radius, f"{key}.through_bore_x.radius_mm", 0)
            for coordinate in center:
                number(coordinate, f"{key}.through_bore_x.center_yz_mm")
            require(radius > 0 and all(origin + radius < coordinate < origin + size - radius
                                      for coordinate, origin, size in zip(center, box["origin_mm"][1:], box["size_mm"][1:])),
                    f"{key}.through_bore_x: alésage intérieur strictement positif attendu")
    shape_ids = boxes.keys() | links.keys()
    extraction = geometry.get("extraction", [])
    require(isinstance(extraction, list), "geometry.extraction: liste attendue")
    extracted_ports = set()
    for box in extraction:
        clearance_box(box, "geometry.extraction", shape_ids)
        port = identifier(box.get("port"), "geometry.extraction.port")
        require(port in ports and port not in extracted_ports, f"extraction {port}: port absent ou dupliqué")
        extracted_ports.add(port)
    for key, anchor in indexed(geometry.get("anchors", []), "geometry.anchors").items():
        for field in ("object", "anchor"):
            native = identifier(anchor.get(field), f"{key}.{field}")
            require(native in boxes, f"{key}.{field}: objet hors inventaire des volumes")
        require(anchor["object"] != anchor["anchor"], f"{key}: ancrage sur lui-même")
        if "access_box" in anchor:
            clearance_box(anchor["access_box"], f"{key}.access_box", shape_ids)
        stations = anchor.get("retentions", [])
        require(isinstance(stations, list), f"{key}.retentions: liste attendue")
        for station in stations:
            require(isinstance(station, dict), f"{key}.retentions: objet attendu")
            link = identifier(station.get("link"), f"{key}.retentions.link")
            require(link in links, f"{key}.retentions: liaison absente {link}")
            vector(station.get("point_mm"), f"{key}.retentions.point_mm")
            enclosure = station.get("enclosure")
            require(isinstance(enclosure, dict), f"{key}.retentions.enclosure: objet attendu")
            box_dimensions(enclosure, f"{key}.retentions.enclosure")
            wall = station.get("capture_wall_mm")
            number(wall, f"{key}.retentions.capture_wall_mm", 0)
            require(wall > 0, f"{key}.retentions.capture_wall_mm: épaisseur strictement positive")
            nonempty_text(station.get("source"), f"{key}.retentions.source")
    states = geometry.get("motion_states", {})
    require(isinstance(states, dict), "geometry.motion_states: objet attendu")
    for key, state in states.items():
        identifier(key, "geometry.motion_states")
        require(isinstance(state, dict), f"{key}: état de mouvement attendu")
        provenance(state.get("provenance"), f"état {key}")
        port_poses, box_poses = state.get("ports", {}), state.get("boxes", {})
        require(isinstance(port_poses, dict) and set(port_poses) <= ports.keys(), f"{key}: ports hors référentiel")
        require(isinstance(box_poses, dict) and set(box_poses) <= boxes.keys(), f"{key}: volumes hors référentiel")
        for port_id, pose in port_poses.items():
            name = f"état {key}, port {port_id}"
            require(isinstance(pose, dict), f"{name}: pose attendue")
            vector(pose.get("position_mm"), f"{name}.position_mm")
            vector(pose.get("tangent"), f"{name}.tangent")
            require(math.hypot(*pose["tangent"]) > 0, f"{name}: tangente nulle")
        for box_id, pose in box_poses.items():
            name = f"état {key}, volume {box_id}"
            require(isinstance(pose, dict) and set(pose) == {"translation_mm"}, f"{name}: translation seule prise en charge")
            vector(pose["translation_mm"], f"{name}.translation_mm")


def validate_system(system):
    versioned(system, "system_model")
    identifier(system.get("id"), "system.id")
    nonempty_text(system.get("revision"), "system.revision")
    nonempty_text(system.get("frame"), "system.frame")
    provenance(system.get("provenance"), "system")
    equipment = indexed(system.get("equipment"), "equipment")
    ports = indexed(system.get("ports"), "ports")
    links = indexed(system.get("links"), "links")
    require(links, "system.links: périmètre vide")
    for key, port in ports.items():
        device = identifier(port.get("equipment"), f"port {key}.equipment")
        require(device in equipment, f"port {key}: équipement absent")
        require(isinstance(port.get("status"), str) and port["status"] in STATUSES,
                f"port {key}: statut invalide")
        if port.get("interface") is not None:
            nonempty_text(port["interface"], f"port {key}.interface")
            require(port["status"] != "INCONNUE", f"port {key}: interface avec statut INCONNUE")
        for field in ("position_mm", "tangent"):
            if port.get(field) is not None:
                vector(port[field], f"port {key}.{field}")
        if port.get("tangent") is not None:
            require(math.hypot(*port["tangent"]) > 0, f"port {key}: tangente nulle")
        if "retained_endpoint" in port:
            require(type(port["retained_endpoint"]) is bool, f"port {key}.retained_endpoint: booléen attendu")
        for option_id, option in indexed(port.get("connector_options", []), f"{key}.connector_options").items():
            require(isinstance(option.get("status"), str) and option["status"] in STATUSES,
                    f"{option_id}: statut de connecteur invalide")
            if option.get("interface") is not None:
                nonempty_text(option["interface"], f"{option_id}.interface")
            if option["status"] != "INCONNUE":
                nonempty_text(option.get("source"), f"{option_id}.source")
    for key, link in links.items():
        source = identifier(link.get("source"), f"{key}.source")
        target = identifier(link.get("target"), f"{key}.target")
        require(source in ports and target in ports and source != target, f"liaison {key}: extrémités invalides")
        nonempty_text(link.get("family"), f"liaison {key}.family")
        if "mobile" in link:
            require(type(link["mobile"]) is bool, f"liaison {key}.mobile: booléen attendu")
        for field in ("source_cavities", "target_cavities"):
            if link.get(field) is not None:
                identifier_list(link[field], f"{key}.{field}")
    for key, corridor in indexed(system.get("corridors", []), "corridors").items():
        identifier(corridor.get("carrier"), f"corridor {key}.carrier")
        nonempty_text(corridor.get("zone"), f"corridor {key}.zone")
        path_points(corridor.get("points_mm"), f"corridor {key}.points_mm")
        if corridor.get("width_mm") is not None:
            number(corridor["width_mm"], f"corridor {key}.width_mm", 0)
        if corridor.get("max_carrier_distance_mm") is not None:
            number(corridor["max_carrier_distance_mm"], f"corridor {key}.max_carrier_distance_mm", 0)
    for collection in (equipment.values(), ports.values(), links.values(), system.get("corridors", [])):
        for item in collection:
            if "provenance" in item:
                provenance(item["provenance"], item["id"])
    validate_geometry(system.get("geometry", {}), links, ports)


def validate_requirements(system, requirements):
    versioned(requirements, "design_requirements")
    require(requirements.get("system_id") == system["id"], "exigences pour un autre système")
    nonempty_text(requirements.get("revision"), "exigences.revision")
    provenance(requirements.get("provenance"), "exigences")
    for key in ("clearance_mm", "collision_tolerance_mm3"):
        number(requirements.get(key), key, 0)
    for key in ("position_tolerance_mm", "clearance_tolerance_mm"):
        if key in requirements:
            number(requirements[key], key, 0)
    require(requirements.get("position_tolerance_mm", 1e-5) > 0,
            "position_tolerance_mm: tolérance strictement positive")
    links = requirements.get("links")
    require(isinstance(links, dict) and set(links) == {link["id"] for link in system["links"]},
            "les exigences doivent couvrir toutes les liaisons et seulement elles")
    for key, rule in links.items():
        require(isinstance(rule, dict), f"{key}: objet exigence attendu")
        for field in ("diameter_mm", "min_radius_mm"):
            require(field in rule, f"{key}: {field} obligatoire (null si inconnue)")
        for field in ("diameter_mm", "min_radius_mm", "min_dynamic_radius_mm", "max_unsupported_mm",
                      "min_reserve_mm", "motion_length_tolerance_mm"):
            if rule.get(field) is not None:
                number(rule[field], f"{key}.{field}", 0)
        for field in ("diameter_mm", "min_radius_mm", "min_dynamic_radius_mm"):
            require(rule.get(field) != 0, f"{key}.{field}: valeur strictement positive ou null")
        if "requires_support" in rule:
            require(type(rule["requires_support"]) is bool, f"{key}.requires_support: booléen attendu")
        states = rule.get("required_motion_states", [])
        identifier_list(states, f"{key}.required_motion_states")
        if "provenance" in rule:
            provenance(rule["provenance"], key)
    for state, pose in system.get("geometry", {}).get("motion_states", {}).items():
        consumed = {key for key, rule in links.items() if state in rule.get("required_motion_states", [])}
        moved = pose.get("ports", {}).keys()
        affected = {link["id"] for link in system["links"] if {link["source"], link["target"]} & moved}
        require(consumed and affected <= consumed,
                f"état {state}: contrôle requis pour toutes les liaisons aux ports mobiles")
    ports = {port["id"] for port in system["ports"]}
    extraction = requirements.get("extraction_ports", [])
    identifier_list(extraction, "extraction_ports")
    require(set(extraction) <= ports, "ports d'extraction absents du système")
    for key, support in indexed(requirements.get("supports", []), "supports").items():
        identifier(support.get("anchor"), f"{key}.anchor")
    contacts = requirements.get("allowed_contacts", [])
    require(isinstance(contacts, list), "allowed_contacts: liste attendue")
    shape_ids = set(links) | {box["id"] for box in system.get("geometry", {}).get("boxes", [])}
    retaining_objects = {anchor["object"] for anchor in system.get("geometry", {}).get("anchors", [])
                         if anchor.get("retentions")}
    seen = set()
    for contact in contacts:
        require(isinstance(contact, dict), "allowed_contacts: objet attendu")
        for field in ("a", "b", "relation", "source"):
            nonempty_text(contact.get(field), f"allowed_contacts.{field}")
        require(contact["a"] != contact["b"], "allowed_contacts: auto-contact")
        pair = frozenset((contact["a"], contact["b"]))
        require(pair <= shape_ids and pair not in seen, "allowed_contacts: paire hors inventaire ou dupliquée")
        seen.add(pair)
        require(contact["relation"] in {"functional_contact", "cable_in_conduit_envelope"},
                "allowed_contacts: relation inconnue")
        if contact["relation"] == "cable_in_conduit_envelope":
            require(contact["a"] in links and contact["b"] not in links
                    and contact.get("outer_representation") == "occupancy_envelope",
                    "allowed_contacts: inclusion exige un câble et une enveloppe d'occupation identifiés")
            require(contact["b"] not in retaining_objects,
                    "allowed_contacts: une enveloppe d'occupation n'est pas un solide de retenue")
    objectives = requirements.get("objectives")
    require(isinstance(objectives, list) and bool(objectives), "objectives: liste non vide attendue")
    for objective in objectives:
        identifier(objective, "objective")
    require(len(set(objectives)) == len(objectives), "objectifs dupliqués")
    plateaux = requirements.get("plateaux_mm")
    require(isinstance(plateaux, list) and len(plateaux) == 2, "plateaux_mm: deux altitudes attendues")
    for altitude in plateaux:
        number(altitude, "plateaux_mm")
    require(plateaux[0] < plateaux[1], "plateaux_mm: ordre bas vers haut attendu")


def validate_motion_routes(routes, system=None, requirements=None):
    require(isinstance(routes, dict), "candidate.motion_routes: objet attendu")
    if system is not None:
        states = system.get("geometry", {}).get("motion_states", {})
        links = {item["id"] for item in system["links"]}
        require(routes.keys() <= states.keys(), "candidate.motion_routes: état hors référentiel")
    for state, paths in routes.items():
        identifier(state, "candidate.motion_routes")
        require(isinstance(paths, dict), f"état {state}: routes attendues")
        if system is not None:
            require(paths.keys() <= links, f"état {state}: liaison hors référentiel")
        for link, route in paths.items():
            identifier(link, f"état {state}")
            name = f"état {state}, route {link}"
            if requirements is not None:
                require(state in requirements["links"][link].get("required_motion_states", []),
                        f"{name}: mouvement de liaison non prévu par les exigences")
            require(isinstance(route, dict) and set(route) <= {"points_mm", "bend_radius_mm"},
                    f"{name}: géométrie de route seule attendue")
            path_points(route.get("points_mm"), f"{name}.points_mm")
            number(route.get("bend_radius_mm", 0), f"{name}.bend_radius_mm", 0)


def validate_candidate(candidate, reference_sha256, system=None, requirements=None):
    versioned(candidate, "candidate")
    identifier(candidate.get("id"), "candidate.id")
    require(isinstance(candidate.get("family"), str) and candidate["family"] in FAMILIES,
            "candidate.family: famille inconnue")
    require(candidate.get("reference_sha256") == reference_sha256, "candidat lié à un autre référentiel")
    require(not ({"system", "requirements", "allowed_contacts", "objectives"} & candidate.keys()),
            "un candidat ne peut embarquer ni critères ni référentiel")
    connections = candidate.get("connections")
    require(isinstance(connections, list), "candidate.connections: liste attendue")
    # Les doublons et ports erronés sont du ressort du validateur V1.
    for connection in connections:
        require(isinstance(connection, dict), "candidate.connections: objet attendu")
        for field in ("id", "source", "target"):
            identifier(connection.get(field), f"candidate.connections.{field}")
        for field in ("source_connector", "target_connector"):
            if connection.get(field) is not None:
                identifier(connection[field], f"candidate.connections.{field}")
        for field in ("source_interface", "target_interface"):
            if connection.get(field) is not None:
                nonempty_text(connection[field], f"candidate.connections.{field}")
        for field in ("source_cavities", "target_cavities"):
            if connection.get(field) is not None:
                identifier_list(connection[field], f"candidate.connections.{field}")
    routes = candidate.get("routes")
    require(isinstance(routes, dict), "candidate.routes: objet attendu")
    for link, route in routes.items():
        identifier(link, "candidate.routes")
        require(isinstance(route, dict), f"route {link}: objet attendu")
        path_points(route.get("points_mm"), f"route {link}.points_mm")
        identifier(route.get("corridor"), f"route {link}.corridor")
        if route.get("bend_radius_mm") is not None:
            number(route["bend_radius_mm"], f"route {link}.bend_radius_mm", 0)
    validate_motion_routes(candidate.get("motion_routes", {}), system, requirements)
    for key, support in indexed(candidate.get("supports", []), "candidate.supports").items():
        identifier(support.get("anchor"), f"{key}.anchor")
    require(isinstance(candidate.get("changes", {}), dict), "candidate.changes: objet attendu")
    hypotheses = candidate.get("hypotheses", [])
    require(isinstance(hypotheses, list), "candidate.hypotheses: liste attendue")
    for hypothesis in hypotheses:
        nonempty_text(hypothesis, "candidate.hypotheses")


def open_reference(project):
    project = Path(project)
    lock = load(project / "reference_lock.json")
    versioned(lock, "reference_lock")
    content = {name: (project / name).read_bytes() for name in REFERENCE_FILES}
    actual = {name: hashlib.sha256(raw).hexdigest() for name, raw in content.items()}
    require(lock.get("files") == actual and lock.get("reference_sha256") == digest_value(actual),
            "empreinte du référentiel divergente")
    system, requirements = (decode(name, content[name]) for name in REFERENCE_FILES)
    validate_system(system)
    validate_requirements(system, requirements)
    return system, requirements, lock


def freeze(project, output):
    project, output = Path(project).resolve(), Path(output).resolve()
    inputs = {name: (project / name).read_bytes() for name in REFERENCE_FILES}
    system, requirements = (decode(name, inputs[name]) for name in REFERENCE_FILES)
    validate_system(system)
    validate_requirements(system, requirements)
    output.mkdir(parents=True, exist_ok=False)
    for name, content in inputs.items():
        with (output / name).open("xb") as stream:
            stream.write(content)
    files = {name: hashlib.sha256(content).hexdigest() for name, content in inputs.items()}
    lock = {"version": 1, "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
            "files": files, "reference_sha256": digest_value(files)}
    require(files == {name: digest(output / name) for name in REFERENCE_FILES},
            "copies du référentiel modifiées pendant le gel")
    require(files == {name: digest(project / name) for name in REFERENCE_FILES},
            "sources du référentiel modifiées pendant le gel")
    write(output / "reference_lock.json", lock)
    open_reference(output)
    return lock
