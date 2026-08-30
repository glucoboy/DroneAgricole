from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

from software.visualization.contracts import DefinitionRegistry
from software.visualization.px4_runner_contract import Px4RunnerError, validate_start_payload
from software.visualization.runners import RunnerRegistry, RunnerRequestError


WORKSPACE = Path(__file__).resolve().parents[2]
CONFIG_ROOT = WORKSPACE / "configs" / "visualization"


class DashboardRunnerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.definitions = DefinitionRegistry.load(CONFIG_ROOT / "datasets", CONFIG_ROOT / "simulations")

    def test_public_options_are_driven_by_contracts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            self._prepare_lio_workspace(workspace)
            options = RunnerRegistry(self.definitions, workspace).public_options()
        self.assertEqual("drone_agricole.dashboard_options.v2", options["schema"])
        self.assertEqual({"lio_benchmark", "px4_offboard"}, {value["simulation_id"] for value in options["simulations"]})
        self.assertTrue(options["single_active_run"])

    def test_fast_lio_runner_resolves_profile_and_writes_effective_config(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            self._prepare_lio_workspace(workspace)
            registry = RunnerRegistry(self.definitions, workspace)
            prepared = registry.prepare(
                {
                    "simulation_id": "lio_benchmark",
                    "variant_id": "fast_lio2",
                    "profile_id": "botanicgarden_velodyne_xsens",
                    "inputs": [{"input_id": "dataset", "kind": "dataset_sequence", "reference": {"dataset_id": "botanicgarden", "sequence_id": "1006-03-smoke"}}],
                    "parameters": {"filter_size_surf": 0.25},
                },
                "a1b2c3d4",
                "20260830T100000Z",
            )
            effective = yaml.safe_load(prepared.runtime_files[0].read_text(encoding="utf-8"))
        self.assertEqual("botanicgarden_velodyne_xsens", prepared.profile_id)
        self.assertEqual("bash", prepared.command[0])
        self.assertEqual("tools/benchmarks/run_fastlio2_botanicgarden_benchmark.sh", prepared.command[1])
        self.assertEqual(0.25, effective["/**"]["ros__parameters"]["filter_size_surf"])
        self.assertEqual(1.0, prepared.parameters["playback_rate"])

    def test_liosam_canonical_parameter_is_mapped_to_native_key(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            self._prepare_lio_workspace(workspace)
            prepared = RunnerRegistry(self.definitions, workspace).prepare(
                {
                    "simulation_id": "lio_benchmark",
                    "variant_id": "lio_sam",
                    "dataset_id": "botanicgarden",
                    "sequence_id": "1006-03-smoke",
                    "parameters": {"edge_threshold": 0.7},
                },
                "b1c2d3e4",
                "20260830T100000Z",
            )
            effective = yaml.safe_load(prepared.runtime_files[0].read_text(encoding="utf-8"))
        self.assertEqual(0.7, effective["/**"]["ros__parameters"]["edgeThreshold"])

    def test_px4_runner_has_no_arbitrary_command_or_input(self) -> None:
        with tempfile.TemporaryDirectory() as temporary, patch.dict(
            os.environ, {"DRONE_AGRICOLE_PX4_RUNNER_URL": "http://runner:8091"}
        ):
            prepared = RunnerRegistry(self.definitions, Path(temporary)).prepare(
                {
                    "simulation_id": "px4_offboard",
                    "variant_id": "failsafe",
                    "inputs": [],
                    "parameters": {"takeoff_altitude_m": 3.0},
                },
                "c1d2e3f4",
                "20260830T100000Z",
            )
        self.assertEqual("px4_failsafe", prepared.runner_id)
        self.assertEqual("sitl_confirmed", prepared.safety_class)
        self.assertEqual("python3", prepared.command[0])
        self.assertIn("tools/visualization/px4_remote_client.py", prepared.command)
        self.assertNotIn("bash", prepared.command)
        self.assertEqual([], prepared.inputs)

    def test_unknown_parameter_is_rejected_before_prepare(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            registry = RunnerRegistry(self.definitions, Path(temporary))
            with self.assertRaisesRegex(RunnerRequestError, "Paramètre inconnu"):
                registry.resolve(
                    {
                        "simulation_id": "px4_offboard",
                        "variant_id": "square",
                        "parameters": {"shell_command": "anything"},
                    }
                )

    def test_px4_internal_runner_rejects_path_escape(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            payload = self._px4_payload()
            payload["result_directory"] = "../outside"
            with self.assertRaisesRegex(Px4RunnerError, "chemin relatif"):
                validate_start_payload(payload, Path(temporary))

    def test_px4_internal_runner_accepts_only_bounded_payload(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            validated = validate_start_payload(self._px4_payload(), Path(temporary))
        self.assertEqual("square", validated["mode"])
        self.assertEqual(2.0, validated["parameters"]["takeoff_altitude_m"])

    @staticmethod
    def _px4_payload() -> dict:
        return {
            "run_id": "a1b2c3d4",
            "mode": "square",
            "result_directory": "results/simulation/px4_lot_a/square_a1b2c3d4",
            "parameters": {
                "takeoff_altitude_m": 2.0,
                "leg_m": 2.0,
                "warmup_s": 2.0,
                "hover_s": 3.0,
                "stage_timeout_s": 12.0,
            },
        }

    @staticmethod
    def _prepare_lio_workspace(workspace: Path) -> None:
        bag = workspace / "datasets/derived/botanicgarden/1006-03/smoke/velodyne_xsens_fastlio2_5s_ros2"
        bag.mkdir(parents=True)
        calibration = workspace / "datasets/public/botanicgarden/1006-03/calibration/official_84c4806428ca"
        calibration.mkdir(parents=True)
        base_parameters = {
            "filter_size_surf": 0.5,
            "filter_size_map": 0.5,
            "point_filter_num": 4,
            "max_iteration": 3,
            "preprocess": {"blind": 1.0},
            "mapping": {"det_range": 100.0, "plane_thr": 0.1},
            "publish": {"scan_publish_en": False},
            "common": {},
            "odometrySurfLeafSize": 0.4,
            "mappingCornerLeafSize": 0.2,
            "mappingSurfLeafSize": 0.4,
            "edgeThreshold": 1.0,
            "surfThreshold": 0.1,
            "mappingProcessInterval": 0.0,
        }
        configuration = {"/**": {"ros__parameters": base_parameters}}
        for algorithm in ("fast_lio2", "point_lio", "lio_sam"):
            path = workspace / f"configs/lio/{algorithm}/botanicgarden_velodyne_xsens_visual.yaml"
            path.parent.mkdir(parents=True)
            path.write_text(yaml.safe_dump(configuration), encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
