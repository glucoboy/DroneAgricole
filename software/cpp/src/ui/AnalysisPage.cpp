#include "drone_agricole/ui/AnalysisPage.hpp"
#include "drone_agricole/core/JsonUtils.hpp"
#include "drone_agricole/ui/MetricsPlotWidget.hpp"
#include "drone_agricole/ui/TrajectoryView.hpp"
#include "ui_analysis_page.h"

#include <QCheckBox>
#include <QComboBox>
#include <QFileDialog>
#include <QHeaderView>
#include <QMessageBox>
#include <QSignalBlocker>
#include <QTableWidgetItem>
#include <QTabBar>
#include <algorithm>

namespace drone_agricole::ui {
namespace {
QString markdownText(QString value) {
  value.replace(QLatin1Char('|'), QStringLiteral("\\|"));
  value.replace(QLatin1Char('\n'), QLatin1Char(' '));
  return value;
}
QString displayValue(const QJsonValue& value) {
  const auto text = core::scalarText(value);
  return text.isEmpty() ? QStringLiteral("—") : text;
}
QList<TrajectorySeries> trajectorySeries(const core::ReplayData& replay) {
  QList<TrajectorySeries> series;
  if (!replay.estimate.isEmpty()) series.append({QStringLiteral("Estimation"), QColor(QStringLiteral("#087f8c")), replay.estimate, false, {}});
  if (!replay.truth.isEmpty()) series.append({QStringLiteral("Vérité terrain"), QColor(QStringLiteral("#a26900")), replay.truth, true, {}});
  if (!replay.px4Path.isEmpty()) series.append({QStringLiteral("PX4"), QColor(QStringLiteral("#23834d")), replay.px4Path, false, {}});
  return series;
}
}  // namespace

AnalysisPage::AnalysisPage(application::IStationServices& services, QWidget* parent)
    : QWidget(parent), ui_(std::make_unique<Ui::AnalysisPage>()), services_(services) {
  ui_->setupUi(this);
  ui_->analysisTabs->tabBar()->hide();
  ui_->analysisMetricsTable->horizontalHeader()->setStretchLastSection(true);
  ui_->analysisMetricsTable->verticalHeader()->hide();
  connect(ui_->analysisResultCombo, &QComboBox::currentIndexChanged, this, &AnalysisPage::loadSelectedResult);
  connect(ui_->refreshAnalysisButton, &QPushButton::clicked, this, [this] {
    try { services_.refresh(); currentId_.clear(); refreshResults(); }
    catch (const std::exception& error) { ui_->analysisStatusLabel->setText(QString::fromUtf8(error.what())); }
  });
  connect(ui_->analysisSurfaceCheck, &QCheckBox::toggled, ui_->analysisMapView, &TrajectoryView::setSurfaceVisible);
  connect(ui_->analysisMapPathsCheck, &QCheckBox::toggled, ui_->analysisMapView, &TrajectoryView::setTrajectoriesVisible);
  connect(ui_->analysisFitMapButton, &QPushButton::clicked, ui_->analysisMapView, &TrajectoryView::fitToData);
  connect(ui_->analysisTopMapButton, &QPushButton::clicked, ui_->analysisMapView, &TrajectoryView::setTopView);
  connect(ui_->exportAnalysisReportButton, &QPushButton::clicked, this, &AnalysisPage::exportReport);
  connect(&services_.execution(), &application::RunService::completed, this, &AnalysisPage::refreshResults);
  refreshResults();
}
AnalysisPage::~AnalysisPage() = default;

void AnalysisPage::setSection(const QString& section) {
  const QStringList sections{QStringLiteral("maps"), QStringLiteral("trajectories"), QStringLiteral("metrics"), QStringLiteral("reports")};
  const auto index = sections.indexOf(section);
  if (index >= 0) ui_->analysisTabs->setCurrentIndex(index);
}

void AnalysisPage::refreshResults() {
  const auto selected = ui_->analysisResultCombo->currentData().toString();
  {
    const QSignalBlocker blocker(ui_->analysisResultCombo);
    ui_->analysisResultCombo->clear();
    ui_->analysisResultCombo->addItem(QStringLiteral("Sélectionner une archive"), QString{});
    for (const auto& result : services_.search()) {
      ui_->analysisResultCombo->addItem(QStringLiteral("%1 · %2 · %3").arg(result.variantId, result.runId, result.domain), result.resultId);
    }
    ui_->analysisResultCombo->setCurrentIndex(std::max(0, ui_->analysisResultCombo->findData(selected)));
  }
  loadSelectedResult();
}

void AnalysisPage::openResult(const QString& id) {
  if (ui_->analysisResultCombo->findData(id) < 0) refreshResults();
  const auto index = ui_->analysisResultCombo->findData(id);
  if (index < 0) {
    clearResult();
    ui_->analysisStatusLabel->setText(QStringLiteral("Archive introuvable : %1").arg(id));
    return;
  }
  ui_->analysisResultCombo->setCurrentIndex(index);
  loadSelectedResult();
}

void AnalysisPage::clearResult() {
  currentId_.clear(); report_.clear();
  ui_->analysisMapView->clear(); ui_->analysisTrajectoryView->clear();
  ui_->analysisMetricsPlot->setSeries({});
  ui_->analysisMetricsTable->setRowCount(0);
  ui_->analysisReportEdit->clear();
  ui_->exportAnalysisReportButton->setEnabled(false);
  ui_->analysisSurfaceCheck->setEnabled(false);
  ui_->analysisStatusLabel->setText(QStringLiteral("Sélectionnez une archive."));
  ui_->mapAvailabilityLabel->setText(QStringLiteral("Aucune carte chargée."));
  ui_->trajectoryAvailabilityLabel->setText(QStringLiteral("Aucune trajectoire chargée."));
}

void AnalysisPage::loadSelectedResult() {
  const auto id = ui_->analysisResultCombo->currentData().toString();
  if (id == currentId_ && !id.isEmpty()) return;
  clearResult();
  if (id.isEmpty()) return;
  try {
    const auto detail = services_.detail(id);
    const auto& summary = detail.summary;
    ui_->analysisStatusLabel->setText(QStringLiteral("%1 · %2 · %3").arg(summary.domain, summary.state, summary.metricsStatus));
    const auto metrics = detail.metrics.value(QStringLiteral("summary")).toArray();
    ui_->analysisMetricsTable->setRowCount(metrics.size());
    QStringList lines{QStringLiteral("# Rapport de résultat"), QString{},
        QStringLiteral("- Résultat : %1").arg(markdownText(summary.resultId)),
        QStringLiteral("- Exécution : %1").arg(markdownText(summary.runId)),
        QStringLiteral("- Domaine / variante : %1 / %2").arg(markdownText(summary.domain), markdownText(summary.variantId)),
        QStringLiteral("- Date UTC : %1").arg(summary.createdAtUtc.toString(Qt::ISODate)),
        QStringLiteral("- État : %1 ; métriques : %2").arg(markdownText(summary.state), markdownText(summary.metricsStatus)),
        QStringLiteral("- Dataset / séquence : %1 / %2").arg(markdownText(summary.datasetId), markdownText(summary.sequenceId)),
        QStringLiteral("- Scénario : %1").arg(markdownText(summary.scenarioId)),
        QStringLiteral("- Dossier source : %1").arg(markdownText(summary.relativeDirectory)),
        QString{}, QStringLiteral("## Métriques archivées"), QString{},
        QStringLiteral("| Métrique | Valeur | Unité | Statut |"), QStringLiteral("| --- | --- | --- | --- |")};
    for (qsizetype row = 0; row < metrics.size(); ++row) {
      const auto metric = metrics.at(row).toObject();
      const QStringList values{metric.value(QStringLiteral("label")).toString(), displayValue(metric.value(QStringLiteral("value"))),
          metric.value(QStringLiteral("unit")).toString(), metric.value(QStringLiteral("status")).toString()};
      for (qsizetype column = 0; column < values.size(); ++column) {
        ui_->analysisMetricsTable->setItem(row, column, new QTableWidgetItem(values.at(column)));
      }
      QStringList escaped;
      for (const auto& value : values) escaped.append(markdownText(value));
      lines.append(QStringLiteral("| %1 |").arg(escaped.join(QStringLiteral(" | "))));
    }
    ui_->analysisMetricsTable->resizeColumnsToContents();
    if (metrics.isEmpty()) lines.append(QStringLiteral("Aucune métrique de synthèse disponible."));
    if (summary.replayAvailable) {
      try {
        const auto replay = services_.replay(id);
        const auto paths = trajectorySeries(replay);
        ui_->analysisTrajectoryView->setSeries(paths);
        ui_->analysisTrajectoryView->resetView();
        auto mapSeries = paths;
        for (const auto& line : replay.mapPolylines) {
          const auto candidate = line.role == QStringLiteral("candidate_trajectory");
          const auto legend = candidate ? QStringLiteral("Trajectoires candidates · non qualifiées")
              : line.role == QStringLiteral("detected_row") ? QStringLiteral("Rangs détectés")
              : line.role == QStringLiteral("acquisition_trajectory") ? QStringLiteral("Acquisition estimée")
              : QStringLiteral("Objets cartographiques");
          mapSeries.append({line.label, QColor(candidate ? QStringLiteral("#b56612") : QStringLiteral("#8051b5")),
              line.points, candidate, legend});
        }
        ui_->analysisMapView->setPointCloud(replay.mapPoints);
        ui_->analysisMapView->setCameraProjectedPoints(replay.cameraProjectedPoints, replay.cameraPointColors);
        ui_->analysisMapView->setReferencePoints(replay.referencePoints);
        ui_->analysisMapView->setSurface(replay.surfaceVertices, replay.surfaceTriangles, replay.surfaceColors);
        ui_->analysisMapView->setSeries(mapSeries);
        ui_->analysisMapView->resetView();
        ui_->analysisSurfaceCheck->setEnabled(!replay.surfaceTriangles.isEmpty());
        ui_->mapAvailabilityLabel->setText(QStringLiteral("%1 points · %2 triangles · %3 objets%4")
            .arg(replay.mapPoints.size()).arg(replay.surfaceTriangles.size()).arg(replay.mapPolylines.size())
            .arg(replay.reconstructionPartial ? QStringLiteral(" · reconstruction partielle") : QString{}));
        ui_->trajectoryAvailabilityLabel->setText(paths.isEmpty() ? QStringLiteral("Aucune trajectoire archivée pour ce résultat.")
            : QStringLiteral("%1 trajectoire(s) issue(s) du rejeu archivé.").arg(paths.size()));
        ui_->analysisMetricsPlot->setSeries({CurveSeries{replay.curveLabel, replay.curveUnit, QColor(QStringLiteral("#087f8c")), replay.curve}});
        lines.append(QString{}); lines.append(QStringLiteral("## Notes du rejeu")); lines.append(QString{});
        for (const auto& note : replay.notes) lines.append(QStringLiteral("- %1").arg(markdownText(note)));
        if (replay.reconstructionPartial) lines.append(QStringLiteral("- Reconstruction partielle : vérifier les limites des artefacts sources."));
      } catch (const std::exception& error) {
        const auto message = QStringLiteral("Rejeu indisponible : %1").arg(QString::fromUtf8(error.what()));
        ui_->mapAvailabilityLabel->setText(message); ui_->trajectoryAvailabilityLabel->setText(message);
        lines.append(QString{}); lines.append(markdownText(message));
      }
    } else {
      ui_->mapAvailabilityLabel->setText(QStringLiteral("Ce résultat ne possède pas d'artefact de rejeu cartographique."));
      ui_->trajectoryAvailabilityLabel->setText(QStringLiteral("Ce résultat ne possède pas de trajectoire rejouable."));
    }
    lines.append(QString{}); lines.append(QStringLiteral("Ce rapport restitue les observations de l'archive. La qualification dépend du protocole de validation associé."));
    report_ = lines.join(QLatin1Char('\n')) + QLatin1Char('\n');
    ui_->analysisReportEdit->setPlainText(report_);
    ui_->exportAnalysisReportButton->setEnabled(true);
    currentId_ = id;
  } catch (const std::exception& error) {
    ui_->analysisStatusLabel->setText(QStringLiteral("Archive indisponible : %1").arg(QString::fromUtf8(error.what())));
  }
}

void AnalysisPage::exportReport() {
  if (report_.isEmpty()) return;
  const auto path = QFileDialog::getSaveFileName(this, QStringLiteral("Exporter le rapport"),
      QStringLiteral("rapport_resultat.md"), QStringLiteral("Markdown (*.md)"));
  if (path.isEmpty()) return;
  try { services_.exportReport(path, report_); }
  catch (const std::exception& error) { QMessageBox::warning(this, QStringLiteral("Export impossible"), QString::fromUtf8(error.what())); }
}
}  // namespace drone_agricole::ui
