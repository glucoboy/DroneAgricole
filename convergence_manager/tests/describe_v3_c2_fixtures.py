"""Écrit les autorités de banc C.2 à partir de fermetures natives neuves."""

import argparse
from copy import deepcopy
import math
from pathlib import Path
import shutil

from describe_v3_b1_fixture import action, pose
from replay_v3_b1 import ROOT, digest, load, write


V3 = ROOT / "docs/electromechanical_v3"


def port_rules(index, metadata, secondary):
    moving = index == 1
    angle = math.radians(20 if secondary else 15)
    terminal = metadata["port_d_local"] if moving else pose(0, 0, 14)
    mount_axis = [0, -math.sin(angle), math.cos(angle)] if moving else [0, 0, 1]
    frames = metadata["frames"][index]

    def local(depth):
        return dict(rotation_xyzw=terminal["rotation_xyzw"],
                    translation_mm=[value - (14 - depth) * axis for value, axis in
                                    zip(terminal["translation_mm"], mount_axis, strict=True)])

    return dict(equipment="payload" if moving else "device-c",
                attachment_equipment="device-d" if moving else "device-c",
                frame=frames["WireExit"], local_pose=terminal,
                datum=("SecondaryOutput" if secondary else "PortD") if moving else "PortC",
                outward_local=[0, 0, 1], connector_key="Cle-B", domain="cordon-b",
                mating_pair=[frames["ReceptacleMating"], frames["MateMating"]],
                mating_frames=[dict(path=frames[frame], local_pose=local(depth))
                               for frame, depth in [("Mount", 0), ("ReceptacleMating", 4), ("MateMating", 4)]])


def describe(runtime, secondary, replace):
    suffix = "_secondary" if secondary else ""
    bench = V3 / f"bench_c2_multiharness{suffix}"
    base = V3 / f"bench_c1_coupled{suffix}"
    metadata = load(runtime / f"description{suffix}.json")
    shutil.copytree(runtime / f"multiharness{suffix}", bench / "model", dirs_exist_ok=replace)
    profile, graph = load(base / "profile.json"), load(base / "graph.json")
    bench_path = bench.relative_to(ROOT).as_posix()
    model_id = f"xlink-c2-multiharness{suffix.replace('_', '-')}"
    dependencies = {path.relative_to(bench / "model").as_posix(): digest(path)
                    for path in sorted((bench / "model").rglob("*.FCStd"))}
    profile.update(model_id=model_id, source=f"{bench_path}/model", graph=f"{bench_path}/graph.json",
                   dependencies=dependencies)
    model, rules = profile["model"], profile["model"]["validation"]
    additions = dict()
    for index, tag in enumerate(("c", "d")):
        additions[f"device-{tag}"] = (metadata["device"][index], "DEVICE")
        additions[f"receptacle-{tag}"] = (metadata["receptacle"][index], "RECEPTACLE")
        additions[f"mate-{tag}"] = (metadata["plug"][index], "PLUG")
        additions[f"service-extraction-{tag}"] = (metadata["envelopes"][index], "SERVICE_ENVELOPE")
        rules["ports"][f"port-{tag}"] = port_rules(index, metadata, secondary)
        for pin in (1, 2):
            rules["contacts"][f"m{tag}{pin}"] = dict(receptacle=f"r{tag}{pin}", pin=f"p{tag}{pin}", port=f"port-{tag}")
    additions.update({"cordon-b": (f"HarnessInventory/{metadata['cable']}", "HARNESS_SEGMENT"),
                      "shared-obstacle": ("SharedObstacle", "KEEP_OUT"),
                      "payload-body": (model["occurrences"]["payload"] + "/Body", "STRUCTURE"),
                      "anchor-b": ("Workholding/AnchorB", "ANCHOR"),
                      "plate-b": ("Workholding/PlateB", "SUPPORT"),
                      "stud-b": ("Workholding/StudB", "FASTENER")})
    for i, native_wire in enumerate(metadata["conductors"], start=1):
        identity = f"c2-net-{i}"
        additions[identity] = (native_wire, "CONDUCTOR")
        rules["nets"][identity] = dict(route="cordon-b", contacts=[f"mc{i}", f"md{i}"])
    model["occurrences"].update({name: path for name, (path, _) in additions.items()})
    companions = model["moving_with"]["payload"]
    companions.extend(["device-d", "service-extraction-d", "anchor-b"])
    rules["non_physical"].extend(metadata["envelopes"])
    rules["routes"]["cordon"]["clearance_obstacles"].append("shared-obstacle")
    rules["routes"]["cordon"]["electrical_id"] = "F1"
    rules["routes"]["cordon-b"] = dict(ports=["port-c", "port-d"], diameter_mm=3, minimum_radius_mm=7,
        conductor_sections_mm2=[0.12, 0.12], minimum_length_mm=65, maximum_length_mm=145,
        clearance_obstacles=["shared-obstacle", "local-obstacle", "service-obstacle", "remote-obstacle"],
        electrical_id="F2")
    rules["isolated_domains"] = [["cordon", "cordon-b"]]
    rules["cross_harness"] = dict(harnesses=["cordon", "cordon-b"], minimum_clearance_mm=0.8)
    rules["service"] = [row for row in rules["service"] if not row.get("required_action")]
    for tag in ("c", "d"):
        rules["service"].append(dict(object=model["occurrences"][f"service-extraction-{tag}"],
            obstacles=["cordon", "cordon-b", "shared-obstacle"], clearance_mm=1.0))
    rules["allowed_interferences"] = []
    contacts = []
    for tag, equipment, cable in [("a", "device-a", "cordon"), ("b", "payload-body", "cordon"),
                                  ("c", "device-c", "cordon-b"), ("d", "device-d", "cordon-b")]:
        receptacle, plug = f"receptacle-{tag}", f"mate-{tag}"
        contacts.extend([dict(parts=[equipment, receptacle], role="CONNECTOR_MOUNT",
                              reason="Appui de l’embase sur le corps équipement."),
                         dict(parts=[receptacle, plug], role="CONNECTOR_MATE",
                              reason="Faces d’accouplement de la paire de connecteurs."),
                         dict(parts=[plug, cable], role="NATIVE_WIRE_EXIT",
                              reason="Gaine tangente au repère de sortie du connecteur.")])
    rules["allowed_surface_contacts"] = contacts
    move, route, old_support = profile["actions"]
    move.update(id="c2-move", affected=["payload", "sibling", "port-b", "port-d", "cordon", "cordon-b",
                                        *companions, "plate", "plate-b", "stud", "stud-b"])
    route.update(id="c2-route-a")
    authored = [move, route]
    second = deepcopy(route)
    route_b_params = dict(frame="ROOT", points_mm=metadata["wire_points_mm"], diameter_mm=3, bend_radius_mm=7,
                          minimum_radius_mm=7, conductor_sections_mm2=[0.12, 0.12],
                          start_axis=metadata["outward_axes"][0], end_axis=metadata["outward_axes"][1])
    second.update(id="c2-route-b", occurrence="cordon-b", effect={"fixture_case": "c2-route-b"},
                  parameters=route_b_params, expected_before={"points_mm": metadata["wire_points_mm"]},
                  expected_after={"points_mm": metadata["wire_points_mm"]},
                  affected=["cordon-b", "c2-net-1", "c2-net-2"],
                  domain_limits={"minimum_radius_mm": 7, "diameter_mm": 3}, graph_target="port-d")
    authored.append(second)
    for tag, support_id, anchor, stud in [("a", "plate", "anchor", "stud"), ("b", "plate-b", "anchor-b", "stud-b")]:
        action_id = f"c2-support-{tag}"
        station, width, length = metadata["options"][support_id]
        rules["supports"][support_id] = dict(anchor=anchor, carrier="carrier", carrier_face="Face6",
            min_contact_area_mm2=length * width - 0.1, min_fasteners=1,
            fasteners=[stud], retains=["cordon", "cordon-b"], retention_max_gap_mm=0.001,
            selected_only=True)
        rules["service"].append(dict(anchor=anchor, offset_local_mm=[length / 2, 1, 3], radius_mm=0.35,
            stroke_mm=6, obstacles=["cordon", "cordon-b", "shared-obstacle"], clearance_mm=0.2,
            required_action=action_id))
        rules["allowed_interferences"].append(dict(parts=["carrier", stud], min_volume_mm3=1.2,
            max_volume_mm3=1.36, role="FASTENER_CARRIER_ENGAGEMENT", support=support_id,
            required_action=action_id, reason="Engagement contrôlé du goujon dans la face porteuse du banc."))
        contacts.append(dict(parts=[support_id, stud], role="FASTENER_BEARING",
                             reason="Face du goujon en appui sur la platine solidaire."))
        contacts.append(dict(parts=["carrier", support_id], role="PLATE_BEARING", required_action=action_id,
                             reason="Appui sur la face porteuse scellée."))
        for cable in ("cordon", "cordon-b"):
            contacts.append(dict(parts=[support_id, cable], role="HARNESS_RETENTION", required_action=action_id,
                                 reason="Rétention des deux gaines par la platine sélectionnée."))
        authored.append(action(action_id, "RELOCATE_SUPPORT", support_id,
            dict(anchor=anchor, carrier="carrier", retains=["cordon", "cordon-b"], fasteners=[stud], placement=pose(0, 0, 0)),
            {"placement": pose(station, 70, 0)}, {"placement": pose(station, -5, -5)},
            [support_id, stud, anchor, "carrier", "cordon", "cordon-b"], {"anchors": [anchor]}, "RETENTION", support_id))
    profile["actions"] = authored
    profile["compositions"] = [[row["id"] for row in authored[:3]] + [row["id"]] for row in authored[3:]]
    graph["configuration"] = model_id
    for source_name, native_file in [("native-root", profile["entry"]), ("native-obstacle", "parts/Obstacle.FCStd"),
                                     ("c1-device", "parts/CoupledAssets.FCStd")]:
        graph["sources"][source_name] = {"path": f"{profile['source']}/{native_file}", "sha256": dependencies[native_file]}
    definition = dict(state="DOCUMENTED", source="native-root", scope="Banc numérique C.2", unit=None, reception="NOT_RUN")
    for identity in ("port-c", "port-d"):
        additions[identity] = (rules["ports"][identity]["frame"], "PORT")
    for identity, (path, kind) in additions.items():
        graph["nodes"].append(dict(id=identity, kind=kind, version=1, claims=[],
                                   evidence=dict(definition, locator=f"{profile['entry']}#{path}")))
    # L'autorité logique utilise les identifiants de ports et conducteurs distincts.
    checks = [node["id"] for node in graph["nodes"] if node["kind"] == "CONTROL"]
    links = {"payload": ["device-d", "port-d", "cordon-b", "service-extraction-d", "anchor-b", "plate-b", "stud-b", "payload-body"],
             "port-d": ["cordon-b", "receptacle-d", "mate-d", "service-extraction-d"],
             "cordon": ["cordon-b", "shared-obstacle"],
             "cordon-b": ["port-c", "port-d", "c2-net-1", "c2-net-2", "shared-obstacle", *checks],
             "plate-b": ["anchor-b", "carrier", "stud-b", "cordon", "cordon-b", *checks]}
    for origin, dests in links.items():
        graph["edges"].extend(dict(id=f"c2-{origin}-{dest}", kind="DEPENDS_ON", impact="FORWARD",
                                   **{"from": origin, "to": dest}, evidence=dict(definition, locator=profile["entry"]))
                               for dest in dests)
    write(bench / "graph.json", graph)
    profile["graph_sha256"] = digest(bench / "graph.json")
    write(bench / "profile.json", profile)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("runtime", type=Path)
    parser.add_argument("--replace", action="store_true", help="Actualise les bancs C.2 existants")
    args = parser.parse_args()
    sources = args.runtime.resolve()
    if not sources.is_relative_to(ROOT / ".runtime"):
        parser.error("Fermetures d'origine requises sous .runtime")
    describe(sources, False, args.replace)
    describe(sources, True, args.replace)
