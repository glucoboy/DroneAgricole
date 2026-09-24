#include "drone_agricole/core/JsonUtils.hpp"
#include "drone_agricole/core/VineyardMap.hpp"

#include <QDir>
#include <QFileInfo>
#include <QJsonArray>
#include <QTemporaryDir>
#include <QtTest>

using namespace drone_agricole::core;

namespace {

QJsonArray point(const double x, const double y, const double z) {
  return QJsonArray{x, y, z};
}

}  // namespace

class TestVineyardMap final : public QObject {
  Q_OBJECT

 private slots:
  void readsReplayContract() {
    QTemporaryDir directory;
    QVERIFY(directory.isValid());
    const auto path = QDir(directory.path()).filePath(QStringLiteral("map_replay.json"));
    writeJsonObjectAtomically(
        path,
        QJsonObject{
            {QStringLiteral("schema"), QStringLiteral("drone_agricole.map_replay.v1")},
            {QStringLiteral("point_cloud"), QJsonArray{point(1.0, 2.0, 3.0), point(4.0, 5.0, 6.0)}},
            {QStringLiteral("camera_projected_points"), QJsonArray{point(2.0, 3.0, 4.0)}},
            {QStringLiteral("camera_point_colors"), QJsonArray{QJsonArray{12, 34, 56}}},
            {QStringLiteral("reference_points"), QJsonArray{point(7.0, 8.0, 9.0)}},
            {QStringLiteral("polylines"),
             QJsonArray{QJsonObject{{QStringLiteral("label"), QStringLiteral("Rang 1")},
                                    {QStringLiteral("role"), QStringLiteral("detected_row")},
                                    {QStringLiteral("points"), QJsonArray{point(0.0, 0.0, 0.0), point(0.0, 10.0, 0.0)}}},
                        QJsonObject{{QStringLiteral("label"), QStringLiteral("Trajectoire 1")},
                                    {QStringLiteral("role"), QStringLiteral("candidate_trajectory")},
                                    {QStringLiteral("points"), QJsonArray{point(1.0, 0.0, 1.5), point(1.0, 10.0, 1.5)}}}}},
            {QStringLiteral("warnings"), QJsonArray{QStringLiteral("Paramètres à valider.")}},
        });

    const auto replay = readVineyardMapReplay(path, QStringLiteral("mapping-test"));
    QCOMPARE(replay.resultId, QStringLiteral("mapping-test"));
    QCOMPARE(replay.domain, QStringLiteral("mapping"));
    QCOMPARE(replay.mapPoints.size(), 2);
    QCOMPARE(replay.cameraProjectedPoints.size(), 1);
    QCOMPARE(replay.cameraPointColors, QList<QColor>{QColor(12, 34, 56)});
    QCOMPARE(replay.referencePoints.size(), 1);
    QCOMPARE(replay.mapPolylines.size(), 2);
    QCOMPARE(replay.mapPolylines.at(0).role, QStringLiteral("detected_row"));
    QCOMPARE(replay.mapPolylines.at(1).role, QStringLiteral("candidate_trajectory"));
    QCOMPARE(replay.mapPolylines.at(1).points.size(), 2);
    QCOMPARE(replay.notes, QStringList{QStringLiteral("Paramètres à valider.")});
  }

  void rejectsUnsupportedSchema() {
    QTemporaryDir directory;
    QVERIFY(directory.isValid());
    const auto path = QDir(directory.path()).filePath(QStringLiteral("map_replay.json"));
    writeJsonObjectAtomically(path, QJsonObject{{QStringLiteral("schema"), QStringLiteral("unknown.v1")}});
    QVERIFY_EXCEPTION_THROWN(static_cast<void>(readVineyardMapReplay(path, QStringLiteral("mapping-test"))), ContractError);
  }

  void readsSurfaceAndRejectsInvalidIndices() {
    QTemporaryDir directory;
    const auto path=QDir(directory.path()).filePath(QStringLiteral("map_replay.json"));
    QJsonObject surface{{QStringLiteral("vertices"),QJsonArray{point(0,0,0),point(1,0,0),point(0,1,0)}},
      {QStringLiteral("triangles"),QJsonArray{QJsonArray{0,1,2}}},
      {QStringLiteral("colors"),QJsonArray{QJsonArray{100,100,100},QJsonArray{100,100,100},QJsonArray{100,100,100}}}};
    QJsonObject object{{QStringLiteral("schema"),QStringLiteral("drone_agricole.map_replay.v1")},
      {QStringLiteral("surface"),surface},{QStringLiteral("metadata"),QJsonObject{{QStringLiteral("reconstruction_status"),QStringLiteral("partial")}}}};
    writeJsonObjectAtomically(path,object);
    const auto replay=readVineyardMapReplay(path,QStringLiteral("surface"));
    QCOMPARE(replay.surfaceVertices.size(),3);QCOMPARE(replay.surfaceTriangles.size(),1);
    QVERIFY(replay.reconstructionPartial);
    for(const auto& invalid:QJsonArray{QJsonArray{0,1,3},QJsonArray{0,1,1},QJsonArray{0,1,1.5},QJsonArray{-1,1,2}}) {
      surface.insert(QStringLiteral("triangles"),QJsonArray{invalid});object.insert(QStringLiteral("surface"),surface);
      writeJsonObjectAtomically(path,object);
      QVERIFY_EXCEPTION_THROWN(static_cast<void>(readVineyardMapReplay(path,QStringLiteral("invalid"))),ContractError);
    }
  }

  void rejectsMisalignedAndInvalidColors() {
    QTemporaryDir directory;
    const auto path = QDir(directory.path()).filePath(QStringLiteral("map_replay.json"));
    QJsonObject replay{{QStringLiteral("schema"), QStringLiteral("drone_agricole.map_replay.v1")},
                       {QStringLiteral("camera_projected_points"), QJsonArray{point(0,0,1)}}};
    for (const auto& invalid : QJsonArray{QJsonArray{QJsonArray{0,0,0}, QJsonArray{0,0,0}},
                                        QJsonArray{QJsonArray{0,256,0}}, QJsonArray{QJsonArray{0,1.5,0}}, QStringLiteral("red")}) {
      replay.insert(QStringLiteral("camera_point_colors"), invalid);
      writeJsonObjectAtomically(path, replay);
      QVERIFY_EXCEPTION_THROWN(static_cast<void>(readVineyardMapReplay(path, QStringLiteral("test"))), ContractError);
    }
    replay.remove(QStringLiteral("camera_point_colors"));
    writeJsonObjectAtomically(path, replay);
    QVERIFY(readVineyardMapReplay(path, QStringLiteral("legacy")).cameraPointColors.isEmpty());
  }

  void rejectsOutOfRangeRunnerParameter() {
    QTemporaryDir directory;
    QVERIFY(directory.isValid());
    const auto requestPath = QDir(directory.path()).filePath(QStringLiteral("request.json"));
    writeJsonObjectAtomically(
        requestPath,
        QJsonObject{{QStringLiteral("schema"), QStringLiteral("drone_agricole.run_request.v1")},
                    {QStringLiteral("request_id"), QStringLiteral("request_test")},
                    {QStringLiteral("simulation_id"), QStringLiteral("vineyard_mapping")},
                    {QStringLiteral("variant_id"), QStringLiteral("height_density_v1")},
                    {QStringLiteral("requested_at_utc"), QStringLiteral("2026-09-06T00:00:00Z")},
                    {QStringLiteral("inputs"), QJsonArray{}},
                    {QStringLiteral("parameters"), QJsonObject{{QStringLiteral("grid_resolution_m"), 0.0}}}});
    const QJsonObject options{
        {QStringLiteral("request"), requestPath},
        {QStringLiteral("run-id"), QStringLiteral("invalid-parameter")},
        {QStringLiteral("point-cloud"), QDir(directory.path()).filePath(QStringLiteral("missing.las"))},
        {QStringLiteral("reference-trunks"), QDir(directory.path()).filePath(QStringLiteral("missing.shp"))},
        {QStringLiteral("run-dir"), QDir(directory.path()).filePath(QStringLiteral("result"))},
    };
    QVERIFY_EXCEPTION_THROWN(static_cast<void>(runVineyardMapping(options)), ContractError);
    QVERIFY(!QFileInfo::exists(options.value(QStringLiteral("run-dir")).toString()));
  }
};

QTEST_MAIN(TestVineyardMap)
#include "TestVineyardMap.moc"
