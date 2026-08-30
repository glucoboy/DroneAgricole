"""Pont d'état PX4 vers des messages ROS génériques et le tableau de bord."""

from __future__ import annotations

import json
import math
from typing import Any

import rclpy
from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus, KeyValue
from geometry_msgs.msg import PoseStamped, TransformStamped
from nav_msgs.msg import Odometry, Path
from px4_msgs.msg import BatteryStatus, FailsafeFlags, VehicleOdometry, VehicleStatus
from rclpy.node import Node
from rclpy.qos import (
    DurabilityPolicy,
    HistoryPolicy,
    QoSProfile,
    ReliabilityPolicy,
)
from std_msgs.msg import String
from tf2_ros import TransformBroadcaster

from .frames import (
    frd_to_flu,
    ned_to_enu,
    ned_velocity_to_body_flu,
    px4_quaternion_to_ros_xyzw,
)


NAVIGATION_STATES = {
    0: "manual",
    1: "altitude",
    2: "position",
    3: "mission",
    4: "loiter",
    5: "rtl",
    10: "acro",
    12: "descend",
    13: "termination",
    14: "offboard",
    15: "stabilized",
    17: "takeoff",
    18: "land",
    20: "precision_land",
    21: "orbit",
}


def _finite_or_none(value: Any) -> float | int | bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    try:
        converted = float(value)
    except (TypeError, ValueError):
        return None
    return converted if math.isfinite(converted) else None


def _json_vector(values: Any) -> list[float | int | bool | None]:
    return [_finite_or_none(value) for value in values]


class Px4StateBridge(Node):
    """Expose l'état PX4 sans jamais publier de commande de vol."""

    def __init__(self) -> None:
        super().__init__("px4_state_bridge")
        self.declare_parameter("world_frame", "map")
        self.declare_parameter("body_frame", "base_link")
        self.declare_parameter("publish_tf", True)
        self.declare_parameter("path_max_points", 2500)
        self.declare_parameter("path_min_distance_m", 0.05)
        self.declare_parameter("stale_after_s", 1.0)
        # PX4 1.18 suffixe automatiquement les messages dont MESSAGE_VERSION
        # est non nul. Ces valeurs sont donc liées aux commits figés du lot A.
        self.declare_parameter("vehicle_status_topic", "/fmu/out/vehicle_status_v4")
        self.declare_parameter("battery_status_topic", "/fmu/out/battery_status_v1")

        self._world_frame = str(self.get_parameter("world_frame").value)
        self._body_frame = str(self.get_parameter("body_frame").value)
        self._publish_tf = bool(self.get_parameter("publish_tf").value)
        self._path_max_points = max(
            10, int(self.get_parameter("path_max_points").value)
        )
        self._path_min_distance_m = max(
            0.0, float(self.get_parameter("path_min_distance_m").value)
        )
        self._stale_after_s = max(
            0.1, float(self.get_parameter("stale_after_s").value)
        )
        self._vehicle_status_topic = str(
            self.get_parameter("vehicle_status_topic").value
        )
        self._battery_status_topic = str(
            self.get_parameter("battery_status_topic").value
        )

        px4_qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
        )
        path_qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
        )

        self._odometry_publisher = self.create_publisher(
            Odometry, "/drone/px4/odometry", 10
        )
        self._path_publisher = self.create_publisher(
            Path, "/drone/px4/path", path_qos
        )
        self._state_publisher = self.create_publisher(
            String, "/drone/px4/state_json", 10
        )
        self._diagnostics_publisher = self.create_publisher(
            DiagnosticArray, "/diagnostics", 10
        )
        self._tf_broadcaster = TransformBroadcaster(self) if self._publish_tf else None

        self.create_subscription(
            VehicleOdometry,
            "/fmu/out/vehicle_odometry",
            self._on_odometry,
            px4_qos,
        )
        self.create_subscription(
            VehicleStatus,
            self._vehicle_status_topic,
            self._on_status,
            px4_qos,
        )
        self.create_subscription(
            BatteryStatus,
            self._battery_status_topic,
            self._on_battery,
            px4_qos,
        )
        self.create_subscription(
            FailsafeFlags,
            "/fmu/out/failsafe_flags",
            self._on_failsafe_flags,
            px4_qos,
        )

        self._last_received_ns: dict[str, int] = {}
        self._status: VehicleStatus | None = None
        self._battery: BatteryStatus | None = None
        self._failsafe_flags: FailsafeFlags | None = None
        self._last_px4_odometry: VehicleOdometry | None = None
        self._last_ros_odometry: Odometry | None = None
        self._path = Path()
        self._path.header.frame_id = self._world_frame
        self._unsupported_pose_frame_reported = False

        self.create_timer(0.5, self._publish_state_and_diagnostics)
        self.get_logger().info(
            "Pont PX4 en lecture seule prêt : NED/FRD -> ENU/FLU, domaine ROS courant."
        )

    def _now_ns(self) -> int:
        return self.get_clock().now().nanoseconds

    def _record_received(self, name: str) -> None:
        self._last_received_ns[name] = self._now_ns()

    def _on_status(self, message: VehicleStatus) -> None:
        self._status = message
        self._record_received("vehicle_status")

    def _on_battery(self, message: BatteryStatus) -> None:
        self._battery = message
        self._record_received("battery_status")

    def _on_failsafe_flags(self, message: FailsafeFlags) -> None:
        self._failsafe_flags = message
        self._record_received("failsafe_flags")

    def _on_odometry(self, message: VehicleOdometry) -> None:
        self._last_px4_odometry = message
        self._record_received("vehicle_odometry")
        if message.pose_frame != VehicleOdometry.POSE_FRAME_NED:
            if not self._unsupported_pose_frame_reported:
                self.get_logger().error(
                    "Pose PX4 ignorée : seul le repère NED est qualifié par ce pont."
                )
                self._unsupported_pose_frame_reported = True
            return

        try:
            position = ned_to_enu(message.position)
            orientation = px4_quaternion_to_ros_xyzw(message.q)
        except ValueError as error:
            self.get_logger().warning(f"Pose PX4 invalide ignorée : {error}")
            return
        if not all(math.isfinite(value) for value in position):
            return

        odometry = Odometry()
        odometry.header.stamp = self.get_clock().now().to_msg()
        odometry.header.frame_id = self._world_frame
        odometry.child_frame_id = self._body_frame
        odometry.pose.pose.position.x = position[0]
        odometry.pose.pose.position.y = position[1]
        odometry.pose.pose.position.z = position[2]
        odometry.pose.pose.orientation.x = orientation[0]
        odometry.pose.pose.orientation.y = orientation[1]
        odometry.pose.pose.orientation.z = orientation[2]
        odometry.pose.pose.orientation.w = orientation[3]

        position_variance = message.position_variance
        orientation_variance = message.orientation_variance
        if all(math.isfinite(float(v)) for v in position_variance):
            odometry.pose.covariance[0] = float(position_variance[1])
            odometry.pose.covariance[7] = float(position_variance[0])
            odometry.pose.covariance[14] = float(position_variance[2])
        if all(math.isfinite(float(v)) for v in orientation_variance):
            odometry.pose.covariance[21] = float(orientation_variance[0])
            odometry.pose.covariance[28] = float(orientation_variance[1])
            odometry.pose.covariance[35] = float(orientation_variance[2])

        try:
            if message.velocity_frame == VehicleOdometry.VELOCITY_FRAME_NED:
                linear_velocity = ned_velocity_to_body_flu(message.q, message.velocity)
            elif message.velocity_frame == VehicleOdometry.VELOCITY_FRAME_BODY_FRD:
                linear_velocity = frd_to_flu(message.velocity)
            else:
                linear_velocity = (0.0, 0.0, 0.0)
                odometry.twist.covariance[0] = -1.0
            angular_velocity = frd_to_flu(message.angular_velocity)
        except ValueError:
            linear_velocity = (0.0, 0.0, 0.0)
            angular_velocity = (0.0, 0.0, 0.0)
            odometry.twist.covariance[0] = -1.0

        odometry.twist.twist.linear.x = linear_velocity[0]
        odometry.twist.twist.linear.y = linear_velocity[1]
        odometry.twist.twist.linear.z = linear_velocity[2]
        odometry.twist.twist.angular.x = angular_velocity[0]
        odometry.twist.twist.angular.y = angular_velocity[1]
        odometry.twist.twist.angular.z = angular_velocity[2]

        self._last_ros_odometry = odometry
        self._odometry_publisher.publish(odometry)
        self._update_path(odometry)
        self._broadcast_transform(odometry)

    def _update_path(self, odometry: Odometry) -> None:
        position = odometry.pose.pose.position
        if self._path.poses:
            previous = self._path.poses[-1].pose.position
            distance = math.sqrt(
                (position.x - previous.x) ** 2
                + (position.y - previous.y) ** 2
                + (position.z - previous.z) ** 2
            )
            if distance < self._path_min_distance_m:
                return

        pose = PoseStamped()
        pose.header = odometry.header
        pose.pose.position.x = position.x
        pose.pose.position.y = position.y
        pose.pose.position.z = position.z
        pose.pose.orientation = odometry.pose.pose.orientation
        self._path.poses.append(pose)
        if len(self._path.poses) > self._path_max_points:
            del self._path.poses[: len(self._path.poses) - self._path_max_points]
        self._path.header.stamp = odometry.header.stamp
        self._path_publisher.publish(self._path)

    def _broadcast_transform(self, odometry: Odometry) -> None:
        if self._tf_broadcaster is None:
            return
        transform = TransformStamped()
        transform.header = odometry.header
        transform.child_frame_id = odometry.child_frame_id
        transform.transform.translation.x = odometry.pose.pose.position.x
        transform.transform.translation.y = odometry.pose.pose.position.y
        transform.transform.translation.z = odometry.pose.pose.position.z
        transform.transform.rotation = odometry.pose.pose.orientation
        self._tf_broadcaster.sendTransform(transform)

    def _topic_age(self, name: str) -> float | None:
        received_ns = self._last_received_ns.get(name)
        if received_ns is None:
            return None
        return max(0.0, (self._now_ns() - received_ns) / 1e9)

    def _state_payload(self) -> dict[str, Any]:
        status = self._status
        battery = self._battery
        flags = self._failsafe_flags
        px4_odometry = self._last_px4_odometry
        ros_odometry = self._last_ros_odometry

        payload: dict[str, Any] = {
            "schema": "drone_agricole.px4_state.v1",
            "bridge_time_ns": self._now_ns(),
            "topics_age_s": {
                name: self._topic_age(name)
                for name in (
                    "vehicle_odometry",
                    "vehicle_status",
                    "battery_status",
                    "failsafe_flags",
                )
            },
        }
        if status is not None:
            nav_state = int(status.nav_state)
            payload["vehicle"] = {
                "timestamp_us": int(status.timestamp),
                "armed": int(status.arming_state)
                == int(VehicleStatus.ARMING_STATE_ARMED),
                "arming_state": int(status.arming_state),
                "nav_state": nav_state,
                "nav_state_name": NAVIGATION_STATES.get(nav_state, f"state_{nav_state}"),
                "failsafe": bool(status.failsafe),
                "preflight_checks_pass": bool(status.pre_flight_checks_pass),
                "gcs_connection_lost": bool(status.gcs_connection_lost),
                "accepts_offboard_setpoints": bool(status.accepts_offboard_setpoints),
            }
        if battery is not None:
            payload["battery"] = {
                "timestamp_us": int(battery.timestamp),
                "connected": bool(battery.connected),
                "remaining": _finite_or_none(battery.remaining),
                "voltage_v": _finite_or_none(battery.voltage_v),
                "current_a": _finite_or_none(battery.current_a),
                "warning": int(battery.warning),
            }
        if flags is not None:
            payload["failsafe_flags"] = {
                "offboard_control_signal_lost": bool(
                    flags.offboard_control_signal_lost
                ),
                "local_position_invalid": bool(flags.local_position_invalid),
                "global_position_invalid": bool(flags.global_position_invalid),
                "manual_control_signal_lost": bool(flags.manual_control_signal_lost),
            }
        if px4_odometry is not None:
            payload["px4_odometry"] = {
                "timestamp_us": int(px4_odometry.timestamp),
                "pose_frame": int(px4_odometry.pose_frame),
                "velocity_frame": int(px4_odometry.velocity_frame),
                "position_ned_m": _json_vector(px4_odometry.position),
                "quaternion_wxyz": _json_vector(px4_odometry.q),
                "quality": int(px4_odometry.quality),
            }
        if ros_odometry is not None:
            position = ros_odometry.pose.pose.position
            orientation = ros_odometry.pose.pose.orientation
            payload["ros_odometry"] = {
                "frame": ros_odometry.header.frame_id,
                "child_frame": ros_odometry.child_frame_id,
                "position_enu_m": [position.x, position.y, position.z],
                "quaternion_xyzw": [
                    orientation.x,
                    orientation.y,
                    orientation.z,
                    orientation.w,
                ],
                "path_points": len(self._path.poses),
            }
        return payload

    def _diagnostic_status(self) -> DiagnosticStatus:
        status = DiagnosticStatus()
        status.name = "PX4 SITL / pont ROS 2"
        status.hardware_id = "px4_sitl_x500"
        odometry_age = self._topic_age("vehicle_odometry")
        vehicle = self._status
        battery = self._battery

        if vehicle is None:
            status.level = DiagnosticStatus.ERROR
            status.message = "Aucun état PX4 reçu"
        elif odometry_age is None or odometry_age > self._stale_after_s:
            status.level = DiagnosticStatus.ERROR
            status.message = "Odométrie PX4 absente ou périmée"
        elif bool(vehicle.failsafe):
            status.level = DiagnosticStatus.ERROR
            status.message = "Failsafe PX4 actif"
        elif battery is not None and int(battery.warning) >= int(BatteryStatus.WARNING_CRITICAL):
            status.level = DiagnosticStatus.ERROR
            status.message = "Batterie PX4 critique"
        elif not bool(vehicle.pre_flight_checks_pass):
            status.level = DiagnosticStatus.WARN
            status.message = "Contrôles pré-vol non validés"
        else:
            status.level = DiagnosticStatus.OK
            status.message = "Liaison PX4–ROS 2 opérationnelle"

        status.values = [
            KeyValue(
                key="odometry_age_s",
                value="absent" if odometry_age is None else f"{odometry_age:.3f}",
            ),
            KeyValue(
                key="armed",
                value=str(
                    bool(vehicle)
                    and int(vehicle.arming_state)
                    == int(VehicleStatus.ARMING_STATE_ARMED)
                ).lower(),
            ),
            KeyValue(
                key="failsafe",
                value=str(bool(vehicle) and bool(vehicle.failsafe)).lower(),
            ),
            KeyValue(key="path_points", value=str(len(self._path.poses))),
        ]
        return status

    def _publish_state_and_diagnostics(self) -> None:
        state_message = String()
        state_message.data = json.dumps(
            self._state_payload(), ensure_ascii=False, separators=(",", ":")
        )
        self._state_publisher.publish(state_message)

        diagnostics = DiagnosticArray()
        diagnostics.header.stamp = self.get_clock().now().to_msg()
        diagnostics.status = [self._diagnostic_status()]
        self._diagnostics_publisher.publish(diagnostics)


def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)
    node = Px4StateBridge()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
