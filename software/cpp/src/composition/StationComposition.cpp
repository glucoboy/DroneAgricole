#include "drone_agricole/composition/StationComposition.hpp"
#include "drone_agricole/core/JsonUtils.hpp"
#include "drone_agricole/core/ResultAdapter.hpp"
#include <QFileInfo>
#include <QSaveFile>

namespace drone_agricole::composition {
StationComposition::StationComposition(const QString& workspace)
    : contracts_(workspace), runners_(contracts_), repository_(workspace), comparison_(repository_),
      execution_(*this, backend_, *this) {
  contracts_.load();
  repository_.refresh();
}

domain::PreparedRun StationComposition::prepare(const QJsonObject& request) {
  core::requireSchema(request, QStringLiteral("drone_agricole.run_request.v1"), QStringLiteral("Demande de traitement"));
  if (!request.value(QStringLiteral("parameters")).isObject() || !request.value(QStringLiteral("inputs")).isArray())
    throw core::ContractError(QStringLiteral("La requête exige un objet parameters et un tableau inputs"));
  // Valider à la frontière commune, y compris pour une requête fournie par la CLI.
  const auto inputs = request.value(QStringLiteral("inputs")).toArray();
  const auto reference = inputs.isEmpty() ? QJsonObject{} : inputs.first().toObject().value(QStringLiteral("reference")).toObject();
  auto validated = contracts_.resolveRequest(request.value(QStringLiteral("simulation_id")).toString(),
      request.value(QStringLiteral("variant_id")).toString(), request.value(QStringLiteral("profile_id")).toString(),
      reference.value(QStringLiteral("dataset_id")).toString(), reference.value(QStringLiteral("sequence_id")).toString(),
      request.value(QStringLiteral("parameters")).toObject());
  if (request.value(QStringLiteral("inputs")).toArray() != validated.value(QStringLiteral("inputs")).toArray())
    throw core::ContractError(QStringLiteral("Entrées de la requête non conformes au catalogue"));
  for (const auto& key : {QStringLiteral("request_id"), QStringLiteral("requested_at_utc"), QStringLiteral("tags")}) {
    if (request.contains(key)) validated.insert(key, request.value(key));
  }
  return runners_.prepare(validated);
}

void StationComposition::finalize(const domain::PreparedRun& run) {
  if (!QFileInfo(run.resultDirectory).isDir())
    throw core::ContractError(QStringLiteral("Le traitement n'a pas créé de dossier de résultat : %1").arg(run.resultDirectory));
  const auto normalized = core::normalizeResultDirectory(run.resultDirectory);
  core::writeNativeContracts(normalized, run.request);
}

void StationComposition::exportReport(const QString& path, const QString& report) {
  QSaveFile file(path);
  const auto bytes = report.toUtf8();
  if (!file.open(QIODevice::WriteOnly) || file.write(bytes) != bytes.size() || !file.commit())
    throw core::ContractError(QStringLiteral("Écriture du rapport impossible : %1").arg(path));
}

void StationComposition::resetTelemetry() {
  if (!telemetry_) telemetry_ = std::make_unique<core::LiveTelemetry>();
  telemetry_->reset();
}
core::LiveTelemetrySnapshot StationComposition::snapshot() {
  if (!telemetry_) telemetry_ = std::make_unique<core::LiveTelemetry>();
  return telemetry_->snapshot();
}
}  // namespace drone_agricole::composition
