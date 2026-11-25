"""Prépare deux fermetures FreeCAD C.2 sur copies des bancs C.1."""

import argparse
import os
from pathlib import Path
import shutil
import sys

from make_v3_c1_fixtures import App, ROOT, child, native, placement, require_valid

from hardware.mecanique.banc_interconnexion.verification import freecad_adapter as l2


def exit_pose(mount, depth):
    return mount.multiply(App.Placement(App.Vector(0, 0, depth), App.Rotation()))


def new_interface(document, mount, index, port, contact_suffix):
    socket, terminal = exit_pose(mount, 4), exit_pose(mount, 14)
    endpoint = terminal.Base
    rule = dict(mount=list(mount.toMatrix().A), receptacle_mating=list(socket.toMatrix().A),
                mate_mating=list(socket.toMatrix().A), exit=list(terminal.toMatrix().A),
                extraction_box_mm=[endpoint.x, endpoint.y + 3, endpoint.z + 6,
                                   endpoint.x + 5, endpoint.y + 6, endpoint.z + 9],
                port_id=port, end_id=contact_suffix, equipment_id=f"device-{contact_suffix}",
                receptacle_id=f"receptacle-{contact_suffix}", mate_id=f"mate-{contact_suffix}",
                contacts=[dict(cavity=str(pin), pin_id=f"p{contact_suffix}{pin}",
                               receptacle_contact_id=f"r{contact_suffix}{pin}",
                               mate_contact_id=f"m{contact_suffix}{pin}") for pin in (1, 2)])
    return l2.interface_geometry(document, rule, index)


def parked_support(carrier, cables, option, length, width, station):
    anchor, plate, stud = option
    anchor.Placement = placement(station, -5, -5)
    anchor.Visibility = False
    plate.Length, plate.Width, plate.Height = length, width, 3
    plate.Placement = placement(station, 70, 0)
    stud.Radius, stud.Height = 0.65, 1
    stud.Placement = placement(station + length / 2, 71, -1)
    properties = [("Anchor", "Link", anchor), ("Carrier", "Link", carrier),
                  ("Retains", "LinkListGlobal", cables), ("Fasteners", "LinkList", [stud])]
    for field, kind, value in properties:
        prop = "B1_" + field
        if prop not in plate.PropertiesList:
            plate.addProperty("App::Property" + kind, prop, "V3 C.2")
        setattr(plate, prop, value)


def make_bench(directory, secondary):
    suffix = "_secondary" if secondary else ""
    source = ROOT / f"docs/electromechanical_v3/bench_c1_coupled{suffix}/model"
    shutil.copytree(source, directory)
    doc = App.openDocument(str(directory / "Banc_Interconnexion.FCStd"))
    native.complete_dependencies(doc, directory)
    assets = next(item for item in App.listDocuments().values() if Path(item.FileName).name == "CoupledAssets.FCStd")
    App.setActiveDocument(doc.Name)

    side = 19 if secondary else 16
    angle = 20 if secondary else 15
    mount_c = App.Placement(App.Vector(0, side, -0.5),
                            App.Rotation(App.Vector(0, 0, 1), angle).multiply(App.Rotation(App.Vector(0, 1, 0), 90)))
    mount_d = App.Placement(App.Vector(100, side, -0.5),
                            App.Rotation(App.Vector(0, 0, 1), angle).multiply(App.Rotation(App.Vector(0, 1, 0), -90)))
    first = new_interface(doc, mount_c, 3, "port-c", "c")
    last = new_interface(doc, mount_d, 4, "port-d", "d")
    start, end = [ui["frames"]["WireExit"].getGlobalPlacement() for ui in (first, last)]
    forward, backward = [item.Rotation.multVec(App.Vector(0, 0, 1)) for item in (start, end)]
    points = [start.Base, start.Base + forward * 15, end.Base + backward * 15, end.Base]
    cable = l2.add_cable(doc, {"id": "cordon-b", "points_mm": [list(point) for point in points],
                              "bend_radius_mm": 7, "diameter_mm": 3,
                              "conductors": [{"id": f"c2-net-{i}", "mate_contact_ids": [f"mc{i}", f"md{i}"]}
                                             for i in (1, 2)]}, [first, last])
    cable.addProperty("App::PropertyFloatList", "B1_ConductorSections", "V3 C.2")
    cable.B1_ConductorSections = [0.12, 0.12]
    doc.HarnessInventory.addObject(cable)
    cable.Visibility = True
    first["envelope"].Visibility = last["envelope"].Visibility = False
    fixed_datum = doc.addObject("PartDesign::CoordinateSystem", "PortC")
    fixed_datum.AttachmentSupport = [(first["device"], [""])]
    fixed_datum.MapMode = "ObjectXY"
    fixed_datum.AttachmentOffset = placement(0, 0, 14)
    fixed_datum.Visibility = False
    datum_name = "SecondaryOutput" if secondary else "PortD"
    datum = child(assets, assets.DeviceDefinition, "PartDesign::CoordinateSystem", datum_name)
    datum.Placement = doc.ElectricalDevice001.Placement.inverse().multiply(end)
    datum.Visibility = False
    assets.recompute()
    assets.save()

    obstacle = doc.addObject("Part::Box", "SharedObstacle")
    obstacle.Length, obstacle.Width, obstacle.Height = (11 if secondary else 8), side + 7, 7
    obstacle.Placement = placement(41 if secondary else 40, -1, -3.5)
    doc.ServiceObstacle.LinkPlacement = placement(44 if secondary else 46, -24, -4)
    doc.RemoteObstacle.LinkPlacement = placement(46, 43, -4)
    if secondary:
        doc.LateralBaffle.Placement = placement(30, 36, -4)
    workholding = doc.Workholding
    carrier = doc.Carrier
    carrier.Length, carrier.Width = 40, side + 32
    carrier.Placement = placement(57, -12, -7)
    options = [(doc.Anchor, doc.Plate, doc.Stud),
               (child(doc, workholding, "PartDesign::CoordinateSystem", "AnchorB"),
                child(doc, workholding, "Part::Box", "PlateB"),
                child(doc, workholding, "Part::Cylinder", "StudB"))]
    for option, dimensions, station in zip(options, [(6, side + 17), (8, side + 18)],
                                           (64, 77) if secondary else (62, 75), strict=True):
        parked_support(carrier, [doc.Cable, cable], option, *dimensions, station)
    l2.recompute(doc)
    require_valid(doc)
    description = {"device": [first["device"].Name, last["device"].Name],
                   "receptacle": [first["receptacle"].Name, last["receptacle"].Name],
                   "plug": [first["plug"].Name, last["plug"].Name],
                   "frames": [{name: frame.Name for name, frame in row["frames"].items()} for row in (first, last)],
                   "mounts": [list(mount.toMatrix().A) for mount in (mount_c, mount_d)],
                   "port_d_local": {"translation_mm": list(datum.Placement.Base),
                                    "rotation_xyzw": list(datum.Placement.Rotation.Q)},
                   "wire_exit_points_mm": [list(start.Base), list(end.Base)],
                   "outward_axes": [list(forward), list(backward)], "wire_points_mm": [list(point) for point in points],
                   "envelopes": [first["envelope"].Name, last["envelope"].Name],
                   "cable": cable.Name, "conductors": [wire.Name for wire in cable.L2Conductors],
                   "options": {"plate": [64 if secondary else 62, side + 17, 6],
                               "plate-b": [77 if secondary else 75, side + 18, 8]}}
    doc.save()
    for name in reversed(list(App.listDocuments())):
        App.closeDocument(name)
    for backup in directory.rglob("*.FCBak"):
        backup.unlink()
    l2.publish_json(directory.parent / f"description{suffix}.json", description)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    output = parser.parse_args().output.resolve()
    if output.exists() or not output.is_relative_to(ROOT / ".runtime"):
        parser.error("Choisir un nouveau dossier sous .runtime")
    l2.initialize()
    make_bench(output / "multiharness", False)
    make_bench(output / "multiharness_secondary", True)


if __name__ == "__main__":
    main()
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0)
