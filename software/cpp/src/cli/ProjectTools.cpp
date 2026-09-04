#include "drone_agricole/core/BenchmarkSupport.hpp"
#include "drone_agricole/core/DatasetAdapter.hpp"
#include "drone_agricole/core/JsonUtils.hpp"
#include "drone_agricole/core/LioOrchestrator.hpp"
#include "drone_agricole/core/ResultAdapter.hpp"
#include "drone_agricole/core/RosbagAnalysis.hpp"
#include "drone_agricole/core/RosbagTrajectoryReader.hpp"
#include "drone_agricole/core/RosRuntimeTools.hpp"
#include "drone_agricole/core/TelemetryBridge.hpp"

#include <QCoreApplication>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QJsonArray>
#include <QJsonDocument>
#include <QSet>
#include <QTextStream>

#include <exception>

namespace {

QJsonObject parseOptions(const QStringList& arguments) {
  static const QSet<QString> booleanOptions{QStringLiteral("hash"), QStringLiteral("replace-native")};
  QJsonObject options;
  QJsonArray positional;
  for (qsizetype index = 0; index < arguments.size(); ++index) {
    const auto argument = arguments[index];
    if (!argument.startsWith(QStringLiteral("--"))) {
      positional.append(argument);
      continue;
    }
    const auto separator = argument.indexOf(QLatin1Char('='));
    QString key;
    QString value;
    if (separator > 2) {
      key = argument.mid(2, separator - 2);
      value = argument.mid(separator + 1);
    } else {
      key = argument.mid(2);
      if (booleanOptions.contains(key)) {
        options.insert(key, true);
        continue;
      }
      if (index + 1 < arguments.size() && !arguments[index + 1].startsWith(QStringLiteral("--"))) {
        value = arguments[++index];
      } else {
        options.insert(key, true);
        continue;
      }
    }
    bool integerOk = false;
    const auto integer = value.toLongLong(&integerOk);
    bool numberOk = false;
    const auto number = value.toDouble(&numberOk);
    if (integerOk && !value.contains(QLatin1Char('.')) && !value.contains(QLatin1Char('e'), Qt::CaseInsensitive)) {
      options.insert(key, static_cast<double>(integer));
    } else if (numberOk) {
      options.insert(key, number);
    } else if (value == QStringLiteral("true") || value == QStringLiteral("false")) {
      options.insert(key, value == QStringLiteral("true"));
    } else {
      options.insert(key, value);
    }
  }
  options.insert(QStringLiteral("positional"), positional);
  return options;
}

void printFile(const QString& path) {
  QFile file(path);
  if (!file.open(QIODevice::ReadOnly)) {
    return;
  }
  QTextStream(stdout) << QString::fromUtf8(file.readAll());
}

void printHelp() {
  QTextStream stream(stdout);
  stream << "drone-agricole-tools — outils C++17 du projet\n\n"
            "Commandes disponibles :\n"
            "  summarize-run       Génère run_manifest.json\n"
            "  summarize-sensitivity Agrège une étude de sensibilité\n"
            "  summarize-campaign  Agrège les répétitions d'une campagne\n"
            "  compare-runs        Compare au moins deux résultats\n"
            "  compare-rates       Compare les campagnes 1x et 0,8x\n"
            "  archive-result     Normalise un résultat et écrit ses cinq contrats T0\n"
            "  analyze             Analyse ATE/RPE d'un rosbag2 (construction ROS 2)\n"
            "  replay-trajectory   Relit une trajectoire historique via le pont C++\n"
            "  lio-run             Orchestre un benchmark LIO (construction ROS 2)\n"
            "  telemetry-server    Expose la télémétrie ROS 2 au dashboard Qt\n"
            "  inspect             Inspecte un ou plusieurs rosbags ROS 1\n"
            "  export-tum          Exporte /gt_poses au format TUM\n"
            "  prepare             Prépare un sous-ensemble BotanicGarden (construction ROS 2)\n";
}

}  // namespace

int main(int argc, char* argv[]) {
  QCoreApplication application(argc, argv);
  application.setApplicationName(QStringLiteral("drone-agricole-tools"));
  const auto arguments = application.arguments().mid(1);
  if (arguments.isEmpty() || arguments.first() == QStringLiteral("--help") || arguments.first() == QStringLiteral("help")) {
    printHelp();
    return 0;
  }
  const auto command = arguments.first();
  auto options = parseOptions(arguments.mid(1));
  const auto positional = options.value(QStringLiteral("positional")).toArray();
  try {
    using namespace drone_agricole::core;
    if (command == QStringLiteral("summarize-run")) {
      summarizeRun(options);
      printFile(options.value(QStringLiteral("output")).toString());
    } else if (command == QStringLiteral("summarize-sensitivity")) {
      if (!positional.isEmpty()) {
        options.insert(QStringLiteral("root"), positional.first());
      }
      summarizeSensitivity(options);
      const auto root = options.value(QStringLiteral("root")).toString();
      printFile(options.value(QStringLiteral("output-json")).toString(
          QDir(root).filePath(QStringLiteral("sensitivity_summary.json"))));
    } else if (command == QStringLiteral("summarize-campaign")) {
      if (!positional.isEmpty()) {
        options.insert(QStringLiteral("root"), positional.first());
      }
      summarizeCampaign(options);
      printFile(QDir(options.value(QStringLiteral("root")).toString()).filePath(QStringLiteral("campaign_summary.json")));
    } else if (command == QStringLiteral("compare-runs")) {
      options.insert(QStringLiteral("runs"), positional);
      compareRuns(options);
      printFile(options.value(QStringLiteral("output")).toString());
    } else if (command == QStringLiteral("compare-rates")) {
      comparePlaybackRates(options);
      printFile(QDir(options.value(QStringLiteral("campaign-08x")).toString())
                    .filePath(QStringLiteral("comparison_1x_vs_08x.json")));
    } else if (command == QStringLiteral("archive-result")) {
      if (positional.isEmpty()) {
        throw ContractError(QStringLiteral("Le répertoire de résultat est requis"));
      }
      const auto directory = positional.first().toString();
      const auto requestPath = options.value(QStringLiteral("request")).toString();
      if (requestPath.isEmpty()) {
        throw ContractError(QStringLiteral("L'option --request vers un RunRequest JSON est requise"));
      }
      if (QFileInfo(QDir(directory).filePath(QStringLiteral("t0_run_manifest.json"))).exists() &&
          !options.value(QStringLiteral("replace-native")).toBool()) {
        throw ContractError(QStringLiteral("Le résultat possède déjà des contrats T0 natifs"));
      }
      const auto request = readJsonObject(requestPath);
      requireSchema(request, QStringLiteral("drone_agricole.run_request.v1"), QStringLiteral("RunRequest"));
      requireFields(request,
                    {QStringLiteral("request_id"), QStringLiteral("simulation_id"), QStringLiteral("variant_id"),
                     QStringLiteral("requested_at_utc"), QStringLiteral("inputs"), QStringLiteral("parameters")},
                    QStringLiteral("RunRequest"));
      static_cast<void>(parseUtcDate(request.value(QStringLiteral("requested_at_utc"))));
      const auto normalized = normalizeResultDirectory(directory);
      writeNativeContracts(normalized, request);
      QTextStream(stdout) << QJsonDocument(normalized.manifest).toJson(QJsonDocument::Indented);
    } else if (command == QStringLiteral("analyze")) {
      if (positional.isEmpty()) {
        throw ContractError(QStringLiteral("Le chemin du rosbag2 est requis"));
      }
      const auto result = analyzeRosbag(
          positional.first().toString(), options.value(QStringLiteral("max-delta-s")).toDouble(0.06),
          options.value(QStringLiteral("rpe-delta-s")).toDouble(1.0),
          options.value(QStringLiteral("rpe-delta-tolerance-s")).toDouble(0.06),
          options.value(QStringLiteral("estimate-topic")).toString(QStringLiteral("/Odometry")),
          options.value(QStringLiteral("ground-truth-topic")).toString(QStringLiteral("/gt_poses")),
          options.value(QStringLiteral("pipeline-topic")).toString(QStringLiteral("/fast_lio2/pipeline_counters")));
      const auto output = options.value(QStringLiteral("output")).toString();
      if (!output.isEmpty()) {
        writeJsonObjectAtomically(output, result);
      }
      QTextStream(stdout) << QJsonDocument(result).toJson(QJsonDocument::Indented);
    } else if (command == QStringLiteral("replay-trajectory")) {
      if (positional.isEmpty()) {
        throw ContractError(QStringLiteral("Le chemin du rosbag2 est requis"));
      }
      const auto result = readLioTrajectory(
          positional.first().toString(),
          options.value(QStringLiteral("result-id")).toString(QStringLiteral("replay-diagnostic")));
      QTextStream(stdout) << QJsonDocument(replayDataToJson(result)).toJson(QJsonDocument::Indented);
    } else if (command == QStringLiteral("lio-sam-monitor")) {
      return runLioSamPipelineMonitor();
    } else if (command == QStringLiteral("wait-drain")) {
      const auto result = waitForPipelineDrain(
          options.value(QStringLiteral("bag")).toString(),
          options.value(QStringLiteral("input-topic")).toString(QStringLiteral("/velodyne_points")),
          options.value(QStringLiteral("pipeline-topic")).toString(),
          options.value(QStringLiteral("timeout-s")).toDouble(15.0),
          options.value(QStringLiteral("stable-s")).toDouble(1.0));
      const auto output = options.value(QStringLiteral("output")).toString();
      if (!output.isEmpty()) {
        writeJsonObjectAtomically(output, result);
      }
      QTextStream(stdout) << QJsonDocument(result).toJson(QJsonDocument::Indented);
      return result.value(QStringLiteral("status")).toString() == QStringLiteral("complete") ? 0 : 4;
    } else if (command == QStringLiteral("lio-run")) {
      return runLioBenchmark(options);
    } else if (command == QStringLiteral("telemetry-server")) {
      return runTelemetryServer(options);
    } else if (command == QStringLiteral("fast-lio-campaign")) {
      if (!positional.isEmpty()) {
        options.insert(QStringLiteral("root"), positional.first());
      }
      return runFastLioCampaign(options);
    } else if (command == QStringLiteral("inspect")) {
      QStringList bags;
      for (const auto& value : positional) {
        bags.append(value.toString());
      }
      const auto result = inspectRos1Bags(bags, options.value(QStringLiteral("hash")).toBool());
      const auto output = options.value(QStringLiteral("output")).toString();
      if (!output.isEmpty()) {
        writeJsonObjectAtomically(output, result);
      }
      QTextStream(stdout) << QJsonDocument(result).toJson(QJsonDocument::Indented);
    } else if (command == QStringLiteral("export-tum")) {
      const auto result = exportGroundTruthTum(options.value(QStringLiteral("ground-truth-bag")).toString(),
                                               options.value(QStringLiteral("output")).toString());
      QTextStream(stdout) << QJsonDocument(result).toJson(QJsonDocument::Indented);
    } else if (command == QStringLiteral("prepare")) {
      const auto result = prepareBotanicGarden(options);
      QTextStream(stdout) << QJsonDocument(result).toJson(QJsonDocument::Indented);
    } else {
      throw ContractError(QStringLiteral("Commande inconnue ou indisponible dans cette construction : %1").arg(command));
    }
  } catch (const std::exception& error) {
    QTextStream(stderr) << "error: " << QString::fromUtf8(error.what()) << Qt::endl;
    return 1;
  }
  return 0;
}
