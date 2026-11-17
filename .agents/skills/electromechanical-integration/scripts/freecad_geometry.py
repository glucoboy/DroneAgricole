"""FreeCAD measurement infrastructure; no routing policy or implicit file save.

Import with FreeCAD's Python. Lengths are mm, angles degrees and volume mm^3.
Numerical spline samples are diagnostic, never a global curvature certificate.
"""
import hashlib
import math

import FreeCAD as App
import Part


def _finite(value, label="measurement", minimum=None):
    if isinstance(value, bool):
        raise ValueError("Boolean is not a numerical " + label)
    number = float(value)
    if not math.isfinite(number) or (minimum is not None and number < minimum):
        raise ValueError("Non-finite or out-of-range " + label)
    return number


def _vec(value):
    vector = App.Vector(value) if isinstance(value, App.Vector) else App.Vector(*value)
    for component in (vector.x, vector.y, vector.z):
        _finite(component, "vector component")
    return vector


def _angle(a, b):
    a, b = _vec(a), _vec(b)
    if _finite(a.Length, "direction length", 0) <= 1e-12 or _finite(b.Length, "direction length", 0) <= 1e-12:
        raise ValueError("Undefined direction")
    return _finite(math.degrees(a.getAngle(b)), "direction angle", 0)


def _ends(edge):
    a, b = _finite(edge.FirstParameter, "first parameter"), _finite(edge.LastParameter, "last parameter")
    if b <= a:
        raise ValueError("Empty or reversed parameter domain")
    return (b, a, -1.0) if edge.Orientation == "Reversed" else (a, b, 1.0)


def _tangent(edge, parameter, sign):
    return _vec(edge.tangentAt(_finite(parameter, "tangent parameter")) * sign)


def _status(failures, unknowns):
    return "fail" if failures else "unknown" if unknowns else "pass"


def shape_sha256(shape):
    return hashlib.sha256(shape.exportBrepToString().encode("utf-8")).hexdigest()


def inspect_route(wire, minimum_radius_mm=None, start_axis=None, end_axis=None,
                  waypoints=(), position_tolerance_mm=1e-5,
                  tangent_tolerance_deg=0.1, min_depth=5, max_depth=12,
                  curvature_relative_tolerance=0.01, start_position=None, end_position=None):
    """Measure one open, oriented wire in a single explicitly chosen frame.

    start_axis and end_axis both point OUT of their respective connector.
    waypoints are positions on the axis (not merely spline control points).
    For splines, inspect every knot span and subdivide adaptively. Successful
    sampling remains unknown until an independent global bound is supplied.
    """
    failures, unknowns = [], []
    result = {"stage": "geometry", "failures": failures, "unknowns": unknowns,
              "minimum_radius_mm": None, "radius_evidence": "unavailable",
              "edge_measurements": [], "join_angles_deg": [],
              "waypoint_distances_mm": []}
    if (not math.isfinite(position_tolerance_mm) or position_tolerance_mm <= 0
            or not math.isfinite(tangent_tolerance_deg) or tangent_tolerance_deg < 0
            or type(min_depth) is not int or type(max_depth) is not int
            or not 0 <= min_depth <= max_depth <= 18
            or not math.isfinite(curvature_relative_tolerance)
            or curvature_relative_tolerance <= 0):
        raise ValueError("Invalid measurement tolerances or recursion budget")
    if minimum_radius_mm is None:
        unknowns.append("minimum_radius_requirement_missing")
    elif not math.isfinite(minimum_radius_mm) or minimum_radius_mm <= 0:
        raise ValueError("minimum_radius_mm must be positive or None")
    try:
        if wire.isNull() or not wire.isValid() or len(wire.Wires) != 1 or wire.isClosed():
            raise ValueError("Expected one valid open wire")
        edges = wire.OrderedEdges
        if not edges:
            raise ValueError("Empty wire")
        result.update(length_mm=_finite(wire.Length, "wire length", 0), shape_sha256=shape_sha256(wire))
        maximum_curvature = 0.0
        all_exact = True
        for edge in edges:
            kind = edge.Curve.TypeId
            detail = {"curve_type": kind, "length_mm": _finite(edge.Length, "edge length", 0)}
            if kind == "Part::GeomLine":
                kmax = 0.0
                detail.update(method="analytic_line", samples=0)
            elif kind == "Part::GeomCircle":
                circle_radius = abs(_finite(edge.Curve.Radius, "circle radius"))
                kmax = _finite(1.0 / circle_radius, "circle curvature", 0)
                detail.update(method="analytic_circle", samples=0)
            else:
                all_exact = False
                cache, exhausted = {}, [False]
                def sample(t):
                    t = _finite(t, "curvature parameter")
                    if t not in cache:
                        value = abs(_finite(edge.curvatureAt(t), "curvature"))
                        cache[t] = value
                    return cache[t]
                def visit(a, b, depth):
                    ts = [a + (b-a)*f for f in (0, .25, .5, .75, 1)]
                    ks = [sample(t) for t in ts]
                    variation = max(ks)-min(ks)
                    needs_more = depth < min_depth or variation > max(1e-9, max(ks)*curvature_relative_tolerance)
                    if needs_more and depth < max_depth:
                        middle = (a+b)/2
                        visit(a, middle, depth+1)
                        visit(middle, b, depth+1)
                    elif needs_more:
                        exhausted[0] = True
                lo, hi = _finite(edge.FirstParameter, "first parameter"), _finite(edge.LastParameter, "last parameter")
                if hi <= lo:
                    raise ValueError("Empty or reversed parameter domain")
                knots = edge.Curve.getKnots() if hasattr(edge.Curve, "getKnots") else []
                knots = [_finite(k, "spline knot") for k in knots]
                boundaries = sorted(set([lo, hi] + [k for k in knots if lo < k < hi]))
                for a, b in zip(boundaries, boundaries[1:]):
                    visit(a, b, 0)
                kmax = max(cache.values())
                detail.update(method="adaptive_curvature_samples", samples=len(cache),
                              knot_spans=len(boundaries)-1, depth_budget_exhausted=exhausted[0],
                              min_depth=min_depth, max_depth=max_depth,
                              curvature_relative_tolerance=curvature_relative_tolerance)
                if exhausted[0]:
                    unknowns.append("curvature_subdivision_budget_reached")
            maximum_curvature = max(maximum_curvature, kmax)
            detail["minimum_radius_mm"] = None if kmax == 0 else _finite(1/kmax, "minimum edge radius", 0)
            result["edge_measurements"].append(detail)
        radius = None if maximum_curvature == 0 else _finite(1/maximum_curvature, "minimum radius", 0)
        result["minimum_radius_mm"] = radius
        result["straight_radius_infinite"] = all_exact and maximum_curvature == 0
        result["radius_evidence"] = "analytic_lines_circles" if all_exact else "sampled_upper_bound_on_true_minimum_radius"
        if not all_exact:
            unknowns.append("global_curvature_bound_not_proven")
        if minimum_radius_mm is not None and radius is not None and radius < minimum_radius_mm - position_tolerance_mm:
            failures.append("bend_radius_below_requirement")
        for previous, following in zip(edges, edges[1:]):
            _, pe, ps = _ends(previous)
            fs, _, ss = _ends(following)
            distance = _finite((_vec(previous.valueAt(pe))-_vec(following.valueAt(fs))).Length, "join distance", 0)
            if distance > position_tolerance_mm:
                failures.append("discontinuous_wire")
            angle = _angle(_tangent(previous, pe, ps), _tangent(following, fs, ss))
            result["join_angles_deg"].append(angle)
            if angle > tangent_tolerance_deg:
                failures.append("non_tangent_join")
        start, _, sign_start = _ends(edges[0])
        _, end, sign_end = _ends(edges[-1])
        for label, expected, actual in (
                ("start", start_position, edges[0].valueAt(start)),
                ("end", end_position, edges[-1].valueAt(end))):
            if expected is None:
                unknowns.append(label + "_connector_position_missing")
            else:
                distance = _finite((_vec(actual) - _vec(expected)).Length, "endpoint distance", 0)
                result[label + "_position_error_mm"] = distance
                if distance > position_tolerance_mm:
                    failures.append(label + "_position_mismatch")
        for label, axis, tangent in (
                ("start", start_axis, _tangent(edges[0], start, sign_start)),
                ("end", end_axis, _tangent(edges[-1], end, sign_end)*-1)):
            if axis is None:
                unknowns.append(label + "_connector_axis_missing")
            else:
                angle = _angle(tangent, _vec(axis))
                result[label + "_axis_error_deg"] = angle
                if angle > tangent_tolerance_deg:
                    failures.append(label + "_axis_mismatch")
        for point in waypoints:
            distance = _finite(wire.distToShape(Part.Vertex(_vec(point)))[0], "waypoint distance", 0)
            result["waypoint_distances_mm"].append(distance)
            if distance > position_tolerance_mm:
                failures.append("required_waypoint_missing")
    except Exception as exc:
        failures.append("route_measurement_error")
        result["error"] = str(exc)
    result["status"] = _status(failures, unknowns)
    return result


def inspect_solid(shape, expected_solids=1):
    if type(expected_solids) is not int or expected_solids < 1:
        raise ValueError("expected_solids must be a positive integer")
    failures = []
    result = {"stage": "solid", "failures": failures}
    try:
        result["null"] = shape.isNull()
        result["valid"] = not result["null"] and shape.isValid()
        result["solid_count"] = len(shape.Solids)
        result["volume_mm3"] = _finite(shape.Volume, "solid volume", 0) if not result["null"] else 0.0
        if not result["valid"] or result["solid_count"] != expected_solids or result["volume_mm3"] <= 0:
            failures.append("solid_generation_invalid")
    except Exception as exc:
        failures.append("solid_inspection_error")
        result["error"] = str(exc)
    result["status"] = _status(failures, [])
    return result


def rebuild_cable_in_isolated_document(doc, cable):
    """ONLY on an isolated document. Erase cached solid before native recompute.

    ArchCable catches some OCC errors and can retain an old valid solid. Emptying
    its shape makes that failure observable. Caller must enforce file isolation.
    No file is opened, saved or copied here.
    """
    before_path = shape_sha256(cable.Base.Shape)
    cable.Shape = Part.Shape()
    cable.Base.touch()
    cable.touch()
    recomputed = doc.recompute()
    result = inspect_solid(cable.Shape)
    result.update(recompute_return=bool(recomputed), path_before_sha256=before_path,
                  path_after_sha256=shape_sha256(cable.Base.Shape), cache_cleared=True,
                  object_states={obj.Name: list(obj.State) for obj in (cable, cable.Base)})
    if not recomputed:
        result["failures"].append("freecad_recompute_failed")
    if any(state in ("Invalid", "Error") for states in result["object_states"].values() for state in states):
        result["failures"].append("freecad_object_error")
    result["status"] = _status(result["failures"], [])
    return result


def inspect_pair(a, b, a_id, b_id, clearance_mm=0.0, relation=None,
                 volume_tolerance_mm3=1e-7, distance_tolerance_mm=1e-6):
    """Boolean/distance measurement with narrowly scoped authorized contact.

    relation.kind='cable_in_conduit_envelope' requires inner_id=a_id,
    outer_id=b_id, outer_representation='occupancy_envelope', justification,
    and full geometric containment. It never excuses conduit-material overlap.
    relation.kind='functional_contact' allows zero-volume contact for exact pair.
    """
    failures, unknowns = [], []
    result = {"stage": "integration", "pair": [a_id, b_id], "failures": failures,
              "unknowns": unknowns, "authorized_relation": False}
    if any(not math.isfinite(x) or x < 0 for x in (clearance_mm, volume_tolerance_mm3, distance_tolerance_mm)):
        raise ValueError("Invalid clearance/tolerance")
    try:
        if any(x.isNull() or not x.isValid() or not x.Solids for x in (a, b)):
            raise ValueError("Boolean inputs must be valid nonempty solids")
        for shape in (a, b):
            if _finite(shape.Volume, "boolean input volume", 0) <= 0:
                raise ValueError("Empty boolean input volume")
        intersection = a.common(b)
        if not intersection.isNull() and not intersection.isValid():
            raise ValueError("Invalid intersection result")
        overlap = _finite(intersection.Volume, "intersection volume", 0)
        distance = _finite(a.distToShape(b)[0], "clearance distance", 0)
        result.update(intersection_volume_mm3=overlap, clearance_mm=distance)
        rel = relation or {}
        justified = isinstance(rel.get("justification"), str) and bool(rel["justification"].strip())
        if justified and rel.get("kind") == "cable_in_conduit_envelope" and rel.get("inner_id") == a_id and rel.get("outer_id") == b_id and rel.get("outer_representation") == "occupancy_envelope":
            outside = a.cut(b)
            if not outside.isNull() and not outside.isValid():
                raise ValueError("Invalid containment result")
            outside_volume = _finite(outside.Volume, "outside envelope volume", 0)
            result["outside_envelope_volume_mm3"] = outside_volume
            result["authorized_relation"] = outside_volume <= volume_tolerance_mm3
        elif justified and rel.get("kind") == "functional_contact" and set(rel.get("pair", [])) == {a_id, b_id}:
            result["authorized_relation"] = overlap <= volume_tolerance_mm3 and distance <= distance_tolerance_mm
        if overlap > volume_tolerance_mm3 and not result["authorized_relation"]:
            failures.append("forbidden_interference")
        if distance < clearance_mm - distance_tolerance_mm and not result["authorized_relation"]:
            failures.append("insufficient_clearance")
    except Exception as exc:
        unknowns.append("boolean_or_distance_not_completed")
        result["error"] = str(exc)
    result["status"] = _status(failures, unknowns)
    return result
