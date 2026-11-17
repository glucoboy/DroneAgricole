#include "drone_agricole/ui/DataPage.hpp"
#include "drone_agricole/application/WorkspaceService.hpp"
#include "ui_data_page.h"

#include <QDir>
#include <QFileDialog>
#include <QHeaderView>
#include <QJsonDocument>
#include <QSignalBlocker>
#include <QTableWidgetItem>
#include <algorithm>

namespace drone_agricole::ui {
namespace {
QTableWidgetItem* cell(const QString& text) { auto* item = new QTableWidgetItem(text); item->setFlags(item->flags() & ~Qt::ItemIsEditable); item->setToolTip(text); return item; }
void prepare(QTableWidget* table) {
  table->verticalHeader()->hide(); table->horizontalHeader()->setStretchLastSection(false);
  table->horizontalHeader()->setMinimumSectionSize(60);
  table->horizontalHeader()->setSectionResizeMode(QHeaderView::Interactive);
  table->horizontalHeader()->setSectionResizeMode(0, QHeaderView::Stretch);
}
QString reference(const QString& dataset, const QString& sequence) {
  return QString::fromUtf8(QJsonDocument(QJsonObject{{QStringLiteral("dataset_id"), dataset}, {QStringLiteral("sequence_id"), sequence}}).toJson(QJsonDocument::Compact));
}
void choices(QComboBox* combo, const QString& all, const QStringList& values) {
  const auto selected = combo->currentData().toString();
  const QSignalBlocker blocker(combo); combo->clear(); combo->addItem(all, QString{});
  auto ordered = values; ordered.removeAll(QString{}); ordered.removeDuplicates(); std::sort(ordered.begin(), ordered.end());
  for (const auto& value : ordered) combo->addItem(value, value);
  const auto index = combo->findData(selected); if (index >= 0) combo->setCurrentIndex(index);
}
}

DataPage::DataPage(application::IStationServices& services, QWidget* parent)
    : QWidget(parent), ui_(std::make_unique<Ui::DataPage>()), services_(services) {
  ui_->setupUi(this); prepare(ui_->catalogueTable); prepare(ui_->acquisitionsTable);
  for (auto* splitter : {ui_->catalogueSplitter, ui_->acquisitionsSplitter}) {
    splitter->setChildrenCollapsible(false); splitter->setStretchFactor(0, 1); splitter->setStretchFactor(1, 0);
    splitter->setSizes({700, 340});
  }
  ui_->catalogueTable->setColumnWidth(1, 150); ui_->catalogueTable->setColumnWidth(2, 145); ui_->catalogueTable->setColumnWidth(3, 85);
  ui_->acquisitionsTable->setColumnWidth(1, 110); ui_->acquisitionsTable->setColumnWidth(2, 90);
  ui_->acquisitionsTable->setColumnWidth(3, 95); ui_->acquisitionsTable->setColumnWidth(4, 130);
  connect(ui_->catalogueSearchEdit, &QLineEdit::textChanged, this, &DataPage::populateCatalogue);
  connect(ui_->catalogueStatusCombo, &QComboBox::currentIndexChanged, this, &DataPage::populateCatalogue);
  connect(ui_->catalogueTable, &QTableWidget::itemSelectionChanged, this, &DataPage::showSequence);
  connect(ui_->refreshCatalogueButton, &QPushButton::clicked, this, &DataPage::refresh);
  connect(ui_->refreshAcquisitionsButton, &QPushButton::clicked, this, [this] {
    try { services_.refresh(); refresh(); }
    catch (const std::exception& error) { ui_->acquisitionCountLabel->setText(QString::fromUtf8(error.what())); }
  });
  connect(ui_->sequenceBenchButton, &QPushButton::clicked, this, [this] {
    const auto rows = ui_->catalogueTable->selectionModel()->selectedRows(); if (rows.isEmpty()) return;
    const auto* item = ui_->catalogueTable->item(rows.first().row(), 0);
    emit routeRequested(QStringLiteral("tests"), reference(item->data(Qt::UserRole).toString(), item->data(Qt::UserRole + 1).toString()));
  });
  connect(ui_->acquisitionSearchEdit, &QLineEdit::textChanged, this, &DataPage::populateAcquisitions);
  connect(ui_->acquisitionDomainCombo, &QComboBox::currentIndexChanged, this, &DataPage::populateAcquisitions);
  connect(ui_->acquisitionsTable, &QTableWidget::itemSelectionChanged, this, &DataPage::showAcquisition);
  connect(ui_->openAcquisitionButton, &QPushButton::clicked, this, [this] {
    if (!selectedResultId_.isEmpty()) emit routeRequested(QStringLiteral("results"), selectedResultId_);
  });
  connect(ui_->exportMetadataButton, &QPushButton::clicked, this, &DataPage::exportMetadata);
  connect(ui_->transferMetadataButton, &QPushButton::clicked, this, &DataPage::exportMetadata);
  connect(ui_->importMissionButton, &QPushButton::clicked, this, &DataPage::importDrafts);
  connect(ui_->exportMissionButton, &QPushButton::clicked, this, &DataPage::exportDrafts);
  refresh();
}
DataPage::~DataPage() = default;

void DataPage::setSection(const QString& section) {
  ui_->sectionsStack->setCurrentWidget(section == QStringLiteral("acquisitions") ? ui_->acquisitionsSection :
      section == QStringLiteral("import-export") ? ui_->transferSection : ui_->catalogueSection);
  refresh();
}
void DataPage::refresh() {
  QStringList statuses; for (const auto& sequence : services_.datasetSequences()) statuses.append(sequence.status);
  choices(ui_->catalogueStatusCombo, QStringLiteral("Tous les statuts"), statuses);
  QStringList domains; for (const auto& result : services_.search()) domains.append(result.domain);
  choices(ui_->acquisitionDomainCombo, QStringLiteral("Tous les domaines"), domains);
  populateCatalogue(); populateAcquisitions();
  try {
    const auto selected = ui_->exportMissionCombo->currentData().toString();
    ui_->exportMissionCombo->clear();
    for (const auto& draft : services_.workspaceData().missions()) ui_->exportMissionCombo->addItem(draft.name + QStringLiteral(" · Brouillon"), draft.id);
    const auto index = ui_->exportMissionCombo->findData(selected); if (index >= 0) ui_->exportMissionCombo->setCurrentIndex(index);
    ui_->exportMissionButton->setEnabled(ui_->exportMissionCombo->count() > 0);
    if (ui_->exportMissionCombo->count() == 0) ui_->exportMissionCombo->addItem(QStringLiteral("Aucun brouillon à exporter"), QString{});
  } catch (const std::exception& error) { ui_->transferStatusLabel->setText(QString::fromUtf8(error.what())); ui_->exportMissionButton->setEnabled(false); }
}

void DataPage::populateCatalogue() {
  QString dataset; QString sequenceId;
  const auto rows = ui_->catalogueTable->selectionModel()->selectedRows();
  if (!rows.isEmpty()) {
    const auto* item = ui_->catalogueTable->item(rows.first().row(), 0);
    dataset = item->data(Qt::UserRole).toString(); sequenceId = item->data(Qt::UserRole + 1).toString();
  }
  const QSignalBlocker blocker(ui_->catalogueTable); ui_->catalogueTable->setRowCount(0);
  const auto query = ui_->catalogueSearchEdit->text().trimmed(); const auto status = ui_->catalogueStatusCombo->currentData().toString();
  for (const auto& sequence : services_.datasetSequences()) {
    if (!status.isEmpty() && sequence.status != status) continue;
    const auto text = QStringList{sequence.datasetId, sequence.datasetLabel, sequence.sequenceId, sequence.sequenceLabel, sequence.status, sequence.capabilities.values().join(QLatin1Char(' '))}.join(QLatin1Char(' '));
    if (!query.isEmpty() && !text.contains(query, Qt::CaseInsensitive)) continue;
    const int row = ui_->catalogueTable->rowCount(); ui_->catalogueTable->insertRow(row);
    auto* title = cell(sequence.datasetLabel); title->setData(Qt::UserRole, sequence.datasetId); title->setData(Qt::UserRole + 1, sequence.sequenceId);
    ui_->catalogueTable->setItem(row, 0, title); ui_->catalogueTable->setItem(row, 1, cell(sequence.sequenceLabel));
    ui_->catalogueTable->setItem(row, 2, cell(sequence.status));
    ui_->catalogueTable->setItem(row, 3, cell(sequence.durationSeconds > 0 ? QString::number(sequence.durationSeconds, 'f', 1) : QStringLiteral("Non déclarée")));
    if (sequence.datasetId == dataset && sequence.sequenceId == sequenceId) ui_->catalogueTable->selectRow(row);
  }
  ui_->catalogueCountLabel->setText(QStringLiteral("%1 séquence(s) déclarée(s)").arg(ui_->catalogueTable->rowCount()));
  showSequence();
}
void DataPage::showSequence() {
  ui_->sequenceBenchButton->setEnabled(false); ui_->sequenceDetailEdit->clear();
  ui_->sequenceTitleLabel->setText(QStringLiteral("Détail de la séquence"));
  const auto rows = ui_->catalogueTable->selectionModel()->selectedRows(); if (rows.isEmpty()) return;
  const auto* item = ui_->catalogueTable->item(rows.first().row(), 0);
  for (const auto& sequence : services_.datasetSequences()) {
    if (sequence.datasetId != item->data(Qt::UserRole).toString() || sequence.sequenceId != item->data(Qt::UserRole + 1).toString()) continue;
    auto capabilities = sequence.capabilities.values(); std::sort(capabilities.begin(), capabilities.end());
    ui_->sequenceTitleLabel->setText(sequence.datasetLabel + QStringLiteral(" / ") + sequence.sequenceLabel);
    ui_->sequenceDetailEdit->setPlainText(QStringLiteral("Dataset : %1\nSéquence : %2\nStatut déclaré : %3\n\nCapacités déclarées\n%4\n\nRessources déclarées\n%5")
        .arg(sequence.datasetId, sequence.sequenceId, sequence.status, capabilities.join(QStringLiteral("\n")),
             QString::fromUtf8(QJsonDocument(sequence.resources).toJson(QJsonDocument::Indented))));
    ui_->sequenceBenchButton->setEnabled(true); break;
  }
}

void DataPage::populateAcquisitions() {
  const auto previous = selectedResultId_;
  const QSignalBlocker blocker(ui_->acquisitionsTable); ui_->acquisitionsTable->setRowCount(0);
  core::SearchFilters filters; filters.domain = ui_->acquisitionDomainCombo->currentData().toString();
  const auto query = ui_->acquisitionSearchEdit->text().trimmed();
  for (const auto& result : services_.search(filters)) {
    if (!query.isEmpty() && !QStringList{result.resultId, result.runId, result.datasetId, result.sequenceId, result.sourceKind, result.domain, result.state, result.variantId}.join(QLatin1Char(' ')).contains(query, Qt::CaseInsensitive)) continue;
    const int row = ui_->acquisitionsTable->rowCount(); ui_->acquisitionsTable->insertRow(row);
    auto* title = cell(result.runId); title->setData(Qt::UserRole, result.resultId);
    ui_->acquisitionsTable->setItem(row, 0, title); ui_->acquisitionsTable->setItem(row, 1, cell(result.datasetId));
    ui_->acquisitionsTable->setItem(row, 2, cell(result.sourceKind)); ui_->acquisitionsTable->setItem(row, 3, cell(result.state));
    ui_->acquisitionsTable->setItem(row, 4, cell(result.createdAtUtc.toLocalTime().toString(QStringLiteral("dd/MM/yyyy HH:mm"))));
    if (result.resultId == previous) ui_->acquisitionsTable->selectRow(row);
  }
  ui_->acquisitionCountLabel->setText(QStringLiteral("%1 archive(s) affichée(s)").arg(ui_->acquisitionsTable->rowCount()));
  showAcquisition();
}
void DataPage::showAcquisition() {
  selectedResultId_.clear(); ui_->openAcquisitionButton->setEnabled(false); ui_->acquisitionDetailEdit->clear();
  ui_->acquisitionTitleLabel->setText(QStringLiteral("Détail de l'archive"));
  const auto rows = ui_->acquisitionsTable->selectionModel()->selectedRows(); if (rows.isEmpty()) return;
  selectedResultId_ = ui_->acquisitionsTable->item(rows.first().row(), 0)->data(Qt::UserRole).toString();
  try {
    const auto detail = services_.detail(selectedResultId_); const auto& summary = detail.summary;
    ui_->acquisitionTitleLabel->setText(summary.runId);
    ui_->acquisitionDetailEdit->setPlainText(QStringLiteral("Identifiant : %1\nType : %2\nDomaine : %3\nÉtat : %4\nDataset : %5\nSéquence : %6\nRépertoire : %7\n\nArtefacts déclarés\n%8")
        .arg(summary.resultId, summary.sourceKind, summary.domain, summary.state, summary.datasetId, summary.sequenceId,
             summary.relativeDirectory, QString::fromUtf8(QJsonDocument(detail.artifacts).toJson(QJsonDocument::Indented))));
    ui_->openAcquisitionButton->setEnabled(true);
  } catch (const std::exception& error) { ui_->acquisitionDetailEdit->setPlainText(QString::fromUtf8(error.what())); }
}

void DataPage::exportMetadata() {
  const auto path = QFileDialog::getSaveFileName(this, QStringLiteral("Exporter les métadonnées des archives affichées"),
      QDir(services_.workspace()).filePath(QStringLiteral("archives_metadata.json")), QStringLiteral("JSON (*.json)"));
  if (path.isEmpty()) return;
  try {
    QSet<QString> selected;
    for (int row = 0; row < ui_->acquisitionsTable->rowCount(); ++row) selected.insert(ui_->acquisitionsTable->item(row, 0)->data(Qt::UserRole).toString());
    QJsonArray archives;
    for (const auto& summary : services_.search()) if (selected.contains(summary.resultId)) archives.append(summary.toJson());
    const QJsonObject document{{QStringLiteral("schema_version"), 1}, {QStringLiteral("kind"), QStringLiteral("ArchiveMetadataExport")},
        {QStringLiteral("exported_at_utc"), QDateTime::currentDateTimeUtc().toString(Qt::ISODate)},
        {QStringLiteral("query"), ui_->acquisitionSearchEdit->text()}, {QStringLiteral("domain"), ui_->acquisitionDomainCombo->currentData().toString()},
        {QStringLiteral("archives"), archives}};
    services_.exportReport(path, QString::fromUtf8(QJsonDocument(document).toJson(QJsonDocument::Indented)));
    const auto message = QStringLiteral("%1 métadonnée(s) exportée(s) : %2").arg(archives.size()).arg(path);
    ui_->transferStatusLabel->setText(message); ui_->acquisitionCountLabel->setText(message);
  } catch (const std::exception& error) { ui_->transferStatusLabel->setText(QString::fromUtf8(error.what())); ui_->acquisitionCountLabel->setText(QString::fromUtf8(error.what())); }
}
void DataPage::importDrafts() {
  const auto path = QFileDialog::getOpenFileName(this, QStringLiteral("Importer un brouillon de mission"), services_.workspace(), QStringLiteral("JSON (*.json)"));
  if (path.isEmpty()) return;
  try {
    const auto imported = services_.workspaceData().importMission(path); refresh();
    ui_->transferStatusLabel->setText(QStringLiteral("Brouillon importé : %1. Il reste local et À valider.").arg(imported.name));
  } catch (const std::exception& error) { ui_->transferStatusLabel->setText(QStringLiteral("Import refusé : %1").arg(QString::fromUtf8(error.what()))); }
}
void DataPage::exportDrafts() {
  const auto id = ui_->exportMissionCombo->currentData().toString(); if (id.isEmpty()) return;
  const auto path = QFileDialog::getSaveFileName(this, QStringLiteral("Exporter un brouillon de mission"),
      QDir(services_.workspace()).filePath(QStringLiteral("mission_draft.json")), QStringLiteral("JSON (*.json)"));
  if (path.isEmpty()) return;
  try {
    services_.workspaceData().exportMission(id, path);
    ui_->transferStatusLabel->setText(QStringLiteral("Brouillon exporté : %1").arg(path));
  } catch (const std::exception& error) { ui_->transferStatusLabel->setText(QStringLiteral("Export refusé : %1").arg(QString::fromUtf8(error.what()))); }
}
}
