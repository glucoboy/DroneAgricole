"""V1–V4 on synthetic observations, independently of the FreeCAD runtime."""

import unittest

from electromechanical_engine.validation import validate


class ValidationTests(unittest.TestCase):
    def setUp(self):
        provenance = {"status": "DOCUMENTEE", "source": "synthetic test definition"}
        self.system = {
            "provenance": provenance,
            "ports": [{"id": name, "status": "DOCUMENTEE", "interface": "2-pin"}
                      for name in ("A", "B", "C")],
            "links": [{"id": "L1", "source": "A", "target": "B", "family": "signal"}],
            "geometry": {"boxes": [{"id": "frame"}]},
        }
        self.rules = {
            "provenance": provenance,
            "clearance_mm": 0.5,
            "collision_tolerance_mm3": 0.000001,
            "links": {"L1": {"min_radius_mm": 5, "diameter_mm": 1}},
            "supports": [{"id": "clip", "anchor": "frame"}],
            "extraction_ports": ["A"],
        }
        self.candidate = {
            "id": "test", "connections": [{"id": "L1", "source": "A", "target": "B",
                                            "source_interface": "2-pin", "target_interface": "2-pin"}],
            "routes": {"L1": {"points_mm": [[0, 0, 0], [40, 0, 0]], "corridor": "rail"}},
            "supports": [{"id": "clip", "anchor": "frame"}],
        }
        self.observed = {
            "backend": "synthetic unit fixture", "reopened": True, "recompute_ok": True,
            "invalid_objects": [], "broken_links": [], "collision_complete": True,
            "collisions": [{"a": "L1", "b": "frame", "intersection_mm3": 0, "clearance_mm": 1}],
            "route_metrics": {"L1": {"length_mm": 40, "min_radius_mm": 6, "radius_certified": True,
                                     "continuity_ok": True, "tangency_ok": True, "endpoints_ok": True,
                                     "solid_valid": True, "diameter_mm": 1}},
            "extraction_clear": {"A": True},
            "extraction_evidence": {"A": {"measurements": [{"b": "frame", "clearance_mm": 2, "status": "pass"}],
                                         "unavailable_ids": []}},
            "anchor_valid": {"clip": {"anchor": "frame", "attached": True, "access_clear": True}},
        }

    def report(self):
        return validate(self.system, self.rules, self.candidate, self.observed)

    def assert_finding(self, code, status, reason=None):
        findings = [item for item in self.report()["findings"] if item["code"] == code]
        self.assertTrue(any(item["status"] == status and (reason is None or item["reason"] == reason)
                            for item in findings), findings)

    def test_valid_connections_and_cad(self):
        report = self.report()
        self.assertEqual(report["status"], "VALIDE_GEOMETRIQUEMENT")
        self.assertEqual(report["validation_physique"], "VALIDATION_PHYSIQUE_REQUISE")
        self.assertEqual(report["connection_coverage"],
                         {"inventoried": 1, "evaluated": 1, "pass": 1, "fail": 0, "unknown": 0})

    def test_port_identity_even_if_interfaces_match(self):
        self.candidate["connections"][0]["target"] = "C"
        self.assert_finding("V1.CONNECTION", "fail")
        self.assertEqual(self.report()["status"], "NON_CONFORME")

    def test_missing_duplicate_and_unexpected_connections(self):
        original = self.candidate["connections"][0]
        for connections in ([], [original, original]):
            with self.subTest(connections=connections):
                self.candidate["connections"] = connections
                self.assert_finding("V1.CONNECTION", "fail", "connection_count")
                self.assertEqual(self.report()["connection_coverage"]["evaluated"], 1)
        self.candidate["connections"] = [original, dict(original, id="UNEXPECTED")]
        self.assert_finding("V1.UNEXPECTED_CONNECTION", "fail")

    def test_incompatible_connector_or_cavity(self):
        self.candidate["connections"][0]["target_interface"] = "1-pin"
        self.assert_finding("V1.CONNECTION", "fail")
        self.candidate["connections"][0]["target_interface"] = "2-pin"
        self.system["links"][0]["target_cavities"] = ["1", "2"]
        self.candidate["connections"][0]["target_cavities"] = ["2", "1"]
        self.assert_finding("V1.CONNECTION", "fail")

    def test_incomplete_endpoint_declaration_is_not_filled_by_reference(self):
        link = self.system["links"][0]
        connection = self.candidate["connections"][0]
        del connection["source_interface"]
        self.assert_finding("V1.CONNECTION", "unknown")
        connection["source_interface"] = "2-pin"
        link["target_cavities"] = ["1", "2"]
        self.assert_finding("V1.CONNECTION", "unknown")
        connection["target_cavities"] = ["1", "2"]
        self.assert_finding("V1.CONNECTION", "pass")
        link["target_cavities"] = None
        self.assert_finding("V1.CONNECTION", "unknown")

    def test_elbow_uses_the_frozen_mating_catalogue(self):
        port = self.system["ports"][0]
        port["connector_options"] = [
            {"id": "elbow-2", "interface": "2-pin", "status": "DOCUMENTEE", "source": "test drawing 1"},
            {"id": "elbow-4", "interface": "4-pin", "status": "DOCUMENTEE", "source": "test drawing 2"},
            {"id": "elbow-candidate", "interface": "2-pin", "status": "HYPOTHESE", "source": "study"},
        ]
        for part, status in (("elbow-2", "pass"), ("elbow-4", "fail"),
                             ("elbow-candidate", "unknown"), ("unknown-part", "fail")):
            with self.subTest(part=part):
                self.candidate["connections"][0]["source_connector"] = part
                self.assert_finding("V1.CONNECTION", status)

    def test_unknown_supplier_port_and_radius(self):
        self.system["ports"][0].update(interface=None, status="INCONNUE")
        self.rules["links"]["L1"]["min_radius_mm"] = None
        self.assert_finding("V1.CONNECTION", "unknown")
        self.assert_finding("V2.RADIUS", "unknown")
        self.assertEqual(self.report()["status"], "CANDIDAT_CONDITIONNEL")

    def test_unmeasured_envelope_cannot_be_replaced_by_nominal_diameter(self):
        del self.observed["route_metrics"]["L1"]["diameter_mm"]
        self.assert_finding("V2.ENVELOPE", "unknown")
        self.assertEqual(self.report()["status"], "CANDIDAT_CONDITIONNEL")

    def test_exact_radius_and_observed_local_spline_minimum(self):
        route = self.observed["route_metrics"]["L1"]
        route.update(min_radius_mm=None, radius_certified=True)
        self.assert_finding("V2.RADIUS", "pass")
        route.update(min_radius_mm=4.9, radius_certified=True)
        self.assert_finding("V2.RADIUS", "fail")
        route.update(min_radius_mm=0.4, radius_certified=False)
        self.assert_finding("V2.RADIUS", "fail")
        route.update(min_radius_mm=5.1, radius_certified=False)
        self.assert_finding("V2.RADIUS", "unknown")

    def test_collision_clearance_and_unmeasured_pair(self):
        pair = self.observed["collisions"][0]
        pair.update(intersection_mm3=2, clearance_mm=0)
        self.assert_finding("V2.PAIR", "fail", "forbidden_interference")
        pair.update(intersection_mm3=0, clearance_mm=0.1)
        self.assert_finding("V2.PAIR", "fail", "insufficient_clearance")
        pair["clearance_mm"] = None
        self.assert_finding("V2.PAIR", "unknown", "clearance_unmeasured")

    def test_filtered_pair_records_bound_for_the_same_unordered_identity(self):
        pair = {"a": "L1", "b": "obstacle", "clearance_lower_bound_mm": 2}
        self.system["geometry"]["boxes"].append({"id": "obstacle"})
        self.observed["collision_filtered_evidence"] = [pair, dict(pair, a="frame")]
        finding = next(item for item in self.report()["findings"] if item["object"] == ["L1", "obstacle"])
        self.assertEqual(finding["status"], "pass")
        self.assertEqual(finding["evidence"]["clearance_lower_bound_mm"], 2)
        pair["clearance_lower_bound_mm"] = 0.3
        self.assert_finding("V2.PAIR", "unknown", "bounding_box_clearance_lower_bound")

    def test_collision_coverage_rejects_missing_duplicate_and_unexpected_pairs(self):
        expected = self.observed["collisions"][0]
        self.assert_finding("V2.PAIR_COVERAGE", "pass")
        for incomplete in ([], [expected, expected], [dict(expected, b="unexpected")]):
            with self.subTest(collisions=incomplete):
                self.observed["collisions"] = incomplete
                self.assert_finding("V2.PAIR_COVERAGE", "unknown")
                self.assertEqual(self.report()["status"], "CANDIDAT_CONDITIONNEL")

    def test_contained_cable_exception_cannot_exempt_the_sheath_material(self):
        self.rules["allowed_contacts"] = [{"a": "L1", "b": "sheath", "source": "fixture",
                                           "relation": "cable_in_conduit_envelope",
                                           "outer_representation": "occupancy_envelope"}]
        pair = self.observed["collisions"][0]
        pair.update(b="sheath", intersection_mm3=2, clearance_mm=0,
                    outer_representation="occupancy_envelope", outside_envelope_volume_mm3=0)
        self.assert_finding("V2.PAIR", "pass", "verified_occupancy_envelope_containment")
        pair["outside_envelope_volume_mm3"] = 0.1
        self.assert_finding("V2.PAIR", "fail", "forbidden_interference")
        pair.update(outer_representation="physical_wall", outside_envelope_volume_mm3=0)
        self.assert_finding("V2.PAIR", "fail", "forbidden_interference")

    def test_functional_contact_allows_no_positive_intersection(self):
        self.rules["allowed_contacts"] = [{"a": "deck", "b": "obstacle", "source": "fixture",
                                           "relation": "functional_contact"}]
        pair = self.observed["collisions"][0]
        pair.update(a="obstacle", b="deck", clearance_mm=0, intersection_mm3=0.0000005)
        self.assert_finding("V2.PAIR", "pass", "authorized_functional_contact")
        pair["intersection_mm3"] = 0.1
        self.assert_finding("V2.PAIR", "fail", "forbidden_interference")

    def test_claims_cannot_replace_frozen_criteria_or_adapter_observations(self):
        self.candidate["routes"]["L1"].update(min_radius_mm=1, clearance_mm=0, solid_valid=True)
        self.candidate["changes"] = {"allowed_contacts": [{"a": "L1", "b": "frame"}]}
        self.observed["route_metrics"]["L1"].update(min_radius_mm=2, solid_valid=False)
        self.observed["collisions"][0].update(intersection_mm3=1, authorized_relation=True)
        self.assert_finding("V2.RADIUS", "fail")
        self.assert_finding("V2.ROUTE", "fail")
        self.assert_finding("V2.PAIR", "fail", "forbidden_interference")

    def test_favorable_measures_against_hypothetical_requirement_are_conditional(self):
        self.rules["links"]["L1"]["provenance"] = {"status": "HYPOTHESE", "source": "study"}
        self.assert_finding("V2.RADIUS", "pass")
        self.assert_finding("V2.ROUTE_PROVENANCE", "unknown")
        self.assertEqual(self.report()["status"], "CANDIDAT_CONDITIONNEL")

    def test_mated_connector_with_blocked_extraction(self):
        self.observed["extraction_clear"]["A"] = False
        self.assert_finding("V2.PAIR", "pass")
        self.assert_finding("V3.EXTRACTION", "fail")

    def test_extraction_does_not_pass_without_a_measured_obstacle(self):
        evidence = self.observed["extraction_evidence"]["A"]
        evidence["measurements"] = []
        self.assert_finding("V3.EXTRACTION", "unknown")
        evidence["measurements"] = [{"b": "frame", "clearance_mm": 2, "status": "pass"}]
        evidence["unavailable_ids"] = ["unmeasured"]
        self.assert_finding("V3.EXTRACTION", "unknown")
        evidence["unavailable_ids"] = []
        evidence["measurements"][0]["status"] = "fail"
        self.assert_finding("V3.EXTRACTION", "unknown")

    def test_floating_support_and_unknown_tool_access(self):
        measurement = self.observed["anchor_valid"]["clip"]
        measurement["access_clear"] = None
        self.assert_finding("V3.ANCHOR", "unknown")
        measurement["attached"] = False
        self.assert_finding("V3.ANCHOR", "fail")

    def test_anchor_needs_both_attachment_and_access_observations(self):
        self.observed["anchor_valid"]["clip"] = True
        self.assert_finding("V3.ANCHOR", "unknown")

    def test_longest_unsupported_span(self):
        self.rules["links"]["L1"]["max_unsupported_mm"] = 20
        self.assert_finding("V3.UNSUPPORTED_SPAN", "unknown")
        self.observed["route_metrics"]["L1"]["unsupported_span_mm"] = 30
        self.assert_finding("V3.UNSUPPORTED_SPAN", "fail")
        self.observed["route_metrics"]["L1"]["unsupported_span_mm"] = 20
        self.assert_finding("V3.UNSUPPORTED_SPAN", "pass")

    def test_motion_pass_fail_and_unverified_states(self):
        states = ["min", "nominal", "max"]
        self.rules["links"]["L1"].update(required_motion_states=states,
                                         min_reserve_mm=4, min_dynamic_radius_mm=8,
                                         motion_length_tolerance_mm=0.1)
        self.assert_finding("V4.RADIUS", "unknown")
        self.assert_finding("V4.STATE_REFERENCE", "unknown")
        self.system["geometry"]["motion_states"] = {
            state: {"provenance": {"status": "DOCUMENTEE"}} for state in states
        }
        length = self.observed["route_metrics"]["L1"]["length_mm"]
        self.observed["motion"] = {"L1": {state: {"clearance_ok": True, "reserve_mm": 5,
                                                   "min_radius_mm": 9, "radius_certified": True,
                                                   "solid_valid": True, "continuity_ok": True,
                                                   "tangency_ok": True, "endpoints_ok": True,
                                                   "diameter_ok": True, "length_mm": length}
                                           for state in states}}
        self.assertEqual(self.report()["domains"]["V4"], {"pass": 15, "fail": 0, "unknown": 0})
        self.observed["motion"]["L1"]["max"].update(clearance_ok=False, reserve_mm=3, min_radius_mm=7,
                                                     endpoints_ok=False, length_mm=length + 1)
        for code in ("V4.CLEARANCE", "V4.RESERVE", "V4.RADIUS", "V4.STATE_GEOMETRY", "V4.LENGTH"):
            self.assert_finding(code, "fail")

    def test_dynamic_requirement_without_states_is_unverified(self):
        self.rules["links"]["L1"]["min_dynamic_radius_mm"] = 10
        self.assert_finding("V4.STATE_COVERAGE", "unknown")
        self.assertEqual(self.report()["status"], "CANDIDAT_CONDITIONNEL")

    def test_applicable_support_and_motion_without_thresholds_are_unverified(self):
        self.system["links"][0]["mobile"] = True
        self.rules["links"]["L1"]["requires_support"] = True
        self.assert_finding("V4.STATE_COVERAGE", "unknown")
        self.assert_finding("V3.UNSUPPORTED_SPAN", "unknown")
        self.assertEqual(self.report()["status"], "CANDIDAT_CONDITIONNEL")

    def test_bad_native_state_does_not_validate_cached_solid(self):
        for field, value, code in (("recompute_ok", False, "V2.RECOMPUTE"),
                                   ("reopened", False, "V2.REOPENED"),
                                   ("invalid_objects", ["Cable"], "V2.INVALID_OBJECTS"),
                                   ("broken_links", ["Support.Link"], "V2.BROKEN_LINKS")):
            with self.subTest(field=field):
                previous = self.observed[field]
                self.observed[field] = value
                self.assert_finding(code, "fail")
                self.assert_finding("V2.ROUTE", "unknown")
                self.observed[field] = previous

    def test_path_endpoint_or_tangent_mismatch(self):
        route = self.observed["route_metrics"]["L1"]
        for field in ("endpoints_ok", "tangency_ok", "continuity_ok", "solid_valid"):
            with self.subTest(field=field):
                route[field] = False
                self.assert_finding("V2.ROUTE", "fail")
                route[field] = True


if __name__ == "__main__":
    unittest.main()
