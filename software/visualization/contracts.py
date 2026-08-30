"""Contrats versionnés du tableau de bord Drone Agricole.

Le validateur est volontairement limité à la bibliothèque standard : les schémas
JSON publiés restent la référence d'échange, tandis que ces contrôles sémantiques
sont utilisables aussi bien sur l'hôte que dans les conteneurs existants.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Iterable, Mapping


IDENTIFIER_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,95}$")
CAPABILITY_RE = re.compile(r"^[a-z][a-z0-9_-]*(?:\.[a-z0-9_-]+)+$")
SEMVER_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
SCHEMA_RE = re.compile(r"^drone_agricole\.[a-z0-9_.-]+\.v[1-9][0-9]*$")


class ContractError(ValueError):
    """Erreur de contrat avec un chemin précis vers la donnée fautive."""


def _fail(path: str, message: str) -> None:
    raise ContractError(f"{path}: {message}")


def _mapping(value: Any, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        _fail(path, "un objet JSON est attendu")
    return value


def _list(value: Any, path: str, *, non_empty: bool = False) -> list[Any]:
    if not isinstance(value, list):
        _fail(path, "une liste JSON est attendue")
    if non_empty and not value:
        _fail(path, "la liste ne doit pas être vide")
    return value


def _required(obj: Mapping[str, Any], fields: Iterable[str], path: str) -> None:
    missing = [field for field in fields if field not in obj]
    if missing:
        _fail(path, f"champs requis absents : {', '.join(missing)}")


def _string(value: Any, path: str, *, non_empty: bool = True) -> str:
    if not isinstance(value, str) or (non_empty and not value.strip()):
        _fail(path, "une chaîne non vide est attendue")
    return value


def _identifier(value: Any, path: str) -> str:
    text = _string(value, path)
    if not IDENTIFIER_RE.fullmatch(text):
        _fail(path, "identifiant invalide (minuscules, chiffres, '_' et '-' uniquement)")
    return text


def _capability(value: Any, path: str) -> str:
    text = _string(value, path)
    if len(text) > 128 or not CAPABILITY_RE.fullmatch(text):
        _fail(path, "capacité invalide (forme attendue : domaine.capacite)")
    return text


def _unique_strings(values: Any, path: str, validator: Callable[[Any, str], str]) -> list[str]:
    result = [validator(value, f"{path}[{index}]") for index, value in enumerate(_list(values, path))]
    if len(result) != len(set(result)):
        _fail(path, "les valeurs doivent être uniques")
    return result


def _enum(value: Any, allowed: Iterable[str], path: str) -> str:
    text = _string(value, path)
    allowed_set = set(allowed)
    if text not in allowed_set:
        _fail(path, f"valeur '{text}' non autorisée ; attendu : {', '.join(sorted(allowed_set))}")
    return text


def _boolean(value: Any, path: str) -> bool:
    if not isinstance(value, bool):
        _fail(path, "un booléen est attendu")
    return value


def _number(value: Any, path: str, *, minimum: float | None = None, exclusive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        _fail(path, "un nombre fini est attendu")
    number = float(value)
    if minimum is not None and (number <= minimum if exclusive else number < minimum):
        operator = ">" if exclusive else ">="
        _fail(path, f"la valeur doit être {operator} {minimum}")
    return number


def _timestamp(value: Any, path: str) -> str:
    text = _string(value, path)
    candidate = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise ContractError(f"{path}: horodatage ISO 8601 invalide") from exc
    if parsed.tzinfo is None:
        _fail(path, "l'horodatage doit inclure un fuseau horaire")
    return text


def _relative_path(value: Any, path: str) -> str:
    text = _string(value, path)
    if "\\" in text:
        _fail(path, "utiliser un chemin relatif POSIX avec des '/'")
    pure = PurePosixPath(text)
    if pure.is_absolute() or re.match(r"^[A-Za-z]:", text) or ".." in pure.parts:
        _fail(path, "un chemin relatif contenu dans le projet est attendu")
    return text


def _schema(obj: Mapping[str, Any], expected: str, path: str) -> None:
    actual = obj.get("schema")
    if actual != expected:
        _fail(f"{path}.schema", f"'{expected}' attendu, reçu {actual!r}")


def _input_reference(value: Any, path: str) -> None:
    obj = _mapping(value, path)
    _required(obj, ("input_id", "kind", "reference"), path)
    _identifier(obj["input_id"], f"{path}.input_id")
    _enum(obj["kind"], ("dataset_sequence", "map", "mission", "model", "calibration", "scenario", "other"), f"{path}.kind")
    _mapping(obj["reference"], f"{path}.reference")
    if "checksums" in obj:
        checksums = _mapping(obj["checksums"], f"{path}.checksums")
        for name, checksum in checksums.items():
            _string(name, f"{path}.checksums.<clé>")
            _string(checksum, f"{path}.checksums.{name}")


def _parameter_definition(value: Any, path: str) -> None:
    obj = _mapping(value, path)
    _required(obj, ("id", "label", "description", "type", "group", "safety_class", "default"), path)
    _identifier(obj["id"], f"{path}.id")
    _string(obj["label"], f"{path}.label")
    _string(obj["description"], f"{path}.description")
    parameter_type = _enum(obj["type"], ("number", "integer", "boolean", "string", "enum"), f"{path}.type")
    _enum(obj["group"], ("principal", "advanced", "structural", "safety", "derived"), f"{path}.group")
    _enum(obj["safety_class"], ("analysis", "simulation", "sitl_confirmed", "read_only"), f"{path}.safety_class")
    default = obj["default"]
    if parameter_type == "number":
        default_number = _number(default, f"{path}.default")
    elif parameter_type == "integer":
        if isinstance(default, bool) or not isinstance(default, int):
            _fail(f"{path}.default", "un entier est attendu")
        default_number = float(default)
    elif parameter_type == "boolean":
        _boolean(default, f"{path}.default")
        default_number = None
    elif parameter_type in ("string", "enum"):
        _string(default, f"{path}.default", non_empty=False)
        default_number = None
    else:  # pragma: no cover - protégé par _enum
        default_number = None
    minimum = _number(obj["minimum"], f"{path}.minimum") if "minimum" in obj else None
    maximum = _number(obj["maximum"], f"{path}.maximum") if "maximum" in obj else None
    if minimum is not None and maximum is not None and minimum > maximum:
        _fail(path, "minimum doit être inférieur ou égal à maximum")
    if default_number is not None:
        if minimum is not None and default_number < minimum:
            _fail(f"{path}.default", "valeur inférieure au minimum")
        if maximum is not None and default_number > maximum:
            _fail(f"{path}.default", "valeur supérieure au maximum")
    if "step" in obj:
        _number(obj["step"], f"{path}.step", minimum=0, exclusive=True)
    if "runner_key" in obj:
        _string(obj["runner_key"], f"{path}.runner_key")
    if parameter_type == "enum":
        choices = _list(obj.get("choices"), f"{path}.choices", non_empty=True)
        choice_values = []
        for index, choice_value in enumerate(choices):
            choice = _mapping(choice_value, f"{path}.choices[{index}]")
            _required(choice, ("value", "label"), f"{path}.choices[{index}]")
            choice_values.append(choice["value"])
            _string(choice["label"], f"{path}.choices[{index}].label")
        if default not in choice_values:
            _fail(f"{path}.default", "la valeur par défaut ne figure pas dans choices")


def validate_dataset_definition(payload: Any) -> Mapping[str, Any]:
    obj = _mapping(payload, "dataset")
    _schema(obj, "drone_agricole.dataset_definition.v1", "dataset")
    _required(obj, ("dataset_id", "label", "description", "status", "platform", "environment", "license", "capabilities", "sequences"), "dataset")
    _identifier(obj["dataset_id"], "dataset.dataset_id")
    _string(obj["label"], "dataset.label")
    _string(obj["description"], "dataset.description")
    _enum(obj["status"], ("installed", "partial", "remote", "candidate", "disabled"), "dataset.status")
    _enum(obj["platform"], ("ground_robot", "aerial_robot", "simulator", "handheld", "mixed", "unknown"), "dataset.platform")
    _string(obj["environment"], "dataset.environment")
    license_info = _mapping(obj["license"], "dataset.license")
    _required(license_info, ("status", "redistribution"), "dataset.license")
    _enum(license_info["status"], ("verified", "to_validate", "restricted", "unknown"), "dataset.license.status")
    _enum(license_info["redistribution"], ("allowed", "forbidden", "to_validate"), "dataset.license.redistribution")
    _unique_strings(obj["capabilities"], "dataset.capabilities", _capability)
    sequence_ids: set[str] = set()
    for index, sequence_value in enumerate(_list(obj["sequences"], "dataset.sequences", non_empty=True)):
        path = f"dataset.sequences[{index}]"
        sequence = _mapping(sequence_value, path)
        _required(sequence, ("sequence_id", "source_sequence_id", "label", "status", "duration_s", "capabilities", "resources"), path)
        sequence_id = _identifier(sequence["sequence_id"], f"{path}.sequence_id")
        if sequence_id in sequence_ids:
            _fail(f"{path}.sequence_id", "identifiant de séquence dupliqué")
        sequence_ids.add(sequence_id)
        _string(sequence["source_sequence_id"], f"{path}.source_sequence_id")
        _string(sequence["label"], f"{path}.label")
        _enum(sequence["status"], ("installed", "partial", "remote", "disabled"), f"{path}.status")
        _number(sequence["duration_s"], f"{path}.duration_s", minimum=0, exclusive=True)
        _unique_strings(sequence["capabilities"], f"{path}.capabilities", _capability)
        resource_ids: set[str] = set()
        for resource_index, resource_value in enumerate(_list(sequence["resources"], f"{path}.resources", non_empty=True)):
            resource_path = f"{path}.resources[{resource_index}]"
            resource = _mapping(resource_value, resource_path)
            _required(resource, ("resource_id", "kind", "uri", "required"), resource_path)
            resource_id = _identifier(resource["resource_id"], f"{resource_path}.resource_id")
            if resource_id in resource_ids:
                _fail(f"{resource_path}.resource_id", "identifiant de ressource dupliqué")
            resource_ids.add(resource_id)
            _enum(resource["kind"], ("rosbag1", "rosbag2", "mcap", "images", "annotations", "calibration", "ground_truth", "map", "other"), f"{resource_path}.kind")
            _relative_path(resource["uri"], f"{resource_path}.uri")
            _boolean(resource["required"], f"{resource_path}.required")
    return obj


def validate_simulation_definition(payload: Any) -> Mapping[str, Any]:
    obj = _mapping(payload, "simulation")
    _schema(obj, "drone_agricole.simulation_definition.v1", "simulation")
    _required(obj, ("simulation_id", "version", "label", "description", "domain", "runner_id", "safety_class", "selectors", "variants", "parameters", "outputs", "visualization", "comparison_group"), "simulation")
    _identifier(obj["simulation_id"], "simulation.simulation_id")
    if not SEMVER_RE.fullmatch(_string(obj["version"], "simulation.version")):
        _fail("simulation.version", "version sémantique X.Y.Z attendue")
    for field in ("label", "description"):
        _string(obj[field], f"simulation.{field}")
    for field in ("domain", "runner_id", "comparison_group"):
        _identifier(obj[field], f"simulation.{field}")
    _enum(obj["safety_class"], ("analysis", "simulation", "sitl_confirmed", "hardware_restricted"), "simulation.safety_class")
    selector_ids: set[str] = set()
    for index, selector_value in enumerate(_list(obj["selectors"], "simulation.selectors")):
        path = f"simulation.selectors[{index}]"
        selector = _mapping(selector_value, path)
        _required(selector, ("selector_id", "kind", "required", "multiple", "required_capabilities"), path)
        selector_id = _identifier(selector["selector_id"], f"{path}.selector_id")
        if selector_id in selector_ids:
            _fail(f"{path}.selector_id", "sélecteur dupliqué")
        selector_ids.add(selector_id)
        _enum(selector["kind"], ("dataset_sequence", "map", "mission", "model", "calibration", "scenario", "other"), f"{path}.kind")
        _boolean(selector["required"], f"{path}.required")
        _boolean(selector["multiple"], f"{path}.multiple")
        _unique_strings(selector["required_capabilities"], f"{path}.required_capabilities", _capability)
    variant_ids: set[str] = set()
    for index, variant_value in enumerate(_list(obj["variants"], "simulation.variants", non_empty=True)):
        path = f"simulation.variants[{index}]"
        variant = _mapping(variant_value, path)
        _required(variant, ("variant_id", "label", "runner_id", "available", "required_capabilities", "parameters"), path)
        variant_id = _identifier(variant["variant_id"], f"{path}.variant_id")
        if variant_id in variant_ids:
            _fail(f"{path}.variant_id", "variante dupliquée")
        variant_ids.add(variant_id)
        _string(variant["label"], f"{path}.label")
        _identifier(variant["runner_id"], f"{path}.runner_id")
        _boolean(variant["available"], f"{path}.available")
        _unique_strings(variant["required_capabilities"], f"{path}.required_capabilities", _capability)
        if "base_config_uri" in variant:
            _relative_path(variant["base_config_uri"], f"{path}.base_config_uri")
        _validate_parameters(variant["parameters"], f"{path}.parameters")
    _validate_parameters(obj["parameters"], "simulation.parameters")
    profile_ids: set[str] = set()
    for index, profile_value in enumerate(_list(obj.get("profiles", []), "simulation.profiles")):
        path = f"simulation.profiles[{index}]"
        profile = _mapping(profile_value, path)
        _required(profile, ("profile_id", "label", "selectors", "variant_settings"), path)
        profile_id = _identifier(profile["profile_id"], f"{path}.profile_id")
        if profile_id in profile_ids:
            _fail(f"{path}.profile_id", "profil dupliqué")
        profile_ids.add(profile_id)
        _string(profile["label"], f"{path}.label")
        selectors = _mapping(profile["selectors"], f"{path}.selectors")
        if "dataset_id" in selectors:
            _identifier(selectors["dataset_id"], f"{path}.selectors.dataset_id")
        if "sequence_ids" in selectors:
            _unique_strings(selectors["sequence_ids"], f"{path}.selectors.sequence_ids", _identifier)
        settings = _mapping(profile["variant_settings"], f"{path}.variant_settings")
        for variant_id, setting_value in settings.items():
            _identifier(variant_id, f"{path}.variant_settings.<clé>")
            if variant_id not in variant_ids:
                _fail(f"{path}.variant_settings.{variant_id}", "variante inconnue")
            setting = _mapping(setting_value, f"{path}.variant_settings.{variant_id}")
            _required(setting, ("base_config_uri",), f"{path}.variant_settings.{variant_id}")
            _relative_path(setting["base_config_uri"], f"{path}.variant_settings.{variant_id}.base_config_uri")
            if "pipeline_topic" in setting:
                topic = _string(setting["pipeline_topic"], f"{path}.variant_settings.{variant_id}.pipeline_topic")
                if not topic.startswith("/"):
                    _fail(f"{path}.variant_settings.{variant_id}.pipeline_topic", "un topic ROS absolu est attendu")
            if "default_parameters" in setting:
                _mapping(setting["default_parameters"], f"{path}.variant_settings.{variant_id}.default_parameters")
    for index, output_value in enumerate(_list(obj["outputs"], "simulation.outputs")):
        path = f"simulation.outputs[{index}]"
        output = _mapping(output_value, path)
        _required(output, ("output_id", "kind", "required"), path)
        _identifier(output["output_id"], f"{path}.output_id")
        _identifier(output["kind"], f"{path}.kind")
        _boolean(output["required"], f"{path}.required")
    visualization = _mapping(obj["visualization"], "simulation.visualization")
    _required(visualization, ("live", "replay", "layers", "charts"), "simulation.visualization")
    _boolean(visualization["live"], "simulation.visualization.live")
    _boolean(visualization["replay"], "simulation.visualization.replay")
    _list(visualization["layers"], "simulation.visualization.layers")
    _list(visualization["charts"], "simulation.visualization.charts")
    return obj


def _validate_parameters(values: Any, path: str) -> None:
    parameter_ids: set[str] = set()
    for index, value in enumerate(_list(values, path)):
        item_path = f"{path}[{index}]"
        _parameter_definition(value, item_path)
        parameter_id = value["id"]
        if parameter_id in parameter_ids:
            _fail(f"{item_path}.id", "paramètre dupliqué")
        parameter_ids.add(parameter_id)


def validate_run_request(payload: Any) -> Mapping[str, Any]:
    obj = _mapping(payload, "run_request")
    _schema(obj, "drone_agricole.run_request.v1", "run_request")
    _required(obj, ("request_id", "simulation_id", "variant_id", "requested_at_utc", "inputs", "parameters"), "run_request")
    for field in ("request_id", "simulation_id", "variant_id"):
        _identifier(obj[field], f"run_request.{field}")
    _timestamp(obj["requested_at_utc"], "run_request.requested_at_utc")
    for index, value in enumerate(_list(obj["inputs"], "run_request.inputs")):
        _input_reference(value, f"run_request.inputs[{index}]")
    _mapping(obj["parameters"], "run_request.parameters")
    return obj


def validate_run_manifest(payload: Any) -> Mapping[str, Any]:
    obj = _mapping(payload, "run_manifest")
    _schema(obj, "drone_agricole.run_manifest.v1", "run_manifest")
    _required(obj, ("run_id", "simulation_id", "variant_id", "runner_id", "domain", "state", "created_at_utc", "inputs", "parameters", "software", "files", "compatibility"), "run_manifest")
    for field in ("run_id", "simulation_id", "variant_id", "runner_id", "domain"):
        _identifier(obj[field], f"run_manifest.{field}")
    _enum(obj["state"], ("queued", "preparing", "running", "stopping", "analyzing", "completed", "cancelled", "failed", "abandoned"), "run_manifest.state")
    for field in ("created_at_utc", "started_at_utc", "finished_at_utc"):
        if obj.get(field) is not None:
            _timestamp(obj[field], f"run_manifest.{field}")
    for index, value in enumerate(_list(obj["inputs"], "run_manifest.inputs")):
        _input_reference(value, f"run_manifest.inputs[{index}]")
    _mapping(obj["parameters"], "run_manifest.parameters")
    _mapping(obj["software"], "run_manifest.software")
    for name, value in _mapping(obj["files"], "run_manifest.files").items():
        _identifier(name, "run_manifest.files.<clé>")
        if value is not None:
            _relative_path(value, f"run_manifest.files.{name}")
    compatibility = _mapping(obj["compatibility"], "run_manifest.compatibility")
    _required(compatibility, ("comparison_group",), "run_manifest.compatibility")
    _identifier(compatibility["comparison_group"], "run_manifest.compatibility.comparison_group")
    return obj


def validate_metrics(payload: Any) -> Mapping[str, Any]:
    obj = _mapping(payload, "metrics")
    _schema(obj, "drone_agricole.metrics.v1", "metrics")
    _required(obj, ("run_id", "simulation_id", "status", "summary", "groups"), "metrics")
    _identifier(obj["run_id"], "metrics.run_id")
    _identifier(obj["simulation_id"], "metrics.simulation_id")
    _enum(obj["status"], ("complete", "partial", "unavailable", "invalid"), "metrics.status")
    metric_ids: set[str] = set()
    for index, value in enumerate(_list(obj["summary"], "metrics.summary")):
        path = f"metrics.summary[{index}]"
        metric = _mapping(value, path)
        _required(metric, ("metric_id", "label", "value", "unit", "direction", "status"), path)
        metric_id = _identifier(metric["metric_id"], f"{path}.metric_id")
        if metric_id in metric_ids:
            _fail(f"{path}.metric_id", "métrique dupliquée")
        metric_ids.add(metric_id)
        _string(metric["label"], f"{path}.label")
        if isinstance(metric["value"], float) and not math.isfinite(metric["value"]):
            _fail(f"{path}.value", "la valeur doit être finie")
        _string(metric["unit"], f"{path}.unit", non_empty=False)
        _enum(metric["direction"], ("lower", "higher", "target", "neutral"), f"{path}.direction")
        _enum(metric["status"], ("good", "warning", "error", "unknown"), f"{path}.status")
    _mapping(obj["groups"], "metrics.groups")
    return obj


def validate_artifacts(payload: Any) -> Mapping[str, Any]:
    obj = _mapping(payload, "artifacts")
    _schema(obj, "drone_agricole.artifacts.v1", "artifacts")
    _required(obj, ("run_id", "items"), "artifacts")
    _identifier(obj["run_id"], "artifacts.run_id")
    artifact_ids: set[str] = set()
    for index, value in enumerate(_list(obj["items"], "artifacts.items")):
        path = f"artifacts.items[{index}]"
        artifact = _mapping(value, path)
        _required(artifact, ("artifact_id", "kind", "label", "path", "media_type", "role", "replayable"), path)
        artifact_id = _identifier(artifact["artifact_id"], f"{path}.artifact_id")
        if artifact_id in artifact_ids:
            _fail(f"{path}.artifact_id", "artefact dupliqué")
        artifact_ids.add(artifact_id)
        _enum(artifact["kind"], ("manifest", "metrics", "configuration", "rosbag", "point_cloud", "trajectory", "image", "map", "model", "log", "report", "events", "other"), f"{path}.kind")
        _string(artifact["label"], f"{path}.label")
        _relative_path(artifact["path"], f"{path}.path")
        _string(artifact["media_type"], f"{path}.media_type")
        _enum(artifact["role"], ("input", "output", "diagnostic", "visualization", "source"), f"{path}.role")
        _boolean(artifact["replayable"], f"{path}.replayable")
    return obj


def validate_event(payload: Any) -> Mapping[str, Any]:
    obj = _mapping(payload, "event")
    _schema(obj, "drone_agricole.event.v1", "event")
    _required(obj, ("run_id", "sequence", "event_type", "severity", "message", "data"), "event")
    _identifier(obj["run_id"], "event.run_id")
    if isinstance(obj["sequence"], bool) or not isinstance(obj["sequence"], int) or obj["sequence"] < 0:
        _fail("event.sequence", "un entier positif ou nul est attendu")
    _identifier(obj["event_type"], "event.event_type")
    _enum(obj["severity"], ("debug", "info", "warning", "error", "critical"), "event.severity")
    _string(obj["message"], "event.message", non_empty=False)
    _mapping(obj["data"], "event.data")
    if "timestamp_utc" not in obj and "elapsed_s" not in obj:
        _fail("event", "timestamp_utc ou elapsed_s est requis")
    if "timestamp_utc" in obj:
        _timestamp(obj["timestamp_utc"], "event.timestamp_utc")
    if "elapsed_s" in obj:
        _number(obj["elapsed_s"], "event.elapsed_s", minimum=0)
    return obj


VALIDATORS: dict[str, Callable[[Any], Mapping[str, Any]]] = {
    "drone_agricole.dataset_definition.v1": validate_dataset_definition,
    "drone_agricole.simulation_definition.v1": validate_simulation_definition,
    "drone_agricole.run_request.v1": validate_run_request,
    "drone_agricole.run_manifest.v1": validate_run_manifest,
    "drone_agricole.metrics.v1": validate_metrics,
    "drone_agricole.artifacts.v1": validate_artifacts,
    "drone_agricole.event.v1": validate_event,
}


def validate_contract(payload: Any, expected_schema: str | None = None) -> Mapping[str, Any]:
    obj = _mapping(payload, "contract")
    schema_name = obj.get("schema")
    if not isinstance(schema_name, str) or not SCHEMA_RE.fullmatch(schema_name):
        _fail("contract.schema", "nom de schéma versionné invalide")
    if expected_schema is not None and schema_name != expected_schema:
        _fail("contract.schema", f"'{expected_schema}' attendu")
    validator = VALIDATORS.get(schema_name)
    if validator is None:
        _fail("contract.schema", f"version non prise en charge : {schema_name}")
    return validator(obj)


def load_schema_documents(schema_directory: Path) -> dict[str, Mapping[str, Any]]:
    documents: dict[str, Mapping[str, Any]] = {}
    for path in sorted(schema_directory.glob("*.schema.json")):
        try:
            document = _mapping(json.loads(path.read_text(encoding="utf-8")), str(path))
        except (OSError, json.JSONDecodeError) as exc:
            raise ContractError(f"{path}: schéma JSON illisible : {exc}") from exc
        if document.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
            _fail(str(path), "le draft JSON Schema 2020-12 est requis")
        schema_id = _string(document.get("$id"), f"{path}.$id")
        if schema_id in documents:
            _fail(str(path), f"$id dupliqué : {schema_id}")
        documents[schema_id] = document
    if not documents:
        _fail(str(schema_directory), "aucun schéma JSON trouvé")
    return documents


@dataclass(frozen=True)
class DefinitionRegistry:
    datasets: dict[str, Mapping[str, Any]]
    simulations: dict[str, Mapping[str, Any]]

    @classmethod
    def load(cls, dataset_directory: Path, simulation_directory: Path) -> "DefinitionRegistry":
        datasets: dict[str, Mapping[str, Any]] = {}
        simulations: dict[str, Mapping[str, Any]] = {}
        for path in sorted(dataset_directory.glob("*.json")):
            payload = _load_json(path)
            validate_dataset_definition(payload)
            dataset_id = payload["dataset_id"]
            if dataset_id in datasets:
                _fail(str(path), f"dataset_id dupliqué : {dataset_id}")
            datasets[dataset_id] = payload
        for path in sorted(simulation_directory.glob("*.json")):
            payload = _load_json(path)
            validate_simulation_definition(payload)
            simulation_id = payload["simulation_id"]
            if simulation_id in simulations:
                _fail(str(path), f"simulation_id dupliqué : {simulation_id}")
            simulations[simulation_id] = payload
        if not datasets:
            _fail(str(dataset_directory), "aucune définition de dataset")
        if not simulations:
            _fail(str(simulation_directory), "aucune définition de simulation")
        return cls(datasets=datasets, simulations=simulations)

    def compatible_dataset_sequences(self, simulation_id: str, variant_id: str | None = None) -> list[dict[str, Any]]:
        try:
            simulation = self.simulations[simulation_id]
        except KeyError as exc:
            raise ContractError(f"simulation inconnue : {simulation_id}") from exc
        required = {
            capability
            for selector in simulation["selectors"]
            if selector["kind"] == "dataset_sequence" and selector["required"]
            for capability in selector["required_capabilities"]
        }
        if variant_id is not None:
            variants = [variant for variant in simulation["variants"] if variant["variant_id"] == variant_id]
            if not variants:
                raise ContractError(f"variante inconnue pour {simulation_id} : {variant_id}")
            required.update(variants[0]["required_capabilities"])
        compatible: list[dict[str, Any]] = []
        for dataset in self.datasets.values():
            if dataset["status"] == "disabled":
                continue
            dataset_capabilities = set(dataset["capabilities"])
            for sequence in dataset["sequences"]:
                if sequence["status"] == "disabled":
                    continue
                capabilities = dataset_capabilities | set(sequence["capabilities"])
                if not required.issubset(capabilities):
                    continue
                compatible.append(
                    {
                        "dataset_id": dataset["dataset_id"],
                        "dataset_label": dataset["label"],
                        "dataset_status": dataset["status"],
                        "sequence_id": sequence["sequence_id"],
                        "sequence_label": sequence["label"],
                        "sequence_status": sequence["status"],
                        "duration_s": sequence["duration_s"],
                        "recommended": bool(sequence.get("recommended", False)),
                        "capabilities": sorted(capabilities),
                        "resources": sequence["resources"],
                    }
                )
        return compatible


def _load_json(path: Path) -> Mapping[str, Any]:
    try:
        return _mapping(json.loads(path.read_text(encoding="utf-8")), str(path))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractError(f"{path}: JSON illisible : {exc}") from exc
