"""Contre-épreuves V3-B.2 sur les reçus et la reprise de transaction."""

import argparse
from pathlib import Path
import shutil

from replay_v3_b1 import ROOT, digest, load, plan_for, setup, write
from replay_v3_b2 import artifact, invoke


PROFILE = Path('docs/electromechanical_v3/bench_b1_c4/profile.json')
VERIFIER = Path('convergence_manager/native/v3_verify.py')
BUILDER = Path('convergence_manager/native/v3_mutate.py')


def false_expected(args, area, positive):
    case = area / 'false-expected-after'
    case.mkdir()
    job = load(positive / 'candidate-job.json')
    job['actions'][0]['expected_after']['placement']['translation_mm'][1] += 3
    request = case / 'job.json'
    receipt = case / 'output.json'
    write(request, job)
    cad = case / 'cad'
    shutil.copytree(positive / 'cad', cad)
    process = invoke(case, 'freecad', [str(args.freecad), '-B', str(ROOT / VERIFIER), '--root', str(cad),
                                     '--job', str(request), '--output', str(receipt)])
    assert process.returncode == 0
    assert load(positive / 'build.json')['status'] == 'PASS'
    observed = load(receipt)
    pose = next(row for check in observed['checks'] if check['id'] == 'L4_GEOMETRY'
                for row in check['details']['poses'] if row.get('occurrence') == 'device-b')
    assert observed['status'] == 'FAIL' and abs(pose['position_error_mm']-3) <= 1e-6
    return {'prediction': 'FAIL en géométrie (+3 mm dans expected_after), constructeur historique PASS',
            'actual': observed['status'], 'position_error_mm': pose['position_error_mm'], 'receipt': artifact(receipt),
            'invocation': artifact(case / 'freecad-invocation.json')}


def reject_forged_receipt(args, area, positive):
    case = area / 'forged-published-receipt'
    case.mkdir()
    transaction = case / 'transaction'
    shutil.copytree(positive, transaction)
    receipt = transaction / 'candidate-validation.json'
    report = load(receipt)
    report['inputs_sha256']['Banc_Interconnexion.FCStd'] = '0' * 64
    write(receipt, report)
    t0 = invoke(case, 't0', [str(args.t0), 'validate', str(transaction), str(ROOT)], timeout=60)
    assert t0.returncode != 0
    return {'prediction': 'Le reçu modifié est refusé avant qu’il serve à une reprise.',
            'actual': 'FAIL', 'exit_code': t0.returncode, 'receipt': artifact(receipt),
            'invocation': artifact(case / 't0-invocation.json')}


def replica(case, profile):
    root = case / 'repo'
    inputs = {PROFILE, VERIFIER, BUILDER, Path(profile['graph'])}
    graph = load(ROOT / profile['graph'])
    inputs |= {Path(row['path']) for row in graph['sources'].values()}
    inputs |= {Path(profile['source']) / name for name in profile['dependencies']}
    inputs.add(Path('hardware/mecanique/cartographe/verification/cable_workbench_prototype.py'))
    for path in inputs:
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / path, target)
    shutil.copytree(ROOT / 'electromechanical_engine', root / 'electromechanical_engine', ignore=shutil.ignore_patterns('__pycache__'))
    for directory in ('.agents/skills/electromechanical-integration/scripts', 'configs/visualization/schemas'):
        shutil.copytree(ROOT / directory, root / directory, ignore=shutil.ignore_patterns('__pycache__'))
    return root


def fresh_transaction(args, case, root, *, malicious_verifier):
    profile = load(ROOT / PROFILE)
    plan = plan_for(profile, digest(ROOT / PROFILE), case.name, profile['compositions'][0])
    sandbox = setup(root / '.runtime', profile, plan)
    output = root / '.runtime/output'
    output.mkdir()
    if malicious_verifier:
        worker = root / VERIFIER
        source = worker.read_text(encoding='utf-8')
        anchor = '        require(guard.sha256(job_path) == job_hash'
        assert source.count(anchor) == 1
        worker.write_text(source.replace(anchor, '        report["status"] = "PASS"\n'
                         '        next(row for row in report["checks"] if row["id"] == "L2_TOPOLOGY")["status"] = "FAIL"\n' + anchor),
                          encoding='utf-8', newline='\n')
    else:
        attempt = output / '.attempt-faux'
        (attempt / 'publication').mkdir(parents=True)
        write(attempt / 'journal.json', {'schema': 'v3.b1.journal/1', 'plan_id': case.name,
              'plan_sha256': digest(root / '.runtime/plan.json'), 'events': [{'event': 'CANDIDATE'}]})
        write(attempt / 'publication/campaign.json', {'finalized': True, 'status': 'PASS', 'native_sha256': {}})
    result = invoke(case, 'v3-build', [str(args.core), 'v3-build', '--root', str(root), '--request', '.runtime/plan.json',
                    '--sandbox', str(sandbox), '--output', str(output), '--freecad-python', str(args.freecad),
                    '--t0-validator', str(args.t0)], timeout=180)
    receipt = output / 'transaction/campaign.json'
    if not receipt.is_file():
        receipt = output / 'refusal.json'
    return result, receipt


def inspect_inconsistent_report(args, area, profile):
    case = area / 'inconsistent-native-report'
    case.mkdir()
    root = replica(case, profile)
    process, receipt = fresh_transaction(args, case, root, malicious_verifier=True)
    observed = load(receipt)
    assert process.returncode == 4 and observed['status'] == 'INCONCLUSIVE'
    assert observed['candidate_transactions'] == 0 and observed['candidate_state'] == 'ROLLED_BACK'
    assert 'Réouverture indépendante incohérente' in observed['reason'] and not (receipt.parent / 'cad').exists()
    proof = load(receipt.parent / 'baseline-validation.json')
    assert proof['reopened'] and proof['documents_closed'] and proof['status'] == 'PASS'
    assert any(row['id'] == 'L2_TOPOLOGY' and row['status'] == 'FAIL' for row in proof['checks'])
    return {'prediction': 'INCONCLUSIVE si PASS agrégé contredit un contrôle obligatoire FAIL', 'actual': observed['status'],
            'receipt': artifact(receipt), 'invocation': artifact(case / 'v3-build-invocation.json')}


def replay_abandoned_claim(args, area, profile):
    case = area / 'forged-abandoned-publication'
    case.mkdir()
    root = replica(case, profile)
    process, receipt = fresh_transaction(args, case, root, malicious_verifier=False)
    observed = load(receipt)
    assert process.returncode == 0 and observed['status'] == 'PASS'
    assert observed['candidate_transactions'] == 1 and observed['abandoned_attempts'][0]['attempt'] == '.attempt-faux'
    assert observed['native_sha256'] and load(receipt.parent / 't0-crosscheck.json')['exit_code'] == 0
    return {'prediction': 'La publication abandonnée est ignorée. Reprise avec nouveau constructeur et nouvelle validation.',
            'actual': 'NEW_TRANSACTION', 'receipt': artifact(receipt), 'invocation': artifact(case / 'v3-build-invocation.json')}


def abrupt_native_exit(args, area, profile):
    case = area / 'interrupted-in-memory'
    case.mkdir()
    root = replica(case, profile)
    builder = root / BUILDER
    source = builder.read_text(encoding='utf-8')
    marker = "            row['status'] = 'APPLIED_IN_MEMORY'\n"
    assert source.count(marker) == 1
    builder.write_text(source.replace(marker, marker +
                       "            print('APPLIED_IN_MEMORY_BEFORE_SAVE', flush=True)\n"
                       '            os._exit(73)\n'), encoding='utf-8', newline='\n')
    process, receipt = fresh_transaction(args, case, root, malicious_verifier=False)
    observed = load(receipt)
    journal = load(receipt.parent / 'journal.json')
    build_end = next(row['detail'] for row in journal['events']
                     if row['event'] == 'PROCESS_END' and row['detail']['stage'] == 'build')
    assert build_end['exit_code'] == 73 and 'APPLIED_IN_MEMORY_BEFORE_SAVE' in build_end['stdout']
    assert process.returncode == 4 and observed['status'] == 'INCONCLUSIVE'
    assert observed['candidate_transactions'] == 1 and observed['candidate_state'] == 'ROLLED_BACK'
    assert observed['source_integrity']['status'] == 'PASS' and not (receipt.parent / 'cad').exists()
    return {'prediction': 'Sortie brutale après mutation mémoire, avant sauvegarde. Aucun natif publié.',
            'actual': 'ROLLED_BACK', 'builder_exit_code': 73, 'receipt': artifact(receipt),
            'journal': artifact(receipt.parent / 'journal.json'), 'invocation': artifact(case / 'v3-build-invocation.json')}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for parameter in ('core', 'freecad', 't0', 'positive', 'output'):
        parser.add_argument('--'+parameter, type=Path, required=True)
    args = parser.parse_args()
    for parameter in ('core', 'freecad', 't0', 'positive'):
        setattr(args, parameter, getattr(args, parameter).resolve(strict=True))
    area = args.output.resolve()
    assert area.is_relative_to(ROOT / '.runtime')
    area.mkdir(parents=True, exist_ok=False)
    profile = load(ROOT / PROFILE)
    tests = {'false_expected_after': false_expected(args, area, args.positive),
             'forged_published_receipt': reject_forged_receipt(args, area, args.positive),
             'inconsistent_native_report': inspect_inconsistent_report(args, area, profile),
             'forged_abandoned_publication': replay_abandoned_claim(args, area, profile),
             'interruption_after_in_memory_mutation': abrupt_native_exit(args, area, profile)}
    assert all(digest(ROOT / profile['source'] / name) == sha for name, sha in profile['dependencies'].items())
    write(area / 'checks.json', {'schema': 'v3.b2.adversarial_evidence/1', 'cases': tests})
    print(f'{len(tests)} contre-épreuves de provenance et reprise exécutées')


if __name__ == '__main__':
    main()
