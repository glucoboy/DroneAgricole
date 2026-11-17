#include "drone_agricole/ui/MainWindow.hpp"
#include "drone_agricole/ui/ExecutionPage.hpp"
#include "drone_agricole/ui/ResultsPage.hpp"
#include "drone_agricole/ui/ComparisonPage.hpp"
#include "drone_agricole/ui/ResultViewPage.hpp"
#include "drone_agricole/ui/MissionsPage.hpp"
#include "drone_agricole/ui/DataPage.hpp"
#include "drone_agricole/ui/SystemPage.hpp"
#include "drone_agricole/ui/AnalysisPage.hpp"
#include "drone_agricole/ui/GazeboModelPage.hpp"
#include "drone_agricole/application/WorkspaceService.hpp"
#include "ui_main_window.h"
#include <QCloseEvent>
#include <QDir>
#include <QFile>
#include <QHeaderView>
#include <QJsonDocument>
#include <QJsonObject>
#include <QMessageBox>
#include <QSignalBlocker>
#include <QTimer>
#include <algorithm>

namespace drone_agricole::ui {
MainWindow::MainWindow(application::IStationServices& services, QWidget* parent)
    : QMainWindow(parent), ui_(std::make_unique<Ui::MainWindow>()), services_(services) {
  ui_->setupUi(this);
  ui_->workspaceLabel->setText(QDir(services_.workspace()).dirName());
  ui_->workspaceLabel->setToolTip(services_.workspace());
  executionPage_ = new ExecutionPage(services_, this);
  resultsPage_ = new ResultsPage(services_, this);
  comparisonPage_ = new ComparisonPage(services_, this);
  resultPage_ = new ResultViewPage(services_, this);
  missionsPage_ = new MissionsPage(services_, this);
  dataPage_ = new DataPage(services_, this);
  systemPage_ = new SystemPage(services_, this);
  analysisPage_ = new AnalysisPage(services_, this);
  gazeboModelPage_ = new GazeboModelPage(services_.gazeboExport(), this);
  const auto add = [this](const char* id, const char* title, QWidget* page, const char* section, const char* sectionTitle) {
    registerPage(QString::fromUtf8(id), QString::fromUtf8(title), page, QString::fromUtf8(section), QString::fromUtf8(sectionTitle));
  };
  add("overview", "Dashboard", ui_->overviewPage, "home", "Accueil");
  add("recent", "Récents", ui_->overviewPage, "home", "Accueil");
  add("favorites", "Favoris", ui_->overviewPage, "home", "Accueil");
  add("mission-preparation", "Préparation", missionsPage_, "missions", "Missions");
  add("mission-supervision", "Supervision", missionsPage_, "missions", "Missions");
  add("mission-journal", "Journal", missionsPage_, "missions", "Missions");
  add("data-catalogue", "Catalogue", dataPage_, "data", "Données");
  add("acquisitions", "Acquisitions", dataPage_, "data", "Données");
  add("data-transfer", "Import / Export", dataPage_, "data", "Données");
  add("bench-configuration", "Configuration", executionPage_, "bench", "Simulations");
  add("tests", "Exécution", executionPage_, "bench", "Simulations");
  add("results", "Résultats", resultsPage_, "bench", "Simulations");
  add("comparison", "Comparaison", comparisonPage_, "bench", "Simulations");
  add("bench-model", "Modèle 3D", gazeboModelPage_, "bench", "Simulations");
  add("analysis-maps", "Cartes", analysisPage_, "analysis", "Analyse");
  add("analysis-trajectories", "Trajectoires", analysisPage_, "analysis", "Analyse");
  add("analysis-metrics", "Métriques", analysisPage_, "analysis", "Analyse");
  add("analysis-reports", "Rapports", analysisPage_, "analysis", "Analyse");
  add("system-settings", "Paramètres", systemPage_, "system", "Système");
  add("system-hardware", "Matériel", systemPage_, "system", "Système");
  add("system-diagnostics", "Diagnostics", systemPage_, "system", "Système");
  add("system-maintenance", "Maintenance", systemPage_, "system", "Système");
  // Une archive conserve son identité dans l'historique de navigation.
  add("result", "Archive", resultPage_, "bench", "Simulations");
  connect(&navigation_, &NavigationModel::changed, this, &MainWindow::updateNavigation);
  connect(ui_->navigationList, &QListWidget::currentRowChanged, this, [this](int row) {
    if (row >= 0) navigate(ui_->navigationList->item(row)->data(Qt::UserRole).toString());
  });
  connect(ui_->sectionTabs, &QTabBar::currentChanged, this, [this](int index) {
    if (index >= 0) navigate(ui_->sectionTabs->tabData(index).toString());
  });
  connect(ui_->backButton, &QPushButton::clicked, &navigation_, &NavigationModel::back);
  const auto shortcut = [this](QPushButton* button, const QString& route) {
    connect(button, &QPushButton::clicked, this, [this, route] { navigate(route); });
  };
  connect(ui_->createMissionButton, &QPushButton::clicked, this, [this] {
    missionsPage_->startNewDraft();
    navigate(QStringLiteral("mission-preparation"));
  });
  shortcut(ui_->openMissionsButton, QStringLiteral("mission-preparation"));
  shortcut(ui_->openAcquisitionsButton, QStringLiteral("acquisitions"));
  shortcut(ui_->openTestsButton, QStringLiteral("tests"));
  shortcut(ui_->openResultsButton, QStringLiteral("results"));
  shortcut(ui_->openHardwareButton, QStringLiteral("system-hardware"));
  shortcut(ui_->openDiagnosticsButton, QStringLiteral("system-diagnostics"));
  shortcut(ui_->settingsShortcut, QStringLiteral("system-settings"));
  connect(ui_->showTreatmentButton,&QPushButton::clicked,this,[this] {
    navigate(services_.gazeboExport().active()&&!services_.execution().active()?QStringLiteral("bench-model"):QStringLiteral("tests"));
  });
  connect(missionsPage_, &MissionsPage::routeRequested, this, &MainWindow::navigate);
  connect(dataPage_, &DataPage::routeRequested, this, &MainWindow::navigate);
  connect(systemPage_, &SystemPage::routeRequested, this, &MainWindow::navigate);
  connect(systemPage_, &SystemPage::themeChanged, this, &MainWindow::applyTheme);
  connect(ui_->cancelTreatmentButton, &QPushButton::clicked, this, [this] {
    if(services_.gazeboExport().active()&&!services_.execution().active())services_.gazeboExport().cancel();else services_.execution().cancel();
  });
  connect(ui_->openTreatmentResultButton, &QPushButton::clicked, this, [this] {
    if (!lastResultId_.isEmpty()) navigate(QStringLiteral("result"), lastResultId_);
  });
  connect(resultsPage_, &ResultsPage::replayRequested, this, [this](const QString& id) { navigate(QStringLiteral("result"), id); });
  connect(resultsPage_, &ResultsPage::analysisRequested, this, [this](const QString& id) { navigate(QStringLiteral("analysis-maps"), id); });
  connect(resultsPage_, &ResultsPage::duplicateRequested, this, [this](const QJsonObject& request) {
    executionPage_->applyRequest(request);
    navigate(QStringLiteral("tests"));
  });
  connect(resultsPage_, &ResultsPage::comparisonRequested, this, [this](const QStringList& ids) {
    if (comparisonPage_->compare(ids)) navigate(QStringLiteral("comparison"));
  });
  connect(executionPage_, &ExecutionPage::resultAvailable, this, [this](const QString& id) {
    lastResultId_ = id;
    ui_->openTreatmentResultButton->setEnabled(true);
  });
  connect(&services_.execution(), &application::RunService::changed, this, &MainWindow::updateTreatment);
  connect(&services_.gazeboExport(), &application::GazeboExportService::changed, this, &MainWindow::updateTreatment);
  connect(&services_.execution(), &application::RunService::completed, this, [this] {
    refreshOverview();
    if (closePending_) QTimer::singleShot(0, this, &QWidget::close);
  });
  connect(&services_.gazeboExport(), &application::GazeboExportService::completed, this, [this] {
    if(closePending_&&!services_.execution().active())QTimer::singleShot(0,this,&QWidget::close);
  });
  connect(ui_->recentResultsTable, &QTableWidget::cellDoubleClicked, this, [this](int row, int) {
    const auto* item = ui_->recentResultsTable->item(row, 0);
    if (item) navigate(QStringLiteral("results"), item->data(Qt::UserRole).toString());
  });
  applyTheme();
  updateTreatment();
  navigate(QStringLiteral("overview"));
}
MainWindow::~MainWindow() = default;
bool MainWindow::navigate(const QString& route, const QString& object) { return navigation_.navigate(route, object); }

void MainWindow::registerPage(const QString& id, const QString& title, QWidget* page,
                              const QString& section, const QString& sectionTitle) {
  navigation_.registerPage(id, title);
  pages_.insert(id, page);
  if (ui_->pageStack->indexOf(page) < 0) ui_->pageStack->addWidget(page);
  const auto existing = std::any_of(routes_.cbegin(), routes_.cend(), [&](const Route& route) { return route.section == section; });
  routes_.append({id, title, section, sectionTitle});
  if (!existing) {
    auto* item = new QListWidgetItem(sectionTitle, ui_->navigationList);
    item->setData(Qt::UserRole, id);
    item->setData(Qt::UserRole + 1, section);
  }
}

void MainWindow::updateNavigation() {
  const auto route = navigation_.current();
  const auto found = std::find_if(routes_.cbegin(), routes_.cend(), [&](const Route& value) { return value.id == route.page; });
  if (found == routes_.cend()) return;
  try {
    if (route.page == QStringLiteral("tests") && !route.object.isEmpty()) {
      const auto selection = QJsonDocument::fromJson(route.object.toUtf8()).object();
      executionPage_->selectDataset(selection.value(QStringLiteral("dataset_id")).toString(),
                                    selection.value(QStringLiteral("sequence_id")).toString());
    }
    if (pages_.value(route.page) == missionsPage_) {
      missionsPage_->setSection(route.page.mid(QStringLiteral("mission-").size()));
      missionsPage_->refresh();
    }
    if (pages_.value(route.page) == dataPage_) {
      dataPage_->setSection(route.page == QStringLiteral("acquisitions") ? QStringLiteral("acquisitions")
        : route.page == QStringLiteral("data-transfer") ? QStringLiteral("import-export") : QStringLiteral("catalogue"));
      dataPage_->refresh();
    }
    if (pages_.value(route.page) == systemPage_) {
      systemPage_->setSection(route.page.mid(QStringLiteral("system-").size()));
      systemPage_->refresh();
    }
    if (pages_.value(route.page) == analysisPage_) {
      analysisPage_->setSection(route.page.mid(QStringLiteral("analysis-").size()));
      analysisPage_->refreshResults();
      if (!route.object.isEmpty()) analysisPage_->openResult(route.object);
    }
    if (route.page == QStringLiteral("result")) resultPage_->openResult(route.object);
    if (route.page == QStringLiteral("results") && !route.object.isEmpty()) resultsPage_->selectResult(route.object);
    if (route.page == QStringLiteral("comparison")) comparisonPage_->refreshResults();
    if (pages_.value(route.page) == ui_->overviewPage) refreshOverview();
    ui_->pageStack->setCurrentWidget(pages_.value(route.page));
    ui_->breadcrumbLabel->setText(QStringLiteral("Espace de travail  ›  %1  ›  %2%3").arg(found->sectionTitle, found->title,
      route.object.isEmpty() || route.page == QStringLiteral("tests") ? QString{} : QStringLiteral(" · ") + route.object));
    ui_->backButton->setEnabled(navigation_.canGoBack());
    const QSignalBlocker tabsBlocker(ui_->sectionTabs);
    while (ui_->sectionTabs->count()) ui_->sectionTabs->removeTab(0);
    for (const auto& item : routes_) {
      if (item.section != found->section || item.id == QStringLiteral("result")) continue;
      const auto index = ui_->sectionTabs->addTab(item.title);
      ui_->sectionTabs->setTabData(index, item.id);
      if (item.id == route.page || (route.page == QStringLiteral("result") && item.id == QStringLiteral("results")))
        ui_->sectionTabs->setCurrentIndex(index);
    }
    const QSignalBlocker menuBlocker(ui_->navigationList);
    for (int row = 0; row < ui_->navigationList->count(); ++row)
      if (ui_->navigationList->item(row)->data(Qt::UserRole + 1).toString() == found->section)
        ui_->navigationList->setCurrentRow(row);
  } catch (const std::exception& error) {
    statusBar()->showMessage(QString::fromUtf8(error.what()), 15000);
    if (navigation_.canGoBack()) navigation_.back();
  }
}

void MainWindow::applyTheme() {
  QString theme = QStringLiteral("professional");
  try { theme = services_.workspaceData().preferences().themeId; }
  catch (const std::exception& error) { statusBar()->showMessage(QString::fromUtf8(error.what()), 15000); }
  previewTheme(theme);
}

void MainWindow::previewTheme(const QString& theme) {
  if (theme != QStringLiteral("professional") && theme != QStringLiteral("premium")) return;
  QFile style(QStringLiteral(":/dashboard/station.qss"));
  if (!style.open(QIODevice::ReadOnly)) return;
  auto sheet = QString::fromUtf8(style.readAll());
  const bool premium = theme == QStringLiteral("premium");
  sheet.replace(QStringLiteral("@accent@"), premium ? QStringLiteral("#397a68") : QStringLiteral("#286a96"));
  sheet.replace(QStringLiteral("@tint@"), premium ? QStringLiteral("#edf5ef") : QStringLiteral("#e9f3f9"));
  sheet.replace(QStringLiteral("@background@"), premium ? QStringLiteral("#f6f8f4") : QStringLiteral("#f6f8fa"));
  sheet.replace(QStringLiteral("@sidebar@"), premium ? QStringLiteral("#f1f5f0") : QStringLiteral("#f1f4f6"));
  sheet.replace(QStringLiteral("@text@"), premium ? QStringLiteral("#2d3c36") : QStringLiteral("#293643"));
  setProperty("stationTheme", theme);
  setStyleSheet(sheet);
  statusBar()->showMessage(premium ? QStringLiteral("Clair premium sobre") : QStringLiteral("Clair professionnel"), 3000);
}

void MainWindow::updateTreatment() {
  const auto& execution = services_.execution();
  const auto& exporter = services_.gazeboExport();
  if(exporter.active()&&!execution.active()) {
    ui_->treatmentLabel->setText(exporter.message());ui_->treatmentProgress->show();ui_->treatmentProgress->setValue(exporter.progress());
    ui_->cancelTreatmentButton->setEnabled(true);ui_->showTreatmentButton->setEnabled(true);ui_->openTreatmentResultButton->setEnabled(false);return;
  }
  if (execution.state() == domain::RunState::Preparing) {
    lastResultId_.clear();
    ui_->openTreatmentResultButton->setEnabled(false);
  }
  const auto run = execution.run();
  ui_->treatmentLabel->setText(run ? QStringLiteral("%1 · %2").arg(run->variantId, execution.message())
                                  : domain::stateLabel(execution.state()));
  ui_->treatmentProgress->setVisible(execution.active());
  ui_->treatmentProgress->setValue(execution.progress());
  ui_->cancelTreatmentButton->setEnabled(execution.active() && execution.state() != domain::RunState::Cancelling);
  ui_->showTreatmentButton->setEnabled(execution.state() != domain::RunState::Idle);
}

void MainWindow::refreshOverview() {
  const auto route = navigation_.current().page;
  const bool favorites = route == QStringLiteral("favorites");
  ui_->overviewTitle->setText(favorites ? QStringLiteral("Vos favoris") : route == QStringLiteral("recent")
    ? QStringLiteral("Activité récente") : QStringLiteral("Vue d'ensemble"));
  ui_->overviewDescription->setText(favorites ? QStringLiteral("Retrouvez les résultats épinglés depuis leur fiche.")
    : QStringLiteral("Votre espace de travail pour préparer, simuler et analyser vos opérations."));
  ui_->dataStatValue->setText(QString::number(services_.datasetSequences().size()));
  ui_->resultStatValue->setText(QString::number(services_.totalCount()));
  ui_->systemStatValue->setText(QStringLiteral("Non mesuré"));
  try {
    const auto& workspace = services_.workspaceData();
    ui_->missionStatValue->setText(QString::number(workspace.missions().size()));
    const auto inventory = workspace.hardwareInventory();
    ui_->systemStateLabel->setText(QStringLiteral("Configuration cartographe\n%1 lignes de nomenclature\n\n%2\n\nConnexion et santé des équipements : non mesurées.")
      .arg(inventory.items.size()).arg(inventory.qualification));
    ui_->followLabel->setText(QStringLiteral("%1 brouillon(s) de mission\n%2 résultat(s) ignoré(s) par l'index\n\nLes critères matériels restent À valider.")
      .arg(workspace.missions().size()).arg(services_.invalidResultCount()));
  } catch (const std::exception& error) {
    ui_->missionStatValue->setText(QStringLiteral("—"));
    ui_->systemStateLabel->setText(QString::fromUtf8(error.what()));
  }
  auto results = services_.search();
  if (favorites) {
    const auto favoriteIds = services_.workspaceData().preferences().favoriteResultIds;
    results.erase(std::remove_if(results.begin(), results.end(), [&favoriteIds](const auto& result) {
      return !favoriteIds.contains(result.resultId);
    }), results.end());
  }
  std::sort(results.begin(), results.end(), [](const auto& a, const auto& b) { return a.createdAtUtc > b.createdAtUtc; });
  const auto count = favorites || route == QStringLiteral("recent") ? results.size() : std::min<qsizetype>(6, results.size());
  ui_->recentGroup->setTitle(favorites ? QStringLiteral("Résultats favoris") : QStringLiteral("Activité récente"));
  ui_->recentResultsTable->setRowCount(count);
  ui_->recentEmptyLabel->setVisible(count == 0);
  for (qsizetype row = 0; row < count; ++row) {
    const auto& result = results[row];
    const QStringList cells{result.createdAtUtc.toString(QStringLiteral("dd/MM HH:mm")), result.variantId, result.domain, result.state};
    for (int column = 0; column < cells.size(); ++column) {
      auto* item = new QTableWidgetItem(cells[column]);
      item->setData(Qt::UserRole, result.resultId);
      ui_->recentResultsTable->setItem(row, column, item);
    }
  }
  ui_->recentResultsTable->verticalHeader()->hide();
  ui_->recentResultsTable->horizontalHeader()->setSectionResizeMode(QHeaderView::Stretch);
}

void MainWindow::closeEvent(QCloseEvent* event) {
  if (!services_.execution().active() && !services_.gazeboExport().active()) { event->accept(); return; }
  event->ignore();
  if (closePending_) return;
  const auto answer = QMessageBox::question(this, QStringLiteral("Traitement en cours"),
      QStringLiteral("Annuler le traitement et fermer la station après son arrêt ?"), QMessageBox::Yes | QMessageBox::No, QMessageBox::No);
  if (answer == QMessageBox::Yes) {
    closePending_ = true;
    services_.execution().cancel();
    services_.gazeboExport().cancel();
    statusBar()->showMessage(QStringLiteral("Fermeture après l'arrêt du traitement…"));
  }
}
}  // namespace drone_agricole::ui
