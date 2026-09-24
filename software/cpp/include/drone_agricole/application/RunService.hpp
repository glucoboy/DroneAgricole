#pragma once

#include "drone_agricole/application/RunPorts.hpp"
#include <optional>

namespace drone_agricole::application {

class RunService final : public QObject {
  Q_OBJECT
 public:
  RunService(IRunPreparation& preparation, IRunBackend& backend, IResultFinalizer& finalizer,
             QObject* parent = nullptr);
  bool start(const QJsonObject& request);
  void cancel();
  [[nodiscard]] domain::RunState state() const { return state_; }
  [[nodiscard]] bool active() const { return domain::isActive(state_); }
  [[nodiscard]] const std::optional<domain::PreparedRun>& run() const { return run_; }
  [[nodiscard]] QString message() const { return message_; }
  [[nodiscard]] int progress() const { return progress_; }
 signals:
  void changed();
  void output(const QString& text);
  void completed();
 private:
  IRunPreparation& preparation_;
  IRunBackend& backend_;
  IResultFinalizer& finalizer_;
  domain::RunState state_{domain::RunState::Idle};
  std::optional<domain::PreparedRun> run_;
  QString message_;
  QString lineBuffer_;
  int progress_{0};
  void transition(domain::RunState state, const QString& message = {});
  void finish(int exitCode, bool normalExit);
  void consumeOutput(const QString& text);
};
}  // namespace drone_agricole::application
