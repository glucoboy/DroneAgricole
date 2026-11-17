"""Measure point retentions on a freshly recomputed native cable axis."""

import math

import FreeCAD as App
import Part


def _project_station(wire, point, tolerance):
    """Return a unique curvilinear station and tangent on an ordered wire."""
    vertex = Part.Vertex(point)
    candidates = []
    offset = 0.0
    for edge in wire.OrderedEdges:
        distance, pairs, information = edge.distToShape(vertex)
        if distance <= tolerance:
            first, last = edge.FirstParameter, edge.LastParameter
            for (axis_point, _), info in zip(pairs, information):
                if info[0] == 'Edge':
                    parameter = min(last, max(first, info[2]))
                elif info[0] == 'Vertex':
                    parameter = min((first, last), key=lambda value: (edge.valueAt(value) - axis_point).Length)
                else:
                    return None
                local = edge.Curve.length(first, parameter) if parameter > first else 0.0
                if edge.Orientation == 'Reversed':
                    local = edge.Length - local
                candidates.append((distance, offset + local, axis_point, edge.tangentAt(parameter)))
        offset += edge.Length
    if not candidates:
        return None
    best = min(candidates, key=lambda row: (row[0], row[1]))
    if any(abs(other[1] - best[1]) > tolerance for other in candidates):
        return None
    return best


def _station(wire, spec, radius, anchors, required, declared, shapes, tolerance):
    identity = spec['support']
    result = {'support': identity, 'object': spec['object'], 'source': spec['source'],
              'status': 'unknown', 'station_mm': None}
    expected = required.get(identity, {}).get('anchor')
    observation = anchors.get(identity, {})
    if (expected is None or declared.get(identity, {}).get('anchor') != expected
            or observation.get('anchor') != expected or observation.get('attached') is not True
            or observation.get('access_clear') is not True or spec['object'] not in shapes):
        return {**result, 'reason': 'retention_support_not_verified'}

    projection = _project_station(wire, App.Vector(*spec['point_mm']), tolerance)
    if projection is None:
        return {**result, 'reason': 'station_off_axis_or_ambiguous'}
    offset, station, axis_point, tangent = projection
    result.update(station_mm=station, axis_offset_mm=offset)

    # A ball bound is orientation-independent and contains the full normal disk.
    enclosure = spec['enclosure']
    position = (axis_point.x, axis_point.y, axis_point.z)
    margin = min(min(value - origin, origin + length - value) - radius
                 for value, origin, length in zip(position, enclosure['origin_mm'], enclosure['size_mm']))
    result['enclosure_margin_mm'] = margin
    if margin < -tolerance:
        return {**result, 'reason': 'cable_cross_section_outside_enclosure'}

    support_shape = shapes[spec['object']]
    disk = Part.Face(Part.Wire([Part.makeCircle(radius, axis_point, tangent)]))
    contact, _, _ = disk.distToShape(support_shape)
    result['section_support_distance_mm'] = contact
    if not math.isfinite(contact) or contact > tolerance:
        return {**result, 'reason': 'cable_cross_section_does_not_contact_support'}
    overlap = disk.common(support_shape).Area
    result['section_support_overlap_mm2'] = overlap
    if not math.isfinite(overlap) or overlap > tolerance * 2 * radius:
        return {**result, 'reason': 'retention_support_penetrates_cable_cross_section'}

    wall = spec.get('capture_wall_mm')
    if type(wall) not in (float, int) or not math.isfinite(wall) or wall <= 0:
        return {**result, 'reason': 'native_capture_wall_requirement_missing'}
    outer_radius = radius + wall
    target_area = math.pi * wall * (2 * radius + wall)
    if outer_radius <= radius or not math.isfinite(target_area):
        return {**result, 'reason': 'native_capture_wall_geometry_invalid'}
    # Check the section annulus against actual material. Cap the tolerated
    # area fraction so a very thin wall cannot pass without measured material.
    area_tolerance = min(target_area * 1e-6, 2 * math.pi * outer_radius * tolerance)
    outer = Part.Face(Part.Wire([Part.makeCircle(outer_radius, axis_point, tangent)]))
    annulus = outer.cut(disk)
    if (annulus.isNull() or not annulus.isValid() or not math.isfinite(annulus.Area)
            or abs(annulus.Area - target_area) > area_tolerance):
        return {**result, 'reason': 'native_capture_wall_geometry_invalid'}
    uncovered = annulus.cut(support_shape)
    uncovered_area = 0.0 if uncovered.isNull() else uncovered.Area
    result.update(capture_wall_mm=wall, capture_area_mm2=annulus.Area,
                  capture_uncovered_mm2=uncovered_area, capture_area_tolerance_mm2=area_tolerance)
    if (not uncovered.isNull() and not uncovered.isValid()) or not math.isfinite(uncovered_area):
        return {**result, 'reason': 'native_capture_wall_measurement_invalid'}
    if uncovered_area > area_tolerance:
        return {**result, 'reason': 'native_capture_wall_incomplete'}
    return {**result, 'status': 'pass', 'reason': 'verified_geometric_point_retention'}


def measure(wire, route_measurement, link, ports, stations, anchors, required_supports,
            declared_supports, shapes, position_tolerance, require_station=False):
    """Measure all gaps between qualified geometry points, including both end gaps."""
    result = {'unsupported_span_mm': None, 'unsupported_length_mm': None}
    evidence = {'method': 'native_axis_distance_between_geometric_retention_stations',
                'status': 'unknown', 'stations': [], 'gaps_mm': None}
    result['retention_evidence'] = evidence
    endpoints = [ports[link[field]] for field in ('source', 'target')]
    if (not all(route_measurement.get(field) is True for field in
                ('solid_valid', 'continuity_ok', 'tangency_ok', 'endpoints_ok'))
            or not all(port.get('retained_endpoint') is True
                       and port.get('status') in {'MESUREE', 'DOCUMENTEE'}
                       and port.get('position_mm') is not None and port.get('tangent') is not None
                       for port in endpoints)):
        evidence['reason'] = 'native_retained_endpoints_not_verified'
        return result
    diameter = route_measurement.get('diameter_mm')
    length = float(wire.Length)
    if diameter is None or not math.isfinite(diameter) or diameter <= 0 or not math.isfinite(length) or length <= 0:
        evidence['reason'] = 'native_axis_length_or_diameter_unavailable'
        return result

    evidence['endpoints'] = [port['id'] for port in endpoints]
    for spec in stations:
        if spec['link'] != link['id']:
            continue
        try:
            measured = _station(wire, spec, diameter / 2, anchors, required_supports,
                                declared_supports, shapes, position_tolerance)
        except (ValueError, RuntimeError) as exc:
            measured = {'support': spec['support'], 'object': spec['object'], 'status': 'unknown',
                        'reason': 'occt_station_measurement_failed', 'error': str(exc)}
        evidence['stations'].append(measured)

    if any(station['status'] != 'pass' for station in evidence['stations']):
        evidence['reason'] = 'retention_station_not_verified'
        return result
    positions = sorted(station['station_mm'] for station in evidence['stations'])
    if require_station and not any(position_tolerance < s < length - position_tolerance for s in positions):
        evidence['reason'] = 'intermediate_retention_required'
        return result
    positions = [0.0, *positions, length]
    gaps = [last - first for first, last in zip(positions, positions[1:])]
    if min(gaps) < -position_tolerance:
        evidence['reason'] = 'native_station_outside_measured_wire'
        return result
    gaps = [max(0.0, gap) for gap in gaps]
    evidence.update(status='pass', gaps_mm=gaps)
    result.update(unsupported_span_mm=max(gaps), unsupported_length_mm=length)
    return result
