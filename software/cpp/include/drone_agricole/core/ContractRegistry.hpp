#pragma once

#include "drone_agricole/core/Types.hpp"

#include <QHash>

namespace drone_agricole::core {

class ContractRegistry {
 public:
  explicit ContractRegistry(QString workspace);

  void load();

  [[nodiscard]] const QString& workspace() const noexcept;
  [[nodiscard]] QList<SimulationDefinition> simulations() const;
  [[nodiscard]] QList<DatasetSequence> datasetSequences() const;
  [[nodiscard]] const SimulationDefinition& simulation(const QString& simulationId) const;
  [[nodiscard]] const VariantDefinition& variant(const QString& simulationId, const QString& variantId) const;
  [[nodiscard]] QList<DatasetSequence> compatibleSequences(const QString& simulationId,
                                                           const QString& variantId) const;
  [[nodiscard]] QJsonObject resolveRequest(const QString& simulationId,
                                           const QString& variantId,
                                           const QString& profileId,
                                           const QString& datasetId,
                                           const QString& sequenceId,
                                           const QJsonObject& parameters) const;
  [[nodiscard]] qsizetype schemaDocumentCount() const noexcept;

 private:
  QString workspace_;
  QHash<QString, SimulationDefinition> simulations_;
  QList<DatasetSequence> sequences_;
  qsizetype schemaDocumentCount_{0};

  static ParameterDefinition parameterFromJson(const QJsonObject& object);
  static VariantDefinition variantFromJson(const QJsonObject& object);
  static SimulationDefinition simulationFromJson(const QJsonObject& object);
  void loadSchemas();
  void loadDatasets();
  void loadSimulations();
};

}  // namespace drone_agricole::core
