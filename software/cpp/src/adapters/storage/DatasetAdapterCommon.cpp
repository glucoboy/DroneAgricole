#include "drone_agricole/core/DatasetAdapter.hpp"

#include "drone_agricole/core/JsonUtils.hpp"
#include "drone_agricole/core/Ros1Bag.hpp"

#include <QCryptographicHash>
#include <QDateTime>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QJsonArray>
#include <QSaveFile>
#include <QTextStream>
#include <QTimeZone>

#include <array>
#include <cstring>
#include <limits>

namespace drone_agricole::core {
namespace {

class BufferReader final {
 public:
  explicit BufferReader(const QByteArray& data) : data_(data) {}

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
    quint64 result = 0;
    for (int index = 0; index < 8; ++index) {
      result |= static_cast<quint64>(static_cast<uchar>(bytes[index])) << (8U * index);
    }
    return result;
  }
  float f32() {
    const auto bits = u32();
    float result = 0.0f;
    std::memcpy(&result, &bits, sizeof(result));
    return result;
  }
  double f64() {
    const auto bits = u64();
    double result = 0.0;
    std::memcpy(&result, &bits, sizeof(result));
    return result;
  }
  QString string() { return QString::fromUtf8(take(u32())); }
  QByteArray bytes() { return take(u32()); }

  void skip(const qsizetype size) { static_cast<void>(take(size)); }

 private:
  QByteArray take(const qsizetype size) {
    if (size < 0 || offset_ + size > data_.size()) {
      throw ContractError(QStringLiteral("Message ROS 1 tronqué"));
    }
    const auto result = data_.mid(offset_, size);
    offset_ += size;
    return result;
  }

  const QByteArray& data_;
  qsizetype offset_{0};
};

struct Ros1Header {
  quint32 sequence{0};
  quint32 seconds{0};
  quint32 nanoseconds{0};
  QString frameId;
};

Ros1Header header(BufferReader& reader) {
  return Ros1Header{reader.u32(), reader.u32(), reader.u32(), reader.string()};
}

QString hashFile(const QString& path) {
  QFile file(path);
  if (!file.open(QIODevice::ReadOnly)) {
    throw ContractError(QStringLiteral("Fichier illisible pour SHA-256"));
  }
  QCryptographicHash hash(QCryptographicHash::Sha256);
  while (!file.atEnd()) {
    hash.addData(file.read(8 * 1024 * 1024));
  }
  return QString::fromLatin1(hash.result().toHex());
}

QString utc(const qint64 nanoseconds) {
  return QDateTime::fromMSecsSinceEpoch(nanoseconds / 1000000LL, QTimeZone::utc()).toString(Qt::ISODateWithMs);
}

}  // namespace

QJsonObject inspectRos1Bags(const QStringList& paths, const bool includeHash) {
  QJsonArray bags;
  for (const auto& path : paths) {
    Ros1Bag bag(path);
    bag.open();
    QJsonArray topics;
    auto connections = bag.connections().values();
    std::sort(connections.begin(), connections.end(), [](const auto& left, const auto& right) {
      return left.topic < right.topic;
    });
    for (const auto& connection : connections) {
      topics.append(QJsonObject{
          {QStringLiteral("topic"), connection.topic},
          {QStringLiteral("type"), connection.type},
          {QStringLiteral("messages"), static_cast<double>(connection.messageCount)},
      });
    }
    QJsonObject report{
        {QStringLiteral("path"), QFileInfo(path).absoluteFilePath()},
        {QStringLiteral("format"), QStringLiteral("ROS 1 bag")},
        {QStringLiteral("size_bytes"), static_cast<double>(QFileInfo(path).size())},
        {QStringLiteral("start_timestamp_ns"), static_cast<double>(bag.startNanoseconds())},
        {QStringLiteral("end_timestamp_ns"), static_cast<double>(bag.endNanoseconds())},
        {QStringLiteral("start_utc"), utc(bag.startNanoseconds())},
        {QStringLiteral("end_utc"), utc(bag.endNanoseconds())},
        {QStringLiteral("duration_s"), static_cast<double>(bag.endNanoseconds() - bag.startNanoseconds()) * 1e-9},
        {QStringLiteral("messages"), static_cast<double>(bag.messageCount())},
        {QStringLiteral("chunks"), bag.chunks().size()},
        {QStringLiteral("topics"), topics},
    };
    QSet<QString> compressions;
    for (const auto& chunk : bag.chunks()) {
      compressions.insert(chunk.compression);
    }
    QJsonArray compressionValues;
    auto sortedCompressions = compressions.values();
    std::sort(sortedCompressions.begin(), sortedCompressions.end());
    for (const auto& compression : sortedCompressions) {
      compressionValues.append(compression);
    }
    report.insert(QStringLiteral("chunk_compressions"), compressionValues);
    if (includeHash) {
      report.insert(QStringLiteral("sha256"), hashFile(path));
    }
    bags.append(report);
  }
  return {{QStringLiteral("generated_at_utc"), QDateTime::currentDateTimeUtc().toString(Qt::ISODateWithMs)},
          {QStringLiteral("bags"), bags}};
}

QJsonObject exportGroundTruthTum(const QString& groundTruthBag, const QString& outputPath) {
  if (QFileInfo::exists(outputPath)) {
    throw ContractError(QStringLiteral("La sortie existe déjà : %1").arg(outputPath));
  }
  Ros1Bag bag(groundTruthBag);
  bag.open();
  QDir().mkpath(QFileInfo(outputPath).absolutePath());
  QSaveFile output(outputPath);
  if (!output.open(QIODevice::WriteOnly | QIODevice::Text)) {
    throw ContractError(QStringLiteral("Sortie TUM impossible à créer"));
  }
  QTextStream stream(&output);
  stream.setRealNumberNotation(QTextStream::FixedNotation);
  stream.setRealNumberPrecision(9);
  stream << "# timestamp tx ty tz qx qy qz qw\n";
  quint64 count = 0;
  bag.forEachMessage({QStringLiteral("/gt_poses")}, std::numeric_limits<qint64>::min(),
                     std::numeric_limits<qint64>::max(), [&](const Ros1Connection&, const Ros1Message& message) {
                       BufferReader reader(message.data);
                       static_cast<void>(header(reader));
                       const std::array<double, 3> position{reader.f64(), reader.f64(), reader.f64()};
                       const std::array<double, 4> orientation{reader.f64(), reader.f64(), reader.f64(), reader.f64()};
                       stream << static_cast<double>(message.timestampNanoseconds) * 1e-9 << ' ' << position[0] << ' '
                              << position[1] << ' ' << position[2] << ' ' << orientation[0] << ' ' << orientation[1]
                              << ' ' << orientation[2] << ' ' << orientation[3] << '\n';
                       ++count;
                     });
  if (!output.commit()) {
    throw ContractError(QStringLiteral("Validation de la sortie TUM impossible"));
  }
  return {{QStringLiteral("output"), QFileInfo(outputPath).absoluteFilePath()},
          {QStringLiteral("poses"), static_cast<double>(count)}};
}

}  // namespace drone_agricole::core
