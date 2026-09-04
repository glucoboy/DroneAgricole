#include "drone_agricole/station/StationArchitecture.hpp"

#include <QtTest>

#include <QSet>

using namespace drone_agricole::station;

class TestStationArchitecture final : public QObject {
  Q_OBJECT

 private slots:
  void coversTheCompleteStationWorkflow() {
    const auto modules = StationArchitecture::modules();
    QCOMPARE(modules.size(), 10);
    QSet<QString> identifiers;
    for (const auto& module : modules) {
      QVERIFY(!module.id.isEmpty());
      QVERIFY(!module.label.isEmpty());
      QVERIFY(!module.responsibility.isEmpty());
      QVERIFY(!identifiers.contains(module.id));
      identifiers.insert(module.id);
    }
    QCOMPARE(StationArchitecture::nominalWorkflowModuleIds(),
             QStringList({QStringLiteral("survey-reception"), QStringLiteral("survey-compilation"),
                          QStringLiteral("map-construction"), QStringLiteral("map-editing"),
                          QStringLiteral("map-approval"), QStringLiteral("treatment-mission-preparation"),
                          QStringLiteral("mission-simulation"), QStringLiteral("operational-transfer"),
                          QStringLiteral("treatment-return-reception"),
                          QStringLiteral("treatment-report-compilation")}));
  }

  void preservesTheSafetyBoundary() {
    for (const auto& module : StationArchitecture::modules()) {
      QVERIFY2(!module.controlsFlightCriticalFunctions, qPrintable(module.id));
    }
  }

  void exposesApprovalAndTransferGates() {
    const auto approval = StationArchitecture::module(QStringLiteral("map-approval"));
    QVERIFY(approval.has_value());
    QVERIFY(approval->requiresOperatorApproval);
    QVERIFY(approval->consumes.contains(PackageKind::VineyardMap));
    QVERIFY(approval->produces.contains(PackageKind::VineyardMap));

    const auto transfer = StationArchitecture::module(QStringLiteral("operational-transfer"));
    QVERIFY(transfer.has_value());
    QVERIFY(transfer->requiresOperatorApproval);
    QVERIFY(transfer->consumes.contains(PackageKind::VineyardMap));
    QVERIFY(transfer->consumes.contains(PackageKind::TreatmentMission));

    const auto simulation = StationArchitecture::module(QStringLiteral("mission-simulation"));
    QVERIFY(simulation.has_value());
    QCOMPARE(simulation->maturity, ModuleMaturity::OperationalPreliminary);
  }

  void keepsPackageNamesStable() {
    QCOMPARE(StationArchitecture::packageKindId(PackageKind::SurveyMission), QStringLiteral("SurveyMissionPackage"));
    QCOMPARE(StationArchitecture::packageKindId(PackageKind::SurveyRun), QStringLiteral("SurveyRunPackage"));
    QCOMPARE(StationArchitecture::packageKindId(PackageKind::VineyardMap), QStringLiteral("VineyardMapPackage"));
    QCOMPARE(StationArchitecture::packageKindId(PackageKind::TreatmentMission),
             QStringLiteral("TreatmentMissionPackage"));
    QCOMPARE(StationArchitecture::packageKindId(PackageKind::MissionReport), QStringLiteral("MissionReportPackage"));
  }
};

QTEST_APPLESS_MAIN(TestStationArchitecture)
#include "TestStationArchitecture.moc"
