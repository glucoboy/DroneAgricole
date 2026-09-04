#include "drone_agricole/core/ContractRegistry.hpp"

#include "drone_agricole/core/JsonUtils.hpp"

#include <QDir>
#include <QDateTime>
#include <QFileInfo>
#include <QJsonArray>
#include <QSet>
#include <QUuid>

#include <algorithm>
#include <cmath>

namespace drone_agricole::core {
namespace {

QSet<QString> stringSet(const QJsonValue& value) {
  QSet<QString> result;
  for (const auto& item : value.toArray()) {
    if (item.isString() && !item.toString().isEmpty()) {
      result.insert(item.toString());
    }
  }
  return result;
}

QStringList jsonFiles(const QString& directory) {
  QDir dir(directory);
  return dir.entryList({QStringLiteral("*.json")}, QDir::Files, QDir::Name);
}

const ParameterDefinition* findParameter(const SimulationDefinition& simulation,
                                         const VariantDefinition& variant,
                                         const QString& parameterId) {
  const auto shared = std::find_if(simulation.parameters.cbegin(), simulation.parameters.cend(),
                                   [&parameterId](const auto& value) { return value.id == parameterId; });
  if (shared != simulation.parameters.cend()) {
    return &*shared;
  }
  const auto local = std::find_if(variant.parameters.cbegin(), variant.parameters.cend(),
                                  [&parameterId](const auto& value) { return value.id == parameterId; });
  return local == variant.parameters.cend() ? nullptr : &*local;
}

QJsonValue boundedValue(const ParameterDefinition& definition, const QJsonValue& candidate) {
  const auto value = candidate.isUndefined() ? definition.defaultValue : candidate;
  if (definition.type == QStringLiteral("number") || definition.type == QStringLiteral("integer")) {
    if (!value.isDouble()) {
      throw ContractError(QStringLiteral("Le paramètre %1 doit être numérique").arg(definition.id));
    }
    const auto number = value.toDouble();
    if (!definition.minimum.isUndefined() && number < definition.minimum.toDouble()) {
      throw ContractError(QStringLiteral("Le paramètre %1 est inférieur à sa borne").arg(definition.id));
    }
    if (!definition.maximum.isUndefined() && number > definition.maximum.toDouble()) {
      throw ContractError(QStringLiteral("Le paramètre %1 dépasse sa borne").arg(definition.id));
    }
    if (definition.type == QStringLiteral("integer") && number != std::floor(number)) {
      throw ContractError(QStringLiteral("Le paramètre %1 doit être entier").arg(definition.id));
    }
  } else if (definition.type == QStringLiteral("boolean") && !value.isBool()) {
    throw ContractError(QStringLiteral("Le paramètre %1 doit être booléen").arg(definition.id));
  } else if (definition.type == QStringLiteral("string") && !value.isString()) {
    throw ContractError(QStringLiteral("Le paramètre %1 doit être textuel").arg(definition.id));
  }
  return value;
}

}  // namespace

ContractRegistry::ContractRegistry(QString workspace) : workspace_(normalizedPath(std::move(workspace))) {}

void ContractRegistry::load() {
  simulations_.clear();
  sequences_.clear();
  schemaDocumentCount_ = 0;
  loadSchemas();
  loadDatasets();
  loadSimulations();
  if (simulations_.isEmpty()) {
    throw ContractError(QStringLiteral("Aucune simulation T0 publiée"));
  }
}

const QString& ContractRegistry::workspace() const noexcept { return workspace_; }

QList<SimulationDefinition> ContractRegistry::simulations() const {
  auto values = simulations_.values();
  std::sort(values.begin(), values.end(), [](const auto& left, const auto& right) { return left.label < right.label; });
  return values;
}

QList<DatasetSequence> ContractRegistry::datasetSequences() const { return sequences_; }

const SimulationDefinition& ContractRegistry::simulation(const QString& simulationId) const {
  const auto iterator = simulations_.constFind(simulationId);
  if (iterator == simulations_.cend()) {
    throw ContractError(QStringLiteral("Simulation inconnue : %1").arg(simulationId));
  }
  return iterator.value();
}

const VariantDefinition& ContractRegistry::variant(const QString& simulationId, const QString& variantId) const {
  const auto& definition = simulation(simulationId);
  const auto iterator = std::find_if(definition.variants.cbegin(), definition.variants.cend(),
                                     [&variantId](const auto& value) { return value.id == variantId; });
  if (iterator == definition.variants.cend() || !iterator->available) {
    throw ContractError(QStringLiteral("Variante indisponible : %1").arg(variantId));
  }
  return *iterator;
}

QList<DatasetSequence> ContractRegistry::compatibleSequences(const QString& simulationId,
                                                              const QString& variantId) const {
  const auto& definition = simulation(simulationId);
  const auto& selectedVariant = variant(simulationId, variantId);
  QSet<QString> required = selectedVariant.requiredCapabilities;
  for (const auto& selectorValue : definition.selectors) {
    const auto selector = selectorValue.toObject();
    if (selector.value(QStringLiteral("kind")).toString() == QStringLiteral("dataset_sequence")) {
      required.unite(stringSet(selector.value(QStringLiteral("required_capabilities"))));
    }
  }
  if (required.isEmpty()) {
    return {};
  }
  QList<DatasetSequence> compatible;
  for (const auto& sequence : sequences_) {
    if (required.subtract(sequence.capabilities).isEmpty()) {
      compatible.append(sequence);
    }
    required = selectedVariant.requiredCapabilities;
    for (const auto& selectorValue : definition.selectors) {
      const auto selector = selectorValue.toObject();
      if (selector.value(QStringLiteral("kind")).toString() == QStringLiteral("dataset_sequence")) {
        required.unite(stringSet(selector.value(QStringLiteral("required_capabilities"))));
      }
    }
  }
  return compatible;
}

QJsonObject ContractRegistry::resolveRequest(const QString& simulationId,
                                             const QString& variantId,
                                             const QString& profileId,
                                             const QString& datasetId,
                                             const QString& sequenceId,
                                             const QJsonObject& parameters) const {
  const auto& definition = simulation(simulationId);
  const auto& selectedVariant = variant(simulationId, variantId);

  if (!definition.selectors.isEmpty()) {
    const auto compatible = compatibleSequences(simulationId, variantId);
    const auto sequence = std::find_if(compatible.cbegin(), compatible.cend(),
                                       [&](const auto& item) { return item.datasetId == datasetId && item.sequenceId == sequenceId; });
    if (sequence == compatible.cend()) {
      throw ContractError(QStringLiteral("Dataset ou séquence incompatible avec %1").arg(variantId));
    }
    for (const auto& resourceValue : sequence->resources) {
      const auto resource = resourceValue.toObject();
      if (!resource.value(QStringLiteral("required")).toBool()) {
        continue;
      }
      const auto uri = resource.value(QStringLiteral("uri")).toString();
      const auto path = safeWorkspacePath(workspace_, uri, QStringLiteral("Ressource dataset"));
      if (!QFileInfo::exists(path)) {
        throw ContractError(QStringLiteral("Ressource dataset absente : %1").arg(uri));
      }
    }
  }

  QSet<QString> accepted;
  for (const auto& item : definition.parameters) {
    accepted.insert(item.id);
  }
  for (const auto& item : selectedVariant.parameters) {
    accepted.insert(item.id);
  }
  for (auto iterator = parameters.constBegin(); iterator != parameters.constEnd(); ++iterator) {
    if (!accepted.contains(iterator.key())) {
      throw ContractError(QStringLiteral("Paramètre inconnu : %1").arg(iterator.key()));
    }
  }

  QJsonObject resolvedParameters;
  for (const auto& parameterId : accepted) {
    const auto* parameter = findParameter(definition, selectedVariant, parameterId);
    resolvedParameters.insert(parameterId, boundedValue(*parameter, parameters.value(parameterId)));
  }

  QJsonArray inputs;
  if (!definition.selectors.isEmpty()) {
    inputs.append(QJsonObject{
        {QStringLiteral("input_id"), QStringLiteral("dataset")},
        {QStringLiteral("kind"), QStringLiteral("dataset_sequence")},
        {QStringLiteral("reference"), QJsonObject{{QStringLiteral("dataset_id"), datasetId},
                                                   {QStringLiteral("sequence_id"), sequenceId}}},
    });
  }

  return QJsonObject{
      {QStringLiteral("schema"), QStringLiteral("drone_agricole.run_request.v1")},
      {QStringLiteral("request_id"), QStringLiteral("request_%1").arg(QUuid::createUuid().toString(QUuid::Id128).left(8))},
      {QStringLiteral("simulation_id"), simulationId},
      {QStringLiteral("variant_id"), variantId},
      {QStringLiteral("requested_at_utc"), QDateTime::currentDateTimeUtc().toString(Qt::ISODateWithMs)},
      {QStringLiteral("profile_id"), profileId.isEmpty() ? QJsonValue{} : QJsonValue(profileId)},
      {QStringLiteral("inputs"), inputs},
      {QStringLiteral("parameters"), resolvedParameters},
      {QStringLiteral("tags"), QJsonArray{}},
  };
}

qsizetype ContractRegistry::schemaDocumentCount() const noexcept { return schemaDocumentCount_; }

ParameterDefinition ContractRegistry::parameterFromJson(const QJsonObject& object) {
  requireFields(object, {QStringLiteral("id"), QStringLiteral("label"), QStringLiteral("type"),
                         QStringLiteral("default")}, QStringLiteral("parameter"));
  return ParameterDefinition{
      object.value(QStringLiteral("id")).toString(),
      object.value(QStringLiteral("runner_key")).toString(object.value(QStringLiteral("id")).toString()),
      object.value(QStringLiteral("label")).toString(),
      object.value(QStringLiteral("description")).toString(),
      object.value(QStringLiteral("type")).toString(),
      object.value(QStringLiteral("unit")).toString(),
      object.value(QStringLiteral("group")).toString(),
      object.value(QStringLiteral("safety_class")).toString(),
      object.value(QStringLiteral("default")),
      object.value(QStringLiteral("minimum")),
      object.value(QStringLiteral("maximum")),
      object.value(QStringLiteral("step")),
  };
}

VariantDefinition ContractRegistry::variantFromJson(const QJsonObject& object) {
  requireFields(object, {QStringLiteral("variant_id"), QStringLiteral("label"), QStringLiteral("runner_id"),
                         QStringLiteral("available")}, QStringLiteral("variant"));
  VariantDefinition result;
  result.id = object.value(QStringLiteral("variant_id")).toString();
  result.label = object.value(QStringLiteral("label")).toString();
  result.description = object.value(QStringLiteral("description")).toString();
  result.runnerId = object.value(QStringLiteral("runner_id")).toString();
  result.available = object.value(QStringLiteral("available")).toBool();
  result.requiredCapabilities = stringSet(object.value(QStringLiteral("required_capabilities")));
  for (const auto& value : object.value(QStringLiteral("parameters")).toArray()) {
    result.parameters.append(parameterFromJson(value.toObject()));
  }
  result.raw = object;
  return result;
}

SimulationDefinition ContractRegistry::simulationFromJson(const QJsonObject& object) {
  requireSchema(object, QStringLiteral("drone_agricole.simulation_definition.v1"), QStringLiteral("simulation"));
  requireFields(object, {QStringLiteral("simulation_id"), QStringLiteral("version"), QStringLiteral("label"),
                         QStringLiteral("domain"), QStringLiteral("runner_id"), QStringLiteral("safety_class"),
                         QStringLiteral("variants"), QStringLiteral("parameters"), QStringLiteral("comparison_group")},
                QStringLiteral("simulation"));
  SimulationDefinition result;
  result.id = object.value(QStringLiteral("simulation_id")).toString();
  result.version = object.value(QStringLiteral("version")).toString();
  result.label = object.value(QStringLiteral("label")).toString();
  result.description = object.value(QStringLiteral("description")).toString();
  result.domain = object.value(QStringLiteral("domain")).toString();
  result.runnerId = object.value(QStringLiteral("runner_id")).toString();
  result.safetyClass = object.value(QStringLiteral("safety_class")).toString();
  result.comparisonGroup = object.value(QStringLiteral("comparison_group")).toString();
  result.selectors = object.value(QStringLiteral("selectors")).toArray();
  result.profiles = object.value(QStringLiteral("profiles")).toArray();
  for (const auto& value : object.value(QStringLiteral("variants")).toArray()) {
    result.variants.append(variantFromJson(value.toObject()));
  }
  for (const auto& value : object.value(QStringLiteral("parameters")).toArray()) {
    result.parameters.append(parameterFromJson(value.toObject()));
  }
  result.raw = object;
  return result;
}

void ContractRegistry::loadSchemas() {
  const auto directory = safeWorkspacePath(workspace_, QStringLiteral("configs/visualization/schemas"),
                                           QStringLiteral("Répertoire des schémas"));
  for (const auto& fileName : jsonFiles(directory)) {
    const auto document = readJsonObject(QDir(directory).filePath(fileName));
    if (document.value(QStringLiteral("$schema")).toString() != QStringLiteral("https://json-schema.org/draft/2020-12/schema")) {
      throw ContractError(QStringLiteral("Le schéma %1 n'utilise pas JSON Schema 2020-12").arg(fileName));
    }
    ++schemaDocumentCount_;
  }
  if (schemaDocumentCount_ < 8) {
    throw ContractError(QStringLiteral("Les huit schémas T0 sont requis"));
  }
}

void ContractRegistry::loadDatasets() {
  const auto directory = safeWorkspacePath(workspace_, QStringLiteral("configs/visualization/datasets"),
                                           QStringLiteral("Répertoire des datasets"));
  for (const auto& fileName : jsonFiles(directory)) {
    const auto object = readJsonObject(QDir(directory).filePath(fileName));
    requireSchema(object, QStringLiteral("drone_agricole.dataset_definition.v1"), QStringLiteral("dataset"));
    requireFields(object, {QStringLiteral("dataset_id"), QStringLiteral("label"), QStringLiteral("capabilities"),
                           QStringLiteral("sequences")}, QStringLiteral("dataset"));
    const auto datasetId = object.value(QStringLiteral("dataset_id")).toString();
    const auto datasetLabel = object.value(QStringLiteral("label")).toString();
    const auto commonCapabilities = stringSet(object.value(QStringLiteral("capabilities")));
    for (const auto& value : object.value(QStringLiteral("sequences")).toArray()) {
      const auto sequence = value.toObject();
      requireFields(sequence, {QStringLiteral("sequence_id"), QStringLiteral("label"), QStringLiteral("status"),
                               QStringLiteral("capabilities"), QStringLiteral("resources")},
                    QStringLiteral("dataset.sequence"));
      auto capabilities = commonCapabilities;
      capabilities.unite(stringSet(sequence.value(QStringLiteral("capabilities"))));
      sequences_.append(DatasetSequence{
          datasetId,
          datasetLabel,
          sequence.value(QStringLiteral("sequence_id")).toString(),
          sequence.value(QStringLiteral("label")).toString(),
          sequence.value(QStringLiteral("status")).toString(),
          sequence.value(QStringLiteral("duration_s")).toDouble(),
          sequence.value(QStringLiteral("recommended")).toBool(),
          capabilities,
          sequence.value(QStringLiteral("resources")).toArray(),
      });
    }
  }
}

void ContractRegistry::loadSimulations() {
  const auto directory = safeWorkspacePath(workspace_, QStringLiteral("configs/visualization/simulations"),
                                           QStringLiteral("Répertoire des simulations"));
  for (const auto& fileName : jsonFiles(directory)) {
    auto definition = simulationFromJson(readJsonObject(QDir(directory).filePath(fileName)));
    if (simulations_.contains(definition.id)) {
      throw ContractError(QStringLiteral("Simulation dupliquée : %1").arg(definition.id));
    }
    simulations_.insert(definition.id, std::move(definition));
  }
}

}  // namespace drone_agricole::core
