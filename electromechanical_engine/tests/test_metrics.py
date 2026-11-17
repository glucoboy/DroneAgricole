import math
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from electromechanical_engine.metrics import measure, render_views


class NativeMetricsTest(unittest.TestCase):
    def setUp(self):
        self.system = {"links": [{"id": "L", "family": "signal"}]}
        self.rules = {"plateaux_mm": [0, 10], "extraction_ports": ["P"]}
        self.candidate = {"supports": [{"id": "clip"}]}
        self.arc = {
            "kind": "arc", "length_mm": math.pi / 2, "volume_mm3": math.pi,
            "start_mm": [1, 0, 12], "end_mm": [0, 1, 12],
            "bounds_mm": [[0, 0, 12], [1, 1, 12]],
            "samples_mm": [[1, 0, 12], [2**-0.5, 2**-0.5, 12], [0, 1, 12]],
        }
        self.observed = {
            "reopened": True, "recompute_ok": True, "invalid_objects": [], "broken_links": [],
            "route_metrics": {"L": {"length_mm": self.arc["length_mm"], "segments": [self.arc]}},
            "extraction_clear": {"P": True},
            "extraction_evidence": {"P": {"bounds_mm": [[0, 0, 0], [2, 3, 4]],
                                          "measurements": [{"clearance_mm": 3}, {"clearance_mm": 2}],
                                          "unavailable_ids": []}},
            "anchor_valid": {"clip": {"attached": True}},
            "view_objects": [{"id": "clip", "role": "support", "volume_mm3": 4,
                              "bounds_mm": [[0, 0, 0], [1, 2, 2]]}],
        }

    def report(self):
        return measure(self.system, self.rules, self.observed, self.candidate)

    def test_flat_arc_uses_native_extent_and_keeps_its_samples_in_zone_view(self):
        report = self.report()
        above = report["by_zone"]["AU_DESSUS"]
        self.assertAlmostEqual(above["axis_length_mm"], self.arc["length_mm"])
        self.assertAlmostEqual(above["nominal_volume_mm3"], self.arc["volume_mm3"])
        self.assertEqual(report["values"]["height_p95_mm"], 12)
        with TemporaryDirectory() as directory:
            views = render_views(self.observed, directory, self.rules)
            svg = (Path(directory) / views["files"]["au_dessus"]).read_text(encoding="utf-8")
            self.assertEqual(svg.split('<polyline points="')[1].split('"')[0].count(" "), 2)

    def test_curve_crossing_a_plateau_has_unknown_zone_totals(self):
        self.arc["bounds_mm"][0][2] = 9
        self.assertIsNone(self.report()["values"]["length_au_dessus_mm"])
        self.arc["bounds_mm"][0][2] = 11
        report = self.report()
        self.assertEqual(report["values"]["length_au_dessus_mm"], self.arc["length_mm"])
        self.assertIsNone(report["values"]["height_p95_mm"])

    def test_volumes_and_clearances_require_observations_for_all_applicable_items(self):
        report = self.report()
        self.assertEqual(report["values"]["attached_support_volume_mm3"], 4)
        self.assertEqual(report["values"]["extraction_envelope_volume_mm3"], 24)
        self.assertEqual(report["values"]["min_extraction_clearance_mm"], 2)
        self.observed["extraction_evidence"]["P"]["unavailable_ids"] = ["unknown"]
        self.assertIsNone(self.report()["values"]["min_extraction_clearance_mm"])
        self.observed["view_objects"].clear()
        self.assertIsNone(self.report()["values"]["attached_support_volume_mm3"])


if __name__ == "__main__":
    unittest.main()
