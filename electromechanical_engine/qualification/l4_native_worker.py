"""Read saved BRep and FreeCAD L2 objects in an isolated worker process."""

import os
from pathlib import Path
import sys
from uuid import uuid4

import FreeCAD as App
import Part

from electromechanical_engine.contracts import load, write
from electromechanical_engine.freecad import guard, load_helper
from electromechanical_engine.freecad_worker import cables_environment, geometry
from electromechanical_engine.qualification import native_replay as history


def pair(shape_a, shape_b, a, b):
    result = geometry.inspect_pair(shape_a, shape_b, a, b)
    return {'a': a, 'b': b, 'intersection_mm3': result.get('intersection_volume_mm3'),
            'clearance_mm': result.get('clearance_mm'), 'measurement': result}


def history_config(workspace, configuration):
    zones = load(workspace / configuration['zones'])['zones_mm']
    return {'zones_mm': zones}


def radius(copy, config):
    cases = history.reopened_f16(copy, geometry, App)
    measured = cases[config['variant']]
    axis = measured['axis']
    solid = measured.get('regeneration_after_cache_clear', measured['solid'])
    route = {'min_radius_mm': axis['minimum_radius_mm'],
             'radius_certified': axis['radius_evidence'] == 'analytic_lines_circles',
             'length_mm': axis['length_mm'],
             'continuity_ok': not {'route_measurement_error', 'discontinuous_wire'} & set(axis['failures']),
             'tangency_ok': not {'route_measurement_error', 'non_tangent_join'} & set(axis['failures']),
             'solid_valid': solid['status'] == 'pass', 'solid_measurement': solid, 'measurement': axis}
    return {'reopened': True, 'route_metrics': {'F16': route}, 'f16_diagnostics': measured}


def opening(copy, entry):
    doc = App.openDocument(str(copy / entry))
    try:
        observed = {Path(item.FileName).resolve().relative_to(copy).as_posix(): bool(item.Partial)
                    for item in App.listDocuments().values()}
        expected = {path.relative_to(copy).as_posix() for path in guard.dependencies(copy, [entry])}
        return {'reopened': True, 'inventory_complete': expected == observed.keys() and not any(observed.values()),
                'partial_documents': sorted(name for name, partial in observed.items() if partial),
                'missing_documents': sorted(expected - observed.keys()),
                'unexpected_documents': sorted(observed.keys() - expected),
                'root_objects': len(doc.Objects)}
    finally:
        App.closeDocument(doc.Name)


def interconnection(copy, entry, config, workspace):
    adapter = load_helper(workspace / config['adapter'])
    plan, digest = adapter.load_plan(workspace / config['projection'])
    environment = adapter.initialize()
    # The L2 workbench helper expects its standard filename. L4 stages the exact saved bytes.
    if entry != adapter.MODEL:
        raise ValueError('Le nom natif du banc L2 ne correspond pas à la projection gelée.')
    report = adapter.revalidate(plan, digest, copy)
    interfaces = report['interfaces']
    document = App.openDocument(str(copy / entry))
    try:
        view_objects = []
        for item in interfaces:
            for field, role in (('device', 'structure'), ('receptacle', 'connector'),
                                ('plug', 'connector'), ('envelope', 'extraction')):
                name = item[field]
                bounds = adapter.box_bounds(document.getObject(name).Shape)
                view_objects.append({'id': name, 'role': role, 'bounds_mm': [bounds[:3], bounds[3:]]})
            if item.get('tooling'):
                bounds = item['tooling']['bounds_mm']
                view_objects.append({'id': f'outillage-{item["port_id"]}', 'role': 'extraction',
                                     'bounds_mm': [bounds[:3], bounds[3:]]})
    finally:
        App.closeDocument(document.Name)
    return {'reopened': True, 'l2_environment': environment, 'l2_interfaces': interfaces,
            'view_objects': view_objects,
            'mate_poses': {item['port_id']: {key: row['matrix'] for key, row in item['frames'].items()}
                           for item in interfaces},
            'l2_conductors': report['conductors'], 'l2_faults': report['faults']}


def targeted_history(copy, config, workspace):
    verification = workspace / 'hardware/mecanique/cartographe/verification'
    sys.path.insert(0, str(verification))
    from read_brep_prototype import Reader

    reader = Reader(copy)
    if config['operation'] == 'can1':
        dimensions = config['sweep_size_mm']
        sweep = Part.makeBox(*dimensions, App.Vector(*config['sweep_origin_mm']))
        cable = reader.shape(config['assembly'], 'F35')
        measurement = pair(sweep, cable, 'approach_volume', 'F35')
        return {'extraction_evidence': {'CAN1': {'measurements': [measurement],
                 'ignored_ids': [], 'unavailable_ids': []}}, 'sweep_mm': config['sweep_mm'],
                'sweep_size_mm': dimensions, 'sweep_origin_mm': config['sweep_origin_mm']}
    sys.path[:0] = [str(verification / 'refonte_faisceaux'),
                    str(workspace / 'hardware/mecanique/cartographe_refonte_systeme/verification')]
    from adapter_implantation import Scene

    scene = Scene(copy)
    items = {item.name: item for item in scene.items.values()}
    cable = items['F16'].shape
    obstacle = items[config['obstacle']].shape.Solids[config['solid_index']]
    return {'collisions': [pair(cable, obstacle, 'F16', 'Chassis')],
            'obstacle_name': config['obstacle'], 'solid_index_zero_based': config['solid_index']}


def compare_architecture(row):
    axes = row['axes']
    values = {'total_length_mm': {'value': axes['axis_sum_mm'], 'unit': 'mm',
                                  'method': 'Somme des longueurs OCC des axes sauvegardés'},
              'max_cable_z_mm': {'value': axes['height_max_mm'], 'unit': 'mm',
                                 'method': 'Z maximal des boîtes englobantes des gaines'}}
    for key, length in axes['zones_384_mm'].items():
        values[f'zone_{key}_mm'] = {'value': length, 'unit': 'mm', 'certified': False,
                                     'method': 'Discrétisation de 384 points par courbe et découpe par zone'}
    return {'architecture_metrics': values, 'electrical_endpoints_mm': row['electrical_endpoints_mm'],
            'axis_count': axes['count'], 'historical_axes': axes}


def run(request, output):
    job = load(request)
    copy, workspace = Path(job['copy']), Path(job['workspace'])
    config = job['config']
    operation = config['operation']
    cables = cables_environment(False) if operation in ('radius', 'partial') else None
    if operation == 'radius':
        result = radius(copy, config)
    elif operation == 'partial':
        result = opening(copy, job['entry'])
    elif operation == 'l2':
        result = interconnection(copy, job['entry'], config, workspace)
    elif operation in ('can1', 'chassis'):
        result = targeted_history(copy, config, workspace)
    else:
        raw = history.measure(copy, 'a' if operation == 'architecture' else 'f16_targeted',
                              history_config(workspace, job['configuration']))
        if operation == 'pair':
            row = raw['engine_pair_checks'][config['variant']]
            result = {'collisions': [{'a': 'F16', 'b': 'P73', 'clearance_mm': row.get('clearance_mm'),
                                      'intersection_mm3': row.get('intersection_volume_mm3'),
                                      'measurement': row}]}
        elif operation == 'architecture':
            result = compare_architecture(raw)
        else:
            raise ValueError(f'Opération de mesure inconnue : {operation}')
    write(output, {**result, 'pid': os.getpid(), 'worker_id': uuid4().hex, 'backend': 'freecad_python',
                   'freecad': App.Version(), 'occt': Part.OCC_VERSION, 'python': sys.version, 'cables': cables})
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0)
