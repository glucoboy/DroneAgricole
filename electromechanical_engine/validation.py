"""Deterministic verdicts on frozen requirements and independent CAD observations."""

from collections import Counter, defaultdict
from math import isfinite, ulp


PASS = "pass"
FAIL = "fail"
UNKNOWN = "unknown"
ESTABLISHED = {"MESUREE", "DOCUMENTEE", "CALCULEE"}


def _finding(code, status, subject, reason, **evidence):
    return {"code": code, "status": status, "object": subject, "reason": reason,
            "criticality": {PASS: "none", FAIL: "blocking", UNKNOWN: "reserve"}[status],
            "evidence": evidence}


def _boolean(value):
    if value is True:
        return PASS
    return FAIL if value is False else UNKNOWN


def _combine(*statuses):
    return FAIL if FAIL in statuses else UNKNOWN if UNKNOWN in statuses else PASS


def _nonnegative(value):
    return type(value) in (int, float) and isfinite(value) and value >= 0


def _minimum(measured, required):
    if not (_nonnegative(measured) and _nonnegative(required)):
        return UNKNOWN
    return PASS if measured >= required else FAIL


def _bend_radius_finding(code, measurement, required, subject, reason, **evidence):
    radius = measurement.get("min_radius_mm")
    certified = measurement.get("radius_certified")
    method = measurement.get("radius_evidence", measurement.get("measurement", {}).get("radius_evidence"))
    roundoff = 0.0
    if not _nonnegative(required) or required == 0:
        status = UNKNOWN
    else:
        # The circular radius passes through OCCT construction and reciprocal
        # conversions. The saved F16 arc benchmark differs by 13 ULP at 22 mm.
        if certified is True and method == "analytic_lines_circles":
            roundoff = 16 * ulp(required)
        if _nonnegative(radius) and radius < required and (radius == 0 or required - radius > roundoff):
            # A sampled radius can refute the requirement without a global bound.
            status = FAIL
        elif certified is True and "min_radius_mm" in measurement and (radius is None or _nonnegative(radius)):
            # A certified null radius denotes a straight path with zero curvature.
            status = PASS
        else:
            status = UNKNOWN
    return _finding(code, status, subject, reason, measured_mm=radius, required_mm=required,
                    certified=certified, method=method, roundoff_tolerance_mm=roundoff, **evidence)


def _connector_option(port, connector):
    if connector is None:
        return PASS, "reference_connector", None
    catalogue = port.get("connector_options")
    if catalogue is None:
        return UNKNOWN, "connector_catalogue_missing", None
    option = next((row for row in catalogue if row["id"] == connector), None)
    if option is None:
        return FAIL, "connector_outside_frozen_catalogue", None
    if option.get("status") not in ESTABLISHED or not option.get("source") or option.get("interface") is None:
        return UNKNOWN, "connector_option_not_established", option
    if option["interface"] != port.get("interface"):
        return FAIL, "incompatible_connector_option", option
    return PASS, "matches_reference", option


def _endpoint(role, link, port, connection):
    actual_port = connection.get(role)
    interface = port.get("interface")
    actual_interface = connection.get(f"{role}_interface")
    cavity_field = f"{role}_cavities"
    cavities, actual_cavities = link.get(cavity_field), connection.get(cavity_field)
    connector = connection.get(f"{role}_connector")
    option = None
    if actual_port != link[role]:
        status, reason = FAIL, "wrong_port"
    else:
        interface_status = UNKNOWN
        if port.get("status") in ESTABLISHED and interface is not None and actual_interface is not None:
            interface_status = _boolean(actual_interface == interface)
        cavity_status = PASS
        if cavity_field in link or cavity_field in connection:
            cavity_status = UNKNOWN if cavities is None or actual_cavities is None else _boolean(
                actual_cavities == cavities)
        connector_status, connector_reason, option = _connector_option(port, connector)
        checks = [(interface_status, "interface_mismatch" if interface_status == FAIL else "interface_not_established"),
                  (cavity_status, "cavities_mismatch" if cavity_status == FAIL else "cavities_not_established"),
                  (connector_status, connector_reason)]
        status = _combine(*(outcome for outcome, _ in checks))
        reason = next(message for outcome, message in checks if outcome == status) if status != PASS else connector_reason
    return {"status": status, "reason": reason, "expected_port": link[role], "declared_port": actual_port,
            "expected_interface": interface, "declared_interface": actual_interface, "port_status": port.get("status"),
            "expected_cavities": cavities, "declared_cavities": actual_cavities,
            "cavities_in_scope": cavity_field in link or cavity_field in connection,
            "declared_connector": connector, "catalogue_option": option}


def _connectivity(system, candidate):
    ports = {item["id"]: item for item in system["ports"]}
    connections = defaultdict(list)
    for connection in candidate["connections"]:
        connections[connection["id"]].append(connection)
    for link in system["links"]:
        identity = link["id"]
        matched = connections.pop(identity, [])
        if len(matched) != 1:
            yield _finding("V1.CONNECTION", FAIL, identity, "connection_count",
                           expected=1, observed=len(matched))
            continue
        connection = matched[0]
        endpoints = {role: _endpoint(role, link, ports[link[role]], connection)
                     for role in ("source", "target")}
        status = _combine(*(item["status"] for item in endpoints.values()))
        link_source = link.get("provenance")
        if link_source is not None and link_source.get("status") not in ESTABLISHED:
            status = _combine(status, UNKNOWN)
        yield _finding("V1.CONNECTION", status, identity, "endpoint_identity_and_interfaces",
                       **endpoints, link_provenance=link_source)
    for identity, rows in sorted(connections.items()):
        yield _finding("V1.UNEXPECTED_CONNECTION", FAIL, identity, "outside_reference_inventory",
                       observed=len(rows))


def _native_state(observed):
    for code, field in (("V2.REOPENED", "reopened"), ("V2.RECOMPUTE", "recompute_ok")):
        yield _finding(code, _boolean(observed.get(field)), "assembly", field,
                       observed=observed.get(field), backend=observed.get("backend"))
    for code, field in (("V2.INVALID_OBJECTS", "invalid_objects"), ("V2.BROKEN_LINKS", "broken_links")):
        issues = observed.get(field)
        outcome = (FAIL if issues else PASS) if isinstance(issues, list) else UNKNOWN
        yield _finding(code, outcome, "assembly", field, objects=issues)


def _route_checks(system, requirements, candidate, observed):
    for link in system["links"]:
        identity = link["id"]
        if identity not in candidate["routes"]:
            yield _finding("V2.ROUTE", FAIL, identity, "route_missing_from_candidate")
            continue
        measurement = observed.get("route_metrics", {}).get(identity, {})
        criteria = requirements["links"][identity]
        source = criteria.get("provenance", requirements.get("provenance", {}))
        if source.get("status") not in ESTABLISHED:
            yield _finding("V2.ROUTE_PROVENANCE", UNKNOWN, identity,
                           "route_criteria_not_established", provenance=source)
        flags = {field: measurement.get(field) for field in
                 ("solid_valid", "continuity_ok", "tangency_ok", "endpoints_ok")}
        length = measurement.get("length_mm")
        axis = measurement.get("measurement", {})
        solid = measurement.get("solid_measurement", {})
        length_status = UNKNOWN if not _nonnegative(length) else PASS if length > 0 else FAIL
        yield _finding("V2.ROUTE", _combine(length_status, *map(_boolean, flags.values())),
                       identity, "saved_solid_axis_and_connectors", length_mm=length,
                       axis_failures=axis.get("failures"), solid_failures=solid.get("failures"), **flags)
        minimum = criteria.get("min_radius_mm")
        yield _bend_radius_finding("V2.RADIUS", measurement, minimum, identity, "static_bend_radius")
        diameter = criteria.get("diameter_mm")
        measured_diameter = measurement.get("diameter_mm")
        if not _nonnegative(diameter) or diameter == 0:
            yield _finding("V2.ENVELOPE", UNKNOWN, identity, "cable_diameter_unknown",
                           required_mm=diameter, measured_mm=measured_diameter)
        else:
            tolerance = requirements.get("position_tolerance_mm", 1e-5)
            outcome = UNKNOWN
            if _nonnegative(measured_diameter) and _nonnegative(tolerance):
                outcome = PASS if abs(measured_diameter - diameter) <= tolerance else FAIL
            yield _finding("V2.ENVELOPE", outcome, identity, "cable_diameter_match",
                           required_mm=diameter, measured_mm=measured_diameter, tolerance_mm=tolerance)
    extra_routes = set(candidate["routes"]) - {link["id"] for link in system["links"]}
    for identity in sorted(extra_routes):
        yield _finding("V2.ROUTE", FAIL, identity, "route_outside_reference_inventory")


def _pair_status(pair, permission, tolerance, clearance, distance_tolerance):
    volume = pair.get("intersection_mm3")
    distance = pair.get("clearance_mm")
    if not (_nonnegative(volume) and _nonnegative(tolerance)):
        return UNKNOWN, "intersection_unmeasured"
    if permission and permission["relation"] == "cable_in_conduit_envelope":
        declared = permission.get("outer_representation")
        observed = pair.get("outer_representation")
        if declared == observed == "occupancy_envelope":
            outside = pair.get("outside_envelope_volume_mm3")
            if not _nonnegative(outside):
                return UNKNOWN, "containment_unmeasured"
            if outside <= tolerance:
                return PASS, "verified_occupancy_envelope_containment"
        elif declared == "occupancy_envelope" and observed is None and volume > tolerance:
            return UNKNOWN, "conduit_representation_unverified"
    if volume > tolerance:
        return FAIL, "forbidden_interference"
    if not (_nonnegative(distance) and _nonnegative(clearance) and _nonnegative(distance_tolerance)):
        return UNKNOWN, "clearance_unmeasured"
    if permission and permission["relation"] == "functional_contact" and distance <= distance_tolerance:
        return PASS, "authorized_functional_contact"
    if distance + distance_tolerance < clearance:
        return FAIL, "insufficient_clearance"
    return PASS, "clearance_checked"


def _collisions(system, requirements, observed):
    pairs = observed.get("collisions")
    filtered = observed.get("collision_filtered_evidence", [])
    has_pair_lists = isinstance(pairs, list) and isinstance(filtered, list)
    pairs = pairs if isinstance(pairs, list) else []
    filtered = filtered if isinstance(filtered, list) else []
    shape_ids = {row["id"] for row in system["links"]}
    shape_ids.update(row["id"] for row in system.get("geometry", {}).get("boxes", []))
    expected = len(shape_ids) * (len(shape_ids) - 1) // 2
    identities = [frozenset((pair["a"], pair["b"])) for pair in pairs + filtered]
    complete = (has_pair_lists and observed.get("collision_complete") is True
                and len(identities) == len(set(identities)) == expected
                and all(len(pair) == 2 and pair <= shape_ids for pair in identities))
    yield _finding("V2.PAIR_COVERAGE", PASS if complete else UNKNOWN, "assembly",
                   "potentially_relevant_pair_coverage", tested=len(pairs), filtered=len(filtered),
                   expected=expected)
    permissions = {(row["a"], row["b"]): row for row in requirements.get("allowed_contacts", [])
                   if row.get("source")}
    volume = requirements["collision_tolerance_mm3"]
    clearance = requirements["clearance_mm"]
    tolerance = requirements.get("clearance_tolerance_mm", 1e-6)
    for pair in pairs:
        a, b = pair["a"], pair["b"]
        permission = permissions.get((a, b))
        reverse = permissions.get((b, a), {})
        if not permission and reverse.get("relation") == "functional_contact":
            permission = reverse
        status, reason = _pair_status(pair, permission, volume, clearance, tolerance)
        yield _finding("V2.PAIR", status, [a, b], reason, measurement=pair,
                       permission=permission, required_clearance_mm=clearance,
                       volume_tolerance_mm3=volume, distance_tolerance_mm=tolerance)
    measured_pairs = {frozenset((pair["a"], pair["b"])) for pair in pairs}
    permitted_pairs = {frozenset(pair) for pair in permissions}
    for pair in filtered:
        a, b = pair["a"], pair["b"]
        identity = frozenset((a, b))
        lower_bound = pair.get("clearance_lower_bound_mm")
        certified = (complete and len(identity) == 2 and identity not in measured_pairs | permitted_pairs
                     and _nonnegative(lower_bound) and lower_bound > clearance)
        yield _finding("V2.PAIR", PASS if certified else UNKNOWN, [a, b], "bounding_box_clearance_lower_bound",
                       clearance_lower_bound_mm=lower_bound, required_clearance_mm=clearance)
        measured_pairs.add(identity)


def _assembly(requirements, candidate, observed):
    for port in requirements.get("extraction_ports", []):
        clear = observed.get("extraction_clear", {}).get(port)
        evidence = observed.get("extraction_evidence", {}).get(port)
        status = _boolean(clear)
        if status == PASS:
            measurements = evidence.get("measurements", []) if isinstance(evidence, dict) else []
            if (not measurements or evidence.get("unavailable_ids")
                    or any(pair.get("status") != PASS for pair in measurements)):
                status = UNKNOWN
        yield _finding("V3.EXTRACTION", status, port, "extraction_swept_volume", clear=clear,
                       measurements=evidence)
    supports = {item["id"]: item for item in candidate.get("supports", [])}
    for item in requirements.get("supports", []):
        identity, expected = item["id"], item["anchor"]
        present = supports.get(identity)
        if present is None or present.get("anchor") != expected:
            yield _finding("V3.ANCHOR", FAIL, identity, "required_support_or_anchor_missing",
                           required_anchor=expected, declared=present)
            continue
        measurement = observed.get("anchor_valid", {}).get(identity)
        if isinstance(measurement, dict):
            anchor = measurement.get("anchor")
            anchor_matches = UNKNOWN if anchor is None else _boolean(anchor == expected)
            status = _combine(anchor_matches, _boolean(measurement.get("attached")),
                              _boolean(measurement.get("access_clear")))
        else:
            status = FAIL if measurement is False else UNKNOWN
        yield _finding("V3.ANCHOR", status, identity, "physical_attachment_and_access",
                       required_anchor=expected, measurement=measurement)
    required_ids = {item["id"] for item in requirements.get("supports", [])}
    for identity in sorted(set(supports) - required_ids):
        yield _finding("V3.ANCHOR", UNKNOWN, identity, "support_outside_verified_anchor_scope",
                       declared=supports[identity])
    for identity, criteria in requirements["links"].items():
        if "max_unsupported_mm" not in criteria and not criteria.get("requires_support"):
            continue
        maximum = criteria.get("max_unsupported_mm")
        measurement = observed.get("route_metrics", {}).get(identity, {})
        span = measurement.get("unsupported_span_mm")
        yield _finding("V3.UNSUPPORTED_SPAN", _minimum(maximum, span), identity,
                       "longest_unsupported_span", observed_mm=span, maximum_mm=maximum,
                       retention=measurement.get("retention_evidence"))


def _motion(system, requirements, observed):
    mobile_links = {link["id"] for link in system["links"] if link.get("mobile") is True}
    reference_states = system.get("geometry", {}).get("motion_states", {})
    for identity, criteria in requirements["links"].items():
        states = criteria.get("required_motion_states", [])
        needs_motion = identity in mobile_links or {"min_dynamic_radius_mm", "min_reserve_mm"} & criteria.keys()
        if not states and needs_motion:
            yield _finding("V4.STATE_COVERAGE", UNKNOWN, identity, "motion_states_unspecified")
        for state in states:
            measurement = observed.get("motion", {}).get(identity, {}).get(state, {})
            source = reference_states.get(state, {}).get("provenance", {})
            if source.get("status") not in ESTABLISHED:
                yield _finding("V4.STATE_REFERENCE", UNKNOWN, identity, "motion_state_reference_unestablished",
                               state=state, provenance=source)
            flags = {field: measurement.get(field) for field in
                     ("solid_valid", "continuity_ok", "tangency_ok", "endpoints_ok", "diameter_ok")}
            yield _finding("V4.STATE_GEOMETRY", _combine(*map(_boolean, flags.values())), identity,
                           "saved_motion_solid_axis_and_connectors", state=state, **flags)
            nominal = observed.get("route_metrics", {}).get(identity, {}).get("length_mm")
            length = measurement.get("length_mm")
            tolerance = criteria.get("motion_length_tolerance_mm")
            delta = abs(length - nominal) if _nonnegative(nominal) and _nonnegative(length) else None
            length_status = UNKNOWN if not (_nonnegative(delta) and _nonnegative(tolerance)) else (
                PASS if delta <= tolerance else FAIL)
            yield _finding("V4.LENGTH", length_status, identity, "developed_length_conservation",
                           state=state, nominal_mm=nominal, measured_mm=length,
                           difference_mm=delta, tolerance_mm=tolerance)
            clear, reserve = measurement.get("clearance_ok"), measurement.get("reserve_mm")
            required_reserve = criteria.get("min_reserve_mm")
            required_radius = criteria.get("min_dynamic_radius_mm")
            yield _finding("V4.CLEARANCE", _boolean(clear), identity, "clearance_at_motion_state",
                           state=state, clear=clear, pairs=measurement.get("clearance_pairs"),
                           missing_shapes=measurement.get("missing_shapes"))
            yield _finding("V4.RESERVE", _minimum(reserve, required_reserve), identity, "geometric_reserve",
                           state=state, measured_mm=reserve, required_mm=required_reserve,
                           method=measurement.get("reserve_method"))
            yield _bend_radius_finding("V4.RADIUS", measurement, required_radius, identity, "dynamic_bend_radius",
                                       state=state)


def validate(system, requirements, candidate, observed):
    """Assess parsed contracts. Observations must come from the independent adapter."""
    findings = list(_connectivity(system, candidate))
    for subject, document in (("system", system), ("requirements", requirements)):
        source = document.get("provenance", {})
        if source.get("status") not in ESTABLISHED:
            findings.append(_finding("V1.REFERENCE_PROVENANCE", UNKNOWN, subject,
                                     "reference_contains_unestablished_data", provenance=source))
    native = list(_native_state(observed))
    findings.extend(native)
    # Never apply apparently favorable measurements from an invalid/stale document.
    fresh = observed if all(item["status"] == PASS for item in native) else {}
    findings.extend(_route_checks(system, requirements, candidate, fresh))
    findings.extend(_collisions(system, requirements, fresh))
    findings.extend(_assembly(requirements, candidate, fresh))
    findings.extend(_motion(system, requirements, fresh))

    domains = {}
    for domain in ("V1", "V2", "V3", "V4"):
        statuses = Counter(item["status"] for item in findings if item["code"].startswith(domain + "."))
        domains[domain] = {key: statuses[key] for key in (PASS, FAIL, UNKNOWN)}
    connection_statuses = Counter(item["status"] for item in findings if item["code"] == "V1.CONNECTION")
    coverage = {"inventoried": len(system["links"]), "evaluated": sum(connection_statuses.values()),
                **{key: connection_statuses[key] for key in (PASS, FAIL, UNKNOWN)}}
    if any(item["status"] == FAIL for item in findings):
        verdict = "NON_CONFORME"
    elif not any(item["status"] == PASS for item in findings):
        verdict = "NON_VERIFIE"
    elif any(item["status"] == UNKNOWN for item in findings):
        verdict = "CANDIDAT_CONDITIONNEL"
    else:
        verdict = "VALIDE_GEOMETRIQUEMENT"
    return {"status": verdict, "findings": findings, "domains": domains,
            "connection_coverage": coverage, "validation_physique": "VALIDATION_PHYSIQUE_REQUISE"}
