"""Build and measure discrete cable poses in an isolated FreeCAD candidate."""

from itertools import combinations
import math

import FreeCAD as App


STATE_PROPERTY = 'EngineMotionState'
LINK_PROPERTY = 'EngineMotionLink'


def _proposals(plan):
    system = plan['system']
    states = system.get('geometry', {}).get('motion_states', {})
    links = {link['id'] for link in system['links']}
    for state, routes in sorted(plan['candidate'].get('motion_routes', {}).items()):
        if state not in states:
            raise ValueError(f'Motion state {state} is absent from the frozen model')
        for link, route in sorted(routes.items()):
            if link not in links:
                raise ValueError(f'Motion cable {link} is absent from the frozen model')
            yield state, link, route


def build_motion(doc, plan, make_route_cable):
    """Save separate editable cable objects for poses; nominal geometry stays visible."""
    for state, link, route in _proposals(plan):
        diameter = plan['requirements']['links'][link]['diameter_mm']
        cable = make_route_cable(doc, route, diameter)
        for field, value in ((STATE_PROPERTY, state), (LINK_PROPERTY, link)):
            cable.addProperty('App::PropertyString', field, 'Electromechanical')
            setattr(cable, field, value)
        cable.Label = f'{link} — {state}'
        cable.Visibility = False


def motion_cables(doc, plan):
    """Resolve the exact saved state inventory before excluding it from nominal checks."""
    expected = {(state, link) for state, link, _ in _proposals(plan)}
    found, cables = set(), {}
    for cable in doc.Objects:
        props = set(cable.PropertiesList)
        if not {STATE_PROPERTY, LINK_PROPERTY} & props:
            continue
        state = getattr(cable, STATE_PROPERTY, None)
        link = getattr(cable, LINK_PROPERTY, None)
        key = (state, link)
        base = getattr(cable, 'Base', None)
        proxy = getattr(cable, 'Proxy', None)
        wire_proxy = getattr(base, 'Proxy', None)
        if ('EngineId' in props or key not in expected or key in found
                or type(proxy).__module__ != 'freecad.cables.archCable'
                or type(wire_proxy).__module__ != 'freecad.cables.wireFlex'):
            raise ValueError(f'Unexpected or duplicate native motion cable: {cable.Name} ({state}, {link})')
        cables.setdefault(state, {})[link] = cable
        found.add(key)
    if found != expected:
        raise ValueError(f'Missing native motion cables: {sorted(expected - found)}')
    return cables


def _finite_length(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def _route_measurements(cable, doc, ident, link, ports, rule, route, nominal, tolerance,
                        route_observation, rebuild_cable):
    fresh = rebuild_cable(doc, cable)
    if fresh['status'] != 'pass':
        return {'solid_valid': False, 'solid_measurement': fresh}
    measured = route_observation(cable, ident, link, ports, {'min_radius_mm': rule.get('min_dynamic_radius_mm')},
                                 route, tolerance)
    length = measured.get('length_mm')
    baseline = nominal.get('length_mm')
    limit = rule.get('motion_length_tolerance_mm')
    difference = length - baseline if _finite_length(length) and _finite_length(baseline) else None
    conserved = abs(difference) <= limit if difference is not None and _finite_length(limit) else None
    diameter = measured.get('diameter_mm')
    expected_diameter = rule.get('diameter_mm')
    same_diameter = (abs(diameter - expected_diameter) <= tolerance
                     if _finite_length(diameter) and _finite_length(expected_diameter) else None)
    chord = None
    reserve = None
    if measured.get('endpoints_ok') is True:
        chord = math.dist(ports[link['source']]['position_mm'], ports[link['target']]['position_mm'])
        if conserved is True and length >= chord - 2 * tolerance:
            reserve = max(0, length - chord)
    return {key: measured[key] for key in ('solid_valid', 'continuity_ok', 'tangency_ok', 'endpoints_ok',
                                           'min_radius_mm', 'radius_certified', 'length_mm', 'diameter_mm')} | {
        'native_object': cable.Name, 'nominal_length_mm': baseline, 'length_delta_mm': difference,
        'length_tolerance_mm': limit, 'length_ok': conserved, 'diameter_ok': same_diameter,
        'chord_mm': chord, 'reserve_mm': reserve,
        'reserve_method': 'developed_length_minus_frozen_endpoint_chord',
        'radius_evidence': measured['measurement']['radius_evidence'],
        'axis_sha256': measured['measurement'].get('shape_sha256'),
        'rebuild_evidence': fresh,
    }


def _scene_pairs(shapes, identities, changed_links, moved_boxes, requirements, measure_pair):
    contacts = {frozenset((entry['a'], entry['b'])): entry
                for entry in requirements.get('allowed_contacts', []) if entry.get('source')}
    clearance = requirements.get('clearance_mm', 0)
    volume_tolerance = requirements.get('collision_tolerance_mm3', 1e-7)
    distance_tolerance = requirements.get('clearance_tolerance_mm', 1e-6)
    for a, b in combinations(sorted(identities), 2):
        if not {a, b} & (changed_links | moved_boxes):
            continue
        if not {a, b} <= shapes.keys():
            yield {'a': a, 'b': b, 'status': 'unknown', 'reason': 'native_motion_shape_unavailable'}
            continue
        authorization = None
        relation = contacts.get(frozenset((a, b)))
        if relation is not None:
            kind = relation.get('relation')
            if kind == 'cable_in_conduit_envelope':
                a, b = relation['a'], relation['b']
            authorization = {'kind': kind, 'justification': relation['source'], 'pair': [a, b],
                             'inner_id': a, 'outer_id': b, 'outer_representation': relation.get('outer_representation')}
        yield measure_pair(shapes[a], shapes[b], a, b, clearance, volume_tolerance,
                           distance_tolerance, authorization)


def measure_motion(doc, plan, native_cables, nominal_routes, nominal_shapes, *,
                   route_observation, rebuild_cable, measure_pair, inspect_solid):
    """Measure the saved state wires and transformed copies of frozen obstacles."""
    system, requirements = plan['system'], plan['requirements']
    geometry = system.get('geometry', {})
    links = {link['id']: link for link in system['links']}
    ports = {port['id']: port for port in system['ports']}
    identities = links.keys() | {box['id'] for box in geometry.get('boxes', [])}
    rules = requirements['links']
    tolerance = requirements.get('position_tolerance_mm', 1e-5)
    observations = {}
    for state, spec in sorted(geometry.get('motion_states', {}).items()):
        state_cables = native_cables.get(state, {})
        moved_ports, moved_boxes = spec.get('ports', {}), spec.get('boxes', {})
        posed_ports = {ident: port | moved_ports.get(ident, {}) for ident, port in ports.items()}
        changed_links = set(state_cables)
        changed_links.update(ident for ident, link in links.items()
                             if state in rules[ident].get('required_motion_states', [])
                             or {link['source'], link['target']} & moved_ports.keys())
        shapes = {ident: shape for ident, shape in nominal_shapes.items() if ident not in changed_links}
        for ident, pose in moved_boxes.items():
            original = shapes.pop(ident, None)
            if original is not None:
                moved = original.copy()
                moved.translate(App.Vector(*pose['translation_mm']))
                if inspect_solid(moved)['status'] == 'pass':
                    shapes[ident] = moved
        state_routes = {}
        for ident, cable in state_cables.items():
            route = plan['candidate']['motion_routes'][state][ident]
            measured = _route_measurements(cable, doc, ident, links[ident], posed_ports, rules[ident], route,
                                           nominal_routes.get(ident, {}), tolerance, route_observation, rebuild_cable)
            state_routes[ident] = measured
            if measured.get('solid_valid') is True:
                shapes[ident] = cable.Shape
        pairs = list(_scene_pairs(shapes, identities, changed_links, set(moved_boxes), requirements, measure_pair))
        missing_shapes = sorted(identities - shapes.keys())
        translations = {key: value['translation_mm'] for key, value in moved_boxes.items()}
        for ident in sorted(changed_links):
            measured = state_routes.get(ident, {'reason': 'native_motion_route_unavailable'})
            relevant_pairs = [pair for pair in pairs
                              if ident in (pair['a'], pair['b'])
                              or not {pair['a'], pair['b']} & changed_links]
            if any(pair['status'] == 'fail' for pair in relevant_pairs):
                clear = False
            elif not missing_shapes and all(pair['status'] == 'pass' for pair in relevant_pairs):
                clear = True
            else:
                clear = None
            observations.setdefault(ident, {})[state] = measured | {
                'clearance_ok': clear, 'clearance_pairs': relevant_pairs, 'missing_shapes': missing_shapes,
                'obstacle_translations_mm': translations,
            }
    return observations
