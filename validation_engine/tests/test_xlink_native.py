"""Native XLink occurrence tests using a separate FreeCAD Python process."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from electromechanical_engine.freecad import FreeCADAdapter, PROJECT, guard


ENTRY = 'assemblies/Root.FCStd'
DEPENDENCY = 'parts/Component.FCStd'
CONTACT = DEPENDENCY + '#Contact'
FIRST = ENTRY + '#Root/First/Contact'
SECOND = ENTRY + '#Root/Second/Contact'
ARRAY_ELEMENTS = [ENTRY + '#Root/Array/0', ENTRY + '#Root/Array/1']


def create_fixture(root):
    import FreeCAD as App
    import Part

    component = App.newDocument('Component')
    body = component.addObject('App::Part', 'Component')
    body.Placement = App.Placement(App.Vector(10, 0, 0), App.Rotation())
    contact = body.newObject('Part::Feature', 'Contact')
    contact.Shape = Part.makeBox(2, 3, 4)
    contact.Placement = App.Placement(App.Vector(0, 8, 0), App.Rotation())
    construction = body.newObject('Part::Feature', 'Construction')
    construction.Shape = Part.makeBox(1, 1, 1)
    construction.Visibility = False
    array_target = component.addObject('Part::Feature', 'ArrayTarget')
    array_target.Shape = Part.makeBox(2, 3, 4)
    array_target.Placement = App.Placement(App.Vector(10, 0, 0), App.Rotation())
    component.recompute()
    (root / DEPENDENCY).parent.mkdir(parents=True)
    component.saveAs(str(root / DEPENDENCY))

    assembly = App.newDocument('Assembly')
    (root / ENTRY).parent.mkdir()
    assembly.saveAs(str(root / ENTRY))
    group = assembly.addObject('App::Part', 'Root')
    group.Placement = App.Placement(App.Vector(0, 0, 13), App.Rotation())
    for name, x, transform in [('First', 7, False), ('Second', 14, True)]:
        link = group.newObject('App::Link', name)
        link.Label = 'Même composant'
        link.setLink(body)
        link.LinkTransform = transform
        link.LinkPlacement = App.Placement(
            App.Vector(x, 0, 0), App.Rotation(App.Vector(0, 0, 1), 90))
    array = group.newObject('App::Link', 'Array')
    array.setLink(array_target)
    array.LinkTransform = True
    array.LinkPlacement = App.Placement(App.Vector(20, 0, 0), App.Rotation())
    array.ShowElement = False
    array.ElementCount = 2
    array.PlacementList = [App.Placement(App.Vector(0, y, 0), App.Rotation()) for y in (10, 20)]
    assembly.recompute()
    assembly.save()


def change_dependency(root, action):
    import FreeCAD as App

    component = App.openDocument(str(root / DEPENDENCY))
    if action == 'move':
        component.Component.Placement = App.Placement(App.Vector(20, 0, 0), App.Rotation())
    else:
        component.removeObject('Component')
    component.recompute()
    component.save()


def inspect_fixture(root, output):
    from electromechanical_engine.freecad_worker import App, complete_dependencies
    from electromechanical_engine.xlink_native import collect

    hashes = FreeCADAdapter._native_hashes(root, ENTRY)
    assembly = App.openDocument(str(root / ENTRY))
    complete_dependencies(assembly, root)
    occurrences, shapes, _ = collect(assembly, root, hashes)
    bounds = {}
    for occurrence in (FIRST, SECOND, *ARRAY_ELEMENTS):
        if occurrence in shapes:
            box = shapes[occurrence].BoundBox
            bounds[occurrence] = [box.XMin, box.YMin, box.ZMin, box.XMax, box.YMax, box.ZMax]
    output.write_text(json.dumps({
        'pid': os.getpid(),
        'hashes': hashes,
        'occurrences': occurrences,
        'bounds_mm': bounds,
    }, allow_nan=False), encoding='utf-8')


@unittest.skipUnless(os.environ.get('ELECTROMECHANICAL_FREECAD_PYTHON'), 'FreeCAD integration not requested')
class XLinkNativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        runtime = PROJECT / '.runtime'
        runtime.mkdir(exist_ok=True)
        working = tempfile.TemporaryDirectory(prefix='v21-xlink-tests-', dir=runtime)
        cls.addClassCleanup(working.cleanup)
        cls.root = Path(working.name)
        cls.source = cls.root / 'source'
        cls.worker('create', cls.source)

    @staticmethod
    def worker(action, root, *args):
        result = subprocess.run(
            [os.environ['ELECTROMECHANICAL_FREECAD_PYTHON'], '-B', str(Path(__file__).resolve()),
             '--worker', action, str(root), *map(str, args)],
            cwd=PROJECT, capture_output=True, text=True, encoding='utf-8', errors='replace',
            env=dict(os.environ, PYTHONPATH=str(PROJECT), PYTHONUTF8='1', QT_QPA_PLATFORM='offscreen'),
            timeout=30, check=False)
        if result.returncode != 0:
            raise AssertionError(f'Worker {action} failed with code {result.returncode}\n'
                                 f'{result.stdout}\n{result.stderr}')

    def staged(self, label):
        target = self.root / label
        return target, guard.stage(self.source, ENTRY, target)

    def observe(self, root, suffix):
        output = self.root / f'{suffix}.json'
        self.worker('inspect', root, output)
        return json.loads(output.read_text(encoding='utf-8'))

    def assert_coordinates(self, actual, expected):
        self.assertEqual(len(actual), len(expected))
        for value, reference in zip(actual, expected, strict=True):
            self.assertAlmostEqual(value, reference, places=7)

    def test_repeated_reference_has_distinct_poses_and_world_shapes(self):
        copy, receipt = self.staged('repeated')
        observed = self.observe(copy, 'repeated')
        for key, translation, bounds in (
                (FIRST, [-1, 0, 13], [-4, 0, 13, -1, 2, 17]),
                (SECOND, [6, 10, 13], [3, 10, 13, 6, 12, 17])):
            item = observed['occurrences'][key]
            self.assertEqual(item['definition'], CONTACT)
            self.assertEqual(item['status'], 'PASS')
            self.assertTrue(item['terminal_shape'])
            self.assert_coordinates([item['matrix'][i] for i in (3, 7, 11)], translation)
            self.assert_coordinates(observed['bounds_mm'][key], bounds)
        self.assertEqual(observed['hashes'], receipt['inputs_sha256'])
        self.assertTrue(guard.verify_sources(receipt)['sources_unchanged'])

    def test_hidden_construction_solid_does_not_count_as_visible_geometry(self):
        copy, _ = self.staged('visibility')
        observed = self.observe(copy, 'visibility')
        for link in ('First', 'Second'):
            reference = ENTRY + '#Root/' + link + '/Construction'
            self.assertFalse(observed['occurrences'][reference]['visible'])

    def test_indexed_link_array_exposes_each_physical_occurrence(self):
        copy, _ = self.staged('array')
        observed = self.observe(copy, 'array')
        for key, y in zip(ARRAY_ELEMENTS, (10, 20), strict=True):
            item = observed['occurrences'][key]
            self.assertEqual(item['definition'], DEPENDENCY + '#ArrayTarget')
            self.assertEqual(item['status'], 'PASS')
            self.assertTrue(item['terminal_shape'])
            self.assert_coordinates(observed['bounds_mm'][key], [30, y, 13, 32, y + 3, 17])

    def test_dependency_edit_changes_closure_and_affected_occurrence_only(self):
        copy, receipt = self.staged('moved')
        before = self.observe(copy, 'before-move')
        self.worker('move', copy)
        after = self.observe(copy, 'after-move')
        self.assertNotEqual(before['pid'], after['pid'])
        self.assertEqual(before['hashes'][ENTRY], after['hashes'][ENTRY])
        self.assertNotEqual(before['hashes'][DEPENDENCY], after['hashes'][DEPENDENCY])
        self.assert_coordinates(after['bounds_mm'][FIRST], before['bounds_mm'][FIRST])
        self.assert_coordinates(after['bounds_mm'][SECOND], [3, 20, 13, 6, 22, 17])
        self.assertTrue(guard.verify_sources(receipt)['sources_unchanged'])

    def test_missing_native_is_reported_before_opening(self):
        copy, receipt = self.staged('missing')
        (copy / DEPENDENCY).unlink()
        with self.assertRaisesRegex(ValueError, 'Dépendance absente'):
            guard.stage(copy, ENTRY, self.root / 'missing-attempt')
        self.assertFalse((self.root / 'missing-attempt').exists())
        self.assertTrue(guard.verify_sources(receipt)['sources_unchanged'])

    def test_existing_dependency_with_removed_link_target_is_visible(self):
        copy, receipt = self.staged('broken')
        self.worker('remove-target', copy)
        after = self.observe(copy, 'broken')
        self.assertEqual(after['hashes'][ENTRY], receipt['inputs_sha256'][ENTRY])
        self.assertNotEqual(after['hashes'][DEPENDENCY], receipt['inputs_sha256'][DEPENDENCY])
        for key in ('First', 'Second'):
            item = after['occurrences'][ENTRY + '#Root/' + key]
            self.assertIn(item['status'], ('FAIL', 'INCONCLUSIVE', 'NOT_RUN'))
        self.assertNotIn(FIRST, after['occurrences'])
        self.assertNotIn(SECOND, after['occurrences'])
        self.assertTrue(guard.verify_sources(receipt)['sources_unchanged'])


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--worker':
        action, working = sys.argv[2], Path(sys.argv[3]).resolve()
        if action == 'create':
            create_fixture(working)
        elif action == 'inspect':
            inspect_fixture(working, Path(sys.argv[4]))
        else:
            change_dependency(working, action)
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(0)
    unittest.main()
