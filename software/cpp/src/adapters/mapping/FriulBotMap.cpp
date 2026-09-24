#include "drone_agricole/algorithms/RowDetection.hpp"
#include "drone_agricole/algorithms/CameraColorFusion.hpp"
#include "drone_agricole/adapters/FriulBotSensors.hpp"
#include "drone_agricole/core/FriulBotMap.hpp"

#include "drone_agricole/core/JsonUtils.hpp"
#include "drone_agricole/core/ResultAdapter.hpp"
#include "drone_agricole/core/Ros1Bag.hpp"
#include "drone_agricole/core/Ros1Messages.hpp"

#include <QCryptographicHash>
#include <QDateTime>
#include <QDir>
#include <QDirIterator>
#include <QElapsedTimer>
#include <QFile>
#include <QFileInfo>
#include <QJsonArray>
#include <QJsonDocument>
#include <QMap>
#include <QRegularExpression>
#include <QTextStream>
#include <QVector3D>

#include <tiffio.h>
#include <yaml-cpp/yaml.h>

#include <algorithm>
#include <array>
#include <cmath>
#include <limits>
#include <numeric>
#include <vector>

namespace drone_agricole::core {
namespace {

constexpr double pi = 3.14159265358979323846;
const QString kLidarTopic = QStringLiteral("velodyne_points");
const QString kImuTopic = QStringLiteral("imu/data");
const QString kCaptureTopic = QStringLiteral("micasense_capture_lidar_points");
const QString kRtkTopic = QStringLiteral("ublox_position_receiver/fix");
const QString kWheelTopic = QStringLiteral("odom");
const QString kSlamTopic = QStringLiteral("map_base_link/odometry");



struct CameraModel {
  QString band;
  double focalPixels{0.0};
  double principalX{0.0};
  double principalY{0.0};
  std::array<double, 5> distortion{};
  std::array<double, 3> translation{};
  std::array<double, 4> quaternion{};
};

struct GrayTiff {
  quint32 width{0};
  quint32 height{0};
  std::vector<quint16> pixels;
};

struct FusionStatistics {
  int lidarPoints{0};
  int projectedBothBands{0};
  int validContrastPoints{0};
  double meanContrast{0.0};
  double medianContrast{0.0};
  double positiveContrastPercent{0.0};
  QList<QVector3D> cameraVisiblePoints;
};

double percentile(std::vector<double> values, double ratio);

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

void requireRange(const double value, const double minimum, const double maximum, const QString& key) {
  if (!std::isfinite(value) || value < minimum || value > maximum) {
    throw ContractError(QStringLiteral("Paramètre %1 hors de l'intervalle autorisé [%2, %3]")
                            .arg(key)
                            .arg(minimum)
                            .arg(maximum));
  }
}

QJsonArray pointArray(const QList<QVector3D>& points) {
  QJsonArray result;
  for (const auto& point : points) {
    result.append(QJsonArray{point.x(), point.y(), point.z()});
  }
  return result;
}

QJsonObject metric(const QString& id,
                   const QString& label,
                   const QJsonValue& value,
                   const QString& unit,
                   const QString& direction,
                   const QString& status) {
  return {{QStringLiteral("metric_id"), id},
          {QStringLiteral("label"), label},
          {QStringLiteral("value"), value},
          {QStringLiteral("unit"), unit},
          {QStringLiteral("direction"), direction},
          {QStringLiteral("status"), status},
          {QStringLiteral("metadata"),
           QJsonObject{{QStringLiteral("preliminary"), true},
                       {QStringLiteral("reason"), QStringLiteral("single_trigger_capture_parameters_to_validate")}}}};
}

QJsonObject event(const QString& runId,
                  const int sequence,
                  const double elapsed,
                  const QString& type,
                  const QString& state,
                  const QString& message) {
  return {{QStringLiteral("schema"), QStringLiteral("drone_agricole.event.v1")},
          {QStringLiteral("run_id"), runId},
          {QStringLiteral("sequence"), sequence},
          {QStringLiteral("elapsed_s"), elapsed},
          {QStringLiteral("event_type"), type},
          {QStringLiteral("severity"), QStringLiteral("warning")},
          {QStringLiteral("state"), state},
          {QStringLiteral("message"), message},
          {QStringLiteral("data"), QJsonObject{}}};
}

void progress(const QString& stage, const int percent) {
  QTextStream(stdout) << "MAP_PROGRESS stage=" << stage << " percent=" << percent << Qt::endl;
}

QStringList imageFiles(const QString& directory) {
  if (directory.isEmpty() || !QFileInfo(directory).isDir()) {
    return {};
  }
  QStringList files;
  QDirIterator iterator(directory,
                        {QStringLiteral("*.tif"), QStringLiteral("*.TIF"), QStringLiteral("*.tiff"),
                         QStringLiteral("*.TIFF")},
                        QDir::Files, QDirIterator::Subdirectories);
  while (iterator.hasNext()) {
    files.append(QFileInfo(iterator.next()).absoluteFilePath());
  }
  std::sort(files.begin(), files.end());
  return files;
}

QList<QStringList> imageCaptureSets(const QString& directory) {
  QMap<QString, QStringList> grouped;
  const QRegularExpression pattern(QStringLiteral("^(.*)_([1-5])\\.(?:tif|tiff)$"),
                                   QRegularExpression::CaseInsensitiveOption);
  for (const auto& path : imageFiles(directory)) {
    const auto info = QFileInfo(path);
    const auto match = pattern.match(info.fileName());
    if (!match.hasMatch()) {
      continue;
    }
    const auto key = QDir(directory).relativeFilePath(info.dir().filePath(match.captured(1)));
    grouped[key].append(path);
  }
  QList<QStringList> result;
  for (auto iterator = grouped.cbegin(); iterator != grouped.cend(); ++iterator) {
    auto files = iterator.value();
    std::sort(files.begin(), files.end());
    if (files.size() == 5) {
      result.append(files);
    }
  }
  return result;
}

QString xmpValue(const QString& text, const QString& tag) {
  const QRegularExpression expression(QStringLiteral("<[^>]*%1>([^<]+)</[^>]*%1>").arg(tag));
  const auto match = expression.match(text);
  return match.hasMatch() ? match.captured(1).trimmed() : QString{};
}

std::vector<double> xmpSequence(const QString& text, const QString& tag) {
  const QRegularExpression blockExpression(
      QStringLiteral("<[^>]*%1>\\s*<rdf:Seq>(.*?)</rdf:Seq>\\s*</[^>]*%1>").arg(tag),
      QRegularExpression::DotMatchesEverythingOption);
  const auto block = blockExpression.match(text);
  if (!block.hasMatch()) {
    return {};
  }
  std::vector<double> result;
  QRegularExpression valueExpression(QStringLiteral("<rdf:li>([^<]+)</rdf:li>"));
  auto iterator = valueExpression.globalMatch(block.captured(1));
  while (iterator.hasNext()) {
    bool ok = false;
    const auto value = iterator.next().captured(1).toDouble(&ok);
    if (ok) {
      result.push_back(value);
    }
  }
  return result;
}

QString readImageText(const QString& path) {
  QFile file(path);
  if (!file.open(QIODevice::ReadOnly)) {
    throw ContractError(QStringLiteral("TIFF MicaSense illisible : %1").arg(path));
  }
  return QString::fromUtf8(file.readAll());
}

CameraModel cameraModel(const QString& imagePath, const QString& calibrationPath, const QString& key) {
  const auto text = readImageText(imagePath);
  const auto principal = xmpValue(text, QStringLiteral("PrincipalPoint")).split(QLatin1Char(','));
  const auto distortion = xmpSequence(text, QStringLiteral("PerspectiveDistortion"));
  bool focalOk = false;
  const auto focalMillimeters = xmpValue(text, QStringLiteral("PerspectiveFocalLength")).toDouble(&focalOk);
  if (principal.size() != 2 || distortion.size() != 5 || !focalOk) {
    throw ContractError(QStringLiteral("Intrinsèques XMP incomplets : %1").arg(imagePath));
  }
  bool principalXOk = false;
  bool principalYOk = false;
  constexpr double pixelSizeMillimeters = 0.00375;
  CameraModel model;
  model.band = xmpValue(text, QStringLiteral("BandName"));
  model.focalPixels = focalMillimeters / pixelSizeMillimeters;
  model.principalX = principal.at(0).trimmed().toDouble(&principalXOk) / pixelSizeMillimeters;
  model.principalY = principal.at(1).trimmed().toDouble(&principalYOk) / pixelSizeMillimeters;
  if (!principalXOk || !principalYOk) {
    throw ContractError(QStringLiteral("Point principal XMP invalide : %1").arg(imagePath));
  }
  std::copy_n(distortion.cbegin(), 5, model.distortion.begin());
  const auto configuration = YAML::LoadFile(calibrationPath.toStdString());
  const auto extrinsic = configuration["extrinsics_from_lidar"][key.toStdString()];
  if (!extrinsic || !extrinsic["translation_m"] || !extrinsic["quaternion_xyzw"] ||
      extrinsic["translation_m"].size() != 3 || extrinsic["quaternion_xyzw"].size() != 4) {
    throw ContractError(QStringLiteral("Extrinsèque LiDAR–caméra absent pour %1").arg(key));
  }
  for (std::size_t index = 0; index < 3; ++index) {
    model.translation[index] = extrinsic["translation_m"][index].as<double>();
  }
  for (std::size_t index = 0; index < 4; ++index) {
    model.quaternion[index] = extrinsic["quaternion_xyzw"][index].as<double>();
  }
  return model;
}

GrayTiff readGrayTiff(const QString& path) {
  auto* tiff = TIFFOpen(QFile::encodeName(path).constData(), "r");
  if (tiff == nullptr) {
    throw ContractError(QStringLiteral("Ouverture libtiff impossible : %1").arg(path));
  }
  GrayTiff image;
  quint16 bits = 0;
  quint16 samples = 0;
  TIFFGetField(tiff, TIFFTAG_IMAGEWIDTH, &image.width);
  TIFFGetField(tiff, TIFFTAG_IMAGELENGTH, &image.height);
  TIFFGetFieldDefaulted(tiff, TIFFTAG_BITSPERSAMPLE, &bits);
  TIFFGetFieldDefaulted(tiff, TIFFTAG_SAMPLESPERPIXEL, &samples);
  if (image.width == 0 || image.height == 0 || bits != 16 || samples != 1) {
    TIFFClose(tiff);
    throw ContractError(QStringLiteral("TIFF MicaSense 16 bits mono attendu : %1").arg(path));
  }
  image.pixels.resize(static_cast<std::size_t>(image.width) * image.height);
  std::vector<quint16> scanline(image.width);
  for (quint32 row = 0; row < image.height; ++row) {
    if (TIFFReadScanline(tiff, scanline.data(), row, 0) < 0) {
      TIFFClose(tiff);
      throw ContractError(QStringLiteral("Lecture TIFF incomplète : %1").arg(path));
    }
    std::copy(scanline.cbegin(), scanline.cend(), image.pixels.begin() + static_cast<std::size_t>(row) * image.width);
  }
  TIFFClose(tiff);
  return image;
}

std::array<double, 3> rotateByQuaternion(const std::array<double, 4>& quaternion,
                                         const std::array<double, 3>& point) {
  auto x = quaternion[0];
  auto y = quaternion[1];
  auto z = quaternion[2];
  auto w = quaternion[3];
  const auto norm = std::sqrt(x * x + y * y + z * z + w * w);
  if (norm <= 0.0) {
    throw ContractError(QStringLiteral("Quaternion extrinsèque nul"));
  }
  x /= norm;
  y /= norm;
  z /= norm;
  w /= norm;
  return {(1.0 - 2.0 * (y * y + z * z)) * point[0] + 2.0 * (x * y - z * w) * point[1] +
              2.0 * (x * z + y * w) * point[2],
          2.0 * (x * y + z * w) * point[0] + (1.0 - 2.0 * (x * x + z * z)) * point[1] +
              2.0 * (y * z - x * w) * point[2],
          2.0 * (x * z - y * w) * point[0] + 2.0 * (y * z + x * w) * point[1] +
              (1.0 - 2.0 * (x * x + y * y)) * point[2]};
}

bool projectPoint(const QVector3D& point,
                  const CameraModel& camera,
                  const quint32 width,
                  const quint32 height,
                  int& pixelX,
                  int& pixelY) {
  auto cameraPoint = rotateByQuaternion(camera.quaternion, {point.x(), point.y(), point.z()});
  for (std::size_t index = 0; index < 3; ++index) {
    cameraPoint[index] += camera.translation[index];
  }
  if (cameraPoint[2] <= 0.05) {
    return false;
  }
  const auto x = cameraPoint[0] / cameraPoint[2];
  const auto y = cameraPoint[1] / cameraPoint[2];
  const auto r2 = x * x + y * y;
  const auto radial = 1.0 + camera.distortion[0] * r2 + camera.distortion[1] * r2 * r2 +
                      camera.distortion[2] * r2 * r2 * r2;
  const auto distortedX = x * radial + 2.0 * camera.distortion[3] * x * y +
                          camera.distortion[4] * (r2 + 2.0 * x * x);
  const auto distortedY = y * radial + camera.distortion[3] * (r2 + 2.0 * y * y) +
                          2.0 * camera.distortion[4] * x * y;
  pixelX = static_cast<int>(std::llround(camera.focalPixels * distortedX + camera.principalX));
  pixelY = static_cast<int>(std::llround(camera.focalPixels * distortedY + camera.principalY));
  return pixelX >= 0 && pixelY >= 0 && pixelX < static_cast<int>(width) && pixelY < static_cast<int>(height);
}

FusionStatistics fuseRedNir(const QList<QVector3D>& points,
                            const QString& redPath,
                            const QString& nirPath,
                            const QString& calibrationPath) {
  const auto red = readGrayTiff(redPath);
  const auto nir = readGrayTiff(nirPath);
  if (red.width != nir.width || red.height != nir.height) {
    throw ContractError(QStringLiteral("Dimensions rouge/NIR incompatibles"));
  }
  const auto redCamera = cameraModel(redPath, calibrationPath, QStringLiteral("red"));
  const auto nirCamera = cameraModel(nirPath, calibrationPath, QStringLiteral("nir"));
  std::vector<double> contrasts;
  int positive = 0;
  FusionStatistics statistics;
  statistics.lidarPoints = points.size();
  for (const auto& point : points) {
    int redX = 0;
    int redY = 0;
    int nirX = 0;
    int nirY = 0;
    if (!projectPoint(point, redCamera, red.width, red.height, redX, redY) ||
        !projectPoint(point, nirCamera, nir.width, nir.height, nirX, nirY)) {
      continue;
    }
    ++statistics.projectedBothBands;
    statistics.cameraVisiblePoints.append(point);
    const auto redValue = static_cast<double>(red.pixels[static_cast<std::size_t>(redY) * red.width + redX]);
    const auto nirValue = static_cast<double>(nir.pixels[static_cast<std::size_t>(nirY) * nir.width + nirX]);
    const auto denominator = nirValue + redValue;
    if (denominator <= 1.0) {
      continue;
    }
    const auto contrast = (nirValue - redValue) / denominator;
    contrasts.push_back(contrast);
    if (contrast > 0.0) {
      ++positive;
    }
  }
  statistics.validContrastPoints = static_cast<int>(contrasts.size());
  if (!contrasts.empty()) {
    statistics.meanContrast = std::accumulate(contrasts.cbegin(), contrasts.cend(), 0.0) / contrasts.size();
    statistics.medianContrast = percentile(contrasts, 0.5);
    statistics.positiveContrastPercent = 100.0 * positive / contrasts.size();
  }
  return statistics;
}

QJsonObject imageInventory(const QString& directory) {
  const auto files = imageFiles(directory);
  QSet<QString> captures;
  QHash<QString, int> bands;
  const QRegularExpression pattern(QStringLiteral("^(.*)_([1-5])\\.(?:tif|tiff)$"),
                                   QRegularExpression::CaseInsensitiveOption);
  for (const auto& path : files) {
    const auto match = pattern.match(QFileInfo(path).fileName());
    if (!match.hasMatch()) {
      continue;
    }
    captures.insert(match.captured(1));
    ++bands[match.captured(2)];
  }
  QJsonObject bandCounts;
  for (auto iterator = bands.cbegin(); iterator != bands.cend(); ++iterator) {
    bandCounts.insert(iterator.key(), iterator.value());
  }
  QJsonArray calibrationByBand;
  QSet<QString> inspectedBands;
  for (const auto& path : files) {
    if (inspectedBands.size() >= 5) {
      break;
    }
    QFile file(path);
    if (!file.open(QIODevice::ReadOnly)) {
      continue;
    }
    const auto text = QString::fromUtf8(file.readAll());
    const auto value = [&](const QString& tag) {
      const QRegularExpression expression(QStringLiteral("<[^>]*%1>([^<]+)</[^>]*%1>").arg(tag));
      const auto match = expression.match(text);
      return match.hasMatch() ? match.captured(1).trimmed() : QString{};
    };
    const auto bandName = value(QStringLiteral("BandName"));
    if (bandName.isEmpty() || inspectedBands.contains(bandName)) {
      continue;
    }
    inspectedBands.insert(bandName);
    calibrationByBand.append(
        QJsonObject{{QStringLiteral("band"), bandName},
                    {QStringLiteral("central_wavelength_nm"), value(QStringLiteral("CentralWavelength")).toDouble()},
                    {QStringLiteral("principal_point_mm"), value(QStringLiteral("PrincipalPoint"))},
                    {QStringLiteral("focal_length_mm"), value(QStringLiteral("PerspectiveFocalLength")).toDouble()},
                    {QStringLiteral("capture_id"), value(QStringLiteral("CaptureId"))},
                    {QStringLiteral("perspective_distortion_embedded"), text.contains(QStringLiteral("PerspectiveDistortion"))},
                    {QStringLiteral("vignetting_embedded"), text.contains(QStringLiteral("VignettingPolynomial"))},
                    {QStringLiteral("radiometric_calibration_embedded"), text.contains(QStringLiteral("RadiometricCalibration"))},
                    {QStringLiteral("dls_irradiance_embedded"), text.contains(QStringLiteral("SpectralIrradiance"))}});
  }
  QJsonObject imageDecode;
  if (!files.isEmpty()) {
    try {
      const auto image = readGrayTiff(files.constFirst());
      imageDecode = {{QStringLiteral("decoder"), QStringLiteral("libtiff")},
                     {QStringLiteral("format"), QStringLiteral("tiff")},
                     {QStringLiteral("readable"), true},
                     {QStringLiteral("width"), static_cast<int>(image.width)},
                     {QStringLiteral("height"), static_cast<int>(image.height)},
                     {QStringLiteral("storage_depth_bits"), 16},
                     {QStringLiteral("sensor_depth_bits"), 12}};
    } catch (const std::exception& error) {
      imageDecode = {{QStringLiteral("decoder"), QStringLiteral("libtiff")},
                     {QStringLiteral("format"), QStringLiteral("tiff")},
                     {QStringLiteral("readable"), false},
                     {QStringLiteral("error"), QString::fromUtf8(error.what())}};
    }
  }
  return {{QStringLiteral("directory"), QFileInfo(directory).absoluteFilePath()},
          {QStringLiteral("tiff_count"), files.size()},
          {QStringLiteral("capture_set_count"), captures.size()},
          {QStringLiteral("band_counts"), bandCounts},
          {QStringLiteral("calibration_by_band"), calibrationByBand},
          {QStringLiteral("image_decode"), imageDecode},
          {QStringLiteral("pairing_rule"), QStringLiteral("capture_order_and_trigger_timestamp")},
          {QStringLiteral("pairing_status"), captures.isEmpty() ? QStringLiteral("to_validate")
                                                                : QStringLiteral("indexed")}};
}

QSet<QString> topicNames(const Ros1Bag& bag) {
  QSet<QString> names;
  for (const auto& connection : bag.connections()) {
    names.insert(connection.topic);
  }
  return names;
}

QJsonArray stringArray(const QStringList& values) {
  QJsonArray result;
  for (const auto& value : values) {
    result.append(value);
  }
  return result;
}

double percentile(std::vector<double> values, const double ratio) {
  if (values.empty()) {
    return std::numeric_limits<double>::quiet_NaN();
  }
  std::sort(values.begin(), values.end());
  return values[static_cast<std::size_t>(std::clamp(ratio, 0.0, 1.0) * (values.size() - 1))];
}

QList<QVector3D> cloudPoints(const Ros1PointCloud2Data& cloud,
                            const double minimumZ,
                            const double maximumZ,
                            const double maximumRange,
                            const int displayBudget) {
  QList<QVector3D> points;
  const auto count = static_cast<qsizetype>(cloud.width) * cloud.height;
  const auto stride = std::max<qsizetype>(1, count / std::max(1, displayBudget));
  points.reserve(std::min<qsizetype>(count, displayBudget));
  for (qsizetype index = 0; index < count; index += stride) {
    const auto x = ros1PointFieldAsDouble(cloud, index, QStringLiteral("x"));
    const auto y = ros1PointFieldAsDouble(cloud, index, QStringLiteral("y"));
    const auto z = ros1PointFieldAsDouble(cloud, index, QStringLiteral("z"));
    if (!std::isfinite(x) || !std::isfinite(y) || !std::isfinite(z) || z < minimumZ || z > maximumZ) {
      continue;
    }
    const auto range = std::hypot(x, y);
    if (range < 0.8 || range > maximumRange) {
      continue;
    }
    points.append(QVector3D(static_cast<float>(x), static_cast<float>(y), static_cast<float>(z)));
  }
  return points;
}

}  // namespace

QJsonObject inspectFriulBot(const QJsonObject& options) {
  const auto bagPath = requiredOption(options, QStringLiteral("bag"));
  const auto imagesPath = options.value(QStringLiteral("images")).toString();
  Ros1Bag bag(bagPath);
  bag.open();
  const auto found = topicNames(bag);
  const QSet<QString> required{kLidarTopic, kImuTopic, kCaptureTopic, kRtkTopic};
  const auto missing = required - found;
  if (!missing.isEmpty()) {
    throw ContractError(QStringLiteral("Topics FriûlBot absents : %1").arg(QStringList(missing.values()).join(QStringLiteral(", "))));
  }
  QSet<QString> compressions;
  for (const auto& chunk : bag.chunks()) {
    compressions.insert(chunk.compression);
  }
  QJsonObject scanDescription;
  QJsonObject captureDescription;
  const auto stop = std::min(bag.endNanoseconds(), bag.startNanoseconds() + 30000000000LL);
  bag.forEachMessage({kLidarTopic, kCaptureTopic}, bag.startNanoseconds(), stop,
                     [&](const Ros1Connection& connection, const Ros1Message& message) {
                       if (connection.topic == kLidarTopic && scanDescription.isEmpty()) {
                         scanDescription = describeRos1PointCloud2(deserializeRos1PointCloud2(message.data));
                       } else if (connection.topic == kCaptureTopic && captureDescription.isEmpty()) {
                         captureDescription = describeRos1PointCloud2(deserializeRos1PointCloud2(message.data));
                         captureDescription.insert(QStringLiteral("timestamp_ns"), static_cast<double>(message.timestampNanoseconds));
                       }
                     });
  QJsonArray compressionValues;
  auto compressionList = compressions.values();
  std::sort(compressionList.begin(), compressionList.end());
  for (const auto& compression : compressionList) {
    compressionValues.append(compression);
  }
  return {{QStringLiteral("schema"), QStringLiteral("drone_agricole.friulbot_inspection.v1")},
          {QStringLiteral("bag"), QFileInfo(bagPath).absoluteFilePath()},
          {QStringLiteral("duration_s"), static_cast<double>(bag.endNanoseconds() - bag.startNanoseconds()) * 1e-9},
          {QStringLiteral("messages"), static_cast<double>(bag.messageCount())},
          {QStringLiteral("chunk_compressions"), compressionValues},
          {QStringLiteral("velodyne_scan"), scanDescription},
          {QStringLiteral("trigger_capture_scan"), captureDescription},
          {QStringLiteral("images"), imageInventory(imagesPath)},
          {QStringLiteral("topic_policy"),
           QJsonObject{{QStringLiteral("perception_inputs"), stringArray({kLidarTopic, kImuTopic, kCaptureTopic})},
                       {QStringLiteral("evaluation_only"), stringArray({kRtkTopic, kWheelTopic, kSlamTopic})},
                       {QStringLiteral("published_indices_allowed_as_input"), false}}}};
}

QList<QStringList> friulBotImageSets(const QString& directory) { return imageCaptureSets(directory); }
algorithms::CameraColorCloud colorFriulBotScan(const QList<QVector3D>& points,
                                              const QStringList& paths,const QString& calibration) {
  std::array<algorithms::CameraBand,3> bands;
  const std::array<QString,3> keys{QStringLiteral("red"),QStringLiteral("green"),QStringLiteral("blue")};
  const std::array<int,3> numbers{3,2,1};
  for(std::size_t b=0;b<3;++b) {
    QString path;
    for(const auto& candidate:paths)
      if(QFileInfo(candidate).completeBaseName().endsWith(QStringLiteral("_%1").arg(numbers[b])))path=candidate;
    if(path.isEmpty())throw ContractError(QStringLiteral("Bande RGB absente"));
    auto image=readGrayTiff(path);
    const auto model=cameraModel(path,calibration,keys[b]);
    bands[b]={static_cast<int>(image.width),static_cast<int>(image.height),std::move(image.pixels),
              {model.focalPixels,model.principalX,model.principalY,model.distortion,model.translation,model.quaternion}};
  }
  return algorithms::fuseCameraRgb(points,bands);
}

QJsonObject runFriulBotCaptureMapping(const QJsonObject& options) {
  const auto requestForMode = readJsonObject(requiredOption(options,QStringLiteral("request")));
  if(requestForMode.value(QStringLiteral("variant_id")).toString()==QStringLiteral("scan_surface_v1"))
    return runFriulBotReconstruction(options);
  QElapsedTimer timer;
  timer.start();
  progress(QStringLiteral("initialization"), 3);
  const auto bagPath = requiredOption(options, QStringLiteral("bag"));
  const auto imagesPath = options.value(QStringLiteral("images")).toString();
  auto calibrationPath = options.value(QStringLiteral("calibration")).toString();
  if (calibrationPath.isEmpty()) {
    calibrationPath = QStringLiteral("configs/datasets/friulbot/test2-2024-07-22.yaml");
  }
  const auto resultDirectory = requiredOption(options, QStringLiteral("run-dir"));
  const auto requestPath = requiredOption(options, QStringLiteral("request"));
  const auto requestedRunId = requiredOption(options, QStringLiteral("run-id"));
  if (QFileInfo::exists(resultDirectory)) {
    throw ContractError(QStringLiteral("Le dossier de résultat existe déjà"));
  }
  const auto request = readJsonObject(requestPath);
  requireSchema(request, QStringLiteral("drone_agricole.run_request.v1"), QStringLiteral("RunRequest"));
  if (request.value(QStringLiteral("simulation_id")).toString() != QStringLiteral("vineyard_capture_mapping") ||
      request.value(QStringLiteral("variant_id")).toString() != QStringLiteral("trigger_rows_v1")) {
    throw ContractError(QStringLiteral("Le runner attend vineyard_capture_mapping/trigger_rows_v1"));
  }
  const auto parameters = request.value(QStringLiteral("parameters")).toObject();
  const auto captureOffset = parameter(parameters, QStringLiteral("capture_offset_s"), 120.0);
  const auto cropMinimumZ = parameter(parameters, QStringLiteral("crop_min_z_m"), -0.50);
  const auto cropMaximumZ = parameter(parameters, QStringLiteral("crop_max_z_m"), 1.80);
  const auto maximumRange = parameter(parameters, QStringLiteral("maximum_range_m"), 20.0);
  const auto rowBin = parameter(parameters, QStringLiteral("row_bin_m"), 0.25);
  const auto minimumSpacing = parameter(parameters, QStringLiteral("row_spacing_min_m"), 1.50);
  const auto peakRatio = parameter(parameters, QStringLiteral("row_peak_ratio"), 0.25);
  const auto trajectoryZ = parameter(parameters, QStringLiteral("trajectory_z_m"), 2.50);
  const auto displayBudget = integerParameter(parameters, QStringLiteral("display_point_budget"), 30000);
  requireRange(captureOffset, 0.0, 1250.0, QStringLiteral("capture_offset_s"));
  requireRange(cropMinimumZ, -2.5, 1.0, QStringLiteral("crop_min_z_m"));
  requireRange(cropMaximumZ, 0.0, 4.0, QStringLiteral("crop_max_z_m"));
  requireRange(maximumRange, 5.0, 100.0, QStringLiteral("maximum_range_m"));
  requireRange(rowBin, 0.10, 1.0, QStringLiteral("row_bin_m"));
  requireRange(minimumSpacing, 0.75, 4.0, QStringLiteral("row_spacing_min_m"));
  requireRange(peakRatio, 0.05, 0.90, QStringLiteral("row_peak_ratio"));
  requireRange(trajectoryZ, 1.0, 6.0, QStringLiteral("trajectory_z_m"));
  requireRange(displayBudget, 2000, 100000, QStringLiteral("display_point_budget"));
  if (cropMaximumZ <= cropMinimumZ) {
    throw ContractError(QStringLiteral("La borne z maximale doit dépasser la borne minimale"));
  }
  const auto runId = safeIdentifier(requestedRunId, QStringLiteral("friulbot_map"));
  const auto startedAt = QDateTime::currentDateTimeUtc().toString(Qt::ISODateWithMs);

  Ros1Bag bag(bagPath);
  bag.open();
  const auto target = bag.startNanoseconds() + static_cast<qint64>(std::llround(captureOffset * 1.0e9));
  const auto start = std::max(bag.startNanoseconds(), target - 3000000000LL);
  const auto stop = std::min(bag.endNanoseconds(), target + 3000000000LL);
  QByteArray selectedMessage;
  qint64 selectedTimestamp = 0;
  auto bestDelta = std::numeric_limits<qint64>::max();
  qsizetype selectedCaptureIndex = -1;
  qsizetype captureIndex = 0;
  bag.forEachMessage({kCaptureTopic}, bag.startNanoseconds(), stop, [&](const Ros1Connection&, const Ros1Message& message) {
    const auto delta = std::abs(message.timestampNanoseconds - target);
    if (message.timestampNanoseconds >= start && delta < bestDelta) {
      bestDelta = delta;
      selectedTimestamp = message.timestampNanoseconds;
      selectedMessage = message.data;
      selectedCaptureIndex = captureIndex;
    }
    ++captureIndex;
  });
  if (selectedMessage.isEmpty()) {
    throw ContractError(QStringLiteral("Aucun déclenchement MicaSense dans la fenêtre demandée"));
  }
  const auto cloud = deserializeRos1PointCloud2(selectedMessage);
  auto points = cloudPoints(cloud, cropMinimumZ, cropMaximumZ, maximumRange, displayBudget);
  const auto scenePoints = cloudPoints(cloud, -maximumRange, maximumRange, maximumRange, displayBudget);
  progress(QStringLiteral("capture"), 38);
  double orientation = 0.0;
  const auto rows = algorithms::detectCaptureRows(points, rowBin, minimumSpacing, peakRatio, orientation);
  progress(QStringLiteral("rows"), 72);

  QList<ReplayData::Polyline> polylines;
  for (qsizetype index = 0; index < rows.size(); ++index) {
    polylines.append({QStringLiteral("Rang local %1").arg(index + 1), QStringLiteral("detected_row"), rows.at(index).points});
  }
  const auto tangentX = std::cos(orientation * pi / 180.0);
  const auto tangentY = std::sin(orientation * pi / 180.0);
  const auto normalX = -tangentY;
  const auto normalY = tangentX;
  int trajectoryCount = 0;
  for (qsizetype index = 1; index < rows.size(); ++index) {
    const auto spacing = rows.at(index).rho - rows.at(index - 1).rho;
    auto minimumT = std::max(rows.at(index - 1).minimumT, rows.at(index).minimumT) + 0.5;
    auto maximumT = std::min(rows.at(index - 1).maximumT, rows.at(index).maximumT) - 0.5;
    if (spacing < minimumSpacing * 0.8 || spacing > 5.0 || maximumT - minimumT < 2.0) {
      continue;
    }
    if (trajectoryCount % 2 != 0) {
      std::swap(minimumT, maximumT);
    }
    const auto rho = 0.5 * (rows.at(index - 1).rho + rows.at(index).rho);
    QList<QVector3D> trajectory;
    const auto segmentCount = std::max(2, static_cast<int>(std::ceil(std::abs(maximumT - minimumT))) + 1);
    for (int segment = 0; segment < segmentCount; ++segment) {
      const auto ratio = static_cast<double>(segment) / (segmentCount - 1);
      const auto t = minimumT + ratio * (maximumT - minimumT);
      trajectory.append(QVector3D(static_cast<float>(tangentX * t + normalX * rho),
                                  static_cast<float>(tangentY * t + normalY * rho),
                                  static_cast<float>(trajectoryZ)));
    }
    ++trajectoryCount;
    polylines.append({QStringLiteral("Trajectoire locale candidate %1").arg(trajectoryCount),
                      QStringLiteral("candidate_trajectory"), trajectory});
  }
  QJsonArray replayPolylines;
  for (const auto& line : polylines) {
    replayPolylines.append(QJsonObject{{QStringLiteral("label"), line.label},
                                       {QStringLiteral("role"), line.role},
                                       {QStringLiteral("points"), pointArray(line.points)}});
  }
  const auto inventory = imageInventory(imagesPath);
  const auto captureSets = imageCaptureSets(imagesPath);
  quint64 triggerCount = 0;
  for (const auto& connection : bag.connections()) {
    if (connection.topic == kCaptureTopic) triggerCount += connection.messageCount;
  }
  const bool pairingComplete = triggerCount == static_cast<quint64>(captureSets.size());
  QJsonArray pairedImages;
  QJsonArray cameraProjectedPoints;
  QJsonArray cameraPointColors;
  QString rgbStatus = QStringLiteral("not_available");
  QString rgbError;
  QJsonObject cameraFusion{{QStringLiteral("status"), QStringLiteral("not_available")},
                           {QStringLiteral("role"), QStringLiteral("diagnostic_not_row_detection_input")},
                           {QStringLiteral("radiometric_correction_applied"), false}};
  if (pairingComplete && selectedCaptureIndex >= 0 && selectedCaptureIndex < captureSets.size()) {
    QString redPath;
    QString nirPath;
    const auto captureImages = captureSets.at(selectedCaptureIndex);
    for (const auto& path : captureImages) {
      pairedImages.append(QDir(imagesPath).relativeFilePath(path));
      const auto name = QFileInfo(path).fileName();
      if (name.contains(QRegularExpression(QStringLiteral("_3\\.(?:tif|tiff)$"),
                                           QRegularExpression::CaseInsensitiveOption))) {
        redPath = path;
      } else if (name.contains(QRegularExpression(QStringLiteral("_4\\.(?:tif|tiff)$"),
                                                  QRegularExpression::CaseInsensitiveOption))) {
        nirPath = path;
      }
    }
    if (!redPath.isEmpty() && !nirPath.isEmpty()) {
      try {
        const auto fusion = fuseRedNir(points, redPath, nirPath, calibrationPath);
        cameraProjectedPoints = pointArray(fusion.cameraVisiblePoints);
        const auto coverage = fusion.lidarPoints > 0
                                  ? 100.0 * static_cast<double>(fusion.projectedBothBands) / fusion.lidarPoints
                                  : 0.0;
        cameraFusion = QJsonObject{
            {QStringLiteral("status"), QStringLiteral("projected")},
            {QStringLiteral("role"), QStringLiteral("diagnostic_not_row_detection_input")},
            {QStringLiteral("lidar_points"), fusion.lidarPoints},
            {QStringLiteral("projected_both_bands"), fusion.projectedBothBands},
            {QStringLiteral("coverage_percent"), coverage},
            {QStringLiteral("valid_raw_contrast_points"), fusion.validContrastPoints},
            {QStringLiteral("mean_raw_nir_red_normalized_difference"), fusion.meanContrast},
            {QStringLiteral("median_raw_nir_red_normalized_difference"), fusion.medianContrast},
            {QStringLiteral("positive_raw_contrast_percent"), fusion.positiveContrastPercent},
            {QStringLiteral("red_image"), QDir(imagesPath).relativeFilePath(redPath)},
            {QStringLiteral("nir_image"), QDir(imagesPath).relativeFilePath(nirPath)},
            {QStringLiteral("pixel_pitch_um"), 3.75},
            {QStringLiteral("transform_interpretation"), QStringLiteral("author_lidar_to_lens_direct")},
            {QStringLiteral("radiometric_correction_applied"), false},
            {QStringLiteral("ndvi_claimed"), false}};
      } catch (const std::exception& error) {
        cameraFusion.insert(QStringLiteral("status"), QStringLiteral("error"));
        cameraFusion.insert(QStringLiteral("error"), QString::fromUtf8(error.what()));
      }
    }
  }
  if (pairingComplete && selectedCaptureIndex >= 0 && selectedCaptureIndex < captureSets.size()) {
    try {
      std::array<algorithms::CameraBand, 3> bands;
      const std::array<QString, 3> keys{QStringLiteral("red"), QStringLiteral("green"), QStringLiteral("blue")};
      const std::array<int, 3> numbers{3, 2, 1};
      const auto paths = captureSets.at(selectedCaptureIndex);
      for (std::size_t b = 0; b < bands.size(); ++b) {
        QString path;
        for (const auto& candidate : paths) {
          if (QFileInfo(candidate).completeBaseName().endsWith(QStringLiteral("_%1").arg(numbers[b]))) path = candidate;
        }
        if (path.isEmpty()) throw ContractError(QStringLiteral("Bande visible absente : %1").arg(keys[b]));
        auto image = readGrayTiff(path);
        const auto model = cameraModel(path, calibrationPath, keys[b]);
        bands[b] = {static_cast<int>(image.width), static_cast<int>(image.height), std::move(image.pixels),
                    {model.focalPixels, model.principalX, model.principalY, model.distortion,
                     model.translation, model.quaternion}};
      }
      const auto colored = algorithms::fuseCameraRgb(scenePoints, bands);
      cameraProjectedPoints = pointArray(colored.points);
      for (const auto& color : colored.colors) cameraPointColors.append(QJsonArray{color.red(), color.green(), color.blue()});
      rgbStatus = colored.points.isEmpty() ? QStringLiteral("no_overlap") : QStringLiteral("projected");
    } catch (const std::exception& error) {
      rgbStatus = QStringLiteral("error");
      rgbError = QString::fromUtf8(error.what());
    }
  }
  cameraFusion.insert(QStringLiteral("rgb_status"), rgbStatus);
  cameraFusion.insert(QStringLiteral("pairing_complete_count"), pairingComplete);
  cameraFusion.insert(QStringLiteral("trigger_count"), static_cast<double>(triggerCount));
  cameraFusion.insert(QStringLiteral("rgb_error"), rgbError);
  cameraFusion.insert(QStringLiteral("rgb_points"), cameraPointColors.size());
  cameraFusion.insert(QStringLiteral("rgb_display"), QStringLiteral("visible_bands_percentile_2_98_sqrt_not_radiometric"));
  cameraFusion.insert(QStringLiteral("rgb_occlusion"), QStringLiteral("nearest_depth_per_pixel_each_band_0.05m_tolerance"));
  const auto pixelProjectionStatus = cameraFusion.value(QStringLiteral("status")).toString();
  const auto prediction = QJsonObject{
      {QStringLiteral("schema"), QStringLiteral("drone_agricole.map_prediction.v1")},
      {QStringLiteral("run_id"), runId},
      {QStringLiteral("domain"), QStringLiteral("mapping")},
      {QStringLiteral("local_origin"), QJsonArray{0.0, 0.0, 0.0}},
      {QStringLiteral("point_cloud"), pointArray(scenePoints)},
      {QStringLiteral("camera_projected_points"), cameraProjectedPoints},
      {QStringLiteral("camera_point_colors"), cameraPointColors},
      {QStringLiteral("polylines"), replayPolylines},
      {QStringLiteral("metadata"),
       QJsonObject{{QStringLiteral("coordinate_frame"), cloud.header.frameId},
                   {QStringLiteral("reconstruction_scope"), QStringLiteral("single_capture_3d_not_global_surface")},
                   {QStringLiteral("capture_timestamp_ns"), static_cast<double>(selectedTimestamp)},
                   {QStringLiteral("capture_index"), static_cast<double>(selectedCaptureIndex)},
                   {QStringLiteral("orientation_deg"), orientation},
                   {QStringLiteral("geometry_detection_inputs"), stringArray({kCaptureTopic})},
                   {QStringLiteral("associated_modalities"),
                    stringArray({QStringLiteral("raw_multispectral_tiff"), QStringLiteral("lidar_camera_extrinsics")})},
                   {QStringLiteral("perception_inputs"),
                    stringArray({kCaptureTopic, QStringLiteral("raw_multispectral_tiff"),
                                 QStringLiteral("lidar_camera_extrinsics")})},
                   {QStringLiteral("excluded_topics"), stringArray({kRtkTopic, kWheelTopic, kSlamTopic})},
                   {QStringLiteral("temporal_fusion"), QStringLiteral("hardware_trigger_topic")},
                   {QStringLiteral("pixel_projection"), pixelProjectionStatus},
                   {QStringLiteral("camera_fusion"), cameraFusion},
                   {QStringLiteral("paired_multispectral_images"), pairedImages},
                   {QStringLiteral("image_inventory"), inventory}}}};
  QDir().mkpath(resultDirectory);
  writeJsonObjectAtomically(QDir(resultDirectory).filePath(QStringLiteral("map_prediction.json")), prediction);
  auto canonical = prediction;
  canonical.remove(QStringLiteral("run_id"));
  const auto predictionHash = QString::fromLatin1(
      QCryptographicHash::hash(QJsonDocument(canonical).toJson(QJsonDocument::Compact), QCryptographicHash::Sha256).toHex());
  QJsonArray warnings{
      QStringLiteral("Détection locale sur un seul scan déclenché ; l'accumulation LIO reste à qualifier."),
      QStringLiteral("Couleurs visibles RGB à contraste étiré ; ni texture de surface, ni couleur radiométriquement calibrée. Calibration : À valider."),
      QStringLiteral("Projection rouge/NIR diagnostique depuis les XMP ; convention extrinsèque et correction radiométrique : À valider."),
      QStringLiteral("Seuils de végétation, axes et trajectoires locales : À valider."),
      QStringLiteral("Les trajectoires sont des candidats hors ligne, jamais des ordres envoyés à PX4.")};
  if (rgbStatus != QStringLiteral("projected"))
    warnings.append(QStringLiteral("Couleurs RGB indisponibles : %1 %2").arg(rgbStatus, rgbError));
  if (!pairingComplete)
    warnings.append(QStringLiteral("Nombre de captures TIFF différent du nombre de déclenchements : appariement caméra refusé."));
  auto replay = prediction;
  replay.insert(QStringLiteral("schema"), QStringLiteral("drone_agricole.map_replay.v1"));
  replay.insert(QStringLiteral("reference_points"), QJsonArray{});
  replay.insert(QStringLiteral("warnings"), warnings);
  auto replayMetadata = replay.value(QStringLiteral("metadata")).toObject();
  replayMetadata.insert(QStringLiteral("prediction_content_sha256"), predictionHash);
  replayMetadata.insert(QStringLiteral("reference_role"), QStringLiteral("not_loaded_by_prediction_runner"));
  replayMetadata.insert(QStringLiteral("reference_isolation"), QStringLiteral("pass_by_topic_allowlist"));
  replay.insert(QStringLiteral("metadata"), replayMetadata);
  writeJsonObjectAtomically(QDir(resultDirectory).filePath(QStringLiteral("map_replay.json")), replay);

  const auto finishedAt = QDateTime::currentDateTimeUtc().toString(Qt::ISODateWithMs);
  QJsonArray summary{
      metric(QStringLiteral("rgb_colored_points"), QStringLiteral("Points colorés par la caméra RGB"), cameraPointColors.size(),
             QStringLiteral("point"), QStringLiteral("neutral"), QStringLiteral("warning")),
      metric(QStringLiteral("scene_points"), QStringLiteral("Points de la scène 3D, sol compris"), scenePoints.size(),
             QStringLiteral("point"), QStringLiteral("neutral"), QStringLiteral("good")),
      metric(QStringLiteral("local_row_count"), QStringLiteral("Rangs locaux détectés"), rows.size(), QStringLiteral("rang"),
             QStringLiteral("neutral"), QStringLiteral("warning")),
      metric(QStringLiteral("local_candidate_trajectory_count"), QStringLiteral("Trajectoires locales candidates"),
             trajectoryCount, QStringLiteral("trajectoire"), QStringLiteral("neutral"), QStringLiteral("warning")),
      metric(QStringLiteral("processed_capture_points"), QStringLiteral("Points du scan filtré"), points.size(),
             QStringLiteral("point"), QStringLiteral("neutral"), QStringLiteral("good")),
      metric(QStringLiteral("indexed_multispectral_sets"), QStringLiteral("Captures multispectrales indexées"),
             inventory.value(QStringLiteral("capture_set_count")), QStringLiteral("capture"),
             QStringLiteral("neutral"), QStringLiteral("warning"))};
  if (pixelProjectionStatus == QStringLiteral("projected")) {
    summary.append(metric(QStringLiteral("lidar_camera_projection_coverage"),
                          QStringLiteral("Points LiDAR projetés dans rouge et NIR"),
                          cameraFusion.value(QStringLiteral("coverage_percent")), QStringLiteral("%"),
                          QStringLiteral("higher_is_better"), QStringLiteral("warning")));
  }
  const auto manifest = QJsonObject{
      {QStringLiteral("schema"), QStringLiteral("drone_agricole.run_manifest.v1")},
      {QStringLiteral("run_id"), runId},
      {QStringLiteral("request_id"), request.value(QStringLiteral("request_id"))},
      {QStringLiteral("simulation_id"), QStringLiteral("vineyard_capture_mapping")},
      {QStringLiteral("variant_id"), QStringLiteral("trigger_rows_v1")},
      {QStringLiteral("runner_id"), QStringLiteral("friulbot_capture_rows")},
      {QStringLiteral("domain"), QStringLiteral("mapping")},
      {QStringLiteral("state"), QStringLiteral("completed")},
      {QStringLiteral("created_at_utc"), startedAt},
      {QStringLiteral("started_at_utc"), startedAt},
      {QStringLiteral("finished_at_utc"), finishedAt},
      {QStringLiteral("inputs"), request.value(QStringLiteral("inputs")).toArray()},
      {QStringLiteral("parameters"), parameters},
      {QStringLiteral("software"), QJsonObject{{QStringLiteral("implementation"), QStringLiteral("cpp17_friulbot_trigger_rows_v2")}}},
      {QStringLiteral("files"), QJsonObject{{QStringLiteral("map_prediction"), QStringLiteral("map_prediction.json")},
                                             {QStringLiteral("map_replay"), QStringLiteral("map_replay.json")}}},
      {QStringLiteral("compatibility"), QJsonObject{{QStringLiteral("comparison_group"), QStringLiteral("vineyard_local_rows_v1")},
                                                      {QStringLiteral("result_contract_version"), 1}}},
      {QStringLiteral("metadata"), QJsonObject{{QStringLiteral("tags"), QJsonArray{QStringLiteral("friulbot"),
                                                                                     QStringLiteral("lidar_camera"),
                                                                                     QStringLiteral("preliminary")}},
                                                {QStringLiteral("mapping_safe"), false},
                                                {QStringLiteral("prediction_content_sha256"), predictionHash},
                                                {QStringLiteral("reference_isolation"), QStringLiteral("pass")},
                                                {QStringLiteral("warnings"), warnings}}}};
  const auto metrics = QJsonObject{
      {QStringLiteral("schema"), QStringLiteral("drone_agricole.metrics.v1")},
      {QStringLiteral("run_id"), runId},
      {QStringLiteral("simulation_id"), QStringLiteral("vineyard_capture_mapping")},
      {QStringLiteral("status"), QStringLiteral("partial")},
      {QStringLiteral("summary"), summary},
      {QStringLiteral("groups"),
       QJsonObject{{QStringLiteral("geometry"), QJsonObject{{QStringLiteral("orientation_deg"), orientation},
                                                              {QStringLiteral("capture_timestamp_ns"), static_cast<double>(selectedTimestamp)}}},
                   {QStringLiteral("quality_gates"), QJsonObject{{QStringLiteral("reference_isolation"), QStringLiteral("pass")},
                                                                   {QStringLiteral("pixel_projection"), pixelProjectionStatus},
                                                                   {QStringLiteral("global_mapping"), QStringLiteral("not_evaluated")},
                                                                   {QStringLiteral("flight_authorized"), false}}}}},
      {QStringLiteral("source"), QJsonObject{{QStringLiteral("adapter"), QStringLiteral("friulbot_cpp17_v2")}}}};
  const auto artifacts = QJsonObject{
      {QStringLiteral("schema"), QStringLiteral("drone_agricole.artifacts.v1")},
      {QStringLiteral("run_id"), runId},
      {QStringLiteral("items"), QJsonArray{QJsonObject{{QStringLiteral("artifact_id"), QStringLiteral("map_prediction")},
                                                        {QStringLiteral("kind"), QStringLiteral("map")},
                                                        {QStringLiteral("label"), QStringLiteral("Prédiction locale figée")},
                                                        {QStringLiteral("path"), QStringLiteral("map_prediction.json")},
                                                        {QStringLiteral("media_type"), QStringLiteral("application/json")},
                                                        {QStringLiteral("role"), QStringLiteral("result")},
                                                        {QStringLiteral("replayable"), false}},
                                             QJsonObject{{QStringLiteral("artifact_id"), QStringLiteral("map_replay")},
                                                        {QStringLiteral("kind"), QStringLiteral("map")},
                                                        {QStringLiteral("label"), QStringLiteral("Scan synchronisé et trajectoires locales")},
                                                        {QStringLiteral("path"), QStringLiteral("map_replay.json")},
                                                        {QStringLiteral("media_type"), QStringLiteral("application/json")},
                                                        {QStringLiteral("role"), QStringLiteral("visualization")},
                                                        {QStringLiteral("replayable"), true}}}}};
  const auto elapsed = timer.elapsed() / 1000.0;
  const auto events = QJsonArray{
      event(runId, 0, 0.0, QStringLiteral("mapping_started"), QStringLiteral("running"),
            QStringLiteral("Analyse du déclenchement LiDAR–MicaSense démarrée.")),
      event(runId, 1, elapsed * 0.45, QStringLiteral("capture_selected"), QStringLiteral("running"),
            QStringLiteral("Scan associé au déclenchement caméra sélectionné par allowlist.")),
      event(runId, 2, elapsed * 0.80, QStringLiteral("rows_detected"), QStringLiteral("analyzing"),
            QStringLiteral("Rangs locaux et trajectoires candidates calculés sans ouvrir les références.")),
      event(runId, 3, elapsed, QStringLiteral("mapping_completed"), QStringLiteral("completed"),
            QStringLiteral("Carte locale et association caméra diagnostique produites ; carte globale à valider."))};
  writeNativeContracts(NormalizedResult{QStringLiteral("t0_native"), resultDirectory, manifest, metrics, artifacts, events}, request);
  progress(QStringLiteral("complete"), 100);
  return {{QStringLiteral("run_id"), runId},
          {QStringLiteral("result_directory"), QFileInfo(resultDirectory).absoluteFilePath()},
          {QStringLiteral("detected_rows"), rows.size()},
          {QStringLiteral("candidate_trajectories"), trajectoryCount},
          {QStringLiteral("camera_projection_status"), pixelProjectionStatus},
          {QStringLiteral("camera_projection_coverage_percent"),
           cameraFusion.value(QStringLiteral("coverage_percent"))},
          {QStringLiteral("prediction_content_sha256"), predictionHash},
          {QStringLiteral("mapping_safe"), false}};
}

}  // namespace drone_agricole::core
