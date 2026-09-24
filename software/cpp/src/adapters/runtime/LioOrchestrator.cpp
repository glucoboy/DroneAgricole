#include "drone_agricole/core/LioOrchestrator.hpp"

#include "drone_agricole/core/BenchmarkSupport.hpp"
#include "drone_agricole/core/BenchmarkTelemetry.hpp"
#include "drone_agricole/core/JsonUtils.hpp"
#include "drone_agricole/core/RosRuntimeTools.hpp"
#include "drone_agricole/core/RosbagAnalysis.hpp"

#include <QCoreApplication>
#include <QDateTime>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QJsonArray>
#include <QJsonDocument>
#include <QProcess>
#include <QRegularExpression>
#include <QTextStream>
#include <QThread>

#include <algorithm>
#include <chrono>
#include <cmath>
#include <memory>
#include <set>
#include <vector>

#ifdef Q_OS_UNIX
#include <csignal>
#include <unistd.h>
#endif

namespace drone_agricole::core {
namespace {

struct ProcessSample {
  double cpuSeconds{0.0};
  quint64 rssBytes{0};
};

struct ProcessProfile {
  double maximumCpuSeconds{0.0};
  quint64 peakRssBytes{0};
  qint64 samples{0};
};

QString requiredString(const QJsonObject& options, const QString& key) {
  const auto value = options.value(key).toString();
  if (value.isEmpty()) {
    throw ContractError(QStringLiteral("Option requise : --%1").arg(key));
  }
  return value;
}

void stopProcess(QProcess& process) {
  if (process.state() == QProcess::NotRunning) {
    return;
  }
#ifdef Q_OS_UNIX
  ::kill(static_cast<pid_t>(process.processId()), SIGINT);
#else
  process.terminate();
#endif
  if (!process.waitForFinished(10000)) {
    process.terminate();
    if (!process.waitForFinished(5000)) {
      process.kill();
      process.waitForFinished(3000);
    }
  }
}

#ifdef Q_OS_LINUX
std::set<qint64> processTree(const qint64 root) {
  std::set<qint64> result{root};
  std::vector<qint64> pending{root};
  while (!pending.empty()) {
    const auto process = pending.back();
    pending.pop_back();
    QFile children(QStringLiteral("/proc/%1/task/%1/children").arg(process));
    if (!children.open(QIODevice::ReadOnly | QIODevice::Text)) {
      continue;
    }
    for (const auto& token : QString::fromUtf8(children.readAll()).split(QLatin1Char(' '), Qt::SkipEmptyParts)) {
      bool valid = false;
      const auto child = token.toLongLong(&valid);
      if (valid && result.insert(child).second) {
        pending.push_back(child);
      }
    }
  }
  return result;
}
#endif

ProcessSample sampleProcess(const qint64 root) {
  ProcessSample sample;
#ifdef Q_OS_LINUX
  const auto ticks = static_cast<double>(::sysconf(_SC_CLK_TCK));
  for (const auto process : processTree(root)) {
    QFile stat(QStringLiteral("/proc/%1/stat").arg(process));
    if (stat.open(QIODevice::ReadOnly | QIODevice::Text)) {
      const auto line = QString::fromUtf8(stat.readAll());
      const auto close = line.lastIndexOf(QLatin1Char(')'));
      const auto fields = line.mid(close + 2).split(QLatin1Char(' '), Qt::SkipEmptyParts);
      if (fields.size() > 12) {
        sample.cpuSeconds += (fields[11].toDouble() + fields[12].toDouble()) / ticks;
      }
    }
    QFile status(QStringLiteral("/proc/%1/status").arg(process));
    quint64 residentBytes = 0;
    if (status.open(QIODevice::ReadOnly | QIODevice::Text)) {
      while (!status.atEnd()) {
        const auto line = status.readLine();
        if (line.startsWith("VmRSS:")) {
          const auto parts = QString::fromUtf8(line).split(QRegularExpression(QStringLiteral("\\s+")), Qt::SkipEmptyParts);
          if (parts.size() >= 2) {
            residentBytes = parts[1].toULongLong() * 1024ULL;
          }
          break;
        }
      }
    }
    if (residentBytes == 0) {
      QFile statm(QStringLiteral("/proc/%1/statm").arg(process));
      if (statm.open(QIODevice::ReadOnly | QIODevice::Text)) {
        const auto fields = QString::fromUtf8(statm.readAll()).split(QLatin1Char(' '), Qt::SkipEmptyParts);
        if (fields.size() >= 2) {
          residentBytes = fields[1].toULongLong() * static_cast<quint64>(::sysconf(_SC_PAGESIZE));
        }
      }
    }
    sample.rssBytes += residentBytes;
  }
#else
  Q_UNUSED(root)
#endif
  return sample;
}

ProcessSample updateProfile(ProcessProfile& profile, const std::vector<std::unique_ptr<QProcess>>& processes) {
  ProcessSample combined;
  for (const auto& process : processes) {
    if (process->state() == QProcess::Running) {
      const auto sample = sampleProcess(process->processId());
      combined.cpuSeconds += sample.cpuSeconds;
      combined.rssBytes += sample.rssBytes;
    }
  }
  profile.maximumCpuSeconds = std::max(profile.maximumCpuSeconds, combined.cpuSeconds);
  profile.peakRssBytes = std::max(profile.peakRssBytes, combined.rssBytes);
  ++profile.samples;
  return combined;
}

std::unique_ptr<QProcess> startProcess(const QString& program,
                                       const QStringList& arguments,
                                       const QString& workingDirectory,
                                       const QString& logPath,
                                       const bool append = false) {
  auto process = std::make_unique<QProcess>();
  process->setWorkingDirectory(workingDirectory);
  if (!logPath.isEmpty()) {
    process->setStandardOutputFile(logPath, append ? QIODevice::Append : QIODevice::Truncate);
    process->setStandardErrorFile(logPath, QIODevice::Append);
  }
  process->setProgram(program);
  process->setArguments(arguments);
  process->start();
  if (!process->waitForStarted(10000)) {
    throw ContractError(QStringLiteral("Démarrage impossible : %1 (%2)").arg(program, process->errorString()));
  }
  return process;
}

bool topicAvailable(const QString& topic, const QString& workspace) {
  QProcess command;
  command.setWorkingDirectory(workspace);
  command.start(QStringLiteral("ros2"), {QStringLiteral("topic"), QStringLiteral("list")});
  if (!command.waitForFinished(5000) || command.exitCode() != 0) {
    return false;
  }
  return QString::fromUtf8(command.readAllStandardOutput()).split(QLatin1Char('\n')).contains(topic);
}

void waitForTopic(const QString& topic,
                  const QString& workspace,
                  const std::vector<std::unique_ptr<QProcess>>& algorithms,
                  const int attempts = 60) {
  for (int attempt = 0; attempt < attempts; ++attempt) {
    if (topicAvailable(topic, workspace)) {
      return;
    }
    if (std::any_of(algorithms.cbegin(), algorithms.cend(), [](const auto& process) {
          return process->state() == QProcess::NotRunning;
        })) {
      throw ContractError(QStringLiteral("Un processus LIO s'est arrêté pendant son initialisation"));
    }
    QThread::msleep(200);
  }
  throw ContractError(QStringLiteral("Le topic %1 n'est pas apparu").arg(topic));
}

QJsonObject profileJson(const ProcessProfile& profile,
                        const QStringList& command,
                        const double startedUnix,
                        const double wallSeconds,
                        const int exitCode) {
  const auto cpu = profile.maximumCpuSeconds;
  const auto logical = std::max(1, QThread::idealThreadCount());
  return {
      {QStringLiteral("schema_version"), 1},
      {QStringLiteral("command"), QJsonArray::fromStringList(command)},
      {QStringLiteral("started_at_unix_s"), startedUnix},
      {QStringLiteral("wall_seconds"), wallSeconds},
      {QStringLiteral("exit_code"), exitCode},
      {QStringLiteral("forwarded_signal"), QJsonValue(QJsonValue::Null)},
      {QStringLiteral("samples"), static_cast<double>(profile.samples)},
      {QStringLiteral("sample_interval_s"), 0.25},
      {QStringLiteral("cpu_user_seconds"), cpu},
      {QStringLiteral("cpu_system_seconds"), 0.0},
      {QStringLiteral("cpu_total_seconds"), cpu},
      {QStringLiteral("cpu_average_equivalent_cores"), wallSeconds > 0.0 ? QJsonValue(cpu / wallSeconds) : QJsonValue(QJsonValue::Null)},
      {QStringLiteral("cpu_average_percent_one_core_100"), wallSeconds > 0.0 ? QJsonValue(100.0 * cpu / wallSeconds) : QJsonValue(QJsonValue::Null)},
      {QStringLiteral("logical_cpu_count_visible"), logical},
      {QStringLiteral("cpu_average_percent_visible_machine"),
       wallSeconds > 0.0 ? QJsonValue(100.0 * cpu / wallSeconds / logical) : QJsonValue(QJsonValue::Null)},
      {QStringLiteral("peak_rss_bytes"), static_cast<double>(profile.peakRssBytes)},
      {QStringLiteral("peak_rss_mib"), static_cast<double>(profile.peakRssBytes) / (1024.0 * 1024.0)},
  };
}

QString defaultRunDirectory(const QString& algorithm) {
  const auto stamp = QDateTime::currentDateTimeUtc().toString(QStringLiteral("yyyyMMdd'T'HHmmss'Z'"));
  return QStringLiteral("results/benchmarks/%1/botanicgarden_1006-03/smoke_%2").arg(algorithm, stamp);
}

void writeText(const QString& path, const QByteArray& data) {
  QFile file(path);
  if (!file.open(QIODevice::WriteOnly | QIODevice::Truncate)) {
    throw ContractError(QStringLiteral("Écriture impossible : %1").arg(path));
  }
  file.write(data);
}

void reportProgress(const QString& stage,
                    const int percent,
                    const double currentSeconds = 0.0,
                    const double totalSeconds = 0.0) {
  QTextStream output(stdout);
  output << "LIO_PROGRESS stage=" << stage << " percent=" << std::clamp(percent, 0, 100);
  if (totalSeconds > 0.0) {
    output << " current_s=" << QString::number(std::clamp(currentSeconds, 0.0, totalSeconds), 'f', 1)
           << " total_s=" << QString::number(totalSeconds, 'f', 1);
  }
  output << Qt::endl;
}

}  // namespace

int runLioBenchmark(const QJsonObject& options) {
  const auto algorithm = requiredString(options, QStringLiteral("algorithm"));
  if (!QStringList{QStringLiteral("fast_lio2"), QStringLiteral("point_lio"), QStringLiteral("lio_sam")}.contains(algorithm)) {
    throw ContractError(QStringLiteral("Algorithme LIO inconnu : %1").arg(algorithm));
  }
  const auto bag = requiredString(options, QStringLiteral("bag"));
  const auto config = requiredString(options, QStringLiteral("config"));
  const auto workspace = QDir::currentPath();
  auto runDirectory = options.value(QStringLiteral("run-dir")).toString(defaultRunDirectory(algorithm));
  runDirectory = QFileInfo(runDirectory).absoluteFilePath();
  if (!QFileInfo(bag).isDir() || !QFileInfo(config).isFile()) {
    throw ContractError(QStringLiteral("Rosbag2 ou configuration LIO absent"));
  }
  if (QFileInfo::exists(runDirectory)) {
    throw ContractError(QStringLiteral("Le dossier de résultat existe déjà : %1").arg(runDirectory));
  }
  if (!QDir().mkpath(runDirectory)) {
    throw ContractError(QStringLiteral("Création du dossier de résultat impossible"));
  }
  const auto effectiveConfig = QDir(runDirectory).filePath(QStringLiteral("effective_config.yaml"));
  if (!QFile::copy(config, effectiveConfig)) {
    throw ContractError(QStringLiteral("Copie de la configuration impossible"));
  }
  const auto playbackRate = options.value(QStringLiteral("playback-rate")).toDouble(1.0);
  const auto playbackDelay = options.value(QStringLiteral("playback-delay-s")).toDouble(1.0);
  const auto drainTimeout = options.value(QStringLiteral("pipeline-drain-timeout-s")).toDouble(15.0);
  const auto stableSeconds = options.value(QStringLiteral("pipeline-stable-s")).toDouble(1.0);
  const auto bagMetadata = readBagMetadata(QFileInfo(bag).absoluteFilePath());
  const QHash<QString, QString> pipelineTopics{
      {QStringLiteral("fast_lio2"), QStringLiteral("/fast_lio2/pipeline_counters")},
      {QStringLiteral("point_lio"), QStringLiteral("/point_lio/pipeline_counters")},
      {QStringLiteral("lio_sam"), QStringLiteral("/lio_sam/pipeline_counters")},
  };
  std::vector<std::unique_ptr<QProcess>> algorithms;
  std::unique_ptr<QProcess> monitor;
  QStringList measuredCommand;
  try {
    BenchmarkTelemetryPublisher benchmarkTelemetry;
    benchmarkTelemetry.publish(bagMetadata.durationSeconds, 0.0, 0.0, 0.0);
    reportProgress(QStringLiteral("initialization"), 2);
    if (algorithm == QStringLiteral("fast_lio2")) {
      measuredCommand = {QStringLiteral("/opt/fast_lio_ws/install/lib/fast_lio/fastlio_mapping"),
                         QStringLiteral("--ros-args"), QStringLiteral("--params-file"), effectiveConfig};
      algorithms.push_back(startProcess(measuredCommand.first(), measuredCommand.mid(1), workspace,
                                        QDir(runDirectory).filePath(QStringLiteral("fast_lio2.log"))));
    } else if (algorithm == QStringLiteral("point_lio")) {
      measuredCommand = {QStringLiteral("/opt/point_lio_ws/install/lib/point_lio/pointlio_mapping"),
                         QStringLiteral("--ros-args"), QStringLiteral("--params-file"), effectiveConfig,
                         QStringLiteral("-r"), QStringLiteral("/aft_mapped_to_init:=/Odometry")};
      algorithms.push_back(startProcess(measuredCommand.first(), measuredCommand.mid(1), workspace,
                                        QDir(runDirectory).filePath(QStringLiteral("point_lio.log"))));
    } else {
      monitor = startProcess(QCoreApplication::applicationFilePath(), {QStringLiteral("lio-sam-monitor")}, workspace,
                             QDir(runDirectory).filePath(QStringLiteral("pipeline_monitor.log")));
      const QStringList executables{
          QStringLiteral("lio_sam_imuPreintegration"), QStringLiteral("lio_sam_imageProjection"),
          QStringLiteral("lio_sam_featureExtraction"), QStringLiteral("lio_sam_mapOptimization")};
      for (const auto& executable : executables) {
        const auto program = QStringLiteral("/opt/lio_sam_ws/install/lib/lio_sam/%1").arg(executable);
        const QStringList arguments{
            QStringLiteral("--ros-args"), QStringLiteral("--params-file"), effectiveConfig,
            QStringLiteral("-r"), QStringLiteral("lio_sam/mapping/odometry:=/Odometry"),
            QStringLiteral("-r"), QStringLiteral("lio_sam/mapping/path:=/path"),
            QStringLiteral("-r"), QStringLiteral("lio_sam/mapping/cloud_registered:=/cloud_registered")};
        algorithms.push_back(startProcess(program, arguments, workspace,
                                          QDir(runDirectory).filePath(QStringLiteral("lio_sam.log")), true));
      }
      measuredCommand = {QStringLiteral("LIO-SAM components"), effectiveConfig};
    }
    waitForTopic(QStringLiteral("/Odometry"), workspace, algorithms, algorithm == QStringLiteral("lio_sam") ? 100 : 60);
    reportProgress(QStringLiteral("recording"), 4);

    auto recorder = startProcess(
        QStringLiteral("ros2"),
        {QStringLiteral("bag"), QStringLiteral("record"), QStringLiteral("--storage"), QStringLiteral("mcap"),
         QStringLiteral("--output"), QDir(runDirectory).filePath(QStringLiteral("estimate")),
         QStringLiteral("/Odometry"), QStringLiteral("/path"), QStringLiteral("/gt_poses"), pipelineTopics.value(algorithm)},
        workspace, QDir(runDirectory).filePath(QStringLiteral("record.log")));
    QThread::sleep(1);

    const auto startedUnix = static_cast<double>(QDateTime::currentMSecsSinceEpoch()) / 1000.0;
    const auto playbackStartNs = QDateTime::currentMSecsSinceEpoch() * 1000000LL;
    const auto wallStarted = std::chrono::steady_clock::now();
    auto playback = startProcess(
        QStringLiteral("ros2"),
        {QStringLiteral("bag"), QStringLiteral("play"), QFileInfo(bag).absoluteFilePath(), QStringLiteral("--rate"),
         QString::number(playbackRate, 'g', 12), QStringLiteral("--delay"), QString::number(playbackDelay, 'g', 12)},
        workspace, QDir(runDirectory).filePath(QStringLiteral("playback.log")));
    ProcessProfile profile;
    auto lastReportedSecond = -5LL;
    auto lastTelemetryTime = wallStarted;
    ProcessSample lastTelemetrySample;
    while (playback->state() != QProcess::NotRunning) {
      const auto processSample = updateProfile(profile, algorithms);
      const auto now = std::chrono::steady_clock::now();
      const auto elapsedSeconds = std::chrono::duration<double>(now - wallStarted).count();
      const auto telemetryInterval = std::chrono::duration<double>(now - lastTelemetryTime).count();
      if (telemetryInterval >= 1.0) {
        const auto cpuDelta = std::max(0.0, processSample.cpuSeconds - lastTelemetrySample.cpuSeconds);
        benchmarkTelemetry.publish(bagMetadata.durationSeconds, 100.0 * cpuDelta / telemetryInterval,
                                   processSample.cpuSeconds,
                                   static_cast<double>(processSample.rssBytes) / (1024.0 * 1024.0));
        lastTelemetryTime = now;
        lastTelemetrySample = processSample;
      }
      const auto elapsedWholeSeconds = static_cast<long long>(std::floor(elapsedSeconds));
      if (elapsedWholeSeconds - lastReportedSecond >= 5) {
        const auto playedSeconds = std::max(0.0, elapsedSeconds - playbackDelay) * playbackRate;
        reportProgress(QStringLiteral("playback"),
                       playbackProgressPercent(elapsedSeconds, bagMetadata.durationSeconds, playbackRate, playbackDelay),
                       playedSeconds, bagMetadata.durationSeconds);
        lastReportedSecond = elapsedWholeSeconds;
      }
      if (std::any_of(algorithms.cbegin(), algorithms.cend(), [](const auto& process) {
            return process->state() == QProcess::NotRunning;
          })) {
        stopProcess(*playback);
        throw ContractError(QStringLiteral("Un processus LIO s'est arrêté pendant le rejeu"));
      }
      playback->waitForFinished(250);
    }
    const auto playbackEndNs = QDateTime::currentMSecsSinceEpoch() * 1000000LL;
    if (playback->exitStatus() != QProcess::NormalExit || playback->exitCode() != 0) {
      throw ContractError(QStringLiteral("Le rejeu rosbag2 a échoué avec le code %1").arg(playback->exitCode()));
    }
    reportProgress(QStringLiteral("drain"), 92);
    QJsonObject drain;
    try {
      drain = waitForPipelineDrain(QFileInfo(bag).absoluteFilePath(), QStringLiteral("/velodyne_points"),
                                   pipelineTopics.value(algorithm), drainTimeout, stableSeconds);
    } catch (const std::exception& error) {
      drain = {{QStringLiteral("schema_version"), 1}, {QStringLiteral("status"), QStringLiteral("error")},
               {QStringLiteral("message"), QString::fromUtf8(error.what())}};
    }
    writeJsonObjectAtomically(QDir(runDirectory).filePath(QStringLiteral("pipeline_drain.json")), drain);
    stopProcess(*recorder);
    for (auto& process : algorithms) {
      stopProcess(*process);
    }
    if (monitor) {
      stopProcess(*monitor);
    }
    reportProgress(QStringLiteral("artifacts"), 95);
    const auto wallSeconds = std::chrono::duration<double>(std::chrono::steady_clock::now() - wallStarted).count();
    writeJsonObjectAtomically(QDir(runDirectory).filePath(QStringLiteral("resource_profile.json")),
                              profileJson(profile, measuredCommand, startedUnix, wallSeconds, 0));

    QProcess bagInfo;
    bagInfo.setWorkingDirectory(workspace);
    bagInfo.start(QStringLiteral("ros2"), {QStringLiteral("bag"), QStringLiteral("info"),
                                           QDir(runDirectory).filePath(QStringLiteral("estimate"))});
    bagInfo.waitForFinished(30000);
    writeText(QDir(runDirectory).filePath(QStringLiteral("bag_info.txt")),
              bagInfo.readAllStandardOutput() + bagInfo.readAllStandardError());

    summarizeRun({
        {QStringLiteral("algorithm"), algorithm},
        {QStringLiteral("bag"), QFileInfo(bag).absoluteFilePath()},
        {QStringLiteral("config"), effectiveConfig},
        {QStringLiteral("profile"), QDir(runDirectory).filePath(QStringLiteral("resource_profile.json"))},
        {QStringLiteral("output"), QDir(runDirectory).filePath(QStringLiteral("run_manifest.json"))},
        {QStringLiteral("playback-rate"), playbackRate},
        {QStringLiteral("playback-delay-s"), playbackDelay},
        {QStringLiteral("playback-start-ns"), static_cast<double>(playbackStartNs)},
        {QStringLiteral("playback-end-ns"), static_cast<double>(playbackEndNs)},
    });
    reportProgress(QStringLiteral("analysis"), 97);
    const auto metrics = analyzeRosbag(QDir(runDirectory).filePath(QStringLiteral("estimate")), 0.06, 1.0, 0.06,
                                       QStringLiteral("/Odometry"), QStringLiteral("/gt_poses"),
                                       pipelineTopics.value(algorithm));
    writeJsonObjectAtomically(QDir(runDirectory).filePath(QStringLiteral("metrics.json")), metrics);
    reportProgress(QStringLiteral("complete"), 100);
  } catch (...) {
    for (auto& process : algorithms) {
      stopProcess(*process);
    }
    if (monitor) {
      stopProcess(*monitor);
    }
    throw;
  }
  QTextStream(stdout) << algorithm.toUpper() << "_RUN_DIR=" << QDir::toNativeSeparators(runDirectory) << Qt::endl;
  return 0;
}

int runFastLioCampaign(const QJsonObject& options) {
  const auto root = options.value(QStringLiteral("root")).toString(
      QStringLiteral("results/benchmarks/fast_lio2/botanicgarden_1006-03/qualification_08x_v01"));
  const auto phase = options.value(QStringLiteral("phase")).toString(QStringLiteral("all"));
  if (!QStringList{QStringLiteral("qualification"), QStringLiteral("repeats"), QStringLiteral("all")}.contains(phase)) {
    throw ContractError(QStringLiteral("Phase invalide : %1").arg(phase));
  }
  struct Case {
    QString scope;
    QString variant;
    QString repeat;
    QString bag;
    QString config;
  };
  const auto dynamicBag = QStringLiteral("datasets/derived/botanicgarden/1006-03/dynamic/velodyne_xsens_fastlio2_30s_offset60_ros2");
  const auto fullBag = QStringLiteral("datasets/derived/botanicgarden/1006-03/full/velodyne_xsens_fastlio2_full_ros2");
  const auto baseline = QStringLiteral("configs/lio/fast_lio2/botanicgarden_velodyne_xsens.yaml");
  QList<Case> cases;
  if (phase == QStringLiteral("qualification") || phase == QStringLiteral("all")) {
    cases.append({QStringLiteral("dynamic"), QStringLiteral("baseline"), QStringLiteral("01"), dynamicBag, baseline});
    cases.append({QStringLiteral("full"), QStringLiteral("baseline"), QStringLiteral("01"), fullBag, baseline});
  }
  if (phase == QStringLiteral("repeats") || phase == QStringLiteral("all")) {
    cases.append({QStringLiteral("dynamic"), QStringLiteral("baseline"), QStringLiteral("02"), dynamicBag, baseline});
    cases.append({QStringLiteral("dynamic"), QStringLiteral("baseline"), QStringLiteral("03"), dynamicBag, baseline});
    const QHash<QString, QString> variants{
        {QStringLiteral("voxel_fine_025m"), QStringLiteral("configs/lio/fast_lio2/sensitivity/voxel_fine_025m.yaml")},
        {QStringLiteral("voxel_coarse_100m"), QStringLiteral("configs/lio/fast_lio2/sensitivity/voxel_coarse_100m.yaml")},
        {QStringLiteral("extrinsic_translation_x_plus_5cm"),
         QStringLiteral("configs/lio/fast_lio2/sensitivity/extrinsic_translation_x_plus_5cm.yaml")},
        {QStringLiteral("extrinsic_yaw_plus_2deg"),
         QStringLiteral("configs/lio/fast_lio2/sensitivity/extrinsic_yaw_plus_2deg.yaml")},
    };
    for (auto iterator = variants.cbegin(); iterator != variants.cend(); ++iterator) {
      for (const auto& repeat : {QStringLiteral("01"), QStringLiteral("02"), QStringLiteral("03")}) {
        cases.append({QStringLiteral("dynamic"), iterator.key(), repeat, dynamicBag, iterator.value()});
      }
    }
  }
  for (const auto& item : cases) {
    const auto directory = QDir(root).filePath(QStringLiteral("%1/%2/repeat_%3").arg(item.scope, item.variant, item.repeat));
    if (QFileInfo::exists(QDir(directory).filePath(QStringLiteral("run_manifest.json"))) &&
        QFileInfo::exists(QDir(directory).filePath(QStringLiteral("metrics.json")))) {
      continue;
    }
    if (QFileInfo::exists(directory)) {
      throw ContractError(QStringLiteral("Essai incomplet déjà présent : %1").arg(directory));
    }
    runLioBenchmark({{QStringLiteral("algorithm"), QStringLiteral("fast_lio2")},
                     {QStringLiteral("bag"), item.bag}, {QStringLiteral("config"), item.config},
                     {QStringLiteral("run-dir"), directory}, {QStringLiteral("playback-rate"), 0.8}});
  }
  summarizeCampaign({{QStringLiteral("root"), root}, {QStringLiteral("playback-rate"), 0.8}});
  return 0;
}

}  // namespace drone_agricole::core
