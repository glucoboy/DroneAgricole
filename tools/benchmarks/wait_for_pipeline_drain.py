#!/usr/bin/env python3
"""Wait until a LIO pipeline has received all input scans and becomes stable."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import time
from typing import Any

import yaml


def bag_topic_count(bag: Path, topic: str) -> int:
    metadata = yaml.safe_load((bag / "metadata.yaml").read_text(encoding="utf-8"))
    information = metadata["rosbag2_bagfile_information"]
    for item in information.get("topics_with_message_count", []):
        if item["topic_metadata"]["name"] == topic:
            return int(item["message_count"])
    raise ValueError(f"Topic absent du rosbag : {topic}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bag", required=True, type=Path)
    parser.add_argument("--input-topic", default="/velodyne_points")
    parser.add_argument("--pipeline-topic", required=True)
    parser.add_argument("--timeout-s", type=float, default=15.0)
    parser.add_argument("--stable-s", type=float, default=1.0)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    if args.timeout_s <= 0.0 or args.stable_s < 0.0:
        parser.error("Les temporisations doivent être positives.")

    import rclpy
    from rclpy.node import Node
    from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
    from std_msgs.msg import String

    expected_scans = bag_topic_count(args.bag, args.input_topic)
    latest: dict[str, Any] | None = None
    last_change = time.monotonic()

    class PipelineDrainNode(Node):
        def __init__(self) -> None:
            super().__init__("lio_pipeline_drain_monitor")
            qos = QoSProfile(
                depth=10,
                reliability=ReliabilityPolicy.RELIABLE,
                durability=DurabilityPolicy.VOLATILE,
            )
            self.create_subscription(String, args.pipeline_topic, self.receive, qos)

        def receive(self, message: String) -> None:
            nonlocal latest, last_change
            try:
                counters = json.loads(message.data)
            except (TypeError, json.JSONDecodeError):
                return
            if counters != latest:
                latest = counters
                last_change = time.monotonic()

    started = time.monotonic()
    deadline = started + args.timeout_s
    status = "timeout"
    rclpy.init()
    node = PipelineDrainNode()
    try:
        while time.monotonic() < deadline:
            rclpy.spin_once(node, timeout_sec=0.1)
            now = time.monotonic()
            received = int((latest or {}).get("scans_received", 0))
            if received >= expected_scans and now - last_change >= args.stable_s:
                status = "complete"
                break
    finally:
        node.destroy_node()
        rclpy.shutdown()

    observed_scans = int((latest or {}).get("scans_received", 0))
    result = {
        "schema_version": 1,
        "status": status,
        "pipeline_topic": args.pipeline_topic,
        "input_topic": args.input_topic,
        "expected_scans": expected_scans,
        "observed_scans": observed_scans,
        "missing_scans": max(expected_scans - observed_scans, 0),
        "wait_seconds": time.monotonic() - started,
        "stable_seconds_required": args.stable_s,
        "final_counters": latest,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if status != "complete":
        raise SystemExit(4)


if __name__ == "__main__":
    main()
