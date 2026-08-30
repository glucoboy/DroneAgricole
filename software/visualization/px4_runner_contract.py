"""Validation pure de l'interface entre le dashboard et le runner PX4 SITL."""

from __future__ import annotations

import math
from pathlib import Path, PurePosixPath
import re
from typing import Any, Mapping


IDENTIFIER = re.compile(r"^[a-z0-9][a-z0-9_-]{0,95}$")
MODES = {"square", "failsafe"}
PARAMETER_BOUNDS = {
    "takeoff_altitude_m": (0.5, 10.0),
    "leg_m": (0.5, 20.0),
    "warmup_s": (1.0, 10.0),
    "hover_s": (1.0, 15.0),
    "stage_timeout_s": (5.0, 30.0),
}


class Px4RunnerError(ValueError):
    pass


def validate_start_payload(payload: Any, workspace: Path) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise Px4RunnerError("La requête doit être un objet JSON.")
    allowed = {"run_id", "mode", "result_directory", "parameters"}
    unexpected = sorted(set(payload) - allowed)
    if unexpected:
        raise Px4RunnerError(f"Champ inconnu : {unexpected[0]}")
    run_id = str(payload.get("run_id", ""))
    mode = str(payload.get("mode", ""))
    if not IDENTIFIER.fullmatch(run_id):
        raise Px4RunnerError("run_id invalide.")
    if mode not in MODES:
        raise Px4RunnerError("mode doit valoir square ou failsafe.")
    relative = str(payload.get("result_directory", ""))
    pure = PurePosixPath(relative)
    if pure.is_absolute() or ".." in pure.parts or "\\" in relative:
        raise Px4RunnerError("result_directory doit être un chemin relatif POSIX.")
    expected_root = PurePosixPath("results/simulation/px4_lot_a")
    if tuple(pure.parts[: len(expected_root.parts)]) != expected_root.parts:
        raise Px4RunnerError("result_directory doit rester dans results/simulation/px4_lot_a.")
    result_directory = (workspace / Path(*pure.parts)).resolve()
    if not result_directory.is_relative_to(workspace.resolve()):
        raise Px4RunnerError("result_directory sort du workspace.")
    if result_directory.exists():
        raise Px4RunnerError("Le répertoire de résultat existe déjà.")
    supplied = payload.get("parameters")
    if not isinstance(supplied, Mapping):
        raise Px4RunnerError("parameters doit être un objet JSON.")
    unexpected_parameters = sorted(set(supplied) - set(PARAMETER_BOUNDS))
    if unexpected_parameters:
        raise Px4RunnerError(f"Paramètre PX4 inconnu : {unexpected_parameters[0]}")
    parameters: dict[str, float] = {}
    for name, (minimum, maximum) in PARAMETER_BOUNDS.items():
        try:
            value = float(supplied[name])
        except (KeyError, TypeError, ValueError) as exc:
            raise Px4RunnerError(f"Paramètre PX4 absent ou invalide : {name}") from exc
        if not math.isfinite(value) or not minimum <= value <= maximum:
            raise Px4RunnerError(f"{name} doit rester entre {minimum:g} et {maximum:g}.")
        parameters[name] = value
    return {
        "run_id": run_id,
        "mode": mode,
        "result_directory": relative,
        "parameters": parameters,
    }
