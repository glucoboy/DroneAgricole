#include "drone_agricole/core/LiveTelemetry.hpp"
#include "drone_agricole/core/AdaptivePointMap.hpp"

#include <Eigen/Dense>
#include <geometry_msgs/msg/pose_stamped.hpp>
#include <nav_msgs/msg/odometry.hpp>
#include <rclcpp/executors/single_threaded_executor.hpp>
#include <rclcpp/rclcpp.hpp>
#include <sensor_msgs/msg/point_cloud2.hpp>
#include <std_msgs/msg/float64.hpp>
#include <std_msgs/msg/string.hpp>

#include <QJsonDocument>
#include <QtEndian>

#include <algorithm>
#include <cmath>
#include <cstring>
#include <mutex>
#include <thread>
#include <type_traits>
#include <utility>
#include <vector>

namespace drone_agricole::core {
namespace {

struct TimedPosition {
  double time{0.0};
  QVector3D position;
};

constexpr float initialCloudVoxelSizeMeters = 0.08F;
constexpr std::size_t maximumAccumulatedCloudPoints = 250000;
constexpr qsizetype maximumSnapshotCloudPoints = 16000;

double seconds(const builtin_interfaces::msg::Time& stamp) {
  return static_cast<double>(stamp.sec) + static_cast<double>(stamp.nanosec) * 1e-9;
}

template <typename Values>
QList<QVector3D> downsample(const Values& values, const qsizetype maximum = 2400) {
  QList<QVector3D> result;
  if (values.empty()) {
    return result;
  }
  const auto step = std::max<std::size_t>(1, (values.size() + static_cast<std::size_t>(maximum) - 1) /
                                                 static_cast<std::size_t>(maximum));
  result.reserve(static_cast<qsizetype>((values.size() + step - 1) / step));
  for (std::size_t index = 0; index < values.size(); index += step) {
    if constexpr (std::is_same_v<typename Values::value_type, TimedPosition>) {
      result.append(values.at(index).position);
    } else {
      result.append(values.at(index));
    }
  }
  return result;
}

struct Alignment {
  QList<QVector3D> truthInEstimate;
  double ateRmse{0.0};
  bool valid{false};
};

Alignment alignTruth(const std::vector<TimedPosition>& estimate, const std::vector<TimedPosition>& truth) {
  if (estimate.size() < 3 || truth.size() < 3) {
    return {downsample(truth), 0.0, false};
  }
  std::vector<Eigen::Vector3d> source;
  std::vector<Eigen::Vector3d> target;
  source.reserve(estimate.size());
  target.reserve(estimate.size());
  for (const auto& value : estimate) {
    const auto right = std::lower_bound(truth.cbegin(), truth.cend(), value.time,
                                        [](const auto& item, const double time) { return item.time < time; });
    auto nearest = right;
    if (right == truth.cend()) {
      nearest = std::prev(truth.cend());
    } else if (right != truth.cbegin()) {
      const auto left = std::prev(right);
      nearest = std::abs(left->time - value.time) <= std::abs(right->time - value.time) ? left : right;
    }
    if (std::abs(nearest->time - value.time) > 0.08) {
      continue;
    }
    source.emplace_back(value.position.x(), value.position.y(), value.position.z());
    target.emplace_back(nearest->position.x(), nearest->position.y(), nearest->position.z());
  }
  if (source.size() < 3) {
    return {downsample(truth), 0.0, false};
  }
  Eigen::Vector3d sourceCenter = Eigen::Vector3d::Zero();
  Eigen::Vector3d targetCenter = Eigen::Vector3d::Zero();
  for (std::size_t index = 0; index < source.size(); ++index) {
    sourceCenter += source.at(index);
    targetCenter += target.at(index);
  }
  sourceCenter /= static_cast<double>(source.size());
  targetCenter /= static_cast<double>(target.size());
  Eigen::Matrix3d covariance = Eigen::Matrix3d::Zero();
  for (std::size_t index = 0; index < source.size(); ++index) {
    covariance += (source.at(index) - sourceCenter) * (target.at(index) - targetCenter).transpose();
  }
  const Eigen::JacobiSVD<Eigen::Matrix3d> svd(covariance, Eigen::ComputeFullU | Eigen::ComputeFullV);
  Eigen::Matrix3d rotation = svd.matrixV() * svd.matrixU().transpose();
  if (rotation.determinant() < 0.0) {
    auto corrected = svd.matrixV();
    corrected.col(2) *= -1.0;
    rotation = corrected * svd.matrixU().transpose();
  }
  const auto translation = targetCenter - rotation * sourceCenter;
  double squaredError = 0.0;
  for (std::size_t index = 0; index < source.size(); ++index) {
    squaredError += (rotation * source.at(index) + translation - target.at(index)).squaredNorm();
  }
  QList<QVector3D> transformed;
  const auto sampledTruth = downsample(truth);
  transformed.reserve(sampledTruth.size());
  for (const auto& point : sampledTruth) {
    const Eigen::Vector3d value(point.x(), point.y(), point.z());
    const auto inEstimate = rotation.transpose() * (value - translation);
    transformed.append(QVector3D(static_cast<float>(inEstimate.x()), static_cast<float>(inEstimate.y()),
                                 static_cast<float>(inEstimate.z())));
  }
  return {transformed, std::sqrt(squaredError / static_cast<double>(source.size())), true};
}

float cloudCoordinate(const sensor_msgs::msg::PointCloud2& message, const std::size_t offset) {
  quint32 bits = 0;
  std::memcpy(&bits, message.data.data() + offset, sizeof(bits));
  bits = message.is_bigendian ? qFromBigEndian(bits) : qFromLittleEndian(bits);
  float value = 0.0F;
  std::memcpy(&value, &bits, sizeof(value));
  return value;
}

}  // namespace

class LiveTelemetry::Impl final {
 public:
  Impl() {
    context_ = std::make_shared<rclcpp::Context>();
    int argc = 0;
    char** argv = nullptr;
    context_->init(argc, argv);
    rclcpp::NodeOptions nodeOptions;
    nodeOptions.context(context_);
    node_ = std::make_shared<rclcpp::Node>("drone_agricole_qt_dashboard", nodeOptions);
    rclcpp::ExecutorOptions executorOptions;
    executorOptions.context = context_;
    executor_ = std::make_unique<rclcpp::executors::SingleThreadedExecutor>(executorOptions);
    executor_->add_node(node_);
    const auto sensorQos = rclcpp::SensorDataQoS();
    odometry_ = node_->create_subscription<nav_msgs::msg::Odometry>(
        "/Odometry", sensorQos, [this](const nav_msgs::msg::Odometry& message) {
          std::scoped_lock lock(mutex_);
          appendTimed(estimate_, seconds(message.header.stamp), message.pose.pose.position.x,
                      message.pose.pose.position.y, message.pose.pose.position.z);
        });
    truthSubscription_ = node_->create_subscription<geometry_msgs::msg::PoseStamped>(
        "/gt_poses", sensorQos, [this](const geometry_msgs::msg::PoseStamped& message) {
          std::scoped_lock lock(mutex_);
          appendTimed(truth_, seconds(message.header.stamp), message.pose.position.x, message.pose.position.y,
                      message.pose.position.z);
        });
    cloudSubscription_ = node_->create_subscription<sensor_msgs::msg::PointCloud2>(
        "/cloud_registered", sensorQos,
        [this](const sensor_msgs::msg::PointCloud2& message) { receiveCloud(message); });
    px4Odometry_ = node_->create_subscription<nav_msgs::msg::Odometry>(
        "/drone/px4/odometry", sensorQos, [this](const nav_msgs::msg::Odometry& message) {
          std::scoped_lock lock(mutex_);
          const QVector3D position(static_cast<float>(message.pose.pose.position.x),
                                   static_cast<float>(message.pose.pose.position.y),
                                   static_cast<float>(message.pose.pose.position.z));
          if (px4Path_.empty() || (px4Path_.back() - position).length() >= 0.03F) {
            px4Path_.push_back(position);
            if (px4Path_.size() > 12000) {
              px4Path_.erase(px4Path_.begin(), px4Path_.begin() + 2000);
            }
          }
        });
    const auto metric = [this](const QString& id) {
      return [this, id](const std_msgs::msg::Float64& message) {
        std::scoped_lock lock(mutex_);
        metrics_.insert(id, message.data);
      };
    };
    cpu_ = node_->create_subscription<std_msgs::msg::Float64>(
        "/benchmark/cpu_percent_one_core", 10, metric(QStringLiteral("cpu_percent_one_core")));
    cpuTotal_ = node_->create_subscription<std_msgs::msg::Float64>(
        "/benchmark/cpu_total_seconds", 10, metric(QStringLiteral("cpu_total_seconds")));
    memory_ = node_->create_subscription<std_msgs::msg::Float64>(
        "/benchmark/memory_rss_mib", 10, metric(QStringLiteral("memory_rss_mib")));
    expectedDuration_ = node_->create_subscription<std_msgs::msg::Float64>(
        "/benchmark/expected_duration_s", 10, metric(QStringLiteral("expected_duration_s")));
    for (const auto& topic : {"/fast_lio2/pipeline_counters", "/point_lio/pipeline_counters",
                              "/lio_sam/pipeline_counters"}) {
      counterSubscriptions_.push_back(node_->create_subscription<std_msgs::msg::String>(
          topic, 10, [this](const std_msgs::msg::String& message) { receiveJson(message.data, false); }));
    }
    px4StateSubscription_ = node_->create_subscription<std_msgs::msg::String>(
        "/drone/px4/state_json", 10,
        [this](const std_msgs::msg::String& message) { receiveJson(message.data, true); });
    worker_ = std::thread([this] { executor_->spin(); });
  }

  ~Impl() {
    executor_->cancel();
    if (worker_.joinable()) {
      worker_.join();
    }
    executor_->remove_node(node_);
    context_->shutdown(QStringLiteral("Arrêt du tableau de bord Qt").toStdString());
  }

  void reset() {
    std::scoped_lock lock(mutex_);
    estimate_.clear();
    truth_.clear();
    cloudMap_.clear();
    cloudFrameCount_ = 0;
    px4Path_.clear();
    metrics_ = {};
    px4State_ = {};
  }

  LiveTelemetrySnapshot snapshot() const {
    std::vector<TimedPosition> estimate;
    std::vector<TimedPosition> truth;
    std::vector<QVector3D> cloud;
    std::vector<QVector3D> px4;
    std::size_t cloudFrameCount = 0;
    float cloudVoxelSizeMeters = initialCloudVoxelSizeMeters;
    std::size_t mapCompactionCount = 0;
    QJsonObject metrics;
    QJsonObject px4State;
    {
      std::scoped_lock lock(mutex_);
      estimate = estimate_;
      truth = truth_;
      cloud = cloudMap_.points();
      cloudFrameCount = cloudFrameCount_;
      cloudVoxelSizeMeters = cloudMap_.voxelSizeMeters();
      mapCompactionCount = cloudMap_.compactionCount();
      px4 = px4Path_;
      metrics = metrics_;
      px4State = px4State_;
    }
    const auto alignment = alignTruth(estimate, truth);
    metrics.insert(QStringLiteral("odometry_count"), static_cast<double>(estimate.size()));
    metrics.insert(QStringLiteral("reference_count"), static_cast<double>(truth.size()));
    metrics.insert(QStringLiteral("output_ratio_percent"), truth.empty() ? 0.0 : 100.0 * estimate.size() / truth.size());
    metrics.insert(QStringLiteral("map_point_count"), static_cast<double>(cloud.size()));
    metrics.insert(QStringLiteral("cloud_frame_count"), static_cast<double>(cloudFrameCount));
    metrics.insert(QStringLiteral("map_capacity_percent"),
                   100.0 * static_cast<double>(cloud.size()) /
                       static_cast<double>(maximumAccumulatedCloudPoints));
    metrics.insert(QStringLiteral("map_voxel_size_m"), static_cast<double>(cloudVoxelSizeMeters));
    metrics.insert(QStringLiteral("map_compaction_count"), static_cast<double>(mapCompactionCount));
    if (alignment.valid) {
      metrics.insert(QStringLiteral("ate_rmse_m"), alignment.ateRmse);
    }
    return LiveTelemetrySnapshot{true, downsample(cloud, maximumSnapshotCloudPoints), downsample(estimate), alignment.truthInEstimate,
                                 downsample(px4), metrics, px4State};
  }

 private:
  mutable std::mutex mutex_;
  std::shared_ptr<rclcpp::Context> context_;
  std::shared_ptr<rclcpp::Node> node_;
  std::unique_ptr<rclcpp::executors::SingleThreadedExecutor> executor_;
  std::thread worker_;
  std::vector<TimedPosition> estimate_;
  std::vector<TimedPosition> truth_;
  AdaptivePointMap cloudMap_{initialCloudVoxelSizeMeters, maximumAccumulatedCloudPoints};
  std::size_t cloudFrameCount_{0};
  std::vector<QVector3D> px4Path_;
  QJsonObject metrics_;
  QJsonObject px4State_;
  rclcpp::Subscription<nav_msgs::msg::Odometry>::SharedPtr odometry_;
  rclcpp::Subscription<geometry_msgs::msg::PoseStamped>::SharedPtr truthSubscription_;
  rclcpp::Subscription<sensor_msgs::msg::PointCloud2>::SharedPtr cloudSubscription_;
  rclcpp::Subscription<nav_msgs::msg::Odometry>::SharedPtr px4Odometry_;
  rclcpp::Subscription<std_msgs::msg::Float64>::SharedPtr cpu_;
  rclcpp::Subscription<std_msgs::msg::Float64>::SharedPtr cpuTotal_;
  rclcpp::Subscription<std_msgs::msg::Float64>::SharedPtr memory_;
  rclcpp::Subscription<std_msgs::msg::Float64>::SharedPtr expectedDuration_;
  std::vector<rclcpp::Subscription<std_msgs::msg::String>::SharedPtr> counterSubscriptions_;
  rclcpp::Subscription<std_msgs::msg::String>::SharedPtr px4StateSubscription_;

  static void appendTimed(std::vector<TimedPosition>& values, const double time, const double x, const double y,
                          const double z) {
    values.push_back({time, QVector3D(static_cast<float>(x), static_cast<float>(y), static_cast<float>(z))});
    if (values.size() > 20000) {
      values.erase(values.begin(), values.begin() + 3000);
    }
  }

  void receiveCloud(const sensor_msgs::msg::PointCloud2& message) {
    std::size_t xOffset = message.point_step;
    std::size_t yOffset = message.point_step;
    std::size_t zOffset = message.point_step;
    for (const auto& field : message.fields) {
      if (field.datatype != sensor_msgs::msg::PointField::FLOAT32) {
        continue;
      }
      if (field.name == "x") {
        xOffset = field.offset;
      } else if (field.name == "y") {
        yOffset = field.offset;
      } else if (field.name == "z") {
        zOffset = field.offset;
      }
    }
    const auto count = static_cast<std::size_t>(message.width) * message.height;
    if (count == 0 || message.point_step == 0 || xOffset + 4 > message.point_step || yOffset + 4 > message.point_step ||
        zOffset + 4 > message.point_step || message.data.size() < count * message.point_step) {
      return;
    }
    const auto step = std::max<std::size_t>(1, (count + 11999) / 12000);
    std::vector<QVector3D> points;
    points.reserve((count + step - 1) / step);
    for (std::size_t index = 0; index < count; index += step) {
      const auto base = index * message.point_step;
      const auto x = cloudCoordinate(message, base + xOffset);
      const auto y = cloudCoordinate(message, base + yOffset);
      const auto z = cloudCoordinate(message, base + zOffset);
      if (std::isfinite(x) && std::isfinite(y) && std::isfinite(z)) {
        points.emplace_back(x, y, z);
      }
    }
    std::scoped_lock lock(mutex_);
    ++cloudFrameCount_;
    cloudMap_.insert(points);
  }

  void receiveJson(const std::string& text, const bool px4) {
    QJsonParseError error;
    const auto document = QJsonDocument::fromJson(QByteArray::fromStdString(text), &error);
    if (error.error != QJsonParseError::NoError || !document.isObject()) {
      return;
    }
    std::scoped_lock lock(mutex_);
    if (px4) {
      px4State_ = document.object();
    } else {
      const auto counters = document.object();
      for (auto iterator = counters.begin(); iterator != counters.end(); ++iterator) {
        if (iterator.value().isDouble()) {
          metrics_.insert(QStringLiteral("pipeline_%1").arg(iterator.key()), iterator.value());
        }
      }
    }
  }
};

LiveTelemetry::LiveTelemetry() : impl_(std::make_unique<Impl>()) {}
LiveTelemetry::~LiveTelemetry() = default;
void LiveTelemetry::reset() { impl_->reset(); }
LiveTelemetrySnapshot LiveTelemetry::snapshot() const { return impl_->snapshot(); }

}  // namespace drone_agricole::core
