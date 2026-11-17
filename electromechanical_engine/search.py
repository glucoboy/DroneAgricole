"""Bornes de recherche, présélection et rétrovalidation des variantes CAO."""

from collections import Counter, deque
from copy import deepcopy
from itertools import product
import math

from .contracts import (ContractError, FAMILIES, digest_value, indexed, number, path_points,
                        require, validate_motion_routes)

CAD_ADMISSIBLE = "VALIDE_GEOMETRIQUEMENT"
NATIVE_ADMISSION_FINDINGS = {
    "V2.REOPENED", "V2.RECOMPUTE", "V2.INVALID_OBJECTS", "V2.BROKEN_LINKS", "V2.PAIR_COVERAGE",
}


def _defect(code, object_id, evidence):
    return {"code": code, "object": object_id, "evidence": evidence}


def _declared_value(value):
    if isinstance(value, dict):
        if value.get("status") not in {"MESUREE", "DOCUMENTEE", "CALCULEE"}:
            return None
        value = value.get("value")
    if type(value) in (int, float) and math.isfinite(value) and value >= 0:
        return value
    return None


def _route_points(points):
    try:
        path_points(points, "route.points_mm")
    except ContractError:
        return None
    return points


def _resolve_routes(alternative, links, corridors, criteria):
    routes = {}
    defects = []
    reservations = []
    for link_id, proposal in sorted(alternative.get("routes", {}).items()):
        if link_id not in links:
            defects.append(_defect("LINK_UNKNOWN", link_id, {}))
            continue
        corridor_id = proposal.get("corridor")
        corridor = corridors.get(corridor_id)
        if corridor is None:
            defects.append(_defect("CORRIDOR_UNKNOWN", link_id, {"corridor": corridor_id}))
            continue
        reference_points = _route_points(corridor.get("points_mm"))
        points = _route_points(proposal.get("points_mm", reference_points))
        if points is None:
            defects.append(_defect("ROUTE_POINTS_INVALID", link_id, {"corridor": corridor_id}))
            continue
        if not corridor.get("carrier"):
            defects.append(_defect("CORRIDOR_UNANCHORED", corridor_id, {}))
        if reference_points is None or points not in (reference_points, reference_points[::-1]):
            reservations.append(_defect("CORRIDOR_DEVIATION_UNVERIFIED", link_id,
                                        {"corridor": corridor_id}))
        width = _declared_value(corridor.get("width_mm"))
        rule = criteria.get(link_id, {})
        diameter = _declared_value(rule.get("diameter_mm"))
        source = rule.get("provenance")
        if source and source.get("status") not in {"MESUREE", "DOCUMENTEE", "CALCULEE"}:
            diameter = None
        if width is None or diameter is None:
            reservations.append(_defect("CORRIDOR_CAPACITY_UNKNOWN", link_id,
                                        {"corridor": corridor_id}))
        elif diameter > width:
            defects.append(_defect("CORRIDOR_CAPACITY_EXCEEDED", link_id,
                                   {"corridor": corridor_id, "diameter_mm": diameter,
                                    "width_mm": width}))
        radius = proposal.get("bend_radius_mm")
        if radius is not None:
            number(radius, f"route {link_id}.bend_radius_mm", 0)
        routes[link_id] = {"points_mm": deepcopy(points), "corridor": corridor_id,
                           "bend_radius_mm": 0 if radius is None else radius}
    for link_id in sorted(links.keys() - alternative.get("routes", {}).keys()):
        defects.append(_defect("ROUTE_MISSING", link_id, {}))
    for corridor_id, usage in Counter(route["corridor"] for route in routes.values()).items():
        if usage > 1:
            reservations.append(_defect("CORRIDOR_SHARED_CAPACITY_UNVERIFIED", corridor_id,
                                        {"route_count": usage}))
    return routes, defects, reservations


def _candidate_signature(candidate):
    # Only physical inputs distinguish the geometry. Design hypotheses have a separate identity.
    physical_routes = tuple(
        (link_id, tuple(map(tuple, route["points_mm"])), route["bend_radius_mm"])
        for link_id, route in sorted(candidate["routes"].items())
    )
    supports = tuple(sorted((support["id"], support["anchor"]) for support in candidate["supports"]))
    motion = tuple((state, tuple((link, tuple(map(tuple, route["points_mm"])), route.get("bend_radius_mm", 0))
                                 for link, route in sorted(routes.items())))
                   for state, routes in sorted(candidate.get("motion_routes", {}).items()) if routes)
    return physical_routes, supports, motion


def _connections(system):
    ports = {port["id"]: port for port in system.get("ports", [])}
    result = []
    for link in system["links"]:
        connection = {key: link[key] for key in ("id", "source", "target")}
        for role in ("source", "target"):
            interface = ports.get(link[role], {}).get("interface")
            if interface is not None:
                connection[f"{role}_interface"] = interface
            cavities = f"{role}_cavities"
            if cavities in link:
                connection[cavities] = deepcopy(link[cavities])
        result.append(connection)
    return result


def explore(system, design_space, reference_sha256, requirements=None):
    """Resolve variants with an external design space and a frozen reference."""
    if type(design_space.get("version")) is not int or design_space["version"] != 1:
        raise ValueError("Version d'espace de conception inconnue")
    max_candidates = design_space.get("max_candidates", 8)
    if type(max_candidates) is not int or not 1 <= max_candidates <= 100:
        raise ValueError("max_candidates doit être compris entre 1 et 100")
    max_stalled = design_space.get("max_stalled_attempts", max_candidates)
    if type(max_stalled) is not int or not 1 <= max_stalled <= max_candidates:
        raise ValueError("max_stalled_attempts doit être compris entre 1 et max_candidates")
    links = {link["id"]: link for link in system["links"]}
    criteria = (requirements or {}).get("links", {})
    corridors = {corridor["id"]: corridor for corridor in system.get("corridors", [])}
    connections = _connections(system)
    alternatives = indexed(design_space.get("alternatives"), "design_space.alternatives")
    seen_ids = set()

    candidates = []
    rejected = []
    corrections = {}
    reservations_by_candidate = {}
    signatures = {}
    geometry_signatures = {}
    for candidate_id, alternative in alternatives.items():
        folded_id = candidate_id.casefold()
        basename = folded_id.partition(".")[0]
        require(folded_id not in seen_ids and not folded_id.endswith(".")
                and folded_id not in {"exploration", "exploration.json", "attempts",
                                      "campaign_context.json", "campaign_report.json"}
                and basename not in {"con", "prn", "aux", "nul"}
                and not (len(basename) == 4 and basename[:3] in {"com", "lpt"} and basename[3].isdigit()),
                f"Identifiant de variante réservé ou équivalent sur disque: {candidate_id}")
        correction = alternative.get("corrects")
        if correction is not None:
            require(isinstance(correction, dict), f"Déclencheur de correction invalide pour {candidate_id}")
            previous, codes = correction.get("candidate_id"), correction.get("codes")
            require(isinstance(previous, str) and previous in alternatives and previous.casefold() in seen_ids
                    and isinstance(codes, list) and codes
                    and all(isinstance(code, str) and code for code in codes),
                    f"Déclencheur de correction invalide pour {candidate_id}")
        seen_ids.add(folded_id)
        family = alternative["family"]
        if family not in FAMILIES:
            raise ValueError(f"Famille inconnue pour {candidate_id}: {family}")
        proposals = alternative.get("routes", {})
        require(isinstance(proposals, dict) and all(isinstance(route, dict) for route in proposals.values()),
                f"Routes invalides pour {candidate_id}")
        routes, defects, reservations = _resolve_routes(alternative, links, corridors, criteria)
        changes = deepcopy(alternative.get("changes", {}))
        hypotheses = deepcopy(alternative.get("hypotheses", []))
        require(isinstance(changes, dict) and isinstance(hypotheses, list),
                f"Changements ou hypothèses invalides pour {candidate_id}")
        conditional = family != "MATERIEL_CONSTANT" or any(changes.values()) or bool(hypotheses)
        if conditional:
            reservations.append(_defect("ARCHITECTURE_CHANGES_REQUIRE_EVIDENCE", candidate_id,
                                        {"family": family, "changes": changes, "hypotheses": hypotheses}))
        candidate = {
            "version": 1,
            "id": candidate_id,
            "family": family,
            "reference_sha256": reference_sha256,
            "connections": deepcopy(connections),
            "routes": routes,
            "supports": deepcopy(alternative.get("supports", [])),
            "changes": changes,
            "hypotheses": hypotheses,
        }
        if "motion_routes" in alternative:
            candidate["motion_routes"] = deepcopy(alternative["motion_routes"])
            validate_motion_routes(candidate["motion_routes"], system, requirements)
        if not defects:
            geometry = _candidate_signature(candidate)
            signature = geometry, (family, digest_value(changes), digest_value(hypotheses)) if conditional else None
            if signature in signatures:
                defects.append(_defect("EQUIVALENT_DESIGN", candidate_id,
                                       {"equivalent_to": signatures[signature]}))
            else:
                signatures[signature] = candidate_id
                equivalent = geometry_signatures.setdefault(geometry, candidate_id)
                if conditional and equivalent != candidate_id:
                    reservations.append(_defect("UNREALIZED_ARCHITECTURE_SHARES_GEOMETRY", candidate_id,
                                                {"equivalent_geometry_to": equivalent}))
        if defects:
            rejected.append({"candidate_id": candidate_id, "family": family, "defects": defects,
                             "changes": changes, "hypotheses": candidate["hypotheses"]})
            continue
        if correction is not None:
            corrections[candidate_id] = deepcopy(correction)
        candidates.append(candidate)
        reservations_by_candidate[candidate_id] = reservations
    return {
        "version": 1,
        "reference_sha256": reference_sha256,
        "candidates": candidates,
        "rejected": rejected,
        "corrections": corrections,
        "reservations": reservations_by_candidate,
        "max_candidates": max_candidates,
        "max_stalled_attempts": max_stalled,
    }


def _bounds(value):
    if _route_points(value) is None or len(value) != 2:
        return None
    if any(low > high for low, high in zip(*value)):
        return None
    return value


def _carrier_check(link_id, corridor, native_carrier, native_route):
    carrier = _bounds(native_carrier.get("bounds_mm"))
    cable = _bounds(native_route.get("bounds_mm"))
    limit = _declared_value(corridor.get("max_carrier_distance_mm"))
    evidence = {"criterion": "carrier_distance", "carrier": corridor["carrier"],
                "corridor": corridor["id"], "limit_mm": limit}
    if (native_carrier.get("representation") != "reference_box" or carrier is None
            or cable is None or native_route.get("solid_valid") is not True or limit is None):
        return "unknown", _defect("CORRIDOR_CARRIER_PROXIMITY_UNVERIFIED", link_id, evidence)
    low, high = carrier
    lower = math.hypot(*(max(0, a - y, x - b) for a, b, x, y in zip(low, high, *cable)))
    upper = max(math.hypot(*(max(0, a - point, point - b) for point, a, b in zip(corner, low, high)))
                for corner in product(*zip(*cable)))
    evidence.update(lower_bound_mm=lower, upper_bound_mm=upper,
                    method="enveloppe du solide câble vers la boîte porteuse native")
    if lower > limit:
        return "fail", _defect("CORRIDOR_CARRIER_TOO_FAR", link_id, evidence)
    if upper > limit:
        return "unknown", _defect("CORRIDOR_CARRIER_PROXIMITY_UNVERIFIED", link_id, evidence)
    return "pass", _defect("CORRIDOR_CARRIER_DISTANCE_BOUNDED", link_id, evidence)


def check_corridors(system, requirements, candidate, observed):
    """Apply corridor constraints to any candidate, independently of exploration."""
    links = {link["id"]: link for link in system["links"]}
    corridors = {corridor["id"]: corridor for corridor in system.get("corridors", [])}
    routes, defects, reservations = _resolve_routes(candidate, links, corridors, requirements["links"])
    carriers = {obj.get("id"): obj for obj in observed.get("view_objects", []) if obj.get("role") == "structure"}
    native_routes = observed.get("route_metrics", {})
    findings = [("fail", item) for item in defects] + [("unknown", item) for item in reservations]
    for link_id, route in routes.items():
        corridor = corridors[route["corridor"]]
        if corridor.get("carrier"):
            findings.append(_carrier_check(link_id, corridor, carriers.get(corridor["carrier"], {}),
                                           native_routes.get(link_id, {})))
    return [{"code": "V5.CORRIDOR", "status": status,
             "criticality": {"fail": "blocking", "unknown": "reserve", "pass": "none"}[status],
             "object": item["object"], "reason": item["code"], "evidence": item["evidence"]}
            for status, item in findings]


def _metric_value(metrics, key):
    value = metrics.get("values", {}).get(key)
    if type(value) in (int, float) and math.isfinite(value):
        return value
    return None


def compare_reports(baseline, candidate, objectives):
    """A metric delta can be informative even if Pareto admission is impossible."""
    left = baseline.get("metrics", {})
    right = candidate.get("metrics", {})
    scope = left.get("scope")
    reference = baseline.get("reference_sha256")
    comparable = bool(reference and reference == candidate.get("reference_sha256")
                      and scope and scope == right.get("scope")
                      and left.get("version") == right.get("version") == 1)
    deltas = {}
    missing = []
    baseline_values = []
    candidate_values = []
    for objective in objectives:
        old_value = _metric_value(left, objective)
        new_value = _metric_value(right, objective)
        if not comparable or old_value is None or new_value is None:
            missing.append(objective)
            continue
        delta = new_value - old_value
        if not math.isfinite(delta):
            raise ValueError(f"Écart de métrique non fini: {objective}")
        deltas[objective] = delta
        baseline_values.append(old_value)
        candidate_values.append(new_value)

    admissible = (comparable and bool(objectives) and not missing
                  and baseline.get("status") == candidate.get("status") == CAD_ADMISSIBLE
                  and _has_native_admission_evidence(baseline)
                  and _has_native_admission_evidence(candidate)
                  and not baseline.get("exploration_reservations")
                  and not candidate.get("exploration_reservations"))
    dominance = None
    if admissible:
        if baseline_values == candidate_values:
            dominance = "EQUIVALENT"
        elif all(old <= new for old, new in zip(baseline_values, candidate_values)):
            dominance = "BASELINE"
        elif all(new <= old for old, new in zip(baseline_values, candidate_values)):
            dominance = "CANDIDATE"
        else:
            dominance = "COMPROMIS"
    link_deltas = {}
    if comparable:
        for link_id in scope.get("link_ids", []):
            old = left.get("by_link", {}).get(link_id, {}).get("length_mm")
            new = right.get("by_link", {}).get(link_id, {}).get("length_mm")
            if (type(old) in (int, float) and type(new) in (int, float)
                    and math.isfinite(old) and math.isfinite(new) and math.isfinite(new - old)):
                link_deltas[link_id] = new - old
    return {"comparable": comparable, "admissible": admissible, "dominance": dominance,
            "deltas": deltas, "link_length_deltas_mm": link_deltas, "missing_objectives": missing}


def _has_native_admission_evidence(report):
    findings = report.get("findings")
    if not isinstance(findings, list) or any(
            not isinstance(row, dict) or row.get("status") != "pass"
            or not isinstance(row.get("code"), str) for row in findings):
        return False
    counts = Counter(row["code"] for row in findings)
    return all(counts[code] == 1 for code in NATIVE_ADMISSION_FINDINGS)


def _failed_findings(report):
    return [finding for finding in report.get("findings", [])
            if finding.get("status") in {"fail", "unknown", "NON_CONFORME", "NON_VERIFIE"}]


def _finding_key(finding, object_id):
    code = finding["code"]
    if code == "V2.PAIR" and isinstance(object_id, list):
        object_id = sorted(object_id)
    evidence = finding.get("evidence", {})
    return code, digest_value([object_id, evidence.get("state"), evidence.get("criterion")])


def _progress_key(report):
    failures = set()
    for finding in _failed_findings(report):
        subject = finding.get("object")
        if subject == report["candidate_id"]:
            subject = None
        failures.add((*_finding_key(finding, subject), finding.get("reason")))
    return report.get("status"), failures


def _resolution(report, trigger):
    if trigger is None:
        return [], []
    passed = {_finding_key(row, row.get("object")): row for row in report.get("findings", [])
              if row.get("status") == "pass" and row.get("object") is not None}
    failed = {_finding_key(row, row.get("object")) for row in _failed_findings(report)}
    resolved, unresolved_codes = [], set()
    for row in trigger["findings"]:
        key = _finding_key(row, row.get("object"))
        if key in passed and key not in failed:
            resolved.append({"before": row, "after": passed[key]})
        else:
            unresolved_codes.add(row["code"])
    return sorted(set(trigger["codes"]) - unresolved_codes), resolved


def _pareto(reports, objectives):
    eligible = [report for report in reports if compare_reports(report, report, objectives)["admissible"]]
    return [report["candidate_id"] for report in eligible
            if not any(compare_reports(report, other, objectives)["dominance"] == "CANDIDATE"
                       for other in eligible if other is not report)]


def _signal(report, reports, objectives):
    if compare_reports(report, report, objectives)["admissible"]:
        return not any(compare_reports(previous, report, objectives)["dominance"] in {"BASELINE", "EQUIVALENT"}
                       for previous in reports)
    signature = _progress_key(report)
    return all(signature != _progress_key(previous) for previous in reports)


def run_feedback(exploration, evaluate, objectives, record_attempt=None):
    """Build/evaluate alternatives within budget, promoting matched corrections."""
    candidates = {candidate["id"]: candidate for candidate in exploration["candidates"]}
    corrections = exploration["corrections"]
    queue = deque((candidate_id, None) for candidate_id in candidates if candidate_id not in corrections)

    def queue_corrections(previous_id, failures):
        for next_id, correction in reversed(list(corrections.items())):
            if correction["candidate_id"] != previous_id:
                continue
            matched = [finding for finding in failures if finding["code"] in correction["codes"]]
            if matched:
                queue.appendleft((next_id, {"candidate_id": previous_id,
                                            "codes": sorted({finding["code"] for finding in matched}),
                                            "findings": deepcopy(matched)}))

    for rejection in reversed(exploration["rejected"]):
        queue_corrections(rejection["candidate_id"], rejection["defects"])
    attempts = []
    reports = []
    processed = set()
    budget = exploration["max_candidates"]
    stalled = 0
    while queue and len(attempts) < budget and stalled < exploration["max_stalled_attempts"]:
        candidate_id, triggered_by = queue.popleft()
        if candidate_id in processed:
            continue
        report = deepcopy(evaluate(deepcopy(candidates[candidate_id])))
        if report.get("reference_sha256") != exploration["reference_sha256"]:
            raise ValueError(f"Empreinte de rapport incompatible pour {candidate_id}")
        if report.get("candidate_id", candidate_id) != candidate_id:
            raise ValueError(f"Identité de rapport incompatible pour {candidate_id}")
        report["candidate_id"] = candidate_id
        report["exploration_reservations"] = deepcopy(exploration["reservations"][candidate_id])
        signal = _signal(report, reports, objectives)
        stalled = 0 if signal else stalled + 1
        reports.append(report)
        processed.add(candidate_id)
        resolved_codes, resolved_findings = _resolution(report, triggered_by)
        attempt = {"candidate_id": candidate_id, "triggered_by": triggered_by,
                   "resolved_trigger_codes": resolved_codes, "resolved_trigger_findings": resolved_findings,
                   "new_signal": signal, "report": report}
        attempts.append(attempt)
        if record_attempt is not None:
            record_attempt(len(attempts), attempt)
        queue_corrections(candidate_id, _failed_findings(report))

    pending = {candidate_id for candidate_id, _ in queue}
    stop_reason = "ALTERNATIVES_EXHAUSTED"
    if pending:
        stop_reason = "BUDGET" if len(attempts) == budget else "NO_PROGRESS"
    skipped = [{"candidate_id": candidate_id,
                "reason": stop_reason if candidate_id in pending else "TRIGGER_NOT_OBSERVED"}
               for candidate_id in candidates.keys() - processed]
    return {
        "version": 1,
        "reference_sha256": exploration["reference_sha256"],
        "attempts": attempts,
        "rejected": deepcopy(exploration["rejected"]),
        "skipped": sorted(skipped, key=lambda item: item["candidate_id"]),
        "objectives": list(objectives),
        "pareto": _pareto(reports, objectives),
        "stop_reason": stop_reason,
        "optimality_proven": False,
    }
