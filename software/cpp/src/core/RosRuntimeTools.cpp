#include "drone_agricole/core/RosRuntimeTools.hpp"

#include "drone_agricole/core/BenchmarkSupport.hpp"
#include "drone_agricole/core/JsonUtils.hpp"

#include <rclcpp/rclcpp.hpp>
#include <std_msgs/msg/string.hpp>
#include <std_msgs/msg/u_int64.hpp>

#include <QJsonDocument>

#include <algorithm>
#include <atomic>
#include <chrono>
#include <map>
#include <mutex>

namespace drone_agricole::core {
namespace {

using Clock = std::chrono::steady_clock;

rclcpp::QoS reliableQos(const std::size_t depth) {
  return rclcpp::QoS(rclcpp::KeepLast(depth)).reliable().durability_volatile();
}

class DrainNode final : public rclcpp::Node {
 public:
  explicit DrainNode(const std::string& topic) : Node("lio_pipeline_drain_monitor") {
    subscription_ = create_subscription<std_msgs::msg::String>(
        topic, reliableQos(10), [this](const std_msgs::msg::String::SharedPtr message) {
          QJsonParseError error;
          const auto document = QJsonDocument::fromJson(QByteArray::fromStdString(message->data), &error);
          if (error.error != QJsonParseError::NoError || !document.isObject()) {
            return;
          }
          const std::scoped_lock lock(mutex_);
          if (document.object() != latest_) {
            latest_ = document.object();
            changedAt_ = Clock::now();
          }
        });
  }

  [[nodiscard]] QJsonObject latest() const {
    const std::scoped_lock lock(mutex_);
    return latest_;
  }

  [[nodiscard]] Clock::time_point changedAt() const {
    const std::scoped_lock lock(mutex_);
    return changedAt_;
  }

 private:
  mutable std::mutex mutex_;
  QJsonObject latest_;
  Clock::time_point changedAt_{Clock::now()};
  rclcpp::Subscription<std_msgs::msg::String>::SharedPtr subscription_;
};

class LioSamMonitor final : public rclcpp::Node {
 public:
  LioSamMonitor() : Node("lio_sam_pipeline_monitor") {
    const std::map<std::string, std::string> topics{
        {"scans_received", "/lio_sam/pipeline/scans_received"},
        {"scans_preprocessed", "/lio_sam/pipeline/scans_preprocessed"},
        {"scans_synchronized", "/lio_sam/pipeline/scans_synchronized"},
        {"odometry_published", "/lio_sam/pipeline/odometry_published"},
    };
    for (const auto& [key, topic] : topics) {
      subscriptions_.append(create_subscription<std_msgs::msg::UInt64>(
          topic, reliableQos(100), [this, key](const std_msgs::msg::UInt64::SharedPtr message) {
            const std::scoped_lock lock(mutex_);
            values_[key] = std::max(values_[key], message->data);
          }));
    }
    publisher_ = create_publisher<std_msgs::msg::String>("/lio_sam/pipeline_counters", 10);
    timer_ = create_wall_timer(std::chrono::milliseconds(250), [this] { publish(); });
  }

  [[nodiscard]] QJsonObject snapshot() const {
    const std::scoped_lock lock(mutex_);
    const auto received = values_.at("scans_received");
    const auto preprocessed = values_.at("scans_preprocessed");
    const auto synchronized = values_.at("scans_synchronized");
    const auto odometry = values_.at("odometry_published");
    return {
        {QStringLiteral("schema_version"), 1},
        {QStringLiteral("scans_received"), static_cast<double>(received)},
        {QStringLiteral("scans_preprocessed"), static_cast<double>(preprocessed)},
        {QStringLiteral("scans_synchronized"), static_cast<double>(synchronized)},
        {QStringLiteral("odometry_published"), static_cast<double>(odometry)},
        {QStringLiteral("scans_preprocess_empty"), 0},
        {QStringLiteral("scans_initialization"), static_cast<double>(synchronized > odometry ? synchronized - odometry : 0)},
        {QStringLiteral("scans_imu_processed"), static_cast<double>(preprocessed)},
        {QStringLiteral("scans_rejected_undistort_empty"), 0},
        {QStringLiteral("scans_map_initialization"), 0},
        {QStringLiteral("scans_rejected_downsample"), 0},
        {QStringLiteral("state_updates"), static_cast<double>(odometry)},
        {QStringLiteral("scans_input_buffered"), static_cast<double>(received > preprocessed ? received - preprocessed : 0)},
    };
  }

 private:
  void publish() {
    std_msgs::msg::String message;
    message.data = QJsonDocument(snapshot()).toJson(QJsonDocument::Compact).toStdString();
    publisher_->publish(message);
  }

  mutable std::mutex mutex_;
  std::map<std::string, std::uint64_t> values_{{"scans_received", 0}, {"scans_preprocessed", 0},
                                               {"scans_synchronized", 0}, {"odometry_published", 0}};
  QList<rclcpp::Subscription<std_msgs::msg::UInt64>::SharedPtr> subscriptions_;
  rclcpp::Publisher<std_msgs::msg::String>::SharedPtr publisher_;
  rclcpp::TimerBase::SharedPtr timer_;
};

}  // namespace

QJsonObject waitForPipelineDrain(const QString& bagDirectory,
                                 const QString& inputTopic,
                                 const QString& pipelineTopic,
                                 const double timeoutSeconds,
                                 const double stableSeconds) {
  const auto expected = bagTopicCount(bagDirectory, inputTopic);
  const auto started = Clock::now();
  const auto deadline = started + std::chrono::duration<double>(timeoutSeconds);
  rclcpp::init(0, nullptr);
  auto node = std::make_shared<DrainNode>(pipelineTopic.toStdString());
  rclcpp::executors::SingleThreadedExecutor executor;
  executor.add_node(node);
  QString status = QStringLiteral("timeout");
  while (Clock::now() < deadline) {
    executor.spin_some(std::chrono::milliseconds(100));
    const auto latest = node->latest();
    const auto received = static_cast<qint64>(latest.value(QStringLiteral("scans_received")).toDouble());
    if (received >= expected && Clock::now() - node->changedAt() >= std::chrono::duration<double>(stableSeconds)) {
      status = QStringLiteral("complete");
      break;
    }
  }
  const auto latest = node->latest();
  const auto observed = static_cast<qint64>(latest.value(QStringLiteral("scans_received")).toDouble());
  executor.remove_node(node);
  node.reset();
  rclcpp::shutdown();
  return {
      {QStringLiteral("schema_version"), 1},
      {QStringLiteral("status"), status},
      {QStringLiteral("pipeline_topic"), pipelineTopic},
      {QStringLiteral("input_topic"), inputTopic},
      {QStringLiteral("expected_scans"), static_cast<double>(expected)},
      {QStringLiteral("observed_scans"), static_cast<double>(observed)},
      {QStringLiteral("missing_scans"), static_cast<double>(std::max<qint64>(expected - observed, 0))},
      {QStringLiteral("wait_seconds"), std::chrono::duration<double>(Clock::now() - started).count()},
      {QStringLiteral("stable_seconds_required"), stableSeconds},
      {QStringLiteral("final_counters"), latest.isEmpty() ? QJsonValue(QJsonValue::Null) : QJsonValue(latest)},
  };
}

int runLioSamPipelineMonitor() {
  rclcpp::init(0, nullptr);
  auto node = std::make_shared<LioSamMonitor>();
  rclcpp::spin(node);
  const auto final = node->snapshot();
  RCLCPP_INFO(node->get_logger(), "LIOSAM_PIPELINE_FINAL %s",
              QJsonDocument(final).toJson(QJsonDocument::Compact).constData());
  node.reset();
  rclcpp::shutdown();
  return 0;
}

}  // namespace drone_agricole::core
