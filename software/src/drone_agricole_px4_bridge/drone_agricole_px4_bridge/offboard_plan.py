"""Génération pure de la trajectoire d'essai PX4 en repère NED."""

from __future__ import annotations

from collections.abc import Sequence


def square_mission_ned(
    origin_ned: Sequence[float], altitude_m: float, leg_m: float
) -> list[tuple[str, tuple[float, float, float]]]:
    """Construit un décollage puis un carré revenant au-dessus de l'origine."""

    if len(origin_ned) != 3:
        raise ValueError("l'origine NED doit contenir trois coordonnées")
    if not 0.5 <= float(altitude_m) <= 10.0:
        raise ValueError("l'altitude d'essai doit être comprise entre 0,5 et 10 m")
    if not 0.5 <= float(leg_m) <= 20.0:
        raise ValueError("le côté du carré doit être compris entre 0,5 et 20 m")
    north, east, down = (float(value) for value in origin_ned)
    flight_down = down - float(altitude_m)
    side = float(leg_m)
    return [
        ("takeoff", (north, east, flight_down)),
        ("leg_north", (north + side, east, flight_down)),
        ("leg_east", (north + side, east + side, flight_down)),
        ("leg_south", (north, east + side, flight_down)),
        ("leg_west", (north, east, flight_down)),
    ]
