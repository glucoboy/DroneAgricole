"""Conversions explicites entre les conventions PX4 et ROS REP-103.

PX4 publie une pose locale NED avec un corps FRD. Le pont expose une pose ROS
ENU avec un corps FLU. Les quaternions d'entrée suivent l'ordre PX4 w, x, y, z
et les quaternions de sortie l'ordre ROS x, y, z, w.
"""

from __future__ import annotations

import math
from collections.abc import Sequence


_SQRT_HALF = math.sqrt(0.5)
_Q_ENU_FROM_NED = (0.0, _SQRT_HALF, _SQRT_HALF, 0.0)
_Q_FRD_FROM_FLU = (0.0, 1.0, 0.0, 0.0)


def _quaternion_multiply(
    left: Sequence[float], right: Sequence[float]
) -> tuple[float, float, float, float]:
    """Compose deux quaternions Hamilton dans l'ordre w, x, y, z."""

    lw, lx, ly, lz = left
    rw, rx, ry, rz = right
    return (
        lw * rw - lx * rx - ly * ry - lz * rz,
        lw * rx + lx * rw + ly * rz - lz * ry,
        lw * ry - lx * rz + ly * rw + lz * rx,
        lw * rz + lx * ry - ly * rx + lz * rw,
    )


def _normalize_quaternion(
    quaternion: Sequence[float],
) -> tuple[float, float, float, float]:
    if len(quaternion) != 4 or not all(math.isfinite(float(v)) for v in quaternion):
        raise ValueError("quaternion PX4 invalide")
    norm = math.sqrt(sum(float(v) * float(v) for v in quaternion))
    if norm < 1e-12:
        raise ValueError("quaternion PX4 de norme nulle")
    normalized = tuple(float(v) / norm for v in quaternion)
    if normalized[0] < 0.0:
        normalized = tuple(-v for v in normalized)
    return normalized  # type: ignore[return-value]


def ned_to_enu(vector: Sequence[float]) -> tuple[float, float, float]:
    """Convertit un vecteur exprimé dans le repère monde NED vers ENU."""

    if len(vector) != 3:
        raise ValueError("un vecteur 3D est requis")
    north, east, down = (float(v) for v in vector)
    return east, north, -down


def frd_to_flu(vector: Sequence[float]) -> tuple[float, float, float]:
    """Convertit un vecteur exprimé dans le repère corps FRD vers FLU."""

    if len(vector) != 3:
        raise ValueError("un vecteur 3D est requis")
    forward, right, down = (float(v) for v in vector)
    return forward, -right, -down


def px4_quaternion_to_ros_wxyz(
    quaternion_wxyz: Sequence[float],
) -> tuple[float, float, float, float]:
    """Retourne la rotation corps FLU vers monde ENU dans l'ordre w, x, y, z."""

    px4 = _normalize_quaternion(quaternion_wxyz)
    converted = _quaternion_multiply(
        _quaternion_multiply(_Q_ENU_FROM_NED, px4), _Q_FRD_FROM_FLU
    )
    converted = _normalize_quaternion(converted)
    return converted


def px4_quaternion_to_ros_xyzw(
    quaternion_wxyz: Sequence[float],
) -> tuple[float, float, float, float]:
    """Retourne la rotation corps FLU vers monde ENU dans l'ordre ROS."""

    w, x, y, z = px4_quaternion_to_ros_wxyz(quaternion_wxyz)
    return x, y, z, w


def _rotate_world_to_body(
    quaternion_body_to_world_wxyz: Sequence[float], vector_world: Sequence[float]
) -> tuple[float, float, float]:
    """Exprime dans le corps un vecteur fourni dans le repère monde."""

    q = _normalize_quaternion(quaternion_body_to_world_wxyz)
    conjugate = (q[0], -q[1], -q[2], -q[3])
    vector_quaternion = (0.0, *(float(v) for v in vector_world))
    rotated = _quaternion_multiply(
        _quaternion_multiply(conjugate, vector_quaternion), q
    )
    return rotated[1], rotated[2], rotated[3]


def ned_velocity_to_body_flu(
    quaternion_px4_wxyz: Sequence[float], velocity_ned: Sequence[float]
) -> tuple[float, float, float]:
    """Convertit la vitesse monde NED PX4 en vitesse corps FLU ROS."""

    velocity_enu = ned_to_enu(velocity_ned)
    orientation_ros = px4_quaternion_to_ros_wxyz(quaternion_px4_wxyz)
    return _rotate_world_to_body(orientation_ros, velocity_enu)
