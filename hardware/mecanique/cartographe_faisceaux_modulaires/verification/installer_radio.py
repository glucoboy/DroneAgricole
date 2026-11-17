"""Adapte le support radio natif P70 aux colonnes P68, dans une copie."""
import argparse
import os
from pathlib import Path
import sys
import traceback

from assembler_modules import (
    App, BUILD, ENTRY, ROUTES, add, boot, bounds, cable_geometry, checked_recompute, dependencies, fresh_solid,
    isolated, make_piece, placement, read, rebuild_cable_in_isolated_document, require, sha, verify_sources, write,
)
from controles_geometrie import same_placement

NAVIGATION = "sous_assemblages/SA06_Prototype_Navigation.FCStd"
HARNESSES = "sous_assemblages/SA07_Prototype_Faisceaux.FCStd"
PART = "pieces/fabriquees/P70_Support_Radio_Prototype.FCStd"


def make_mount(doc, group, seed, variant, pose):
    identifier = variant["id"]
    shapes = {seed.Name: seed}
    for node in variant["primitives"]:
        obj = doc.addObject("Part::" + node["type"], identifier + node["id"])
        for name, value in node.get("properties", {}).items():
            setattr(obj, name, value)
        if "origin_mm" in node:
            obj.Placement = pose.inverse().multiply(placement(node["origin_mm"]))
        if node["type"] == "Cut":
            obj.Base, obj.Tool = (shapes[name] for name in node["inputs"])
            obj.Refine = True
        if node["type"] == "MultiFuse":
            obj.Shapes = [shapes[name] for name in node["inputs"]]
            obj.Refine = True
        group.addObject(obj)
        shapes[node["id"]] = obj
    result = shapes[variant["result"]]
    result.Label = variant["label"]
    add(result, "String", "Interface", variant["interface"])
    add(result, "String", "Montage", variant["assembly"])
    add(result, "String", "Qualification", "À valider")
    checked_recompute(doc)
    require(fresh_solid(result.Shape), "Support RF sans solide valide " + identifier)
    require(abs(result.Shape.Volume - variant["expected_volume_mm3"]) < 1e-5,
            "Géométrie de support différente de l'essai " + identifier)
    for obj in shapes.values():
        obj.Visibility = False
    material = App.Material()
    material.DiffuseColor = (.16, .55, .51)
    result.ViewObject.ShapeAppearance = [material]
    return result


def install_accessory(root, registry, assembly, parent, spec):
    part, target = make_piece(spec)
    file = f"pieces/{spec['directory']}/{spec['id']}.FCStd"
    part.saveAs(str(root / file))
    added = []
    for occurrence in spec["occurrences"]:
        link = assembly.addObject("App::Link", occurrence["id"])
        require(link.Name == occurrence["id"], "Nom de retenue déjà utilisé")
        link.LinkedObject = target
        link.LinkTransform = False
        link.Placement = placement(occurrence["origin_mm"], occurrence.get("direction"), occurrence.get("angle_z", 0))
        link.Label = occurrence["label"]
        group = assembly.getObject("RetenuesLocales" if parent == HARNESSES else "Ensemble")
        group.addObject(link)
        link.Visibility = True
        add(link, "String", "InterfaceFixation", occurrence["interface"])
        add(link, "StringList", "ParcoursCouverts", occurrence.get("routes", []))
        added.append({"parent": parent, "occurrence": link.Name, "source": file, "objet_source": target.Name,
                      "matrice": list(link.Placement.toMatrix().A), "bom_ids": [], "statut": "À valider"})
    registry["occurrences"].extend(added)
    registry["references"].append({"reference": spec["id"], "fichier": file, "objet": target.Name,
                                   "bom_ids": [], "type": spec["directory"], "statut": "Implémenté",
                                   "qualification": "À valider", "bbox_mm": bounds(target.Shape),
                                   "compose_valide": True, "sha256": sha(root / file)})
    return added


def install_routes(root, selected, trials_path):
    if not selected:
        return {}
    trials = read(trials_path)
    require(trials["complete"], "Essai de route incomplet")
    records = read(root / ROUTES)
    installed = {}
    for row in records["routes"]:
        name = row["id"]
        if name not in selected:
            continue
        candidate = next(result for result in trials["results"]
                         if result["route"] == name and result["id"] == selected[name])
        require(not (candidate.get("generation_error") or candidate["collisions"] or candidate["unknowns"]),
                "Variante de route non admissible " + name)
        points = candidate["points_mm"]
        require(points[0] == row["points_mm"][0] and points[-1] == row["points_mm"][-1],
                "Terminaison modifiée " + name)
        doc = App.openDocument(str(root / row["fichier"]))
        isolated(root)
        cable = doc.getObject(row["objet_cable"])
        wire = cable.Base
        wire.Points = [wire.Placement.inverse().multVec(App.Vector(*point)) for point in points]
        require(rebuild_cable_in_isolated_document(doc, cable)["status"] == "pass",
                "Recalcul de route impossible " + name)
        geometry = cable_geometry(cable)
        length = geometry["longueur_courbe_mm"]
        require(abs(length - candidate["geometry"]["longueur_courbe_mm"]) < 1e-6, "Longueur différente de l'essai")
        installed[name] = {"variant": candidate["id"], "before_mm": row["longueur_courbe_mm"], "after_mm": length}
        row.update(geometry, points_mm=points, longueur_trace_mm=round(length, 3))
        checked_recompute(doc)
        doc.save()
        App.closeDocument(doc.Name)
    require(set(installed) == set(selected), "Routes sélectionnées manquantes")
    write(root / ROUTES, records)
    return installed


def install(root, spec_path, nominal_path, route_trials):
    receipt = read(root / "experiment.json")
    require(Path(receipt["copy_root"]).resolve() == root, "Copie incorrecte")
    require(verify_sources(receipt)["sources_unchanged"], "Source de reprise altérée")
    for name, expected in receipt["inputs_sha256"].items():
        require(sha(root / name) == expected, "Copie de reprise altérée : " + name)
    spec = read(spec_path)
    proof = read(nominal_path)
    require(proof["construction_sha256"] == sha(root / BUILD), "Essai sur une construction différente")
    for variant in spec["mounts"]:
        trial = next(row for row in proof["results"] if row["support"] == NAVIGATION + "#" + variant["occurrence"]
                     and row["radius_mm"] == variant["radius_mm"])
        require(trial["form"]["valide"] and abs(trial["form"]["volume_mm3"] - variant["expected_volume_mm3"]) < 1e-5
                and len(trial["assembly_translation"]) == 6
                and not any(r["volume_intersection_mm3"] > 1e-4 for r in trial["nominal"]["observations"])
                and not trial["nominal"]["erreurs"], "Essai préalable non admissible")
    environment = boot()
    updated_routes = install_routes(root, spec.get("reroutes", {}), route_trials)
    registry = read(root / BUILD)
    assembly = App.openDocument(str(root / ENTRY))
    isolated(root)
    opened = {Path(doc.FileName).resolve(): doc for doc in App.listDocuments().values()}
    nav = opened[root / NAVIGATION]
    doc = opened[root / PART]
    group = doc.getObject("Ensemble")
    seed = doc.getObject("SupportRFAncre1")
    require(seed in group.Group and seed.Visibility, "Source de géométrie P70 inattendue")
    targets = []
    records = {row["occurrence"]: row for row in registry["occurrences"] if row["parent"] == NAVIGATION}
    for variant in spec["mounts"]:
        name = variant["occurrence"]
        link = nav.getObject(name)
        pose = link.Placement
        require(same_placement(pose, App.Placement(App.Matrix(*records[name]["matrice"]))), "Pose RF divergente")
        target = make_mount(doc, group, seed, variant, pose)
        targets.append(target)
        link.LinkedObject = target
        link.LinkTransform = False
        link.Placement = pose
        link.Visibility = True
        add(link, "String", "InterfaceFixation", variant["interface"])
        records[name]["objet_source"] = target.Name
    targets[0].Visibility = True
    checked_recompute(doc)
    doc.save()

    added = install_accessory(root, registry, nav, NAVIGATION, spec["band"])
    harnesses = opened[root / HARNESSES]
    for support in spec.get("f41_accessories", []):
        added.extend(install_accessory(root, registry, harnesses, HARNESSES, support))
    original = next(row for row in registry["references"] if row["fichier"] == PART)
    original.update(objet=targets[0].Name, objets_finaux=[target.Name for target in targets],
                    sha256=sha(root / PART), bbox_mm=bounds(targets[0].Shape),
                    limites="Deux supports P70 avec capture axiale sur P68. Effort, jeux réels et tenue RF à valider.")
    checked_recompute(nav)
    if spec.get("f41_accessories"):
        checked_recompute(harnesses)
    checked_recompute(assembly)
    isolated(root)
    nav.save()
    if spec.get("f41_accessories"):
        harnesses.save()
    assembly.save()
    updated_files = {row["fichier"] for row in read(root / ROUTES)["routes"] if row["id"] in updated_routes}
    for row in registry["references"]:
        if row["fichier"] in updated_files:
            row["sha256"] = sha(root / row["fichier"])
    write(root / BUILD, registry)
    manifest = read(root / "manifest.json")
    manifest.update(references=registry["references"], occurrences=registry["occurrences"],
                    integration_radio="verification/integration_radio.json",
                    validation_radio="verification/validation_radio.json")
    write(root / "manifest.json", manifest)
    metadata_path = root / "verification/roles_controle.json"
    metadata = read(metadata_path)
    for variant, target in zip(spec["mounts"], targets):
        metadata[variant["occurrence"]] = {"role": "fixation", "source_file": PART, "fresh_objects": [target.Name]}
    for row in added:
        metadata[row["occurrence"]] = {"role": "fixation", "source_file": row["source"],
                                       "fresh_objects": [row["objet_source"]]}
    write(metadata_path, metadata)
    require(verify_sources(receipt)["sources_unchanged"], "Source de reprise altérée après sauvegarde")
    native = {p.relative_to(root).as_posix(): sha(p) for p in dependencies(root, [ENTRY])}
    generation = read(root / "verification/generation.json")
    generation["routes_installed"].update(updated_routes)
    generation.update(native_sha256=native, added=[*generation["added"], *added],
                      radio={"environment": environment, "install_recipe_sha256": sha(Path(__file__)),
                             "design_sha256": sha(spec_path), "trial_sha256": sha(nominal_path),
                             "route_trials_sha256": sha(route_trials) if route_trials else None,
                             "changed_occurrences": [v["occurrence"] for v in spec["mounts"]],
                             "source_receipt_sha256": sha(root / "experiment.json")})
    write(root / "verification/generation.json", generation)
    print("Reprise RF sauvegardée", root, flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("copy", type=Path)
    parser.add_argument("design", type=Path)
    parser.add_argument("trial", type=Path)
    parser.add_argument("--route-trials", type=Path)
    args = parser.parse_args()
    try:
        install(args.copy.resolve(), args.design, args.trial, args.route_trials)
        os._exit(0)
    except Exception:
        traceback.print_exc()
        sys.stderr.flush()
        os._exit(2)
