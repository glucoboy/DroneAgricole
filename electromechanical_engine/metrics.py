"""Mesures de comparaison et vues orthographiques issues des observations CAO."""

from itertools import product
import math
from pathlib import Path
from xml.sax.saxutils import escape


ZONES = ("SOUS", "ENTRE", "AU_DESSUS")


def _number(value):
    return type(value) in (int, float) and math.isfinite(value)


def _point(value):
    return isinstance(value, (list, tuple)) and len(value) == 3 and all(map(_number, value))


def _sum_complete(values):
    values = list(values)
    return math.fsum(values) if values and all(map(_number, values)) else None


def _fresh(observed):
    if (observed.get("reopened") is True and observed.get("recompute_ok") is True
            and observed.get("broken_links") == [] and observed.get("invalid_objects") == []):
        return observed
    return {}


def _zone(z, plateaux):
    return ZONES[int(z >= plateaux[0]) + int(z > plateaux[1])]


def _linear_parts(segment, plateaux):
    """Return zone, centreline length and the nominal volume fraction of a straight span."""
    start = segment.get("start_mm")
    end = segment.get("end_mm")
    length = segment.get("length_mm")
    if not _point(start) or not _point(end) or not _number(length) or length <= 0:
        return None
    if segment.get("kind", "line") != "line" or not math.isclose(length, math.dist(start, end),
                                                                  rel_tol=1e-9, abs_tol=1e-8):
        return None
    slope = end[2] - start[2]
    fractions = [0.0, 1.0]
    if slope:
        fractions.extend((threshold - start[2]) / slope for threshold in plateaux
                         if min(start[2], end[2]) < threshold < max(start[2], end[2]))
    fractions.sort()
    volume = segment.get("volume_mm3")
    pieces = []
    for left, right in zip(fractions, fractions[1:]):
        z = start[2] + ((left + right) / 2) * slope
        points = [tuple(a + fraction * (b - a) for a, b in zip(start, end))
                  for fraction in (left, right)]
        altitude = sorted(point[2] for point in points)
        pieces.append((_zone(z, plateaux), length * (right - left),
                       volume * (right - left) if _number(volume) else None, points, altitude))
    return pieces


def _curve_parts(segment, plateaux):
    bounds = segment.get("bounds_mm")
    length = segment.get("length_mm")
    if not _valid_bounds(bounds) or not _number(length) or length <= 0:
        return None
    low, high = (corner[2] for corner in bounds)
    zone = _zone(low, plateaux)
    if _zone(high, plateaux) != zone:
        return None
    # Native bounds establish zone membership. A flat axis contributes a point mass in altitude.
    altitude = [(low + high) / 2] * 2 if high - low <= 1e-8 else None
    samples = segment.get("samples_mm", [])
    points = samples if len(samples) >= 2 and all(map(_point, samples)) else None
    volume = segment.get("volume_mm3")
    return [(zone, length, volume if _number(volume) else None, points, altitude)]


def _route_zone_parts(route, plateaux):
    segments = route.get("segments")
    total = route.get("length_mm")
    if not segments or not _number(total):
        return None
    parts = [(_linear_parts if segment.get("kind", "line") == "line" else _curve_parts)(segment, plateaux)
             for segment in segments]
    if any(part is None for part in parts):
        return None
    pieces = [piece for part in parts for piece in part]
    if not math.isclose(math.fsum(piece[1] for piece in pieces), total, rel_tol=1e-9, abs_tol=1e-8):
        return None
    return pieces


def _height_quantile(segments, fraction):
    if any(altitude is None for _, _, _, _, altitude in segments):
        return None
    intervals = [(length, low, high) for _, length, _, _, (low, high) in segments]
    lo = min(start for _, start, _ in intervals)
    hi = max(end for _, _, end in intervals)
    target = math.fsum(length for length, _, _ in intervals) * fraction
    for _ in range(64):
        mid = lo + (hi - lo) / 2
        cumulative = math.fsum(length if end <= mid else length * (mid - start) / (end - start)
                               for length, start, end in intervals if start <= mid)
        if cumulative >= target:
            hi = mid
        else:
            lo = mid
    return hi


def _zone_metrics(routes, plateaux):
    if len(plateaux) != 2 or not routes:
        return {}, None, None
    by_route = [_route_zone_parts(route, plateaux) for route in routes.values()]
    if any(pieces is None for pieces in by_route):
        return {}, None, None
    segments = [segment for pieces in by_route for segment in pieces]
    volumes_known = all(_number(piece[2]) for piece in segments)
    by_zone = {
        zone: {
            "axis_length_mm": math.fsum(length for piece_zone, length, _, _, _ in segments
                                        if piece_zone == zone),
            "nominal_volume_mm3": (math.fsum(volume for piece_zone, _, volume, _, _ in segments
                                             if piece_zone == zone) if volumes_known else None),
        }
        for zone in ZONES
    }
    changes = sum(a[0] != b[0] for pieces in by_route for a, b in zip(pieces, pieces[1:]))
    return by_zone, changes, _height_quantile(segments, 0.95)


def _extraction_metrics(observed, extraction_ids):
    summaries = {}
    for port in extraction_ids:
        evidence = observed.get("extraction_evidence", {}).get(port, {})
        bounds = evidence.get("bounds_mm")
        distances = [pair.get("clearance_mm") for pair in evidence.get("measurements", [])]
        summaries[port] = {
            "envelope_volume_mm3": (math.prod(high - low for low, high in zip(*bounds))
                                    if _valid_bounds(bounds) else None),
            "min_clearance_mm": (min(distances) if distances and not evidence.get("unavailable_ids")
                                 and all(map(_number, distances)) else None),
        }
    return summaries


def measure(system, requirements, observed, candidate):
    """Recompute stable objectives from fresh native measurements and reference scope."""
    observed = _fresh(observed)
    observed_routes = observed.get("route_metrics", {})
    routes = {link["id"]: observed_routes.get(link["id"], {}) for link in system["links"]}
    plateaux = requirements.get("plateaux_mm", [])
    if len(plateaux) != 2 or not all(map(_number, plateaux)) or plateaux[0] >= plateaux[1]:
        plateaux = []
    by_zone, level_changes, height_p95 = _zone_metrics(routes, plateaux)
    families = {}
    for link in system["links"]:
        family = link.get("family", link.get("category"))
        families.setdefault(family or "NON_CLASSEE", []).append(link["id"])
    values = {
        "total_length_mm": _sum_complete(route.get("length_mm") for route in routes.values()),
        "total_cable_volume_mm3": _sum_complete(route.get("volume_mm3") for route in routes.values()),
        "unsupported_length_mm": _sum_complete(route.get("unsupported_length_mm") for route in routes.values()),
        "height_p95_mm": height_p95,
        "level_changes": level_changes,
    }
    maxima = [route.get("z_max_mm") for route in routes.values()]
    values["max_cable_z_mm"] = max(maxima) if maxima and all(map(_number, maxima)) else None
    for zone in ZONES:
        values[f"length_{zone.lower()}_mm"] = by_zone.get(zone, {}).get("axis_length_mm")
        values[f"volume_{zone.lower()}_nominal_mm3"] = by_zone.get(zone, {}).get("nominal_volume_mm3")

    anchors = observed.get("anchor_valid", {})
    attached = [anchors.get(support["id"]) for support in candidate.get("supports", [])]
    attached = [value.get("attached") if isinstance(value, dict) else value for value in attached]
    values["attached_support_count"] = (sum(attached) if all(type(value) is bool for value in attached)
                                        else None)
    values["declared_support_count"] = len(attached)
    support_volumes = {obj["id"]: obj.get("volume_mm3") for obj in observed.get("view_objects", [])
                       if obj.get("role") == "support"}
    values["attached_support_volume_mm3"] = None
    if all(type(value) is bool for value in attached):
        volumes = [support_volumes.get(support["id"]) for support, is_attached in
                   zip(candidate.get("supports", []), attached) if is_attached]
        values["attached_support_volume_mm3"] = _sum_complete(volumes) if volumes else 0
    extraction = observed.get("extraction_clear", {})
    extraction_ids = sorted(requirements.get("extraction_ports", []))
    checked = [extraction.get(port) for port in extraction_ids]
    values["blocked_extraction_count"] = (sum(not value for value in checked)
                                          if observed and all(type(value) is bool for value in checked)
                                          else None)
    by_extraction = _extraction_metrics(observed, extraction_ids)
    values["extraction_envelope_volume_mm3"] = _sum_complete(
        summary["envelope_volume_mm3"] for summary in by_extraction.values())
    clearances = [summary["min_clearance_mm"] for summary in by_extraction.values()]
    values["min_extraction_clearance_mm"] = min(clearances) if clearances and all(map(_number, clearances)) else None
    return {
        "version": 1,
        "scope": {"link_ids": sorted(routes), "plateaux_mm": list(plateaux),
                  "extraction_ids": extraction_ids, "frame": system.get("frame")},
        "values": values,
        "by_link": {link_id: {"length_mm": route.get("length_mm"),
                             "volume_mm3": route.get("volume_mm3")}
                    for link_id, route in routes.items()},
        "by_family": {
            family: {"length_mm": _sum_complete(routes[link_id].get("length_mm") for link_id in ids),
                     "volume_mm3": _sum_complete(routes[link_id].get("volume_mm3") for link_id in ids)}
            for family, ids in sorted(families.items())
        },
        "by_zone": by_zone,
        "by_extraction": by_extraction,
        "methods": {
            "route": "Mesures de l'axe et du solide issus du natif rouvert",
            "zone": "Découpe des segments droits par seuil Z et classement des courbes dont la boîte reste dans un niveau",
            "height_p95_mm": "Quantile d'altitude pondéré par la longueur des segments droits et courbes horizontales",
            "attached_support_count": "Nombre de retenues déclarées dont l'ancrage est observé",
            "declared_support_count": "Nombre de retenues déclarées dans le candidat",
            "attached_support_volume_mm3": "Somme des volumes des solides des retenues déclarées et observées comme attachées",
            "blocked_extraction_count": "Nombre de blocages pour toutes les extractions exigées et effectivement observées",
            "extraction_envelope_volume_mm3": "Somme des volumes des boîtes d'approche déclarées, sans union géométrique",
            "min_extraction_clearance_mm": "Plus petit écart entre les boîtes d'approche et les objets effectivement comparés",
        },
        "not_measured": ["longueur mutualisée physique", "congestion volumique", "masse et variété des supports",
                         "surface porteuse exploitée", "volume balayé réel des fiches", "détour admissible", "impact électronique"],
    }


def _valid_bounds(value):
    return (isinstance(value, list) and len(value) == 2 and all(map(_point, value))
            and all(low <= high for low, high in zip(*value)))


def _view_geometry(observed):
    observed = _fresh(observed)
    routes = {}
    for link_id, route in observed.get("route_metrics", {}).items():
        samples = route.get("axis_samples_mm")
        if samples and all(map(_point, samples)):
            routes[link_id] = [samples]
        else:
            routes[link_id] = [[segment["start_mm"], segment["end_mm"]]
                               for segment in route.get("segments", [])
                               if _point(segment.get("start_mm")) and _point(segment.get("end_mm"))]
    objects = [obj for obj in observed.get("view_objects", []) if _valid_bounds(obj.get("bounds_mm"))]
    return routes, objects


def view_frame(observations):
    """One world-space frame for all candidates in a visual comparison."""
    points = []
    for observed in observations:
        routes, objects = _view_geometry(observed)
        points.extend(point for chains in routes.values() for chain in chains for point in chain)
        points.extend(point for obj in objects for point in obj["bounds_mm"])
    if not points:
        return None
    return [[min(values) for values in zip(*points)], [max(values) for values in zip(*points)]]


def render_views(observed, output_dir, requirements, frame=None):
    """Render synchronised orthographic schematics, preserving the visual review's limits."""
    observed = _fresh(observed)
    routes, objects = _view_geometry(observed)
    frame = view_frame([observed]) if frame is None else frame
    if frame is None:
        return {"status": "NON_VERIFIE", "files": {}, "missing_views": ["géométrie observée"]}
    if not _valid_bounds(frame):
        raise ValueError("Cadre des vues invalide")
    diagonal = max(high - low for low, high in zip(*frame))
    scale = 470 / max(diagonal, 1)
    center = [(low + high) / 2 for low, high in zip(*frame)]
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    files = {}
    missing_views = []

    def render(name, axes, included_routes, included_objects):
        if not any(included_routes.values()) and not included_objects:
            missing_views.append(name)
            return
        x_axis, y_axis, sign = axes

        def project(point):
            return (280 + (point[x_axis] - center[x_axis]) * scale * sign,
                    280 - (point[y_axis] - center[y_axis]) * scale)

        colors = {"structure": "#607080", "support": "#186249", "extraction": "#b14b1a",
                  "reserved": "#8a4196"}
        svg = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 560 560">',
               '<rect width="560" height="560" fill="#f6f8fa"/>',
               f'<title>{escape(name)} · projection schématique CAO</title>',
               f'<text x="15" y="23" font-family="sans-serif" font-size="14">{escape(name)} · {scale:.5g} px/mm</text>',
               '<text x="15" y="543" font-family="sans-serif" font-size="11">Axes discrétisés ou cordes · boîtes englobantes</text>']
        for obj in included_objects:
            corners = list(product(*zip(*obj["bounds_mm"])))
            xs, ys = zip(*(project(point) for point in corners))
            color = colors.get(obj.get("role"), "#607080")
            svg.append(f'<rect x="{min(xs):.3f}" y="{min(ys):.3f}" width="{max(xs)-min(xs):.3f}" '
                       f'height="{max(ys)-min(ys):.3f}" fill="none" stroke="{color}">'
                       f'<title>{escape(str(obj["id"]))}</title></rect>')
        for link_id, chains in sorted(included_routes.items()):
            for chain in chains:
                positions = " ".join(f"{x:.3f},{y:.3f}" for x, y in map(project, chain))
                svg.append(f'<polyline points="{positions}" fill="none" stroke="#1266ad" '
                           f'stroke-width="2"><title>{escape(link_id)}</title></polyline>')
        svg.append("</svg>")
        name_svg = f"{name}.svg"
        (output_dir / name_svg).write_text("\n".join(svg) + "\n", encoding="utf-8")
        files[name] = name_svg

    top = (0, 1, 1)
    render("dessus", top, routes, objects)
    render("dessous", (0, 1, -1), routes, objects)
    render("profil_xz", (0, 2, 1), routes, objects)
    render("profil_yz", (1, 2, 1), routes, objects)
    render("cables", top, routes, [])
    render("supports", top, {}, [obj for obj in objects if obj.get("role") == "support"])
    render("extraction", top, {}, [obj for obj in objects if obj.get("role") == "extraction"])
    render("congestion", top, routes if any(obj.get("role") == "reserved" for obj in objects) else {},
           [obj for obj in objects if obj.get("role") == "reserved"])
    plateaux = requirements.get("plateaux_mm", [])
    by_zone = {zone: {} for zone in ZONES}
    if len(plateaux) == 2 and all(map(_number, plateaux)) and plateaux[0] < plateaux[1]:
        for link_id, route in observed.get("route_metrics", {}).items():
            for zone, _, _, points, _ in _route_zone_parts(route, plateaux) or []:
                if points:
                    by_zone[zone].setdefault(link_id, []).append(points)
    for zone in ZONES:
        render(zone.lower(), top, by_zone[zone], [])
    return {"status": "SCHEMAS_DISPONIBLES" if files else "NON_VERIFIE", "files": files,
            "missing_views": missing_views, "frame_mm": frame, "scale_px_per_mm": scale}
