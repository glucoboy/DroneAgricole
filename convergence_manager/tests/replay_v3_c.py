"""Gèle les outils et rejoue la recherche V3-C sur les deux bancs scellés."""

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess

from replay_v3_b1 import ROOT, digest, load, setup, write
from replay_v3_b2 import artifact, invoke, measurement


DOMAINS = ROOT / 'docs/electromechanical_v3/domains'
BENCHES = {'workholding': 'bench_b1_workholding', 'c4': 'bench_b1_c4'}
SEED = 2026
BUDGET = {'max_proposals': 30, 'max_native': 6}
OBJECTIVES = [{'metric': 'route_length_mm', 'direction': 'MIN'}, {'metric': 'service_clearance_mm', 'direction': 'MAX'}]


def source_commit():
    return subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()


def authority(bench):
    domain_path = DOMAINS / f'{bench}.json'
    profile_path = DOMAINS.parent / BENCHES[bench] / 'profile.json'
    domain, profile = load(domain_path), load(profile_path)
    assert digest(profile_path) == domain['profile_sha256']
    return domain_path, domain, profile_path, profile


def freeze(args, output):
    files = [args.core, args.l3, args.t0, args.freecad, args.python, Path(__file__).resolve()]
    files += [ROOT / name for name in ['convergence_manager/native/v3_mutate.py', 'convergence_manager/native/v3_verify.py',
             'convergence_manager/native/v3_cross_measure.py', 'convergence_manager/tests/replay_v3_b2.py',
             'docs/electromechanical_v3/parametric_domain.schema.json', 'docs/electromechanical_v3/mutation_plan_v2.schema.json',
             'docs/electromechanical_v3/problem_spec.schema.json', 'docs/electromechanical_v3/candidate_result.schema.json']]
    for bench in BENCHES:
        domain_path, _, profile_path, profile = authority(bench)
        files.extend((domain_path, profile_path, ROOT / profile['graph']))
        files.extend(ROOT / profile['source'] / name for name in profile['dependencies'])
    snapshot = {'schema': 'v3.c.freeze/1', 'date_utc': datetime.now(timezone.utc).isoformat(),
                'source_commit': source_commit(), 'seed': SEED, 'budget': BUDGET, 'objectives': OBJECTIVES,
                'perturbation_rule': 'Resserrer un axe autour du témoin B.1 préexistant au point médian avec le gagnant T1, en excluant ce gagnant.',
                'scope': 'SYNTHETIC_BENCH', 'files_sha256': {str(path): digest(path) for path in files}}
    write(output / 'perturbation_freeze.json', snapshot)
    return snapshot


def verify_freeze(snapshot):
    for name, sha in snapshot['files_sha256'].items():
        if digest(Path(name)) != sha:
            raise RuntimeError(f'Le gel a changé pendant l’exploration : {name}')


def problem(args, case, domain_path, profile, observation, phase, narrowing, base=None):
    model = ROOT / profile['source'] / profile['entry']
    request = {'schema': 'v3.problem_spec/1', 'phase': phase, 'domain_sha256': digest(domain_path),
               'model_sha256': digest(model), 'observation_sha256': digest(observation),
               'seed': SEED, 'budget': BUDGET, 'objectives': OBJECTIVES, 'narrowing': {'translation_mm': narrowing}}
    if base:
        request['base_problem_sha256'] = digest(base)
    request_path, spec_path = case / f'{phase}-request.json', case / f'{phase}-problem.json'
    write(request_path, request)
    command = [str(args.l3), 'v3-problem', '--root', str(ROOT), '--request', str(request_path), '--domain', str(domain_path),
               '--model', str(model), '--observation', str(observation), '--output', str(spec_path)]
    if base:
        command += ['--base-problem', str(base)]
    proc = invoke(case, f'{phase}-l3', command)
    if proc.returncode != 0 or not spec_path.is_file():
        raise RuntimeError(f'L3 {phase} non finalisé : {proc.stderr}')
    return spec_path


def run_campaign(args, case, phase, spec, observation, base=None):
    target = case / phase
    command = [str(args.core), 'v3-converge', '--root', str(ROOT), '--request', str(spec), '--observation', str(observation),
               '--freecad-python', str(args.freecad), '--python', str(args.python), '--t0-validator', str(args.t0), '--output', str(target)]
    if base:
        command += ['--base-problem', str(base)]
    proc = invoke(case, f'{phase}-l5', command, timeout=720)
    if proc.returncode not in (0, 4) or not (target / 'campaign.json').is_file():
        raise RuntimeError(f'L5 {phase} non finalisé (code {proc.returncode}) : {proc.stderr}')
    report = load(target / 'campaign.json')
    print(phase, report['verdict'], report['proposals'], report['native_attempts'], report['qualified_candidates'], flush=True)
    return report


def values_for_witness(profile, domain):
    actions = {row['id']: row for row in profile['actions']}
    first = actions[domain['composition'][0]]['parameters']
    route = actions[domain['composition'][1]]['parameters']
    return {'translation_mm': first['placement']['translation_mm'], 'route_points_mm': route['points_mm'], 'bend_radius_mm': route['bend_radius_mm']}


def proposal(domain_path, name, values):
    seal = digest(domain_path)
    return {'schema': 'v3.mutation_plan/2', 'domain': 'SYNTHETIC_BENCH', 'plan_id': name,
            'authority_sha256': seal, 'domain_sha256': seal, 'values': values}


def check_plan(args, area, profile, plan, wanted):
    sandbox = setup(area, profile, plan)
    target = area / 'output'
    proc = invoke(area, 'v3-build', [str(args.core), 'v3-build', '--root', str(ROOT), '--request', str(area/'plan.json'),
                  '--sandbox', str(sandbox), '--output', str(target), '--freecad-python', str(args.freecad), '--t0-validator', str(args.t0)], timeout=240)
    receipt = target / ('transaction/campaign.json' if proc.returncode == 0 else 'refusal.json')
    if proc.returncode != wanted or not receipt.is_file():
        raise RuntimeError(f'Décision v3-build inattendue dans {area.name} : code {proc.returncode}, {proc.stderr}')
    if wanted != 0:
        assert load(receipt)['candidate_transactions'] == 0 and not (target / 'transaction').exists()
    return {'exit_code': proc.returncode, 'invocation': artifact(area / 'v3-build-invocation.json'), 'receipt': artifact(receipt)}


def narrow(used, first, witness):
    axis = max(range(3), key=lambda index: abs(first[index]-witness[index]))
    if first[axis] == witness[axis]:
        raise RuntimeError('Le gagnant T1 reproduit la pose témoin, perturbation discriminante indisponible')
    box = deepcopy(used)
    split = (first[axis]+witness[axis])/2
    box['min' if first[axis] < witness[axis] else 'max'][axis] = split
    return box


def qualification(campaign, report):
    target = campaign / 'campaign.json'
    trace = campaign / 'candidate_trace.jsonl'
    rows = [json.loads(row) for row in trace.read_text(encoding='utf-8').splitlines()]
    assert report['finalized'] and load(campaign / 't0-crosscheck.json')['exit_code'] == 0
    generated = [row['detail']['translation_mm'] for row in rows if row['stage'] == 'GENERATE']
    return {**report, 'campaign': artifact(target), 'trace': artifact(trace), 'pareto': artifact(campaign/'pareto.json'),
            'family_transitions': artifact(campaign/'family_transitions.json'), 't0': artifact(campaign/'t0-crosscheck.json'),
            'discovered_poses': [list(coords) for coords in sorted({tuple(row) for row in generated})]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('core', 'l3', 'freecad', 'python', 't0', 'output'):
        parser.add_argument('--'+key, type=Path, required=True)
    args = parser.parse_args()
    for key in ('core', 'l3', 'freecad', 'python', 't0'):
        setattr(args, key, getattr(args, key).resolve(strict=True))
    area = args.output.resolve()
    assert area.is_relative_to(ROOT / '.runtime')
    area.mkdir(parents=True, exist_ok=False)
    snapshot = freeze(args, area)
    results = {}
    for bench, phase in [('workholding', 'T1'), ('c4', 'T3')]:
        case = area / bench
        case.mkdir()
        domain_path, domain, profile_path, profile = authority(bench)
        _, obs_path = measurement(args.freecad, case, 'reference', ROOT/profile['source'], profile['dependencies'], profile_path)
        witness = values_for_witness(profile, domain)
        results[f'{phase}_feasibility_witness'] = check_plan(args, case/'witness', profile,
                                                             proposal(domain_path, 'witness-'+bench, witness), 0)
        bounds = domain['placement']
        box = {'min': bounds['translation_min_mm'], 'max': bounds['translation_max_mm']}
        frozen_problem = problem(args, case, domain_path, profile, obs_path, phase, box)
        report = run_campaign(args, case, phase, frozen_problem, obs_path)
        results[phase] = qualification(case/phase, report)
        verify_freeze(snapshot)
        if phase == 'T1' and report['retained']:
            first = report['retained']['values']['translation_mm']
            restricted = narrow(box, first, witness['translation_mm'])
            assert not all(a <= p <= b for p, a, b in zip(first, restricted['min'], restricted['max']))
            assert all(a <= p <= b for p, a, b in zip(witness['translation_mm'], restricted['min'], restricted['max']))
            perturbed = problem(args, case, domain_path, profile, obs_path, 'T2', restricted, frozen_problem)
            after = run_campaign(args, case, 'T2', perturbed, obs_path, frozen_problem)
            results['T2'] = {**qualification(case/'T2', after), 'restriction': restricted, 'excluded_T1_translation_mm': first,
                             'preexisting_feasibility_witness': results['T1_feasibility_witness']}
            verify_freeze(snapshot)

    domain_path, _, _, profile = authority('workholding')
    sealed = values_for_witness(profile, load(domain_path))
    invalid = {
        'translation': {**sealed, 'translation_mm': [999, 0, 0]},
        'radius': {**sealed, 'bend_radius_mm': 3.5},
        'endpoint': {**sealed, 'route_points_mm': [[14, 3, 0], *sealed['route_points_mm'][1:]]},
        'support': {**sealed, 'anchor': 'unmeasured'},
        'pinout': {**sealed, 'pinout': {'ma1': 'pa2'}},
        'cache': {**sealed, 'cache': {'status': 'PASS'}},
    }
    faults = area / 'adversarial'
    faults.mkdir()
    results['T4'] = {label: check_plan(args, faults/label, profile, proposal(domain_path, 'deny-'+label, values), 2)
                     for label, values in invalid.items()}
    forged = proposal(domain_path, 'deny-sha', sealed)
    forged['authority_sha256'] = '0' * 64
    results['T4']['authority_sha256'] = check_plan(args, faults/'sha', profile, forged, 2)
    verify_freeze(snapshot)
    write(area/'generalization.json', {'schema': 'v3.c.generalization/1', 'freeze': artifact(area/'perturbation_freeze.json'),
                                       'phases': results})
    return 0 if all(results.get(phase, {}).get('verdict') == 'V3_C_PASS' and len(results[phase]['discovered_poses']) >= 3
                    for phase in ('T1', 'T2', 'T3')) else 4


if __name__ == '__main__':
    raise SystemExit(main())
