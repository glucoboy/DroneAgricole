#!/usr/bin/env python3
"""Compare two or more instrumented LIO benchmark directories."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def load_run(path: Path) -> dict[str, object]:
    return {
        "path": str(path.resolve()),
        "metrics": json.loads((path / "metrics.json").read_text(encoding="utf-8")),
        "manifest": json.loads((path / "run_manifest.json").read_text(encoding="utf-8")),
    }


def compact(run: dict[str, object]) -> dict[str, object]:
    metrics = run["metrics"]
    manifest = run["manifest"]
    profile = manifest["mapping_process"]
    counters = metrics.get("pipeline_counters") or {}
    return {
        "run": run["path"],
        "algorithm": manifest.get("algorithm", "fast_lio2"),
        "ate_translation_rmse_m": metrics["ate_translation_m"]["rmse"],
        "ate_orientation_rmse_deg": metrics["ate_orientation_deg"]["rmse"],
        "rpe_translation_rmse_m": metrics["rpe"]["translation_m"]["rmse"],
        "rpe_rotation_rmse_deg": metrics["rpe"]["rotation_deg"]["rmse"],
        "cpu_seconds": profile["cpu_total_seconds"],
        "average_cpu_cores": profile["cpu_average_equivalent_cores"],
        "peak_rss_mib": profile["peak_rss_mib"],
        "scans_received": counters.get("scans_received"),
        "odometry_published": counters.get("odometry_published"),
        "odometry_over_received_percent": (
            metrics.get("pipeline_accounting", {})
            .get("ratios_percent", {})
            .get("odometry_over_received")
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("runs", nargs="+", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if len(args.runs) < 2:
        parser.error("At least two benchmark directories are required")
    result = {
        "schema_version": 1,
        "runs": [compact(load_run(path)) for path in args.runs],
    }
    rendered = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")


if __name__ == "__main__":
    main()
