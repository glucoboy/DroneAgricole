#pragma once

#include <QByteArray>
#include <QJsonObject>
#include <QString>

#include <vector>

namespace drone_agricole::core {

struct Ros1MessageHeader {
  quint32 sequence{0};
  quint32 seconds{0};
  quint32 nanoseconds{0};
  QString frameId;
};

struct Ros1PointFieldData {
  QString name;
  quint32 offset{0};
  quint8 datatype{0};
  quint32 count{0};
};

struct Ros1PointCloud2Data {
  Ros1MessageHeader header;
  quint32 height{0};
  quint32 width{0};
  std::vector<Ros1PointFieldData> fields;
  bool bigEndian{false};
  quint32 pointStep{0};
  quint32 rowStep{0};
  QByteArray data;
  bool dense{false};
};

struct Ros1NavSatFixData {
  Ros1MessageHeader header;
  qint8 status{-1};
  quint16 service{0};
  double latitude{0.0};
  double longitude{0.0};
  double altitude{0.0};
  double covariance[9]{};
  quint8 covarianceType{0};
};

[[nodiscard]] Ros1PointCloud2Data deserializeRos1PointCloud2(const QByteArray& bytes);
[[nodiscard]] Ros1NavSatFixData deserializeRos1NavSatFix(const QByteArray& bytes);
[[nodiscard]] QJsonObject describeRos1PointCloud2(const Ros1PointCloud2Data& cloud);
[[nodiscard]] double ros1PointFieldAsDouble(const Ros1PointCloud2Data& cloud,
                                            qsizetype pointIndex,
                                            const QString& fieldName);

}  // namespace drone_agricole::core
