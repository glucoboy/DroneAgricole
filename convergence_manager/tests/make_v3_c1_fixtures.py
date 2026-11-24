"""Construit les scènes C.1 sur copies privées du banc C4, sans lancer le solveur."""

import argparse
import os
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from electromechanical_engine import freecad_worker as native

App, Part = native.App, native.Part


def placement(x, y, z, angle=0):
    return App.Placement(App.Vector(x, y, z), App.Rotation(App.Vector(0, 0, 1), angle))


def child(doc, group, kind, name):
    entity = doc.addObject(kind, name)
    group.addObject(entity)
    return entity


def make_scene(output, second):
    shutil.copytree(ROOT / "docs/electromechanical_v3/bench_b1_c4/model", output)
    doc = App.openDocument(str(output / "Banc_Interconnexion.FCStd"))
    native.complete_dependencies(doc, output)
    device = doc.ElectricalDevice001
    fixed_port = doc.addObject("PartDesign::CoordinateSystem", "PortA")
    fixed_port.AttachmentSupport = [(doc.ElectricalDevice, [""])]
    fixed_port.MapMode = "ObjectXY"
    fixed_port.AttachmentOffset = placement(0, 0, 14)
    fixed_port.Visibility = False

    assets = App.newDocument("CoupledAssets")
    assembly = assets.addObject("App::Part", "DeviceDefinition")
    body = child(assets, assembly, "Part::Feature", "Body")
    body.Shape = doc.DeviceGeometry2.Shape.copy()
    datum_name = "OutputDatum" if second else "PortB"
    datum = child(assets, assembly, "PartDesign::CoordinateSystem", datum_name)
    datum.Placement = placement(0, 0, 14)
    datum.Visibility = False
    assets.recompute()
    assets.saveAs(str(output / "parts" / "CoupledAssets.FCStd"))

    fixture = doc.addObject("App::Part", "FixtureRig")
    fixture.Placement = placement(101, 5, 3, 25)
    stage = fixture
    if second:
        stage = child(doc, fixture, "App::Part", "InnerStage")
        stage.Placement = placement(6, -3, 1, -72)
    sibling_pose = App.Placement(App.Vector(111, -29, 0), device.Placement.Rotation)
    for name, target in (("Payload", device.Placement), ("Sibling", sibling_pose)):
        occurrence = child(doc, stage, "App::Link", name)
        occurrence.setLink(assembly)
        occurrence.LinkTransform = True
        occurrence.LinkPlacement = stage.getGlobalPlacement().inverse().multiply(target)
    # L2 exige le proxy d'attache visible. Le profil exclut son doublon
    # de l'inventaire physique ; le lien porte la géométrie de référence.
    device.Visibility = True
    doc.ServiceObstacle.LinkPlacement = placement(44 if second else 46, -4, -4)

    harness = doc.addObject("App::DocumentObjectGroup", "HarnessInventory")
    harness.addObject(doc.Cable)
    harness.Visibility = True
    doc.Cable.Visibility = True

    workholding = doc.addObject("App::Part", "Workholding")
    carrier = child(doc, workholding, "Part::Box", "Carrier")
    carrier.Length, carrier.Width, carrier.Height = 25, 23, 2
    carrier.Placement = placement(61, -7, -7)
    anchor = child(doc, workholding, "PartDesign::CoordinateSystem", "Anchor")
    anchor.Placement = placement(69, -4, -5)
    anchor.Visibility = False
    support = child(doc, workholding, "Part::Box", "Plate")
    support.Length, support.Width, support.Height = 6, 8, 3
    support.Placement = anchor.Placement
    stud = child(doc, workholding, "Part::Cylinder", "Stud")
    stud.Radius, stud.Height = 0.6, 1
    stud.Placement = placement(72, -2.9, -6)
    for field, kind, value in [("Anchor", "Link", anchor), ("Carrier", "Link", carrier),
                               ("Retains", "LinkListGlobal", [doc.Cable]), ("Fasteners", "LinkList", [stud])]:
        support.addProperty("App::Property" + kind, "B1_" + field, "V3 C.1")
        setattr(support, "B1_" + field, value)
    doc.Cable.addProperty("App::PropertyFloatList", "B1_ConductorSections", "V3 C.1")
    doc.Cable.B1_ConductorSections = [0.2] * 4

    # La première scène laisse l'outil passer au-dessus d'une butée latérale.
    # La seconde resserre aussi le côté positif à mi-parcours.
    guard = doc.addObject("Part::Box", "ServiceGuard")
    guard.Length, guard.Width, guard.Height = 5, 3, 5
    guard.Placement = placement(98, -10, -2)
    if second:
        baffle = doc.addObject("Part::Box", "LateralBaffle")
        baffle.Length, baffle.Width, baffle.Height = 11, 8, 9
        baffle.Placement = placement(37, 6, -4)

    doc.recompute()
    require_valid(doc)
    doc.save()
    for name in reversed(list(App.listDocuments())):
        App.closeDocument(name)
    for backup in output.glob("*.FCBak"):
        backup.unlink()


def require_valid(doc):
    invalid = [item.Name for item in doc.Objects if {"Invalid", "Error"}.intersection(item.State)]
    if invalid:
        raise RuntimeError(f"Objets natifs invalides : {invalid}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(ROOT / ".runtime") or output.exists():
        parser.error("Choisir un nouveau dossier sous .runtime")
    native.cables_environment(gui=True)
    make_scene(output / "coupled", second=False)
    make_scene(output / "secondary", second=True)


if __name__ == "__main__":
    main()
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0)
