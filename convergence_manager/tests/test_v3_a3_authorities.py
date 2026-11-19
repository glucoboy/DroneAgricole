"""Contrôles A.3 du dossier d'autorité et de la porte L5 en lecture seule."""

import argparse
from pathlib import Path
import shutil
import stat
import subprocess

from test_v3_i_scope import check_closure, check_refusal
from verify_v3_a2_evidence import A, A2, ROOT, digest, read, require, write


def observation_request(core, request, sandbox, output):
    receipt = output / 'admission.json'
    argv = [str(core), 'v3-admission', '--root', str(ROOT), '--request', str(request),
            '--sandbox', str(sandbox), '--output', str(output)]
    result = subprocess.run(argv, cwd=ROOT, capture_output=True, timeout=60)
    require(result.returncode == 0 and receipt.is_file(), f'Observation L5 incomplète : {result.stderr!r}')
    decision = read(receipt)
    require(decision['admission']['execution_scope'] == 'READ_ONLY_IMPACT' and
            decision['admission']['decision'] == 'ALLOW' and decision['dispatch_status'] == 'READ_ONLY' and
            decision['candidate_transactions'] == 0 and decision['construction_result'] == 'NOT_RUN' and
            decision['request_sha256'] == digest(request) and list(output.iterdir()) == [receipt],
            'La demande A.1 de lecture a changé de portée')
    return {'argv': argv, 'exit_code': result.returncode, 'receipt_sha256': digest(receipt),
            'scope': 'READ_ONLY_IMPACT', 'candidate_transactions': 0}


def adversarial_inputs():
    # Valeurs fictives pour sonder la frontière L5, sans contenu physique signé.
    for maker in ('JBD', 'WAVESHARE', 'HOLYBRO'):
        yield f'revision-{maker}', 'CHANGE_CONNECTOR_VARIANT', {'revision': 'test-other-revision', 'manufacturer': maker}
    yield 'ttl-plus-3mm', 'CHANGE_CONNECTOR_VARIANT', {'offset_mm': [3, 0, 0]}
    yield 'axe-presente-comme-repere', 'CHANGE_CONNECTOR_VARIANT', {'mating_frame_from': 'F40-axis'}
    for field in ('lot_or_serial', 'tolerance', 'operator_id', 'raw_evidence_sha256'):
        yield f'dossier-sans-{field}', 'CREATE_SUPPORT', {'metrology_missing': field}
    yield 'appui-flottant', 'CREATE_SUPPORT', {'claimed_contact': True, 'gap_mm': 0.3}
    yield 'gorge-non-engagee', 'RELOCATE_SUPPORT', {'claimed_retained': True, 'groove_engaged': False}
    yield 'intersection-P72', 'CREATE_SUPPORT', {'claimed_clear': True, 'intersection_p72_mm3': 109.734}
    yield 'tx-rx-inverses', 'CHANGE_INTERFACE_TOPOLOGY', {'claimed_connections': [['TXD_BMS', 'TXD_ISO']]}
    yield 'vdd-contacte', 'CHANGE_INTERFACE_TOPOLOGY', {'claimed_connections': [['VDD_BMS', 'VCC_ISO']]}
    for net in ('P_MINUS_PROTEGE', 'USB_GND', 'USB_SHIELD', 'CHASSIS'):
        yield f'pont-Bmoins-{net}', 'CHANGE_INTERFACE_TOPOLOGY', {'claimed_connections': [['B_MINUS_BRUT', net]]}
    yield 'can1-5v-contacte', 'CHANGE_INTERFACE_TOPOLOGY', {'claimed_connections': [['CAN1_5V', 'PM08_5V']]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--core', type=Path, required=True)
    parser.add_argument('--source', type=Path, required=True, help='Source XLink scellée V3-A')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    out = args.out.resolve()
    require(out.is_relative_to(ROOT / '.runtime') and out != ROOT / '.runtime', 'Sortie privée .runtime requise')
    core = args.core.resolve(strict=True)
    source = args.source.resolve(strict=True)
    dossier = ROOT / 'docs/verification/v3/a3/operation_admission.json'
    register = ROOT / 'docs/verification/v3/a3/evidence_register.json'
    paths = (dossier, register, core)
    before = {str(path): digest(path) for path in paths}
    scopes = read(A2 / 'operation_scopes.json')
    graph_issues = sorted(row['id'] for row in read(A / 'acceptance.json')['open'])
    register_issues = sorted(row['id'] for row in read(register)['issues'] if row['status'] == 'OPEN')
    require(len(graph_issues) == 8 and register_issues == graph_issues, 'Les huit issues A doivent rester ouvertes')
    native = read(A / 'native_receipt.json')
    dependencies = native['inputs_sha256']
    matrix = read(dossier)
    require(matrix['schema'] == 'v3.a3.operation_admission/1' and matrix['mutation'] == 'DENY' and
            matrix['bounded_experiments'] == [], 'Dossier A.3 sans autorité attendue')
    rows = matrix['occurrences']
    expected = {(row['operation'], occurrence) for row in scopes['operations'] for occurrence in row['occurrences']}
    require(len(rows) == len(expected) and {(row['operation'], row['occurrence']) for row in rows} == expected,
            'Couverture des occurrences A.2 divergente')
    require(all(row['scope'] == 'BLOCKED' and row['domain_bound'] is None and row['decision'] == 'DENY' for row in rows),
            'Une occurrence accorde implicitement une permission')

    sandbox = out / 'input'
    sandbox.mkdir(parents=True, exist_ok=False)
    for name, expected_sha in dependencies.items():
        origin = source / name
        require(digest(origin) == expected_sha, f'Source non scellée : {name}')
        target = sandbox / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(origin, target)
        target.chmod(stat.S_IREAD)
    check_closure(source, sandbox, dependencies)

    common = {**scopes['observation_request_common'], 'xlink_dependencies': dependencies}
    observations = {}
    for fragment in scopes['observation_requests']:
        case = fragment['effect']['hypothetical_operation']
        request = out / f'lecture-{case}.json'
        write(request, {**common, **fragment})
        observations[case] = observation_request(core, request, sandbox, out / f'lecture-{case}')
    raw = out / 'dossier-comme-demande'
    raw.mkdir()
    cases = {raw.name: check_refusal(core, sandbox, raw, dossier, 'UNSUPPORTED', 'CONTRACT_VERSION_UNSUPPORTED', [])}

    def refuse(name, operation, occurrence, effect, locator):
        case = out / name
        case.mkdir()
        request = dict(common, operation=operation, occurrence=occurrence, effect=effect,
                       output='PRIVATE_CANDIDATE', rollback='DISCARD_PRIVATE_COPY',
                       authorities={'V3_A3_OPERATION_ADMISSION': locator})
        request_path = case / 'request.json'
        write(request_path, request)
        result = check_refusal(core, sandbox, case, request_path, 'DENY',
                               'CARTOGRAPHER_AUTHORITIES_UNRESOLVED', graph_issues)
        return {'operation': operation, 'occurrence': occurrence, **result}

    first_row_by_operation = {}
    for index, row in enumerate(rows):
        operation, occurrence = row['operation'], row['occurrence']
        locator = f'/occurrences/{index}'
        first_row_by_operation.setdefault(operation, (occurrence, locator))
        key = f'occurrence-{index:02d}'
        cases[key] = refuse(key, operation, occurrence, {}, locator)
    raw_mat = out / 'dossier-forge'
    raw_mat.mkdir()
    forged = read(dossier)
    forged.update(mutation='ALLOW', auto_authorization=True)
    forged['occurrences'][0].update(scope='BOUNDED_CAD_EXPERIMENT', decision='ALLOW')
    forged_path = raw_mat / 'request.json'
    write(forged_path, forged)
    cases[raw_mat.name] = check_refusal(core, sandbox, raw_mat, forged_path, 'UNSUPPORTED',
                                      'CONTRACT_VERSION_UNSUPPORTED', [])

    attacks = {}
    for name, operation, effect in adversarial_inputs():
        occurrence, locator = first_row_by_operation[operation]
        attacks[name] = refuse(name, operation, occurrence, effect, locator)
    check_closure(source, sandbox, dependencies)
    require(all(digest(path) == before[str(path)] for path in paths), 'Dossier ou binaire modifié pendant L5')
    write(out / 'scope_checks.json', {
        'schema': 'v3.a3.scope_checks/1', 'status': 'PASS', 'inputs_sha256': before,
        'observations': observations, 'dossier_and_occurrences': cases, 'adversarial_cases': attacks,
        'verified_closure_files': len(dependencies),
        'scope': 'Contrôle L5 de non-escalade. Les motifs techniques des injections ne sont pas qualifiés par L5.',
    })
    print(f'{len(cases)} refus de portée, {len(attacks)} injections bloquées, {len(observations)} témoins de lecture admis')


if __name__ == '__main__':
    main()
