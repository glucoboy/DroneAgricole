#pragma once

#include <QJsonObject>
#include <QList>
#include <QVector3D>

#include <memory>

namespace drone_agricole::core {

struct LiveTelemetrySnapshot {
  bool available{false};
  QList<QVector3D> cloud;
  QList<QVector3D> estimate;
  QList<QVector3D> truth;
  QList<QVector3D> px4Path;
  QJsonObject metrics;
  QJsonObject px4State;
};

class LiveTelemetry final {
 public:
  LiveTelemetry();
  ~LiveTelemetry();

  LiveTelemetry(const LiveTelemetry&) = delete;
  LiveTelemetry& operator=(const LiveTelemetry&) = delete;

  void reset();
  [[nodiscard]] LiveTelemetrySnapshot snapshot() const;

 private:
  class Impl;
  std::unique_ptr<Impl> impl_;
};

}  // namespace drone_agricole::core
