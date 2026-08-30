"""Prepare reproducible BotanicGarden subsets for ROS 2 benchmarks."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from rosbags.convert.converter import create_connections_converters
from rosbags.highlevel import AnyReader
from rosbags.rosbag1 import Reader as Rosbag1Reader
from rosbags.rosbag2 import (
    CompressionFormat,
    CompressionMode,
    StoragePlugin,
    Writer,
)
from rosbags.typesys import Stores, get_types_from_msg, get_typestore
from ruamel.yaml import YAML


PIPELINE_TOPICS = {
    "velodyne_xsens": ("/velodyne_points", "/imu/data", "/gt_poses"),
    "livox_bmi088": ("/livox/lidar", "/livox/imu", "/gt_poses"),
}

LIVOX2_CUSTOM_POINT_TYPE = "livox_ros_driver2/msg/CustomPoint"
LIVOX2_CUSTOM_MSG_TYPE = "livox_ros_driver2/msg/CustomMsg"
LIVOX2_CUSTOM_POINT_DEFINITION = """uint32 offset_time
float32 x
float32 y
float32 z
uint8 reflectivity
uint8 tag
uint8 line
"""
LIVOX2_CUSTOM_MSG_DEFINITION = """std_msgs/Header header
uint64 timebase
uint32 point_num
uint8 lidar_id
uint8[3] rsvd
CustomPoint[] points
"""


def _register_livox2_types(typestore: Any) -> None:
    """Register the official livox_ros_driver2 message schema in rosbags."""
    types = {}
    types.update(
        get_types_from_msg(
            LIVOX2_CUSTOM_POINT_DEFINITION,
            LIVOX2_CUSTOM_POINT_TYPE,
        )
    )
    types.update(
        get_types_from_msg(
            LIVOX2_CUSTOM_MSG_DEFINITION,
            LIVOX2_CUSTOM_MSG_TYPE,
        )
    )
    typestore.register(types)


def _convert_livox_custom_message(message: Any, typestore: Any) -> Any:
    """Map a ROS 1 livox_ros_driver CustomMsg to the ROS 2 driver2 namespace."""
    point_class = typestore.types[LIVOX2_CUSTOM_POINT_TYPE]
    message_class = typestore.types[LIVOX2_CUSTOM_MSG_TYPE]
    header_class = typestore.types["std_msgs/msg/Header"]
    time_class = typestore.types["builtin_interfaces/msg/Time"]
    stamp = message.header.stamp
    header = header_class(
        stamp=time_class(sec=int(stamp.sec), nanosec=int(stamp.nanosec)),
        frame_id=str(message.header.frame_id),
    )
    points = [
        point_class(
            offset_time=int(point.offset_time),
            x=float(point.x),
            y=float(point.y),
            z=float(point.z),
            reflectivity=int(point.reflectivity),
            tag=int(point.tag),
            line=int(point.line),
        )
        for point in message.points
    ]
    return message_class(
        header=header,
        timebase=int(message.timebase),
        point_num=int(message.point_num),
        lidar_id=int(message.lidar_id),
        rsvd=np.asarray(message.rsvd, dtype=np.uint8),
        points=points,
    )


def load_config(path: Path) -> dict[str, Any]:
    """Load the normalized project configuration."""
    data = YAML(typ="safe").load(path.read_text(encoding="utf-8"))
    if data.get("dataset") != "botanicgarden":
        raise ValueError(f"Unexpected dataset in {path}: {data.get('dataset')!r}")
    return data


def bag_start_time(path: Path) -> int:
    """Return the first bag timestamp in nanoseconds."""
    with Rosbag1Reader(path) as reader:
        return reader.start_time


def inspect_bags(paths: list[Path]) -> dict[str, Any]:
    """Return lightweight structural metadata for ROS 1 bags."""
    result: dict[str, Any] = {"bags": []}
    for path in paths:
        with Rosbag1Reader(path) as reader:
            result["bags"].append(
                {
                    "path": str(path.resolve()),
                    "size_bytes": path.stat().st_size,
                    "start_timestamp_ns": reader.start_time,
                    "end_timestamp_ns": reader.end_time,
                    "duration_s": reader.duration / 1_000_000_000,
                    "messages": reader.message_count,
                    "topics": [
                        {
                            "name": connection.topic,
                            "type": connection.msgtype,
                            "messages": connection.msgcount,
                        }
                        for connection in reader.connections
                    ],
                }
            )
    return result


def _scale_livox_acceleration(message: Any, factor: float) -> None:
    acceleration = message.linear_acceleration
    acceleration.x *= factor
    acceleration.y *= factor
    acceleration.z *= factor


def _normalize_velodyne_point_times(message: Any) -> dict[str, float | int]:
    """Make PointCloud2 time offsets start at zero and shift its header stamp."""
    time_fields = [field for field in message.fields if field.name == "time"]
    if len(time_fields) != 1:
        raise ValueError("Expected exactly one PointCloud2 field named 'time'")
    time_field = time_fields[0]
    if time_field.datatype != 7 or time_field.count != 1:
        raise ValueError("PointCloud2 field 'time' must be a scalar FLOAT32")
    if message.point_step < time_field.offset + 4:
        raise ValueError("PointCloud2 point_step is inconsistent with field 'time'")

    byte_order = ">" if message.is_bigendian else "<"
    data = np.array(message.data, dtype=np.uint8, copy=True)
    rows: list[np.ndarray[Any, np.dtype[np.float32]]] = []
    for row in range(message.height):
        rows.append(
            np.ndarray(
                shape=(message.width,),
                dtype=f"{byte_order}f4",
                buffer=data,
                offset=row * message.row_step + time_field.offset,
                strides=(message.point_step,),
            )
        )
    if not rows or not message.width:
        raise ValueError("Cannot normalize an empty PointCloud2")

    minimum = min(float(np.min(row)) for row in rows)
    maximum = max(float(np.max(row)) for row in rows)
    if not np.isfinite(minimum) or not np.isfinite(maximum):
        raise ValueError("PointCloud2 field 'time' contains non-finite values")
    for row in rows:
        row -= minimum
    message.data = data

    original_stamp_ns = (
        int(message.header.stamp.sec) * 1_000_000_000
        + int(message.header.stamp.nanosec)
    )
    shifted_stamp_ns = original_stamp_ns + round(minimum * 1_000_000_000)
    message.header.stamp.sec = shifted_stamp_ns // 1_000_000_000
    message.header.stamp.nanosec = shifted_stamp_ns % 1_000_000_000
    return {
        "points": int(message.width * message.height),
        "original_min_s": minimum,
        "original_max_s": maximum,
        "normalized_span_s": maximum - minimum,
        "header_shift_s": minimum,
    }


def _normalize_metadata_for_humble(path: Path) -> None:
    """Downgrade rosbag2 metadata fields to the format parsed by Humble."""
    yaml = YAML()
    data = yaml.load(path)
    information = data["rosbag2_bagfile_information"]
    information["version"] = 5
    information.pop("custom_data", None)
    information.pop("ros_distro", None)
    for item in information["topics_with_message_count"]:
        metadata = item["topic_metadata"]
        metadata["offered_qos_profiles"] = ""
        metadata.pop("type_description_hash", None)
    with path.open("w", encoding="utf-8") as stream:
        yaml.dump(data, stream)


def prepare_smoke_bag(
    *,
    lio_bag: Path,
    ground_truth_bag: Path,
    output: Path,
    pipeline: str,
    start_offset_s: float,
    duration_s: float,
    livox_accel_mode: str,
    velodyne_time_mode: str,
    config_path: Path,
) -> dict[str, Any]:
    """Create a time-bounded ROS 2 MCAP without changing source bags."""
    if output.exists():
        raise FileExistsError(f"Output already exists and will not be overwritten: {output}")
    if start_offset_s < 0 or duration_s <= 0:
        raise ValueError("start offset must be >= 0 and duration must be > 0")

    config = load_config(config_path)
    topics = set(PIPELINE_TOPICS[pipeline])
    start_ns = bag_start_time(lio_bag) + round(start_offset_s * 1_000_000_000)
    stop_ns = start_ns + round(duration_s * 1_000_000_000)
    scale_factor = 1.0
    if pipeline == "livox_bmi088" and livox_accel_mode == "si":
        scale_factor = float(
            config["pipelines"]["livox_bmi088"]["acceleration"]["raw_to_m_s2_factor"]
        )

    output.parent.mkdir(parents=True, exist_ok=True)
    writer = Writer(output, version=9, storage_plugin=StoragePlugin.MCAP)
    writer.set_compression(CompressionMode.STORAGE, CompressionFormat.ZSTD)

    counts: Counter[str] = Counter()
    first_timestamp: dict[str, int] = {}
    last_timestamp: dict[str, int] = {}
    velodyne_time_stats: list[dict[str, float | int]] = []
    try:
        with AnyReader([lio_bag, ground_truth_bag]) as reader:
            source_connections = [
                connection for connection in reader.connections if connection.topic in topics
            ]
            found_topics = {connection.topic for connection in source_connections}
            missing_topics = topics - found_topics
            if missing_topics:
                raise RuntimeError(f"Missing topics: {sorted(missing_topics)}")

            ros2_typestore = get_typestore(Stores.ROS2_HUMBLE)
            writer.open()
            converter_sources = source_connections
            if pipeline == "livox_bmi088":
                _register_livox2_types(ros2_typestore)
                converter_sources = [
                    connection
                    for connection in source_connections
                    if connection.topic != "/livox/lidar"
                ]
            destination_connections, converters = create_connections_converters(
                converter_sources,
                ros2_typestore,
                reader,
                writer,
            )
            if pipeline == "livox_bmi088":
                for connection in source_connections:
                    if connection.topic == "/livox/lidar":
                        destination_connections[(connection.id, connection.owner)] = (
                            writer.add_connection(
                                connection.topic,
                                LIVOX2_CUSTOM_MSG_TYPE,
                                typestore=ros2_typestore,
                            )
                        )

            for connection, timestamp, rawdata in reader.messages(
                connections=source_connections,
                start=start_ns,
                stop=stop_ns,
            ):
                destination_connection = destination_connections[
                    (connection.id, connection.owner)
                ]
                if connection.topic == "/livox/lidar":
                    source_message = reader.deserialize(rawdata, connection.msgtype)
                    message = _convert_livox_custom_message(
                        source_message,
                        ros2_typestore,
                    )
                    cdr = ros2_typestore.serialize_cdr(
                        message,
                        LIVOX2_CUSTOM_MSG_TYPE,
                    )
                else:
                    cdr = converters[connection.msgtype](rawdata)
                needs_message_edit = (
                    connection.topic == "/livox/imu" and scale_factor != 1.0
                ) or (
                    connection.topic == "/velodyne_points"
                    and velodyne_time_mode == "start-relative"
                )
                if needs_message_edit:
                    message = ros2_typestore.deserialize_cdr(
                        cdr,
                        destination_connection.msgtype,
                    )
                    if connection.topic == "/livox/imu" and scale_factor != 1.0:
                        _scale_livox_acceleration(message, scale_factor)
                    if connection.topic == "/velodyne_points":
                        velodyne_time_stats.append(
                            _normalize_velodyne_point_times(message)
                        )
                    cdr = ros2_typestore.serialize_cdr(
                        message,
                        destination_connection.msgtype,
                    )
                writer.write(
                    destination_connection,
                    timestamp,
                    cdr,
                )
                counts[connection.topic] += 1
                first_timestamp.setdefault(connection.topic, timestamp)
                last_timestamp[connection.topic] = timestamp
    except Exception:
        if output.exists():
            shutil.rmtree(output)
        raise
    finally:
        if writer.storage:
            writer.close()

    _normalize_metadata_for_humble(output / "metadata.yaml")

    manifest = {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "dataset": "botanicgarden",
        "sequence": config["sequence"],
        "pipeline": pipeline,
        "source_lio_bag": str(lio_bag.resolve()),
        "source_ground_truth_bag": str(ground_truth_bag.resolve()),
        "output": str(output.resolve()),
        "format": "rosbag2_mcap_zstd",
        "rosbag2_metadata_version": 5,
        "target_ros_distro": "humble",
        "requested_start_offset_s": start_offset_s,
        "requested_duration_s": duration_s,
        "start_timestamp_ns": start_ns,
        "stop_timestamp_ns": stop_ns,
        "livox_accel_mode": livox_accel_mode,
        "livox_accel_scale_factor": scale_factor,
        "livox_message_conversion": {
            "source_type": (
                "livox_ros_driver/msg/CustomMsg"
                if pipeline == "livox_bmi088"
                else None
            ),
            "target_type": (
                LIVOX2_CUSTOM_MSG_TYPE if pipeline == "livox_bmi088" else None
            ),
            "messages": counts["/livox/lidar"],
        },
        "velodyne_time_mode": velodyne_time_mode,
        "velodyne_time_normalization": {
            "scans": len(velodyne_time_stats),
            "minimum_original_offset_s": min(
                (float(item["original_min_s"]) for item in velodyne_time_stats),
                default=None,
            ),
            "maximum_original_offset_s": max(
                (float(item["original_max_s"]) for item in velodyne_time_stats),
                default=None,
            ),
            "maximum_normalized_span_s": max(
                (float(item["normalized_span_s"]) for item in velodyne_time_stats),
                default=None,
            ),
        },
        "topics": {
            topic: {
                "messages": counts[topic],
                "first_timestamp_ns": first_timestamp.get(topic),
                "last_timestamp_ns": last_timestamp.get(topic),
            }
            for topic in sorted(topics)
        },
    }
    (output / "adapter_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return manifest


def export_tum(ground_truth_bag: Path, output: Path) -> dict[str, Any]:
    """Export `/gt_poses` as TUM trajectory text."""
    if output.exists():
        raise FileExistsError(f"Output already exists and will not be overwritten: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with AnyReader([ground_truth_bag]) as reader, output.open("w", encoding="utf-8") as stream:
        connections = [connection for connection in reader.connections if connection.topic == "/gt_poses"]
        if not connections:
            raise RuntimeError("Topic /gt_poses not found")
        stream.write("# timestamp tx ty tz qx qy qz qw\n")
        for connection, timestamp, rawdata in reader.messages(connections=connections):
            message = reader.deserialize(rawdata, connection.msgtype)
            position = message.pose.position
            orientation = message.pose.orientation
            stream.write(
                f"{timestamp / 1_000_000_000:.9f} "
                f"{position.x:.9f} {position.y:.9f} {position.z:.9f} "
                f"{orientation.x:.9f} {orientation.y:.9f} "
                f"{orientation.z:.9f} {orientation.w:.9f}\n"
            )
            count += 1
    return {"output": str(output.resolve()), "poses": count}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect_parser = subparsers.add_parser("inspect", help="inspect source bags")
    inspect_parser.add_argument("bags", nargs="+", type=Path)

    prepare_parser = subparsers.add_parser("prepare", help="create a bounded ROS 2 MCAP")
    prepare_parser.add_argument("--lio-bag", required=True, type=Path)
    prepare_parser.add_argument("--ground-truth-bag", required=True, type=Path)
    prepare_parser.add_argument("--output", required=True, type=Path)
    prepare_parser.add_argument("--pipeline", choices=sorted(PIPELINE_TOPICS), required=True)
    prepare_parser.add_argument("--start-offset-s", type=float, default=20.0)
    prepare_parser.add_argument("--duration-s", type=float, default=10.0)
    prepare_parser.add_argument("--livox-accel-mode", choices=("raw", "si"), default="raw")
    prepare_parser.add_argument(
        "--velodyne-time-mode",
        choices=("preserve", "start-relative"),
        default="preserve",
        help="normalize VLP-16 per-point seconds for FAST-LIO2 when requested",
    )
    prepare_parser.add_argument(
        "--config",
        type=Path,
        default=Path("/workspace/configs/datasets/botanicgarden/1006-03.yaml"),
    )

    tum_parser = subparsers.add_parser("export-tum", help="export ground truth in TUM format")
    tum_parser.add_argument("--ground-truth-bag", required=True, type=Path)
    tum_parser.add_argument("--output", required=True, type=Path)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    try:
        if args.command == "inspect":
            result = inspect_bags(args.bags)
        elif args.command == "prepare":
            result = prepare_smoke_bag(
                lio_bag=args.lio_bag,
                ground_truth_bag=args.ground_truth_bag,
                output=args.output,
                pipeline=args.pipeline,
                start_offset_s=args.start_offset_s,
                duration_s=args.duration_s,
                livox_accel_mode=args.livox_accel_mode,
                velodyne_time_mode=args.velodyne_time_mode,
                config_path=args.config,
            )
        else:
            result = export_tum(args.ground_truth_bag, args.output)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
