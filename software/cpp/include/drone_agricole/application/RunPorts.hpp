#pragma once

#include "drone_agricole/domain/RunTypes.hpp"
#include <QObject>

namespace drone_agricole::application {

class IRunPreparation {
 public:
  virtual ~IRunPreparation() = default;
  virtual domain::PreparedRun prepare(const QJsonObject& request) = 0;
};

class IResultFinalizer {
 public:
  virtual ~IResultFinalizer() = default;
  virtual void finalize(const domain::PreparedRun& run) = 0;
};

// Un seul lancement en vol. finished est émis une seule fois, après l'arrêt
// du client et de l'éventuelle commande de nettoyage du backend.
class IRunBackend : public QObject {
  Q_OBJECT
 public:
  using QObject::QObject;
  virtual void start(const domain::PreparedRun& run) = 0;
  virtual void cancel() = 0;
  [[nodiscard]] virtual bool cancellationConfirmed() const { return true; }
 signals:
  void started();
  void output(const QString& text);
  void finished(int exitCode, bool normalExit);
  void diagnostic(const QString& text);
};
}  // namespace drone_agricole::application
