"""Exécuter L4 XLink et valider la finalisation T0 d’un candidat GO3B."""

import argparse
import csv
from hashlib import file_digest
import json
import os
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[3]
VERIFICATION = ROOT / 'docs/verification'
FREECAD = 'C:/Program Files/FreeCAD 1.1/bin/python.exe'
L4 = ROOT / '.runtime/v21-xlink-build/validation_core.exe'
T0 = ROOT / '.runtime/fix-a/.runtime/build-t0/cartographe-evidence.exe'
WORK = ROOT / '.runtime/v21-go3b-validation'


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def artifact(path):
    with path.open('rb') as stream:
        digest = file_digest(stream, 'sha256').hexdigest()
    return {'path': path.relative_to(ROOT).as_posix(), 'sha256': digest}


def execute(command, output):
    env = os.environ | {'PATH': 'C:/msys64/ucrt64/bin;' + os.environ['PATH']}
    result = subprocess.run(command, cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            encoding='utf-8', errors='replace', check=False)
    output.write_text(result.stdout, encoding='utf-8')
    return result


def main(case, electrical, limit):
    if case not in {'H03-A', 'H03-B', 'H02-A', 'H02-B', 'H01-A-reprise', 'H01-B-reprise', 'consolidee'}:
        raise ValueError('Identité de variante GO3B invalide.')
    candidate = ROOT / '.runtime/v21-go3b' / case
    out = WORK / case
    out.mkdir(parents=True, exist_ok=True)
    construction = read(candidate / 'construction.json')
    if construction['phase'] != 'SAVED':
        raise ValueError('Natif candidat non sauvegardé.')
    configuration = read(ROOT / 'validation_engine/fixtures/xlink_cartographe.json')
    register = ROOT / configuration.pop('equipment_register')
    record = read(VERIFICATION / 'v21_go3a_candidates.json')['reference']['dependencies']['connector_bom']
    if artifact(register) != record:
        raise ValueError('Nomenclature d’entrée divergente du gel GO3A.')
    expected, equipment = {}, {}
    with register.open(newline='', encoding='utf-8-sig') as stream:
        for row in csv.DictReader(stream):
            side = row['cle_interface']
            frame = json.loads(row['repere_equipement_vers_assemblage'] or 'null')
            values = frame.get('valeur', {}) if frame else {}
            if not values.get('occurrence'):
                continue
            equipment[side] = {'object': values['occurrence'], 'source': frame.get('source')}
            expected[side] = values['matrice_4x4_lignes']
    if 'isolator_placement' in construction:
        for side in ('W40/B', 'W41/A'):
            expected[side] = construction['isolator_placement']['after']
            equipment[side]['source'] = 'Pose d’essai portée par la demande de construction; contact non qualifié'
    mapping = out / 'equipment_mapping.json'
    write(mapping, {'equipment': equipment, 'contacts': {}})
    configuration |= {'scope': f'prototype_cartographe_go3b_{case.lower()}',
                      'source': (candidate / 'cad').relative_to(ROOT).as_posix(),
                      'native_count': len(construction['native_sha256']),
                      'extras': list(read(VERIFICATION / 'v21_go3a_reference_replay.json')['native']['auxiliary_files']),
                      'equipment_mapping': mapping.relative_to(ROOT).as_posix()}
    config = out / 'l4_configuration.json'
    write(config, configuration)
    argv = [str(L4), 'xlink', '--configuration', str(config), '--electrical', str(electrical.resolve()),
            '--freecad-python', FREECAD, '--output', str(out / 'l4-t0'), '--native-timeout-ms', '180000',
            '--batch-timeout-ms', '90000', '--max-native-tasks', str(limit)]
    result = execute(argv, out / 'l4.log')
    runs = sorted((out / 'l4-t0').glob('run-*/campaign.json'), key=lambda path: path.stat().st_mtime)
    receipt = {'argv': argv, 'configuration': artifact(config), 'mapping': artifact(mapping),
               'exit_code': result.returncode, 'status': 'NOT_RUN'}
    if result.returncode in {0, 2, 3} and runs:
        path = runs[-1]
        t0 = execute([str(T0), 'validate', str(path.parent), str(ROOT)], out / 't0.log')
        report = read(path)
        geometry, electrical_result = report['geometry'], report['electrical']
        poses = {}
        for side, matrix in expected.items():
            actual = electrical_result['interfaces'][side]['equipment'].get('observed', {}).get('matrix')
            error = max(abs(actual_point - expected_point) for actual_point, expected_point in zip(actual, matrix)) if actual else None
            poses[side] = {'nominal_pose': 'INCONCLUSIVE' if error is None else 'PASS' if error <= 1e-6 else 'FAIL',
                           'declared_matrix': matrix, 'observed_matrix': actual, 'largest_absolute_component_error': error}
        receipt |= {'status': report['verdict'], 'finalized': report['finalized'], 't0_exit_code': t0.returncode,
                    'validator': artifact(L4), 't0_manifest': artifact(path.parent / 't0_run_manifest.json'),
                    'campaign': artifact(path), 'electrical_status': electrical_result['status'],
                    'electrical': electrical_result['summary'], 'nominal_equipment_poses': poses,
                    'solid_pair_coverage': {key: geometry[key] for key in ('expected_pairs', 'possible_brep_pairs',
                                            'pairs_examined', 'pairs_not_run', 'pairs_screened_out')},
                    'note': 'L4 standard et calcul B.2 indépendant ont des preuves distinctes.'}
    write(out / 'l4_receipt.json', receipt)
    print(receipt['status'])
    return 0 if receipt.get('t0_exit_code') == 0 and receipt.get('finalized') else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', required=True)
    parser.add_argument('--electrical', required=True, type=Path)
    parser.add_argument('--l4-limit', type=int, default=53)
    args = parser.parse_args()
    raise SystemExit(main(args.case, args.electrical, args.l4_limit))
