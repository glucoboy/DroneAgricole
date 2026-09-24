#include "drone_agricole/adapters/ProcessRunBackend.hpp"
#include <QProcessEnvironment>
#include <stdexcept>

namespace drone_agricole::adapters {
ProcessRunBackend::ProcessRunBackend(QObject* parent) : IRunBackend(parent) {
  killTimer_.setSingleShot(true);
  killTimer_.setInterval(15000);
  stopTimer_.setSingleShot(true);
  stopTimer_.setInterval(15000);
  connect(&killTimer_, &QTimer::timeout, &process_, &QProcess::kill);
  connect(&stopTimer_, &QTimer::timeout, this, [this] {
    emit diagnostic(QStringLiteral("Délai de confirmation d'arrêt dépassé ; arrêt forcé du client."));
    stop_.kill();
  });
  connect(&process_, &QProcess::started, this, [this] {
    emit started();
    if (killTimer_.isActive()) process_.terminate();
  });
  connect(&process_, &QProcess::readyReadStandardOutput, this, [this] {
    emit output(QString::fromUtf8(process_.readAllStandardOutput()));
  });
  connect(&process_, &QProcess::readyReadStandardError, this, [this] {
    emit output(QString::fromUtf8(process_.readAllStandardError()));
  });
  connect(&process_, &QProcess::errorOccurred, this, [this](QProcess::ProcessError error) {
    emit diagnostic(process_.errorString());
    if (error == QProcess::FailedToStart) {
      processDone_ = true;
      deliverIfDone();
    }
  });
  connect(&process_, qOverload<int, QProcess::ExitStatus>(&QProcess::finished), this,
          [this](int code, QProcess::ExitStatus status) {
    emit output(QString::fromUtf8(process_.readAllStandardOutput()));
    emit output(QString::fromUtf8(process_.readAllStandardError()));
    processDone_ = true;
    exitCode_ = code;
    normalExit_ = status == QProcess::NormalExit;
    killTimer_.stop();
    deliverIfDone();
  });
  connect(&stop_, qOverload<int, QProcess::ExitStatus>(&QProcess::finished), this,
          [this](int code, QProcess::ExitStatus status) {
    stopTimer_.stop();
    cancellationConfirmed_ = code == 0 && status == QProcess::NormalExit;
    emit diagnostic(code == 0 && status == QProcess::NormalExit
        ? QStringLiteral("Commande d'arrêt transmise au runner.")
        : QStringLiteral("Arrêt non confirmé par le runner ; PX4 conserve ses failsafes."));
    stopping_ = false;
    terminateClient();
  });
  connect(&stop_, &QProcess::errorOccurred, this, [this](QProcess::ProcessError error) {
    if (error == QProcess::FailedToStart) {
      stopTimer_.stop();
      emit diagnostic(QStringLiteral("Commande d'arrêt indisponible : %1").arg(stop_.errorString()));
      stopping_ = false;
      terminateClient();
    }
  });
}

ProcessRunBackend::~ProcessRunBackend() {
  // La fermeture normale attend completed ; filet de nettoyage à la destruction.
  for (auto* process : {&stop_, &process_}) {
    if (process->state() != QProcess::NotRunning) {
      process->kill();
      process->waitForFinished(3000);
    }
  }
}

void ProcessRunBackend::start(const domain::PreparedRun& run) {
  if (!delivered_) throw std::runtime_error("Un processus est déjà actif");
  run_ = run;
  delivered_ = false;
  processDone_ = false;
  stopping_ = false;
  cancellationConfirmed_ = false;
  exitCode_ = -1;
  normalExit_ = false;
  auto environment = QProcessEnvironment::systemEnvironment();
  environment.insert(QStringLiteral("FASTLIO_DASHBOARD"), QStringLiteral("1"));
  environment.insert(QStringLiteral("LIO_DASHBOARD"), QStringLiteral("1"));
  process_.setProcessEnvironment(environment);
  process_.setWorkingDirectory(run.workingDirectory);
  process_.start(run.program, run.arguments);
}

void ProcessRunBackend::cancel() {
  if (delivered_ || stopping_) return;
  if (run_.stopProgram.isEmpty()) {
    cancellationConfirmed_ = true;
    terminateClient();
    return;
  }
  stopping_ = true;
  stop_.setWorkingDirectory(run_.workingDirectory);
  stop_.start(run_.stopProgram, run_.stopArguments);
  stopTimer_.start();
}

void ProcessRunBackend::terminateClient() {
  if (!processDone_) {
    process_.terminate();
    killTimer_.start();
  }
  deliverIfDone();
}

void ProcessRunBackend::deliverIfDone() {
  if (delivered_ || !processDone_ || stopping_) return;
  delivered_ = true;
  killTimer_.stop();
  stopTimer_.stop();
  emit finished(exitCode_, normalExit_);
}
}  // namespace drone_agricole::adapters
