"""FreeCAD worker regressions for occurrence-specific poses and rollback."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import unittest
from uuid import uuid4


REPO = Path(__file__).resolve().parents[2]
WORKER = REPO / 'convergence_manager/native/v3_mutate.py'
ENTRY = 'assemblies/Assembly.FCStd'
DEFINITION = 'parts/Shared.FCStd'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pose(translation, rotation):
    return dict(translation_mm=translation, rotation_xyzw=rotation)


def create_fixture(root):
    import FreeCAD as App

    for path in (ENTRY, DEFINITION):
        (root / path).parent.mkdir(parents=True, exist_ok=True)
    source = App.newDocument('Definitions')
    obj = source.addObject('Part::Box', 'SharedBox')
    obj.Length, obj.Width, obj.Height = 4, 2, 1
    obj.Placement = App.Placement(App.Vector(3, 4, 5), App.Rotation(App.Vector(0, 0, 1), 30))
    source.recompute()
    source.saveAs(str(root / DEFINITION))
    doc = App.newDocument('Bench')
    doc.saveAs(str(root / ENTRY))
    assembly = doc.addObject('App::Part', 'Assembly')
    assembly.Placement = App.Placement(App.Vector(20, 30, 4), App.Rotation(App.Vector(0, 0, 1), 90))
    for name, x in [('Mobile', 10), ('Peer', 45)]:
        link = doc.addObject('App::Link', name)
        assembly.addObject(link)
        link.setLink(obj)
        link.LinkTransform = True
        link.LinkPlacement = App.Placement(App.Vector(x, 0, 0), App.Rotation())
    doc.recompute()
    doc.save()
    App.closeDocument(doc.Name)
    App.closeDocument(source.Name)


def extract(root, target):
    import FreeCAD as App
    import Part

    doc = App.openDocument(str(root / ENTRY))
    doc.recompute()
    rows = {}
    for name in ('Mobile', 'Peer'):
        shape, matrix, _ = Part.getShape(doc.Assembly, name + '.', retType=2)
        place = App.Placement(matrix)
        rows[name] = dict(placement=pose(list(place.Base), list(place.Rotation.Q)),
                          shape_sha256=hashlib.sha256(shape.exportBrepToString().encode()).hexdigest(),
                          link_transform=doc.getObject(name).LinkTransform)
    target.write_text(json.dumps(rows), encoding='utf-8')
    names = list(App.listDocuments())
    for name in names:
        if name in App.listDocuments():
            App.closeDocument(name)


class NativeMutations(unittest.TestCase):
    freecad = None

    def setUp(self):
        self.work = REPO / '.runtime/v3-b1/worker-tests' / uuid4().hex
        self.source = self.work / 'source'
        self.call(['--fixture-worker', str(self.source)])
        self.baseline = self.inspect(self.source, 'baseline.json')
        self.dependencies = {key: sha(self.source / key) for key in (ENTRY, DEFINITION)}

    def call(self, arguments, expected=0, script=Path(__file__).resolve()):
        result = subprocess.run([str(self.freecad), '-B', str(script), *arguments], cwd=REPO,
                                env=dict(os.environ, QT_QPA_PLATFORM='offscreen', PYTHONUTF8='1'),
                                capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=45)
        self.assertEqual(result.returncode, expected, result.stdout + '\n' + result.stderr)

    def inspect(self, root, name):
        path = self.work / name
        self.call(['--extract-worker', str(root), str(path)])
        return json.loads(path.read_text(encoding='utf-8'))

    def execute(self, actions, name, expected=0):
        case = self.work / name
        root = case / 'mutation'
        shutil.copytree(self.source, root)
        job = dict(entry=ENTRY, dependencies=self.dependencies, plan_id=name, actions=actions,
                   model=dict(occurrences={'mobile': 'Assembly/Mobile', 'peer': 'Assembly/Peer'}))
        request, result = case / 'job.json', case / 'build.json'
        request.write_text(json.dumps(job), encoding='utf-8')
        self.call(['--root', str(root), '--job', str(request), '--output', str(result)], expected, WORKER)
        report = json.loads(result.read_text(encoding='utf-8'))
        self.assertTrue(report['finalized'], report)
        self.assertTrue(report['documents_closed'], report)
        self.assertEqual(report['job_sha256'], sha(request))
        self.assertEqual(report['before_sha256'], self.dependencies)
        for key, digest in self.dependencies.items():
            self.assertEqual(sha(self.source / key), digest)
        return root, report

    def action(self, requested, effective, frame='ROOT'):
        return dict(id='MOVE-01', operation='REPOSITION_DEVICE', occurrence='mobile',
                    parameters=dict(frame=frame, placement=requested),
                    expected_before=dict(placement=self.baseline['Mobile']['placement']),
                    expected_after=dict(placement=effective))

    def test_pose_inputs_preserve_shared_definition_and_peer_after_transfer(self):
        unit = 2 ** -0.5
        first_pose = pose([13, 15, 4], [0, 0, 0, 1])
        local_pose = pose([3, 7, 12], [0, 0, 0, 1])
        second_pose = pose([13, 33, 16], [0, 0, unit, unit])
        cases = [('root-pose', self.action(first_pose, first_pose)),
                 ('parent-pose', self.action(local_pose, second_pose, 'PARENT'))]
        shapes = {self.baseline['Mobile']['shape_sha256']}
        for name, action in cases:
            with self.subTest(case=name):
                root, report = self.execute([action], name)
                self.assertEqual(report['status'], 'PASS')
                self.assertEqual(report['memory_transaction'], 'COMMITTED')
                self.assertNotEqual(report['after_sha256'][ENTRY], self.dependencies[ENTRY])
                self.assertEqual(report['after_sha256'][DEFINITION], self.dependencies[DEFINITION])
                transferred = self.work / (name + '-independent')
                shutil.copytree(root, transferred)
                observed = self.inspect(transferred, name + '-reopened.json')
                self.assertEqual(observed['Peer'], self.baseline['Peer'])
                self.assertTrue(observed['Mobile']['link_transform'])
                before = self.baseline['Mobile']['placement']
                after = observed['Mobile']['placement']
                expected = action['expected_after']['placement']
                self.assertNotEqual(before['translation_mm'], after['translation_mm'])
                for key in expected:
                    for expected_value, actual_value in zip(expected[key], after[key], strict=True):
                        self.assertAlmostEqual(expected_value, actual_value, places=7)
                self.assertNotIn(observed['Mobile']['shape_sha256'], shapes)
                shapes.add(observed['Mobile']['shape_sha256'])

    def test_late_duplicate_point_failure_rolls_back_already_moved_occurrence(self):
        goal = pose([13, 15, 4], [0, 0, 0, 1])
        invalid = dict(id='DUPLICATE-02', operation='REROUTE_HARNESS', occurrence='peer',
                       parameters=dict(frame='ROOT', points_mm=[[0, 0, 0], [0, 0, 0]]),
                       expected_before=dict(exists=True), expected_after=dict(exists=True))
        root, report = self.execute([self.action(goal, goal), invalid], 'duplicate-point', 2)
        self.assertEqual(report['status'], 'FAIL')
        self.assertEqual(report['memory_transaction'], 'ABORTED')
        self.assertFalse(report['save_performed'])
        self.assertIn('points du parcours sont confondus', report['reason'])
        self.assertEqual([row['status'] for row in report['operations']], ['APPLIED_IN_MEMORY', 'STARTED'])
        for key, digest in self.dependencies.items():
            self.assertEqual(sha(root / key), digest)


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '--fixture-worker':
        create_fixture(Path(sys.argv[2]))
    elif len(sys.argv) == 4 and sys.argv[1] == '--extract-worker':
        extract(Path(sys.argv[2]), Path(sys.argv[3]))
    else:
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument('--freecad', required=True, type=Path)
        args, remaining = parser.parse_known_args()
        NativeMutations.freecad = args.freecad.resolve(strict=True)
        unittest.main(argv=[sys.argv[0], *remaining])
