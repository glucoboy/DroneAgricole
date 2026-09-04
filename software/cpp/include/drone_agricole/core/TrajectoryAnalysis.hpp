#pragma once

#include <QJsonObject>
#include <QList>
#include <QQuaternion>
#include <QVector3D>

namespace drone_agricole::core {

struct TimedPose {
  double timeSeconds{0.0};
  QVector3D position;
  QQuaternion orientation;
};

struct RigidAlignment {
  QQuaternion rotation;
  QVector3D translation;
};

[[nodiscard]] QJsonObject errorStatistics(const QList<double>& values);
[[nodiscard]] double rotationErrorDegrees(const QQuaternion& reference, const QQuaternion& estimate);
[[nodiscard]] RigidAlignment alignPositions(const QList<QVector3D>& source, const QList<QVector3D>& target);
[[nodiscard]] QJsonObject computeRpe(const QList<TimedPose>& estimate,
                                     const QList<TimedPose>& truth,
                                     double deltaSeconds,
                                     double toleranceSeconds);
[[nodiscard]] double trajectoryLength(const QList<QVector3D>& positions);

}  // namespace drone_agricole::core
