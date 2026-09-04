#include "drone_agricole/core/AdaptivePointMap.hpp"

#include <QtTest>

#include <algorithm>
#include <cmath>
#include <vector>

using namespace drone_agricole::core;

class TestAdaptivePointMap final : public QObject {
  Q_OBJECT

 private slots:
  void compactionKeepsWholeRouteRepresented() {
    AdaptivePointMap map(0.10F, 64);
    std::vector<QVector3D> route;
    for (int index = 0; index < 800; ++index) {
      const auto x = static_cast<float>(index) * 0.11F;
      route.emplace_back(x, 0.2F * std::sin(x), 1.0F);
    }

    map.insert(route);

    QVERIFY(map.size() <= map.capacity());
    QVERIFY(map.compactionCount() > 0);
    QVERIFY(map.voxelSizeMeters() > 0.10F);
    const auto [minimum, maximum] = std::minmax_element(
        map.points().cbegin(), map.points().cend(),
        [](const auto& left, const auto& right) { return left.x() < right.x(); });
    QVERIFY(minimum != map.points().cend());
    QVERIFY(minimum->x() < 2.0F);
    QVERIFY(maximum->x() > 80.0F);
  }

  void duplicatesDoNotFillCapacity() {
    AdaptivePointMap map(0.10F, 8);
    std::vector<QVector3D> duplicates(100, QVector3D(1.0F, 2.0F, 3.0F));

    map.insert(duplicates);

    QCOMPARE(map.size(), std::size_t{1});
    QCOMPARE(map.compactionCount(), std::size_t{0});
  }

  void clearRestoresInitialResolution() {
    AdaptivePointMap map(0.10F, 8);
    std::vector<QVector3D> route;
    for (int index = 0; index < 100; ++index) {
      route.emplace_back(static_cast<float>(index), 0.0F, 0.0F);
    }
    map.insert(route);
    QVERIFY(map.compactionCount() > 0);

    map.clear();

    QCOMPARE(map.size(), std::size_t{0});
    QCOMPARE(map.compactionCount(), std::size_t{0});
    QCOMPARE(map.voxelSizeMeters(), 0.10F);
  }
};

QTEST_APPLESS_MAIN(TestAdaptivePointMap)
#include "TestAdaptivePointMap.moc"
