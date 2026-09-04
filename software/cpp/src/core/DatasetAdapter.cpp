#include "drone_agricole/core/DatasetAdapter.hpp"

#include "drone_agricole/core/JsonUtils.hpp"
#include "drone_agricole/core/Ros1Bag.hpp"

#include <geometry_msgs/msg/pose_stamped.hpp>
#include <rclcpp/time.hpp>
#include <rosbag2_cpp/writer.hpp>
#include <rosbag2_storage/storage_options.hpp>
#include <sensor_msgs/msg/imu.hpp>
#include <sensor_msgs/msg/point_cloud2.hpp>
#include <sensor_msgs/msg/point_field.hpp>
#include <std_msgs/msg/header.hpp>
#include <yaml-cpp/yaml.h>

#ifdef DRONE_AGRICOLE_WITH_LIVOX_MESSAGES
#include <livox_ros_driver2/msg/custom_msg.hpp>
#include <livox_ros_driver2/msg/custom_point.hpp>
#endif

#include <QDateTime>
#include <QDir>
#include <QFileInfo>
#include <QHash>
#include <QJsonArray>
#include <QJsonObject>

#include <algorithm>
#include <array>
#include <cmath>
#include <cstring>
#include <limits>
#include <utility>
#include <vector>

namespace drone_agricole::core {
namespace {

class MessageReader final {
 public:
  explicit MessageReader(const QByteArray& data) : data_(data) {}

  quint8 u8() { return static_cast<quint8>(take(1).front()); }
  quint32 u32() {
    const auto bytes = take(4);
    return static_cast<quint32>(static_cast<uchar>(bytes[0])) |
           (static_cast<quint32>(static_cast<uchar>(bytes[1])) << 8U) |
           (static_cast<quint32>(static_cast<uchar>(bytes[2])) << 16U) |
           (static_cast<quint32>(static_cast<uchar>(bytes[3])) << 24U);
  }
  quint64 u64() {
    const auto bytes = take(8);
    quint64 value = 0;
    for (int index = 0; index < 8; ++index) {
      value |= static_cast<quint64>(static_cast<uchar>(bytes[index])) << (8U * index);
    }
    return value;
  }
  float f32() {
    const auto bits = u32();
    float value = 0.0F;
    std::memcpy(&value, &bits, sizeof(value));
    return value;
  }
  double f64() {
    const auto bits = u64();
    double value = 0.0;
    std::memcpy(&value, &bits, sizeof(value));
    return value;
  }
  QString string() { return QString::fromUtf8(take(u32())); }
  QByteArray bytes() { return take(u32()); }

 private:
  QByteArray take(const qsizetype count) {
    if (count < 0 || offset_ + count > data_.size()) {
      throw ContractError(QStringLiteral("Message ROS 1 tronqué"));
    }
    const auto value = data_.mid(offset_, count);
    offset_ += count;
    return value;
  }

  const QByteArray& data_;
  qsizetype offset_{0};
};

std_msgs::msg::Header readHeader(MessageReader& reader) {
  static_cast<void>(reader.u32());  // seq n'existe plus dans std_msgs/Header ROS 2.
  std_msgs::msg::Header header;
  header.stamp.sec = static_cast<std::int32_t>(reader.u32());
  header.stamp.nanosec = reader.u32();
  header.frame_id = reader.string().toStdString();
  return header;
}

geometry_msgs::msg::PoseStamped readPoseStamped(const QByteArray& bytes) {
  MessageReader reader(bytes);
  geometry_msgs::msg::PoseStamped message;
  message.header = readHeader(reader);
  message.pose.position.x = reader.f64();
  message.pose.position.y = reader.f64();
  message.pose.position.z = reader.f64();
  message.pose.orientation.x = reader.f64();
  message.pose.orientation.y = reader.f64();
  message.pose.orientation.z = reader.f64();
  message.pose.orientation.w = reader.f64();
  return message;
}

sensor_msgs::msg::Imu readImu(const QByteArray& bytes) {
  MessageReader reader(bytes);
  sensor_msgs::msg::Imu message;
  message.header = readHeader(reader);
  message.orientation.x = reader.f64();
  message.orientation.y = reader.f64();
  message.orientation.z = reader.f64();
  message.orientation.w = reader.f64();
  for (auto& value : message.orientation_covariance) {
    value = reader.f64();
  }
  message.angular_velocity.x = reader.f64();
  message.angular_velocity.y = reader.f64();
  message.angular_velocity.z = reader.f64();
  for (auto& value : message.angular_velocity_covariance) {
    value = reader.f64();
  }
  message.linear_acceleration.x = reader.f64();
  message.linear_acceleration.y = reader.f64();
  message.linear_acceleration.z = reader.f64();
  for (auto& value : message.linear_acceleration_covariance) {
    value = reader.f64();
  }
  return message;
}

sensor_msgs::msg::PointCloud2 readPointCloud2(const QByteArray& bytes) {
  MessageReader reader(bytes);
  sensor_msgs::msg::PointCloud2 message;
  message.header = readHeader(reader);
  message.height = reader.u32();
  message.width = reader.u32();
  const auto fieldCount = reader.u32();
  message.fields.reserve(fieldCount);
  for (quint32 index = 0; index < fieldCount; ++index) {
    sensor_msgs::msg::PointField field;
    field.name = reader.string().toStdString();
    field.offset = reader.u32();
    field.datatype = reader.u8();
    field.count = reader.u32();
    message.fields.push_back(field);
  }
  message.is_bigendian = reader.u8() != 0;
  message.point_step = reader.u32();
  message.row_step = reader.u32();
  const auto data = reader.bytes();
  message.data.assign(reinterpret_cast<const std::uint8_t*>(data.constData()),
                      reinterpret_cast<const std::uint8_t*>(data.constData() + data.size()));
  message.is_dense = reader.u8() != 0;
  return message;
}

quint32 readPointBits(const std::vector<std::uint8_t>& data, const qsizetype offset, const bool bigEndian) {
  if (offset < 0 || offset + 4 > static_cast<qsizetype>(data.size())) {
    throw ContractError(QStringLiteral("Champ time PointCloud2 hors limites"));
  }
  if (bigEndian) {
    return (static_cast<quint32>(data[offset]) << 24U) | (static_cast<quint32>(data[offset + 1]) << 16U) |
           (static_cast<quint32>(data[offset + 2]) << 8U) | static_cast<quint32>(data[offset + 3]);
  }
  return static_cast<quint32>(data[offset]) | (static_cast<quint32>(data[offset + 1]) << 8U) |
         (static_cast<quint32>(data[offset + 2]) << 16U) | (static_cast<quint32>(data[offset + 3]) << 24U);
}

void writePointBits(std::vector<std::uint8_t>& data, const qsizetype offset, const bool bigEndian, const quint32 bits) {
  for (int index = 0; index < 4; ++index) {
    const auto shift = bigEndian ? 8U * (3 - index) : 8U * index;
    data[offset + index] = static_cast<std::uint8_t>((bits >> shift) & 0xffU);
  }
}

QJsonObject normalizePointTimes(sensor_msgs::msg::PointCloud2& message) {
  const auto iterator = std::find_if(message.fields.cbegin(), message.fields.cend(), [](const auto& field) {
    return field.name == "time";
  });
  if (iterator == message.fields.cend() || iterator->datatype != sensor_msgs::msg::PointField::FLOAT32 ||
      iterator->count != 1 || message.point_step < iterator->offset + 4 || message.width == 0 || message.height == 0) {
    throw ContractError(QStringLiteral("Champ time FLOAT32 PointCloud2 absent ou invalide"));
  }
  float minimum = std::numeric_limits<float>::infinity();
  float maximum = -std::numeric_limits<float>::infinity();
  for (quint32 row = 0; row < message.height; ++row) {
    for (quint32 point = 0; point < message.width; ++point) {
      const auto offset = static_cast<qsizetype>(row) * message.row_step +
                          static_cast<qsizetype>(point) * message.point_step + iterator->offset;
      const auto bits = readPointBits(message.data, offset, message.is_bigendian);
      float value = 0.0F;
      std::memcpy(&value, &bits, sizeof(value));
      if (!std::isfinite(value)) {
        throw ContractError(QStringLiteral("Champ time PointCloud2 non fini"));
      }
      minimum = std::min(minimum, value);
      maximum = std::max(maximum, value);
    }
  }
  for (quint32 row = 0; row < message.height; ++row) {
    for (quint32 point = 0; point < message.width; ++point) {
      const auto offset = static_cast<qsizetype>(row) * message.row_step +
                          static_cast<qsizetype>(point) * message.point_step + iterator->offset;
      auto bits = readPointBits(message.data, offset, message.is_bigendian);
      float value = 0.0F;
      std::memcpy(&value, &bits, sizeof(value));
      value -= minimum;
      std::memcpy(&bits, &value, sizeof(bits));
      writePointBits(message.data, offset, message.is_bigendian, bits);
    }
  }
  auto stampNanoseconds = static_cast<qint64>(message.header.stamp.sec) * 1000000000LL + message.header.stamp.nanosec;
  stampNanoseconds += static_cast<qint64>(std::llround(static_cast<double>(minimum) * 1.0e9));
  message.header.stamp.sec = static_cast<std::int32_t>(stampNanoseconds / 1000000000LL);
  message.header.stamp.nanosec = static_cast<std::uint32_t>(stampNanoseconds % 1000000000LL);
  return {{QStringLiteral("points"), static_cast<double>(message.width) * message.height},
          {QStringLiteral("original_min_s"), minimum},
          {QStringLiteral("original_max_s"), maximum},
          {QStringLiteral("normalized_span_s"), maximum - minimum},
          {QStringLiteral("header_shift_s"), minimum}};
}

#ifdef DRONE_AGRICOLE_WITH_LIVOX_MESSAGES
livox_ros_driver2::msg::CustomMsg readLivox(const QByteArray& bytes) {
  MessageReader reader(bytes);
  livox_ros_driver2::msg::CustomMsg message;
  message.header = readHeader(reader);
  message.timebase = reader.u64();
  message.point_num = reader.u32();
  message.lidar_id = reader.u8();
  for (auto& value : message.rsvd) {
    value = reader.u8();
  }
  const auto pointCount = reader.u32();
  message.points.reserve(pointCount);
  for (quint32 index = 0; index < pointCount; ++index) {
    livox_ros_driver2::msg::CustomPoint point;
    point.offset_time = reader.u32();
    point.x = reader.f32();
    point.y = reader.f32();
    point.z = reader.f32();
    point.reflectivity = reader.u8();
    point.tag = reader.u8();
    point.line = reader.u8();
    message.points.push_back(point);
  }
  return message;
}
#endif

struct TopicStatistics {
  quint64 messages{0};
  qint64 first{0};
  qint64 last{0};
};

struct BufferedMessage {
  qint64 timestamp{0};
  QByteArray data;
};

QString requiredString(const QJsonObject& options, const QString& key) {
  const auto value = options.value(key).toString();
  if (value.isEmpty()) {
    throw ContractError(QStringLiteral("Option --%1 requise").arg(key));
  }
  return value;
}

void ensureTopics(const Ros1Bag& bag, const QSet<QString>& expected) {
  QSet<QString> found;
  for (const auto& connection : bag.connections()) {
    found.insert(connection.topic);
  }
  const auto missing = expected - found;
  if (!missing.isEmpty()) {
    throw ContractError(QStringLiteral("Topics ROS 1 absents : %1").arg(QStringList(missing.values()).join(QStringLiteral(", "))));
  }
}

}  // namespace

QJsonObject prepareBotanicGarden(const QJsonObject& options) {
  const auto lioPath = requiredString(options, QStringLiteral("lio-bag"));
  const auto groundTruthPath = requiredString(options, QStringLiteral("ground-truth-bag"));
  const auto outputPath = requiredString(options, QStringLiteral("output"));
  const auto pipeline = requiredString(options, QStringLiteral("pipeline"));
  const auto configPath = options.value(QStringLiteral("config")).toString(
      QStringLiteral("/workspace/configs/datasets/botanicgarden/1006-03.yaml"));
  const auto startOffsetSeconds = options.value(QStringLiteral("start-offset-s")).toDouble(20.0);
  const auto durationSeconds = options.value(QStringLiteral("duration-s")).toDouble(10.0);
  const auto livoxAccelerationMode = options.value(QStringLiteral("livox-accel-mode")).toString(QStringLiteral("raw"));
  const auto velodyneTimeMode = options.value(QStringLiteral("velodyne-time-mode")).toString(QStringLiteral("preserve"));
  if (pipeline != QStringLiteral("velodyne_xsens") && pipeline != QStringLiteral("livox_bmi088")) {
    throw ContractError(QStringLiteral("Pipeline inconnu : %1").arg(pipeline));
  }
  if (startOffsetSeconds < 0.0 || durationSeconds <= 0.0) {
    throw ContractError(QStringLiteral("La fenêtre temporelle est invalide"));
  }
  if (QFileInfo::exists(outputPath)) {
    throw ContractError(QStringLiteral("La sortie existe déjà : %1").arg(outputPath));
  }

  const auto config = YAML::LoadFile(configPath.toStdString());
  if (!config["dataset"] || config["dataset"].as<std::string>() != "botanicgarden") {
    throw ContractError(QStringLiteral("Configuration BotanicGarden attendue"));
  }
  const auto sequence = QString::fromStdString(config["sequence"].as<std::string>());
  double accelerationScale = 1.0;
  if (pipeline == QStringLiteral("livox_bmi088") && livoxAccelerationMode == QStringLiteral("si")) {
    accelerationScale = config["pipelines"]["livox_bmi088"]["acceleration"]["raw_to_m_s2_factor"].as<double>();
  }

  const auto lidarTopic = pipeline == QStringLiteral("velodyne_xsens") ? QStringLiteral("/velodyne_points")
                                                                       : QStringLiteral("/livox/lidar");
  const auto imuTopic = pipeline == QStringLiteral("velodyne_xsens") ? QStringLiteral("/imu/data")
                                                                     : QStringLiteral("/livox/imu");
  const auto groundTruthTopic = QStringLiteral("/gt_poses");
  Ros1Bag lioBag(lioPath);
  Ros1Bag groundTruthBag(groundTruthPath);
  lioBag.open();
  groundTruthBag.open();
  ensureTopics(lioBag, {lidarTopic, imuTopic});
  ensureTopics(groundTruthBag, {groundTruthTopic});
  const auto startNanoseconds = lioBag.startNanoseconds() + static_cast<qint64>(std::llround(startOffsetSeconds * 1.0e9));
  const auto stopNanoseconds = startNanoseconds + static_cast<qint64>(std::llround(durationSeconds * 1.0e9));

  std::vector<BufferedMessage> groundTruthMessages;
  groundTruthBag.forEachMessage({groundTruthTopic}, startNanoseconds, stopNanoseconds,
                                [&](const Ros1Connection&, const Ros1Message& message) {
                                  groundTruthMessages.push_back({message.timestampNanoseconds, message.data});
                                });
  std::sort(groundTruthMessages.begin(), groundTruthMessages.end(), [](const auto& left, const auto& right) {
    return left.timestamp < right.timestamp;
  });

  QDir().mkpath(QFileInfo(outputPath).absolutePath());
  rosbag2_storage::StorageOptions storageOptions;
  storageOptions.uri = QFileInfo(outputPath).absoluteFilePath().toStdString();
  storageOptions.storage_id = "mcap";
  storageOptions.storage_preset_profile = "zstd_fast";
  rosbag2_cpp::ConverterOptions converterOptions{"cdr", "cdr"};
  rosbag2_cpp::Writer writer;
  QHash<QString, TopicStatistics> topicStatistics;
  QJsonArray pointTimeStatistics;
  auto note = [&](const QString& topic, const qint64 timestamp) {
    auto& statistics = topicStatistics[topic];
    if (statistics.messages == 0) {
      statistics.first = timestamp;
    }
    statistics.last = timestamp;
    ++statistics.messages;
  };
  auto writeGroundTruth = [&](const BufferedMessage& source) {
    writer.write(readPoseStamped(source.data), groundTruthTopic.toStdString(), rclcpp::Time(source.timestamp));
    note(groundTruthTopic, source.timestamp);
  };

  try {
    writer.open(storageOptions, converterOptions);
    std::size_t groundTruthIndex = 0;
    lioBag.forEachMessage({lidarTopic, imuTopic}, startNanoseconds, stopNanoseconds,
                          [&](const Ros1Connection& connection, const Ros1Message& source) {
                            while (groundTruthIndex < groundTruthMessages.size() &&
                                   groundTruthMessages[groundTruthIndex].timestamp <= source.timestampNanoseconds) {
                              writeGroundTruth(groundTruthMessages[groundTruthIndex++]);
                            }
                            if (connection.topic == imuTopic) {
                              auto message = readImu(source.data);
                              if (accelerationScale != 1.0) {
                                message.linear_acceleration.x *= accelerationScale;
                                message.linear_acceleration.y *= accelerationScale;
                                message.linear_acceleration.z *= accelerationScale;
                              }
                              writer.write(message, connection.topic.toStdString(), rclcpp::Time(source.timestampNanoseconds));
                            } else if (pipeline == QStringLiteral("velodyne_xsens")) {
                              auto message = readPointCloud2(source.data);
                              if (velodyneTimeMode == QStringLiteral("start-relative")) {
                                pointTimeStatistics.append(normalizePointTimes(message));
                              }
                              writer.write(message, connection.topic.toStdString(), rclcpp::Time(source.timestampNanoseconds));
                            } else {
#ifdef DRONE_AGRICOLE_WITH_LIVOX_MESSAGES
                              writer.write(readLivox(source.data), connection.topic.toStdString(),
                                           rclcpp::Time(source.timestampNanoseconds));
#else
                              throw ContractError(QStringLiteral("Interfaces C++ livox_ros_driver2 indisponibles"));
#endif
                            }
                            note(connection.topic, source.timestampNanoseconds);
                          });
    while (groundTruthIndex < groundTruthMessages.size()) {
      writeGroundTruth(groundTruthMessages[groundTruthIndex++]);
    }
    writer.close();
  } catch (...) {
    writer.close();
    QDir output(outputPath);
    if (output.exists()) {
      output.removeRecursively();
    }
    throw;
  }

  QJsonObject topicManifest;
  for (const auto& topic : {lidarTopic, imuTopic, groundTruthTopic}) {
    const auto statistics = topicStatistics.value(topic);
    topicManifest.insert(topic, QJsonObject{{QStringLiteral("messages"), static_cast<double>(statistics.messages)},
                                            {QStringLiteral("first_timestamp_ns"), static_cast<double>(statistics.first)},
                                            {QStringLiteral("last_timestamp_ns"), static_cast<double>(statistics.last)}});
  }
  double minimumOriginalOffset = std::numeric_limits<double>::infinity();
  double maximumOriginalOffset = -std::numeric_limits<double>::infinity();
  double maximumNormalizedSpan = 0.0;
  for (const auto& value : pointTimeStatistics) {
    const auto item = value.toObject();
    minimumOriginalOffset = std::min(minimumOriginalOffset, item.value(QStringLiteral("original_min_s")).toDouble());
    maximumOriginalOffset = std::max(maximumOriginalOffset, item.value(QStringLiteral("original_max_s")).toDouble());
    maximumNormalizedSpan = std::max(maximumNormalizedSpan, item.value(QStringLiteral("normalized_span_s")).toDouble());
  }
  const auto noPointStatistics = pointTimeStatistics.isEmpty();
  QJsonObject manifest{
      {QStringLiteral("schema_version"), 1},
      {QStringLiteral("generated_at_utc"), QDateTime::currentDateTimeUtc().toString(Qt::ISODateWithMs)},
      {QStringLiteral("dataset"), QStringLiteral("botanicgarden")},
      {QStringLiteral("sequence"), sequence},
      {QStringLiteral("pipeline"), pipeline},
      {QStringLiteral("source_lio_bag"), QFileInfo(lioPath).absoluteFilePath()},
      {QStringLiteral("source_ground_truth_bag"), QFileInfo(groundTruthPath).absoluteFilePath()},
      {QStringLiteral("output"), QFileInfo(outputPath).absoluteFilePath()},
      {QStringLiteral("format"), QStringLiteral("rosbag2_mcap_zstd")},
      {QStringLiteral("target_ros_distro"), QStringLiteral("humble")},
      {QStringLiteral("requested_start_offset_s"), startOffsetSeconds},
      {QStringLiteral("requested_duration_s"), durationSeconds},
      {QStringLiteral("start_timestamp_ns"), static_cast<double>(startNanoseconds)},
      {QStringLiteral("stop_timestamp_ns"), static_cast<double>(stopNanoseconds)},
      {QStringLiteral("livox_accel_mode"), livoxAccelerationMode},
      {QStringLiteral("livox_accel_scale_factor"), accelerationScale},
      {QStringLiteral("velodyne_time_mode"), velodyneTimeMode},
      {QStringLiteral("velodyne_time_normalization"),
       QJsonObject{{QStringLiteral("scans"), pointTimeStatistics.size()},
                   {QStringLiteral("minimum_original_offset_s"), noPointStatistics ? QJsonValue() : QJsonValue(minimumOriginalOffset)},
                   {QStringLiteral("maximum_original_offset_s"), noPointStatistics ? QJsonValue() : QJsonValue(maximumOriginalOffset)},
                   {QStringLiteral("maximum_normalized_span_s"), noPointStatistics ? QJsonValue() : QJsonValue(maximumNormalizedSpan)}}},
      {QStringLiteral("topics"), topicManifest},
  };
  writeJsonObjectAtomically(QDir(outputPath).filePath(QStringLiteral("adapter_manifest.json")), manifest);
  return manifest;
}

}  // namespace drone_agricole::core
