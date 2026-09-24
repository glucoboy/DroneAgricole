#include "drone_agricole/algorithms/RowDetection.hpp"
#include "drone_agricole/core/VineyardMap.hpp"

#include "drone_agricole/core/JsonUtils.hpp"
#include "drone_agricole/core/ResultAdapter.hpp"

#include <QDateTime>
#include <QCryptographicHash>
#include <QDir>
#include <QElapsedTimer>
#include <QFile>
#include <QFileInfo>
#include <QJsonArray>
#include <QJsonDocument>
#include <QTextStream>
#include <QtEndian>

#include <algorithm>
#include <cmath>
#include <cstring>
#include <limits>
#include <numeric>
#include <vector>

namespace drone_agricole::core {
namespace {

constexpr double pi = 3.14159265358979323846;

struct Point3d {
  double x{0.0};
  double y{0.0};
  double z{0.0};
};

struct LasHeader {
  quint8 major{0};
  quint8 minor{0};
  quint32 pointOffset{0};
  quint8 pointFormat{0};
  quint16 pointLength{0};
  quint32 pointCount{0};
  Point3d scale;
  Point3d offset;
  Point3d minimum;
  Point3d maximum;
};

using ActiveCell = algorithms::WeightedCell;



template <typename T>
T littleInteger(const uchar* data) {
  return qFromLittleEndian<T>(data);
}

quint32 bigInteger(const uchar* data) { return qFromBigEndian<quint32>(data); }

double littleDouble(const uchar* data) {
  const auto bits = littleInteger<quint64>(data);
  double value = 0.0;
  std::memcpy(&value, &bits, sizeof(value));
  return value;
}

void requireBytes(const qsizetype size, const qsizetype offset, const qsizetype count, const QString& label) {
  if (offset < 0 || count < 0 || offset + count > size) {
    throw ContractError(QStringLiteral("%1 tronqué ou incohérent").arg(label));
  }
}

LasHeader readLasHeader(const uchar* data, const qsizetype size) {
  requireBytes(size, 0, 227, QStringLiteral("En-tête LAS"));
  if (std::memcmp(data, "LASF", 4) != 0) {
    throw ContractError(QStringLiteral("Signature LASF absente"));
  }
  LasHeader header;
  header.major = data[24];
  header.minor = data[25];
  header.pointOffset = littleInteger<quint32>(data + 96);
  const auto rawFormat = data[104];
  if ((rawFormat & 0x80U) != 0U) {
    throw ContractError(QStringLiteral("Le bootstrap V1 n'accepte pas les fichiers LAZ compressés"));
  }
  header.pointFormat = rawFormat & 0x3fU;
  header.pointLength = littleInteger<quint16>(data + 105);
  header.pointCount = littleInteger<quint32>(data + 107);
  header.scale = {littleDouble(data + 131), littleDouble(data + 139), littleDouble(data + 147)};
  header.offset = {littleDouble(data + 155), littleDouble(data + 163), littleDouble(data + 171)};
  header.maximum = {littleDouble(data + 179), littleDouble(data + 195), littleDouble(data + 211)};
  header.minimum = {littleDouble(data + 187), littleDouble(data + 203), littleDouble(data + 219)};
  if (header.major != 1 || header.minor != 2 || header.pointFormat != 3 || header.pointLength < 34 ||
      header.pointCount == 0) {
    throw ContractError(QStringLiteral("EscaYard V1 attend un LAS 1.2 non compressé de format 3"));
  }
  const auto expected = static_cast<quint64>(header.pointOffset) +
                        static_cast<quint64>(header.pointCount) * header.pointLength;
  if (expected > static_cast<quint64>(size)) {
    throw ContractError(QStringLiteral("Table de points LAS tronquée"));
  }
  return header;
}

Point3d lasPoint(const uchar* data, const LasHeader& header, const quint32 index) {
  const auto* record = data + header.pointOffset + static_cast<quint64>(index) * header.pointLength;
  return {
      static_cast<double>(littleInteger<qint32>(record)) * header.scale.x + header.offset.x,
      static_cast<double>(littleInteger<qint32>(record + 4)) * header.scale.y + header.offset.y,
      static_cast<double>(littleInteger<qint32>(record + 8)) * header.scale.z + header.offset.z,
  };
}

QList<Point3d> readShapefilePoints(const QString& path) {
  QFile file(path);
  if (!file.open(QIODevice::ReadOnly)) {
    throw ContractError(QStringLiteral("Shapefile RTK illisible"));
  }
  const auto bytes = file.readAll();
  const auto* data = reinterpret_cast<const uchar*>(bytes.constData());
  requireBytes(bytes.size(), 0, 100, QStringLiteral("Shapefile RTK"));
  if (bigInteger(data) != 9994U || littleInteger<quint32>(data + 28) != 1000U ||
      littleInteger<quint32>(data + 32) != 1U) {
    throw ContractError(QStringLiteral("Le bootstrap V1 attend un Shapefile de points"));
  }
  QList<Point3d> points;
  qsizetype offset = 100;
  while (offset < bytes.size()) {
    requireBytes(bytes.size(), offset, 8, QStringLiteral("Enregistrement Shapefile"));
    const auto contentBytes = static_cast<qsizetype>(bigInteger(data + offset + 4)) * 2;
    offset += 8;
    requireBytes(bytes.size(), offset, contentBytes, QStringLiteral("Géométrie Shapefile"));
    const auto shapeType = littleInteger<quint32>(data + offset);
    if (shapeType == 1U) {
      requireBytes(bytes.size(), offset, 20, QStringLiteral("Point Shapefile"));
      points.append({littleDouble(data + offset + 4), littleDouble(data + offset + 12), 0.0});
    } else if (shapeType != 0U) {
      throw ContractError(QStringLiteral("Type de géométrie Shapefile non pris en charge"));
    }
    offset += contentBytes;
  }
  if (points.isEmpty()) {
    throw ContractError(QStringLiteral("Aucun tronc RTK dans le Shapefile"));
  }
  return points;
}

QString requiredOption(const QJsonObject& options, const QString& key) {
  const auto value = options.value(key).toString();
  if (value.isEmpty()) {
    throw ContractError(QStringLiteral("L'option --%1 est requise").arg(key));
  }
  return value;
}

double parameter(const QJsonObject& values, const QString& key, const double fallback) {
  const auto value = values.value(key);
  return value.isDouble() ? value.toDouble() : fallback;
}

int integerParameter(const QJsonObject& values, const QString& key, const int fallback) {
  return static_cast<int>(std::llround(parameter(values, key, fallback)));
}

void requireParameterRange(const double value,
                           const double minimum,
                           const double maximum,
                           const QString& key) {
  if (!std::isfinite(value) || value < minimum || value > maximum) {
    throw ContractError(QStringLiteral("Paramètre %1 hors de l'intervalle autorisé [%2, %3]")
                            .arg(key)
                            .arg(minimum)
                            .arg(maximum));
  }
}

void progress(const QString& stage, const int percent) {
  QTextStream(stdout) << "MAP_PROGRESS stage=" << stage << " percent=" << percent << Qt::endl;
}

QJsonArray pointArray(const QList<QVector3D>& points) {
  QJsonArray result;
  for (const auto& point : points) {
    result.append(QJsonArray{point.x(), point.y(), point.z()});
  }
  return result;
}

QList<QVector3D> pointsFromJson(const QJsonValue& value, const qsizetype limit, const QString& label) {
  const auto values = value.toArray();
  if (values.size() > limit) {
    throw ContractError(QStringLiteral("%1 dépasse la limite d'affichage").arg(label));
  }
  QList<QVector3D> points;
  points.reserve(values.size());
  for (const auto& item : values) {
    const auto coordinates = item.toArray();
    if (coordinates.size() != 3 || !coordinates.at(0).isDouble() || !coordinates.at(1).isDouble() ||
        !coordinates.at(2).isDouble()) {
      throw ContractError(QStringLiteral("Point invalide dans %1").arg(label));
    }
    points.append(QVector3D(static_cast<float>(coordinates.at(0).toDouble()),
                            static_cast<float>(coordinates.at(1).toDouble()),
                            static_cast<float>(coordinates.at(2).toDouble())));
  }
  return points;
}

QJsonObject metric(const QString& id,
                   const QString& label,
                   const QJsonValue& value,
                   const QString& unit,
                   const QString& direction,
                   const QString& status,
                   const QJsonObject& metadata = {}) {
  QJsonObject result{
      {QStringLiteral("metric_id"), id},       {QStringLiteral("label"), label},
      {QStringLiteral("value"), value},       {QStringLiteral("unit"), unit},
      {QStringLiteral("direction"), direction}, {QStringLiteral("status"), status},
  };
  if (!metadata.isEmpty()) {
    result.insert(QStringLiteral("metadata"), metadata);
  }
  return result;
}

QJsonObject event(const QString& runId,
                  const int sequence,
                  const double elapsed,
                  const QString& type,
                  const QString& severity,
                  const QString& state,
                  const QString& message,
                  const QJsonObject& data = {}) {
  return {
      {QStringLiteral("schema"), QStringLiteral("drone_agricole.event.v1")},
      {QStringLiteral("run_id"), runId},
      {QStringLiteral("sequence"), sequence},
      {QStringLiteral("elapsed_s"), elapsed},
      {QStringLiteral("event_type"), type},
      {QStringLiteral("severity"), severity},
      {QStringLiteral("state"), state},
      {QStringLiteral("message"), message},
      {QStringLiteral("data"), data},
  };
}

int gridIndex(const double x,
              const double y,
              const double originX,
              const double originY,
              const double cell,
              const int width,
              const int height) {
  const auto column = static_cast<int>(std::floor((x - originX) / cell));
  const auto row = static_cast<int>(std::floor((y - originY) / cell));
  if (column < 0 || row < 0 || column >= width || row >= height) {
    return -1;
  }
  return row * width + column;
}

double percentile(std::vector<double> values, const double ratio) {
  if (values.empty()) {
    return std::numeric_limits<double>::quiet_NaN();
  }
  std::sort(values.begin(), values.end());
  const auto index = static_cast<std::size_t>(std::clamp(ratio, 0.0, 1.0) * (values.size() - 1));
  return values[index];
}

}  // namespace

QJsonObject runVineyardMapping(const QJsonObject& options) {
  QElapsedTimer timer;
  timer.start();
  progress(QStringLiteral("initialization"), 3);
  const auto pointCloudPath = requiredOption(options, QStringLiteral("point-cloud"));
  const auto referenceTrunkPath = options.value(QStringLiteral("reference-trunks")).toString();
  const auto resultDirectory = requiredOption(options, QStringLiteral("run-dir"));
  const auto requestPath = requiredOption(options, QStringLiteral("request"));
  const auto requestedRunId = requiredOption(options, QStringLiteral("run-id"));
  if (QFileInfo::exists(resultDirectory)) {
    throw ContractError(QStringLiteral("Le dossier de résultat existe déjà"));
  }
  const auto request = readJsonObject(requestPath);
  requireSchema(request, QStringLiteral("drone_agricole.run_request.v1"), QStringLiteral("RunRequest"));
  requireFields(request,
                {QStringLiteral("request_id"), QStringLiteral("simulation_id"), QStringLiteral("variant_id"),
                 QStringLiteral("requested_at_utc"), QStringLiteral("inputs"), QStringLiteral("parameters")},
                QStringLiteral("RunRequest"));
  if (request.value(QStringLiteral("simulation_id")).toString() != QStringLiteral("vineyard_mapping") ||
      request.value(QStringLiteral("variant_id")).toString() != QStringLiteral("height_density_v1")) {
    throw ContractError(QStringLiteral("Le runner attend la simulation vineyard_mapping/height_density_v1"));
  }
  const auto parameters = request.value(QStringLiteral("parameters")).toObject();
  const auto groundCell = parameter(parameters, QStringLiteral("ground_cell_m"), 1.0);
  const auto gridResolution = parameter(parameters, QStringLiteral("grid_resolution_m"), 0.30);
  const auto minimumCanopyHeight = parameter(parameters, QStringLiteral("min_canopy_height_m"), 0.55);
  const auto minimumCellPoints = integerParameter(parameters, QStringLiteral("min_cell_points"), 6);
  const auto minimumRowSpacing = parameter(parameters, QStringLiteral("row_spacing_min_m"), 1.50);
  const auto peakRatio = parameter(parameters, QStringLiteral("row_peak_ratio"), 0.30);
  const auto trajectoryClearance = parameter(parameters, QStringLiteral("trajectory_clearance_m"), 2.50);
  const auto displayBudget = integerParameter(parameters, QStringLiteral("display_point_budget"), 30000);
  requireParameterRange(groundCell, 0.5, 3.0, QStringLiteral("ground_cell_m"));
  requireParameterRange(gridResolution, 0.15, 0.75, QStringLiteral("grid_resolution_m"));
  requireParameterRange(minimumCanopyHeight, 0.20, 1.50, QStringLiteral("min_canopy_height_m"));
  requireParameterRange(minimumCellPoints, 1.0, 100.0, QStringLiteral("min_cell_points"));
  requireParameterRange(minimumRowSpacing, 0.75, 4.0, QStringLiteral("row_spacing_min_m"));
  requireParameterRange(peakRatio, 0.05, 0.90, QStringLiteral("row_peak_ratio"));
  requireParameterRange(trajectoryClearance, 1.0, 6.0, QStringLiteral("trajectory_clearance_m"));
  requireParameterRange(displayBudget, 2000.0, 100000.0, QStringLiteral("display_point_budget"));
  const auto runId = safeIdentifier(requestedRunId, QStringLiteral("vineyard_map"));
  const auto startedAt = QDateTime::currentDateTimeUtc().toString(Qt::ISODateWithMs);

  QFile lasFile(pointCloudPath);
  if (!lasFile.open(QIODevice::ReadOnly)) {
    throw ContractError(QStringLiteral("Nuage LAS illisible"));
  }
  auto* lasBytes = lasFile.map(0, lasFile.size());
  if (lasBytes == nullptr) {
    throw ContractError(QStringLiteral("Le nuage LAS ne peut pas être projeté en mémoire"));
  }
  const auto header = readLasHeader(lasBytes, lasFile.size());
  // La prédiction utilise exclusivement le nuage. La référence RTK n'est ouverte
  // qu'après le gel des rangs et trajectoires candidates, dans la phase d'évaluation.
  const auto roiMinimumX = header.minimum.x;
  const auto roiMinimumY = header.minimum.y;
  const auto roiMaximumX = header.maximum.x;
  const auto roiMaximumY = header.maximum.y;

  const auto groundWidth = static_cast<int>(std::ceil((roiMaximumX - roiMinimumX) / groundCell)) + 1;
  const auto groundHeight = static_cast<int>(std::ceil((roiMaximumY - roiMinimumY) / groundCell)) + 1;
  const auto fineWidth = static_cast<int>(std::ceil((roiMaximumX - roiMinimumX) / gridResolution)) + 1;
  const auto fineHeight = static_cast<int>(std::ceil((roiMaximumY - roiMinimumY) / gridResolution)) + 1;
  const auto groundSize = static_cast<quint64>(groundWidth) * groundHeight;
  const auto fineSize = static_cast<quint64>(fineWidth) * fineHeight;
  if (groundSize == 0 || groundSize > 2000000ULL || fineSize == 0 || fineSize > 5000000ULL) {
    lasFile.unmap(lasBytes);
    throw ContractError(QStringLiteral("Grille cartographique hors limites"));
  }
  std::vector<float> ground(static_cast<std::size_t>(groundSize), std::numeric_limits<float>::infinity());
  quint64 roiPointCount = 0;
  for (quint32 index = 0; index < header.pointCount; ++index) {
    const auto point = lasPoint(lasBytes, header, index);
    const auto cell = gridIndex(point.x, point.y, roiMinimumX, roiMinimumY, groundCell, groundWidth, groundHeight);
    if (cell < 0) {
      continue;
    }
    ground[static_cast<std::size_t>(cell)] =
        std::min(ground[static_cast<std::size_t>(cell)], static_cast<float>(point.z));
    ++roiPointCount;
  }
  if (roiPointCount == 0) {
    lasFile.unmap(lasBytes);
    throw ContractError(QStringLiteral("Aucun point LAS dans l'emprise déclarée par le nuage"));
  }
  progress(QStringLiteral("terrain"), 28);

  const auto groundAt = [&](const double x, const double y) {
    const auto column = static_cast<int>(std::floor((x - roiMinimumX) / groundCell));
    const auto row = static_cast<int>(std::floor((y - roiMinimumY) / groundCell));
    auto bestDistance = std::numeric_limits<int>::max();
    auto best = std::numeric_limits<float>::infinity();
    for (int radius = 0; radius <= 2; ++radius) {
      for (int deltaY = -radius; deltaY <= radius; ++deltaY) {
        for (int deltaX = -radius; deltaX <= radius; ++deltaX) {
          const auto candidateX = column + deltaX;
          const auto candidateY = row + deltaY;
          if (candidateX < 0 || candidateY < 0 || candidateX >= groundWidth || candidateY >= groundHeight) {
            continue;
          }
          const auto value = ground[static_cast<std::size_t>(candidateY * groundWidth + candidateX)];
          const auto distance = deltaX * deltaX + deltaY * deltaY;
          if (std::isfinite(value) && distance < bestDistance) {
            best = value;
            bestDistance = distance;
          }
        }
      }
      if (std::isfinite(best)) {
        break;
      }
    }
    return static_cast<double>(best);
  };

  std::vector<quint32> density(static_cast<std::size_t>(fineSize), 0U);
  std::vector<double> heightSum(static_cast<std::size_t>(fineSize), 0.0);
  QList<QVector3D> displayCloud;
  displayCloud.reserve(displayBudget);
  const auto sampleStride = std::max<quint64>(1, roiPointCount / static_cast<quint64>(std::max(1, displayBudget)));
  quint64 visitedInRoi = 0;
  quint64 vegetationPointCount = 0;
  for (quint32 index = 0; index < header.pointCount; ++index) {
    const auto point = lasPoint(lasBytes, header, index);
    const auto fineCell = gridIndex(point.x, point.y, roiMinimumX, roiMinimumY, gridResolution, fineWidth, fineHeight);
    if (fineCell < 0) {
      continue;
    }
    if (displayCloud.size() < displayBudget && visitedInRoi % sampleStride == 0U) {
      displayCloud.append(QVector3D(static_cast<float>(point.x - roiMinimumX),
                                    static_cast<float>(point.y - roiMinimumY),
                                    static_cast<float>(point.z - header.minimum.z)));
    }
    ++visitedInRoi;
    const auto localGround = groundAt(point.x, point.y);
    const auto heightAboveGround = point.z - localGround;
    if (!std::isfinite(localGround) || heightAboveGround < minimumCanopyHeight || heightAboveGround > 4.0) {
      continue;
    }
    auto& count = density[static_cast<std::size_t>(fineCell)];
    ++count;
    heightSum[static_cast<std::size_t>(fineCell)] += point.z;
    ++vegetationPointCount;
  }
  lasFile.unmap(lasBytes);
  progress(QStringLiteral("vegetation"), 52);

  std::vector<ActiveCell> active;
  active.reserve(static_cast<std::size_t>(fineSize / 4));
  for (int row = 0; row < fineHeight; ++row) {
    for (int column = 0; column < fineWidth; ++column) {
      const auto index = static_cast<std::size_t>(row * fineWidth + column);
      const auto count = density[index];
      if (count < static_cast<quint32>(minimumCellPoints)) {
        continue;
      }
      active.push_back({(column + 0.5) * gridResolution,
                        (row + 0.5) * gridResolution,
                        heightSum[index] / count,
                        std::log1p(static_cast<double>(count))});
    }
  }
  if (active.size() < 20) {
    throw ContractError(QStringLiteral("Masque de végétation insuffisant pour estimer les rangs"));
  }

  const auto detected = algorithms::detectWeightedRows(active,
      {roiMaximumX - roiMinimumX, roiMaximumY - roiMinimumY, gridResolution, minimumRowSpacing, peakRatio},
      [&](double x, double y) { return groundAt(roiMinimumX + x, roiMinimumY + y) - header.minimum.z; });
  const auto& rows = detected.rows;
  const auto bestAngleDegrees = detected.orientationDegrees;
  const auto angle = bestAngleDegrees * pi / 180.0;
  const auto tangentX = std::cos(angle);
  const auto tangentY = std::sin(angle);
  const auto normalX = -tangentY;
  const auto normalY = tangentX;
  progress(QStringLiteral("rows"), 74);

  QList<ReplayData::Polyline> polylines;
  for (std::size_t index = 0; index < rows.size(); ++index) {
    polylines.append({QStringLiteral("Rang détecté %1").arg(index + 1), QStringLiteral("detected_row"),
                      rows[index].points});
  }
  int candidateTrajectoryCount = 0;
  for (std::size_t index = 1; index < rows.size(); ++index) {
    const auto spacing = rows[index].rho - rows[index - 1].rho;
    if (spacing < minimumRowSpacing * 0.8 || spacing > 4.5) {
      continue;
    }
    auto minimumT = std::max(rows[index - 1].minimumT, rows[index].minimumT) + 2.0;
    auto maximumT = std::min(rows[index - 1].maximumT, rows[index].maximumT) - 2.0;
    if (maximumT - minimumT < 8.0) {
      continue;
    }
    if (candidateTrajectoryCount % 2 != 0) {
      std::swap(minimumT, maximumT);
    }
    const auto rho = 0.5 * (rows[index - 1].rho + rows[index].rho);
    const auto segmentCount = std::max(2, static_cast<int>(std::ceil(std::abs(maximumT - minimumT) / 2.0)) + 1);
    QList<QVector3D> points;
    for (int segment = 0; segment < segmentCount; ++segment) {
      const auto ratio = static_cast<double>(segment) / (segmentCount - 1);
      const auto t = minimumT + ratio * (maximumT - minimumT);
      const auto localX = tangentX * t + normalX * rho;
      const auto localY = tangentY * t + normalY * rho;
      const auto terrain = groundAt(roiMinimumX + localX, roiMinimumY + localY);
      points.append(QVector3D(static_cast<float>(localX), static_cast<float>(localY),
                              static_cast<float>((std::isfinite(terrain) ? terrain : header.minimum.z) -
                                                 header.minimum.z + trajectoryClearance)));
    }
    ++candidateTrajectoryCount;
    polylines.append({QStringLiteral("Trajectoire candidate %1").arg(candidateTrajectoryCount),
                      QStringLiteral("candidate_trajectory"), points});
  }

  QJsonArray replayPolylines;
  for (const auto& line : polylines) {
    replayPolylines.append(QJsonObject{{QStringLiteral("label"), line.label},
                                       {QStringLiteral("role"), line.role},
                                       {QStringLiteral("points"), pointArray(line.points)}});
  }
  const auto prediction = QJsonObject{
      {QStringLiteral("schema"), QStringLiteral("drone_agricole.map_prediction.v1")},
      {QStringLiteral("run_id"), runId},
      {QStringLiteral("domain"), QStringLiteral("mapping")},
      {QStringLiteral("local_origin"), QJsonArray{roiMinimumX, roiMinimumY, header.minimum.z}},
      {QStringLiteral("point_cloud"), pointArray(displayCloud)},
      {QStringLiteral("polylines"), replayPolylines},
      {QStringLiteral("metadata"),
       QJsonObject{{QStringLiteral("point_cloud_crs"), QStringLiteral("EPSG:32629")},
                   {QStringLiteral("orientation_deg"), bestAngleDegrees},
                   {QStringLiteral("roi_source"), QStringLiteral("point_cloud_header_bounds")},
                   {QStringLiteral("perception_inputs"), QJsonArray{QStringLiteral("point_cloud")}}}},
  };
  QDir().mkpath(resultDirectory);
  writeJsonObjectAtomically(QDir(resultDirectory).filePath(QStringLiteral("map_prediction.json")), prediction);
  auto canonicalPrediction = prediction;
  canonicalPrediction.remove(QStringLiteral("run_id"));
  const auto predictionSha256 = QString::fromLatin1(
      QCryptographicHash::hash(QJsonDocument(canonicalPrediction).toJson(QJsonDocument::Compact),
                               QCryptographicHash::Sha256)
          .toHex());

  // À partir de ce point seulement, la prédiction est écrite et figée. La vérité
  // terrain peut être chargée par l'évaluateur sans influencer la détection.
  const auto trunks = referenceTrunkPath.isEmpty() ? QList<Point3d>{} : readShapefilePoints(referenceTrunkPath);
  const auto referenceAvailable = !trunks.isEmpty();
  progress(QStringLiteral("evaluation"), 82);

  QList<QVector3D> referencePoints;
  referencePoints.reserve(trunks.size());
  std::vector<double> crossTrackErrors;
  crossTrackErrors.reserve(static_cast<std::size_t>(trunks.size()));
  for (const auto& trunk : trunks) {
    const auto localX = trunk.x - roiMinimumX;
    const auto localY = trunk.y - roiMinimumY;
    const auto terrain = groundAt(trunk.x, trunk.y);
    referencePoints.append(QVector3D(static_cast<float>(localX), static_cast<float>(localY),
                                     static_cast<float>((std::isfinite(terrain) ? terrain : header.minimum.z) -
                                                        header.minimum.z + 0.15)));
    const auto trunkRho = normalX * localX + normalY * localY;
    auto error = std::numeric_limits<double>::infinity();
    for (const auto& row : rows) {
      error = std::min(error, std::abs(trunkRho - row.rho));
    }
    if (std::isfinite(error)) {
      crossTrackErrors.push_back(error);
    }
  }

  const auto medianError = percentile(crossTrackErrors, 0.50);
  const auto p95Error = percentile(crossTrackErrors, 0.95);
  double squaredError = 0.0;
  int covered = 0;
  for (const auto error : crossTrackErrors) {
    squaredError += error * error;
    if (error <= 0.75) {
      ++covered;
    }
  }
  const auto rmse = crossTrackErrors.empty()
                        ? std::numeric_limits<double>::quiet_NaN()
                        : std::sqrt(squaredError / static_cast<double>(crossTrackErrors.size()));
  const auto coverage = crossTrackErrors.empty()
                            ? 0.0
                            : 100.0 * covered / static_cast<double>(crossTrackErrors.size());

  QJsonArray warnings;
  if (referenceAvailable) {
    warnings.append(QStringLiteral("Le LAS annonce EPSG:32629 tandis que les troncs annoncent EPSG:25829."));
  } else {
    warnings.append(QStringLiteral("Aucune référence de troncs n'est disponible ; les métriques RTK ne sont pas calculées."));
  }
  warnings.append(QStringLiteral("Le datum vertical est inconnu."));
  warnings.append(QStringLiteral("Les trajectoires sont des candidats de visualisation hors ligne, pas des ordres de vol."));
  auto replay = prediction;
  replay.insert(QStringLiteral("schema"), QStringLiteral("drone_agricole.map_replay.v1"));
  replay.insert(QStringLiteral("reference_points"), pointArray(referencePoints));
  replay.insert(QStringLiteral("warnings"), warnings);
  auto replayMetadata = replay.value(QStringLiteral("metadata")).toObject();
  replayMetadata.insert(QStringLiteral("reference_crs"),
                        referenceAvailable ? QStringLiteral("EPSG:25829") : QStringLiteral("unavailable"));
  replayMetadata.insert(QStringLiteral("reference_role"), QStringLiteral("evaluation_only_after_prediction"));
  replayMetadata.insert(QStringLiteral("prediction_frozen_before_reference_load"), true);
  replayMetadata.insert(QStringLiteral("prediction_content_sha256"), predictionSha256);
  replay.insert(QStringLiteral("metadata"), replayMetadata);
  writeJsonObjectAtomically(QDir(resultDirectory).filePath(QStringLiteral("map_replay.json")), replay);
  progress(QStringLiteral("artifacts"), 91);
  const auto finishedAt = QDateTime::currentDateTimeUtc().toString(Qt::ISODateWithMs);
  const auto provisional = QJsonObject{
      {QStringLiteral("preliminary"), true},
      {QStringLiteral("reason"), referenceAvailable ? QStringLiteral("crs_mismatch_and_parameters_to_validate")
                                                      : QStringLiteral("reference_unavailable_and_parameters_to_validate")}};
  const auto referenceStatus = referenceAvailable ? QStringLiteral("warning") : QStringLiteral("unknown");
  const auto summary = QJsonArray{
      metric(QStringLiteral("detected_row_count"), QStringLiteral("Rangs détectés"),
             static_cast<double>(rows.size()), QStringLiteral("rang"), QStringLiteral("neutral"), QStringLiteral("warning"), provisional),
      metric(QStringLiteral("candidate_trajectory_count"), QStringLiteral("Trajectoires candidates"),
             candidateTrajectoryCount, QStringLiteral("trajectoire"), QStringLiteral("neutral"), QStringLiteral("warning"), provisional),
      metric(QStringLiteral("trunk_cross_track_rmse_m"), QStringLiteral("Écart RTK RMSE préliminaire"),
             std::isfinite(rmse) ? QJsonValue(rmse) : QJsonValue::Null, QStringLiteral("m"), QStringLiteral("lower"), referenceStatus, provisional),
      metric(QStringLiteral("trunk_cross_track_median_m"), QStringLiteral("Écart RTK médian préliminaire"),
             std::isfinite(medianError) ? QJsonValue(medianError) : QJsonValue::Null, QStringLiteral("m"), QStringLiteral("lower"), referenceStatus, provisional),
      metric(QStringLiteral("trunk_cross_track_p95_m"), QStringLiteral("Écart RTK P95 préliminaire"),
             std::isfinite(p95Error) ? QJsonValue(p95Error) : QJsonValue::Null, QStringLiteral("m"), QStringLiteral("lower"), referenceStatus, provisional),
      metric(QStringLiteral("trunk_coverage_075m_percent"), QStringLiteral("Troncs à moins de 0,75 m"),
             referenceAvailable ? QJsonValue(coverage) : QJsonValue::Null, QStringLiteral("%"), QStringLiteral("higher"), referenceStatus, provisional),
      metric(QStringLiteral("processed_point_count"), QStringLiteral("Points LAS analysés"),
             static_cast<double>(roiPointCount), QStringLiteral("point"), QStringLiteral("neutral"), QStringLiteral("good")),
  };
  const auto manifest = QJsonObject{
      {QStringLiteral("schema"), QStringLiteral("drone_agricole.run_manifest.v1")},
      {QStringLiteral("run_id"), runId},
      {QStringLiteral("request_id"), request.value(QStringLiteral("request_id"))},
      {QStringLiteral("simulation_id"), QStringLiteral("vineyard_mapping")},
      {QStringLiteral("variant_id"), QStringLiteral("height_density_v1")},
      {QStringLiteral("runner_id"), QStringLiteral("vineyard_height_density")},
      {QStringLiteral("domain"), QStringLiteral("mapping")},
      {QStringLiteral("state"), QStringLiteral("completed")},
      {QStringLiteral("created_at_utc"), startedAt},
      {QStringLiteral("started_at_utc"), startedAt},
      {QStringLiteral("finished_at_utc"), finishedAt},
      {QStringLiteral("inputs"), request.value(QStringLiteral("inputs")).toArray()},
      {QStringLiteral("parameters"), parameters},
      {QStringLiteral("software"), QJsonObject{{QStringLiteral("implementation"), QStringLiteral("cpp17_height_density_v1")}}},
      {QStringLiteral("files"), QJsonObject{{QStringLiteral("map_prediction"), QStringLiteral("map_prediction.json")},
                                              {QStringLiteral("map_replay"), QStringLiteral("map_replay.json")}}},
      {QStringLiteral("compatibility"), QJsonObject{{QStringLiteral("comparison_group"), QStringLiteral("vineyard_rows_b7_v1")},
                                                     {QStringLiteral("result_contract_version"), 1}}},
      {QStringLiteral("metadata"), QJsonObject{{QStringLiteral("tags"), QJsonArray{QStringLiteral("escayard"), QStringLiteral("mapping"), QStringLiteral("preliminary")}},
                                                {QStringLiteral("mapping_safe"), false},
                                                {QStringLiteral("prediction_content_sha256"), predictionSha256},
                                                {QStringLiteral("reference_role"), QStringLiteral("evaluation_only")},
                                                {QStringLiteral("warnings"), warnings}}},
  };
  const auto metrics = QJsonObject{
      {QStringLiteral("schema"), QStringLiteral("drone_agricole.metrics.v1")},
      {QStringLiteral("run_id"), runId},
      {QStringLiteral("simulation_id"), QStringLiteral("vineyard_mapping")},
      {QStringLiteral("status"), QStringLiteral("partial")},
      {QStringLiteral("summary"), summary},
      {QStringLiteral("groups"),
       QJsonObject{{QStringLiteral("geometry"), QJsonObject{{QStringLiteral("orientation_deg"), bestAngleDegrees},
                                                             {QStringLiteral("active_cells"), static_cast<double>(active.size())},
                                                             {QStringLiteral("vegetation_points"), static_cast<double>(vegetationPointCount)}}},
                   {QStringLiteral("quality_gates"), QJsonObject{{QStringLiteral("horizontal_crs"), referenceAvailable ? QStringLiteral("warning") : QStringLiteral("not_evaluated")},
                                                                  {QStringLiteral("vertical_datum"), QStringLiteral("unknown")},
                                                                  {QStringLiteral("reference_isolation"), QStringLiteral("pass")},
                                                                  {QStringLiteral("flight_authorized"), false}}}}},
      {QStringLiteral("source"), QJsonObject{{QStringLiteral("adapter"), QStringLiteral("vineyard_mapping_cpp17_v1")}}},
  };
  const auto artifacts = QJsonObject{
      {QStringLiteral("schema"), QStringLiteral("drone_agricole.artifacts.v1")},
      {QStringLiteral("run_id"), runId},
      {QStringLiteral("items"), QJsonArray{QJsonObject{{QStringLiteral("artifact_id"), QStringLiteral("map_prediction")},
                                                        {QStringLiteral("kind"), QStringLiteral("map")},
                                                        {QStringLiteral("label"), QStringLiteral("Prédiction cartographique figée")},
                                                        {QStringLiteral("path"), QStringLiteral("map_prediction.json")},
                                                        {QStringLiteral("media_type"), QStringLiteral("application/json")},
                                                        {QStringLiteral("role"), QStringLiteral("result")},
                                                        {QStringLiteral("replayable"), false}},
                                             QJsonObject{{QStringLiteral("artifact_id"), QStringLiteral("map_replay")},
                                                        {QStringLiteral("kind"), QStringLiteral("map")},
                                                        {QStringLiteral("label"), QStringLiteral("Carte des rangs et trajectoires candidates")},
                                                        {QStringLiteral("path"), QStringLiteral("map_replay.json")},
                                                        {QStringLiteral("media_type"), QStringLiteral("application/json")},
                                                        {QStringLiteral("role"), QStringLiteral("visualization")},
                                                        {QStringLiteral("replayable"), true}}}},
  };
  const auto elapsed = timer.elapsed() / 1000.0;
  const auto events = QJsonArray{
      event(runId, 0, 0.0, QStringLiteral("mapping_started"), QStringLiteral("info"), QStringLiteral("running"),
            QStringLiteral("Analyse cartographique EscaYard démarrée.")),
      event(runId, 1, elapsed * 0.30, QStringLiteral("terrain_estimated"), QStringLiteral("info"), QStringLiteral("running"),
            QStringLiteral("Approximation locale du terrain calculée.")),
      event(runId, 2, elapsed * 0.65, QStringLiteral("rows_detected"), QStringLiteral("warning"), QStringLiteral("analyzing"),
            QStringLiteral("Prédiction figée avant ouverture de la référence RTK."),
            QJsonObject{{QStringLiteral("row_count"), static_cast<double>(rows.size())},
                        {QStringLiteral("prediction_content_sha256"), predictionSha256}}),
      event(runId, 3, elapsed * 0.82, QStringLiteral("reference_evaluated"),
            referenceAvailable ? QStringLiteral("warning") : QStringLiteral("info"), QStringLiteral("analyzing"),
            referenceAvailable ? QStringLiteral("Référence RTK évaluée après gel de la prédiction.")
                               : QStringLiteral("Évaluation RTK ignorée : référence indisponible.")),
      event(runId, 4, elapsed, QStringLiteral("mapping_completed"), QStringLiteral("warning"), QStringLiteral("completed"),
            QStringLiteral("Carte produite avec avertissements de géoréférencement."),
            QJsonObject{{QStringLiteral("candidate_trajectory_count"), candidateTrajectoryCount},
                        {QStringLiteral("mapping_safe"), false}}),
  };
  const NormalizedResult normalized{QStringLiteral("t0_native"), resultDirectory, manifest, metrics, artifacts, events};
  writeNativeContracts(normalized, request);
  progress(QStringLiteral("complete"), 100);
  return QJsonObject{{QStringLiteral("run_id"), runId},
                     {QStringLiteral("result_directory"), QFileInfo(resultDirectory).absoluteFilePath()},
                     {QStringLiteral("detected_rows"), static_cast<double>(rows.size())},
                     {QStringLiteral("candidate_trajectories"), candidateTrajectoryCount},
                     {QStringLiteral("prediction_content_sha256"), predictionSha256},
                     {QStringLiteral("mapping_safe"), false}};
}

ReplayData readVineyardMapReplay(const QString& path, const QString& resultId) {
  const auto object = readJsonObject(path);
  requireSchema(object, QStringLiteral("drone_agricole.map_replay.v1"), QStringLiteral("MapReplay"));
  ReplayData replay;
  replay.resultId = resultId;
  replay.domain = QStringLiteral("mapping");
  replay.reconstructionPartial = object.value(QStringLiteral("metadata")).toObject()
      .value(QStringLiteral("reconstruction_status")).toString() == QStringLiteral("partial");
  if (object.contains(QStringLiteral("surface"))) {
    if (!object.value(QStringLiteral("surface")).isObject()) throw ContractError(QStringLiteral("Surface invalide"));
    const auto surface = object.value(QStringLiteral("surface")).toObject();
    replay.surfaceVertices = pointsFromJson(surface.value(QStringLiteral("vertices")),100000,QStringLiteral("sommets de surface"));
    if (!surface.value(QStringLiteral("triangles")).isArray()) throw ContractError(QStringLiteral("Faces de surface absentes"));
    const auto faces = surface.value(QStringLiteral("triangles")).toArray();
    if (faces.size()>150000) throw ContractError(QStringLiteral("Trop de faces de surface"));
    for (const auto& face : faces) {
      const auto indices=face.toArray();
      if(indices.size()!=3)throw ContractError(QStringLiteral("Face triangulaire attendue"));
      std::array<int,3> triangle;
      for(int i=0;i<3;++i) {
        const double index=indices[i].toDouble(-1);
        if(!indices[i].isDouble()||index<0||index>=replay.surfaceVertices.size()||std::floor(index)!=index)
          throw ContractError(QStringLiteral("Indice de surface invalide"));
        triangle[i]=static_cast<int>(index);
      }
      if(triangle[0]==triangle[1]||triangle[1]==triangle[2]||triangle[0]==triangle[2])
        throw ContractError(QStringLiteral("Face dégénérée"));
      replay.surfaceTriangles.append(triangle);
    }
    if(surface.contains(QStringLiteral("colors"))) {
      const auto colors=surface.value(QStringLiteral("colors")).toArray();
      if(!surface.value(QStringLiteral("colors")).isArray()||colors.size()!=replay.surfaceVertices.size())
        throw ContractError(QStringLiteral("Couleurs de surface non alignées"));
      for(const auto& value:colors){const auto rgb=value.toArray();
        if(rgb.size()!=3)throw ContractError(QStringLiteral("Couleur de surface invalide"));
        for(const auto& channel:rgb)if(!channel.isDouble()||channel.toDouble()<0||channel.toDouble()>255||std::floor(channel.toDouble())!=channel.toDouble())
          throw ContractError(QStringLiteral("Canal de surface invalide"));
        replay.surfaceColors.append(QColor(rgb[0].toInt(),rgb[1].toInt(),rgb[2].toInt()));
      }
    }
  }
  replay.mapPoints = pointsFromJson(object.value(QStringLiteral("point_cloud")), 100000,
                                   QStringLiteral("nuage de visualisation"));
  replay.cameraProjectedPoints = pointsFromJson(object.value(QStringLiteral("camera_projected_points")), 100000,
                                                QStringLiteral("points LiDAR projetés dans la caméra"));
  if (object.contains(QStringLiteral("camera_point_colors")) && !object.value(QStringLiteral("camera_point_colors")).isArray())
    throw ContractError(QStringLiteral("Tableau de couleurs attendu"));
  const auto colors = object.value(QStringLiteral("camera_point_colors")).toArray();
  if (!colors.isEmpty() && colors.size() != replay.cameraProjectedPoints.size())
    throw ContractError(QStringLiteral("Nombre de couleurs différent du nombre de points caméra"));
  for (const auto& value : colors) {
    const auto color = value.toArray();
    if (color.size() != 3) throw ContractError(QStringLiteral("Triplet RGB attendu"));
    for (const auto& channel : color) {
      if (!channel.isDouble() || channel.toDouble() < 0 || channel.toDouble() > 255 ||
          std::floor(channel.toDouble()) != channel.toDouble())
        throw ContractError(QStringLiteral("Canal RGB invalide"));
    }
    replay.cameraPointColors.append(QColor(color[0].toInt(), color[1].toInt(), color[2].toInt()));
  }
  replay.referencePoints = pointsFromJson(object.value(QStringLiteral("reference_points")), 10000,
                                         QStringLiteral("références RTK"));
  const auto lines = object.value(QStringLiteral("polylines")).toArray();
  if (lines.size() > 512) {
    throw ContractError(QStringLiteral("Trop de polylignes dans la carte"));
  }
  for (const auto& value : lines) {
    const auto line = value.toObject();
    const auto label = line.value(QStringLiteral("label")).toString();
    const auto role = line.value(QStringLiteral("role")).toString();
    if (label.isEmpty() || role.isEmpty()) {
      throw ContractError(QStringLiteral("Polyligne cartographique sans rôle ou libellé"));
    }
    replay.mapPolylines.append({label, role, pointsFromJson(line.value(QStringLiteral("points")), 10000, label)});
  }
  for (const auto& warning : object.value(QStringLiteral("warnings")).toArray()) {
    if (!warning.toString().isEmpty()) {
      replay.notes.append(warning.toString());
    }
  }
  return replay;
}

}  // namespace drone_agricole::core
