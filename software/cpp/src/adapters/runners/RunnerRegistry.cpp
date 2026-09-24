#include "drone_agricole/core/RunnerRegistry.hpp"
#include "drone_agricole/core/JsonUtils.hpp"
#include <QUuid>
#include <algorithm>
namespace drone_agricole::core {
void registerBuiltInRunners(RunnerRegistry&, const ContractRegistry&);
RunnerRegistry::RunnerRegistry(const ContractRegistry& contracts) : contracts_(contracts) {
  registerBuiltInRunners(*this, contracts);
}
void RunnerRegistry::registerRunner(const QString& id, Factory factory) {
  if (id.isEmpty() || !factory || factories_.contains(id))
    throw ContractError(QStringLiteral("Runner vide, invalide ou déjà enregistré : %1").arg(id));
  factories_.insert(id, std::move(factory));
  orderedIds_.append(id);
}
QStringList RunnerRegistry::approvedRunnerIds() const { return orderedIds_; }
PreparedRun RunnerRegistry::prepare(const QJsonObject& request, QString runId, QDateTime timestamp) const {
  const auto simulationId = request.value(QStringLiteral("simulation_id")).toString();
  const auto variantId = request.value(QStringLiteral("variant_id")).toString();
  const auto& simulation = contracts_.simulation(simulationId);
  const auto& variant = contracts_.variant(simulationId, variantId);
  const auto factory = factories_.constFind(variant.runnerId);
  if (factory == factories_.cend()) throw ContractError(QStringLiteral("Aucun runner approuvé pour %1").arg(variant.runnerId));
  if (runId.isEmpty()) runId = QUuid::createUuid().toString(QUuid::Id128).left(8);
  RunnerContext context{simulation, variant, request, {}, request.value(QStringLiteral("profile_id")).toString(),
                        runId, timestamp.toUTC().toString(QStringLiteral("yyyyMMdd'T'HHmmss'Z'"))};
  if (!simulation.selectors.isEmpty()) {
    QString datasetId, sequenceId;
    for (const auto& input : request.value(QStringLiteral("inputs")).toArray()) {
      if (input.toObject().value(QStringLiteral("kind")).toString() == QStringLiteral("dataset_sequence")) {
        const auto reference = input.toObject().value(QStringLiteral("reference")).toObject();
        datasetId = reference.value(QStringLiteral("dataset_id")).toString();
        sequenceId = reference.value(QStringLiteral("sequence_id")).toString();
      }
    }
    const auto compatible = contracts_.compatibleSequences(simulationId, variantId);
    const auto sequence = std::find_if(compatible.cbegin(), compatible.cend(), [&](const auto& item) {
      return item.datasetId == datasetId && item.sequenceId == sequenceId;
    });
    if (sequence == compatible.cend()) throw ContractError(QStringLiteral("Une séquence compatible doit être sélectionnée"));
    context.sequence = *sequence;
  } else if (!request.value(QStringLiteral("inputs")).toArray().isEmpty()) {
    throw ContractError(QStringLiteral("Cette simulation n'accepte pas d'entrée sélectionnable"));
  }
  return (*factory)(context);
}
}
