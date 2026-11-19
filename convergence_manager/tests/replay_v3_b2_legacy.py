"""Contre-mesure L4 XLink du cordon des bancs V3 B.1, avec critères projetés."""

import argparse
from datetime import datetime, timezone
from pathlib import Path
import subprocess

from replay_v3_b1 import ROOT, digest, load, write


C4 = ROOT / 'docs/electromechanical_v3/bench_b1_c4'
WORKHOLDING = ROOT / 'docs/electromechanical_v3/bench_b1_workholding'
CASES = {
    'c4-reference': (C4, None, 0, 'PASS', 'FAIL'),
    'c4-candidate': (C4, 'xlink-historical-c4-1', 12, 'PASS', 'CLEAR'),
    'workholding-candidate': (WORKHOLDING, 'xlink-workholding-b1-1', 0, 'PASS', 'CLEAR'),
    'workholding-radius-low': (WORKHOLDING, 'xlink-workholding-b1-4', 0, 'FAIL', 'CLEAR'),
}


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def relative(path):
    return path.relative_to(ROOT).as_posix()


def check_hashes(source, expected):
    for name, sha256 in expected.items():
        path = source / name
        require(path.resolve(strict=True) == path and path.stat().st_nlink == 1 and digest(path) == sha256,
                f'Fermeture source divergente : {path}')


def load_source(profile_path, profile, replay, candidate):
    if candidate is None:
        return ROOT / profile['source'], profile['dependencies'], None
    transaction = replay / candidate / 'output/transaction'
    receipt_path = transaction / 'campaign.json'
    plan_path = transaction / 'mutation-plan.json'
    receipt = load(receipt_path)
    plan = load(plan_path)
    require(receipt['finalized'] and receipt['plan_id'] == plan['plan_id'] == candidate and
            receipt['plan_sha256'] == digest(plan_path) and plan['profile_sha256'] == digest(profile_path) and
            receipt['construction_result'] == 'PASS' and receipt['source_integrity']['status'] == 'PASS',
            f'Transaction B.1 non liée au profil du banc : {candidate}')
    hashes = receipt['native_sha256']
    require(hashes.keys() == profile['dependencies'].keys() and
            hashes[profile['entry']] != profile['dependencies'][profile['entry']] and
            all(hashes[name] == sha for name, sha in profile['dependencies'].items()
                if name != profile['entry']), f'Fermeture du candidat inattendue : {candidate}')
    return transaction / 'cad', hashes, receipt_path


def invoke(argv, log):
    started = datetime.now(timezone.utc).isoformat()
    result = subprocess.run(list(map(str, argv)), cwd=ROOT, capture_output=True, timeout=210)
    log.write_bytes(result.stdout + result.stderr)
    return {'argv': list(map(str, argv)), 'started_utc': started, 'exit_code': result.returncode,
            'log': relative(log), 'log_sha256': digest(log)}


def pair_observation(run, geometry, cordon, obstacle):
    matches = [row for row in geometry['checks'] if row['task']['kind'] == 'pair' and
               {row['task']['a'], row['task']['b']} == {cordon, obstacle}]
    if matches:
        row, = matches
        native = row['native_evidence']
        return {'method': 'BREP', 'status': row['status'],
                'observation': native['observation'] if native else None}
    exclusions = load(run / geometry['aabb_exclusion_proof'])
    bounds = [gap for first, second, gap in exclusions['exclusions']
              if {first, second} == {cordon, obstacle}]
    if not bounds:
        return {'method': None, 'status': 'NOT_RUN'}
    lower_bound, = bounds
    require(lower_bound > exclusions['cutoff_mm'], 'Exclusion AABB incohérente')
    return {'method': 'AABB_LOWER_BOUND', 'status': 'CLEAR',
            'lower_bound_mm': lower_bound, 'cutoff_mm': exclusions['cutoff_mm']}


def replay_case(args, name, case):
    bench, candidate, end_y, expected_route, expected_pair = case
    profile_path = bench / 'profile.json'
    profile_sha256 = digest(profile_path)
    profile = load(profile_path)
    source, hashes, receipt_path = load_source(profile_path, profile, args.replay, candidate)
    receipt_sha256 = digest(receipt_path) if receipt_path else None
    check_hashes(source, hashes)

    area = args.output / name
    area.mkdir()
    criteria_path = C4 / 'criteria.json'
    criteria_sha256 = digest(criteria_path)
    criteria = load(criteria_path)['criteria']
    entry = profile['entry']
    occurrences = profile['model']['occurrences']
    cordon = f'{entry}#{occurrences["cordon"]}'
    obstacle = f'{entry}#{occurrences["service-obstacle"]}'
    (old_cordon, route), = criteria['route_criteria'].items()
    require(route['minimum_radius_mm'] == profile['model']['validation']['routes']['cordon']['minimum_radius_mm'],
            f'Seuil de courbure divergent : {bench.name}')
    # Les deux bancs documentent les mêmes sorties selon ±X. Seul C4 déplace B de +12 mm.
    route['end_mm'][1] = end_y
    criteria['route_criteria'] = {cordon: route}
    criteria['source'] = relative(criteria_path)
    for contact in criteria['contacts']:
        require(contact['inner_id'] == old_cordon, 'Contact du cordon historique non reconnu')
        contact['inner_id'] = cordon
    config = area / 'configuration.json'
    write(config, {'scope': 'v3_b2_legacy_cable_geometry', 'source': relative(source),
                   'entry': entry, 'native_count': len(hashes), 'criteria': criteria, 'open_checks': []})
    output = area / 'l4'
    l4 = invoke([args.l4, 'xlink', '--configuration', relative(config), '--output', relative(output),
                 '--freecad-python', args.freecad], area / 'l4.log')
    require(l4['exit_code'] == 3, f'Campagne L4 historique non finalisée : {name}')
    report_path, = output.glob('run-*/campaign.json')
    run = report_path.parent
    report = load(report_path)
    closure = report['closure']
    require(report['finalized'] and closure['reopened'] and closure['source_sha256'] == hashes and
            closure['saved_worker'] != closure['reopened_worker'] and closure['integrity']['sources_unchanged'],
            f'Fermeture L4 non attestée : {name}')
    check_hashes(source, hashes)
    t0 = invoke([args.t0, 'validate', relative(run), '.'], area / 't0.log')
    require(t0['exit_code'] == 0, f'Reçu T0 L4 invalide : {name}')
    require(digest(criteria_path) == criteria_sha256 and digest(profile_path) == profile_sha256 and
            (receipt_path is None or digest(receipt_path) == receipt_sha256),
            f'Autorité ou reçu modifiés pendant L4 : {name}')

    geometry = report['geometry']
    route_row, = [row for row in geometry['checks']
                  if row['task']['kind'] == 'route' and row['task']['a'] == cordon]
    pair = pair_observation(run, geometry, cordon, obstacle)
    observation = (route_row['native_evidence'] or {}).get('observation', {})
    route_ok = route_row['status'] == expected_route and (
        expected_route == 'PASS' or 'bend_radius_below_requirement' in observation['failures'])
    pair_ok = (pair['status'] in ('PASS', 'CLEAR') if expected_pair == 'CLEAR' else
               pair['status'] == 'FAIL' and 'forbidden_interference' in pair['observation']['failures'])
    agreement = route_ok and pair_ok
    return {'status': 'ADAPTED', 'agreement': 'PASS' if agreement else 'FAIL',
            'candidate': candidate, 'candidate_receipt_sha256': receipt_sha256,
            'profile_sha256': profile_sha256, 'criteria_authority_sha256': criteria_sha256,
            'configuration_sha256': digest(config), 'input_sha256': hashes,
            'l4': {**l4, 'verdict': report['verdict'], 'geometry': geometry['status'],
                   'electrical': report['electrical']['status'],
                   'campaign': relative(report_path), 'campaign_sha256': digest(report_path),
                   'saved_pid': closure['saved_pid'], 'reopened_pid': closure['reopened_pid']},
            't0': {**t0, 'manifest_sha256': digest(run / 't0_run_manifest.json')},
            'route': {'expected_status': expected_route, 'criteria': route, 'result': route_row},
            'pair': {'objects': [cordon, obstacle], 'expected_status': expected_pair, **pair}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('l4', 't0', 'freecad', 'replay', 'output'):
        parser.add_argument(f'--{key}', type=lambda value: Path(value).resolve(), required=True)
    parser.add_argument('--case', choices=CASES, action='append')
    args = parser.parse_args()
    runtime = ROOT / '.runtime'
    require(all(path != runtime and path.is_relative_to(runtime) for path in (args.replay, args.output)),
            'Les entrées et les sorties doivent être privées sous .runtime')
    args.output.mkdir(parents=True)
    hashes = {name: digest(getattr(args, name)) for name in ('l4', 't0', 'freecad')}
    cases = {name: replay_case(args, name, CASES[name]) for name in (args.case or CASES)}
    require(all(digest(getattr(args, name)) == sha for name, sha in hashes.items()),
            'Binaire de validation modifié pendant le rejeu')
    write(args.output / 'legacy_comparison.json', {
        'schema': 'v3.b2.legacy_l4_projection/1',
        'scope': 'Rayon nominal du cordon et paire cordon/obstacle de service, bancs synthétiques.',
        'limits': ['L4 mesure les paires visibles impliquant un câble près du seuil. Les exclusions AABB '
                   'sont des bornes, sans booléen BRep.',
                   'La carte C4 couvre le rayon et le seuil de dégagement. Les contacts électriques, '
                   'les autres paires, les repères, les appuis et les ancrages gardent leurs propres preuves.'],
        'tools_sha256': hashes, 'cases': cases,
    })
    return 0 if all(case['agreement'] == 'PASS' for case in cases.values()) else 1


if __name__ == '__main__':
    raise SystemExit(main())
