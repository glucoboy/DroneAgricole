#pragma once

#include <QDateTime>
#include <QJsonObject>
#include <QList>
#include <QStringList>
#include <optional>

namespace drone_agricole::domain {

// Documents de préparation locale : aucune autorisation ni commande de vol.
struct MissionChecklistItem {
  QString id;
  QString label;
  bool checked{false};
};

struct MissionDraft {
  QString id;
  QString name;
  QString parcel;
  QString operation{QStringLiteral("survey")};
  QString drone{QStringLiteral("cartographer")};
  std::optional<double> altitudeMeters;
  std::optional<double> speedMetersPerSecond;
  QString datasetId;
  QString sequenceId;
  QString notes;
  QList<MissionChecklistItem> checklist;
  QDateTime updatedAt;
};

struct WorkspacePreferences {
  QString themeId{QStringLiteral("professional")};
  QStringList favoriteResultIds;
};

struct WorkspaceState {
  QList<MissionDraft> missions;
  WorkspacePreferences preferences;
};

struct HardwareItem {
  QString id;
  QString designation;
  QString family;
  QString manufacturer;
  QString manufacturerReference;
  QString subsystem;
  QString scope;
  QString status;
  QString physicalAvailability;
  std::optional<double> quantity;
  QString unit;
  std::optional<double> unitMassGrams;
  QStringList reservations;
  QStringList sources;
  // Détail lu directement dans la nomenclature, jamais une seconde BOM.
  QJsonObject definition;
};

struct HardwareInventory {
  QString sourcePath;
  QString reference;
  QString date;
  QString status;
  QString qualification;
  QString selection;
  QJsonObject configuration;
  QList<HardwareItem> items;
};

struct WorkspaceDiagnostics {
  QString statePath;
  QString hardwareSourcePath;
  bool stateExists{false};
  bool stateReadable{false};
  bool hardwareReadable{false};
  qsizetype missionCount{0};
  qsizetype favoriteCount{0};
  qsizetype hardwareItemCount{0};
  QStringList messages;
};

}  // namespace drone_agricole::domain
