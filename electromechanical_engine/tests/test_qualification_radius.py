"""Threshold tests using native circular bends measured after reopening."""

from math import ulp
import os
from pathlib import Path
import tempfile
import unittest

from electromechanical_engine.freecad import FreeCADAdapter
from electromechanical_engine.tests.test_freecad import scenario
from electromechanical_engine.validation import _bend_radius_finding, validate


class QualificationRadiusArithmeticTest(unittest.TestCase):
    def test_f16_observed_roundoff_is_not_a_deficit_at_the_diagnostic_threshold(self):
        # Value remeasured from the saved initial F16; 22 mm is a test threshold.
        observation = {"min_radius_mm": 21.999999999999954, "radius_certified": True,
                       "radius_evidence": "analytic_lines_circles"}
        self.assertEqual((22 - observation["min_radius_mm"]) / ulp(22), 13)
        finding = _bend_radius_finding("V2.RADIUS", observation, 22, "F16", "static_bend_radius")
        self.assertEqual(finding["status"], "pass")
        self.assertEqual(finding["evidence"]["roundoff_tolerance_mm"], 16 * ulp(22))

        observation.update(min_radius_mm=22.000001, radius_certified=False,
                           radius_evidence="sampled_upper_bound_on_true_minimum_radius")
        sampled = _bend_radius_finding("V2.RADIUS", observation, 22, "F16", "static_bend_radius")
        self.assertEqual(sampled["status"], "unknown")
        self.assertEqual(sampled["evidence"]["roundoff_tolerance_mm"], 0)


@unittest.skipUnless(os.environ.get("ELECTROMECHANICAL_FREECAD_PYTHON"), "FreeCAD integration not requested")
class NativeQualificationRadiusTest(unittest.TestCase):
    def test_roundoff_at_the_exact_radius_does_not_mask_a_real_deficit(self):
        adapter = FreeCADAdapter(os.environ["ELECTROMECHANICAL_FREECAD_PYTHON"])
        points = [[0, 0, 10], [20, 0, 10], [20, 20, 10], [80, 20, 10], [80, 0, 10], [100, 0, 10]]
        with tempfile.TemporaryDirectory() as directory:
            for label, commanded, expected in (("exact", 7.2, "pass"),
                                                ("undersized", 7.199999, "fail")):
                with self.subTest(label=label):
                    plan = scenario(points, commanded)
                    plan["requirements"]["links"]["L0"]["min_radius_mm"] = 7.2
                    plan["requirements"]["collision_tolerance_mm3"] = 1e-7
                    plan["candidate"]["connections"] = [{"id": "L0", "source": "P0", "target": "P1"}]
                    observed = adapter.build(plan, Path(directory) / label)
                    self.assertTrue(observed["reopened"])
                    self.assertTrue(observed["route_metrics"]["L0"]["radius_certified"])
                    report = validate(plan["system"], plan["requirements"], plan["candidate"], observed)
                    radius = next(row for row in report["findings"] if row["code"] == "V2.RADIUS")
                    self.assertEqual(radius["status"], expected, radius)
