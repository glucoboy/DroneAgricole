"""Decode the bounded, synthetic C.3 geometry exchanged with FreeCAD."""

import json
import math
import re


OBSTACLE_OBJECT = "C3ExternalObstacle"
C3_PROFILES = (
    "docs/electromechanical_v3/bench_c3_spatial/profile.json",
    "docs/electromechanical_v3/bench_c3_spatial_secondary/profile.json",
)
C4_PROFILES = (
    "docs/electromechanical_v3/bench_c4_sixdof/profile.json",
    "docs/electromechanical_v3/bench_c4_sixdof_secondary/profile.json",
)


def box_limits(value, *, allow_surface=False):
    if not isinstance(value, dict) or set(value) != {"min_mm", "max_mm"}:
        raise ValueError("Boîte ROOT attendue avec min_mm et max_mm")
    corners = value["min_mm"], value["max_mm"]
    if not all(isinstance(row, list) and len(row) == 3 and all(
            type(number) in (int, float) and math.isfinite(number) and abs(number) <= 1e6
            for number in row) for row in corners):
        raise ValueError("Boîte ROOT hors limites numériques")
    if any(high < low or (high == low and not allow_surface)
           for low, high in zip(*corners, strict=True)):
        raise ValueError("Bornes de boîte ROOT inversées ou sans volume autorisé")
    return corners


def obstacle_spec(value):
    if not isinstance(value, dict) or set(value) != {"id", "min_mm", "max_mm"}:
        raise ValueError("Obstacle externe mal formé")
    identifier = value["id"]
    if not isinstance(identifier, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,63}", identifier):
        raise ValueError("Identifiant ASCII d'obstacle externe invalide")
    low, high = box_limits({name: value[name] for name in ("min_mm", "max_mm")})
    if any(abs(number) > 10000 for number in low + high) or any(
            end - begin < 0.01 for begin, end in zip(low, high, strict=True)):
        raise ValueError("Obstacle externe hors bornes dimensionnelles C.3")
    return identifier, low, high


def corridor_limits(value, tolerance):
    low, high = box_limits(value, allow_surface=True)
    return ([left - tolerance if left == right else left for left, right in zip(low, high, strict=True)],
            [right + tolerance if left == right else right for left, right in zip(low, high, strict=True)])


def spatial_profile(project, job, *, saved_candidate=False):
    """Refuse spatial worker jobs outside the sealed synthetic fixtures."""
    patch = "offset_patch_mm" in job["spatial_contract"].get("support", {})
    for relative in C4_PROFILES if patch else C3_PROFILES:
        path = project / relative
        if not path.is_file():
            continue
        profile = json.loads(path.read_bytes())
        if job["model"] != profile["model"] or job["entry"] != profile["entry"]:
            continue
        expected, actual = profile["dependencies"], job["dependencies"]
        if expected.keys() == actual.keys() and all(
                actual[name] == value for name, value in expected.items()
                if not saved_candidate or name != job["entry"]):
            return profile
    raise ValueError("Contrat spatial hors profils synthétiques C.3/C.4")


def nominal_axis(value):
    if not isinstance(value, dict) or set(value) != {"axis", "coordinate_mm"} or value["axis"] not in ("X", "Y", "Z"):
        raise ValueError("Plan nominal XYZ invalide")
    coordinate = value["coordinate_mm"]
    if type(coordinate) not in (int, float) or not math.isfinite(coordinate) or abs(coordinate) > 1e6:
        raise ValueError("Coordonnée du plan nominal hors limites")
    return "XYZ".index(value["axis"]), coordinate
