"""Freeze and replay the independent V2.1 Q2 acceptance cases on copies."""

import argparse
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / 'interconnection_engine/examples/banc_l2.json'
BENCH = ROOT / 'hardware/mecanique/banc_interconnexion'
ADAPTER = BENCH / 'verification/freecad_adapter.py'
BUILDER = ROOT / 'hardware/mecanique/cartographe/verification/cable_workbench_prototype.py'
ARCHIVED_NATIVE = BENCH / 'assemblages/Banc_Interconnexion.FCStd'
RETURN_CODES = {'PASS': 0, 'FAIL': 2, 'INCONCLUSIVE': 3}


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write(path, data):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def relative(path):
    return path.resolve().relative_to(ROOT).as_posix()


def select(records, identifier):
    return next(record for record in records if record['id'] == identifier)


def bench_with_bodies():
    bench = read(FIXTURE)
    frames = bench['model']['frames']
    for spec in bench['interfaces']:
        end = spec['end_id']
        mating = select(frames, f'mating-{end}')
        identity = [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]
        frames.extend([
            dict(mating, id=f'receptacle-{end}'),
            dict(mating, id=f'plug-{end}', parent_frame_id=f'mate-{end}-frame', parent_from_local=identity),
        ])
        mating['parent_frame_id'] = f'receptacle-{end}'
        mating['parent_from_local'] = identity
        select(frames, f'exit-{end}')['parent_frame_id'] = f'plug-{end}'
        proof_value = spec['requirements']['current_A']

        def envelope(bounds):
            return {'geometry_class': 'CONSERVATIVE_ENVELOPE',
                    'dimensions': dict(proof_value, value=bounds, unit='mm')}

        spec['receptacle_pinout'] = dict(proof_value, unit='1', value={str(i): str(i) for i in range(1, 5)})
        spec['physical_geometry'] = {
            'receptacle_frame_id': f'receptacle-{end}', 'plug_frame_id': f'plug-{end}',
            'receptacle_body': envelope([-3, -3, -4, 3, 3, 0]),
            'plug_body': envelope([-3, -3, 0, 3, 3, 10]),
            'extraction_sweep': dict(envelope([-4, -4, 0, 4, 4, 18]),
                                     travel=dict(proof_value, value=8, unit='mm')),
            'tool_access_envelope': dict(envelope([-5, -5, 0, 5, 5, 12]),
                                         lock_access_point=dict(proof_value, value=[0, 3, 5], unit='mm')),
        }
    return bench


def freeze(plan_path, binary):
    bench = bench_with_bodies()
    fixtures = plan_path.parent / 'fixtures'
    fixtures.mkdir()
    records = bench['model']['records']
    frames = bench['model']['frames']
    first = bench['interfaces'][0]
    geometry = first['physical_geometry']
    parts = bench['catalog']['parts']
    cases = {}

    def case(name, expected, checks, dossier=bench):
        path = fixtures / f'{name}.json'
        write(path, dossier)
        cases[name] = {'input': relative(path), 'input_sha256': digest(path),
                       'accepted_results': expected, 'required_findings': checks}

    case('nominal', ['PASS'], [
        ['PIN_MAPPING', None, ['PASS']], ['PHYSICAL_PIN_NUMBER', 'ra1', ['PASS']],
        ['EXPLICIT_MATE', 'interface-a', ['PASS']], ['keying', 'interface-a', ['PASS']],
        ['MATING_ORIENTATION', 'interface-a', ['PASS']], ['WIRE_EXIT', 'cordon/a', ['PASS']],
        ['MATED_PLUG', 'interface-a', ['PASS']], ['MATED_RECEPTACLE', 'interface-a', ['PASS']],
        ['EXTRACTION_ENVELOPE', 'interface-a', ['PASS']], ['EXTRACTION_SWEEP', 'interface-a', ['PASS']],
    ])

    port = select(records['ports'], 'port-a')
    receptacle = select(records['connector_receptacles'], 'receptacle-a')
    port['id'], receptacle['port_id'], first['required_port_id'] = 'GPS2', 'GPS2', 'TELEM1'
    for pin in records['pins']:
        if pin['port_id'] == 'port-a':
            pin['port_id'] = 'GPS2'
    case('f12-bad-port', ['FAIL'], [['WRONG_PORT', 'interface-a', ['FAIL']]])
    port['id'], receptacle['port_id'], first['required_port_id'] = 'port-a', 'port-a', 'port-a'
    for pin in records['pins']:
        if pin['port_id'] == 'GPS2':
            pin['port_id'] = 'port-a'

    a, b = [item['terminal_ids'] for item in records['cables'][0]['conductors'][:2]]
    a[1], b[1] = b[1], a[1]
    case('swapped-conductors', ['FAIL'], [['PIN_MAPPING', None, ['FAIL']]])
    a[1], b[1] = b[1], a[1]

    first['mate_part_id'] = 'fiche-autre-cle'
    case('bad-key', ['FAIL'], [['keying', 'interface-a', ['FAIL']]])
    first['mate_part_id'] = 'fiche'

    points = records['routes'][0]['points_mm']
    points[0] = [14, 0, 1]
    case('unmatched-exit', ['FAIL'], [['WIRE_EXIT', 'cordon/a', ['FAIL']]])
    exit_pose = select(frames, 'exit-a')['parent_from_local']
    exit_pose[2][3] = 7
    points[0] = [11, 0, 0]
    length = bench['cable_parts']['cordon']['specifications']['length_mm']
    old_length, length['value'] = length['value'], 75
    case('matched-fictional-exit', ['FAIL', 'INCONCLUSIVE'], [])
    points[0], exit_pose[2][3], length['value'] = [14, 0, 0], 10, old_length

    obstacles = bench['geometry']['obstacles']
    obstacles.append({'id': 'withdrawal-only', 'box_mm': [20, -1, -1, 21, 1, 1]})
    case('blocked-withdrawal', ['FAIL'], [['EXTRACTION_ENVELOPE', 'interface-a', ['FAIL']],
                                         ['MATED_PLUG', 'interface-a', ['PASS']]])
    obstacles.pop()

    plug_reference = select(parts, 'fiche')['reference']
    old_evidence, plug_reference['evidence_ids'] = plug_reference['evidence_ids'], []
    case('unverified-mpn', ['INCONCLUSIVE'], [['PART_PROVENANCE', 'interface-a', ['INCONCLUSIVE']]])
    plug_reference['evidence_ids'] = old_evidence

    equipment = select(records['equipment'], 'device-a')['item_reference']
    old_revision, equipment['revision'] = equipment['revision'], 'lot-hardware-contradictoire'
    case('hardware-revision-conflict', ['FAIL', 'INCONCLUSIVE'], [['PORT_IDENTITY', 'interface-a', ['FAIL', 'INCONCLUSIVE']]])
    equipment['revision'] = old_revision

    removed = select(records['contacts'], 'ma1')
    records['contacts'].remove(removed)
    case('missing-contact', ['FAIL', 'INCONCLUSIVE'], [['CONTACT_MAPPING', 'ra1', ['FAIL', 'INCONCLUSIVE']]])
    records['contacts'].append(removed)

    geometry['plug_body']['geometry_class'] = 'APPROXIMATION'
    case('approximate-model', ['INCONCLUSIVE'], [['MATED_PLUG', 'interface-a', ['INCONCLUSIVE']]])
    geometry['plug_body']['geometry_class'] = 'CONSERVATIVE_ENVELOPE'

    spoof = copy.deepcopy(bench)
    spoof['mode'] = 'PROTOTYPE_CANDIDATE'
    spoof['model']['scope'] = 'CARTOGRAPHE'
    spoof['model']['records']['technical_evidence'][0].update(
        kind='SOURCE', domain='DOCUMENT', hypothetical=False,
        artifact_path=relative(ARCHIVED_NATIVE), sha256=digest(ARCHIVED_NATIVE),
        locator='Natif CAO synthétique réétiqueté en document fournisseur pour le test',
    )
    for identifier in ('embase', 'fiche'):
        part = select(spoof['catalog']['parts'], identifier)
        part['origin'] = 'SUPPLIER'
        part['reference']['status'] = 'SOURCED'
    case('cad-as-supplier-proof', ['INCONCLUSIVE'], [['PART_PROVENANCE', 'interface-a', ['INCONCLUSIVE']]], spoof)

    sources = [FIXTURE, ARCHIVED_NATIVE, ADAPTER, BUILDER, Path(__file__), binary]
    sources.extend(sorted((ROOT / 'interconnection_engine/src').glob('*.*')))
    write(plan_path, {
        'schema': 'drone-agricole.v21.q2.oracles.v1',
        'inputs_sha256': {relative(path): digest(path) for path in sources},
        'cases': cases,
        'oracle_native': {
            'card_count': 2, 'receptacle_count': 2, 'plug_count': 2, 'contact_pairs': 8, 'conductors': 4,
            'position_tolerance_mm': 1e-6, 'volume_tolerance_mm3': 1e-6,
            'ports': {'a': 'port-a', 'b': 'port-b'},
            'continuity': [[f'pa{i}', f'pb{i}'] for i in range(1, 5)],
            'exits_mm': {'a': [14, 0, 0], 'b': [86, 0, 0]},
            'retraction_travel_mm': 8,
            'unobstructed_retraction': 'PASS', 'obstructed_retraction': 'FAIL',
            'obstruction_volume_mm3': 1, 'generic_terminal': 'FAIL',
            'fictional_exit_from_independent_baseline_mm': [11, 0, 0],
        },
    })


def status_for(findings, code, subject):
    return sorted({finding['status'] for finding in findings
                   if finding['code'] == code and (subject is None or finding['subject_id'] == subject)})


def native_summary(native, oracle):
    build, reopen = (native['phases'][phase] for phase in ('build', 'reopen'))
    interfaces = sorted(reopen['interfaces'], key=lambda item: item['end_id'])
    faults = reopen['faults']
    interfaces_summary = []
    for item in interfaces:
        pose = item['frames']['exit']['matrix']
        interfaces_summary.append({
            'end': item['end_id'], 'port': item['port_id'], 'exit_mm': [pose[i] for i in (3, 7, 11)],
            'contact_pair_count': len(item['contacts']),
            'max_contact_gap_mm': max(pair['gap_mm'] for pair in item['contacts']),
            'pull_status': item['pull_envelope']['status'],
            'extraction_status': item['extraction']['status'],
        })
    tol = oracle['position_tolerance_mm']
    observed = {
        'tolerances': native['tolerances'], 'pids': {phase: native['phases'][phase]['pid'] for phase in ('build', 'reopen')},
        'fcstd_sha256': reopen['fcstd_sha256'], 'interfaces': interfaces_summary,
        'conductors': len(reopen['conductors']),
        'card_count': len({item['device'] for item in interfaces}),
        'receptacle_count': len({item['receptacle'] for item in interfaces}),
        'plug_count': len({item['plug'] for item in interfaces}),
        'contact_pairs': sum(item['contact_pair_count'] for item in interfaces_summary),
        'obstructed_retraction': faults['extraction_blocked']['status'],
        'obstruction_volume_mm3': sum(pair['volume_mm3'] for pair in faults['extraction_blocked']['pairs']),
        'generic_terminal': faults['generic_endpoint_same_position']['status'],
        'generic_terminal_endpoint_errors_mm': faults['generic_endpoint_same_position']['endpoint_errors_mm'],
        'provenance_same_native': build['fcstd_sha256'] == reopen['fcstd_sha256'] and build['pid'] != reopen['pid'],
    }
    observed['oracle_match'] = (
        observed['provenance_same_native']
        and all(observed[key] == oracle[key] for key in ('card_count', 'receptacle_count', 'plug_count', 'contact_pairs',
                                                        'conductors', 'obstructed_retraction', 'generic_terminal'))
        and abs(observed['obstruction_volume_mm3'] - oracle['obstruction_volume_mm3']) <= oracle['volume_tolerance_mm3']
        and max(observed['generic_terminal_endpoint_errors_mm']) <= tol
        and all(item['port'] == oracle['ports'][item['end']] and
                all(abs(a - b) <= tol for a, b in zip(item['exit_mm'], oracle['exits_mm'][item['end']], strict=True)) and
                item['max_contact_gap_mm'] <= tol and item['pull_status'] == item['extraction_status'] ==
                oracle['unobstructed_retraction'] for item in interfaces_summary)
    )
    return observed


def run(plan_path, binary, freecad):
    plan = read(plan_path)
    assert all(digest(ROOT / path) == expected for path, expected in plan['inputs_sha256'].items())
    assert relative(binary) in plan['inputs_sha256']
    reports = plan_path.parent / 'reports'
    reports.mkdir()
    observations = {}
    commands = []
    raw = {}
    for name, spec in plan['cases'].items():
        path = ROOT / spec['input']
        assert digest(path) == spec['input_sha256']
        report = reports / f'{name}.json'
        command = [relative(binary), 'validate', relative(path), '--output', relative(report)]
        commands.append(command)
        execution = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=20)
        observation = {'status': 'NOT_RUN', 'process_code': execution.returncode}
        if report.is_file():
            result = read(report)
            raw[name] = result
            observed = result['status']
            checks = []
            for code, subject, expected in spec['required_findings']:
                matching = status_for(result['findings'], code, subject)
                checks.append({'code': code, 'subject': subject, 'expected': expected, 'observed': matching,
                               'match': any(value in expected for value in matching)})
            integrity = (result.get('input_sha256') == spec['input_sha256']
                         and execution.returncode == RETURN_CODES.get(observed))
            observation.update(status='PASS' if observed in spec['accepted_results'] and integrity
                               and all(check['match'] for check in checks) else 'FAIL',
                               observed=observed, domains={domain: result[domain] for domain in
                                                          ('electrical', 'compatibility', 'geometry')},
                               findings=checks, report=relative(report), report_sha256=digest(report),
                               input_integrity=integrity)
        else:
            observation['stderr'] = execution.stderr.decode('utf-8', errors='replace')
        observations[name] = observation

    oracle = plan['oracle_native']
    nominal = raw.get('nominal')
    if nominal:
        continuity = [[pin['pin_id'] for pin in circuit['endpoints']] for circuit in nominal['continuity']]
        observations['nominal']['continuity'] = continuity
        if sorted(continuity) != sorted(oracle['continuity']):
            observations['nominal']['status'] = 'FAIL'
    native = {}
    for name in ('nominal', 'matched-fictional-exit'):
        if raw.get(name, {}).get('status') != 'PASS':
            continue
        directory = reports / f'native-{name}'
        argv = [sys.executable, '-B', relative(ADAPTER), 'run', relative(reports / f'{name}.json'),
                relative(directory), '--freecad', str(freecad)]
        commands.append(argv)
        with (reports / f'native-{name}.log').open('wb') as log:
            execution = subprocess.run(argv, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, timeout=120)
        proof = directory / 'native_l2.json'
        native[name] = {'process_code': execution.returncode, 'status': 'NOT_RUN'}
        if proof.is_file() and execution.returncode == 0:
            measured = native_summary(read(proof), oracle)
            native[name].update(measured=measured, status='PASS' if measured['oracle_match'] else 'FAIL',
                                adapter_status=read(proof)['status'], proof=relative(proof),
                                proof_sha256=digest(proof))

    write(reports / 'qualification.json', {'plan': relative(plan_path), 'plan_sha256': digest(plan_path),
                                            'observations': observations, 'native': native, 'commands': commands})
    return 0 if (all(item['status'] == 'PASS' for item in observations.values())
                 and native.get('nominal', {}).get('status') == 'PASS') else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['freeze', 'run'])
    parser.add_argument('plan', type=Path)
    parser.add_argument('binary', type=Path)
    parser.add_argument('--freecad', type=Path)
    args = parser.parse_args()
    if args.mode == 'freeze':
        freeze(args.plan, args.binary)
        return 0
    if not args.freecad:
        parser.error('run requires --freecad')
    return run(args.plan, args.binary, args.freecad)


if __name__ == '__main__':
    raise SystemExit(main())
