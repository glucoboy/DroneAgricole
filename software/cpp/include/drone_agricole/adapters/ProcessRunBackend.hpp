#pragma once
#include "drone_agricole/application/RunPorts.hpp"
#include <QProcess>
#include <QTimer>

namespace drone_agricole::adapters {
class ProcessRunBackend final : public application::IRunBackend {
  Q_OBJECT
 public:
  explicit ProcessRunBackend(QObject* parent = nullptr);
  ~ProcessRunBackend() override;
  void start(const domain::PreparedRun& run) override;
  void cancel() override;
  bool cancellationConfirmed() const override { return cancellationConfirmed_; }
 private:
  QProcess process_;
  QProcess stop_;
  QTimer killTimer_;
  QTimer stopTimer_;
  domain::PreparedRun run_;
  bool delivered_{true};
  bool processDone_{false};
  bool stopping_{false};
  bool cancellationConfirmed_{false};
  int exitCode_{-1};
  bool normalExit_{false};
  void deliverIfDone();
  void terminateClient();
};
}  // namespace drone_agricole::adapters
