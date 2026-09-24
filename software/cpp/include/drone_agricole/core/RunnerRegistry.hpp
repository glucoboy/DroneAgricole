#pragma once
#include "drone_agricole/core/ContractRegistry.hpp"
#include <functional>
#include <optional>
namespace drone_agricole::core {
struct RunnerContext {
  const SimulationDefinition& simulation;
  const VariantDefinition& variant;
  const QJsonObject& request;
  std::optional<DatasetSequence> sequence;
  QString profileId;
  QString runId;
  QString stamp;
};
class RunnerRegistry {
 public:
  using Factory = std::function<PreparedRun(const RunnerContext&)>;
  explicit RunnerRegistry(const ContractRegistry& contracts);
  void registerRunner(const QString& id, Factory factory);
  [[nodiscard]] PreparedRun prepare(const QJsonObject& request, QString runId = {},
      QDateTime timestamp = QDateTime::currentDateTimeUtc()) const;
  [[nodiscard]] QStringList approvedRunnerIds() const;
 private:
  const ContractRegistry& contracts_;
  QHash<QString, Factory> factories_;
  QStringList orderedIds_;
};
}
