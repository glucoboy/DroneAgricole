#include "drone_agricole/ui/MainWindow.hpp"
#include "drone_agricole/ui/ExecutionPage.hpp"
#include "drone_agricole/ui/ResultsPage.hpp"
#include "drone_agricole/ui/ComparisonPage.hpp"
#include "drone_agricole/ui/ResultViewPage.hpp"
#include "ui_main_window.h"
#include <QCloseEvent>
#include <QDir>
#include <QFile>
#include <QHeaderView>
#include <QMessageBox>
#include <QSignalBlocker>
#include <QTimer>
#include <algorithm>

namespace drone_agricole::ui {
MainWindow::MainWindow(application::IStationServices& services, QWidget* parent)
    : QMainWindow(parent), ui_(std::make_unique<Ui::MainWindow>()), services_(services) {
  ui_->setupUi(this);
  QFile style(QStringLiteral(":/dashboard/station.qss"));
  if (style.open(QIODevice::ReadOnly)) setStyleSheet(QString::fromUtf8(style.readAll()));
  ui_->workspaceLabel->setText(QDir(services_.workspace()).dirName());
  ui_->workspaceLabel->setToolTip(services_.workspace());
  executionPage_ = new ExecutionPage(services_, this);
  resultsPage_ = new ResultsPage(services_, this);
  comparisonPage_ = new ComparisonPage(services_, this);
  resultPage_ = new ResultViewPage(services_, this);
  registerPage(QStringLiteral("overview"), QStringLiteral("Vue d'ensemble"), ui_->overviewPage, true);
  registerPage(QStringLiteral("acquisitions"), QStringLiteral("Acquisitions"), ui_->acquisitionsPage, true);
  registerPage(QStringLiteral("tests"), QStringLiteral("Essais"), executionPage_, true);
  registerPage(QStringLiteral("results"), QStringLiteral("Résultats"), resultsPage_, true);
  registerPage(QStringLiteral("comparison"), QStringLiteral("Résultats > Comparaison"), comparisonPage_, false);
  registerPage(QStringLiteral("result"), QStringLiteral("Résultats > Archive"), resultPage_, false);
  connect(&navigation_, &NavigationModel::changed, this, &MainWindow::updateNavigation);
  connect(ui_->navigationList, &QListWidget::currentRowChanged, this, [this](int row) {
    if (row >= 0) navigation_.navigate(ui_->navigationList->item(row)->data(Qt::UserRole).toString());
  });
  connect(ui_->backButton, &QPushButton::clicked, &navigation_, &NavigationModel::back);
  connect(ui_->openAcquisitionsButton, &QPushButton::clicked, this, [this] { navigation_.navigate(QStringLiteral("acquisitions")); });
  connect(ui_->openTestsButton, &QPushButton::clicked, this, [this] { navigation_.navigate(QStringLiteral("tests")); });
  connect(ui_->openResultsButton, &QPushButton::clicked, this, [this] { navigation_.navigate(QStringLiteral("results")); });
  connect(ui_->showTreatmentButton, &QPushButton::clicked, this, [this] { navigation_.navigate(QStringLiteral("tests")); });
  connect(ui_->cancelTreatmentButton, &QPushButton::clicked, &services_.execution(), &application::RunService::cancel);
  connect(ui_->openTreatmentResultButton, &QPushButton::clicked, this, [this] {
    if (!lastResultId_.isEmpty()) navigation_.navigate(QStringLiteral("result"), lastResultId_);
  });
  connect(resultsPage_, &ResultsPage::replayRequested, this, [this](const QString& id) { navigation_.navigate(QStringLiteral("result"), id); });
  connect(resultsPage_, &ResultsPage::duplicateRequested, this, [this](const QJsonObject& request) {
    executionPage_->applyRequest(request);
    navigation_.navigate(QStringLiteral("tests"));
  });
  connect(resultsPage_, &ResultsPage::comparisonRequested, this, [this](const QStringList& ids) {
    if (comparisonPage_->compare(ids)) navigation_.navigate(QStringLiteral("comparison"));
  });
  connect(executionPage_, &ExecutionPage::resultAvailable, this, [this](const QString& id) {
    lastResultId_ = id;
    ui_->openTreatmentResultButton->setEnabled(true);
  });
  connect(&services_.execution(), &application::RunService::changed, this, &MainWindow::updateTreatment);
  connect(&services_.execution(), &application::RunService::completed, this, [this] {
    refreshOverview();
    if (closePending_) QTimer::singleShot(0, this, &QWidget::close);
  });
  connect(ui_->recentResultsTable, &QTableWidget::cellDoubleClicked, this, [this](int row, int) {
    navigation_.navigate(QStringLiteral("results"), ui_->recentResultsTable->item(row, 0)->data(Qt::UserRole).toString());
  });
  refreshOverview();
  updateTreatment();
  navigation_.navigate(QStringLiteral("overview"));
}
MainWindow::~MainWindow() = default;

void MainWindow::registerPage(const QString& id, const QString& title, QWidget* page, bool primary) {
  navigation_.registerPage(id, title);
  pages_.insert(id, page);
  if (ui_->pageStack->indexOf(page) < 0) ui_->pageStack->addWidget(page);
  if (primary) {
    auto* item = new QListWidgetItem(title, ui_->navigationList);
    item->setData(Qt::UserRole, id);
  }
}

void MainWindow::updateNavigation() {
  const auto route = navigation_.current();
  try {
    if (route.page == QStringLiteral("result")) resultPage_->openResult(route.object);
    if (route.page == QStringLiteral("results") && !route.object.isEmpty()) resultsPage_->selectResult(route.object);
    ui_->pageStack->setCurrentWidget(pages_.value(route.page));
    ui_->breadcrumbLabel->setText(route.object.isEmpty() ? navigation_.title()
        : QStringLiteral("%1 · %2").arg(navigation_.title(), route.object));
    ui_->backButton->setEnabled(navigation_.canGoBack());
    const QSignalBlocker blocker(ui_->navigationList);
    const auto primary = route.page == QStringLiteral("result") || route.page == QStringLiteral("comparison")
                             ? QStringLiteral("results") : route.page;
    for (int row = 0; row < ui_->navigationList->count(); ++row)
      if (ui_->navigationList->item(row)->data(Qt::UserRole).toString() == primary) ui_->navigationList->setCurrentRow(row);
  } catch (const std::exception& error) {
    QMessageBox::warning(this, QStringLiteral("Ouverture impossible"), QString::fromUtf8(error.what()));
    navigation_.back();
  }
}

void MainWindow::updateTreatment() {
  const auto& execution = services_.execution();
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
  const auto sequences = services_.datasetSequences();
  ui_->overviewCounts->setText(QStringLiteral("%1 séquences déclarées    ·    %2 essais disponibles    ·    %3 résultats")
      .arg(sequences.size()).arg(services_.simulations().size()).arg(services_.totalCount()));
  ui_->acquisitionsTable->setRowCount(sequences.size());
  for (qsizetype row = 0; row < sequences.size(); ++row) {
    const auto& sequence = sequences.at(row);
    auto capabilities = sequence.capabilities.values();
    std::sort(capabilities.begin(), capabilities.end());
    const QStringList cells{sequence.datasetLabel, sequence.sequenceLabel, sequence.status, capabilities.join(QStringLiteral(", "))};
    for (int column = 0; column < cells.size(); ++column) ui_->acquisitionsTable->setItem(row, column, new QTableWidgetItem(cells[column]));
  }
  auto results = services_.search();
  const auto count = std::min<qsizetype>(8, results.size());
  ui_->recentResultsTable->setRowCount(count);
  for (qsizetype row = 0; row < count; ++row) {
    const auto& result = results[row];
    auto* date = new QTableWidgetItem(result.createdAtUtc.toString(QStringLiteral("yyyy-MM-dd HH:mm")));
    date->setData(Qt::UserRole, result.resultId);
    ui_->recentResultsTable->setItem(row, 0, date);
    ui_->recentResultsTable->setItem(row, 1, new QTableWidgetItem(result.variantId));
    ui_->recentResultsTable->setItem(row, 2, new QTableWidgetItem(result.state));
  }
  for (auto* table : {ui_->acquisitionsTable, ui_->recentResultsTable}) {
    table->verticalHeader()->hide();
    table->resizeColumnsToContents();
    table->horizontalHeader()->setStretchLastSection(true);
  }
}

void MainWindow::closeEvent(QCloseEvent* event) {
  if (!services_.execution().active()) { event->accept(); return; }
  event->ignore();
  if (closePending_) return;
  const auto answer = QMessageBox::question(this, QStringLiteral("Traitement en cours"),
      QStringLiteral("Annuler le traitement et fermer la station après son arrêt ?"), QMessageBox::Yes | QMessageBox::No, QMessageBox::No);
  if (answer == QMessageBox::Yes) {
    closePending_ = true;
    services_.execution().cancel();
    statusBar()->showMessage(QStringLiteral("Fermeture après l'arrêt du traitement…"));
  }
}
}  // namespace drone_agricole::ui
