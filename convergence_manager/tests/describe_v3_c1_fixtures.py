"""Scelle les entrées des bancs C.1 à partir des fichiers natifs sélectionnés."""

import argparse
from pathlib import Path

from describe_v3_b1_fixture import action, pose
from replay_v3_b1 import ROOT, digest, load, write


V3 = ROOT / "docs/electromechanical_v3"
HALF = 2 ** -0.5


def authority(second):
    suffix = "_secondary" if second else ""
    bench = V3 / f"bench_c1_coupled{suffix}"
    base = V3 / "bench_b1_c4"
    profile = load(base / "profile.json")
    graph = load(base / "graph.json")
    directory = bench.relative_to(ROOT).as_posix()
    model_id = "xlink-c1-coupled" + ("-secondary" if second else "")
    parent = "FixtureRig/InnerStage" if second else "FixtureRig"
    profile.update(model_id=model_id, source=f"{directory}/model", graph=f"{directory}/graph.json")
    dependencies = {p.relative_to(bench / "model").as_posix(): digest(p)
                    for p in sorted((bench / "model").rglob("*.FCStd"))}
    if set(dependencies) != {"Banc_Interconnexion.FCStd", "parts/Obstacle.FCStd", "parts/CoupledAssets.FCStd"}:
        raise ValueError("Fermeture native C.1 incomplète")
    profile["dependencies"] = dependencies
    profile["constraints"]["SUPPORT_ANCHOR"] = {"applicable": True, "evidence": "model.validation.supports"}
    profile["constraints"]["SERVICE"]["scope"] = "Réservations Cables et accès à l'ancrage sur banc numérique."
    additions = {
        "payload": (f"{parent}/Payload", "DEVICE"),
        "sibling": (f"{parent}/Sibling", "DEVICE"),
        "carrier": ("Workholding/Carrier", "STRUCTURE"),
        "anchor": ("Workholding/Anchor", "ANCHOR"),
        "plate": ("Workholding/Plate", "SUPPORT"),
        "stud": ("Workholding/Stud", "FASTENER"),
        "service-guard": ("ServiceGuard", "KEEP_OUT"),
    }
    if second:
        additions["lateral-baffle"] = ("LateralBaffle", "KEEP_OUT")

    model = profile["model"]
    model["occurrences"].update({key: path for key, (path, _) in additions.items()})
    model["occurrences"]["cordon"] = "HarnessInventory/Cable"
    companions = ["device-b", "service-extraction-b", "service-tool-b", "anchor"]
    model["moving_with"] = {"payload": companions}
    rules = model["validation"]
    rules["non_physical"].append("ElectricalDevice001")
    rules["ports"]["port-a"]["datum"] = "PortA"
    rules["ports"]["port-b"].update(equipment="payload", attachment_equipment="device-b",
                                   datum="OutputDatum" if second else "PortB")
    rules["routes"]["cordon"].update(
        conductor_sections_mm2=[0.2] * 4, minimum_length_mm=60, maximum_length_mm=115,
        clearance_obstacles=["local-obstacle", "service-obstacle", "remote-obstacle",
                             *(["lateral-baffle"] if second else [])])
    rules["supports"]["plate"] = dict(anchor="anchor", carrier="carrier", retains=["cordon"],
                                       min_contact_area_mm2=47.9, min_fasteners=1,
                                       retention_max_gap_mm=0.001, carrier_face="Face6")
    rules["allowed_interferences"] = [{"parts": ["carrier", "stud"], "max_volume_mm3": 1.14,
                                        "reason": "Engagement du goujon du banc dans le porteur."}]
    for service in rules["service"]:
        if service["object"].endswith(("Extraction2", "ToolAccess2")):
            service["obstacles"].append("service-guard")
    rules["service"].append(dict(anchor="anchor", offset_local_mm=[3, 1.1, 3], radius_mm=0.35,
                                 stroke_mm=7, obstacles=["cordon", "payload"], clearance_mm=0.2,
                                 required_action="c1-support"))

    body = {"translation_mm": [100, 0, 0], "rotation_xyzw": [0, -HALF, 0, HALF]}
    move = action("c1-move", "REPOSITION_DEVICE", "payload", {"frame": "ROOT", "placement": body},
                  {"placement": body}, {"placement": body}, ["payload", "sibling", "port-b", "cordon",
                                                              *companions, "plate", "stud"],
                  {"pose_autorisee": body, "frame": "ROOT"}, "MOVE", "payload")
    reroute = profile["actions"][1]
    reroute["id"] = "c1-route"
    reroute["effect"] = {"fixture_case": reroute["id"]}
    support_pose = pose(69, -4, -5)
    support = action("c1-support", "RELOCATE_SUPPORT", "plate",
                     dict(anchor="anchor", carrier="carrier", retains=["cordon"],
                          fasteners=["stud"], placement=pose(0, 0, 0)),
                     {"placement": support_pose}, {"placement": support_pose},
                     ["plate", "stud", "anchor", "carrier", "cordon"], {"anchors": ["anchor"]},
                     "RETENTION", "plate")
    profile["actions"] = [move, reroute, support]
    profile["compositions"] = [[row["id"] for row in profile["actions"]]]
    profile.pop("replay", None)

    graph["configuration"] = model_id
    graph["sources"]["native-root"] = {"path": f"{directory}/model/{profile['entry']}",
                                       "sha256": dependencies[profile["entry"]]}
    graph["sources"]["native-obstacle"] = {"path": f"{directory}/model/parts/Obstacle.FCStd",
                                           "sha256": dependencies["parts/Obstacle.FCStd"]}
    graph["sources"]["c1-device"] = {"path": f"{directory}/model/parts/CoupledAssets.FCStd",
                                     "sha256": dependencies["parts/CoupledAssets.FCStd"]}
    logics = dict(state="DOCUMENTED", source="native-root", scope="Banc logiciel C.1",
                   locator="Géométrie native du banc", unit=None, reception="NOT_RUN")
    for name, (path, kind) in additions.items():
        evidence = dict(logics, locator=f"{profile['entry']}#{path}")
        graph["nodes"].append(dict(id=name, kind=kind, version=1, evidence=evidence, claims=[]))
    controls = [node["id"] for node in graph["nodes"] if node["kind"] == "CONTROL"]
    graph["nodes"].append(dict(id="L4_SUPPORT_ANCHOR", kind="CONTROL", version=1, evidence=logics, claims=[]))
    controls.append("L4_SUPPORT_ANCHOR")
    for subject, related in {
        "payload": ["port-b", "cordon", "sibling", *companions, "plate", "stud", *controls],
        "plate": ["stud", "anchor", "carrier", "cordon", *controls],
        "cordon": ["service-guard", *(["lateral-baffle"] if second else [])],
    }.items():
        graph["edges"].extend(dict(id=f"c1-{subject}-{target}", kind="DEPENDS_ON", impact="FORWARD",
                                   **{"from": subject, "to": target}, evidence=logics) for target in related)
    write(bench / "graph.json", graph)
    profile["graph_sha256"] = digest(bench / "graph.json")
    write(bench / "profile.json", profile)

    domain = dict(schema="v3.parametric_domain/1", domain="SYNTHETIC_BENCH", model_id=model_id,
                  profile_sha256=digest(bench / "profile.json"), composition=profile["compositions"][0],
                  scene=dict(device_occurrence=model["occurrences"]["payload"],
                             cable_occurrence=model["occurrences"]["cordon"],
                             ports=["port-a", "port-b"],
                             moving_with=[model["occurrences"][item] for item in companions]),
                  placement=dict(frame="ROOT", translation_min_mm=[98, 2, 0], translation_max_mm=[106, 9, 0],
                                 rotation_xyzw=body["rotation_xyzw"]),
                  route=dict(corridor_min_mm=[14, -19, 0], corridor_max_mm=[92, 15, 0], start_mm=[14, 0, 0],
                             end_reference_mm=[86, 0, 0], terminal_mode="NATIVE_PORT", device_reference_mm=[100, 0, 0],
                             radius_min_mm=5, radius_max_mm=6.5, min_points=2, max_points=16),
                  supports=[dict(operation="RELOCATE_SUPPORT", occurrence="plate", anchor="anchor",
                                 anchor_path=model["occurrences"]["anchor"], support_path=model["occurrences"]["plate"],
                                 carrier_path=model["occurrences"]["carrier"])])
    write(V3 / "domains" / f"c1_coupled{suffix}.json", domain)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-seals", action="store_true", required=True,
                        help="Régénère les autorités qui seront revues et épinglées dans L3/L5")
    parser.parse_args()
    authority(second=False)
    authority(second=True)
