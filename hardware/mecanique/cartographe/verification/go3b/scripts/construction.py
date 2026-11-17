"""Adaptateur d'essai natif sur les copies GO3B, sans modification des sources."""
import os
from pathlib import Path
import shutil
import sys
import traceback

from preparation import ROOT, RUN, read, write, require
from electromechanical_engine.freecad import guard
from electromechanical_engine.freecad_worker import App, Part, builder, cables_environment, complete_dependencies, geometry, recalculate
from electromechanical_engine.qualification.native_replay import ENTRY, REGISTERS

V = App.Vector
SA03 = "sous_assemblages/SA03_Prototype_Energie.FCStd"
SA07 = "sous_assemblages/SA07_Prototype_Faisceaux.FCStd"
ISOLATOR = "pieces/commerce/EQ_Waveshare15817_UART_Isole.FCStd"
P85 = "pieces/fabriquees/P85_Retenue_Chant_P66.FCStd"
TRIAL = "pieces/fabriquees/ASSUMED_GO3B_Service.FCStd"
DONOR = ROOT / ".runtime/cartographe-action3-integre/candidat"
CAMERA = ROOT / ".runtime/cartographe-action3-f16-z10/candidat"
COMMON = {
    "F12": "7c033e4ec954a0f6a45fd13c3bb66fac4dfd6cce2845a553168535afec587341",
    "F35": "1834a490692f80ce887fb3734667a6a2964c528350824241e22224b33019448f",
    "F25": "e824371affbaaf6e57241e38665c6f29407bf76d382d91d7c8727c686a151457",
    P85: "c42a05c6f95df5fa73e4dad792a914ee3759f6f1d87c859752d8f06f7b8c8760",
}
F16_SHA = "14293252ce2ca91f3e7a03ecb2c534daead990b3e55e21d94120fd1aea87708a"
TTL = V(12, 18.5, 50.5)
USB = V(-68.8, -28.575, 51)
BMS = V(-66.25, -10, -13)
HOST = V(7, -42, 131.5)
EX, EY, EZ = V(1, 0, 0), V(0, 1, 0), V(0, 0, 1)


def filename(axis):
    return f"pieces/commerce/W_{axis}_Prototype.FCStd"


def sha_tree(cad):
    return {p.relative_to(cad).as_posix(): guard.sha256(p) for p in guard.dependencies(cad, [ENTRY])}


def record_by_id(records, key, value):
    return next(row for row in records if row[key] == value)


def replace_record(records, key, value, data):
    index = next(i for i, row in enumerate(records) if row[key] == value)
    records[index] = data


def copy_donor(cad, relative, source, expected, result):
    donor = source / relative
    require(guard.sha256(donor) == expected, f"Donneur divergent : {relative}")
    shutil.copy2(donor, cad / relative)
    result["donors"][relative] = {"source": donor.relative_to(ROOT).as_posix(), "sha256": expected}


def vlist(points):
    return [list(p) for p in points]


def unit(value):
    result = V(value)
    result.normalize()
    return result


def plan(case, isolator):
    case = case.removesuffix("_R")
    family = case[:3]
    if family == "H03":
        center = isolator.Shape.BoundBox.Center
        angle = 180 if case.endswith("A") else 270
        rotation = App.Rotation(EZ, angle)
        location = V(-119, 2, 71)
        transform = App.Placement(location - rotation.multVec(center), rotation)
        ttl, usb = transform.multVec(TTL), transform.multVec(USB)
        ttl_out, usb_out = rotation.multVec(EX), rotation.multVec(-EX)
        if angle == 180:
            ttl_route = [BMS, (-95,-10,-10), (-182,-30,-10), (-182,-30,ttl.z),
                         (-182,ttl.y,ttl.z), ttl]
            usb_route = [usb, (-43,usb.y,usb.z), (-43,100,usb.z), (-166,100,usb.z),
                         (-166,100,131.5), (-166,-105,131.5), (7,-105,131.5), HOST]
        else:
            # Stable proxy for the endpoint tangent, with wide radii in the exterior corridor.
            ttl_route = [BMS, (-95,-10,-10), (-168,-78,-10),
                         (ttl.x,-78,-10), (ttl.x,-78,ttl.z), ttl]
            usb_route = [usb, (usb.x,107,usb.z), (usb.x,107,131.5),
                         (-194,107,131.5), (-194,-107,131.5), (7,-107,131.5), HOST]
        support = {"origin": list(location + V(-28,-19,-16)), "size": [76,38,2],
                   "comment": "Ébauche d’appui au chant P66. Ancrages et reprise d’effort inconnus."}
        return dict(transform=transform, angle=angle, ttl=ttl, usb=usb, ttl_out=ttl_out, usb_out=usb_out,
                    ttl_route=ttl_route, usb_route=usb_route, support=support,
                    geometry="support réversible et service direct")
    if family == "H02":
        usb_route = ([USB, (-119,USB.y,USB.z), (-119,USB.y,1), (-119,88,1),
                      (-155,135,1), (-155,135,131.5), (-155,-107,131.5), (7,-107,131.5), HOST]
                     if case.endswith("A") else
                     [USB, (-153,USB.y,USB.z), (-153,USB.y,131.5),
                      (-153,-107,131.5), (7,-107,131.5), HOST])
        ttl_route = [BMS, (-94,-10,-10), (-94,70,-10), (27,70,-10), (27,70,TTL.z), (27,TTL.y,TTL.z), TTL]
        return dict(ttl=TTL, usb=USB, ttl_out=EX, usb_out=-EX, ttl_route=ttl_route, usb_route=usb_route,
                    geometry="isolateur fixe, profil USB coudé et corridor différencié", camera=True, ferrite_start=V(-119,USB.y,27) if case.endswith("A") else V(-153,USB.y,79), ferrite_axis=-EZ if case.endswith("A") else EZ)
    remote_y = -83 if case.endswith("A") else -100
    remote_ttl = V(-128, remote_y, 52)
    remote_usb = V(-146, USB.y, USB.z) if case.endswith("A") else V(-172, USB.y, 93)
    ttl_route = [BMS, (-94,-10,-10), (-128,-10,-10), remote_ttl,
                 (-128,remote_y,68), (34,remote_y,68), (34,TTL.y,68), (34,TTL.y,TTL.z), TTL]
    usb_x = -183 if case.endswith("A") else -172
    usb_route = [USB, (usb_x,USB.y,USB.z), (usb_x,USB.y,131.5),
                 (usb_x,-112,131.5), (7,-112,131.5), HOST]
    return dict(ttl=TTL, usb=USB, ttl_out=EX, usb_out=-EX, ttl_route=ttl_route, usb_route=usb_route,
                remote=[("TTLDeporte",remote_ttl,EX),("USBDeporte",remote_usb,-EX if case.endswith("A") else EZ)],
                geometry="réservation de deux raccords passifs, graphe inchangé")


def configured(plan):
    data = {}
    for key, value in plan.items():
        if isinstance(value, App.Placement):
            data[key] = list(value.toMatrix().A)
        elif isinstance(value, App.Vector):
            data[key] = list(value)
        elif key == "remote":
            data[key] = [{"id": name, "center_mm": list(point), "orientation": list(axis)} for name, point, axis in value]
        elif key.endswith("_route"):
            data[key] = [list(point) for point in value]
        else:
            data[key] = value
    return data


def update_axis(doc, row, points):
    points = [V(*p) if not isinstance(p, App.Vector) else V(p) for p in points]
    cable = doc.getObject(row["objet_cable"])
    route = cable.Base
    require(route.PathType == "Wire", f"Mode de courbe imprévu {row['id']}: {route.PathType}")
    radius = cable.BaseWireFilletRadius.Value
    diameter = cable.ProfilExterieur.DiametreExterieur.Value
    builder._check_polyline(points, diameter, radius)
    transform = route.Placement.inverse()
    route.Points = [transform.multVec(point) for point in points]
    regenerated = geometry.rebuild_cable_in_isolated_document(doc, cable)
    require(regenerated["status"] == "pass", f"Reconstruction {row['id']} : {regenerated}")
    measured = builder.cable_geometry(cable)
    require(measured["solide_valide"] and measured["parcours_valide"] and measured["solides"] == 1
            and measured["continuite"] and not measured["erreurs"], f"Géométrie {row['id']} : {measured}")
    axis = geometry.inspect_route(builder.effective_wire(cable), radius)
    require(not axis["failures"], f"Axe {row['id']} : {axis}")
    row.update(measured)
    row.update(points_mm=vlist(points), supports=[], substrat=[],
               retentions="Implantation numérique GO3B. Appuis, gestes et retenues à définir.",
               terminaisons="Repères de face CAO. Accouplement et contacts à valider.")
    doc.save()
    return {"fresh": regenerated, "geometry": measured, "axis": axis}


def box_at(doc, name, start, axis, along, width, height, exposure, title):
    feature = doc.addObject("Part::Box", "ASSUMED_" + name)
    feature.Label = "ASSUMED · " + title
    feature.Length, feature.Width, feature.Height = along, width, height
    rotation = App.Rotation(EX, unit(axis))
    feature.Placement = App.Placement(start + rotation.multVec(V(0,-width/2,-height/2)), rotation)
    feature.addProperty("App::PropertyString", "Statut", "GO3B")
    feature.Statut = exposure
    return feature


def service_geometry(target, config, case):
    specs = []
    def envelope(name, start, axis, lengths, sizes, comment, group):
        for depth, (width, height) in zip(lengths, sizes):
            specs.append((name + "_" + str(depth).replace(".","p"), start, axis, depth, width, height, group, comment))
    envelope("CAN1", V(52.85,-14.5,134.30232), EZ, [5.7,9.95,17.7],
             [(6.25,4.15),(6.25,6.25),(6.25,6.25)], "CAN1 emboîté puis retrait, proxy Action 3", "service")
    ttl_sizes = [(9,6),(12,8),(15,12)]
    usb_sizes = [(10.8,9.2),(11.8,10.2),(15,13)]
    envelope("TTL", config["ttl"], config["ttl_out"], [3,5,15], ttl_sizes,
             "TTL, sortie et outil selon trois hypothèses", "service")
    envelope("USB", config["usb"], config["usb_out"], [5,15,50], usb_sizes,
             "USB-B, corps et volume service selon trois hypothèses", "service")
    if case.startswith("H02"):
        envelope("Ferrite", config["ferrite_start"], config["ferrite_axis"], [12,20,30], [(10,10),(14,14),(18,18)],
                 "Profil de ferrite 84809, dimensions de sensibilité", "service")
    if config.get("camera"):
        envelope("F16_MicroB_Up", V(109.785,-.525,-96.82), EZ, [12,16,21],
                 [(9,6),(12,8),(15,10)], "Micro-B Up, volume de sortie candidat", "service")
        envelope("M8_coude", V(74.2,31.1,-90.855), EY, [14,20,27],
                 [(9,9),(12,12),(15,15)], "M8, sortie coudée et retrait candidats", "service")
    for name, position, direction in config.get("remote", []):
        envelope(name, position, direction, [9,16,23], [(9,8),(13,11),(17,15)],
                 "Raccord passif réservé, contacts et support inconnus", "service")
    doc = App.newDocument("GO3BService")
    root = doc.addObject("App::Part", "Ensemble")
    for name, start, axis, length, width, height, group, comment in specs:
        box_at(doc, name, start, axis, length, width, height, group, comment)
    if "support" in config:
        spec = config["support"]
        support = doc.addObject("Part::Box", "ASSUMED_SupportIsolateur")
        support.Label = "ASSUMED · support de l’isolateur, ancrages à confirmer"
        support.Length, support.Width, support.Height = spec["size"]
        support.Placement = App.Placement(V(*spec["origin"]), App.Rotation())
        root.addObject(support)
    else:
        # The assembly links one non-physical coordinate system, not the overlapping sweeps.
        marker = doc.addObject("App::FeaturePython", "ASSUMED_ReperesService")
        marker.addProperty("App::PropertyString", "Portee", "GO3B")
        marker.Portee = "Sondes non matérielles détaillées dans ce document."
        root.addObject(marker)
    doc.recompute()
    doc.saveAs(str(target / TRIAL))
    return doc, root, [{"name": name, "from_mm": list(start), "axis": list(axis),
              "length_mm": length, "width_mm": width, "height_mm": height, "meaning": comment}
             for name, start, axis, length, width, height, _, comment in specs]


def added_link(parent, name, source):
    link = parent.addObject("App::Link", name)
    link.setLink(source)
    link.LinkTransform = False
    parent.getObject("Ensemble").addObject(link)
    return link


def preserve_visibility(parent, original):
    for name, flag in original.items():
        parent.getObject(name).Visibility = flag


def build(target_name, plan_name):
    target = RUN / target_name
    cad = target / "cad"
    result = {"candidate": target_name, "parameter_case": plan_name, "pid": os.getpid(), "donors": {},
              "axes": {}, "phase": "STARTED"}
    write(target / "construction.json", result)
    receipt = read(cad / "experiment.json")
    baseline = read(RUN / "baseline/snapshot.json")
    before = sha_tree(cad)
    require(before == baseline["native_sha256"], "La copie n'est pas le témoin byte-identique.")
    guard.verify_sources(receipt)
    cables_environment(False)
    for axis, expected in COMMON.items():
        relative = axis if axis.endswith(".FCStd") else filename(axis)
        copy_donor(cad, relative, DONOR, expected, result)
    routes = read(cad / REGISTERS[1])
    construction = read(cad / REGISTERS[0])
    donor_construction = read(DONOR / REGISTERS[0])
    donor_routes = read(DONOR / REGISTERS[1])
    for axis in ("F12", "F35", "F25"):
        replace_record(routes["routes"], "id", axis, record_by_id(donor_routes["routes"], "id", axis))
    construction["references"].append(record_by_id(donor_construction["references"], "fichier", P85))
    construction["occurrences"].append(record_by_id(donor_construction["occurrences"], "occurrence", "RetenueP85F25"))
    if plan_name.startswith(("H01", "H02")):
        copy_donor(cad, filename("F16"), CAMERA, F16_SHA, result)
        camera_routes = read(CAMERA / REGISTERS[1])
        camera_construction = read(CAMERA / REGISTERS[0])
        replace_record(routes["routes"], "id", "F16", record_by_id(camera_routes["routes"], "id", "F16"))
        replace_record(construction["occurrences"], "occurrence", "F16",
                       record_by_id(camera_construction["occurrences"], "occurrence", "F16"))
    if plan_name != "commun":
        energy = App.openDocument(str(cad / SA03))
        complete_dependencies(energy, cad)
        isolator = energy.getObject("UART_isole")
        require(Path(isolator.LinkedObject.Document.FileName).resolve() == cad / ISOLATOR,
                "Lien de l'isolateur hors copie ou différent de l'autorité.")
        config = plan(plan_name, isolator)
        result["parameters"] = configured(config)
        write(target / "construction.json", result)
        if "transform" in config:
            original = isolator.Placement
            isolator.Placement = config["transform"].multiply(original)
            result["isolator_placement"] = {"before": list(original.toMatrix().A),
                                            "after": list(isolator.Placement.toMatrix().A)}
            record_by_id(construction["occurrences"], "occurrence", "UART_isole")["matrice"] = result["isolator_placement"]["after"]
            _, counts = recalculate(energy, cad)
            require(isolator.Shape.isValid(), "Isolateur invalide après déplacement.")
            energy.save()
            result["energy_recalculation"] = counts
        for axis, points in (("F40", config["ttl_route"]), ("F41", config["usb_route"])):
            doc = App.openDocument(str(cad / filename(axis)))
            row = record_by_id(routes["routes"], "id", axis)
            result["axes"][axis] = update_axis(doc, row, points)
            App.closeDocument(doc.Name)
            write(target / "construction.json", result)
        service_doc, service_root, service = service_geometry(cad, config, plan_name)
        result["envelopes"] = service
    else:
        config = {"ttl":TTL, "usb":USB, "ttl_out":EX, "usb_out":-EX,
                  "geometry":"consolidation de diagnostic des corrections communes"}
        result["parameters"] = configured(config)
        service_doc, service_root, service = service_geometry(cad, config, plan_name)
        result["envelopes"] = service
    parent = App.openDocument(str(cad / SA07))
    complete_dependencies(parent, cad)
    visibility = {obj.Name: obj.Visibility for obj in parent.Objects}
    clip = App.openDocument(str(cad / P85))
    p85_link = added_link(parent, "RetenueP85F25", clip.getObject("Ensemble"))
    p85_link.Label = "P85 · maintien local F25 · À valider"
    affected = {"F12", "F25", "F35", *result["axes"]}
    if plan_name.startswith(("H01", "H02")):
        f16 = App.openDocument(str(cad / filename("F16")))
        link = parent.getObject("F16")
        link.setLink(f16.getObject("Cable002"))
        link.LinkTransform = False
        link.Placement = App.Placement()
        affected.add("F16")
    if service_doc is not None:
        # Reserve volumes remain visible in their own document. Only the trial support is linked.
        if "support" in config:
            trial_link = added_link(parent, "ASSUMED_ServiceGO3B", service_root)
            trial_link.Visibility = True
            construction["references"].append({"fichier": TRIAL, "ref": "ASSUMED_GO3B", "type": "support_essai"})
            prototype = record_by_id(construction["occurrences"], "occurrence", "RetenueP85F25")
            construction["occurrences"].append({**prototype, "occurrence": trial_link.Name, "source": TRIAL,
                                                   "objet_source": "Ensemble", "ref": "ASSUMED_GO3B"})
    for axis in affected:
        parent.getObject(axis).touch()
    _, counts = recalculate(parent, cad)
    preserve_visibility(parent, visibility)
    p85_link.Visibility = True
    require(p85_link.Shape.isValid(), "Lien P85 invalide.")
    links = {}
    for axis in sorted(affected):
        link = parent.getObject(axis)
        require(link.Shape.isValid() and len(link.Shape.Solids) == 1, f"Lien invalide : {axis}")
        links[axis] = Path(link.LinkedObject.Document.FileName).resolve().relative_to(cad).as_posix() + "#" + link.LinkedObject.Name
    parent.save()
    if target_name == "consolidee":
        root = App.openDocument(str(cad / ENTRY))
        complete_dependencies(root, cad)
        _, root_counts = recalculate(root, cad)
        root.save()
        result["root_recalculation"] = root_counts
    write(cad / REGISTERS[0], construction)
    write(cad / REGISTERS[1], routes)
    after = sha_tree(cad)
    result.update(phase="SAVED", affected=sorted(affected), links=links, recalculation=counts,
                  added_native=sorted(set(after) - set(before)),
                  changed_native=sorted(name for name in before if after.get(name) != before[name]),
                  native_sha256=after, source_integrity=guard.verify_sources(receipt))
    write(target / "construction.json", result)
    print(target_name, result["phase"], sorted(affected), len(after), flush=True)


if __name__ == "__main__":
    name = sys.argv[1]
    try:
        build(name, sys.argv[2] if len(sys.argv) > 2 else name)
    except Exception:
        failure = RUN / name / "construction.json"
        record = read(failure) if failure.exists() else {"candidate": name}
        record.update(phase="FAILED", error=traceback.format_exc())
        write(failure, record)
        print(record["error"], file=sys.stderr, flush=True)
        os._exit(1)
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0)

