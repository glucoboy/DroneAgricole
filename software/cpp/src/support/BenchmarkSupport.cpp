#include "drone_agricole/core/BenchmarkSupport.hpp"

#include "drone_agricole/core/JsonUtils.hpp"

#include <QCryptographicHash>
#include <QDir>
#include <QDirIterator>
#include <QFile>
#include <QFileInfo>
#include <QJsonArray>
#include <QJsonDocument>
#include <QSaveFile>
#include <QTextStream>

#include <yaml-cpp/yaml.h>

#include <algorithm>
#include <cmath>
#include <numeric>

namespace drone_agricole::core {
namespace {

QString requiredString(const QJsonObject& options, const QString& key) {
  const auto value = options.value(key).toString();
  if (value.isEmpty()) {
    throw ContractError(QStringLiteral("Option requise : %1").arg(key));
  }
  return value;
}

double requiredNumber(const QJsonObject& options, const QString& key) {
  const auto value = options.value(key);
  if (!value.isDouble() || !std::isfinite(value.toDouble())) {
    throw ContractError(QStringLiteral("Valeur numérique requise : %1").arg(key));
  }
  return value.toDouble();
}

qint64 requiredInteger(const QJsonObject& options, const QString& key) {
  return static_cast<qint64>(requiredNumber(options, key));
}

QByteArray fileSha256(const QString& path) {
  QFile file(path);
  if (!file.open(QIODevice::ReadOnly)) {
    throw ContractError(QStringLiteral("Fichier illisible : %1").arg(path));
  }
  QCryptographicHash digest(QCryptographicHash::Sha256);
  while (!file.atEnd()) {
    digest.addData(file.read(8 * 1024 * 1024));
  }
  return digest.result().toHex();
}

void writeJson(const QString& path, const QJsonObject& object) {
  writeJsonObjectAtomically(path, object);
}

QString csvCell(const QJsonValue& value) {
  QString text;
  if (value.isString()) {
    text = value.toString();
  } else if (value.isBool()) {
    text = value.toBool() ? QStringLiteral("true") : QStringLiteral("false");
  } else if (value.isDouble()) {
    text = QString::number(value.toDouble(), 'g', 15);
  } else if (!value.isNull() && !value.isUndefined()) {
    text = QString::fromUtf8(QJsonDocument(value.isArray() ? QJsonDocument(value.toArray())
                                                         : QJsonDocument(value.toObject()))
                                 .toJson(QJsonDocument::Compact));
  }
  if (text.contains(QLatin1Char(',')) || text.contains(QLatin1Char('"')) || text.contains(QLatin1Char('\n'))) {
    text.replace(QLatin1Char('"'), QStringLiteral("\"\""));
    text = QLatin1Char('"') + text + QLatin1Char('"');
  }
  return text;
}

void writeCsv(const QString& path, const QJsonArray& rows) {
  if (rows.isEmpty()) {
    return;
  }
  QDir().mkpath(QFileInfo(path).absolutePath());
  QSaveFile file(path);
  if (!file.open(QIODevice::WriteOnly | QIODevice::Text)) {
    throw ContractError(QStringLiteral("CSV impossible à écrire : %1").arg(path));
  }
  QTextStream stream(&file);
  const auto first = rows.first().toObject();
  const auto fields = first.keys();
  stream << fields.join(QLatin1Char(',')) << Qt::endl;
  for (const auto& value : rows) {
    const auto row = value.toObject();
    QStringList cells;
    cells.reserve(fields.size());
    for (const auto& field : fields) {
      cells.append(csvCell(row.value(field)));
    }
    stream << cells.join(QLatin1Char(',')) << Qt::endl;
  }
  if (!file.commit()) {
    throw ContractError(QStringLiteral("Validation du CSV impossible : %1").arg(path));
  }
}

double nestedDouble(const QJsonObject& object, const QStringList& path) {
  const auto value = nestedValue(object, path);
  if (!value.isDouble() || !std::isfinite(value.toDouble())) {
    throw ContractError(QStringLiteral("Mesure absente : %1").arg(path.join(QLatin1Char('.'))));
  }
  return value.toDouble();
}

QJsonObject compactRun(const QString& path) {
  const auto metrics = readJsonObject(QDir(path).filePath(QStringLiteral("metrics.json")));
  const auto manifest = readJsonObject(QDir(path).filePath(QStringLiteral("run_manifest.json")));
  const auto profile = manifest.value(QStringLiteral("mapping_process")).toObject();
  const auto counters = metrics.value(QStringLiteral("pipeline_counters")).toObject();
  QJsonObject result{
      {QStringLiteral("run"), QFileInfo(path).absoluteFilePath()},
      {QStringLiteral("algorithm"), manifest.value(QStringLiteral("algorithm")).toString(QStringLiteral("fast_lio2"))},
      {QStringLiteral("ate_translation_rmse_m"), nestedDouble(metrics, {QStringLiteral("ate_translation_m"), QStringLiteral("rmse")})},
      {QStringLiteral("ate_orientation_rmse_deg"), nestedDouble(metrics, {QStringLiteral("ate_orientation_deg"), QStringLiteral("rmse")})},
      {QStringLiteral("rpe_translation_rmse_m"), nestedDouble(metrics, {QStringLiteral("rpe"), QStringLiteral("translation_m"), QStringLiteral("rmse")})},
      {QStringLiteral("rpe_rotation_rmse_deg"), nestedDouble(metrics, {QStringLiteral("rpe"), QStringLiteral("rotation_deg"), QStringLiteral("rmse")})},
      {QStringLiteral("cpu_seconds"), profile.value(QStringLiteral("cpu_total_seconds"))},
      {QStringLiteral("average_cpu_cores"), profile.value(QStringLiteral("cpu_average_equivalent_cores"))},
      {QStringLiteral("peak_rss_mib"), profile.value(QStringLiteral("peak_rss_mib"))},
      {QStringLiteral("scans_received"), counters.value(QStringLiteral("scans_received"))},
      {QStringLiteral("odometry_published"), counters.value(QStringLiteral("odometry_published"))},
  };
  result.insert(QStringLiteral("odometry_over_received_percent"),
                nestedValue(metrics, {QStringLiteral("pipeline_accounting"), QStringLiteral("ratios_percent"),
                                      QStringLiteral("odometry_over_received")}));
  return result;
}

QList<QString> measurementNames() {
  return {
      QStringLiteral("output_scan_ratio_percent"),
      QStringLiteral("trajectory_coverage_percent"),
      QStringLiteral("ate_translation_rmse_m"),
      QStringLiteral("ate_orientation_rmse_deg"),
      QStringLiteral("rpe_translation_rmse_m"),
      QStringLiteral("rpe_rotation_rmse_deg"),
      QStringLiteral("cpu_total_seconds"),
      QStringLiteral("cpu_average_equivalent_cores"),
      QStringLiteral("peak_rss_mib"),
      QStringLiteral("scheduled_data_seconds_per_wall_second"),
  };
}

}  // namespace

BagMetadata readBagMetadata(const QString& bagDirectory) {
  const auto path = QDir(bagDirectory).filePath(QStringLiteral("metadata.yaml"));
  YAML::Node root;
  try {
    root = YAML::LoadFile(path.toStdString());
  } catch (const YAML::Exception& error) {
    throw ContractError(QStringLiteral("Métadonnées rosbag2 illisibles : %1").arg(QString::fromUtf8(error.what())));
  }
  const auto information = root["rosbag2_bagfile_information"];
  if (!information || !information["duration"] || !information["message_count"]) {
    throw ContractError(QStringLiteral("metadata.yaml incomplet"));
  }
  const auto durationNode = information["duration"];
  const auto nanoseconds = durationNode.IsMap() ? durationNode["nanoseconds"].as<long long>() : durationNode.as<long long>();
  QJsonObject topics;
  if (const auto entries = information["topics_with_message_count"]; entries && entries.IsSequence()) {
    for (const auto& entry : entries) {
      const auto name = QString::fromStdString(entry["topic_metadata"]["name"].as<std::string>());
      topics.insert(name, static_cast<double>(entry["message_count"].as<long long>()));
    }
  }
  return BagMetadata{static_cast<double>(nanoseconds) * 1e-9, information["message_count"].as<long long>(), topics};
}

qint64 bagTopicCount(const QString& bagDirectory, const QString& topic) {
  const auto metadata = readBagMetadata(bagDirectory);
  if (!metadata.topicMessageCounts.contains(topic)) {
    throw ContractError(QStringLiteral("Topic absent du rosbag : %1").arg(topic));
  }
  return static_cast<qint64>(metadata.topicMessageCounts.value(topic).toDouble());
}

int playbackProgressPercent(const double elapsedWallSeconds,
                            const double bagDurationSeconds,
                            const double playbackRate,
                            const double playbackDelaySeconds) {
  if (!std::isfinite(elapsedWallSeconds) || !std::isfinite(bagDurationSeconds) ||
      !std::isfinite(playbackRate) || !std::isfinite(playbackDelaySeconds) ||
      bagDurationSeconds <= 0.0 || playbackRate <= 0.0) {
    return 5;
  }
  const auto playedSeconds = std::max(0.0, elapsedWallSeconds - std::max(0.0, playbackDelaySeconds)) * playbackRate;
  const auto ratio = std::clamp(playedSeconds / bagDurationSeconds, 0.0, 1.0);
  return std::clamp(5 + static_cast<int>(std::lround(85.0 * ratio)), 5, 90);
}

QJsonObject pipelineAccounting(const QJsonObject& counters) {
  const auto integer = [&](const char* key) { return static_cast<qint64>(counters.value(QLatin1String(key)).toDouble()); };
  const auto received = integer("scans_received");
  const auto preprocessed = integer("scans_preprocessed");
  const auto synchronized = integer("scans_synchronized");
  const auto odometry = integer("odometry_published");
  const auto accounted = integer("scans_initialization") + integer("scans_rejected_undistort_empty") +
                         integer("scans_map_initialization") + integer("scans_rejected_downsample") +
                         integer("state_updates");
  QJsonObject ratios;
  ratios.insert(QStringLiteral("synchronized_over_received"),
                received ? QJsonValue(100.0 * synchronized / received) : QJsonValue(QJsonValue::Null));
  ratios.insert(QStringLiteral("odometry_over_received"),
                received ? QJsonValue(100.0 * odometry / received) : QJsonValue(QJsonValue::Null));
  ratios.insert(QStringLiteral("odometry_over_synchronized"),
                synchronized ? QJsonValue(100.0 * odometry / synchronized) : QJsonValue(QJsonValue::Null));
  return {
      {QStringLiteral("received_minus_preprocessed"), static_cast<double>(received - preprocessed)},
      {QStringLiteral("preprocessed_minus_synchronized"), static_cast<double>(preprocessed - synchronized)},
      {QStringLiteral("accounted_synchronized_scans"), static_cast<double>(accounted)},
      {QStringLiteral("unaccounted_synchronized_scans"), static_cast<double>(synchronized - accounted)},
      {QStringLiteral("state_updates_minus_odometry"), static_cast<double>(integer("state_updates") - odometry)},
      {QStringLiteral("ratios_percent"), ratios},
  };
}

QJsonObject numericStatistics(const QList<double>& values) {
  if (values.isEmpty()) {
    throw ContractError(QStringLiteral("Une statistique exige au moins une valeur"));
  }
  const auto total = std::accumulate(values.cbegin(), values.cend(), 0.0);
  const auto mean = total / static_cast<double>(values.size());
  double variance = 0.0;
  for (const auto value : values) {
    variance += (value - mean) * (value - mean);
  }
  const auto [minimum, maximum] = std::minmax_element(values.cbegin(), values.cend());
  return {
      {QStringLiteral("n"), values.size()},
      {QStringLiteral("mean"), mean},
      {QStringLiteral("sample_stdev"), values.size() > 1 ? std::sqrt(variance / (values.size() - 1)) : 0.0},
      {QStringLiteral("minimum"), *minimum},
      {QStringLiteral("maximum"), *maximum},
  };
}

QJsonObject loadCampaignRun(const QString& directory, const QString& campaignRoot) {
  const auto relative = QDir(campaignRoot).relativeFilePath(directory);
  const auto parts = QDir::fromNativeSeparators(relative).split(QLatin1Char('/'), Qt::SkipEmptyParts);
  if (parts.size() != 3) {
    throw ContractError(QStringLiteral("Chemin de campagne inattendu : %1").arg(relative));
  }
  const auto manifest = readJsonObject(QDir(directory).filePath(QStringLiteral("run_manifest.json")));
  const auto metrics = readJsonObject(QDir(directory).filePath(QStringLiteral("metrics.json")));
  const auto inputCounts = manifest.value(QStringLiteral("input_topic_message_counts")).toObject();
  const auto inputScans = static_cast<qint64>(inputCounts.value(QStringLiteral("/velodyne_points"))
                                                 .toDouble(metrics.value(QStringLiteral("ground_truth_poses")).toDouble()));
  const auto outputPoses = static_cast<qint64>(metrics.value(QStringLiteral("estimate_poses")).toDouble());
  const auto inputDuration = manifest.value(QStringLiteral("input_bag_duration_s")).toDouble();
  const auto trajectoryDuration = metrics.value(QStringLiteral("estimate_header_duration_s")).toDouble();
  const auto profile = manifest.value(QStringLiteral("mapping_process")).toObject();
  return {
      {QStringLiteral("scope"), parts[0]},
      {QStringLiteral("variant"), parts[1]},
      {QStringLiteral("repetition"), parts[2]},
      {QStringLiteral("directory"), QDir::fromNativeSeparators(relative)},
      {QStringLiteral("config_sha256"), manifest.value(QStringLiteral("config_sha256"))},
      {QStringLiteral("playback_rate_requested"), manifest.value(QStringLiteral("playback_rate_requested"))},
      {QStringLiteral("input_scans"), static_cast<double>(inputScans)},
      {QStringLiteral("output_poses"), static_cast<double>(outputPoses)},
      {QStringLiteral("output_scan_ratio_percent"), inputScans ? 100.0 * outputPoses / inputScans : 0.0},
      {QStringLiteral("trajectory_coverage_percent"), inputDuration ? 100.0 * trajectoryDuration / inputDuration : 0.0},
      {QStringLiteral("matched_poses"), metrics.value(QStringLiteral("matched_poses"))},
      {QStringLiteral("ate_translation_rmse_m"), nestedDouble(metrics, {QStringLiteral("ate_translation_m"), QStringLiteral("rmse")})},
      {QStringLiteral("ate_orientation_rmse_deg"), nestedDouble(metrics, {QStringLiteral("ate_orientation_deg"), QStringLiteral("rmse")})},
      {QStringLiteral("rpe_translation_rmse_m"), nestedDouble(metrics, {QStringLiteral("rpe"), QStringLiteral("translation_m"), QStringLiteral("rmse")})},
      {QStringLiteral("rpe_rotation_rmse_deg"), nestedDouble(metrics, {QStringLiteral("rpe"), QStringLiteral("rotation_deg"), QStringLiteral("rmse")})},
      {QStringLiteral("cpu_total_seconds"), profile.value(QStringLiteral("cpu_total_seconds"))},
      {QStringLiteral("cpu_average_equivalent_cores"), profile.value(QStringLiteral("cpu_average_equivalent_cores"))},
      {QStringLiteral("peak_rss_mib"), profile.value(QStringLiteral("peak_rss_mib"))},
      {QStringLiteral("scheduled_data_seconds_per_wall_second"),
       manifest.value(QStringLiteral("scheduled_data_seconds_per_wall_second"))},
  };
}

void summarizeRun(const QJsonObject& options) {
  const auto bag = requiredString(options, QStringLiteral("bag"));
  const auto config = requiredString(options, QStringLiteral("config"));
  const auto profilePath = requiredString(options, QStringLiteral("profile"));
  const auto output = requiredString(options, QStringLiteral("output"));
  const auto metadata = readBagMetadata(bag);
  const auto playbackRate = requiredNumber(options, QStringLiteral("playback-rate"));
  const auto delay = options.value(QStringLiteral("playback-delay-s")).toDouble(0.0);
  const auto start = requiredInteger(options, QStringLiteral("playback-start-ns"));
  const auto end = requiredInteger(options, QStringLiteral("playback-end-ns"));
  const auto wall = static_cast<double>(end - start) * 1e-9;
  const auto active = std::max(0.0, wall - delay);
  const QJsonObject result{
      {QStringLiteral("schema_version"), 3},
      {QStringLiteral("algorithm"), options.value(QStringLiteral("algorithm")).toString(QStringLiteral("fast_lio2"))},
      {QStringLiteral("input_bag"), QFileInfo(bag).absoluteFilePath()},
      {QStringLiteral("input_bag_duration_s"), metadata.durationSeconds},
      {QStringLiteral("input_message_count"), static_cast<double>(metadata.messageCount)},
      {QStringLiteral("input_topic_message_counts"), metadata.topicMessageCounts},
      {QStringLiteral("config"), QFileInfo(config).absoluteFilePath()},
      {QStringLiteral("config_sha256"), QString::fromLatin1(fileSha256(config))},
      {QStringLiteral("playback_rate_requested"), playbackRate},
      {QStringLiteral("playback_delay_seconds"), delay},
      {QStringLiteral("playback_wall_seconds"), wall},
      {QStringLiteral("active_playback_wall_seconds"), active},
      {QStringLiteral("scheduled_data_seconds_per_wall_second"),
       active > 0.0 ? QJsonValue(metadata.durationSeconds / active) : QJsonValue(QJsonValue::Null)},
      {QStringLiteral("mapping_process"), readJsonObject(profilePath)},
  };
  writeJson(output, result);
}

void compareRuns(const QJsonObject& options) {
  const auto runs = options.value(QStringLiteral("runs")).toArray();
  if (runs.size() < 2) {
    throw ContractError(QStringLiteral("Au moins deux résultats sont requis"));
  }
  QJsonArray compact;
  for (const auto& run : runs) {
    compact.append(compactRun(run.toString()));
  }
  const QJsonObject report{{QStringLiteral("schema_version"), 1}, {QStringLiteral("runs"), compact}};
  const auto output = options.value(QStringLiteral("output")).toString();
  if (!output.isEmpty()) {
    writeJson(output, report);
  }
}

void summarizeSensitivity(const QJsonObject& options) {
  const auto root = requiredString(options, QStringLiteral("root"));
  const auto baselineName = options.value(QStringLiteral("baseline")).toString(QStringLiteral("baseline"));
  QJsonArray rows;
  QDir directory(root);
  const auto directories = directory.entryInfoList(QDir::Dirs | QDir::NoDotAndDotDot, QDir::Name);
  const QHash<QString, QStringList> fields{
      {QStringLiteral("ate_translation_rmse_m"), {QStringLiteral("ate_translation_m"), QStringLiteral("rmse")}},
      {QStringLiteral("ate_orientation_rmse_deg"), {QStringLiteral("ate_orientation_deg"), QStringLiteral("rmse")}},
      {QStringLiteral("rpe_translation_rmse_m"), {QStringLiteral("rpe"), QStringLiteral("translation_m"), QStringLiteral("rmse")}},
      {QStringLiteral("rpe_rotation_rmse_deg"), {QStringLiteral("rpe"), QStringLiteral("rotation_deg"), QStringLiteral("rmse")}},
      {QStringLiteral("path_length_ratio"), {QStringLiteral("matched_path_length_m"), QStringLiteral("ratio_estimate_over_ground_truth")}},
  };
  for (const auto& entry : directories) {
    const auto metricsPath = QDir(entry.absoluteFilePath()).filePath(QStringLiteral("metrics.json"));
    const auto manifestPath = QDir(entry.absoluteFilePath()).filePath(QStringLiteral("run_manifest.json"));
    if (!QFileInfo::exists(metricsPath) || !QFileInfo::exists(manifestPath)) {
      continue;
    }
    const auto metrics = readJsonObject(metricsPath);
    const auto manifest = readJsonObject(manifestPath);
    const auto profile = manifest.value(QStringLiteral("mapping_process")).toObject();
    QJsonObject row{
        {QStringLiteral("variant"), entry.fileName()},
        {QStringLiteral("config"), manifest.value(QStringLiteral("config"))},
        {QStringLiteral("config_sha256"), manifest.value(QStringLiteral("config_sha256"))},
        {QStringLiteral("matched_poses"), metrics.value(QStringLiteral("matched_poses"))},
        {QStringLiteral("playback_wall_seconds"), manifest.value(QStringLiteral("playback_wall_seconds"))},
        {QStringLiteral("cpu_total_seconds"), profile.value(QStringLiteral("cpu_total_seconds"))},
        {QStringLiteral("cpu_average_equivalent_cores"), profile.value(QStringLiteral("cpu_average_equivalent_cores"))},
        {QStringLiteral("peak_rss_mib"), profile.value(QStringLiteral("peak_rss_mib"))},
    };
    for (auto iterator = fields.cbegin(); iterator != fields.cend(); ++iterator) {
      row.insert(iterator.key(), nestedDouble(metrics, iterator.value()));
    }
    rows.append(row);
  }
  if (rows.isEmpty()) {
    throw ContractError(QStringLiteral("Aucun résultat de sensibilité complet sous %1").arg(root));
  }
  QJsonObject baseline;
  for (const auto& value : rows) {
    if (value.toObject().value(QStringLiteral("variant")).toString() == baselineName) {
      baseline = value.toObject();
      break;
    }
  }
  if (baseline.isEmpty()) {
    throw ContractError(QStringLiteral("Baseline absente : %1").arg(baselineName));
  }
  for (auto index = 0; index < rows.size(); ++index) {
    auto row = rows[index].toObject();
    for (auto iterator = fields.cbegin(); iterator != fields.cend(); ++iterator) {
      const auto reference = baseline.value(iterator.key()).toDouble();
      const auto value = row.value(iterator.key()).toDouble();
      row.insert(iterator.key() + QStringLiteral("_change_percent"),
                 reference != 0.0 ? QJsonValue(100.0 * (value - reference) / reference) : QJsonValue(QJsonValue::Null));
    }
    rows[index] = row;
  }
  const auto outputJson = options.value(QStringLiteral("output-json")).toString(
      QDir(root).filePath(QStringLiteral("sensitivity_summary.json")));
  const auto outputCsv = options.value(QStringLiteral("output-csv")).toString(
      QDir(root).filePath(QStringLiteral("sensitivity_summary.csv")));
  writeJson(outputJson, {{QStringLiteral("schema_version"), 1}, {QStringLiteral("baseline"), baselineName},
                         {QStringLiteral("runs"), rows}});
  writeCsv(outputCsv, rows);
}

void summarizeCampaign(const QJsonObject& options) {
  const auto root = requiredString(options, QStringLiteral("root"));
  QJsonArray runs;
  QDirIterator iterator(root, QStringList{QStringLiteral("run_manifest.json")}, QDir::Files, QDirIterator::Subdirectories);
  while (iterator.hasNext()) {
    const auto manifestPath = iterator.next();
    const auto directory = QFileInfo(manifestPath).absolutePath();
    if (QFileInfo::exists(QDir(directory).filePath(QStringLiteral("metrics.json")))) {
      const auto relative = QDir(root).relativeFilePath(directory);
      if (QDir::fromNativeSeparators(relative).split(QLatin1Char('/'), Qt::SkipEmptyParts).size() == 3) {
        runs.append(loadCampaignRun(directory, root));
      }
    }
  }
  if (runs.isEmpty()) {
    throw ContractError(QStringLiteral("Aucune répétition complète sous %1").arg(root));
  }
  QSet<QString> keys;
  for (const auto& value : runs) {
    const auto row = value.toObject();
    keys.insert(row.value(QStringLiteral("scope")).toString() + QLatin1Char('\n') +
                row.value(QStringLiteral("variant")).toString());
  }
  auto sortedKeys = keys.values();
  std::sort(sortedKeys.begin(), sortedKeys.end());
  QJsonArray groups;
  for (const auto& key : sortedKeys) {
    const auto parts = key.split(QLatin1Char('\n'));
    QJsonArray selected;
    for (const auto& value : runs) {
      const auto row = value.toObject();
      if (row.value(QStringLiteral("scope")).toString() == parts[0] &&
          row.value(QStringLiteral("variant")).toString() == parts[1]) {
        selected.append(row);
      }
    }
    QJsonObject measurements;
    for (const auto& name : measurementNames()) {
      QList<double> values;
      for (const auto& value : selected) {
        values.append(value.toObject().value(name).toDouble());
      }
      measurements.insert(name, numericStatistics(values));
    }
    groups.append(QJsonObject{{QStringLiteral("scope"), parts[0]}, {QStringLiteral("variant"), parts[1]},
                              {QStringLiteral("repetitions"), selected.size()},
                              {QStringLiteral("measurements"), measurements}});
  }
  const QJsonObject report{{QStringLiteral("schema_version"), 1},
                           {QStringLiteral("playback_rate"), options.value(QStringLiteral("playback-rate")).toDouble(0.8)},
                           {QStringLiteral("runs"), runs}, {QStringLiteral("groups"), groups}};
  writeJson(QDir(root).filePath(QStringLiteral("campaign_summary.json")), report);
  writeCsv(QDir(root).filePath(QStringLiteral("campaign_runs.csv")), runs);
}

void comparePlaybackRates(const QJsonObject& options) {
  const auto campaignRoot = requiredString(options, QStringLiteral("campaign-08x"));
  const auto campaign = readJsonObject(QDir(campaignRoot).filePath(QStringLiteral("campaign_summary.json")));
  const auto previous = readJsonObject(requiredString(options, QStringLiteral("sensitivity-1x")));
  const auto fullDirectory = requiredString(options, QStringLiteral("full-1x"));
  QJsonArray comparisons;
  const QStringList measurements{
      QStringLiteral("output_scan_ratio_percent"), QStringLiteral("ate_translation_rmse_m"),
      QStringLiteral("ate_orientation_rmse_deg"), QStringLiteral("rpe_translation_rmse_m"),
      QStringLiteral("rpe_rotation_rmse_deg"), QStringLiteral("cpu_total_seconds"),
      QStringLiteral("cpu_average_equivalent_cores"), QStringLiteral("peak_rss_mib")};
  for (const auto& groupValue : campaign.value(QStringLiteral("groups")).toArray()) {
    const auto group = groupValue.toObject();
    const auto scope = group.value(QStringLiteral("scope")).toString();
    const auto variant = group.value(QStringLiteral("variant")).toString();
    QList<QJsonObject> oldRows;
    if (scope == QStringLiteral("dynamic")) {
      for (const auto& rowValue : previous.value(QStringLiteral("runs")).toArray()) {
        const auto row = rowValue.toObject();
        const auto rowVariant = row.value(QStringLiteral("variant")).toString();
        if ((variant == QStringLiteral("baseline") && rowVariant.startsWith(QStringLiteral("baseline"))) ||
            rowVariant == variant) {
          oldRows.append({
              {QStringLiteral("output_scan_ratio_percent"), 100.0 * row.value(QStringLiteral("matched_poses")).toDouble() / 298.0},
              {QStringLiteral("ate_translation_rmse_m"), row.value(QStringLiteral("ate_translation_rmse_m"))},
              {QStringLiteral("ate_orientation_rmse_deg"), row.value(QStringLiteral("ate_orientation_rmse_deg"))},
              {QStringLiteral("rpe_translation_rmse_m"), row.value(QStringLiteral("rpe_translation_rmse_m"))},
              {QStringLiteral("rpe_rotation_rmse_deg"), row.value(QStringLiteral("rpe_rotation_rmse_deg"))},
              {QStringLiteral("cpu_total_seconds"), row.value(QStringLiteral("cpu_total_seconds"))},
              {QStringLiteral("cpu_average_equivalent_cores"), row.value(QStringLiteral("cpu_average_equivalent_cores"))},
              {QStringLiteral("peak_rss_mib"), row.value(QStringLiteral("peak_rss_mib"))},
          });
        }
      }
    } else if (scope == QStringLiteral("full") && variant == QStringLiteral("baseline")) {
      auto compact = compactRun(fullDirectory);
      compact.insert(QStringLiteral("output_scan_ratio_percent"),
                     100.0 * readJsonObject(QDir(fullDirectory).filePath(QStringLiteral("metrics.json")))
                                 .value(QStringLiteral("estimate_poses"))
                                 .toDouble() /
                         5762.0);
      oldRows.append(compact);
    } else {
      continue;
    }
    if (oldRows.isEmpty()) {
      continue;
    }
    QJsonObject atOne;
    QJsonObject atCandidate;
    QJsonObject changes;
    const auto candidate = group.value(QStringLiteral("measurements")).toObject();
    for (const auto& measurement : measurements) {
      QList<double> oldValues;
      for (const auto& row : oldRows) {
        oldValues.append(row.value(measurement).toDouble());
      }
      const auto oldStats = numericStatistics(oldValues);
      const auto newStats = candidate.value(measurement).toObject();
      const auto oldMean = oldStats.value(QStringLiteral("mean")).toDouble();
      const auto newMean = newStats.value(QStringLiteral("mean")).toDouble();
      atOne.insert(measurement, oldStats);
      atCandidate.insert(measurement, newStats);
      changes.insert(measurement,
                     QJsonObject{{QStringLiteral("absolute"), newMean - oldMean},
                                 {QStringLiteral("percent"), oldMean != 0.0
                                                                   ? QJsonValue(100.0 * (newMean - oldMean) / oldMean)
                                                                   : QJsonValue(QJsonValue::Null)}});
    }
    comparisons.append(QJsonObject{{QStringLiteral("scope"), scope}, {QStringLiteral("variant"), variant},
                                   {QStringLiteral("at_1x"), atOne}, {QStringLiteral("at_08x"), atCandidate},
                                   {QStringLiteral("change_08x_minus_1x"), changes}});
  }
  const QJsonObject report{{QStringLiteral("schema_version"), 1}, {QStringLiteral("reference_rate"), 1.0},
                           {QStringLiteral("candidate_rate"), 0.8}, {QStringLiteral("comparisons"), comparisons}};
  writeJson(QDir(campaignRoot).filePath(QStringLiteral("comparison_1x_vs_08x.json")), report);
}

}  // namespace drone_agricole::core
