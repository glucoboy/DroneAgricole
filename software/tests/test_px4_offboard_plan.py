from unittest import TestCase

from drone_agricole_px4_bridge.offboard_plan import square_mission_ned


class Px4OffboardPlanTest(TestCase):
    def test_square_returns_above_origin_at_requested_altitude(self) -> None:
        mission = square_mission_ned((10.0, -2.0, 0.5), 2.0, 3.0)

        self.assertEqual([stage for stage, _ in mission], [
            "takeoff", "leg_north", "leg_east", "leg_south", "leg_west"
        ])
        self.assertEqual(mission[0][1], (10.0, -2.0, -1.5))
        self.assertEqual(mission[-1][1], (10.0, -2.0, -1.5))
        self.assertEqual(mission[2][1], (13.0, 1.0, -1.5))

    def test_unsafe_dimensions_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            square_mission_ned((0.0, 0.0, 0.0), 0.1, 2.0)
        with self.assertRaises(ValueError):
            square_mission_ned((0.0, 0.0, 0.0), 2.0, 30.0)
