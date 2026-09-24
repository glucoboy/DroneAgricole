#include "drone_agricole/core/RosbagAnalysis.hpp"

#include "drone_agricole/core/BenchmarkSupport.hpp"
#include "drone_agricole/core/JsonUtils.hpp"
#include "drone_agricole/core/TrajectoryAnalysis.hpp"

#include <geometry_msgs/msg/pose_stamped.hpp>
#include <nav_msgs/msg/odometry.hpp>
#include <rclcpp/serialization.hpp>
#include <rclcpp/serialized_message.hpp>
#include <rosbag2_cpp/reader.hpp>
#include <rosbag2_storage/storage_options.hpp>
#include <std_msgs/msg/string.hpp>

#include <QFileInfo>
#include <QJsonArray>
#include <QJsonDocument>
#include <QMatrix3x3>

#include <algorithm>
#include <cmath>
#include <limits>

namespace drone_agricole::core {
namespace {

template <typename Message>
Message deserialize(const std::shared_ptr<rosbag2_storage::SerializedBagMessage>& bagMessage) {
  rclcpp::SerializedMessage serialized(*bagMessage->serialized_data);
  rclcpp::Serialization<Message> serialization;
  Message message;
  serialization.deserialize_message(&serialized, &message);
  return message;
}

double messageTime(const builtin_interfaces::msg::Time& stamp, const std::int64_t fallback) {
  const auto header = static_cast<double>(stamp.sec) + static_cast<double>(stamp.nanosec) * 1e-9;
  return header > 0.0 ? header : static_cast<double>(fallback) * 1e-9;
}

QJsonArray vectorJson(const QVector3D& value) {
  return {value.x(), value.y(), value.z()};
}

QJsonArray rotationJson(const QQuaternion& quaternion) {
  const auto matrix = quaternion.toRotationMatrix();
  QJsonArray rows;
  for (int row = 0; row < 3; ++row) {
    rows.append(QJsonArray{matrix(row, 0), matrix(row, 1), matrix(row, 2)});
  }
  return rows;
}

QList<QVector3D> positions(const QList<TimedPose>& poses) {
  QList<QVector3D> result;
  result.reserve(poses.size());
  for (const auto& pose : poses) {
    result.append(pose.position);
  }
  return result;
}

double distance(const QVector3D& left, const QVector3D& right) {
  return static_cast<double>((left - right).length());
}

}  // namespace

QJsonObject analyzeRosbag(const QString& bagDirectory,
                          const double maximumAssociationDeltaSeconds,
                          const double rpeDeltaSeconds,
                          const double rpeToleranceSeconds,
                          const QString& estimateTopic,
                          const QString& groundTruthTopic,
                          const QString& pipelineTopic) {
  QList<TimedPose> estimates;
  QList<TimedPose> truth;
  QJsonObject pipelineCounters;
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
      const auto topic = QString::fromStdString(bagMessage->topic_name);
      if (topic == estimateTopic) {
        const auto message = deserialize<nav_msgs::msg::Odometry>(bagMessage);
        estimates.append(TimedPose{
            messageTime(message.header.stamp, bagMessage->time_stamp),
            QVector3D(message.pose.pose.position.x, message.pose.pose.position.y, message.pose.pose.position.z),
            QQuaternion(message.pose.pose.orientation.w, message.pose.pose.orientation.x,
                        message.pose.pose.orientation.y, message.pose.pose.orientation.z),
        });
      } else if (topic == groundTruthTopic) {
        const auto message = deserialize<geometry_msgs::msg::PoseStamped>(bagMessage);
        truth.append(TimedPose{
            messageTime(message.header.stamp, bagMessage->time_stamp),
            QVector3D(message.pose.position.x, message.pose.position.y, message.pose.position.z),
            QQuaternion(message.pose.orientation.w, message.pose.orientation.x,
                        message.pose.orientation.y, message.pose.orientation.z),
        });
      } else if (topic == pipelineTopic) {
        const auto message = deserialize<std_msgs::msg::String>(bagMessage);
        QJsonParseError error;
        const auto document = QJsonDocument::fromJson(QByteArray::fromStdString(message.data), &error);
        if (error.error == QJsonParseError::NoError && document.isObject() &&
            document.object().value(QStringLiteral("schema_version")).toInt() == 1) {
          pipelineCounters = document.object();
        }
      }
    }
  } catch (const std::exception& error) {
    throw ContractError(QStringLiteral("Rosbag2 illisible : %1").arg(QString::fromUtf8(error.what())));
  }
  if (estimates.size() < 3 || truth.size() < 3) {
    throw ContractError(QStringLiteral("Au moins trois poses estimées et trois poses terrain sont requises"));
  }
  std::sort(estimates.begin(), estimates.end(), [](const auto& left, const auto& right) {
    return left.timeSeconds < right.timeSeconds;
  });
  std::sort(truth.begin(), truth.end(), [](const auto& left, const auto& right) {
    return left.timeSeconds < right.timeSeconds;
  });

  QList<TimedPose> matchedEstimates;
  QList<TimedPose> matchedTruth;
  QList<double> deltas;
  for (const auto& estimate : estimates) {
    const auto insertion = std::lower_bound(truth.cbegin(), truth.cend(), estimate.timeSeconds,
                                            [](const TimedPose& pose, const double time) {
                                              return pose.timeSeconds < time;
                                            });
    qsizetype best = -1;
    auto bestDelta = std::numeric_limits<double>::infinity();
    if (insertion != truth.cend()) {
      best = std::distance(truth.cbegin(), insertion);
      bestDelta = std::abs(insertion->timeSeconds - estimate.timeSeconds);
    }
    if (insertion != truth.cbegin()) {
      const auto previous = static_cast<qsizetype>(std::distance(truth.cbegin(), insertion - 1));
      const auto delta = std::abs(truth[previous].timeSeconds - estimate.timeSeconds);
      if (delta < bestDelta) {
        best = previous;
        bestDelta = delta;
      }
    }
    if (best >= 0 && bestDelta <= maximumAssociationDeltaSeconds) {
      matchedEstimates.append(estimate);
      matchedTruth.append(truth[best]);
      deltas.append(bestDelta);
    }
  }
  if (matchedEstimates.size() < 3) {
    throw ContractError(QStringLiteral("Moins de trois poses ont été appariées par horodatage"));
  }

  const auto estimatePositions = positions(matchedEstimates);
  const auto truthPositions = positions(matchedTruth);
  const auto alignment = alignPositions(estimatePositions, truthPositions);
  QList<double> translationErrors;
  QList<double> orientationErrors;
  for (qsizetype index = 0; index < matchedEstimates.size(); ++index) {
    const auto alignedPosition = alignment.rotation.rotatedVector(matchedEstimates[index].position) + alignment.translation;
    const auto alignedOrientation = alignment.rotation * matchedEstimates[index].orientation;
    translationErrors.append(distance(alignedPosition, matchedTruth[index].position));
    orientationErrors.append(rotationErrorDegrees(matchedTruth[index].orientation, alignedOrientation));
  }
  const auto estimateLength = trajectoryLength(estimatePositions);
  const auto truthLength = trajectoryLength(truthPositions);
  const auto maximumDelta = *std::max_element(deltas.cbegin(), deltas.cend());
  const auto countersValue = pipelineCounters.isEmpty() ? QJsonValue(QJsonValue::Null) : QJsonValue(pipelineCounters);
  const auto accountingValue = pipelineCounters.isEmpty() ? QJsonValue(QJsonValue::Null)
                                                           : QJsonValue(pipelineAccounting(pipelineCounters));
  return {
      {QStringLiteral("schema_version"), 3},
      {QStringLiteral("bag"), QFileInfo(bagDirectory).absoluteFilePath()},
      {QStringLiteral("topics"), QJsonObject{{QStringLiteral("estimate"), estimateTopic},
                                             {QStringLiteral("ground_truth"), groundTruthTopic},
                                             {QStringLiteral("pipeline_counters"), pipelineTopic}}},
      {QStringLiteral("estimate_poses"), estimates.size()},
      {QStringLiteral("ground_truth_poses"), truth.size()},
      {QStringLiteral("matched_poses"), matchedEstimates.size()},
      {QStringLiteral("max_association_delta_s"), maximumAssociationDeltaSeconds},
      {QStringLiteral("observed_max_association_delta_s"), maximumDelta},
      {QStringLiteral("estimate_header_duration_s"), estimates.last().timeSeconds - estimates.first().timeSeconds},
      {QStringLiteral("matched_ground_truth_duration_s"),
       matchedTruth.last().timeSeconds - matchedTruth.first().timeSeconds},
      {QStringLiteral("finite_values"), true},
      {QStringLiteral("pipeline_counters"), countersValue},
      {QStringLiteral("pipeline_accounting"), accountingValue},
      {QStringLiteral("alignment"), QJsonObject{{QStringLiteral("mode"), QStringLiteral("SE3_position_only_no_scale")},
                                                {QStringLiteral("rotation_row_major"), rotationJson(alignment.rotation)},
                                                {QStringLiteral("translation_m"), vectorJson(alignment.translation)}}},
      {QStringLiteral("ate_translation_m"), errorStatistics(translationErrors)},
      {QStringLiteral("ate_orientation_deg"), errorStatistics(orientationErrors)},
      {QStringLiteral("rpe"), computeRpe(matchedEstimates, matchedTruth, rpeDeltaSeconds, rpeToleranceSeconds)},
      {QStringLiteral("matched_path_length_m"),
       QJsonObject{{QStringLiteral("estimate"), estimateLength}, {QStringLiteral("ground_truth"), truthLength},
                   {QStringLiteral("ratio_estimate_over_ground_truth"),
                    truthLength > 0.0 ? QJsonValue(estimateLength / truthLength) : QJsonValue(QJsonValue::Null)}}},
      {QStringLiteral("matched_endpoint_displacement_m"),
       QJsonObject{{QStringLiteral("estimate"), distance(matchedEstimates.last().position, matchedEstimates.first().position)},
                   {QStringLiteral("ground_truth"), distance(matchedTruth.last().position, matchedTruth.first().position)}}},
  };
}

}  // namespace drone_agricole::core
