#include "drone_agricole/ui/ResultsPage.hpp"

#include "drone_agricole/core/JsonUtils.hpp"
#include "drone_agricole/application/WorkspaceService.hpp"

#include "drone_agricole/ui/MetricsPlotWidget.hpp"
#include "drone_agricole/ui/TrajectoryView.hpp"
#include "ui_results_page.h"

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

QString displayValue(const QJsonValue& value) {
  return core::scalarText(value).isEmpty() ? QStringLiteral("—") : core::scalarText(value);
}

QString datasetReferenceText(const core::ResultSummary& summary) {
  return summary.datasetId.isEmpty() ? summary.scenarioId : summary.datasetId;
}

QString csvCell(QString value) {
  // Les chaînes restent du texte lorsqu'un tableur ouvre l'export.
  if (!value.isEmpty() && QStringLiteral("=+-@\t\r").contains(value.front())) value.prepend(QLatin1Char('\''));
  value.replace(QLatin1Char('"'), QStringLiteral("\"\""));
  return QLatin1Char('"') + value + QLatin1Char('"');
}


void prepareTable(QTableWidget* table) {
  table->horizontalHeader()->setStretchLastSection(true);
  table->verticalHeader()->setVisible(false);
  table->setAlternatingRowColors(true);
}

}  // namespace

ResultsPage::ResultsPage(application::IStationServices& services, QWidget* parent)
    : QWidget(parent), ui_(std::make_unique<Ui::ResultsPage>()), services_(services) {
  ui_->setupUi(this);
  for (auto* combo : {ui_->domainFilterCombo, ui_->algorithmFilterCombo, ui_->stateFilterCombo}) {
    combo->setMinimumContentsLength(12);
    combo->setSizeAdjustPolicy(QComboBox::AdjustToMinimumContentsLengthWithIcon);
  }
  for (auto* table : {ui_->historyTable, ui_->detailMetricsTable, ui_->detailEventsTable}) prepareTable(table);
  for (auto* date : {ui_->dateFromEdit, ui_->dateToEdit}) {
    date->setMinimumDate(QDate(2000, 1, 1));
    date->setDate(date->minimumDate());
  }
  connect(ui_->refreshHistoryButton, &QPushButton::clicked, this, &ResultsPage::refreshHistory);
  connect(ui_->applyFiltersButton, &QPushButton::clicked, this, &ResultsPage::applyHistoryFilters);
  connect(ui_->resetFiltersButton, &QPushButton::clicked, this, &ResultsPage::resetHistoryFilters);
  connect(ui_->searchResultsEdit, &QLineEdit::textChanged, this, &ResultsPage::applyHistoryFilters);
  connect(ui_->favoritesOnlyCheck, &QCheckBox::toggled, this, &ResultsPage::applyHistoryFilters);
  connect(ui_->favoriteButton, &QPushButton::clicked, this, &ResultsPage::toggleFavorite);
  connect(ui_->exportCsvButton, &QPushButton::clicked, this, &ResultsPage::exportVisibleResults);
  connect(ui_->analyzeButton, &QPushButton::clicked, this, [this] {
    if (!selectedResultId_.isEmpty()) emit analysisRequested(selectedResultId_);
  });
  connect(ui_->historyTable, &QTableWidget::itemSelectionChanged, this, &ResultsPage::historySelectionChanged);
  connect(ui_->openResultFolderButton, &QPushButton::clicked, this, &ResultsPage::openSelectedResultFolder);
  connect(ui_->replayButton, &QPushButton::clicked, this, [this] {
    if (!selectedResultId_.isEmpty()) emit replayRequested(selectedResultId_);
  });
  connect(ui_->duplicateButton, &QPushButton::clicked, this, [this] {
    if (selectedResultId_.isEmpty()) return;
    try { emit duplicateRequested(services_.detail(selectedResultId_).duplicateRequest); }
    catch (const std::exception& error) { QMessageBox::warning(this, QStringLiteral("Duplication impossible"), QString::fromUtf8(error.what())); }
  });
  connect(ui_->compareButton, &QPushButton::clicked, this, [this] { emit comparisonRequested(checkedResultIds()); });
  connect(ui_->historyTable, &QTableWidget::itemChanged, this, [this] {
    const auto count = checkedResultIds().size();
    ui_->compareButton->setEnabled(count >= 2 && count <= 4);
  });
  connect(&services_.execution(), &application::RunService::completed, this, &ResultsPage::refreshHistory);
  populateFilterChoices();
  populateHistoryTable();
}
ResultsPage::~ResultsPage() = default;

void ResultsPage::refreshHistory() {
  try {
    services_.refresh();
    populateFilterChoices();
    populateHistoryTable(historyFilters());
  } catch (const std::exception& error) {
    QMessageBox::warning(this, QStringLiteral("Indexation impossible"), QString::fromUtf8(error.what()));
  }
}

void ResultsPage::selectResult(const QString& id) {
  if (id.isEmpty() || selectVisibleResult(id)) return;
  const auto results = services_.search();
  const auto exists = std::any_of(results.cbegin(), results.cend(), [&](const auto& result) { return result.resultId == id; });
  if (!exists) return;
  resetHistoryFilters();
  selectVisibleResult(id);
}

bool ResultsPage::selectVisibleResult(const QString& id) {
  for (int row = 0; row < ui_->historyTable->rowCount(); ++row) {
    if (ui_->historyTable->item(row, 0)->data(Qt::UserRole).toString() == id) {
      ui_->historyTable->selectRow(row);
      return true;
    }
  }
  return false;
}

void ResultsPage::populateFilterChoices() {
  const auto all = services_.search();
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
    ResultsPage::selectComboData(combo, current);
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

core::SearchFilters ResultsPage::historyFilters() const {
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

void ResultsPage::populateHistoryTable(const core::SearchFilters& filters) {
  const auto previousSelection = selectedResultId_;
  const QSignalBlocker selectionBlocker(ui_->historyTable);
  const auto checkedIds = checkedResultIds();
  const QSet<QString> checked(checkedIds.cbegin(), checkedIds.cend());
  refreshFavorites();
  visibleResults_ = services_.search(filters);
  const auto text = ui_->searchResultsEdit->text().trimmed();
  visibleResults_.erase(std::remove_if(visibleResults_.begin(), visibleResults_.end(), [&](const auto& result) {
    const auto searchable = QStringList{result.resultId, result.runId, result.domain, result.variantId,
        result.datasetId, result.sequenceId, result.scenarioId, result.state, result.tags.join(QLatin1Char(' '))}
        .join(QLatin1Char(' '));
    return (!text.isEmpty() && !searchable.contains(text, Qt::CaseInsensitive)) ||
        (ui_->favoritesOnlyCheck->isChecked() && !favoriteResultIds_.contains(result.resultId));
  }), visibleResults_.end());
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
    ui_->historyTable->setItem(row, 3, item((favoriteResultIds_.contains(result.resultId)
        ? QStringLiteral("★ ") : QString{}) + result.variantId));
    ui_->historyTable->setItem(row, 4, item(result.runId));
    ui_->historyTable->setItem(row, 5, item(datasetReferenceText(result)));
    ui_->historyTable->setItem(row, 6, item(result.sequenceId));
    ui_->historyTable->setItem(row, 7, item(result.state));
    ui_->historyTable->setItem(row, 8, item(result.metricsStatus));
  }
  ui_->historyTable->setSortingEnabled(true);
  ui_->historyTable->resizeColumnsToContents();
  ui_->historyDescriptionLabel->setText(QStringLiteral("%1 résultat(s) affiché(s) · %2 archive(s) indexée(s)%3")
      .arg(visibleResults_.size()).arg(services_.totalCount())
      .arg(favoritesAvailable_ ? QString{} : QStringLiteral(" · Favoris indisponibles : ") + favoriteError_));
  ui_->exportCsvButton->setEnabled(!visibleResults_.isEmpty());
  const auto selectedCount = checkedResultIds().size();
  ui_->compareButton->setEnabled(selectedCount >= 2 && selectedCount <= 4);
  selectVisibleResult(previousSelection);
  if (!ui_->historyTable->selectedItems().isEmpty()) {
    historySelectionChanged();
  } else {
    selectedResultId_.clear();
    ui_->replayButton->setEnabled(false);
    ui_->duplicateButton->setEnabled(false);
    ui_->openResultFolderButton->setEnabled(false);
    ui_->analyzeButton->setEnabled(false);
    ui_->favoriteButton->setEnabled(false);
    ui_->detailTitleLabel->setText(QStringLiteral("Sélectionnez un résultat"));
    ui_->detailSummaryLabel->clear();
    ui_->detailMetricsTable->setRowCount(0);
    ui_->detailEventsTable->setRowCount(0);
    ui_->detailJsonEdit->clear();
  }
}

void ResultsPage::refreshFavorites() {
  favoriteResultIds_.clear();
  try {
    const auto favorites = services_.workspaceData().preferences().favoriteResultIds;
    favoriteResultIds_ = QSet<QString>(favorites.cbegin(), favorites.cend());
    favoritesAvailable_ = true; favoriteError_.clear();
  } catch (const std::exception& error) {
    favoritesAvailable_ = false; favoriteError_ = QString::fromUtf8(error.what());
    const QSignalBlocker blocker(ui_->favoritesOnlyCheck);
    ui_->favoritesOnlyCheck->setChecked(false);
  }
  ui_->favoritesOnlyCheck->setEnabled(favoritesAvailable_);
}

void ResultsPage::applyHistoryFilters() { populateHistoryTable(historyFilters()); }

void ResultsPage::resetHistoryFilters() {
  ui_->domainFilterCombo->setCurrentIndex(0);
  ui_->algorithmFilterCombo->setCurrentIndex(0);
  ui_->stateFilterCombo->setCurrentIndex(0);
  ui_->tagFilterEdit->clear();
  ui_->searchResultsEdit->clear();
  ui_->favoritesOnlyCheck->setChecked(false);
  ui_->dateFromEdit->setDate(ui_->dateFromEdit->minimumDate());
  ui_->dateToEdit->setDate(ui_->dateToEdit->minimumDate());
  populateHistoryTable();
}

void ResultsPage::historySelectionChanged() {
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
    showResultDetail(services_.detail(selectedResultId_));
  } catch (const std::exception& error) {
    QMessageBox::warning(this, QStringLiteral("Fiche indisponible"), QString::fromUtf8(error.what()));
  }
}

void ResultsPage::showResultDetail(const core::ResultDetail& detail) {
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
  ui_->openResultFolderButton->setEnabled(true);
  ui_->analyzeButton->setEnabled(true);
  ui_->favoriteButton->setEnabled(favoritesAvailable_);
  ui_->favoriteButton->setText(!favoritesAvailable_ ? QStringLiteral("Favoris indisponibles")
      : favoriteResultIds_.contains(summary.resultId) ? QStringLiteral("Retirer des favoris") : QStringLiteral("Ajouter aux favoris"));
}

void ResultsPage::toggleFavorite() {
  if (selectedResultId_.isEmpty()) return;
  try {
    auto& workspace = services_.workspaceData();
    workspace.setFavoriteResult(selectedResultId_, !workspace.isFavoriteResult(selectedResultId_));
    populateHistoryTable(historyFilters());
  } catch (const std::exception& error) {
    QMessageBox::warning(this, QStringLiteral("Favori non enregistré"), QString::fromUtf8(error.what()));
  }
}

void ResultsPage::exportVisibleResults() {
  const auto path = QFileDialog::getSaveFileName(this, QStringLiteral("Exporter les résultats affichés"),
      QStringLiteral("resultats.csv"), QStringLiteral("CSV (*.csv)"));
  if (path.isEmpty()) return;
  QStringList lines{QStringLiteral("result_id,run_id,date_utc,domain,variant,dataset,sequence,scenario,state,metrics_status,favorite")};
  for (const auto& result : visibleResults_) {
    QStringList values{result.resultId, result.runId, result.createdAtUtc.toString(Qt::ISODate), result.domain,
        result.variantId, result.datasetId, result.sequenceId, result.scenarioId, result.state,
        result.metricsStatus, !favoritesAvailable_ ? QString{} : favoriteResultIds_.contains(result.resultId) ? QStringLiteral("true") : QStringLiteral("false")};
    for (auto& value : values) value = csvCell(value);
    lines.append(values.join(QLatin1Char(',')));
  }
  try { services_.exportReport(path, lines.join(QStringLiteral("\r\n")) + QStringLiteral("\r\n")); }
  catch (const std::exception& error) {
    QMessageBox::warning(this, QStringLiteral("Export impossible"), QString::fromUtf8(error.what()));
  }
}

void ResultsPage::openSelectedResultFolder() {
  if (selectedResultId_.isEmpty()) {
    return;
  }
  try {
    const auto detail = services_.detail(selectedResultId_);
    const auto path = QDir(services_.resultsRoot()).filePath(detail.summary.relativeDirectory);
    QDesktopServices::openUrl(QUrl::fromLocalFile(path));
  } catch (const std::exception& error) {
    QMessageBox::warning(this, QStringLiteral("Dossier indisponible"), QString::fromUtf8(error.what()));
  }
}

QStringList ResultsPage::checkedResultIds() const {
  QStringList ids;
  for (int row = 0; row < ui_->historyTable->rowCount(); ++row) {
    const auto* value = ui_->historyTable->item(row, 0);
    if (value && value->checkState() == Qt::Checked) {
      ids.append(value->data(Qt::UserRole).toString());
    }
  }
  return ids;
}

void ResultsPage::selectComboData(QComboBox* combo, const QString& value) {
  const auto index = combo->findData(value);
  if (index >= 0) {
    combo->setCurrentIndex(index);
  }
}

}  // namespace drone_agricole::ui
