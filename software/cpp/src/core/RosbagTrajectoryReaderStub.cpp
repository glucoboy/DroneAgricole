#include "drone_agricole/core/RosbagTrajectoryReader.hpp"

#include "drone_agricole/core/JsonUtils.hpp"
#include "drone_agricole/core/TelemetryBridge.hpp"

#include <QDir>
#include <QEventLoop>
#include <QFileInfo>
#include <QJsonDocument>
#include <QJsonParseError>
#include <QNetworkAccessManager>
#include <QNetworkReply>
#include <QNetworkRequest>
#include <QTimer>
#include <QUrl>

namespace drone_agricole::core {
namespace {

constexpr qint64 maximumReplayBytes = 8LL * 1024LL * 1024LL;
constexpr int replayTimeoutMilliseconds = 60000;

QString telemetryRootUrl() {
  auto value = qEnvironmentVariable("DRONE_AGRICOLE_TELEMETRY_URL",
                                    QStringLiteral("http://127.0.0.1:8092"));
  while (value.endsWith(QLatin1Char('/'))) {
    value.chop(1);
  }
  return value;
}

QString portableBagPath(const QString& bagDirectory) {
  const auto path = QDir::cleanPath(QDir::fromNativeSeparators(QFileInfo(bagDirectory).absoluteFilePath()));
#ifdef Q_OS_WIN
  constexpr auto sensitivity = Qt::CaseInsensitive;
#else
  constexpr auto sensitivity = Qt::CaseSensitive;
#endif
  const auto marker = QStringLiteral("/results/");
  const auto index = path.lastIndexOf(marker, -1, sensitivity);
  if (index < 0) {
    throw ContractError(QStringLiteral("Le rosbag historique n'est pas situé dans le dossier results du projet."));
  }
  return path.mid(index + 1);
}

}  // namespace

ReplayData readLioTrajectory(const QString& bagDirectory, const QString& resultId) {
  QNetworkAccessManager manager;
  QNetworkRequest request(QUrl(telemetryRootUrl() + QStringLiteral("/api/replay")));
  request.setHeader(QNetworkRequest::ContentTypeHeader, QStringLiteral("application/json"));
  request.setRawHeader(QByteArrayLiteral("Accept"), QByteArrayLiteral("application/json"));
  request.setAttribute(QNetworkRequest::CacheLoadControlAttribute, QNetworkRequest::AlwaysNetwork);
  const QJsonObject requestPayload{
      {QStringLiteral("bag_directory"), portableBagPath(bagDirectory)},
      {QStringLiteral("result_id"), resultId},
  };

  QEventLoop loop;
  QTimer timeout;
  timeout.setSingleShot(true);
  auto* reply = manager.post(request, QJsonDocument(requestPayload).toJson(QJsonDocument::Compact));
  QObject::connect(reply, &QNetworkReply::finished, &loop, &QEventLoop::quit);
  QObject::connect(&timeout, &QTimer::timeout, &loop, &QEventLoop::quit);
  timeout.start(replayTimeoutMilliseconds);
  loop.exec();

  if (!timeout.isActive()) {
    reply->abort();
    throw ContractError(QStringLiteral("La relecture historique a dépassé 60 secondes."));
  }
  timeout.stop();
  const auto body = reply->readAll();
  if (body.size() > maximumReplayBytes) {
    throw ContractError(QStringLiteral("La réponse de relecture historique est trop volumineuse."));
  }

  QJsonParseError parseError;
  const auto document = QJsonDocument::fromJson(body, &parseError);
  const auto payload = document.isObject() ? document.object() : QJsonObject{};
  if (reply->error() != QNetworkReply::NoError) {
    const auto remoteError = payload.value(QStringLiteral("error")).toString();
    if (!remoteError.isEmpty()) {
      throw ContractError(QStringLiteral("Relecture historique refusée : %1").arg(remoteError));
    }
    throw ContractError(
        QStringLiteral("Pont C++ de relecture indisponible : %1. Lancez le service telemetry-bridge.")
            .arg(reply->errorString()));
  }
  if (parseError.error != QJsonParseError::NoError || !document.isObject()) {
    throw ContractError(QStringLiteral("Réponse invalide du pont C++ de relecture."));
  }
  return replayDataFromJson(payload);
}

}  // namespace drone_agricole::core
