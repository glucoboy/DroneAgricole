#include "drone_agricole_px4_bridge/Frames.hpp"

#include <diagnostic_msgs/msg/diagnostic_array.hpp>
#include <diagnostic_msgs/msg/diagnostic_status.hpp>
#include <diagnostic_msgs/msg/key_value.hpp>
#include <geometry_msgs/msg/pose_stamped.hpp>
#include <geometry_msgs/msg/transform_stamped.hpp>
#include <nav_msgs/msg/odometry.hpp>
#include <nav_msgs/msg/path.hpp>
#include <px4_msgs/msg/battery_status.hpp>
#include <px4_msgs/msg/failsafe_flags.hpp>
#include <px4_msgs/msg/vehicle_odometry.hpp>
#include <px4_msgs/msg/vehicle_status.hpp>
#include <rclcpp/rclcpp.hpp>
#include <std_msgs/msg/string.hpp>
#include <tf2_ros/transform_broadcaster.h>

#include <QHash>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QString>

#include <algorithm>
#include <array>
#include <cmath>
#include <memory>
#include <optional>
#include <string>
#include <utility>

namespace drone_agricole::px4 {
namespace {

QJsonValue finiteValue(const double value) { return std::isfinite(value) ? QJsonValue(value) : QJsonValue(); }

template <typename Range>
QJsonArray jsonVector(const Range& values) {
  QJsonArray result;
  for (const auto value : values) {
    result.append(finiteValue(value));
  }
  return result;
}

QString navigationStateName(const int value) {
  static const QHash<int, QString> names{{0, QStringLiteral("manual")},
                                         {1, QStringLiteral("altitude")},
                                         {2, QStringLiteral("position")},
                                         {3, QStringLiteral("mission")},
                                         {4, QStringLiteral("loiter")},
                                         {5, QStringLiteral("rtl")},
                                         {10, QStringLiteral("acro")},
                                         {12, QStringLiteral("descend")},
                                         {13, QStringLiteral("termination")},
                                         {14, QStringLiteral("offboard")},
                                         {15, QStringLiteral("stabilized")},
                                         {17, QStringLiteral("takeoff")},
                                         {18, QStringLiteral("land")},
                                         {20, QStringLiteral("precision_land")},
                                         {21, QStringLiteral("orbit")}};
  return names.value(value, QStringLiteral("state_%1").arg(value));
}

template <typename Range>
bool allFinite(const Range& values) {
  return std::all_of(values.begin(), values.end(), [](const auto value) { return std::isfinite(value); });
}

}  // namespace

class StateBridge final : public rclcpp::Node {
 public:
  StateBridge() : Node("px4_state_bridge") {
    worldFrame_ = declare_parameter<std::string>("world_frame", "map");
    bodyFrame_ = declare_parameter<std::string>("body_frame", "base_link");
    const auto publishTf = declare_parameter<bool>("publish_tf", true);
    pathMaxPoints_ = std::max<std::size_t>(10, declare_parameter<int>("path_max_points", 2500));
    pathMinDistance_ = std::max(0.0, declare_parameter<double>("path_min_distance_m", 0.05));
    staleAfterSeconds_ = std::max(0.1, declare_parameter<double>("stale_after_s", 1.0));
    const auto statusTopic = declare_parameter<std::string>("vehicle_status_topic", "/fmu/out/vehicle_status_v4");
    const auto batteryTopic = declare_parameter<std::string>("battery_status_topic", "/fmu/out/battery_status_v1");

    auto px4Qos = rclcpp::QoS(rclcpp::KeepLast(1)).best_effort().transient_local();
    auto pathQos = rclcpp::QoS(rclcpp::KeepLast(1)).reliable().transient_local();
    odometryPublisher_ = create_publisher<nav_msgs::msg::Odometry>("/drone/px4/odometry", 10);
    pathPublisher_ = create_publisher<nav_msgs::msg::Path>("/drone/px4/path", pathQos);
    statePublisher_ = create_publisher<std_msgs::msg::String>("/drone/px4/state_json", 10);
    diagnosticsPublisher_ = create_publisher<diagnostic_msgs::msg::DiagnosticArray>("/diagnostics", 10);
    if (publishTf) {
      transformBroadcaster_ = std::make_unique<tf2_ros::TransformBroadcaster>(*this);
    }

    odometrySubscription_ = create_subscription<px4_msgs::msg::VehicleOdometry>(
        "/fmu/out/vehicle_odometry", px4Qos,
        [this](px4_msgs::msg::VehicleOdometry::UniquePtr message) { onOdometry(*message); });
    statusSubscription_ = create_subscription<px4_msgs::msg::VehicleStatus>(
        statusTopic, px4Qos, [this](px4_msgs::msg::VehicleStatus::UniquePtr message) {
          status_ = std::move(message);
          recordReceived(QStringLiteral("vehicle_status"));
        });
    batterySubscription_ = create_subscription<px4_msgs::msg::BatteryStatus>(
        batteryTopic, px4Qos, [this](px4_msgs::msg::BatteryStatus::UniquePtr message) {
          battery_ = std::move(message);
          recordReceived(QStringLiteral("battery_status"));
        });
    failsafeSubscription_ = create_subscription<px4_msgs::msg::FailsafeFlags>(
        "/fmu/out/failsafe_flags", px4Qos, [this](px4_msgs::msg::FailsafeFlags::UniquePtr message) {
          failsafe_ = std::move(message);
          recordReceived(QStringLiteral("failsafe_flags"));
        });
    path_.header.frame_id = worldFrame_;
    timer_ = create_wall_timer(std::chrono::milliseconds(500), [this] { publishStateAndDiagnostics(); });
    RCLCPP_INFO(get_logger(), "Pont PX4 C++ en lecture seule prêt : NED/FRD -> ENU/FLU.");
  }

 private:
  qint64 nowNanoseconds() const { return now().nanoseconds(); }

  void recordReceived(const QString& name) { lastReceived_.insert(name, nowNanoseconds()); }

  std::optional<double> topicAge(const QString& name) const {
    if (!lastReceived_.contains(name)) {
      return std::nullopt;
    }
    return std::max(0.0, static_cast<double>(nowNanoseconds() - lastReceived_.value(name)) * 1.0e-9);
  }

  void onOdometry(const px4_msgs::msg::VehicleOdometry& message) {
    lastPx4Odometry_ = message;
    recordReceived(QStringLiteral("vehicle_odometry"));
    if (message.pose_frame != px4_msgs::msg::VehicleOdometry::POSE_FRAME_NED) {
      if (!unsupportedPoseReported_) {
        RCLCPP_ERROR(get_logger(), "Pose PX4 ignorée : seul le repère NED est qualifié.");
        unsupportedPoseReported_ = true;
      }
      return;
    }
    try {
      const Vector3 positionNed{message.position[0], message.position[1], message.position[2]};
      const Quaternion orientationPx4{message.q[0], message.q[1], message.q[2], message.q[3]};
      const auto position = nedToEnu(positionNed);
      const auto orientation = px4QuaternionToRosXyzw(orientationPx4);
      if (!allFinite(position)) {
        return;
      }
      nav_msgs::msg::Odometry odometry;
      odometry.header.stamp = now();
      odometry.header.frame_id = worldFrame_;
      odometry.child_frame_id = bodyFrame_;
      odometry.pose.pose.position.x = position[0];
      odometry.pose.pose.position.y = position[1];
      odometry.pose.pose.position.z = position[2];
      odometry.pose.pose.orientation.x = orientation[0];
      odometry.pose.pose.orientation.y = orientation[1];
      odometry.pose.pose.orientation.z = orientation[2];
      odometry.pose.pose.orientation.w = orientation[3];
      if (allFinite(message.position_variance)) {
        odometry.pose.covariance[0] = message.position_variance[1];
        odometry.pose.covariance[7] = message.position_variance[0];
        odometry.pose.covariance[14] = message.position_variance[2];
      }
      if (allFinite(message.orientation_variance)) {
        odometry.pose.covariance[21] = message.orientation_variance[0];
        odometry.pose.covariance[28] = message.orientation_variance[1];
        odometry.pose.covariance[35] = message.orientation_variance[2];
      }
      Vector3 linear{};
      const Vector3 velocity{message.velocity[0], message.velocity[1], message.velocity[2]};
      if (message.velocity_frame == px4_msgs::msg::VehicleOdometry::VELOCITY_FRAME_NED) {
        linear = nedVelocityToBodyFlu(orientationPx4, velocity);
      } else if (message.velocity_frame == px4_msgs::msg::VehicleOdometry::VELOCITY_FRAME_BODY_FRD) {
        linear = frdToFlu(velocity);
      } else {
        odometry.twist.covariance[0] = -1.0;
      }
      const auto angular = frdToFlu({message.angular_velocity[0], message.angular_velocity[1],
                                     message.angular_velocity[2]});
      odometry.twist.twist.linear.x = linear[0];
      odometry.twist.twist.linear.y = linear[1];
      odometry.twist.twist.linear.z = linear[2];
      odometry.twist.twist.angular.x = angular[0];
      odometry.twist.twist.angular.y = angular[1];
      odometry.twist.twist.angular.z = angular[2];
      lastRosOdometry_ = odometry;
      odometryPublisher_->publish(odometry);
      updatePath(odometry);
      broadcastTransform(odometry);
    } catch (const std::exception& error) {
      RCLCPP_WARN(get_logger(), "Pose PX4 invalide ignorée : %s", error.what());
    }
  }

  void updatePath(const nav_msgs::msg::Odometry& odometry) {
    const auto& position = odometry.pose.pose.position;
    if (!path_.poses.empty()) {
      const auto& previous = path_.poses.back().pose.position;
      const auto distance = std::hypot(std::hypot(position.x - previous.x, position.y - previous.y),
                                       position.z - previous.z);
      if (distance < pathMinDistance_) {
        return;
      }
    }
    geometry_msgs::msg::PoseStamped pose;
    pose.header = odometry.header;
    pose.pose = odometry.pose.pose;
    path_.poses.push_back(pose);
    if (path_.poses.size() > pathMaxPoints_) {
      path_.poses.erase(path_.poses.begin(), path_.poses.begin() + (path_.poses.size() - pathMaxPoints_));
    }
    path_.header.stamp = odometry.header.stamp;
    pathPublisher_->publish(path_);
  }

  void broadcastTransform(const nav_msgs::msg::Odometry& odometry) {
    if (!transformBroadcaster_) {
      return;
    }
    geometry_msgs::msg::TransformStamped transform;
    transform.header = odometry.header;
    transform.child_frame_id = odometry.child_frame_id;
    transform.transform.translation.x = odometry.pose.pose.position.x;
    transform.transform.translation.y = odometry.pose.pose.position.y;
    transform.transform.translation.z = odometry.pose.pose.position.z;
    transform.transform.rotation = odometry.pose.pose.orientation;
    transformBroadcaster_->sendTransform(transform);
  }

  QJsonObject statePayload() const {
    QJsonObject ages;
    for (const auto& name : {QStringLiteral("vehicle_odometry"), QStringLiteral("vehicle_status"),
                             QStringLiteral("battery_status"), QStringLiteral("failsafe_flags")}) {
      const auto value = topicAge(name);
      ages.insert(name, value ? QJsonValue(*value) : QJsonValue());
    }
    QJsonObject payload{{QStringLiteral("schema"), QStringLiteral("drone_agricole.px4_state.v1")},
                        {QStringLiteral("bridge_time_ns"), static_cast<double>(nowNanoseconds())},
                        {QStringLiteral("topics_age_s"), ages}};
    if (status_) {
      const auto navState = static_cast<int>(status_->nav_state);
      payload.insert(QStringLiteral("vehicle"),
                     QJsonObject{{QStringLiteral("timestamp_us"), static_cast<double>(status_->timestamp)},
                                 {QStringLiteral("armed"), status_->arming_state == px4_msgs::msg::VehicleStatus::ARMING_STATE_ARMED},
                                 {QStringLiteral("arming_state"), status_->arming_state},
                                 {QStringLiteral("nav_state"), navState},
                                 {QStringLiteral("nav_state_name"), navigationStateName(navState)},
                                 {QStringLiteral("failsafe"), status_->failsafe},
                                 {QStringLiteral("preflight_checks_pass"), status_->pre_flight_checks_pass},
                                 {QStringLiteral("gcs_connection_lost"), status_->gcs_connection_lost},
                                 {QStringLiteral("accepts_offboard_setpoints"), status_->accepts_offboard_setpoints}});
    }
    if (battery_) {
      payload.insert(QStringLiteral("battery"),
                     QJsonObject{{QStringLiteral("timestamp_us"), static_cast<double>(battery_->timestamp)},
                                 {QStringLiteral("connected"), battery_->connected},
                                 {QStringLiteral("remaining"), finiteValue(battery_->remaining)},
                                 {QStringLiteral("voltage_v"), finiteValue(battery_->voltage_v)},
                                 {QStringLiteral("current_a"), finiteValue(battery_->current_a)},
                                 {QStringLiteral("warning"), battery_->warning}});
    }
    if (failsafe_) {
      payload.insert(QStringLiteral("failsafe_flags"),
                     QJsonObject{{QStringLiteral("offboard_control_signal_lost"), failsafe_->offboard_control_signal_lost},
                                 {QStringLiteral("local_position_invalid"), failsafe_->local_position_invalid},
                                 {QStringLiteral("global_position_invalid"), failsafe_->global_position_invalid},
                                 {QStringLiteral("manual_control_signal_lost"), failsafe_->manual_control_signal_lost}});
    }
    if (lastPx4Odometry_) {
      payload.insert(QStringLiteral("px4_odometry"),
                     QJsonObject{{QStringLiteral("timestamp_us"), static_cast<double>(lastPx4Odometry_->timestamp)},
                                 {QStringLiteral("pose_frame"), lastPx4Odometry_->pose_frame},
                                 {QStringLiteral("velocity_frame"), lastPx4Odometry_->velocity_frame},
                                 {QStringLiteral("position_ned_m"), jsonVector(lastPx4Odometry_->position)},
                                 {QStringLiteral("quaternion_wxyz"), jsonVector(lastPx4Odometry_->q)},
                                 {QStringLiteral("quality"), lastPx4Odometry_->quality}});
    }
    if (lastRosOdometry_) {
      const auto& position = lastRosOdometry_->pose.pose.position;
      const auto& orientation = lastRosOdometry_->pose.pose.orientation;
      payload.insert(QStringLiteral("ros_odometry"),
                     QJsonObject{{QStringLiteral("frame"), QString::fromStdString(lastRosOdometry_->header.frame_id)},
                                 {QStringLiteral("child_frame"), QString::fromStdString(lastRosOdometry_->child_frame_id)},
                                 {QStringLiteral("position_enu_m"), QJsonArray{position.x, position.y, position.z}},
                                 {QStringLiteral("quaternion_xyzw"),
                                  QJsonArray{orientation.x, orientation.y, orientation.z, orientation.w}},
                                 {QStringLiteral("path_points"), static_cast<double>(path_.poses.size())}});
    }
    return payload;
  }

  diagnostic_msgs::msg::DiagnosticStatus diagnosticStatus() const {
    diagnostic_msgs::msg::DiagnosticStatus result;
    result.name = "PX4 SITL / pont ROS 2 C++";
    result.hardware_id = "px4_sitl_x500";
    const auto age = topicAge(QStringLiteral("vehicle_odometry"));
    if (!status_) {
      result.level = diagnostic_msgs::msg::DiagnosticStatus::ERROR;
      result.message = "Aucun état PX4 reçu";
    } else if (!age || *age > staleAfterSeconds_) {
      result.level = diagnostic_msgs::msg::DiagnosticStatus::ERROR;
      result.message = "Odométrie PX4 absente ou périmée";
    } else if (status_->failsafe) {
      result.level = diagnostic_msgs::msg::DiagnosticStatus::ERROR;
      result.message = "Failsafe PX4 actif";
    } else if (battery_ && battery_->warning >= px4_msgs::msg::BatteryStatus::WARNING_CRITICAL) {
      result.level = diagnostic_msgs::msg::DiagnosticStatus::ERROR;
      result.message = "Batterie PX4 critique";
    } else if (!status_->pre_flight_checks_pass) {
      result.level = diagnostic_msgs::msg::DiagnosticStatus::WARN;
      result.message = "Contrôles pré-vol non validés";
    } else {
      result.level = diagnostic_msgs::msg::DiagnosticStatus::OK;
      result.message = "Liaison PX4–ROS 2 opérationnelle";
    }
    auto keyValue = [](std::string key, std::string value) {
      diagnostic_msgs::msg::KeyValue item;
      item.key = std::move(key);
      item.value = std::move(value);
      return item;
    };
    result.values = {
        keyValue("odometry_age_s", age ? QString::number(*age, 'f', 3).toStdString() : "absent"),
        keyValue("armed", status_ && status_->arming_state == px4_msgs::msg::VehicleStatus::ARMING_STATE_ARMED
                              ? "true"
                              : "false"),
        keyValue("failsafe", status_ && status_->failsafe ? "true" : "false"),
        keyValue("path_points", std::to_string(path_.poses.size()))};
    return result;
  }

  void publishStateAndDiagnostics() {
    std_msgs::msg::String state;
    state.data = QJsonDocument(statePayload()).toJson(QJsonDocument::Compact).toStdString();
    statePublisher_->publish(state);
    diagnostic_msgs::msg::DiagnosticArray diagnostics;
    diagnostics.header.stamp = now();
    diagnostics.status.push_back(diagnosticStatus());
    diagnosticsPublisher_->publish(diagnostics);
  }

  std::string worldFrame_;
  std::string bodyFrame_;
  std::size_t pathMaxPoints_{2500};
  double pathMinDistance_{0.05};
  double staleAfterSeconds_{1.0};
  QHash<QString, qint64> lastReceived_;
  px4_msgs::msg::VehicleStatus::UniquePtr status_;
  px4_msgs::msg::BatteryStatus::UniquePtr battery_;
  px4_msgs::msg::FailsafeFlags::UniquePtr failsafe_;
  std::optional<px4_msgs::msg::VehicleOdometry> lastPx4Odometry_;
  std::optional<nav_msgs::msg::Odometry> lastRosOdometry_;
  nav_msgs::msg::Path path_;
  bool unsupportedPoseReported_{false};
  std::unique_ptr<tf2_ros::TransformBroadcaster> transformBroadcaster_;
  rclcpp::Publisher<nav_msgs::msg::Odometry>::SharedPtr odometryPublisher_;
  rclcpp::Publisher<nav_msgs::msg::Path>::SharedPtr pathPublisher_;
  rclcpp::Publisher<std_msgs::msg::String>::SharedPtr statePublisher_;
  rclcpp::Publisher<diagnostic_msgs::msg::DiagnosticArray>::SharedPtr diagnosticsPublisher_;
  rclcpp::Subscription<px4_msgs::msg::VehicleOdometry>::SharedPtr odometrySubscription_;
  rclcpp::Subscription<px4_msgs::msg::VehicleStatus>::SharedPtr statusSubscription_;
  rclcpp::Subscription<px4_msgs::msg::BatteryStatus>::SharedPtr batterySubscription_;
  rclcpp::Subscription<px4_msgs::msg::FailsafeFlags>::SharedPtr failsafeSubscription_;
  rclcpp::TimerBase::SharedPtr timer_;
};

}  // namespace drone_agricole::px4

int main(int argc, char** argv) {
  rclcpp::init(argc, argv);
  rclcpp::spin(std::make_shared<drone_agricole::px4::StateBridge>());
  rclcpp::shutdown();
  return 0;
}
