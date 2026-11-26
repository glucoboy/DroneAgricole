"""Construit les deux bancs synthétiques C.3 à partir des fermetures scellées C.2."""

import argparse
import os
from pathlib import Path
import shutil
import sys

from make_v3_c1_fixtures import App, native, placement, require_valid
from replay_v3_b1 import ROOT, digest, load, write
from hardware.mecanique.banc_interconnexion.verification import freecad_adapter as l2


V3 = ROOT / "docs/electromechanical_v3"


def closure(directory):
    return {path.relative_to(directory).as_posix(): digest(path)
            for path in sorted(directory.rglob("*.FCStd"))}


def box(lower, upper):
    return {"min_mm": lower, "max_mm": upper}


def configure_routes(domain):
    for name, nominal_z, y_min, y_max, landing_x in (
            ("cordon", 0, -8, 8, 54),
            ("cordon-b", -0.5, 10, 35, 58)):
        route = domain["harnesses"][name]["route"]
        lower = [12, y_min, nominal_z - 0.1]
        upper = [97, y_max, nominal_z + 22]
        route.update(corridor_min_mm=lower, corridor_max_mm=upper,
                     nominal_plane={"axis": "Z", "coordinate_mm": nominal_z},
                     polycorridors=[
                         box(lower, [landing_x + 10, y_max, upper[2]]),
                         box([landing_x, y_min, nominal_z], [97, y_max, nominal_z]),
                     ])


def configure_authority(target, source, profile, domain, graph, secondary):
    path = target.relative_to(ROOT).as_posix()
    model = profile["model"]
    actions = {action["id"]: action for action in profile["actions"]}
    renamed = {name: name.replace("c2-", "c3-", 1) for name in actions}
    for name, action in actions.items():
        action["id"] = renamed[name]
        effect = action["effect"]
        if effect.get("fixture_case") == name:
            effect["fixture_case"] = renamed[name]
    for key in ("allowed_interferences", "allowed_surface_contacts", "service"):
        for rule in model["validation"][key]:
            if "required_action" in rule:
                rule["required_action"] = renamed[rule["required_action"]]
    profile["compositions"] = [[renamed[name] for name in composition]
                               for composition in profile["compositions"]]
    anchors = {option["anchor"] for option in domain["support_options"].values()}
    model["moving_with"]["payload"] = [
        name for name in model["moving_with"]["payload"] if name not in anchors
    ]
    domain["scene"]["moving_with"] = [model["occurrences"][name] for name in model["moving_with"]["payload"]]
    actions["c2-move"]["affected"] = [name for name in actions["c2-move"]["affected"] if name not in anchors]

    graph["configuration"] = profile["model_id"] = "xlink-c3-spatial" + ("-secondary" if secondary else "")
    profile["source"] = f"{path}/model"
    profile["graph"] = f"{path}/graph.json"
    profile["dependencies"] = closure(target / "model")
    for evidence in graph["sources"].values():
        if evidence["path"].startswith(source.relative_to(ROOT).as_posix() + "/model/"):
            native_path = evidence["path"].split("/model/", 1)[1]
            evidence.update(path=f"{profile['source']}/{native_path}",
                            sha256=profile["dependencies"][native_path])
    for node in graph["nodes"]:
        if node["id"] == "shared-obstacle":
            node["evidence"]["scope"] = "Porte volumique synthétique C.3 en repère ROOT."
    write(target / "graph.json", graph)
    profile["graph_sha256"] = digest(target / "graph.json")
    write(target / "profile.json", profile)

    domain.update(schema="v3.parametric_domain/3", model_id=profile["model_id"],
                  profile_sha256=digest(target / "profile.json"),
                  move_action=renamed[domain["move_action"]],
                  minimum_clearance_mm=model["validation"]["cross_harness"]["minimum_clearance_mm"])
    domain["placement"].update(translation_min_mm=[100, 3, 0], translation_max_mm=[106, 7, 0])
    for harness in domain["harnesses"].values():
        harness["action"] = renamed[harness["action"]]
    for option in domain["support_options"].values():
        action = actions[option["action"]]
        option["action"] = renamed[option["action"]]
        origin = action["expected_after"]["placement"]["translation_mm"]
        option["anchor_zone"] = box(origin, origin)
    configure_routes(domain)
    return domain


def generate(work, secondary):
    suffix = "_secondary" if secondary else ""
    existing = f"c2_multiharness{suffix}"
    new = f"c3_spatial{suffix}"
    source, target = V3 / f"bench_{existing}", V3 / f"bench_{new}"
    destination = V3 / "domains" / f"{new}.json"
    if target.exists() or destination.exists():
        raise ValueError(f"Banc C.3 déjà présent : {target}")

    profile = load(source / "profile.json")
    graph = load(source / "graph.json")
    domain = load(V3 / "domains" / f"{existing}.json")
    if (closure(source / "model") != profile["dependencies"]
            or digest(source / "graph.json") != profile["graph_sha256"]
            or digest(source / "profile.json") != domain["profile_sha256"]):
        raise ValueError(f"Fermeture C.2 divergente : {source}")
    copy = work / new
    shutil.copytree(source / "model", copy)
    entry = copy / profile["entry"]
    doc = App.openDocument(str(entry))
    try:
        native.complete_dependencies(doc, copy)
        gate = doc.SharedObstacle
        if secondary:
            gate.Placement = placement(36, 10, -4)
            gate.Length, gate.Width, gate.Height = 7, 26, 7
            doc.LateralBaffle.Placement = placement(30, 39, -4)
        else:
            gate.Placement = placement(37, -8, -4)
            gate.Length, gate.Width, gate.Height = 7, 16, 7
        gate.Label = "Porte volumique C.3"
        l2.recompute(doc)
        require_valid(doc)
        doc.save()
    finally:
        for name in reversed(list(App.listDocuments())):
            App.closeDocument(name)
    if closure(source / "model") != profile["dependencies"]:
        raise RuntimeError(f"Une source C.2 a changé : {source}")
    for name in profile["dependencies"]:
        rendered = target / "model" / name
        rendered.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(copy / name, rendered)
    authority = configure_authority(target, source, profile, domain, graph, secondary)
    write(destination, authority)
    print(f"{destination.relative_to(ROOT).as_posix()} {digest(destination)}")
    print(f"{target.relative_to(ROOT).as_posix()}/profile.json {digest(target / 'profile.json')}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    output = parser.parse_args().output.resolve()
    runtime = ROOT / ".runtime"
    if output.exists() or output == runtime or not output.is_relative_to(runtime):
        parser.error("Choisir un nouveau dossier sous .runtime")
    output.mkdir(parents=True)
    l2.initialize()
    generate(output, False)
    generate(output, True)


if __name__ == "__main__":
    main()
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0)
