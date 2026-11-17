"""Réception du parcours L5 depuis sa CLI, dans des dossiers de banc privés."""

import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / 'convergence_manager/fixtures/campaign.json'
CONNECTOR_ISSUE = 'L3-F31-MATE-COMPATIBILITY'
NATIVE_FIXTURES = ROOT / 'convergence_manager/fixtures/native'


def load(path):
    return json.loads(path.read_bytes())


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    return path


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def command(executable, *arguments, timeout=300, env=None):
    return subprocess.run(
        [str(executable), *map(str, arguments)], cwd=ROOT, encoding='utf-8',
        errors='replace', capture_output=True, timeout=timeout, check=False, env=env,
    )


def contradictory_catalog(work, original):
    catalog = load(ROOT / original)
    question = next(item for item in catalog['questions'] if item['issue_id'] == CONNECTOR_ISSUE)
    # Transcriptions de deux fiches synthétiques de même révision, page et périmètre explicites.
    question['reference'].update(manufacturer='Fabricant synthétique', revision='A1')
    template = catalog['sources'][0]
    sources = []
    for label, measurement in (('A', True), ('B', False)):
        record = deepcopy(template)
        transcript = save(work / f'fiche-{label}.json', {
            'mpn': question['reference']['part_number'],
            'page': 7,
            'mating_compatibility': measurement,
        })
        record.update(reference=question['reference'], applicability=question['applicability'],
                      authority='MANUFACTURER')
        record['evidence'].update(
            id=f'E.L5-MANUFACTURER-{label}', artifact_path=transcript.relative_to(ROOT).as_posix(),
            sha256=sha256(transcript), locator='p. 7, /mating_compatibility', revision='A1',
            method='Transcription de fiche fabricant synthétique.',
            limits='Échantillon documentaire de test pour le banc uniquement.',
        )
        record['extraction'] = {
            'format': 'JSON_POINTER', 'value': '/mating_compatibility',
            'checks': {'/mpn': question['reference']['part_number'], '/page': 7},
        }
        sources.append(record)
    catalog['sources'] = sources
    path = save(work / 'contradictory-catalog.json', catalog)
    return path.relative_to(ROOT).as_posix(), [item['evidence']['artifact_path'] for item in sources]


class CampaignHarness(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        runtime = ROOT / '.runtime'
        runtime.mkdir(exist_ok=True)
        temporary = tempfile.TemporaryDirectory(prefix='l5-test-', dir=runtime)
        cls.addClassCleanup(temporary.cleanup)
        cls.work = Path(temporary.name)

    @classmethod
    def run_cli(cls, output, *extra, freecad=None, config=DEFAULT_CONFIG):
        freecad = freecad or OPTIONS.freecad or cls.work / 'no-freecad.exe'
        return command(
            OPTIONS.core, '--output', output, '--config', config, '--l1', OPTIONS.l1,
            '--l3', OPTIONS.l3, '--l4', OPTIONS.l4, '--python', sys.executable,
            '--freecad-python', freecad, *extra,
        )

    def assert_exit(self, process, expected):
        self.assertIn(process.returncode, expected, process.stdout + process.stderr)

    def assert_finalized(self, run, process):
        self.assert_exit(process, (0, 2, 3))
        campaign = load(run / 'campaign.json')
        self.assertEqual(campaign['verdict'], {0: 'L5_PASS', 2: 'L5_FAIL', 3: 'L5_CONDITIONAL'}[process.returncode])
        self.assertEqual(load(run / 'checkpoint.json')['state'], 'VERDICT')
        for entry in load(run / 'artifacts.json')['items']:
            self.assertEqual(sha256(run / entry['path']), entry['checksum_sha256'], entry['path'])
        if OPTIONS.evidence:
            self.assert_exit(command(OPTIONS.evidence, 'validate', run, ROOT), (0,))
        return campaign


class CampaignTests(CampaignHarness):
    def test_unavailable_freecad_has_a_bounded_verdict_without_a_promotion(self):
        run = self.work / 'unavailable'
        absent = self.work / 'no-freecad.exe'
        process = self.run_cli(run, freecad=absent)
        self.assert_exit(process, (2, 3))
        self.assert_finalized(run, process)
        checkpoint = load(run / 'checkpoint.json')
        self.assertIsNone(checkpoint['last_consolidated'])
        self.assertLessEqual(len(checkpoint['attempts']), 12)
        self.assertLessEqual(checkpoint['consolidation_used'], 2)
        self.assertIn('FreeCAD', json.dumps(checkpoint, ensure_ascii=False))

    def test_pause_cannot_publish_pass_without_an_independent_consolidation(self):
        run = self.work / 'forged-verdict'
        self.assert_exit(self.run_cli(run, '--steps', 1), (4,))
        checkpoint_path = run / 'checkpoint.json'
        checkpoint = load(checkpoint_path)
        checkpoint.update(state='VERDICT', selection={'selected': []}, outcome={
            'schema_version': 1, 'finalized': True, 'milestone': 'DIGITAL_BENCH',
            'reference_sha256': checkpoint['inventory']['reference_sha256'],
            'verdict': 'L5_PASS', 'decision': 'GO', 'reasons': [], 'consolidated': None,
            'detailed_used': 0, 'consolidation_used': 0, 'physical_go': False,
        })
        save(checkpoint_path, checkpoint)
        self.assert_exit(self.run_cli(run), (1,))
        self.assertFalse((run / 'consolidations').exists())
        self.assertFalse((run / 't0_run_manifest.json').exists())

    def test_preexisting_authority_must_match_frozen_reference_recipe(self):
        for name in ('intact', 'replaced-mechanical'):
            with self.subTest(name=name):
                run = self.work / name
                lock = run / 'authority/l4-lock.json'
                lock.parent.mkdir(parents=True)
                freecad = OPTIONS.freecad or self.work / 'no-freecad.exe'
                seal_args = ['seal', '--configuration', NATIVE_FIXTURES / 'reference.json',
                             '--lock', lock, '--python', sys.executable]
                if freecad.is_file():
                    seal_args += ['--freecad-python', freecad]
                self.assert_exit(command(OPTIONS.l4, *seal_args), (0,))
                expected = 4
                if name == 'replaced-mechanical':
                    reference = load(lock)
                    replacement = ROOT / 'validation_engine/fixtures/mechanical.json'
                    reference['files']['mechanical'] = {
                        'path': replacement.relative_to(ROOT).as_posix(), 'sha256': sha256(replacement),
                    }
                    save(lock, reference)
                    expected = 1
                self.assert_exit(self.run_cli(run, '--steps', 0, freecad=freecad), (expected,))
                self.assertEqual((run / 'manifest.json').exists(), expected == 4)

    def test_rejects_a_changed_frozen_configuration_on_resume(self):
        run = self.work / 'frozen'
        config = self.work / 'frozen-config.json'
        config.write_bytes(DEFAULT_CONFIG.read_bytes())
        process = self.run_cli(run, '--steps', 1, config=config)
        self.assert_exit(process, (4,))
        manifest = sha256(run / 'manifest.json')
        checkpoint = sha256(run / 'checkpoint.json')
        config.write_bytes(config.read_bytes() + b'\n')
        self.assert_exit(self.run_cli(run, config=config), (1,))
        self.assertEqual(sha256(run / 'manifest.json'), manifest)
        self.assertEqual(sha256(run / 'checkpoint.json'), checkpoint)


class NativeCampaignTests(CampaignHarness):
    @classmethod
    def setUpClass(cls):
        if not OPTIONS.freecad or not OPTIONS.freecad.is_file():
            raise unittest.SkipTest('FreeCAD non configuré pour la réception native')
        super().setUpClass()
        cls.nominal_dir = cls.work / 'nominal'
        cls.nominal_process = cls.run_cli(cls.nominal_dir)

    def test_complete_replay_preserves_checkpoint_history_and_results(self):
        nominal = self.assert_finalized(self.nominal_dir, self.nominal_process)
        checkpoint = load(self.nominal_dir / 'checkpoint.json')
        self.assertIsNotNone(checkpoint['last_consolidated'])
        replay = self.work / 'replay'
        self.assert_exit(self.run_cli(replay, '--steps', 8), (4,))
        manifest = (replay / 'manifest.json').read_bytes()
        before = load(replay / 'checkpoint.json')
        self.assertTrue(before['transitions'])
        self.assertEqual([item['id'] for item in before['attempts']], ['local-direct'])
        self.assertFalse((replay / 't0_run_manifest.json').exists())

        outcome = self.assert_finalized(replay, self.run_cli(replay))
        after = load(replay / 'checkpoint.json')
        self.assertEqual((replay / 'manifest.json').read_bytes(), manifest)
        self.assertEqual(after['transitions'][:len(before['transitions'])], before['transitions'])
        self.assertEqual(after['attempts'][:len(before['attempts'])], before['attempts'])
        self.assertEqual(outcome['verdict'], nominal['verdict'])
        self.assertEqual(after['selected'], checkpoint['selected'])
        self.assertEqual(after['consolidation_used'], checkpoint['consolidation_used'])
        self.assertEqual(after['transitions'], checkpoint['transitions'])
        self.assertEqual(
            [(row['id'], row['status']) for row in after['attempts']],
            [(row['id'], row['status']) for row in checkpoint['attempts']],
        )
        tolerances = {row['id']: row['tolerance'] for row in load(DEFAULT_CONFIG)['objectives']}
        for actual, expected in zip(after['attempts'], checkpoint['attempts'], strict=True):
            for metric, tolerance in tolerances.items():
                value = actual.get('metrics', {}).get(metric)
                reference = expected.get('metrics', {}).get(metric)
                if value is None or reference is None:
                    self.assertEqual(value, reference)
                else:
                    self.assertAlmostEqual(value, reference, delta=tolerance)
        settled = (replay / 'checkpoint.json').read_bytes()
        self.assert_exit(self.run_cli(replay), (self.nominal_process.returncode,))
        self.assertEqual((replay / 'checkpoint.json').read_bytes(), settled)

    def test_terminal_resume_refuses_a_modified_nested_measurement(self):
        run = self.nominal_dir
        checkpoint = load(run / 'checkpoint.json')
        last = checkpoint['last_consolidated']
        validation = run / last['validation']['report']
        l4_case = validation.parents[1] / 'native' / 'consolidated-bench'
        measurement = l4_case / 'measurement-1.json'
        self.assertTrue(measurement.is_file())
        original = measurement.read_bytes()
        measurement.write_bytes(original + b'\n')
        terminal = sha256(run / 't0_run_manifest.json')
        try:
            refused = self.run_cli(run)
            self.assert_exit(refused, (1,))
            self.assertIn('Artefact T0 invalide', refused.stderr)
            self.assertIn('measurement-1.json', refused.stderr)
            self.assertEqual(sha256(run / 't0_run_manifest.json'), terminal)
            self.assertEqual(measurement.read_bytes(), original + b'\n')
        finally:
            measurement.write_bytes(original)

    def test_resume_cannot_substitute_a_local_variant_for_the_consolidation(self):
        run = self.work / 'variant-fake-consolidation'
        self.assert_exit(self.run_cli(run, '--steps', 5), (4,))
        checkpoint_path = run / 'checkpoint.json'
        checkpoint = load(checkpoint_path)
        variant = checkpoint['built']
        self.assertTrue(variant['path'].startswith('attempts/'))
        checkpoint['detailed_used'] = 1
        candidate = {**variant, 'id': 'lateral-service', 'status': 'PASS',
                     'coverage': ['L1', 'L2'], 'validation': {}}
        checkpoint.update(state='VERDICT', selection={'selected': ['lateral-service']},
                          last_consolidated=candidate, outcome={
            'schema_version': 1, 'finalized': True, 'milestone': 'DIGITAL_BENCH',
            'reference_sha256': checkpoint['inventory']['reference_sha256'],
            'verdict': 'L5_PASS', 'decision': 'GO', 'reasons': [], 'consolidated': candidate,
            'detailed_used': 1, 'consolidation_used': 0, 'physical_go': False,
        })
        save(checkpoint_path, checkpoint)
        refused = self.run_cli(run)
        self.assert_exit(refused, (1,))
        self.assertIn('Natif consolidé absent ou divergent', refused.stderr)
        self.assertFalse((run / 't0_run_manifest.json').exists())

    def test_final_native_covers_only_the_staged_geometry_and_frozen_rules(self):
        self.assert_exit(self.nominal_process, (0,))
        checkpoint = load(self.nominal_dir / 'checkpoint.json')
        last = checkpoint['last_consolidated']
        validation = self.nominal_dir / last['validation']['report']
        self.assertEqual(validation.name, 'consolidated-bench.json')
        observation = load(validation.with_name('consolidated-bench-native-observation.json'))
        evidence = observation['native_evidence']
        report = load(validation)
        self.assertEqual(report['verdict'], 'PASS')
        self.assertEqual(report['candidate_sha256'], last['sha256'])
        self.assertEqual(report['native_sha256'], last['sha256'])
        self.assertEqual(evidence['native_sha256'], last['sha256'])
        required_checks = {check['key'] for check in load(NATIVE_FIXTURES / 'mechanical.json')['consolidated-bench']}
        self.assertEqual({finding['key'] for finding in report['findings']}, required_checks)
        self.assertTrue(all(finding['status'] == 'PASS' for finding in report['findings']))
        self.assertTrue(evidence['repeat_exact'])
        self.assertTrue(evidence['sources_unchanged'])
        self.assertEqual(len({run['worker_id'] for run in evidence['attempts']}), 2)
        self.assertEqual(set(observation['measurements']['route_metrics']), {'L1', 'L2'})
        self.assertEqual(set(last['coverage']), {'L1', 'L2'})
        self.assertEqual(sha256(self.nominal_dir / last['path']), last['sha256'])
        measured = observation['measurements']['architecture_metrics']
        for metric in load(DEFAULT_CONFIG)['objectives']:
            metric_id = metric['id']
            self.assertAlmostEqual(last['validation']['metrics'][metric_id], measured[metric_id]['value'],
                                   delta=metric['tolerance'])
            self.assertEqual(set(measured[metric_id]['scope']['route_ids']), {'L1', 'L2'})
        lock_id = report['fingerprints']['reference_sha256']
        self.assertEqual(report['fingerprints']['validator_sha256'], sha256(OPTIONS.l4))
        self.assertIn(lock_id, json.dumps(load(self.nominal_dir / 'checkpoint.json')))

    def test_individually_passing_variants_cannot_promote_an_incompatible_portfolio(self):
        checkpoint = load(self.nominal_dir / 'checkpoint.json')
        attempts = {item['id']: item for item in checkpoint['attempts']}
        for variant in ('lateral', 'upper', 'shared', 'service-direct'):
            self.assertEqual(attempts[variant]['status'], 'PASS')
        selection = load(self.nominal_dir / 'selection.json')
        portfolios = {item['id']: item for item in selection['portfolios']}
        self.assertIn('CONFLICTING_ASSIGNMENTS', json.dumps(portfolios['conflicting-routes']))
        self.assertEqual(portfolios['shared-service']['status'], 'FAIL')
        self.assertTrue(portfolios['shared-service']['rollback'])
        self.assertEqual(portfolios['upper-service']['status'], 'SKIPPED')
        self.assertEqual(portfolios['upper-service']['reason'], 'CONSOLIDATION_BUDGET_EXHAUSTED')
        self.assertNotEqual(checkpoint['last_consolidated']['id'], 'shared-service')
        self.assertNotEqual(checkpoint['last_consolidated']['id'], 'conflicting-routes')
        self.assertEqual(set(checkpoint['selected']), {'lateral', 'service-direct'})

    def test_recurrent_local_failure_changes_family_and_keeps_unproved_connector_open(self):
        self.assert_exit(self.nominal_process, (0,))
        checkpoint = load(self.nominal_dir / 'checkpoint.json')
        attempts = checkpoint['attempts']
        local = [item for item in attempts if item['id'].startswith('local-')]
        self.assertEqual([item['id'] for item in local], ['local-direct', 'local-offset-2', 'local-offset-3'])
        self.assertTrue(all(item['status'] == 'FAIL' for item in local))
        self.assertIn('CHANGE_FAMILY', checkpoint['transitions'])
        after = {item['id']: item for item in attempts}
        self.assertTrue({'connector-unknown', 'lateral', 'upper', 'service-direct'} <= after.keys())
        self.assertNotEqual(after['connector-unknown']['status'], 'PASS')
        question = checkpoint['unknowns'][CONNECTOR_ISSUE]
        self.assertEqual(question['repeat_count'], 1)
        self.assertEqual(question['variants'], ['connector-unknown', 'connector-repeat'])
        self.assertEqual(question['report']['outcome'], 'UNKNOWN')
        for field in ('searches', 'sources', 'calculations', 'next_check'):
            self.assertTrue(question[field])

    def test_geometrically_equivalent_proposals_spend_no_second_build(self):
        checkpoint = load(self.nominal_dir / 'checkpoint.json')
        attempts = {item['id']: item for item in checkpoint['attempts']}
        self.assertEqual(attempts['lateral']['status'], 'PASS')
        equivalent = attempts['lateral-equivalent']
        self.assertIn('DUPLIC', json.dumps(equivalent).upper())
        self.assertFalse(equivalent.get('path'))
        self.assertFalse(equivalent.get('metrics'))

    def test_conflicting_supplier_transcripts_leave_only_the_dependent_branch_open(self):
        run = self.work / 'contradictory'
        config = load(DEFAULT_CONFIG)
        catalog, sources = contradictory_catalog(self.work, config['research']['catalog'])
        config['research'].update(catalog=catalog, inputs=sources)
        config['issues'][CONNECTOR_ISSUE]['impact'] = 'CONDITION'
        path = save(self.work / 'contradictory-config.json', config)
        process = self.run_cli(run, config=path)
        self.assert_exit(process, (3,))
        self.assert_finalized(run, process)
        checkpoint = load(run / 'checkpoint.json')
        self.assertIsNotNone(checkpoint['last_consolidated'])
        self.assertNotIn('connector-unknown', checkpoint['selected'])
        evidence = json.dumps(checkpoint['unknowns'][CONNECTOR_ISSUE], ensure_ascii=False)
        for term in ('INCONCLUSIVE', 'E.L5-MANUFACTURER-A', 'E.L5-MANUFACTURER-B'):
            self.assertIn(term, evidence)
        checkpoint['outcome'].update(verdict='L5_PASS', decision='GO', reasons=[])
        save(run / 'checkpoint.json', checkpoint)
        terminal = sha256(run / 't0_run_manifest.json')
        refused = self.run_cli(run, config=path)
        self.assert_exit(refused, (1,))
        self.assertIn('Verdict terminal incohérent', refused.stderr)
        self.assertEqual(sha256(run / 't0_run_manifest.json'), terminal)

    def test_l4_refuses_a_broken_native_link_before_measuring(self):
        lock = self.work / 'broken-link-lock.json'
        process = command(OPTIONS.l4, 'seal', '--configuration', NATIVE_FIXTURES / 'reference.json',
                          '--lock', lock, '--freecad-python', OPTIONS.freecad, '--python', sys.executable)
        self.assert_exit(process, (0,))
        lock_sha = process.stdout.strip()
        self.assertEqual(lock_sha, sha256(lock))
        source = self.work / 'broken-link-source'
        source.mkdir()
        candidate = source / 'linked-candidate.FCStd'
        with ZipFile(candidate, 'w') as archive:
            archive.writestr('Document.xml', '<Document><XLink file="Absent.FCStd"/></Document>')
        expected_sha = sha256(candidate)
        output = self.work / 'broken-link-revalidation'
        process = command(OPTIONS.l4, 'validate', '--lock', lock, '--lock-sha256', lock_sha,
                          '--case', 'consolidated-bench', '--candidate', candidate, '--output', output,
                          '--freecad-python', OPTIONS.freecad, '--python', sys.executable)
        self.assert_exit(process, (3,))
        observation = load(output / 'cases/consolidated-bench-native-observation.json')
        self.assertEqual(observation['measurements'], {})
        self.assertIn('Absent.FCStd', observation['native_evidence']['reason'])
        self.assertEqual(sha256(candidate), expected_sha)

    def test_freecad_save_failure_is_reported_by_the_native_worker(self):
        target = self.work / 'save-failure'
        target.mkdir()
        # The worker reaches saveAs but the destination is a directory.
        blocked = target / 'candidate.FCStd'
        blocked.mkdir()
        routes = load(NATIVE_FIXTURES / 'routes.json')
        system = load(NATIVE_FIXTURES / 'system.json')
        for box in system['geometry']['boxes']:
            if box['id'] == 'Deck':
                box['size_mm'][2] = 2
        plan = {
            'system': system, 'requirements': load(NATIVE_FIXTURES / 'requirements.json'),
            'candidate': {'routes': {'L1': routes['l1-lateral'], 'L2': routes['l2-direct']}},
        }
        request = save(target / 'build.request.json', {
            'action': 'build', 'entry': blocked.name, 'plan': plan,
        })
        response = target / 'build.result.json'
        env = dict(os.environ, QT_QPA_PLATFORM='offscreen', PYTHONUTF8='1', PYTHONPATH=str(ROOT))
        process = command(OPTIONS.freecad, '-B', '-m', 'electromechanical_engine.freecad_worker',
                          request, response, env=env, timeout=45)
        self.assert_exit(process, (1,))
        result = load(response)
        self.assertFalse(result['finalized'])
        self.assertIn('saving candidate.FCStd', process.stderr)
        self.assertTrue(blocked.is_dir())


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('core', 'l1', 'l3', 'l4'):
        parser.add_argument(f'--{name}', type=Path, required=True)
    parser.add_argument('--freecad', type=Path)
    parser.add_argument('--evidence', type=Path)
    options, remaining = parser.parse_known_args()
    for name, value in vars(options).items():
        if value is not None:
            setattr(options, name, value.resolve())
    sys.argv[1:] = remaining
    return options


if __name__ == '__main__':
    OPTIONS = parse_args()
    unittest.main(verbosity=2)
