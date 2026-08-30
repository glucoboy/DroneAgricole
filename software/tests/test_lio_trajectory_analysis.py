from unittest import TestCase

import numpy as np

from tools.benchmarks.analyze_lio_trajectory import (
    compute_rpe,
    pipeline_accounting,
    quaternions_to_matrices,
    rotation_angles_deg,
)


class LioTrajectoryAnalysisTest(TestCase):
    def test_pipeline_accounting_locates_missing_outputs(self) -> None:
        result = pipeline_accounting(
            {
                "scans_received": 100,
                "scans_preprocessed": 100,
                "scans_synchronized": 96,
                "scans_initialization": 1,
                "scans_rejected_undistort_empty": 2,
                "scans_map_initialization": 1,
                "scans_rejected_downsample": 0,
                "state_updates": 92,
                "odometry_published": 92,
            }
        )

        self.assertEqual(result["preprocessed_minus_synchronized"], 4)
        self.assertEqual(result["unaccounted_synchronized_scans"], 0)
        self.assertEqual(result["state_updates_minus_odometry"], 0)
        self.assertAlmostEqual(result["ratios_percent"]["odometry_over_received"], 92.0)

    def test_quaternion_rotation_error_is_reported_in_degrees(self) -> None:
        identity = quaternions_to_matrices(
            np.asarray([[0.0, 0.0, 0.0, 1.0]], dtype=np.float64)
        )
        sine = np.sqrt(0.5)
        yaw_90 = quaternions_to_matrices(
            np.asarray([[0.0, 0.0, sine, sine]], dtype=np.float64)
        )

        error = rotation_angles_deg(identity, yaw_90)

        self.assertAlmostEqual(float(error[0]), 90.0, places=9)

    def test_fixed_time_rpe_detects_translation_scale_error(self) -> None:
        times = np.asarray([0.0, 1.0, 2.0], dtype=np.float64)
        estimate_positions = np.asarray(
            [[0.0, 0.0, 0.0], [1.1, 0.0, 0.0], [2.2, 0.0, 0.0]],
            dtype=np.float64,
        )
        truth_positions = np.asarray(
            [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [2.0, 0.0, 0.0]],
            dtype=np.float64,
        )
        rotations = np.repeat(np.eye(3)[np.newaxis, :, :], 3, axis=0)

        result = compute_rpe(
            times,
            estimate_positions,
            rotations,
            truth_positions,
            rotations,
            delta_s=1.0,
            delta_tolerance_s=0.01,
        )

        self.assertEqual(result["pairs"], 2)
        self.assertAlmostEqual(result["translation_m"]["rmse"], 0.1, places=9)
        self.assertAlmostEqual(result["rotation_deg"]["maximum"], 0.0, places=9)
