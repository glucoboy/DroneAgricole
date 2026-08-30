import json
from pathlib import Path
import tempfile
from unittest import TestCase

from tools.benchmarks.summarize_fastlio_08x_campaign import load_run, statistics
from tools.benchmarks.summarize_fastlio_run import bag_metadata
from tools.benchmarks.wait_for_pipeline_drain import bag_topic_count


class FastlioCampaignSummaryTest(TestCase):
    def test_bag_metadata_exposes_topic_counts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "metadata.yaml").write_text(
                """rosbag2_bagfile_information:
  duration: {nanoseconds: 5000000000}
  message_count: 30
  topics_with_message_count:
    - message_count: 12
      topic_metadata: {name: /velodyne_points}
    - message_count: 18
      topic_metadata: {name: /imu/data}
""",
                encoding="utf-8",
            )

            duration, messages, topics = bag_metadata(root)

            self.assertEqual(duration, 5.0)
            self.assertEqual(messages, 30)
            self.assertEqual(topics["/velodyne_points"], 12)
            self.assertEqual(bag_topic_count(root, "/velodyne_points"), 12)

    def test_campaign_run_uses_input_scan_count(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run = root / "dynamic" / "baseline" / "repeat_01"
            run.mkdir(parents=True)
            manifest = {
                "config_sha256": "abc",
                "playback_rate_requested": 0.8,
                "input_bag_duration_s": 30.0,
                "input_topic_message_counts": {"/velodyne_points": 300},
                "scheduled_data_seconds_per_wall_second": 0.8,
                "mapping_process": {
                    "cpu_total_seconds": 10.0,
                    "cpu_average_equivalent_cores": 0.3,
                    "peak_rss_mib": 170.0,
                },
            }
            metrics = {
                "estimate_poses": 270,
                "ground_truth_poses": 300,
                "estimate_header_duration_s": 29.0,
                "matched_poses": 270,
                "ate_translation_m": {"rmse": 0.02},
                "ate_orientation_deg": {"rmse": 1.0},
                "rpe": {
                    "translation_m": {"rmse": 0.04},
                    "rotation_deg": {"rmse": 0.2},
                },
            }
            (run / "run_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            (run / "metrics.json").write_text(json.dumps(metrics), encoding="utf-8")

            row = load_run(run, root)

            self.assertEqual(row["input_scans"], 300)
            self.assertEqual(row["output_poses"], 270)
            self.assertEqual(row["output_scan_ratio_percent"], 90.0)
            self.assertAlmostEqual(row["trajectory_coverage_percent"], 96.6666667)

    def test_statistics_reports_repeatability(self) -> None:
        result = statistics([1.0, 2.0, 3.0])

        self.assertEqual(result["n"], 3)
        self.assertEqual(result["mean"], 2.0)
        self.assertEqual(result["sample_stdev"], 1.0)
