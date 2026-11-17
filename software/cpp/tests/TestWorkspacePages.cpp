#include "drone_agricole/ui/MissionsPage.hpp"
#include "drone_agricole/ui/DataPage.hpp"
#include "drone_agricole/ui/SystemPage.hpp"
#include "drone_agricole/adapters/JsonWorkspaceStore.hpp"

#include <QComboBox>
#include <QFile>
#include <QLabel>
#include <QLineEdit>
#include <QPlainTextEdit>
#include <QPushButton>
#include <QTableWidget>
#include <QTemporaryDir>
#include <QtTest>
#include <stdexcept>

using namespace drone_agricole;
namespace {
struct Preparation final : application::IRunPreparation { domain::PreparedRun prepare(const QJsonObject&) override { return {}; } };
struct Finalizer final : application::IResultFinalizer { void finalize(const domain::PreparedRun&) override {} };
struct Backend final : application::IRunBackend {
  void start(const domain::PreparedRun&) override { ++starts; }
  void cancel() override {}
  int starts{0};
};
struct Hardware final : application::IHardwareInventory {
  domain::HardwareInventory load() const override { return inventory; }
  QString sourcePath() const override { return QStringLiteral("fixture-bom.json"); }
  domain::HardwareInventory inventory;
};
class FakeStation final : public application::IStationServices {
 public:
  explicit FakeStation(const QString& path)
      : root(path), store(path), workspaceService(store, hardware), runService(preparation, backend, finalizer) {
    domain::HardwareItem item; item.id = QStringLiteral("LIDAR"); item.designation = QStringLiteral("Capteur candidat");
    item.status = QStringLiteral("À valider"); item.physicalAvailability = QStringLiteral("Non inventoriée");
    item.subsystem = QStringLiteral("Acquisition"); item.reservations = {QStringLiteral("Interface et datation à mesurer")};
    hardware.inventory.items.append(item); hardware.inventory.qualification = QStringLiteral("À valider");
    core::DatasetSequence first; first.datasetId = QStringLiteral("alpha"); first.datasetLabel = QStringLiteral("Vignoble Alpha");
    first.sequenceId = QStringLiteral("sequence-a"); first.sequenceLabel = QStringLiteral("Première séquence");
    first.status = QStringLiteral("declared"); first.capabilities.insert(QStringLiteral("lidar"));
    core::DatasetSequence second = first; second.datasetId = QStringLiteral("beta"); second.datasetLabel = QStringLiteral("Beta"); second.sequenceId = QStringLiteral("sequence-b");
    sequences = {first, second};
    core::ResultSummary result; result.resultId = QStringLiteral("archive-alpha"); result.runId = QStringLiteral("run-alpha");
    result.datasetId = QStringLiteral("alpha"); result.sequenceId = first.sequenceId;
    result.domain = QStringLiteral("localization"); result.state = QStringLiteral("completed");
    result.sourceKind = QStringLiteral("fixture"); results.append(result);
  }
  application::RunService& execution() override { return runService; }
  application::GazeboExportService& gazeboExport() override { throw std::logic_error("Gazebo not used by this fixture"); }
  application::WorkspaceService& workspaceData() override { return workspaceService; }
  QString workspace() const override { return root; }
  QList<core::SimulationDefinition> simulations() const override { return {}; }
  QList<core::DatasetSequence> datasetSequences() const override { return sequences; }
  const core::SimulationDefinition& simulation(const QString&) const override { throw std::runtime_error("No simulation"); }
  const core::VariantDefinition& variant(const QString&, const QString&) const override { throw std::runtime_error("No variant"); }
  QList<core::DatasetSequence> compatibleSequences(const QString&, const QString&) const override { return {}; }
  QJsonObject resolveRequest(const QString&, const QString&, const QString&, const QString&, const QString&, const QJsonObject&) const override { return {}; }
  qsizetype schemaDocumentCount() const override { return 0; }
  void refresh() override {}
  QList<core::ResultSummary> search(const core::SearchFilters& filters = {}) const override {
    QList<core::ResultSummary> found;
    for (const auto& result : results) if (filters.domain.isEmpty() || result.domain == filters.domain) found.append(result);
    return found;
  }
  core::ResultDetail detail(const QString& id) const override {
    for (const auto& result : results) if (result.resultId == id) { core::ResultDetail detail; detail.summary = result; return detail; }
    throw std::runtime_error("Unknown result");
  }
  core::ReplayData replay(const QString&) override { return {}; }
  qsizetype totalCount() const override { return results.size(); }
  qsizetype invalidResultCount() const override { return 0; }
  QString resultsRoot() const override { return root; }
  core::ComparisonResult compare(const QStringList&) override { return {}; }
  void exportReport(const QString& path, const QString& report) override {
    QFile file(path); if (!file.open(QIODevice::WriteOnly)) throw std::runtime_error("Export failed"); file.write(report.toUtf8());
  }
  void resetTelemetry() override {}
  core::LiveTelemetrySnapshot snapshot() override { return {}; }
  QString root;
  adapters::JsonWorkspaceStore store;
  Hardware hardware;
  application::WorkspaceService workspaceService;
  Preparation preparation; Backend backend; Finalizer finalizer;
  application::RunService runService;
  QList<core::DatasetSequence> sequences;
  QList<core::ResultSummary> results;
};
}

class TestWorkspacePages final : public QObject {
  Q_OBJECT
 private slots:
  void missionDraftPersistsWithoutStartingFlightOrInventingPerformance() {
    QTemporaryDir directory; QVERIFY(directory.isValid()); FakeStation services(directory.path());
    ui::MissionsPage page(services);
    auto* save = page.findChild<QPushButton*>(QStringLiteral("saveMissionButton")); save->click();
    QVERIFY(services.workspaceData().missions().isEmpty());
    page.findChild<QLineEdit*>(QStringLiteral("missionNameEdit"))->setText(QStringLiteral("Préparation Cornas"));
    page.findChild<QLineEdit*>(QStringLiteral("missionParcelEdit"))->setText(QStringLiteral("Zone nord"));
    auto* dataset = page.findChild<QComboBox*>(QStringLiteral("missionDatasetCombo")); dataset->setCurrentIndex(dataset->findData(QStringLiteral("alpha")));
    auto* sequence = page.findChild<QComboBox*>(QStringLiteral("missionSequenceCombo")); sequence->setCurrentIndex(sequence->findData(QStringLiteral("sequence-a")));
    save->click();
    QCOMPARE(services.workspaceData().missions().size(), 1);
    const auto saved = services.workspaceData().missions().front();
    QCOMPARE(saved.datasetId, QStringLiteral("alpha")); QCOMPARE(saved.sequenceId, QStringLiteral("sequence-a"));
    QVERIFY(!saved.altitudeMeters); QVERIFY(!saved.speedMetersPerSecond); QCOMPARE(services.backend.starts, 0);
    QVERIFY(!services.execution().active());
    FakeStation reopened(directory.path()); ui::MissionsPage restored(reopened);
    auto* table = restored.findChild<QTableWidget*>(QStringLiteral("missionsTable")); QCOMPARE(table->rowCount(), 1); table->selectRow(0);
    QCOMPARE(restored.findChild<QLineEdit*>(QStringLiteral("missionNameEdit"))->text(), QStringLiteral("Préparation Cornas"));
    QCOMPARE(restored.findChild<QLineEdit*>(QStringLiteral("missionParcelEdit"))->text(), QStringLiteral("Zone nord"));
    restored.findChild<QLineEdit*>(QStringLiteral("missionNameEdit"))->setText(QStringLiteral("Préparation mise à jour"));
    restored.findChild<QPushButton*>(QStringLiteral("saveMissionButton"))->click();
    QCOMPARE(reopened.workspaceData().missions().size(), 1); QCOMPARE(reopened.workspaceData().mission(saved.id).name, QStringLiteral("Préparation mise à jour"));
    QSignalSpy route(&restored, &ui::MissionsPage::routeRequested);
    restored.findChild<QPushButton*>(QStringLiteral("missionBenchButton"))->click();
    QCOMPARE(route.count(), 1); QCOMPARE(route.first().first().toString(), QStringLiteral("tests"));
    QVERIFY(route.first().at(1).toString().contains(QStringLiteral("alpha"))); QCOMPARE(reopened.backend.starts, 0);
  }
  void bothThemesPersistAndPreserveFavorites() {
    QTemporaryDir directory; QVERIFY(directory.isValid()); FakeStation services(directory.path());
    services.workspaceData().setFavoriteResult(QStringLiteral("favorite-archive"), true);
    ui::SystemPage page(services); auto* themes = page.findChild<QComboBox*>(QStringLiteral("themeCombo"));
    QCOMPARE(themes->count(), 2); QSignalSpy changed(&page, &ui::SystemPage::themeChanged);
    themes->setCurrentIndex(themes->findData(QStringLiteral("premium")));
    page.findChild<QPushButton*>(QStringLiteral("saveSettingsButton"))->click(); QCOMPARE(changed.count(), 1);
    FakeStation reopened(directory.path()); QCOMPARE(reopened.workspaceData().preferences().themeId, QStringLiteral("premium"));
    QVERIFY(reopened.workspaceData().isFavoriteResult(QStringLiteral("favorite-archive")));
    themes->setCurrentIndex(themes->findData(QStringLiteral("professional")));
    page.findChild<QPushButton*>(QStringLiteral("saveSettingsButton"))->click(); QCOMPARE(changed.count(), 2);
    QCOMPARE(reopened.workspaceData().preferences().themeId, QStringLiteral("professional"));
  }
  void inventoryAndTelemetryKeepUnknownStatesVisible() {
    QTemporaryDir directory; QVERIFY(directory.isValid()); FakeStation services(directory.path());
    ui::SystemPage page(services); page.setSection(QStringLiteral("hardware"));
    auto* table = page.findChild<QTableWidget*>(QStringLiteral("hardwareTable")); QCOMPARE(table->rowCount(), 1);
    QVERIFY(table->item(0, 2)->text().contains(QStringLiteral("Inconnue"))); table->selectRow(0);
    const auto detail = page.findChild<QPlainTextEdit*>(QStringLiteral("hardwareDetailEdit"))->toPlainText();
    QVERIFY(detail.contains(QStringLiteral("Non inventoriée"))); QVERIFY(detail.contains(QStringLiteral("À valider")));
    QVERIFY(detail.contains(QStringLiteral("Masse unitaire : Inconnue"))); QVERIFY(!detail.contains(QStringLiteral("Connecté")));
    page.findChild<QLineEdit*>(QStringLiteral("hardwareSearchEdit"))->setText(QStringLiteral("absent-component"));
    QCOMPARE(table->rowCount(), 0); QVERIFY(page.findChild<QPlainTextEdit*>(QStringLiteral("hardwareDetailEdit"))->toPlainText().isEmpty());
    page.findChild<QLineEdit*>(QStringLiteral("hardwareSearchEdit"))->clear();
    auto* subsystem = page.findChild<QComboBox*>(QStringLiteral("hardwareSubsystemCombo"));
    subsystem->setCurrentIndex(subsystem->findData(QStringLiteral("Acquisition")));
    services.hardware.inventory.items.front().subsystem = QStringLiteral("Énergie"); page.refresh();
    QCOMPARE(subsystem->currentData().toString(), QString{}); QCOMPARE(table->rowCount(), 1);
    page.setSection(QStringLiteral("diagnostics"));
    auto* diagnostics = page.findChild<QTableWidget*>(QStringLiteral("diagnosticsTable"));
    bool unavailableTelemetry = false;
    for (int row = 0; row < diagnostics->rowCount(); ++row) if (diagnostics->item(row, 0)->text() == QStringLiteral("Pont de télémétrie")) unavailableTelemetry = diagnostics->item(row, 1)->text() == QStringLiteral("Aucune donnée disponible");
    QVERIFY(unavailableTelemetry);
  }
  void dataSearchClearsDetailsAndPreservesReferenceRouting() {
    QTemporaryDir directory; QVERIFY(directory.isValid()); FakeStation services(directory.path()); ui::DataPage page(services);
    auto* catalogue = page.findChild<QTableWidget*>(QStringLiteral("catalogueTable")); QCOMPARE(catalogue->rowCount(), 2);
    auto* search = page.findChild<QLineEdit*>(QStringLiteral("catalogueSearchEdit")); search->setText(QStringLiteral("alpha"));
    QCOMPARE(catalogue->rowCount(), 1); catalogue->selectRow(0);
    QVERIFY(page.findChild<QPlainTextEdit*>(QStringLiteral("sequenceDetailEdit"))->toPlainText().contains(QStringLiteral("lidar")));
    QSignalSpy route(&page, &ui::DataPage::routeRequested); page.findChild<QPushButton*>(QStringLiteral("sequenceBenchButton"))->click();
    QCOMPARE(route.count(), 1); QCOMPARE(route.first().first().toString(), QStringLiteral("tests"));
    search->setText(QStringLiteral("absent-dataset")); QCOMPARE(catalogue->rowCount(), 0);
    QVERIFY(!page.findChild<QPushButton*>(QStringLiteral("sequenceBenchButton"))->isEnabled());
    QVERIFY(page.findChild<QPlainTextEdit*>(QStringLiteral("sequenceDetailEdit"))->toPlainText().isEmpty());
    page.setSection(QStringLiteral("acquisitions")); auto* archives = page.findChild<QTableWidget*>(QStringLiteral("acquisitionsTable"));
    QCOMPARE(archives->rowCount(), 1); archives->selectRow(0);
    QVERIFY(page.findChild<QPushButton*>(QStringLiteral("openAcquisitionButton"))->isEnabled());
    route.clear(); page.findChild<QPushButton*>(QStringLiteral("openAcquisitionButton"))->click();
    QCOMPARE(route.count(), 1); QCOMPARE(route.first().first().toString(), QStringLiteral("results"));
    QCOMPARE(route.first().at(1).toString(), QStringLiteral("archive-alpha"));
    page.findChild<QLineEdit*>(QStringLiteral("acquisitionSearchEdit"))->setText(QStringLiteral("missing-archive"));
    QCOMPARE(archives->rowCount(), 0); QVERIFY(!page.findChild<QPushButton*>(QStringLiteral("openAcquisitionButton"))->isEnabled());
    QVERIFY(page.findChild<QPlainTextEdit*>(QStringLiteral("acquisitionDetailEdit"))->toPlainText().isEmpty());
    services.sequences.clear(); services.results.clear(); page.refresh(); QCOMPARE(catalogue->rowCount(), 0); QCOMPARE(archives->rowCount(), 0);
    page.setSection(QStringLiteral("import-export")); QVERIFY(!page.findChild<QPushButton*>(QStringLiteral("exportMissionButton"))->isEnabled());
  }
};
QTEST_MAIN(TestWorkspacePages)
#include "TestWorkspacePages.moc"
