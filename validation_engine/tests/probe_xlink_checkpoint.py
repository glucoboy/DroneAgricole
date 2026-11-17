"""Adversarial test that presents a forged measurement on XLink resume."""

import argparse
import hashlib
import json
from pathlib import Path

from test_xlink_cli import CABLE, DEPENDENCY, ENTRY, execute, relation, relative, sha256


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def run_test(validator, freecad, work):
    assert relative(work).startswith('.runtime/')
    work.mkdir(parents=True)
    source, output = work / 'source', work / 'campaign'
    configuration = work / 'settings.json'
    write_json(configuration, {
        'scope': 'checkpoint_integrity_test', 'source': relative(source), 'entry': ENTRY, 'native_count': 2,
        'criteria': {'requirements': ['MEC-INT-001'], 'state': 'nominal_banc', 'screening_only': False,
                     'clearance_mm': 0.5, 'distance_tolerance_mm': 0.1, 'volume_tolerance_mm3': 1e-7,
                     'route_criteria': {CABLE: {'minimum_radius_mm': 2, 'start_mm': [0, 0, 0],
                                                'end_mm': [20, 0, 0], 'start_axis': [1, 0, 0],
                                                'end_axis': [-1, 0, 0]}},
                     'contacts': [relation('functional_contact', 'Bearing'),
                                  relation('cable_in_conduit_envelope', 'ConduitEnvelope',
                                           outer_representation='occupancy_envelope')]},
    })
    commands = []

    def logged(tag, command):
        result = execute(command)
        log = work / f'{tag}.log'
        log.write_text(result.stdout + result.stderr, encoding='utf-8')
        commands.append({'command': list(map(str, command)), 'exit_code': result.returncode,
                         'log': relative(log), 'log_sha256': sha256(log)})
        return result

    worker_file = Path(__file__).with_name('test_xlink_cli.py')
    create = logged('create', [freecad, '-B', str(worker_file), '--worker', 'create', str(source)])
    assert create.returncode == 0, create.stdout + create.stderr
    originals = {name: sha256(source / name) for name in (ENTRY, DEPENDENCY)}
    args = [validator, 'xlink', '--configuration', relative(configuration), '--output', relative(output),
            '--freecad-python', freecad]

    def campaign(tag):
        existing = set(output.glob('run-*/campaign.json'))
        result = logged(tag, args)
        candidates = set(output.glob('run-*/campaign.json')) - existing
        assert len(candidates) <= 1
        return result, next(iter(candidates), None)

    def collision(report):
        return next(row for row in report['geometry']['checks'] if row['task']['kind'] == 'pair'
                    and row['task']['b'].endswith('/Obstacle'))

    initial, first_file = campaign('initial')
    assert initial.returncode == 3 and first_file
    first = load(first_file)
    first_pair = collision(first)
    first_native = first_pair['native_evidence']
    assert first['finalized'] and first['geometry']['status'] == first_pair['status'] == 'FAIL'
    assert first_native['observation']['intersection_mm3'] > 0
    key = first['closure']['cache_key']
    checkpoint = output / 'cache' / key / (first_pair['task']['id'] + '.json')
    before = checkpoint.read_bytes()
    (work / 'checkpoint-original.json').write_bytes(before)
    forged = json.loads(before)
    forged['observation'].update(status='pass', intersection_mm3=0.0, clearance_mm=5.0)
    write_json(checkpoint, forged)
    (work / 'checkpoint-forged.json').write_bytes(checkpoint.read_bytes())

    resumed, second_file = campaign('resumed')
    record = {'expected': 'Le point falsifié est refusé ou la collision est remesurée FAIL.',
              'criteria_sha256': sha256(configuration), 'closure_sha256': first['closure']['saved_sha256'],
              'originals_sha256': originals, 'initial_pair': first_pair, 'initial_geometry': first['geometry']['status'],
              'initial_report': relative(first_file), 'initial_report_sha256': sha256(first_file),
              'checkpoint_sha256_before': hashlib.sha256(before).hexdigest(),
              'checkpoint_sha256_after': sha256(work / 'checkpoint-forged.json'), 'commands': commands}
    assert all(sha256(source / name) == digest for name, digest in originals.items())
    assert all(sha256(output / 'copy' / name) == digest
               for name, digest in first['closure']['saved_sha256'].items())
    if second_file:
        second = load(second_file)
        second_pair = collision(second)
        assert second['closure']['cache_key'] == key
        record.update(resumed_report=relative(second_file), resumed_report_sha256=sha256(second_file),
                      resumed_finalized=second['finalized'], resumed_manifest=(second_file.parent / 't0_run_manifest.json').is_file(),
                      resumed_pair=second_pair, resumed_geometry=second['geometry']['status'],
                      resumed_tasks=second['geometry']['resumed_tasks'],
                      status='PASS' if second_pair['status'] == 'FAIL' else 'FAIL')
    else:
        record['status'] = 'PASS' if resumed.returncode == 1 else 'FAIL'
    write_json(work / 'result.json', record)
    return record['status'] == 'PASS'


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('validator')
    parser.add_argument('freecad')
    parser.add_argument('work', type=Path)
    args = parser.parse_args()
    raise SystemExit(0 if run_test(args.validator, args.freecad, args.work.resolve()) else 1)
