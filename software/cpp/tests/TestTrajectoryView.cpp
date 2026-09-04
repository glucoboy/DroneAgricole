#include "drone_agricole/ui/TrajectoryView.hpp"

#include <QImage>
#include <QGuiApplication>
#include <QtTest>

#include <cmath>

using namespace drone_agricole::ui;

class TestTrajectoryView final : public QObject {
  Q_OBJECT

 private slots:
  void rendersNavigableMetricMap() {
    TrajectoryView view;
    view.resize(960, 620);

    QList<QVector3D> cloud;
    for (int row = -4; row <= 4; ++row) {
      const auto x = static_cast<float>(row) * 2.4F;
      for (int step = 0; step <= 180; ++step) {
        const auto y = static_cast<float>(step) * 0.28F;
        const auto terrain = 0.12F * std::sin(y * 0.16F);
        cloud.append(QVector3D(x - 0.35F, y, terrain + 0.45F));
        cloud.append(QVector3D(x + 0.35F, y, terrain + 0.95F));
        cloud.append(QVector3D(x, y, terrain + 1.55F));
      }
    }
    QList<QVector3D> estimate;
    QList<QVector3D> truth;
    for (int step = 0; step <= 160; ++step) {
      const auto y = static_cast<float>(step) * 0.31F;
      truth.append(QVector3D(0.0F, y, 1.8F));
      estimate.append(QVector3D(0.08F * std::sin(y * 0.25F), y, 1.82F));
    }

    view.setPointCloud(cloud);
    view.setSeries({
        {QStringLiteral("Estimation"), QColor(QStringLiteral("#55e2d2")), estimate, false},
        {QStringLiteral("Vérité terrain"), QColor(QStringLiteral("#ffd166")), truth, true},
    });
    view.fitToData();

    QCOMPARE(view.pointCloudSize(), cloud.size());
    QVERIFY(std::abs(view.cameraTarget().y() - 25.2F) < 1.0F);
    QVERIFY(std::isfinite(view.cameraDistance()));
    QVERIFY(view.cameraDistance() > 10.0F);

    view.show();
    QTest::qWait(150);
    const auto initialDistance = view.cameraDistance();
    QTest::keyClick(&view, Qt::Key_Plus);
    QVERIFY(view.cameraDistance() < initialDistance);
    if (QGuiApplication::platformName() == QStringLiteral("offscreen")) {
      return;
    }
    const auto image = view.grabFramebuffer();
    QVERIFY(!image.isNull());
    QVERIFY(image.width() >= 900);
    const auto screenshot = qEnvironmentVariable("DRONE_AGRICOLE_MAP_SCREENSHOT");
    if (!screenshot.isEmpty()) {
      QVERIFY(image.save(screenshot, "PNG"));
    }
  }

  void clearResetsMapContent() {
    TrajectoryView view;
    view.setPointCloud({QVector3D(1.0F, 2.0F, 3.0F)});
    QCOMPARE(view.pointCloudSize(), 1);
    view.clear();
    QCOMPARE(view.pointCloudSize(), 0);
  }
};

QTEST_MAIN(TestTrajectoryView)
#include "TestTrajectoryView.moc"
