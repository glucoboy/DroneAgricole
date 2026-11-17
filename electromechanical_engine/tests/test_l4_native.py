"""Smoke-test the L4 measurement boundary independently of the C++ verdicts."""

import json
import os
from pathlib import Path
from shutil import copy2
import subprocess
import sys
import tempfile
import unittest

from electromechanical_engine.contracts import load
from electromechanical_engine.freecad import FreeCADAdapter, PROJECT, guard
from electromechanical_engine.qualification.l4_native import bench_plan


REFERENCE = PROJECT / 'validation_engine/fixtures/native.json'
XLINK_REFERENCE = PROJECT / 'validation_engine/fixtures/xlink_l5/native.json'
FREECAD = os.environ.get('ELECTROMECHANICAL_FREECAD_PYTHON')


def observe(executable, case, output, *args, reference=REFERENCE):
    result = subprocess.run(
        [sys.executable, '-B', '-m', 'electromechanical_engine.qualification.l4_native',
         '--freecad-python', str(executable), '--workspace', str(PROJECT),
         '--reference', str(reference), '--case', case, '--output', str(output), *args],
        cwd=PROJECT, capture_output=True, text=True, timeout=90, check=False)
    receipt = json.loads((output / 'observation.json').read_text(encoding='utf-8'))
    return result, receipt


def build_xlink_fixture(executable, root):
    """Reconstruct the two-link static bench while preserving its editable Cables proxies."""
    upstream = PROJECT / 'convergence_manager/fixtures/native/native.json'
    plan = bench_plan(PROJECT, load(upstream)['cases']['consolidated-bench'])
    plan['candidate']['routes'] = {
        'L1': {'points_mm': [[0, 0, 10], [20, 0, 10], [20, -15, 10], [80, -15, 10],
                             [80, 0, 10], [100, 0, 10]], 'bend_radius_mm': 5},
        'L2': {'points_mm': [[0, 11, 10], [100, 11, 10]]},
    }
    built = root / 'monodocument'
    FreeCADAdapter(executable).build(plan, built)
    linked = root / 'linked'
    linked.mkdir()
    candidate = linked / 'assembly.FCStd'
    copy2(built / 'candidate.FCStd', candidate)
    subprocess.run([str(executable), '-B', '-c', '''
from pathlib import Path
import sys
from electromechanical_engine.freecad_worker import App, Part, cables_environment

cables_environment(gui=True)
entry = Path(sys.argv[1])
doc = App.openDocument(str(entry))
folder = entry.parent
reference = App.newDocument('Reference')
obstacle = reference.addObject('Part::Feature', 'ExternalReference')
obstacle.Shape = Part.makeBox(5, 5, 5, App.Vector(150, 50, 10))
reference.recompute()
reference.saveAs(str(folder / 'reference.FCStd'))
link = doc.addObject('App::Link', 'ExternalReferenceLink')
link.setLink(obstacle)
doc.recompute()
doc.save()
''', str(candidate)], cwd=PROJECT, check=True, timeout=30,
                   env=dict(os.environ, QT_QPA_PLATFORM='offscreen', PYTHONPATH=str(PROJECT)),
                   capture_output=True)
    return candidate


class L4NativeAdapterTests(unittest.TestCase):
    def test_unavailable_backend_finishes_with_explicit_state(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run, receipt = observe(root / 'absent-freecad.exe', 'native-nominal', root / 'output')
            self.assertNotEqual(run.returncode, 0)
            self.assertEqual(receipt['native_evidence']['state'], 'UNAVAILABLE')
            self.assertEqual(receipt['measurements'], {})

    @unittest.skipUnless(FREECAD, 'FreeCAD integration not requested')
    def test_saved_candidate_uses_native_bytes_and_ignores_builder_claims(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run, initial = observe(FREECAD, 'native-nominal', root / 'built')
            self.assertEqual(run.returncode, 0, initial)
            candidate = root / 'built/built/candidate.FCStd'
            digest = guard.sha256(candidate)
            claims = candidate.with_name('candidate_report.json')
            claims.write_text('{"status":"FAIL","clearance_mm":999}', encoding='utf-8')
            run, receipt = observe(FREECAD, 'saved-bench', root / 'inspect', '--candidate', str(candidate))
            self.assertEqual(run.returncode, 0, receipt)
            evidence = receipt['native_evidence']
            self.assertEqual(evidence['state'], 'MEASURED')
            self.assertTrue(evidence['repeat_exact'] and evidence['sources_unchanged']
                            and evidence['copies_unchanged'])
            self.assertEqual(evidence['native_sha256'], digest)
            self.assertEqual(guard.sha256(candidate), digest)
            self.assertEqual(len({record['pid'] for record in evidence['attempts']}), 2)
            self.assertEqual(len({record['worker_id'] for record in evidence['attempts']}), 2)
            for record in evidence['attempts']:
                self.assertEqual(guard.sha256(root / 'inspect' / record['artifact_path']), record['sha256'])
            self.assertNotIn('saved_process', evidence)
            self.assertEqual(receipt['measurements']['route_metrics']['L1']['diameter_mm'], 2)
            self.assertEqual(receipt['measurements']['architecture_metrics']['upper_zone_axis_length_mm']['value'], 0)

    @unittest.skipUnless(FREECAD, 'FreeCAD integration not requested')
    def test_missing_candidate_does_not_trigger_construction(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run, receipt = observe(FREECAD, 'saved-bench', root / 'output')
            self.assertNotEqual(run.returncode, 0)
            self.assertEqual(receipt['native_evidence']['state'], 'UNAVAILABLE')
            self.assertFalse((root / 'output/built').exists())

    @unittest.skipUnless(FREECAD, 'FreeCAD integration not requested')
    def test_frozen_xlink_obstacle_enlarges_pair_scope_on_both_reopens(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            candidate = build_xlink_fixture(FREECAD, root)
            before = {part.name: guard.sha256(part) for part in guard.dependencies(candidate.parent, [candidate.name])}
            run, receipt = observe(FREECAD, 'consolidated-bench', root / 'inspect',
                                   '--candidate', str(candidate), reference=XLINK_REFERENCE)
            self.assertEqual(run.returncode, 0, receipt)
            evidence, observations = receipt['native_evidence'], receipt['measurements']
            self.assertEqual(evidence['source_manifest']['before'], before)
            self.assertEqual(evidence['source_manifest']['after'], before)
            self.assertEqual(len({record['pid'] for record in evidence['attempts']}), 2)
            self.assertTrue(evidence['repeat_exact'] and observations['collision_complete'])
            obstacle = observations['xlink_obstacles']['ExternalReference']
            self.assertEqual(obstacle['occurrence'], 'assembly.FCStd#ExternalReferenceLink')
            self.assertEqual(obstacle['definition'], 'reference.FCStd#ExternalReference')
            self.assertEqual(obstacle['bounds_mm'], [[150, 50, 10], [155, 55, 15]])
            coverage = observations['xlink_pair_coverage']
            self.assertEqual(coverage['expected_pairs'], 10)
            self.assertEqual(coverage['native_pairs_attempted'] + coverage['pairs_excluded_by_aabb'], 10)
            self.assertEqual(coverage['pairs_missing_shapes'], [])
            for extraction in observations['extraction_evidence'].values():
                self.assertEqual(len(extraction['measurements']), 4)
                self.assertTrue(any(pair['b'] == 'ExternalReference' for pair in extraction['measurements']))

            # Move the definition geometry while keeping the root placement and XLink untouched.
            dependency = candidate.with_name('reference.FCStd')
            subprocess.run([str(FREECAD), '-B', '-c', '''
import sys
import FreeCAD as App
import Part

doc = App.openDocument(sys.argv[1])
doc.ExternalReference.Shape = Part.makeBox(5, 5, 6, App.Vector(150, 50, 10))
doc.recompute()
doc.save()
''', str(dependency)], check=True, timeout=30, capture_output=True)
            self.assertEqual(guard.sha256(candidate), before[candidate.name])
            self.assertNotEqual(guard.sha256(dependency), before[dependency.name])
            run, receipt = observe(FREECAD, 'consolidated-bench', root / 'moved',
                                   '--candidate', str(candidate), reference=XLINK_REFERENCE)
            self.assertEqual(run.returncode, 3, receipt)
            self.assertIn('changed shape or placement', receipt['native_evidence']['reason'])


if __name__ == '__main__':
    unittest.main()
