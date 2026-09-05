#include "drone_agricole/core/TrajectoryAnalysis.hpp"

#include <QtTest>

#include <cmath>

using namespace drone_agricole::core;

class TestTrajectoryAnalysis final : public QObject {
  Q_OBJECT

 private slots:
  void alignsPlanarPositions() {
    const QList<QVector3D> source{QVector3D(0, 0, 0), QVector3D(100, 0, 0),
                                  QVector3D(100, 30, 0), QVector3D(0, 30, 0)};
    for (const float angle : {2.0f, 90.0f, 180.0f}) {
      const auto rotation = QQuaternion::fromAxisAndAngle(QVector3D(0, 0, 1), angle);
      const QVector3D translation(2, -1, 0.5f);
      QList<QVector3D> target;
      for (const auto& point : source) {
        target.append(rotation.rotatedVector(point) + translation);
      }
      const auto alignment = alignPositions(source, target);
      for (qsizetype i = 0; i < source.size(); ++i) {
        QVERIFY((alignment.rotation.rotatedVector(source[i]) + alignment.translation - target[i]).length() < 1e-3f);
      }
    }
  }

  void reportsQuaternionAngle() {
    const auto yaw = QQuaternion::fromAxisAndAngle(QVector3D(0.0f, 0.0f, 1.0f), 90.0f);
    QVERIFY(std::abs(rotationErrorDegrees(QQuaternion(), yaw) - 90.0) < 1e-5);
  }

  void detectsRpeScaleError() {
    QList<TimedPose> estimate;
    QList<TimedPose> truth;
    for (int index = 0; index < 3; ++index) {
      estimate.append(TimedPose{static_cast<double>(index), QVector3D(1.1f * index, 0.0f, 0.0f), QQuaternion()});
      truth.append(TimedPose{static_cast<double>(index), QVector3D(static_cast<float>(index), 0.0f, 0.0f), QQuaternion()});
    }
    const auto result = computeRpe(estimate, truth, 1.0, 0.01);
    QCOMPARE(result.value(QStringLiteral("pairs")).toInt(), 2);
    QVERIFY(std::abs(result.value(QStringLiteral("translation_m")).toObject().value(QStringLiteral("rmse")).toDouble() -
                     0.1) < 1e-5);
    QVERIFY(result.value(QStringLiteral("rotation_deg")).toObject().value(QStringLiteral("maximum")).toDouble() < 1e-9);
  }

  void alignsRotatedPositions() {
    const QList<QVector3D> source{QVector3D(0, 0, 0), QVector3D(1, 0, 0), QVector3D(0, 1, 0), QVector3D(1, 1, 1)};
    const auto expectedRotation = QQuaternion::fromAxisAndAngle(QVector3D(0, 0, 1), 90.0f);
    const QVector3D expectedTranslation(2, -1, 0.5f);
    QList<QVector3D> target;
    for (const auto& point : source) {
      target.append(expectedRotation.rotatedVector(point) + expectedTranslation);
    }
    const auto alignment = alignPositions(source, target);
    QVERIFY(rotationErrorDegrees(expectedRotation, alignment.rotation) < 1e-3);
    QVERIFY((alignment.translation - expectedTranslation).length() < 1e-3f);
  }
};

QTEST_APPLESS_MAIN(TestTrajectoryAnalysis)
#include "TestTrajectoryAnalysis.moc"
