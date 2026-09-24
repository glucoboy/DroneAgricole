#include "drone_agricole/core/Ros1Messages.hpp"

#include "drone_agricole/core/JsonUtils.hpp"

#include <QJsonArray>

#include <algorithm>
#include <cmath>
#include <cstring>
#include <limits>

namespace drone_agricole::core {
namespace {

class Reader final {
 public:
  explicit Reader(const QByteArray& data) : data_(data) {}

  quint8 u8() { return static_cast<quint8>(take(1).front()); }
  qint8 i8() { return static_cast<qint8>(u8()); }
  quint16 u16() {
    const auto bytes = take(2);
    return static_cast<quint16>(static_cast<uchar>(bytes[0])) |
           static_cast<quint16>(static_cast<uchar>(bytes[1]) << 8U);
  }
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

Ros1MessageHeader readHeader(Reader& reader) {
  return {reader.u32(), reader.u32(), reader.u32(), reader.string()};
}

quint64 unsignedValue(const char* data, const quint8 datatype, const bool bigEndian) {
  const auto bytes = datatype == 1 || datatype == 2 ? 1
                     : datatype == 3 || datatype == 4 ? 2
                     : datatype == 5 || datatype == 6 || datatype == 7 ? 4
                     : 8;
  quint64 value = 0;
  for (int index = 0; index < bytes; ++index) {
    const auto source = bigEndian ? index : bytes - 1 - index;
    value = (value << 8U) | static_cast<uchar>(data[source]);
  }
  return value;
}

}  // namespace

Ros1PointCloud2Data deserializeRos1PointCloud2(const QByteArray& bytes) {
  Reader reader(bytes);
  Ros1PointCloud2Data cloud;
  cloud.header = readHeader(reader);
  cloud.height = reader.u32();
  cloud.width = reader.u32();
  const auto fieldCount = reader.u32();
  if (fieldCount > 128) {
    throw ContractError(QStringLiteral("Nombre de champs PointCloud2 invalide"));
  }
  cloud.fields.reserve(fieldCount);
  for (quint32 index = 0; index < fieldCount; ++index) {
    cloud.fields.push_back({reader.string(), reader.u32(), reader.u8(), reader.u32()});
  }
  cloud.bigEndian = reader.u8() != 0;
  cloud.pointStep = reader.u32();
  cloud.rowStep = reader.u32();
  cloud.data = reader.bytes();
  cloud.dense = reader.u8() != 0;
  const auto expectedMinimum = static_cast<quint64>(cloud.height) * cloud.rowStep;
  if (cloud.pointStep == 0 || cloud.width == 0 || cloud.height == 0 ||
      expectedMinimum > static_cast<quint64>(cloud.data.size())) {
    throw ContractError(QStringLiteral("Disposition PointCloud2 invalide"));
  }
  return cloud;
}

Ros1NavSatFixData deserializeRos1NavSatFix(const QByteArray& bytes) {
  Reader reader(bytes);
  Ros1NavSatFixData fix;
  fix.header = readHeader(reader);
  fix.status = reader.i8();
  fix.service = reader.u16();
  fix.latitude = reader.f64();
  fix.longitude = reader.f64();
  fix.altitude = reader.f64();
  for (auto& value : fix.covariance) {
    value = reader.f64();
  }
  fix.covarianceType = reader.u8();
  return fix;
}

QJsonObject describeRos1PointCloud2(const Ros1PointCloud2Data& cloud) {
  QJsonArray fields;
  for (const auto& field : cloud.fields) {
    fields.append(QJsonObject{{QStringLiteral("name"), field.name},
                              {QStringLiteral("offset"), static_cast<double>(field.offset)},
                              {QStringLiteral("datatype"), static_cast<int>(field.datatype)},
                              {QStringLiteral("count"), static_cast<double>(field.count)}});
  }
  return {{QStringLiteral("frame_id"), cloud.header.frameId},
          {QStringLiteral("height"), static_cast<double>(cloud.height)},
          {QStringLiteral("width"), static_cast<double>(cloud.width)},
          {QStringLiteral("points"), static_cast<double>(cloud.height) * cloud.width},
          {QStringLiteral("point_step"), static_cast<double>(cloud.pointStep)},
          {QStringLiteral("row_step"), static_cast<double>(cloud.rowStep)},
          {QStringLiteral("big_endian"), cloud.bigEndian},
          {QStringLiteral("dense"), cloud.dense},
          {QStringLiteral("fields"), fields}};
}

double ros1PointFieldAsDouble(const Ros1PointCloud2Data& cloud,
                              const qsizetype pointIndex,
                              const QString& fieldName) {
  const auto iterator = std::find_if(cloud.fields.cbegin(), cloud.fields.cend(), [&](const auto& field) {
    return field.name == fieldName && field.count == 1;
  });
  if (iterator == cloud.fields.cend()) {
    return std::numeric_limits<double>::quiet_NaN();
  }
  const auto row = pointIndex / cloud.width;
  const auto column = pointIndex % cloud.width;
  const auto offset = static_cast<quint64>(row) * cloud.rowStep + static_cast<quint64>(column) * cloud.pointStep + iterator->offset;
  const auto byteCount = iterator->datatype == 1 || iterator->datatype == 2 ? 1
                         : iterator->datatype == 3 || iterator->datatype == 4 ? 2
                         : iterator->datatype == 5 || iterator->datatype == 6 || iterator->datatype == 7 ? 4
                         : iterator->datatype == 8 ? 8 : 0;
  if (byteCount == 0 || offset + byteCount > static_cast<quint64>(cloud.data.size())) {
    throw ContractError(QStringLiteral("Champ PointCloud2 hors limites : %1").arg(fieldName));
  }
  const auto* data = cloud.data.constData() + static_cast<qsizetype>(offset);
  const auto bits = unsignedValue(data, iterator->datatype, cloud.bigEndian);
  if (iterator->datatype == 7) {
    const auto valueBits = static_cast<quint32>(bits);
    float value = 0.0F;
    std::memcpy(&value, &valueBits, sizeof(value));
    return value;
  }
  if (iterator->datatype == 8) {
    double value = 0.0;
    std::memcpy(&value, &bits, sizeof(value));
    return value;
  }
  if (iterator->datatype == 1) {
    return static_cast<qint8>(bits);
  }
  if (iterator->datatype == 3) {
    return static_cast<qint16>(bits);
  }
  if (iterator->datatype == 5) {
    return static_cast<qint32>(bits);
  }
  return static_cast<double>(bits);
}

}  // namespace drone_agricole::core
