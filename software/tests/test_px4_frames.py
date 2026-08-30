import math
from unittest import TestCase

from drone_agricole_px4_bridge.frames import (
    frd_to_flu,
    ned_to_enu,
    ned_velocity_to_body_flu,
    px4_quaternion_to_ros_xyzw,
)


class Px4FrameConversionsTest(TestCase):
    def test_ned_vector_becomes_enu(self) -> None:
        self.assertEqual(ned_to_enu((1.0, 2.0, 3.0)), (2.0, 1.0, -3.0))

    def test_frd_vector_becomes_flu(self) -> None:
        self.assertEqual(frd_to_flu((1.0, 2.0, 3.0)), (1.0, -2.0, -3.0))

    def test_north_facing_px4_body_has_ros_yaw_plus_90_degrees(self) -> None:
        x, y, z, w = px4_quaternion_to_ros_xyzw((1.0, 0.0, 0.0, 0.0))
        expected = math.sqrt(0.5)
        self.assertAlmostEqual(x, 0.0, places=12)
        self.assertAlmostEqual(y, 0.0, places=12)
        self.assertAlmostEqual(z, expected, places=12)
        self.assertAlmostEqual(w, expected, places=12)

    def test_east_facing_px4_body_has_zero_ros_yaw(self) -> None:
        half = math.sqrt(0.5)
        x, y, z, w = px4_quaternion_to_ros_xyzw((half, 0.0, 0.0, half))
        self.assertAlmostEqual(x, 0.0, places=12)
        self.assertAlmostEqual(y, 0.0, places=12)
        self.assertAlmostEqual(z, 0.0, places=12)
        self.assertAlmostEqual(w, 1.0, places=12)

    def test_north_velocity_is_forward_for_north_facing_body(self) -> None:
        velocity = ned_velocity_to_body_flu(
            (1.0, 0.0, 0.0, 0.0), (3.0, 0.0, 0.0)
        )
        self.assertAlmostEqual(velocity[0], 3.0, places=12)
        self.assertAlmostEqual(velocity[1], 0.0, places=12)
        self.assertAlmostEqual(velocity[2], 0.0, places=12)

    def test_invalid_quaternion_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            px4_quaternion_to_ros_xyzw((0.0, 0.0, 0.0, 0.0))
