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


def move_root_obstacle(source):
    from electromechanical_engine.freecad_worker import App, cables_environment

    cables_environment(gui=False)
    doc = App.openDocument(str(source / ENTRY))
    doc.getObject('Far').Placement.Base = App.Vector(12, -0.5, -1)
    doc.recompute()
    doc.save()


def relative(path):
    return path.resolve().relative_to(PROJECT).as_posix()


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def relation(kind, outer, **details):
    return {'kind': kind, 'inner_id': CABLE, 'outer_id': ENTRY + '#Root/' + outer,
            'justification': 'Géométrie et relation définies pour le banc synthétique', **details}


def execute(command, timeout=90, environment=None):
    env = dict(os.environ, PYTHONPATH=str(PROJECT), PYTHONUTF8='1', QT_QPA_PLATFORM='offscreen')
    env.update(environment or {})
    return subprocess.run(command, cwd=PROJECT, capture_output=True, text=True, encoding='utf-8',
                          errors='replace', timeout=timeout, check=False, env=env)


class XLinkCliTest(unittest.TestCase):
    def worker(self, action, source):
        run = execute([FREECAD, '-B', str(Path(__file__).resolve()), '--worker', action, str(source)], timeout=40)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)

    def campaign(self, configuration, output, *options, environment=None):
        existing = set(output.glob('run-*/campaign.json'))
        run = execute([VALIDATOR, 'xlink', '--configuration', relative(configuration), '--output', relative(output),
                       '--freecad-python', FREECAD, *options], environment=environment)
        self.assertEqual(run.returncode, 3, run.stdout + run.stderr)
        candidates = set(output.glob('run-*/campaign.json')) - existing
        self.assertEqual(len(candidates), 1, run.stdout + run.stderr)
        report_file = candidates.pop()
        self.assertTrue(report_file.with_name('t0_run_manifest.json').is_file())
        report = json.loads(report_file.read_text(encoding='utf-8'))
        checkpoint = report_file.with_name('checkpoint.json')
        self.last_checkpoint = next(line.split(' ', 2)[1:] for line in run.stderr.splitlines()
                                    if line.startswith('XLINK_CHECKPOINT '))
        self.assertEqual(self.last_checkpoint, [sha256(checkpoint), relative(checkpoint)])
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

            partial = self.campaign(configuration, first, '--max-native-tasks', '2', '--native-batch-size', '1')
            partial_pin, partial_checkpoint = self.last_checkpoint
            self.assertEqual(len(partial['phases']['batches']), 2)
            self.assertEqual(partial['geometry']['pairs_not_run_by_reason'], {'BUDGET_TASKS': 3})
            partial_checks = partial['geometry']['checks']
            published = {row['task']['id']: row['native_evidence'] for row in partial_checks if row['native_evidence']}
            self.assertEqual(len(published), 2)
            completed = self.campaign(configuration, first)
            complete_pin, complete_checkpoint = self.last_checkpoint
            self.assertEqual(completed['closure']['cache_key'], interrupted['closure']['cache_key'])
            self.assertEqual(completed['geometry']['resumed_tasks'], 0)
            self.assertEqual(completed['phases']['cache']['policy'], 'REMEASURE')
            self.assertEqual(completed['phases']['cache']['diagnostic_files_ignored'], 2)
            self.assertNotEqual(completed['phases']['batch']['worker_id'], partial['phases']['batch']['worker_id'])
            self.assertEqual(completed['geometry']['pairs_examined'], 4)
            self.assertEqual(completed['geometry']['pairs_not_run'], 0)
            self.assertEqual(completed['geometry']['pairs_screened_out'], 1)
            self.assertEqual(completed['geometry']['status'], 'FAIL')
            for row in completed['geometry']['checks']:
                if row['task']['id'] in published:
                    fresh = row['native_evidence']
                    prior = published[row['task']['id']]
                    self.assertEqual(fresh['observation'], prior['observation'])

            pairs = {row['task']['b'].rsplit('/', 1)[1]: row for row in completed['geometry']['checks']
                     if row['task']['kind'] == 'pair'}
            self.assertEqual({name: row['status'] for name, row in pairs.items()},
                             {'Bearing': 'PASS', 'ConduitEnvelope': 'PASS', 'Near': 'PASS', 'Obstacle': 'FAIL'})
            self.assertTrue(pairs['Bearing']['native_evidence']['observation']['authorized_relation'])
            self.assertTrue(pairs['ConduitEnvelope']['native_evidence']['observation']['authorized_relation'])
            self.assertAlmostEqual(pairs['Near']['native_evidence']['observation']['clearance_mm'], 0.55, places=6)
            self.assertGreater(pairs['Obstacle']['native_evidence']['observation']['intersection_mm3'], 0)
            self.assertEqual(completed['geometry']['pairs_forbidden_intersections'], 1)
            self.assertEqual(completed['geometry']['pairs_authorized_contacts'], 2)
            proof = first / completed['attempt'] / 'aabb_exclusions.json'
            exclusions = json.loads(proof.read_text(encoding='utf-8'))
            self.assertEqual(exclusions['cutoff_mm'], 0.6)
            self.assertEqual(len(exclusions['exclusions']), 1)
            cable, other, lower_gap = exclusions['exclusions'][0]
            self.assertEqual(cable, CABLE)
            self.assertTrue(other.endswith('/Far'))
            self.assertGreater(lower_gap, exclusions['cutoff_mm'])
            self.assertEqual(sha256(source / ENTRY), root_hash)
            self.assertEqual(sha256(source / DEPENDENCY), obstacle_hash)

            timed_out = self.campaign(configuration, first, '--batch-timeout-ms', '1')
            self.assertTrue(timed_out['phases']['batch']['timed_out'])
            self.assertEqual(timed_out['phases']['cache']['diagnostic_files_ignored'], len(completed['geometry']['checks']))
            self.assertTrue(all(row['status'] == 'NOT_RUN' and row['native_evidence'] is None
                                for row in timed_out['geometry']['checks']))
            self.assertEqual(timed_out['geometry']['pairs_not_run_by_reason'], {'NATIVE_TIMEOUT': 4})

            resumed = self.campaign(configuration, first, '--checkpoint', partial_checkpoint,
                                    '--checkpoint-sha256', partial_pin, '--native-batch-size', '2')
            self.assertEqual(resumed['geometry']['resumed_tasks'], 2)
            self.assertEqual(resumed['phases']['cache']['policy'], 'PINNED_CHECKPOINT')
            self.assertEqual(resumed['checkpoint']['previous_sha256'], partial_pin)
            normalize = lambda report: {row['task']['id']: (row['status'], row['native_evidence']['observation'])
                                        for row in report['geometry']['checks']}
            self.assertEqual(normalize(completed), normalize(resumed))

            checkpoint = PROJECT / complete_checkpoint
            original = checkpoint.read_bytes()
            forged = json.loads(original)
            target = forged['observations'][pairs['Obstacle']['task']['id']]['observation']
            target.update(status='pass', intersection_volume_mm3=0, intersection_mm3=0, clearance_mm=5, failures=[])
            checkpoint.write_text(json.dumps(forged), encoding='utf-8')
            run = execute([VALIDATOR, 'xlink', '--configuration', relative(configuration), '--output', relative(first),
                           '--freecad-python', FREECAD, '--checkpoint', complete_checkpoint,
                           '--checkpoint-sha256', complete_pin])
            self.assertEqual(run.returncode, 1, run.stdout + run.stderr)
            self.assertIn('Point de reprise ou empreinte divergente', run.stderr)
            self.assertNotIn('XLINK_CHECKPOINT', run.stderr)
            checkpoint.write_bytes(original)

            # Inject a crash in the measuring process after it writes an imitation
            # result to the campaign directory. The pipe never supplied a result.
            (work / 'sitecustomize.py').write_text('''
import json
import os
from pathlib import Path
import sys

output = Path(sys.orig_argv[-1])
if output.name == 'batch.result.json':
    if os.environ.get('XLINK_TEST_ALTER_REQUEST'):
        request = Path(sys.orig_argv[-2])
        data = json.loads(request.read_bytes())
        data['criteria']['volume_tolerance_mm3'] = 1000
        request.write_text(json.dumps(data), encoding='utf-8')
    elif os.environ.get('XLINK_TEST_CRASH'):
        output.write_text(json.dumps({'finalized': True, 'observations': [{'observation': {'status': 'pass'}}]}))
        print('Injected crash after writing an imitation result', flush=True)
        os._exit(23)
if output.name == 'verify.result.json' and os.environ.get('XLINK_TEST_ALTER_PROOF'):
    proof = output.with_name('batch.result.json')
    data = json.loads(proof.read_bytes())
    collision = next(row for row in data['observations'] if row['task'].get('b', '').endswith('/Obstacle'))
    collision['observation'].update(status='pass', intersection_mm3=0, clearance_mm=5)
    proof.write_text(json.dumps(data), encoding='utf-8')
''', encoding='utf-8')
            crashed = self.campaign(configuration, first, environment={'PYTHONPATH': str(work), 'XLINK_TEST_CRASH': '1'})
            self.assertFalse(crashed['phases']['batch']['finalized'])
            self.assertFalse(crashed['phases']['batch']['timed_out'])
            self.assertIn('sans résultat', crashed['phases']['batch']['reason'])
            self.assertTrue(all(row['status'] == 'NOT_RUN' and row['native_evidence'] is None
                                for row in crashed['geometry']['checks']))
            crash_attempt = first / crashed['attempt']
            self.assertIn('Injected crash', (crash_attempt / 'batch.log').read_text(encoding='utf-8'))
            self.assertTrue((crash_attempt / 'batch.result.json').is_file())
            self.assertNotIn('batch.result.json', (crash_attempt / 'artifacts.json').read_text(encoding='utf-8'))

            recovered = self.campaign(configuration, first, '--max-native-retries', '2',
                                      environment={'PYTHONPATH': str(work), 'XLINK_TEST_CRASH': '1'})
            self.assertFalse(recovered['phases']['batches'][0]['finalized'])
            self.assertTrue(all(lot['finalized'] for lot in recovered['phases']['batches'][1:]))
            self.assertEqual(normalize(completed), normalize(recovered))

            altered = self.campaign(configuration, first, environment={'PYTHONPATH': str(work),
                                                                      'XLINK_TEST_ALTER_REQUEST': '1'})
            self.assertFalse(altered['phases']['batch']['finalized'])
            self.assertIn('Empreinte de la requête native divergente', altered['phases']['batch']['reason'])
            self.assertTrue(all(row['status'] == 'NOT_RUN' and row['native_evidence'] is None
                                for row in altered['geometry']['checks']))
            altered_attempt = first / altered['attempt']
            self.assertNotIn('batch.request.json', (altered_attempt / 'artifacts.json').read_text(encoding='utf-8'))

            altered_proof = work / 'altered-proof'
            run = execute([VALIDATOR, 'xlink', '--configuration', relative(configuration), '--output', relative(altered_proof),
                           '--freecad-python', FREECAD], environment={'PYTHONPATH': str(work), 'XLINK_TEST_ALTER_PROOF': '1'})
            self.assertEqual(run.returncode, 1, run.stdout + run.stderr)
            self.assertIn('Artefact invalide ou modifié : batch.result.json', run.stderr)
            self.assertEqual(list(altered_proof.glob('run-*/t0_run_manifest.json')), [])

            copy_root = first / 'copy'
            saved_record = first / 'saved.json'
            saved_bytes = saved_record.read_bytes()
            finalized_before = set(first.glob('run-*/t0_run_manifest.json'))
            for filename, mutation, rejection in (
                (DEPENDENCY, 'move', 'Dépendance privée modifiée'),
                (ENTRY, 'move-root', 'Racine privée divergente d’une sauvegarde indépendante'),
            ):
                native = copy_root / filename
                native_bytes = native.read_bytes()
                self.worker(mutation, copy_root)
                forged = json.loads(saved_bytes)
                forged['after_sha256'][filename] = sha256(native)
                saved_record.write_text(json.dumps(forged), encoding='utf-8')
                run = execute([VALIDATOR, 'xlink', '--configuration', relative(configuration), '--output', relative(first),
                               '--freecad-python', FREECAD])
                self.assertEqual(run.returncode, 1, run.stdout + run.stderr)
                self.assertIn(rejection, run.stderr)
                self.assertEqual(set(first.glob('run-*/t0_run_manifest.json')), finalized_before)
                native.write_bytes(native_bytes)
                saved_record.write_bytes(saved_bytes)

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
            changed_proof = work / 'changed' / changed['attempt'] / 'aabb_exclusions.json'
            self.assertTrue(any(row[1].endswith('/Obstacle') for row in
                                json.loads(changed_proof.read_text(encoding='utf-8'))['exclusions']))

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

    def test_frozen_checkpoint_forgery(self):
        from probe_xlink_checkpoint import run_test

        runtime = PROJECT / '.runtime'
        runtime.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='v21-xlink-forged-', dir=runtime) as temporary:
            work = Path(temporary) / 'probe'
            self.assertTrue(run_test(VALIDATOR, FREECAD, work))
            result = json.loads((work / 'result.json').read_text(encoding='utf-8'))
            self.assertAlmostEqual(result['initial_pair']['native_evidence']['observation']['intersection_mm3'],
                                   7.652891819924148, places=6)
            self.assertAlmostEqual(result['resumed_pair']['native_evidence']['observation']['intersection_mm3'],
                                   7.652891819924148, places=6)
            self.assertEqual(result['resumed_tasks'], 0)


if __name__ == '__main__':
    if sys.argv[1:2] == ['--worker']:
        action = sys.argv[2]
        root = Path(sys.argv[3])
        {'create': create_fixture, 'move': move_obstacle, 'move-root': move_root_obstacle}[action](root)
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
