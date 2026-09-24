#include "drone_agricole/core/Ros1Bag.hpp"

#include "drone_agricole/core/JsonUtils.hpp"

#include <QFile>
#include <QFileInfo>

#include <algorithm>
#include <limits>

namespace drone_agricole::core {
namespace {

constexpr quint8 kMessageData = 0x02;
constexpr quint8 kBagHeader = 0x03;
constexpr quint8 kChunk = 0x05;
constexpr quint8 kChunkInfo = 0x06;
constexpr quint8 kConnection = 0x07;

struct Record {
  quint64 position{0};
  QHash<QByteArray, QByteArray> header;
  QByteArray data;
};

quint32 littleU32(const QByteArray& value) {
  if (value.size() < 4) {
    throw ContractError(QStringLiteral("Champ uint32 ROS 1 tronqué"));
  }
  const auto* bytes = reinterpret_cast<const uchar*>(value.constData());
  return static_cast<quint32>(bytes[0]) | (static_cast<quint32>(bytes[1]) << 8U) |
         (static_cast<quint32>(bytes[2]) << 16U) | (static_cast<quint32>(bytes[3]) << 24U);
}

quint64 littleU64(const QByteArray& value) {
  if (value.size() < 8) {
    throw ContractError(QStringLiteral("Champ uint64 ROS 1 tronqué"));
  }
  quint64 result = 0;
  for (int index = 0; index < 8; ++index) {
    result |= static_cast<quint64>(static_cast<uchar>(value[index])) << (8U * index);
  }
  return result;
}

qint64 rosTime(const QByteArray& value) {
  if (value.size() < 8) {
    throw ContractError(QStringLiteral("Horodatage ROS 1 tronqué"));
  }
  return static_cast<qint64>(littleU32(value.left(4))) * 1000000000LL + littleU32(value.mid(4, 4));
}

QHash<QByteArray, QByteArray> parseHeader(const QByteArray& bytes) {
  QHash<QByteArray, QByteArray> fields;
  qsizetype offset = 0;
  while (offset < bytes.size()) {
    if (offset + 4 > bytes.size()) {
      throw ContractError(QStringLiteral("En-tête ROS 1 tronqué"));
    }
    const auto length = littleU32(bytes.mid(offset, 4));
    offset += 4;
    if (length == 0 || length > static_cast<quint32>(bytes.size() - offset)) {
      throw ContractError(QStringLiteral("Champ d'en-tête ROS 1 invalide"));
    }
    const auto field = bytes.mid(offset, length);
    offset += length;
    const auto separator = field.indexOf('=');
    if (separator <= 0) {
      throw ContractError(QStringLiteral("Champ d'en-tête ROS 1 sans nom"));
    }
    fields.insert(field.left(separator), field.mid(separator + 1));
  }
  return fields;
}

quint8 operation(const Record& record) {
  const auto value = record.header.value("op");
  return value.isEmpty() ? 0 : static_cast<quint8>(value.front());
}

Record readRecord(QFile& file, const bool loadData) {
  Record record;
  record.position = file.pos();
  QByteArray sizeBytes = file.read(4);
  if (sizeBytes.size() != 4) {
    throw ContractError(QStringLiteral("Longueur d'en-tête ROS 1 absente"));
  }
  const auto headerSize = littleU32(sizeBytes);
  const auto headerBytes = file.read(headerSize);
  if (headerBytes.size() != static_cast<qsizetype>(headerSize)) {
    throw ContractError(QStringLiteral("En-tête ROS 1 incomplet"));
  }
  record.header = parseHeader(headerBytes);
  sizeBytes = file.read(4);
  if (sizeBytes.size() != 4) {
    throw ContractError(QStringLiteral("Longueur de données ROS 1 absente"));
  }
  const auto dataSize = littleU32(sizeBytes);
  if (loadData) {
    record.data = file.read(dataSize);
    if (record.data.size() != static_cast<qsizetype>(dataSize)) {
      throw ContractError(QStringLiteral("Données ROS 1 incomplètes"));
    }
  } else if (!file.seek(file.pos() + dataSize)) {
    throw ContractError(QStringLiteral("Déplacement impossible dans le rosbag ROS 1"));
  }
  return record;
}

Record readMemoryRecord(const QByteArray& bytes, qsizetype& offset) {
  auto read = [&](const qsizetype count) {
    if (offset + count > bytes.size()) {
      throw ContractError(QStringLiteral("Chunk ROS 1 tronqué"));
    }
    const auto value = bytes.mid(offset, count);
    offset += count;
    return value;
  };
  Record record;
  record.position = offset;
  const auto headerSize = littleU32(read(4));
  record.header = parseHeader(read(headerSize));
  const auto dataSize = littleU32(read(4));
  record.data = read(dataSize);
  return record;
}

Ros1Connection connectionFrom(const Record& record) {
  Ros1Connection connection;
  connection.id = littleU32(record.header.value("conn"));
  connection.topic = QString::fromUtf8(record.header.value("topic"));
  const auto metadata = parseHeader(record.data);
  connection.type = QString::fromUtf8(metadata.value("type"));
  connection.md5 = QString::fromUtf8(metadata.value("md5sum"));
  connection.messageDefinition = QString::fromUtf8(metadata.value("message_definition"));
  return connection;
}

QByteArray chunkData(const Ros1Chunk& descriptor, QFile& file) {
  if (!file.seek(descriptor.position)) {
    throw ContractError(QStringLiteral("Chunk ROS 1 inaccessible"));
  }
  const auto record = readRecord(file, true);
  if (operation(record) != kChunk) {
    throw ContractError(QStringLiteral("Position de chunk ROS 1 invalide"));
  }
  const auto compression = QString::fromUtf8(record.header.value("compression"));
  if (compression != QStringLiteral("none")) {
    throw ContractError(QStringLiteral("Compression ROS 1 non supportée : %1").arg(compression));
  }
  return record.data;
}

}  // namespace

Ros1Bag::Ros1Bag(QString path) : path_(std::move(path)) {}

void Ros1Bag::open() {
  QFile file(path_);
  if (!file.open(QIODevice::ReadOnly)) {
    throw ContractError(QStringLiteral("Rosbag ROS 1 illisible : %1").arg(path_));
  }
  if (file.read(13) != QByteArray("#ROSBAG V2.0\n", 13)) {
    throw ContractError(QStringLiteral("Signature rosbag ROS 1 V2 absente"));
  }
  const auto bagHeader = readRecord(file, false);
  if (operation(bagHeader) != kBagHeader) {
    throw ContractError(QStringLiteral("BAGHEADER ROS 1 attendu"));
  }
  const auto indexPosition = littleU64(bagHeader.header.value("index_pos"));
  if (!file.seek(static_cast<qint64>(indexPosition))) {
    throw ContractError(QStringLiteral("Index ROS 1 inaccessible"));
  }
  connections_.clear();
  chunks_.clear();
  startNanoseconds_ = std::numeric_limits<qint64>::max();
  endNanoseconds_ = 0;
  messageCount_ = 0;
  while (!file.atEnd()) {
    const auto record = readRecord(file, true);
    if (operation(record) == kConnection) {
      auto connection = connectionFrom(record);
      connection.messageCount = connections_.value(connection.id).messageCount;
      connections_.insert(connection.id, connection);
    } else if (operation(record) == kChunkInfo) {
      Ros1Chunk chunk;
      chunk.position = littleU64(record.header.value("chunk_pos"));
      chunk.startNanoseconds = rosTime(record.header.value("start_time"));
      chunk.endNanoseconds = rosTime(record.header.value("end_time"));
      startNanoseconds_ = std::min(startNanoseconds_, chunk.startNanoseconds);
      endNanoseconds_ = std::max(endNanoseconds_, chunk.endNanoseconds);
      const auto count = littleU32(record.header.value("count"));
      for (quint32 index = 0; index < count; ++index) {
        const auto offset = static_cast<qsizetype>(index * 8);
        const auto connectionId = littleU32(record.data.mid(offset, 4));
        const auto messages = littleU32(record.data.mid(offset + 4, 4));
        connections_[connectionId].id = connectionId;
        connections_[connectionId].messageCount += messages;
        messageCount_ += messages;
      }
      chunks_.append(chunk);
    }
  }
  if (chunks_.isEmpty()) {
    startNanoseconds_ = 0;
  }
  for (auto& chunk : chunks_) {
    if (!file.seek(chunk.position)) {
      throw ContractError(QStringLiteral("Chunk indexé inaccessible"));
    }
    const auto record = readRecord(file, false);
    chunk.compression = QString::fromUtf8(record.header.value("compression"));
    chunk.uncompressedSize = littleU32(record.header.value("size"));
    chunk.storedSize = static_cast<quint32>(file.pos() - chunk.position);  // taille d'en-tête informative
  }
}

const QString& Ros1Bag::path() const { return path_; }
const QHash<quint32, Ros1Connection>& Ros1Bag::connections() const { return connections_; }
const QList<Ros1Chunk>& Ros1Bag::chunks() const { return chunks_; }
qint64 Ros1Bag::startNanoseconds() const { return startNanoseconds_; }
qint64 Ros1Bag::endNanoseconds() const { return endNanoseconds_; }
quint64 Ros1Bag::messageCount() const { return messageCount_; }

void Ros1Bag::forEachMessage(const QSet<QString>& topics,
                             const qint64 startNanoseconds,
                             const qint64 stopNanoseconds,
                             const std::function<void(const Ros1Connection&, const Ros1Message&)>& callback) const {
  QFile file(path_);
  if (!file.open(QIODevice::ReadOnly)) {
    throw ContractError(QStringLiteral("Rosbag ROS 1 illisible"));
  }
  QSet<quint32> selectedConnections;
  for (auto iterator = connections_.cbegin(); iterator != connections_.cend(); ++iterator) {
    if (topics.contains(iterator->topic)) {
      selectedConnections.insert(iterator.key());
    }
  }
  for (const auto& chunk : chunks_) {
    if (chunk.endNanoseconds < startNanoseconds || chunk.startNanoseconds >= stopNanoseconds) {
      continue;
    }
    const auto data = chunkData(chunk, file);
    qsizetype offset = 0;
    while (offset < data.size()) {
      const auto record = readMemoryRecord(data, offset);
      if (operation(record) == kConnection) {
        continue;
      }
      if (operation(record) != kMessageData) {
        continue;
      }
      const auto connectionId = littleU32(record.header.value("conn"));
      if (!selectedConnections.contains(connectionId)) {
        continue;
      }
      const auto timestamp = rosTime(record.header.value("time"));
      if (timestamp >= startNanoseconds && timestamp < stopNanoseconds) {
        callback(connections_.value(connectionId), Ros1Message{connectionId, timestamp, record.data});
      }
    }
  }
}

}  // namespace drone_agricole::core
