import copy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from xml.etree import ElementTree

from electromechanical_engine.__main__ import run_campaign
from electromechanical_engine.contracts import freeze, load
from electromechanical_engine.metrics import measure, render_views, view_frame
from electromechanical_engine.search import check_corridors, compare_reports, explore, run_feedback


REFERENCE = "a" * 64


def corridor(identity, y, width=10, carrier="Plate"):
    return {"id": identity, "carrier": carrier, "width_mm": width, "zone": "SOUS", "max_carrier_distance_mm": 5,
            "points_mm": [[0, y, 0], [10, y, 0]]}


def alternative(identity, route, **fields):
    return {"id": identity, "family": "MATERIEL_CONSTANT", "routes": {"L1": {"corridor": route}}, **fields}


def observation(routes):
    return {"reopened": True, "recompute_ok": True, "invalid_objects": [], "broken_links": [],
            "route_metrics": routes}


def result(status="VALIDE_GEOMETRIQUEMENT", findings=None, length=10, volume=20):
    native = [{"code": code, "status": "pass"} for code in
              ("V2.REOPENED", "V2.RECOMPUTE", "V2.INVALID_OBJECTS",
               "V2.BROKEN_LINKS", "V2.PAIR_COVERAGE")]
    return {"status": status, "findings": native + (findings or []), "reference_sha256": REFERENCE,
            "metrics": {"version": 1, "scope": {"link_ids": ["L1"]},
                        "values": {"total_length_mm": length, "total_cable_volume_mm3": volume}}}


class SearchTest(unittest.TestCase):
    def setUp(self):
        self.system = {"frame": "WORLD", "links": [{"id": "L1", "source": "A", "target": "B", "family": "data"}],
                       "corridors": [corridor("Lower", 0), corridor("Upper", 1), corridor("Side", 2),
                                     corridor("Floating", 3, carrier=None), corridor("Narrow", 4, width=1),
                                     corridor("UnknownWidth", 5, width=None), corridor("Copy", 0.0)]}
        self.requirements = {"links": {"L1": {"diameter_mm": 2}}, "plateaux_mm": [-1, 1]}

    def plan(self, alternatives, **budget):
        return explore(self.system, {"version": 1, "alternatives": alternatives, **budget},
                       REFERENCE, self.requirements)

    def test_rejects_floating_and_narrow_corridors_and_deduplicates_physical_geometry(self):
        plan = self.plan([alternative("good", "Lower"), alternative("floating", "Floating"),
                          alternative("narrow", "Narrow"), alternative("unknown", "UnknownWidth"),
                          alternative("same", "Copy")])
        self.assertEqual([row["id"] for row in plan["candidates"]], ["good", "unknown"])
        self.assertEqual([row["defects"][0]["code"] for row in plan["rejected"]],
                         ["CORRIDOR_UNANCHORED", "CORRIDOR_CAPACITY_EXCEEDED", "EQUIVALENT_DESIGN"])
        self.assertEqual(plan["reservations"]["good"], [])
        self.assertEqual(plan["reservations"]["unknown"][0]["code"], "CORRIDOR_CAPACITY_UNKNOWN")
        self.assertEqual(plan["candidates"][0]["routes"]["L1"]["bend_radius_mm"], 0)
        self.assertEqual(plan["candidates"][0]["connections"], [{"id": "L1", "source": "A", "target": "B"}])

    def test_preserves_hardware_variant_families_and_marks_unproven_changes(self):
        plan = self.plan([alternative("constant", "Lower"),
                          alternative("angle", "Upper", family="IMPLANTATION_CONNECTIQUE",
                                      changes={"connectors": ["candidate-angle"]}),
                          alternative("board", "Lower", family="REVISION_ELECTRONIQUE",
                                      changes={"electronics": ["candidate-board"]})])
        self.assertEqual(len({row["family"] for row in plan["candidates"]}), 3)
        self.assertEqual(plan["reservations"]["angle"][0]["code"], "ARCHITECTURE_CHANGES_REQUIRE_EVIDENCE")
        self.assertEqual(plan["reservations"]["board"][1]["code"], "UNREALIZED_ARCHITECTURE_SHARES_GEOMETRY")
        run = run_feedback(plan, lambda _: result(), ["total_length_mm"])
        self.assertEqual(run["pareto"], ["constant"])

    def test_rejects_alternative_names_ambiguous_or_reserved_on_disk(self):
        for identity in ("initial.", "INITIAL", "exploration", "attempts", "NUL.json"):
            with self.subTest(identity=identity), self.assertRaises(ValueError):
                self.plan([alternative("initial", "Upper"), alternative(identity, "Lower")])

    def test_nominal_connections_make_interface_and_cavities_explicit(self):
        self.system["ports"] = [{"id": "A", "interface": "UART"}, {"id": "B", "interface": "UART"}]
        self.system["links"][0]["source_cavities"] = ["A1"]
        plan = self.plan([alternative("initial", "Upper")])
        self.assertEqual(plan["candidates"][0]["connections"], [
            {"id": "L1", "source": "A", "target": "B",
             "source_interface": "UART", "target_interface": "UART", "source_cavities": ["A1"]},
        ])

    def test_failed_native_collision_triggers_correction_before_other_design(self):
        plan = self.plan([alternative("initial", "Upper"), alternative("side", "Side"),
                          alternative("corrected", "Lower", corrects={"candidate_id": "initial", "codes": ["V2.PAIR"]})],
                         max_candidates=2)

        def evaluate(candidate):
            if candidate["id"] == "initial":
                return result("NON_CONFORME", [{"status": "fail", "code": "V2.PAIR", "object": ["L1", "Obstacle"]}])
            return result(findings=[{"status": "pass", "code": "V2.PAIR", "object": ["Obstacle", "L1"]}])

        run = run_feedback(plan, evaluate, ["total_length_mm"])
        self.assertEqual([row["candidate_id"] for row in run["attempts"]], ["initial", "corrected"])
        self.assertEqual(run["attempts"][1]["resolved_trigger_codes"], ["V2.PAIR"])
        self.assertEqual(run["attempts"][1]["resolved_trigger_findings"][0]["after"]["object"], ["Obstacle", "L1"])
        self.assertEqual(run["pareto"], ["corrected"])
        self.assertEqual(run["stop_reason"], "BUDGET")

    def test_other_pair_motion_state_or_criterion_cannot_close_a_finding(self):
        plan = self.plan([alternative("initial", "Upper"),
                          alternative("corrected", "Lower", corrects={"candidate_id": "initial",
                                                                     "codes": ["V2.PAIR", "V4.CLEARANCE", "V5.CORRIDOR"]})])
        findings = [{"code": "V2.PAIR", "status": "fail", "object": ["L1", "Obstacle"]},
                    {"code": "V4.CLEARANCE", "status": "fail", "object": "L1", "evidence": {"state": "full"}},
                    {"code": "V5.CORRIDOR", "status": "unknown", "object": "L1", "reason": "CORRIDOR_CAPACITY_UNKNOWN"}]
        unrelated = [{"code": "V2.PAIR", "status": "pass", "object": ["L1", "Deck"]},
                     {"code": "V4.CLEARANCE", "status": "pass", "object": "L1", "evidence": {"state": "half"}},
                     {"code": "V5.CORRIDOR", "status": "pass", "object": "L1", "evidence": {"criterion": "carrier_distance"}}]
        rows = iter([result("NON_CONFORME", findings), result(findings=unrelated)])
        run = run_feedback(plan, lambda _: next(rows), ["total_length_mm"])
        self.assertEqual(run["attempts"][1]["resolved_trigger_codes"], [])
        self.assertEqual(run["attempts"][1]["resolved_trigger_findings"], [])

    def test_passed_finding_does_not_trigger_and_dominated_repeat_stops(self):
        plan = self.plan([alternative("initial", "Upper"), alternative("repeat", "Side"),
                          alternative("untried", "UnknownWidth"),
                          alternative("corrected", "Lower", corrects={"candidate_id": "initial", "codes": ["V2.PAIR"]})],
                         max_stalled_attempts=1)
        run = run_feedback(plan, lambda _: result(findings=[{"status": "pass", "code": "V2.PAIR"}]),
                           ["total_length_mm"])
        self.assertEqual(run["stop_reason"], "NO_PROGRESS")
        self.assertEqual(run["skipped"], [{"candidate_id": "corrected", "reason": "TRIGGER_NOT_OBSERVED"},
                                          {"candidate_id": "untried", "reason": "NO_PROGRESS"}])

    def test_prefilter_failure_triggers_a_bounded_correction(self):
        plan = self.plan([alternative("narrow", "Narrow"),
                          alternative("lower", "Lower", corrects={"candidate_id": "narrow", "codes": ["CORRIDOR_CAPACITY_EXCEEDED"]})])
        run = run_feedback(plan, lambda _: result(), ["total_length_mm"])
        self.assertEqual(run["pareto"], ["lower"])
        self.assertEqual(run["attempts"][0]["triggered_by"]["candidate_id"], "narrow")

    def test_direct_validation_checks_carrier_and_capacity_even_without_explore(self):
        candidate = alternative("direct", "Lower")
        self.assertEqual(check_corridors(self.system, self.requirements, candidate, {})[0]["reason"],
                         "CORRIDOR_CARRIER_PROXIMITY_UNVERIFIED")
        plate = {"id": "Plate", "role": "structure", "representation": "reference_box",
                 "bounds_mm": [[-1, -2, -2], [11, 2, -1]]}
        route = {"solid_valid": True, "bounds_mm": [[0, -1, 0], [10, 1, 2]]}
        native = {"view_objects": [plate], "route_metrics": {"L1": route}}
        finding = check_corridors(self.system, self.requirements, candidate, native)[0]
        self.assertEqual(finding["status"], "pass")
        self.assertEqual(finding["evidence"]["upper_bound_mm"], 3)
        route["bounds_mm"][1][2] = 9
        finding = check_corridors(self.system, self.requirements, candidate, native)[0]
        self.assertEqual(finding["status"], "unknown")
        route["bounds_mm"][0][2] = 6
        finding = check_corridors(self.system, self.requirements, candidate, native)[0]
        self.assertEqual(finding["reason"], "CORRIDOR_CARRIER_TOO_FAR")
        self.assertEqual(finding["evidence"]["lower_bound_mm"], 7)
        candidate["routes"]["L1"]["corridor"] = "Narrow"
        self.assertEqual(check_corridors(self.system, self.requirements, candidate, native)[0]["status"], "fail")

    def test_comparison_rejects_different_reference_or_missing_objective(self):
        old = result()
        new = result(volume=None)
        self.assertTrue(compare_reports(old, new, ["total_cable_volume_mm3"])["comparable"])
        self.assertIsNone(compare_reports(old, new, ["total_cable_volume_mm3"])["dominance"])
        new["reference_sha256"] = "b" * 64
        self.assertFalse(compare_reports(old, new, ["total_length_mm"])["comparable"])

    def test_comparison_rejects_admissibility_when_findings_contradict_the_verdict(self):
        contradictory = result(findings=[{"status": "unknown", "code": "V5.CORRIDOR"}])
        comparison = compare_reports(result(), contradictory, ["total_length_mm"])
        self.assertTrue(comparison["comparable"])
        self.assertFalse(comparison["admissible"])

    def test_comparison_requires_native_findings_even_with_a_favorable_verdict(self):
        baseline = result()
        self.assertTrue(compare_reports(baseline, baseline, ["total_length_mm"])["admissible"])
        candidate = copy.deepcopy(baseline)
        candidate["findings"].pop()
        comparison = compare_reports(baseline, candidate, ["total_length_mm"])
        self.assertTrue(comparison["comparable"])
        self.assertFalse(comparison["admissible"])
        self.assertIsNone(comparison["dominance"])

    def test_pareto_keeps_tradeoff_and_rejects_dominated(self):
        plan = self.plan([alternative("short", "Lower"), alternative("small", "Upper"),
                          alternative("dominated", "Side")])
        results = {"short": result(length=10, volume=20), "small": result(length=12, volume=15),
                   "dominated": result(length=13, volume=20)}
        run = run_feedback(plan, lambda row: results[row["id"]],
                           ["total_length_mm", "total_cable_volume_mm3"])
        self.assertEqual(run["pareto"], ["short", "small"])

    def test_campaign_persists_completed_attempts_before_interruption(self):
        fixture = Path(__file__).parent / "fixtures" / "banc"
        with TemporaryDirectory() as folder:
            reference, output = Path(folder) / "reference", Path(folder) / "output"
            lock = freeze(fixture, reference)
            report = result("NON_CONFORME")
            report["reference_sha256"] = lock["reference_sha256"]
            with patch("electromechanical_engine.__main__.build_one",
                       side_effect=[(report, {}), KeyboardInterrupt]):
                with self.assertRaises(KeyboardInterrupt):
                    run_campaign(None, reference, fixture / "design_space.json", output)
            self.assertFalse((output / "campaign_report.json").exists())
            self.assertEqual(load(output / "campaign_context.json")["reference_sha256"], lock["reference_sha256"])
            self.assertEqual(load(output / "attempts/001.json")["candidate_id"], "direct")
            self.assertFalse((output / "attempts/002.json").exists())


class MetricsTest(unittest.TestCase):
    def setUp(self):
        self.system = {"frame": "WORLD", "links": [{"id": "L1", "family": "power"}, {"id": "L2", "family": "data"}]}
        self.requirements = {"plateaux_mm": [0, 10], "extraction_ports": ["A", "B"]}

    def test_zone_totals_height_quantile_and_missing_evidence(self):
        segment = {"start_mm": [0, 0, -10], "end_mm": [0, 0, 20], "length_mm": 30,
                   "kind": "line", "volume_mm3": 60}
        route = {"length_mm": 30, "volume_mm3": 60, "z_max_mm": 21, "segments": [segment]}
        observed = observation({"L1": route, "L2": route})
        observed["extraction_clear"] = {"A": False}
        measured = measure(self.system, self.requirements, observed, {})
        self.assertAlmostEqual(measured["values"]["height_p95_mm"], 18.5)
        self.assertEqual(measured["values"]["max_cable_z_mm"], 21)
        self.assertEqual(measured["values"]["level_changes"], 4)
        self.assertAlmostEqual(measured["values"]["length_au_dessus_mm"], 20)
        self.assertAlmostEqual(measured["values"]["volume_entre_nominal_mm3"], 40)
        self.assertIsNone(measured["values"]["blocked_extraction_count"])
        self.assertIsNone(measured["values"]["unsupported_length_mm"])
        observed["recompute_ok"] = False
        self.assertIsNone(measure(self.system, self.requirements, observed, {})["values"]["total_length_mm"])

    def test_comparison_exposes_displaced_equipment_tradeoff_per_link(self):
        old = result()
        old["metrics"] = measure(self.system, self.requirements,
                                 observation({"L1": {"length_mm": 8}, "L2": {"length_mm": 5}}), {})
        new = result()
        new["metrics"] = measure(self.system, self.requirements,
                                 observation({"L1": {"length_mm": 4}, "L2": {"length_mm": 7}}), {})
        comparison = compare_reports(old, new, ["total_length_mm"])
        self.assertEqual(comparison["deltas"], {"total_length_mm": -2})
        self.assertEqual(comparison["link_length_deltas_mm"], {"L1": -4, "L2": 2})

    def test_visuals_share_frame_and_report_missing_supports(self):
        left = observation({"L1": {"axis_samples_mm": [[0, 0, 1], [10, 0, 1]]}})
        right = copy.deepcopy(left)
        right["route_metrics"]["L1"]["axis_samples_mm"][-1][0] = 100
        frame = view_frame([left, right])
        with TemporaryDirectory() as base:
            l_dir, r_dir = Path(base) / "left", Path(base) / "right"
            one = render_views(left, l_dir, self.requirements, frame)
            two = render_views(right, r_dir, self.requirements, frame)
            self.assertEqual(one["scale_px_per_mm"], two["scale_px_per_mm"])
            self.assertIn("supports", one["missing_views"])
            self.assertIn("dessus", one["files"])
            self.assertEqual(ElementTree.parse(l_dir / one["files"]["dessus"]).getroot().tag,
                             "{http://www.w3.org/2000/svg}svg")


if __name__ == "__main__":
    unittest.main()
