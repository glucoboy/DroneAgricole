from __future__ import annotations

import json
from pathlib import Path
import shutil
import tempfile
import unittest

from software.tests.test_result_history import create_native_lio, write_json
from software.visualization.result_comparison import ComparisonError, ComparisonService
from software.visualization.result_history import ResultRepository


def clone_result(source: Path, workspace: Path, algorithm: str, run_id: str, ate: float) -> Path:
    destination = workspace / f"results/benchmarks/{algorithm}/botanicgarden_1006-03/{run_id}"
    shutil.copytree(source, destination)
    for path in destination.glob("*.json*"):
        content = path.read_text(encoding="utf-8")
        content = content.replace("run_native", run_id).replace("request_native", f"request_{run_id}")
        content = content.replace("fast_lio2", algorithm)
        path.write_text(content, encoding="utf-8")
    metrics_path = destination / "t0_metrics.json"
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    metrics["summary"][0]["value"] = ate
    next(metric for metric in metrics["summary"] if metric["metric_id"] == "cpu_average_cores")["value"] = {
        "point_lio": 0.4,
        "lio_sam": 1.6,
    }.get(algorithm, 0.5)
    write_json(metrics_path, metrics)
    return destination


class ResultComparisonTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temporary.name)
        source = create_native_lio(self.workspace)
        base_metrics = json.loads((source / "t0_metrics.json").read_text(encoding="utf-8"))
        base_metrics["summary"].append({
            "metric_id": "cpu_average_cores",
            "label": "CPU moyen",
            "value": 0.5,
            "unit": "coeur",
            "direction": "lower",
            "status": "unknown",
        })
        write_json(source / "t0_metrics.json", base_metrics)
        clone_result(source, self.workspace, "point_lio", "run_point", 0.18)
        clone_result(source, self.workspace, "lio_sam", "run_sam", 0.14)
        self.repository = ResultRepository(self.workspace)
        items = self.repository.search({"domain": "localization"}, refresh=True)["items"]
        self.ids = [next(item["result_id"] for item in items if item["variant_id"] == algorithm) for algorithm in ("fast_lio2", "point_lio", "lio_sam")]
        self.service = ComparisonService(self.repository)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_compares_three_compatible_lio_results(self) -> None:
        comparison = self.service.preview(self.ids)
        self.assertTrue(comparison["compatibility"]["compatible"])
        self.assertEqual(comparison["compatibility"]["dataset_id"], "botanicgarden")
        self.assertEqual(len(comparison["runs"]), 3)
        ate = next(metric for metric in comparison["metrics"] if metric["metric_id"] == "ate_translation_rmse_m")
        self.assertEqual(ate["best_result_ids"], [self.ids[0]])
        self.assertTrue(next(value for value in comparison["parameters"] if value["parameter_id"] == "playback_rate")["same_for_all"])

    def test_refuses_mismatched_sequence(self) -> None:
        item = next(value for value in self.repository.search()["items"] if value["result_id"] == self.ids[-1])
        manifest_path = self.workspace / "results" / item["relative_directory"] / "t0_run_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["inputs"][0]["reference"]["sequence_id"] = "another-sequence"
        write_json(manifest_path, manifest)
        self.repository.search(refresh=True)
        comparison = self.service.preview(self.ids)
        self.assertFalse(comparison["compatibility"]["compatible"])
        self.assertIn("Séquence diffère", " ".join(comparison["compatibility"]["reasons"]))

    def test_validates_selection_cardinality_and_uniqueness(self) -> None:
        with self.assertRaises(ComparisonError):
            self.service.preview(self.ids[:1])
        with self.assertRaises(ComparisonError):
            self.service.preview([self.ids[0], self.ids[0]])
        with self.assertRaises(ComparisonError):
            self.service.preview([*self.ids, "four", "five"])

    def test_exports_self_contained_markdown_report(self) -> None:
        report = self.service.report(self.ids)
        self.assertIn("# Rapport de comparaison T0.4", report)
        self.assertIn("Compatibilité : **validée**", report)
        self.assertIn("ATE translation RMSE", report)
        self.assertIn("fast_lio2 · run_native", report)
        self.assertIn("★", report)

    def test_builds_multitrajectory_replay(self) -> None:
        previews = self.service.preview(self.ids)
        details = {run["result_id"]: self.repository.detail(run["result_id"]) for run in previews["runs"]}

        class FakeRepository:
            def detail(self, result_id: str) -> dict:
                value = json.loads(json.dumps(details[result_id]))
                value["summary"]["replay_available"] = True
                return value

            def replay(self, result_id: str) -> dict:
                return {
                    "scene": {"estimate": [[0, 0, 0], [1, 0, 0]], "truth": [[0, 0, 0], [1, 0, 0]], "px4_path": []},
                    "curves": [{"curve_id": "ate_cumulative_rmse_m", "unit": "m", "values": [[0, 0], [1, 0.1]]}],
                }

        replay = ComparisonService(FakeRepository()).replay(self.ids)
        self.assertEqual(len(replay["scene"]["comparison_paths"]), 3)
        self.assertEqual(len(replay["curves"]), 3)
        self.assertEqual(replay["scene"]["truth"][-1], [1, 0, 0])


if __name__ == "__main__":
    unittest.main()
