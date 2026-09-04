#include "drone_agricole/core/ResultAdapter.hpp"

#include "drone_agricole/core/JsonUtils.hpp"

#include <QDir>
#include <QFileInfo>
#include <QJsonArray>
#include <QRegularExpression>
#include <QSaveFile>

#include <algorithm>

namespace drone_agricole::core {
namespace {

QString canonicalAlgorithm(const QJsonValue& value) {
  const auto identifier = safeIdentifier(value, QStringLiteral("unknown_lio"));
  static const QHash<QString, QString> aliases{
      {QStringLiteral("fast-lio2"), QStringLiteral("fast_lio2")},
      {QStringLiteral("fastlio2"), QStringLiteral("fast_lio2")},
      {QStringLiteral("point-lio"), QStringLiteral("point_lio")},
      {QStringLiteral("pointlio"), QStringLiteral("point_lio")},
      {QStringLiteral("lio-sam"), QStringLiteral("lio_sam")},
      {QStringLiteral("liosam"), QStringLiteral("lio_sam")},
  };
  return aliases.value(identifier, identifier);
}

QString utcFromMtime(const QString& path) {
  return QFileInfo(path).lastModified().toUTC().toString(Qt::ISODateWithMs);
}

QJsonObject metric(const QString& id,
                   const QString& label,
                   const QJsonValue& value,
                   const QString& unit,
                   const QString& direction = QStringLiteral("neutral")) {
  if (value.isUndefined() || value.isNull() || value.isObject() || value.isArray()) {
    return {};
  }
  return QJsonObject{
      {QStringLiteral("metric_id"), id},
      {QStringLiteral("label"), label},
      {QStringLiteral("value"), value},
      {QStringLiteral("unit"), unit},
      {QStringLiteral("direction"), direction},
      {QStringLiteral("status"), QStringLiteral("unknown")},
  };
}

void appendMetric(QJsonArray& values, const QJsonObject& value) {
  if (!value.isEmpty()) {
    values.append(value);
  }
}

QJsonArray lifecycleEvents(const QString& runId,
                           const QString& startedAt,
                           const QString& finishedAt,
                           const QString& state) {
  QJsonArray events{
      QJsonObject{
          {QStringLiteral("schema"), QStringLiteral("drone_agricole.event.v1")},
          {QStringLiteral("run_id"), runId},
          {QStringLiteral("sequence"), 0},
          {QStringLiteral("timestamp_utc"), startedAt},
          {QStringLiteral("event_type"), QStringLiteral("legacy_run_started")},
          {QStringLiteral("severity"), QStringLiteral("info")},
          {QStringLiteral("state"), QStringLiteral("running")},
          {QStringLiteral("message"), QStringLiteral("Début reconstruit depuis le résultat historique.")},
          {QStringLiteral("data"), QJsonObject{{QStringLiteral("synthetic"), true}}},
      },
  };
  if (!finishedAt.isEmpty()) {
    events.append(QJsonObject{
        {QStringLiteral("schema"), QStringLiteral("drone_agricole.event.v1")},
        {QStringLiteral("run_id"), runId},
        {QStringLiteral("sequence"), 1},
        {QStringLiteral("timestamp_utc"), finishedAt},
        {QStringLiteral("event_type"), QStringLiteral("legacy_run_finished")},
        {QStringLiteral("severity"), state == QStringLiteral("completed") ? QStringLiteral("info") : QStringLiteral("error")},
        {QStringLiteral("state"), state},
        {QStringLiteral("message"), QStringLiteral("Fin reconstruite depuis le résultat historique.")},
        {QStringLiteral("data"), QJsonObject{{QStringLiteral("synthetic"), true}}},
    });
  }
  return events;
}

QJsonObject lioArtifacts(const QString& directory, const QString& runId) {
  struct Definition {
    QString id;
    QString kind;
    QString label;
    QString path;
    QString mediaType;
    QString role;
    bool replayable;
  };
  const QList<Definition> definitions{
      {QStringLiteral("legacy_manifest"), QStringLiteral("manifest"), QStringLiteral("Manifeste historique"),
       QStringLiteral("run_manifest.json"), QStringLiteral("application/json"), QStringLiteral("source"), false},
      {QStringLiteral("legacy_metrics"), QStringLiteral("metrics"), QStringLiteral("Métriques historiques"),
       QStringLiteral("metrics.json"), QStringLiteral("application/json"), QStringLiteral("source"), true},
      {QStringLiteral("dashboard_request"), QStringLiteral("configuration"), QStringLiteral("Requête du tableau de bord"),
       QStringLiteral("dashboard_request.json"), QStringLiteral("application/json"), QStringLiteral("source"), false},
      {QStringLiteral("resource_profile"), QStringLiteral("other"), QStringLiteral("Profil de ressources"),
       QStringLiteral("resource_profile.json"), QStringLiteral("application/json"), QStringLiteral("diagnostic"), true},
      {QStringLiteral("effective_config"), QStringLiteral("configuration"), QStringLiteral("Configuration effective"),
       QStringLiteral("effective_config.yaml"), QStringLiteral("application/yaml"), QStringLiteral("source"), false},
      {QStringLiteral("estimate_bag"), QStringLiteral("rosbag"), QStringLiteral("Trajectoire estimée"),
       QStringLiteral("estimate"), QStringLiteral("application/x-rosbag2"), QStringLiteral("output"), true},
  };
  QJsonArray items;
  for (const auto& definition : definitions) {
    if (!QFileInfo::exists(QDir(directory).filePath(definition.path))) {
      continue;
    }
    items.append(QJsonObject{
        {QStringLiteral("artifact_id"), definition.id},
        {QStringLiteral("kind"), definition.kind},
        {QStringLiteral("label"), definition.label},
        {QStringLiteral("path"), definition.path},
        {QStringLiteral("media_type"), definition.mediaType},
        {QStringLiteral("role"), definition.role},
        {QStringLiteral("replayable"), definition.replayable},
    });
  }
  return QJsonObject{
      {QStringLiteral("schema"), QStringLiteral("drone_agricole.artifacts.v1")},
      {QStringLiteral("run_id"), runId},
      {QStringLiteral("items"), items},
  };
}

NormalizedResult normalizeLio(const QString& directory) {
  const auto legacyManifest = readJsonObject(QDir(directory).filePath(QStringLiteral("run_manifest.json")));
  const auto legacyMetrics = readJsonObject(QDir(directory).filePath(QStringLiteral("metrics.json")), false);
  const auto request = readJsonObject(QDir(directory).filePath(QStringLiteral("dashboard_request.json")), false);
  const auto resourceProfile = readJsonObject(QDir(directory).filePath(QStringLiteral("resource_profile.json")), false);

  QJsonValue algorithmSource = request.value(QStringLiteral("algorithm_id"));
  if (algorithmSource.isUndefined() || algorithmSource.toString().isEmpty()) {
    algorithmSource = legacyManifest.value(QStringLiteral("algorithm"));
  }
  if (algorithmSource.isUndefined() || algorithmSource.toString().isEmpty()) {
    const auto parts = normalizedPath(directory).split(QLatin1Char('/'), Qt::SkipEmptyParts);
    for (auto iterator = parts.crbegin(); iterator != parts.crend(); ++iterator) {
      const auto candidate = canonicalAlgorithm(*iterator);
      if (candidate == QStringLiteral("fast_lio2") || candidate == QStringLiteral("point_lio") ||
          candidate == QStringLiteral("lio_sam")) {
        algorithmSource = candidate;
        break;
      }
    }
  }
  const auto algorithm = canonicalAlgorithm(algorithmSource);
  const auto folderName = QFileInfo(directory).fileName();
  const auto requestedRunId = request.value(QStringLiteral("run_id"));
  const auto runId = safeIdentifier(requestedRunId.isUndefined() ? QJsonValue(folderName) : requestedRunId,
                                    QStringLiteral("lio_result"));
  auto startedAt = request.value(QStringLiteral("started_at")).toString();
  if (startedAt.isEmpty()) {
    startedAt = request.value(QStringLiteral("started_at_utc")).toString();
  }
  if (startedAt.isEmpty()) {
    startedAt = utcFromMtime(directory);
  }
  auto finishedAt = request.value(QStringLiteral("finished_at")).toString();
  if (finishedAt.isEmpty()) {
    finishedAt = request.value(QStringLiteral("finished_at_utc")).toString();
  }

  auto recordedState = request.value(QStringLiteral("state")).toString();
  if (recordedState.isEmpty()) {
    recordedState = legacyManifest.value(QStringLiteral("state")).toString();
  }
  if (recordedState.isEmpty()) {
    recordedState = legacyMetrics.isEmpty() ? QStringLiteral("abandoned") : QStringLiteral("completed");
  }
  static const QHash<QString, QString> states{
      {QStringLiteral("completed"), QStringLiteral("completed")},
      {QStringLiteral("failed"), QStringLiteral("failed")},
      {QStringLiteral("stopped"), QStringLiteral("cancelled")},
      {QStringLiteral("cancelled"), QStringLiteral("cancelled")},
      {QStringLiteral("running"), QStringLiteral("abandoned")},
      {QStringLiteral("abandoned"), QStringLiteral("abandoned")},
  };
  const auto state = states.value(recordedState, QStringLiteral("failed"));

  const auto inputBag = normalizedPath(legacyManifest.value(QStringLiteral("input_bag")).toString()).toLower();
  const auto pathLower = normalizedPath(directory).toLower();
  const auto inferredDataset = inputBag.contains(QStringLiteral("botanicgarden")) ||
                                       pathLower.contains(QStringLiteral("botanicgarden"))
                                   ? QStringLiteral("botanicgarden")
                                   : QString{};
  QString inferredSequence;
  if (inputBag.contains(QStringLiteral("/1006-03/smoke/"))) {
    inferredSequence = QStringLiteral("1006-03-smoke");
  } else if (inputBag.contains(QStringLiteral("/1006-03/dynamic/"))) {
    inferredSequence = QStringLiteral("1006-03-dynamic");
  } else if (inputBag.contains(QStringLiteral("/1006-03/full/"))) {
    inferredSequence = QStringLiteral("1006-03-full");
  }
  const auto datasetId = safeIdentifier(request.contains(QStringLiteral("dataset_id"))
                                            ? request.value(QStringLiteral("dataset_id"))
                                            : QJsonValue(inferredDataset),
                                        QStringLiteral("unknown_dataset"));
  const auto sequenceId = safeIdentifier(request.contains(QStringLiteral("sequence_id"))
                                             ? request.value(QStringLiteral("sequence_id"))
                                             : QJsonValue(inferredSequence),
                                         QStringLiteral("unknown_sequence"));

  QJsonObject files{
      {QStringLiteral("source_manifest"), QStringLiteral("run_manifest.json")},
      {QStringLiteral("metrics"), QStringLiteral("metrics.json")},
  };
  if (QFileInfo::exists(QDir(directory).filePath(QStringLiteral("dashboard_request.json")))) {
    files.insert(QStringLiteral("request"), QStringLiteral("dashboard_request.json"));
  }
  if (!resourceProfile.isEmpty()) {
    files.insert(QStringLiteral("resource_profile"), QStringLiteral("resource_profile.json"));
  }
  if (QFileInfo::exists(QDir(directory).filePath(QStringLiteral("effective_config.yaml")))) {
    files.insert(QStringLiteral("configuration"), QStringLiteral("effective_config.yaml"));
  }
  if (QFileInfo::exists(QDir(directory).filePath(QStringLiteral("estimate")))) {
    files.insert(QStringLiteral("estimate"), QStringLiteral("estimate"));
  }

  QJsonArray sourceFiles;
  for (const auto& name : {QStringLiteral("run_manifest.json"), QStringLiteral("metrics.json"),
                           QStringLiteral("dashboard_request.json"), QStringLiteral("resource_profile.json")}) {
    if (QFileInfo::exists(QDir(directory).filePath(name))) {
      sourceFiles.append(name);
    }
  }

  const auto manifest = QJsonObject{
      {QStringLiteral("schema"), QStringLiteral("drone_agricole.run_manifest.v1")},
      {QStringLiteral("run_id"), runId},
      {QStringLiteral("request_id"), request.value(QStringLiteral("run_id"))},
      {QStringLiteral("simulation_id"), QStringLiteral("lio_benchmark")},
      {QStringLiteral("variant_id"), algorithm},
      {QStringLiteral("runner_id"), algorithm},
      {QStringLiteral("domain"), QStringLiteral("localization")},
      {QStringLiteral("state"), state},
      {QStringLiteral("created_at_utc"), startedAt},
      {QStringLiteral("started_at_utc"), startedAt},
      {QStringLiteral("finished_at_utc"), finishedAt.isEmpty() ? QJsonValue::Null : QJsonValue(finishedAt)},
      {QStringLiteral("inputs"), QJsonArray{QJsonObject{
           {QStringLiteral("input_id"), QStringLiteral("dataset")},
           {QStringLiteral("kind"), QStringLiteral("dataset_sequence")},
           {QStringLiteral("reference"), QJsonObject{{QStringLiteral("dataset_id"), datasetId},
                                                      {QStringLiteral("sequence_id"), sequenceId}}},
       }}},
      {QStringLiteral("parameters"), request.value(QStringLiteral("parameters")).toObject()},
      {QStringLiteral("software"), QJsonObject{
           {QStringLiteral("legacy_algorithm"), legacyManifest.value(QStringLiteral("algorithm"))},
           {QStringLiteral("mapping_process"), legacyManifest.value(QStringLiteral("mapping_process")).toObject()},
       }},
      {QStringLiteral("files"), files},
      {QStringLiteral("compatibility"), QJsonObject{
           {QStringLiteral("comparison_group"), QStringLiteral("lio_trajectory_v1")},
           {QStringLiteral("result_contract_version"), 1},
       }},
      {QStringLiteral("legacy"), QJsonObject{
           {QStringLiteral("adapter"), QStringLiteral("lio_legacy_v3_cpp")},
           {QStringLiteral("source_schema"), legacyManifest.value(QStringLiteral("schema_version"))},
           {QStringLiteral("source_files"), sourceFiles},
       }},
      {QStringLiteral("metadata"), QJsonObject{{QStringLiteral("source_directory_name"), folderName}}},
  };

  QJsonArray summary;
  appendMetric(summary, metric(QStringLiteral("ate_translation_rmse_m"), QStringLiteral("ATE translation RMSE"),
                               nestedValue(legacyMetrics, {QStringLiteral("ate_translation_m"), QStringLiteral("rmse")}),
                               QStringLiteral("m"), QStringLiteral("lower")));
  appendMetric(summary, metric(QStringLiteral("ate_orientation_rmse_deg"), QStringLiteral("ATE orientation RMSE"),
                               nestedValue(legacyMetrics, {QStringLiteral("ate_orientation_deg"), QStringLiteral("rmse")}),
                               QStringLiteral("deg"), QStringLiteral("lower")));
  appendMetric(summary, metric(QStringLiteral("rpe_translation_rmse_m"), QStringLiteral("RPE translation RMSE"),
                               nestedValue(legacyMetrics, {QStringLiteral("rpe"), QStringLiteral("translation_m"), QStringLiteral("rmse")}),
                               QStringLiteral("m"), QStringLiteral("lower")));
  appendMetric(summary, metric(QStringLiteral("rpe_rotation_rmse_deg"), QStringLiteral("RPE rotation RMSE"),
                               nestedValue(legacyMetrics, {QStringLiteral("rpe"), QStringLiteral("rotation_deg"), QStringLiteral("rmse")}),
                               QStringLiteral("deg"), QStringLiteral("lower")));

  auto cpuValue = nestedValue(legacyManifest, {QStringLiteral("mapping_process"), QStringLiteral("cpu_average_equivalent_cores")});
  if (cpuValue.isUndefined() || cpuValue.isNull() || (cpuValue.isDouble() && cpuValue.toDouble() == 0.0)) {
    cpuValue = resourceProfile.value(QStringLiteral("cpu_average_equivalent_cores"));
  }
  appendMetric(summary, metric(QStringLiteral("cpu_average_cores"), QStringLiteral("CPU moyen"), cpuValue,
                               QStringLiteral("coeur"), QStringLiteral("lower")));
  auto memoryValue = nestedValue(legacyManifest, {QStringLiteral("mapping_process"), QStringLiteral("peak_rss_mib")});
  if (memoryValue.isUndefined() || memoryValue.isNull() || (memoryValue.isDouble() && memoryValue.toDouble() == 0.0)) {
    memoryValue = resourceProfile.value(QStringLiteral("peak_rss_mib"));
  }
  appendMetric(summary, metric(QStringLiteral("peak_rss_mib"), QStringLiteral("Mémoire RSS maximale"), memoryValue,
                               QStringLiteral("MiB"), QStringLiteral("lower")));
  appendMetric(summary, metric(QStringLiteral("scheduled_realtime_factor"), QStringLiteral("Facteur temps réel planifié"),
                               legacyManifest.value(QStringLiteral("scheduled_data_seconds_per_wall_second")),
                               QStringLiteral("x"), QStringLiteral("higher")));
  appendMetric(summary, metric(QStringLiteral("scans_received"), QStringLiteral("Scans reçus"),
                               nestedValue(legacyMetrics, {QStringLiteral("pipeline_counters"), QStringLiteral("scans_received")}),
                               QStringLiteral("scan"), QStringLiteral("higher")));
  auto odometry = nestedValue(legacyMetrics, {QStringLiteral("pipeline_counters"), QStringLiteral("odometry_published")});
  if (odometry.isUndefined() || odometry.isNull() || (odometry.isDouble() && odometry.toDouble() == 0.0)) {
    odometry = legacyMetrics.value(QStringLiteral("estimate_poses"));
  }
  appendMetric(summary, metric(QStringLiteral("odometry_published"), QStringLiteral("Odométries publiées"), odometry,
                               QStringLiteral("pose"), QStringLiteral("higher")));
  appendMetric(summary, metric(QStringLiteral("odometry_over_received_percent"), QStringLiteral("Sorties sur scans reçus"),
                               nestedValue(legacyMetrics, {QStringLiteral("pipeline_accounting"), QStringLiteral("ratios_percent"),
                                                           QStringLiteral("odometry_over_received")}),
                               QStringLiteral("%"), QStringLiteral("higher")));

  const auto metricsStatus = summary.isEmpty() ? QStringLiteral("unavailable")
                                                : legacyMetrics.value(QStringLiteral("finite_values")).toBool()
                                                      ? QStringLiteral("complete")
                                                      : QStringLiteral("partial");
  const auto metrics = QJsonObject{
      {QStringLiteral("schema"), QStringLiteral("drone_agricole.metrics.v1")},
      {QStringLiteral("run_id"), runId},
      {QStringLiteral("simulation_id"), QStringLiteral("lio_benchmark")},
      {QStringLiteral("status"), metricsStatus},
      {QStringLiteral("summary"), summary},
      {QStringLiteral("groups"), QJsonObject{
           {QStringLiteral("trajectory"), legacyMetrics},
           {QStringLiteral("resources"), resourceProfile.isEmpty()
                                                  ? legacyManifest.value(QStringLiteral("mapping_process")).toObject()
                                                  : resourceProfile},
       }},
      {QStringLiteral("source"), QJsonObject{{QStringLiteral("adapter"), QStringLiteral("lio_legacy_v3_cpp")},
                                              {QStringLiteral("path"), QStringLiteral("metrics.json")}}},
  };

  return NormalizedResult{QStringLiteral("lio_benchmark_legacy"), directory, manifest, metrics,
                          lioArtifacts(directory, runId), lifecycleEvents(runId, startedAt, finishedAt, state)};
}

NormalizedResult normalizePx4(const QString& directory) {
  const auto source = readJsonObject(QDir(directory).filePath(QStringLiteral("result.json")));
  const auto runId = safeIdentifier(QFileInfo(directory).fileName(), QStringLiteral("px4_result"));
  const auto mode = safeIdentifier(source.value(QStringLiteral("mode")), QStringLiteral("unknown_mode"));
  auto createdAt = source.value(QStringLiteral("created_utc")).toString();
  if (createdAt.isEmpty()) {
    createdAt = utcFromMtime(directory);
  }
  const auto success = source.value(QStringLiteral("success")).toBool();
  const auto observations = source.value(QStringLiteral("observations")).toObject();
  const auto sourceEvents = source.value(QStringLiteral("events")).toArray();
  double duration = 0.0;
  for (const auto& eventValue : sourceEvents) {
    duration = std::max(duration, eventValue.toObject().value(QStringLiteral("elapsed_s")).toDouble());
  }

  const auto manifest = QJsonObject{
      {QStringLiteral("schema"), QStringLiteral("drone_agricole.run_manifest.v1")},
      {QStringLiteral("run_id"), runId},
      {QStringLiteral("request_id"), QJsonValue::Null},
      {QStringLiteral("simulation_id"), QStringLiteral("px4_offboard")},
      {QStringLiteral("variant_id"), mode},
      {QStringLiteral("runner_id"), QStringLiteral("px4_offboard_test")},
      {QStringLiteral("domain"), QStringLiteral("flight_simulation")},
      {QStringLiteral("state"), success ? QStringLiteral("completed") : QStringLiteral("failed")},
      {QStringLiteral("created_at_utc"), createdAt},
      {QStringLiteral("started_at_utc"), createdAt},
      {QStringLiteral("finished_at_utc"), QJsonValue::Null},
      {QStringLiteral("inputs"), QJsonArray{QJsonObject{
           {QStringLiteral("input_id"), QStringLiteral("scenario")},
           {QStringLiteral("kind"), QStringLiteral("scenario")},
           {QStringLiteral("reference"), QJsonObject{{QStringLiteral("scenario_id"), QStringLiteral("px4_default_world")},
                                                      {QStringLiteral("mode"), mode}}},
       }}},
      {QStringLiteral("parameters"), source.value(QStringLiteral("parameters")).toObject()},
      {QStringLiteral("software"), QJsonObject{{QStringLiteral("legacy_schema"), source.value(QStringLiteral("schema"))}}},
      {QStringLiteral("files"), QJsonObject{{QStringLiteral("source_result"), QStringLiteral("result.json")}}},
      {QStringLiteral("compatibility"), QJsonObject{
           {QStringLiteral("comparison_group"), QStringLiteral("px4_offboard_v1")},
           {QStringLiteral("result_contract_version"), 1},
       }},
      {QStringLiteral("legacy"), QJsonObject{{QStringLiteral("adapter"), QStringLiteral("px4_offboard_v1_cpp")},
                                              {QStringLiteral("source_schema"), source.value(QStringLiteral("schema"))},
                                              {QStringLiteral("source_files"), QJsonArray{QStringLiteral("result.json")}}}},
      {QStringLiteral("metadata"), QJsonObject{{QStringLiteral("reason"), source.value(QStringLiteral("reason"))},
                                                {QStringLiteral("source_directory_name"), QFileInfo(directory).fileName()}}},
  };

  QJsonArray summary;
  appendMetric(summary, metric(QStringLiteral("success"), QStringLiteral("Test réussi"), success, QString{}, QStringLiteral("higher")));
  appendMetric(summary, metric(QStringLiteral("duration_s"), QStringLiteral("Durée observée"), duration,
                               QStringLiteral("s"), QStringLiteral("lower")));
  appendMetric(summary, metric(QStringLiteral("max_altitude_m"), QStringLiteral("Altitude maximale"),
                               observations.value(QStringLiteral("max_altitude_m")), QStringLiteral("m"), QStringLiteral("target")));
  appendMetric(summary, metric(QStringLiteral("offboard_entered"), QStringLiteral("Mode Offboard atteint"),
                               observations.value(QStringLiteral("offboard_entered")), QString{}, QStringLiteral("higher")));
  appendMetric(summary, metric(QStringLiteral("landed"), QStringLiteral("Atterrissage confirmé"),
                               observations.value(QStringLiteral("landed")), QString{}, QStringLiteral("higher")));
  appendMetric(summary, metric(QStringLiteral("failsafe"), QStringLiteral("Failsafe observé"),
                               observations.value(QStringLiteral("failsafe")), QString{}, QStringLiteral("lower")));
  appendMetric(summary, metric(QStringLiteral("offboard_loss"), QStringLiteral("Perte Offboard"),
                               observations.value(QStringLiteral("offboard_loss_flag")), QString{}, QStringLiteral("lower")));
  const auto metrics = QJsonObject{
      {QStringLiteral("schema"), QStringLiteral("drone_agricole.metrics.v1")},
      {QStringLiteral("run_id"), runId},
      {QStringLiteral("simulation_id"), QStringLiteral("px4_offboard")},
      {QStringLiteral("status"), QStringLiteral("complete")},
      {QStringLiteral("summary"), summary},
      {QStringLiteral("groups"), QJsonObject{{QStringLiteral("observations"), observations},
                                              {QStringLiteral("command_acks"), source.value(QStringLiteral("command_acks")).toArray()}}},
      {QStringLiteral("source"), QJsonObject{{QStringLiteral("adapter"), QStringLiteral("px4_offboard_v1_cpp")},
                                              {QStringLiteral("path"), QStringLiteral("result.json")}}},
  };
  const auto artifacts = QJsonObject{
      {QStringLiteral("schema"), QStringLiteral("drone_agricole.artifacts.v1")},
      {QStringLiteral("run_id"), runId},
      {QStringLiteral("items"), QJsonArray{QJsonObject{
           {QStringLiteral("artifact_id"), QStringLiteral("source_result")},
           {QStringLiteral("kind"), QStringLiteral("report")},
           {QStringLiteral("label"), QStringLiteral("Résultat PX4 historique")},
           {QStringLiteral("path"), QStringLiteral("result.json")},
           {QStringLiteral("media_type"), QStringLiteral("application/json")},
           {QStringLiteral("role"), QStringLiteral("source")},
           {QStringLiteral("replayable"), true},
       }}},
  };

  QJsonArray events;
  qsizetype sequence = 0;
  for (const auto& eventValue : sourceEvents) {
    const auto sourceEvent = eventValue.toObject();
    const auto eventType = safeIdentifier(sourceEvent.value(QStringLiteral("event")), QStringLiteral("legacy_event"));
    auto severity = QStringLiteral("info");
    if (eventType == QStringLiteral("test_finished") && !success) {
      severity = QStringLiteral("error");
    } else if (eventType.contains(QStringLiteral("failsafe")) || eventType.contains(QStringLiteral("timeout"))) {
      severity = QStringLiteral("warning");
    }
    auto data = sourceEvent;
    data.remove(QStringLiteral("event"));
    data.remove(QStringLiteral("elapsed_s"));
    data.remove(QStringLiteral("state"));
    events.append(QJsonObject{
        {QStringLiteral("schema"), QStringLiteral("drone_agricole.event.v1")},
        {QStringLiteral("run_id"), runId},
        {QStringLiteral("sequence"), static_cast<double>(sequence++)},
        {QStringLiteral("elapsed_s"), sourceEvent.value(QStringLiteral("elapsed_s")).toDouble()},
        {QStringLiteral("event_type"), eventType},
        {QStringLiteral("severity"), severity},
        {QStringLiteral("state"), sourceEvent.value(QStringLiteral("state"))},
        {QStringLiteral("message"), QString(eventType).replace(QLatin1Char('_'), QLatin1Char(' '))},
        {QStringLiteral("data"), data},
    });
  }
  return NormalizedResult{QStringLiteral("px4_offboard_v1"), directory, manifest, metrics, artifacts, events};
}

NormalizedResult loadNative(const QString& directory) {
  const auto manifest = readJsonObject(QDir(directory).filePath(QStringLiteral("t0_run_manifest.json")));
  const auto metrics = readJsonObject(QDir(directory).filePath(QStringLiteral("t0_metrics.json")));
  const auto artifacts = readJsonObject(QDir(directory).filePath(QStringLiteral("artifacts.json")));
  const auto events = readJsonLines(QDir(directory).filePath(QStringLiteral("events.jsonl")));
  requireSchema(manifest, QStringLiteral("drone_agricole.run_manifest.v1"), QStringLiteral("manifest"));
  requireSchema(metrics, QStringLiteral("drone_agricole.metrics.v1"), QStringLiteral("metrics"));
  requireSchema(artifacts, QStringLiteral("drone_agricole.artifacts.v1"), QStringLiteral("artifacts"));
  requireFields(manifest, {QStringLiteral("run_id"), QStringLiteral("simulation_id"), QStringLiteral("variant_id"),
                           QStringLiteral("runner_id"), QStringLiteral("domain"), QStringLiteral("state")},
                QStringLiteral("manifest"));
  return NormalizedResult{QStringLiteral("t0_native"), directory, manifest, metrics, artifacts, events};
}

}  // namespace

QString detectResultKind(const QString& directory) {
  const auto native = QDir(directory).filePath(QStringLiteral("t0_run_manifest.json"));
  if (QFileInfo::exists(native)) {
    return QStringLiteral("t0_native");
  }
  const auto px4 = readJsonObject(QDir(directory).filePath(QStringLiteral("result.json")), false);
  if (px4.value(QStringLiteral("schema")).toString() == QStringLiteral("drone_agricole.px4_offboard_test.v1")) {
    return QStringLiteral("px4_offboard_v1");
  }
  const auto manifest = readJsonObject(QDir(directory).filePath(QStringLiteral("run_manifest.json")), false);
  if (manifest.value(QStringLiteral("schema_version")).isDouble()) {
    return QStringLiteral("lio_benchmark_legacy");
  }
  throw ContractError(QStringLiteral("Format de résultat non reconnu : %1").arg(QFileInfo(directory).fileName()));
}

NormalizedResult normalizeResultDirectory(const QString& directory) {
  const auto absolute = QFileInfo(directory).absoluteFilePath();
  if (!QFileInfo(absolute).isDir()) {
    throw ContractError(QStringLiteral("Répertoire de résultat absent : %1").arg(directory));
  }
  const auto kind = detectResultKind(absolute);
  if (kind == QStringLiteral("t0_native")) {
    return loadNative(absolute);
  }
  if (kind == QStringLiteral("lio_benchmark_legacy")) {
    return normalizeLio(absolute);
  }
  return normalizePx4(absolute);
}

void writeNativeContracts(const NormalizedResult& result, const QJsonObject& request) {
  auto linkedManifest = result.manifest;
  linkedManifest.insert(QStringLiteral("request_id"), request.value(QStringLiteral("request_id")));
  linkedManifest.insert(QStringLiteral("parameters"), request.value(QStringLiteral("parameters")));
  writeJsonObjectAtomically(QDir(result.directory).filePath(QStringLiteral("run_request.json")), request);
  writeJsonObjectAtomically(QDir(result.directory).filePath(QStringLiteral("t0_run_manifest.json")), linkedManifest);
  writeJsonObjectAtomically(QDir(result.directory).filePath(QStringLiteral("t0_metrics.json")), result.metrics);
  writeJsonObjectAtomically(QDir(result.directory).filePath(QStringLiteral("artifacts.json")), result.artifacts);
  QSaveFile eventsFile(QDir(result.directory).filePath(QStringLiteral("events.jsonl")));
  if (!eventsFile.open(QIODevice::WriteOnly | QIODevice::Text)) {
    throw ContractError(QStringLiteral("Écriture des événements T0 impossible"));
  }
  for (const auto& value : result.events) {
    eventsFile.write(QJsonDocument(value.toObject()).toJson(QJsonDocument::Compact));
    eventsFile.write("\n");
  }
  if (!eventsFile.commit()) {
    throw ContractError(QStringLiteral("Validation des événements T0 impossible"));
  }
}

}  // namespace drone_agricole::core
