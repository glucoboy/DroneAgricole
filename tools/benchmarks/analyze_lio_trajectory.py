#!/usr/bin/env python3
"""Measure aligned ATE, orientation error and fixed-time RPE for a LIO run."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from rosbags.highlevel import AnyReader


DEFAULT_ESTIMATE_TOPIC = "/Odometry"
DEFAULT_GROUND_TRUTH_TOPIC = "/gt_poses"
DEFAULT_PIPELINE_TOPIC = "/fast_lio2/pipeline_counters"


def stamp_seconds(message: object) -> float:
    stamp = message.header.stamp
    return float(stamp.sec) + float(stamp.nanosec) / 1_000_000_000.0


def _quaternion_xyzw(orientation: object) -> list[float]:
    return [orientation.x, orientation.y, orientation.z, orientation.w]


def read_poses(
    bag: Path,
    estimate_topic: str,
    ground_truth_topic: str,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    estimate_times: list[float] = []
    estimate_positions: list[list[float]] = []
    estimate_quaternions: list[list[float]] = []
    truth_times: list[float] = []
    truth_positions: list[list[float]] = []
    truth_quaternions: list[list[float]] = []

    with AnyReader([bag]) as reader:
        connections = [
            connection
            for connection in reader.connections
            if connection.topic in {estimate_topic, ground_truth_topic}
        ]
        for connection, _, rawdata in reader.messages(connections=connections):
            message = reader.deserialize(rawdata, connection.msgtype)
            if connection.topic == estimate_topic:
                pose = message.pose.pose
                estimate_times.append(stamp_seconds(message))
                estimate_positions.append([pose.position.x, pose.position.y, pose.position.z])
                estimate_quaternions.append(_quaternion_xyzw(pose.orientation))
            else:
                pose = message.pose
                truth_times.append(stamp_seconds(message))
                truth_positions.append([pose.position.x, pose.position.y, pose.position.z])
                truth_quaternions.append(_quaternion_xyzw(pose.orientation))

    return (
        np.asarray(estimate_times, dtype=np.float64),
        np.asarray(estimate_positions, dtype=np.float64),
        np.asarray(estimate_quaternions, dtype=np.float64),
        np.asarray(truth_times, dtype=np.float64),
        np.asarray(truth_positions, dtype=np.float64),
        np.asarray(truth_quaternions, dtype=np.float64),
    )


def read_pipeline_counters(
    bag: Path,
    pipeline_topic: str = DEFAULT_PIPELINE_TOPIC,
) -> dict[str, int] | None:
    """Return the last valid LIO pipeline snapshot recorded in the bag."""
    latest: dict[str, int] | None = None
    with AnyReader([bag]) as reader:
        connections = [
            connection
            for connection in reader.connections
            if connection.topic == pipeline_topic
        ]
        # rosbags interprets an empty connection sequence as "all connections".
        # An absent diagnostic topic must therefore be handled before iteration.
        if not connections:
            return None
        for connection, _, rawdata in reader.messages(connections=connections):
            message = reader.deserialize(rawdata, connection.msgtype)
            try:
                payload = json.loads(message.data)
            except (json.JSONDecodeError, TypeError):
                continue
            if payload.get("schema_version") != 1:
                continue
            latest = {
                key: int(value)
                for key, value in payload.items()
                if key != "schema_version" and isinstance(value, (int, float))
            }
            latest["schema_version"] = 1
    return latest


def pipeline_accounting(counters: dict[str, int] | None) -> dict[str, object] | None:
    if counters is None:
        return None
    received = int(counters.get("scans_received", 0))
    preprocessed = int(counters.get("scans_preprocessed", 0))
    synchronized = int(counters.get("scans_synchronized", 0))
    odometry = int(counters.get("odometry_published", 0))
    accounted = sum(
        int(counters.get(key, 0))
        for key in (
            "scans_initialization",
            "scans_rejected_undistort_empty",
            "scans_map_initialization",
            "scans_rejected_downsample",
            "state_updates",
        )
    )
    return {
        "received_minus_preprocessed": received - preprocessed,
        "preprocessed_minus_synchronized": preprocessed - synchronized,
        "accounted_synchronized_scans": accounted,
        "unaccounted_synchronized_scans": synchronized - accounted,
        "state_updates_minus_odometry": int(counters.get("state_updates", 0)) - odometry,
        "ratios_percent": {
            "synchronized_over_received": (
                100.0 * synchronized / received if received else None
            ),
            "odometry_over_received": 100.0 * odometry / received if received else None,
            "odometry_over_synchronized": (
                100.0 * odometry / synchronized if synchronized else None
            ),
        },
    }


def _nearest_index(times: np.ndarray, timestamp: float) -> int:
    insertion = int(np.searchsorted(times, timestamp))
    candidates = [index for index in (insertion - 1, insertion) if 0 <= index < len(times)]
    return min(candidates, key=lambda index: abs(float(times[index] - timestamp)))


def associate_nearest(
    estimate_times: np.ndarray,
    estimate_positions: np.ndarray,
    estimate_quaternions: np.ndarray,
    truth_times: np.ndarray,
    truth_positions: np.ndarray,
    truth_quaternions: np.ndarray,
    max_delta_s: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    matched_times: list[float] = []
    matched_estimate_positions: list[np.ndarray] = []
    matched_estimate_quaternions: list[np.ndarray] = []
    matched_truth_positions: list[np.ndarray] = []
    matched_truth_quaternions: list[np.ndarray] = []
    matched_truth_times: list[float] = []
    deltas: list[float] = []
    for timestamp, position, quaternion in zip(
        estimate_times,
        estimate_positions,
        estimate_quaternions,
        strict=True,
    ):
        index = _nearest_index(truth_times, float(timestamp))
        delta = abs(float(truth_times[index] - timestamp))
        if delta <= max_delta_s:
            matched_times.append(float(timestamp))
            matched_estimate_positions.append(position)
            matched_estimate_quaternions.append(quaternion)
            matched_truth_positions.append(truth_positions[index])
            matched_truth_quaternions.append(truth_quaternions[index])
            matched_truth_times.append(float(truth_times[index]))
            deltas.append(delta)
    return (
        np.asarray(matched_times, dtype=np.float64),
        np.asarray(matched_estimate_positions, dtype=np.float64),
        np.asarray(matched_estimate_quaternions, dtype=np.float64),
        np.asarray(matched_truth_times, dtype=np.float64),
        np.asarray(matched_truth_positions, dtype=np.float64),
        np.asarray(matched_truth_quaternions, dtype=np.float64),
        np.asarray(deltas, dtype=np.float64),
    )


def normalize_quaternions(quaternions: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(quaternions, axis=1)
    if np.any(norms < 1e-12):
        raise RuntimeError("Trajectory contains a zero-norm quaternion")
    return quaternions / norms[:, np.newaxis]


def quaternions_to_matrices(quaternions: np.ndarray) -> np.ndarray:
    normalized = normalize_quaternions(quaternions)
    x, y, z, w = normalized.T
    matrices = np.empty((len(normalized), 3, 3), dtype=np.float64)
    matrices[:, 0, 0] = 1.0 - 2.0 * (y * y + z * z)
    matrices[:, 0, 1] = 2.0 * (x * y - z * w)
    matrices[:, 0, 2] = 2.0 * (x * z + y * w)
    matrices[:, 1, 0] = 2.0 * (x * y + z * w)
    matrices[:, 1, 1] = 1.0 - 2.0 * (x * x + z * z)
    matrices[:, 1, 2] = 2.0 * (y * z - x * w)
    matrices[:, 2, 0] = 2.0 * (x * z - y * w)
    matrices[:, 2, 1] = 2.0 * (y * z + x * w)
    matrices[:, 2, 2] = 1.0 - 2.0 * (x * x + y * y)
    return matrices


def align_se3(source: np.ndarray, target: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    source_center = np.mean(source, axis=0)
    target_center = np.mean(target, axis=0)
    covariance = (source - source_center).T @ (target - target_center)
    left, _, right_transpose = np.linalg.svd(covariance)
    rotation = right_transpose.T @ left.T
    if np.linalg.det(rotation) < 0:
        right_transpose[-1, :] *= -1
        rotation = right_transpose.T @ left.T
    translation = target_center - rotation @ source_center
    aligned = (rotation @ source.T).T + translation
    return aligned, rotation, translation


def rotation_angles_deg(reference: np.ndarray, estimate: np.ndarray) -> np.ndarray:
    relative = np.einsum("nji,njk->nik", reference, estimate)
    cosines = np.clip((np.trace(relative, axis1=1, axis2=2) - 1.0) / 2.0, -1.0, 1.0)
    return np.degrees(np.arccos(cosines))


def path_length(positions: np.ndarray) -> float:
    if len(positions) < 2:
        return 0.0
    return float(np.sum(np.linalg.norm(np.diff(positions, axis=0), axis=1)))


def error_stats(values: np.ndarray) -> dict[str, float]:
    return {
        "rmse": float(np.sqrt(np.mean(values**2))),
        "mean": float(np.mean(values)),
        "median": float(np.median(values)),
        "maximum": float(np.max(values)),
    }


def compute_rpe(
    times: np.ndarray,
    estimate_positions: np.ndarray,
    estimate_rotations: np.ndarray,
    truth_positions: np.ndarray,
    truth_rotations: np.ndarray,
    delta_s: float,
    delta_tolerance_s: float,
) -> dict[str, object]:
    translation_errors: list[float] = []
    rotation_errors: list[float] = []
    observed_deltas: list[float] = []
    for first in range(len(times) - 1):
        target = float(times[first] + delta_s)
        insertion = int(np.searchsorted(times, target))
        candidates = [
            index
            for index in (insertion - 1, insertion)
            if first < index < len(times)
        ]
        if not candidates:
            continue
        second = min(candidates, key=lambda index: abs(float(times[index] - target)))
        observed_delta = float(times[second] - times[first])
        if abs(observed_delta - delta_s) > delta_tolerance_s:
            continue

        estimate_relative_rotation = estimate_rotations[first].T @ estimate_rotations[second]
        truth_relative_rotation = truth_rotations[first].T @ truth_rotations[second]
        estimate_relative_translation = estimate_rotations[first].T @ (
            estimate_positions[second] - estimate_positions[first]
        )
        truth_relative_translation = truth_rotations[first].T @ (
            truth_positions[second] - truth_positions[first]
        )
        translation_errors.append(
            float(np.linalg.norm(estimate_relative_translation - truth_relative_translation))
        )
        rotation_errors.append(
            float(
                rotation_angles_deg(
                    truth_relative_rotation[np.newaxis, :, :],
                    estimate_relative_rotation[np.newaxis, :, :],
                )[0]
            )
        )
        observed_deltas.append(observed_delta)

    if not translation_errors:
        raise RuntimeError("No valid pose pairs were found for the requested RPE interval")
    translation_array = np.asarray(translation_errors, dtype=np.float64)
    rotation_array = np.asarray(rotation_errors, dtype=np.float64)
    delta_array = np.asarray(observed_deltas, dtype=np.float64)
    return {
        "delta_s": delta_s,
        "delta_tolerance_s": delta_tolerance_s,
        "pairs": int(len(delta_array)),
        "observed_delta_s": {
            "minimum": float(np.min(delta_array)),
            "mean": float(np.mean(delta_array)),
            "maximum": float(np.max(delta_array)),
        },
        "translation_m": error_stats(translation_array),
        "rotation_deg": error_stats(rotation_array),
    }


def analyze(
    bag: Path,
    max_delta_s: float,
    rpe_delta_s: float,
    rpe_delta_tolerance_s: float,
    estimate_topic: str = DEFAULT_ESTIMATE_TOPIC,
    ground_truth_topic: str = DEFAULT_GROUND_TRUTH_TOPIC,
    pipeline_topic: str = DEFAULT_PIPELINE_TOPIC,
) -> dict[str, object]:
    (
        estimate_times,
        estimate_positions,
        estimate_quaternions,
        truth_times,
        truth_positions,
        truth_quaternions,
    ) = read_poses(bag, estimate_topic, ground_truth_topic)
    if len(estimate_positions) < 3:
        raise RuntimeError("At least three odometry poses are required")
    if len(truth_positions) < 3:
        raise RuntimeError("At least three ground-truth poses are required")

    (
        matched_times,
        matched_estimate_positions,
        matched_estimate_quaternions,
        matched_truth_times,
        matched_truth_positions,
        matched_truth_quaternions,
        deltas,
    ) = associate_nearest(
        estimate_times,
        estimate_positions,
        estimate_quaternions,
        truth_times,
        truth_positions,
        truth_quaternions,
        max_delta_s,
    )
    if len(matched_estimate_positions) < 3:
        raise RuntimeError("Fewer than three poses matched by timestamp")

    aligned_positions, alignment_rotation, translation = align_se3(
        matched_estimate_positions,
        matched_truth_positions,
    )
    estimate_rotations = quaternions_to_matrices(matched_estimate_quaternions)
    truth_rotations = quaternions_to_matrices(matched_truth_quaternions)
    aligned_estimate_rotations = np.einsum(
        "ij,njk->nik",
        alignment_rotation,
        estimate_rotations,
    )
    translation_errors = np.linalg.norm(aligned_positions - matched_truth_positions, axis=1)
    orientation_errors = rotation_angles_deg(truth_rotations, aligned_estimate_rotations)
    estimate_length = path_length(matched_estimate_positions)
    truth_length = path_length(matched_truth_positions)
    finite = bool(
        np.all(np.isfinite(estimate_positions))
        and np.all(np.isfinite(truth_positions))
        and np.all(np.isfinite(translation_errors))
        and np.all(np.isfinite(orientation_errors))
    )
    pipeline_counters = read_pipeline_counters(bag, pipeline_topic)
    return {
        "schema_version": 3,
        "bag": str(bag.resolve()),
        "topics": {
            "estimate": estimate_topic,
            "ground_truth": ground_truth_topic,
            "pipeline_counters": pipeline_topic,
        },
        "estimate_poses": int(len(estimate_positions)),
        "ground_truth_poses": int(len(truth_positions)),
        "matched_poses": int(len(matched_estimate_positions)),
        "max_association_delta_s": max_delta_s,
        "observed_max_association_delta_s": float(np.max(deltas)),
        "estimate_header_duration_s": float(estimate_times[-1] - estimate_times[0]),
        "matched_ground_truth_duration_s": float(
            matched_truth_times[-1] - matched_truth_times[0]
        ),
        "finite_values": finite,
        "pipeline_counters": pipeline_counters,
        "pipeline_accounting": pipeline_accounting(pipeline_counters),
        "alignment": {
            "mode": "SE3_position_only_no_scale",
            "rotation_row_major": alignment_rotation.tolist(),
            "translation_m": translation.tolist(),
        },
        "ate_translation_m": error_stats(translation_errors),
        "ate_orientation_deg": error_stats(orientation_errors),
        "rpe": compute_rpe(
            matched_times,
            matched_estimate_positions,
            estimate_rotations,
            matched_truth_positions,
            truth_rotations,
            rpe_delta_s,
            rpe_delta_tolerance_s,
        ),
        "matched_path_length_m": {
            "estimate": estimate_length,
            "ground_truth": truth_length,
            "ratio_estimate_over_ground_truth": (
                estimate_length / truth_length if truth_length else None
            ),
        },
        "matched_endpoint_displacement_m": {
            "estimate": float(
                np.linalg.norm(matched_estimate_positions[-1] - matched_estimate_positions[0])
            ),
            "ground_truth": float(
                np.linalg.norm(matched_truth_positions[-1] - matched_truth_positions[0])
            ),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bag", type=Path)
    parser.add_argument("--max-delta-s", type=float, default=0.06)
    parser.add_argument("--rpe-delta-s", type=float, default=1.0)
    parser.add_argument("--rpe-delta-tolerance-s", type=float, default=0.06)
    parser.add_argument("--estimate-topic", default=DEFAULT_ESTIMATE_TOPIC)
    parser.add_argument("--ground-truth-topic", default=DEFAULT_GROUND_TRUTH_TOPIC)
    parser.add_argument("--pipeline-topic", default=DEFAULT_PIPELINE_TOPIC)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    result = analyze(
        args.bag,
        args.max_delta_s,
        args.rpe_delta_s,
        args.rpe_delta_tolerance_s,
        args.estimate_topic,
        args.ground_truth_topic,
        args.pipeline_topic,
    )
    rendered = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")


if __name__ == "__main__":
    main()
