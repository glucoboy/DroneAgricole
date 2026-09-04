#include "drone_agricole_px4_bridge/RunnerContract.hpp"

#include <QDir>
#include <QFileInfo>
#include <QJsonValue>
#include <QRegularExpression>
#include <QSet>

#include <cmath>

namespace drone_agricole::px4 {

RunnerContractError::RunnerContractError(const QString& message) : std::runtime_error(message.toStdString()) {}

QString rosDoubleParameterValue(const double value) {
  auto formatted = QString::number(value, 'g', 12);
  if (!formatted.contains(QLatin1Char('.')) && !formatted.contains(QLatin1Char('e'), Qt::CaseInsensitive)) {
    formatted += QStringLiteral(".0");
  }
  return formatted;
}

QJsonObject validateStartPayload(const QJsonObject& payload, const QString& workspace) {
  static const QSet<QString> allowed{QStringLiteral("run_id"), QStringLiteral("mode"),
                                     QStringLiteral("result_directory"), QStringLiteral("parameters")};
  for (auto iterator = payload.constBegin(); iterator != payload.constEnd(); ++iterator) {
    if (!allowed.contains(iterator.key())) {
      throw RunnerContractError(QStringLiteral("Champ inconnu : %1").arg(iterator.key()));
    }
  }
  const auto runId = payload.value(QStringLiteral("run_id")).toString();
  static const QRegularExpression identifier(QStringLiteral("^[a-z0-9][a-z0-9_-]{0,95}$"));
  if (!identifier.match(runId).hasMatch()) {
    throw RunnerContractError(QStringLiteral("run_id invalide."));
  }
  const auto mode = payload.value(QStringLiteral("mode")).toString();
  if (mode != QStringLiteral("square") && mode != QStringLiteral("failsafe")) {
    throw RunnerContractError(QStringLiteral("mode doit valoir square ou failsafe."));
  }
  const auto relative = payload.value(QStringLiteral("result_directory")).toString();
  const auto cleaned = QDir::cleanPath(relative);
  if (relative.isEmpty() || QDir::isAbsolutePath(relative) || relative.contains(QLatin1Char('\\')) ||
      cleaned == QStringLiteral("..") || cleaned.startsWith(QStringLiteral("../")) ||
      !cleaned.startsWith(QStringLiteral("results/simulation/px4_lot_a/"))) {
    throw RunnerContractError(QStringLiteral("result_directory doit rester dans results/simulation/px4_lot_a."));
  }
  const auto workspacePath = QFileInfo(workspace).absoluteFilePath();
  const auto resultPath = QFileInfo(QDir(workspacePath).filePath(cleaned)).absoluteFilePath();
  const auto rootPrefix = QDir(workspacePath).filePath(QStringLiteral("results/simulation/px4_lot_a/"));
  if (!resultPath.startsWith(rootPrefix) || QFileInfo::exists(resultPath)) {
    throw RunnerContractError(QFileInfo::exists(resultPath) ? QStringLiteral("Le répertoire de résultat existe déjà.")
                                                            : QStringLiteral("result_directory sort du workspace."));
  }
  const auto suppliedValue = payload.value(QStringLiteral("parameters"));
  if (!suppliedValue.isObject()) {
    throw RunnerContractError(QStringLiteral("parameters doit être un objet JSON."));
  }
  const auto supplied = suppliedValue.toObject();
  const QHash<QString, QPair<double, double>> bounds{
      {QStringLiteral("takeoff_altitude_m"), {0.5, 10.0}},
      {QStringLiteral("leg_m"), {0.5, 20.0}},
      {QStringLiteral("warmup_s"), {1.0, 10.0}},
      {QStringLiteral("hover_s"), {1.0, 15.0}},
      {QStringLiteral("stage_timeout_s"), {5.0, 30.0}},
  };
  for (auto iterator = supplied.constBegin(); iterator != supplied.constEnd(); ++iterator) {
    if (!bounds.contains(iterator.key())) {
      throw RunnerContractError(QStringLiteral("Paramètre PX4 inconnu : %1").arg(iterator.key()));
    }
  }
  QJsonObject parameters;
  for (auto iterator = bounds.constBegin(); iterator != bounds.constEnd(); ++iterator) {
    const auto value = supplied.value(iterator.key());
    if (!value.isDouble() || !std::isfinite(value.toDouble()) || value.toDouble() < iterator.value().first ||
        value.toDouble() > iterator.value().second) {
      throw RunnerContractError(QStringLiteral("Paramètre PX4 absent ou hors limites : %1").arg(iterator.key()));
    }
    parameters.insert(iterator.key(), value.toDouble());
  }
  return {{QStringLiteral("run_id"), runId},
          {QStringLiteral("mode"), mode},
          {QStringLiteral("result_directory"), cleaned},
          {QStringLiteral("parameters"), parameters}};
}

}  // namespace drone_agricole::px4
