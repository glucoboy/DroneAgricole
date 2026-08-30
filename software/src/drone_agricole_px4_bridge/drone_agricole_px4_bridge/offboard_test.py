"""Essai offboard PX4 SITL protégé, avec scénario nominal ou perte de liaison."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import time
from typing import Any

import rclpy
from px4_msgs.msg import (
    FailsafeFlags,
    OffboardControlMode,
    TrajectorySetpoint,
    VehicleCommand,
    VehicleCommandAck,
    VehicleLandDetected,
    VehicleOdometry,
    VehicleStatus,
)
from rclpy.node import Node
from rclpy.qos import (
    DurabilityPolicy,
    HistoryPolicy,
    QoSProfile,
    ReliabilityPolicy,
)

from .offboard_plan import square_mission_ned


class OffboardTest(Node):
    """Exécute un vol court uniquement quand les deux verrous SITL sont ouverts."""

    def __init__(self) -> None:
        super().__init__("px4_offboard_test")
        self.declare_parameter("execute", False)
        self.declare_parameter("mission_mode", "square")
        self.declare_parameter("takeoff_altitude_m", 2.0)
        self.declare_parameter("leg_m", 2.0)
        self.declare_parameter("warmup_s", 2.0)
        self.declare_parameter("hover_s", 3.0)
        self.declare_parameter("stage_timeout_s", 12.0)
        self.declare_parameter("result_root", "results/simulation/px4_lot_a")
        self.declare_parameter("result_directory", "")

        self.execute = bool(self.get_parameter("execute").value)
        self.mission_mode = str(self.get_parameter("mission_mode").value)
        self.takeoff_altitude_m = float(
            self.get_parameter("takeoff_altitude_m").value
        )
        self.leg_m = float(self.get_parameter("leg_m").value)
        self.warmup_s = max(1.0, float(self.get_parameter("warmup_s").value))
        self.hover_s = max(1.0, float(self.get_parameter("hover_s").value))
        self.stage_timeout_s = max(
            5.0, float(self.get_parameter("stage_timeout_s").value)
        )
        if self.mission_mode not in {"square", "failsafe"}:
            raise ValueError("mission_mode doit valoir square ou failsafe")
        if not self.execute:
            raise PermissionError(
                "Essai refusé : passer explicitement execute:=true pour commander PX4."
            )
        if os.environ.get("DRONE_AGRICOLE_SITL") != "1":
            raise PermissionError(
                "Essai refusé : le verrou d'environnement SITL n'est pas présent."
            )

        workspace = Path.cwd().resolve()
        configured_directory = str(self.get_parameter("result_directory").value).strip()
        if configured_directory:
            self.result_directory = (workspace / configured_directory).resolve()
            approved_root = (workspace / "results/simulation/px4_lot_a").resolve()
            if not self.result_directory.is_relative_to(approved_root):
                raise ValueError(
                    "result_directory doit rester dans results/simulation/px4_lot_a"
                )
            if self.result_directory.exists():
                raise ValueError("result_directory existe déjà")
        else:
            result_root = (
                workspace / str(self.get_parameter("result_root").value)
            ).resolve()
            if not result_root.is_relative_to(workspace):
                raise ValueError("result_root doit rester dans le workspace du projet")
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
            self.result_directory = result_root / f"{self.mission_mode}_{stamp}"

        px4_qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
        )
        self.offboard_publisher = self.create_publisher(
            OffboardControlMode, "/fmu/in/offboard_control_mode", px4_qos
        )
        self.trajectory_publisher = self.create_publisher(
            TrajectorySetpoint, "/fmu/in/trajectory_setpoint", px4_qos
        )
        self.command_publisher = self.create_publisher(
            VehicleCommand, "/fmu/in/vehicle_command", px4_qos
        )
        self.create_subscription(
            VehicleOdometry,
            "/fmu/out/vehicle_odometry",
            self._on_odometry,
            px4_qos,
        )
        self.create_subscription(
            VehicleStatus,
            "/fmu/out/vehicle_status_v4",
            self._on_status,
            px4_qos,
        )
        self.create_subscription(
            FailsafeFlags,
            "/fmu/out/failsafe_flags",
            self._on_failsafe_flags,
            px4_qos,
        )
        self.create_subscription(
            VehicleLandDetected,
            "/fmu/out/vehicle_land_detected",
            self._on_land_detected,
            px4_qos,
        )
        self.create_subscription(
            VehicleCommandAck,
            "/fmu/out/vehicle_command_ack_v1",
            self._on_command_ack,
            px4_qos,
        )

        self.status: VehicleStatus | None = None
        self.odometry: VehicleOdometry | None = None
        self.failsafe_flags: FailsafeFlags | None = None
        self.land_detected: VehicleLandDetected | None = None
        self.last_status_at = 0.0
        self.last_odometry_at = 0.0
        self.state = "waiting_for_data"
        self.state_started = time.monotonic()
        self.started = self.state_started
        self.finished = False
        self.success = False
        self.finish_reason = ""
        self.events: list[dict[str, Any]] = []
        self.command_acks: list[dict[str, int]] = []
        self.origin_ned: tuple[float, float, float] | None = None
        self.origin_yaw = 0.0
        self.target_ned: tuple[float, float, float] | None = None
        self.mission: list[tuple[str, tuple[float, float, float]]] = []
        self.mission_index = -1
        self.last_command_at = 0.0
        self.pending_success = False
        self.pending_reason = ""
        self.max_altitude_m = 0.0
        self.offboard_entered = False
        self.armed_observed = False
        self.failsafe_observed = False
        self.offboard_loss_observed = False
        self.publish_enabled = False
        self.create_timer(0.05, self._tick)
        self._event("test_started", mode=self.mission_mode)
        self.get_logger().warning(
            f"Essai SITL autorisé : mode={self.mission_mode}, aucun matériel réel."
        )

    def _timestamp_us(self) -> int:
        return int(self.get_clock().now().nanoseconds / 1000)

    def _event(self, name: str, **details: Any) -> None:
        event = {
            "event": name,
            "elapsed_s": round(time.monotonic() - self.started, 3),
            "state": self.state,
        }
        event.update(details)
        self.events.append(event)
        self.get_logger().info(json.dumps(event, ensure_ascii=False))

    def _transition(self, state: str, **details: Any) -> None:
        self.state = state
        self.state_started = time.monotonic()
        self._event("state_changed", new_state=state, **details)

    def _on_status(self, message: VehicleStatus) -> None:
        self.status = message
        self.last_status_at = time.monotonic()
        self.offboard_entered = self.offboard_entered or (
            int(message.nav_state) == int(VehicleStatus.NAVIGATION_STATE_OFFBOARD)
        )
        self.armed_observed = self.armed_observed or (
            int(message.arming_state) == int(VehicleStatus.ARMING_STATE_ARMED)
        )
        self.failsafe_observed = self.failsafe_observed or bool(message.failsafe)

    def _on_odometry(self, message: VehicleOdometry) -> None:
        self.odometry = message
        self.last_odometry_at = time.monotonic()
        if self.origin_ned is not None and math.isfinite(float(message.position[2])):
            altitude = self.origin_ned[2] - float(message.position[2])
            self.max_altitude_m = max(self.max_altitude_m, altitude)

    def _on_failsafe_flags(self, message: FailsafeFlags) -> None:
        self.failsafe_flags = message
        if self.state == "failsafe_gap" and bool(message.offboard_control_signal_lost):
            self.offboard_loss_observed = True

    def _on_land_detected(self, message: VehicleLandDetected) -> None:
        self.land_detected = message

    def _on_command_ack(self, message: VehicleCommandAck) -> None:
        ack = {
            "command": int(message.command),
            "result": int(message.result),
            "result_param1": int(message.result_param1),
            "result_param2": int(message.result_param2),
        }
        self.command_acks.append(ack)
        self._event("command_ack", **ack)

    def _publish_setpoint(self) -> None:
        if not self.publish_enabled or self.target_ned is None:
            return
        timestamp = self._timestamp_us()
        mode = OffboardControlMode()
        mode.timestamp = timestamp
        mode.position = True
        self.offboard_publisher.publish(mode)

        setpoint = TrajectorySetpoint()
        setpoint.timestamp = timestamp
        setpoint.position = list(self.target_ned)
        nan = float("nan")
        setpoint.velocity = [nan, nan, nan]
        setpoint.acceleration = [nan, nan, nan]
        setpoint.jerk = [nan, nan, nan]
        setpoint.yaw = float(self.origin_yaw)
        setpoint.yawspeed = nan
        self.trajectory_publisher.publish(setpoint)

    def _send_command(self, command: int, param1: float = 0.0, param2: float = 0.0) -> None:
        message = VehicleCommand()
        message.timestamp = self._timestamp_us()
        message.command = int(command)
        message.param1 = float(param1)
        message.param2 = float(param2)
        message.target_system = 1
        message.target_component = 1
        message.source_system = 1
        message.source_component = 1
        message.from_external = True
        self.command_publisher.publish(message)
        self._event("command_sent", command=int(command), param1=param1, param2=param2)

    def _send_offboard_and_arm(self) -> None:
        self._send_command(VehicleCommand.VEHICLE_CMD_DO_SET_MODE, 1.0, 6.0)
        self._send_command(VehicleCommand.VEHICLE_CMD_COMPONENT_ARM_DISARM, 1.0)
        self.last_command_at = time.monotonic()

    def _send_land(self) -> None:
        self._send_command(VehicleCommand.VEHICLE_CMD_NAV_LAND)
        self.last_command_at = time.monotonic()

    def _send_disarm_if_landed(self) -> None:
        if self.land_detected is not None and bool(self.land_detected.landed):
            self._send_command(VehicleCommand.VEHICLE_CMD_COMPONENT_ARM_DISARM, 0.0)
            self.last_command_at = time.monotonic()

    def _ready(self, now: float) -> bool:
        return (
            self.status is not None
            and self.odometry is not None
            and now - self.last_status_at < 1.0
            and now - self.last_odometry_at < 0.5
            and self.odometry.pose_frame == VehicleOdometry.POSE_FRAME_NED
            and all(math.isfinite(float(value)) for value in self.odometry.position)
            and all(math.isfinite(float(value)) for value in self.odometry.q)
        )

    def _current_distance(self) -> float:
        if self.odometry is None or self.target_ned is None:
            return math.inf
        return math.dist(
            tuple(float(value) for value in self.odometry.position), self.target_ned
        )

    def _start_mission_stage(self, index: int) -> None:
        if index >= len(self.mission):
            self._transition("hover")
            return
        self.mission_index = index
        label, target = self.mission[index]
        self.target_ned = target
        self._transition("mission_stage", stage=label, target_ned=list(target))

    def _begin_landing(self, success: bool, reason: str, command_land: bool) -> None:
        self.pending_success = success
        self.pending_reason = reason
        self.publish_enabled = False
        self._transition("landing", expected_success=success, reason=reason)
        if command_land:
            self._send_land()
        else:
            # Laisse au failsafe PX4 cinq secondes pour exécuter seul son
            # action avant que le watchdog ne renforce éventuellement LAND.
            self.last_command_at = time.monotonic()

    def _abort(self, reason: str) -> None:
        self._event("abort_requested", reason=reason)
        armed = self.status is not None and (
            int(self.status.arming_state) == int(VehicleStatus.ARMING_STATE_ARMED)
        )
        if armed:
            self._begin_landing(False, reason, command_land=True)
        else:
            self._finish(False, reason)

    def _finish(self, success: bool, reason: str) -> None:
        if self.finished:
            return
        self.finished = True
        self.success = success
        self.finish_reason = reason
        self.publish_enabled = False
        self._event("test_finished", success=success, reason=reason)
        self.result_directory.mkdir(parents=True, exist_ok=False)
        result = {
            "schema": "drone_agricole.px4_offboard_test.v1",
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "success": success,
            "reason": reason,
            "mode": self.mission_mode,
            "parameters": {
                "takeoff_altitude_m": self.takeoff_altitude_m,
                "leg_m": self.leg_m,
                "warmup_s": self.warmup_s,
                "hover_s": self.hover_s,
            },
            "observations": {
                "offboard_entered": self.offboard_entered,
                "armed": self.armed_observed,
                "failsafe": self.failsafe_observed,
                "offboard_loss_flag": self.offboard_loss_observed,
                "max_altitude_m": self.max_altitude_m,
                "landed": bool(self.land_detected and self.land_detected.landed),
            },
            "origin_ned_m": list(self.origin_ned) if self.origin_ned else None,
            "events": self.events,
            "command_acks": self.command_acks,
        }
        result_path = self.result_directory / "result.json"
        result_path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        self.get_logger().info(f"PX4_OFFBOARD_RESULT={result_path}")

    def _tick(self) -> None:
        if self.finished:
            return
        now = time.monotonic()
        elapsed_state = now - self.state_started
        if now - self.started > 100.0 and self.state != "landing":
            self._abort("global_timeout")
            return

        if self.state == "waiting_for_data":
            if self._ready(now):
                assert self.odometry is not None
                self.origin_ned = tuple(float(value) for value in self.odometry.position)
                q = [float(value) for value in self.odometry.q]
                self.origin_yaw = math.atan2(
                    2.0 * (q[0] * q[3] + q[1] * q[2]),
                    1.0 - 2.0 * (q[2] * q[2] + q[3] * q[3]),
                )
                self.mission = square_mission_ned(
                    self.origin_ned, self.takeoff_altitude_m, self.leg_m
                )
                self.target_ned = self.origin_ned
                self.publish_enabled = True
                self._transition("warmup", origin_ned=list(self.origin_ned))
            elif elapsed_state > 12.0:
                self._abort("px4_data_unavailable")
            return

        self._publish_setpoint()

        if self.state == "warmup":
            if elapsed_state >= self.warmup_s:
                self._transition("arming")
                self._send_offboard_and_arm()
            return

        if self.state == "arming":
            if self.status is not None:
                armed = int(self.status.arming_state) == int(
                    VehicleStatus.ARMING_STATE_ARMED
                )
                offboard = int(self.status.nav_state) == int(
                    VehicleStatus.NAVIGATION_STATE_OFFBOARD
                )
                if armed and offboard:
                    self._event("armed_and_offboard")
                    self._start_mission_stage(0)
                    return
            if now - self.last_command_at >= 1.0:
                self._send_offboard_and_arm()
            if elapsed_state > 10.0:
                self._abort("arming_or_offboard_rejected")
            return

        if self.state == "mission_stage":
            if self.status is not None and int(self.status.nav_state) != int(
                VehicleStatus.NAVIGATION_STATE_OFFBOARD
            ):
                self._abort("unexpected_offboard_exit")
                return
            if self._current_distance() < 0.35 and elapsed_state >= 1.0:
                self._event(
                    "target_reached",
                    stage=self.mission[self.mission_index][0],
                    error_m=round(self._current_distance(), 3),
                )
                self._start_mission_stage(self.mission_index + 1)
            elif elapsed_state > self.stage_timeout_s:
                self._abort(f"stage_timeout:{self.mission[self.mission_index][0]}")
            return

        if self.state == "hover":
            if elapsed_state < self.hover_s:
                return
            if self.mission_mode == "failsafe":
                self.publish_enabled = False
                self._transition("failsafe_gap")
                self._event("offboard_stream_stopped")
            else:
                self._begin_landing(True, "square_completed", command_land=True)
            return

        if self.state == "failsafe_gap":
            if self.status is not None and int(self.status.nav_state) != int(
                VehicleStatus.NAVIGATION_STATE_OFFBOARD
            ):
                nav_state = int(self.status.nav_state)
                expected_land = nav_state == int(VehicleStatus.NAVIGATION_STATE_AUTO_LAND)
                self._event(
                    "offboard_loss_action",
                    nav_state=nav_state,
                    failsafe=bool(self.status.failsafe),
                    expected_land=expected_land,
                )
                self._begin_landing(
                    expected_land,
                    "offboard_loss_land_observed"
                    if expected_land
                    else f"unexpected_offboard_loss_mode:{nav_state}",
                    command_land=not expected_land,
                )
            elif elapsed_state > 6.0:
                self._begin_landing(
                    False, "offboard_loss_not_detected", command_land=True
                )
            return

        if self.state == "landing":
            armed = self.status is not None and int(self.status.arming_state) == int(
                VehicleStatus.ARMING_STATE_ARMED
            )
            landed = self.land_detected is not None and bool(self.land_detected.landed)
            if landed and not armed:
                self._finish(self.pending_success, self.pending_reason)
                return
            if landed and armed and now - self.last_command_at >= 2.0:
                self._send_disarm_if_landed()
            elif not landed and now - self.last_command_at >= 5.0:
                self._send_land()


def main(args: list[str] | None = None) -> int:
    rclpy.init(args=args)
    try:
        node = OffboardTest()
    except (PermissionError, ValueError) as error:
        print(f"PX4_OFFBOARD_REFUSED={error}")
        rclpy.shutdown()
        return 2
    try:
        while rclpy.ok() and not node.finished:
            rclpy.spin_once(node, timeout_sec=0.1)
        return 0 if node.success else 1
    except KeyboardInterrupt:
        node._abort("keyboard_interrupt")
        deadline = time.monotonic() + 15.0
        while rclpy.ok() and not node.finished and time.monotonic() < deadline:
            rclpy.spin_once(node, timeout_sec=0.1)
        return 130
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
