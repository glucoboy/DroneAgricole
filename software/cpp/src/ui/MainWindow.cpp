#include "drone_agricole/ui/MainWindow.hpp"

#include "drone_agricole/core/JsonUtils.hpp"
#include "drone_agricole/core/ResultAdapter.hpp"
#include "drone_agricole/ui/MetricsPlotWidget.hpp"
#include "drone_agricole/ui/TrajectoryView.hpp"
#include "ui_main_window.h"

#include <QApplication>
#include <QCheckBox>
#include <QComboBox>
#include <QDateEdit>
#include <QDesktopServices>
#include <QDoubleSpinBox>
#include <QEventLoop>
#include <QFileDialog>
#include <QFileInfo>
#include <QFormLayout>
#include <QHeaderView>
#include <QJsonDocument>
#include <QLabel>
#include <QLineEdit>
#include <QMessageBox>
#include <QProcessEnvironment>
#include <QRegularExpression>
#include <QSaveFile>
#include <QSignalBlocker>
#include <QSpinBox>
#include <QStyle>
#include <QTableWidgetItem>
#include <QTimer>
#include <QUrl>

#include <algorithm>
#include <cmath>
#include <limits>
#include <tuple>

namespace drone_agricole::ui {
namespace {

const QList<QColor> comparisonColors{
    QColor(QStringLiteral("#55e2d2")),
    QColor(QStringLiteral("#c995ff")),
    QColor(QStringLiteral("#74e3a8")),
    QColor(QStringLiteral("#ff8fa8")),
};

QTableWidgetItem* item(const QString& text) {
  auto* value = new QTableWidgetItem(text);
  value->setFlags(value->flags() & ~Qt::ItemIsEditable);
  return value;
}

QString displayValue(const QJsonValue& value) {
  return core::scalarText(value).isEmpty() ? QStringLiteral("—") : core::scalarText(value);
}

QString datasetReferenceText(const core::ResultSummary& summary) {
  return summary.domain == QStringLiteral("localization") ? summary.datasetId : summary.scenarioId;
}

QString resultLabel(const core::ResultSummary& summary) {
  return QStringLiteral("%1 · %2").arg(summary.variantId, summary.runId);
}

void prepareTable(QTableWidget* table) {
  table->horizontalHeader()->setStretchLastSection(true);
  table->verticalHeader()->setVisible(false);
  table->setAlternatingRowColors(true);
}

}  // namespace

MainWindow::MainWindow(QString workspace, QWidget* parent)
    : QMainWindow(parent), ui_(std::make_unique<Ui::MainWindow>()), workspace_(core::normalizedPath(std::move(workspace))) {
  ui_->setupUi(this);
  ui_->workspaceLabel->setText(QStringLiteral("PROJET LOCAL\n%1").arg(QDir(workspace_).dirName()));
  ui_->workspaceLabel->setToolTip(workspace_);
  for (auto* table : {ui_->liveMetricsTable, ui_->historyTable, ui_->detailMetricsTable, ui_->detailEventsTable,
                      ui_->comparisonMetricsTable, ui_->comparisonParametersTable, ui_->comparisonVersionsTable}) {
    prepareTable(table);
  }
  ui_->historyTable->horizontalHeader()->setSectionResizeMode(QHeaderView::ResizeToContents);
  ui_->historyTable->horizontalHeader()->setStretchLastSection(true);
  ui_->dateFromEdit->setMinimumDate(QDate(2000, 1, 1));
  ui_->dateToEdit->setMinimumDate(QDate(2000, 1, 1));
  ui_->dateFromEdit->setDate(ui_->dateFromEdit->minimumDate());
  ui_->dateToEdit->setDate(ui_->dateToEdit->minimumDate());
  connectInterface();
  initializeData();
}

MainWindow::~MainWindow() {
  if (process_.state() != QProcess::NotRunning) {
    if (activeRun_ && !activeRun_->stopProgram.isEmpty()) {
      QProcess::execute(activeRun_->stopProgram, activeRun_->stopArguments);
    }
    process_.terminate();
    process_.waitForFinished(3000);
  }
}

void MainWindow::connectInterface() {
  connect(ui_->simulationCombo, &QComboBox::currentIndexChanged, this, &MainWindow::simulationChanged);
  connect(ui_->variantCombo, &QComboBox::currentIndexChanged, this, &MainWindow::variantChanged);
  connect(ui_->startButton, &QPushButton::clicked, this, &MainWindow::startRun);
  connect(ui_->stopButton, &QPushButton::clicked, this, &MainWindow::stopRun);
  connect(&process_, &QProcess::readyReadStandardOutput, this, &MainWindow::processOutput);
  connect(&process_, &QProcess::readyReadStandardError, this, &MainWindow::processOutput);
  connect(&process_, qOverload<int, QProcess::ExitStatus>(&QProcess::finished), this, &MainWindow::processFinished);
  connect(ui_->refreshHistoryButton, &QPushButton::clicked, this, &MainWindow::refreshHistory);
  connect(ui_->rebuildIndexAction, &QAction::triggered, this, &MainWindow::refreshHistory);
  connect(ui_->applyFiltersButton, &QPushButton::clicked, this, &MainWindow::applyHistoryFilters);
  connect(ui_->resetFiltersButton, &QPushButton::clicked, this, &MainWindow::resetHistoryFilters);
  connect(ui_->historyTable, &QTableWidget::itemSelectionChanged, this, &MainWindow::historySelectionChanged);
  connect(ui_->replayButton, &QPushButton::clicked, this, &MainWindow::replaySelectedResult);
  connect(ui_->duplicateButton, &QPushButton::clicked, this, &MainWindow::duplicateSelectedResult);
  connect(ui_->openResultFolderButton, &QPushButton::clicked, this, &MainWindow::openSelectedResultFolder);
  connect(ui_->compareButton, &QPushButton::clicked, this, &MainWindow::compareSelectedResults);
  connect(ui_->exportReportButton, &QPushButton::clicked, this, &MainWindow::exportComparisonReport);
  connect(ui_->resetViewAction, &QAction::triggered, ui_->trajectoryView, &TrajectoryView::resetView);
  connect(ui_->resetViewAction, &QAction::triggered, ui_->comparisonTrajectoryView, &TrajectoryView::resetView);
  connect(ui_->fitMapButton, &QPushButton::clicked, ui_->trajectoryView, &TrajectoryView::fitToData);
  connect(ui_->topMapButton, &QPushButton::clicked, ui_->trajectoryView, &TrajectoryView::setTopView);
  connect(ui_->quitAction, &QAction::triggered, qApp, &QApplication::quit);
  connect(ui_->aboutAction, &QAction::triggered, this, &MainWindow::showAbout);
  connect(&telemetryTimer_, &QTimer::timeout, this, &MainWindow::updateLiveTelemetry);
  telemetryTimer_.setInterval(250);
  telemetryTimer_.start();
}

void MainWindow::initializeData() {
  try {
    contracts_ = std::make_unique<core::ContractRegistry>(workspace_);
    contracts_->load();
    repository_ = std::make_unique<core::ResultRepository>(workspace_);
    repository_->refresh();
    runners_ = std::make_unique<core::RunnerRegistry>(*contracts_);
    comparisons_ = std::make_unique<core::ComparisonService>(*repository_);
    telemetry_ = std::make_unique<core::LiveTelemetry>();
    populateSimulations();
    populateFilterChoices();
    populateHistoryTable();
    setGlobalStatus(QStringLiteral("PRÊT · %1 résultats · %2 schémas")
                        .arg(repository_->totalCount())
                        .arg(contracts_->schemaDocumentCount()));
    statusBar()->showMessage(QStringLiteral("Application desktop Qt initialisée · aucune archive modifiée"), 8000);
  } catch (const std::exception& error) {
    setGlobalStatus(QStringLiteral("ERREUR"), true);
    QMessageBox::critical(this, QStringLiteral("Initialisation impossible"), QString::fromUtf8(error.what()));
  }
}

void MainWindow::populateSimulations() {
  QSignalBlocker blocker(ui_->simulationCombo);
  ui_->simulationCombo->clear();
  for (const auto& simulation : contracts_->simulations()) {
    ui_->simulationCombo->addItem(simulation.label, simulation.id);
  }
  populateVariants();
}

void MainWindow::simulationChanged() {
  if (!contracts_) {
    return;
  }
  populateVariants();
}

void MainWindow::variantChanged() {
  if (!contracts_ || currentVariantId().isEmpty()) {
    return;
  }
  populateDatasetSequences();
  populateProfiles();
  rebuildParameterEditors();
}

void MainWindow::populateVariants() {
  QSignalBlocker blocker(ui_->variantCombo);
  ui_->variantCombo->clear();
  if (currentSimulationId().isEmpty()) {
    return;
  }
  try {
    for (const auto& variant : contracts_->simulation(currentSimulationId()).variants) {
      if (variant.available) {
        ui_->variantCombo->addItem(variant.label, variant.id);
      }
    }
  } catch (const std::exception& error) {
    appendLog(QString::fromUtf8(error.what()));
  }
  variantChanged();
}

void MainWindow::populateDatasetSequences() {
  QSignalBlocker datasetBlocker(ui_->datasetCombo);
  QSignalBlocker sequenceBlocker(ui_->sequenceCombo);
  ui_->datasetCombo->clear();
  ui_->sequenceCombo->clear();
  const auto& simulation = contracts_->simulation(currentSimulationId());
  const auto usesDataset = !simulation.selectors.isEmpty();
  ui_->datasetLabel->setVisible(usesDataset);
  ui_->datasetCombo->setVisible(usesDataset);
  ui_->sequenceLabel->setVisible(usesDataset);
  ui_->sequenceCombo->setVisible(usesDataset);
  if (!usesDataset) {
    return;
  }
  const auto compatible = contracts_->compatibleSequences(currentSimulationId(), currentVariantId());
  QStringList datasets;
  for (const auto& sequence : compatible) {
    if (!datasets.contains(sequence.datasetId)) {
      datasets.append(sequence.datasetId);
      ui_->datasetCombo->addItem(sequence.datasetLabel, sequence.datasetId);
    }
  }
  const auto selectedDataset = ui_->datasetCombo->currentData().toString();
  for (const auto& sequence : compatible) {
    if (sequence.datasetId == selectedDataset) {
      ui_->sequenceCombo->addItem(sequence.sequenceLabel, sequence.sequenceId);
      if (sequence.recommended) {
        ui_->sequenceCombo->setCurrentIndex(ui_->sequenceCombo->count() - 1);
      }
    }
  }
}

void MainWindow::populateProfiles() {
  QSignalBlocker blocker(ui_->profileCombo);
  ui_->profileCombo->clear();
  const auto profiles = contracts_->simulation(currentSimulationId()).profiles;
  const auto visible = !profiles.isEmpty();
  ui_->profileLabel->setVisible(visible);
  ui_->profileCombo->setVisible(visible);
  for (const auto& value : profiles) {
    const auto profile = value.toObject();
    if (!profile.value(QStringLiteral("variant_settings")).toObject().contains(currentVariantId())) {
      continue;
    }
    ui_->profileCombo->addItem(profile.value(QStringLiteral("label")).toString(),
                               profile.value(QStringLiteral("profile_id")).toString());
    if (profile.value(QStringLiteral("default")).toBool()) {
      ui_->profileCombo->setCurrentIndex(ui_->profileCombo->count() - 1);
    }
  }
}

void MainWindow::rebuildParameterEditors() {
  while (ui_->parametersFormLayout->count() > 0) {
    if (auto* child = ui_->parametersFormLayout->takeAt(0)) {
      delete child->widget();
      delete child;
    }
  }
  parameterEditors_.clear();
  const auto& simulation = contracts_->simulation(currentSimulationId());
  const auto& variant = contracts_->variant(currentSimulationId(), currentVariantId());
  auto parameters = simulation.parameters;
  parameters.append(variant.parameters);
  for (const auto& definition : parameters) {
    QWidget* editor = nullptr;
    if (definition.type == QStringLiteral("integer")) {
      auto* spin = new QSpinBox(ui_->parametersContainer);
      spin->setRange(definition.minimum.toInt(std::numeric_limits<int>::lowest()),
                     definition.maximum.toInt(std::numeric_limits<int>::max()));
      spin->setSingleStep(std::max(1, definition.step.toInt(1)));
      spin->setValue(definition.defaultValue.toInt());
      editor = spin;
    } else if (definition.type == QStringLiteral("number")) {
      auto* spin = new QDoubleSpinBox(ui_->parametersContainer);
      spin->setDecimals(6);
      spin->setRange(definition.minimum.isUndefined() ? -1e12 : definition.minimum.toDouble(),
                     definition.maximum.isUndefined() ? 1e12 : definition.maximum.toDouble());
      spin->setSingleStep(definition.step.toDouble(0.1));
      spin->setValue(definition.defaultValue.toDouble());
      editor = spin;
    } else if (definition.type == QStringLiteral("boolean")) {
      auto* check = new QCheckBox(ui_->parametersContainer);
      check->setChecked(definition.defaultValue.toBool());
      editor = check;
    } else {
      auto* line = new QLineEdit(definition.defaultValue.toString(), ui_->parametersContainer);
      editor = line;
    }
    editor->setObjectName(QStringLiteral("parameter_%1").arg(definition.id));
    editor->setToolTip(QStringLiteral("%1\nGroupe : %2 · sûreté : %3")
                           .arg(definition.description, definition.group, definition.safetyClass));
    const auto labelText = definition.unit.isEmpty() ? definition.label
                                                     : QStringLiteral("%1 [%2]").arg(definition.label, definition.unit);
    ui_->parametersFormLayout->addRow(labelText, editor);
    parameterEditors_.insert(definition.id, editor);
  }
}

QJsonObject MainWindow::parameterValues() const {
  QJsonObject parameters;
  for (auto iterator = parameterEditors_.cbegin(); iterator != parameterEditors_.cend(); ++iterator) {
    if (const auto* spin = qobject_cast<QSpinBox*>(iterator.value())) {
      parameters.insert(iterator.key(), spin->value());
    } else if (const auto* spin = qobject_cast<QDoubleSpinBox*>(iterator.value())) {
      parameters.insert(iterator.key(), spin->value());
    } else if (const auto* check = qobject_cast<QCheckBox*>(iterator.value())) {
      parameters.insert(iterator.key(), check->isChecked());
    } else if (const auto* line = qobject_cast<QLineEdit*>(iterator.value())) {
      parameters.insert(iterator.key(), line->text());
    }
  }
  return parameters;
}

QJsonObject MainWindow::currentRequest() const {
  return contracts_->resolveRequest(currentSimulationId(), currentVariantId(), ui_->profileCombo->currentData().toString(),
                                    ui_->datasetCombo->currentData().toString(), ui_->sequenceCombo->currentData().toString(),
                                    parameterValues());
}

void MainWindow::startRun() {
  try {
    const auto request = currentRequest();
    activeRun_ = runners_->prepare(request);
    if (telemetry_) {
      telemetry_->reset();
    }
    ui_->trajectoryView->clear();
    liveAteCurve_.clear();
    processLineBuffer_.clear();
    ui_->runProgressBar->setRange(0, 100);
    ui_->runProgressBar->setValue(0);
    ui_->runProgressBar->setFormat(QStringLiteral("Initialisation…"));
    ui_->runProgressBar->setVisible(true);
    process_.setProgram(activeRun_->program);
    process_.setArguments(activeRun_->arguments);
    process_.setWorkingDirectory(activeRun_->workingDirectory);
    auto environment = QProcessEnvironment::systemEnvironment();
    environment.insert(QStringLiteral("FASTLIO_DASHBOARD"), QStringLiteral("1"));
    environment.insert(QStringLiteral("LIO_DASHBOARD"), QStringLiteral("1"));
    process_.setProcessEnvironment(environment);
    ui_->logsEdit->clear();
    appendLog(QStringLiteral("Lancement %1 · %2").arg(activeRun_->simulationId, activeRun_->variantId));
    appendLog(QStringLiteral("Commande approuvée : %1 %2").arg(activeRun_->program, activeRun_->arguments.join(QLatin1Char(' '))));
    process_.start();
    setRunState(true, QStringLiteral("Démarrage de %1…").arg(activeRun_->runId));
  } catch (const std::exception& error) {
    QMessageBox::warning(this, QStringLiteral("Lancement refusé"), QString::fromUtf8(error.what()));
  }
}

void MainWindow::stopRun() {
  if (process_.state() == QProcess::NotRunning) {
    return;
  }
  appendLog(QStringLiteral("Arrêt demandé. PX4 conserve la gestion du failsafe et de l'atterrissage."));
  if (activeRun_ && !activeRun_->stopProgram.isEmpty()) {
    const auto stopCode = QProcess::execute(activeRun_->stopProgram, activeRun_->stopArguments);
    appendLog(stopCode == 0 ? QStringLiteral("Commande d'arrêt sûr transmise au runner.")
                            : QStringLiteral("Le runner n'a pas confirmé la commande d'arrêt (code %1).").arg(stopCode));
  }
  process_.terminate();
  QTimer::singleShot(15000, &process_, [this] {
    if (process_.state() != QProcess::NotRunning) {
      appendLog(QStringLiteral("Délai d'arrêt dépassé, terminaison forcée du runner client."));
      process_.kill();
    }
  });
  ui_->runStatusLabel->setText(QStringLiteral("Arrêt sûr demandé…"));
}

void MainWindow::processOutput() {
  const auto standard = process_.readAllStandardOutput();
  const auto errors = process_.readAllStandardError();
  if (!standard.isEmpty()) {
    const auto text = QString::fromUtf8(standard);
    consumeRunnerProgress(text);
    appendLog(text);
  }
  if (!errors.isEmpty()) {
    appendLog(QString::fromUtf8(errors));
  }
}

void MainWindow::updateLiveTelemetry() {
  if (!telemetry_) {
    return;
  }
  const auto snapshot = telemetry_->snapshot();
  setTelemetryConnectionState(snapshot.available);
  if (!snapshot.available || process_.state() == QProcess::NotRunning) {
    return;
  }
  QList<TrajectorySeries> trajectories;
  if (!snapshot.estimate.isEmpty()) {
    trajectories.append({QStringLiteral("Estimation"), comparisonColors.at(0), snapshot.estimate, false});
  }
  if (!snapshot.truth.isEmpty()) {
    trajectories.append({QStringLiteral("Vérité terrain"), QColor(QStringLiteral("#ffd166")), snapshot.truth, true});
  }
  if (!snapshot.px4Path.isEmpty()) {
    trajectories.append({QStringLiteral("PX4"), QColor(QStringLiteral("#74e3a8")), snapshot.px4Path, false});
  }
  ui_->trajectoryView->setPointCloud(snapshot.cloud);
  ui_->trajectoryView->setSeries(trajectories);

  const QList<std::tuple<QString, QString, QString>> definitions{
      {QStringLiteral("ate_rmse_m"), QStringLiteral("ATE RMSE"), QStringLiteral("m")},
      {QStringLiteral("cpu_percent_one_core"), QStringLiteral("CPU (un cœur)"), QStringLiteral("%")},
      {QStringLiteral("cpu_total_seconds"), QStringLiteral("CPU cumulé"), QStringLiteral("s")},
      {QStringLiteral("memory_rss_mib"), QStringLiteral("Mémoire RSS"), QStringLiteral("Mio")},
      {QStringLiteral("odometry_count"), QStringLiteral("Odométries"), QStringLiteral("pose")},
      {QStringLiteral("reference_count"), QStringLiteral("Références"), QStringLiteral("pose")},
      {QStringLiteral("output_ratio_percent"), QStringLiteral("Sorties / références"), QStringLiteral("%")},
      {QStringLiteral("pipeline_scans_received"), QStringLiteral("Scans reçus"), QStringLiteral("scan")},
      {QStringLiteral("pipeline_odometry_published"), QStringLiteral("Odométries publiées"), QStringLiteral("pose")},
      {QStringLiteral("map_point_count"), QStringLiteral("Points de carte conservés"), QStringLiteral("point")},
      {QStringLiteral("cloud_frame_count"), QStringLiteral("Trames LiDAR intégrées"), QStringLiteral("trame")},
      {QStringLiteral("map_capacity_percent"), QStringLiteral("Capacité de carte utilisée"), QStringLiteral("%")},
      {QStringLiteral("map_voxel_size_m"), QStringLiteral("Voxel d'affichage effectif"), QStringLiteral("m")},
      {QStringLiteral("map_compaction_count"), QStringLiteral("Compactions de carte"), QStringLiteral("opération")},
  };
  ui_->liveMetricsTable->setRowCount(definitions.size());
  for (qsizetype row = 0; row < definitions.size(); ++row) {
    const auto& [id, label, unit] = definitions.at(row);
    const auto value = snapshot.metrics.value(id);
    ui_->liveMetricsTable->setItem(row, 0, item(label));
    ui_->liveMetricsTable->setItem(row, 1, item(value.isDouble() ? QString::number(value.toDouble(), 'f', 3)
                                                                 : QStringLiteral("—")));
    ui_->liveMetricsTable->setItem(row, 2, item(unit));
  }
  const auto ate = snapshot.metrics.value(QStringLiteral("ate_rmse_m"));
  if (ate.isDouble()) {
    liveAteCurve_.append(QPointF(liveAteCurve_.size() * telemetryTimer_.interval() / 1000.0, ate.toDouble()));
    while (liveAteCurve_.size() > 1200) {
      liveAteCurve_.removeFirst();
    }
    ui_->liveMetricsPlot->setSeries(
        {CurveSeries{QStringLiteral("ATE RMSE"), QStringLiteral("m"), comparisonColors.at(0), liveAteCurve_}});
  }
}

void MainWindow::setTelemetryConnectionState(const bool connected) {
  if (telemetryConnected_ == connected) {
    return;
  }
  telemetryConnected_ = connected;
  ui_->liveBadgeLabel->setProperty("connected", connected);
  ui_->liveBadgeLabel->setText(connected ? QStringLiteral("DIRECT") : QStringLiteral("EN ATTENTE"));
  ui_->liveBadgeLabel->style()->unpolish(ui_->liveBadgeLabel);
  ui_->liveBadgeLabel->style()->polish(ui_->liveBadgeLabel);
}

void MainWindow::processFinished(const int exitCode, const QProcess::ExitStatus exitStatus) {
  processOutput();
  const auto run = activeRun_;
  const auto successful = exitStatus == QProcess::NormalExit && exitCode == 0;
  ui_->runProgressBar->setValue(successful ? 100 : ui_->runProgressBar->value());
  ui_->runProgressBar->setFormat(successful ? QStringLiteral("Terminé") : QStringLiteral("Échec · consulter le journal"));
  appendLog(QStringLiteral("Runner terminé · code %1 · %2").arg(exitCode).arg(successful ? QStringLiteral("succès") : QStringLiteral("échec")));
  if (successful && run) {
    try {
      if (!QFileInfo(run->resultDirectory).isDir()) {
        throw core::ContractError(QStringLiteral("Le runner a terminé sans créer le dossier de résultat : %1")
                                      .arg(run->resultDirectory));
      }
      const auto normalized = core::normalizeResultDirectory(run->resultDirectory);
      core::writeNativeContracts(normalized, run->request);
      appendLog(QStringLiteral("Contrats T0 natifs archivés et validés."));
    } catch (const std::exception& error) {
      appendLog(QStringLiteral("Archivage T0 incomplet : %1").arg(QString::fromUtf8(error.what())));
    }
  } else if (run && QFileInfo(run->resultDirectory).isDir()) {
    appendLog(QStringLiteral("Résultat partiel conservé pour diagnostic, sans archivage T0 : %1")
                  .arg(run->resultDirectory));
  }
  activeRun_.reset();
  setRunState(false, successful ? QStringLiteral("Exécution terminée") : QStringLiteral("Exécution terminée avec erreur"));
  refreshHistory();
}

void MainWindow::setRunState(const bool running, const QString& message) {
  ui_->startButton->setEnabled(!running);
  ui_->stopButton->setEnabled(running);
  ui_->selectionGroup->setEnabled(!running);
  ui_->parametersGroup->setEnabled(!running);
  ui_->runStatusLabel->setText(message);
  setGlobalStatus(running ? QStringLiteral("EXÉCUTION ACTIVE") : QStringLiteral("PRÊT"));
}

void MainWindow::refreshHistory() {
  if (!repository_) {
    return;
  }
  try {
    repository_->refresh();
    populateFilterChoices();
    populateHistoryTable(historyFilters());
    setGlobalStatus(QStringLiteral("PRÊT · %1 résultats · %2 invalides")
                        .arg(repository_->totalCount())
                        .arg(repository_->invalidResultCount()),
                    repository_->invalidResultCount() > 0);
    statusBar()->showMessage(QStringLiteral("Index reconstruit depuis les archives"), 5000);
  } catch (const std::exception& error) {
    QMessageBox::warning(this, QStringLiteral("Indexation impossible"), QString::fromUtf8(error.what()));
  }
}

void MainWindow::populateFilterChoices() {
  const auto all = repository_->search();
  const auto preserve = [](QComboBox* combo, const QString& placeholder, const QSet<QString>& values) {
    const auto current = combo->currentData().toString();
    QSignalBlocker blocker(combo);
    combo->clear();
    combo->addItem(placeholder, QString{});
    auto ordered = values.values();
    std::sort(ordered.begin(), ordered.end());
    for (const auto& value : ordered) {
      if (!value.isEmpty()) {
        combo->addItem(value, value);
      }
    }
    MainWindow::selectComboData(combo, current);
  };
  QSet<QString> domains;
  QSet<QString> algorithms;
  QSet<QString> states;
  for (const auto& result : all) {
    domains.insert(result.domain);
    algorithms.insert(result.variantId);
    states.insert(result.state);
  }
  preserve(ui_->domainFilterCombo, QStringLiteral("Tous les domaines"), domains);
  preserve(ui_->algorithmFilterCombo, QStringLiteral("Tous les algorithmes/scénarios"), algorithms);
  preserve(ui_->stateFilterCombo, QStringLiteral("Tous les états"), states);
}

core::SearchFilters MainWindow::historyFilters() const {
  return core::SearchFilters{
      ui_->domainFilterCombo->currentData().toString(),
      {},
      {},
      ui_->algorithmFilterCombo->currentData().toString(),
      ui_->stateFilterCombo->currentData().toString(),
      ui_->tagFilterEdit->text().trimmed(),
      ui_->dateFromEdit->date() == ui_->dateFromEdit->minimumDate() ? QDate{} : ui_->dateFromEdit->date(),
      ui_->dateToEdit->date() == ui_->dateToEdit->minimumDate() ? QDate{} : ui_->dateToEdit->date(),
  };
}

void MainWindow::populateHistoryTable(const core::SearchFilters& filters) {
  const auto checkedIds = checkedResultIds();
  const QSet<QString> checked(checkedIds.cbegin(), checkedIds.cend());
  visibleResults_ = repository_->search(filters);
  ui_->historyTable->setSortingEnabled(false);
  ui_->historyTable->setRowCount(visibleResults_.size());
  for (qsizetype row = 0; row < visibleResults_.size(); ++row) {
    const auto& result = visibleResults_.at(row);
    auto* check = item(QString{});
    check->setCheckState(checked.contains(result.resultId) ? Qt::Checked : Qt::Unchecked);
    check->setData(Qt::UserRole, result.resultId);
    ui_->historyTable->setItem(row, 0, check);
    ui_->historyTable->setItem(row, 1, item(result.createdAtUtc.toString(QStringLiteral("yyyy-MM-dd HH:mm:ss"))));
    ui_->historyTable->setItem(row, 2, item(result.domain));
    ui_->historyTable->setItem(row, 3, item(result.variantId));
    ui_->historyTable->setItem(row, 4, item(result.runId));
    ui_->historyTable->setItem(row, 5, item(datasetReferenceText(result)));
    ui_->historyTable->setItem(row, 6, item(result.sequenceId));
    ui_->historyTable->setItem(row, 7, item(result.state));
    ui_->historyTable->setItem(row, 8, item(result.metricsStatus));
  }
  ui_->historyTable->setSortingEnabled(true);
  ui_->historyTable->resizeColumnsToContents();
}

void MainWindow::applyHistoryFilters() { populateHistoryTable(historyFilters()); }

void MainWindow::resetHistoryFilters() {
  ui_->domainFilterCombo->setCurrentIndex(0);
  ui_->algorithmFilterCombo->setCurrentIndex(0);
  ui_->stateFilterCombo->setCurrentIndex(0);
  ui_->tagFilterEdit->clear();
  ui_->dateFromEdit->setDate(ui_->dateFromEdit->minimumDate());
  ui_->dateToEdit->setDate(ui_->dateToEdit->minimumDate());
  populateHistoryTable();
}

void MainWindow::historySelectionChanged() {
  const auto selected = ui_->historyTable->selectedItems();
  if (selected.isEmpty()) {
    return;
  }
  const auto row = selected.front()->row();
  const auto* check = ui_->historyTable->item(row, 0);
  if (!check) {
    return;
  }
  selectedResultId_ = check->data(Qt::UserRole).toString();
  try {
    showResultDetail(repository_->detail(selectedResultId_));
  } catch (const std::exception& error) {
    QMessageBox::warning(this, QStringLiteral("Fiche indisponible"), QString::fromUtf8(error.what()));
  }
}

void MainWindow::showResultDetail(const core::ResultDetail& detail) {
  const auto& summary = detail.summary;
  ui_->detailTitleLabel->setText(QStringLiteral("%1 · %2").arg(summary.variantId, summary.runId));
  ui_->detailSummaryLabel->setText(QStringLiteral("%1 · %2 · %3\n%4")
                                       .arg(summary.domain, summary.state, summary.metricsStatus, summary.relativeDirectory));
  const auto metrics = detail.metrics.value(QStringLiteral("summary")).toArray();
  ui_->detailMetricsTable->setRowCount(metrics.size());
  for (qsizetype row = 0; row < metrics.size(); ++row) {
    const auto metric = metrics.at(row).toObject();
    ui_->detailMetricsTable->setItem(row, 0, item(metric.value(QStringLiteral("label")).toString()));
    ui_->detailMetricsTable->setItem(row, 1, item(displayValue(metric.value(QStringLiteral("value")))));
    ui_->detailMetricsTable->setItem(row, 2, item(metric.value(QStringLiteral("unit")).toString()));
    ui_->detailMetricsTable->setItem(row, 3, item(metric.value(QStringLiteral("status")).toString()));
  }
  ui_->detailMetricsTable->resizeColumnsToContents();
  ui_->detailEventsTable->setRowCount(detail.events.size());
  for (qsizetype row = 0; row < detail.events.size(); ++row) {
    const auto event = detail.events.at(row).toObject();
    const auto time = event.contains(QStringLiteral("elapsed_s"))
                          ? QStringLiteral("%1 s").arg(event.value(QStringLiteral("elapsed_s")).toDouble(), 0, 'f', 2)
                          : event.value(QStringLiteral("timestamp_utc")).toString();
    ui_->detailEventsTable->setItem(row, 0, item(time));
    ui_->detailEventsTable->setItem(row, 1, item(event.value(QStringLiteral("event_type")).toString()));
    ui_->detailEventsTable->setItem(row, 2, item(event.value(QStringLiteral("state")).toString()));
    ui_->detailEventsTable->setItem(row, 3, item(event.value(QStringLiteral("message")).toString()));
  }
  ui_->detailEventsTable->resizeColumnsToContents();
  ui_->detailJsonEdit->setPlainText(QString::fromUtf8(QJsonDocument(detail.manifest).toJson(QJsonDocument::Indented)));
  ui_->replayButton->setEnabled(summary.replayAvailable);
  ui_->duplicateButton->setEnabled(summary.duplicateAvailable);
}

void MainWindow::replaySelectedResult() {
  if (selectedResultId_.isEmpty()) {
    return;
  }
  try {
    const auto detail = repository_->detail(selectedResultId_);
    const auto replay = repository_->replay(selectedResultId_);
    showReplay(replay, resultLabel(detail.summary));
    ui_->mainTabs->setCurrentWidget(ui_->executionTab);
    statusBar()->showMessage(QStringLiteral("Archive rechargée sans relancer l'algorithme"), 6000);
  } catch (const std::exception& error) {
    QMessageBox::warning(this, QStringLiteral("Rechargement impossible"), QString::fromUtf8(error.what()));
  }
}

void MainWindow::showReplay(const core::ReplayData& replay, const QString& label) {
  ui_->trajectoryView->clear();
  QList<TrajectorySeries> trajectories;
  if (!replay.estimate.isEmpty()) {
    trajectories.append(TrajectorySeries{label, comparisonColors.at(0), replay.estimate, false});
  }
  if (!replay.truth.isEmpty()) {
    trajectories.append(TrajectorySeries{QStringLiteral("Vérité terrain"), QColor(QStringLiteral("#ffd166")), replay.truth, true});
  }
  if (!replay.px4Path.isEmpty()) {
    trajectories.append(TrajectorySeries{label, comparisonColors.at(0), replay.px4Path, false});
  }
  ui_->trajectoryView->setSeries(trajectories);
  ui_->trajectoryView->resetView();
  ui_->liveMetricsPlot->setSeries({CurveSeries{replay.curveLabel, replay.curveUnit, comparisonColors.at(0), replay.curve}});
}

void MainWindow::duplicateSelectedResult() {
  if (selectedResultId_.isEmpty()) {
    return;
  }
  try {
    const auto detail = repository_->detail(selectedResultId_);
    const auto request = detail.duplicateRequest;
    if (request.isEmpty()) {
      throw core::ContractError(QStringLiteral("La configuration exacte n'est pas archivée"));
    }
    selectComboData(ui_->simulationCombo, request.value(QStringLiteral("simulation_id")).toString());
    simulationChanged();
    selectComboData(ui_->variantCombo, request.value(QStringLiteral("variant_id")).toString());
    variantChanged();
    const auto inputs = request.value(QStringLiteral("inputs")).toArray();
    const auto reference = inputs.isEmpty() ? QJsonObject{}
                                            : inputs.at(0).toObject().value(QStringLiteral("reference")).toObject();
    selectComboData(ui_->datasetCombo, reference.value(QStringLiteral("dataset_id")).toString());
    populateDatasetSequences();
    selectComboData(ui_->sequenceCombo, reference.value(QStringLiteral("sequence_id")).toString());
    selectComboData(ui_->profileCombo, request.value(QStringLiteral("profile_id")).toString());
    const auto parameters = request.value(QStringLiteral("parameters")).toObject();
    for (auto iterator = parameterEditors_.cbegin(); iterator != parameterEditors_.cend(); ++iterator) {
      const auto value = parameters.value(iterator.key());
      if (auto* spin = qobject_cast<QSpinBox*>(iterator.value())) {
        spin->setValue(value.toInt(spin->value()));
      } else if (auto* spin = qobject_cast<QDoubleSpinBox*>(iterator.value())) {
        spin->setValue(value.toDouble(spin->value()));
      } else if (auto* check = qobject_cast<QCheckBox*>(iterator.value())) {
        check->setChecked(value.toBool(check->isChecked()));
      } else if (auto* line = qobject_cast<QLineEdit*>(iterator.value())) {
        line->setText(value.toString());
      }
    }
    ui_->mainTabs->setCurrentWidget(ui_->executionTab);
    ui_->runStatusLabel->setText(QStringLiteral("Configuration dupliquée · lancement manuel requis"));
  } catch (const std::exception& error) {
    QMessageBox::warning(this, QStringLiteral("Duplication impossible"), QString::fromUtf8(error.what()));
  }
}

void MainWindow::openSelectedResultFolder() {
  if (selectedResultId_.isEmpty()) {
    return;
  }
  try {
    const auto detail = repository_->detail(selectedResultId_);
    const auto path = QDir(repository_->resultsRoot()).filePath(detail.summary.relativeDirectory);
    QDesktopServices::openUrl(QUrl::fromLocalFile(path));
  } catch (const std::exception& error) {
    QMessageBox::warning(this, QStringLiteral("Dossier indisponible"), QString::fromUtf8(error.what()));
  }
}

QStringList MainWindow::checkedResultIds() const {
  QStringList ids;
  for (int row = 0; row < ui_->historyTable->rowCount(); ++row) {
    const auto* value = ui_->historyTable->item(row, 0);
    if (value && value->checkState() == Qt::Checked) {
      ids.append(value->data(Qt::UserRole).toString());
    }
  }
  return ids;
}

void MainWindow::compareSelectedResults() {
  const auto ids = checkedResultIds();
  try {
    const auto comparison = comparisons_->compare(ids);
    comparisonReport_ = comparison.markdownReport;
    showComparison(comparison.preview, ids);
    ui_->comparisonReportEdit->setPlainText(comparisonReport_);
    ui_->exportReportButton->setEnabled(true);
    ui_->mainTabs->setCurrentWidget(ui_->comparisonTab);
  } catch (const std::exception& error) {
    QMessageBox::warning(this, QStringLiteral("Comparaison refusée"), QString::fromUtf8(error.what()));
  }
}

void MainWindow::showComparison(const QJsonObject& comparison, const QStringList& resultIds) {
  const auto compatibility = comparison.value(QStringLiteral("compatibility")).toObject();
  const auto runs = comparison.value(QStringLiteral("runs")).toArray();
  const auto compatible = compatibility.value(QStringLiteral("compatible")).toBool();
  ui_->comparisonStatusLabel->setText(compatible
                                          ? QStringLiteral("Compatibilité validée · %1 exécutions · %2 métriques communes")
                                                .arg(runs.size())
                                                .arg(compatibility.value(QStringLiteral("common_metric_ids")).toArray().size())
                                          : QStringLiteral("Comparaison refusée · %1")
                                                .arg(displayValue(compatibility.value(QStringLiteral("reasons")))));

  QStringList runLabels;
  for (const auto& value : runs) {
    runLabels.append(value.toObject().value(QStringLiteral("label")).toString());
  }
  const auto metrics = comparison.value(QStringLiteral("metrics")).toArray();
  ui_->comparisonMetricsTable->setRowCount(metrics.size());
  ui_->comparisonMetricsTable->setColumnCount(2 + runs.size());
  ui_->comparisonMetricsTable->setHorizontalHeaderLabels(QStringList{QStringLiteral("Métrique"), QStringLiteral("Unité")} + runLabels);
  for (qsizetype row = 0; row < metrics.size(); ++row) {
    const auto metric = metrics.at(row).toObject();
    ui_->comparisonMetricsTable->setItem(row, 0, item(metric.value(QStringLiteral("label")).toString()));
    ui_->comparisonMetricsTable->setItem(row, 1, item(metric.value(QStringLiteral("unit")).toString()));
    const auto best = metric.value(QStringLiteral("best_result_ids")).toArray();
    const auto values = metric.value(QStringLiteral("values")).toArray();
    for (qsizetype column = 0; column < values.size(); ++column) {
      const auto value = values.at(column).toObject();
      auto* cell = item(displayValue(value.value(QStringLiteral("value"))));
      if (best.contains(value.value(QStringLiteral("result_id")))) {
        cell->setText(cell->text() + QStringLiteral(" ★"));
        cell->setBackground(QColor(QStringLiteral("#14533f")));
        cell->setForeground(QColor(QStringLiteral("#ffffff")));
      }
      ui_->comparisonMetricsTable->setItem(row, 2 + column, cell);
    }
  }
  ui_->comparisonMetricsTable->resizeColumnsToContents();

  const auto parameters = comparison.value(QStringLiteral("parameters")).toArray();
  ui_->comparisonParametersTable->setRowCount(parameters.size());
  ui_->comparisonParametersTable->setColumnCount(2 + runs.size());
  ui_->comparisonParametersTable->setHorizontalHeaderLabels(QStringList{QStringLiteral("Paramètre"), QStringLiteral("Identique")} + runLabels);
  for (qsizetype row = 0; row < parameters.size(); ++row) {
    const auto parameter = parameters.at(row).toObject();
    ui_->comparisonParametersTable->setItem(row, 0, item(parameter.value(QStringLiteral("parameter_id")).toString()));
    ui_->comparisonParametersTable->setItem(row, 1, item(parameter.value(QStringLiteral("same_for_all")).toBool()
                                                                ? QStringLiteral("oui")
                                                                : QStringLiteral("non")));
    const auto values = parameter.value(QStringLiteral("values")).toArray();
    for (qsizetype column = 0; column < values.size(); ++column) {
      ui_->comparisonParametersTable->setItem(row, 2 + column,
                                              item(displayValue(values.at(column).toObject().value(QStringLiteral("value")))));
    }
  }
  ui_->comparisonParametersTable->resizeColumnsToContents();

  const auto versions = comparison.value(QStringLiteral("versions")).toArray();
  ui_->comparisonVersionsTable->setRowCount(versions.size());
  ui_->comparisonVersionsTable->setColumnCount(7);
  ui_->comparisonVersionsTable->setHorizontalHeaderLabels({QStringLiteral("Exécution"), QStringLiteral("Runner"),
                                                            QStringLiteral("Algorithme"), QStringLiteral("Source"),
                                                            QStringLiteral("Contrat"), QStringLiteral("Schéma processus"),
                                                            QStringLiteral("Code sortie")});
  for (qsizetype row = 0; row < versions.size(); ++row) {
    const auto version = versions.at(row).toObject();
    const auto run = runs.at(row).toObject();
    const QList<QJsonValue> values{run.value(QStringLiteral("label")), version.value(QStringLiteral("runner_id")),
                                   version.value(QStringLiteral("algorithm")), version.value(QStringLiteral("source_kind")),
                                   version.value(QStringLiteral("result_contract_version")),
                                   version.value(QStringLiteral("process_schema_version")),
                                   version.value(QStringLiteral("process_exit_code"))};
    for (qsizetype column = 0; column < values.size(); ++column) {
      ui_->comparisonVersionsTable->setItem(row, column, item(displayValue(values.at(column))));
    }
  }
  ui_->comparisonVersionsTable->resizeColumnsToContents();

  QList<TrajectorySeries> trajectories;
  QList<CurveSeries> curves;
  bool truthAdded = false;
  if (compatible && compatibility.value(QStringLiteral("overlay_available")).toBool()) {
    try {
      for (qsizetype index = 0; index < resultIds.size(); ++index) {
        QApplication::processEvents(QEventLoop::ExcludeUserInputEvents);
        const auto replay = repository_->replay(resultIds.at(index));
        const auto color = comparisonColors.at(index);
        const auto points = replay.domain == QStringLiteral("localization") ? replay.estimate : replay.px4Path;
        trajectories.append(TrajectorySeries{runLabels.at(index), color, points, false});
        if (!truthAdded && !replay.truth.isEmpty()) {
          trajectories.append(TrajectorySeries{QStringLiteral("Vérité terrain"), QColor(QStringLiteral("#ffd166")), replay.truth, true});
          truthAdded = true;
        }
        if (!replay.curve.isEmpty()) {
          curves.append(CurveSeries{runLabels.at(index), replay.curveUnit, color, replay.curve});
        }
      }
    } catch (const std::exception& error) {
      ui_->comparisonStatusLabel->setText(ui_->comparisonStatusLabel->text() +
                                          QStringLiteral(" · superposition indisponible : %1").arg(QString::fromUtf8(error.what())));
    }
  }
  ui_->comparisonTrajectoryView->clear();
  ui_->comparisonTrajectoryView->setSeries(trajectories);
  ui_->comparisonTrajectoryView->resetView();
  ui_->comparisonMetricsPlot->setSeries(curves);
}

void MainWindow::exportComparisonReport() {
  if (comparisonReport_.isEmpty()) {
    return;
  }
  const auto path = QFileDialog::getSaveFileName(this, QStringLiteral("Exporter le rapport"),
                                                 QStringLiteral("comparaison_t0.md"), QStringLiteral("Markdown (*.md)"));
  if (path.isEmpty()) {
    return;
  }
  QSaveFile file(path);
  if (!file.open(QIODevice::WriteOnly | QIODevice::Text)) {
    QMessageBox::warning(this, QStringLiteral("Export impossible"), QStringLiteral("Le fichier ne peut pas être écrit."));
    return;
  }
  file.write(comparisonReport_.toUtf8());
  if (!file.commit()) {
    QMessageBox::warning(this, QStringLiteral("Export impossible"), QStringLiteral("Le fichier n'a pas pu être validé."));
  }
}

void MainWindow::appendLog(const QString& text) {
  for (const auto& line : text.split(QLatin1Char('\n'), Qt::SkipEmptyParts)) {
    ui_->logsEdit->appendPlainText(line);
  }
}

void MainWindow::consumeRunnerProgress(const QString& text) {
  processLineBuffer_.append(text);
  static const QRegularExpression progressExpression(
      QStringLiteral("^LIO_PROGRESS stage=([a-z_]+) percent=(\\d+)(?: current_s=([0-9.]+) total_s=([0-9.]+))?$"));
  while (true) {
    const auto newline = processLineBuffer_.indexOf(QLatin1Char('\n'));
    if (newline < 0) {
      break;
    }
    const auto line = processLineBuffer_.left(newline).trimmed();
    processLineBuffer_.remove(0, newline + 1);
    const auto match = progressExpression.match(line);
    if (!match.hasMatch()) {
      continue;
    }
    const auto stage = match.captured(1);
    const auto percent = match.captured(2).toInt();
    const QHash<QString, QString> labels{
        {QStringLiteral("initialization"), QStringLiteral("Initialisation du moteur LIO")},
        {QStringLiteral("recording"), QStringLiteral("Préparation de l'enregistrement")},
        {QStringLiteral("playback"), QStringLiteral("Rejeu du dataset")},
        {QStringLiteral("drain"), QStringLiteral("Finalisation du pipeline")},
        {QStringLiteral("artifacts"), QStringLiteral("Production des artefacts")},
        {QStringLiteral("analysis"), QStringLiteral("Analyse de la trajectoire")},
        {QStringLiteral("complete"), QStringLiteral("Exécution terminée")},
    };
    const auto label = labels.value(stage, QStringLiteral("Exécution LIO"));
    ui_->runProgressBar->setValue(percent);
    ui_->runProgressBar->setFormat(QStringLiteral("%1 · %p %").arg(label));
    if (stage == QStringLiteral("playback") && !match.captured(4).isEmpty()) {
      const auto current = static_cast<int>(std::round(match.captured(3).toDouble()));
      const auto total = static_cast<int>(std::round(match.captured(4).toDouble()));
      ui_->runStatusLabel->setText(QStringLiteral("%1 · %2 / %3 s de données").arg(label).arg(current).arg(total));
    } else {
      ui_->runStatusLabel->setText(label);
    }
  }
  if (processLineBuffer_.size() > 8192) {
    processLineBuffer_.clear();
  }
}

void MainWindow::setGlobalStatus(const QString& text, const bool error) {
  ui_->globalStatusLabel->setText(text);
  ui_->globalStatusLabel->setStyleSheet(error ? QStringLiteral("background:#692b38;color:#ffffff;border:1px solid #ef7083;border-radius:12px;padding:7px 14px;font-weight:700;")
                                               : QString{});
}

QString MainWindow::currentSimulationId() const { return ui_->simulationCombo->currentData().toString(); }

QString MainWindow::currentVariantId() const { return ui_->variantCombo->currentData().toString(); }

void MainWindow::selectComboData(QComboBox* combo, const QString& value) {
  const auto index = combo->findData(value);
  if (index >= 0) {
    combo->setCurrentIndex(index);
  }
}

void MainWindow::showAbout() {
  QMessageBox::about(this, QStringLiteral("À propos"),
                     QStringLiteral("Drone Agricole · Station de mission desktop\n\n"
                                    "C++17 · Qt 6 Widgets · contrats T0 compatibles\n"
                                    "La structure de l'interface est définie dans main_window.ui.\n\n"
                                    "PX4 conserve l'autorité de vol critique ; ROS 2 fournit les consignes et fonctions avancées."));
}

}  // namespace drone_agricole::ui
