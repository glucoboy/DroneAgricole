"""Prépare les entrées de la CLI L2/L4 à partir des preuves gelées et des FCStd."""

import argparse
import collections
import csv
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import xml.etree.ElementTree as ET
import zipfile


ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / ".runtime/v21-go3b-electrical"
VERIFICATION = ROOT / "docs/verification"
GO3A = VERIFICATION / "go3a"
ACTIVE = ROOT / "hardware/mecanique/cartographe"
MODEL = GO3A / "GO3A_SYSTEM_MODEL.json"
MATRIX = GO3A / "GO3A_INTERCONNECTION_MATRIX.csv"
BOM = GO3A / "GO3A_CONNECTOR_BOM.csv"
EXCEPTIONS = VERIFICATION / "go3b/GO3B_INTERCONNECTION_COVERAGE.csv"
INVENTORY = ACTIVE / "verification/refonte_faisceaux/inventaire.json"
F12_WITNESS = VERIFICATION / "cartographe_action3_reprise_f12.json"
F16_WITNESS = VERIFICATION / "cartographe_action3_f16.json"
DIAGNOSTIC = GO3A / "GO3A_VARIANT_EVIDENCE.json"
ENERGY = Path("sous_assemblages/SA03_Prototype_Energie.FCStd")
ELECTRONICS = ROOT / "hardware/electronique/cartographe"
NETLIST_SOURCE = ACTIVE / "verification/refonte_faisceaux/inventaire_netlist_ca01.json"
CONNECTOR_SOURCES = VERIFICATION / "v21_connector_sources.json"
UART = ELECTRONICS / "contrat_uart_bms.json"
WIRING = ELECTRONICS / "cablage_global.json"
L2 = ROOT / ".runtime/v21-xlink-build/interconnection/interconnection_core.exe"
L2_EXAMPLE = ROOT / "interconnection_engine/examples/cartographe_candidats.json"
DATE = "2026-11-17T00:00:00Z"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def relative(path):
    return path.resolve(strict=True).relative_to(ROOT).as_posix()


def sha256(path):
    with path.open("rb") as file:
        return hashlib.file_digest(file, "sha256").hexdigest()


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def receipt(path):
    return {"path": relative(path), "sha256": sha256(path)}


def index(rows, field):
    result = {}
    for row in rows:
        key = row[field]
        require(key and key not in result, f"Identité vide ou dupliquée {key}")
        result[key] = row
    return result


def read_csv(path, key):
    with path.open(encoding="utf-8-sig", newline="") as file:
        return index(csv.DictReader(file), key)


def property_(document, object_, name):
    return document.find(f"ObjectData/Object[@name='{object_}']/Properties/Property[@name='{name}']")


def native_document(path):
    with zipfile.ZipFile(path) as archive:
        return ET.fromstring(archive.read("Document.xml"))


def read_axis(path, cable_name):
    document = native_document(path)
    wire_link = property_(document, cable_name, "Base")
    if wire_link is not None:
        wire_name = wire_link[0].get("value")
    else:
        wire_name = "Wire"
    require(wire_name, f"Lien de définition d’axe absent: {path.name}")
    parts = property_(document, wire_name, "Links")
    segmented = [link.get("value") for link in parts.findall("LinkList/Link")] if parts is not None else [wire_name]
    endpoints = []
    for name, side in ((segmented[0], "Start"), (segmented[-1], "End")):
        vector = property_(document, name, side)
        if vector is None:
            return {"status": "INCONCLUSIVE", "reason": f"{name}/{side} absent"}
        xyz = [float(vector[0].get(f"value{axis}")) for axis in "XYZ"]
        require(all(math.isfinite(value) for value in xyz), f"Coordonnées invalides: {path.name}/{side}")
        endpoints.append(xyz)
    length = property_(document, wire_name, "Length")
    return {"status": "PASS", "endpoints_mm": endpoints,
            "axis_length_mm": float(length[0].get("value")) if length is not None else None}


def isolator_pose(path):
    document = native_document(path)
    placement = property_(document, "UART_isole", "LinkPlacement")[0]
    position = [float(placement.get(f"P{axis}")) for axis in "xyz"]
    x, y, z, w = (float(placement.get(f"Q{i}")) for i in range(4))
    rotation = [[1 - 2 * (y*y + z*z), 2 * (x*y - w*z), 2 * (x*z + w*y)],
                [2 * (x*y + w*z), 1 - 2 * (x*x + z*z), 2 * (y*z - w*x)],
                [2 * (x*z - w*y), 2 * (y*z + w*x), 1 - 2 * (x*x + y*y)]]
    return position, rotation


def apply_rotation(rotation, vector):
    return [sum(a * b for a, b in zip(row, vector)) for row in rotation]


def validate_diagnostic(cad, observations):
    frozen_translation, frozen_rotation = isolator_pose(ACTIVE / ENERGY)
    translation, rotation = isolator_pose(cad / ENERGY)
    frozen_inverse_rotation = list(zip(*frozen_rotation))
    frames = read_json(DIAGNOSTIC)["criblage_GO3A_diagnostic"]
    result = {"scope": "Vérification de raccordement aux réservations historiques, hors contacts qualifiés",
        "source": receipt(DIAGNOSTIC), "native_pose": receipt(cad / ENERGY),
        "reference_pose": receipt(ACTIVE / ENERGY), "control_tolerance_mm": 1e-6,
        "relocated": (translation, rotation) != (frozen_translation, frozen_rotation), "checks": {}}
    for label, route, moving in (("TTL", "F40", 1), ("USB-B", "F41", 0)):
        axis = observations[route]
        endpoint = axis.get("endpoints_mm", [None, None])[moving]
        opposite = axis.get("endpoints_mm", [None, None])[1 - moving]
        original = read_axis(ACTIVE / Path(axis["native_file"]["path"]).relative_to(cad.relative_to(ROOT)), "Cable")
        opposite_expected = original["endpoints_mm"][1 - moving]
        local = apply_rotation(frozen_inverse_rotation, [a - b for a, b in zip(frames["point_faces_mm"][label], frozen_translation)])
        predicted = [a + b for a, b in zip(translation, apply_rotation(rotation, local))]
        local_direction = apply_rotation(frozen_inverse_rotation, frames["axes_sortie"][label])
        predicted_direction = apply_rotation(rotation, local_direction)
        incoming_error = math.dist(endpoint, predicted) if endpoint is not None else None
        opposite_error = math.dist(opposite, opposite_expected) if opposite is not None else None
        result["checks"][route] = {"documentary_side": "W40/B" if moving == 1 else "W41/A",
            "port": label, "local_origin_mm": local, "local_exit_direction": local_direction,
            "transformed_origin_mm": predicted, "transformed_exit_direction": predicted_direction,
            "observed_mm": endpoint, "observed_other_end_mm": opposite, "frozen_other_end_mm": opposite_expected,
            "origin_error_mm": incoming_error, "other_end_error_mm": opposite_error,
            "reservation_status": ("INCONCLUSIVE" if incoming_error is None or opposite_error is None else
                                   ("PASS" if max(incoming_error, opposite_error) <= 1e-6 else "FAIL")),
            "mating_status": "INCONCLUSIVE", "withdrawal_status": "INCONCLUSIVE"}
    return result


def reconcile_candidate(cad, out):
    graph = read_json(WORK / "l2-interfaces.json")
    inventory = read_json(INVENTORY)
    lines = index(graph["lines"], "id")
    authority_lines = index(inventory["connections"], "id")
    matrix = read_csv(MATRIX, "liaison_id")
    exceptions = read_csv(EXCEPTIONS, "liaison_id")
    bom = read_csv(BOM, "cle_interface")
    require(lines.keys() == matrix.keys() == authority_lines.keys() == exceptions.keys(), "Couverture système divergente")
    require({side for line in graph["line_interfaces"].values() for side in line} == bom.keys() == graph["interfaces"].keys(),
            "Couverture des côtés divergente")
    inverse = collections.defaultdict(set)
    for name, line in lines.items():
        authority = authority_lines[name]
        reference = matrix[name]
        require(line["scope"] == authority["scope"] == reference["perimetre"] and line["class"] == reference["classe_l2"],
                f"Périmètre ou classe divergent: {name}")
        require(line["path"] == authority["path"], f"Parcours orienté divergent: {name}")
        require(line["cord_ids"] == authority["cable_ids"] and line["junction_ids"] == authority["junctions"],
                f"Cordon ou jonction divergente: {name}")
        if not line["path"]:
            require(exceptions[name]["motif_absence_axe"], f"Motif d’absence d’axe absent: {name}")
        for path in line["path"]:
            inverse[path["route_id"]].add(name)
        for side in graph["line_interfaces"][name]:
            interface = graph["interfaces"][side]
            side_letter = side.rsplit("/", 1)[-1]
            source_role = "origin" if side_letter == "A" else "destination"
            require(interface["side"] == bom[side]["extremite"] == side_letter and
                    bom[side]["libelle_autorite"] == (authority[source_role] or ""),
                    f"Identité de côté divergente: {side}")
    require(graph["axes"].keys() == inverse.keys() and sum(map(len, inverse.values())) == 56, "Associations d’axes incomplètes")
    cad_rel = relative(cad)
    require(cad_rel.startswith(".runtime/"), "Une copie privée sous .runtime est requise")
    observations = {}
    for route, axis in graph["axes"].items():
        require(inverse[route] == set(axis["line_ids"]), f"Liaison inverse divergente: {route}")
        original = ROOT / axis["native_file"]["path"]
        path = cad / original.relative_to(ACTIVE)
        path_rel = relative(path)
        require(path_rel.startswith(cad_rel + "/"), f"Axe hors copie: {route}")
        digest = sha256(path)
        axis["native_file"] = {"path": path_rel, "sha256": digest}
        graph["source_sha256"][path_rel] = digest
        if route == "F16" and digest == read_json(F16_WITNESS)["variante_f16_z10"]["donor"]["sha256"]:
            axis["native_object"] = "Cable002"
            graph["source_sha256"][relative(F16_WITNESS)] = sha256(F16_WITNESS)
        observations[route] = read_axis(path, axis["native_object"]) | {"native_file": axis["native_file"],
            "changed_from_freeze": digest != graph["source_sha256"][relative(original)]}
    write_json(out / "electrical.json", graph)
    witness = read_json(F12_WITNESS)
    expected = witness["candidate"]["endpoints_mm"]
    observed = observations["F12"].get("endpoints_mm")
    known_wrong = witness["before"]["endpoints_mm"][1]
    f12 = {"status": "INCONCLUSIVE", "expected_names": ["CA01 J402", "Pixhawk TELEM1"],
           "expected_reservations_mm": expected, "known_wrong_GPS2_mm": known_wrong,
           "observed_wire_properties_mm": observed, "tolerance_mm": 1e-6,
           "source": relative(F12_WITNESS), "scope": "Coordonnées sauvées de Wire/Start et Wire/End. Sans preuve d’accouplement."}
    if observed is not None:
        f12["status"] = "PASS" if all(math.dist(a, b) <= 1e-6 for a, b in zip(expected, observed)) else "FAIL"
    write_json(out / "axis-endpoints.json", {"scope": cad_rel, "axis_count": len(observations),
                  "axes": observations, "F12_TELEM1": f12})
    return graph, inventory, observations, f12


def verified_netlist():
    reference = read_json(NETLIST_SOURCE)
    for sheet in reference["scheme_sources"]:
        require(sha256(ROOT / sheet["path"]) == sheet["sha256"], f"Feuille CA01 divergente: {sheet['path']}")
    expected = reference["candidate_ca01_netlist_pins"]
    netlist_path = WORK / "ca01.xml"
    doc = ET.parse(netlist_path)
    selected = {ref: {} for ref in expected}
    for net in doc.findall("nets/net"):
        for node in net.findall("node"):
            ref, pin = node.get("ref"), node.get("pin")
            if ref in selected:
                require(pin not in selected[ref], f"Broche CA01 attribuée deux fois: {ref}/{pin}")
                selected[ref][pin] = net.get("name")
    require(selected == expected, "Brochage CA01 divergent de l’inventaire gelé")
    required_dnp = {"R530", "R531", "R532", "R533"}
    observed_dnp = {node.get("ref") for node in doc.findall("components/comp")
                    if node.find("property[@name='dnp']") is not None}
    require(required_dnp <= observed_dnp, "Population documentaire R530 à R533 modifiée")
    return selected, {"status": "PASS", "reference": receipt(NETLIST_SOURCE), "netlist": receipt(netlist_path),
                      "sheet_count": len(reference["scheme_sources"]), "port_count": len(selected),
                      "pin_count": sum(map(len, selected.values())), "schematic_sources": reference["scheme_sources"],
                      "documented_dnp": sorted(required_dnp)}


def assumption(value=None, unit="1", evidence_ids=()):
    return {"value": value, "unit": unit, "status": "ESTIMATED" if value is not None else "UNKNOWN",
            "evidence_ids": list(evidence_ids), "revision": None, "collected_at": DATE, "precision": None,
            "uncertainty": None, "method": "Rapprochement documentaire" if value is not None else None,
            "input_value_refs": [], "limits": "Référence, contact ou cote sans preuve de montage sur le lot."}


def document_proof(proof_id, path, locator=None, domain="DOCUMENT"):
    return {"id": proof_id, "kind": "SOURCE", "domain": domain, "artifact_path": relative(path), "uri": None,
            "sha256": sha256(path), "locator": locator, "revision": "GO3B-20261117", "collected_at": DATE,
            "method": "Rapprochement du gel et observations de la copie privée", "hypothetical": False,
            "limits": "Portée documentaire ou CAO. Applicabilité et continuité physiques ouvertes."}


def pin_role(signal):
    if signal.startswith("unconnected-") or signal.startswith("NC"):
        return "RESERVED"
    if signal == "GND" or signal.endswith("_RETURN") or signal == "BAT_MOINS_BRUT_ISOLE":
        return "RETURN"
    if signal in {"VBAT_PAYLOAD", "12V_COMPUTE", "12V_LIDAR", "5V_AUX", "5V_SYNC", "3V3_ORIN_IO_REF", "5V_RADIO"}:
        return "POWER"
    return "SIGNAL"


def prepare_l2(graph, inventory, ca01, f12, out):
    dossier = read_json(L2_EXAMPLE)
    model = dossier["model"]
    model["configuration_id"] = "prototype_cartographe_go3b"
    model["states"][0]["description"] = "Projection documentaire de la copie GO3B au nominal sauvegardé"
    records = model["records"]
    for items in records.values():
        items.clear()
    dossier["catalog"] = {"parts": [], "pairs": []}
    dossier["interfaces"] = []
    dossier["cable_parts"] = {}
    dossier["research_issue_ids"] = []
    records["technical_evidence"] = [document_proof("E.MATRIX", MATRIX), document_proof("E.BOM", BOM),
        document_proof("E.WIRING", WIRING), document_proof("E.CONNECTOR", CONNECTOR_SOURCES),
        document_proof("E.UART", UART), document_proof("E.CA01", WORK / "ca01.xml"),
        document_proof("E.AXES", out / "axis-endpoints.json", domain="CAD")]
    side_bom = read_csv(BOM, "cle_interface")
    electrical_rows = index(inventory["connections"], "id")
    harnesses = index(inventory["harnesses"], "id")
    equipment = {}
    port_keys = {}
    ports = {}
    pin_maps = {}
    side_to_port = {}
    end_keys = {}
    cable_ends = collections.defaultdict(list)
    projections = []
    for key, side in graph["interfaces"].items():
        bom = side_bom[key]
        label = side["functional_port"] or f"Port inconnu {key}"
        equipment_id = side["equipment_id"] or "EQ.INCONNU." + side["port_record_id"]
        if equipment_id not in equipment:
            equipment[equipment_id] = {"id": equipment_id, "item_reference": assumption(
                side["equipment_reference_documentary"] or None, evidence_ids=["E.BOM"]),
                "native_anchor": None, "evidence_ids": ["E.BOM"]}
        port_key = (equipment_id, label)
        port_id = port_keys.setdefault(port_key, "P." + side["port_record_id"])
        side_to_port[key] = port_id
        if port_id not in ports:
            ports[port_id] = {"id": port_id, "equipment_id": equipment_id, "function": label,
                "direction": "UNKNOWN", "frame_id": None, "origin_mm": None, "exit_axis": None,
                "evidence_ids": ["E.MATRIX"]}
        if equipment_id == "AVI-CA01":
            match = re.fullmatch(r"CA01 (J\d+|MOD\d+)", label)
            if match and match[1] in ca01:
                pin_maps[port_id] = (ca01[match[1]], "E.CA01")
        connection = electrical_rows[side["line_id"]]
        if connection["scope"] != "faisceau_embarque":
            continue
        require(len(connection["cable_ids"]) == 1, f"Cordon ambigu pour {key}")
        cable = connection["cable_ids"][0]
        end_key = (cable, port_id)
        if end_key in end_keys:
            projections.append({"side": key, "cord": cable, "logical_end": end_keys[end_key], "port": port_id})
            continue
        end_id = "End." + side["port_record_id"]
        end_keys[end_key] = end_id
        cable_ends[cable].append(end_id)
        receptacle = "R." + port_id
        if not any(row["id"] == receptacle for row in records["connector_receptacles"]):
            records["connector_receptacles"].append({"id": receptacle, "port_id": port_id,
                "part_reference": assumption(bom["embase_candidate"] or None, evidence_ids=["E.BOM"]),
                "frame_id": None, "origin_mm": None, "orientation": None, "locking": assumption(),
                "family": assumption(), "keying": assumption(), "evidence_ids": ["E.BOM"]})
        mate = "M." + side["port_record_id"]
        records["connector_mates"].append({"id": mate, "cable_id": cable, "end_id": end_id,
            "receptacle_id": receptacle, "part_reference": assumption(bom["fiche_cordon_candidat"] or None, evidence_ids=["E.BOM"]),
            "assembly_state": "UNKNOWN", "family": assumption(), "keying": assumption(), "evidence_ids": ["E.BOM"]})
        dossier["interfaces"].append({"id": side["port_record_id"], "cable_id": cable, "end_id": end_id,
            "mate_id": mate, "required_port_id": port_id,
            "component_part_ids": [], "required_component_roles": []})
        projections.append({"side": key, "cord": cable, "logical_end": end_id, "port": port_id})

    # Le graphe source conserve toutes les lignes et leurs alias de côté. Les
    # épissures, les cavités réelles et les contacts restent sans modèle avéré.
    records["equipment"] = list(equipment.values())
    records["ports"] = list(ports.values())
    for cable, ends in cable_ends.items():
        candidate = harnesses[cable]["manufacturer_reference_or_candidate"]
        records["cables"].append({"id": cable, "part_reference": assumption(candidate, evidence_ids=["E.BOM"]),
            "kind": "UNKNOWN", "end_ids": ends, "conductors": [], "outer_diameter_mm": assumption(unit="mm"),
            "min_static_radius_mm": assumption(unit="mm"), "min_dynamic_radius_mm": assumption(unit="mm"),
            "linear_mass_g_m": assumption(unit="g/m"), "evidence_ids": ["E.BOM"]})
    uart_contract = read_json(UART)
    bms = {str(pin["pin"]): pin.get("net", "NC_VDD" if pin.get("connection") == "NC" else pin["function"])
           for pin in uart_contract["bms"]["pins"]}
    for side, mapping, evidence in (("W12/B", {"2": "TX7", "3": "RX7", "6": "GND"}, "E.CONNECTOR"),
                                   ("W31/B", {"1": "NC_+5V", "2": "CAN_H", "3": "CAN_L", "4": "GND"}, "E.WIRING"),
                                   ("W40/A", bms, "E.UART"),
                                   ("W24.A/B", {"2": "GPIO_07", "6": "GND"}, "E.CONNECTOR")):
        pin_maps[side_to_port[side]] = (mapping, evidence)
    for port, (signals, evidence) in pin_maps.items():
        for pin, signal in signals.items():
            records["pins"].append({"id": f"{port}.pin{pin}", "port_id": port, "number": pin,
                "signal": signal, "role": pin_role(signal), "evidence_ids": [evidence]})

    for line, maps in {
        "W12": [("GND", "RETURN", "1", "6"), ("FC_RX_RF", "SIGNAL", "2", "2"), ("FC_TX_RF", "SIGNAL", "3", "3")],
        "W24.A": [("PPS_ORIN", "SIGNAL", "1", "2"), ("GND", "RETURN", "2", "6")],
        "W31": [("CAN_H", "SIGNAL", None, "2"), ("CAN_L", "SIGNAL", None, "3"), ("GND", "RETURN", None, "4")],
        "W40": [("TTL_GND_BRUT", "RETURN", "1", None), ("RXD_BMS/TXD_ISO", "SIGNAL", "2", None),
                ("TXD_BMS/RXD_ISO", "SIGNAL", "3", None)],
    }.items():
        for i, (function, role, pin_a, pin_b) in enumerate(maps, start=1):
            sides = [(side, pin) for side, pin in (("A", pin_a), ("B", pin_b)) if pin]
            records["circuits"].append({"id": f"C.{line}.{i}", "group_id": None, "function": function,
                "kind": role, "scope": "ONBOARD", "pin_ids": [f"{side_to_port[f'{line}/{side}']}.pin{pin}" for side, pin in sides],
                "spans": [], "evidence_ids": ["E.WIRING"]})
    for route_id, axis in graph["axes"].items():
        cable_ids = sorted({cord for line in axis["line_ids"] for cord in electrical_rows[line]["cable_ids"]})
        records["routes"].append({"id": route_id, "representation": "SHARED_AXIS" if len(axis["line_ids"]) > 1 else "RESERVATION",
            "frame_id": "root", "state_id": "nominal", "cable_ids": cable_ids, "segment_ids": [],
            "geometry_kind": "NATIVE", "points_mm": None,
            "native_anchor": {"evidence_id": "E.AXES", "object_name": axis["native_object"],
                "occurrence_path": [axis["assembly_occurrence"]], "subelement": None}, "evidence_ids": ["E.AXES"]})

    if f12["status"] == "FAIL" and f12["observed_wire_properties_mm"][1] == f12["known_wrong_GPS2_mm"]:
        wrong = dict(ports[side_to_port["W12/B"]], id="P.GPS2.CONNU", function="Pixhawk GPS2")
        records["ports"].append(wrong)
        receptacle = dict(next(row for row in records["connector_receptacles"] if row["port_id"] == side_to_port["W12/B"]),
                          id="R.GPS2.CONNU", port_id=wrong["id"])
        records["connector_receptacles"].append(receptacle)
        next(row for row in records["connector_mates"] if row["id"] == "M.W12-B")["receptacle_id"] = receptacle["id"]
    write_json(out / "l2-dossier.json", dossier)
    write_json(out / "l2-correspondence.json", {"sides_all": side_to_port, "logical_harness_sides": projections,
        "logical_ends": sum(map(len, cable_ends.values())), "available_documentary_pins": len(records["pins"]),
        "contact_cavities_native": 0, "onboard_cords": len(cable_ends), "physical_cords_verified": 0})
    return dossier


def run_l2(dossier, report):
    command = [relative(L2), "validate", relative(dossier), "--output", report.relative_to(ROOT).as_posix()]
    run = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=ROOT, check=False)
    report.with_suffix(".log").write_bytes(run.stdout)
    require(run.returncode in (0, 2, 3), f"Erreur CLI L2: {run.returncode}")
    result = read_json(report)
    return {"command": command, "exit_code": run.returncode, "status": result["status"],
        "electrical": result["electrical"], "compatibility": result["compatibility"], "geometry": result["geometry"],
        "report": receipt(report), "findings": dict(collections.Counter(finding["status"] for finding in result["findings"])),
        "continuity_proven": len(result["continuity"]),
        "failures": [finding for finding in result["findings"] if finding["status"] == "FAIL"]}


def candidate_bom(graph, inventory, observations, f12, diagnostic, out):
    bom = read_csv(BOM, "cle_interface")
    lines = index(graph["lines"], "id")
    written = []
    for key, row in bom.items():
        line = lines[row["liaison_id"]]
        axis_records = []
        side_sources = json.loads(row["repere_bout_axe_global"] or "[]")
        for source in side_sources:
            point = source["valeur"]
            route = point["route_id"]
            require(route in {entry["route_id"] for entry in line["path"]}, f"Axe attaché au mauvais côté: {key}")
            observation = observations[route]
            end_index = {"debut": 0, "fin": 1}[point["cote_natif"]]
            observed = observation.get("endpoints_mm", [None, None])[end_index]
            axis_records.append({"axis": route, "axis_end": point["cote_natif"], "observation": observed,
                "native_file": observation["native_file"], "status": observation["status"]})
        layout_status = "INCONCLUSIVE" if axis_records else "NOT_RUN"
        if key == "W12/B":
            layout_status = f12["status"]
        for row_diagnostic in diagnostic["checks"].values():
            if key == row_diagnostic["documentary_side"]:
                layout_status = row_diagnostic["reservation_status"]
        written.append({"line_id": row["liaison_id"], "side": row["extremite"], "side_key": key,
            "scope": line["scope"], "line_class": line["class"], "functional_port": graph["interfaces"][key]["functional_port"],
            "device_candidate": row["reference_appareil_candidate"], "receptacle_candidate": row["embase_candidate"],
            "plug_candidate": row["fiche_cordon_candidat"], "documented_contacts": row["contacts_documentaires"],
            "confirmed_device_revision": row["revision_physique_confirmee"] or None,
            "cord_or_inclusion_ids": line["cord_ids"], "axis_endpoints": axis_records,
            "layout_reservation_status": layout_status, "contacts_physical": "INCONCLUSIVE" if axis_records else "NOT_RUN",
            "mating_and_withdrawal": "NOT_RUN", "sources": row["sources"], "condition_to_close": row["condition_a_lever"]})
    cords = []
    for cord in inventory["harnesses"]:
        measured = {route: observations[route]["axis_length_mm"] for route in cord["route_ids"]
                    if observations[route]["status"] == "PASS"}
        cords.append(cord | {"axis_lengths_observed_mm": measured, "cut_length_mm": None,
            "scope_of_lengths": "Axes distincts CAO, épissures, gaines partagées et inclusions OEM à instruire."})
    write_json(out / "connector-bom.json", {"status": "INCONCLUSIVE", "scope": "Nomenclature de revue sur copie privée",
        "connector_sides": written, "cords_without_double_counting": cords, "junctions": inventory["junctions"]})
    with (out / "connector-bom.csv").open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=list(written[0]))
        writer.writeheader()
        for row in written:
            writer.writerow({key: json.dumps(value, ensure_ascii=False, separators=(",", ":")) if isinstance(value, list) else value
                             for key, value in row.items()})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cad", type=Path)
    parser.add_argument("out", type=Path)
    parser.add_argument("--validate-l2", action="store_true")
    args = parser.parse_args()
    require(args.out.resolve().is_relative_to(WORK), "Les preuves doivent rester sous .runtime/v21-go3b-electrical")
    graph, inventory, observations, f12 = reconcile_candidate(args.cad.resolve(), args.out.resolve())
    if args.validate_l2:
        ca01, netlist_proof = verified_netlist()
        dossier = prepare_l2(graph, inventory, ca01, f12, args.out.resolve())
        report = run_l2(args.out.resolve() / "l2-dossier.json", args.out.resolve() / "l2-validation.json")
        diagnostic = validate_diagnostic(args.cad.resolve(), observations)
        candidate_bom(graph, inventory, observations, f12, diagnostic, args.out.resolve())
        shifted_observations = {**observations, "F40": {**observations["F40"]}}
        if not args.cad.resolve().parent.name.startswith("baseline") and diagnostic["checks"]["F40"]["reservation_status"] == "PASS":
            start, end = observations["F40"]["endpoints_mm"]
            shifted_observations["F40"]["endpoints_mm"] = [start, [end[0] + 1, *end[1:]]]
            negative = validate_diagnostic(args.cad.resolve(), shifted_observations)["checks"]["F40"]
            require(negative["reservation_status"] == "FAIL", "La sonde de décalage F40 n’est pas discriminée")
            write_json(args.out.resolve() / "negative-frame.json", {"status": "PASS",
                "test": "Décalage de +1 mm en X de la capture d’extrémité sur une projection de preuve séparée.",
                "native_copy_unchanged": True, "probe": negative})
        if f12["status"] == "PASS":
            mates = index(dossier["model"]["records"]["connector_mates"], "id")
            mates["M.W12-B"]["receptacle_id"] = mates["M.W12-A"]["receptacle_id"]
            negative_dossier = args.out.resolve() / "negative-side-dossier.json"
            write_json(negative_dossier, dossier)
            negative_result = run_l2(negative_dossier, args.out.resolve() / "negative-side-validation.json")
            require(any(finding["code"] == "WRONG_PORT" and finding["subject_id"] == "W12-B"
                        for finding in negative_result["failures"]), "Le mauvais côté W12 n’est pas discriminé")
            write_json(args.out.resolve() / "negative-side.json", {"status": "PASS", "report": negative_result,
                "test": "Permutation d’embase W12/B vers W12/A sur une copie séparée du dossier L2.",
                "native_copy_unchanged": True})
        write_json(args.out.resolve() / "l2-summary.json", {"validation": report, "ca01": netlist_proof, "diagnostic": diagnostic})
