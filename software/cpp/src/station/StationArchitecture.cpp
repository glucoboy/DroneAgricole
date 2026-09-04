#include "drone_agricole/station/StationArchitecture.hpp"

#include <algorithm>

namespace drone_agricole::station {

QList<StationModuleDescriptor> StationArchitecture::modules() {
  return {
      {QStringLiteral("survey-reception"), QStringLiteral("Réception cartographe"),
       QStringLiteral("Importer, vérifier et enregistrer un SurveyRunPackage sans modifier les données brutes."),
       StationStage::SurveyReception, {PackageKind::SurveyRun}, {PackageKind::SurveyRun}, ModuleMaturity::Planned,
       false, false},
      {QStringLiteral("survey-compilation"), QStringLiteral("Compilation des acquisitions"),
       QStringLiteral("Contrôler les horodatages, calibrations, couvertures et préparer les données reproductibles."),
       StationStage::SurveyCompilation, {PackageKind::SurveyRun}, {PackageKind::SurveyRun}, ModuleMaturity::Prototype,
       false, false},
      {QStringLiteral("map-construction"), QStringLiteral("Construction de la carte"),
       QStringLiteral("Produire une trajectoire optimisée et un VineyardMapPackage candidat à partir des acquisitions."),
       StationStage::MapConstruction, {PackageKind::SurveyRun}, {PackageKind::VineyardMap}, ModuleMaturity::Planned,
       false, false},
      {QStringLiteral("map-editing"), QStringLiteral("Édition de la carte"),
       QStringLiteral("Éditer les entités, zones, prescriptions et instructions métier dans une nouvelle version candidate."),
       StationStage::MapEditing, {PackageKind::VineyardMap}, {PackageKind::VineyardMap}, ModuleMaturity::Planned,
       false, false},
      {QStringLiteral("map-approval"), QStringLiteral("Contrôle et signature"),
       QStringLiteral("Contrôler la qualité et associer une preuve d'approbation à l'empreinte de la carte."),
       StationStage::MapApproval, {PackageKind::VineyardMap}, {PackageKind::VineyardMap}, ModuleMaturity::Planned,
       true, false},
      {QStringLiteral("treatment-mission-preparation"), QStringLiteral("Préparation de la mission"),
       QStringLiteral("Construire la mission de traitement depuis une carte approuvée et des prescriptions autorisées."),
       StationStage::TreatmentMissionPreparation, {PackageKind::VineyardMap}, {PackageKind::TreatmentMission},
       ModuleMaturity::Planned, true, false},
      {QStringLiteral("mission-simulation"), QStringLiteral("Simulation et validation"),
       QStringLiteral("Simuler les scénarios autorisés et conserver les résultats nécessaires à la porte de mission."),
       StationStage::MissionSimulation, {PackageKind::TreatmentMission}, {}, ModuleMaturity::OperationalPreliminary,
       true, false},
      {QStringLiteral("operational-transfer"), QStringLiteral("Transfert vers le drone de traitement"),
       QStringLiteral("Vérifier puis transférer les paquets approuvés avec un accusé de réception traçable."),
       StationStage::OperationalTransfer, {PackageKind::VineyardMap, PackageKind::TreatmentMission}, {},
       ModuleMaturity::Planned, true, false},
      {QStringLiteral("treatment-return-reception"), QStringLiteral("Réception des données de traitement"),
       QStringLiteral("Importer et contrôler le MissionReportPackage et les données associées au retour du drone."),
       StationStage::TreatmentReturnReception, {PackageKind::MissionReport}, {PackageKind::MissionReport},
       ModuleMaturity::Planned, false, false},
      {QStringLiteral("treatment-report-compilation"), QStringLiteral("Rapport de traitement"),
       QStringLiteral("Compiler trajectoires, couverture, actions du bras, doses, incidents et événements en rapport."),
       StationStage::TreatmentReportCompilation, {PackageKind::MissionReport}, {PackageKind::MissionReport},
       ModuleMaturity::Planned, false, false},
  };
}

QStringList StationArchitecture::nominalWorkflowModuleIds() {
  QStringList result;
  for (const auto& descriptor : modules()) {
    result.append(descriptor.id);
  }
  return result;
}

std::optional<StationModuleDescriptor> StationArchitecture::module(const QString& id) {
  const auto available = modules();
  const auto found = std::find_if(available.cbegin(), available.cend(),
                                  [&id](const auto& descriptor) { return descriptor.id == id; });
  return found == available.cend() ? std::nullopt : std::optional<StationModuleDescriptor>(*found);
}

QString StationArchitecture::packageKindId(const PackageKind kind) {
  switch (kind) {
    case PackageKind::SurveyMission:
      return QStringLiteral("SurveyMissionPackage");
    case PackageKind::SurveyRun:
      return QStringLiteral("SurveyRunPackage");
    case PackageKind::VineyardMap:
      return QStringLiteral("VineyardMapPackage");
    case PackageKind::TreatmentMission:
      return QStringLiteral("TreatmentMissionPackage");
    case PackageKind::MissionReport:
      return QStringLiteral("MissionReportPackage");
  }
  return {};
}

QString StationArchitecture::stageId(const StationStage stage) {
  switch (stage) {
    case StationStage::SurveyReception:
      return QStringLiteral("survey_reception");
    case StationStage::SurveyCompilation:
      return QStringLiteral("survey_compilation");
    case StationStage::MapConstruction:
      return QStringLiteral("map_construction");
    case StationStage::MapEditing:
      return QStringLiteral("map_editing");
    case StationStage::MapApproval:
      return QStringLiteral("map_approval");
    case StationStage::TreatmentMissionPreparation:
      return QStringLiteral("treatment_mission_preparation");
    case StationStage::MissionSimulation:
      return QStringLiteral("mission_simulation");
    case StationStage::OperationalTransfer:
      return QStringLiteral("operational_transfer");
    case StationStage::TreatmentReturnReception:
      return QStringLiteral("treatment_return_reception");
    case StationStage::TreatmentReportCompilation:
      return QStringLiteral("treatment_report_compilation");
  }
  return {};
}

QString StationArchitecture::maturityId(const ModuleMaturity maturity) {
  switch (maturity) {
    case ModuleMaturity::Planned:
      return QStringLiteral("planned");
    case ModuleMaturity::Prototype:
      return QStringLiteral("prototype");
    case ModuleMaturity::OperationalPreliminary:
      return QStringLiteral("operational_preliminary");
  }
  return {};
}

}  // namespace drone_agricole::station
