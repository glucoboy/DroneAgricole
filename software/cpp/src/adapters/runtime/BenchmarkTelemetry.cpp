#include "drone_agricole/core/BenchmarkTelemetry.hpp"

#include <rclcpp/context.hpp>
#include <rclcpp/node.hpp>
#include <rclcpp/node_options.hpp>
#include <std_msgs/msg/float64.hpp>

#include <memory>

namespace drone_agricole::core {

class BenchmarkTelemetryPublisher::Impl final {
 public:
  Impl() {
    context_ = std::make_shared<rclcpp::Context>();
    int argc = 0;
    char** argv = nullptr;
    context_->init(argc, argv);
    rclcpp::NodeOptions options;
    options.context(context_);
    node_ = std::make_shared<rclcpp::Node>("drone_agricole_benchmark_telemetry", options);
    expectedDuration_ = node_->create_publisher<std_msgs::msg::Float64>("/benchmark/expected_duration_s", 10);
    cpuPercent_ = node_->create_publisher<std_msgs::msg::Float64>("/benchmark/cpu_percent_one_core", 10);
    cpuTotal_ = node_->create_publisher<std_msgs::msg::Float64>("/benchmark/cpu_total_seconds", 10);
    memory_ = node_->create_publisher<std_msgs::msg::Float64>("/benchmark/memory_rss_mib", 10);
  }

  ~Impl() { context_->shutdown("Arrêt du publisher de télémétrie benchmark"); }

  void publish(const double expectedDurationSeconds,
               const double cpuPercentOneCore,
               const double cpuTotalSeconds,
               const double memoryRssMib) {
    publishValue(*expectedDuration_, expectedDurationSeconds);
    publishValue(*cpuPercent_, cpuPercentOneCore);
    publishValue(*cpuTotal_, cpuTotalSeconds);
    publishValue(*memory_, memoryRssMib);
  }

 private:
  static void publishValue(rclcpp::Publisher<std_msgs::msg::Float64>& publisher, const double value) {
    std_msgs::msg::Float64 message;
    message.data = value;
    publisher.publish(message);
  }

  std::shared_ptr<rclcpp::Context> context_;
  std::shared_ptr<rclcpp::Node> node_;
  rclcpp::Publisher<std_msgs::msg::Float64>::SharedPtr expectedDuration_;
  rclcpp::Publisher<std_msgs::msg::Float64>::SharedPtr cpuPercent_;
  rclcpp::Publisher<std_msgs::msg::Float64>::SharedPtr cpuTotal_;
  rclcpp::Publisher<std_msgs::msg::Float64>::SharedPtr memory_;
};

BenchmarkTelemetryPublisher::BenchmarkTelemetryPublisher() : impl_(std::make_unique<Impl>()) {}
BenchmarkTelemetryPublisher::~BenchmarkTelemetryPublisher() = default;
void BenchmarkTelemetryPublisher::publish(const double expectedDurationSeconds,
                                          const double cpuPercentOneCore,
                                          const double cpuTotalSeconds,
                                          const double memoryRssMib) {
  impl_->publish(expectedDurationSeconds, cpuPercentOneCore, cpuTotalSeconds, memoryRssMib);
}

}  // namespace drone_agricole::core
