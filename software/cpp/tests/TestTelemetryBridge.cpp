#include "drone_agricole/core/TelemetryBridge.hpp"
#include "drone_agricole/core/JsonUtils.hpp"

#include <QJsonArray>
#include <QtTest>

using namespace drone_agricole::core;

class TestTelemetryBridge final : public QObject {
  Q_OBJECT

 private slots:
  void roundTripPreservesSnapshot() {
    LiveTelemetrySnapshot source;
    source.available = true;
    source.cloud = {QVector3D(1.0F, 2.0F, 3.0F)};
    source.estimate = {QVector3D(4.0F, 5.0F, 6.0F)};
    source.truth = {QVector3D(7.0F, 8.0F, 9.0F)};
    source.px4Path = {QVector3D(10.0F, 11.0F, 12.0F)};
    source.metrics = {{QStringLiteral("ate_rmse_m"), 0.12}};
    source.px4State = {{QStringLiteral("armed"), false}};

    const auto result = telemetrySnapshotFromJson(telemetrySnapshotToJson(source));

    QVERIFY(result.available);
    QCOMPARE(result.cloud, source.cloud);
    QCOMPARE(result.estimate, source.estimate);
    QCOMPARE(result.truth, source.truth);
    QCOMPARE(result.px4Path, source.px4Path);
    QCOMPARE(result.metrics, source.metrics);
    QCOMPARE(result.px4State, source.px4State);
  }

  void rejectsUnknownSchema() {
    const auto result = telemetrySnapshotFromJson(
        {{QStringLiteral("schema"), QStringLiteral("drone_agricole.telemetry_snapshot.v99")},
         {QStringLiteral("available"), true}});

    QVERIFY(!result.available);
    QVERIFY(result.cloud.isEmpty());
  }

  void boundsCloudPayload() {
    LiveTelemetrySnapshot source;
    source.available = true;
    for (int index = 0; index < 48000; ++index) {
      source.cloud.append(QVector3D(static_cast<float>(index), 0.0F, 0.0F));
    }

    const auto payload = telemetrySnapshotToJson(source);
    const auto cloud = payload.value(QStringLiteral("cloud")).toArray();

    QVERIFY(cloud.size() <= 16000);
    QVERIFY(!cloud.isEmpty());
  }

  void roundTripPreservesReplay() {
    ReplayData source;
    source.resultId = QStringLiteral("result-42");
    source.domain = QStringLiteral("localization");
    source.estimate = {QVector3D(1.0F, 2.0F, 3.0F)};
    source.truth = {QVector3D(4.0F, 5.0F, 6.0F)};
    source.curve = {QPointF(0.0, 0.4), QPointF(1.0, 0.2)};
    source.curveId = QStringLiteral("ate_cumulative_rmse_m");
    source.curveLabel = QStringLiteral("ATE cumulée");
    source.curveUnit = QStringLiteral("m");
    source.notes = {QStringLiteral("Relecture sans relance.")};

    const auto result = replayDataFromJson(replayDataToJson(source));

    QCOMPARE(result.resultId, source.resultId);
    QCOMPARE(result.domain, source.domain);
    QCOMPARE(result.estimate, source.estimate);
    QCOMPARE(result.truth, source.truth);
    QCOMPARE(result.curve, source.curve);
    QCOMPARE(result.curveId, source.curveId);
    QCOMPARE(result.curveLabel, source.curveLabel);
    QCOMPARE(result.curveUnit, source.curveUnit);
    QCOMPARE(result.notes, source.notes);
  }

  void rejectsUnknownReplaySchema() {
    QVERIFY_EXCEPTION_THROWN(
        static_cast<void>(
            replayDataFromJson({{QStringLiteral("schema"), QStringLiteral("drone_agricole.replay.v99")}})),
        ContractError);
  }
};

QTEST_MAIN(TestTelemetryBridge)
#include "TestTelemetryBridge.moc"
