#include "drone_agricole/core/RosbagTrajectoryReader.hpp"

#include "drone_agricole/core/JsonUtils.hpp"

#include <Eigen/Dense>
#include <geometry_msgs/msg/pose_stamped.hpp>
#include <nav_msgs/msg/odometry.hpp>
#include <rclcpp/serialization.hpp>
#include <rclcpp/serialized_message.hpp>
#include <rosbag2_cpp/reader.hpp>
#include <rosbag2_storage/storage_options.hpp>

#include <algorithm>
#include <cmath>
#include <limits>
#include <vector>

namespace drone_agricole::core {
namespace {

struct TimedPoint {
  double time{0.0};
  Eigen::Vector3d position{Eigen::Vector3d::Zero()};
};

template <typename Message>
Message deserialize(const std::shared_ptr<rosbag2_storage::SerializedBagMessage>& bagMessage) {
  rclcpp::SerializedMessage serialized(*bagMessage->serialized_data);
  rclcpp::Serialization<Message> serialization;
  Message message;
  serialization.deserialize_message(&serialized, &message);
  return message;
}

double timestamp(double seconds, std::uint32_t nanoseconds, const std::int64_t bagNanoseconds) {
  const auto header = seconds + static_cast<double>(nanoseconds) * 1e-9;
  return header > 0.0 ? header : static_cast<double>(bagNanoseconds) * 1e-9;
}

QList<QVector3D> downsample(const std::vector<Eigen::Vector3d>& values, const qsizetype maximum) {
  QList<QVector3D> result;
  if (values.empty()) {
    return result;
  }
  const auto step = std::max<std::size_t>(1, static_cast<std::size_t>(std::ceil(
                                                  static_cast<double>(values.size()) / static_cast<double>(maximum))));
  result.reserve(static_cast<qsizetype>((values.size() + step - 1) / step));
  for (std::size_t index = 0; index < values.size(); index += step) {
    const auto& point = values[index];
    result.append(QVector3D(static_cast<float>(point.x()), static_cast<float>(point.y()), static_cast<float>(point.z())));
  }
  return result;
}

QList<QPointF> downsampleCurve(const std::vector<QPointF>& values, const qsizetype maximum) {
  QList<QPointF> result;
  if (values.empty()) {
    return result;
  }
  const auto step = std::max<std::size_t>(1, static_cast<std::size_t>(std::ceil(
                                                  static_cast<double>(values.size()) / static_cast<double>(maximum))));
  result.reserve(static_cast<qsizetype>((values.size() + step - 1) / step));
  for (std::size_t index = 0; index < values.size(); index += step) {
    result.append(values[index]);
  }
  return result;
}

}  // namespace

ReplayData readLioTrajectory(const QString& bagDirectory, const QString& resultId) {
  std::vector<TimedPoint> estimate;
  std::vector<TimedPoint> truth;
  try {
    rosbag2_storage::StorageOptions storageOptions;
    storageOptions.uri = bagDirectory.toStdString();
    rosbag2_cpp::ConverterOptions converterOptions;
    converterOptions.input_serialization_format = "cdr";
    converterOptions.output_serialization_format = "cdr";
    rosbag2_cpp::Reader reader;
    reader.open(storageOptions, converterOptions);
    while (reader.has_next()) {
      const auto bagMessage = reader.read_next();
      if (bagMessage->topic_name == "/Odometry") {
        const auto message = deserialize<nav_msgs::msg::Odometry>(bagMessage);
        estimate.push_back(TimedPoint{
            timestamp(message.header.stamp.sec, message.header.stamp.nanosec, bagMessage->time_stamp),
            Eigen::Vector3d(message.pose.pose.position.x, message.pose.pose.position.y, message.pose.pose.position.z),
        });
      } else if (bagMessage->topic_name == "/gt_poses") {
        const auto message = deserialize<geometry_msgs::msg::PoseStamped>(bagMessage);
        truth.push_back(TimedPoint{
            timestamp(message.header.stamp.sec, message.header.stamp.nanosec, bagMessage->time_stamp),
            Eigen::Vector3d(message.pose.position.x, message.pose.position.y, message.pose.position.z),
        });
      }
    }
  } catch (const std::exception& error) {
    throw ContractError(QStringLiteral("Trajectoire enregistrée illisible : %1").arg(QString::fromUtf8(error.what())));
  }

  if (estimate.empty() || truth.empty()) {
    throw ContractError(QStringLiteral("Le rosbag ne contient pas /Odometry et /gt_poses"));
  }

  std::vector<Eigen::Vector3d> matchedEstimate;
  std::vector<Eigen::Vector3d> matchedTruth;
  std::vector<double> matchedTimes;
  std::vector<double> truthTimes;
  truthTimes.reserve(truth.size());
  for (const auto& point : truth) {
    truthTimes.push_back(point.time);
  }
  for (const auto& point : estimate) {
    const auto insertion = std::lower_bound(truthTimes.cbegin(), truthTimes.cend(), point.time);
    std::size_t bestIndex = 0;
    double bestDistance = std::numeric_limits<double>::infinity();
    if (insertion != truthTimes.cend()) {
      bestIndex = static_cast<std::size_t>(std::distance(truthTimes.cbegin(), insertion));
      bestDistance = std::abs(*insertion - point.time);
    }
    if (insertion != truthTimes.cbegin()) {
      const auto previous = static_cast<std::size_t>(std::distance(truthTimes.cbegin(), insertion - 1));
      const auto distance = std::abs(truthTimes[previous] - point.time);
      if (distance < bestDistance) {
        bestIndex = previous;
        bestDistance = distance;
      }
    }
    if (bestDistance <= 0.08) {
      matchedEstimate.push_back(point.position);
      matchedTruth.push_back(truth[bestIndex].position);
      matchedTimes.push_back(point.time);
    }
  }

  Eigen::Matrix3d rotation = Eigen::Matrix3d::Identity();
  Eigen::Vector3d translation = truth.front().position - estimate.front().position;
  if (matchedEstimate.size() >= 3) {
    Eigen::Vector3d sourceCenter = Eigen::Vector3d::Zero();
    Eigen::Vector3d targetCenter = Eigen::Vector3d::Zero();
    for (std::size_t index = 0; index < matchedEstimate.size(); ++index) {
      sourceCenter += matchedEstimate[index];
      targetCenter += matchedTruth[index];
    }
    sourceCenter /= static_cast<double>(matchedEstimate.size());
    targetCenter /= static_cast<double>(matchedTruth.size());
    Eigen::Matrix3d covariance = Eigen::Matrix3d::Zero();
    for (std::size_t index = 0; index < matchedEstimate.size(); ++index) {
      covariance += (matchedEstimate[index] - sourceCenter) * (matchedTruth[index] - targetCenter).transpose();
    }
    const Eigen::JacobiSVD<Eigen::Matrix3d> decomposition(covariance, Eigen::ComputeFullU | Eigen::ComputeFullV);
    const auto left = decomposition.matrixU();
    auto right = decomposition.matrixV();
    rotation = right * left.transpose();
    if (rotation.determinant() < 0.0) {
      right.col(2) *= -1.0;
      rotation = right * left.transpose();
    }
    translation = targetCenter - rotation * sourceCenter;
  }

  std::vector<Eigen::Vector3d> alignedEstimate;
  alignedEstimate.reserve(estimate.size());
  for (const auto& point : estimate) {
    alignedEstimate.push_back(rotation * point.position + translation);
  }
  std::vector<Eigen::Vector3d> truthPositions;
  truthPositions.reserve(truth.size());
  for (const auto& point : truth) {
    truthPositions.push_back(point.position);
  }

  std::vector<QPointF> cumulativeCurve;
  if (!matchedEstimate.empty()) {
    cumulativeCurve.reserve(matchedEstimate.size());
    double squaredSum = 0.0;
    for (std::size_t index = 0; index < matchedEstimate.size(); ++index) {
      const auto error = (rotation * matchedEstimate[index] + translation - matchedTruth[index]).norm();
      squaredSum += error * error;
      cumulativeCurve.emplace_back(matchedTimes[index] - matchedTimes.front(),
                                   std::sqrt(squaredSum / static_cast<double>(index + 1)));
    }
  }

  ReplayData replay;
  replay.resultId = resultId;
  replay.domain = QStringLiteral("localization");
  replay.estimate = downsample(alignedEstimate, 1600);
  replay.truth = downsample(truthPositions, 1600);
  replay.curve = downsampleCurve(cumulativeCurve, 500);
  replay.curveId = QStringLiteral("ate_cumulative_rmse_m");
  replay.curveLabel = QStringLiteral("ATE cumulée");
  replay.curveUnit = QStringLiteral("m");
  replay.notes = {
      QStringLiteral("Trajectoires relues depuis le rosbag enregistré, sans relancer l'algorithme."),
      QStringLiteral("Le nuage LiDAR n'est pas archivé dans les résultats LIO historiques."),
  };
  return replay;
}

}  // namespace drone_agricole::core
