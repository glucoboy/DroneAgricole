from pathlib import Path
import tempfile
from unittest import TestCase

import numpy as np
import yaml

from software.visualization.dashboard_server import (
    RequestError,
    align_live,
    downsample_path,
    load_catalog,
    resolve_run_request,
    write_fastlio_config,
    write_lio_config,
)


class LiveDashboardTest(TestCase):
    def test_live_alignment_maps_truth_back_to_estimate_frame(self) -> None:
        times = np.arange(6, dtype=np.float64)
        estimate = np.asarray(
            [
                [0.0, 0.0, 0.0],
                [1.0, 0.0, 0.0],
                [1.0, 1.0, 0.0],
                [0.0, 1.0, 0.0],
                [0.5, 1.5, 0.2],
                [1.5, 0.5, 0.4],
            ],
            dtype=np.float64,
        )
        angle = np.deg2rad(25.0)
        rotation = np.asarray(
            [
                [np.cos(angle), -np.sin(angle), 0.0],
                [np.sin(angle), np.cos(angle), 0.0],
                [0.0, 0.0, 1.0],
            ]
        )
        translation = np.asarray([3.0, -2.0, 0.7])
        truth = (rotation @ estimate.T).T + translation

        rmse, truth_in_estimate = align_live(times, estimate, times, truth)

        self.assertIsNotNone(rmse)
        self.assertLess(float(rmse), 1e-12)
        np.testing.assert_allclose(truth_in_estimate, estimate, atol=1e-12)

    def test_path_downsampling_preserves_both_ends(self) -> None:
        path = np.column_stack(
            (np.arange(100), np.zeros(100), np.zeros(100))
        ).astype(np.float64)

        sampled = downsample_path(path, maximum=10)

        self.assertEqual(len(sampled), 10)
        self.assertEqual(sampled[0][0], 0.0)
        self.assertEqual(sampled[-1][0], 99.0)

    def test_catalog_request_resolves_defaults_and_paths(self) -> None:
        catalog = load_catalog(Path("configs/visualization/dashboard_catalog.json"))
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            sequence = catalog["datasets"][0]["sequences"][0]
            algorithm = catalog["algorithms"][0]
            (workspace / sequence["bag_path"]).mkdir(parents=True)
            config = workspace / algorithm["base_config"]
            config.parent.mkdir(parents=True)
            config.write_text("/**: {ros__parameters: {}}\n", encoding="utf-8")

            resolved = resolve_run_request(
                catalog,
                {
                    "dataset_id": "botanicgarden",
                    "sequence_id": "1006-03-smoke",
                    "algorithm_id": "fast_lio2",
                    "parameters": {"filter_size_surf": 0.25},
                },
                workspace,
            )

            self.assertEqual(resolved["parameters"]["filter_size_surf"], 0.25)
            self.assertEqual(resolved["parameters"]["playback_rate"], 1.0)
            self.assertTrue(resolved["bag_path"].is_relative_to(workspace))

    def test_unknown_algorithm_is_rejected(self) -> None:
        catalog = load_catalog(Path("configs/visualization/dashboard_catalog.json"))
        with self.assertRaises(RequestError):
            resolve_run_request(
                catalog,
                {
                    "dataset_id": "botanicgarden",
                    "sequence_id": "1006-03-smoke",
                    "algorithm_id": "not_integrated",
                },
                Path.cwd(),
            )

    def test_fastlio_configuration_overrides_are_traceable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "effective.yaml"
            write_fastlio_config(
                Path("configs/lio/fast_lio2/botanicgarden_velodyne_xsens_visual.yaml"),
                output,
                {
                    "filter_size_surf": 0.25,
                    "filter_size_map": 0.75,
                    "point_filter_num": 2,
                    "max_iteration": 5,
                    "blind": 0.6,
                    "det_range": 80.0,
                },
            )
            parameters = yaml.safe_load(output.read_text(encoding="utf-8"))["/**"][
                "ros__parameters"
            ]

            self.assertEqual(parameters["filter_size_surf"], 0.25)
            self.assertEqual(parameters["filter_size_map"], 0.75)
            self.assertEqual(parameters["point_filter_num"], 2)
            self.assertEqual(parameters["max_iteration"], 5)
            self.assertEqual(parameters["preprocess"]["blind"], 0.6)
            self.assertEqual(parameters["mapping"]["det_range"], 80.0)
            self.assertTrue(parameters["publish"]["scan_publish_en"])
            self.assertEqual(parameters["common"]["lidar_qos_depth"], 100)
            self.assertTrue(parameters["common"]["lidar_qos_reliable"])

    def test_pointlio_configuration_overrides_are_traceable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "effective.yaml"
            write_lio_config(
                "point_lio",
                Path("configs/lio/point_lio/botanicgarden_velodyne_xsens_visual.yaml"),
                output,
                {
                    "filter_size_surf": 0.3,
                    "filter_size_map": 0.6,
                    "point_filter_num": 3,
                    "blind": 0.8,
                    "det_range": 90.0,
                    "plane_thr": 0.08,
                },
            )
            parameters = yaml.safe_load(output.read_text(encoding="utf-8"))["/**"][
                "ros__parameters"
            ]

            self.assertEqual(parameters["filter_size_surf"], 0.3)
            self.assertEqual(parameters["filter_size_map"], 0.6)
            self.assertEqual(parameters["point_filter_num"], 3)
            self.assertEqual(parameters["preprocess"]["blind"], 0.8)
            self.assertEqual(parameters["mapping"]["det_range"], 90.0)
            self.assertEqual(parameters["mapping"]["plane_thr"], 0.08)
            self.assertTrue(parameters["publish"]["scan_publish_en"])

    def test_liosam_configuration_overrides_are_traceable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "effective.yaml"
            write_lio_config(
                "lio_sam",
                Path("configs/lio/lio_sam/botanicgarden_velodyne_xsens_visual.yaml"),
                output,
                {
                    "odometrySurfLeafSize": 0.3,
                    "mappingCornerLeafSize": 0.15,
                    "mappingSurfLeafSize": 0.35,
                    "edgeThreshold": 0.8,
                    "surfThreshold": 0.08,
                    "mappingProcessInterval": 0.0,
                },
            )
            parameters = yaml.safe_load(output.read_text(encoding="utf-8"))["/**"][
                "ros__parameters"
            ]

            self.assertEqual(parameters["odometrySurfLeafSize"], 0.3)
            self.assertEqual(parameters["mappingCornerLeafSize"], 0.15)
            self.assertEqual(parameters["mappingSurfLeafSize"], 0.35)
            self.assertEqual(parameters["edgeThreshold"], 0.8)
            self.assertEqual(parameters["surfThreshold"], 0.08)
            self.assertEqual(parameters["mappingProcessInterval"], 0.0)
