#include "drone_agricole/composition/StationCommand.hpp"
#include "drone_agricole/composition/StationComposition.hpp"
#include "drone_agricole/core/JsonUtils.hpp"
#include <QDir>
#include <QEventLoop>
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
}
