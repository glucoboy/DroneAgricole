"""Contre-mesure sur les fermetures sauvegardées d'un rejeu V3 scellé."""

import argparse
from datetime import datetime, timezone
import math
import os
from pathlib import Path
import shutil
import stat
import subprocess

from replay_v3_b1 import ROOT, digest, load, write


PROFILES = ROOT / 'docs/electromechanical_v3'
MEASURER = ROOT / 'convergence_manager/native/v3_cross_measure.py'
PROFILE_FILES = [PROFILES / path for path in ('bench_b1_c4/profile.json', 'bench_b1_workholding/profile.json',
                                             'bench_b2_variations.json', 'bench_c1_coupled/profile.json',
                                             'bench_c1_coupled_secondary/profile.json')]
# Les tolérances de distance, angle et volume viennent du profil scellé.
# L'égalité des aires calculées par deux opérations OCC admet 1e-6 mm².
AREA_TOLERANCE_MM2 = 1e-6


def artifact(path):
    return {'path': path.relative_to(ROOT).as_posix(), 'sha256': digest(path)}


def invoke(output, name, argv, timeout=120):
    started = datetime.now(timezone.utc).isoformat()
    result = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True, encoding='utf-8', errors='replace',
                            timeout=timeout, env=dict(os.environ, QT_QPA_PLATFORM='offscreen', PYTHONUTF8='1'))
    write(output / f'{name}-invocation.json', {'argv': argv, 'started_utc': started, 'exit_code': result.returncode,
          'program_sha256': digest(Path(argv[0])), 'stdout': result.stdout, 'stderr': result.stderr})
    return result


def closure(root, expected):
    observed = {path.relative_to(root).as_posix(): digest(path) for path in root.rglob('*.FCStd')}
    if observed != expected:
        raise ValueError(f'Fermeture XLink divergente : {root}')


def measurement(freecad, case, stage, source, dependencies, profile_path):
    closure(source, dependencies)
    copy = case / f'{stage}-copy'
    for name in dependencies:
        target = copy / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / name, target)
        target.chmod(stat.S_IREAD)
    path = case / f'{stage}-observation.json'
    result = invoke(case, stage, [str(freecad), '-B', str(MEASURER), '--root', str(copy),
                                  '--profile', str(profile_path), '--output', str(path)])
    closure(source, dependencies)
    closure(copy, dependencies)
    if result.returncode or not path.is_file():
        raise RuntimeError(f'Contre-mesure non finalisée : {case.name}/{stage} (code {result.returncode})')
    report = load(path)
    if (report['schema'] != 'v3.cross_measurement/1' or report['profile_sha256'] != digest(profile_path) or
            report['worker_sha256'] != digest(MEASURER) or report['inputs_sha256'] != dependencies or
            report['source_sha256'] != load(profile_path)['dependencies']):
        raise ValueError(f'Provenance de contre-mesure incohérente : {path}')
    return report, path


def matrix(pose):
    x, y, z, w = pose['rotation_xyzw']
    tx, ty, tz = pose['translation_mm']
    return [1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w), tx,
            2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w), ty,
            2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y), tz, 0, 0, 0, 1]


def multiply(left, right):
    return [sum(left[4*row+i]*right[4*i+col] for i in range(4)) for row in range(4) for col in range(4)]


def inverse_rigid(pose):
    inverse = [pose[4*col+row] if row < 3 and col < 3 else 0.0 for row in range(4) for col in range(4)]
    for row in range(3):
        inverse[4*row+3] = -sum(inverse[4*row+col]*pose[4*col+3] for col in range(3))
    inverse[15] = 1.0
    return inverse


def angle_between(left, right):
    if len(left) != 3 or len(right) != 3 or not math.isclose(math.hypot(*left), 1, abs_tol=1e-7) or not math.isclose(
            math.hypot(*right), 1, abs_tol=1e-7):
        return None
    cosine = sum(a*b for a, b in zip(left, right))
    return math.degrees(math.acos(max(-1, min(1, cosine))))


def pose_errors(actual, expected):
    distance = math.dist([actual[i] for i in [3, 7, 11]], [expected[i] for i in [3, 7, 11]])
    trace = sum(actual[i]*expected[i] for i in [0, 1, 2, 4, 5, 6, 8, 9, 10])
    angle = math.degrees(math.acos(max(-1, min(1, (trace-1)/2))))
    return distance, angle


def pair_id(pair):
    return tuple(sorted(name.split('#', 1)[-1] for name in pair))


class Assessment:
    def __init__(self, profile):
        model = profile['model']
        self.companions = model.get('moving_with', {})
        self.rules = model['validation']
        self.paths = model['occurrences']
        limits = self.rules['tolerances']
        self.position = limits['position_mm']
        self.angle = limits['direction_deg']
        self.volume = limits['volume_mm3']
        self.distance = limits['distance_mm']
        self.rows = []

    def add(self, identifier, status, observed, criterion):
        self.rows.append({'id': identifier, 'status': status, 'observed': observed, 'criterion': criterion})

    def boolean(self, identifier, passed, observed, criterion):
        self.add(identifier, 'PASS' if passed else 'FAIL', observed, criterion)

    def limit(self, identifier, value, *, lower=None, upper=None, unit):
        criterion = {'minimum': lower, 'maximum': upper, 'unit': unit}
        if not isinstance(value, (int, float)) or not math.isfinite(value):
            self.add(identifier, 'INCONCLUSIVE', value, criterion)
            return
        self.boolean(identifier, (lower is None or value >= lower) and (upper is None or value <= upper), value, criterion)

    def pose(self, identifier, actual, expected):
        distance, angle = pose_errors(actual, expected)
        self.limit(f'{identifier}/position', distance, upper=self.position, unit='mm')
        self.limit(f'{identifier}/angle', angle, upper=self.angle, unit='deg')

    def placements(self, baseline, observed, actions):
        records = observed['occurrences']
        for action in actions:
            params = action['parameters']
            operation = action['operation']
            subject = action['occurrence']
            key = self.paths[params.get('support', subject)]
            if operation == 'REROUTE_HARNESS':
                continue
            expected = matrix(params['placement'])
            if operation in {'RELOCATE_SUPPORT', 'CREATE_SUPPORT'}:
                expected = multiply(records[self.paths[params['anchor']]]['matrix'], expected)
            elif params['frame'] == 'PARENT':
                expected = multiply(baseline['parent_matrices'][key.rsplit('/', 1)[0]], expected)
            self.pose(f'pose/{subject}', records[key]['matrix'], expected)
            if operation == 'REPOSITION_DEVICE' and any('datum' in port for port in self.rules['ports'].values()):
                original = baseline['occurrences']
                delta = multiply(expected, inverse_rigid(original[key]['matrix']))
                for companion in self.companions.get(subject, []):
                    path = self.paths[companion]
                    self.pose(f'pose/{subject}/companion/{companion}', records[path]['matrix'],
                              multiply(delta, original[path]['matrix']))
        if 'sibling' in self.paths:
            key = self.paths['sibling']
            retained, original = records[key], baseline['occurrences'][key]
            self.pose('sibling', retained['matrix'], original['matrix'])
            self.boolean('sibling/definition-and-shape',
                         retained['definition'] == original['definition'] == records[self.paths['payload']]['definition'] and
                         retained['shape_sha256'] == original['shape_sha256'], retained['definition'], original['definition'])

    def topology(self, observed):
        for name, authority in self.rules['ports'].items():
            port = observed['ports'][name]
            carrier = observed['occurrences'][self.paths[authority['equipment']]]['matrix']
            self.pose(f'port/{name}/wire-exit', port['matrix'], multiply(carrier, matrix(authority['local_pose'])))
            if 'datum' in authority:
                datum = port.get('datum')
                definition = port.get('datum_definition', '')
                self.boolean(f'port/{name}/native-datum', isinstance(datum, str) and datum != authority['frame'] and
                             datum.split('/')[-1] == authority['datum'] and definition.endswith('#' + authority['datum']),
                             [datum, definition], authority['datum'])
                self.pose(f'port/{name}/independent-attachment', port['attachment_matrix'], port['matrix'])
                for key, local in [('normal', authority['outward_local']),
                                   ('outward', authority.get('tangent_local', authority['outward_local']))]:
                    direction = [sum(port['matrix'][4*row+col]*local[col] for col in range(3)) for row in range(3)]
                    self.limit(f'port/{name}/{key}', angle_between(port.get(key, []), direction), upper=self.angle, unit='deg')
            for frame in authority['mating_frames']:
                path = frame['path']
                actual = observed['occurrences'][path]['matrix']
                self.pose(f'port/{name}/{path}', actual, multiply(carrier, matrix(frame['local_pose'])))
        contacts = observed['contacts']
        conductors = observed['conductors']
        required_contact_ids = set(self.rules['contacts']) | {row['receptacle'] for row in self.rules['contacts'].values()}
        self.boolean('contact/coverage', set(contacts) == required_contact_ids, sorted(contacts), sorted(required_contact_ids))
        for name, authority in self.rules['contacts'].items():
            contact = contacts[name]
            expected = [authority['pin'], authority['receptacle']]
            actual = [contact['pin'], contact['mate']]
            self.boolean(f'contact/{name}/pin-mate', actual == expected, actual, expected)
            self.limit(f'contact/{name}/mating-gap', contact['mating_gap_mm'], upper=self.distance, unit='mm')
        self.boolean('conductor/coverage', set(conductors) == set(self.rules['nets']), sorted(conductors), sorted(self.rules['nets']))
        for name, authority in self.rules['nets'].items():
            actual = conductors[name]
            ends = actual['endpoints']
            self.boolean(f'conductor/{name}/continuity', actual['route'] == authority['route'] and
                         sorted(end['contact'] for end in ends) == sorted(authority['contacts']) and
                         all(end['reciprocal'] for end in ends), [end['contact'] for end in ends], authority['contacts'])
            for index, end in enumerate(ends):
                self.limit(f'conductor/{name}/endpoint{index}', end['gap_mm'], upper=self.distance, unit='mm')

    def routes(self, baseline, observed, actions):
        requested = {action['occurrence']: action['parameters'] for action in actions if action['operation'] == 'REROUTE_HARNESS'}
        for name, rule in self.rules['routes'].items():
            route = observed['routes'][name]
            straight = (route['radius_evidence'] == 'ANALYTIC' and route['minimum_radius_mm'] is None and
                        all(edge['type'] == 'Line' for edge in route['edges']))
            if straight and name not in requested:
                self.add(f'route/{name}/minimum-radius', 'PASS', 'RECTILIGNE', {'minimum_mm': rule['minimum_radius_mm']})
            else:
                self.limit(f'route/{name}/minimum-radius', route['minimum_radius_mm'], lower=rule['minimum_radius_mm']-self.distance, unit='mm')
            if name in requested:
                radius = route['minimum_radius_mm']
                self.limit(f'route/{name}/radius-change', None if radius is None else abs(radius-requested[name]['bend_radius_mm']),
                           upper=self.distance, unit='mm')
            self.limit(f'route/{name}/diameter', abs(route['diameter_mm']-rule['diameter_mm']), upper=self.distance, unit='mm')
            if 'minimum_length_mm' in rule or 'maximum_length_mm' in rule:
                self.limit(f'route/{name}/length', route['length_mm'], lower=rule['minimum_length_mm'],
                           upper=rule['maximum_length_mm'], unit='mm')
            self.limit(f'route/{name}/saved-sweep', route['sweep_difference_mm3'], upper=self.volume, unit='mm³')
            sections = rule.get('conductor_sections_mm2', baseline['routes'][name]['conductor_sections_mm2'])
            if not sections and name in requested:
                params = requested[name]
                sections = params.get('conductor_sections_mm2')
                if sections is None:
                    ends = sum(net['route'] == name for net in self.rules['nets'].values())
                    sections = [params['conductor_section_mm2']] * ends
            self.boolean(f'route/{name}/sections', route['conductor_sections_mm2'] == sections,
                         route['conductor_sections_mm2'], sections)
            for index, port in enumerate(rule['ports']):
                frame = observed['ports'][port]['matrix']
                self.limit(f'route/{name}/endpoint{index}', math.dist(route['endpoints_mm'][index], [frame[i] for i in [3, 7, 11]]),
                           upper=self.position, unit='mm')
                if 'datum' in self.rules['ports'][port]:
                    tangent = (route['edges'][0]['start_tangent'] if index == 0 else
                               [-component for component in route['edges'][-1]['end_tangent']])
                    self.limit(f'route/{name}/tangent{index}', angle_between(tangent, observed['ports'][port]['outward']),
                               upper=self.angle, unit='deg')

    def geometry(self, baseline, observed, actions):
        previous = {pair_id(row['pair']): row['intersection_mm3'] for row in baseline['pairs']}
        exemptions = {pair_id([self.paths.get(name, name) for name in rule['parts']]): rule['max_volume_mm3']
                      for rule in self.rules['allowed_interferences']}
        for row in observed['pairs']:
            pair = pair_id(row['pair'])
            self.limit(f'pair/{pair[0]}/{pair[1]}', row['intersection_mm3'], upper=exemptions.get(pair, 0)+self.volume, unit='mm³')
            self.rows[-1]['baseline_mm3'] = previous.get(pair)
        action_ids = {action['id'] for action in actions}
        limits = {pair_id([rule.get('anchor') or rule['object'], obstacle]): rule['clearance_mm']
                  for rule in self.rules['service'] for obstacle in rule['obstacles']}
        for row in observed['service']:
            pair = pair_id(row['pair'])
            required = row['required_action']
            if required is not None and required not in action_ids:
                self.add(f'service/{pair[0]}/{pair[1]}', 'NOT_APPLICABLE', row, f'Activation par {required}')
                continue
            minimum = limits.get(pair)
            self.limit(f'service/{pair[0]}/{pair[1]}/volume', row['intersection_mm3'], upper=self.volume, unit='mm³')
            if minimum is None:
                self.add(f'service/{pair[0]}/{pair[1]}/clearance', 'INCONCLUSIVE', row, 'Seuil applicable manquant')
            else:
                self.limit(f'service/{pair[0]}/{pair[1]}/clearance', row['gap_mm'], lower=minimum-self.distance, unit='mm')

    def supports(self, observed, actions):
        selected = {action['parameters'].get('support', action['occurrence']): action['parameters'] for action in actions
                    if action['operation'] in {'RELOCATE_SUPPORT', 'CREATE_SUPPORT'}}
        if not self.rules['supports']:
            self.add('support', 'NOT_APPLICABLE', None, 'Aucun support de maintien dans le modèle C4')
        for name, rule in self.rules['supports'].items():
            if rule.get('created_only') and name not in selected:
                self.add(f'support/{name}', 'NOT_APPLICABLE', None, 'Aucune création de ce support dans le plan scellé')
                continue
            support = observed['supports'][name]
            self.limit(f'support/{name}/bearing-area', support['bearing_area_mm2'], lower=rule['min_contact_area_mm2']-AREA_TOLERANCE_MM2, unit='mm²')
            self.limit(f'support/{name}/gap', support['gap_mm'], upper=self.distance, unit='mm')
            self.limit(f'support/{name}/intersection', support['intersection_mm3'], upper=self.volume, unit='mm³')
            if 'carrier_face' in rule:
                surface = support.get('carrier_face', {})
                self.boolean(f'support/{name}/carrier-face', surface.get('face') == rule['carrier_face'],
                             surface.get('face'), rule['carrier_face'])
                self.limit(f'support/{name}/face-gap', surface.get('gap_mm'), upper=self.position, unit='mm')
                self.limit(f'support/{name}/face-normal', surface.get('normal_error_deg'), upper=self.angle, unit='deg')
                self.limit(f'support/{name}/face-contact', surface.get('bearing_area_mm2'),
                           lower=rule['min_contact_area_mm2']-AREA_TOLERANCE_MM2, unit='mm²')
            anchor = selected.get(name, rule)['anchor']
            self.boolean(f'support/{name}/links', support['anchor'] == self.paths[anchor] and support['carrier'] == self.paths[rule['carrier']] and
                         set(support['retains']) == {self.paths[key] for key in rule['retains']},
                         [support['anchor'], support['carrier'], support['retains']], [anchor, rule['carrier'], rule['retains']])
            for cable in rule['retains']:
                self.limit(f'support/{name}/retention/{cable}', support['retention_gaps_mm'][cable], upper=rule['retention_max_gap_mm'], unit='mm')
            engaged = [row for row in support['fasteners'] if row['intersection_mm3'] > self.volume and row['support_gap_mm'] <= self.distance]
            self.limit(f'support/{name}/fasteners', len(engaged), lower=rule['min_fasteners'], unit='1')


def assessment(profile, baseline, observed, actions):
    checks = Assessment(profile)
    closed = all(row['status'] == 'MEASURED' and row['documents_closed'] and row['sources_unchanged'] and
                 row['copy_unchanged'] and not row['invalid_objects'] and set(row['documents']) == set(profile['dependencies'])
                 for row in [baseline, observed])
    checks.add('xlink', 'PASS' if closed else 'INCONCLUSIVE', observed['documents'], sorted(profile['dependencies']))
    if closed:
        checks.placements(baseline, observed, actions)
        checks.topology(observed)
        checks.routes(baseline, observed, actions)
        checks.geometry(baseline, observed, actions)
        checks.supports(observed, actions)
    return checks.rows


def compare(first, third, profile):
    checks = {row['id']: row['details'] for row in first['checks']}
    tolerance = profile['model']['validation']['tolerances']
    comparisons = []

    def difference(name, left, right, limit, unit):
        gap = abs(left-right) if isinstance(left, (int, float)) and isinstance(right, (int, float)) else None
        equal = left == right if gap is None else gap <= limit
        comparisons.append({'id': name, 'status': 'PASS' if equal else 'FAIL', 'b1': left, 'third': right,
                            'difference': gap, 'tolerance': limit, 'unit': unit})

    for subject, route in third['routes'].items():
        original = checks['L4_DYNAMIC_BEND_RADIUS'][subject]
        for field in ['length_mm', 'minimum_radius_mm']:
            difference(f'{subject}/{field}', original[field], route[field], tolerance['distance_mm'], 'mm')
    for subject, support in third['supports'].items():
        original = checks['L4_SUPPORT_ANCHOR'][subject]
        difference(f'{subject}/bearing_area', original['bearing_area_mm2'], support['bearing_area_mm2'], AREA_TOLERANCE_MM2, 'mm²')
        difference(f'{subject}/gap', original['gap_mm'], support['gap_mm'], tolerance['distance_mm'], 'mm')
    for domain, earlier, later in [('geometry', checks['L4_GEOMETRY']['pairs'], third['pairs']),
                                  ('service', checks['L4_SERVICE'], third['service'])]:
        indexed = {pair_id(row['pair']): row for row in later}
        for old in earlier:
            pair = pair_id(old['pair'])
            subject = f'{domain}/{pair[0]}/{pair[1]}'
            if pair not in indexed:
                comparisons.append({'id': subject, 'status': 'INCONCLUSIVE', 'reason': 'Paire B.1 absente de la contre-mesure'})
                continue
            current = indexed[pair]
            difference(subject+'/volume', old.get('intersection_volume_mm3'), current['intersection_mm3'], tolerance['volume_mm3'], 'mm³')
            difference(subject+'/gap', old.get('clearance_mm'), current['gap_mm'], tolerance['distance_mm'], 'mm')
    for name, row in checks['L2_TOPOLOGY']['contacts'].items():
        difference(f'pin/{name}', row['observed_pin'], third['contacts'][name]['pin'], 0, '1')
    for name, rule in profile['model']['validation']['ports'].items():
        if 'datum' not in rule:
            continue
        original = checks['L2_TOPOLOGY']['ports'][name]
        independent = third['ports'][name]
        position, angle = pose_errors(original['matrix'], independent['matrix'])
        difference(f'port/{name}/datum', original['datum'], independent['datum'], 0, '1')
        difference(f'port/{name}/position', 0, position, tolerance['position_mm'], 'mm')
        difference(f'port/{name}/orientation', 0, angle, tolerance['direction_deg'], 'deg')
    return comparisons


def validator(status, contract, tool, path, mode='DIRECT'):
    return {'status': status, 'mode': mode, 'contract': contract, 'tool': tool, 'receipt': artifact(path) if path else None}


def case_result(args, area, replay, profiles):
    candidate_id = replay['plan_id']
    case = area / candidate_id
    case.mkdir()
    receipt = ROOT / replay['receipt']
    if digest(receipt) != replay['sha256']:
        raise ValueError(f'Reçu B.1 divergent : {receipt}')
    transaction = receipt.parent
    native, plan = load(receipt), load(transaction / 'mutation-plan.json')
    proposal = native['plan_sha256']
    if plan['schema'] == 'v3.mutation_plan/2':
        expanded_path = transaction / 'expanded-plan.json'
        if digest(expanded_path) != native['expanded_plan_sha256'] or plan['domain_sha256'] != native['domain_sha256']:
            raise ValueError(f'Expansion d’admission divergente : {receipt}')
        plan = load(expanded_path)
    profile_path = profiles[plan['profile_sha256']]
    profile = load(profile_path)
    origin = ROOT / profile['source']
    dependencies = profile['dependencies']
    if native['source_integrity']['status'] != 'PASS' or proposal != digest(transaction / 'mutation-plan.json'):
        raise ValueError(f'Identification du référentiel non démontrée : {receipt}')
    closure(origin, dependencies)

    t0 = invoke(case, 't0', [str(args.t0), 'validate', str(transaction), str(ROOT)], timeout=60)
    observed_path = None
    assessments, divergences, blocking = [], [], []
    third_status = 'NOT_RUN'
    if native['construction_result'] == 'PASS':
        baseline, _ = measurement(args.freecad, case, 'baseline', origin, dependencies, profile_path)
        observed, observed_path = measurement(args.freecad, case, 'candidate', transaction / 'cad', native['native_sha256'], profile_path)
        first = load(transaction / 'candidate-validation.json')
        built = load(transaction / 'build.json')
        assert len({observed['pid'], baseline['pid'], first['pid'], built['pid']}) == 4
        assert observed['inputs_sha256'] == first['inputs_sha256'] == built['after_sha256']
        assessments = assessment(profile, baseline, observed, plan['actions'])
        comparisons = compare(first, observed, profile) if observed['status'] == 'MEASURED' else []
        write(case / 'comparisons.json', comparisons)
        divergences = sorted({row['id'] for row in comparisons if row['status'] != 'PASS'})
        blocking = sorted({row['id'] for row in assessments if row['status'] in {'FAIL', 'INCONCLUSIVE'}})
        third_status = 'FAIL' if any(row['status'] == 'FAIL' for row in assessments) else 'INCONCLUSIVE' if blocking else 'PASS'
        if third_status != native['status']:
            divergences.append('B1_TRANSACTION_VS_B2_NATIVE')
    else:
        assert not (transaction / 'cad').exists() and native['candidate_state'] == 'ROLLED_BACK'
        blocking.append(native['reason'])
    write(case / 'assessment.json', assessments)
    closure(origin, dependencies)
    final = native['status']
    if t0.returncode or divergences or (third_status == 'INCONCLUSIVE' and final == 'PASS'):
        final = 'INCONCLUSIVE'
    if t0.returncode:
        blocking.append('T0_VALIDATION_FAILED')
    if final != 'PASS' and (case / 'candidate-copy').exists():
        (case / 'candidate-copy').rename(case / 'quarantine')
    saved = observed_path is not None
    result = dict(schema='v3.candidate_result/1', scope='SYNTHETIC_BENCH', candidate_id=candidate_id,
                  proposal_sha256=proposal, source_model_sha256=dependencies[profile['entry']], native_receipt=artifact(receipt),
                  measurements=artifact(observed_path) if saved else None,
                  validator_by_domain={
                      'B1_TRANSACTION': validator(native['status'], native['schema'], 'convergence_core v3-build', receipt),
                      'B2_NATIVE': validator(third_status, 'v3.cross_measurement/1', 'FreeCAD + v3_cross_measure.py', observed_path),
                      'T0': validator('PASS' if t0.returncode == 0 else 'FAIL', 'drone_agricole.run_manifest.v1',
                                      'cartographe-evidence validate', case / 't0-invocation.json')},
                  independent_disagreements=divergences, blocking_issues=blocking,
                  candidate_state='CANDIDATE' if final == 'PASS' else 'QUARANTINED' if saved else 'ROLLED_BACK',
                  rollback='NOT_REQUIRED' if final == 'PASS' else 'QUARANTINED_PRIVATE_COPY' if saved else 'DISCARDED_PRIVATE_COPY',
                  coverage={'checks': len(assessments), 'comparison': artifact(case / 'comparisons.json') if saved else None,
                            'assessment': artifact(case / 'assessment.json'), 'fixed_scope': 'SYNTHETIC_BENCH'},
                  cost_proxy=None, final_verdict=final)
    output = case / 'candidate-result.json'
    write(output, result)
    print(candidate_id, final, len(divergences), len(blocking), flush=True)
    return artifact(output), final == native['status'] and not divergences and t0.returncode == 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for argument in ('replay', 't0', 'freecad', 'output'):
        parser.add_argument('--'+argument, required=True, type=Path)
    args = parser.parse_args()
    args.t0, args.freecad = args.t0.resolve(strict=True), args.freecad.resolve(strict=True)
    area = args.output.resolve()
    assert area.is_relative_to(ROOT / '.runtime')
    area.mkdir(parents=True, exist_ok=False)
    profiles = {digest(path): path for path in PROFILE_FILES}
    cases = [case_result(args, area, row, profiles) for row in load(args.replay)]
    write(area / 'index.json', {'schema': 'v3.b2.cross_replay/1', 'replay': artifact(args.replay.resolve()),
          'profiles': [artifact(path) for path in PROFILE_FILES], 'results': [path for path, _ in cases]})
    return 0 if cases and all(passed for _, passed in cases) else 2


if __name__ == '__main__':
    raise SystemExit(main())
