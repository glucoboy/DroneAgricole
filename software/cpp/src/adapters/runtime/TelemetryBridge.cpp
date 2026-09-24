#include "drone_agricole/core/TelemetryBridge.hpp"

#include "drone_agricole/core/JsonUtils.hpp"
#include "drone_agricole/core/RosbagTrajectoryReader.hpp"

#include <QCoreApplication>
#include <QDateTime>
#include <QDir>
#include <QFileInfo>
#include <QHostAddress>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonParseError>
#include <QTcpServer>
#include <QTcpSocket>

#include <algorithm>
#include <cmath>
#include <stdexcept>

namespace drone_agricole::core {
namespace {

constexpr qsizetype maximumCloudPoints = 16000;
constexpr qsizetype maximumPathPoints = 2400;
constexpr qsizetype maximumReplayCurvePoints = 1000;
constexpr qsizetype maximumRequestBytes = 64 * 1024;

QJsonArray pointsToJson(const QList<QVector3D>& points, const qsizetype maximum) {
  QJsonArray result;
  if (points.isEmpty() || maximum <= 0) {
    return result;
  }
  const auto step = std::max<qsizetype>(1, (points.size() + maximum - 1) / maximum);
  for (qsizetype index = 0; index < points.size(); index += step) {
    const auto& point = points.at(index);
    if (std::isfinite(point.x()) && std::isfinite(point.y()) && std::isfinite(point.z())) {
      result.append(QJsonArray{point.x(), point.y(), point.z()});
    }
  }
  return result;
}

QList<QVector3D> pointsFromJson(const QJsonValue& value, const qsizetype maximum) {
  QList<QVector3D> result;
  const auto values = value.toArray();
  result.reserve(std::min(values.size(), maximum));
  for (const auto& pointValue : values) {
    if (result.size() >= maximum) {
      break;
    }
    const auto point = pointValue.toArray();
    if (point.size() != 3 || !point.at(0).isDouble() || !point.at(1).isDouble() || !point.at(2).isDouble()) {
      continue;
    }
    const auto x = point.at(0).toDouble();
    const auto y = point.at(1).toDouble();
    const auto z = point.at(2).toDouble();
    if (std::isfinite(x) && std::isfinite(y) && std::isfinite(z)) {
      result.append(QVector3D(static_cast<float>(x), static_cast<float>(y), static_cast<float>(z)));
    }
  }
  return result;
}

QJsonArray curveToJson(const QList<QPointF>& curve) {
  QJsonArray result;
  const auto step = std::max<qsizetype>(1, (curve.size() + maximumReplayCurvePoints - 1) /
                                              maximumReplayCurvePoints);
  for (qsizetype index = 0; index < curve.size(); index += step) {
    const auto& point = curve.at(index);
    if (std::isfinite(point.x()) && std::isfinite(point.y())) {
      result.append(QJsonArray{point.x(), point.y()});
    }
  }
  return result;
}

QList<QPointF> curveFromJson(const QJsonValue& value) {
  QList<QPointF> result;
  const auto values = value.toArray();
  result.reserve(std::min(values.size(), maximumReplayCurvePoints));
  for (const auto& pointValue : values) {
    if (result.size() >= maximumReplayCurvePoints) {
      break;
    }
    const auto point = pointValue.toArray();
    if (point.size() != 2 || !point.at(0).isDouble() || !point.at(1).isDouble()) {
      continue;
    }
    const auto x = point.at(0).toDouble();
    const auto y = point.at(1).toDouble();
    if (std::isfinite(x) && std::isfinite(y)) {
      result.append(QPointF(x, y));
    }
  }
  return result;
}

#ifdef DRONE_AGRICOLE_WITH_ROS2
QString replayBagDirectory(const QString& relativePath) {
  if (relativePath.isEmpty() || QDir::isAbsolutePath(relativePath)) {
    throw ContractError(QStringLiteral("Le chemin du rosbag doit être relatif au workspace."));
  }
  const auto workspace = QDir::currentPath();
  const auto resultsRootInfo = QFileInfo(QDir(workspace).filePath(QStringLiteral("results")));
  const auto resultsRoot = resultsRootInfo.canonicalFilePath();
  if (resultsRoot.isEmpty() || !resultsRootInfo.isDir()) {
    throw ContractError(QStringLiteral("Le dossier results du workspace est introuvable."));
  }
  const auto lexicalCandidate = safeWorkspacePath(workspace, relativePath, QStringLiteral("bag_directory"));
  const QFileInfo candidateInfo(lexicalCandidate);
  const auto canonicalCandidate = candidateInfo.canonicalFilePath();
  if (canonicalCandidate.isEmpty() || !candidateInfo.isDir()) {
    throw ContractError(QStringLiteral("Le rosbag historique est introuvable."));
  }
  if (!pathIsInside(resultsRoot, canonicalCandidate)) {
    throw ContractError(QStringLiteral("Le rosbag historique doit rester dans le dossier results."));
  }
  return canonicalCandidate;
}

QByteArray reasonPhrase(const int status) {
  switch (status) {
    case 200:
      return QByteArrayLiteral("OK");
    case 400:
      return QByteArrayLiteral("Bad Request");
    case 404:
      return QByteArrayLiteral("Not Found");
    case 413:
      return QByteArrayLiteral("Payload Too Large");
    default:
      return QByteArrayLiteral("Conflict");
  }
}

class TelemetryHttpServer final : public QObject {
 public:
  TelemetryHttpServer(const QHostAddress& address, const quint16 port, QObject* parent = nullptr)
      : QObject(parent) {
    connect(&server_, &QTcpServer::newConnection, this, [this] {
      while (auto* socket = server_.nextPendingConnection()) {
        buffers_.insert(socket, {});
        connect(socket, &QTcpSocket::readyRead, this, [this, socket] {
          auto& buffer = buffers_[socket];
          buffer.append(socket->readAll());
          if (buffer.size() > maximumRequestBytes) {
            respond(socket, 413, {{QStringLiteral("error"), QStringLiteral("Requête trop volumineuse.")}});
            return;
          }
          processRequest(socket);
        });
        connect(socket, &QTcpSocket::disconnected, this, [this, socket] {
          buffers_.remove(socket);
          socket->deleteLater();
        });
      }
    });
    if (!server_.listen(address, port)) {
      throw std::runtime_error(server_.errorString().toStdString());
    }
  }

 private:
  void processRequest(QTcpSocket* socket) {
    const auto data = buffers_.value(socket);
    const auto headerEnd = data.indexOf("\r\n\r\n");
    if (headerEnd < 0) {
      return;
    }
    const auto lines = data.left(headerEnd).split('\n');
    const auto request = lines.isEmpty() ? QList<QByteArray>{} : lines.first().trimmed().split(' ');
    if (request.size() < 2) {
      respond(socket, 400, {{QStringLiteral("error"), QStringLiteral("Requête HTTP invalide.")}});
      return;
    }
    qint64 contentLength = 0;
    for (qsizetype index = 1; index < lines.size(); ++index) {
      const auto line = lines.at(index).trimmed();
      const auto separator = line.indexOf(':');
      if (separator < 0 || line.left(separator).trimmed().compare("Content-Length", Qt::CaseInsensitive) != 0) {
        continue;
      }
      bool valid = false;
      contentLength = line.mid(separator + 1).trimmed().toLongLong(&valid);
      if (!valid || contentLength < 0) {
        respond(socket, 400, {{QStringLiteral("error"), QStringLiteral("Content-Length invalide.")}});
        return;
      }
    }
    const auto completeSize = static_cast<qint64>(headerEnd) + 4 + contentLength;
    if (completeSize > maximumRequestBytes) {
      respond(socket, 413, {{QStringLiteral("error"), QStringLiteral("Requête trop volumineuse.")}});
      return;
    }
    if (data.size() < completeSize) {
      return;
    }
    const auto body = data.mid(headerEnd + 4, contentLength);
    auto path = request.at(1);
    if (const auto query = path.indexOf('?'); query >= 0) {
      path.truncate(query);
    }
    if (request.at(0) == "GET" && path == "/api/health") {
      respond(socket, 200,
              {{QStringLiteral("status"), QStringLiteral("ok")},
               {QStringLiteral("schema"), QStringLiteral("drone_agricole.telemetry_snapshot.v1")},
               {QStringLiteral("ros_domain_id"), qEnvironmentVariable("ROS_DOMAIN_ID", QStringLiteral("0"))}});
    } else if (request.at(0) == "GET" && path == "/api/snapshot") {
      respond(socket, 200, telemetrySnapshotToJson(telemetry_.snapshot()));
    } else if (request.at(0) == "POST" && path == "/api/reset") {
      telemetry_.reset();
      respond(socket, 200,
              {{QStringLiteral("status"), QStringLiteral("reset")},
               {QStringLiteral("timestamp_utc"), QDateTime::currentDateTimeUtc().toString(Qt::ISODateWithMs)}});
    } else if (request.at(0) == "POST" && path == "/api/replay") {
      QJsonParseError parseError;
      const auto document = QJsonDocument::fromJson(body, &parseError);
      if (parseError.error != QJsonParseError::NoError || !document.isObject()) {
        respond(socket, 400, {{QStringLiteral("error"), QStringLiteral("Corps JSON invalide.")}});
        return;
      }
      const auto payload = document.object();
      const auto bagDirectory = payload.value(QStringLiteral("bag_directory")).toString();
      const auto resultId = payload.value(QStringLiteral("result_id")).toString();
      if (bagDirectory.isEmpty() || resultId.isEmpty() || resultId.size() > 128) {
        respond(socket, 400,
                {{QStringLiteral("error"), QStringLiteral("bag_directory et result_id sont requis.")}});
        return;
      }
      try {
        respond(socket, 200, replayDataToJson(readLioTrajectory(replayBagDirectory(bagDirectory), resultId)));
      } catch (const std::exception& error) {
        respond(socket, 409, {{QStringLiteral("error"), QString::fromUtf8(error.what())}});
      }
    } else {
      respond(socket, 404, {{QStringLiteral("error"), QStringLiteral("Route inconnue.")}});
    }
  }

  void respond(QTcpSocket* socket, const int status, const QJsonObject& payload) {
    if (!buffers_.contains(socket)) {
      return;
    }
    buffers_.remove(socket);
    const auto body = QJsonDocument(payload).toJson(QJsonDocument::Compact);
    QByteArray response = "HTTP/1.1 " + QByteArray::number(status) + ' ' + reasonPhrase(status) + "\r\n";
    response += "Content-Type: application/json; charset=utf-8\r\n";
    response += "Cache-Control: no-store\r\n";
    response += "Content-Length: " + QByteArray::number(body.size()) + "\r\n";
    response += "Connection: close\r\n\r\n";
    response += body;
    socket->write(response);
    socket->disconnectFromHost();
  }

  LiveTelemetry telemetry_;
  QTcpServer server_;
  QHash<QTcpSocket*, QByteArray> buffers_;
};
#endif

}  // namespace

QJsonObject telemetrySnapshotToJson(const LiveTelemetrySnapshot& snapshot) {
  return {
      {QStringLiteral("schema"), QStringLiteral("drone_agricole.telemetry_snapshot.v1")},
      {QStringLiteral("timestamp_utc"), QDateTime::currentDateTimeUtc().toString(Qt::ISODateWithMs)},
      {QStringLiteral("available"), snapshot.available},
      {QStringLiteral("cloud"), pointsToJson(snapshot.cloud, maximumCloudPoints)},
      {QStringLiteral("estimate"), pointsToJson(snapshot.estimate, maximumPathPoints)},
      {QStringLiteral("truth"), pointsToJson(snapshot.truth, maximumPathPoints)},
      {QStringLiteral("px4_path"), pointsToJson(snapshot.px4Path, maximumPathPoints)},
      {QStringLiteral("metrics"), snapshot.metrics},
      {QStringLiteral("px4_state"), snapshot.px4State},
  };
}

LiveTelemetrySnapshot telemetrySnapshotFromJson(const QJsonObject& payload) {
  if (payload.value(QStringLiteral("schema")).toString() !=
      QStringLiteral("drone_agricole.telemetry_snapshot.v1")) {
    return {};
  }
  return LiveTelemetrySnapshot{
      payload.value(QStringLiteral("available")).toBool(),
      pointsFromJson(payload.value(QStringLiteral("cloud")), maximumCloudPoints),
      pointsFromJson(payload.value(QStringLiteral("estimate")), maximumPathPoints),
      pointsFromJson(payload.value(QStringLiteral("truth")), maximumPathPoints),
      pointsFromJson(payload.value(QStringLiteral("px4_path")), maximumPathPoints),
      payload.value(QStringLiteral("metrics")).toObject(),
      payload.value(QStringLiteral("px4_state")).toObject(),
  };
}

QJsonObject replayDataToJson(const ReplayData& replay) {
  QJsonArray notes;
  for (const auto& note : replay.notes) {
    notes.append(note);
  }
  return {
      {QStringLiteral("schema"), QStringLiteral("drone_agricole.replay.v1")},
      {QStringLiteral("result_id"), replay.resultId},
      {QStringLiteral("domain"), replay.domain},
      {QStringLiteral("estimate"), pointsToJson(replay.estimate, maximumPathPoints)},
      {QStringLiteral("truth"), pointsToJson(replay.truth, maximumPathPoints)},
      {QStringLiteral("px4_path"), pointsToJson(replay.px4Path, maximumPathPoints)},
      {QStringLiteral("curve"), curveToJson(replay.curve)},
      {QStringLiteral("curve_id"), replay.curveId},
      {QStringLiteral("curve_label"), replay.curveLabel},
      {QStringLiteral("curve_unit"), replay.curveUnit},
      {QStringLiteral("notes"), notes},
  };
}

ReplayData replayDataFromJson(const QJsonObject& payload) {
  requireSchema(payload, QStringLiteral("drone_agricole.replay.v1"), QStringLiteral("Relecture historique"));
  requireFields(payload, {QStringLiteral("result_id"), QStringLiteral("domain"), QStringLiteral("estimate"),
                          QStringLiteral("truth"), QStringLiteral("curve")},
                QStringLiteral("Relecture historique"));
  ReplayData replay;
  replay.resultId = payload.value(QStringLiteral("result_id")).toString();
  replay.domain = payload.value(QStringLiteral("domain")).toString();
  replay.estimate = pointsFromJson(payload.value(QStringLiteral("estimate")), maximumPathPoints);
  replay.truth = pointsFromJson(payload.value(QStringLiteral("truth")), maximumPathPoints);
  replay.px4Path = pointsFromJson(payload.value(QStringLiteral("px4_path")), maximumPathPoints);
  replay.curve = curveFromJson(payload.value(QStringLiteral("curve")));
  replay.curveId = payload.value(QStringLiteral("curve_id")).toString();
  replay.curveLabel = payload.value(QStringLiteral("curve_label")).toString();
  replay.curveUnit = payload.value(QStringLiteral("curve_unit")).toString();
  for (const auto& note : payload.value(QStringLiteral("notes")).toArray()) {
    if (note.isString()) {
      replay.notes.append(note.toString());
    }
  }
  if (replay.resultId.isEmpty() || replay.domain.isEmpty()) {
    throw ContractError(QStringLiteral("Relecture historique : identifiant ou domaine invalide"));
  }
  return replay;
}

int runTelemetryServer(const QJsonObject& options) {
#ifdef DRONE_AGRICOLE_WITH_ROS2
  const auto host = options.value(QStringLiteral("host")).toString(QStringLiteral("0.0.0.0"));
  const auto portValue = options.value(QStringLiteral("port")).toInt(8092);
  if (portValue < 1 || portValue > 65535) {
    throw ContractError(QStringLiteral("Port de télémétrie invalide"));
  }
  const QHostAddress address(host);
  if (address.isNull()) {
    throw ContractError(QStringLiteral("Adresse de télémétrie invalide : %1").arg(host));
  }
  TelemetryHttpServer server(address, static_cast<quint16>(portValue));
  return QCoreApplication::exec();
#else
  Q_UNUSED(options)
  throw ContractError(QStringLiteral("Le serveur de télémétrie requiert une construction ROS 2"));
#endif
}

}  // namespace drone_agricole::core
