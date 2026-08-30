#!/usr/bin/env python3
"""Inspect ROS 1 bag metadata without modifying the bag files."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from rosbags.highlevel import AnyReader
from rosbags.rosbag1 import Reader


def iso_utc(timestamp_ns: int) -> str:
    return datetime.fromtimestamp(timestamp_ns / 1_000_000_000, tz=timezone.utc).isoformat()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def summarize_message(topic: str, message: Any) -> dict[str, Any]:
    result: dict[str, Any] = {}
    header = getattr(message, "header", None)
    if header is not None:
        result["frame_id"] = header.frame_id

    if topic == "/velodyne_points":
        result.update(
            {
                "height": message.height,
                "width": message.width,
                "point_fields": [field.name for field in message.fields],
                "point_step_bytes": message.point_step,
                "dense": message.is_dense,
            }
        )
    elif topic == "/livox/lidar":
        result.update(
            {
                "point_num": message.point_num,
                "lidar_id": message.lidar_id,
                "timebase": message.timebase,
            }
        )
    elif topic in {"/imu/data", "/livox/imu"}:
        result.update(
            {
                "orientation_covariance_0": float(message.orientation_covariance[0]),
                "angular_velocity_covariance_0": float(message.angular_velocity_covariance[0]),
                "linear_acceleration_covariance_0": float(message.linear_acceleration_covariance[0]),
            }
        )
    elif topic == "/odom":
        result["child_frame_id"] = message.child_frame_id
    elif topic == "/gt_poses":
        result["position_xyz"] = [
            float(message.pose.position.x),
            float(message.pose.position.y),
            float(message.pose.position.z),
        ]
    return result


def inspect(path: Path, include_hash: bool) -> dict[str, Any]:
    with Reader(path) as reader:
        topics: list[dict[str, Any]] = []
        for connection in reader.connections:
            indexes = reader.indexes[connection.id]
            first_ns = indexes[0].time
            last_ns = indexes[-1].time
            active_duration_s = (last_ns - first_ns) / 1_000_000_000
            timestamps = np.fromiter((entry.time for entry in indexes), dtype=np.int64)
            periods_ms = np.diff(timestamps) / 1_000_000
            median_period_ms = float(np.median(periods_ms)) if periods_ms.size else None
            topics.append(
                {
                    "topic": connection.topic,
                    "type": connection.msgtype,
                    "messages": connection.msgcount,
                    "first_timestamp_ns": first_ns,
                    "last_timestamp_ns": last_ns,
                    "active_duration_s": active_duration_s,
                    "average_hz": (
                        (connection.msgcount - 1) / active_duration_s
                        if connection.msgcount > 1 and active_duration_s > 0
                        else None
                    ),
                    "period_ms": (
                        {
                            "minimum": float(np.min(periods_ms)),
                            "median": median_period_ms,
                            "p95": float(np.percentile(periods_ms, 95)),
                            "p99": float(np.percentile(periods_ms, 99)),
                            "maximum": float(np.max(periods_ms)),
                            "gaps_over_2x_median": int(
                                np.count_nonzero(periods_ms > 2 * median_period_ms)
                            ),
                        }
                        if periods_ms.size and median_period_ms is not None
                        else None
                    ),
                }
            )

        report: dict[str, Any] = {
            "path": str(path),
            "format": "ROS 1 bag",
            "size_bytes": path.stat().st_size,
            "start_timestamp_ns": reader.start_time,
            "end_timestamp_ns": reader.end_time,
            "start_utc": iso_utc(reader.start_time),
            "end_utc": iso_utc(reader.end_time),
            "duration_s": reader.duration / 1_000_000_000,
            "messages": reader.message_count,
            "chunks": len(reader.chunk_infos),
            "topics": topics,
        }

    samples: dict[str, Any] = {}
    pending = {item["topic"] for item in topics}
    with AnyReader([path]) as reader:
        for connection, timestamp, rawdata in reader.messages():
            if connection.topic not in pending:
                continue
            try:
                message = reader.deserialize(rawdata, connection.msgtype)
                samples[connection.topic] = {
                    "timestamp_ns": timestamp,
                    **summarize_message(connection.topic, message),
                }
            except Exception as exc:  # Keep inspection useful for unknown custom messages.
                samples[connection.topic] = {"deserialization_error": str(exc)}
            pending.remove(connection.topic)
            if not pending:
                break

    report["first_message_samples"] = samples
    if include_hash:
        report["sha256"] = sha256(path)
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("bags", nargs="+", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--hash", action="store_true")
    args = parser.parse_args()

    result = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "bags": [inspect(path.resolve(), args.hash) for path in args.bags],
    }
    rendered = json.dumps(result, indent=2, ensure_ascii=False)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
