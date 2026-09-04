#include "drone_agricole_px4_bridge/OffboardPlan.hpp"

#include <px4_msgs/msg/failsafe_flags.hpp>
#include <px4_msgs/msg/offboard_control_mode.hpp>
#include <px4_msgs/msg/trajectory_setpoint.hpp>
#include <px4_msgs/msg/vehicle_command.hpp>
#include <px4_msgs/msg/vehicle_command_ack.hpp>
#include <px4_msgs/msg/vehicle_land_detected.hpp>
#include <px4_msgs/msg/vehicle_odometry.hpp>
#include <px4_msgs/msg/vehicle_status.hpp>
#include <rclcpp/rclcpp.hpp>

#include <QDateTime>
#include <QDir>
#include <QFileInfo>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QSaveFile>

#include <algorithm>
#include <array>
#include <atomic>
#include <chrono>
#include <cmath>
#include <csignal>
#include <cstdlib>
#include <limits>
#include <memory>
#include <stdexcept>
#include <string>

namespace drone_agricole::px4 {
namespace {

using Clock = std::chrono::steady_clock;
double secondsSince(const Clock::time_point start) {
  return std::chrono::duration<double>(Clock::now() - start).count();
}

bool finiteVector(const std::array<float, 3>& values) {
  return std::all_of(values.begin(), values.end(), [](const auto value) { return std::isfinite(value); });
}

bool finiteQuaternion(const std::array<float, 4>& values) {
  return std::all_of(values.begin(), values.end(), [](const auto value) { return std::isfinite(value); });
}

std::atomic_bool stopRequested{false};
void handleSignal(int) { stopRequested.store(true); }

}  // namespace

class OffboardTest final : public rclcpp::Node {
 public:
  OffboardTest() : Node("px4_offboard_test") {
    const auto execute = declare_parameter<bool>("execute", false);
    missionMode_ = declare_parameter<std::string>("mission_mode", "square");
    altitude_ = declare_parameter<double>("takeoff_altitude_m", 2.0);
    leg_ = declare_parameter<double>("leg_m", 2.0);
    warmupSeconds_ = std::max(1.0, declare_parameter<double>("warmup_s", 2.0));
    hoverSeconds_ = std::max(1.0, declare_parameter<double>("hover_s", 3.0));
    stageTimeoutSeconds_ = std::max(5.0, declare_parameter<double>("stage_timeout_s", 12.0));
    const auto resultRoot = declare_parameter<std::string>("result_root", "results/simulation/px4_lot_a");
    const auto configuredDirectory = declare_parameter<std::string>("result_directory", "");
    if (missionMode_ != "square" && missionMode_ != "failsafe") {
      throw std::invalid_argument("mission_mode doit valoir square ou failsafe");
    }
    if (!execute) {
      throw std::runtime_error("Essai refusé : execute:=true est requis.");
    }
    const auto* sitl = std::getenv("DRONE_AGRICOLE_SITL");
    if (sitl == nullptr || std::string(sitl) != "1") {
      throw std::runtime_error("Essai refusé : le verrou d'environnement SITL est absent.");
    }
    static_cast<void>(squareMissionNed({0.0, 0.0, 0.0}, altitude_, leg_));
    configureResultDirectory(resultRoot, configuredDirectory);

    auto qos = rclcpp::QoS(rclcpp::KeepLast(1)).best_effort().transient_local();
    offboardPublisher_ = create_publisher<px4_msgs::msg::OffboardControlMode>("/fmu/in/offboard_control_mode", qos);
    trajectoryPublisher_ = create_publisher<px4_msgs::msg::TrajectorySetpoint>("/fmu/in/trajectory_setpoint", qos);
    commandPublisher_ = create_publisher<px4_msgs::msg::VehicleCommand>("/fmu/in/vehicle_command", qos);
    odometrySubscription_ = create_subscription<px4_msgs::msg::VehicleOdometry>(
        "/fmu/out/vehicle_odometry", qos, [this](px4_msgs::msg::VehicleOdometry::UniquePtr message) {
          odometry_ = std::move(message);
          lastOdometry_ = Clock::now();
          if (originSet_ && std::isfinite(odometry_->position[2])) {
            maxAltitude_ = std::max(maxAltitude_, origin_[2] - static_cast<double>(odometry_->position[2]));
          }
        });
    statusSubscription_ = create_subscription<px4_msgs::msg::VehicleStatus>(
        "/fmu/out/vehicle_status_v4", qos, [this](px4_msgs::msg::VehicleStatus::UniquePtr message) {
          status_ = std::move(message);
          lastStatus_ = Clock::now();
          offboardEntered_ = offboardEntered_ ||
                              status_->nav_state == px4_msgs::msg::VehicleStatus::NAVIGATION_STATE_OFFBOARD;
          armedObserved_ = armedObserved_ ||
                           status_->arming_state == px4_msgs::msg::VehicleStatus::ARMING_STATE_ARMED;
          failsafeObserved_ = failsafeObserved_ || status_->failsafe;
        });
    failsafeSubscription_ = create_subscription<px4_msgs::msg::FailsafeFlags>(
        "/fmu/out/failsafe_flags", qos, [this](px4_msgs::msg::FailsafeFlags::UniquePtr message) {
          failsafe_ = std::move(message);
          if (state_ == "failsafe_gap" && failsafe_->offboard_control_signal_lost) {
            offboardLossObserved_ = true;
          }
        });
    landSubscription_ = create_subscription<px4_msgs::msg::VehicleLandDetected>(
        "/fmu/out/vehicle_land_detected", qos,
        [this](px4_msgs::msg::VehicleLandDetected::UniquePtr message) { landDetected_ = std::move(message); });
    ackSubscription_ = create_subscription<px4_msgs::msg::VehicleCommandAck>(
        "/fmu/out/vehicle_command_ack_v1", qos, [this](px4_msgs::msg::VehicleCommandAck::UniquePtr message) {
          QJsonObject ack{{QStringLiteral("command"), static_cast<double>(message->command)},
                          {QStringLiteral("result"), static_cast<int>(message->result)},
                          {QStringLiteral("result_param1"), static_cast<int>(message->result_param1)},
                          {QStringLiteral("result_param2"), static_cast<int>(message->result_param2)}};
          acknowledgements_.append(ack);
          event(QStringLiteral("command_ack"), ack);
        });
    started_ = Clock::now();
    stateStarted_ = started_;
    timer_ = create_wall_timer(std::chrono::milliseconds(50), [this] { tick(); });
    event(QStringLiteral("test_started"), {{QStringLiteral("mode"), QString::fromStdString(missionMode_)}});
    RCLCPP_WARN(get_logger(), "Essai PX4 autorisé uniquement en SITL : mode=%s", missionMode_.c_str());
  }

  bool finished() const { return finished_; }
  bool success() const { return success_; }
  void requestAbort(const QString& reason) { abort(reason); }

 private:
  void configureResultDirectory(const std::string& root, const std::string& configured) {
    const auto workspace = QDir::current().absolutePath();
    const auto approvedRoot = QFileInfo(QDir(workspace).filePath(QStringLiteral("results/simulation/px4_lot_a"))).absoluteFilePath();
    if (!configured.empty()) {
      resultDirectory_ = QFileInfo(QDir(workspace).filePath(QString::fromStdString(configured))).absoluteFilePath();
      if (!resultDirectory_.startsWith(approvedRoot + QDir::separator()) || QFileInfo::exists(resultDirectory_)) {
        throw std::invalid_argument("result_directory doit être nouveau et rester dans results/simulation/px4_lot_a");
      }
      return;
    }
    const auto absoluteRoot = QFileInfo(QDir(workspace).filePath(QString::fromStdString(root))).absoluteFilePath();
    if (!absoluteRoot.startsWith(workspace + QDir::separator())) {
      throw std::invalid_argument("result_root doit rester dans le workspace");
    }
    const auto stamp = QDateTime::currentDateTimeUtc().toString(QStringLiteral("yyyyMMddTHHmmss.zzzZ"));
    resultDirectory_ = QDir(absoluteRoot).filePath(QString::fromStdString(missionMode_) + QLatin1Char('_') + stamp);
  }

  quint64 timestampMicroseconds() const { return static_cast<quint64>(now().nanoseconds() / 1000); }
  double stateElapsed() const { return secondsSince(stateStarted_); }

  void event(const QString& name, QJsonObject details = {}) {
    QJsonObject item{{QStringLiteral("event"), name},
                     {QStringLiteral("elapsed_s"), secondsSince(started_)},
                     {QStringLiteral("state"), QString::fromStdString(state_)}};
    for (auto iterator = details.constBegin(); iterator != details.constEnd(); ++iterator) {
      item.insert(iterator.key(), iterator.value());
    }
    events_.append(item);
    RCLCPP_INFO(get_logger(), "%s", QJsonDocument(item).toJson(QJsonDocument::Compact).constData());
  }

  void transition(const std::string& state, QJsonObject details = {}) {
    state_ = state;
    stateStarted_ = Clock::now();
    details.insert(QStringLiteral("new_state"), QString::fromStdString(state));
    event(QStringLiteral("state_changed"), details);
  }

  bool ready() const {
    return status_ && odometry_ && secondsSince(lastStatus_) < 1.0 && secondsSince(lastOdometry_) < 0.5 &&
           odometry_->pose_frame == px4_msgs::msg::VehicleOdometry::POSE_FRAME_NED &&
           finiteVector(odometry_->position) && finiteQuaternion(odometry_->q);
  }

  bool armed() const {
    return status_ && status_->arming_state == px4_msgs::msg::VehicleStatus::ARMING_STATE_ARMED;
  }

  double currentDistance() const {
    if (!odometry_ || !targetSet_) {
      return std::numeric_limits<double>::infinity();
    }
    const auto x = static_cast<double>(odometry_->position[0]) - target_[0];
    const auto y = static_cast<double>(odometry_->position[1]) - target_[1];
    const auto z = static_cast<double>(odometry_->position[2]) - target_[2];
    return std::hypot(std::hypot(x, y), z);
  }

  void publishSetpoint() {
    if (!publishEnabled_ || !targetSet_) {
      return;
    }
    px4_msgs::msg::OffboardControlMode mode;
    mode.timestamp = timestampMicroseconds();
    mode.position = true;
    offboardPublisher_->publish(mode);
    px4_msgs::msg::TrajectorySetpoint setpoint;
    setpoint.timestamp = mode.timestamp;
    setpoint.position = {static_cast<float>(target_[0]), static_cast<float>(target_[1]), static_cast<float>(target_[2])};
    const auto nan = std::numeric_limits<float>::quiet_NaN();
    setpoint.velocity = {nan, nan, nan};
    setpoint.acceleration = {nan, nan, nan};
    setpoint.jerk = {nan, nan, nan};
    setpoint.yaw = static_cast<float>(originYaw_);
    setpoint.yawspeed = nan;
    trajectoryPublisher_->publish(setpoint);
  }

  void sendCommand(const std::uint32_t command, const float parameter1 = 0.0F, const float parameter2 = 0.0F) {
    px4_msgs::msg::VehicleCommand message;
    message.timestamp = timestampMicroseconds();
    message.command = command;
    message.param1 = parameter1;
    message.param2 = parameter2;
    message.target_system = 1;
    message.target_component = 1;
    message.source_system = 1;
    message.source_component = 1;
    message.from_external = true;
    commandPublisher_->publish(message);
    event(QStringLiteral("command_sent"), {{QStringLiteral("command"), static_cast<double>(command)},
                                           {QStringLiteral("param1"), parameter1},
                                           {QStringLiteral("param2"), parameter2}});
    lastCommand_ = Clock::now();
  }

  void sendOffboardAndArm() {
    sendCommand(px4_msgs::msg::VehicleCommand::VEHICLE_CMD_DO_SET_MODE, 1.0F, 6.0F);
    sendCommand(px4_msgs::msg::VehicleCommand::VEHICLE_CMD_COMPONENT_ARM_DISARM, 1.0F);
  }

  void beginLanding(const bool expectedSuccess, const QString& reason, const bool commandLand) {
    pendingSuccess_ = expectedSuccess;
    pendingReason_ = reason;
    publishEnabled_ = false;
    transition("landing", {{QStringLiteral("expected_success"), expectedSuccess}, {QStringLiteral("reason"), reason}});
    if (commandLand) {
      sendCommand(px4_msgs::msg::VehicleCommand::VEHICLE_CMD_NAV_LAND);
    } else {
      lastCommand_ = Clock::now();
    }
  }

  void abort(const QString& reason) {
    if (finished_ || state_ == "landing") {
      return;
    }
    event(QStringLiteral("abort_requested"), {{QStringLiteral("reason"), reason}});
    if (armed()) {
      beginLanding(false, reason, true);
    } else {
      finish(false, reason);
    }
  }

  void startMissionStage(const int index) {
    if (index >= static_cast<int>(mission_.size())) {
      transition("hover");
      return;
    }
    missionIndex_ = index;
    target_ = mission_[index].targetNed;
    targetSet_ = true;
    transition("mission_stage", {{QStringLiteral("stage"), QString::fromStdString(mission_[index].name)},
                                  {QStringLiteral("target_ned"), QJsonArray{target_[0], target_[1], target_[2]}}});
  }

  void finish(const bool success, const QString& reason) {
    if (finished_) {
      return;
    }
    finished_ = true;
    success_ = success;
    publishEnabled_ = false;
    event(QStringLiteral("test_finished"), {{QStringLiteral("success"), success}, {QStringLiteral("reason"), reason}});
    if (!QDir().mkpath(resultDirectory_)) {
      RCLCPP_ERROR(get_logger(), "Impossible de créer le répertoire de résultat");
      success_ = false;
      return;
    }
    QJsonObject result{
        {QStringLiteral("schema"), QStringLiteral("drone_agricole.px4_offboard_test.v1")},
        {QStringLiteral("created_utc"), QDateTime::currentDateTimeUtc().toString(Qt::ISODateWithMs)},
        {QStringLiteral("success"), success},
        {QStringLiteral("reason"), reason},
        {QStringLiteral("mode"), QString::fromStdString(missionMode_)},
        {QStringLiteral("parameters"), QJsonObject{{QStringLiteral("takeoff_altitude_m"), altitude_},
                                                    {QStringLiteral("leg_m"), leg_},
                                                    {QStringLiteral("warmup_s"), warmupSeconds_},
                                                    {QStringLiteral("hover_s"), hoverSeconds_}}},
        {QStringLiteral("observations"), QJsonObject{{QStringLiteral("offboard_entered"), offboardEntered_},
                                                      {QStringLiteral("armed"), armedObserved_},
                                                      {QStringLiteral("failsafe"), failsafeObserved_},
                                                      {QStringLiteral("offboard_loss_flag"), offboardLossObserved_},
                                                      {QStringLiteral("max_altitude_m"), maxAltitude_},
                                                      {QStringLiteral("landed"), landDetected_ && landDetected_->landed}}},
        {QStringLiteral("origin_ned_m"), originSet_ ? QJsonValue(QJsonArray{origin_[0], origin_[1], origin_[2]}) : QJsonValue()},
        {QStringLiteral("events"), events_},
        {QStringLiteral("command_acks"), acknowledgements_}};
    const auto resultPath = QDir(resultDirectory_).filePath(QStringLiteral("result.json"));
    QSaveFile file(resultPath);
    if (file.open(QIODevice::WriteOnly)) {
      file.write(QJsonDocument(result).toJson(QJsonDocument::Indented));
      file.commit();
    }
    RCLCPP_INFO(get_logger(), "PX4_OFFBOARD_RESULT=%s", resultPath.toStdString().c_str());
  }

  void tick() {
    if (finished_) {
      return;
    }
    if (secondsSince(started_) > 100.0 && state_ != "landing") {
      abort(QStringLiteral("global_timeout"));
      return;
    }
    if (state_ == "waiting_for_data") {
      if (ready()) {
        origin_ = {odometry_->position[0], odometry_->position[1], odometry_->position[2]};
        originSet_ = true;
        const auto& q = odometry_->q;
        originYaw_ = std::atan2(2.0 * (q[0] * q[3] + q[1] * q[2]),
                                1.0 - 2.0 * (q[2] * q[2] + q[3] * q[3]));
        mission_ = squareMissionNed(origin_, altitude_, leg_);
        target_ = origin_;
        targetSet_ = true;
        publishEnabled_ = true;
        transition("warmup", {{QStringLiteral("origin_ned"), QJsonArray{origin_[0], origin_[1], origin_[2]}}});
      } else if (stateElapsed() > 12.0) {
        abort(QStringLiteral("px4_data_unavailable"));
      }
      return;
    }
    publishSetpoint();
    if (state_ == "warmup") {
      if (stateElapsed() >= warmupSeconds_) {
        transition("arming");
        sendOffboardAndArm();
      }
    } else if (state_ == "arming") {
      const auto offboard = status_ && status_->nav_state == px4_msgs::msg::VehicleStatus::NAVIGATION_STATE_OFFBOARD;
      if (armed() && offboard) {
        event(QStringLiteral("armed_and_offboard"));
        startMissionStage(0);
      } else if (secondsSince(lastCommand_) >= 1.0) {
        sendOffboardAndArm();
      } else if (stateElapsed() > 10.0) {
        abort(QStringLiteral("arming_or_offboard_rejected"));
      }
    } else if (state_ == "mission_stage") {
      if (status_ && status_->nav_state != px4_msgs::msg::VehicleStatus::NAVIGATION_STATE_OFFBOARD) {
        abort(QStringLiteral("unexpected_offboard_exit"));
      } else if (currentDistance() < 0.35 && stateElapsed() >= 1.0) {
        event(QStringLiteral("target_reached"), {{QStringLiteral("stage"), QString::fromStdString(mission_[missionIndex_].name)},
                                                  {QStringLiteral("error_m"), currentDistance()}});
        startMissionStage(missionIndex_ + 1);
      } else if (stateElapsed() > stageTimeoutSeconds_) {
        abort(QStringLiteral("stage_timeout:%1").arg(QString::fromStdString(mission_[missionIndex_].name)));
      }
    } else if (state_ == "hover" && stateElapsed() >= hoverSeconds_) {
      if (missionMode_ == "failsafe") {
        publishEnabled_ = false;
        transition("failsafe_gap");
        event(QStringLiteral("offboard_stream_stopped"));
      } else {
        beginLanding(true, QStringLiteral("square_completed"), true);
      }
    } else if (state_ == "failsafe_gap") {
      if (status_ && status_->nav_state != px4_msgs::msg::VehicleStatus::NAVIGATION_STATE_OFFBOARD) {
        const auto expected = status_->nav_state == px4_msgs::msg::VehicleStatus::NAVIGATION_STATE_AUTO_LAND;
        event(QStringLiteral("offboard_loss_action"), {{QStringLiteral("nav_state"), status_->nav_state},
                                                        {QStringLiteral("failsafe"), status_->failsafe},
                                                        {QStringLiteral("expected_land"), expected}});
        beginLanding(expected, expected ? QStringLiteral("offboard_loss_land_observed")
                                        : QStringLiteral("unexpected_offboard_loss_mode:%1").arg(status_->nav_state),
                     !expected);
      } else if (stateElapsed() > 6.0) {
        beginLanding(false, QStringLiteral("offboard_loss_not_detected"), true);
      }
    } else if (state_ == "landing") {
      const auto landed = landDetected_ && landDetected_->landed;
      if (landed && !armed()) {
        finish(pendingSuccess_, pendingReason_);
      } else if (landed && armed() && secondsSince(lastCommand_) >= 2.0) {
        sendCommand(px4_msgs::msg::VehicleCommand::VEHICLE_CMD_COMPONENT_ARM_DISARM, 0.0F);
      } else if (!landed && secondsSince(lastCommand_) >= 5.0) {
        sendCommand(px4_msgs::msg::VehicleCommand::VEHICLE_CMD_NAV_LAND);
      }
    }
  }

  std::string missionMode_;
  double altitude_{2.0};
  double leg_{2.0};
  double warmupSeconds_{2.0};
  double hoverSeconds_{3.0};
  double stageTimeoutSeconds_{12.0};
  QString resultDirectory_;
  std::string state_{"waiting_for_data"};
  Clock::time_point started_{Clock::now()};
  Clock::time_point stateStarted_{Clock::now()};
  Clock::time_point lastStatus_{Clock::time_point::min()};
  Clock::time_point lastOdometry_{Clock::time_point::min()};
  Clock::time_point lastCommand_{Clock::time_point::min()};
  px4_msgs::msg::VehicleStatus::UniquePtr status_;
  px4_msgs::msg::VehicleOdometry::UniquePtr odometry_;
  px4_msgs::msg::FailsafeFlags::UniquePtr failsafe_;
  px4_msgs::msg::VehicleLandDetected::UniquePtr landDetected_;
  Vector3 origin_{};
  Vector3 target_{};
  bool originSet_{false};
  bool targetSet_{false};
  double originYaw_{0.0};
  std::vector<MissionStage> mission_;
  int missionIndex_{-1};
  bool publishEnabled_{false};
  bool finished_{false};
  bool success_{false};
  bool pendingSuccess_{false};
  QString pendingReason_;
  bool offboardEntered_{false};
  bool armedObserved_{false};
  bool failsafeObserved_{false};
  bool offboardLossObserved_{false};
  double maxAltitude_{0.0};
  QJsonArray events_;
  QJsonArray acknowledgements_;
  rclcpp::Publisher<px4_msgs::msg::OffboardControlMode>::SharedPtr offboardPublisher_;
  rclcpp::Publisher<px4_msgs::msg::TrajectorySetpoint>::SharedPtr trajectoryPublisher_;
  rclcpp::Publisher<px4_msgs::msg::VehicleCommand>::SharedPtr commandPublisher_;
  rclcpp::Subscription<px4_msgs::msg::VehicleOdometry>::SharedPtr odometrySubscription_;
  rclcpp::Subscription<px4_msgs::msg::VehicleStatus>::SharedPtr statusSubscription_;
  rclcpp::Subscription<px4_msgs::msg::FailsafeFlags>::SharedPtr failsafeSubscription_;
  rclcpp::Subscription<px4_msgs::msg::VehicleLandDetected>::SharedPtr landSubscription_;
  rclcpp::Subscription<px4_msgs::msg::VehicleCommandAck>::SharedPtr ackSubscription_;
  rclcpp::TimerBase::SharedPtr timer_;
};

}  // namespace drone_agricole::px4

int main(int argc, char** argv) {
  rclcpp::init(argc, argv, rclcpp::InitOptions(), rclcpp::SignalHandlerOptions::None);
  std::signal(SIGINT, drone_agricole::px4::handleSignal);
  std::signal(SIGTERM, drone_agricole::px4::handleSignal);
  try {
    auto node = std::make_shared<drone_agricole::px4::OffboardTest>();
    rclcpp::executors::SingleThreadedExecutor executor;
    executor.add_node(node);
    while (rclcpp::ok() && !node->finished()) {
      executor.spin_some(std::chrono::milliseconds(100));
      if (drone_agricole::px4::stopRequested.exchange(false)) {
        node->requestAbort(QStringLiteral("signal_interrupt"));
      }
    }
    const auto result = node->success() ? 0 : 1;
    rclcpp::shutdown();
    return result;
  } catch (const std::exception& error) {
    std::fprintf(stderr, "PX4_OFFBOARD_REFUSED=%s\n", error.what());
    rclcpp::shutdown();
    return 2;
  }
}
