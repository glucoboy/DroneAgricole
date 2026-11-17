"""Adaptateur FreeCAD. Consomme une nomenclature et des primitives déclaratives."""
import argparse
import os
from pathlib import Path
import sys
import traceback

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
LEGACY = ROOT / "hardware/mecanique/cartographe/verification/refonte_faisceaux"
sys.path.insert(0, str(LEGACY))
from adapter_freecad import (
    App, BUILD, ENTRY, Part, ROUTES, SA, add, boot, cable_geometry, dependencies,
    fresh_solid, read, rebuild_cable_in_isolated_document, require, sha, verify_sources, write,
)
from controles_geometrie import bounds
from prototype_fixations_equipements import collar_shape_native


def placement(origin, z_direction=None, angle_z=0):
    axis = App.Vector(0, 0, 1)
    rotation = (App.Rotation(axis, App.Vector(*z_direction)) if z_direction
                else App.Rotation(axis, angle_z))
    return App.Placement(App.Vector(*origin), rotation)


def isolated(root):
    for doc in App.listDocuments().values():
        require(doc.FileName and Path(doc.FileName).resolve().is_relative_to(root),
                "Document ouvert hors copie " + str(doc.FileName))


def checked_recompute(doc):
    doc.recompute()
    errors = {obj.Name: list(obj.State) for obj in doc.Objects
              if set(obj.State) & {"Error", "Invalid"}}
    require(not errors, f"{doc.Name} en erreur {errors}")


def make_piece(spec):
    doc = App.newDocument(spec["id"])
    group = doc.addObject("App::Part", "Ensemble")
    group.Label = spec["label"]
    objects = {}
    for node in spec.get("primitives", []):
        obj = doc.addObject("Part::" + node["type"], node["id"])
        for name, value in node.get("properties", {}).items():
            setattr(obj, name, value)
        if "origin_mm" in node:
            obj.Placement = placement(node["origin_mm"], node.get("direction"), node.get("angle_z", 0))
        if node["type"] == "MultiFuse":
            obj.Shapes = [objects[name] for name in node["inputs"]]
            obj.Refine = True
        if node["type"] == "Cut":
            obj.Base, obj.Tool = (objects[name] for name in node["inputs"])
            obj.Refine = True
        group.addObject(obj)
        objects[node["id"]] = obj
    if "collar_bounds_mm" in spec:
        objects["Bande"] = collar_shape_native(doc, group, "Bande", spec["collar_bounds_mm"])
    result = objects[spec["result"]]
    result.Label = spec["label"]
    add(result, "String", "DefinitionCandidate", spec["procedure"])
    add(result, "String", "Qualification", "À valider")
    if spec.get("axis_object"):
        add(result, "Link", "AxeReference", objects[spec["axis_object"]])
    checked_recompute(doc)
    require(fresh_solid(result.Shape), "Pièce sans solide valide " + spec["id"])
    for obj in doc.Objects:
        obj.Visibility = obj in (group, result)
    material = App.Material()
    material.DiffuseColor = tuple(spec["color"])
    result.ViewObject.ShapeAppearance = [material]
    return doc, result


def build(root, design, modules, trial):
    receipt = read(root / "experiment.json")
    require(Path(receipt["copy_root"]).resolve() == root, "Mauvaise copie déclarée")
    require(verify_sources(receipt)["sources_unchanged"], "Baseline modifiée")
    for path, expected in receipt["inputs_sha256"].items():
        require(sha(root / path) == expected, "Repartir d'une copie neuve pour " + path)
    require(trial["complete"], "Mesures des variantes incomplètes")
    rows = read(root / ROUTES)
    by_id = {row["id"]: row for row in rows["routes"]}
    membership = {route: module["id"] for module in modules["modules"] for route in module["route_ids"]}
    require(len(by_id) == len(membership) == 53 and set(by_id) == set(membership)
            and sum(len(module["route_ids"]) for module in modules["modules"]) == 53,
            "Partition et routes divergentes")
    installed = {}
    environment = boot()
    for route_id, candidate in design["selected_routes"].items():
        measured = next(r for r in trial["results"] if r["route"] == route_id and r["id"] == candidate)
        require(not (measured.get("generation_error") or measured["collisions"] or measured["unknowns"]),
                "Variante non admissible " + candidate)
        row = by_id[route_id]
        doc = App.openDocument(str(root / row["fichier"]))
        isolated(root)
        cable = doc.getObject(row["objet_cable"])
        wire = cable.Base
        points = measured["points_mm"]
        wire.Points = [wire.Placement.inverse().multVec(App.Vector(*point)) for point in points]
        rebuilt = rebuild_cable_in_isolated_document(doc, cable)
        geometry = cable_geometry(cable)
        require(rebuilt["status"] == "pass" and abs(geometry["longueur_courbe_mm"]
                - measured["geometry"]["longueur_courbe_mm"]) < 1e-6, "Recalcul divergent " + route_id)
        previous = row["longueur_courbe_mm"]
        row.update(geometry, points_mm=points, longueur_trace_mm=round(geometry["longueur_courbe_mm"], 3))
        installed[route_id] = {"variant": candidate, "before_mm": previous, "after_mm": geometry["longueur_courbe_mm"]}
        checked_recompute(doc)
        doc.save()
        App.closeDocument(doc.Name)

    main = App.openDocument(str(root / ENTRY))
    isolated(root)
    sa = next(doc for doc in App.listDocuments().values() if Path(doc.FileName).resolve() == root / SA)
    assembly = sa.getObject("Ensemble")
    registry = read(root / BUILD)
    records = {r["occurrence"]: r for r in registry["occurrences"] if r["parent"] == SA}
    retained = set(by_id) | set(design["reuse"])
    require(retained <= set(records), "Occurrence à conserver absente")
    previous_groups = [obj for obj in assembly.Group if obj.TypeId == "App::Part"]
    for record in records.values():
        name = record["occurrence"]
        link = sa.getObject(name)
        require(link and link.TypeId == "App::Link", "Occurrence native absente " + name)
        if name not in retained:
            sa.removeObject(name)
            continue
        for property_name in ("RetenuesIdentifiees", "TronconsCommuns", "FonctionPhysique", "EtatIntegration"):
            if property_name in link.PropertiesList:
                link.removeProperty(property_name)
    for group in previous_groups:
        for obj in list(group.Group):
            group.removeObject(obj)
            if obj.TypeId == "App::FeaturePython":
                sa.removeObject(obj.Name)
        sa.removeObject(group.Name)

    def part(name, label):
        group = sa.addObject("App::Part", name)
        group.Label = label
        assembly.addObject(group)
        group.Visibility = True
        return group

    groups = {module["id"]: part("Module_" + module["id"], module.get("designation", module["id"]))
              for module in modules["modules"]}
    support_group = part("RetenuesLocales", "Retenues physiques et fixations locales")
    for route_id, module_id in membership.items():
        link = sa.getObject(route_id)
        groups[module_id].addObject(link)
        add(link, "String", "FonctionPhysique", module_id)
        add(link, "String", "Qualification", "À valider")
        link.Visibility = True
    for name, destination in design["reuse"].items():
        link = sa.getObject(name)
        (support_group if destination == "retenues" else groups[destination]).addObject(link)
        link.Visibility = True

    additions, refs, metadata = [], [], {}
    for spec in design["pieces"]:
        doc, target = make_piece(spec)
        file = f"pieces/{spec['directory']}/{spec['id']}.FCStd"
        doc.saveAs(str(root / file))
        refs.append({"reference": spec["id"], "fichier": file, "objet": target.Name,
                     "type": spec["directory"], "bom_ids": [], "statut": "Implémenté",
                     "qualification": "À valider", "sha256": sha(root / file),
                     "bbox_mm": bounds(target.Shape), "compose_valide": True})
        for occurrence in spec["occurrences"]:
            name = occurrence["id"]
            link = sa.addObject("App::Link", name)
            require(link.Name == name, "Identifiant FreeCAD non unique " + name)
            link.LinkedObject = target
            link.LinkTransform = False
            link.Placement = placement(occurrence["origin_mm"], occurrence.get("direction"),
                                       occurrence.get("angle_z", 0))
            link.Label = occurrence["label"]
            group = groups[occurrence["module"]] if spec["role"] == "gaine" else support_group
            group.addObject(link)
            link.Visibility = True
            add(link, "String", "InterfaceFixation", occurrence["interface"])
            add(link, "StringList", "ParcoursCouverts", occurrence["routes"])
            add(link, "String", "Qualification", "À valider")
            additions.append({"parent": SA, "occurrence": name, "source": file, "objet_source": target.Name,
                              "matrice": list(link.Placement.toMatrix().A), "bom_ids": [], "statut": "À valider"})
            metadata[name] = {"role": spec["role"], "source_file": file, "fresh_objects": [target.Name]}
            if spec["role"] == "gaine":
                start = occurrence["origin_mm"][0]
                length = next(node["properties"]["Height"] for node in spec["primitives"] if node["id"] == "Passage")
                metadata[name].update(members=occurrence["routes"], cavity_object="Passage",
                                      axis_length_mm=length, window_x_mm=[start, start + length])
    for name, group in design["reuse"].items():
        if group == "retenues":
            metadata[name] = {"role": "fixation"}

    checked_recompute(sa)
    checked_recompute(main)
    for name in retained:
        original = records[name]
        link = sa.getObject(name)
        require(link.Visibility and link.LinkedObject and
                Path(link.LinkedObject.Document.FileName).resolve() == root / original["source"]
                and link.LinkedObject.Name == original["objet_source"]
                and max(abs(a-b) for a,b in zip(original["matrice"], link.Placement.toMatrix().A)) < 1e-8,
                "Lien ou placement changé pour " + name)
    isolated(root)
    sa.save()
    main.save()
    final = {path.relative_to(root).as_posix(): sha(path) for path in dependencies(root, [ENTRY])}
    remaining = [row for row in registry["occurrences"] if row["parent"] != SA or row["occurrence"] in retained]
    registry["occurrences"] = remaining + additions
    active_files = {r["source"] for r in registry["occurrences"]}
    registry["references"] = [row for row in registry["references"] if row["fichier"] in active_files] + refs
    for row in registry["references"]:
        if row["fichier"] in final:
            row["sha256"] = final[row["fichier"]]
    registry.pop("refonte_faisceaux", None)
    registry["integration_modulaire"] = {"statut": "Implémenté", "qualification": "À valider",
                                         "modules": list(groups), "new_occurrences": additions}
    for row in rows["routes"]:
        row["module"] = membership[row["id"]]
        row["supports_baseline_non_contractuels"] = row.pop("supports", [])
    rows.pop("guides", None)
    write(root / ROUTES, rows)
    write(root / BUILD, registry)
    manifest = {
        "configuration": "copie de conception modulaire du prototype cartographe sans dock",
        "promotion": "Copie candidate isolée",
        "assemblage": ENTRY, "statut": "Implémenté", "qualification": "À valider",
        "construction": BUILD, "routes": ROUTES, "nomenclature": "verification/modules_electriques.json",
        "definition_retenues": "verification/integration.json",
        "controle": "verification/validation.json",
        "references": registry["references"], "occurrences": registry["occurrences"],
        "archives": {"baseline": "cartographe_faisceaux_refonte", "copie_sha256": "experiment.json"},
        "date_mise_a_jour": "2026-11-09",
    }
    write(root / "manifest.json", manifest)
    write(root / "verification/roles_controle.json", metadata)
    source_check = verify_sources(receipt)
    require(source_check["sources_unchanged"], "Une source a été modifiée")
    return {"complete": True, "environment": environment, "source_check": source_check,
            "input_receipt_sha256": sha(root / "experiment.json"), "native_sha256": final,
            "removed": sorted(set(records) - retained), "reused": design["reuse"],
            "routes_installed": installed, "added": additions, "module_count": len(groups),
            "route_count": len(membership)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("copy", type=Path)
    parser.add_argument("--modules", type=Path, required=True)
    parser.add_argument("--trials", type=Path, required=True)
    parser.add_argument("--design", type=Path, default=HERE / "integration.json")
    args = parser.parse_args()
    try:
        result = build(args.copy.resolve(), read(args.design), read(args.modules), read(args.trials))
        result["recipe_sha256"] = {str(p.name): sha(p) for p in (Path(__file__), args.design, args.modules, args.trials)}
        write(args.copy / "verification/generation.json", result)
        print("Copie générée", args.copy, flush=True)
        os._exit(0)
    except Exception:
        traceback.print_exc()
        sys.stderr.flush()
        os._exit(2)
