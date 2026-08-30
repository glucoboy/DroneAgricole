"""Catalogue exécutable et runners approuvés du tableau de bord T0.2."""

from __future__ import annotations

import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import yaml

from software.visualization.contracts import ContractError, DefinitionRegistry


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
LIOSAM_CANONICAL_ALIASES = {
    "odometry_surf_leaf_size": "odometrySurfLeafSize",
    "mapping_corner_leaf_size": "mappingCornerLeafSize",
    "mapping_surf_leaf_size": "mappingSurfLeafSize",
    "edge_threshold": "edgeThreshold",
    "surf_threshold": "surfThreshold",
    "mapping_process_interval": "mappingProcessInterval",
}


class RunnerRequestError(ValueError):
    """Demande refusée avant tout lancement de processus."""


def workspace_path(workspace: Path, relative: str, kind: str) -> Path:
    candidate = (workspace / relative).resolve()
    if not candidate.is_relative_to(workspace.resolve()):
        raise RunnerRequestError(f"Chemin {kind} hors du workspace.")
    return candidate


def parameter_value(definition: Mapping[str, Any], supplied: Any) -> Any:
    identifier = definition["id"]
    kind = definition["type"]
    if kind in {"number", "integer"}:
        if isinstance(supplied, bool):
            raise RunnerRequestError(f"Valeur invalide pour {identifier}.")
        try:
            number = float(supplied)
        except (TypeError, ValueError) as exc:
            raise RunnerRequestError(f"Valeur invalide pour {identifier}.") from exc
        if not math.isfinite(number):
            raise RunnerRequestError(f"{identifier} doit être un nombre fini.")
        minimum = definition.get("minimum")
        maximum = definition.get("maximum")
        if minimum is not None and number < float(minimum):
            raise RunnerRequestError(f"{identifier} doit être supérieur ou égal à {minimum:g}.")
        if maximum is not None and number > float(maximum):
            raise RunnerRequestError(f"{identifier} doit être inférieur ou égal à {maximum:g}.")
        if kind == "integer":
            if not number.is_integer():
                raise RunnerRequestError(f"{identifier} doit être un entier.")
            return int(number)
        return number
    if kind == "boolean":
        if not isinstance(supplied, bool):
            raise RunnerRequestError(f"{identifier} doit être un booléen.")
        return supplied
    if kind == "string":
        if not isinstance(supplied, str):
            raise RunnerRequestError(f"{identifier} doit être une chaîne.")
        return supplied
    if kind == "enum":
        allowed = [choice["value"] for choice in definition.get("choices", [])]
        if supplied not in allowed:
            raise RunnerRequestError(f"Valeur non autorisée pour {identifier}.")
        return supplied
    raise RunnerRequestError(f"Type de paramètre non pris en charge : {kind}.")


def write_lio_config(runner_id: str, base: Path, output: Path, parameters: Mapping[str, Any]) -> None:
    try:
        configuration = yaml.safe_load(base.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise RunnerRequestError(f"Configuration LIO illisible : {base}") from exc
    normalized = dict(parameters)
    if runner_id == "lio_sam":
        for canonical, native in LIOSAM_CANONICAL_ALIASES.items():
            if canonical in normalized:
                normalized[native] = normalized[canonical]
    paths = {
        "fast_lio2": FASTLIO_PARAMETER_PATHS,
        "point_lio": POINTLIO_PARAMETER_PATHS,
        "lio_sam": LIOSAM_PARAMETER_PATHS,
    }.get(runner_id)
    if paths is None:
        raise RunnerRequestError(f"Runner LIO inconnu : {runner_id}.")
    try:
        for identifier, key_path in paths.items():
            if identifier not in normalized:
                continue
            target = configuration
            for key in key_path[:-1]:
                target = target[key]
            target[key_path[-1]] = normalized[identifier]
        if runner_id in {"fast_lio2", "point_lio"}:
            configuration["/**"]["ros__parameters"]["publish"]["scan_publish_en"] = True
    except (KeyError, TypeError) as exc:
        raise RunnerRequestError(f"Structure inattendue dans la configuration {base}.") from exc
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(yaml.safe_dump(configuration, sort_keys=False, allow_unicode=True), encoding="utf-8")


@dataclass(frozen=True)
class PreparedRun:
    run_id: str
    simulation_id: str
    simulation_label: str
    variant_id: str
    variant_label: str
    runner_id: str
    domain: str
    safety_class: str
    parameters: dict[str, Any]
    inputs: list[dict[str, Any]]
    profile_id: str | None
    dataset_id: str | None
    dataset_label: str | None
    sequence_id: str | None
    sequence_label: str | None
    result_directory: Path
    command: tuple[str, ...]
    environment: Mapping[str, str]
    runtime_files: tuple[Path, ...]
    pipeline_topic: str | None
    analysis_kind: str

    def public_status(self, workspace: Path) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "simulation_id": self.simulation_id,
            "simulation_label": self.simulation_label,
            "variant_id": self.variant_id,
            "variant_label": self.variant_label,
            "runner_id": self.runner_id,
            "domain": self.domain,
            "safety_class": self.safety_class,
            "profile_id": self.profile_id,
            "dataset_id": self.dataset_id,
            "dataset_label": self.dataset_label,
            "sequence_id": self.sequence_id,
            "sequence_label": self.sequence_label,
            "algorithm_id": self.variant_id if self.simulation_id == "lio_benchmark" else None,
            "algorithm_label": self.variant_label if self.simulation_id == "lio_benchmark" else None,
            "parameters": self.parameters,
            "pipeline_topic": self.pipeline_topic,
            "result_directory": self.result_directory.relative_to(workspace).as_posix(),
        }


class ApprovedRunner:
    runner_ids: frozenset[str] = frozenset()

    def prepare(self, resolved: Mapping[str, Any], workspace: Path, run_id: str, stamp: str) -> PreparedRun:
        raise NotImplementedError


class LioRunner(ApprovedRunner):
    runner_ids = frozenset({"fast_lio2", "point_lio", "lio_sam"})
    scripts = {
        "fast_lio2": "tools/benchmarks/run_fastlio2_botanicgarden_benchmark.sh",
        "point_lio": "tools/benchmarks/run_pointlio_botanicgarden_benchmark.sh",
        "lio_sam": "tools/benchmarks/run_liosam_botanicgarden_benchmark.sh",
    }

    def prepare(self, resolved: Mapping[str, Any], workspace: Path, run_id: str, stamp: str) -> PreparedRun:
        runner_id = resolved["variant"]["runner_id"]
        if runner_id not in self.runner_ids:
            raise RunnerRequestError("Runner LIO non approuvé.")
        sequence = resolved["sequence"]
        profile = resolved["profile"]
        settings = profile["variant_settings"].get(resolved["variant"]["variant_id"])
        if not settings:
            raise RunnerRequestError("Ce profil ne prend pas en charge la variante sélectionnée.")
        rosbag_resources = [resource for resource in sequence["resources"] if resource["kind"] in {"rosbag2", "mcap"}]
        if len(rosbag_resources) != 1:
            raise RunnerRequestError("La séquence doit fournir exactement un rosbag exécutable.")
        bag_path = workspace_path(workspace, rosbag_resources[0]["uri"], "dataset")
        config_path = workspace_path(workspace, settings["base_config_uri"], "configuration")
        if not bag_path.is_dir():
            raise RunnerRequestError(f"Dataset absent : {rosbag_resources[0]['uri']}")
        if not config_path.is_file():
            raise RunnerRequestError(f"Configuration absente : {settings['base_config_uri']}")
        result_group = sequence.get("result_group") or f"{resolved['dataset']['dataset_id']}_{sequence['source_sequence_id']}"
        result_relative = Path("results/benchmarks") / resolved["variant"]["variant_id"] / result_group / f"dashboard_{stamp}_{run_id}"
        result_directory = workspace_path(workspace, result_relative.as_posix(), "résultat")
        runtime_config = workspace_path(workspace, f".runtime/dashboard/{run_id}.yaml", "configuration temporaire")
        write_lio_config(runner_id, config_path, runtime_config, resolved["parameters"])
        command = (
            "bash",
            self.scripts[runner_id],
            bag_path.relative_to(workspace).as_posix(),
            result_directory.relative_to(workspace).as_posix(),
            runtime_config.relative_to(workspace).as_posix(),
            str(resolved["parameters"]["playback_rate"]),
        )
        environment = os.environ.copy()
        environment.update({"FASTLIO_DASHBOARD": "1", "LIO_DASHBOARD": "1"})
        return _prepared_common(
            resolved,
            run_id,
            result_directory,
            command,
            environment,
            (runtime_config,),
            settings.get("pipeline_topic"),
            "lio_trajectory",
        )


class Px4OffboardRunner(ApprovedRunner):
    runner_ids = frozenset({"px4_square", "px4_failsafe"})

    def prepare(self, resolved: Mapping[str, Any], workspace: Path, run_id: str, stamp: str) -> PreparedRun:
        runner_id = resolved["variant"]["runner_id"]
        if runner_id not in self.runner_ids:
            raise RunnerRequestError("Runner PX4 non approuvé.")
        mode = resolved["variant"]["variant_id"]
        result_relative = Path("results/simulation/px4_lot_a") / f"{mode}_{stamp}_{run_id}"
        result_directory = workspace_path(workspace, result_relative.as_posix(), "résultat")
        remote_url = os.environ.get("DRONE_AGRICOLE_PX4_RUNNER_URL", "http://px4-runner-api:8091")
        parameters = resolved["parameters"]
        command = (
            "python3",
            "tools/visualization/px4_remote_client.py",
            "--url",
            remote_url,
            "--run-id",
            run_id,
            "--mode",
            mode,
            "--result-directory",
            result_relative.as_posix(),
            "--takeoff-altitude-m",
            str(parameters["takeoff_altitude_m"]),
            "--leg-m",
            str(parameters["leg_m"]),
            "--warmup-s",
            str(parameters["warmup_s"]),
            "--hover-s",
            str(parameters["hover_s"]),
            "--stage-timeout-s",
            str(parameters["stage_timeout_s"]),
        )
        return _prepared_common(
            resolved,
            run_id,
            result_directory,
            command,
            os.environ.copy(),
            (),
            None,
            "px4_result",
        )


def _prepared_common(
    resolved: Mapping[str, Any],
    run_id: str,
    result_directory: Path,
    command: tuple[str, ...],
    environment: Mapping[str, str],
    runtime_files: tuple[Path, ...],
    pipeline_topic: str | None,
    analysis_kind: str,
) -> PreparedRun:
    dataset = resolved.get("dataset")
    sequence = resolved.get("sequence")
    profile = resolved.get("profile")
    simulation = resolved["simulation"]
    variant = resolved["variant"]
    return PreparedRun(
        run_id=run_id,
        simulation_id=simulation["simulation_id"],
        simulation_label=simulation["label"],
        variant_id=variant["variant_id"],
        variant_label=variant["label"],
        runner_id=variant["runner_id"],
        domain=simulation["domain"],
        safety_class=simulation["safety_class"],
        parameters=dict(resolved["parameters"]),
        inputs=list(resolved["inputs"]),
        profile_id=profile["profile_id"] if profile else None,
        dataset_id=dataset["dataset_id"] if dataset else None,
        dataset_label=dataset["label"] if dataset else None,
        sequence_id=sequence["sequence_id"] if sequence else None,
        sequence_label=sequence["label"] if sequence else None,
        result_directory=result_directory,
        command=command,
        environment=environment,
        runtime_files=runtime_files,
        pipeline_topic=pipeline_topic,
        analysis_kind=analysis_kind,
    )


class RunnerRegistry:
    def __init__(self, definitions: DefinitionRegistry, workspace: Path) -> None:
        self.definitions = definitions
        self.workspace = workspace.resolve()
        adapters = (LioRunner(), Px4OffboardRunner())
        self.adapters = {runner_id: adapter for adapter in adapters for runner_id in adapter.runner_ids}

    def public_options(self) -> dict[str, Any]:
        datasets = []
        for definition in self.definitions.datasets.values():
            dataset = _clone(definition)
            for sequence in dataset["sequences"]:
                availability = []
                for resource in sequence["resources"]:
                    path = workspace_path(self.workspace, resource["uri"], "ressource")
                    exists = path.exists()
                    resource["available"] = exists
                    availability.append(exists or not resource["required"])
                sequence["available"] = all(availability)
            datasets.append(dataset)
        simulations = [_clone(value) for value in self.definitions.simulations.values()]
        compatibility = {
            simulation_id: {
                variant["variant_id"]: self.definitions.compatible_dataset_sequences(simulation_id, variant["variant_id"])
                for variant in simulation["variants"]
            }
            for simulation_id, simulation in self.definitions.simulations.items()
        }
        for variants in compatibility.values():
            for sequences in variants.values():
                for sequence in sequences:
                    dataset = next(value for value in datasets if value["dataset_id"] == sequence["dataset_id"])
                    definition = next(value for value in dataset["sequences"] if value["sequence_id"] == sequence["sequence_id"])
                    sequence["available"] = definition["available"]
        for simulation_id, variants in compatibility.items():
            simulation = self.definitions.simulations[simulation_id]
            for variant_id, sequences in variants.items():
                for sequence in sequences:
                    dataset = self.definitions.datasets[sequence["dataset_id"]]
                    sequence_definition = next(
                        value for value in dataset["sequences"] if value["sequence_id"] == sequence["sequence_id"]
                    )
                    try:
                        profile = self._select_profile(
                            simulation,
                            variant_id,
                            dataset,
                            sequence_definition,
                            None,
                        )
                        sequence["profile_ids"] = [profile["profile_id"]] if profile else []
                        sequence["runnable"] = bool(sequence["available"])
                    except RunnerRequestError:
                        sequence["profile_ids"] = []
                        sequence["runnable"] = False
        return {
            "schema": "drone_agricole.dashboard_options.v2",
            "datasets": datasets,
            "simulations": simulations,
            "compatibility": compatibility,
            "single_active_run": True,
        }

    def resolve(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        simulation_id = str(payload.get("simulation_id") or ("lio_benchmark" if payload.get("algorithm_id") else ""))
        variant_id = str(payload.get("variant_id") or payload.get("algorithm_id") or "")
        simulation = self.definitions.simulations.get(simulation_id)
        if simulation is None:
            raise RunnerRequestError(f"Simulation inconnue : {simulation_id}")
        variants = [value for value in simulation["variants"] if value["variant_id"] == variant_id]
        if not variants:
            raise RunnerRequestError(f"Variante inconnue : {variant_id}")
        variant = variants[0]
        if not variant["available"]:
            raise RunnerRequestError(f"{variant['label']} n'est pas disponible.")
        if variant["runner_id"] not in self.adapters:
            raise RunnerRequestError(f"Aucun runner approuvé pour {variant['runner_id']}.")

        dataset = None
        sequence = None
        inputs: list[dict[str, Any]] = []
        dataset_selectors = [value for value in simulation["selectors"] if value["kind"] == "dataset_sequence" and value["required"]]
        if dataset_selectors:
            dataset_id, sequence_id = _dataset_selection(payload)
            dataset = self.definitions.datasets.get(dataset_id)
            if dataset is None:
                raise RunnerRequestError(f"Dataset inconnu : {dataset_id}")
            sequences = [value for value in dataset["sequences"] if value["sequence_id"] == sequence_id]
            if not sequences:
                raise RunnerRequestError(f"Séquence inconnue : {sequence_id}")
            sequence = sequences[0]
            compatible = self.definitions.compatible_dataset_sequences(simulation_id, variant_id)
            if not any(value["dataset_id"] == dataset_id and value["sequence_id"] == sequence_id for value in compatible):
                raise RunnerRequestError("Cette séquence n'est pas compatible avec la simulation sélectionnée.")
            inputs.append({"input_id": dataset_selectors[0]["selector_id"], "kind": "dataset_sequence", "reference": {"dataset_id": dataset_id, "sequence_id": sequence_id}})
        elif payload.get("inputs") not in (None, []):
            raise RunnerRequestError("Cette simulation n'accepte pas d'entrée sélectionnable.")

        profile = self._select_profile(simulation, variant_id, dataset, sequence, payload.get("profile_id"))
        definitions = [*simulation.get("parameters", []), *variant.get("parameters", [])]
        supplied = payload.get("parameters") or {}
        if not isinstance(supplied, Mapping):
            raise RunnerRequestError("Le bloc parameters doit être un objet.")
        allowed = {definition["id"] for definition in definitions}
        unexpected = sorted(set(supplied) - allowed)
        if unexpected:
            raise RunnerRequestError(f"Paramètre inconnu : {unexpected[0]}")
        defaults = profile["variant_settings"][variant_id].get("default_parameters", {}) if profile else {}
        parameters = {
            definition["id"]: parameter_value(
                definition,
                supplied.get(definition["id"], defaults.get(definition["id"], definition["default"])),
            )
            for definition in definitions
        }
        return {
            "simulation": simulation,
            "variant": variant,
            "dataset": dataset,
            "sequence": sequence,
            "profile": profile,
            "parameters": parameters,
            "inputs": inputs,
        }

    def prepare(self, payload: Mapping[str, Any], run_id: str, stamp: str) -> PreparedRun:
        resolved = self.resolve(payload)
        adapter = self.adapters[resolved["variant"]["runner_id"]]
        return adapter.prepare(resolved, self.workspace, run_id, stamp)

    @staticmethod
    def _select_profile(
        simulation: Mapping[str, Any],
        variant_id: str,
        dataset: Mapping[str, Any] | None,
        sequence: Mapping[str, Any] | None,
        requested_profile: Any,
    ) -> Mapping[str, Any] | None:
        profiles = simulation.get("profiles", [])
        if not profiles:
            if requested_profile not in (None, ""):
                raise RunnerRequestError("Cette simulation n'utilise pas de profil.")
            return None
        compatible = []
        for profile in profiles:
            selectors = profile["selectors"]
            if dataset and selectors.get("dataset_id") not in (None, dataset["dataset_id"]):
                continue
            sequence_ids = selectors.get("sequence_ids", [])
            if sequence and sequence_ids and sequence["sequence_id"] not in sequence_ids:
                continue
            if variant_id not in profile["variant_settings"]:
                continue
            compatible.append(profile)
        if requested_profile:
            compatible = [profile for profile in compatible if profile["profile_id"] == requested_profile]
        if not compatible:
            raise RunnerRequestError("Aucun profil dataset–variante compatible n'est disponible.")
        defaults = [profile for profile in compatible if profile.get("default")]
        return (defaults or compatible)[0]


def _dataset_selection(payload: Mapping[str, Any]) -> tuple[str, str]:
    dataset_id = payload.get("dataset_id")
    sequence_id = payload.get("sequence_id")
    if dataset_id and sequence_id:
        return str(dataset_id), str(sequence_id)
    inputs = payload.get("inputs")
    if isinstance(inputs, list):
        for value in inputs:
            if isinstance(value, Mapping) and value.get("kind") == "dataset_sequence":
                reference = value.get("reference")
                if isinstance(reference, Mapping):
                    return str(reference.get("dataset_id", "")), str(reference.get("sequence_id", ""))
    raise RunnerRequestError("Une séquence de dataset doit être sélectionnée.")


def _clone(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _clone(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_clone(item) for item in value]
    return value
