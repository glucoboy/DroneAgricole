#include "drone_agricole/core/RunnerRegistry.hpp"

#include <QtTest>

#include <QDir>
#include <QFile>

#include <yaml-cpp/yaml.h>

using namespace drone_agricole::core;

class TestRunnerRegistry final : public QObject {
  Q_OBJECT

 private slots:
  void exposesOnlyApprovedRunners() {
    ContractRegistry contracts(QStringLiteral(DRONE_AGRICOLE_TEST_WORKSPACE));
    contracts.load();
    RunnerRegistry runners(contracts);
    QCOMPARE(runners.approvedRunnerIds(),
             QStringList({QStringLiteral("fast_lio2"), QStringLiteral("point_lio"), QStringLiteral("lio_sam"),
                          QStringLiteral("px4_square"), QStringLiteral("px4_failsafe")}));
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
};

QTEST_GUILESS_MAIN(TestRunnerRegistry)
#include "TestRunnerRegistry.moc"
