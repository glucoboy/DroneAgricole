#include "drone_agricole/ui/MissionsPage.hpp"
#include "drone_agricole/application/WorkspaceService.hpp"
#include "ui_missions_page.h"

#include <QDoubleValidator>
#include <QHeaderView>
#include <QJsonDocument>
#include <QLocale>
#include <QSignalBlocker>
#include <QTableWidgetItem>
#include <algorithm>
#include <cmath>
#include <stdexcept>

namespace drone_agricole::ui {
namespace {
QTableWidgetItem* cell(const QString& text) {
  auto* item = new QTableWidgetItem(text);
  item->setFlags(item->flags() & ~Qt::ItemIsEditable);
  item->setToolTip(text);
  return item;
}
void prepare(QTableWidget* table) {
  table->verticalHeader()->hide();
  table->horizontalHeader()->setStretchLastSection(false);
  table->horizontalHeader()->setMinimumSectionSize(48);
  table->horizontalHeader()->setSectionResizeMode(QHeaderView::Interactive);
  table->setAlternatingRowColors(false);
}
QString encodedReference(const QString& dataset, const QString& sequence) {
  return QString::fromUtf8(QJsonDocument(QJsonObject{{QStringLiteral("dataset_id"), dataset},
      {QStringLiteral("sequence_id"), sequence}}).toJson(QJsonDocument::Compact));
}
QString observedValue(const QJsonValue& value) {
  if (value.isString()) return value.toString();
  if (value.isBool()) return value.toBool() ? QStringLiteral("true") : QStringLiteral("false");
  if (value.isDouble()) return QString::number(value.toDouble(), 'g', 10);
  if (value.isNull() || value.isUndefined()) return QStringLiteral("Non renseigné");
  const auto document = value.isObject() ? QJsonDocument(value.toObject()) : QJsonDocument(value.toArray());
  return QString::fromUtf8(document.toJson(QJsonDocument::Compact));
}
}

MissionsPage::MissionsPage(application::IStationServices& services, QWidget* parent)
    : QWidget(parent), ui_(std::make_unique<Ui::MissionsPage>()), services_(services) {
  ui_->setupUi(this);
  for (auto* table : {ui_->missionsTable, ui_->missionChecklistTable, ui_->telemetryTable, ui_->journalTable}) prepare(table);
  ui_->missionSplitter->setChildrenCollapsible(false);
  ui_->missionSplitter->setStretchFactor(0, 0); ui_->missionSplitter->setStretchFactor(1, 1);
  ui_->missionSplitter->setSizes({330, 700});
  ui_->missionsTable->horizontalHeader()->setSectionResizeMode(0, QHeaderView::Stretch);
  ui_->missionsTable->setColumnWidth(1, 100); ui_->missionsTable->setColumnWidth(2, 132);
  ui_->missionChecklistTable->setColumnWidth(0, 58);
  ui_->missionChecklistTable->horizontalHeader()->setSectionResizeMode(1, QHeaderView::Stretch);
  ui_->telemetryTable->setColumnWidth(0, 240);
  ui_->telemetryTable->horizontalHeader()->setSectionResizeMode(1, QHeaderView::Stretch);
  ui_->journalTable->setColumnWidth(0, 180); ui_->journalTable->setColumnWidth(1, 190); ui_->journalTable->setColumnWidth(2, 100);
  ui_->journalTable->horizontalHeader()->setSectionResizeMode(3, QHeaderView::Stretch);
  ui_->missionOperationCombo->addItem(QStringLiteral("Cartographie · brouillon"), QStringLiteral("survey"));
  ui_->missionOperationCombo->addItem(QStringLiteral("Traitement · préparation planifiée"), QStringLiteral("treatment"));
  ui_->missionDroneCombo->addItem(QStringLiteral("Drone cartographe"), QStringLiteral("cartographer"));
  ui_->missionDroneCombo->addItem(QStringLiteral("Drone de traitement · Planifié"), QStringLiteral("sprayer"));
  ui_->missionDatasetCombo->addItem(QStringLiteral("Aucune référence"), QString{});
  QSet<QString> datasets;
  for (const auto& sequence : services_.datasetSequences()) {
    if (datasets.contains(sequence.datasetId)) continue;
    datasets.insert(sequence.datasetId);
    ui_->missionDatasetCombo->addItem(sequence.datasetLabel, sequence.datasetId);
  }
  for (auto* editor : {ui_->missionAltitudeEdit, ui_->missionSpeedEdit}) {
    auto* validator = new QDoubleValidator(editor);
    validator->setBottom(0.0);
    editor->setValidator(validator);
  }
  connect(ui_->newMissionButton, &QPushButton::clicked, this, &MissionsPage::newDraft);
  connect(ui_->saveMissionButton, &QPushButton::clicked, this, &MissionsPage::saveDraft);
  connect(ui_->missionSearchEdit, &QLineEdit::textChanged, this, &MissionsPage::populateDrafts);
  connect(ui_->missionsTable, &QTableWidget::itemSelectionChanged, this, &MissionsPage::selectDraft);
  connect(ui_->missionDatasetCombo, &QComboBox::currentIndexChanged, this, &MissionsPage::updateSequences);
  connect(ui_->missionBenchButton, &QPushButton::clicked, this, [this] {
    emit routeRequested(QStringLiteral("tests"), encodedReference(ui_->missionDatasetCombo->currentData().toString(),
        ui_->missionSequenceCombo->currentData().toString()));
  });
  connect(ui_->refreshJournalButton, &QPushButton::clicked, this, [this] {
    try { services_.refresh(); populateJournal(); }
    catch (const std::exception& error) { ui_->journalStatusLabel->setText(QString::fromUtf8(error.what())); }
  });
  connect(ui_->journalSearchEdit, &QLineEdit::textChanged, this, &MissionsPage::populateJournal);
  connect(ui_->journalTable, &QTableWidget::cellDoubleClicked, this, [this](int row, int) {
    if (const auto* item = ui_->journalTable->item(row, 0)) emit routeRequested(QStringLiteral("results"), item->data(Qt::UserRole).toString());
  });
  connect(&telemetryTimer_, &QTimer::timeout, this, [this] {
    if (isVisible() && ui_->sectionsStack->currentWidget() == ui_->supervisionSection) updateSupervision();
  });
  telemetryTimer_.start(1500);
  newDraft();
  populateDrafts();
}
MissionsPage::~MissionsPage() = default;
void MissionsPage::startNewDraft() { newDraft(); }

void MissionsPage::setSection(const QString& section) {
  if (section == QStringLiteral("supervision")) {
    ui_->sectionsStack->setCurrentWidget(ui_->supervisionSection);
    updateSupervision();
  } else if (section == QStringLiteral("journal")) {
    ui_->sectionsStack->setCurrentWidget(ui_->journalSection);
    populateJournal();
  } else {
    ui_->sectionsStack->setCurrentWidget(ui_->preparationSection);
    populateDrafts();
  }
}
void MissionsPage::refresh() {
  populateDrafts();
  if (ui_->sectionsStack->currentWidget() == ui_->journalSection) populateJournal();
  if (ui_->sectionsStack->currentWidget() == ui_->supervisionSection) updateSupervision();
}

void MissionsPage::populateDrafts() {
  try {
    const QSignalBlocker blocker(ui_->missionsTable);
    ui_->missionsTable->setRowCount(0);
    const auto query = ui_->missionSearchEdit->text().trimmed();
    for (const auto& draft : services_.workspaceData().missions()) {
      if (!query.isEmpty() && !QStringList{draft.name, draft.parcel, draft.operation, draft.notes}.join(QLatin1Char(' ')).contains(query, Qt::CaseInsensitive)) continue;
      const int row = ui_->missionsTable->rowCount();
      ui_->missionsTable->insertRow(row);
      auto* title = cell(draft.name);
      title->setData(Qt::UserRole, draft.id);
      ui_->missionsTable->setItem(row, 0, title);
      ui_->missionsTable->setItem(row, 1, cell(draft.parcel));
      ui_->missionsTable->setItem(row, 2, cell(draft.updatedAt.toLocalTime().toString(QStringLiteral("dd/MM/yyyy HH:mm"))));
      if (draft.id == selectedDraftId_) ui_->missionsTable->selectRow(row);
    }
    ui_->missionCountLabel->setText(QStringLiteral("%1 brouillon(s) · préparation locale").arg(ui_->missionsTable->rowCount()));
  } catch (const std::exception& error) {
    ui_->missionStatusLabel->setText(QStringLiteral("Lecture impossible : %1").arg(QString::fromUtf8(error.what())));
  }
}

void MissionsPage::newDraft() {
  selectedDraftId_.clear();
  ui_->missionsTable->clearSelection();
  ui_->missionEditorTitle->setText(QStringLiteral("Nouveau brouillon"));
  ui_->missionNameEdit->clear(); ui_->missionParcelEdit->clear();
  ui_->missionOperationCombo->setCurrentIndex(0); ui_->missionDroneCombo->setCurrentIndex(0);
  ui_->missionDatasetCombo->setCurrentIndex(0); updateSequences();
  ui_->missionAltitudeEdit->clear(); ui_->missionSpeedEdit->clear(); ui_->missionNotesEdit->clear();
  const QList<domain::MissionChecklistItem> checklist{
      {QStringLiteral("configuration"), QStringLiteral("Configuration matérielle et réserves examinées"), false},
      {QStringLiteral("zone"), QStringLiteral("Zone, contraintes et autorisations à examiner"), false},
      {QStringLiteral("acquisition"), QStringLiteral("Acquisition, datation et stockage à vérifier"), false},
      {QStringLiteral("safety"), QStringLiteral("Protocole et conditions d'arrêt à valider"), false}};
  ui_->missionChecklistTable->setRowCount(checklist.size());
  for (int row = 0; row < checklist.size(); ++row) {
    auto* checked = cell({}); checked->setFlags(checked->flags() | Qt::ItemIsUserCheckable);
    checked->setCheckState(Qt::Unchecked); checked->setData(Qt::UserRole, checklist[row].id);
    ui_->missionChecklistTable->setItem(row, 0, checked);
    ui_->missionChecklistTable->setItem(row, 1, cell(checklist[row].label));
  }
  ui_->missionStatusLabel->setText(QStringLiteral("Brouillon non enregistré. Les valeurs de mission restent À valider."));
}

void MissionsPage::selectDraft() {
  const auto rows = ui_->missionsTable->selectionModel()->selectedRows();
  if (rows.isEmpty()) return;
  try {
    const auto draft = services_.workspaceData().mission(ui_->missionsTable->item(rows.first().row(), 0)->data(Qt::UserRole).toString());
    selectedDraftId_ = draft.id;
    ui_->missionEditorTitle->setText(draft.name + QStringLiteral(" · Brouillon"));
    ui_->missionNameEdit->setText(draft.name); ui_->missionParcelEdit->setText(draft.parcel);
    ui_->missionOperationCombo->setCurrentIndex(ui_->missionOperationCombo->findData(draft.operation));
    ui_->missionDroneCombo->setCurrentIndex(ui_->missionDroneCombo->findData(draft.drone));
    if (ui_->missionDatasetCombo->findData(draft.datasetId) < 0) ui_->missionDatasetCombo->addItem(draft.datasetId + QStringLiteral(" · absent du catalogue"), draft.datasetId);
    ui_->missionDatasetCombo->setCurrentIndex(ui_->missionDatasetCombo->findData(draft.datasetId));
    updateSequences();
    if (ui_->missionSequenceCombo->findData(draft.sequenceId) < 0) ui_->missionSequenceCombo->addItem(draft.sequenceId + QStringLiteral(" · absente du catalogue"), draft.sequenceId);
    ui_->missionSequenceCombo->setCurrentIndex(ui_->missionSequenceCombo->findData(draft.sequenceId));
    ui_->missionAltitudeEdit->setText(draft.altitudeMeters ? QLocale().toString(*draft.altitudeMeters, 'g', 12) : QString{});
    ui_->missionSpeedEdit->setText(draft.speedMetersPerSecond ? QLocale().toString(*draft.speedMetersPerSecond, 'g', 12) : QString{});
    ui_->missionNotesEdit->setPlainText(draft.notes);
    ui_->missionChecklistTable->setRowCount(draft.checklist.size());
    for (int row = 0; row < draft.checklist.size(); ++row) {
      auto* checked = cell({}); checked->setFlags(checked->flags() | Qt::ItemIsUserCheckable);
      checked->setCheckState(draft.checklist[row].checked ? Qt::Checked : Qt::Unchecked);
      checked->setData(Qt::UserRole, draft.checklist[row].id);
      ui_->missionChecklistTable->setItem(row, 0, checked);
      ui_->missionChecklistTable->setItem(row, 1, cell(draft.checklist[row].label));
    }
    ui_->missionStatusLabel->setText(QStringLiteral("Brouillon local · modifié le %1 · valeurs et préparation À valider").arg(draft.updatedAt.toLocalTime().toString(QStringLiteral("dd/MM/yyyy HH:mm"))));
  } catch (const std::exception& error) {
    ui_->missionStatusLabel->setText(QString::fromUtf8(error.what()));
  }
}

void MissionsPage::saveDraft() {
  try {
    domain::MissionDraft draft;
    draft.id = selectedDraftId_; draft.name = ui_->missionNameEdit->text(); draft.parcel = ui_->missionParcelEdit->text();
    draft.operation = ui_->missionOperationCombo->currentData().toString(); draft.drone = ui_->missionDroneCombo->currentData().toString();
    draft.datasetId = ui_->missionDatasetCombo->currentData().toString(); draft.sequenceId = ui_->missionSequenceCombo->currentData().toString();
    draft.notes = ui_->missionNotesEdit->toPlainText();
    const auto optionalNumber = [](const QLineEdit* edit) -> std::optional<double> {
      if (edit->text().trimmed().isEmpty()) return std::nullopt;
      bool valid = false; const auto value = QLocale().toDouble(edit->text(), &valid);
      if (!valid || !std::isfinite(value) || value <= 0.0) throw std::invalid_argument("Altitude et vitesse doivent être positives, ou laissées non définies.");
      return value;
    };
    draft.altitudeMeters = optionalNumber(ui_->missionAltitudeEdit); draft.speedMetersPerSecond = optionalNumber(ui_->missionSpeedEdit);
    for (int row = 0; row < ui_->missionChecklistTable->rowCount(); ++row) {
      const auto* check = ui_->missionChecklistTable->item(row, 0);
      draft.checklist.append({check->data(Qt::UserRole).toString(), ui_->missionChecklistTable->item(row, 1)->text(), check->checkState() == Qt::Checked});
    }
    const auto saved = services_.workspaceData().saveMission(draft);
    selectedDraftId_ = saved.id;
    populateDrafts();
    ui_->missionEditorTitle->setText(saved.name + QStringLiteral(" · Brouillon"));
    ui_->missionStatusLabel->setText(QStringLiteral("Brouillon enregistré à %1. Aucune mission transmise ou approuvée.").arg(saved.updatedAt.toLocalTime().toString(QStringLiteral("HH:mm:ss"))));
  } catch (const std::exception& error) {
    ui_->missionStatusLabel->setText(QStringLiteral("Enregistrement refusé : %1").arg(QString::fromUtf8(error.what())));
  }
}

void MissionsPage::updateSequences() {
  const auto previous = ui_->missionSequenceCombo->currentData().toString();
  ui_->missionSequenceCombo->clear(); ui_->missionSequenceCombo->addItem(QStringLiteral("Aucune référence"), QString{});
  for (const auto& sequence : services_.datasetSequences()) {
    if (sequence.datasetId == ui_->missionDatasetCombo->currentData().toString()) ui_->missionSequenceCombo->addItem(sequence.sequenceLabel, sequence.sequenceId);
  }
  const auto index = ui_->missionSequenceCombo->findData(previous);
  if (index >= 0) ui_->missionSequenceCombo->setCurrentIndex(index);
}

void MissionsPage::updateSupervision() {
  try {
    const auto snapshot = services_.snapshot();
    ui_->telemetryStateLabel->setText(snapshot.available ? QStringLiteral("Données disponibles depuis le pont de télémétrie") : QStringLiteral("Aucune télémétrie disponible depuis le pont"));
    ui_->telemetryCountsLabel->setText(QStringLiteral("%1 points LiDAR · %2 poses estimées · %3 poses PX4 · source réelle ou banc à vérifier")
        .arg(snapshot.cloud.size()).arg(snapshot.estimate.size()).arg(snapshot.px4Path.size()));
    ui_->telemetryTable->setRowCount(0);
    const auto append = [this](const QString& prefix, const QJsonObject& object) {
      for (auto it = object.begin(); it != object.end(); ++it) {
        const int row = ui_->telemetryTable->rowCount(); ui_->telemetryTable->insertRow(row);
        ui_->telemetryTable->setItem(row, 0, cell(prefix + it.key()));
        ui_->telemetryTable->setItem(row, 1, cell(observedValue(it.value())));
      }
    };
    if (snapshot.available) { append(QStringLiteral("PX4 / "), snapshot.px4State); append(QStringLiteral("Métrique / "), snapshot.metrics); }
  } catch (const std::exception& error) {
    ui_->telemetryStateLabel->setText(QStringLiteral("Observation indisponible : %1").arg(QString::fromUtf8(error.what())));
    ui_->telemetryTable->setRowCount(0);
  }
}

void MissionsPage::populateJournal() {
  try {
    ui_->journalTable->setRowCount(0);
    const auto query = ui_->journalSearchEdit->text().trimmed();
    int inspected = 0; int unavailable = 0; bool truncated = false;
    for (const auto& result : services_.search()) {
      if (++inspected > 100 || ui_->journalTable->rowCount() >= 500) { truncated = true; break; }
      try {
        const auto detail = services_.detail(result.resultId);
        for (const auto& value : detail.events) {
          const auto event = value.toObject();
          const auto message = event.value(QStringLiteral("message")).toString(event.value(QStringLiteral("event_type")).toString());
          const auto state = event.value(QStringLiteral("state")).toString(result.state);
          if (!query.isEmpty() && !QStringList{result.runId, result.variantId, message, state}.join(QLatin1Char(' ')).contains(query, Qt::CaseInsensitive)) continue;
          if (ui_->journalTable->rowCount() >= 500) { truncated = true; break; }
          const auto time = event.contains(QStringLiteral("timestamp_utc")) ? event.value(QStringLiteral("timestamp_utc")).toString() : QStringLiteral("%1 s").arg(event.value(QStringLiteral("elapsed_s")).toDouble());
          const int row = ui_->journalTable->rowCount(); ui_->journalTable->insertRow(row);
          auto* date = cell(time); date->setData(Qt::UserRole, result.resultId);
          ui_->journalTable->setItem(row, 0, date); ui_->journalTable->setItem(row, 1, cell(result.runId));
          ui_->journalTable->setItem(row, 2, cell(state)); ui_->journalTable->setItem(row, 3, cell(message));
        }
      } catch (const std::exception&) { ++unavailable; }
    }
    ui_->journalStatusLabel->setText(QStringLiteral("%1 événement(s) affiché(s) · %2 archive(s) illisible(s)%3")
        .arg(ui_->journalTable->rowCount()).arg(unavailable).arg(truncated ? QStringLiteral(" · affichage limité aux 100 premières archives et 500 événements") : QString{}));
  } catch (const std::exception& error) {
    ui_->journalStatusLabel->setText(QString::fromUtf8(error.what()));
  }
}
}
