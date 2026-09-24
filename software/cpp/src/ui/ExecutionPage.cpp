#include "drone_agricole/ui/ExecutionPage.hpp"

#include "drone_agricole/core/JsonUtils.hpp"

#include "drone_agricole/ui/MetricsPlotWidget.hpp"
#include "drone_agricole/ui/TrajectoryView.hpp"
#include "ui_execution_page.h"

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



QString resultLabel(const core::ResultSummary& summary) {
  return QStringLiteral("%1 · %2").arg(summary.variantId, summary.runId);
}

void prepareTable(QTableWidget* table) {
  table->horizontalHeader()->setStretchLastSection(true);
  table->verticalHeader()->setVisible(false);
  table->setAlternatingRowColors(true);
}

}  // namespace

ExecutionPage::ExecutionPage(application::IStationServices& services, QWidget* parent)
    : QWidget(parent), ui_(std::make_unique<Ui::ExecutionPage>()), services_(services) {
  ui_->setupUi(this);
  prepareTable(ui_->liveMetricsTable);
  connect(ui_->simulationCombo, &QComboBox::currentIndexChanged, this, &ExecutionPage::simulationChanged);
  connect(ui_->variantCombo, &QComboBox::currentIndexChanged, this, &ExecutionPage::variantChanged);
  connect(ui_->datasetCombo, &QComboBox::currentIndexChanged, this, &ExecutionPage::populateSequences);
  connect(ui_->sequenceCombo, &QComboBox::currentIndexChanged, this, &ExecutionPage::populateProfiles);
  connect(ui_->startButton, &QPushButton::clicked, this, &ExecutionPage::startRun);
  connect(ui_->stopButton, &QPushButton::clicked, &services_.execution(), &application::RunService::cancel);
  connect(&services_.execution(), &application::RunService::changed, this, &ExecutionPage::updateRunState);
  connect(&services_.execution(), &application::RunService::output, this, &ExecutionPage::appendLog);
  connect(&services_.execution(), &application::RunService::completed, this, &ExecutionPage::runCompleted);
  connect(ui_->fitMapButton, &QPushButton::clicked, ui_->trajectoryView, &TrajectoryView::fitToData);
  connect(ui_->topMapButton, &QPushButton::clicked, ui_->trajectoryView, &TrajectoryView::setTopView);
  connect(ui_->surfaceCheckBox,&QCheckBox::toggled,ui_->trajectoryView,&TrajectoryView::setSurfaceVisible);
  connect(ui_->pathCheckBox,&QCheckBox::toggled,ui_->trajectoryView,&TrajectoryView::setTrajectoriesVisible);
  connect(&telemetryTimer_, &QTimer::timeout, this, &ExecutionPage::updateLiveTelemetry);
  telemetryTimer_.start(250);
  populateSimulations();
  updateRunState();
}
ExecutionPage::~ExecutionPage() = default;

void ExecutionPage::startRun() {
  try {
    const auto request = currentRequest();
    services_.resetTelemetry();
    ui_->trajectoryView->clear();
    ui_->logsEdit->clear();
    liveAteCurve_.clear();
    services_.execution().start(request);
  } catch (const std::exception& error) {
    QMessageBox::warning(this, QStringLiteral("Lancement refusé"), QString::fromUtf8(error.what()));
  }
}

void ExecutionPage::updateRunState() {
  const auto& execution = services_.execution();
  ui_->startButton->setEnabled(!execution.active());
  ui_->stopButton->setEnabled(execution.active() && execution.state() != domain::RunState::Cancelling);
  ui_->selectionGroup->setEnabled(!execution.active());
  ui_->parametersGroup->setEnabled(!execution.active());
  ui_->runStatusLabel->setText(execution.message());
  ui_->runProgressBar->setVisible(execution.state() != domain::RunState::Idle);
  ui_->runProgressBar->setRange(0, 100);
  ui_->runProgressBar->setValue(execution.progress());
  ui_->runProgressBar->setFormat(QStringLiteral("%1 · %p %").arg(domain::stateLabel(execution.state())));
}

void ExecutionPage::runCompleted() {
  if (services_.execution().state() != domain::RunState::Completed) return;
  const auto run = services_.execution().run();
  if (!run) return;
  try {
    services_.refresh();
    for (const auto& result : services_.search()) {
      if (result.runId == run->runId && result.replayAvailable) {
        showReplay(services_.replay(result.resultId), resultLabel(result));
        appendLog(QStringLiteral("Résultat affiché automatiquement dans la carte 3D."));
        emit resultAvailable(result.resultId);
        break;
      }
    }
  } catch (const std::exception& error) {
    appendLog(QStringLiteral("Visualisation indisponible : %1").arg(QString::fromUtf8(error.what())));
  }
}

void ExecutionPage::populateSimulations() {
  QSignalBlocker blocker(ui_->simulationCombo);
  ui_->simulationCombo->clear();
  for (const auto& simulation : services_.simulations()) {
    ui_->simulationCombo->addItem(simulation.label, simulation.id);
  }
  populateVariants();
}

void ExecutionPage::simulationChanged() {
  if (services_.simulations().isEmpty()) {
    return;
  }
  populateVariants();
}

void ExecutionPage::variantChanged() {
  if (currentVariantId().isEmpty()) {
    return;
  }
  populateDatasetSequences();
  populateProfiles();
  rebuildParameterEditors();
}

void ExecutionPage::populateVariants() {
  QSignalBlocker blocker(ui_->variantCombo);
  ui_->variantCombo->clear();
  if (currentSimulationId().isEmpty()) {
    return;
  }
  try {
    for (const auto& variant : services_.simulation(currentSimulationId()).variants) {
      if (variant.available) {
        ui_->variantCombo->addItem(variant.label, variant.id);
      }
    }
  } catch (const std::exception& error) {
    appendLog(QString::fromUtf8(error.what()));
  }
  variantChanged();
}

void ExecutionPage::populateDatasetSequences() {
  QSignalBlocker datasetBlocker(ui_->datasetCombo);
  QSignalBlocker sequenceBlocker(ui_->sequenceCombo);
  ui_->datasetCombo->clear();
  ui_->sequenceCombo->clear();
  const auto& simulation = services_.simulation(currentSimulationId());
  const auto usesDataset = !simulation.selectors.isEmpty();
  ui_->datasetLabel->setVisible(usesDataset);
  ui_->datasetCombo->setVisible(usesDataset);
  ui_->sequenceLabel->setVisible(usesDataset);
  ui_->sequenceCombo->setVisible(usesDataset);
  if (!usesDataset) {
    return;
  }
  const auto compatible = services_.compatibleSequences(currentSimulationId(), currentVariantId());
  QStringList datasets;
  for (const auto& sequence : compatible) {
    if (!datasets.contains(sequence.datasetId)) {
      datasets.append(sequence.datasetId);
      ui_->datasetCombo->addItem(sequence.datasetLabel, sequence.datasetId);
    }
  }
  populateSequences();
}

void ExecutionPage::populateSequences() {
  QSignalBlocker blocker(ui_->sequenceCombo);
  ui_->sequenceCombo->clear();
  const auto compatible = services_.compatibleSequences(currentSimulationId(), currentVariantId());
  const auto selectedDataset = ui_->datasetCombo->currentData().toString();
  for (const auto& sequence : compatible) {
    if (sequence.datasetId == selectedDataset) {
      ui_->sequenceCombo->addItem(sequence.sequenceLabel, sequence.sequenceId);
      if (sequence.recommended) {
        ui_->sequenceCombo->setCurrentIndex(ui_->sequenceCombo->count() - 1);
      }
    }
  }
  populateProfiles();
}

void ExecutionPage::populateProfiles() {
  QSignalBlocker blocker(ui_->profileCombo);
  ui_->profileCombo->clear();
  const auto profiles = services_.simulation(currentSimulationId()).profiles;
  const auto visible = !profiles.isEmpty();
  ui_->profileLabel->setVisible(visible);
  ui_->profileCombo->setVisible(visible);
  for (const auto& value : profiles) {
    const auto profile = value.toObject();
    if (!profile.value(QStringLiteral("variant_settings")).toObject().contains(currentVariantId())) {
      continue;
    }
    const auto selectors = profile.value(QStringLiteral("selectors")).toObject();
    const auto dataset = selectors.value(QStringLiteral("dataset_id")).toString();
    const auto sequences = selectors.value(QStringLiteral("sequence_ids")).toArray();
    if ((!dataset.isEmpty() && dataset != ui_->datasetCombo->currentData().toString()) ||
        (!sequences.isEmpty() && !sequences.contains(ui_->sequenceCombo->currentData().toString()))) continue;
    ui_->profileCombo->addItem(profile.value(QStringLiteral("label")).toString(),
                               profile.value(QStringLiteral("profile_id")).toString());
    if (profile.value(QStringLiteral("default")).toBool()) {
      ui_->profileCombo->setCurrentIndex(ui_->profileCombo->count() - 1);
    }
  }
}

void ExecutionPage::rebuildParameterEditors() {
  while (ui_->parametersFormLayout->count() > 0) {
    if (auto* child = ui_->parametersFormLayout->takeAt(0)) {
      delete child->widget();
      delete child;
    }
  }
  parameterEditors_.clear();
  const auto& simulation = services_.simulation(currentSimulationId());
  const auto& variant = services_.variant(currentSimulationId(), currentVariantId());
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

QJsonObject ExecutionPage::parameterValues() const {
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

QJsonObject ExecutionPage::currentRequest() const {
  return services_.resolveRequest(currentSimulationId(), currentVariantId(), ui_->profileCombo->currentData().toString(),
                                    ui_->datasetCombo->currentData().toString(), ui_->sequenceCombo->currentData().toString(),
                                    parameterValues());
}

void ExecutionPage::updateLiveTelemetry() {
  if (!services_.execution().active()) return;
  const auto snapshot = services_.snapshot();
  setTelemetryConnectionState(snapshot.available);
  if (!snapshot.available || !services_.execution().active()) {
    return;
  }
  QList<TrajectorySeries> trajectories;
  if (!snapshot.estimate.isEmpty()) {
    trajectories.append({QStringLiteral("Estimation"), comparisonColors.at(0), snapshot.estimate, false, {}});
  }
  if (!snapshot.truth.isEmpty()) {
    trajectories.append({QStringLiteral("Vérité terrain"), QColor(QStringLiteral("#ffd166")), snapshot.truth, true, {}});
  }
  if (!snapshot.px4Path.isEmpty()) {
    trajectories.append({QStringLiteral("PX4"), QColor(QStringLiteral("#74e3a8")), snapshot.px4Path, false, {}});
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

void ExecutionPage::setTelemetryConnectionState(const bool connected) {
  if (telemetryConnected_ == connected) {
    return;
  }
  telemetryConnected_ = connected;
  ui_->liveBadgeLabel->setProperty("connected", connected);
  ui_->liveBadgeLabel->setText(connected ? QStringLiteral("DIRECT") : QStringLiteral("EN ATTENTE"));
  ui_->liveBadgeLabel->style()->unpolish(ui_->liveBadgeLabel);
  ui_->liveBadgeLabel->style()->polish(ui_->liveBadgeLabel);
}

void ExecutionPage::showReplay(const core::ReplayData& replay, const QString& label) {
  ui_->liveBadgeLabel->setText(replay.reconstructionPartial?QStringLiteral("CARTE PARTIELLE"):QStringLiteral("RÉSULTAT"));
  ui_->trajectoryView->clear();
  QList<TrajectorySeries> trajectories;
  if (!replay.estimate.isEmpty()) {
    trajectories.append(TrajectorySeries{label, comparisonColors.at(0), replay.estimate, false, {}});
  }
  if (!replay.truth.isEmpty()) {
    trajectories.append(TrajectorySeries{QStringLiteral("Vérité terrain"), QColor(QStringLiteral("#ffd166")), replay.truth, true, {}});
  }
  if (!replay.px4Path.isEmpty()) {
    trajectories.append(TrajectorySeries{label, comparisonColors.at(0), replay.px4Path, false, {}});
  }
  for (const auto& line : replay.mapPolylines) {
    if (line.role == QStringLiteral("detected_row")) {
      trajectories.append(TrajectorySeries{line.label, QColor(QStringLiteral("#53d8d2")), line.points, false,
                                           QStringLiteral("Rangs détectés")});
    } else if (line.role == QStringLiteral("candidate_trajectory")) {
      trajectories.append(TrajectorySeries{line.label, QColor(QStringLiteral("#ff9f68")), line.points, true,
                                           QStringLiteral("Trajectoires candidates · non qualifiées")});
    } else if (line.role == QStringLiteral("acquisition_trajectory")) {
      trajectories.append(TrajectorySeries{line.label,QColor(QStringLiteral("#ffbf69")),line.points,false,
                                           QStringLiteral("Acquisition estimée · superposition")});
    } else {
      trajectories.append(TrajectorySeries{line.label, QColor(QStringLiteral("#d98cff")), line.points, true,
                                           QStringLiteral("Objets cartographiques")});
    }
  }
  ui_->trajectoryView->setPointCloud(replay.mapPoints);
  ui_->trajectoryView->setCameraProjectedPoints(replay.cameraProjectedPoints, replay.cameraPointColors);
  ui_->trajectoryView->setReferencePoints(replay.referencePoints);
  ui_->trajectoryView->setSeries(trajectories);
  ui_->trajectoryView->setSurface(replay.surfaceVertices,replay.surfaceTriangles,replay.surfaceColors);
  ui_->surfaceCheckBox->setEnabled(!replay.surfaceTriangles.isEmpty());
  if (replay.domain == QStringLiteral("mapping") && replay.cameraPointColors.isEmpty() && replay.surfaceTriangles.isEmpty()) {
    ui_->trajectoryView->setTopView();
  } else {
    ui_->trajectoryView->resetView();
  }
  ui_->liveMetricsPlot->setSeries({CurveSeries{replay.curveLabel, replay.curveUnit, comparisonColors.at(0), replay.curve}});
  for (const auto& note : replay.notes) {
    appendLog(QStringLiteral("Carte · %1").arg(note));
  }
}

void ExecutionPage::appendLog(const QString& text) {
  for (const auto& line : text.split(QLatin1Char('\n'), Qt::SkipEmptyParts)) {
    ui_->logsEdit->appendPlainText(line);
  }
}

QString ExecutionPage::currentSimulationId() const { return ui_->simulationCombo->currentData().toString(); }

QString ExecutionPage::currentVariantId() const { return ui_->variantCombo->currentData().toString(); }

void ExecutionPage::selectComboData(QComboBox* combo, const QString& value) {
  const auto index = combo->findData(value);
  if (index >= 0) {
    combo->setCurrentIndex(index);
  }
}

void ExecutionPage::applyRequest(const QJsonObject& request) {
  if (ui_->simulationCombo->findData(request.value(QStringLiteral("simulation_id")).toString()) < 0) {
    QMessageBox::information(this, QStringLiteral("Essai historique"),
        QStringLiteral("Ce module a été retiré des nouveaux essais. Son résultat reste consultable dans les archives."));
    return;
  }
  if (services_.execution().active()) {
    QMessageBox::information(this, QStringLiteral("Traitement actif"), QStringLiteral("Attendez la fin du traitement avant de modifier sa configuration."));
    return;
  }
    selectComboData(ui_->simulationCombo, request.value(QStringLiteral("simulation_id")).toString());
    simulationChanged();
    selectComboData(ui_->variantCombo, request.value(QStringLiteral("variant_id")).toString());
    variantChanged();
    const auto inputs = request.value(QStringLiteral("inputs")).toArray();
    const auto reference = inputs.isEmpty() ? QJsonObject{}
                                            : inputs.at(0).toObject().value(QStringLiteral("reference")).toObject();
    selectComboData(ui_->datasetCombo, reference.value(QStringLiteral("dataset_id")).toString());
    populateSequences();
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
  ui_->runStatusLabel->setText(QStringLiteral("Configuration dupliquée · lancement manuel requis"));
}

}  // namespace drone_agricole::ui
