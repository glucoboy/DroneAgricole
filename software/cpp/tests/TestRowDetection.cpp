#include "drone_agricole/algorithms/RowDetection.hpp"
#include "drone_agricole/core/JsonUtils.hpp"
#include <QtTest>
using namespace drone_agricole;
class TestRowDetection : public QObject {
  Q_OBJECT
 private slots:
  void detectsParallelRowsFromNormalizedCells() {
    std::vector<algorithms::WeightedCell> cells;
    for (int row = 0; row < 4; ++row)
      for (int x = 0; x < 120; ++x) cells.push_back({x * 0.25, 2.0 + row * 3.0, 1.0, 3.0});
    const auto result = algorithms::detectWeightedRows(cells, {30.0, 14.0, 0.25, 2.0, 0.3},
                                                       [](double, double) { return 0.0; });
    QCOMPARE(result.orientationDegrees, 0);
    QCOMPARE(result.rows.size(), std::size_t{4});
    for (const auto& row : result.rows) {
      QVERIFY(row.maximumT - row.minimumT > 20.0);
      QCOMPARE(row.points.first().z(), 1.2F);
    }
  }
  void captureUsesSameNormalizedGeometryWithoutDataset() {
    QList<QVector3D> points;
    for (int row = 0; row < 3; ++row)
      for (int x = 0; x < 100; ++x) points.append(QVector3D(x * 0.1F, row * 3.0F, 0.0F));
    double orientation = -1;
    const auto rows = algorithms::detectCaptureRows(points, 0.25, 2.0, 0.3, orientation);
    QCOMPARE(orientation, 0.0);
    QCOMPARE(rows.size(), 3);
  }
  void rejectsInvalidInput() {
    QVERIFY_EXCEPTION_THROWN(algorithms::detectWeightedRows({}, {1,1,0,1,0.3}, [](double,double){return 0.0;}), core::ContractError);
  }
};
QTEST_GUILESS_MAIN(TestRowDetection)
#include "TestRowDetection.moc"
