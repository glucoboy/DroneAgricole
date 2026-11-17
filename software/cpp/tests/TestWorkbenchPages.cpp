#include "drone_agricole/ui/AnalysisPage.hpp"
#include "drone_agricole/ui/ComparisonPage.hpp"
#include "drone_agricole/ui/ResultsPage.hpp"
#include "drone_agricole/ui/TrajectoryView.hpp"
#include "drone_agricole/adapters/JsonWorkspaceStore.hpp"

#include <QCheckBox>
#include <QComboBox>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QLabel>
#include <QLineEdit>
#include <QPlainTextEdit>
#include <QPushButton>
#include <QTableWidget>
#include <QTabWidget>
#include <QTemporaryDir>
#include <QtTest>
#include <stdexcept>

using namespace drone_agricole;
namespace {
struct Preparation final : application::IRunPreparation {
  domain::PreparedRun prepare(const QJsonObject&) override { return {}; }
};
struct Finalizer final : application::IResultFinalizer {
  void finalize(const domain::PreparedRun&) override {}
};
struct Backend final : application::IRunBackend {
  void start(const domain::PreparedRun&) override {}
  void cancel() override {}
};
struct Hardware final : application::IHardwareInventory {
  domain::HardwareInventory load() const override { return {}; }
  QString sourcePath() const override { return {}; }
};

class FakeStation final : public application::IStationServices {
 public:
  explicit FakeStation(const QString& path)
      : root(path), store(path), workspaceService(store, hardware), runService(preparation, backend, finalizer) {
    for (int index = 0; index < 3; ++index) {
      core::ResultSummary result;
      result.resultId = QStringLiteral("archive-%1").arg(index);
      result.runId = QStringLiteral("run-%1").arg(index);
      result.variantId = index == 0 ? QStringLiteral("FAST_LIO") : QStringLiteral("Scan surface");
      result.domain = index == 0 ? QStringLiteral("localization") : QStringLiteral("mapping");
      result.datasetId = QStringLiteral("parcelle-test");
      result.state = QStringLiteral("completed"); result.metricsStatus = QStringLiteral("available");
      result.relativeDirectory = QStringLiteral("fixture/%1").arg(result.runId);
      result.createdAtUtc = QDateTime::fromString(QStringLiteral("2026-10-23T10:00:00Z"), Qt::ISODate);
      result.replayAvailable = index != 2;
      result.duplicateAvailable = true;
      results.append(result);
    }
  }
  application::RunService& execution() override { return runService; }
  application::GazeboExportService& gazeboExport() override { throw std::logic_error("Gazebo not used by this fixture"); }
  application::WorkspaceService& workspaceData() override { return workspaceService; }
  QString workspace() const override { return root; }
  QList<core::SimulationDefinition> simulations() const override { return {}; }
  QList<core::DatasetSequence> datasetSequences() const override { return {}; }
  const core::SimulationDefinition& simulation(const QString&) const override { throw std::runtime_error("No simulation"); }
  const core::VariantDefinition& variant(const QString&, const QString&) const override { throw std::runtime_error("No variant"); }
  QList<core::DatasetSequence> compatibleSequences(const QString&, const QString&) const override { return {}; }
  QJsonObject resolveRequest(const QString&, const QString&, const QString&, const QString&, const QString&, const QJsonObject&) const override { return {}; }
  qsizetype schemaDocumentCount() const override { return 0; }
  void refresh() override {}
  QList<core::ResultSummary> search(const core::SearchFilters& = {}) const override { return results; }
  core::ResultDetail detail(const QString& id) const override {
    for (const auto& result : results) if (result.resultId == id) {
      core::ResultDetail detail; detail.summary = result;
      detail.metrics = QJsonObject{{QStringLiteral("summary"), QJsonArray{QJsonObject{
          {QStringLiteral("label"), QStringLiteral("Écart mesuré")}, {QStringLiteral("value"), 0.125},
          {QStringLiteral("unit"), QStringLiteral("m")}, {QStringLiteral("status"), QStringLiteral("observed")}}}}};
      return detail;
    }
    throw std::runtime_error("Unknown result");
  }
  core::ReplayData replay(const QString& id) override {
    ++replayCalls;
    core::ReplayData replay; replay.resultId = id; replay.domain = detail(id).summary.domain;
    replay.mapPoints = {QVector3D(0, 0, 0), QVector3D(1, 0, 0), QVector3D(0, 1, 0)};
    replay.estimate = {QVector3D(0, 0, 0), QVector3D(1, 1, 0)};
    replay.surfaceVertices = replay.mapPoints; replay.surfaceTriangles = {std::array<int, 3>{0, 1, 2}};
    replay.notes = {QStringLiteral("Note issue de la fixture archivée")};
    return replay;
  }
  qsizetype totalCount() const override { return results.size(); }
  qsizetype invalidResultCount() const override { return 0; }
  QString resultsRoot() const override { return root; }
  core::ComparisonResult compare(const QStringList& ids) override {
    comparedIds = ids;
    QJsonArray runs;
    for (const auto& id : ids) runs.append(QJsonObject{{QStringLiteral("label"), id}});
    return {QJsonObject{{QStringLiteral("compatibility"), QJsonObject{{QStringLiteral("compatible"), true}}},
                        {QStringLiteral("runs"), runs}}, QStringLiteral("# Rapport de comparaison issu des fixtures")};
  }
  void exportReport(const QString& path, const QString& report) override {
    QFile file(path);
    if (!file.open(QIODevice::WriteOnly)) throw std::runtime_error("Cannot write fixture report");
    file.write(report.toUtf8());
  }
  void resetTelemetry() override {}
  core::LiveTelemetrySnapshot snapshot() override { return {}; }

  QString root;
  adapters::JsonWorkspaceStore store;
  Hardware hardware;
  application::WorkspaceService workspaceService;
  Preparation preparation; Backend backend; Finalizer finalizer;
  application::RunService runService;
  QList<core::ResultSummary> results;
  QStringList comparedIds;
  int replayCalls{0};
};
}  // namespace

class TestWorkbenchPages final : public QObject {
  Q_OBJECT
 private slots:
  void unreadableWorkspaceKeepsArchivesSearchable() {
    QTemporaryDir directory; QVERIFY(directory.isValid());
    FakeStation services(directory.path());
    QVERIFY(QDir().mkpath(QFileInfo(services.store.path()).absolutePath()));
    QFile corrupt(services.store.path()); QVERIFY(corrupt.open(QIODevice::WriteOnly));
    corrupt.write("{broken"); corrupt.close();
    ui::ResultsPage page(services);
    auto* table = page.findChild<QTableWidget*>(QStringLiteral("historyTable"));
    QCOMPARE(table->rowCount(), 3);
    QVERIFY(!page.findChild<QCheckBox*>(QStringLiteral("favoritesOnlyCheck"))->isEnabled());
    page.findChild<QLineEdit*>(QStringLiteral("searchResultsEdit"))->setText(QStringLiteral("FAST_LIO"));
    QCOMPARE(table->rowCount(), 1);
    page.selectResult(QStringLiteral("archive-0"));
    QVERIFY(!page.findChild<QPushButton*>(QStringLiteral("favoriteButton"))->isEnabled());
    QVERIFY(page.findChild<QPushButton*>(QStringLiteral("analyzeButton"))->isEnabled());
    QVERIFY(page.findChild<QLabel*>(QStringLiteral("historyDescriptionLabel"))->text().contains(QStringLiteral("Favoris indisponibles")));
  }
  void searchesAndPersistsFavoritesWithoutDatasets() {
    QTemporaryDir directory; QVERIFY(directory.isValid());
    FakeStation services(directory.path());
    ui::ResultsPage page(services);
    auto* table = page.findChild<QTableWidget*>(QStringLiteral("historyTable"));
    auto* search = page.findChild<QLineEdit*>(QStringLiteral("searchResultsEdit"));
    auto* favorites = page.findChild<QCheckBox*>(QStringLiteral("favoritesOnlyCheck"));
    QCOMPARE(table->rowCount(), 3);
    search->setText(QStringLiteral("fast_lio"));
    QCOMPARE(table->rowCount(), 1);
    page.selectResult(QStringLiteral("archive-0"));
    page.findChild<QPushButton*>(QStringLiteral("favoriteButton"))->click();
    QVERIFY(services.workspaceData().isFavoriteResult(QStringLiteral("archive-0")));
    search->clear(); favorites->setChecked(true);
    QCOMPARE(table->rowCount(), 1);
    adapters::JsonWorkspaceStore reopenedStore(directory.path());
    Hardware hardware;
    application::WorkspaceService reopened(reopenedStore, hardware);
    QVERIFY(reopened.isFavoriteResult(QStringLiteral("archive-0")));
    page.selectResult(QStringLiteral("archive-0"));
    QSignalSpy analyze(&page, &ui::ResultsPage::analysisRequested);
    page.findChild<QPushButton*>(QStringLiteral("analyzeButton"))->click();
    QCOMPARE(analyze.count(), 1);
    QCOMPARE(analyze.takeFirst().front().toString(), QStringLiteral("archive-0"));
    page.findChild<QPushButton*>(QStringLiteral("favoriteButton"))->click();
    QCOMPARE(table->rowCount(), 0);
    QVERIFY(!page.findChild<QPushButton*>(QStringLiteral("analyzeButton"))->isEnabled());
  }
  void externalResultSelectionRevealsAnExistingFilteredArchive() {
    QTemporaryDir directory; QVERIFY(directory.isValid());
    FakeStation services(directory.path());
    services.workspaceData().setFavoriteResult(QStringLiteral("archive-0"), true);
    ui::ResultsPage page(services);
    auto* table = page.findChild<QTableWidget*>(QStringLiteral("historyTable"));
    auto* search = page.findChild<QLineEdit*>(QStringLiteral("searchResultsEdit"));
    auto* favorites = page.findChild<QCheckBox*>(QStringLiteral("favoritesOnlyCheck"));
    auto* detailTitle = page.findChild<QLabel*>(QStringLiteral("detailTitleLabel"));
    search->setText(QStringLiteral("FAST_LIO"));
    QCOMPARE(table->rowCount(), 1);
    page.selectResult(QStringLiteral("missing-archive"));
    QCOMPARE(table->rowCount(), 1);
    QCOMPARE(search->text(), QStringLiteral("FAST_LIO"));
    page.selectResult(QStringLiteral("archive-1"));
    QCOMPARE(table->rowCount(), 3);
    QVERIFY(search->text().isEmpty());
    QVERIFY(detailTitle->text().contains(QStringLiteral("run-1")));
    favorites->setChecked(true);
    QCOMPARE(table->rowCount(), 1);
    page.selectResult(QStringLiteral("archive-2"));
    QVERIFY(!favorites->isChecked());
    QCOMPARE(table->rowCount(), 3);
    QVERIFY(detailTitle->text().contains(QStringLiteral("run-2")));
  }
  void comparesExplicitSelectionAndInvalidatesPreviousReport() {
    QTemporaryDir directory; QVERIFY(directory.isValid());
    FakeStation services(directory.path());
    ui::ComparisonPage page(services);
    auto* first = page.findChild<QComboBox*>(QStringLiteral("firstResultCombo"));
    auto* second = page.findChild<QComboBox*>(QStringLiteral("secondResultCombo"));
    auto* button = page.findChild<QPushButton*>(QStringLiteral("compareSelectionButton"));
    auto* exportButton = page.findChild<QPushButton*>(QStringLiteral("exportReportButton"));
    QVERIFY(!button->isEnabled());
    first->setCurrentIndex(first->findData(QStringLiteral("archive-0")));
    second->setCurrentIndex(second->findData(QStringLiteral("archive-0")));
    QVERIFY(!button->isEnabled());
    second->setCurrentIndex(second->findData(QStringLiteral("archive-1")));
    QVERIFY(button->isEnabled()); button->click();
    QCOMPARE(services.comparedIds, QStringList({QStringLiteral("archive-0"), QStringLiteral("archive-1")}));
    QVERIFY(exportButton->isEnabled());
    page.refreshResults();
    QVERIFY(exportButton->isEnabled());
    second->setCurrentIndex(second->findData(QStringLiteral("archive-2")));
    QVERIFY(!exportButton->isEnabled());
    QVERIFY(page.findChild<QPlainTextEdit*>(QStringLiteral("comparisonReportEdit"))->toPlainText().isEmpty());
  }
  void analysesReadOnlyArchiveArtifactsAndPreservesSelectedSection() {
    QTemporaryDir directory; QVERIFY(directory.isValid());
    FakeStation services(directory.path());
    ui::AnalysisPage page(services);
    page.setSection(QStringLiteral("metrics"));
    page.openResult(QStringLiteral("archive-1"));
    QCOMPARE(page.findChild<QTabWidget*>(QStringLiteral("analysisTabs"))->currentIndex(), 2);
    auto* view = page.findChild<ui::TrajectoryView*>(QStringLiteral("analysisMapView"));
    QCOMPARE(view->pointCloudSize(), 3); QCOMPARE(view->surfaceTriangleCount(), 1);
    auto* metrics = page.findChild<QTableWidget*>(QStringLiteral("analysisMetricsTable"));
    QCOMPARE(metrics->rowCount(), 1); QCOMPARE(metrics->item(0, 1)->text(), QStringLiteral("0.125"));
    const auto report = page.findChild<QPlainTextEdit*>(QStringLiteral("analysisReportEdit"))->toPlainText();
    QVERIFY(report.contains(QStringLiteral("archive-1")));
    QVERIFY(report.contains(QStringLiteral("Note issue de la fixture archivée")));
    const auto replayCalls = services.replayCalls;
    page.refreshResults(); QCOMPARE(services.replayCalls, replayCalls);
    page.openResult(QStringLiteral("archive-2"));
    QCOMPARE(services.replayCalls, replayCalls);
    QCOMPARE(view->pointCloudSize(), 0);
    QCOMPARE(metrics->rowCount(), 1);
    QVERIFY(page.findChild<QLabel*>(QStringLiteral("mapAvailabilityLabel"))->text().contains(QStringLiteral("ne possède pas")));
  }
};
QTEST_MAIN(TestWorkbenchPages)
#include "TestWorkbenchPages.moc"
