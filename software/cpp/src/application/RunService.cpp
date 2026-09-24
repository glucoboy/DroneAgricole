#include "drone_agricole/application/RunService.hpp"
#include <QRegularExpression>
#include <algorithm>
#include <exception>

namespace drone_agricole::application {
using domain::RunState;

RunService::RunService(IRunPreparation& preparation, IRunBackend& backend,
                       IResultFinalizer& finalizer, QObject* parent)
    : QObject(parent), preparation_(preparation), backend_(backend), finalizer_(finalizer) {
  connect(&backend_, &IRunBackend::started, this, [this] {
    if (state_ == RunState::Preparing) transition(RunState::Running);
  });
  connect(&backend_, &IRunBackend::output, this, &RunService::consumeOutput);
  connect(&backend_, &IRunBackend::diagnostic, this, &RunService::output);
  connect(&backend_, &IRunBackend::finished, this, &RunService::finish);
}

void RunService::transition(RunState state, const QString& message) {
  state_ = state;
  message_ = message.isEmpty() ? domain::stateLabel(state) : message;
  emit changed();
}

bool RunService::start(const QJsonObject& request) {
  if (active()) return false;
  run_.reset();
  progress_ = 0;
  lineBuffer_.clear();
  transition(RunState::Preparing);
  try {
    run_ = preparation_.prepare(request);
    emit output(QStringLiteral("Lancement %1 · %2\nCommande approuvée : %3 %4")
                    .arg(run_->simulationId, run_->variantId, run_->program,
                         run_->arguments.join(QLatin1Char(' '))));
    backend_.start(*run_);
    return true;
  } catch (const std::exception& error) {
    transition(RunState::Failed, QString::fromUtf8(error.what()));
    emit output(message_);
    emit completed();
    return false;
  }
}

void RunService::cancel() {
  if (state_ != RunState::Running && state_ != RunState::Preparing) return;
  // La préparation est synchrone ; l'annulation effective concerne le backend.
  if (!run_) return;
  transition(RunState::Cancelling);
  backend_.cancel();
}

void RunService::finish(int exitCode, bool normalExit) {
  if (!active() || !run_) return;
  if (state_ == RunState::Cancelling) {
    if (backend_.cancellationConfirmed())
      transition(RunState::Cancelled, QStringLiteral("Annulé · résultats partiels conservés s'ils existent"));
    else
      transition(RunState::Failed, QStringLiteral("Client arrêté · annulation du traitement distant non confirmée ; consulter le journal"));
  } else if (!normalExit || exitCode != 0) {
    transition(RunState::Failed, QStringLiteral("Échec du traitement (code %1) · consulter le journal").arg(exitCode));
  } else {
    transition(RunState::Finalizing);
    try {
      finalizer_.finalize(*run_);
      progress_ = 100;
      transition(RunState::Completed);
      emit output(QStringLiteral("Contrats T0 natifs archivés et validés."));
    } catch (const std::exception& error) {
      transition(RunState::Failed, QStringLiteral("Calcul terminé · finalisation en échec : %1")
                                      .arg(QString::fromUtf8(error.what())));
    }
  }
  emit output(message_);
  emit completed();
}

void RunService::consumeOutput(const QString& text) {
  emit output(text);
  if (!active()) return;
  lineBuffer_.append(text);
  static const QRegularExpression expression(
      QStringLiteral("^(?:LIO|MAP)_PROGRESS stage=([a-z_]+) percent=(\\d+)(?: .*)?$"));
  while (true) {
    const auto newline = lineBuffer_.indexOf(QLatin1Char('\n'));
    if (newline < 0) break;
    const auto line = lineBuffer_.left(newline).trimmed();
    lineBuffer_.remove(0, newline + 1);
    const auto match = expression.match(line);
    if (match.hasMatch() && state_ != RunState::Cancelling) {
      // Le 100 % du runner n'est pas encore une finalisation validée.
      progress_ = std::clamp(match.captured(2).toInt(), 0, 99);
      emit changed();
    }
  }
  if (lineBuffer_.size() > 8192) lineBuffer_.clear();
}
}  // namespace drone_agricole::application
