"""Index reconstruisible et rechargement hors ligne des résultats T0."""

from __future__ import annotations

from collections import Counter
from datetime import date, datetime, time, timedelta, timezone
import hashlib
import json
import math
from pathlib import Path
import threading
import time as wall_time
from typing import Any, Iterable, Mapping

from software.visualization.contracts import (
    ContractError,
    validate_artifacts,
    validate_event,
    validate_metrics,
    validate_run_manifest,
)
from software.visualization.result_adapters import NormalizedResult, normalize_result_directory


class ResultHistoryError(ValueError):
    """Erreur publique et sans fuite de chemin de l'historique."""


def _read_json(path: Path, *, required: bool = True) -> Mapping[str, Any] | None:
    if not path.is_file():
        if required:
            raise ContractError(f"fichier absent : {path.name}")
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractError(f"JSON illisible : {path.name}: {exc}") from exc
    if not isinstance(value, Mapping):
        raise ContractError(f"objet JSON attendu : {path.name}")
    return value


def _read_events(path: Path) -> tuple[Mapping[str, Any], ...]:
    if not path.is_file():
        return ()
    events: list[Mapping[str, Any]] = []
    try:
        for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if not raw_line.strip():
                continue
            value = json.loads(raw_line)
            if not isinstance(value, Mapping):
                raise ContractError(f"événement non objet à la ligne {line_number}")
            validate_event(value)
            events.append(value)
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractError(f"événements illisibles : {exc}") from exc
    return tuple(events)


def _load_native(directory: Path) -> NormalizedResult:
    manifest = _read_json(directory / "t0_run_manifest.json") or {}
    metrics = _read_json(directory / "t0_metrics.json") or {}
    artifacts = _read_json(directory / "artifacts.json") or {}
    events = _read_events(directory / "events.jsonl")
    validate_run_manifest(manifest)
    validate_metrics(metrics)
    validate_artifacts(artifacts)
    return NormalizedResult("t0_native", directory, manifest, metrics, artifacts, events)


def _load_result(directory: Path) -> NormalizedResult:
    if (directory / "t0_run_manifest.json").is_file():
        return _load_native(directory)
    return normalize_result_directory(directory)


def _timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _filter_boundary(value: str | None, *, end: bool) -> datetime | None:
    if not value:
        return None
    try:
        if "T" in value:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        parsed_date = date.fromisoformat(value)
    except ValueError as exc:
        raise ResultHistoryError(f"Date de filtre invalide : {value}") from exc
    boundary = datetime.combine(parsed_date, time.min, tzinfo=timezone.utc)
    return boundary + timedelta(days=1) if end else boundary


def _dataset_reference(manifest: Mapping[str, Any]) -> tuple[str | None, str | None]:
    for value in manifest.get("inputs", []):
        if not isinstance(value, Mapping) or value.get("kind") != "dataset_sequence":
            continue
        reference = value.get("reference")
        if isinstance(reference, Mapping):
            return _optional_text(reference.get("dataset_id")), _optional_text(reference.get("sequence_id"))
    return None, None


def _optional_text(value: Any) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text or None


def _request(directory: Path) -> Mapping[str, Any]:
    return (
        _read_json(directory / "run_request.json", required=False)
        or _read_json(directory / "dashboard_request.json", required=False)
        or {}
    )


def _tags(directory: Path, source_kind: str, manifest: Mapping[str, Any]) -> list[str]:
    request = _request(directory)
    values = request.get("tags", []) if isinstance(request.get("tags"), list) else []
    metadata = manifest.get("metadata") if isinstance(manifest.get("metadata"), Mapping) else {}
    if isinstance(metadata.get("tags"), list):
        values = [*values, *metadata["tags"]]
    values.extend(["native" if source_kind == "t0_native" else "historique", str(manifest.get("domain", ""))])
    return sorted({str(value).strip().lower() for value in values if str(value).strip()})


def _result_id(relative_directory: str) -> str:
    return hashlib.sha256(relative_directory.encode("utf-8")).hexdigest()[:20]


def _metric_preview(metrics: Mapping[str, Any], maximum: int = 5) -> list[Mapping[str, Any]]:
    summary = metrics.get("summary")
    if not isinstance(summary, list):
        return []
    return [value for value in summary if isinstance(value, Mapping)][:maximum]


def _duplicate_request(directory: Path, manifest: Mapping[str, Any]) -> dict[str, Any] | None:
    request = _request(directory)
    if not request or not isinstance(request.get("parameters"), Mapping):
        return None
    simulation_id = _optional_text(manifest.get("simulation_id"))
    variant_id = _optional_text(manifest.get("variant_id"))
    if not simulation_id or not variant_id:
        return None
    inputs = request.get("inputs") if isinstance(request.get("inputs"), list) else manifest.get("inputs", [])
    parameters = request.get("parameters") if isinstance(request.get("parameters"), Mapping) else manifest.get("parameters", {})
    payload = {
        "simulation_id": simulation_id,
        "variant_id": variant_id,
        "profile_id": request.get("profile_id"),
        "inputs": inputs if isinstance(inputs, list) else [],
        "parameters": dict(parameters) if isinstance(parameters, Mapping) else {},
    }
    if simulation_id == "lio_benchmark":
        dataset_id, sequence_id = _dataset_reference({"inputs": payload["inputs"]})
        if not dataset_id or not sequence_id or dataset_id.startswith("unknown_") or sequence_id.startswith("unknown_"):
            return None
    return payload


def _public_summary(directory: Path, results_root: Path, normalized: NormalizedResult) -> dict[str, Any]:
    manifest = normalized.manifest
    relative = directory.relative_to(results_root).as_posix()
    dataset_id, sequence_id = _dataset_reference(manifest)
    domain = str(manifest["domain"])
    variant_id = str(manifest["variant_id"])
    created_at = (
        manifest.get("started_at_utc")
        or manifest.get("created_at_utc")
        or datetime.fromtimestamp(directory.stat().st_mtime, timezone.utc).isoformat()
    )
    duplicate = _duplicate_request(directory, manifest)
    return {
        "result_id": _result_id(relative),
        "run_id": manifest["run_id"],
        "relative_directory": relative,
        "source_kind": normalized.source_kind,
        "simulation_id": manifest["simulation_id"],
        "variant_id": variant_id,
        "runner_id": manifest["runner_id"],
        "domain": domain,
        "state": manifest["state"],
        "created_at_utc": created_at,
        "finished_at_utc": manifest.get("finished_at_utc"),
        "dataset_id": dataset_id,
        "sequence_id": sequence_id,
        "algorithm_id": variant_id if domain == "localization" else None,
        "scenario_id": variant_id if domain != "localization" else None,
        "comparison_group": manifest.get("compatibility", {}).get("comparison_group"),
        "tags": _tags(directory, normalized.source_kind, manifest),
        "metric_preview": _metric_preview(normalized.metrics),
        "metrics_status": normalized.metrics.get("status"),
        "event_count": len(normalized.events),
        "artifact_count": len(normalized.artifacts.get("items", [])),
        "replay_available": _replay_available(directory, normalized),
        "duplicate_available": duplicate is not None,
    }


def _replay_available(directory: Path, normalized: NormalizedResult) -> bool:
    if normalized.manifest.get("domain") == "flight_simulation":
        return bool(normalized.events) or (directory / "result.json").is_file()
    for artifact in normalized.artifacts.get("items", []):
        if not isinstance(artifact, Mapping) or not artifact.get("replayable"):
            continue
        candidate = (directory / str(artifact.get("path", ""))).resolve()
        if candidate.is_relative_to(directory) and candidate.exists() and artifact.get("kind") in {"rosbag", "trajectory"}:
            return True
    return (directory / "estimate").is_dir()


class ResultRepository:
    """Cache mémoire reconstruisible à partir des seuls répertoires de résultats."""

    def __init__(self, workspace: Path | str, results_directory: Path | str | None = None) -> None:
        self.workspace = Path(workspace).resolve()
        self.results_root = Path(results_directory).resolve() if results_directory else (self.workspace / "results").resolve()
        if not self.results_root.is_relative_to(self.workspace):
            raise ValueError("Le dépôt de résultats doit rester dans le workspace.")
        self._lock = threading.RLock()
        self._records: dict[str, tuple[Path, NormalizedResult, dict[str, Any]]] = {}
        self._replay_cache: dict[str, dict[str, Any]] = {}
        self._errors: list[dict[str, str]] = []
        self._indexed_at = ""
        self._refreshed_monotonic = 0.0

    def refresh(self) -> None:
        records: dict[str, tuple[Path, NormalizedResult, dict[str, Any]]] = {}
        errors: list[dict[str, str]] = []
        if self.results_root.is_dir():
            native = {path.parent for path in self.results_root.rglob("t0_run_manifest.json")}
            legacy_lio = {path.parent for path in self.results_root.rglob("run_manifest.json")}
            legacy_px4 = {path.parent for path in self.results_root.rglob("result.json")}
            for directory in sorted(native | legacy_lio | legacy_px4):
                try:
                    resolved = directory.resolve()
                    if not resolved.is_relative_to(self.results_root):
                        continue
                    normalized = _load_result(resolved)
                    summary = _public_summary(resolved, self.results_root, normalized)
                    records[summary["result_id"]] = (resolved, normalized, summary)
                except (ContractError, OSError, ValueError) as exc:
                    errors.append({"directory": directory.relative_to(self.results_root).as_posix(), "error": str(exc)})
        with self._lock:
            self._records = records
            self._replay_cache = {
                result_id: replay
                for result_id, replay in self._replay_cache.items()
                if result_id in records
            }
            self._errors = errors
            self._indexed_at = datetime.now(timezone.utc).isoformat()
            self._refreshed_monotonic = wall_time.monotonic()

    def _ensure_fresh(self, force: bool = False) -> None:
        with self._lock:
            stale = wall_time.monotonic() - self._refreshed_monotonic > 300.0
        if force or stale:
            self.refresh()

    def search(self, filters: Mapping[str, str] | None = None, *, refresh: bool = False) -> dict[str, Any]:
        self._ensure_fresh(force=refresh)
        filters = filters or {}
        date_from = _filter_boundary(filters.get("date_from"), end=False)
        date_to = _filter_boundary(filters.get("date_to"), end=True)
        try:
            limit = min(200, max(1, int(filters.get("limit", "100"))))
            offset = max(0, int(filters.get("offset", "0")))
        except ValueError as exc:
            raise ResultHistoryError("Pagination invalide.") from exc
        with self._lock:
            all_items = [record[2].copy() for record in self._records.values()]
            errors = list(self._errors)
            indexed_at = self._indexed_at
        facets = self._facets(all_items)
        items = [value for value in all_items if self._matches(value, filters, date_from, date_to)]
        items.sort(key=lambda value: (_timestamp(value.get("created_at_utc")) or datetime.min.replace(tzinfo=timezone.utc), value["result_id"]), reverse=True)
        return {
            "schema": "drone_agricole.result_index.v1",
            "indexed_at_utc": indexed_at,
            "total": len(items),
            "offset": offset,
            "limit": limit,
            "items": items[offset : offset + limit],
            "facets": facets,
            "invalid_result_count": len(errors),
            "errors": errors[:20],
        }

    @staticmethod
    def _matches(item: Mapping[str, Any], filters: Mapping[str, str], date_from: datetime | None, date_to: datetime | None) -> bool:
        for name in ("domain", "dataset_id", "state"):
            value = filters.get(name)
            if value and item.get(name) != value:
                return False
        algorithm = filters.get("algorithm_id")
        if algorithm and item.get("algorithm_id") != algorithm:
            return False
        scenario = filters.get("scenario_id")
        if scenario and item.get("scenario_id") != scenario:
            return False
        tag = filters.get("tag", "").strip().lower()
        if tag and not any(tag in value for value in item.get("tags", [])):
            return False
        query = filters.get("q", "").strip().lower()
        if query:
            haystack = " ".join(str(item.get(name) or "") for name in ("run_id", "relative_directory", "simulation_id", "variant_id", "dataset_id", "sequence_id"))
            if query not in haystack.lower():
                return False
        created = _timestamp(item.get("created_at_utc"))
        if date_from and (created is None or created < date_from):
            return False
        if date_to and (created is None or created >= date_to):
            return False
        return True

    @staticmethod
    def _facets(items: Iterable[Mapping[str, Any]]) -> dict[str, list[dict[str, Any]]]:
        fields = ("domain", "dataset_id", "algorithm_id", "scenario_id", "state")
        facets: dict[str, list[dict[str, Any]]] = {}
        for field in fields:
            counts = Counter(str(item[field]) for item in items if item.get(field))
            facets[field] = [{"value": value, "count": count} for value, count in sorted(counts.items())]
        tag_counts = Counter(tag for item in items for tag in item.get("tags", []))
        facets["tags"] = [{"value": value, "count": count} for value, count in sorted(tag_counts.items())]
        return facets

    def _record(self, result_id: str) -> tuple[Path, NormalizedResult, dict[str, Any]]:
        with self._lock:
            record = self._records.get(result_id)
        if record is None:
            self.refresh()
            with self._lock:
                record = self._records.get(result_id)
        if record is None:
            raise ResultHistoryError("Résultat introuvable ou identifiant expiré.")
        return record

    def detail(self, result_id: str) -> dict[str, Any]:
        directory, normalized, summary = self._record(result_id)
        artifacts = json.loads(json.dumps(normalized.artifacts))
        for artifact in artifacts.get("items", []):
            candidate = (directory / artifact["path"]).resolve()
            safe = candidate.is_relative_to(directory)
            artifact["available"] = bool(safe and candidate.exists())
            artifact["size_bytes"] = candidate.stat().st_size if safe and candidate.is_file() else None
        legacy_metrics = _read_json(directory / "metrics.json", required=False)
        return {
            "schema": "drone_agricole.result_detail.v1",
            "summary": summary,
            "manifest": normalized.manifest,
            "metrics": normalized.metrics,
            "legacy_metrics": legacy_metrics,
            "artifacts": artifacts,
            "events": list(normalized.events),
            "duplicate_request": _duplicate_request(directory, normalized.manifest),
        }

    def replay(self, result_id: str) -> dict[str, Any]:
        with self._lock:
            cached = self._replay_cache.get(result_id)
        if cached is not None:
            return cached
        directory, normalized, summary = self._record(result_id)
        if not summary["replay_available"]:
            raise ResultHistoryError("Ce résultat ne possède aucun artefact rechargeable.")
        if normalized.manifest.get("domain") == "localization":
            replay = _replay_lio(directory, normalized, result_id)
        else:
            replay = _replay_px4(directory, normalized, result_id)
        with self._lock:
            self._replay_cache[result_id] = replay
        return replay


def _downsample(values: np.ndarray, maximum: int) -> list[list[float]]:
    import numpy as np

    if values.size == 0:
        return []
    step = max(1, int(math.ceil(len(values) / maximum)))
    return values[::step].astype(float).tolist()


def _pose_position(message: Any) -> list[float]:
    pose = message.pose.pose if hasattr(message.pose, "pose") else message.pose
    return [float(pose.position.x), float(pose.position.y), float(pose.position.z)]


def _pose_time(message: Any, bag_timestamp: int) -> float:
    header = getattr(message, "header", None)
    stamp = getattr(header, "stamp", None)
    if stamp is not None:
        value = float(stamp.sec) + float(stamp.nanosec) * 1e-9
        if value > 0:
            return value
    return float(bag_timestamp) * 1e-9


def _estimate_bag(directory: Path, normalized: NormalizedResult) -> Path | None:
    for artifact in normalized.artifacts.get("items", []):
        if not isinstance(artifact, Mapping) or artifact.get("kind") not in {"rosbag", "trajectory"}:
            continue
        candidate = (directory / str(artifact.get("path", ""))).resolve()
        if candidate.is_relative_to(directory) and candidate.exists():
            return candidate
    candidate = directory / "estimate"
    return candidate if candidate.is_dir() else None


def _read_lio_poses(bag: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    import numpy as np

    try:
        from rosbags.highlevel import AnyReader
    except ImportError as exc:
        raise ResultHistoryError("Le lecteur rosbag hors ligne n'est pas disponible dans cette image.") from exc
    estimate_times: list[float] = []
    estimate_positions: list[list[float]] = []
    truth_times: list[float] = []
    truth_positions: list[list[float]] = []
    try:
        with AnyReader([bag]) as reader:
            connections = [connection for connection in reader.connections if connection.topic in {"/Odometry", "/gt_poses"}]
            for connection, timestamp, rawdata in reader.messages(connections=connections):
                message = reader.deserialize(rawdata, connection.msgtype)
                if connection.topic == "/Odometry":
                    estimate_times.append(_pose_time(message, timestamp))
                    estimate_positions.append(_pose_position(message))
                else:
                    truth_times.append(_pose_time(message, timestamp))
                    truth_positions.append(_pose_position(message))
    except Exception as exc:
        raise ResultHistoryError(f"Trajectoire enregistrée illisible : {exc}") from exc
    return (
        np.asarray(estimate_times, dtype=float),
        np.asarray(estimate_positions, dtype=float).reshape((-1, 3)),
        np.asarray(truth_times, dtype=float),
        np.asarray(truth_positions, dtype=float).reshape((-1, 3)),
    )


def _associate_and_align(
    estimate_times: np.ndarray,
    estimate: np.ndarray,
    truth_times: np.ndarray,
    truth: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    import numpy as np

    if len(estimate) == 0 or len(truth) == 0:
        return estimate, truth, np.empty(0), np.empty(0)
    matched_estimate: list[np.ndarray] = []
    matched_truth: list[np.ndarray] = []
    matched_times: list[float] = []
    for index, timestamp in enumerate(estimate_times):
        insertion = int(np.searchsorted(truth_times, timestamp))
        candidates = [value for value in (insertion - 1, insertion) if 0 <= value < len(truth_times)]
        if not candidates:
            continue
        nearest = min(candidates, key=lambda value: abs(float(truth_times[value] - timestamp)))
        if abs(float(truth_times[nearest] - timestamp)) <= 0.08:
            matched_estimate.append(estimate[index])
            matched_truth.append(truth[nearest])
            matched_times.append(float(timestamp))
    if len(matched_estimate) < 3:
        origin_estimate = estimate[0] if len(estimate) else np.zeros(3)
        origin_truth = truth[0] if len(truth) else np.zeros(3)
        return estimate - origin_estimate, truth - origin_truth, np.empty(0), np.empty(0)
    source = np.asarray(matched_estimate)
    target = np.asarray(matched_truth)
    source_center = source.mean(axis=0)
    target_center = target.mean(axis=0)
    covariance = (source - source_center).T @ (target - target_center)
    left, _, right = np.linalg.svd(covariance)
    rotation = right.T @ left.T
    if np.linalg.det(rotation) < 0:
        right[-1, :] *= -1
        rotation = right.T @ left.T
    translation = target_center - rotation @ source_center
    aligned = (rotation @ estimate.T).T + translation
    aligned_matches = (rotation @ source.T).T + translation
    errors = np.linalg.norm(aligned_matches - target, axis=1)
    relative_times = np.asarray(matched_times) - matched_times[0]
    return aligned, truth, relative_times, errors


def _replay_lio(directory: Path, normalized: NormalizedResult, result_id: str) -> dict[str, Any]:
    import numpy as np

    bag = _estimate_bag(directory, normalized)
    if bag is None:
        raise ResultHistoryError("Rosbag de trajectoire absent.")
    estimate_times, estimate, truth_times, truth = _read_lio_poses(bag)
    aligned, aligned_truth, relative_times, errors = _associate_and_align(estimate_times, estimate, truth_times, truth)
    curve: list[list[float]] = []
    if len(errors):
        cumulative = np.sqrt(np.cumsum(errors * errors) / np.arange(1, len(errors) + 1))
        curve = _downsample(np.column_stack((relative_times, cumulative)), 500)
    return {
        "schema": "drone_agricole.offline_replay.v1",
        "result_id": result_id,
        "domain": "localization",
        "scene": {
            "cloud": [],
            "estimate": _downsample(aligned, 1600),
            "truth": _downsample(aligned_truth, 1600),
            "px4_path": [],
            "px4_pose": None,
        },
        "curves": [{"curve_id": "ate_cumulative_rmse_m", "label": "ATE cumulée", "unit": "m", "values": curve}] if curve else [],
        "notes": ["Trajectoires relues depuis le rosbag enregistré, sans relancer l'algorithme.", "Le nuage LiDAR n'est pas archivé dans les résultats LIO historiques."],
    }


def _replay_px4(directory: Path, normalized: NormalizedResult, result_id: str) -> dict[str, Any]:
    points: list[list[float]] = [[0.0, 0.0, 0.0]]
    altitude: list[list[float]] = [[0.0, 0.0]]
    origin_ned: list[float] | None = None
    for event in normalized.events:
        data = event.get("data") if isinstance(event.get("data"), Mapping) else {}
        if origin_ned is None and isinstance(data.get("origin_ned"), list) and len(data["origin_ned"]) == 3:
            origin_ned = [float(value) for value in data["origin_ned"]]
        target = data.get("target_ned")
        if not isinstance(target, list) or len(target) != 3:
            continue
        north, east, down = (float(value) for value in target)
        if origin_ned:
            north -= origin_ned[0]
            east -= origin_ned[1]
            down -= origin_ned[2]
        point = [east, north, -down]
        points.append(point)
        elapsed = float(event.get("elapsed_s", len(altitude)))
        altitude.append([elapsed, point[2]])
    last = points[-1]
    return {
        "schema": "drone_agricole.offline_replay.v1",
        "result_id": result_id,
        "domain": "flight_simulation",
        "scene": {
            "cloud": [],
            "estimate": [],
            "truth": [],
            "px4_path": points,
            "px4_pose": {"position": last, "orientation_xyzw": [0.0, 0.0, 0.0, 1.0]},
        },
        "curves": [{"curve_id": "target_altitude_m", "label": "Altitude cible", "unit": "m", "values": altitude}],
        "notes": ["Parcours reconstruit depuis les consignes NED archivées dans les événements PX4."],
    }
