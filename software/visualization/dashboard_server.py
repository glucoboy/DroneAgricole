#!/usr/bin/env python3
"""Serve the contract-driven LIO and PX4 simulation dashboard."""

from __future__ import annotations

import argparse
import asyncio
from collections import deque
from datetime import datetime, timezone
import json
import math
import os
import re
import signal
import threading
import time
from pathlib import Path
from typing import Any
import uuid

import numpy as np
import yaml
from aiohttp import WSMsgType, web
from geometry_msgs.msg import PoseStamped
import rclpy
from nav_msgs.msg import Odometry
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import PointCloud2
from std_msgs.msg import Float64, String

from software.visualization.contracts import (
    DefinitionRegistry,
    validate_artifacts,
    validate_event,
    validate_metrics,
    validate_run_manifest,
    validate_run_request,
)
from software.visualization.result_adapters import normalize_result_directory
from software.visualization.result_comparison import ComparisonError, ComparisonService
from software.visualization.result_history import ResultHistoryError, ResultRepository
from software.visualization.runners import PreparedRun, RunnerRegistry, RunnerRequestError


FASTLIO_PARAMETER_PATHS = {
    "filter_size_surf": ("/**", "ros__parameters", "filter_size_surf"),
    "filter_size_map": ("/**", "ros__parameters", "filter_size_map"),
    "point_filter_num": ("/**", "ros__parameters", "point_filter_num"),
    "max_iteration": ("/**", "ros__parameters", "max_iteration"),
    "blind": ("/**", "ros__parameters", "preprocess", "blind"),
    "det_range": ("/**", "ros__parameters", "mapping", "det_range"),
}
POINTLIO_PARAMETER_PATHS = {
    "filter_size_surf": ("/**", "ros__parameters", "filter_size_surf"),
    "filter_size_map": ("/**", "ros__parameters", "filter_size_map"),
    "point_filter_num": ("/**", "ros__parameters", "point_filter_num"),
    "blind": ("/**", "ros__parameters", "preprocess", "blind"),
    "det_range": ("/**", "ros__parameters", "mapping", "det_range"),
    "plane_thr": ("/**", "ros__parameters", "mapping", "plane_thr"),
}
LIOSAM_PARAMETER_PATHS = {
    "odometrySurfLeafSize": ("/**", "ros__parameters", "odometrySurfLeafSize"),
    "mappingCornerLeafSize": ("/**", "ros__parameters", "mappingCornerLeafSize"),
    "mappingSurfLeafSize": ("/**", "ros__parameters", "mappingSurfLeafSize"),
    "edgeThreshold": ("/**", "ros__parameters", "edgeThreshold"),
    "surfThreshold": ("/**", "ros__parameters", "surfThreshold"),
    "mappingProcessInterval": ("/**", "ros__parameters", "mappingProcessInterval"),
}
IDENTIFIER_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


RequestError = RunnerRequestError


def load_catalog(path: Path) -> dict[str, Any]:
    catalog = json.loads(path.read_text(encoding="utf-8"))
    if catalog.get("schema_version") != 1:
        raise ValueError("Unsupported dashboard catalog schema")
    registry_config = catalog.get("contract_registry")
    if registry_config is not None:
        if not isinstance(registry_config, dict):
            raise ValueError("Invalid contract registry configuration")
        workspace = path.resolve().parents[2]
        dataset_directory = (workspace / registry_config["datasets_directory"]).resolve()
        simulation_directory = (workspace / registry_config["simulations_directory"]).resolve()
        if not dataset_directory.is_relative_to(workspace) or not simulation_directory.is_relative_to(workspace):
            raise ValueError("Contract registry directories must stay inside the workspace")
        registry = DefinitionRegistry.load(dataset_directory, simulation_directory)
        catalog["contract_options"] = {
            "datasets": list(registry.datasets.values()),
            "simulations": list(registry.simulations.values()),
            "compatibility": {
                simulation_id: {
                    variant["variant_id"]: registry.compatible_dataset_sequences(simulation_id, variant["variant_id"])
                    for variant in simulation["variants"]
                }
                for simulation_id, simulation in registry.simulations.items()
            },
        }
    return catalog


def catalog_item(values: list[dict[str, Any]], identifier: str, kind: str) -> dict[str, Any]:
    if not IDENTIFIER_PATTERN.fullmatch(identifier):
        raise RequestError(f"Identifiant {kind} invalide.")
    for value in values:
        if value.get("id") == identifier:
            return value
    raise RequestError(f"{kind.capitalize()} inconnu : {identifier}")


def workspace_path(workspace: Path, relative: str, kind: str) -> Path:
    candidate = (workspace / relative).resolve()
    if not candidate.is_relative_to(workspace):
        raise RequestError(f"Chemin {kind} hors du workspace.")
    return candidate


def numeric_parameter(definition: dict[str, Any], supplied: Any) -> int | float:
    identifier = definition["id"]
    try:
        value = float(supplied)
    except (TypeError, ValueError) as error:
        raise RequestError(f"Valeur invalide pour {identifier}.") from error
    minimum = float(definition["minimum"])
    maximum = float(definition["maximum"])
    if not minimum <= value <= maximum:
        raise RequestError(
            f"{identifier} doit rester entre {minimum:g} et {maximum:g}."
        )
    if definition.get("type") == "integer":
        if not value.is_integer():
            raise RequestError(f"{identifier} doit être un entier.")
        return int(value)
    return value


def resolve_run_request(
    catalog: dict[str, Any],
    payload: dict[str, Any],
    workspace: Path,
) -> dict[str, Any]:
    dataset = catalog_item(catalog["datasets"], str(payload.get("dataset_id", "")), "dataset")
    sequence = catalog_item(
        dataset["sequences"],
        str(payload.get("sequence_id", "")),
        "séquence",
    )
    algorithm = catalog_item(
        catalog["algorithms"],
        str(payload.get("algorithm_id", "")),
        "algorithme",
    )
    if not algorithm.get("available", False):
        raise RequestError(f"{algorithm['label']} n'est pas encore intégré.")
    if algorithm.get("runner") not in {"fast_lio2", "point_lio", "lio_sam"}:
        raise RequestError("Aucun lanceur n'est disponible pour cet algorithme.")

    bag_path = workspace_path(workspace, sequence["bag_path"], "dataset")
    config_path = workspace_path(workspace, algorithm["base_config"], "configuration")
    if not bag_path.is_dir():
        raise RequestError(f"Dataset absent : {sequence['bag_path']}")
    if not config_path.is_file():
        raise RequestError(f"Configuration absente : {algorithm['base_config']}")

    supplied_parameters = payload.get("parameters") or {}
    if not isinstance(supplied_parameters, dict):
        raise RequestError("Le bloc parameters doit être un objet.")
    definitions = [*catalog.get("run_parameters", []), *algorithm.get("parameters", [])]
    allowed = {definition["id"] for definition in definitions}
    unexpected = sorted(set(supplied_parameters) - allowed)
    if unexpected:
        raise RequestError(f"Paramètre inconnu : {unexpected[0]}")
    parameters = {
        definition["id"]: numeric_parameter(
            definition,
            supplied_parameters.get(definition["id"], definition["default"]),
        )
        for definition in definitions
    }
    return {
        "dataset": dataset,
        "sequence": sequence,
        "algorithm": algorithm,
        "bag_path": bag_path,
        "base_config_path": config_path,
        "parameters": parameters,
    }


def write_fastlio_config(base: Path, output: Path, parameters: dict[str, Any]) -> None:
    configuration = yaml.safe_load(base.read_text(encoding="utf-8"))
    for identifier, path in FASTLIO_PARAMETER_PATHS.items():
        if identifier not in parameters:
            continue
        target = configuration
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = parameters[identifier]
    configuration["/**"]["ros__parameters"]["publish"]["scan_publish_en"] = True
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        yaml.safe_dump(configuration, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


def write_lio_config(
    runner: str,
    base: Path,
    output: Path,
    parameters: dict[str, Any],
) -> None:
    if runner == "fast_lio2":
        write_fastlio_config(base, output, parameters)
        return
    if runner not in {"point_lio", "lio_sam"}:
        raise RequestError("Lanceur LIO inconnu.")
    configuration = yaml.safe_load(base.read_text(encoding="utf-8"))
    parameter_paths = (
        POINTLIO_PARAMETER_PATHS if runner == "point_lio" else LIOSAM_PARAMETER_PATHS
    )
    for identifier, path in parameter_paths.items():
        if identifier not in parameters:
            continue
        target = configuration
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = parameters[identifier]
    if runner == "point_lio":
        configuration["/**"]["ros__parameters"]["publish"]["scan_publish_en"] = True
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        yaml.safe_dump(configuration, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


class RunController:
    def __init__(self, workspace: Path, catalog_path: Path, node: "DashboardNode") -> None:
        self.workspace = workspace.resolve()
        self.catalog_path = catalog_path.resolve()
        self.catalog = load_catalog(self.catalog_path)
        registry_config = self.catalog.get("contract_registry")
        if not isinstance(registry_config, dict):
            raise ValueError("Le registre T0.2 est requis par le tableau de bord.")
        self.definition_registry = DefinitionRegistry.load(
            workspace_path(self.workspace, registry_config["datasets_directory"], "registre datasets"),
            workspace_path(self.workspace, registry_config["simulations_directory"], "registre simulations"),
        )
        self.runners = RunnerRegistry(self.definition_registry, self.workspace)
        self.node = node
        self.process: asyncio.subprocess.Process | None = None
        self.wait_task: asyncio.Task[None] | None = None
        self.log_task: asyncio.Task[None] | None = None
        self.prepared: PreparedRun | None = None
        self.logs: deque[str] = deque(maxlen=80)
        self.stop_requested = False
        self.current: dict[str, Any] = {
            "state": "idle",
            "message": "Prêt à lancer une simulation.",
        }

    def public_catalog(self) -> dict[str, Any]:
        return self.runners.public_options()

    def status(self) -> dict[str, Any]:
        return {**self.current, "logs": list(self.logs)[-8:]}

    async def start(self, payload: dict[str, Any]) -> dict[str, Any]:
        if self.process is not None and self.process.returncode is None:
            raise RuntimeError("Une simulation est déjà en cours.")
        if self.wait_task is not None and not self.wait_task.done():
            raise RuntimeError("La simulation précédente est encore en cours d'analyse.")
        run_id = uuid.uuid4().hex[:8]
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        prepared = self.runners.prepare(payload, run_id, stamp)
        self.prepared = prepared
        self.node.prepare_run()
        self.logs.clear()
        self.stop_requested = False
        started_at = datetime.now(timezone.utc).isoformat()
        self.current = {
            "state": "starting",
            **prepared.public_status(self.workspace),
            "message": f"Démarrage de {prepared.variant_label}…",
            "started_at": started_at,
            "finished_at": None,
            "exit_code": None,
            "analysis_state": "pending",
            "analysis_error": None,
            "final_metrics": None,
            "summary_metrics": None,
        }
        try:
            self.process = await asyncio.create_subprocess_exec(
                *prepared.command,
                cwd=self.workspace,
                env=prepared.environment,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                start_new_session=True,
            )
        except Exception:
            self._cleanup_runtime(prepared)
            self.current.update(
                state="failed",
                message="Le processus de simulation n'a pas pu démarrer.",
                finished_at=datetime.now(timezone.utc).isoformat(),
            )
            raise
        self.current.update(state="running", message="Simulation en cours.")
        self.log_task = asyncio.create_task(self._consume_logs(self.process))
        self.wait_task = asyncio.create_task(
            self._watch(self.process, prepared)
        )
        return self.status()

    async def _consume_logs(self, process: asyncio.subprocess.Process) -> None:
        if process.stdout is None:
            return
        async for raw_line in process.stdout:
            line = raw_line.decode("utf-8", errors="replace").strip()
            if line:
                self.logs.append(line)

    async def _analyze_run(
        self,
        result_directory: Path,
        pipeline_topic: str | None,
    ) -> dict[str, Any]:
        metrics_path = result_directory / "metrics.json"
        command = [
            "python3",
            "tools/benchmarks/analyze_lio_trajectory.py",
            result_directory.relative_to(self.workspace).joinpath("estimate").as_posix(),
            "--output",
            metrics_path.relative_to(self.workspace).as_posix(),
        ]
        if pipeline_topic:
            command.extend(["--pipeline-topic", pipeline_topic])
        process = await asyncio.create_subprocess_exec(
            *command,
            cwd=self.workspace,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        output, _ = await process.communicate()
        (result_directory / "analysis.log").write_bytes(output)
        if process.returncode != 0:
            detail = output.decode("utf-8", errors="replace").strip().splitlines()
            raise RuntimeError(detail[-1] if detail else "Analyse de trajectoire en échec.")
        return json.loads(metrics_path.read_text(encoding="utf-8"))

    async def _watch(
        self,
        process: asyncio.subprocess.Process,
        prepared: PreparedRun,
    ) -> None:
        exit_code = await process.wait()
        if self.log_task is not None:
            await self.log_task
        finished_at = datetime.now(timezone.utc).isoformat()
        if self.stop_requested:
            state = "stopped"
            message = "Simulation arrêtée par l'utilisateur."
        elif exit_code == 0:
            state = "completed"
            message = "Simulation terminée avec succès."
        else:
            state = "failed"
            message = f"Simulation interrompue avec le code {exit_code}."
        analysis_state = "not_run"
        analysis_error = None
        final_metrics = None
        if state == "completed" and prepared.analysis_kind == "lio_trajectory" and (prepared.result_directory / "estimate").is_dir():
            analysis_state = "running"
            self.current.update(
                state="analyzing",
                message="Simulation terminée · calcul des métriques finales…",
                exit_code=exit_code,
            )
            try:
                final_metrics = await self._analyze_run(
                    prepared.result_directory,
                    prepared.pipeline_topic,
                )
                analysis_state = "completed"
                message = "Simulation et métriques terminées avec succès."
            except (OSError, RuntimeError, json.JSONDecodeError) as error:
                analysis_state = "failed"
                analysis_error = str(error)
                message = "Simulation terminée, mais le calcul des métriques a échoué."
                self.logs.append(f"Analyse finale : {error}")
        elif state == "completed" and prepared.analysis_kind == "px4_result":
            result_path = prepared.result_directory / "result.json"
            if result_path.is_file():
                try:
                    final_metrics = json.loads(result_path.read_text(encoding="utf-8"))
                    analysis_state = "completed"
                    message = "Simulation PX4 et résultat terminés avec succès."
                except (OSError, json.JSONDecodeError) as error:
                    analysis_state = "failed"
                    analysis_error = str(error)
                    message = "Simulation PX4 terminée, mais result.json est illisible."
            else:
                analysis_state = "failed"
                analysis_error = "result.json absent"
                message = "Simulation PX4 terminée sans résultat exploitable."
        elif state == "completed":
            analysis_state = "not_required"

        summary_metrics = None
        if prepared.result_directory.is_dir():
            try:
                self._write_run_request(prepared, started_at=self.current["started_at"])
                self._write_legacy_dashboard_request(
                    prepared,
                    state,
                    finished_at,
                    exit_code,
                    analysis_state,
                    final_metrics,
                )
                normalized = normalize_result_directory(prepared.result_directory)
                summary_metrics = self._write_normalized_contracts(
                    prepared,
                    normalized,
                    state,
                    finished_at,
                )
            except (OSError, ValueError, json.JSONDecodeError) as error:
                if analysis_state in {"completed", "not_required"}:
                    analysis_state = "failed"
                    analysis_error = f"Contrats T0.2 : {error}"
                    message = "Simulation terminée, mais l'archivage des contrats T0.2 a échoué."
                self.logs.append(f"Contrats T0.2 : {error}")
        self.current.update(
            state=state,
            message=message,
            finished_at=finished_at,
            exit_code=exit_code,
            analysis_state=analysis_state,
            analysis_error=analysis_error,
            final_metrics=final_metrics,
            summary_metrics=summary_metrics,
        )
        self._cleanup_runtime(prepared)
        if self.process is process:
            self.process = None
        if self.prepared is prepared:
            self.prepared = None

    def _write_run_request(self, prepared: PreparedRun, started_at: str) -> None:
        request = {
            "schema": "drone_agricole.run_request.v1",
            "request_id": f"request_{prepared.run_id}",
            "simulation_id": prepared.simulation_id,
            "variant_id": prepared.variant_id,
            "requested_at_utc": started_at,
            "profile_id": prepared.profile_id,
            "inputs": prepared.inputs,
            "parameters": prepared.parameters,
            "tags": ["dashboard", "t0_2"],
        }
        validate_run_request(request)
        (prepared.result_directory / "run_request.json").write_text(
            json.dumps(request, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def _write_legacy_dashboard_request(
        self,
        prepared: PreparedRun,
        state: str,
        finished_at: str,
        exit_code: int,
        analysis_state: str,
        final_metrics: dict[str, Any] | None,
    ) -> None:
        manifest = {
            "schema_version": 1,
            "run_id": prepared.run_id,
            "state": state,
            "simulation_id": prepared.simulation_id,
            "variant_id": prepared.variant_id,
            "dataset_id": prepared.dataset_id,
            "sequence_id": prepared.sequence_id,
            "algorithm_id": prepared.variant_id if prepared.simulation_id == "lio_benchmark" else None,
            "parameters": prepared.parameters,
            "profile_id": prepared.profile_id,
            "started_at": self.current.get("started_at"),
            "finished_at": finished_at,
            "exit_code": exit_code,
            "analysis_state": analysis_state,
            "metrics_file": "metrics.json" if final_metrics is not None and prepared.analysis_kind == "lio_trajectory" else None,
        }
        (prepared.result_directory / "dashboard_request.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    def _write_normalized_contracts(
        self,
        prepared: PreparedRun,
        normalized: Any,
        state: str,
        finished_at: str,
    ) -> list[dict[str, Any]]:
        manifest = json.loads(json.dumps(normalized.manifest))
        metrics = json.loads(json.dumps(normalized.metrics))
        artifacts = json.loads(json.dumps(normalized.artifacts))
        events = json.loads(json.dumps(list(normalized.events)))
        canonical_state = {"stopped": "cancelled"}.get(state, state)
        manifest.update(
            run_id=prepared.run_id,
            request_id=f"request_{prepared.run_id}",
            simulation_id=prepared.simulation_id,
            variant_id=prepared.variant_id,
            runner_id=prepared.runner_id,
            domain=prepared.domain,
            state=canonical_state,
            finished_at_utc=finished_at,
            parameters=prepared.parameters,
            inputs=prepared.inputs,
        )
        metrics.update(run_id=prepared.run_id, simulation_id=prepared.simulation_id)
        artifacts["run_id"] = prepared.run_id
        for event in events:
            event["run_id"] = prepared.run_id
        validate_run_manifest(manifest)
        validate_metrics(metrics)
        validate_artifacts(artifacts)
        for event in events:
            validate_event(event)
        files = (
            ("t0_run_manifest.json", manifest),
            ("t0_metrics.json", metrics),
            ("artifacts.json", artifacts),
        )
        for filename, payload in files:
            (prepared.result_directory / filename).write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        with (prepared.result_directory / "events.jsonl").open("w", encoding="utf-8") as stream:
            for event in events:
                stream.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")
        return metrics["summary"]

    @staticmethod
    def _cleanup_runtime(prepared: PreparedRun) -> None:
        for path in prepared.runtime_files:
            path.unlink(missing_ok=True)

    async def stop(self) -> dict[str, Any]:
        process = self.process
        if process is None or process.returncode is not None:
            raise RuntimeError("Aucune simulation n'est en cours.")
        self.stop_requested = True
        self.current.update(state="stopping", message="Arrêt en cours…")
        try:
            os.killpg(process.pid, signal.SIGINT)
        except ProcessLookupError:
            pass
        try:
            await asyncio.wait_for(asyncio.shield(process.wait()), timeout=20.0)
        except asyncio.TimeoutError:
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        if self.wait_task is not None:
            try:
                await asyncio.wait_for(asyncio.shield(self.wait_task), timeout=10.0)
            except asyncio.TimeoutError:
                self.current.update(
                    state="failed",
                    message="Le processus ne s'est pas arrêté proprement.",
                )
        return self.status()


def stamp_seconds(message: Any) -> float:
    stamp = message.header.stamp
    return float(stamp.sec) + float(stamp.nanosec) / 1_000_000_000.0


def downsample_path(values: np.ndarray, maximum: int = 1600) -> list[list[float]]:
    if not len(values):
        return []
    if len(values) > maximum:
        indices = np.linspace(0, len(values) - 1, maximum, dtype=np.int64)
        values = values[indices]
    return np.round(values, 3).tolist()


def align_live(
    estimate_times: np.ndarray,
    estimate_positions: np.ndarray,
    truth_times: np.ndarray,
    truth_positions: np.ndarray,
    max_delta_s: float = 0.06,
) -> tuple[float | None, np.ndarray]:
    if len(estimate_positions) < 5 or len(truth_positions) < 5:
        return None, truth_positions
    insertion = np.searchsorted(truth_times, estimate_times)
    right = np.clip(insertion, 0, len(truth_times) - 1)
    left = np.clip(insertion - 1, 0, len(truth_times) - 1)
    use_left = np.abs(truth_times[left] - estimate_times) <= np.abs(
        truth_times[right] - estimate_times
    )
    nearest = np.where(use_left, left, right)
    valid = np.abs(truth_times[nearest] - estimate_times) <= max_delta_s
    source = estimate_positions[valid]
    target = truth_positions[nearest[valid]]
    if len(source) < 5:
        return None, truth_positions

    source_center = np.mean(source, axis=0)
    target_center = np.mean(target, axis=0)
    covariance = (source - source_center).T @ (target - target_center)
    left_svd, _, right_transpose = np.linalg.svd(covariance)
    rotation = right_transpose.T @ left_svd.T
    if np.linalg.det(rotation) < 0:
        right_transpose[-1, :] *= -1
        rotation = right_transpose.T @ left_svd.T
    translation = target_center - rotation @ source_center
    aligned = (rotation @ source.T).T + translation
    ate_rmse = float(np.sqrt(np.mean(np.sum((aligned - target) ** 2, axis=1))))
    truth_in_estimate = (rotation.T @ (truth_positions - translation).T).T
    return ate_rmse, truth_in_estimate


class DashboardNode(Node):
    def __init__(self, max_cloud_points: int) -> None:
        super().__init__("drone_agricole_live_dashboard")
        self.max_cloud_points = max_cloud_points
        self.lock = threading.Lock()
        self.estimate_times: list[float] = []
        self.estimate_positions: list[list[float]] = []
        self.truth_times: list[float] = []
        self.truth_positions: list[list[float]] = []
        self.cloud: list[float] = []
        self.cloud_sequence = 0
        self.wall_started: float | None = None
        self.last_truth_time: float | None = None
        self.last_truth_wall: float | None = None
        self.cpu_percent = 0.0
        self.cpu_total_seconds = 0.0
        self.memory_mib = 0.0
        self.expected_duration_s = 0.0
        self.pipeline_counters: dict[str, int] = {}
        self.px4_positions: deque[list[float]] = deque(maxlen=2500)
        self.px4_pose: dict[str, Any] | None = None
        self.px4_state: dict[str, Any] = {}
        self.px4_received_at: float | None = None

        self.create_subscription(
            Odometry,
            "/Odometry",
            self.on_odometry,
            qos_profile_sensor_data,
        )
        self.create_subscription(
            PointCloud2,
            "/cloud_registered",
            self.on_cloud,
            qos_profile_sensor_data,
        )
        self.create_subscription(
            PoseStamped,
            "/gt_poses",
            self.on_truth,
            qos_profile_sensor_data,
        )
        self.create_subscription(
            Float64,
            "/benchmark/cpu_percent_one_core",
            lambda message: self.set_metric("cpu_percent", message.data),
            10,
        )
        self.create_subscription(
            Float64,
            "/benchmark/cpu_total_seconds",
            lambda message: self.set_metric("cpu_total_seconds", message.data),
            10,
        )
        self.create_subscription(
            Float64,
            "/benchmark/memory_rss_mib",
            lambda message: self.set_metric("memory_mib", message.data),
            10,
        )
        self.create_subscription(
            Float64,
            "/benchmark/expected_duration_s",
            lambda message: self.set_metric("expected_duration_s", message.data),
            10,
        )
        self.create_subscription(
            String,
            "/fast_lio2/pipeline_counters",
            self.on_pipeline_counters,
            10,
        )
        self.create_subscription(
            String,
            "/point_lio/pipeline_counters",
            self.on_pipeline_counters,
            10,
        )
        self.create_subscription(
            String,
            "/lio_sam/pipeline_counters",
            self.on_pipeline_counters,
            10,
        )
        self.create_subscription(
            Odometry,
            "/drone/px4/odometry",
            self.on_px4_odometry,
            qos_profile_sensor_data,
        )
        self.create_subscription(
            String,
            "/drone/px4/state_json",
            self.on_px4_state,
            10,
        )

    def set_metric(self, name: str, value: float) -> None:
        with self.lock:
            setattr(self, name, float(value))

    def on_pipeline_counters(self, message: String) -> None:
        try:
            payload = json.loads(message.data)
        except (json.JSONDecodeError, TypeError):
            return
        if payload.get("schema_version") != 1:
            return
        counters = {
            key: int(value)
            for key, value in payload.items()
            if key != "schema_version" and isinstance(value, (int, float))
        }
        counters["schema_version"] = 1
        with self.lock:
            self.pipeline_counters = counters

    def on_px4_state(self, message: String) -> None:
        try:
            payload = json.loads(message.data)
        except (json.JSONDecodeError, TypeError):
            return
        if payload.get("schema") != "drone_agricole.px4_state.v1":
            return
        with self.lock:
            self.px4_state = payload
            self.px4_received_at = time.monotonic()

    def on_px4_odometry(self, message: Odometry) -> None:
        position = message.pose.pose.position
        orientation = message.pose.pose.orientation
        coordinates = [float(position.x), float(position.y), float(position.z)]
        pose = {
            "position": coordinates,
            "orientation_xyzw": [
                float(orientation.x),
                float(orientation.y),
                float(orientation.z),
                float(orientation.w),
            ],
            "frame": message.header.frame_id,
        }
        with self.lock:
            if not self.px4_positions or math.dist(self.px4_positions[-1], coordinates) >= 0.03:
                self.px4_positions.append(coordinates)
            self.px4_pose = pose
            self.px4_received_at = time.monotonic()

    def reset_run(self, wall_started: float | None = None) -> None:
        self.estimate_times.clear()
        self.estimate_positions.clear()
        self.truth_times.clear()
        self.truth_positions.clear()
        self.cloud.clear()
        self.cloud_sequence += 1
        self.wall_started = wall_started
        self.last_truth_time = None
        self.last_truth_wall = None
        self.cpu_percent = 0.0
        self.cpu_total_seconds = 0.0
        self.memory_mib = 0.0
        self.expected_duration_s = 0.0
        self.pipeline_counters = {}

    def prepare_run(self) -> None:
        with self.lock:
            self.reset_run()

    def on_truth(self, message: Any) -> None:
        timestamp = stamp_seconds(message)
        position = message.pose.position
        received_at = time.monotonic()
        with self.lock:
            if self.last_truth_time is not None and timestamp < self.last_truth_time - 1.0:
                self.reset_run(received_at)
            if self.wall_started is None:
                self.wall_started = received_at
            self.last_truth_time = timestamp
            self.last_truth_wall = received_at
            self.truth_times.append(timestamp)
            self.truth_positions.append([position.x, position.y, position.z])

    def on_odometry(self, message: Odometry) -> None:
        timestamp = stamp_seconds(message)
        position = message.pose.pose.position
        with self.lock:
            self.estimate_times.append(timestamp)
            self.estimate_positions.append([position.x, position.y, position.z])

    def on_cloud(self, message: PointCloud2) -> None:
        fields = {field.name: field for field in message.fields}
        if not {"x", "y", "z"}.issubset(fields):
            return
        byte_order = ">" if message.is_bigendian else "<"
        names = ["x", "y", "z"]
        formats = [f"{byte_order}f4"] * 3
        offsets = [fields[name].offset for name in names]
        has_intensity = "intensity" in fields and fields["intensity"].datatype == 7
        if has_intensity:
            names.append("intensity")
            formats.append(f"{byte_order}f4")
            offsets.append(fields["intensity"].offset)
        count = int(message.width * message.height)
        if not count:
            return
        try:
            dtype = np.dtype(
                {
                    "names": names,
                    "formats": formats,
                    "offsets": offsets,
                    "itemsize": message.point_step,
                }
            )
            points = np.frombuffer(bytes(message.data), dtype=dtype, count=count)
        except (TypeError, ValueError):
            return
        step = max(1, int(np.ceil(count / self.max_cloud_points)))
        sampled = points[::step]
        xyz = np.column_stack((sampled["x"], sampled["y"], sampled["z"]))
        finite = np.all(np.isfinite(xyz), axis=1)
        xyz = xyz[finite]
        if has_intensity:
            intensity = np.asarray(sampled["intensity"][finite], dtype=np.float32)
            low, high = np.percentile(intensity, [5.0, 95.0]) if len(intensity) else (0.0, 1.0)
            intensity = np.clip((intensity - low) / max(float(high - low), 1e-6), 0.0, 1.0)
        else:
            intensity = np.full(len(xyz), 0.5, dtype=np.float32)
        packed = np.column_stack((xyz, intensity))
        with self.lock:
            self.cloud = np.round(packed, 3).ravel().tolist()
            self.cloud_sequence += 1

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            estimate_times = np.asarray(self.estimate_times, dtype=np.float64)
            estimate_positions = np.asarray(self.estimate_positions, dtype=np.float64).reshape(-1, 3)
            truth_times = np.asarray(self.truth_times, dtype=np.float64)
            truth_positions = np.asarray(self.truth_positions, dtype=np.float64).reshape(-1, 3)
            cloud = self.cloud
            cloud_sequence = self.cloud_sequence
            cpu_percent = self.cpu_percent
            cpu_total_seconds = self.cpu_total_seconds
            memory_mib = self.memory_mib
            expected_duration_s = self.expected_duration_s
            pipeline_counters = dict(self.pipeline_counters)
            wall_started = self.wall_started
            last_truth_wall = self.last_truth_wall
            px4_positions = np.asarray(
                list(self.px4_positions), dtype=np.float64
            ).reshape(-1, 3)
            px4_pose = dict(self.px4_pose) if self.px4_pose is not None else None
            px4_state = dict(self.px4_state)
            px4_received_at = self.px4_received_at

        ate_rmse, truth_in_estimate = align_live(
            estimate_times,
            estimate_positions,
            truth_times,
            truth_positions,
        )
        data_elapsed = (
            float(truth_times[-1] - truth_times[0]) if len(truth_times) > 1 else 0.0
        )
        wall_elapsed = (
            last_truth_wall - wall_started
            if wall_started is not None and last_truth_wall is not None
            else 0.0
        )
        progress = (
            min(100.0, 100.0 * data_elapsed / expected_duration_s)
            if expected_duration_s > 0.0
            else 0.0
        )
        realtime_factor = data_elapsed / wall_elapsed if wall_elapsed > 0.0 else 0.0
        output_ratio = (
            100.0 * len(estimate_positions) / len(truth_positions)
            if len(truth_positions)
            else 0.0
        )
        px4_age_s = (
            max(0.0, time.monotonic() - px4_received_at)
            if px4_received_at is not None
            else None
        )
        return {
            "type": "snapshot",
            "timestamp": time.time(),
            "metrics": {
                "progress_percent": progress,
                "data_elapsed_s": data_elapsed,
                "wall_elapsed_s": wall_elapsed,
                "realtime_factor": realtime_factor,
                "cpu_percent_one_core": cpu_percent,
                "cpu_total_seconds": cpu_total_seconds,
                "memory_rss_mib": memory_mib,
                "ate_rmse_m": ate_rmse,
                "odometry_count": int(len(estimate_positions)),
                "reference_count": int(len(truth_positions)),
                "output_ratio_percent": output_ratio,
                "pipeline_counters": pipeline_counters,
            },
            "scene": {
                "cloud_sequence": cloud_sequence,
                "cloud": cloud,
                "estimate": downsample_path(estimate_positions),
                "truth": downsample_path(truth_in_estimate),
                "px4_path": downsample_path(px4_positions),
                "px4_pose": px4_pose,
            },
            "px4": {
                "connected": px4_age_s is not None and px4_age_s < 2.0,
                "age_s": px4_age_s,
                "pose": px4_pose,
                "path_points": int(len(px4_positions)),
                "state": px4_state,
            },
        }


def create_application(
    node: DashboardNode,
    controller: RunController,
    assets: Path,
    rate_hz: float,
) -> web.Application:
    application = web.Application()
    sockets: set[web.WebSocketResponse] = set()
    result_repository = ResultRepository(controller.workspace)
    comparison_service = ComparisonService(result_repository)
    application["result_repository"] = result_repository
    application["comparison_service"] = comparison_service

    async def index(_request: web.Request) -> web.FileResponse:
        return web.FileResponse(assets / "index.html")

    async def health(_request: web.Request) -> web.Response:
        return web.json_response(
            {
                "status": "ok",
                "ros_node": node.get_name(),
                "runner_state": controller.status()["state"],
            }
        )

    async def snapshot(_request: web.Request) -> web.Response:
        payload = node.snapshot()
        payload["run"] = controller.status()
        return web.json_response(payload)

    async def options(_request: web.Request) -> web.Response:
        return web.json_response(controller.public_catalog())

    async def run_status(_request: web.Request) -> web.Response:
        return web.json_response(controller.status())

    async def start_run(request: web.Request) -> web.Response:
        try:
            payload = await request.json()
            if not isinstance(payload, dict):
                raise RequestError("La requête doit être un objet JSON.")
            status = await controller.start(payload)
        except (json.JSONDecodeError, RequestError) as error:
            return web.json_response({"error": str(error)}, status=400)
        except RuntimeError as error:
            return web.json_response({"error": str(error)}, status=409)
        return web.json_response(status, status=202)

    async def stop_run(_request: web.Request) -> web.Response:
        try:
            status = await controller.stop()
        except RuntimeError as error:
            return web.json_response({"error": str(error)}, status=409)
        return web.json_response(status)

    async def result_index(request: web.Request) -> web.Response:
        filters = {key: value for key, value in request.query.items() if key != "refresh"}
        try:
            payload = await asyncio.to_thread(
                result_repository.search,
                filters,
                refresh=request.query.get("refresh") == "1",
            )
        except ResultHistoryError as error:
            return web.json_response({"error": str(error)}, status=400)
        return web.json_response(payload)

    async def result_detail(request: web.Request) -> web.Response:
        try:
            payload = await asyncio.to_thread(result_repository.detail, request.match_info["result_id"])
        except ResultHistoryError as error:
            return web.json_response({"error": str(error)}, status=404)
        return web.json_response(payload)

    async def result_replay(request: web.Request) -> web.Response:
        try:
            payload = await asyncio.to_thread(result_repository.replay, request.match_info["result_id"])
        except ResultHistoryError as error:
            return web.json_response({"error": str(error)}, status=422)
        return web.json_response(payload)

    async def comparison_ids(request: web.Request) -> list[str]:
        try:
            payload = await request.json()
        except json.JSONDecodeError as error:
            raise ComparisonError("La requête doit être un objet JSON valide.") from error
        if not isinstance(payload, dict):
            raise ComparisonError("La requête doit être un objet JSON.")
        return comparison_service.validate_result_ids(payload.get("result_ids"))

    async def comparison_preview(request: web.Request) -> web.Response:
        try:
            result_ids = await comparison_ids(request)
            payload = await asyncio.to_thread(comparison_service.preview, result_ids)
        except (ComparisonError, ResultHistoryError) as error:
            return web.json_response({"error": str(error)}, status=400)
        return web.json_response(payload)

    async def comparison_replay(request: web.Request) -> web.Response:
        try:
            result_ids = await comparison_ids(request)
            payload = await asyncio.to_thread(comparison_service.replay, result_ids)
        except ComparisonError as error:
            return web.json_response({"error": str(error)}, status=409)
        except ResultHistoryError as error:
            return web.json_response({"error": str(error)}, status=422)
        return web.json_response(payload)

    async def comparison_report(request: web.Request) -> web.Response:
        try:
            result_ids = await comparison_ids(request)
            report = await asyncio.to_thread(comparison_service.report, result_ids)
        except (ComparisonError, ResultHistoryError) as error:
            return web.json_response({"error": str(error)}, status=400)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        return web.Response(
            text=report,
            content_type="text/markdown",
            charset="utf-8",
            headers={"Content-Disposition": f'attachment; filename="comparaison_T0_4_{timestamp}.md"'},
        )

    async def websocket(request: web.Request) -> web.WebSocketResponse:
        socket = web.WebSocketResponse(heartbeat=20.0, compress=True)
        await socket.prepare(request)
        sockets.add(socket)
        try:
            async for message in socket:
                if message.type == WSMsgType.ERROR:
                    break
        finally:
            sockets.discard(socket)
        return socket

    async def broadcast() -> None:
        interval = 1.0 / max(rate_hz, 1.0)
        while True:
            if sockets:
                payload = node.snapshot()
                payload["run"] = controller.status()
                rendered = json.dumps(payload, separators=(",", ":"))
                stale: list[web.WebSocketResponse] = []
                for socket in sockets:
                    try:
                        await socket.send_str(rendered)
                    except (ConnectionResetError, RuntimeError):
                        stale.append(socket)
                for socket in stale:
                    sockets.discard(socket)
            await asyncio.sleep(interval)

    async def start_background(_application: web.Application) -> None:
        _application["broadcast_task"] = asyncio.create_task(broadcast())

    async def stop_background(_application: web.Application) -> None:
        if controller.process is not None and controller.process.returncode is None:
            await controller.stop()
        task = _application["broadcast_task"]
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

    application.router.add_get("/", index)
    application.router.add_get("/api/health", health)
    application.router.add_get("/api/snapshot", snapshot)
    application.router.add_get("/api/options", options)
    application.router.add_get("/api/run/status", run_status)
    application.router.add_post("/api/run/start", start_run)
    application.router.add_post("/api/run/stop", stop_run)
    application.router.add_get("/api/results", result_index)
    application.router.add_get("/api/results/{result_id}", result_detail)
    application.router.add_get("/api/results/{result_id}/replay", result_replay)
    application.router.add_post("/api/comparisons/preview", comparison_preview)
    application.router.add_post("/api/comparisons/replay", comparison_replay)
    application.router.add_post("/api/comparisons/report", comparison_report)
    application.router.add_get("/ws", websocket)
    application.router.add_static("/static", assets)
    application.on_startup.append(start_background)
    application.on_cleanup.append(stop_background)
    return application


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument(
        "--assets",
        type=Path,
        default=Path("software/visualization/web"),
    )
    parser.add_argument("--max-cloud-points", type=int, default=6000)
    parser.add_argument("--rate-hz", type=float, default=5.0)
    parser.add_argument(
        "--catalog",
        type=Path,
        default=Path("configs/visualization/dashboard_catalog.json"),
    )
    args = parser.parse_args()
    if not (args.assets / "index.html").is_file():
        raise FileNotFoundError(f"Dashboard assets not found: {args.assets}")
    if not args.catalog.is_file():
        raise FileNotFoundError(f"Dashboard catalog not found: {args.catalog}")

    rclpy.init()
    node = DashboardNode(args.max_cloud_points)
    workspace = Path.cwd()
    controller = RunController(workspace, args.catalog, node)
    spin_thread = threading.Thread(target=rclpy.spin, args=(node,), daemon=True)
    spin_thread.start()
    application = create_application(node, controller, args.assets, args.rate_hz)
    print(f"DASHBOARD_URL=http://localhost:{args.port}", flush=True)
    try:
        web.run_app(
            application,
            host=args.host,
            port=args.port,
            print=None,
            handle_signals=True,
        )
    finally:
        node.destroy_node()
        rclpy.shutdown()
        spin_thread.join(timeout=2.0)


if __name__ == "__main__":
    main()
