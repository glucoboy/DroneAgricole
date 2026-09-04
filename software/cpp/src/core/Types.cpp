#include "drone_agricole/core/Types.hpp"

namespace drone_agricole::core {

QJsonObject ResultSummary::toJson() const {
  return QJsonObject{
      {QStringLiteral("result_id"), resultId},
      {QStringLiteral("run_id"), runId},
      {QStringLiteral("relative_directory"), relativeDirectory},
      {QStringLiteral("source_kind"), sourceKind},
      {QStringLiteral("simulation_id"), simulationId},
      {QStringLiteral("variant_id"), variantId},
      {QStringLiteral("runner_id"), runnerId},
      {QStringLiteral("domain"), domain},
      {QStringLiteral("state"), state},
      {QStringLiteral("created_at_utc"), createdAtUtc.isValid() ? QJsonValue(createdAtUtc.toString(Qt::ISODateWithMs))
                                                                 : QJsonValue(QJsonValue::Null)},
      {QStringLiteral("finished_at_utc"), finishedAtUtc.isValid() ? QJsonValue(finishedAtUtc.toString(Qt::ISODateWithMs))
                                                                   : QJsonValue(QJsonValue::Null)},
      {QStringLiteral("dataset_id"), datasetId.isEmpty() ? QJsonValue::Null : QJsonValue(datasetId)},
      {QStringLiteral("sequence_id"), sequenceId.isEmpty() ? QJsonValue::Null : QJsonValue(sequenceId)},
      {QStringLiteral("algorithm_id"), domain == QStringLiteral("localization") ? QJsonValue(variantId) : QJsonValue::Null},
      {QStringLiteral("scenario_id"), scenarioId.isEmpty() ? QJsonValue::Null : QJsonValue(scenarioId)},
      {QStringLiteral("comparison_group"), comparisonGroup},
      {QStringLiteral("tags"), QJsonArray::fromStringList(tags)},
      {QStringLiteral("metric_preview"), metricPreview},
      {QStringLiteral("metrics_status"), metricsStatus},
      {QStringLiteral("event_count"), static_cast<double>(eventCount)},
      {QStringLiteral("artifact_count"), static_cast<double>(artifactCount)},
      {QStringLiteral("replay_available"), replayAvailable},
      {QStringLiteral("duplicate_available"), duplicateAvailable},
  };
}

}  // namespace drone_agricole::core
