"""Relire les copies GO3B avec les mesures natives et le référentiel B.2 gelés."""

import argparse
from collections import Counter
from hashlib import sha256
from itertools import combinations
import json
import math
import os
from pathlib import Path
import sys
import traceback


ROOT = Path(__file__).resolve().parents[3]
FROZEN = ROOT / '.runtime/fix-b'
ENTRY = 'assemblages/Prototype_Cartographe.FCStd'
STATUS = {'pass': 'PASS', 'fail': 'FAIL', 'unknown': 'INCONCLUSIVE'}


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def pair_key(a, b):
    return tuple(sorted((a, b)))


def gap(left, right):
    lo, hi = left
    rlo, rhi = right
    return math.hypot(*(max(0, a - d, c - b) for a, b, c, d in zip(lo, hi, rlo, rhi)))


def overlap_size(left, right):
    return math.prod(max(0, min(b, d) - max(a, c)) for a, b, c, d in zip(*left, *right))


def pin(path, expected, guard):
    if guard.sha256(path) != expected:
        raise RuntimeError(f'Empreinte divergente : {path}')
    return path


def metrics(native, records, shapes, objects, zones):
    from electromechanical_engine.qualification.native_replay import clipped_length

    measurements = {}
    for ident in sorted(key for key in shapes if records[key].get('route')):
        record, obj = records[ident], objects[ident]
        wire = native.builder.effective_wire(obj)
        pose = native.App.Matrix()
        pose.A = tuple(record['matrix'])
        world = wire.transformShape(pose.multiply(obj.Placement.inverse().toMatrix()), True, True)
        lengths = {name: [0.0, 0.0] for name in zones}
        for edge in world.Edges:
            lo, hi = edge.ParameterRange
            for index, resolution in enumerate((96, 384)):
                count = 2 if edge.Curve.TypeId == 'Part::GeomLine' else resolution
                points = [edge.valueAt(lo + (hi - lo) * i / (count - 1)) for i in range(count)]
                for name, bounds in zones.items():
                    lengths[name][index] += clipped_length(points, bounds)
        measurements[ident] = {'length_mm': world.Length, 'zone_lengths_mm_96_384': lengths,
                               'sheath_bounds_mm': record['bounds_mm']}
    return {'axis_count': len(measurements),
            'axes': measurements,
            'axis_length_mm': sum(row['length_mm'] for row in measurements.values()),
            'zone_lengths_mm_96_384': {name: [sum(row['zone_lengths_mm_96_384'][name][i]
                                                for row in measurements.values()) for i in (0, 1)]
                                       for name in zones},
            'sheath_top_z_mm': max(row['sheath_bounds_mm'][1][2] for row in measurements.values()),
            'zones_mm': zones}


def replay(args):
    sys.path.insert(0, str(FROZEN))
    from electromechanical_engine import freecad_worker as native
    from electromechanical_engine import xlink_native as xlink

    guard = xlink.guard
    root = guard.inside(ROOT / '.runtime/v21-go3b', args.copy)
    output = guard.inside(ROOT / '.runtime/v21-go3b-validation', args.output)
    output.mkdir(parents=True, exist_ok=True)
    portfolio = read(ROOT / 'docs/verification/v21_go3a_candidates.json')
    dependencies = portfolio['reference']['dependencies']
    coverage = read(pin(ROOT / dependencies['b2']['path'], dependencies['b2']['sha256'], guard))
    model = read(pin(ROOT / dependencies['system_model']['path'], dependencies['system_model']['sha256'], guard))
    pin(ROOT / dependencies['requirements']['path'], dependencies['requirements']['sha256'], guard)
    for path, digest in coverage['baseline_validator_and_inputs_sha256'].items():
        if '/' in path:
            pin(FROZEN / path, digest, guard)
    pin(Path(sys.executable), coverage['baseline_validator_and_inputs_sha256']['freecad_python'], guard)
    artifacts = coverage['artifacts']
    checkpoint_path = pin(ROOT / artifacts['final_checkpoint']['path'], artifacts['final_checkpoint']['sha256'], guard)
    inventory_path = checkpoint_path.parent / 'inventory.result.json'
    before = read(inventory_path)
    historical = read(checkpoint_path)
    campaign = read(pin(ROOT / artifacts['final_campaign']['path'], artifacts['final_campaign']['sha256'], guard))
    # Qt wrote integral coordinates as JSON integers. The original native
    # measurement identity hashes FreeCAD's double precision coordinates.
    for row in before['occurrences'].values():
        if 'matrix' in row:
            row['matrix'] = [float(element) for element in row['matrix']]
        if 'bounds_mm' in row:
            row['bounds_mm'] = [[float(element) for element in corner] for corner in row['bounds_mm']]
    if (xlink.measurement_identity(before['occurrences']) != coverage['measurement_identity_sha256'] or
            before['measurement_identity_sha256'] != coverage['measurement_identity_sha256'] or
            campaign['closure']['saved_sha256'] != before['before_sha256']):
        raise RuntimeError('Inventaire historique B.2 non réconcilié.')
    criteria = coverage['criteria']
    if criteria != campaign['criteria'] or criteria['contacts'] or not criteria['screening_only']:
        raise RuntimeError('Critères du criblage B.2 divergents.')
    base_shapes = {key: row for key, row in before['occurrences'].items() if row['terminal_shape']}
    base_pairs = {pair_key(row['task']['a'], row['task']['b']): row
                  for row in historical['observations'].values() if row['task']['kind'] == 'pair'}
    if len(base_pairs) != coverage['coverage']['expected']:
        raise RuntimeError('Paires historiques B.2 manquantes ou dupliquées.')
    failures = {pair_key(row['a'], row['b']): row for row in coverage['failure_pairs']}
    extras = list(read(ROOT / 'docs/verification/v21_go3a_reference_replay.json')['native']['auxiliary_files'])
    files = guard.dependencies(root, [ENTRY, *extras])
    hashes = {path.relative_to(root).as_posix(): guard.sha256(path) for path in files}
    receipt = {'source_root': str(root), 'copy_root': str(root), 'entry': ENTRY,
               'inputs_sha256': hashes, 'parameters': {'extras': extras}}
    if args.case == 'baseline' and any(hashes.get(k) != v for k, v in model['cad']['native_sha256'].items()):
        raise RuntimeError('La copie témoin diffère du gel.')
    doc, reopening = xlink.reopen(root, receipt, False)
    if reopening['environment'] != before['environment']:
        raise RuntimeError('Environnement de mesure différent de l’environnement B.2.')
    records, shapes, objects = xlink.collect(doc, root, hashes)
    xlink.publish(output / 'inventory.json', {**reopening, 'pid': os.getpid(), 'occurrences': records})
    comparable = ('object', 'definition', 'shape_sha256', 'matrix', 'status', 'visible',
                  'geometry_scope', 'terminal_shape', 'bounds_mm', 'route')
    unchanged = {key for key in shapes.keys() & base_shapes.keys()
                 if all(records[key].get(attr) == base_shapes[key].get(attr) for attr in comparable)}
    changed = shapes.keys() - unchanged
    assumed = {key for key in shapes if records[key]['definition'].split('#')[-1].startswith('ASSUMED_')}
    service = {key for key in assumed if not records[key]['definition'].split('#')[-1].startswith('ASSUMED_Support')}
    unavailable = {key: row.get('reason') for key, row in records.items()
                   if row['visible'] and row['status'] != 'PASS'}
    routes = {key for key, row in records.items() if key in shapes and row.get('route')}
    margins = {key: records[key]['bounds_mm'] for key in shapes}
    cutoff = criteria['clearance_mm'] + criteria['distance_tolerance_mm']
    todo, rows, aabb, geometric_count = [], [], 0, 0
    for a, b in combinations(sorted(shapes), 2):
        key = (a, b)
        if (a not in routes and b not in routes) or a in service or b in service:
            continue
        geometric_count += 1
        margin = gap(margins[a], margins[b])
        if margin > cutoff:
            aabb += 1
            if key in failures:
                rows.append({'pair': key, 'origin': 'AABB_DISJOINT', 'status': 'INCONCLUSIVE',
                             'aabb_gap_mm': margin})
            continue
        if key in base_pairs and a in unchanged and b in unchanged and key not in failures:
            original = base_pairs[key]['observation']
            rows.append({'pair': key, 'origin': 'B2_REUSE_IDENTICAL_BREP', 'status': (
                'INCONCLUSIVE' if original['status'] == 'pass' else STATUS[original['status']]),
                'observation': original})
            continue
        todo.append((key, 'B2_PAIR'))
    for a, b in combinations(sorted(shapes), 2):
        if a in service and b in service:
            continue  # Mutually exclusive envelopes, measured against the installation below.
        if gap(margins[a], margins[b]) > cutoff:
            continue
        if a in service or b in service:
            todo.append(((a, b), 'ASSUMED_SERVICE'))
        elif a not in routes and b not in routes and (a in changed or b in changed):
            todo.append(((a, b), 'CHANGED_SOLID_PAIR'))
    for key in sorted(failures.keys() - {key for key, _ in todo}):
        if any(name not in shapes for name in key):
            rows.append({'pair': key, 'origin': 'MISSING_HISTORICAL_OCCURRENCE', 'status': 'NOT_RUN'})
    todo.sort(key=lambda task: (task[0] not in failures, task[1] == 'ASSUMED_SERVICE',
                               -overlap_size(*(margins[key] for key in task[0])), task[0]))

    def status_summary():
        return {status: sum(row['status'] == status for row in all_rows) for status in STATUS.values()} | {
            'NOT_RUN': sum(row['status'] == 'NOT_RUN' for row in all_rows)}

    xlink.publish(output / 'metrics.json', metrics(native, records, shapes, objects, model['zones_comparaison_mm']))
    baseline_result = output.parents[1] / 'baseline/independent/report.json'
    witnessed_solids = read(baseline_result)['solids'] if args.case != 'baseline' and baseline_result.exists() else {}
    solid_results = {key: witnessed_solids[key] if key in unchanged and key in witnessed_solids
                     else 'PASS' if shape.isValid() and shape.Volume > 0 else 'FAIL'
                     for key, shape in shapes.items()}
    route_results = {key: xlink.route_measurement(records[key], objects[key]) for key in sorted(routes)}
    cache = output / 'measurements'
    cache.mkdir(exist_ok=True)
    performed = Counter()
    all_rows = list(rows)
    deferred = {tuple(read(path)['pair']): path.relative_to(ROOT).as_posix()
                for path in (path.resolve() for path in args.defer_pair_from)}
    for key, scope in todo:
        a, b = key
        group = 'service' if scope == 'ASSUMED_SERVICE' else 'nominal'
        limit = args.service_limit if group == 'service' else args.pair_limit
        token = sha256(json.dumps([key, scope, hashes, [records[k]['shape_sha256'] for k in key]],
                                  sort_keys=True).encode()).hexdigest()
        observation_file = cache / (token + '.json')
        if observation_file.exists():
            item = read(observation_file)
        elif key in deferred:
            item = {'pair': key, 'origin': 'FRESH_REQUIRED', 'scope': scope, 'status': 'NOT_RUN',
                    'reason': 'Calcul BRep différé après blocage du même couple dans le lot précédent.',
                    'previous_checkpoint': deferred[key]}
        elif performed[group] >= limit:
            item = {'pair': key, 'origin': 'FRESH_REQUIRED', 'scope': scope, 'status': 'NOT_RUN'}
        else:
            performed[group] += 1
            print(scope, a, b, flush=True)
            xlink.publish(output / 'current.json', {'pair': key, 'scope': scope, 'pid': os.getpid()})
            try:
                observation = native.measure_pair(shapes[a], shapes[b], a, b, criteria['clearance_mm'],
                                                  criteria['volume_tolerance_mm3'], criteria['distance_tolerance_mm'])
            except (RuntimeError, ValueError, TypeError) as exc:
                observation = {'status': 'unknown', 'reason': str(exc)}
            item = {'pair': key, 'scope': scope, 'origin': 'FRESH_BREP', 'worker_pid': os.getpid(),
                    'status': ('INCONCLUSIVE' if observation['status'] == 'pass' else STATUS[observation['status']]),
                    'observation': observation}
            if key in base_pairs:
                item['historical_observation'] = base_pairs[key]['observation']
            xlink.publish(observation_file, item)
        if any(name in assumed for name in key):
            item = {**item, 'assumed_occurrences': [name for name in key if name in assumed]}
            if item['status'] == 'FAIL':
                item['status'] = 'INCONCLUSIVE'
                item['geometric_conflict_under_assumptions'] = True
        all_rows.append(item)
    if xlink.check_files(root, receipt) != hashes:
        raise RuntimeError('La fermeture sauvegardée a changé durant le rejeu.')
    xlink.publish(output / 'pairs.json', all_rows)
    xlink.publish(output / 'report.json', {
        'schema': 'drone-agricole.v21.go3b.independent-b2.v1', 'case': args.case, 'scope': str(root.relative_to(ROOT)),
        'pid': os.getpid(), 'finalized': True, 'closure': {**reopening, 'unchanged': True},
        'criteria': criteria, 'known_b2_failures': [row for row in all_rows if tuple(row['pair']) in failures],
        'counts': {'eligible_cable_pairs': geometric_count, 'aabb_excluded': aabb, 'retained_and_extra': len(all_rows),
                   'by_origin': dict(Counter(row['origin'] for row in all_rows)), 'by_status': status_summary(),
                   'same_brep_and_pose': len(unchanged), 'changed_or_new_brep_or_pose': len(changed),
                   'removed_visible_solids': len(base_shapes.keys() - shapes.keys()),
                   'routes': len(routes), 'solids': len(shapes), 'solid_status': dict(Counter(solid_results.values())),
                   'service_proxy_count': len(service),
                   'route_status': dict(Counter(STATUS[row['status']] for row in route_results.values()))},
        'observed_failures': [row for row in all_rows if row['status'] == 'FAIL'],
        'assumed_conflicts': [row for row in all_rows if row.get('geometric_conflict_under_assumptions')],
        'unavailable_visible_occurrences': unavailable, 'solids': solid_results, 'routes': route_results,
        'changed_solids': sorted(changed), 'criteria_open': {
            'radius_and_tangency_at_actual_interfaces': 'INCONCLUSIVE', 'mating_and_pin_to_pin': 'NOT_RUN',
            'tool_extraction_and_assembly_sequence': 'NOT_RUN', 'moving_envelope': 'NOT_RUN',
            'thermal_vibration_emc_flight': 'NOT_RUN'},
        'history': {'coverage_sha256': dependencies['b2']['sha256'], 'inventory_sha256': guard.sha256(inventory_path),
                    'measurement_identity_sha256': coverage['measurement_identity_sha256'],
                    'checkpoint_sha256': artifacts['final_checkpoint']['sha256']},
    })
    native.App.closeDocument(doc.Name)


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--case', required=True)
parser.add_argument('--copy', required=True, type=Path)
parser.add_argument('--output', required=True, type=Path)
parser.add_argument('--pair-limit', type=int, required=True)
parser.add_argument('--service-limit', type=int, default=20)
parser.add_argument('--defer-pair-from', type=Path, action='append', default=[])
try:
    replay(parser.parse_args())
except Exception:
    traceback.print_exc()
    sys.stderr.flush()
    os._exit(1)
sys.stdout.flush()
os._exit(0)
