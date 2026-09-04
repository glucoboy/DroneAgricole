#pragma once

#include <QList>
#include <QString>

#include <optional>

namespace drone_agricole::station {

enum class PackageKind {
  SurveyMission,
  SurveyRun,
  VineyardMap,
  TreatmentMission,
  MissionReport,
};

enum class StationStage {
  SurveyReception,
  SurveyCompilation,
  MapConstruction,
  MapEditing,
  MapApproval,
  TreatmentMissionPreparation,
  MissionSimulation,
  OperationalTransfer,
  TreatmentReturnReception,
  TreatmentReportCompilation,
};

enum class ModuleMaturity {
  Planned,
  Prototype,
  OperationalPreliminary,
};

struct StationModuleDescriptor {
  QString id;
  QString label;
  QString responsibility;
  StationStage stage;
  QList<PackageKind> consumes;
  QList<PackageKind> produces;
  ModuleMaturity maturity{ModuleMaturity::Planned};
  bool requiresOperatorApproval{false};
  bool controlsFlightCriticalFunctions{false};
};

class StationArchitecture final {
 public:
  [[nodiscard]] static QList<StationModuleDescriptor> modules();
  [[nodiscard]] static QStringList nominalWorkflowModuleIds();
  [[nodiscard]] static std::optional<StationModuleDescriptor> module(const QString& id);
  [[nodiscard]] static QString packageKindId(PackageKind kind);
  [[nodiscard]] static QString stageId(StationStage stage);
  [[nodiscard]] static QString maturityId(ModuleMaturity maturity);
};

}  // namespace drone_agricole::station
