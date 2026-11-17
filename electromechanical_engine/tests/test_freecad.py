"""Native tests opt in with ELECTROMECHANICAL_FREECAD_PYTHON."""

import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from zipfile import ZipFile

from electromechanical_engine.freecad import FreeCADAdapter, FreeCADError, guard


def scenario(points, radius):
    return {
        'system': {
            'ports': [{'id': 'P0', 'position_mm': [0, 0, 10], 'tangent': [1, 0, 0]},
                      {'id': 'P1', 'position_mm': [100, 0, 10], 'tangent': [-1, 0, 0]}],
            'links': [{'id': 'L0', 'source': 'P0', 'target': 'P1'}],
            'geometry': {'boxes': [{'id': 'plate', 'origin_mm': [45, -4, 7], 'size_mm': [10, 8, 6]},
                                   {'id': 'far', 'origin_mm': [120, 0, 0], 'size_mm': [2, 2, 2]}],
                         'extraction': [{'port': 'P0', 'origin_mm': [40, -2, 8], 'size_mm': [8, 4, 4],
                                         'ignore_ids': ['L0']}]},
        },
        'requirements': {'links': {'L0': {'diameter_mm': 2, 'min_radius_mm': 5}}, 'clearance_mm': 1},
        'candidate': {'routes': {'L0': {'points_mm': points, 'bend_radius_mm': radius, 'corridor': 'C0'}}},
    }


class FreeCADIsolationTests(unittest.TestCase):
    def test_backend_selection_does_not_claim_geometry_was_executed(self):
        self.assertEqual(guard.select_backend(True, {}),
                         {'backend': 'mcp', 'geometry_executed': False})
        self.assertEqual(guard.select_backend(False, {'verified': True}),
                         {'backend': 'freecad_python', 'geometry_executed': False,
                          'requires_cables_probe': True})

    def test_missing_backend_is_explicit(self):
        with tempfile.TemporaryDirectory() as target:
            adapter = FreeCADAdapter(Path(target) / 'absent.exe')
            self.assertFalse(adapter.probe()['verified'])
            with self.assertRaises(FreeCADError):
                adapter.build({}, Path(target) / 'candidate')

    def test_broken_xlink_prevents_opening(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'source'
            source.mkdir()
            with ZipFile(source / 'Assembly.FCStd', 'w') as archive:
                archive.writestr('Document.xml', '<Document><XLink file="Absent.FCStd"/></Document>')
            with self.assertRaisesRegex(ValueError, 'Dépendance absente'):
                FreeCADAdapter(root / 'unused.exe').extract(source, 'Assembly.FCStd', root / 'copy')
            self.assertFalse((root / 'copy').exists())

    def test_reference_write_is_detected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'source'
            source.mkdir()
            native = source / 'Assembly.FCStd'
            with ZipFile(native, 'w') as archive:
                archive.writestr('Document.xml', '<Document/>')
            receipt = guard.stage(source, native.name, root / 'copy')
            self.assertTrue(guard.verify_sources(receipt)['sources_unchanged'])
            native.write_bytes(b'changed')
            with self.assertRaisesRegex(RuntimeError, 'Sources modifiées'):
                guard.verify_sources(receipt)


@unittest.skipUnless(os.environ.get('ELECTROMECHANICAL_FREECAD_PYTHON'), 'FreeCAD integration not requested')
class FreeCADIntegrationTests(unittest.TestCase):
    def test_invalid_native_feature_or_solid_blocks_extraction(self):
        adapter = FreeCADAdapter(os.environ['ELECTROMECHANICAL_FREECAD_PYTHON'])
        setup = '''
import sys
import FreeCAD as App
import Part
doc = App.newDocument('InvalidSource')
'''
        bodies = {
            'recompute': '''
obj = doc.addObject('Part::Box', 'BadObject')
obj.Length = 0
doc.recompute()
assert 'Invalid' in obj.State and obj.Shape.isNull()
''',
            'solid': '''
obj = doc.addObject('Part::Feature', 'BadObject')
obj.Shape = Part.Solid(Part.Shell([Part.makePlane(10, 10)]))
assert not obj.Shape.isValid() and len(obj.Shape.Solids) == 1
''',
        }
        for case, body in bodies.items():
            with self.subTest(case=case), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                source = root / 'source'
                source.mkdir()
                native = source / 'Invalid.FCStd'
                fixture = setup + body + 'doc.saveAs(sys.argv[1])'
                subprocess.run([str(adapter.python), '-B', '-c', fixture, str(native)], check=True, timeout=20)
                original = guard.sha256(native)
                observed = adapter.extract(source, native.name, root / 'copy')
                self.assertTrue(observed['inventory_complete'])
                self.assertFalse(observed['recompute_ok'])
                self.assertFalse(observed['save_performed'])
                self.assertFalse(observed['reopened'])
                self.assertEqual(observed['invalid_objects'], ['Invalid.FCStd#BadObject'])
                self.assertEqual(observed['native_inputs_sha256'], {native.name: original})
                self.assertEqual(guard.sha256(native), original)

    def test_native_xlink_extraction_preserves_the_two_sources(self):
        adapter = FreeCADAdapter(os.environ['ELECTROMECHANICAL_FREECAD_PYTHON'])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'source'
            (source / 'parts').mkdir(parents=True)
            (source / 'assemblies').mkdir()
            fixture = '''
import sys
from pathlib import Path
import FreeCAD as App
import Part
root = Path(sys.argv[1])
part = App.newDocument('SourcePart')
box = part.addObject('Part::Box', 'Box')
part.addObject('Part::Box', 'UnlinkedBox')
part.recompute()
part.saveAs(str(root / 'parts' / 'Part.FCStd'))
assembly = App.newDocument('SourceAssembly')
assembly.saveAs(str(root / 'assemblies' / 'Assembly.FCStd'))
assembly.addObject('App::Link', 'Link').LinkedObject = box
assembly.recompute()
assembly.save()
'''
            subprocess.run([str(adapter.python), '-B', '-c', fixture, str(source)], check=True, timeout=20)
            report = adapter.extract(source, 'assemblies/Assembly.FCStd', root / 'copy')
            self.assertEqual(report['files_checked'], 2)
            self.assertTrue(report['sources_unchanged'])
            self.assertTrue(report['recompute_ok'])
            self.assertTrue(report['reopened'])
            self.assertNotEqual(report['saved_worker_id'], report['worker_id'])
            self.assertEqual(report['documents'][0]['objects'][0]['linked_object'], 'parts/Part.FCStd#Box')
            self.assertEqual(report['partial_documents'], [])
            self.assertEqual({obj['name'] for obj in report['documents'][1]['objects']},
                             {'Box', 'UnlinkedBox'})
            self.assertEqual(set(report['native_inputs_sha256']),
                             {'assemblies/Assembly.FCStd', 'parts/Part.FCStd'})

    def test_native_collision_and_correction_after_independent_reopen(self):
        adapter = FreeCADAdapter(os.environ['ELECTROMECHANICAL_FREECAD_PYTHON'])
        straight = scenario([[0, 0, 10], [100, 0, 10]], 0)
        bend = scenario([[0, 0, 10], [20, 0, 10], [20, 15, 10], [80, 15, 10], [80, 0, 10], [100, 0, 10]], 5)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            baseline = adapter.build(straight, root / 'baseline')
            corrected = adapter.build(bend, root / 'corrected')
            for report in (baseline, corrected):
                self.assertTrue(report['reopened'])
                self.assertNotEqual(report['worker_id'], report['saved_worker_id'])
                self.assertTrue(report['recompute_ok'])
                self.assertTrue(report['collision_complete'])
                self.assertFalse(report['extraction_clear']['P0'])
                route = report['route_metrics']['L0']
                self.assertTrue(route['radius_certified'])
                self.assertTrue(route['solid_valid'])
                self.assertTrue(route['tangency_ok'])
                self.assertTrue(route['endpoints_ok'])
            self.assertGreater(baseline['collisions'][0]['intersection_mm3'], 1)
            self.assertTrue(all(pair['status'] == 'pass' for pair in corrected['collisions']))
            filtered = corrected['collision_filtered_evidence']
            self.assertEqual(len(filtered), corrected['collision_filtered_pairs'])
            self.assertTrue(all(pair['clearance_lower_bound_mm'] > 1 for pair in filtered))
            self.assertIn({'far', 'L0'}, [{pair['a'], pair['b']} for pair in filtered])
            self.assertAlmostEqual(corrected['route_metrics']['L0']['min_radius_mm'], 5)
            self.assertGreater(corrected['route_metrics']['L0']['length_mm'], baseline['route_metrics']['L0']['length_mm'])
            observed = adapter.inspect(root / 'corrected', bend)
            self.assertEqual(observed['native_sha256'], corrected['native_sha256'])
            self.assertNotEqual(observed['worker_id'], corrected['worker_id'])

    def test_native_clear_route_can_still_block_connector_extraction(self):
        adapter = FreeCADAdapter(os.environ['ELECTROMECHANICAL_FREECAD_PYTHON'])
        points = [[0, 0, 10], [20, 0, 10], [20, 15, 10],
                  [80, 15, 10], [80, 0, 10], [100, 0, 10]]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for case, y, expected in (('blocked', -2, False), ('clear', 25, True)):
                with self.subTest(case=case):
                    plan = scenario(points, 5)
                    plan['system']['geometry']['extraction'][0]['origin_mm'][1] = y
                    report = adapter.build(plan, root / case)
                    self.assertTrue(report['reopened'])
                    self.assertTrue(report['collision_complete'])
                    self.assertTrue(all(pair['status'] == 'pass' for pair in report['collisions']))
                    self.assertIs(report['extraction_clear']['P0'], expected)
                    evidence = report['extraction_evidence']['P0']
                    self.assertEqual(evidence['ignored_ids'], ['L0'])
                    self.assertEqual(evidence['unavailable_ids'], [])
                    self.assertEqual({row['b']: row['status'] for row in evidence['measurements']},
                                     {'far': 'pass', 'plate': 'pass' if expected else 'fail'})
