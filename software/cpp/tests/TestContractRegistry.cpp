#include "drone_agricole/core/ContractRegistry.hpp"
#include "drone_agricole/core/JsonUtils.hpp"

#include <QtTest>

using namespace drone_agricole::core;

class TestContractRegistry final : public QObject {
  Q_OBJECT

 private slots:
  void loadsPublishedContracts() {
    ContractRegistry registry(QStringLiteral(DRONE_AGRICOLE_TEST_WORKSPACE));
    registry.load();
    QCOMPARE(registry.schemaDocumentCount(), 8);
    QCOMPARE(registry.simulations().size(), 3);
    int mappingModules = 0;
    for (const auto& simulation : registry.simulations()) {
      if (simulation.domain == QStringLiteral("mapping")) {
        ++mappingModules;
        QCOMPARE(simulation.id, QStringLiteral("vineyard_capture_mapping"));
      }
    }
    QCOMPARE(mappingModules, 1);
    QCOMPARE(registry.datasetSequences().size(), 6);
    QCOMPARE(registry.compatibleSequences(QStringLiteral("lio_benchmark"), QStringLiteral("fast_lio2")).size(), 4);
    QCOMPARE(registry.compatibleSequences(QStringLiteral("lio_benchmark"), QStringLiteral("point_lio")).size(), 4);
    QCOMPARE(registry.compatibleSequences(QStringLiteral("lio_benchmark"), QStringLiteral("lio_sam")).size(), 4);
    QCOMPARE(registry.compatibleSequences(QStringLiteral("vineyard_mapping"),
                                          QStringLiteral("height_density_v1")).size(), 1);
    const auto captureSequences = registry.compatibleSequences(QStringLiteral("vineyard_capture_mapping"),
                                                                QStringLiteral("trigger_rows_v1"));
    QCOMPARE(captureSequences.size(), 1);
    QCOMPARE(captureSequences.constFirst().datasetId, QStringLiteral("friulbot"));
  }

  void resolvesAndBoundsRunRequest() {
    ContractRegistry registry(QStringLiteral(DRONE_AGRICOLE_TEST_WORKSPACE));
    registry.load();
    const auto request = registry.resolveRequest(
        QStringLiteral("lio_benchmark"), QStringLiteral("fast_lio2"),
        QStringLiteral("botanicgarden_velodyne_xsens"), QStringLiteral("botanicgarden"),
        QStringLiteral("1006-03-smoke"), QJsonObject{{QStringLiteral("playback_rate"), 1.0}});
    QCOMPARE(request.value(QStringLiteral("schema")).toString(), QStringLiteral("drone_agricole.run_request.v1"));
    QVERIFY(!request.value(QStringLiteral("request_id")).toString().isEmpty());
    const auto requestedAt = QDateTime::fromString(request.value(QStringLiteral("requested_at_utc")).toString(),
                                                   Qt::ISODateWithMs);
    QVERIFY(requestedAt.isValid());
    QCOMPARE(requestedAt.timeSpec(), Qt::UTC);
    QCOMPARE(request.value(QStringLiteral("parameters")).toObject().size(), 7);
    QVERIFY_EXCEPTION_THROWN(
        static_cast<void>(registry.resolveRequest(
            QStringLiteral("lio_benchmark"), QStringLiteral("fast_lio2"), QString{},
            QStringLiteral("botanicgarden"), QStringLiteral("1006-03-smoke"),
            QJsonObject{{QStringLiteral("playback_rate"), 50.0}})),
        ContractError);
    QVERIFY_EXCEPTION_THROWN(
        static_cast<void>(registry.resolveRequest(
            QStringLiteral("lio_benchmark"), QStringLiteral("fast_lio2"), QString{},
            QStringLiteral("botanicgarden"), QStringLiteral("1006-03-smoke"),
            QJsonObject{{QStringLiteral("command"), QStringLiteral("rm")}})),
        ContractError);
  }
};

QTEST_APPLESS_MAIN(TestContractRegistry)
#include "TestContractRegistry.moc"
