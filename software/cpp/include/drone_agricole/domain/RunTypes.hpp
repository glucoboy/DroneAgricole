#pragma once

#include <QJsonObject>
#include <QStringList>

namespace drone_agricole::domain {

struct PreparedRun {
  QString runId;
  QString simulationId;
  QString variantId;
  QString runnerId;
  QString program;
  QStringList arguments;
  QString workingDirectory;
  QString resultDirectory;
  QJsonObject request;
  QString stopProgram;
  QStringList stopArguments;
};

enum class RunState { Idle, Preparing, Running, Cancelling, Finalizing, Completed, Cancelled, Failed };

inline bool isActive(RunState state) {
  return state == RunState::Preparing || state == RunState::Running ||
         state == RunState::Cancelling || state == RunState::Finalizing;
}

inline QString stateLabel(RunState state) {
  switch (state) {
    case RunState::Idle: return QStringLiteral("Aucun traitement");
    case RunState::Preparing: return QStringLiteral("Préparation");
    case RunState::Running: return QStringLiteral("En cours");
    case RunState::Cancelling: return QStringLiteral("Annulation demandée");
    case RunState::Finalizing: return QStringLiteral("Finalisation des résultats");
    case RunState::Completed: return QStringLiteral("Terminé · résultats archivés");
    case RunState::Cancelled: return QStringLiteral("Annulé");
    case RunState::Failed: return QStringLiteral("Échec");
  }
  return {};
}
}  // namespace drone_agricole::domain
