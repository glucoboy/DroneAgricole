"""FreeCAD measurement adapter for the independent L4 validator."""

import argparse
import os
from pathlib import Path
import subprocess
import sys

from electromechanical_engine.contracts import digest_value, load, validate_requirements, validate_system, write
from electromechanical_engine.freecad import FreeCADAdapter, FreeCADError, PROJECT, guard
from electromechanical_engine.metrics import measure, render_views
from electromechanical_engine.qualification import native_replay as history
from electromechanical_engine.search import explore


ENTRY = history.ENTRY
FIXTURES = 'electromechanical_engine/tests/fixtures'
VIEW_NAMES = {'profil_xz': 'profil-x', 'profil_yz': 'profil-y'}


def artifact(path, root):
    return {'artifact_path': path.relative_to(root).as_posix(), 'sha256': guard.sha256(path)}


def save_json(path, data):
    pending = path.with_suffix('.pending.json')
    write(pending, data)
    pending.replace(path)


def bench_plan(workspace, config):
    if 'frozen_model' in config:
        if config['mode'] != 'candidate':
            raise ValueError('Le modèle gelé externe est réservé à un natif déjà sauvegardé.')
        model = config['frozen_model']
        system = load(guard.relative_file(workspace, model['system']))
        requirements = load(guard.relative_file(workspace, model['requirements']))
        obstacles = config.get('xlink_obstacles')
        bindings = None
        if obstacles is not None:
            if (not isinstance(obstacles, list) or not obstacles or any(
                    not isinstance(item, dict) or set(item) != {'box', 'occurrence', 'definition'}
                    or not isinstance(item['box'], dict) or not isinstance(item['box'].get('id'), str)
                    or not all(isinstance(item[key], str) and item[key]
                               for key in ('occurrence', 'definition')) for item in obstacles)):
                raise ValueError('Les obstacles XLink exigent un volume et deux identités natives gelés.')
            system['geometry']['boxes'].extend(item['box'] for item in obstacles)
            bindings = {item['box']['id']: {key: item[key] for key in ('occurrence', 'definition')}
                        for item in obstacles}
        validate_system(system)
        validate_requirements(system, requirements)
        plan = {'system': system, 'requirements': requirements, 'candidate': {}}
        if bindings is not None:
            plan['xlink_obstacles'] = bindings
        return plan
    if 'xlink_obstacles' in config:
        raise ValueError('Les obstacles XLink exigent un référentiel de géométrie externe gelé.')
    fixture = workspace / FIXTURES / config['fixture']
    system = load(fixture / 'system_model.json')
    requirements = load(fixture / 'design_requirements.yaml')
    space = load(fixture / 'design_space.json')
    for key, additions in config.get('geometry_additions', {}).items():
        system['geometry'].setdefault(key, []).extend(additions)
    for box in system['geometry']['boxes']:
        if box['id'] in config.get('translated_boxes', {}):
            delta = config['translated_boxes'][box['id']]
            box['origin_mm'] = [x + dx for x, dx in zip(box['origin_mm'], delta, strict=True)]
    requirements.update(config.get('requirements', {}))
    reference = digest_value({'system': system, 'requirements': requirements})
    candidates = explore(system, space, reference, requirements)['candidates']
    candidate = next(item for item in candidates if item['id'] == config['alternative'])
    return {'system': system, 'requirements': requirements, 'candidate': candidate}


def freeze_manifest(workspace, configuration):
    """Resolve previously recorded authoritative hashes, without loading native objects."""
    historical = load(workspace / configuration['historical_integrity'])['sha256_avant']
    baseline = load(workspace / configuration['baseline_manifest'])
    for group in baseline['references'].values():
        for record in group:
            historical.setdefault(record['path'], record['sha256'])
    return historical


def history_paths(workspace, config, configuration):
    root = guard.inside(workspace, workspace / config['source'])
    extra = config.get('extra', [])
    frozen = freeze_manifest(workspace, configuration)
    receipt = config.get('historical_receipt')
    if receipt:
        path = guard.relative_file(workspace, receipt['path'])
        if guard.sha256(path) != receipt['sha256']:
            raise ValueError('Le reçu historique diverge de son empreinte publiée.')
        report = load(path)
        for key in receipt.get('table', ['native_inputs_sha256']):
            report = report[key]
        frozen = {f'{config["source"]}/{name}': digest for name, digest in report.items()}
    files = guard.dependencies(root, [config['entry'], *extra])
    expected = {path.relative_to(root).as_posix(): frozen[path.relative_to(workspace).as_posix()]
                for path in files}
    return root, config['entry'], extra, expected


def staged_input(workspace, config, configuration, candidate, adapter, output, evidence):
    mode = config['mode']
    plan = None
    if mode in ('bench', 'candidate'):
        plan = bench_plan(workspace, config)
        if mode == 'bench':
            # The existing builder runs independently from the two measurement workers.
            root = output / 'built'
            built = adapter.build(plan, root)
            evidence['saved_process'] = {'pid': built['saved_process'],
                                         'worker_id': built['saved_worker_id']}
            entry = 'candidate.FCStd'
        else:
            if candidate is None or not candidate.is_file():
                raise FileNotFoundError('Un natif sauvegardé est requis pour ce périmètre.')
            entry, root = candidate.name, candidate.parent
        extra, expected = [], None
    elif mode == 'l2':
        native = guard.relative_file(workspace, config['native'])
        root, entry, extra = native.parent, native.name, []
        expected = {entry: load(workspace / config['manifest'])['assembly']['sha256']}
    else:
        root, entry, extra, expected = history_paths(workspace, config, configuration)

    copy = output / 'staged'
    receipt = guard.stage(root, entry, copy, extra)
    before = receipt['inputs_sha256']
    if expected is not None and before != expected:
        changed = sorted(key for key in before.keys() | expected.keys()
                         if before.get(key) != expected.get(key))
        raise ValueError(f'La fermeture historique diverge du gel : {changed}')
    return receipt, plan


def source_manifest(receipt, workspace):
    root = Path(receipt['source_root'])
    before = receipt['inputs_sha256']
    after = {name: guard.sha256(root / name) if (root / name).is_file() else None for name in before}
    copy = Path(receipt['copy_root'])
    unchanged = all((copy / name).is_file() and guard.sha256(copy / name) == digest
                    for name, digest in before.items())
    prefix = root.relative_to(workspace).as_posix() if root.is_relative_to(workspace) else None
    return {'source_root_relative': prefix, 'before': before, 'after': after}, before == after, unchanged


def worker(adapter, output, copy, entry, config, configuration, workspace, index):
    request = output / f'request-{index}.json'
    result = output / f'measurement-{index}.json'
    trace = output / f'freecad-{index}.log'
    write(request, {'copy': str(copy), 'entry': entry, 'config': config,
                    'configuration': configuration, 'workspace': str(workspace)})
    env = dict(os.environ, QT_QPA_PLATFORM='offscreen', PYTHONUTF8='1', PYTHONPATH=str(PROJECT))
    with trace.open('wb') as diagnostics:
        execution = subprocess.run(
            [str(adapter.python), '-B', '-m', 'electromechanical_engine.qualification.l4_native',
             '--worker', str(request), str(result)], cwd=copy, env=env, stdout=diagnostics,
            stderr=subprocess.STDOUT, timeout=adapter.timeout, check=False,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    if execution.returncode != 0 or not result.is_file():
        raise FreeCADError(f'Mesure FreeCAD interrompue, code {execution.returncode} ({trace.name})')
    return load(result), artifact(result, output)


def interval_from_segments(route, zone):
    """Conservative length interval by native edge bounding boxes, in millimetres."""
    full, crossing = [], []
    for segment in route['segments']:
        lo, hi = segment['bounds_mm']
        if any(end < low or start > high for start, end, low, high in zip(lo, hi, *zone, strict=True)):
            continue
        if all(low <= start <= end <= high for start, end, low, high in zip(lo, hi, *zone, strict=True)):
            full.append(segment['length_mm'])
        else:
            crossing.append(segment['length_mm'])
    return sum(full), sum(full) + sum(crossing)


def bench_metrics(measured, plan, config):
    report = measure(plan['system'], plan['requirements'], measured, plan['candidate'])
    values = {}
    for key, value in report['values'].items():
        unit = 'mm3' if key.endswith('_mm3') else 'mm' if key.endswith('_mm') else '1'
        values[key] = {'value': value, 'unit': unit, 'method': report['methods']['route']}
    route_ids = report['scope']['link_ids']
    for key in ('total_length_mm', 'max_cable_z_mm'):
        values[key]['scope'] = {'route_ids': route_ids}
    if 'upper_zone' in config:
        zone = config['upper_zone']
        intervals = [interval_from_segments(route, zone) for route in measured['route_metrics'].values()
                     if route.get('segments')]
        if len(intervals) == len(plan['system']['links']):
            lower = sum(a for a, _ in intervals)
            upper = sum(b for _, b in intervals)
            values['upper_zone_axis_length_mm'] = {
                'value': lower if lower == upper else None, 'unit': 'mm', 'lower_bound': lower,
                'upper_bound': upper, 'zone_mm': zone,
                'scope': {'minimum_z_mm': zone[0][2], 'route_ids': route_ids},
                'method': 'Bornes de longueur par inclusion ou séparation des boîtes d’arêtes natives'}
    measured['architecture_metrics'] = values


def measure_native(args, config, configuration, adapter, evidence):
    receipt, plan = staged_input(args.workspace, config, configuration, args.candidate, adapter,
                                 args.output, evidence)
    copy, entry = Path(receipt['copy_root']), receipt['entry']
    evidence['native_sha256'] = receipt['inputs_sha256'][entry]
    evidence['native_entry'] = entry
    evidence['attempts'] = []
    observations = []
    try:
        for index in (1, 2):
            if plan is None:
                result, file_info = worker(adapter, args.output, copy, entry, config, configuration,
                                           args.workspace, index)
            else:
                result = adapter.inspect(copy / entry, plan)
                report = args.output / f'measurement-{index}.json'
                write(report, result)
                file_info = artifact(report, args.output)
            process = {key: result.pop(key) for key in ('pid', 'worker_id') if key in result}
            evidence['attempts'].append({**process, **file_info})
            observations.append(result)
    finally:
        manifest, sources_unchanged, copies_unchanged = source_manifest(receipt, args.workspace)
        evidence.update(source_manifest=manifest, sources_unchanged=sources_unchanged,
                        copies_unchanged=copies_unchanged)
    first, second = observations
    a, b = evidence['attempts']
    evidence['repeat_exact'] = first == second and a['pid'] != b['pid']
    if not (evidence['repeat_exact'] and sources_unchanged and copies_unchanged):
        raise FreeCADError('Les deux mesures ou les empreintes après contrôle divergent.')
    freecad = first.get('freecad')
    cables = first.get('cables') or {}
    l2 = first.get('l2_environment') or {}
    versions = {'FreeCAD': '.'.join(freecad[:3]) if isinstance(freecad, list) else freecad,
                'Python': first.get('python'),
                'OCCT': first.get('occt') or first.get('shape_validation', {}).get('occt'),
                'Cables Workbench': cables.get('version') or l2.get('cables_version')}
    evidence['environment'] = {key: value for key, value in versions.items() if isinstance(value, str) and value}
    if plan is not None:
        bench_metrics(first, plan, config)
    if 'view_frame_mm' in config:
        # The L2 reader has already independently checked native fixture bodies. It reports
        # interface geometry only, so use those observations for the projection scope.
        projection = first if plan is not None else {**first, 'recompute_ok': True,
                                                     'broken_links': [], 'invalid_objects': []}
        requirements = plan['requirements'] if plan is not None else {}
        views = render_views(projection, args.output / 'views', requirements, config['view_frame_mm'])
        if config['mode'] == 'l2':
            connectors = {**projection, 'view_objects': [obj for obj in first['view_objects']
                                                         if obj['role'] == 'connector']}
            detail = render_views(connectors, args.output / 'views' / 'connecteurs',
                                  requirements, config['view_frame_mm'])
            if 'dessus' in detail['files']:
                views['files']['connecteurs'] = 'connecteurs/' + detail['files']['dessus']
        first['views'] = {VIEW_NAMES.get(name, name): artifact(args.output / 'views' / path, args.output)
                          for name, path in views['files'].items()}
        first['view_frame_id'] = config['view_frame_id']
        first['view_frame_mm'] = views['frame_mm']
        first['missing_views'] = views['missing_views']
    return first


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', type=Path, required=True)
    parser.add_argument('--reference', type=Path, required=True)
    parser.add_argument('--case', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--freecad-python', type=Path, required=True)
    parser.add_argument('--candidate', type=Path)
    parser.add_argument('--timeout', type=int, default=110)
    args = parser.parse_args()
    args.workspace = args.workspace.resolve(strict=True)
    args.output = args.output.resolve()
    if args.candidate is not None:
        args.candidate = args.candidate.resolve()
    return args


def main():
    args = parse_args()
    configuration = load(args.reference)
    config = configuration['cases'][args.case]
    args.output.mkdir(parents=True, exist_ok=False)
    evidence = {'state': 'INCOMPLETE', 'scope': config['scope'], 'adapter_sha256': guard.sha256(__file__)}
    record = {'schema_version': 1, 'case_id': args.case, 'native_evidence': evidence, 'measurements': {}}
    adapter = FreeCADAdapter(args.freecad_python, args.timeout)
    try:
        if args.candidate is not None and config['mode'] != 'candidate':
            raise ValueError('Ce périmètre gelé ne prend aucun candidat externe.')
        probe = adapter.probe()
        evidence['probe'] = probe
        if not probe['verified']:
            evidence['state'] = 'UNAVAILABLE'
        else:
            record['measurements'] = measure_native(args, config, configuration, adapter, evidence)
            evidence['state'] = 'MEASURED'
    except (FileNotFoundError, KeyError) as exc:
        evidence.update(state='UNAVAILABLE', reason=str(exc))
    except (FreeCADError, OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
        evidence['reason'] = str(exc)
    save_json(args.output / 'observation.json', record)
    return 0 if evidence['state'] == 'MEASURED' else 3


if __name__ == '__main__':
    if len(sys.argv) == 4 and sys.argv[1] == '--worker':
        from electromechanical_engine.qualification.l4_native_worker import run
        run(Path(sys.argv[2]), Path(sys.argv[3]))
    raise SystemExit(main())
