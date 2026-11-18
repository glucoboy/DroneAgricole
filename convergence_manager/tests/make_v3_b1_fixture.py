"""Produce the native files of the second B.1 bench in a new runtime directory."""

import argparse
import os
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from electromechanical_engine import freecad_worker as native

App, Part = native.App, native.Part


def placement(x, y, z, degrees=0):
    return App.Placement(App.Vector(x, y, z), App.Rotation(App.Vector(0, 0, 1), degrees))


def member(doc, group, kind, name):
    obj = doc.addObject(kind, name)
    group.addObject(obj)
    return obj


def make_fixture(output):
    source = ROOT / 'docs/electromechanical_v3/bench_b1_c4/model'
    shutil.copytree(source, output)
    native.cables_environment(gui=True)
    doc = App.openDocument(str(output / 'Banc_Interconnexion.FCStd'))
    native.complete_dependencies(doc, output)
    doc.ServiceObstacle.LinkPlacement = placement(46, -31, -4)

    part = App.newDocument('FixtureAssets')
    shared = part.addObject('Part::Box', 'SharedDevice')
    shared.Length, shared.Width, shared.Height = 6, 5, 4
    shared.Placement = placement(2, 0, 1)
    part.recompute()
    part.saveAs(str(output / 'parts' / 'FixtureAssets.FCStd'))
    rig = doc.addObject('App::Part', 'FixtureRig')
    rig.Placement = placement(75, 33, 6, 90)
    for name, where, transform in [('Payload', (6, 0, 0), True), ('Sibling', (22, 0, 0), False)]:
        link = member(doc, rig, 'App::Link', name)
        link.setLink(shared)
        link.LinkTransform = transform
        link.LinkPlacement = placement(*where)

    harness = doc.addObject('App::DocumentObjectGroup', 'HarnessInventory')
    harness.addObject(doc.Cable)
    doc.Cable.addProperty('App::PropertyFloatList', 'B1_ConductorSections', 'V3 B.1')
    doc.Cable.B1_ConductorSections = [0.2] * 4
    group = doc.addObject('App::Part', 'Workholding')
    carrier = member(doc, group, 'Part::Box', 'Carrier')
    carrier.Length, carrier.Width, carrier.Height = 33, 18, 2
    carrier.Placement = placement(56, -9, -7)
    anchors = []
    for name, x in [('AnchorBefore', 60), ('AnchorRelocate', 68), ('AnchorNew', 78)]:
        anchor = member(doc, group, 'PartDesign::CoordinateSystem', name)
        anchor.Placement = placement(x, -4, -5)
        anchor.Visibility = False
        anchors.append(anchor)
    support = member(doc, group, 'Part::Box', 'ExistingPlate')
    support.Length, support.Width, support.Height = 7, 8, 3
    support.Placement = anchors[0].Placement
    stud = member(doc, group, 'Part::Cylinder', 'ExistingStud')
    stud.Radius, stud.Height = 0.7, 1
    stud.Placement = placement(62, -2.8, -6)
    for field, kind, value in [('Anchor', 'Link', anchors[0]), ('Carrier', 'Link', carrier),
                               ('Retains', 'LinkListGlobal', [doc.Cable]), ('Fasteners', 'LinkList', [stud])]:
        support.addProperty('App::Property' + kind, 'B1_' + field, 'V3 B.1')
        setattr(support, 'B1_' + field, value)
    doc.recompute()
    doc.Cable.Visibility = True
    harness.Visibility = True
    group.Visibility = True
    rig.Visibility = True
    doc.save()
    for name in reversed(list(App.listDocuments())):
        App.closeDocument(name)
    for backup in output.glob('*.FCBak'):
        backup.unlink()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(ROOT / '.runtime') or output.exists():
        parser.error('Choisir un nouveau dossier de fixture sous .runtime')
    make_fixture(output)
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0)
