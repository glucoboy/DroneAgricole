"""Rejeu CLI XLink sur deux documents FreeCAD construits pour l’essai."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


PROJECT = Path(__file__).resolve().parents[2]
ENTRY = 'assemblies/Root.FCStd'
DEPENDENCY = 'parts/Obstacle.FCStd'
CABLE = ENTRY + '#Root/Cable'


def create_fixture(source):
    from electromechanical_engine.freecad_worker import App, builder, cables_environment

    cables_environment(gui=True)
    part = App.newDocument('Obstacle')
    obstacle = part.addObject('Part::Box', 'Obstacle')
    obstacle.Length, obstacle.Width, obstacle.Height = 4, 1, 2
    obstacle.Placement.Base = App.Vector(4, -0.5, -1)
    part.recompute()
    (source / DEPENDENCY).parent.mkdir(parents=True)
    part.saveAs(str(source / DEPENDENCY))

    doc = App.newDocument('Assembly')
    (source / ENTRY).parent.mkdir()
    doc.saveAs(str(source / ENTRY))
    group = doc.addObject('App::Part', 'Root')
    cable, _ = builder.make_native_cable(doc, group, 'FixtureCable', [(0, 0, 0), (20, 0, 0)], 2, 2)
    if cable.Name != 'Cable':
        raise RuntimeError(f'Nom natif inattendu : {cable.Name}')
    link = group.newObject('App::Link', 'Obstacle')
    link.setLink(obstacle)
    link.LinkTransform = True
    for name, position, dimensions in (
        ('Bearing', (9, 1, -1), (3, 1, 2)),
        ('ConduitEnvelope', (-1, -2, -2), (22, 4, 4)),
        ('Near', (13, 1.55, -1), (3, 1, 2)),
        ('Far', (30, 0, -1), (3, 1, 2)),
    ):
        element = group.newObject('Part::Box', name)
        element.Length, element.Width, element.Height = dimensions
        element.Placement.Base = App.Vector(*position)
    doc.recompute()
    doc.save()


def move_obstacle(source):
    import FreeCAD as App

    part = App.openDocument(str(source / DEPENDENCY))
    obstacle = part.getObject('Obstacle')
    obstacle.Placement.Base = App.Vector(4, -4, -1)
    part.recompute()
    part.save()


def relative(path):
    return path.resolve().relative_to(PROJECT).as_posix()


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def relation(kind, outer, **details):
    return {'kind': kind, 'inner_id': CABLE, 'outer_id': ENTRY + '#Root/' + outer,
            'justification': 'Géométrie et relation définies pour le banc synthétique', **details}


def execute(command, timeout=90):
    return subprocess.run(command, cwd=PROJECT, capture_output=True, text=True, encoding='utf-8',
                          errors='replace', timeout=timeout, check=False,
                          env=dict(os.environ, PYTHONPATH=str(PROJECT), PYTHONUTF8='1', QT_QPA_PLATFORM='offscreen'))


class XLinkCliTest(unittest.TestCase):
    def worker(self, action, source):
        run = execute([FREECAD, '-B', str(Path(__file__).resolve()), '--worker', action, str(source)], timeout=40)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)

    def campaign(self, configuration, output, *options):
        existing = set(output.glob('run-*/campaign.json'))
        run = execute([VALIDATOR, 'xlink', '--configuration', relative(configuration), '--output', relative(output),
                       '--freecad-python', FREECAD, *options])
        self.assertEqual(run.returncode, 3, run.stdout + run.stderr)
        candidates = set(output.glob('run-*/campaign.json')) - existing
        self.assertEqual(len(candidates), 1, run.stdout + run.stderr)
        report_file = candidates.pop()
        self.assertTrue(report_file.with_name('t0_run_manifest.json').is_file())
        report = json.loads(report_file.read_text(encoding='utf-8'))
        self.assertTrue(report['finalized'])
        self.assertEqual(report['verdict'], 'V21_XLINK_CONDITIONAL')
        self.assertEqual(report['electrical']['status'], 'NOT_RUN')
        closure = report['closure']
        self.assertTrue(closure['reopened'])
        self.assertNotEqual(closure['saved_worker'], closure['reopened_worker'])
        self.assertTrue(closure['integrity']['sources_unchanged'])
        return report

    def test_reprise_and_dependency_change(self):
        runtime = PROJECT / '.runtime'
        runtime.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='v21-xlink-cli-', dir=runtime) as temporary:
            work = Path(temporary)
            source = work / 'source'
            first = work / 'campaign'
            configuration = work / 'settings.json'
            self.worker('create', source)
            configuration.write_text(json.dumps({
                'scope': 'banc_xlink_deux_natifs', 'source': relative(source), 'entry': ENTRY, 'native_count': 2,
                'criteria': {'requirements': ['MEC-INT-001'], 'state': 'nominal_banc', 'screening_only': False,
                             'clearance_mm': 0.5, 'distance_tolerance_mm': 0.1, 'volume_tolerance_mm3': 1e-7,
                             'route_criteria': {CABLE: {'minimum_radius_mm': 2, 'start_mm': [0, 0, 0],
                                                        'end_mm': [20, 0, 0], 'start_axis': [1, 0, 0],
                                                        'end_axis': [-1, 0, 0]}},
                             'contacts': [relation('functional_contact', 'Bearing'),
                                          relation('cable_in_conduit_envelope', 'ConduitEnvelope',
                                                   outer_representation='occupancy_envelope')]},
            }), encoding='utf-8')
            root_hash = sha256(source / ENTRY)
            obstacle_hash = sha256(source / DEPENDENCY)

            interrupted = self.campaign(configuration, first, '--batch-timeout-ms', '1')
            self.assertTrue(interrupted['phases']['batch']['timed_out'])
            self.assertEqual(interrupted['geometry']['expected_pairs'], 5)
            self.assertEqual(interrupted['geometry']['possible_brep_pairs'], 4)
            self.assertEqual(interrupted['geometry']['pairs_examined'], 0)
            self.assertEqual(interrupted['geometry']['pairs_not_run'], 4)
            pending = [row for row in interrupted['geometry']['checks'] if row['task']['kind'] == 'pair']
            self.assertTrue(all(row['status'] == 'NOT_RUN' and row['native_evidence'] is None for row in pending))

            partial = self.campaign(configuration, first, '--max-native-tasks', '2')
            partial_checks = partial['geometry']['checks']
            published = {row['task']['id']: row['native_evidence'] for row in partial_checks if row['native_evidence']}
            self.assertEqual(len(published), 2)
            completed = self.campaign(configuration, first)
            self.assertEqual(completed['closure']['cache_key'], interrupted['closure']['cache_key'])
            self.assertEqual(completed['geometry']['resumed_tasks'], 2)
            self.assertEqual(completed['geometry']['pairs_examined'], 4)
            self.assertEqual(completed['geometry']['pairs_not_run'], 0)
            self.assertEqual(completed['geometry']['pairs_screened_out'], 1)
            self.assertEqual(completed['geometry']['status'], 'FAIL')
            for row in completed['geometry']['checks']:
                if row['task']['id'] in published:
                    self.assertEqual(row['native_evidence'], published[row['task']['id']])

            pairs = {row['task']['b'].rsplit('/', 1)[1]: row for row in completed['geometry']['checks']
                     if row['task']['kind'] == 'pair'}
            self.assertEqual({name: row['status'] for name, row in pairs.items()},
                             {'Bearing': 'PASS', 'ConduitEnvelope': 'PASS', 'Near': 'PASS', 'Obstacle': 'FAIL'})
            self.assertTrue(pairs['Bearing']['native_evidence']['observation']['authorized_relation'])
            self.assertTrue(pairs['ConduitEnvelope']['native_evidence']['observation']['authorized_relation'])
            self.assertAlmostEqual(pairs['Near']['native_evidence']['observation']['clearance_mm'], 0.55, places=6)
            self.assertGreater(pairs['Obstacle']['native_evidence']['observation']['intersection_mm3'], 0)
            self.assertEqual(sha256(source / ENTRY), root_hash)
            self.assertEqual(sha256(source / DEPENDENCY), obstacle_hash)

            self.worker('move', source)
            self.assertEqual(sha256(source / ENTRY), root_hash)
            self.assertNotEqual(sha256(source / DEPENDENCY), obstacle_hash)
            changed = self.campaign(configuration, work / 'changed')
            self.assertEqual(changed['closure']['source_sha256'][ENTRY], root_hash)
            self.assertNotEqual(changed['closure']['cache_key'], completed['closure']['cache_key'])
            self.assertEqual(changed['geometry']['resumed_tasks'], 0)
            self.assertEqual(changed['geometry']['pairs_examined'], 3)
            self.assertEqual(changed['geometry']['pairs_screened_out'], 2)
            self.assertEqual(changed['geometry']['status'], 'PASS')

            (source / DEPENDENCY).unlink()
            blocked = work / 'missing'
            run = execute([VALIDATOR, 'xlink', '--configuration', relative(configuration), '--output',
                           relative(blocked), '--freecad-python', FREECAD])
            self.assertEqual(run.returncode, 2, run.stdout + run.stderr)
            path = next(blocked.glob('run-*/campaign.json'))
            missing = json.loads(path.read_text(encoding='utf-8'))
            self.assertEqual(missing['verdict'], 'V21_XLINK_BLOCKED')
            self.assertEqual(missing['geometry']['status'], 'NOT_RUN')
            self.assertIn('Obstacle.FCStd', missing['phases']['stage']['reason'])
            self.assertTrue(path.with_name('t0_run_manifest.json').is_file())


if __name__ == '__main__':
    if sys.argv[1:2] == ['--worker']:
        action = sys.argv[2]
        root = Path(sys.argv[3])
        {'create': create_fixture, 'move': move_obstacle}[action](root)
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(0)
    if len(sys.argv) not in (2, 3):
        raise SystemExit('Usage: test_xlink_cli.py <validation_core> [<python-freecad>]')
    VALIDATOR = str(Path(sys.argv[1]).resolve())
    interpreter = sys.argv[2] if len(sys.argv) == 3 else os.environ.get('ELECTROMECHANICAL_FREECAD_PYTHON')
    if not interpreter:
        print('FreeCAD intégration non demandée')
        raise SystemExit(77)
    FREECAD = str(Path(interpreter).resolve())
    unittest.main(argv=[sys.argv[0]])
