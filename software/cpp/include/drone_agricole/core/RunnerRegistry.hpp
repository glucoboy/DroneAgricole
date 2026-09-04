#pragma once

#include "drone_agricole/core/ContractRegistry.hpp"

namespace drone_agricole::core {

class RunnerRegistry {
 public:
  explicit RunnerRegistry(const ContractRegistry& contracts);

  [[nodiscard]] PreparedRun prepare(const QJsonObject& request,
                                    QString runId = {},
                                    QDateTime timestamp = QDateTime::currentDateTimeUtc()) const;
  [[nodiscard]] QStringList approvedRunnerIds() const;

 private:
  const ContractRegistry& contracts_;

  [[nodiscard]] PreparedRun prepareLio(const SimulationDefinition& simulation,
                                       const VariantDefinition& variant,
                                       const QJsonObject& request,
                                       const DatasetSequence& sequence,
                                       const QString& profileId,
                                       const QString& runId,
                                       const QString& stamp) const;
  [[nodiscard]] PreparedRun preparePx4(const SimulationDefinition& simulation,
                                       const VariantDefinition& variant,
                                       const QJsonObject& request,
                                       const QString& runId,
                                       const QString& stamp) const;
  static void writeLioConfig(const QString& runnerId,
                             const QString& basePath,
                             const QString& outputPath,
                             const QJsonObject& parameters);
};

}  // namespace drone_agricole::core
