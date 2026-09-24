#include "drone_agricole/core/RunnerRegistry.hpp"

#include <QtTest>

#include <QDir>
#include <QFile>
#include <QTemporaryDir>
#include "drone_agricole/core/JsonUtils.hpp"

#include <yaml-cpp/yaml.h>

using namespace drone_agricole::core;

class TestRunnerRegistry final : public QObject {
  Q_OBJECT

 private slots:
  void registersAnExtensionWithoutChangingDispatcher() {
    QTemporaryDir workspace;
    QVERIFY(workspace.isValid());
    const QDir source(QStringLiteral(DRONE_AGRICOLE_TEST_WORKSPACE));
    const QDir target(workspace.path());
    QVERIFY(target.mkpath(QStringLiteral("configs/visualization/schemas")));
    QVERIFY(target.mkpath(QStringLiteral("configs/visualization/simulations")));
    const QDir schemas(source.filePath(QStringLiteral("configs/visualization/schemas")));
    for (const auto& file : schemas.entryList({QStringLiteral("*.json")}, QDir::Files))
      QVERIFY(QFile::copy(schemas.filePath(file), target.filePath(QStringLiteral("configs/visualization/schemas/") + file)));
    auto definition = readJsonObject(source.filePath(QStringLiteral("configs/visualization/simulations/px4_offboard.json")));
    definition.insert(QStringLiteral("simulation_id"), QStringLiteral("extension"));
    definition.insert(QStringLiteral("domain"), QStringLiteral("new_domain"));
    auto variant = definition.value(QStringLiteral("variants")).toArray().first().toObject();
    variant.insert(QStringLiteral("runner_id"), QStringLiteral("extension_runner"));
    definition.insert(QStringLiteral("variants"), QJsonArray{variant});
    writeJsonObjectAtomically(target.filePath(QStringLiteral("configs/visualization/simulations/extension.json")), definition);
    ContractRegistry contracts(workspace.path());
    contracts.load();
    RunnerRegistry runners(contracts);
    bool invoked = false;
    runners.registerRunner(QStringLiteral("extension_runner"), [&invoked](const RunnerContext& context) {
      invoked = true;
      PreparedRun run;
      run.runId = context.runId;
      run.runnerId = context.variant.runnerId;
      return run;
    });
    const auto request = contracts.resolveRequest(QStringLiteral("extension"), variant.value(QStringLiteral("variant_id")).toString(), {}, {}, {}, {});
    const auto run = runners.prepare(request, QStringLiteral("extension-test"));
    QVERIFY(invoked);
    QCOMPARE(run.runId, QStringLiteral("extension-test"));
    QVERIFY_EXCEPTION_THROWN(runners.registerRunner(QStringLiteral("extension_runner"), {}), ContractError);
  }
  void exposesOnlyApprovedRunners() {
    ContractRegistry contracts(QStringLiteral(DRONE_AGRICOLE_TEST_WORKSPACE));
    contracts.load();
    RunnerRegistry runners(contracts);
    QCOMPARE(runners.approvedRunnerIds(),
             QStringList({QStringLiteral("fast_lio2"), QStringLiteral("point_lio"), QStringLiteral("lio_sam"),
                          QStringLiteral("px4_square"), QStringLiteral("px4_failsafe"),
                          QStringLiteral("vineyard_height_density"), QStringLiteral("friulbot_capture_rows")}));
  }

  void preparesLockedPx4Client() {
    ContractRegistry contracts(QStringLiteral(DRONE_AGRICOLE_TEST_WORKSPACE));
    contracts.load();
    RunnerRegistry runners(contracts);
    const auto request = contracts.resolveRequest(QStringLiteral("px4_offboard"), QStringLiteral("failsafe"), QString{},
                                                  QString{}, QString{}, QJsonObject{});
    const auto prepared = runners.prepare(request, QStringLiteral("test1234"),
                                          QDateTime::fromString(QStringLiteral("2026-08-30T10:00:00Z"), Qt::ISODate));
    QVERIFY(prepared.program.endsWith(QStringLiteral("drone-agricole-px4-client")
#ifdef Q_OS_WIN
                                          + QStringLiteral(".exe")
#endif
                                      ));
    QCOMPARE(prepared.runnerId, QStringLiteral("px4_failsafe"));
    QVERIFY(!prepared.arguments.contains(QStringLiteral("bash")));
    QVERIFY(!prepared.arguments.contains(QStringLiteral("python3")));
    QVERIFY(prepared.arguments.contains(QStringLiteral("http://127.0.0.1:8091")));
    QVERIFY(prepared.arguments.contains(QStringLiteral("--ensure-docker")));
    QCOMPARE(prepared.stopProgram, prepared.program);
    QVERIFY(prepared.stopArguments.contains(QStringLiteral("--stop-only")));
  }

  void preparesConfigurationsForAllLioRunners() {
    ContractRegistry contracts(QStringLiteral(DRONE_AGRICOLE_TEST_WORKSPACE));
    contracts.load();
    RunnerRegistry runners(contracts);
    struct LioCase {
      QString variantId;
      QString yamlSection;
      QString yamlParameter;
      double expectedValue;
    };
    const QList<LioCase> cases{
        {QStringLiteral("fast_lio2"), QString{}, QStringLiteral("filter_size_surf"), 0.5},
        {QStringLiteral("point_lio"), QStringLiteral("mapping"), QStringLiteral("plane_thr"), 0.1},
        {QStringLiteral("lio_sam"), QString{}, QStringLiteral("odometrySurfLeafSize"), 0.4},
    };
    for (const auto& testCase : cases) {
      const auto request = contracts.resolveRequest(
          QStringLiteral("lio_benchmark"), testCase.variantId,
          QStringLiteral("botanicgarden_velodyne_xsens"), QStringLiteral("botanicgarden"),
          QStringLiteral("1006-03-smoke"), QJsonObject{});
      const auto runId = QStringLiteral("test-%1").arg(testCase.variantId);
      const auto prepared = runners.prepare(
          request, runId, QDateTime::fromString(QStringLiteral("2026-09-02T08:00:00Z"), Qt::ISODate));
      QVERIFY2(!QFileInfo::exists(prepared.resultDirectory),
               qPrintable(QStringLiteral("prepare() ne doit pas réserver le dossier final : %1")
                              .arg(prepared.resultDirectory)));
      const auto configArgument = prepared.arguments.indexOf(QStringLiteral("--config"));
      QVERIFY2(configArgument >= 0 && configArgument + 1 < prepared.arguments.size(), qPrintable(testCase.variantId));
      const auto relativeConfig = prepared.arguments.at(configArgument + 1);
      const auto absoluteConfig = QDir(QStringLiteral(DRONE_AGRICOLE_TEST_WORKSPACE)).filePath(relativeConfig);
      QVERIFY2(QFile::exists(absoluteConfig), qPrintable(absoluteConfig));
      const auto document = YAML::LoadFile(absoluteConfig.toStdString());
      const auto parameters = document["/**"]["ros__parameters"];
      QVERIFY2(parameters.IsMap(), qPrintable(testCase.variantId));
      const auto value = testCase.yamlSection.isEmpty()
                             ? parameters[testCase.yamlParameter.toStdString()]
                             : parameters[testCase.yamlSection.toStdString()][testCase.yamlParameter.toStdString()];
      QVERIFY2(value.IsDefined(), qPrintable(testCase.yamlParameter));
      QCOMPARE(value.as<double>(), testCase.expectedValue);
      if (testCase.variantId != QStringLiteral("lio_sam")) {
        const auto detectionRange = parameters["mapping"]["det_range"];
        QCOMPARE(detectionRange.as<double>(), 100.0);
        QCOMPARE(QString::fromStdString(detectionRange.Tag()), QStringLiteral("tag:yaml.org,2002:float"));
        const auto blindRange = parameters["preprocess"]["blind"];
        QCOMPARE(blindRange.as<double>(), 1.0);
        QCOMPARE(QString::fromStdString(blindRange.Tag()), QStringLiteral("tag:yaml.org,2002:float"));
        QCOMPARE(parameters["point_filter_num"].as<int>(), 4);
      }
      QVERIFY(QFile::remove(absoluteConfig));
    }
  }

  void preparesVineyardMappingRunner() {
    ContractRegistry contracts(QStringLiteral(DRONE_AGRICOLE_TEST_WORKSPACE));
    contracts.load();
    RunnerRegistry runners(contracts);
    const auto request = contracts.resolveRequest(
        QStringLiteral("vineyard_mapping"), QStringLiteral("height_density_v1"), QString{},
        QStringLiteral("escayard"), QStringLiteral("b7-green"), QJsonObject{});
    const auto prepared = runners.prepare(
        request, QStringLiteral("maptest1"),
        QDateTime::fromString(QStringLiteral("2026-09-06T08:00:00Z"), Qt::ISODate));
    QCOMPARE(prepared.runnerId, QStringLiteral("vineyard_height_density"));
    QVERIFY(prepared.program.endsWith(QStringLiteral("drone-agricole-tools")
#ifdef Q_OS_WIN
                                          + QStringLiteral(".exe")
#endif
                                      ));
    QVERIFY(prepared.arguments.contains(QStringLiteral("vineyard-map-run")));
    QVERIFY(prepared.arguments.contains(QStringLiteral("--point-cloud")));
    QVERIFY(prepared.arguments.contains(QStringLiteral("--reference-trunks")));
    QVERIFY(!prepared.arguments.contains(QStringLiteral("--trunks")));
    QVERIFY(!prepared.arguments.contains(QStringLiteral("docker")));
    QVERIFY(!QFileInfo::exists(prepared.resultDirectory));
    const auto requestArgument = prepared.arguments.indexOf(QStringLiteral("--request"));
    QVERIFY(requestArgument >= 0 && requestArgument + 1 < prepared.arguments.size());
    const auto requestPath = QDir(QStringLiteral(DRONE_AGRICOLE_TEST_WORKSPACE))
                                 .filePath(prepared.arguments.at(requestArgument + 1));
    QVERIFY(QFile::remove(requestPath));
  }

  void preparesFriulBotCaptureRunnerWithStrictTopicAdapter() {
    ContractRegistry contracts(QStringLiteral(DRONE_AGRICOLE_TEST_WORKSPACE));
    contracts.load();
    RunnerRegistry runners(contracts);
    const auto request = contracts.resolveRequest(
        QStringLiteral("vineyard_capture_mapping"), QStringLiteral("trigger_rows_v1"), QString{},
        QStringLiteral("friulbot"), QStringLiteral("test2-2024-07-22-raw"), QJsonObject{});
    const auto prepared = runners.prepare(
        request, QStringLiteral("friulmap1"),
        QDateTime::fromString(QStringLiteral("2026-09-07T08:00:00Z"), Qt::ISODate));
    QCOMPARE(prepared.runnerId, QStringLiteral("friulbot_capture_rows"));
    QVERIFY(prepared.arguments.contains(QStringLiteral("friulbot-map-run")));
    QVERIFY(prepared.arguments.contains(QStringLiteral("--bag")));
    QVERIFY(prepared.arguments.contains(QStringLiteral("--images")));
    QVERIFY(prepared.arguments.contains(QStringLiteral("--calibration")));
    QVERIFY(!prepared.arguments.contains(QStringLiteral("--reference")));
    QVERIFY(!prepared.arguments.contains(QStringLiteral("--rtk")));
    const auto requestArgument = prepared.arguments.indexOf(QStringLiteral("--request"));
    QVERIFY(requestArgument >= 0 && requestArgument + 1 < prepared.arguments.size());
    const auto requestPath = QDir(QStringLiteral(DRONE_AGRICOLE_TEST_WORKSPACE))
                                 .filePath(prepared.arguments.at(requestArgument + 1));
    QVERIFY(QFile::remove(requestPath));
  }
};

QTEST_GUILESS_MAIN(TestRunnerRegistry)
#include "TestRunnerRegistry.moc"
