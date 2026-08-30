#!/usr/bin/env python3
"""Compare the repeated 0.8x FAST-LIO2 campaign with the previous 1x campaign."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from statistics import mean, stdev
from typing import Any


MEASUREMENTS = (
    "output_scan_ratio_percent",
    "ate_translation_rmse_m",
    "ate_orientation_rmse_deg",
    "rpe_translation_rmse_m",
    "rpe_rotation_rmse_deg",
    "cpu_total_seconds",
    "cpu_average_equivalent_cores",
    "peak_rss_mib",
)


def stats(values: list[float]) -> dict[str, float | int]:
    return {
        "n": len(values),
        "mean": mean(values),
        "sample_stdev": stdev(values) if len(values) > 1 else 0.0,
        "minimum": min(values),
        "maximum": max(values),
    }


def old_dynamic_rows(summary: dict[str, Any], variant: str) -> list[dict[str, float]]:
    source = [
        row
        for row in summary["runs"]
        if row["variant"].startswith("baseline")
        if variant == "baseline"
    ] if variant == "baseline" else [
        row for row in summary["runs"] if row["variant"] == variant
    ]
    return [
        {
            "output_scan_ratio_percent": 100.0 * float(row["matched_poses"]) / 298.0,
            "ate_translation_rmse_m": float(row["ate_translation_rmse_m"]),
            "ate_orientation_rmse_deg": float(row["ate_orientation_rmse_deg"]),
            "rpe_translation_rmse_m": float(row["rpe_translation_rmse_m"]),
            "rpe_rotation_rmse_deg": float(row["rpe_rotation_rmse_deg"]),
            "cpu_total_seconds": float(row["cpu_total_seconds"]),
            "cpu_average_equivalent_cores": float(row["cpu_average_equivalent_cores"]),
            "peak_rss_mib": float(row["peak_rss_mib"]),
        }
        for row in source
    ]


def full_1x_row(directory: Path) -> dict[str, float]:
    manifest = json.loads((directory / "run_manifest.json").read_text(encoding="utf-8"))
    metrics = json.loads((directory / "metrics.json").read_text(encoding="utf-8"))
    profile = manifest["mapping_process"]
    return {
        "output_scan_ratio_percent": 100.0 * float(metrics["estimate_poses"]) / 5762.0,
        "ate_translation_rmse_m": float(metrics["ate_translation_m"]["rmse"]),
        "ate_orientation_rmse_deg": float(metrics["ate_orientation_deg"]["rmse"]),
        "rpe_translation_rmse_m": float(metrics["rpe"]["translation_m"]["rmse"]),
        "rpe_rotation_rmse_deg": float(metrics["rpe"]["rotation_deg"]["rmse"]),
        "cpu_total_seconds": float(profile["cpu_total_seconds"]),
        "cpu_average_equivalent_cores": float(profile["cpu_average_equivalent_cores"]),
        "peak_rss_mib": float(profile["peak_rss_mib"]),
    }


def compare_group(
    scope: str,
    variant: str,
    old_rows: list[dict[str, float]],
    new_measurements: dict[str, dict[str, float]],
) -> dict[str, Any]:
    at_1x = {
        measurement: stats([row[measurement] for row in old_rows])
        for measurement in MEASUREMENTS
    }
    at_08x = {measurement: new_measurements[measurement] for measurement in MEASUREMENTS}
    changes = {}
    for measurement in MEASUREMENTS:
        old_mean = float(at_1x[measurement]["mean"])
        new_mean = float(at_08x[measurement]["mean"])
        changes[measurement] = {
            "absolute": new_mean - old_mean,
            "percent": 100.0 * (new_mean - old_mean) / old_mean if old_mean else None,
        }
    return {
        "scope": scope,
        "variant": variant,
        "at_1x": at_1x,
        "at_08x": at_08x,
        "change_08x_minus_1x": changes,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-08x", required=True, type=Path)
    parser.add_argument("--sensitivity-1x", required=True, type=Path)
    parser.add_argument("--full-1x", required=True, type=Path)
    args = parser.parse_args()

    campaign = json.loads(
        (args.campaign_08x / "campaign_summary.json").read_text(encoding="utf-8")
    )
    previous = json.loads(args.sensitivity_1x.read_text(encoding="utf-8"))
    groups = {(group["scope"], group["variant"]): group for group in campaign["groups"]}
    comparisons = []
    for scope, variant in sorted(groups):
        group = groups[(scope, variant)]
        if scope == "dynamic":
            old_rows = old_dynamic_rows(previous, variant)
        elif scope == "full" and variant == "baseline":
            old_rows = [full_1x_row(args.full_1x)]
        else:
            continue
        comparisons.append(
            compare_group(scope, variant, old_rows, group["measurements"])
        )

    report = {
        "schema_version": 1,
        "reference_rate": 1.0,
        "candidate_rate": 0.8,
        "comparisons": comparisons,
    }
    output_json = args.campaign_08x / "comparison_1x_vs_08x.json"
    output_csv = args.campaign_08x / "comparison_1x_vs_08x.csv"
    output_json.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    rows = []
    for comparison in comparisons:
        row: dict[str, Any] = {
            "scope": comparison["scope"],
            "variant": comparison["variant"],
        }
        for measurement in MEASUREMENTS:
            row[f"{measurement}_1x_mean"] = comparison["at_1x"][measurement]["mean"]
            row[f"{measurement}_08x_mean"] = comparison["at_08x"][measurement]["mean"]
            row[f"{measurement}_change_percent"] = comparison[
                "change_08x_minus_1x"
            ][measurement]["percent"]
        rows.append(row)
    with output_csv.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
