#!/usr/bin/env python3
"""Aggregate LIO-SAM stage counters into the common benchmark schema."""

from __future__ import annotations

import json

import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from std_msgs.msg import String, UInt64


class LioSamPipelineMonitor(Node):
    def __init__(self) -> None:
        super().__init__("lio_sam_pipeline_monitor")
        qos = QoSProfile(
            depth=100,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.VOLATILE,
        )
        self.values = {
            "scans_received": 0,
            "scans_preprocessed": 0,
            "scans_synchronized": 0,
            "odometry_published": 0,
        }
        topics = {
            "scans_received": "/lio_sam/pipeline/scans_received",
            "scans_preprocessed": "/lio_sam/pipeline/scans_preprocessed",
            "scans_synchronized": "/lio_sam/pipeline/scans_synchronized",
            "odometry_published": "/lio_sam/pipeline/odometry_published",
        }
        # Node.subscriptions is a read-only ROS 2 introspection property.
        # Keep explicit references so the subscriptions are not garbage-collected.
        self._pipeline_subscriptions = [
            self.create_subscription(
                UInt64,
                topic,
                lambda message, key=key: self.update(key, message.data),
                qos,
            )
            for key, topic in topics.items()
        ]
        self.publisher = self.create_publisher(
            String,
            "/lio_sam/pipeline_counters",
            10,
        )
        self.timer = self.create_timer(0.25, self.publish)

    def update(self, key: str, value: int) -> None:
        self.values[key] = max(self.values[key], int(value))

    def snapshot(self) -> dict[str, int]:
        synchronized = self.values["scans_synchronized"]
        odometry = self.values["odometry_published"]
        return {
            "schema_version": 1,
            **self.values,
            "scans_preprocess_empty": 0,
            "scans_initialization": max(synchronized - odometry, 0),
            "scans_imu_processed": self.values["scans_preprocessed"],
            "scans_rejected_undistort_empty": 0,
            "scans_map_initialization": 0,
            "scans_rejected_downsample": 0,
            "state_updates": odometry,
            "scans_input_buffered": max(
                self.values["scans_received"] - self.values["scans_preprocessed"],
                0,
            ),
        }

    def publish(self) -> None:
        self.publisher.publish(String(data=json.dumps(self.snapshot(), separators=(",", ":"))))


def main() -> None:
    rclpy.init()
    node = LioSamPipelineMonitor()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        print("LIOSAM_PIPELINE_FINAL " + json.dumps(node.snapshot(), separators=(",", ":")))
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
