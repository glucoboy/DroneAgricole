#pragma once
#include <QObject>
#include <QJsonObject>
#include <QThread>
#include <atomic>
#include <functional>

namespace drone_agricole::application {
struct GazeboExportRequest {
  QString pythonProgram;
  QString outputDirectory;
  bool regenerateMeshes{true};
};
class IGazeboExportBackend {
 public:
  using Progress = std::function<void(int, const QString&)>;
  virtual ~IGazeboExportBackend() = default;
  virtual QJsonObject inspect() const = 0;
  virtual QJsonObject execute(const GazeboExportRequest&, const std::atomic_bool&, Progress) = 0;
};
// Preparation of a model asset, independent of flight RunService and its T0 runs.
class GazeboExportService final : public QObject {
  Q_OBJECT
 public:
  explicit GazeboExportService(IGazeboExportBackend&, QObject* parent = nullptr);
  ~GazeboExportService() override;
  QJsonObject inspect() const;
  bool start(const GazeboExportRequest&);
  void cancel();
  bool active() const { return state_ == QStringLiteral("running"); }
  QString state() const { return state_; }
  QString message() const { return message_; }
  int progress() const { return progress_; }
  QJsonObject result() const { return result_; }
 signals:
  void changed();
  void output(const QString&);
  void completed();
 private:
  IGazeboExportBackend& backend_;
  QThread* worker_{nullptr};
  std::atomic_bool cancelled_{false};
  QString state_{QStringLiteral("idle")}, message_;
  int progress_{0};
  QJsonObject result_;
};
}
