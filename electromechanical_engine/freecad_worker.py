"""Dedicated FreeCAD worker. Execute through FreeCADAdapter, never in the GUI."""

from __future__ import annotations

import inspect
import itertools
import json
import math
import os
from pathlib import Path
import sys
import traceback
from uuid import uuid4

import FreeCAD as App
import Part

from .freecad import BUILDER, SKILL_SCRIPTS, guard, load_helper
from .native_motion import build_motion, measure_motion, motion_cables
from .native_retention import measure as measure_retention


geometry = load_helper(SKILL_SCRIPTS / 'freecad_geometry.py')
builder = load_helper(BUILDER)


def cables_environment(gui):
    if gui:
        import FreeCADGui as Gui

        Gui.showMainWindow()
        Gui.getMainWindow().hide()
    provenance = builder.bootstrap_paths()
    if not gui:
        # Stock Draft only exports this ViewProvider when a GUI is present.
        # Cables subclasses it while restoring proxies in headless FreeCAD.
        import Draft
        from draftviewproviders.view_wire import ViewProviderWire

        Draft.ViewProviderWire = ViewProviderWire
    from freecad.cables import archCable, archCableConduit, compoundPath, wireFlex

    functions = (wireFlex.make_wireflex_from_vectors, archCable.makeCable,
                 compoundPath.make_compoundpath, archCableConduit.makeCableConduit)
    provenance['api'] = {f.__name__: str(inspect.signature(f)) for f in functions}
    paths = [Path(archCableConduit.__file__), Path(compoundPath.__file__)]
    provenance['sha256_modules'].update({p.name: guard.sha256(p) for p in paths})
    return provenance


def vector(value):
    if len(value) != 3 or not all(math.isfinite(x) for x in value):
        raise ValueError(f'Invalid millimetric vector: {value}')
    return App.Vector(*value)


def coordinates(value):
    return [value.x, value.y, value.z]


def bounds(shape):
    box = shape.BoundBox
    return [[box.XMin, box.YMin, box.ZMin], [box.XMax, box.YMax, box.ZMax]]


def tag(obj, ident):
    obj.addProperty('App::PropertyString', 'EngineId', 'Electromechanical')
    obj.EngineId = ident
    obj.Label = ident


def bored_box_shape(spec):
    origin, size = vector(spec['origin_mm']), vector(spec['size_mm'])
    bore = spec['through_bore_x']
    y, z = bore['center_yz_mm']
    tool = Part.makeCylinder(bore['radius_mm'], size.x + 2,
                             App.Vector(origin.x - 1, y, z), App.Vector(1, 0, 0))
    return Part.makeBox(size.x, size.y, size.z, origin).cut(tool)


def add_box(doc, spec):
    size = vector(spec['size_mm'])
    if min(size.x, size.y, size.z) <= 0:
        raise ValueError(f'Nonpositive box dimensions: {spec["id"]}')
    if 'through_bore_x' in spec:
        box = doc.addObject('Part::Feature', 'ReferenceBoredBox')
        box.Shape = bored_box_shape(spec)
        tag(box, spec['id'])
        return
    box = doc.addObject('Part::Box', 'ReferenceBox')
    tag(box, spec['id'])
    box.Length, box.Width, box.Height = size.x, size.y, size.z
    box.Placement.Base = vector(spec['origin_mm'])


def make_route_cable(doc, route, diameter):
    if diameter is None:
        raise ValueError('A known cable diameter is required for construction')
    points = [vector(point) for point in route['points_mm']]
    radius = route.get('bend_radius_mm') or 0
    if radius == 0 and len(points) == 2:
        # The builder requires a fillet parameter even on a straight route.
        radius = diameter
    cable, _ = builder.make_native_cable(doc, None, 'EngineCable', points, diameter, radius)
    fresh = geometry.rebuild_cable_in_isolated_document(doc, cable)
    if fresh['status'] != 'pass':
        raise RuntimeError(f'{cable.Name}: {fresh}')
    return cable


def build(doc, plan):
    for box in plan['system'].get('geometry', {}).get('boxes', []):
        add_box(doc, box)
    for ident, route in sorted(plan['candidate']['routes'].items()):
        diameter = plan['requirements']['links'][ident]['diameter_mm']
        tag(make_route_cable(doc, route, diameter), ident)
    build_motion(doc, plan, make_route_cable)


def recalculate(doc, root):
    documents = list(App.listDocuments().values())
    for document in documents:
        guard.inside(root, document.FileName)
    # Use FreeCAD's topologically sorted XLink closure.
    recomputed = {}
    for dependent in doc.getDependentDocuments():
        result = dependent.recompute()
        if result is False or result < 0:
            raise RuntimeError(f'FreeCAD recompute failed for {dependent.Name}')
        name = Path(dependent.FileName).resolve().relative_to(root).as_posix()
        recomputed[name] = result
    return documents, recomputed


def complete_dependencies(doc, root):
    """Promote native partial XLink loads before evaluating their objects."""
    completed = set()
    while True:
        partial = next((item for item in App.listDocuments().values() if item.Partial), None)
        if partial is None:
            break
        path = guard.inside(root, partial.FileName)
        relative = path.relative_to(root).as_posix()
        if relative in completed or App.openDocument(str(path), True).Partial:
            raise RuntimeError(f'FreeCAD could not fully load dependency {relative}')
        completed.add(relative)
    if completed:
        App.setActiveDocument(doc.Name)
    return sorted(completed)


def check_native_shape(shape, cache, checks):
    bucket = cache.setdefault(hash(shape), [])
    for checked, result in bucket:
        if shape.isEqual(checked):
            checks['exact_cache_hits'] += 1
            return result

    # OCCT 7.8.1 BRepCheck_Analyzer::Put/IsValid adds no constraint of its
    # own to Compound. Check its actual children with inherited placement
    # and orientation. Leave all other topology to the native analyzer.
    if Part.OCC_VERSION == '7.8.1' and shape.ShapeType == 'Compound':
        checks['compound_checks'] += 1
        result = all(check_native_shape(child, cache, checks) for child in shape.childShapes())
    else:
        checks['native_checks'] += 1
        result = shape.isValid()
    bucket.append((shape, result))
    return result


def inventory(documents, root):
    output, invalid, broken, partial = [], [], [], []
    cache = {}
    checks = dict(native_checks=0, compound_checks=0, exact_cache_hits=0)
    for doc in sorted(documents, key=lambda item: item.FileName):
        name = Path(doc.FileName).resolve().relative_to(root).as_posix()
        if doc.Partial:
            partial.append(name)
        objects = []
        for obj in doc.Objects:
            states = list(obj.State)
            record = dict(name=obj.Name, label=obj.Label, type=obj.TypeId, states=states)
            key = f'{name}#{obj.Name}'
            proxy = getattr(obj, 'Proxy', None)
            if proxy is not None:
                record['proxy'] = f'{type(proxy).__module__}.{type(proxy).__name__}'
                if record['proxy'].startswith('freecad.cables.'):
                    record['properties'] = list(obj.PropertiesList)
            if hasattr(obj, 'getGlobalPlacement'):
                record['global_matrix'] = list(obj.getGlobalPlacement().toMatrix().A)
            if obj.TypeId in ('App::Link', 'App::LinkElement'):
                linked = obj.LinkedObject
                if linked is None:
                    broken.append(key)
                else:
                    linked_doc = guard.inside(root, linked.Document.FileName).relative_to(root).as_posix()
                    record['linked_object'] = f'{linked_doc}#{linked.Name}'
            shape = getattr(obj, 'Shape', None)
            if shape is not None and not shape.isNull():
                record['shape'] = {'bounds_mm': bounds(shape), 'valid': check_native_shape(shape, cache, checks),
                                   'solid_count': len(shape.Solids), 'volume_mm3': shape.Volume}
            if {'Invalid', 'Error'} & set(states) or not record.get('shape', {}).get('valid', True):
                invalid.append(key)
            objects.append(record)
        output.append(dict(file=name, label=doc.Label, partial=bool(doc.Partial), objects=objects))
    return {'documents': output, 'invalid_objects': invalid, 'broken_links': broken,
            'partial_documents': partial, 'recompute_ok': not (invalid or broken or partial),
            'shape_validation': {'occt': Part.OCC_VERSION, **checks}}


def route_observation(cable, ident, link, ports, requirements, route, position_tolerance):
    fresh = geometry.inspect_solid(cable.Shape)
    wire = builder.effective_wire(cable)
    source, target = ports[link['source']], ports[link['target']]
    minimum = requirements.get('min_radius_mm', requirements.get('min_static_radius_mm'))
    axis = geometry.inspect_route(wire, minimum,
                                  source.get('tangent'), target.get('tangent'),
                                  position_tolerance_mm=position_tolerance,
                                  start_position=source.get('position_mm'), end_position=target.get('position_mm'))
    failures = set(axis['failures'])
    measurement_error = 'route_measurement_error' in failures
    segments, samples = [], []
    diameter = float(cable.ProfilExterieur.DiametreExterieur.Value)
    section = math.pi * (diameter / 2) ** 2
    nominal_volume = section * wire.Length
    exact_section = abs(fresh.get('volume_mm3', -1) - nominal_volume) <= max(1e-6, nominal_volume * 1e-6)
    kind_map = {'Part::GeomLine': 'line', 'Part::GeomCircle': 'arc'}
    for edge in wire.OrderedEdges:
        reverse = edge.Orientation == 'Reversed'
        first, last = edge.FirstParameter, edge.LastParameter
        start, end = (last, first) if reverse else (first, last)
        points = [coordinates(point) for point in edge.discretize(Deflection=0.05)]
        if reverse:
            points.reverse()
        samples.extend(points[1:] if samples and samples[-1] == points[0] else points)
        segments.append(dict(kind=kind_map.get(edge.Curve.TypeId, 'curve'),
                             start_mm=coordinates(edge.valueAt(start)), end_mm=coordinates(edge.valueAt(end)),
                             length_mm=edge.Length, bounds_mm=bounds(edge), samples_mm=points,
                             corridor_id=route.get('corridor'),
                             volume_mm3=section * edge.Length if exact_section else None))
    cable_bounds = bounds(cable.Shape) if fresh['status'] == 'pass' else None
    endpoint_values = all(p.get('position_mm') is not None for p in (source, target))
    tangent_values = all(p.get('tangent') is not None for p in (source, target))
    return {'id': ident, 'length_mm': axis.get('length_mm'), 'diameter_mm': diameter,
            'min_radius_mm': axis['minimum_radius_mm'], 'radius_certified': axis['radius_evidence'] == 'analytic_lines_circles',
            'continuity_ok': not (measurement_error or 'discontinuous_wire' in failures),
            'tangency_ok': not (measurement_error or failures & {'non_tangent_join', 'start_axis_mismatch', 'end_axis_mismatch'}) if tangent_values else None,
            'endpoints_ok': not (measurement_error or failures & {'start_position_mismatch', 'end_position_mismatch'}) if endpoint_values else None,
            'solid_valid': fresh['status'] == 'pass', 'segments': segments, 'volume_mm3': fresh.get('volume_mm3'),
            'volume_method': 'nominal_constant_circular_section_times_edge_length' if exact_section else None,
            'z_max_mm': cable_bounds[1][2] if cable_bounds else None, 'bounds_mm': cable_bounds,
            'axis_samples_mm': samples, 'measurement': axis, 'solid_measurement': fresh}


def box_gap(a, b):
    left, right = bounds(a), bounds(b)
    return math.sqrt(sum(max(0, m0 - M1, m1 - M0) ** 2
                         for m0, M0, m1, M1 in zip(*left, *right)))


def check_reference_boxes(objects, specs):
    for spec in specs:
        obj = objects[spec['id']]
        if 'through_bore_x' in spec:
            expected = bored_box_shape(spec)
            shape = obj.Shape
            if (obj.TypeId != 'Part::Feature' or geometry.inspect_solid(shape)['status'] != 'pass'
                    or not expected.isValid() or abs(shape.Volume - expected.Volume) > 1e-7
                    or shape.cut(expected).Volume > 1e-7 or expected.cut(shape).Volume > 1e-7):
                raise ValueError(f'Reference bored box {spec["id"]} changed shape or placement')
            continue
        if obj.TypeId != 'Part::Box' or not obj.getGlobalPlacement().Rotation.isIdentity():
            raise ValueError(f'Reference box {spec["id"]} changed type or orientation')
        origin = coordinates(obj.getGlobalPlacement().Base)
        size = [obj.Length.Value, obj.Width.Value, obj.Height.Value]
        if (any(abs(a - b) > 1e-7 for a, b in zip(origin, spec['origin_mm']))
                or any(abs(a - b) > 1e-7 for a, b in zip(size, spec['size_mm']))):
            raise ValueError(f'Reference box {spec["id"]} changed dimensions or position')
        shape = obj.Shape
        if geometry.inspect_solid(shape)['status'] == 'pass':
            lower, upper = bounds(shape)
            if (any(abs(a - b) > 1e-7 for a, b in zip(lower, origin))
                    or any(abs(a - b - length) > 1e-7 for a, b, length in zip(upper, origin, size))):
                raise ValueError(f'Reference box {spec["id"]} changed shape or placement')


def measure_linked_obstacles(doc, root, bindings, specs):
    """Resolve the static top-level obstacles explicitly frozen by the L4 bench."""
    if not isinstance(bindings, dict) or not bindings or not bindings.keys() <= specs.keys():
        raise ValueError('Invalid frozen XLink obstacle inventory')

    def identity(obj):
        path = guard.inside(root, obj.Document.FileName).relative_to(root).as_posix()
        return f'{path}#{obj.Name}'

    links = {identity(obj): obj for obj in doc.Objects if obj.TypeId in ('App::Link', 'App::LinkElement')}
    occurrences = {item['occurrence'] for item in bindings.values()}
    if occurrences != links.keys() or len(occurrences) != len(bindings):
        raise ValueError(f'XLink obstacle inventory differs from the freeze: '
                         f'missing={sorted(occurrences - links.keys())}, extra={sorted(links.keys() - occurrences)}')
    evidence, shapes, documents = {}, {}, {doc.FileName}
    for ident, item in bindings.items():
        link = links[item['occurrence']]
        target = link.LinkedObject
        if (link.TypeId != 'App::Link' or link.ElementCount or link.InList or target is None
                or target.Document == doc or identity(target) != item['definition']
                or target.TypeId not in ('Part::Feature', 'Part::Box')):
            raise ValueError(f'XLink obstacle {ident} is not a frozen top-level link to a simple external solid')
        shape, matrix, resolved = Part.getShape(link, retType=2)
        if resolved is None or identity(resolved) != item['definition']:
            raise ValueError(f'FreeCAD resolved a different definition for XLink obstacle {ident}')
        spec = specs[ident]
        expected = bored_box_shape(spec) if 'through_bore_x' in spec else Part.makeBox(
            *spec['size_mm'], vector(spec['origin_mm']))
        if (geometry.inspect_solid(shape)['status'] != 'pass' or not expected.isValid()
                or abs(shape.Volume - expected.Volume) > 1e-7 or shape.cut(expected).Volume > 1e-7
                or expected.cut(shape).Volume > 1e-7):
            raise ValueError(f'XLink obstacle {ident} changed shape or placement')
        shapes[ident] = shape
        evidence[ident] = {**item, 'matrix': list(matrix.A), 'bounds_mm': bounds(shape)}
        documents.add(target.Document.FileName)
    if documents != {item.FileName for item in App.listDocuments().values()}:
        raise ValueError('The XLink closure contains documents outside the frozen obstacle inventory')
    return shapes, evidence, {obj.Name for obj in links.values()}


def measurements(doc, plan, root):
    system, requirements, candidate = (plan[key] for key in ('system', 'requirements', 'candidate'))
    links = {link['id']: link for link in system['links']}
    ports = {port['id']: port for port in system['ports']}
    native = system.get('geometry', {})
    boxes = {box['id']: box for box in native.get('boxes', [])}
    ref_ids = boxes.keys()
    expected_ids = ref_ids | set(links)
    bindings = plan.get('xlink_obstacles')
    linked_shapes, linked_evidence, linked_names = {}, {}, set()
    if bindings is not None:
        if native.get('motion_states'):
            raise ValueError('The authorized L4 XLink obstacles require a static bench')
        linked_shapes, linked_evidence, linked_names = measure_linked_obstacles(doc, root, bindings, boxes)
    objects = {}
    for obj in doc.Objects:
        if 'EngineId' in obj.PropertiesList:
            if obj.EngineId in objects:
                raise ValueError(f'Duplicate native identity: {obj.EngineId}')
            objects[obj.EngineId] = obj
    root_ids = expected_ids - linked_shapes.keys()
    if root_ids != objects.keys() or ref_ids & links.keys():
        raise ValueError(f'Inconsistent native inventory: missing={root_ids - objects.keys()}, '
                         f'extra={objects.keys() - root_ids}')
    check_reference_boxes(objects, [box for ident, box in boxes.items() if ident not in linked_shapes])
    state_cables = motion_cables(doc, plan)
    accounted = {obj.Name for obj in objects.values()} | linked_names
    accounted.update(obj.Name for state in state_cables.values() for obj in state.values())
    # A FreeCAD dependency can carry an obstacle. Links from an inventoried
    # object do not exempt the linked solid from the collision inventory.
    unexpected = [obj.Name for obj in doc.Objects if obj.Name not in accounted
                  and getattr(obj, 'Shape', None) is not None
                  and not obj.Shape.isNull() and obj.Shape.Solids]
    if unexpected:
        raise ValueError(f'Native assembly contains solids outside the declared inventory: {unexpected}')
    # Erase saved caches on this dedicated in-memory document. A proxy whose
    # recompute fails cannot pass by retaining an older valid ArchCable solid.
    position_tolerance = requirements.get('position_tolerance_mm', 1e-5)
    routes, fresh_failed = {}, []
    for ident, link in links.items():
        cable = objects[ident]
        fresh = geometry.rebuild_cable_in_isolated_document(doc, cable)
        if fresh['status'] == 'pass':
            routes[ident] = route_observation(cable, ident, link, ports, requirements['links'][ident],
                                             candidate.get('routes', {}).get(ident, {}), position_tolerance)
        else:
            fresh_failed.append(ident)
            if bindings is not None:
                missing_proxies = [obj.Name for obj in (cable, cable.Base)
                                   if obj is not None and getattr(obj, 'Proxy', None) is None]
                if missing_proxies:
                    fresh['failures'].append('missing_cables_proxies')
                    fresh['missing_proxies'] = missing_proxies
            routes[ident] = {'solid_valid': False, 'solid_measurement': fresh}
    clearance = requirements.get('clearance_mm')
    tolerance = requirements.get('collision_tolerance_mm3')
    distance_tolerance = requirements.get('clearance_tolerance_mm', 1e-6)
    clearance = 0 if clearance is None else clearance
    tolerance = 1e-7 if tolerance is None else tolerance
    shapes = linked_shapes | {ident: obj.Shape for ident, obj in objects.items()
                              if geometry.inspect_solid(obj.Shape)['status'] == 'pass'}
    contacts = {frozenset((entry['a'], entry['b'])): entry for entry in requirements.get('allowed_contacts', [])}
    tested, filtered = [], []
    for a, b in itertools.combinations(sorted(shapes), 2):
        relation = contacts.get(frozenset((a, b)))
        gap = box_gap(shapes[a], shapes[b])
        if relation is None and gap > clearance + distance_tolerance:
            filtered.append({'a': a, 'b': b, 'clearance_lower_bound_mm': gap})
            continue
        authorization = None
        if relation and relation.get('source'):
            kind = relation.get('relation')
            if kind == 'cable_in_conduit_envelope':
                a, b = relation['a'], relation['b']
            authorization = {'kind': kind, 'justification': str(relation['source']), 'pair': [a, b],
                             'inner_id': a, 'outer_id': b, 'outer_representation': relation.get('outer_representation')}
        tested.append(measure_pair(shapes[a], shapes[b], a, b, clearance, tolerance,
                                   distance_tolerance, authorization))
    complete = shapes.keys() == expected_ids and all(pair['status'] != 'unknown' for pair in tested)
    extraction, extraction_details = {}, {}
    view_objects = [{'id': spec['id'], 'role': 'structure',
                     'representation': 'bored_box' if 'through_bore_x' in spec else 'reference_box',
                     'bounds_mm': bounds(shapes[spec['id']])}
                    for spec in native.get('boxes', []) if spec['id'] in shapes]
    for spec in native.get('extraction', []):
        port = spec['port']
        extraction[port], extraction_details[port] = box_clearance(
            spec, shapes, expected_ids, clearance, tolerance, distance_tolerance)
        view_objects.append({'id': port, 'role': 'extraction', 'bounds_mm': extraction_details[port]['bounds_mm']})
    anchors = {}
    for spec in native.get('anchors', []):
        ident, obj_id, anchor_id = spec['id'], spec['object'], spec['anchor']
        result = {'anchor': anchor_id, 'attached': None, 'access_clear': None}
        if {obj_id, anchor_id} <= shapes.keys():
            joint = measure_pair(shapes[obj_id], shapes[anchor_id], obj_id, anchor_id, 0,
                                 tolerance, distance_tolerance)
            result['attachment_measurement'] = joint
            if joint['status'] != 'unknown':
                result['attached'] = joint['status'] == 'pass' and joint['clearance_mm'] <= distance_tolerance
        if 'access_box' in spec:
            result['access_clear'], result['access_evidence'] = box_clearance(
                spec['access_box'], shapes, expected_ids, clearance, tolerance, distance_tolerance)
            result['access_measurements'] = result['access_evidence']['measurements']
        anchors[ident] = result
        if obj_id in shapes:
            view_objects.append({'id': ident, 'role': 'support', 'bounds_mm': bounds(shapes[obj_id]),
                                 'volume_mm3': shapes[obj_id].Volume})
    stations = [dict(station, support=anchor['id'], object=anchor['object'])
                for anchor in native.get('anchors', []) for station in anchor.get('retentions', [])]
    required = {item['id']: item for item in requirements.get('supports', [])}
    declared = {item['id']: item for item in candidate.get('supports', [])}
    for ident, link in links.items():
        criteria = requirements['links'][ident]
        if routes[ident].get('solid_valid') and ('max_unsupported_mm' in criteria or criteria.get('requires_support')):
            routes[ident].update(measure_retention(
                builder.effective_wire(objects[ident]), routes[ident], link, ports, stations, anchors,
                required, declared, shapes, position_tolerance, require_station=criteria.get('requires_support', False)))
    motion = measure_motion(doc, plan, state_cables, routes, shapes,
                            route_observation=route_observation, rebuild_cable=geometry.rebuild_cable_in_isolated_document,
                            measure_pair=measure_pair, inspect_solid=geometry.inspect_solid)
    result = dict(route_metrics=routes, collisions=tested, collision_complete=complete,
                  collision_filtered_pairs=len(filtered), collision_filtered_evidence=filtered,
                  extraction_clear=extraction, extraction_evidence=extraction_details,
                  anchor_valid=anchors, motion=motion, view_objects=view_objects, failed_rebuilds=fresh_failed)
    if bindings is not None:
        result['xlink_obstacles'] = linked_evidence
        result['xlink_pair_coverage'] = {
            'expected_pairs': math.comb(len(expected_ids), 2),
            'native_pairs_attempted': len(tested),
            'native_pairs_inconclusive': sum(pair['status'] == 'unknown' for pair in tested),
            'pairs_excluded_by_aabb': len(filtered),
            'pairs_missing_shapes': [list(pair) for pair in itertools.combinations(sorted(expected_ids), 2)
                                     if not set(pair) <= shapes.keys()],
        }
    return result


def measure_pair(shape_a, shape_b, a, b, clearance, tolerance, distance_tolerance, authorization=None):
    result = geometry.inspect_pair(shape_a, shape_b, a, b, clearance, authorization,
                                   volume_tolerance_mm3=tolerance, distance_tolerance_mm=distance_tolerance)
    return dict(a=a, b=b, intersection_mm3=result.get('intersection_volume_mm3'),
                outer_representation=(authorization or {}).get('outer_representation'), **result)


def box_clearance(spec, shapes, expected_ids, clearance, tolerance, distance_tolerance):
    size = vector(spec['size_mm'])
    shape = Part.makeBox(size.x, size.y, size.z, vector(spec['origin_mm']))
    ignored = set(spec.get('ignore_ids', []))
    compared = expected_ids - ignored
    unavailable = compared - shapes.keys()
    details = [measure_pair(shape, shapes[ident], 'approach_volume', ident, clearance,
                            tolerance, distance_tolerance)
               for ident in sorted(compared & shapes.keys())]
    if any(pair['status'] == 'fail' for pair in details):
        clear = False
    elif details and not unavailable and all(pair['status'] == 'pass' for pair in details):
        clear = True
    else:
        clear = None
    return clear, {'measurements': details, 'bounds_mm': bounds(shape),
                   'ignored_ids': sorted(ignored), 'unavailable_ids': sorted(unavailable)}


def execute(request, root):
    action, entry = request['action'], guard.inside(root, root / request['entry'])
    plan = request.get('plan')
    print(f'{action}: initializing Cables Workbench', file=sys.stderr, flush=True)
    cables = cables_environment(gui=plan is not None)
    print(f'{action}: opening or creating {entry.name}', file=sys.stderr, flush=True)
    doc = App.newDocument('ElectromechanicalCandidate') if action == 'build' else App.openDocument(str(entry))
    if action == 'build':
        doc.FileName = str(entry)
        build(doc, plan)
    print(f'{action}: completing partial dependency loads', file=sys.stderr, flush=True)
    completed = complete_dependencies(doc, root)
    print(f'{action}: recomputing document closure', file=sys.stderr, flush=True)
    documents, recomputed = recalculate(doc, root)
    print(f'{action}: inspecting document closure', file=sys.stderr, flush=True)
    observed = inventory(documents, root)
    if action == 'build' and not observed['recompute_ok']:
        raise RuntimeError(f'Native file cannot be saved: {observed["invalid_objects"]}, '
                           f'{observed["broken_links"]}, {observed["partial_documents"]}')
    save_performed = action in ('build', 'roundtrip') and observed['recompute_ok']
    if save_performed:
        print(f'{action}: saving {entry.name}', file=sys.stderr, flush=True)
        if action == 'build':
            doc.saveAs(str(entry))
        else:
            doc.save()
    if action == 'inspect' and plan is not None:
        if len(documents) != 1 and 'xlink_obstacles' not in plan:
            raise ValueError('Native candidate inventory requires a single document without XLinks')
        observed.update(measurements(doc, plan, root))
        observed['recompute_ok'] = observed['recompute_ok'] and not observed['failed_rebuilds']
    if action == 'build':
        native = [obj for obj in doc.Objects if getattr(obj, 'EngineId', '') in plan['candidate']['routes']]
        if native:
            base = native[0].Base
            cables['wireflex_properties'] = list(base.PropertiesList)
            cables['wireflex_modes'] = list(base.getEnumerationsOfProperty('PathType'))
    result = dict(schema_version=1, backend='freecad_python', phase=action,
                  freecad=App.Version(), python=sys.version, cables=cables,
                  native_sha256=guard.sha256(entry), recomputed_features=recomputed,
                  inventory_complete=True, save_performed=save_performed,
                  completed_partial_documents=completed, **observed)
    print(f'{action}: closing {entry.name}', file=sys.stderr, flush=True)
    App.closeDocument(doc.Name)
    return result


def main():
    request, output = map(Path, sys.argv[1:])
    try:
        result = execute(json.loads(request.read_text(encoding='utf-8')), request.parent)
        result['finalized'] = True
    except Exception:
        result = {'finalized': False, 'error': traceback.format_exc()}
    result.update(pid=os.getpid(), worker_id=uuid4().hex)
    output.write_text(json.dumps(result, ensure_ascii=False, allow_nan=False, indent=2) + '\n', encoding='utf-8')
    sys.stdout.flush()
    sys.stderr.flush()
    # FreeCAD's offscreen Qt event loop can hang during interpreter shutdown.
    os._exit(0 if result['finalized'] else 1)


if __name__ == '__main__':
    main()
