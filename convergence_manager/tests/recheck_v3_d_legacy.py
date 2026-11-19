"""Remesure les sept intersections V2.1 B.2 sur une copie de lecture V3-A."""

import argparse
import math
from pathlib import Path
import stat
import sys

from replay_v3_b1 import ROOT, digest, load, write
from replay_v3_b2 import artifact, invoke


REFERENCE = ROOT / 'docs/verification/v3/a/native_receipt.json'
PAIR_AUTHORITY = ROOT / 'docs/verification/v21_b2/pairs.json'
STAGER = ROOT / '.agents/skills/electromechanical-integration/scripts/workspace_guard.py'


def run_worker(freecad, output, name, request):
    query, result = (output / f'{name}-{suffix}.json' for suffix in ('request', 'result'))
    write(query, request)
    status = invoke(output, name, [str(freecad), '-B', '-m', 'electromechanical_engine.xlink_native', str(query), str(result)],
                    timeout=360)
    if status.returncode or not result.is_file():
        raise RuntimeError(f'Rejeu {name} non finalisé : {status.returncode}. Consulter le journal et le reçu.')
    data = load(result)
    if not (data['finalized'] and data['recompute_ok'] and data['inventory_complete'] and not data['save_performed'] and
            data['request_sha256'] == digest(query) and data['before_sha256'] == data['after_sha256']):
        raise ValueError(f'Fermeture XLink incohérente dans {name}')
    return data, {'request': artifact(query), 'result': artifact(result), 'process': artifact(output/f'{name}-invocation.json')}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--freecad', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    freecad = args.freecad.resolve(strict=True)
    output = args.output.resolve()
    if not output.is_relative_to(ROOT / '.runtime') or output == ROOT / '.runtime':
        raise ValueError('Choisir une sortie privée sous .runtime')
    output.mkdir(parents=True, exist_ok=False)
    reference, history = load(REFERENCE), load(PAIR_AUTHORITY)
    source = ROOT / reference['source_prefix']
    entry = (ROOT / reference['entry']).relative_to(source).as_posix()
    hashes = {name: value for name, value in reference['inputs_sha256'].items() if name.lower().endswith('.fcstd')}
    failures = [row for row in history['pairs'] if row['status'] == 'FAIL']
    if len(hashes) != 137 or len(failures) != 7:
        raise ValueError('Référence de rejeu différente')
    copy = output / 'read-only-copy'
    staged = invoke(output, 'stage', [sys.executable, '-B', str(STAGER), 'stage', '--root', str(source),
                    '--entry', entry, '--target', str(copy)], timeout=180)
    if staged.returncode:
        raise RuntimeError('Préparation de la copie XLink impossible')
    assert load(copy / 'experiment.json')['inputs_sha256'] == hashes
    for name, sha in hashes.items():
        path = copy / name
        if digest(path) != sha:
            raise ValueError(f'Copie divergente : {name}')
        path.chmod(stat.S_IREAD)
    request = {'copy': str(copy), 'native_sha256': hashes}
    inventory, proof_inventory = run_worker(freecad, output, 'inventory', {**request, 'action': 'inventory'})
    task_list = [{'id': row['id'], 'kind': 'pair', 'a': row['a'], 'b': row['b']} for row in failures]
    criteria = history['criteria']
    measured, proof_measure = run_worker(freecad, output, 'measure', {**request, 'action': 'measure', 'tasks': task_list,
        'measurement_identity_sha256': inventory['measurement_identity_sha256'], 'environment': inventory['environment'],
        'criteria': criteria, 'cache_key': digest(output/'inventory-result.json')})
    assert inventory['pid'] != measured['pid'] and inventory['occurrence_count'] == 2772
    assert all(digest(source / name) == digest(copy / name) == sha for name, sha in hashes.items())
    observations = {row['task']['id']: row['observation'] for row in measured['observations']}
    assert len(observations) == len(measured['observations']) == len(task_list)
    rows = []
    for historic in failures:
        live = observations[historic['id']]
        agrees = live['status'] == historic['status'].lower() and all(
            math.isclose(live[key], historic[key], rel_tol=1e-10, abs_tol=1e-10) for key in ('intersection_mm3', 'clearance_mm'))
        rows.append({'id': historic['id'], 'a': historic['a'], 'b': historic['b'], 'historic': historic,
                     'measured': live, 'comparison': 'AGREES' if agrees else 'DIVERGENCE'})
    matched = sum(row['comparison'] == 'AGREES' for row in rows)
    write(output/'legacy_pair_comparison.json', {'schema': 'v3.d.legacy_pair_comparison/1', 'scope': 'READ_ONLY_IMPACT',
          'reference': artifact(REFERENCE), 'authority': artifact(PAIR_AUTHORITY), 'criteria': criteria,
          'documents': len(hashes), 'occurrences': inventory['occurrence_count'], 'newly_measured_pairs': len(rows),
          'agreements': matched, 'pairs': rows, 'stage_process': artifact(output/'stage-invocation.json'),
          'inventory_process': proof_inventory, 'measurement_process': proof_measure, 'candidate_count': 0})
    print(f'{matched}/{len(rows)} interférences concordantes sur copie de lecture', flush=True)
    return 0 if matched == len(rows) else 2


if __name__ == '__main__':
    raise SystemExit(main())
