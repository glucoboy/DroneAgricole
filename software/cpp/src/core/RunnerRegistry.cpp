#include "drone_agricole/core/RunnerRegistry.hpp"

#include "drone_agricole/core/JsonUtils.hpp"

#include <QDir>
#include <QCoreApplication>
#include <QFile>
#include <QFileInfo>
#include <QJsonDocument>
#include <QSaveFile>
#include <QUuid>

#include <yaml-cpp/yaml.h>

#include <array>
#include <cmath>
#include <fstream>

namespace drone_agricole::core {
namespace {

const QHash<QString, QString> lioServices{
    {QStringLiteral("fast_lio2"), QStringLiteral("fast-lio2")},
    {QStringLiteral("point_lio"), QStringLiteral("point-lio")},
    {QStringLiteral("lio_sam"), QStringLiteral("lio-sam")},
};

QString projectToolsProgram() {
  auto name = QStringLiteral("drone-agricole-tools");
#ifdef Q_OS_WIN
  name += QStringLiteral(".exe");
#endif
  return QDir(QCoreApplication::applicationDirPath()).filePath(name);
}

QString projectPx4ClientProgram() {
  auto name = QStringLiteral("drone-agricole-px4-client");
#ifdef Q_OS_WIN
  name += QStringLiteral(".exe");
#endif
  return QDir(QCoreApplication::applicationDirPath()).filePath(name);
}

bool isFloatingScalar(const YAML::Node& node) {
  if (!node.IsScalar()) {
    return false;
  }
  const auto scalar = QString::fromStdString(node.Scalar());
  return scalar.contains(QLatin1Char('.')) || scalar.contains(QLatin1Char('e'), Qt::CaseInsensitive);
}

YAML::Node jsonToYaml(const QJsonValue& value, const YAML::Node& original) {
  if (value.isBool()) {
    return YAML::Node(value.toBool());
  }
  if (value.isDouble()) {
    const auto number = value.toDouble();
    if (std::floor(number) == number && !isFloatingScalar(original)) {
      return YAML::Node(static_cast<long long>(number));
    }
    if (std::floor(number) == number) {
      YAML::Node floating(QString::number(number, 'f', 1).toStdString());
      floating.SetTag("tag:yaml.org,2002:float");
      return floating;
    }
    return YAML::Node(number);
  }
  return YAML::Node(value.toString().toStdString());
}

QString yamlPathText(const std::vector<std::string>& path, const std::size_t lastIndex) {
  QStringList segments;
  for (std::size_t index = 0; index <= lastIndex && index < path.size(); ++index) {
    segments.append(QString::fromStdString(path[index]));
  }
  return segments.join(QLatin1Char('.'));
}

void setPathNode(YAML::Node node,
                 const std::vector<std::string>& path,
                 const std::size_t index,
                 const QJsonValue& value) {
  if (!node.IsMap() || index >= path.size()) {
    throw ContractError(QStringLiteral("Structure YAML LIO invalide au chemin '%1'")
                            .arg(path.empty() ? QStringLiteral("<racine>") : yamlPathText(path, index)));
  }
  const YAML::Node& readable = node;
  const auto child = readable[path[index]];
  if (!child.IsDefined()) {
    throw ContractError(QStringLiteral("Configuration LIO incompatible : clé '%1' absente")
                            .arg(yamlPathText(path, index)));
  }
  if (index + 1 == path.size()) {
    node[path[index]] = jsonToYaml(value, child);
    return;
  }
  if (!child.IsMap()) {
    throw ContractError(QStringLiteral("Configuration LIO incompatible : section '%1' non structurée")
                            .arg(yamlPathText(path, index)));
  }
  setPathNode(child, path, index + 1, value);
}

void setPath(YAML::Node root, const std::vector<std::string>& path, const QJsonValue& value) {
  if (path.empty()) {
    throw ContractError(QStringLiteral("Chemin de paramètre LIO vide"));
  }
  setPathNode(root, path, 0, value);
}

const QHash<QString, std::vector<std::string>> fastLioPaths{
    {QStringLiteral("filter_size_surf"), {"/**", "ros__parameters", "filter_size_surf"}},
    {QStringLiteral("filter_size_map"), {"/**", "ros__parameters", "filter_size_map"}},
    {QStringLiteral("point_filter_num"), {"/**", "ros__parameters", "point_filter_num"}},
    {QStringLiteral("max_iteration"), {"/**", "ros__parameters", "max_iteration"}},
    {QStringLiteral("blind"), {"/**", "ros__parameters", "preprocess", "blind"}},
    {QStringLiteral("det_range"), {"/**", "ros__parameters", "mapping", "det_range"}},
};

const QHash<QString, std::vector<std::string>> pointLioPaths{
    {QStringLiteral("filter_size_surf"), {"/**", "ros__parameters", "filter_size_surf"}},
    {QStringLiteral("filter_size_map"), {"/**", "ros__parameters", "filter_size_map"}},
    {QStringLiteral("point_filter_num"), {"/**", "ros__parameters", "point_filter_num"}},
    {QStringLiteral("blind"), {"/**", "ros__parameters", "preprocess", "blind"}},
    {QStringLiteral("det_range"), {"/**", "ros__parameters", "mapping", "det_range"}},
    {QStringLiteral("plane_thr"), {"/**", "ros__parameters", "mapping", "plane_thr"}},
};

const QHash<QString, std::vector<std::string>> lioSamPaths{
    {QStringLiteral("odometry_surf_leaf_size"), {"/**", "ros__parameters", "odometrySurfLeafSize"}},
    {QStringLiteral("mapping_corner_leaf_size"), {"/**", "ros__parameters", "mappingCornerLeafSize"}},
    {QStringLiteral("mapping_surf_leaf_size"), {"/**", "ros__parameters", "mappingSurfLeafSize"}},
    {QStringLiteral("edge_threshold"), {"/**", "ros__parameters", "edgeThreshold"}},
    {QStringLiteral("surf_threshold"), {"/**", "ros__parameters", "surfThreshold"}},
    {QStringLiteral("mapping_process_interval"), {"/**", "ros__parameters", "mappingProcessInterval"}},
};

const QHash<QString, std::vector<std::string>>& parameterPaths(const QString& runnerId) {
  if (runnerId == QStringLiteral("fast_lio2")) {
    return fastLioPaths;
  }
  if (runnerId == QStringLiteral("point_lio")) {
    return pointLioPaths;
  }
  if (runnerId == QStringLiteral("lio_sam")) {
    return lioSamPaths;
  }
  throw ContractError(QStringLiteral("Runner LIO inconnu : %1").arg(runnerId));
}

QJsonObject findProfile(const SimulationDefinition& simulation,
                        const QString& variantId,
                        const QString& datasetId,
                        const QString& sequenceId,
                        const QString& requestedProfile) {
  QList<QJsonObject> compatible;
  for (const auto& value : simulation.profiles) {
    const auto profile = value.toObject();
    const auto selectors = profile.value(QStringLiteral("selectors")).toObject();
    const auto profileDataset = selectors.value(QStringLiteral("dataset_id")).toString();
    if (!profileDataset.isEmpty() && profileDataset != datasetId) {
      continue;
    }
    const auto sequenceIds = selectors.value(QStringLiteral("sequence_ids")).toArray();
    if (!sequenceIds.isEmpty() && !sequenceIds.contains(sequenceId)) {
      continue;
    }
    if (!profile.value(QStringLiteral("variant_settings")).toObject().contains(variantId)) {
      continue;
    }
    if (!requestedProfile.isEmpty() && profile.value(QStringLiteral("profile_id")).toString() != requestedProfile) {
      continue;
    }
    compatible.append(profile);
  }
  if (compatible.isEmpty()) {
    throw ContractError(QStringLiteral("Aucun profil dataset-variante compatible n'est disponible"));
  }
  const auto preferred = std::find_if(compatible.cbegin(), compatible.cend(), [](const auto& profile) {
    return profile.value(QStringLiteral("default")).toBool();
  });
  return preferred == compatible.cend() ? compatible.front() : *preferred;
}

QString resultGroupFor(const DatasetSequence& sequence) {
  const auto source = sequence.sequenceId.section(QLatin1Char('-'), 0, 1);
  return QStringLiteral("%1_%2").arg(sequence.datasetId, source);
}

}  // namespace

RunnerRegistry::RunnerRegistry(const ContractRegistry& contracts) : contracts_(contracts) {}

PreparedRun RunnerRegistry::prepare(const QJsonObject& request, QString runId, QDateTime timestamp) const {
  const auto simulationId = request.value(QStringLiteral("simulation_id")).toString();
  const auto variantId = request.value(QStringLiteral("variant_id")).toString();
  const auto& simulation = contracts_.simulation(simulationId);
  const auto& variant = contracts_.variant(simulationId, variantId);
  if (!approvedRunnerIds().contains(variant.runnerId)) {
    throw ContractError(QStringLiteral("Aucun runner approuvé pour %1").arg(variant.runnerId));
  }
  if (runId.isEmpty()) {
    runId = QUuid::createUuid().toString(QUuid::Id128).left(8);
  }
  const auto stamp = timestamp.toUTC().toString(QStringLiteral("yyyyMMdd'T'HHmmss'Z'"));
  const auto profileId = request.value(QStringLiteral("profile_id")).toString();
  if (simulation.domain == QStringLiteral("localization")) {
    QString datasetId;
    QString sequenceId;
    for (const auto& inputValue : request.value(QStringLiteral("inputs")).toArray()) {
      const auto input = inputValue.toObject();
      if (input.value(QStringLiteral("kind")).toString() == QStringLiteral("dataset_sequence")) {
        const auto reference = input.value(QStringLiteral("reference")).toObject();
        datasetId = reference.value(QStringLiteral("dataset_id")).toString();
        sequenceId = reference.value(QStringLiteral("sequence_id")).toString();
      }
    }
    const auto compatible = contracts_.compatibleSequences(simulationId, variantId);
    const auto selected = std::find_if(compatible.cbegin(), compatible.cend(), [&](const auto& sequence) {
      return sequence.datasetId == datasetId && sequence.sequenceId == sequenceId;
    });
    if (selected == compatible.cend()) {
      throw ContractError(QStringLiteral("Une séquence compatible doit être sélectionnée"));
    }
    return prepareLio(simulation, variant, request, *selected, profileId, runId, stamp);
  }
  if (!request.value(QStringLiteral("inputs")).toArray().isEmpty()) {
    throw ContractError(QStringLiteral("Cette simulation n'accepte pas d'entrée sélectionnable"));
  }
  return preparePx4(simulation, variant, request, runId, stamp);
}

QStringList RunnerRegistry::approvedRunnerIds() const {
  return {QStringLiteral("fast_lio2"), QStringLiteral("point_lio"), QStringLiteral("lio_sam"),
          QStringLiteral("px4_square"), QStringLiteral("px4_failsafe")};
}

PreparedRun RunnerRegistry::prepareLio(const SimulationDefinition& simulation,
                                       const VariantDefinition& variant,
                                       const QJsonObject& request,
                                       const DatasetSequence& sequence,
                                       const QString& profileId,
                                       const QString& runId,
                                       const QString& stamp) const {
  const auto profile = findProfile(simulation, variant.id, sequence.datasetId, sequence.sequenceId, profileId);
  const auto settings = profile.value(QStringLiteral("variant_settings")).toObject().value(variant.id).toObject();
  QJsonObject rosbag;
  for (const auto& value : sequence.resources) {
    const auto resource = value.toObject();
    const auto kind = resource.value(QStringLiteral("kind")).toString();
    if (kind == QStringLiteral("rosbag2") || kind == QStringLiteral("mcap")) {
      if (!rosbag.isEmpty()) {
        throw ContractError(QStringLiteral("La séquence doit fournir exactement un rosbag exécutable"));
      }
      rosbag = resource;
    }
  }
  if (rosbag.isEmpty()) {
    throw ContractError(QStringLiteral("La séquence doit fournir exactement un rosbag exécutable"));
  }
  const auto bagRelative = rosbag.value(QStringLiteral("uri")).toString();
  const auto bagPath = safeWorkspacePath(contracts_.workspace(), bagRelative, QStringLiteral("Dataset"));
  const auto configRelative = settings.value(QStringLiteral("base_config_uri")).toString();
  const auto configPath = safeWorkspacePath(contracts_.workspace(), configRelative, QStringLiteral("Configuration"));
  if (!QFileInfo(bagPath).isDir() || !QFileInfo(configPath).isFile()) {
    throw ContractError(QStringLiteral("Dataset ou configuration LIO absent"));
  }
  const auto resultRelative = QStringLiteral("results/benchmarks/%1/%2/dashboard_%3_%4")
                                  .arg(variant.id, resultGroupFor(sequence), stamp, runId);
  const auto resultDirectory = safeWorkspacePath(contracts_.workspace(), resultRelative, QStringLiteral("Résultat"));
  const auto runtimeRelative = QStringLiteral(".runtime/dashboard/%1.yaml").arg(runId);
  const auto runtimePath = safeWorkspacePath(contracts_.workspace(), runtimeRelative, QStringLiteral("Configuration temporaire"));
  writeLioConfig(variant.runnerId, configPath, runtimePath, request.value(QStringLiteral("parameters")).toObject());
  const auto playbackRate = scalarText(
      request.value(QStringLiteral("parameters")).toObject().value(QStringLiteral("playback_rate")));
  auto program = projectToolsProgram();
  auto arguments = QStringList{QStringLiteral("lio-run"), QStringLiteral("--algorithm"), variant.runnerId,
                               QStringLiteral("--bag"), bagRelative, QStringLiteral("--run-dir"), resultRelative,
                               QStringLiteral("--config"), runtimeRelative, QStringLiteral("--playback-rate"),
                               playbackRate};
  QString stopProgram;
  QStringList stopArguments;
#ifdef Q_OS_WIN
  const auto containerName = QStringLiteral("drone-agricole-run-%1").arg(runId);
  program = QStringLiteral("docker");
  arguments = {QStringLiteral("compose"), QStringLiteral("--profile"), QStringLiteral("lio"), QStringLiteral("run"),
               QStringLiteral("--rm"), QStringLiteral("--name"), containerName, lioServices.value(variant.runnerId),
               QStringLiteral("drone-agricole-tools"), QStringLiteral("lio-run"), QStringLiteral("--algorithm"),
               variant.runnerId, QStringLiteral("--bag"), bagRelative, QStringLiteral("--run-dir"), resultRelative,
               QStringLiteral("--config"), runtimeRelative, QStringLiteral("--playback-rate"), playbackRate};
  stopProgram = QStringLiteral("docker");
  stopArguments = {QStringLiteral("stop"), QStringLiteral("--time"), QStringLiteral("15"), containerName};
#endif
  return PreparedRun{
      runId,
      simulation.id,
      variant.id,
      variant.runnerId,
      program,
      arguments,
      contracts_.workspace(),
      resultDirectory,
      request,
      stopProgram,
      stopArguments,
  };
}

PreparedRun RunnerRegistry::preparePx4(const SimulationDefinition& simulation,
                                       const VariantDefinition& variant,
                                       const QJsonObject& request,
                                       const QString& runId,
                                       const QString& stamp) const {
  const auto resultRelative = QStringLiteral("results/simulation/px4_lot_a/%1_%2_%3").arg(variant.id, stamp, runId);
  const auto resultDirectory = safeWorkspacePath(contracts_.workspace(), resultRelative, QStringLiteral("Résultat PX4"));
  const auto parameters = request.value(QStringLiteral("parameters")).toObject();
  const auto remoteUrl = qEnvironmentVariable("DRONE_AGRICOLE_PX4_RUNNER_URL",
                                               QStringLiteral("http://127.0.0.1:8091"));
  auto arguments = QStringList{QStringLiteral("--url"), remoteUrl, QStringLiteral("--run-id"), runId,
                               QStringLiteral("--mode"), variant.id, QStringLiteral("--result-directory"),
                               resultRelative, QStringLiteral("--takeoff-altitude-m"),
                               scalarText(parameters.value(QStringLiteral("takeoff_altitude_m"))),
                               QStringLiteral("--leg-m"), scalarText(parameters.value(QStringLiteral("leg_m"))),
                               QStringLiteral("--warmup-s"), scalarText(parameters.value(QStringLiteral("warmup_s"))),
                               QStringLiteral("--hover-s"), scalarText(parameters.value(QStringLiteral("hover_s"))),
                               QStringLiteral("--stage-timeout-s"),
                               scalarText(parameters.value(QStringLiteral("stage_timeout_s")))};
  if (remoteUrl.startsWith(QStringLiteral("http://127.0.0.1:")) ||
      remoteUrl.startsWith(QStringLiteral("http://localhost:"))) {
    arguments.prepend(QStringLiteral("--ensure-docker"));
  }
  const auto clientProgram = projectPx4ClientProgram();
  return PreparedRun{
      runId,
      simulation.id,
      variant.id,
      variant.runnerId,
      clientProgram,
      arguments,
      contracts_.workspace(),
      resultDirectory,
      request,
      clientProgram,
      {QStringLiteral("--url"), remoteUrl, QStringLiteral("--stop-only")},
  };
}

void RunnerRegistry::writeLioConfig(const QString& runnerId,
                                    const QString& basePath,
                                    const QString& outputPath,
                                    const QJsonObject& parameters) {
  YAML::Node configuration;
  try {
    configuration = YAML::LoadFile(basePath.toStdString());
  } catch (const YAML::Exception& error) {
    throw ContractError(QStringLiteral("Configuration LIO illisible : %1").arg(QString::fromUtf8(error.what())));
  }
  const auto& paths = parameterPaths(runnerId);
  for (auto iterator = paths.cbegin(); iterator != paths.cend(); ++iterator) {
    if (parameters.contains(iterator.key())) {
      setPath(configuration, iterator.value(), parameters.value(iterator.key()));
    }
  }
  if (runnerId == QStringLiteral("fast_lio2") || runnerId == QStringLiteral("point_lio")) {
    setPath(configuration, {"/**", "ros__parameters", "publish", "scan_publish_en"}, true);
  }
  QDir().mkpath(QFileInfo(outputPath).absolutePath());
  std::ofstream output(outputPath.toStdString(), std::ios::trunc);
  if (!output) {
    throw ContractError(QStringLiteral("Écriture de la configuration LIO impossible"));
  }
  output << configuration;
}

}  // namespace drone_agricole::core
