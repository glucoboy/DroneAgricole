#include "drone_agricole/core/ResultRepository.hpp"

#include "drone_agricole/core/JsonUtils.hpp"
#include "drone_agricole/core/ResultAdapter.hpp"
#include "drone_agricole/core/RosbagTrajectoryReader.hpp"
#include "drone_agricole/core/VineyardMap.hpp"

#include <QDir>
#include <QDirIterator>
#include <QFileInfo>
#include <QJsonDocument>
#include <QSet>

#include <algorithm>

namespace drone_agricole::core {
namespace {

std::pair<QString, QString> datasetReference(const QJsonObject& manifest) {
  for (const auto& value : manifest.value(QStringLiteral("inputs")).toArray()) {
    const auto input = value.toObject();
    if (input.value(QStringLiteral("kind")).toString() != QStringLiteral("dataset_sequence")) {
      continue;
    }
    const auto reference = input.value(QStringLiteral("reference")).toObject();
    return {reference.value(QStringLiteral("dataset_id")).toString(),
            reference.value(QStringLiteral("sequence_id")).toString()};
  }
  return {};
}

QJsonObject requestForDirectory(const QString& directory) {
  auto request = readJsonObject(QDir(directory).filePath(QStringLiteral("run_request.json")), false);
  if (request.isEmpty()) {
    request = readJsonObject(QDir(directory).filePath(QStringLiteral("dashboard_request.json")), false);
  }
  return request;
}

QJsonObject duplicateRequest(const QString& directory, const QJsonObject& manifest) {
  const auto request = requestForDirectory(directory);
  const auto parameters = request.value(QStringLiteral("parameters")).toObject();
  if (request.isEmpty() || parameters.isEmpty()) {
    return {};
  }
  const auto simulationId = manifest.value(QStringLiteral("simulation_id")).toString();
  const auto variantId = manifest.value(QStringLiteral("variant_id")).toString();
  if (simulationId.isEmpty() || variantId.isEmpty()) {
    return {};
  }
  auto inputs = request.value(QStringLiteral("inputs")).toArray();
  if (inputs.isEmpty()) {
    inputs = manifest.value(QStringLiteral("inputs")).toArray();
  }
  if (simulationId == QStringLiteral("lio_benchmark")) {
    const auto reference = datasetReference(QJsonObject{{QStringLiteral("inputs"), inputs}});
    if (reference.first.isEmpty() || reference.second.isEmpty() || reference.first.startsWith(QStringLiteral("unknown_")) ||
        reference.second.startsWith(QStringLiteral("unknown_"))) {
      return {};
    }
  }
  return QJsonObject{
      {QStringLiteral("simulation_id"), simulationId},
      {QStringLiteral("variant_id"), variantId},
      {QStringLiteral("profile_id"), request.value(QStringLiteral("profile_id"))},
      {QStringLiteral("inputs"), inputs},
      {QStringLiteral("parameters"), parameters},
  };
}

QStringList tagsFor(const QString& directory, const QString& sourceKind, const QJsonObject& manifest) {
  QSet<QString> tags;
  const auto request = requestForDirectory(directory);
  for (const auto& value : request.value(QStringLiteral("tags")).toArray()) {
    if (!value.toString().trimmed().isEmpty()) {
      tags.insert(value.toString().trimmed().toLower());
    }
  }
  for (const auto& value : manifest.value(QStringLiteral("metadata")).toObject().value(QStringLiteral("tags")).toArray()) {
    if (!value.toString().trimmed().isEmpty()) {
      tags.insert(value.toString().trimmed().toLower());
    }
  }
  tags.insert(sourceKind == QStringLiteral("t0_native") ? QStringLiteral("native") : QStringLiteral("historique"));
  tags.insert(manifest.value(QStringLiteral("domain")).toString());
  auto values = tags.values();
  std::sort(values.begin(), values.end());
  return values;
}

bool replayAvailable(const QString& directory, const NormalizedResult& normalized) {
  if (normalized.manifest.value(QStringLiteral("domain")).toString() == QStringLiteral("flight_simulation")) {
    return !normalized.events.isEmpty() || QFileInfo::exists(QDir(directory).filePath(QStringLiteral("result.json")));
  }
  for (const auto& value : normalized.artifacts.value(QStringLiteral("items")).toArray()) {
    const auto artifact = value.toObject();
    if (!artifact.value(QStringLiteral("replayable")).toBool()) {
      continue;
    }
    const auto kind = artifact.value(QStringLiteral("kind")).toString();
    const auto candidate = QFileInfo(QDir(directory).filePath(artifact.value(QStringLiteral("path")).toString())).absoluteFilePath();
    if (pathIsInside(directory, candidate) && QFileInfo::exists(candidate) &&
        (kind == QStringLiteral("rosbag") || kind == QStringLiteral("trajectory") ||
         kind == QStringLiteral("map"))) {
      return true;
    }
  }
  return QFileInfo(QDir(directory).filePath(QStringLiteral("estimate"))).isDir();
}

bool matches(const ResultSummary& item, const SearchFilters& filters) {
  if (!filters.domain.isEmpty() && item.domain != filters.domain) {
    return false;
  }
  if (!filters.datasetId.isEmpty() && item.datasetId != filters.datasetId) {
    return false;
  }
  if (!filters.scenarioId.isEmpty() && item.scenarioId != filters.scenarioId) {
    return false;
  }
  if (!filters.algorithmId.isEmpty() && item.variantId != filters.algorithmId) {
    return false;
  }
  if (!filters.state.isEmpty() && item.state != filters.state) {
    return false;
  }
  if (!filters.tag.isEmpty() && !item.tags.contains(filters.tag.toLower())) {
    return false;
  }
  if (filters.dateFrom.isValid() && item.createdAtUtc.date() < filters.dateFrom) {
    return false;
  }
  if (filters.dateTo.isValid() && item.createdAtUtc.date() > filters.dateTo) {
    return false;
  }
  return true;
}

}  // namespace

ResultRepository::ResultRepository(QString workspace, QString resultsDirectory)
    : workspace_(normalizedPath(QFileInfo(std::move(workspace)).absoluteFilePath())) {
  resultsRoot_ = resultsDirectory.isEmpty()
                     ? normalizedPath(QDir(workspace_).filePath(QStringLiteral("results")))
                     : normalizedPath(QFileInfo(std::move(resultsDirectory)).absoluteFilePath());
  if (!pathIsInside(workspace_, resultsRoot_)) {
    throw ContractError(QStringLiteral("Le dépôt de résultats doit rester dans le workspace"));
  }
}

void ResultRepository::refresh() {
  QHash<QString, Record> freshRecords;
  QJsonArray freshErrors;
  QSet<QString> directories;
  if (QFileInfo(resultsRoot_).isDir()) {
    QDirIterator iterator(resultsRoot_, QDir::Files, QDirIterator::Subdirectories);
    while (iterator.hasNext()) {
      iterator.next();
      const auto name = iterator.fileInfo().fileName();
      if (name == QStringLiteral("t0_run_manifest.json") || name == QStringLiteral("run_manifest.json") ||
          name == QStringLiteral("result.json")) {
        directories.insert(normalizedPath(iterator.fileInfo().absolutePath()));
      }
    }
  }
  auto ordered = directories.values();
  std::sort(ordered.begin(), ordered.end());
  for (const auto& directory : ordered) {
    try {
      if (!pathIsInside(resultsRoot_, directory)) {
        continue;
      }
      auto normalized = normalizeResultDirectory(directory);
      auto summary = publicSummary(directory, normalized);
      // Conserver la clé avant le déplacement de summary : l'ordre d'évaluation des
      // arguments de insert ne doit jamais pouvoir vider resultId avant sa lecture.
      const auto resultId = summary.resultId;
      freshRecords.insert(resultId, Record{directory, std::move(normalized), std::move(summary)});
    } catch (const ContractError& error) {
      freshErrors.append(QJsonObject{
          {QStringLiteral("directory"), normalizedPath(QDir(resultsRoot_).relativeFilePath(directory))},
          {QStringLiteral("error"), QString::fromUtf8(error.what())},
      });
    }
  }
  records_ = std::move(freshRecords);
  errors_ = std::move(freshErrors);
  for (auto iterator = replayCache_.begin(); iterator != replayCache_.end();) {
    if (!records_.contains(iterator.key())) {
      iterator = replayCache_.erase(iterator);
    } else {
      ++iterator;
    }
  }
}

QList<ResultSummary> ResultRepository::search(const SearchFilters& filters) const {
  QList<ResultSummary> values;
  values.reserve(records_.size());
  for (const auto& recordValue : records_) {
    if (matches(recordValue.summary, filters)) {
      values.append(recordValue.summary);
    }
  }
  std::sort(values.begin(), values.end(), [](const auto& left, const auto& right) {
    if (left.createdAtUtc == right.createdAtUtc) {
      return left.resultId > right.resultId;
    }
    return left.createdAtUtc > right.createdAtUtc;
  });
  return values;
}

ResultDetail ResultRepository::detail(const QString& resultId) const {
  const auto& value = record(resultId);
  auto artifacts = value.normalized.artifacts;
  auto items = artifacts.value(QStringLiteral("items")).toArray();
  for (qsizetype index = 0; index < items.size(); ++index) {
    auto artifact = items.at(index).toObject();
    const auto candidate = QFileInfo(QDir(value.directory).filePath(artifact.value(QStringLiteral("path")).toString())).absoluteFilePath();
    const auto safe = pathIsInside(value.directory, candidate);
    const QFileInfo info(candidate);
    artifact.insert(QStringLiteral("available"), safe && info.exists());
    artifact.insert(QStringLiteral("size_bytes"), safe && info.isFile() ? QJsonValue(static_cast<double>(info.size()))
                                                                          : QJsonValue::Null);
    items.replace(index, artifact);
  }
  artifacts.insert(QStringLiteral("items"), items);
  const auto legacyMetrics = readJsonObject(QDir(value.directory).filePath(QStringLiteral("metrics.json")), false);
  return ResultDetail{value.summary, value.normalized.manifest, value.normalized.metrics, legacyMetrics, artifacts,
                      value.normalized.events, duplicateRequest(value.directory, value.normalized.manifest)};
}

ReplayData ResultRepository::replay(const QString& resultId) {
  if (replayCache_.contains(resultId)) {
    return replayCache_.value(resultId);
  }
  const auto& value = record(resultId);
  if (!value.summary.replayAvailable) {
    throw ContractError(QStringLiteral("Ce résultat ne possède aucun artefact rechargeable"));
  }
  ReplayData replayValue;
  if (value.summary.domain == QStringLiteral("flight_simulation")) {
    replayValue = replayPx4(value);
  } else if (value.summary.domain == QStringLiteral("mapping")) {
    QString mapPath;
    for (const auto& artifactValue : value.normalized.artifacts.value(QStringLiteral("items")).toArray()) {
      const auto artifact = artifactValue.toObject();
      if (!artifact.value(QStringLiteral("replayable")).toBool() ||
          artifact.value(QStringLiteral("kind")).toString() != QStringLiteral("map")) {
        continue;
      }
      const auto candidate =
          QFileInfo(QDir(value.directory).filePath(artifact.value(QStringLiteral("path")).toString())).absoluteFilePath();
      if (pathIsInside(value.directory, candidate) && QFileInfo(candidate).isFile()) {
        mapPath = candidate;
        break;
      }
    }
    if (mapPath.isEmpty()) {
      throw ContractError(QStringLiteral("Artefact de carte rechargeable absent"));
    }
    replayValue = readVineyardMapReplay(mapPath, resultId);
  } else {
    QString bagPath;
    for (const auto& artifactValue : value.normalized.artifacts.value(QStringLiteral("items")).toArray()) {
      const auto artifact = artifactValue.toObject();
      const auto kind = artifact.value(QStringLiteral("kind")).toString();
      if (kind != QStringLiteral("rosbag") && kind != QStringLiteral("trajectory")) {
        continue;
      }
      const auto candidate = QFileInfo(QDir(value.directory).filePath(artifact.value(QStringLiteral("path")).toString())).absoluteFilePath();
      if (pathIsInside(value.directory, candidate) && QFileInfo::exists(candidate)) {
        bagPath = candidate;
        break;
      }
    }
    if (bagPath.isEmpty()) {
      const auto candidate = QDir(value.directory).filePath(QStringLiteral("estimate"));
      if (QFileInfo(candidate).isDir()) {
        bagPath = candidate;
      }
    }
    if (bagPath.isEmpty()) {
      throw ContractError(QStringLiteral("Rosbag de trajectoire absent"));
    }
    replayValue = readLioTrajectory(bagPath, resultId);
  }
  replayCache_.insert(resultId, replayValue);
  return replayValue;
}

qsizetype ResultRepository::totalCount() const noexcept { return records_.size(); }

qsizetype ResultRepository::invalidResultCount() const noexcept { return errors_.size(); }

QJsonArray ResultRepository::errors() const { return errors_; }

const QString& ResultRepository::workspace() const noexcept { return workspace_; }

const QString& ResultRepository::resultsRoot() const noexcept { return resultsRoot_; }

const ResultRepository::Record& ResultRepository::record(const QString& resultId) const {
  const auto iterator = records_.constFind(resultId);
  if (iterator == records_.cend()) {
    throw ContractError(QStringLiteral("Résultat introuvable ou identifiant expiré"));
  }
  return iterator.value();
}

ResultSummary ResultRepository::publicSummary(const QString& directory, const NormalizedResult& normalized) const {
  const auto& manifest = normalized.manifest;
  const auto relative = normalizedPath(QDir(resultsRoot_).relativeFilePath(directory));
  const auto dataset = datasetReference(manifest);
  const auto domain = manifest.value(QStringLiteral("domain")).toString();
  const auto variantId = manifest.value(QStringLiteral("variant_id")).toString();
  auto createdAt = parseUtcDate(manifest.value(QStringLiteral("started_at_utc")));
  if (!createdAt.isValid()) {
    createdAt = parseUtcDate(manifest.value(QStringLiteral("created_at_utc")));
  }
  if (!createdAt.isValid()) {
    createdAt = QFileInfo(directory).lastModified().toUTC();
  }
  auto metricPreview = normalized.metrics.value(QStringLiteral("summary")).toArray();
  while (metricPreview.size() > 5) {
    metricPreview.removeLast();
  }
  const auto duplicate = duplicateRequest(directory, manifest);
  return ResultSummary{
      sha256Id(relative),
      manifest.value(QStringLiteral("run_id")).toString(),
      relative,
      normalized.sourceKind,
      manifest.value(QStringLiteral("simulation_id")).toString(),
      variantId,
      manifest.value(QStringLiteral("runner_id")).toString(),
      domain,
      manifest.value(QStringLiteral("state")).toString(),
      dataset.first,
      dataset.second,
      domain == QStringLiteral("localization") ? QString{} : variantId,
      manifest.value(QStringLiteral("compatibility")).toObject().value(QStringLiteral("comparison_group")).toString(),
      normalized.metrics.value(QStringLiteral("status")).toString(),
      createdAt,
      parseUtcDate(manifest.value(QStringLiteral("finished_at_utc"))),
      tagsFor(directory, normalized.sourceKind, manifest),
      metricPreview,
      normalized.events.size(),
      normalized.artifacts.value(QStringLiteral("items")).toArray().size(),
      replayAvailable(directory, normalized),
      !duplicate.isEmpty(),
  };
}

ReplayData ResultRepository::replayPx4(const Record& value) {
  ReplayData replay;
  replay.resultId = value.summary.resultId;
  replay.domain = QStringLiteral("flight_simulation");
  replay.px4Path.append(QVector3D{});
  replay.curve.append(QPointF{});
  QVector3D origin;
  bool hasOrigin = false;
  for (const auto& eventValue : value.normalized.events) {
    const auto event = eventValue.toObject();
    const auto data = event.value(QStringLiteral("data")).toObject();
    const auto originArray = data.value(QStringLiteral("origin_ned")).toArray();
    if (!hasOrigin && originArray.size() == 3) {
      origin = QVector3D(static_cast<float>(originArray.at(0).toDouble()), static_cast<float>(originArray.at(1).toDouble()),
                         static_cast<float>(originArray.at(2).toDouble()));
      hasOrigin = true;
    }
    const auto target = data.value(QStringLiteral("target_ned")).toArray();
    if (target.size() != 3) {
      continue;
    }
    QVector3D ned(static_cast<float>(target.at(0).toDouble()), static_cast<float>(target.at(1).toDouble()),
                  static_cast<float>(target.at(2).toDouble()));
    if (hasOrigin) {
      ned -= origin;
    }
    const QVector3D enu(ned.y(), ned.x(), -ned.z());
    replay.px4Path.append(enu);
    replay.curve.append(QPointF(event.value(QStringLiteral("elapsed_s")).toDouble(replay.curve.size()), enu.z()));
  }
  replay.curveId = QStringLiteral("target_altitude_m");
  replay.curveLabel = QStringLiteral("Altitude cible");
  replay.curveUnit = QStringLiteral("m");
  replay.notes.append(QStringLiteral("Parcours reconstruit depuis les consignes NED archivées dans les événements PX4."));
  return replay;
}

}  // namespace drone_agricole::core
