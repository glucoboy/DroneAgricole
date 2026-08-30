#!/usr/bin/env python3
"""Launch the four headless LIO-SAM ROS 2 components used by benchmarks."""

from __future__ import annotations

import argparse
from pathlib import Path

from launch import LaunchDescription, LaunchService
from launch.actions import EmitEvent, LogInfo, RegisterEventHandler
from launch.event_handlers import OnProcessExit
from launch.events import Shutdown
from launch_ros.actions import Node


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    args = parser.parse_args()
    config = args.config.resolve()
    if not config.is_file():
        parser.error(f"Configuration absente : {config}")

    common_remappings = [
        ("lio_sam/mapping/odometry", "/Odometry"),
        ("lio_sam/mapping/path", "/path"),
        ("lio_sam/mapping/cloud_registered", "/cloud_registered"),
    ]
    critical_nodes = [
        (
            "imuPreintegration",
            Node(
                package="lio_sam",
                executable="lio_sam_imuPreintegration",
                parameters=[str(config)],
                remappings=common_remappings,
                output="screen",
            ),
        ),
        (
            "imageProjection",
            Node(
                package="lio_sam",
                executable="lio_sam_imageProjection",
                parameters=[str(config)],
                remappings=common_remappings,
                output="screen",
            ),
        ),
        (
            "featureExtraction",
            Node(
                package="lio_sam",
                executable="lio_sam_featureExtraction",
                parameters=[str(config)],
                remappings=common_remappings,
                output="screen",
            ),
        ),
        (
            "mapOptimization",
            Node(
                package="lio_sam",
                executable="lio_sam_mapOptimization",
                parameters=[str(config)],
                remappings=common_remappings,
                output="screen",
            ),
        ),
    ]
    shutdown_guards = [
        RegisterEventHandler(
            OnProcessExit(
                target_action=node,
                on_exit=[
                    LogInfo(msg=f"Critical LIO-SAM process exited: {label}"),
                    EmitEvent(
                        event=Shutdown(
                            reason=f"Critical LIO-SAM process exited: {label}"
                        )
                    )
                ],
            )
        )
        for label, node in critical_nodes
    ]
    description = LaunchDescription(
        [node for _, node in critical_nodes] + shutdown_guards
    )
    service = LaunchService()
    service.include_launch_description(description)
    raise SystemExit(service.run())


if __name__ == "__main__":
    main()
