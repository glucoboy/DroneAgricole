#!/usr/bin/env python3
"""Summarize the repeated FAST-LIO2 0.8x qualification campaign."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from statistics import mean, stdev
from typing import Any


MEASUREMENTS = (
    "output_scan_ratio_percent",
    "trajectory_coverage_percent",
    "ate_translation_rmse_m",
    "ate_orientation_rmse_deg",
    "rpe_translation_rmse_m",
    "rpe_rotation_rmse_deg",
    "cpu_total_seconds",
    "cpu_average_equivalent_cores",
    "peak_rss_mib",
    "scheduled_data_seconds_per_wall_second",
)


def nested(value: dict[str, Any], *path: str) -> Any:
    current: Any = value
    for key in path:
        current = current[key]
    return current


def load_run(directory: Path, root: Path) -> dict[str, Any]:
    relative = directory.relative_to(root)
    if len(relative.parts) != 3:
        raise RuntimeError(f"Unexpected campaign run path: {relative}")
    scope, variant, repetition = relative.parts
    manifest = json.loads((directory / "run_manifest.json").read_text(encoding="utf-8"))
    metrics = json.loads((directory / "metrics.json").read_text(encoding="utf-8"))
    input_scans = int(
        manifest.get("input_topic_message_counts", {}).get(
            "/velodyne_points",
            metrics["ground_truth_poses"],
        )
    )
    output_poses = int(metrics["estimate_poses"])
    input_duration = float(manifest["input_bag_duration_s"])
    trajectory_duration = float(metrics["estimate_header_duration_s"])
    profile = manifest["mapping_process"]
    return {
        "scope": scope,
        "variant": variant,
        "repetition": repetition,
        "directory": relative.as_posix(),
        "config_sha256": manifest["config_sha256"],
        "playback_rate_requested": manifest["playback_rate_requested"],
        "input_scans": input_scans,
        "output_poses": output_poses,
        "output_scan_ratio_percent": 100.0 * output_poses / input_scans,
        "trajectory_coverage_percent": 100.0 * trajectory_duration / input_duration,
        "matched_poses": metrics["matched_poses"],
        "ate_translation_rmse_m": nested(metrics, "ate_translation_m", "rmse"),
        "ate_orientation_rmse_deg": nested(metrics, "ate_orientation_deg", "rmse"),
        "rpe_translation_rmse_m": nested(metrics, "rpe", "translation_m", "rmse"),
        "rpe_rotation_rmse_deg": nested(metrics, "rpe", "rotation_deg", "rmse"),
        "cpu_total_seconds": profile["cpu_total_seconds"],
        "cpu_average_equivalent_cores": profile["cpu_average_equivalent_cores"],
        "peak_rss_mib": profile["peak_rss_mib"],
        "scheduled_data_seconds_per_wall_second": manifest[
            "scheduled_data_seconds_per_wall_second"
        ],
    }


def statistics(values: list[float]) -> dict[str, float | int]:
    return {
        "n": len(values),
        "mean": mean(values),
        "sample_stdev": stdev(values) if len(values) > 1 else 0.0,
        "minimum": min(values),
        "maximum": max(values),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    args = parser.parse_args()

    runs = [
        load_run(directory, args.root)
        for directory in sorted(args.root.glob("*/*/repeat_*"))
        if (directory / "run_manifest.json").is_file()
        and (directory / "metrics.json").is_file()
    ]
    if not runs:
        raise RuntimeError(f"No complete campaign runs found under {args.root}")

    group_keys = sorted({(run["scope"], run["variant"]) for run in runs})
    groups: list[dict[str, Any]] = []
    for scope, variant in group_keys:
        selected = [run for run in runs if run["scope"] == scope and run["variant"] == variant]
        groups.append(
            {
                "scope": scope,
                "variant": variant,
                "repetitions": len(selected),
                "measurements": {
                    measurement: statistics(
                        [float(run[measurement]) for run in selected]
                    )
                    for measurement in MEASUREMENTS
                },
            }
        )

    report = {
        "schema_version": 1,
        "playback_rate": 0.8,
        "runs": runs,
        "groups": groups,
    }
    json_path = args.root / "campaign_summary.json"
    csv_path = args.root / "campaign_runs.csv"
    json_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    with csv_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(runs[0]))
        writer.writeheader()
        writer.writerows(runs)
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
