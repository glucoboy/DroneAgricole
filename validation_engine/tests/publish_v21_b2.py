"""Publish the B.2 pair manifest and coverage from verified artifacts."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
from statistics import mean

from verify_v21_b2 import read, file_hash, publish


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('checkpoint', type=Path)
    parser.add_argument('audit', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    root = Path.cwd()
    run = args.checkpoint.parent
    report = read(run / 'campaign.json')
    final_pin = report['checkpoint']['sha256']
    assert final_pin == file_hash(args.checkpoint)
    provenance = read(args.audit / 'final-provenance.json')
    independent = read(args.audit / 'independent-reopening.json')
    baseline = read(args.audit / 'baseline.json')
    regressions = read(args.output / 'regressions.json')
    assert final_pin == provenance['final_checkpoint_sha256'] == independent['checkpoint_sha256']
    restart_test = args.audit.parent / 'b2-execution/restart-test.json'
    assert read(restart_test)['status'] == 'PASS'

    def relative(path):
        return path.resolve().relative_to(root).as_posix()

    def artifact(path):
        return {'path': relative(path), 'sha256': file_hash(path)}

    counts, admissions = Counter(), Counter()
    pairs, unknown, failures = [], [], []
    for row in report['geometry']['checks']:
        task = row['task']
        if task['kind'] != 'pair':
            continue
        ident = task['id']
        evidence = row['native_evidence']
        observation = evidence['observation'] if evidence else {}
        status = {'pass': 'PASS', 'fail': 'FAIL', 'unknown': 'INCONCLUSIVE'}.get(observation.get('status'), 'NOT_RUN')
        counts[status] += 1
        admissions[row['status']] += 1
        result = {'id': ident, 'a': task['a'], 'b': task['b'], 'status': status,
                  'prototype_admission_status': row['status'],
                  'intersection_mm3': observation.get('intersection_mm3'), 'clearance_mm': observation.get('clearance_mm'),
                  'reason': ('SCREENING_ONLY' if status == 'PASS' and row['status'] == 'INCONCLUSIVE' else
                             observation.get('reason') or observation.get('error') or row.get('reason')),
                  'source': provenance['origins'][ident]['source']}
        pairs.append(result)
        if status == 'FAIL':
            failures.append({**result, 'failures': observation['failures'],
                             'authorized_relation': observation['authorized_relation']})
        if status == 'INCONCLUSIVE':
            unknown.append({**result, 'unknowns': observation.get('unknowns'),
                            'criticality': 'Obligatoire pour établir le résultat nominal de cette paire',
                            'admission_effect': 'La paire reste indéterminée pour le prototype'})
    assert len({row['id'] for row in pairs}) == len(pairs) == 1609
    initial_id_hash = hashlib.sha256(json.dumps(sorted(row['id'] for row in pairs),
                                               separators=(',', ':')).encode()).hexdigest()
    assert initial_id_hash == baseline['screened_pairs_sorted_id_sha256']

    timing, reopen, wall, memories, all_lots = [], [], [], [], []
    for source in provenance['parallel_source']:
        checkpoint = Path(source['path'])
        if not checkpoint.is_absolute():
            checkpoint = args.audit.resolve().parents[1] / checkpoint
        assert file_hash(checkpoint) == source['progress_sha256']
        for lot in read(checkpoint)['lots']:
            directory = checkpoint.parent.parent
            number = lot['batch']
            all_lots.append({
                'batch': number, 'scope': directory.name, 'pairs_planned': len(lot['requested']),
                'pairs_started': len(lot['started']), 'results': len(lot['observed']), 'error': lot['error'],
                'duration_s': lot['elapsed_s'], 'before_first_pair_s': lot['first_task_s'],
                'peak_working_set_bytes': lot['peak_working_set_bytes'],
                'journal': artifact(directory / f'lot-{number:04}.log'),
                'summary': artifact(directory / f'lot-{number:04}.json')})
            if not lot['error']:
                timing.extend(lot['between_task_starts_s'].values())
                wall.append(lot['elapsed_s'])
                if lot['first_task_s'] is not None:
                    reopen.append(lot['first_task_s'])
            if lot['peak_working_set_bytes'] is not None:
                memories.append(lot['peak_working_set_bytes'])
    metrics = {
        'lots': len(all_lots), 'lots_in_error': sum(lot['error'] is not None for lot in all_lots),
        'mean_seconds_per_pair_in_successful_lots': mean(timing),
        'max_seconds_per_pair_in_successful_lots': max(timing),
        'mean_seconds_before_first_pair': mean(reopen), 'sum_successful_batch_seconds': sum(wall),
        'max_worker_peak_working_set_bytes': max(memories, default=None)}
    proof_status = provenance['status'] == 'PASS' and regressions['status'] == 'PASS'
    motor = ('NO_GO_B' if counts['NOT_RUN'] or not proof_status else 'GO_B_CONDITIONNEL'
             if counts['INCONCLUSIVE'] or independent['status'] != 'PASS' else 'GO_B')
    prototype = ('NON_CONFORME_GEOMETRIQUEMENT' if failures else 'RESULTAT_INCOMPLET'
                 if unknown or report['criteria']['screening_only'] else 'CONFORME_GEOMETRIQUEMENT')
    publish(args.output / 'pairs.json', {'criteria': report['criteria'], 'checkpoint_sha256': final_pin,
                                         'expected_ids_sha256': initial_id_hash, 'pairs': pairs})
    publish(args.output / 'inconclusive.json', {
        'measurements': unknown, 'count': len(unknown),
        'screening_only_admission_count': sum(row['reason'] == 'SCREENING_ONLY' for row in pairs),
        'open_outside_pair_measurement': report['open_checks']})
    publish(args.output / 'lots.json', {'performance': metrics, 'lots': all_lots})
    publish(args.output / 'coverage.json', {
        'schema': 'drone-agricole.v21.b2.coverage.v1', 'scope': report['scope'], 'criteria': report['criteria'],
        'verdicts': {'validator': motor, 'prototype_nominal_xlink_geometry': prototype},
        'coverage': {
            'expected': len(pairs), 'status_counts': {key: counts[key] for key in ('PASS', 'FAIL', 'INCONCLUSIVE', 'NOT_RUN')},
            'nominal_admission_counts': dict(admissions),
            'terminal_pairs': len(pairs) - counts['NOT_RUN'], 'conclusive_measurements': counts['PASS'] + counts['FAIL'],
            'original_measurements_reused': provenance['origin_counts'].get('point initial authentifié', 0),
            'all_pairs': report['geometry']['expected_pairs'], 'screened_out': report['geometry']['pairs_screened_out'],
            'aabb_audit': independent['aabb']},
        'performance': metrics, 'failure_pairs': failures,
        'complementary_native_checks': {
            'non_pair_status_counts': dict(Counter(row['status'] for row in report['geometry']['checks']
                                                  if row['task']['kind'] != 'pair')),
            'unavailable_occurrences': report['geometry']['unavailable_occurrences']},
        'original_files_checked': independent['original_files_checked_after'],
        'changed_originals': independent['changed_originals'], 'baseline_validator_and_inputs_sha256': report['pins'],
        'measurement_identity_sha256': independent['measurement_identity_sha256'],
        'independent_repeat_count': independent['repeated'], 'independent_agreement_count': independent['same'],
        'campaigns': {'GO_3A': 'NOT_RUN', 'GO_3B': 'NOT_RUN'},
        'artifacts': {
            'candidate_pairs': artifact(args.output / 'pairs.json'),
            'historical_interferences': artifact(args.output / 'interferences.json'),
            'batches': artifact(args.output / 'lots.json'), 'inconclusive': artifact(args.output / 'inconclusive.json'),
            'regressions': artifact(args.output / 'regressions.json'), 'baseline_audit': artifact(args.audit / 'baseline.json'),
            'restart_test': artifact(restart_test),
            'final_checkpoint': artifact(args.checkpoint), 'final_campaign': artifact(run / 'campaign.json'),
            'aabb_exclusions': artifact(run / 'aabb_exclusions.json'), 't0': artifact(run / 't0_run_manifest.json'),
            'independent_reopening': artifact(args.audit / 'independent-reopening.json'),
            'final_provenance': artifact(args.audit / 'final-provenance.json'),
            'assembly_authority': artifact(args.audit / 'assembly.json')}})
    print(json.dumps({'pairs': len(pairs), 'counts': counts, 'validator': motor, 'prototype': prototype},
                     ensure_ascii=False))


if __name__ == '__main__':
    main()
