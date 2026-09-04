#include "drone_agricole/core/JsonUtils.hpp"

#include <QCommandLineParser>
#include <QCoreApplication>
#include <QDir>
#include <QEventLoop>
#include <QJsonArray>
#include <QJsonDocument>
#include <QNetworkAccessManager>
#include <QNetworkReply>
#include <QNetworkRequest>
#include <QProcess>
#include <QSet>
#include <QTextStream>
#include <QThread>
#include <QTimer>
#include <QUrl>

#include <atomic>
#include <cmath>
#include <csignal>

using drone_agricole::core::ContractError;

namespace {

std::atomic_bool stopRequested{false};

void requestStop(int) { stopRequested.store(true); }

QJsonObject requestJson(QNetworkAccessManager& manager,
                        const QUrl& url,
                        const QByteArray& method = QByteArrayLiteral("GET"),
                        const QJsonObject& payload = {}) {
  QNetworkRequest request(url);
  request.setHeader(QNetworkRequest::ContentTypeHeader, QStringLiteral("application/json"));
  QNetworkReply* reply = nullptr;
  if (method == QByteArrayLiteral("POST")) {
    reply = manager.post(request, QJsonDocument(payload).toJson(QJsonDocument::Compact));
  } else {
    reply = manager.get(request);
  }
  QEventLoop loop;
  QTimer timeout;
  timeout.setSingleShot(true);
  QObject::connect(reply, &QNetworkReply::finished, &loop, &QEventLoop::quit);
  QObject::connect(&timeout, &QTimer::timeout, &loop, &QEventLoop::quit);
  timeout.start(5000);
  loop.exec();
  if (!reply->isFinished()) {
    reply->abort();
    reply->deleteLater();
    throw ContractError(QStringLiteral("Runner PX4 inaccessible : délai réseau dépassé"));
  }
  const auto bytes = reply->readAll();
  const auto networkError = reply->error();
  const auto errorText = reply->errorString();
  reply->deleteLater();
  QJsonParseError parseError;
  const auto document = QJsonDocument::fromJson(bytes, &parseError);
  if (networkError != QNetworkReply::NoError) {
    const auto detail = document.isObject() ? document.object().value(QStringLiteral("error")).toString() : QString{};
    throw ContractError(detail.isEmpty() ? QStringLiteral("Runner PX4 inaccessible : %1").arg(errorText) : detail);
  }
  if (parseError.error != QJsonParseError::NoError || !document.isObject()) {
    throw ContractError(QStringLiteral("Réponse JSON invalide du runner PX4"));
  }
  return document.object();
}

QCommandLineOption requiredValue(const QStringList& names, const QString& description, const QString& valueName) {
  return QCommandLineOption(names, description, valueName);
}

void ensureDockerRunner(QNetworkAccessManager& manager, const QString& root) {
  try {
    requestJson(manager, QUrl(root + QStringLiteral("/api/run/status")));
    return;
  } catch (const ContractError&) {
    QTextStream(stdout) << QStringLiteral("Runner PX4 absent, démarrage des services Docker SITL…\n");
  }

  QProcess docker;
  docker.setWorkingDirectory(QDir::currentPath());
  docker.setProgram(QStringLiteral("docker"));
  docker.setArguments({QStringLiteral("compose"), QStringLiteral("--profile"), QStringLiteral("sim"),
                       QStringLiteral("--profile"), QStringLiteral("viz"), QStringLiteral("up"),
                       QStringLiteral("-d"), QStringLiteral("px4-runner-api")});
  docker.setProcessChannelMode(QProcess::MergedChannels);
  docker.start();
  if (!docker.waitForStarted(10000)) {
    throw ContractError(QStringLiteral("Docker Desktop est inaccessible : %1").arg(docker.errorString()));
  }
  if (!docker.waitForFinished(300000)) {
    docker.kill();
    docker.waitForFinished(5000);
    throw ContractError(QStringLiteral("Le démarrage Docker PX4 a dépassé cinq minutes"));
  }
  const auto dockerOutput = QString::fromLocal8Bit(docker.readAll()).trimmed();
  if (!dockerOutput.isEmpty()) {
    QTextStream(stdout) << dockerOutput << QLatin1Char('\n');
  }
  if (docker.exitStatus() != QProcess::NormalExit || docker.exitCode() != 0) {
    throw ContractError(QStringLiteral("Le profil Docker PX4 n'a pas démarré (code %1)").arg(docker.exitCode()));
  }

  for (int attempt = 0; attempt < 45; ++attempt) {
    try {
      requestJson(manager, QUrl(root + QStringLiteral("/api/run/status")));
      QTextStream(stdout) << QStringLiteral("Runner PX4 prêt sur %1\n").arg(root);
      return;
    } catch (const ContractError&) {
      QThread::msleep(1000);
    }
  }
  throw ContractError(QStringLiteral("Les conteneurs sont démarrés, mais le runner PX4 ne répond pas sur %1").arg(root));
}

}  // namespace

int main(int argc, char* argv[]) {
  QCoreApplication application(argc, argv);
  QCoreApplication::setApplicationName(QStringLiteral("drone-agricole-px4-client"));
  QCoreApplication::setApplicationVersion(QStringLiteral("1.0.0"));
  QCommandLineParser parser;
  parser.setApplicationDescription(QStringLiteral("Client C++ verrouillé du runner PX4 SITL"));
  parser.addHelpOption();
  parser.addVersionOption();
  const auto urlOption = requiredValue({QStringLiteral("u"), QStringLiteral("url")}, QStringLiteral("URL du runner"),
                                       QStringLiteral("url"));
  const auto runOption = requiredValue({QStringLiteral("run-id")}, QStringLiteral("Identifiant d'exécution"),
                                       QStringLiteral("id"));
  const auto modeOption = requiredValue({QStringLiteral("mode")}, QStringLiteral("square ou failsafe"),
                                        QStringLiteral("mode"));
  const auto resultOption = requiredValue({QStringLiteral("result-directory")}, QStringLiteral("Répertoire de résultat relatif"),
                                          QStringLiteral("path"));
  const auto altitudeOption = requiredValue({QStringLiteral("takeoff-altitude-m")}, QStringLiteral("Altitude"), QStringLiteral("m"));
  const auto legOption = requiredValue({QStringLiteral("leg-m")}, QStringLiteral("Côté du carré"), QStringLiteral("m"));
  const auto warmupOption = requiredValue({QStringLiteral("warmup-s")}, QStringLiteral("Préparation"), QStringLiteral("s"));
  const auto hoverOption = requiredValue({QStringLiteral("hover-s")}, QStringLiteral("Stationnaire"), QStringLiteral("s"));
  const auto timeoutOption = requiredValue({QStringLiteral("stage-timeout-s")}, QStringLiteral("Délai maximal"), QStringLiteral("s"));
  const QCommandLineOption stopOnlyOption(QStringLiteral("stop-only"),
                                          QStringLiteral("Demande uniquement l'arrêt sûr du runner actif"));
  const QCommandLineOption ensureDockerOption(QStringLiteral("ensure-docker"),
                                              QStringLiteral("Démarre le profil Docker SITL local si nécessaire"));
  for (const auto& option : {urlOption, runOption, modeOption, resultOption, altitudeOption, legOption, warmupOption,
                             hoverOption, timeoutOption}) {
    parser.addOption(option);
  }
  parser.addOption(stopOnlyOption);
  parser.addOption(ensureDockerOption);
  parser.process(application);
  if (!parser.isSet(urlOption)) {
    parser.showHelp(2);
  }
  QNetworkAccessManager manager;
  auto root = parser.value(urlOption);
  while (root.endsWith(QLatin1Char('/'))) {
    root.chop(1);
  }
  if (parser.isSet(stopOnlyOption)) {
    try {
      const auto status = requestJson(manager, QUrl(root + QStringLiteral("/api/run/stop")), QByteArrayLiteral("POST"), {});
      QTextStream(stdout) << QStringLiteral("PX4_RUNNER_STATE=%1\n").arg(status.value(QStringLiteral("state")).toString());
      return 0;
    } catch (const ContractError& error) {
      QTextStream(stderr) << QString::fromUtf8(error.what()) << QLatin1Char('\n');
      return 2;
    }
  }
  for (const auto& option : {runOption, modeOption, resultOption, altitudeOption, legOption, warmupOption,
                             hoverOption, timeoutOption}) {
    if (!parser.isSet(option)) {
      parser.showHelp(2);
    }
  }
  const auto mode = parser.value(modeOption);
  if (mode != QStringLiteral("square") && mode != QStringLiteral("failsafe")) {
    QTextStream(stderr) << QStringLiteral("Mode PX4 non autorisé\n");
    return 2;
  }
  bool valuesValid = false;
  const auto number = [&](const QCommandLineOption& option) {
    const auto value = parser.value(option).toDouble(&valuesValid);
    if (!valuesValid || !std::isfinite(value)) {
      throw ContractError(QStringLiteral("Paramètre numérique PX4 invalide"));
    }
    return value;
  };

  std::signal(SIGINT, requestStop);
  std::signal(SIGTERM, requestStop);
  try {
    if (parser.isSet(ensureDockerOption)) {
      ensureDockerRunner(manager, root);
    }
    const auto payload = QJsonObject{
        {QStringLiteral("run_id"), parser.value(runOption)},
        {QStringLiteral("mode"), mode},
        {QStringLiteral("result_directory"), parser.value(resultOption)},
        {QStringLiteral("parameters"), QJsonObject{
             {QStringLiteral("takeoff_altitude_m"), number(altitudeOption)},
             {QStringLiteral("leg_m"), number(legOption)},
             {QStringLiteral("warmup_s"), number(warmupOption)},
             {QStringLiteral("hover_s"), number(hoverOption)},
             {QStringLiteral("stage_timeout_s"), number(timeoutOption)},
         }},
    };
    auto status = requestJson(manager, QUrl(root + QStringLiteral("/api/run/start")), QByteArrayLiteral("POST"), payload);
    QTextStream output(stdout);
    output << QStringLiteral("PX4_RUNNER_STARTED=%1\n").arg(parser.value(runOption));
    output.flush();
    qsizetype logCount = 0;
    bool stopSent = false;
    const QSet<QString> terminal{QStringLiteral("completed"), QStringLiteral("failed"), QStringLiteral("cancelled")};
    while (!terminal.contains(status.value(QStringLiteral("state")).toString())) {
      if (stopRequested.load() && !stopSent) {
        status = requestJson(manager, QUrl(root + QStringLiteral("/api/run/stop")), QByteArrayLiteral("POST"), {});
        stopSent = true;
      } else {
        QThread::msleep(500);
        status = requestJson(manager, QUrl(root + QStringLiteral("/api/run/status")));
      }
      const auto logs = status.value(QStringLiteral("logs")).toArray();
      if (logs.size() < logCount) {
        logCount = 0;
      }
      for (qsizetype index = logCount; index < logs.size(); ++index) {
        output << logs.at(index).toString() << QLatin1Char('\n');
      }
      logCount = logs.size();
      output.flush();
    }
    const auto state = status.value(QStringLiteral("state")).toString();
    output << QStringLiteral("PX4_RUNNER_STATE=%1\n").arg(state);
    output.flush();
    return stopSent || state == QStringLiteral("cancelled") ? 130 : state == QStringLiteral("completed") ? 0 : 1;
  } catch (const ContractError& error) {
    QTextStream(stderr) << QString::fromUtf8(error.what()) << QLatin1Char('\n');
    return 2;
  }
}
