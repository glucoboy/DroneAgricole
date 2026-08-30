#!/usr/bin/env python3
"""Aggregate FAST-LIO2 sensitivity runs into comparable JSON and CSV tables."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


FIELDS = {
    "ate_translation_rmse_m": ("ate_translation_m", "rmse"),
    "ate_orientation_rmse_deg": ("ate_orientation_deg", "rmse"),
    "rpe_translation_rmse_m": ("rpe", "translation_m", "rmse"),
    "rpe_rotation_rmse_deg": ("rpe", "rotation_deg", "rmse"),
    "path_length_ratio": ("matched_path_length_m", "ratio_estimate_over_ground_truth"),
}


def nested(data: dict[str, object], path: tuple[str, ...]) -> object:
    value: object = data
    for key in path:
        value = value[key]  # type: ignore[index]
    return value


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--baseline", default="baseline")
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--output-csv", type=Path)
    args = parser.parse_args()

    rows: list[dict[str, object]] = []
    for directory in sorted(path for path in args.root.iterdir() if path.is_dir()):
        metrics_path = directory / "metrics.json"
        manifest_path = directory / "run_manifest.json"
        if not metrics_path.exists() or not manifest_path.exists():
            continue
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        profile = manifest["mapping_process"]
        row: dict[str, object] = {
            "variant": directory.name,
            "config": manifest["config"],
            "config_sha256": manifest["config_sha256"],
            "matched_poses": metrics["matched_poses"],
            "playback_wall_seconds": manifest["playback_wall_seconds"],
            "cpu_total_seconds": profile["cpu_total_seconds"],
            "cpu_average_equivalent_cores": profile["cpu_average_equivalent_cores"],
            "peak_rss_mib": profile["peak_rss_mib"],
        }
        for name, path in FIELDS.items():
            row[name] = nested(metrics, path)
        rows.append(row)

    if not rows:
        raise RuntimeError(f"No complete sensitivity runs found under {args.root}")
    baseline = next((row for row in rows if row["variant"] == args.baseline), None)
    if baseline is None:
        raise RuntimeError(f"Baseline variant {args.baseline!r} was not found")
    for row in rows:
        for name in FIELDS:
            baseline_value = float(baseline[name])
            value = float(row[name])
            row[f"{name}_change_percent"] = (
                100.0 * (value - baseline_value) / baseline_value
                if baseline_value
                else None
            )

    output_json = args.output_json or args.root / "sensitivity_summary.json"
    output_csv = args.output_csv or args.root / "sensitivity_summary.csv"
    report = {
        "schema_version": 1,
        "baseline": args.baseline,
        "runs": rows,
    }
    output_json.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    with output_csv.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
