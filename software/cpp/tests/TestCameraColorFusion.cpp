#include "drone_agricole/algorithms/CameraColorFusion.hpp"
#include <QtTest>
#include <limits>
#include <stdexcept>
using namespace drone_agricole::algorithms;
class TestCameraColorFusion : public QObject {
  Q_OBJECT
 private slots:
  void projectsActualColorsAndRejectsOcclusion() {
    std::array<CameraBand, 3> bands;
    for (auto& band : bands) {
      band.width = band.height = 3;
      band.pixels.assign(9, 0);
      band.camera.focalPixels = 1;
      band.camera.principalX = band.camera.principalY = 1;
    }
    bands[0].pixels[4] = 65535;
    const auto fused = fuseCameraRgb({{0,0,1}, {0,0,2}, {0,0,-1}, {100,0,1}}, bands);
    QCOMPARE(fused.points.size(), 1);
    QCOMPARE(fused.points[0], QVector3D(0,0,1));
    QCOMPARE(fused.colors[0], QColor(255,0,0));
    for (auto& band : bands) band.camera.translation[0] = 1;
    const auto shifted = fuseCameraRgb({{-1,0,1}}, bands);
    QCOMPARE(shifted.colors[0], QColor(255,0,0));
  }
  void rejectsInvalidCalibrationAndImage() {
    std::array<CameraBand, 3> bands;
    QVERIFY_EXCEPTION_THROWN(static_cast<void>(fuseCameraRgb({}, bands)), std::invalid_argument);
    for (auto& band : bands) {
      band.width = band.height = 1;
      band.pixels = {65535};
      band.camera.focalPixels = 1;
    }
    QCOMPARE(fuseCameraRgb({{0,0,1}}, bands).colors[0], QColor(255,255,255));
    bands[1].camera.quaternion = {0,0,0,0};
    QVERIFY_EXCEPTION_THROWN(static_cast<void>(fuseCameraRgb({}, bands)), std::invalid_argument);
    bands[1].camera.quaternion = {0,0,0,1};
    const auto invalid = std::numeric_limits<float>::quiet_NaN();
    QVERIFY(fuseCameraRgb({{invalid,0,1}}, bands).points.isEmpty());
  }
};
QTEST_APPLESS_MAIN(TestCameraColorFusion)
#include "TestCameraColorFusion.moc"
