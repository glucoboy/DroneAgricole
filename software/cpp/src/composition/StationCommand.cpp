#include "drone_agricole/composition/StationCommand.hpp"
#include "drone_agricole/composition/StationComposition.hpp"
#include "drone_agricole/core/JsonUtils.hpp"
#include <QDir>
#include <QEventLoop>
#include <QJsonArray>
#include <QJsonDocument>
#include <QTextStream>
#include <QTimer>
#include <csignal>

namespace drone_agricole::composition {
namespace {
volatile std::sig_atomic_t interrupted = 0;
void handleSignal(int) { interrupted = 1; }
struct SignalScope {
  using Handler = void (*)(int);
  Handler interrupt = std::signal(SIGINT, handleSignal);
  Handler terminate = std::signal(SIGTERM, handleSignal);
  ~SignalScope() { std::signal(SIGINT, interrupt); std::signal(SIGTERM, terminate); }
};
}
int runStationCommand(const QJsonObject& options) {
  const auto requestPath = options.value(QStringLiteral("request")).toString();
  if (requestPath.isEmpty()) throw core::ContractError(QStringLiteral("station-run exige --request chemin.json"));
  StationComposition services(options.value(QStringLiteral("workspace")).toString(QDir::currentPath()));
  auto& execution = services.execution();
  QEventLoop loop;
  QObject::connect(&execution, &application::RunService::output, &loop, [](const QString& text) {
    QTextStream(stdout) << text << Qt::endl;
  });
  QObject::connect(&execution, &application::RunService::completed, &loop, &QEventLoop::quit);
  interrupted = 0;
  SignalScope signalScope;
  QTimer interruptTimer;
  QObject::connect(&interruptTimer, &QTimer::timeout, &loop, [&execution] {
    if (interrupted) execution.cancel();
  });
  interruptTimer.start(100);
  if (!execution.start(core::readJsonObject(requestPath))) return 2;
  if (execution.active()) loop.exec();
  if (execution.state() == domain::RunState::Cancelled) return 130;
  return execution.state() == domain::RunState::Completed ? 0 : 1;
}

int runStationWorkspaceCommand(const QJsonObject& options) {
  StationComposition services(options.value(QStringLiteral("workspace")).toString(QDir::currentPath()));
  auto& workspace = services.workspaceData();
  const auto positional = options.value(QStringLiteral("positional")).toArray();
  const auto action = options.value(QStringLiteral("action")).toString(
      positional.isEmpty() ? QStringLiteral("diagnostics") : positional.first().toString());
  const auto id = options.value(QStringLiteral("id")).toString();
  const auto path = options.value(QStringLiteral("path")).toString();
  QJsonObject output;
  if (action == QStringLiteral("missions")) {
    QJsonArray missions;
    for (const auto& mission : workspace.missions()) missions.append(application::WorkspaceService::missionDocument(mission));
    output.insert(QStringLiteral("missions"), missions);
  } else if (action == QStringLiteral("mission-import")) {
    output = application::WorkspaceService::missionDocument(workspace.importMission(path));
  } else if (action == QStringLiteral("mission-export")) {
    workspace.exportMission(id, path);
    output = {{QStringLiteral("exported"), path}, {QStringLiteral("execution_allowed"), false}};
  } else if (action == QStringLiteral("mission-remove")) {
    output.insert(QStringLiteral("removed"), workspace.removeMission(id));
  } else if (action == QStringLiteral("preferences")) {
    if (options.contains(QStringLiteral("theme"))) {
      auto preferences = workspace.preferences();
      preferences.themeId = options.value(QStringLiteral("theme")).toString();
      workspace.savePreferences(preferences);
    }
    const auto preferences = workspace.preferences();
    output = {{QStringLiteral("theme_id"), preferences.themeId},
              {QStringLiteral("favorite_result_ids"), QJsonArray::fromStringList(preferences.favoriteResultIds)}};
  } else if (action == QStringLiteral("favorite-add") || action == QStringLiteral("favorite-remove")) {
    if (id.isEmpty()) throw core::ContractError(QStringLiteral("Un favori exige --id"));
    workspace.setFavoriteResult(id, action == QStringLiteral("favorite-add"));
    output = {{QStringLiteral("id"), id}, {QStringLiteral("favorite"), workspace.isFavoriteResult(id)}};
  } else if (action == QStringLiteral("hardware")) {
    const auto hardware = workspace.hardwareInventory();
    QJsonArray items;
    for (const auto& item : hardware.items) items.append(item.definition);
    output = {{QStringLiteral("source"), hardware.sourcePath}, {QStringLiteral("reference"), hardware.reference},
              {QStringLiteral("date"), hardware.date}, {QStringLiteral("status"), hardware.status},
              {QStringLiteral("qualification"), hardware.qualification},
              {QStringLiteral("configuration"), hardware.configuration}, {QStringLiteral("items"), items}};
  } else if (action == QStringLiteral("diagnostics")) {
    const auto diagnostics = workspace.diagnostics();
    output = {{QStringLiteral("state_path"), diagnostics.statePath}, {QStringLiteral("hardware_source"), diagnostics.hardwareSourcePath},
              {QStringLiteral("state_exists"), diagnostics.stateExists}, {QStringLiteral("state_readable"), diagnostics.stateReadable},
              {QStringLiteral("hardware_readable"), diagnostics.hardwareReadable},
              {QStringLiteral("mission_count"), static_cast<double>(diagnostics.missionCount)},
              {QStringLiteral("favorite_count"), static_cast<double>(diagnostics.favoriteCount)},
              {QStringLiteral("hardware_item_count"), static_cast<double>(diagnostics.hardwareItemCount)},
              {QStringLiteral("messages"), QJsonArray::fromStringList(diagnostics.messages)}};
    QTextStream(stdout) << QString::fromUtf8(QJsonDocument(output).toJson(QJsonDocument::Indented));
    return diagnostics.stateReadable && diagnostics.hardwareReadable ? 0 : 1;
  } else {
    throw core::ContractError(QStringLiteral("Action station-workspace inconnue : %1").arg(action));
  }
  QTextStream(stdout) << QString::fromUtf8(QJsonDocument(output).toJson(QJsonDocument::Indented));
  return 0;
}
}
