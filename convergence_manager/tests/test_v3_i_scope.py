"""Vérifie que le dossier de préconditions A.2 ne donne aucun droit de mutation."""

import argparse
from datetime import datetime, timezone
from pathlib import Path
import subprocess

from verify_v3_a2_evidence import A2, ROOT, digest, read, require, write


def check_refusal(core, sandbox, case, request, expected_decision, expected_reason, issues):
    output = case / 'output'
    receipt = output / 'admission.json'
    argv = [str(core), 'v3-admission', '--root', str(ROOT), '--request', str(request),
            '--sandbox', str(sandbox), '--output', str(output)]
    request_sha = digest(request)
    started = datetime.now(timezone.utc).isoformat()
    result = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True, encoding='utf-8',
                            errors='replace', timeout=60)
    trace = {
        'argv': argv, 'started_at_utc': started, 'exit_code': result.returncode,
        'stdout': result.stdout, 'stderr': result.stderr, 'request_sha256': request_sha,
        'receipt_sha256': digest(receipt) if receipt.is_file() else None,
    }
    write(case / 'invocation.json', trace)
    require(result.returncode == 2 and receipt.is_file(), f'Refus L5 non finalisé : {case.name}')

    report = read(receipt)
    admission = report['admission']
    require(admission['decision'] == expected_decision and admission['reason'] == expected_reason and
            admission['execution_scope'] == 'NONE' and not admission['allowed_operations'] and
            sorted(admission['open_issues']) == issues, f'Décision L5 inattendue : {case.name}')
    require(report['request_sha256'] == digest(request) == request_sha and
            report['dispatch_status'] == 'BLOCKED' and report['construction_result'] == 'NOT_RUN' and
            report['candidate_transactions'] == 0 and list(output.iterdir()) == [receipt],
            f'Transaction ou reçu incohérent : {case.name}')
    return {**trace, 'decision': admission['decision'], 'reason': admission['reason'],
            'execution_scope': admission['execution_scope'], 'dispatch_status': report['dispatch_status'],
            'candidate_transactions': report['candidate_transactions'],
            'construction_result': report['construction_result'], 'open_issues': issues}


def check_closure(source, sandbox, dependencies):
    for name, expected in dependencies.items():
        require(digest(source / name) == digest(sandbox / name) == expected,
                f'Fermeture XLink divergente : {name}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--core', type=Path, required=True)
    parser.add_argument('--integrity', type=Path, required=True,
                        help='Dossier de sortie de verify_v3_a2_evidence.py')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    core = args.core.resolve(strict=True)
    core_sha = digest(core)
    integrity = args.integrity.resolve(strict=True)
    output = args.out.resolve()
    runtime = (ROOT / '.runtime').resolve()
    require(integrity != runtime and integrity.is_relative_to(runtime) and
            output != runtime and output.is_relative_to(runtime) and not output.is_relative_to(integrity),
            'Des dossiers privés distincts sous .runtime sont requis')

    scopes_path = A2 / 'operation_scopes.json'
    scopes = read(scopes_path)
    scopes_sha = digest(scopes_path)
    integrity_path = integrity / 'integrity.json'
    replay = read(integrity_path)
    require(replay['schema'] == 'v3.a2.integrity_test/1' and replay['status'] == 'PASS' and
            replay['inputs_sha256'][scopes_path.relative_to(ROOT).as_posix()] == scopes_sha,
            'Rejeu A.2 différent du dossier de préconditions')
    move_path = integrity / 'MOVE-request.json'
    move = next(row for row in replay['a1_observations'] if row['case'] == 'MOVE')
    require(move['exit_code'] == 0 and move['decision'] == 'ALLOW' and
            move['execution_scope'] == 'READ_ONLY_IMPACT' and move['candidate_transactions'] == 0 and
            move['request_sha256'] == digest(move_path), 'Demande de lecture A.2 non attestée')
    observation = read(move_path)
    seal = scopes['observation_xlink_dependencies']
    seal_path = ROOT / seal['path']
    require(digest(seal_path) == seal['sha256'], 'Reçu natif A divergent')
    native = read(seal_path)
    dependencies = native['inputs_sha256']
    require(dependencies and observation['xlink_dependencies'] == dependencies,
            'Fermeture de la demande de lecture divergente')
    source = ROOT / native['source_prefix']
    sandbox = integrity / 'input'
    check_closure(source, sandbox, dependencies)

    issues = sorted(row['id'] for row in read(A2 / 'evidence_register.json')['issues'])
    require(len(set(issues)) == len(issues) == 8, 'Huit issues UART distinctes requises')
    output.mkdir(parents=True, exist_ok=False)
    direct = output / 'A2-dossier-direct'
    direct.mkdir()
    results = {direct.name: check_refusal(core, sandbox, direct, scopes_path, 'UNSUPPORTED',
                                         'CONTRACT_VERSION_UNSUPPORTED', [])}
    scope_schema = read(ROOT / scopes['request_schema'])
    operations = scope_schema['$defs']['request']['properties']['operation']['enum']
    expected = set(operations) - {'ANALYZE_IMPACT', 'RECEIVE_PHYSICAL'}
    require(len(scopes['operations']) == len(expected) and
            {row['operation'] for row in scopes['operations']} == expected,
            'Couverture des mutations A.2 divergente')

    for index, row in enumerate(scopes['operations']):
        operation = row['operation']
        occurrence = row['occurrences'][0]
        case = output / operation
        case.mkdir()
        request = dict(observation, operation=operation, occurrence=occurrence,
                       output='PRIVATE_CANDIDATE', rollback='DISCARD_PRIVATE_COPY',
                       effect={}, validations=row['mandatory_checks'],
                       authorities={'V3_A2_PRECONDITIONS': f'/operations/{index}'})
        request_path = case / 'request.json'
        write(request_path, request)
        results[operation] = check_refusal(core, sandbox, case, request_path, 'DENY',
                                           'CARTOGRAPHER_AUTHORITIES_UNRESOLVED', issues)
        results[operation]['occurrence'] = occurrence

    check_closure(source, sandbox, dependencies)
    require(digest(scopes_path) == scopes_sha and digest(core) == core_sha,
            'Registre A.2 ou binaire modifié pendant le rejeu')
    write(output / 'scope_checks.json', {
        'schema': 'v3.i.scope_regression/1', 'status': 'PASS',
        'core': {'path': str(core), 'sha256': core_sha},
        'preconditions_sha256': scopes_sha, 'integrity_receipt_sha256': digest(integrity_path),
        'unchanged_source_and_copy_files': len(dependencies), 'cases': results,
    })
    print(f'{len(results)} refus L5 vérifiés, {len(dependencies)} dépendances XLink intactes')


if __name__ == '__main__':
    main()
