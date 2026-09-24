#include "drone_agricole/composition/StationComposition.hpp"
#include <QListWidget>
#include <QStackedWidget>
#include "drone_agricole/core/JsonUtils.hpp"
#include "drone_agricole/core/VineyardMap.hpp"
#include "drone_agricole/ui/MainWindow.hpp"
#include "drone_agricole/ui/TrajectoryView.hpp"
#include "drone_agricole/ui/ResultViewPage.hpp"
#include <QDoubleSpinBox>
#include <QCheckBox>

#include <QComboBox>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QPlainTextEdit>
#include <QPushButton>
#include <QRegularExpression>
#include <QtTest>

#include <utility>

using namespace drone_agricole::ui;

namespace {

class MappingRunCleanup final {
 public:
  explicit MappingRunCleanup(QString workspace) : workspace_(std::move(workspace)) {}

  void addRunId(QString runId) { runIds_.append(std::move(runId)); }

  ~MappingRunCleanup() {
    QDir resultRoot(QDir(workspace_).filePath(QStringLiteral("results/simulation/vineyard_mapping")));
    for (const auto& runId : runIds_) {
      QFile::remove(QDir(workspace_).filePath(QStringLiteral(".runtime/dashboard/%1_map_request.json").arg(runId)));
      const auto suffix = QStringLiteral("_%1").arg(runId);
      for (const auto& directory : resultRoot.entryList(QDir::Dirs | QDir::NoDotAndDotDot)) {
        if (directory.endsWith(suffix)) {
          QDir(resultRoot.filePath(directory)).removeRecursively();
        }
      }
    }
  }

 private:
  QString workspace_;
  QStringList runIds_;
};

}  // namespace

class TestDashboardMapping final : public QObject {
  Q_OBJECT

 private slots:
  void launchesEscaYardAndDisplaysMap() {
    const auto workspace = QStringLiteral(DRONE_AGRICOLE_TEST_WORKSPACE);
    MappingRunCleanup cleanup(workspace);
    const auto lasPath = QDir(workspace).filePath(
        QStringLiteral("datasets/public/escayard/B7/raw/20220714_FLEXIGROBOTS_B7_30M0G_MS_PRO_Green_densified_point_cloud.las"));
    if (!QFileInfo::exists(lasPath)) {
      QSKIP("Dataset EscaYard B7 absent : test d'intégration cartographique non exécuté.");
    }

    drone_agricole::composition::StationComposition services(workspace);
    MainWindow window(services);
    window.findChild<QListWidget*>(QStringLiteral("navigationList"))->setCurrentRow(2);
    window.resize(1440, 900);
    window.show();

    auto* simulations = window.findChild<QComboBox*>(QStringLiteral("simulationCombo"));
    auto* variants = window.findChild<QComboBox*>(QStringLiteral("variantCombo"));
    auto* datasets = window.findChild<QComboBox*>(QStringLiteral("datasetCombo"));
    auto* sequences = window.findChild<QComboBox*>(QStringLiteral("sequenceCombo"));
    auto* start = window.findChild<QPushButton*>(QStringLiteral("startButton"));
    auto* view = window.findChild<TrajectoryView*>(QStringLiteral("trajectoryView"));
    auto* logs = window.findChild<QPlainTextEdit*>(QStringLiteral("logsEdit"));
    QVERIFY(simulations != nullptr);
    QVERIFY(variants != nullptr);
    QVERIFY(datasets != nullptr);
    QVERIFY(sequences != nullptr);
    QVERIFY(start != nullptr);
    QVERIFY(view != nullptr);
    QVERIFY(logs != nullptr);

    // Régression historique par le service : EscaYard n'est plus proposé aux nouveaux essais.
    QCOMPARE(simulations->findData(QStringLiteral("vineyard_mapping")), -1);
    drone_agricole::core::ContractRegistry registry(workspace);
    registry.load();
    QVERIFY(services.execution().start(registry.resolveRequest(QStringLiteral("vineyard_mapping"),
        QStringLiteral("height_density_v1"), {}, QStringLiteral("escayard"), QStringLiteral("b7-green"), {})));
    const auto runIdMatch = QRegularExpression(QStringLiteral("--run-id\\s+([a-z0-9_-]+)"))
                                .match(logs->toPlainText());
    QVERIFY(runIdMatch.hasMatch());
    cleanup.addRunId(runIdMatch.captured(1));
    QVERIFY(!start->isEnabled());
    auto* navigation = window.findChild<QListWidget*>(QStringLiteral("navigationList"));
    auto* pages = window.findChild<QStackedWidget*>(QStringLiteral("pageStack"));
    navigation->setCurrentRow(1);
    QCOMPARE(pages->currentWidget()->objectName(), QStringLiteral("acquisitionsPage"));
    QVERIFY(services.execution().active());
    QTRY_VERIFY_WITH_TIMEOUT(start->isEnabled(), 30000);
    QCOMPARE(pages->currentWidget()->objectName(), QStringLiteral("acquisitionsPage"));
    QCOMPARE(services.execution().state(), drone_agricole::domain::RunState::Completed);
    navigation->setCurrentRow(2);
    QTRY_VERIFY_WITH_TIMEOUT(view->pointCloudSize() > 1000, 10000);
    QCOMPARE(view->referencePointCount(), 138);
    QVERIFY(logs->toPlainText().contains(QStringLiteral("Résultat affiché automatiquement dans la carte 3D.")));
    QVERIFY(logs->toPlainText().contains(QStringLiteral("mapping_safe")));
    QDir resultRoot(QDir(workspace).filePath(QStringLiteral("results/simulation/vineyard_mapping")));
    const auto resultDirectories = resultRoot.entryList(
        QStringList{QStringLiteral("*_%1").arg(runIdMatch.captured(1))}, QDir::Dirs | QDir::NoDotAndDotDot);
    QCOMPARE(resultDirectories.size(), 1);
    const auto predictionPath = resultRoot.filePath(
        QStringLiteral("%1/map_prediction.json").arg(resultDirectories.constFirst()));
    const auto prediction = drone_agricole::core::readJsonObject(predictionPath);
    QCOMPARE(prediction.value(QStringLiteral("schema")).toString(),
             QStringLiteral("drone_agricole.map_prediction.v1"));
    QVERIFY(!prediction.contains(QStringLiteral("reference_points")));
    const auto predictionMetadata = prediction.value(QStringLiteral("metadata")).toObject();
    QCOMPARE(predictionMetadata.value(QStringLiteral("roi_source")).toString(),
             QStringLiteral("point_cloud_header_bounds"));
    QVERIFY(!predictionMetadata.contains(QStringLiteral("reference_crs")));
    const auto evaluatedReplay = drone_agricole::core::readJsonObject(
        resultRoot.filePath(QStringLiteral("%1/map_replay.json").arg(resultDirectories.constFirst())));
    const auto evaluatedHash = evaluatedReplay.value(QStringLiteral("metadata"))
                                   .toObject()
                                   .value(QStringLiteral("prediction_content_sha256"))
                                   .toString();
    QVERIFY(!evaluatedHash.isEmpty());

    const auto noReferenceRunId = QStringLiteral("%1-no-reference").arg(runIdMatch.captured(1));
    cleanup.addRunId(noReferenceRunId);
    const auto noReferenceDirectory = resultRoot.filePath(QStringLiteral("isolation_%1").arg(noReferenceRunId));
    const auto requestPath = QDir(workspace).filePath(
        QStringLiteral(".runtime/dashboard/%1_map_request.json").arg(runIdMatch.captured(1)));
    const auto noReferenceResult = drone_agricole::core::runVineyardMapping(
        QJsonObject{{QStringLiteral("run-id"), noReferenceRunId},
                    {QStringLiteral("request"), requestPath},
                    {QStringLiteral("point-cloud"), lasPath},
                    {QStringLiteral("run-dir"), noReferenceDirectory}});
    QCOMPARE(noReferenceResult.value(QStringLiteral("prediction_content_sha256")).toString(), evaluatedHash);
    const auto noReferenceReplay = drone_agricole::core::readJsonObject(
        QDir(noReferenceDirectory).filePath(QStringLiteral("map_replay.json")));
    QVERIFY(noReferenceReplay.value(QStringLiteral("reference_points")).toArray().isEmpty());
    const auto screenshot = qEnvironmentVariable("DRONE_AGRICOLE_DASHBOARD_MAPPING_SCREENSHOT");
    if (!screenshot.isEmpty()) {
      QTest::qWait(250);
      QVERIFY(window.grab().save(screenshot, "PNG"));
    }
  }
  void launchesSingleMappingModuleWithCameraColors_data() {
    QTest::addColumn<bool>("reconstruction");
    QTest::newRow("capture") << false;
    QTest::newRow("surface") << true;
  }
  void launchesSingleMappingModuleWithCameraColors() {
    QFETCH(bool,reconstruction);
    const auto workspace = QStringLiteral(DRONE_AGRICOLE_TEST_WORKSPACE);
    if (!QFileInfo::exists(QDir(workspace).filePath(QStringLiteral(
        "datasets/public/friulbot/test2/2024-07-22/raw/2024-07-22-11-03-15.bag"))))
      QSKIP("Dataset FriulBot absent");
    drone_agricole::composition::StationComposition services(workspace);
    MainWindow window(services);
    window.resize(1440, 900);
    window.show();
    auto* navigation = window.findChild<QListWidget*>(QStringLiteral("navigationList"));
    navigation->setCurrentRow(2);
    auto* simulations = window.findChild<QComboBox*>(QStringLiteral("simulationCombo"));
    const auto index = simulations->findData(QStringLiteral("vineyard_capture_mapping"));
    QVERIFY(index >= 0);
    QCOMPARE(simulations->findData(QStringLiteral("vineyard_mapping")), -1);
    simulations->setCurrentIndex(index);
    if(reconstruction) {
      auto* variants=window.findChild<QComboBox*>(QStringLiteral("variantCombo"));
      const auto surfaceIndex=variants->findData(QStringLiteral("scan_surface_v1"));
      QVERIFY(surfaceIndex>=0);variants->setCurrentIndex(surfaceIndex);
      window.findChild<QDoubleSpinBox*>(QStringLiteral("parameter_assembly_duration_s"))->setValue(2.0);
    }
    QTest::mouseClick(window.findChild<QPushButton*>(QStringLiteral("startButton")), Qt::LeftButton);
    QVERIFY(services.execution().active());
    navigation->setCurrentRow(1);
    QTRY_VERIFY_WITH_TIMEOUT(!services.execution().active(), 180000);
    QCOMPARE(services.execution().state(), drone_agricole::domain::RunState::Completed);
    QCOMPARE(navigation->currentRow(), 1);
    navigation->setCurrentRow(2);
    auto* view = window.findChild<TrajectoryView*>(QStringLiteral("trajectoryView"));
    QVERIFY(view->pointCloudSize() > 1000);
    QVERIFY(view->cameraColorCount() > 100);
    QCOMPARE(view->cameraColorCount(), view->cameraProjectedPointCount());
    QCOMPARE(view->referencePointCount(), 0);
    const auto run = *services.execution().run();
    const auto replay = drone_agricole::core::readVineyardMapReplay(
        QDir(run.resultDirectory).filePath(QStringLiteral("map_replay.json")), run.runId);
    QVERIFY(!replay.mapPolylines.isEmpty());
    if(reconstruction) {
      QVERIFY(replay.surfaceTriangles.size()>1000);
      QCOMPARE(view->surfaceTriangleCount(),replay.surfaceTriangles.size());
      QCOMPARE(replay.surfaceColors.size(),replay.surfaceVertices.size());
      QVERIFY(!replay.reconstructionPartial);
      QCOMPARE(replay.mapPolylines.first().role,QStringLiteral("acquisition_trajectory"));
      QVERIFY(replay.mapPolylines.first().points.size()>=3);
      QVERIFY(QFileInfo(QDir(run.resultDirectory).filePath(QStringLiteral("surface.ply"))).size()>10000);
      const auto poses=drone_agricole::core::readJsonObject(QDir(run.resultDirectory).filePath(QStringLiteral("estimated_poses.json")));
      QVERIFY(poses.value(QStringLiteral("metadata")).toObject().value(QStringLiteral("excluded_topics")).toArray().contains(QStringLiteral("odom")));
      window.findChild<QCheckBox*>(QStringLiteral("surfaceCheckBox"))->setChecked(false);
      window.findChild<QCheckBox*>(QStringLiteral("surfaceCheckBox"))->setChecked(true);
      services.refresh();
      QString id;
      for(const auto& result:services.search())if(result.runId==run.runId)id=result.resultId;
      QVERIFY(!id.isEmpty());
      ResultViewPage archive(services);archive.setStyleSheet(window.styleSheet());
      archive.resize(1400,950);archive.openResult(id);archive.show();
      QCOMPARE(archive.findChild<TrajectoryView*>()->surfaceTriangleCount(),replay.surfaceTriangles.size());
      const auto surfaceScreenshot=qEnvironmentVariable("DRONE_AGRICOLE_SURFACE_SCREENSHOT");
      if(!surfaceScreenshot.isEmpty()){QTest::qWait(250);QVERIFY(archive.grab().save(surfaceScreenshot,"PNG"));}
    }
    QVERIFY(std::any_of(replay.mapPoints.begin(), replay.mapPoints.end(),
        [](const auto& p) { return p.z() < -0.5F; }));
    const auto screenshot = reconstruction?QString{}:qEnvironmentVariable("DRONE_AGRICOLE_RGB_SCREENSHOT");
    if (!screenshot.isEmpty()) {
      QTest::qWait(250);
      QVERIFY(window.grab().save(screenshot, "PNG"));
    }
    // Dossier créé par ce test seulement, identifié par le résultat du service.
    const auto root = QDir(workspace).filePath(QStringLiteral("results/simulation/vineyard_capture_mapping/"));
    QVERIFY(QDir::fromNativeSeparators(run.resultDirectory).startsWith(QDir::fromNativeSeparators(root)));
    QVERIFY(QDir(run.resultDirectory).removeRecursively());
    QFile::remove(QDir(workspace).filePath(QStringLiteral(".runtime/dashboard/%1_friulbot_map_request.json").arg(run.runId)));
  }
};

QTEST_MAIN(TestDashboardMapping)
#include "TestDashboardMapping.moc"
