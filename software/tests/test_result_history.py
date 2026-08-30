from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from software.visualization.result_history import ResultHistoryError, ResultRepository


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def create_native_lio(workspace: Path) -> Path:
    directory = workspace / "results/benchmarks/fast_lio2/botanicgarden_1006-03/run_native"
    directory.mkdir(parents=True)
    manifest = {
        "schema": "drone_agricole.run_manifest.v1",
        "run_id": "run_native",
        "request_id": "request_native",
        "simulation_id": "lio_benchmark",
        "variant_id": "fast_lio2",
        "runner_id": "fast_lio2",
        "domain": "localization",
        "state": "completed",
        "created_at_utc": "2026-08-30T10:00:00+00:00",
        "started_at_utc": "2026-08-30T10:00:01+00:00",
        "finished_at_utc": "2026-08-30T10:01:00+00:00",
        "inputs": [{
            "input_id": "dataset",
            "kind": "dataset_sequence",
            "reference": {"dataset_id": "botanicgarden", "sequence_id": "1006-03_5s"},
        }],
        "parameters": {"playback_rate": 1.0, "filter_size_map": 0.5},
        "software": {},
        "files": {"metrics": "t0_metrics.json"},
        "compatibility": {"comparison_group": "lio_trajectory_v1", "result_contract_version": 1},
        "metadata": {},
    }
    metrics = {
        "schema": "drone_agricole.metrics.v1",
        "run_id": "run_native",
        "simulation_id": "lio_benchmark",
        "status": "complete",
        "summary": [{
            "metric_id": "ate_translation_rmse_m",
            "label": "ATE translation RMSE",
            "value": 0.12,
            "unit": "m",
            "direction": "lower",
            "status": "unknown",
        }],
        "groups": {},
    }
    artifacts = {"schema": "drone_agricole.artifacts.v1", "run_id": "run_native", "items": []}
    event = {
        "schema": "drone_agricole.event.v1",
        "run_id": "run_native",
        "sequence": 0,
        "timestamp_utc": "2026-08-30T10:00:01+00:00",
        "event_type": "run_started",
        "severity": "info",
        "message": "début",
        "data": {},
    }
    request = {
        "schema": "drone_agricole.run_request.v1",
        "request_id": "request_native",
        "simulation_id": "lio_benchmark",
        "variant_id": "fast_lio2",
        "requested_at_utc": "2026-08-30T10:00:00+00:00",
        "profile_id": "botanicgarden_velodyne_xsens",
        "inputs": manifest["inputs"],
        "parameters": manifest["parameters"],
        "tags": ["dashboard", "qualification"],
    }
    write_json(directory / "t0_run_manifest.json", manifest)
    write_json(directory / "t0_metrics.json", metrics)
    write_json(directory / "artifacts.json", artifacts)
    write_json(directory / "run_request.json", request)
    (directory / "events.jsonl").write_text(json.dumps(event) + "\n", encoding="utf-8")
    return directory


def create_legacy_px4(workspace: Path) -> Path:
    directory = workspace / "results/simulation/px4_lot_a/square_legacy"
    result = {
        "schema": "drone_agricole.px4_offboard_test.v1",
        "created_utc": "2026-08-29T09:00:00+00:00",
        "mode": "square",
        "success": True,
        "reason": "square_completed",
        "parameters": {"takeoff_altitude_m": 2.0},
        "observations": {"max_altitude_m": 2.01, "landed": True, "offboard_entered": True},
        "command_acks": [],
        "events": [
            {"elapsed_s": 0.1, "event": "state_changed", "state": "warmup", "origin_ned": [10.0, 20.0, -1.0]},
            {"elapsed_s": 2.0, "event": "state_changed", "state": "mission_stage", "target_ned": [10.0, 20.0, -3.0]},
            {"elapsed_s": 4.0, "event": "state_changed", "state": "mission_stage", "target_ned": [12.0, 20.0, -3.0]},
        ],
    }
    write_json(directory / "result.json", result)
    return directory


class ResultRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temporary.name)
        create_native_lio(self.workspace)
        create_legacy_px4(self.workspace)
        self.repository = ResultRepository(self.workspace)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_indexes_native_and_legacy_results(self) -> None:
        index = self.repository.search(refresh=True)
        self.assertEqual(index["total"], 2)
        self.assertEqual(index["invalid_result_count"], 0)
        self.assertEqual({item["source_kind"] for item in index["items"]}, {"t0_native", "px4_offboard_v1"})
        self.assertEqual(index["facets"]["domain"], [
            {"value": "flight_simulation", "count": 1},
            {"value": "localization", "count": 1},
        ])

    def test_filters_and_opens_complete_detail(self) -> None:
        index = self.repository.search({
            "domain": "localization",
            "dataset_id": "botanicgarden",
            "algorithm_id": "fast_lio2",
            "state": "completed",
            "tag": "qualif",
            "date_from": "2026-08-30",
            "date_to": "2026-08-30",
        }, refresh=True)
        self.assertEqual(index["total"], 1)
        detail = self.repository.detail(index["items"][0]["result_id"])
        self.assertEqual(detail["manifest"]["run_id"], "run_native")
        self.assertEqual(detail["metrics"]["summary"][0]["value"], 0.12)
        self.assertEqual(len(detail["events"]), 1)
        self.assertEqual(detail["duplicate_request"]["profile_id"], "botanicgarden_velodyne_xsens")
        self.assertEqual(detail["duplicate_request"]["inputs"][0]["reference"]["sequence_id"], "1006-03_5s")

    def test_reconstructs_px4_scene_without_running_px4(self) -> None:
        index = self.repository.search({"scenario_id": "square"}, refresh=True)
        replay = self.repository.replay(index["items"][0]["result_id"])
        self.assertEqual(replay["domain"], "flight_simulation")
        self.assertEqual(replay["scene"]["px4_path"][-1], [0.0, 2.0, 2.0])
        self.assertEqual(replay["curves"][0]["curve_id"], "target_altitude_m")

    def test_reports_invalid_results_without_hiding_valid_ones(self) -> None:
        invalid = self.workspace / "results/benchmarks/fast_lio2/invalid"
        write_json(invalid / "t0_run_manifest.json", {"schema": "invalid"})
        index = self.repository.search(refresh=True)
        self.assertEqual(index["total"], 2)
        self.assertEqual(index["invalid_result_count"], 1)

    def test_keeps_incomplete_legacy_lio_manifests(self) -> None:
        directory = self.workspace / "results/benchmarks/fast_lio2/incomplete"
        write_json(directory / "run_manifest.json", {
            "schema_version": 3,
            "algorithm": "FAST-LIO2",
            "mapping_process": {"exit_code": 1},
        })
        index = self.repository.search({"state": "abandoned"}, refresh=True)
        self.assertEqual(index["total"], 1)
        self.assertEqual(index["items"][0]["metrics_status"], "unavailable")

    def test_rejects_result_directory_outside_workspace(self) -> None:
        with self.assertRaises(ValueError):
            ResultRepository(self.workspace, self.workspace.parent)
        with self.assertRaises(ResultHistoryError):
            self.repository.detail("unknown")


if __name__ == "__main__":
    unittest.main()
