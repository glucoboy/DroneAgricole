#!/usr/bin/env python3
"""Run one process and sample its CPU time and resident memory with psutil."""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import time
from pathlib import Path

import psutil


def read_bag_duration(path: Path | None) -> float:
    if path is None:
        return 0.0
    import yaml

    metadata = yaml.safe_load((path / "metadata.yaml").read_text(encoding="utf-8"))
    duration = metadata["rosbag2_bagfile_information"]["duration"]
    nanoseconds = duration["nanoseconds"] if isinstance(duration, dict) else duration
    return float(nanoseconds) / 1_000_000_000.0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--interval-s", type=float, default=0.25)
    parser.add_argument("--publish-ros-metrics", action="store_true")
    parser.add_argument("--benchmark-bag", type=Path)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        parser.error("a command is required after --")

    started_utc = time.time()
    started = time.monotonic()
    child = subprocess.Popen(command, start_new_session=True)
    root = psutil.Process(child.pid)
    forwarded_signal: int | None = None

    def forward(signum: int, _frame: object) -> None:
        nonlocal forwarded_signal
        forwarded_signal = signum
        try:
            os.killpg(child.pid, signum)
        except ProcessLookupError:
            pass

    signal.signal(signal.SIGINT, forward)
    signal.signal(signal.SIGTERM, forward)

    ros_node = None
    ros_publishers: dict[str, object] = {}
    expected_duration_s = read_bag_duration(args.benchmark_bag)
    if args.publish_ros_metrics:
        import rclpy
        from rclpy.signals import SignalHandlerOptions
        from std_msgs.msg import Float64

        # Le profileur relaie lui-même SIGINT/SIGTERM au processus mesuré.
        # Désactiver les handlers rclpy évite que le contexte ROS soit fermé
        # avant l'écriture du rapport de ressources.
        rclpy.init(args=None, signal_handler_options=SignalHandlerOptions.NO)
        ros_node = rclpy.create_node("fastlio_resource_profiler")
        ros_publishers = {
            "cpu": ros_node.create_publisher(
                Float64,
                "/benchmark/cpu_percent_one_core",
                10,
            ),
            "cpu_total": ros_node.create_publisher(
                Float64,
                "/benchmark/cpu_total_seconds",
                10,
            ),
            "memory": ros_node.create_publisher(
                Float64,
                "/benchmark/memory_rss_mib",
                10,
            ),
            "duration": ros_node.create_publisher(
                Float64,
                "/benchmark/expected_duration_s",
                10,
            ),
        }

    peak_rss = 0
    last_user = 0.0
    last_system = 0.0
    previous_cpu = 0.0
    previous_sample_time = started
    samples = 0
    while child.poll() is None:
        processes: list[psutil.Process] = []
        try:
            processes = [root, *root.children(recursive=True)]
        except psutil.Error:
            pass
        rss = 0
        user = 0.0
        system = 0.0
        for process in processes:
            try:
                rss += process.memory_info().rss
                cpu = process.cpu_times()
                user += cpu.user
                system += cpu.system
            except psutil.Error:
                continue
        peak_rss = max(peak_rss, rss)
        last_user = max(last_user, user)
        last_system = max(last_system, system)
        current_cpu = last_user + last_system
        current_sample_time = time.monotonic()
        sample_wall = max(current_sample_time - previous_sample_time, 1e-6)
        instant_cpu_percent = 100.0 * (current_cpu - previous_cpu) / sample_wall
        previous_cpu = current_cpu
        previous_sample_time = current_sample_time
        if ros_node is not None:
            from std_msgs.msg import Float64

            ros_publishers["cpu"].publish(Float64(data=instant_cpu_percent))
            ros_publishers["cpu_total"].publish(Float64(data=current_cpu))
            ros_publishers["memory"].publish(
                Float64(data=rss / (1024.0 * 1024.0))
            )
            ros_publishers["duration"].publish(Float64(data=expected_duration_s))
            rclpy.spin_once(ros_node, timeout_sec=0.0)
        samples += 1
        try:
            child.wait(timeout=args.interval_s)
        except subprocess.TimeoutExpired:
            pass

    return_code = child.wait()
    wall_seconds = time.monotonic() - started
    cpu_seconds = last_user + last_system
    logical_cpus = psutil.cpu_count(logical=True) or 1
    result = {
        "schema_version": 1,
        "command": command,
        "started_at_unix_s": started_utc,
        "wall_seconds": wall_seconds,
        "exit_code": return_code,
        "forwarded_signal": (
            signal.Signals(forwarded_signal).name if forwarded_signal is not None else None
        ),
        "samples": samples,
        "sample_interval_s": args.interval_s,
        "cpu_user_seconds": last_user,
        "cpu_system_seconds": last_system,
        "cpu_total_seconds": cpu_seconds,
        "cpu_average_equivalent_cores": cpu_seconds / wall_seconds if wall_seconds else None,
        "cpu_average_percent_one_core_100": (
            100.0 * cpu_seconds / wall_seconds if wall_seconds else None
        ),
        "logical_cpu_count_visible": logical_cpus,
        "cpu_average_percent_visible_machine": (
            100.0 * cpu_seconds / wall_seconds / logical_cpus if wall_seconds else None
        ),
        "peak_rss_bytes": peak_rss,
        "peak_rss_mib": peak_rss / (1024.0 * 1024.0),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    if ros_node is not None:
        ros_node.destroy_node()
        rclpy.shutdown()
    raise SystemExit(return_code if return_code > 0 else 0)


if __name__ == "__main__":
    main()
