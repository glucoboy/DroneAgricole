"""Construit deux fermetures C.4 depuis des copies privées des bancs C.3."""

import argparse
import os
from pathlib import Path
import shutil
import sys

from make_v3_c1_fixtures import App, native, require_valid
from make_v3_c3_fixtures import box, closure
from replay_v3_b1 import ROOT, digest, load, write
from hardware.mecanique.banc_interconnexion.verification import freecad_adapter as l2


V3 = ROOT / "docs/electromechanical_v3"


def make_fixture(work, secondary):
    suffix = "_secondary" if secondary else ""
    old, new = f"c3_spatial{suffix}", f"c4_sixdof{suffix}"
    source, target = V3 / f"bench_{old}", V3 / f"bench_{new}"
    domain_source, domain_target = V3 / "domains" / f"{old}.json", V3 / "domains" / f"{new}.json"
    if target.exists() or domain_target.exists():
        raise ValueError(f"Destination de banc déjà utilisée : {target}")
    domain = load(domain_source)
    profile = load(source / "profile.json")
    graph = load(source / "graph.json")
    if (closure(source / "model") != profile["dependencies"]
            or digest(source / "graph.json") != profile["graph_sha256"]
            or digest(source / "profile.json") != domain["profile_sha256"]):
        raise ValueError(f"Fermeture C.3 différente du profil : {source}")

    copy = work / new
    shutil.copytree(source / "model", copy)
    doc = App.openDocument(str(copy / profile["entry"]))
    try:
        native.complete_dependencies(doc, copy)
        gate = doc.SharedObstacle
        gate.Label = "Porte volumique C.4"
        gate.Length = gate.Length.Value + (0.25 if secondary else 0.5)
        if secondary:
            anchor = doc.Anchor
            destination = anchor.Placement
            destination.Base = destination.Base + App.Vector(-1.0, 0, 0)
            anchor.Placement = destination
        l2.recompute(doc)
        require_valid(doc)
        doc.save()
    finally:
        for name in reversed(list(App.listDocuments())):
            App.closeDocument(name)
    if closure(source / "model") != profile["dependencies"]:
        raise ValueError(f"Une source C.3 a changé : {source}")
    for name in profile["dependencies"]:
        rendered = target / "model" / name
        rendered.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(copy / name, rendered)

    model_id = "xlink-c4-sixdof" + ("-secondary" if secondary else "")
    model = profile["model"]
    profile["model_id"] = graph["configuration"] = model_id
    profile["source"] = (target / "model").relative_to(ROOT).as_posix()
    profile["graph"] = (target / "graph.json").relative_to(ROOT).as_posix()
    profile["dependencies"] = closure(target / "model")
    for evidence in graph["sources"].values():
        if evidence["path"].startswith(source.relative_to(ROOT).as_posix() + "/model/"):
            name = evidence["path"].split("/model/", 1)[1]
            evidence.update(path=f"{profile['source']}/{name}",
                            sha256=profile["dependencies"][name])
    write(target / "graph.json", graph)
    profile["graph_sha256"] = digest(target / "graph.json")

    support = domain["support_options"]["plate"]
    support["offset_patch_mm"] = box([0.35, -0.5, 0], [1.3, 0.65, 0])
    support["min_carrier_thickness_mm"] = 1.95
    if secondary:
        anchor_origin = [61, -5, -5]
        for action in profile["actions"]:
            if action["id"] == support["action"]:
                action["expected_after"]["placement"]["translation_mm"] = anchor_origin
        support["anchor_zone"] = box(anchor_origin, anchor_origin)
    for spec in model["validation"]["service"]:
        if spec.get("required_action") == support["action"]:
            spec["follow_support"] = support["occurrence"]
    write(target / "profile.json", profile)

    domain.update(schema="v3.parametric_domain/4", model_id=model_id,
                  profile_sha256=digest(target / "profile.json"), support_options={"plate": support})
    domain["placement"].update(translation_min_mm=[101, 3, 0.15], translation_max_mm=[106, 7, 0.6],
                               rotation_bounds={"order": "ROOT_XYZ", "min_deg": [-0.5, 0.4, -0.65],
                                                "max_deg": [0.55, 1.2, 0.6]})
    for harness in domain["harnesses"].values():
        route = harness["route"]
        route["corridor_min_mm"][2] = -2
        route["polycorridors"] = [box(route["corridor_min_mm"], route["corridor_max_mm"])]
    write(domain_target, domain)
    print(f"{domain_target.relative_to(ROOT).as_posix()} {digest(domain_target)}")
    print(f"{(target / 'profile.json').relative_to(ROOT).as_posix()} {digest(target / 'profile.json')}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    output = parser.parse_args().output.resolve()
    runtime = ROOT / ".runtime"
    if output.exists() or output == runtime or not output.is_relative_to(runtime):
        parser.error("Choisir un nouveau dossier sous .runtime")
    output.mkdir(parents=True)
    l2.initialize()
    make_fixture(output, False)
    make_fixture(output, True)


if __name__ == "__main__":
    main()
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0)
