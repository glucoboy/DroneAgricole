"""Adaptateurs non destructifs des résultats historiques vers les contrats T0.1."""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from software.visualization.contracts import (
    ContractError,
    validate_artifacts,
    validate_event,
    validate_metrics,
    validate_run_manifest,
)


@dataclass(frozen=True)
class NormalizedResult:
    source_kind: str
    source_directory: Path
    manifest: Mapping[str, Any]
    metrics: Mapping[str, Any]
    artifacts: Mapping[str, Any]
    events: tuple[Mapping[str, Any], ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "source_kind": self.source_kind,
            "source_directory": str(self.source_directory),
            "manifest": self.manifest,
            "metrics": self.metrics,
            "artifacts": self.artifacts,
            "events": list(self.events),
        }


def _read_json(path: Path, *, required: bool = True) -> Mapping[str, Any] | None:
    if not path.is_file():
        if required:
            raise ContractError(f"fichier de résultat absent : {path}")
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractError(f"JSON de résultat illisible : {path}: {exc}") from exc
    if not isinstance(value, Mapping):
        raise ContractError(f"objet JSON attendu dans {path}")
    return value


def _safe_identifier(value: Any, fallback: str) -> str:
    text = str(value or fallback).lower()
    text = re.sub(r"[^a-z0-9_-]+", "_", text).strip("_-")
    if not text or not text[0].isalnum():
        text = fallback
    return text[:96]


def _canonical_lio_algorithm(value: Any) -> str:
    identifier = _safe_identifier(value, "unknown_lio")
    return {
        "fast-lio2": "fast_lio2",
        "fastlio2": "fast_lio2",
        "point-lio": "point_lio",
        "pointlio": "point_lio",
        "lio-sam": "lio_sam",
        "liosam": "lio_sam",
    }.get(identifier, identifier)


def _utc_from_mtime(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat()


def _json_safe(value: Any) -> Any:
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _nested(mapping: Mapping[str, Any], *keys: str) -> Any:
    value: Any = mapping
    for key in keys:
        if not isinstance(value, Mapping) or key not in value:
            return None
        value = value[key]
    return value


def _metric(metric_id: str, label: str, value: Any, unit: str, direction: str = "neutral") -> dict[str, Any] | None:
    if value is None or isinstance(value, (dict, list)):
        return None
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return {
        "metric_id": metric_id,
        "label": label,
        "value": value,
        "unit": unit,
        "direction": direction,
        "status": "unknown",
    }


def detect_result_kind(result_directory: Path | str) -> str:
    directory = Path(result_directory)
    px4_result = _read_json(directory / "result.json", required=False)
    if px4_result and px4_result.get("schema") == "drone_agricole.px4_offboard_test.v1":
        return "px4_offboard_v1"
    manifest = _read_json(directory / "run_manifest.json", required=False)
    if manifest and isinstance(manifest.get("schema_version"), int):
        return "lio_benchmark_legacy"
    raise ContractError(f"format de résultat non reconnu : {directory}")


def normalize_result_directory(result_directory: Path | str) -> NormalizedResult:
    directory = Path(result_directory).resolve()
    if not directory.is_dir():
        raise ContractError(f"répertoire de résultat absent : {directory}")
    kind = detect_result_kind(directory)
    normalized = _normalize_lio(directory) if kind == "lio_benchmark_legacy" else _normalize_px4(directory)
    validate_run_manifest(normalized.manifest)
    validate_metrics(normalized.metrics)
    validate_artifacts(normalized.artifacts)
    for event in normalized.events:
        validate_event(event)
    return normalized


def _normalize_lio(directory: Path) -> NormalizedResult:
    legacy_manifest = _read_json(directory / "run_manifest.json") or {}
    legacy_metrics = _read_json(directory / "metrics.json", required=False) or {}
    request = _read_json(directory / "dashboard_request.json", required=False) or {}
    resource_profile = _read_json(directory / "resource_profile.json", required=False)

    algorithm_source = request.get("algorithm_id") or legacy_manifest.get("algorithm")
    if not algorithm_source:
        for part in reversed(directory.parts):
            candidate = _canonical_lio_algorithm(part)
            if candidate in {"fast_lio2", "point_lio", "lio_sam"}:
                algorithm_source = candidate
                break
    algorithm = _canonical_lio_algorithm(algorithm_source)
    run_id = _safe_identifier(request.get("run_id") or directory.name, "lio_result")
    started_at = request.get("started_at") or _utc_from_mtime(directory)
    finished_at = request.get("finished_at")
    state_map = {
        "completed": "completed",
        "failed": "failed",
        "stopped": "cancelled",
        "cancelled": "cancelled",
        "running": "abandoned",
        "abandoned": "abandoned",
    }
    recorded_state = request.get("state") or legacy_manifest.get("state")
    if recorded_state is None:
        recorded_state = "completed" if legacy_metrics else "abandoned"
    state = state_map.get(str(recorded_state), "failed")
    input_bag = str(legacy_manifest.get("input_bag", "")).replace("\\", "/").lower()
    inferred_dataset = "botanicgarden" if "/botanicgarden/" in input_bag or "botanicgarden" in directory.as_posix().lower() else None
    inferred_sequence = None
    if "/1006-03/smoke/" in input_bag:
        inferred_sequence = "1006-03-smoke"
    elif "/1006-03/dynamic/" in input_bag:
        inferred_sequence = "1006-03-dynamic"
    elif "/1006-03/full/" in input_bag:
        inferred_sequence = "1006-03-full"
    dataset_id = _safe_identifier(request.get("dataset_id") or inferred_dataset, "unknown_dataset")
    sequence_id = _safe_identifier(request.get("sequence_id") or inferred_sequence, "unknown_sequence")

    files: dict[str, str | None] = {
        "source_manifest": "run_manifest.json",
        "metrics": "metrics.json",
        "request": "dashboard_request.json" if (directory / "dashboard_request.json").is_file() else None,
        "resource_profile": "resource_profile.json" if resource_profile is not None else None,
        "configuration": "effective_config.yaml" if (directory / "effective_config.yaml").is_file() else None,
        "estimate": "estimate" if (directory / "estimate").exists() else None,
    }
    manifest = {
        "schema": "drone_agricole.run_manifest.v1",
        "run_id": run_id,
        "request_id": request.get("run_id"),
        "simulation_id": "lio_benchmark",
        "variant_id": algorithm,
        "runner_id": algorithm,
        "domain": "localization",
        "state": state,
        "created_at_utc": started_at,
        "started_at_utc": started_at,
        "finished_at_utc": finished_at,
        "inputs": [
            {
                "input_id": "dataset",
                "kind": "dataset_sequence",
                "reference": {"dataset_id": dataset_id, "sequence_id": sequence_id},
            }
        ],
        "parameters": _json_safe(request.get("parameters", {})),
        "software": {
            "legacy_algorithm": legacy_manifest.get("algorithm"),
            "mapping_process": _json_safe(legacy_manifest.get("mapping_process", {})),
        },
        "files": files,
        "compatibility": {"comparison_group": "lio_trajectory_v1", "result_contract_version": 1},
        "legacy": {
            "adapter": "lio_legacy_v3",
            "source_schema": legacy_manifest.get("schema_version"),
            "source_files": [name for name in ("run_manifest.json", "metrics.json", "dashboard_request.json", "resource_profile.json") if (directory / name).is_file()],
        },
        "metadata": {"source_directory_name": directory.name},
    }

    summary_candidates = (
        _metric("ate_translation_rmse_m", "ATE translation RMSE", _nested(legacy_metrics, "ate_translation_m", "rmse"), "m", "lower"),
        _metric("ate_orientation_rmse_deg", "ATE orientation RMSE", _nested(legacy_metrics, "ate_orientation_deg", "rmse"), "deg", "lower"),
        _metric("rpe_translation_rmse_m", "RPE translation RMSE", _nested(legacy_metrics, "rpe", "translation_m", "rmse"), "m", "lower"),
        _metric("rpe_rotation_rmse_deg", "RPE rotation RMSE", _nested(legacy_metrics, "rpe", "rotation_deg", "rmse"), "deg", "lower"),
        _metric("cpu_average_cores", "CPU moyen", _nested(legacy_manifest, "mapping_process", "cpu_average_equivalent_cores") or _nested(resource_profile or {}, "cpu_average_equivalent_cores"), "coeur", "lower"),
        _metric("peak_rss_mib", "Mémoire RSS maximale", _nested(legacy_manifest, "mapping_process", "peak_rss_mib") or _nested(resource_profile or {}, "peak_rss_mib"), "MiB", "lower"),
        _metric("scheduled_realtime_factor", "Facteur temps réel planifié", legacy_manifest.get("scheduled_data_seconds_per_wall_second"), "x", "higher"),
        _metric("scans_received", "Scans reçus", _nested(legacy_metrics, "pipeline_counters", "scans_received"), "scan", "higher"),
        _metric("odometry_published", "Odométries publiées", _nested(legacy_metrics, "pipeline_counters", "odometry_published") or legacy_metrics.get("estimate_poses"), "pose", "higher"),
        _metric("odometry_over_received_percent", "Sorties sur scans reçus", _nested(legacy_metrics, "pipeline_accounting", "ratios_percent", "odometry_over_received"), "%", "higher"),
    )
    summary = [item for item in summary_candidates if item is not None]
    metrics = {
        "schema": "drone_agricole.metrics.v1",
        "run_id": run_id,
        "simulation_id": "lio_benchmark",
        "status": "complete" if legacy_metrics.get("finite_values") is True and summary else "partial" if summary else "unavailable",
        "summary": summary,
        "groups": {
            "trajectory": _json_safe({key: legacy_metrics.get(key) for key in ("ate_translation_m", "ate_orientation_deg", "rpe", "matched_path_length_m", "matched_endpoint_displacement_m") if key in legacy_metrics}),
            "pipeline": _json_safe({key: legacy_metrics.get(key) for key in ("estimate_poses", "ground_truth_poses", "matched_poses", "pipeline_counters", "pipeline_accounting") if key in legacy_metrics}),
            "resources": _json_safe(resource_profile or legacy_manifest.get("mapping_process", {})),
        },
        "source": {"adapter": "lio_legacy_v3", "path": "metrics.json"},
    }
    artifacts = _build_lio_artifacts(directory, run_id)
    events = _lifecycle_events(run_id, started_at, finished_at, state)
    return NormalizedResult("lio_benchmark_legacy", directory, manifest, metrics, artifacts, events)


def _build_lio_artifacts(directory: Path, run_id: str) -> dict[str, Any]:
    definitions = (
        ("legacy_manifest", "manifest", "Manifeste historique", "run_manifest.json", "application/json", "source", False),
        ("legacy_metrics", "metrics", "Métriques historiques", "metrics.json", "application/json", "source", True),
        ("dashboard_request", "configuration", "Requête du tableau de bord", "dashboard_request.json", "application/json", "source", False),
        ("resource_profile", "other", "Profil de ressources", "resource_profile.json", "application/json", "diagnostic", True),
        ("effective_config", "configuration", "Configuration effective", "effective_config.yaml", "application/yaml", "source", False),
        ("estimate_bag", "rosbag", "Trajectoire estimée", "estimate", "application/x-rosbag2", "output", True),
        ("runner_log", "log", "Journal d'exécution", "runner.log", "text/plain", "diagnostic", False),
    )
    items = []
    for artifact_id, kind, label, relative_path, media_type, role, replayable in definitions:
        if (directory / relative_path).exists():
            items.append(
                {
                    "artifact_id": artifact_id,
                    "kind": kind,
                    "label": label,
                    "path": relative_path,
                    "media_type": media_type,
                    "role": role,
                    "replayable": replayable,
                }
            )
    return {"schema": "drone_agricole.artifacts.v1", "run_id": run_id, "items": items}


def _lifecycle_events(run_id: str, started_at: str, finished_at: str | None, state: str) -> tuple[Mapping[str, Any], ...]:
    events: list[Mapping[str, Any]] = [
        {
            "schema": "drone_agricole.event.v1",
            "run_id": run_id,
            "sequence": 0,
            "timestamp_utc": started_at,
            "event_type": "legacy_run_started",
            "severity": "info",
            "state": "running",
            "message": "Début reconstruit depuis le résultat historique.",
            "data": {"synthetic": True},
        }
    ]
    if finished_at:
        events.append(
            {
                "schema": "drone_agricole.event.v1",
                "run_id": run_id,
                "sequence": 1,
                "timestamp_utc": finished_at,
                "event_type": "legacy_run_finished",
                "severity": "info" if state == "completed" else "error",
                "state": state,
                "message": "Fin reconstruite depuis le résultat historique.",
                "data": {"synthetic": True},
            }
        )
    return tuple(events)


def _normalize_px4(directory: Path) -> NormalizedResult:
    source = _read_json(directory / "result.json") or {}
    run_id = _safe_identifier(directory.name, "px4_result")
    mode = _safe_identifier(source.get("mode"), "unknown_mode")
    created_at = str(source.get("created_utc") or _utc_from_mtime(directory))
    success = bool(source.get("success"))
    observations = source.get("observations") if isinstance(source.get("observations"), Mapping) else {}
    source_events = source.get("events") if isinstance(source.get("events"), list) else []
    duration_s = max((float(event.get("elapsed_s", 0)) for event in source_events if isinstance(event, Mapping)), default=0.0)
    manifest = {
        "schema": "drone_agricole.run_manifest.v1",
        "run_id": run_id,
        "request_id": None,
        "simulation_id": "px4_offboard",
        "variant_id": mode,
        "runner_id": "px4_offboard_test",
        "domain": "flight_simulation",
        "state": "completed" if success else "failed",
        "created_at_utc": created_at,
        "started_at_utc": created_at,
        "finished_at_utc": None,
        "inputs": [
            {
                "input_id": "scenario",
                "kind": "scenario",
                "reference": {"scenario_id": "px4_default_world", "mode": mode},
            }
        ],
        "parameters": _json_safe(source.get("parameters", {})),
        "software": {"legacy_schema": source.get("schema")},
        "files": {"source_result": "result.json"},
        "compatibility": {"comparison_group": "px4_offboard_v1", "result_contract_version": 1},
        "legacy": {
            "adapter": "px4_offboard_v1",
            "source_schema": source.get("schema"),
            "source_files": ["result.json"],
        },
        "metadata": {"reason": source.get("reason"), "source_directory_name": directory.name},
    }
    summary_candidates = (
        _metric("success", "Test réussi", success, "", "higher"),
        _metric("duration_s", "Durée observée", duration_s, "s", "lower"),
        _metric("max_altitude_m", "Altitude maximale", observations.get("max_altitude_m"), "m", "target"),
        _metric("offboard_entered", "Mode Offboard atteint", observations.get("offboard_entered"), "", "higher"),
        _metric("landed", "Atterrissage confirmé", observations.get("landed"), "", "higher"),
        _metric("failsafe", "Failsafe observé", observations.get("failsafe"), "", "lower"),
        _metric("offboard_loss", "Perte Offboard", observations.get("offboard_loss_flag"), "", "lower"),
    )
    metrics = {
        "schema": "drone_agricole.metrics.v1",
        "run_id": run_id,
        "simulation_id": "px4_offboard",
        "status": "complete",
        "summary": [item for item in summary_candidates if item is not None],
        "groups": {
            "observations": _json_safe(observations),
            "command_acks": _json_safe(source.get("command_acks", [])),
        },
        "source": {"adapter": "px4_offboard_v1", "path": "result.json"},
    }
    artifacts = {
        "schema": "drone_agricole.artifacts.v1",
        "run_id": run_id,
        "items": [
            {
                "artifact_id": "source_result",
                "kind": "report",
                "label": "Résultat PX4 historique",
                "path": "result.json",
                "media_type": "application/json",
                "role": "source",
                "replayable": True,
            }
        ],
    }
    events = tuple(_normalize_px4_event(run_id, index, event, success) for index, event in enumerate(source_events) if isinstance(event, Mapping))
    return NormalizedResult("px4_offboard_v1", directory, manifest, metrics, artifacts, events)


def _normalize_px4_event(run_id: str, sequence: int, source: Mapping[str, Any], run_success: bool) -> Mapping[str, Any]:
    event_type = _safe_identifier(source.get("event"), "legacy_event")
    severity = "info"
    if event_type == "test_finished" and not run_success:
        severity = "error"
    elif "failsafe" in event_type or "timeout" in event_type:
        severity = "warning"
    data = {key: _json_safe(value) for key, value in source.items() if key not in ("event", "elapsed_s", "state")}
    return {
        "schema": "drone_agricole.event.v1",
        "run_id": run_id,
        "sequence": sequence,
        "elapsed_s": float(source.get("elapsed_s", 0.0)),
        "event_type": event_type,
        "severity": severity,
        "state": str(source["state"]) if source.get("state") is not None else None,
        "message": event_type.replace("_", " "),
        "data": data,
    }
