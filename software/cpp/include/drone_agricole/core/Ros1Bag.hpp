#pragma once

#include <QByteArray>
#include <QHash>
#include <QList>
#include <QSet>
#include <QString>

#include <functional>

namespace drone_agricole::core {

struct Ros1Connection {
  quint32 id{0};
  QString topic;
  QString type;
  QString md5;
  QString messageDefinition;
  quint64 messageCount{0};
};

struct Ros1Chunk {
  quint64 position{0};
  qint64 startNanoseconds{0};
  qint64 endNanoseconds{0};
  QString compression;
  quint32 uncompressedSize{0};
  quint32 storedSize{0};
};

struct Ros1Message {
  quint32 connectionId{0};
  qint64 timestampNanoseconds{0};
  QByteArray data;
};

class Ros1Bag final {
 public:
  explicit Ros1Bag(QString path);

  void open();
  [[nodiscard]] const QString& path() const;
  [[nodiscard]] const QHash<quint32, Ros1Connection>& connections() const;
  [[nodiscard]] const QList<Ros1Chunk>& chunks() const;
  [[nodiscard]] qint64 startNanoseconds() const;
  [[nodiscard]] qint64 endNanoseconds() const;
  [[nodiscard]] quint64 messageCount() const;

  void forEachMessage(const QSet<QString>& topics,
                      qint64 startNanoseconds,
                      qint64 stopNanoseconds,
                      const std::function<void(const Ros1Connection&, const Ros1Message&)>& callback) const;

 private:
  QString path_;
  QHash<quint32, Ros1Connection> connections_;
  QList<Ros1Chunk> chunks_;
  qint64 startNanoseconds_{0};
  qint64 endNanoseconds_{0};
  quint64 messageCount_{0};
};

}  // namespace drone_agricole::core
