#include "drone_agricole/ui/ComparisonPage.hpp"

#include "drone_agricole/core/JsonUtils.hpp"

#include "drone_agricole/ui/MetricsPlotWidget.hpp"
#include "drone_agricole/ui/TrajectoryView.hpp"
#include "ui_comparison_page.h"

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
#include <QSet>
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
    QColor(QStringLiteral("#087f8c")),
    QColor(QStringLiteral("#8051b5")),
    QColor(QStringLiteral("#23834d")),
    QColor(QStringLiteral("#bf4263")),
};

QTableWidgetItem* item(const QString& text) {
  auto* value = new QTableWidgetItem(text);
  value->setFlags(value->flags() & ~Qt::ItemIsEditable);
  return value;
}

QString displayValue(const QJsonValue& value) {
  return core::scalarText(value).isEmpty() ? QStringLiteral("—") : core::scalarText(value);
}



void prepareTable(QTableWidget* table) {
  table->horizontalHeader()->setStretchLastSection(true);
  table->verticalHeader()->setVisible(false);
  table->setAlternatingRowColors(true);
}

}  // namespace

ComparisonPage::ComparisonPage(application::IStationServices& services, QWidget* parent)
    : QWidget(parent), ui_(std::make_unique<Ui::ComparisonPage>()), services_(services) {
  ui_->setupUi(this);
  for (auto* table : {ui_->comparisonMetricsTable, ui_->comparisonParametersTable, ui_->comparisonVersionsTable}) prepareTable(table);
  connect(ui_->exportReportButton, &QPushButton::clicked, this, &ComparisonPage::exportComparisonReport);
  connect(ui_->compareSelectionButton, &QPushButton::clicked, this, &ComparisonPage::compareSelection);
  connect(ui_->refreshComparisonButton, &QPushButton::clicked, this, [this] {
    try { services_.refresh(); refreshResults(); }
    catch (const std::exception& error) {
      QMessageBox::warning(this, QStringLiteral("Actualisation impossible"), QString::fromUtf8(error.what()));
    }
  });
  for (auto* combo : {ui_->firstResultCombo, ui_->secondResultCombo, ui_->thirdResultCombo, ui_->fourthResultCombo}) {
    connect(combo, &QComboBox::currentIndexChanged, this, [this] {
      QStringList ids;
      for (const auto* selector : {ui_->firstResultCombo, ui_->secondResultCombo, ui_->thirdResultCombo, ui_->fourthResultCombo}) {
        const auto id = selector->currentData().toString();
        if (!id.isEmpty()) ids.append(id);
      }
      const QSet<QString> distinct(ids.cbegin(), ids.cend());
      ui_->compareSelectionButton->setEnabled(ids.size() >= 2 && distinct.size() == ids.size());
      comparisonReport_.clear();
      ui_->exportReportButton->setEnabled(false);
      ui_->comparisonReportEdit->clear();
      ui_->comparisonMetricsTable->setRowCount(0);
      ui_->comparisonParametersTable->setRowCount(0);
      ui_->comparisonVersionsTable->setRowCount(0);
      ui_->comparisonTrajectoryView->clear();
      ui_->comparisonMetricsPlot->setSeries({});
      ui_->comparisonStatusLabel->setText(QStringLiteral("Sélectionnez deux à quatre archives, puis lancez la comparaison."));
    });
  }
  refreshResults();
}
ComparisonPage::~ComparisonPage() = default;

void ComparisonPage::refreshResults() {
  const auto results = services_.search();
  QStringList previousIds;
  QStringList selectedIds;
  for (auto* combo : {ui_->firstResultCombo, ui_->secondResultCombo, ui_->thirdResultCombo, ui_->fourthResultCombo}) {
    const auto current = combo->currentData().toString();
    previousIds.append(current);
    const QSignalBlocker blocker(combo);
    combo->clear();
    combo->addItem(QStringLiteral("Sélectionner une archive"), QString{});
    for (const auto& result : results) {
      combo->addItem(QStringLiteral("%1 · %2 · %3").arg(result.variantId, result.runId, result.domain), result.resultId);
    }
    combo->setCurrentIndex(std::max(0, combo->findData(current)));
    const auto selected = combo->currentData().toString();
    if (!selected.isEmpty()) selectedIds.append(selected);
  }
  const QSet<QString> distinct(selectedIds.cbegin(), selectedIds.cend());
  ui_->compareSelectionButton->setEnabled(selectedIds.size() >= 2 && distinct.size() == selectedIds.size());
  previousIds.removeAll(QString{});
  if (selectedIds != previousIds) {
    comparisonReport_.clear();
    ui_->exportReportButton->setEnabled(false);
    ui_->comparisonReportEdit->clear();
    ui_->comparisonMetricsTable->setRowCount(0);
    ui_->comparisonParametersTable->setRowCount(0);
    ui_->comparisonVersionsTable->setRowCount(0);
    ui_->comparisonTrajectoryView->clear();
    ui_->comparisonMetricsPlot->setSeries({});
    ui_->comparisonStatusLabel->setText(QStringLiteral("Une archive sélectionnée n'est plus disponible. Choisissez une nouvelle sélection."));
  }
}

void ComparisonPage::compareSelection() {
  QStringList ids;
  for (const auto* combo : {ui_->firstResultCombo, ui_->secondResultCombo, ui_->thirdResultCombo, ui_->fourthResultCombo}) {
    const auto id = combo->currentData().toString();
    if (!id.isEmpty()) ids.append(id);
  }
  compare(ids);
}

bool ComparisonPage::compare(const QStringList& ids) {
  try {
    const auto comparison = services_.compare(ids);
    refreshResults();
    const QList<QComboBox*> combos{ui_->firstResultCombo, ui_->secondResultCombo, ui_->thirdResultCombo, ui_->fourthResultCombo};
    for (qsizetype index = 0; index < combos.size(); ++index) {
      combos.at(index)->setCurrentIndex(index < ids.size() ? std::max(0, combos.at(index)->findData(ids.at(index))) : 0);
    }
    comparisonReport_ = comparison.markdownReport;
    showComparison(comparison.preview, ids);
    ui_->comparisonReportEdit->setPlainText(comparisonReport_);
    ui_->exportReportButton->setEnabled(true);
    return true;
  } catch (const std::exception& error) {
    QMessageBox::warning(this, QStringLiteral("Comparaison refusée"), QString::fromUtf8(error.what()));
    return false;
  }
}

void ComparisonPage::exportComparisonReport() {
  if (comparisonReport_.isEmpty()) return;
  const auto path = QFileDialog::getSaveFileName(this, QStringLiteral("Exporter le rapport"),
      QStringLiteral("comparaison_t0.md"), QStringLiteral("Markdown (*.md)"));
  if (path.isEmpty()) return;
  try { services_.exportReport(path, comparisonReport_); }
  catch (const std::exception& error) { QMessageBox::warning(this, QStringLiteral("Export impossible"), QString::fromUtf8(error.what())); }
}

void ComparisonPage::showComparison(const QJsonObject& comparison, const QStringList& resultIds) {
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
        cell->setBackground(QColor(QStringLiteral("#dcfce7")));
        cell->setForeground(QColor(QStringLiteral("#166534")));
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
        const auto replay = services_.replay(resultIds.at(index));
        const auto color = comparisonColors.at(index % comparisonColors.size());
        const auto points = replay.domain == QStringLiteral("localization") ? replay.estimate : replay.px4Path;
        trajectories.append(TrajectorySeries{runLabels.at(index), color, points, false, {}});
        if (!truthAdded && !replay.truth.isEmpty()) {
          trajectories.append(TrajectorySeries{QStringLiteral("Vérité terrain"), QColor(QStringLiteral("#a26900")), replay.truth, true, {}});
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

}  // namespace drone_agricole::ui
