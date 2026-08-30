#!/usr/bin/env python3
"""Create a reproducible timing/resource manifest for one LIO replay."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import yaml


def bag_metadata(path: Path) -> tuple[float, int, dict[str, int]]:
    metadata = yaml.safe_load((path / "metadata.yaml").read_text(encoding="utf-8"))
    information = metadata["rosbag2_bagfile_information"]
    duration = information["duration"]
    nanoseconds = duration["nanoseconds"] if isinstance(duration, dict) else duration
    topic_counts = {
        item["topic_metadata"]["name"]: int(item["message_count"])
        for item in information.get("topics_with_message_count", [])
    }
    return (
        float(nanoseconds) / 1_000_000_000.0,
        int(information["message_count"]),
        topic_counts,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--algorithm", required=True)
    parser.add_argument("--bag", required=True, type=Path)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--profile", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--playback-rate", required=True, type=float)
    parser.add_argument("--playback-delay-s", type=float, default=0.0)
    parser.add_argument("--playback-start-ns", required=True, type=int)
    parser.add_argument("--playback-end-ns", required=True, type=int)
    args = parser.parse_args()

    duration_s, messages, topic_counts = bag_metadata(args.bag)
    playback_wall_s = (args.playback_end_ns - args.playback_start_ns) / 1_000_000_000.0
    active_playback_wall_s = max(playback_wall_s - args.playback_delay_s, 0.0)
    profile = json.loads(args.profile.read_text(encoding="utf-8"))
    result = {
        "schema_version": 3,
        "algorithm": args.algorithm,
        "input_bag": str(args.bag.resolve()),
        "input_bag_duration_s": duration_s,
        "input_message_count": messages,
        "input_topic_message_counts": topic_counts,
        "config": str(args.config.resolve()),
        "config_sha256": hashlib.sha256(args.config.read_bytes()).hexdigest(),
        "playback_rate_requested": args.playback_rate,
        "playback_delay_seconds": args.playback_delay_s,
        "playback_wall_seconds": playback_wall_s,
        "active_playback_wall_seconds": active_playback_wall_s,
        "scheduled_data_seconds_per_wall_second": (
            duration_s / active_playback_wall_s if active_playback_wall_s else None
        ),
        "mapping_process": profile,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
