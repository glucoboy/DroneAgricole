#include "drone_agricole/ui/SystemPage.hpp"
#include "drone_agricole/application/WorkspaceService.hpp"
#include "ui_system_page.h"

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
}
QString known(const QString& value) { return value.isEmpty() ? QStringLiteral("Non renseigné") : value; }
QString amount(const std::optional<double>& value) { return value ? QString::number(*value, 'g', 10) : QStringLiteral("Inconnue"); }
}

SystemPage::SystemPage(application::IStationServices& services, QWidget* parent)
    : QWidget(parent), ui_(std::make_unique<Ui::SystemPage>()), services_(services) {
  ui_->setupUi(this);
  for (auto* table : {ui_->hardwareTable, ui_->diagnosticsTable, ui_->maintenanceTable}) prepare(table);
  ui_->hardwareSplitter->setChildrenCollapsible(false);
  ui_->hardwareSplitter->setStretchFactor(0, 1); ui_->hardwareSplitter->setStretchFactor(1, 0);
  ui_->hardwareSplitter->setSizes({700, 340});
  ui_->hardwareTable->horizontalHeader()->setSectionResizeMode(0, QHeaderView::Stretch);
  ui_->hardwareTable->setColumnWidth(1, 130); ui_->hardwareTable->setColumnWidth(2, 82); ui_->hardwareTable->setColumnWidth(3, 150);
  ui_->diagnosticsTable->setColumnWidth(0, 280);
  ui_->diagnosticsTable->horizontalHeader()->setSectionResizeMode(1, QHeaderView::Stretch);
  ui_->maintenanceTable->setColumnWidth(0, 280);
  ui_->maintenanceTable->horizontalHeader()->setSectionResizeMode(1, QHeaderView::Stretch);
  ui_->themeCombo->addItem(QStringLiteral("Clair professionnel"), QStringLiteral("professional"));
  ui_->themeCombo->addItem(QStringLiteral("Clair premium sobre"), QStringLiteral("premium"));
  ui_->workspacePathLabel->setText(services_.workspace());
  connect(ui_->saveSettingsButton, &QPushButton::clicked, this, &SystemPage::savePreferences);
  connect(ui_->hardwareSearchEdit, &QLineEdit::textChanged, this, &SystemPage::populateHardware);
  connect(ui_->hardwareSubsystemCombo, &QComboBox::currentIndexChanged, this, &SystemPage::populateHardware);
  connect(ui_->hardwareTable, &QTableWidget::itemSelectionChanged, this, &SystemPage::showHardware);
  connect(ui_->refreshHardwareButton, &QPushButton::clicked, this, &SystemPage::populateHardware);
  connect(ui_->refreshDiagnosticsButton, &QPushButton::clicked, this, &SystemPage::updateDiagnostics);
  loadPreferences();
}
SystemPage::~SystemPage() = default;

void SystemPage::setSection(const QString& section) {
  ui_->sectionsStack->setCurrentWidget(section == QStringLiteral("hardware") ? ui_->hardwareSection :
      section == QStringLiteral("diagnostics") ? ui_->diagnosticsSection :
      section == QStringLiteral("maintenance") ? ui_->maintenanceSection : ui_->settingsSection);
  refresh();
}
void SystemPage::refresh() {
  if (ui_->sectionsStack->currentWidget() == ui_->hardwareSection) populateHardware();
  else if (ui_->sectionsStack->currentWidget() == ui_->diagnosticsSection) updateDiagnostics();
  else if (ui_->sectionsStack->currentWidget() == ui_->maintenanceSection) populateMaintenance();
  else loadPreferences();
}

void SystemPage::loadPreferences() {
  try {
    const auto preferences = services_.workspaceData().preferences();
    const auto index = ui_->themeCombo->findData(preferences.themeId);
    if (index >= 0) ui_->themeCombo->setCurrentIndex(index);
    ui_->settingsStatusLabel->setText(QStringLiteral("Choix conservé dans l'espace de travail. Les favoris sont partagés par les pages de résultats."));
  } catch (const std::exception& error) { ui_->settingsStatusLabel->setText(QStringLiteral("Préférences illisibles : %1").arg(QString::fromUtf8(error.what()))); }
}
void SystemPage::savePreferences() {
  try {
    auto preferences = services_.workspaceData().preferences();
    preferences.themeId = ui_->themeCombo->currentData().toString();
    services_.workspaceData().savePreferences(preferences);
    ui_->settingsStatusLabel->setText(QStringLiteral("Thème enregistré et appliqué à la station."));
    emit themeChanged();
  } catch (const std::exception& error) { ui_->settingsStatusLabel->setText(QStringLiteral("Enregistrement refusé : %1").arg(QString::fromUtf8(error.what()))); }
}

void SystemPage::populateHardware() {
  QString selected;
  const auto rows = ui_->hardwareTable->selectionModel()->selectedRows();
  if (!rows.isEmpty()) selected = ui_->hardwareTable->item(rows.first().row(), 0)->data(Qt::UserRole).toString();
  try {
    const auto inventory = services_.workspaceData().hardwareInventory();
    auto subsystem = ui_->hardwareSubsystemCombo->currentData().toString();
    {
      const QSignalBlocker blocker(ui_->hardwareSubsystemCombo);
      ui_->hardwareSubsystemCombo->clear(); ui_->hardwareSubsystemCombo->addItem(QStringLiteral("Tous les sous-systèmes"), QString{});
      QStringList choices; for (const auto& item : inventory.items) if (!item.subsystem.isEmpty()) choices.append(item.subsystem);
      choices.removeDuplicates(); std::sort(choices.begin(), choices.end());
      for (const auto& choice : choices) ui_->hardwareSubsystemCombo->addItem(choice, choice);
      const auto index = ui_->hardwareSubsystemCombo->findData(subsystem); if (index >= 0) ui_->hardwareSubsystemCombo->setCurrentIndex(index);
    }
    subsystem = ui_->hardwareSubsystemCombo->currentData().toString();
    const auto query = ui_->hardwareSearchEdit->text().trimmed();
    const QSignalBlocker blocker(ui_->hardwareTable); ui_->hardwareTable->setRowCount(0);
    for (const auto& item : inventory.items) {
      if (!subsystem.isEmpty() && item.subsystem != subsystem) continue;
      if (!query.isEmpty() && !QStringList{item.id, item.designation, item.family, item.manufacturer, item.manufacturerReference, item.status, item.subsystem, item.reservations.join(QLatin1Char(' '))}.join(QLatin1Char(' ')).contains(query, Qt::CaseInsensitive)) continue;
      const int row = ui_->hardwareTable->rowCount(); ui_->hardwareTable->insertRow(row);
      auto* title = cell(item.designation); title->setData(Qt::UserRole, item.id);
      ui_->hardwareTable->setItem(row, 0, title); ui_->hardwareTable->setItem(row, 1, cell(item.subsystem));
      ui_->hardwareTable->setItem(row, 2, cell(amount(item.quantity) + (item.unit.isEmpty() ? QString{} : QStringLiteral(" ") + item.unit)));
      ui_->hardwareTable->setItem(row, 3, cell(known(item.status)));
      if (selected == item.id) ui_->hardwareTable->selectRow(row);
    }
    ui_->hardwareSourceLabel->setText(QStringLiteral("%1 · %2\nDéfinition : %3 · Qualification : %4\nSource : %5\nLa BOM ne démontre ni disponibilité physique ni connexion à un équipement.")
        .arg(inventory.reference, inventory.selection, known(inventory.status), known(inventory.qualification), inventory.sourcePath));
    ui_->hardwareCountLabel->setText(QStringLiteral("%1 composant(s) affiché(s) sur %2 lignes de nomenclature").arg(ui_->hardwareTable->rowCount()).arg(inventory.items.size()));
    showHardware();
  } catch (const std::exception& error) {
    ui_->hardwareTable->setRowCount(0); ui_->hardwareDetailEdit->clear();
    ui_->hardwareSourceLabel->setText(QStringLiteral("Nomenclature indisponible : %1").arg(QString::fromUtf8(error.what())));
    ui_->hardwareCountLabel->setText(QStringLiteral("Inventaire indisponible"));
  }
}
void SystemPage::showHardware() {
  ui_->hardwareDetailTitle->setText(QStringLiteral("Détail du composant")); ui_->hardwareDetailEdit->clear();
  const auto rows = ui_->hardwareTable->selectionModel()->selectedRows(); if (rows.isEmpty()) return;
  const auto id = ui_->hardwareTable->item(rows.first().row(), 0)->data(Qt::UserRole).toString();
  try {
    const auto inventory = services_.workspaceData().hardwareInventory();
    for (const auto& item : inventory.items) {
      if (item.id != id) continue;
      ui_->hardwareDetailTitle->setText(item.designation);
      const auto mass = item.definition.value(QStringLiteral("donnee_massique")).toObject();
      const auto massText = amount(item.unitMassGrams) + QStringLiteral(" g · ")
          + known(mass.value(QStringLiteral("qualificatif")).toString()) + QStringLiteral(" · ")
          + known(item.definition.value(QStringLiteral("masse_nature")).toString());
      const auto description = QStringLiteral("Identifiant : %1\nFabricant : %2\nRéférence : %3\nPérimètre : %4\nStatut documentaire : %5\nDisponibilité physique : %6\nMasse unitaire publiée/calculée : %7\nQualification du prototype : %8")
          .arg(item.id, known(item.manufacturer), known(item.manufacturerReference), known(item.scope), known(item.status), known(item.physicalAvailability),
               massText, known(inventory.qualification));
      ui_->hardwareDetailEdit->setPlainText(description + QStringLiteral("\n\nRéserves\n%1\n\nSources\n%2\n\nDéfinition canonique\n%3")
          .arg(item.reservations.isEmpty() ? QStringLiteral("Aucune réserve renseignée ; cela ne vaut pas validation.") : item.reservations.join(QStringLiteral("\n\n")),
               item.sources.join(QStringLiteral("\n")), QString::fromUtf8(QJsonDocument(item.definition).toJson(QJsonDocument::Indented))));
      break;
    }
  } catch (const std::exception& error) { ui_->hardwareDetailEdit->setPlainText(QString::fromUtf8(error.what())); }
}

void SystemPage::updateDiagnostics() {
  ui_->diagnosticsTable->setRowCount(0);
  const auto append = [this](const QString& name, const QString& observation) {
    const int row = ui_->diagnosticsTable->rowCount(); ui_->diagnosticsTable->insertRow(row);
    ui_->diagnosticsTable->setItem(row, 0, cell(name)); ui_->diagnosticsTable->setItem(row, 1, cell(observation));
  };
  try {
    const auto diagnostics = services_.workspaceData().diagnostics();
    append(QStringLiteral("Préférences et brouillons"), diagnostics.stateExists ?
        (diagnostics.stateReadable ? QStringLiteral("Fichier local lisible") : QStringLiteral("Fichier présent mais illisible")) : QStringLiteral("Pas encore de fichier local"));
    append(QStringLiteral("Brouillons"), QString::number(diagnostics.missionCount));
    append(QStringLiteral("Favoris"), QString::number(diagnostics.favoriteCount));
    append(QStringLiteral("Nomenclature prototype"), diagnostics.hardwareReadable ? QStringLiteral("%1 lignes lues").arg(diagnostics.hardwareItemCount) : QStringLiteral("Source indisponible ou illisible"));
    append(QStringLiteral("Documents de schéma chargés"), QString::number(services_.schemaDocumentCount()));
    append(QStringLiteral("Archives indexées"), QString::number(services_.totalCount()));
    append(QStringLiteral("Archives invalides observées"), QString::number(services_.invalidResultCount()));
    append(QStringLiteral("Traitement de banc"), services_.execution().active() ? services_.execution().message() : QStringLiteral("Aucun traitement actif"));
    try {
      const auto snapshot = services_.snapshot();
      append(QStringLiteral("Pont de télémétrie"), snapshot.available ? QStringLiteral("Données disponibles ; origine drone/banc à vérifier") : QStringLiteral("Aucune donnée disponible"));
    } catch (const std::exception& error) { append(QStringLiteral("Pont de télémétrie"), QString::fromUtf8(error.what())); }
    auto messages = diagnostics.messages;
    messages.prepend(QStringLiteral("État local : ") + diagnostics.statePath);
    messages.prepend(QStringLiteral("BOM : ") + diagnostics.hardwareSourcePath);
    ui_->diagnosticsMessagesEdit->setPlainText(messages.join(QStringLiteral("\n")));
  } catch (const std::exception& error) { ui_->diagnosticsMessagesEdit->setPlainText(QStringLiteral("Diagnostic indisponible : %1").arg(QString::fromUtf8(error.what()))); }
}

void SystemPage::populateMaintenance() {
  ui_->maintenanceTable->setRowCount(0);
  try {
    const auto inventory = services_.workspaceData().hardwareInventory();
    for (const auto& item : inventory.items) {
      for (const auto& reservation : item.reservations) {
        const int row = ui_->maintenanceTable->rowCount(); ui_->maintenanceTable->insertRow(row);
        ui_->maintenanceTable->setItem(row, 0, cell(item.designation)); ui_->maintenanceTable->setItem(row, 1, cell(reservation));
      }
    }
    ui_->maintenanceTable->setColumnWidth(0, 280);
    ui_->maintenanceTable->resizeRowsToContents();
    ui_->maintenanceCountLabel->setText(QStringLiteral("%1 réserve(s) documentaire(s) · qualification %2").arg(ui_->maintenanceTable->rowCount()).arg(known(inventory.qualification)));
  } catch (const std::exception& error) { ui_->maintenanceCountLabel->setText(QStringLiteral("Réserves indisponibles : %1").arg(QString::fromUtf8(error.what()))); }
}
}
