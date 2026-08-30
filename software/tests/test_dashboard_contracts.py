from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from software.visualization.contracts import (
    ContractError,
    DefinitionRegistry,
    load_schema_documents,
    validate_dataset_definition,
    validate_run_request,
)
from software.visualization.result_adapters import detect_result_kind, normalize_result_directory


WORKSPACE = Path(__file__).resolve().parents[2]
CONFIG_ROOT = WORKSPACE / "configs" / "visualization"


class ContractRegistryTests(unittest.TestCase):
    def test_published_schemas_are_json_schema_2020_12(self) -> None:
        documents = load_schema_documents(CONFIG_ROOT / "schemas")
        self.assertEqual(8, len(documents))

    def test_current_registry_exposes_all_lio_variants_and_sequences(self) -> None:
        registry = DefinitionRegistry.load(CONFIG_ROOT / "datasets", CONFIG_ROOT / "simulations")
        self.assertEqual({"botanicgarden"}, set(registry.datasets))
        self.assertEqual({"lio_benchmark", "px4_offboard"}, set(registry.simulations))
        for variant_id in ("fast_lio2", "point_lio", "lio_sam"):
            compatible = registry.compatible_dataset_sequences("lio_benchmark", variant_id)
            self.assertEqual(3, len(compatible))
            self.assertTrue(all(item["dataset_id"] == "botanicgarden" for item in compatible))

    def test_a_new_compatible_dataset_is_added_without_code_change(self) -> None:
        source_dataset = json.loads((CONFIG_ROOT / "datasets" / "botanicgarden.json").read_text(encoding="utf-8"))
        source_simulation = json.loads((CONFIG_ROOT / "simulations" / "lio_benchmark.json").read_text(encoding="utf-8"))
        second_dataset = copy.deepcopy(source_dataset)
        second_dataset["dataset_id"] = "future_dataset"
        second_dataset["label"] = "Dataset futur"
        second_dataset["sequences"] = [second_dataset["sequences"][0]]
        second_dataset["sequences"][0]["sequence_id"] = "future_smoke"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            dataset_directory = root / "datasets"
            simulation_directory = root / "simulations"
            dataset_directory.mkdir()
            simulation_directory.mkdir()
            (dataset_directory / "botanicgarden.json").write_text(json.dumps(source_dataset), encoding="utf-8")
            (dataset_directory / "future_dataset.json").write_text(json.dumps(second_dataset), encoding="utf-8")
            (simulation_directory / "lio_benchmark.json").write_text(json.dumps(source_simulation), encoding="utf-8")
            registry = DefinitionRegistry.load(dataset_directory, simulation_directory)
            compatible = registry.compatible_dataset_sequences("lio_benchmark", "fast_lio2")
        self.assertEqual({"botanicgarden", "future_dataset"}, {item["dataset_id"] for item in compatible})
        self.assertEqual(4, len(compatible))

    def test_incompatible_sequence_is_filtered_by_capability(self) -> None:
        dataset = json.loads((CONFIG_ROOT / "datasets" / "botanicgarden.json").read_text(encoding="utf-8"))
        simulation = json.loads((CONFIG_ROOT / "simulations" / "lio_benchmark.json").read_text(encoding="utf-8"))
        dataset["capabilities"] = []
        dataset["sequences"][0]["capabilities"] = ["lidar.pointcloud2", "imu.si"]
        dataset["sequences"] = [dataset["sequences"][0]]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "datasets").mkdir()
            (root / "simulations").mkdir()
            (root / "datasets" / "dataset.json").write_text(json.dumps(dataset), encoding="utf-8")
            (root / "simulations" / "simulation.json").write_text(json.dumps(simulation), encoding="utf-8")
            registry = DefinitionRegistry.load(root / "datasets", root / "simulations")
            compatible = registry.compatible_dataset_sequences("lio_benchmark", "fast_lio2")
        self.assertEqual([], compatible)

    def test_dataset_resource_cannot_escape_workspace(self) -> None:
        dataset = json.loads((CONFIG_ROOT / "datasets" / "botanicgarden.json").read_text(encoding="utf-8"))
        dataset["sequences"][0]["resources"][0]["uri"] = "../outside"
        with self.assertRaisesRegex(ContractError, "chemin relatif"):
            validate_dataset_definition(dataset)

    def test_run_request_contract(self) -> None:
        validate_run_request(
            {
                "schema": "drone_agricole.run_request.v1",
                "request_id": "request_001",
                "simulation_id": "lio_benchmark",
                "variant_id": "fast_lio2",
                "requested_at_utc": "2026-08-29T10:00:00+00:00",
                "inputs": [
                    {
                        "input_id": "dataset",
                        "kind": "dataset_sequence",
                        "reference": {"dataset_id": "botanicgarden", "sequence_id": "1006-03-smoke"},
                    }
                ],
                "parameters": {"playback_rate": 1.0},
            }
        )


class LegacyAdapterTests(unittest.TestCase):
    def test_lio_v3_result_is_normalized_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            self._write_json(
                directory / "run_manifest.json",
                {
                    "schema_version": 3,
                    "algorithm": "fast_lio2",
                    "scheduled_data_seconds_per_wall_second": 0.99,
                    "mapping_process": {"cpu_average_equivalent_cores": 0.4, "peak_rss_mib": 300.0},
                },
            )
            self._write_json(
                directory / "metrics.json",
                {
                    "schema_version": 3,
                    "finite_values": True,
                    "estimate_poses": 99,
                    "ate_translation_m": {"rmse": 0.3},
                    "ate_orientation_deg": {"rmse": 1.5},
                    "rpe": {"translation_m": {"rmse": 0.05}, "rotation_deg": {"rmse": 0.6}},
                    "pipeline_counters": {"scans_received": 100, "odometry_published": 99},
                    "pipeline_accounting": {"ratios_percent": {"odometry_over_received": 99.0}},
                },
            )
            self._write_json(
                directory / "dashboard_request.json",
                {
                    "schema_version": 1,
                    "run_id": "abc123",
                    "state": "completed",
                    "dataset_id": "botanicgarden",
                    "sequence_id": "1006-03-smoke",
                    "algorithm_id": "fast_lio2",
                    "parameters": {"playback_rate": 1.0},
                    "started_at": "2026-08-29T10:00:00+00:00",
                    "finished_at": "2026-08-29T10:00:05+00:00",
                },
            )
            before = sorted(path.name for path in directory.iterdir())
            result = normalize_result_directory(directory)
            after = sorted(path.name for path in directory.iterdir())
        self.assertEqual("lio_benchmark_legacy", result.source_kind)
        self.assertEqual("fast_lio2", result.manifest["variant_id"])
        self.assertEqual("lio_trajectory_v1", result.manifest["compatibility"]["comparison_group"])
        self.assertGreaterEqual(len(result.metrics["summary"]), 8)
        self.assertEqual(before, after)

    def test_px4_result_and_events_are_normalized(self) -> None:
        with tempfile.TemporaryDirectory(prefix="square_20260829T100000Z_") as temporary:
            directory = Path(temporary)
            self._write_json(
                directory / "result.json",
                {
                    "schema": "drone_agricole.px4_offboard_test.v1",
                    "created_utc": "2026-08-29T10:00:00+00:00",
                    "success": True,
                    "reason": "square_completed",
                    "mode": "square",
                    "parameters": {"takeoff_altitude_m": 2.0},
                    "observations": {"offboard_entered": True, "max_altitude_m": 2.0, "landed": True, "failsafe": False},
                    "events": [
                        {"event": "test_started", "elapsed_s": 0.0, "state": "warmup"},
                        {"event": "test_finished", "elapsed_s": 20.0, "state": "landing", "success": True},
                    ],
                    "command_acks": [],
                },
            )
            self.assertEqual("px4_offboard_v1", detect_result_kind(directory))
            result = normalize_result_directory(directory)
        self.assertEqual("px4_offboard", result.manifest["simulation_id"])
        self.assertEqual("completed", result.manifest["state"])
        self.assertEqual(2, len(result.events))
        self.assertTrue(any(metric["metric_id"] == "duration_s" for metric in result.metrics["summary"]))

    @staticmethod
    def _write_json(path: Path, value: object) -> None:
        path.write_text(json.dumps(value), encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
