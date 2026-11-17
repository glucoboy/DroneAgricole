"""Rejeu Q4 avec dossiers de preuve persistants et contrôle L4 indépendant."""

import argparse
import json
from pathlib import Path
import sys

from test_campaign import DEFAULT_CONFIG, NATIVE_FIXTURES, ROOT, command, load, save, sha256


def relative(path):
    return path.relative_to(ROOT).as_posix()


def create_inputs(work):
    config = load(DEFAULT_CONFIG)
    config['id'] = 'v21-service-campaign'
    config['budgets']['local_corrections'] = 2
    config['budgets']['by_family']['LOCAL'] = 2
    config['candidates'] = [row for row in config['candidates'] if row['id'] != 'local-offset-3']
    config['ownership']['connector:D1'] = ['L1', 'L2']
    config['ownership']['equipment:diagnostic'] = ['L1', 'L2']
    config['budgets']['by_family']['PLACEMENT'] = 1
    config['candidates'][4:4] = [
        {'id': 'rotate-diagnostic', 'problem': 'obstacle', 'family': 'CONNECTOR',
         'assignments': {'connector:D1': '90-degrees'}},
        {'id': 'relocate-diagnostic', 'problem': 'obstacle', 'family': 'PLACEMENT',
         'assignments': {'equipment:diagnostic': 'side-panel'}},
    ]

    system = load(NATIVE_FIXTURES / 'system.json')
    system['equipment'].append({'id': 'diagnostic'})
    system['ports'].append({'id': 'D1', 'equipment': 'diagnostic', 'interface': 'SERVICE',
                            'status': 'DOCUMENTEE', 'position_mm': [55, 1.5, 10], 'tangent': [-1, 0, 0]})
    system['geometry']['boxes'][1]['size_mm'][2] = 3
    system['geometry']['extraction'].append({
        'port': 'D1', 'origin_mm': [45, -1, 9], 'size_mm': [10, 5, 2], 'ignore_ids': [],
    })
    requirements = load(NATIVE_FIXTURES / 'requirements.json')
    requirements['extraction_ports'].append('D1')
    mechanical = load(NATIVE_FIXTURES / 'mechanical.json')
    mechanical['consolidated-bench'].append({
        'key': 'diagnostic-service', 'family': 'V3', 'method': 'extraction', 'subjects': ['D1'],
        'parameters': {'clearance_mm': 1, 'volume_tolerance_mm3': 0.000001,
                       'obstacle_ids': ['Deck', 'L1', 'L2', 'Obstacle'], 'ignored_ids': []},
        'tolerance': 0.000001,
    })
    acceptance = load(NATIVE_FIXTURES / 'acceptance.json')
    acceptance['cases']['consolidated-bench']['findings']['diagnostic-service'] = 'PASS'
    reference = load(NATIVE_FIXTURES / 'reference.json')
    for name, value in [('mechanical', mechanical), ('acceptance', acceptance),
                        ('model-system', system), ('model-requirements', requirements)]:
        reference['files'][name] = relative(save(work / f'{name}.json', value))
    native = load(NATIVE_FIXTURES / 'native.json')
    native['cases']['consolidated-bench']['scope'] = 'Banc synthétique Q4, service fixe D1 et deux câbles'
    native['cases']['consolidated-bench']['frozen_model'].update(
        system=reference['files']['model-system'], requirements=reference['files']['model-requirements'],
    )
    reference['files']['native'] = relative(save(work / 'native.json', native))
    config['native'].update(system=reference['files']['model-system'],
                            requirements=reference['files']['model-requirements'],
                            reference=relative(save(work / 'reference.json', reference)))

    # L3 conserve le criblage analytique. La réception géométrique est exécutée sur le FCStd par L4.
    benches = load(ROOT / config['exploration']['benches'])
    bench = benches['benches'][0]
    bench['objective'] = 'Dégager le volume de retrait de D1.'
    bench['links'][0]['subjects'] = ['L1', 'D1']
    screening = load(ROOT / config['exploration']['requirements'])
    rule = screening['benches'][0]['rules'][0]
    rule['requirement']['subject_ids'] = ['L1', 'D1']
    rule['diagnostic']['cause'] = 'Les corrections nominales laissent L1 dans l’enveloppe de retrait D1.'
    config['exploration'].update(benches=relative(save(work / 'screening-benches.json', benches)),
                                 requirements=relative(save(work / 'screening-requirements.json', screening)))
    return save(work / 'campaign.json', config), reference, native


def main(options):
    work = options.work.resolve()
    work.mkdir(parents=True, exist_ok=False)
    config_path, reference, native = create_inputs(work)
    config = load(config_path)
    python = Path(sys.executable).resolve()
    inputs = {DEFAULT_CONFIG, *work.glob('*.json'), *NATIVE_FIXTURES.glob('*.json')}
    inputs.update(ROOT / path for path in (*reference['files'].values(), *native['source_files'],
                                          *config['exploration'].values(), *config['research']['inputs'],
                                          config['native']['routes'], config['research']['catalog']))
    inputs.update(ROOT / row['evidence']['artifact_path'] for row in load(ROOT / config['research']['catalog'])['sources'])
    inputs.update((ROOT / 'convergence_manager/fixtures/v21_h01_exploration.json',
                   ROOT / 'convergence_manager/native/build_candidate.py',
                   ROOT / 'architecture_decision_engine/fixtures/benches.json',
                   ROOT / 'architecture_decision_engine/fixtures/requirements.json',
                   ROOT / 'architecture_decision_engine/fixtures/acceptance.json',
                   ROOT / 'architecture_decision_engine/fixtures/f31_interconnection.json',
                   ROOT / 'electromechanical_engine/validation.py', Path(__file__).resolve(),
                   Path(__file__).with_name('test_campaign.py').resolve(),
                   options.core, options.l1, options.l3, options.l4, options.evidence, options.freecad, python))
    expectations = {
        'routes': {'local-direct': 'FAIL', 'local-offset-2': 'FAIL', 'lateral': 'PASS', 'upper': 'PASS',
                   'shared': 'PASS', 'service-direct': 'PASS', 'lateral-equivalent': 'DUPLICATE'},
        'local_constraint': {'key': 'diagnostic-service', 'code': 'V3.EXTRACTION', 'port': 'D1',
                             'obstacle': 'L1', 'clearance_mm': 1,
                             'positive_common_volume_above_mm3': 0.000001, 'occurrences': 2},
        'architectural_options': {'rotate-diagnostic': 'connector:D1', 'relocate-diagnostic': 'equipment:diagnostic'},
        'architectural_native_expected': 'CANDIDATE_WITH_NATIVE_VALIDATION',
        'l3_service': {'f31-over': 'FAIL', 'f31-under': 'FAIL', 'f31-lateral': 'INCONCLUSIVE',
                       'f31-shift': 'PASS', 'diag-passive': 'PASS'},
        'portfolios': {'conflicting-routes': 'REJECTED', 'shared-service': 'FAIL',
                       'lateral-service': 'PASS', 'upper-service': 'SKIPPED'},
        'budget': {'detailed_used': 6, 'consolidation_used': 2, 'pause_steps': 8},
        'final': {'verdict': 'L5_PASS', 'id': 'lateral-service', 'checks': 14, 'coverage': ['L1', 'L2'],
                  'reopen_processes': 2},
        'integrated_admission_expected': 'V21_PLAN_EXECUTED_ON_COPY',
    }
    hashes = {str(path): sha256(path) for path in sorted(inputs)}
    freeze = save(work / 'frozen-oracle.json', {'expectations': expectations, 'inputs_sha256': hashes})
    frozen_hash = sha256(freeze)
    commands = []

    def run(tag, executable, *args, expected):
        result = command(executable, *args, timeout=600)
        log = work / f'{tag}.log'
        log.write_text(result.stdout + result.stderr, encoding='utf-8')
        commands.append({'argv': [str(executable), *map(str, args)], 'exit': result.returncode,
                         'log': relative(log), 'sha256': sha256(log)})
        save(work / 'commands.json', commands)
        assert result.returncode in expected, (tag, result.returncode, log)
        return result

    lock = work / 'paused/authority/l4-lock.json'
    lock.parent.mkdir(parents=True)
    run('seal', options.l4, 'seal', '--configuration', config['native']['reference'],
        '--lock', lock, '--python', python, '--freecad-python', options.freecad, expected=(0,))
    frozen_lock = sha256(lock)
    uninterrupted_lock = work / 'uninterrupted/authority/l4-lock.json'
    uninterrupted_lock.parent.mkdir(parents=True)
    uninterrupted_lock.write_bytes(lock.read_bytes())
    assert sha256(uninterrupted_lock) == frozen_lock

    def campaign(tag, directory, *extra, expected):
        return run(tag, options.core, 'run', '--output', directory, '--config', config_path, '--l1', options.l1,
                   '--l3', options.l3, '--l4', options.l4, '--python', python,
                   '--freecad-python', options.freecad, *extra, expected=expected)

    run('l3-service', options.l3, '--l1', options.l1, '--output', work / 'l3-service', expected=(0,))
    run('l3-t0', options.evidence, 'validate', work / 'l3-service', ROOT, expected=(0,))
    paused = work / 'paused'
    campaign('pause', paused, '--steps', expectations['budget']['pause_steps'], expected=(4,))
    before = load(paused / 'checkpoint.json')
    before_manifest = sha256(paused / 'manifest.json')
    assert not (paused / 't0_run_manifest.json').exists()
    save(work / 'pause-checkpoint.json', before)
    campaign('resume', paused, expected=(0,))
    uninterrupted = work / 'uninterrupted'
    campaign('uninterrupted', uninterrupted, expected=(0,))
    checkpoints = {}
    for directory in (paused, uninterrupted):
        run(f't0-{directory.name}', options.evidence, 'validate', directory, ROOT, expected=(0,))
        checkpoints[directory.name] = load(directory / 'checkpoint.json')
    after = checkpoints['paused']
    assert after['transitions'][:len(before['transitions'])] == before['transitions']
    assert after['attempts'][:len(before['attempts'])] == before['attempts']
    assert sha256(paused / 'manifest.json') == before_manifest
    assert sha256(lock) == sha256(uninterrupted_lock) == frozen_lock
    first_manifest, second_manifest = (load(directory / 'manifest.json') for directory in (paused, uninterrupted))
    assert first_manifest.pop('reference_lock') == relative(lock)
    assert second_manifest.pop('reference_lock') == relative(uninterrupted_lock)
    assert first_manifest == second_manifest
    assert after['transitions'] == checkpoints['uninterrupted']['transitions']
    for key in ('detailed_used', 'consolidation_used'):
        assert after[key] == checkpoints['uninterrupted'][key] == expectations['budget'][key]
    assert after['state'] == 'VERDICT'
    assert [(row['id'], row['status']) for row in after['attempts']] == [
        (row['id'], row['status']) for row in checkpoints['uninterrupted']['attempts']
    ]

    attempts = {row['id']: row for row in after['attempts']}
    observed = {}
    for ident, status in expectations['routes'].items():
        actual = attempts[ident]
        assert actual['status'] == status, actual
        observed[ident] = {'status': status, 'metrics': actual.get('metrics'), 'build_receipt': actual.get('receipt'),
                           'build_receipt_sha256': actual.get('receipt_sha256'), 'native_sha256': actual.get('sha256')}
    assert 'CHANGE_FAMILY' in after['transitions']
    scope = expectations['local_constraint']
    problem = after['problem_state']['obstacle']
    assert problem['escalation_reason'] == 'REPEATED_CONSTRAINT', problem
    conflict = next(row for row in problem['conflicts'] if row['code'] == scope['code'])
    assert conflict['occurrences'] == scope['occurrences']

    def revalidate(tag, candidate, candidate_id, expected):
        directory = work / tag
        run(tag, options.l4, 'validate', '--lock', lock, '--lock-sha256', sha256(lock),
            '--case', 'consolidated-bench', '--candidate', candidate, '--candidate-id', candidate_id,
            '--output', directory, '--python', python, '--freecad-python', options.freecad, expected=(expected,))
        run(f'{tag}-t0', options.evidence, 'validate', directory, ROOT, expected=(0,))
        return directory / 'cases/consolidated-bench.json'

    for ident in ('local-direct', 'local-offset-2'):
        failures = [row for row in attempts[ident]['findings'] if row['status'] == 'FAIL']
        assert [(row['code'], row['subjects']) for row in failures] == [(scope['code'], [scope['port']])]
        candidate = paused / attempts[ident]['path']
        expected_sha = attempts[ident]['sha256']
        report_path = revalidate(f'independent-{ident}', candidate, ident, 2)
        report = load(report_path)
        assert report['candidate_sha256'] == report['native_sha256'] == sha256(candidate) == expected_sha
        failed = [row for row in report['findings'] if row['status'] == 'FAIL']
        assert [row['key'] for row in failed] == [scope['key']]
        local_native = load(report_path.with_name('consolidated-bench-native-observation.json'))['measurements']
        service = local_native['extraction_evidence'][scope['port']]
        obstacle = next(row for row in service['measurements'] if row['b'] == scope['obstacle'])
        assert obstacle['intersection_mm3'] > scope['positive_common_volume_above_mm3']
        assert obstacle['clearance_mm'] < scope['clearance_mm']
        observed[ident].update(service_finding=failed[0], service_measurement=obstacle,
                               l4_report=relative(report_path), l4_report_sha256=sha256(report_path))

    architecture = {ident: attempts[ident] for ident in expectations['architectural_options']}
    portfolios = {row['id']: row for row in after['portfolios']}
    assert {ident: row['status'] for ident, row in portfolios.items()} == expectations['portfolios']
    assert 'CONFLICTING_ASSIGNMENTS' in json.dumps(portfolios['conflicting-routes'])
    assert portfolios['shared-service']['rollback'] is True
    assert portfolios['upper-service']['reason'] == 'CONSOLIDATION_BUDGET_EXHAUSTED'

    winner = after['last_consolidated']
    expected = expectations['final']
    assert winner['id'] == expected['id'] and winner['coverage'] == expected['coverage']
    assert after['outcome']['verdict'] == expected['verdict']
    assert not after['outcome']['physical_go']
    candidate = paused / winner['path']
    candidate_sha = sha256(candidate)
    report_path = revalidate('independent', candidate, winner['id'], 0)
    observation = load(report_path.with_name('consolidated-bench-native-observation.json'))
    report = load(report_path)
    assert report['verdict'] == 'PASS' and len(report['findings']) == expected['checks']
    assert {finding['status'] for finding in report['findings']} == {'PASS'}
    assert report['candidate_sha256'] == report['native_sha256'] == candidate_sha == winner['sha256'] == sha256(candidate)
    native_evidence = observation['native_evidence']
    assert len({row['worker_id'] for row in native_evidence['attempts']}) == expected['reopen_processes']
    assert native_evidence['repeat_exact'] and native_evidence['sources_unchanged'] and native_evidence['copies_unchanged']
    other = checkpoints['uninterrupted']['last_consolidated']
    for metric in config['objectives']:
        key = metric['id']
        assert abs(other['metrics'][key] - winner['metrics'][key]) <= metric['tolerance']
        assert abs(observation['measurements']['architecture_metrics'][key]['value'] - winner['metrics'][key]) <= metric['tolerance']

    l3_path = work / 'l3-service/candidates'
    l3_results = {key: load(l3_path / f'{key}.json') for key in expectations['l3_service']}
    assert {key: row['status'] for key, row in l3_results.items()} == expectations['l3_service']
    settled = sha256(paused / 'checkpoint.json')
    campaign('settled-replay', paused, expected=(0,))
    assert sha256(paused / 'checkpoint.json') == settled
    admission = run('admission-to-run', options.core, 'run', '--plan',
                    ROOT / 'convergence_manager/fixtures/v21_h01_exploration.json',
                    '--output', work / 'admitted', expected=(0, 1, 2, 3))
    assert sha256(freeze) == frozen_hash
    assert {path: sha256(Path(path)) for path in hashes} == hashes

    result = {'frozen_oracle': {'path': relative(freeze), 'sha256': frozen_hash},
              'routes': observed, 'local_constraint': conflict, 'architectural_options': architecture,
              'l3_service': {key: {'status': row['status'], 'path': relative(l3_path / f'{key}.json'),
                                  'sha256': sha256(l3_path / f'{key}.json')} for key, row in l3_results.items()},
              'portfolios': portfolios, 'winner': winner, 'verdict': after['outcome']['verdict'],
              'pause': {'details_before': before['detailed_used'], 'consolidations_before': before['consolidation_used'],
                        'details_after': after['detailed_used'], 'consolidations_after': after['consolidation_used'],
                        'same_frozen_manifest': before_manifest, 'shared_lock_sha256': frozen_lock,
                        'replay_unchanged': True},
              'independent': {'report': relative(report_path), 'report_sha256': sha256(report_path),
                              'worker_ids': [row['worker_id'] for row in native_evidence['attempts']]},
              'native_architectural_option_test': 'PASS' if any(row['status'] == 'PASS' and row.get('path')
                                                                 for row in architecture.values()) else 'FAIL',
              'admission_to_builder_test': 'PASS' if admission.returncode == 0 and (work / 'admitted/t0_run_manifest.json').exists()
              else 'FAIL', 'admission_to_builder_exit': admission.returncode,
              'commands': commands}
    save(work / 'q4-results.json', result)
    print(f'V2.1 Q4: {result["verdict"]}, résolution native de l’architecture {result["native_architectural_option_test"]}, '
          f'liaison admission-construction {result["admission_to_builder_test"]}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('work', 'core', 'l1', 'l3', 'l4', 'freecad', 'evidence'):
        parser.add_argument(f'--{name}', type=lambda value: Path(value).resolve(), required=True)
    main(parser.parse_args())
