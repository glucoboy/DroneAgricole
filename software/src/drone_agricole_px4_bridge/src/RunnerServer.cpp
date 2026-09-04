#include "drone_agricole_px4_bridge/RunnerContract.hpp"

#include <QCommandLineOption>
#include <QCommandLineParser>
#include <QCoreApplication>
#include <QDateTime>
#include <QDir>
#include <QFile>
#include <QHostAddress>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QProcess>
#include <QProcessEnvironment>
#include <QTcpServer>
#include <QTcpSocket>
#include <QTimer>

#include <deque>
#include <stdexcept>

namespace drone_agricole::px4 {
namespace {

QByteArray reasonPhrase(const int status) {
  switch (status) {
    case 200:
      return "OK";
    case 202:
      return "Accepted";
    case 400:
      return "Bad Request";
    case 404:
      return "Not Found";
    case 409:
      return "Conflict";
    default:
      return "Internal Server Error";
  }
}

class RunManager final : public QObject {
 public:
  explicit RunManager(QString workspace, QObject* parent = nullptr)
      : QObject(parent), workspace_(QFileInfo(std::move(workspace)).absoluteFilePath()) {
    current_ = {{QStringLiteral("state"), QStringLiteral("idle")},
                {QStringLiteral("message"), QStringLiteral("Runner PX4 SITL C++ prêt.")}};
    connect(&process_, &QProcess::readyReadStandardOutput, this, [this] {
      const auto lines = process_.readAllStandardOutput().split('\n');
      for (const auto& line : lines) {
        const auto trimmed = QString::fromUtf8(line).trimmed();
        if (!trimmed.isEmpty()) {
          logs_.push_back(trimmed);
          while (logs_.size() > 120) {
            logs_.pop_front();
          }
        }
      }
    });
    connect(&process_, qOverload<int, QProcess::ExitStatus>(&QProcess::finished), this,
            [this](const int exitCode, QProcess::ExitStatus) { processFinished(exitCode); });
  }

  QJsonObject status() const {
    auto result = current_;
    QJsonArray logs;
    const auto first = logs_.size() > 20 ? logs_.size() - 20 : 0;
    for (std::size_t index = first; index < logs_.size(); ++index) {
      logs.append(logs_[index]);
    }
    result.insert(QStringLiteral("logs"), logs);
    return result;
  }

  QJsonObject start(const QJsonObject& payload) {
    if (process_.state() != QProcess::NotRunning) {
      throw std::runtime_error("Un essai PX4 est déjà actif.");
    }
    const auto request = validateStartPayload(payload, workspace_);
    if (qEnvironmentVariable("DRONE_AGRICOLE_SITL") != QStringLiteral("1")) {
      throw std::runtime_error("Le verrou d'environnement SITL n'est pas actif.");
    }
    const auto parameters = request.value(QStringLiteral("parameters")).toObject();
    QStringList arguments{QStringLiteral("ros2"),
                          QStringLiteral("run"),
                          QStringLiteral("drone_agricole_px4_bridge"),
                          QStringLiteral("offboard_test"),
                          QStringLiteral("--ros-args"),
                          QStringLiteral("-p"),
                          QStringLiteral("execute:=true"),
                          QStringLiteral("-p"),
                          QStringLiteral("mission_mode:=%1").arg(request.value(QStringLiteral("mode")).toString())};
    for (const auto& name : {QStringLiteral("takeoff_altitude_m"), QStringLiteral("leg_m"),
                             QStringLiteral("warmup_s"), QStringLiteral("hover_s"),
                             QStringLiteral("stage_timeout_s")}) {
      arguments << QStringLiteral("-p")
                 << QStringLiteral("%1:=%2").arg(name, rosDoubleParameterValue(parameters.value(name).toDouble()));
    }
    arguments << QStringLiteral("-p")
              << QStringLiteral("result_directory:=%1").arg(request.value(QStringLiteral("result_directory")).toString());
    logs_.clear();
    stopRequested_ = false;
    current_ = {{QStringLiteral("state"), QStringLiteral("starting")},
                {QStringLiteral("run_id"), request.value(QStringLiteral("run_id"))},
                {QStringLiteral("mode"), request.value(QStringLiteral("mode"))},
                {QStringLiteral("parameters"), parameters},
                {QStringLiteral("result_directory"), request.value(QStringLiteral("result_directory"))},
                {QStringLiteral("started_at"), QDateTime::currentDateTimeUtc().toString(Qt::ISODateWithMs)},
                {QStringLiteral("finished_at"), QJsonValue()},
                {QStringLiteral("exit_code"), QJsonValue()},
                {QStringLiteral("message"), QStringLiteral("Démarrage du scénario PX4 SITL…")}};
    process_.setWorkingDirectory(workspace_);
    process_.setProcessChannelMode(QProcess::MergedChannels);
    process_.setProcessEnvironment(QProcessEnvironment::systemEnvironment());
    process_.start(QStringLiteral("/usr/bin/setsid"), arguments);
    if (!process_.waitForStarted(5000)) {
      current_.insert(QStringLiteral("state"), QStringLiteral("failed"));
      current_.insert(QStringLiteral("message"), QStringLiteral("Le processus PX4 n'a pas démarré."));
      throw std::runtime_error(process_.errorString().toStdString());
    }
    current_.insert(QStringLiteral("state"), QStringLiteral("running"));
    current_.insert(QStringLiteral("message"), QStringLiteral("Scénario PX4 SITL en cours."));
    return status();
  }

  QJsonObject stop() {
    if (process_.state() == QProcess::NotRunning) {
      throw std::runtime_error("Aucun essai PX4 n'est actif.");
    }
    stopRequested_ = true;
    current_.insert(QStringLiteral("state"), QStringLiteral("stopping"));
    current_.insert(QStringLiteral("message"), QStringLiteral("Arrêt sûr PX4 en cours…"));
    const auto processGroup = QStringLiteral("-%1").arg(process_.processId());
    QProcess::execute(QStringLiteral("/usr/bin/kill"), {QStringLiteral("-INT"), QStringLiteral("--"), processGroup});
    QTimer::singleShot(std::chrono::seconds(20), this, [this] {
      if (process_.state() != QProcess::NotRunning) {
        const auto processGroup = QStringLiteral("-%1").arg(process_.processId());
        QProcess::execute(QStringLiteral("/usr/bin/kill"),
                          {QStringLiteral("-TERM"), QStringLiteral("--"), processGroup});
      }
    });
    return status();
  }

 private:
  void processFinished(const int exitCode) {
    QJsonValue result;
    const auto resultDirectory = current_.value(QStringLiteral("result_directory")).toString();
    QFile file(QDir(workspace_).filePath(resultDirectory + QStringLiteral("/result.json")));
    if (file.open(QIODevice::ReadOnly)) {
      const auto document = QJsonDocument::fromJson(file.readAll());
      if (document.isObject()) {
        result = document.object();
      } else {
        logs_.push_back(QStringLiteral("Le fichier result.json est illisible."));
      }
    }
    QString state;
    QString message;
    if (stopRequested_) {
      state = QStringLiteral("cancelled");
      message = QStringLiteral("Essai PX4 arrêté ; l'atterrissage de sécurité a été demandé.");
    } else if (exitCode == 0 && result.isObject() && result.toObject().value(QStringLiteral("success")).toBool()) {
      state = QStringLiteral("completed");
      message = QStringLiteral("Essai PX4 SITL terminé avec succès.");
    } else {
      state = QStringLiteral("failed");
      message = QStringLiteral("Essai PX4 en échec avec le code %1.").arg(exitCode);
    }
    current_.insert(QStringLiteral("state"), state);
    current_.insert(QStringLiteral("message"), message);
    current_.insert(QStringLiteral("finished_at"), QDateTime::currentDateTimeUtc().toString(Qt::ISODateWithMs));
    current_.insert(QStringLiteral("exit_code"), exitCode);
    current_.insert(QStringLiteral("result"), result);
  }

  QString workspace_;
  QProcess process_;
  std::deque<QString> logs_;
  QJsonObject current_;
  bool stopRequested_{false};
};

class HttpServer final : public QObject {
 public:
  HttpServer(const QHostAddress& address, const quint16 port, QString workspace, QObject* parent = nullptr)
      : QObject(parent), manager_(std::move(workspace), this) {
    connect(&server_, &QTcpServer::newConnection, this, [this] {
      while (auto* socket = server_.nextPendingConnection()) {
        buffers_.insert(socket, {});
        connect(socket, &QTcpSocket::readyRead, this, [this, socket] {
          buffers_[socket].append(socket->readAll());
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
    const auto& data = buffers_[socket];
    const auto headerEnd = data.indexOf("\r\n\r\n");
    if (headerEnd < 0) {
      return;
    }
    const auto header = data.left(headerEnd);
    const auto lines = header.split('\n');
    if (lines.isEmpty()) {
      respond(socket, 400, {{QStringLiteral("error"), QStringLiteral("Requête HTTP invalide.")}});
      return;
    }
    const auto requestParts = lines.first().trimmed().split(' ');
    if (requestParts.size() < 2) {
      respond(socket, 400, {{QStringLiteral("error"), QStringLiteral("Ligne HTTP invalide.")}});
      return;
    }
    int contentLength = 0;
    for (const auto& line : lines) {
      if (line.toLower().startsWith("content-length:")) {
        contentLength = line.mid(line.indexOf(':') + 1).trimmed().toInt();
      }
    }
    if (data.size() < headerEnd + 4 + contentLength) {
      return;
    }
    const auto method = requestParts[0];
    const auto path = requestParts[1];
    const auto body = data.mid(headerEnd + 4, contentLength);
    try {
      if (method == "GET" && path == "/api/health") {
        respond(socket, 200,
                {{QStringLiteral("status"), QStringLiteral("ok")},
                 {QStringLiteral("sitl_locked"), qEnvironmentVariable("DRONE_AGRICOLE_SITL") == QStringLiteral("1")},
                 {QStringLiteral("run"), manager_.status()}});
      } else if (method == "GET" && path == "/api/run/status") {
        respond(socket, 200, manager_.status());
      } else if (method == "POST" && path == "/api/run/start") {
        QJsonParseError error;
        const auto document = QJsonDocument::fromJson(body, &error);
        if (!document.isObject()) {
          throw RunnerContractError(QStringLiteral("La requête doit être un objet JSON."));
        }
        respond(socket, 202, manager_.start(document.object()));
      } else if (method == "POST" && path == "/api/run/stop") {
        respond(socket, 200, manager_.stop());
      } else {
        respond(socket, 404, {{QStringLiteral("error"), QStringLiteral("Route inconnue.")}});
      }
    } catch (const RunnerContractError& error) {
      respond(socket, 400, {{QStringLiteral("error"), QString::fromUtf8(error.what())}});
    } catch (const std::exception& error) {
      respond(socket, 409, {{QStringLiteral("error"), QString::fromUtf8(error.what())}});
    }
  }

  void respond(QTcpSocket* socket, const int status, const QJsonObject& payload) {
    const auto body = QJsonDocument(payload).toJson(QJsonDocument::Compact);
    QByteArray response = "HTTP/1.1 " + QByteArray::number(status) + ' ' + reasonPhrase(status) + "\r\n";
    response += "Content-Type: application/json; charset=utf-8\r\n";
    response += "Content-Length: " + QByteArray::number(body.size()) + "\r\n";
    response += "Connection: close\r\n\r\n";
    response += body;
    socket->write(response);
    socket->disconnectFromHost();
  }

  QTcpServer server_;
  QHash<QTcpSocket*, QByteArray> buffers_;
  RunManager manager_;
};

}  // namespace
}  // namespace drone_agricole::px4

int main(int argc, char** argv) {
  QCoreApplication application(argc, argv);
  QCommandLineParser parser;
  parser.addHelpOption();
  QCommandLineOption hostOption(QStringLiteral("host"), QStringLiteral("Adresse d'écoute."),
                                QStringLiteral("adresse"), QStringLiteral("0.0.0.0"));
  QCommandLineOption portOption(QStringLiteral("port"), QStringLiteral("Port d'écoute."),
                                QStringLiteral("port"), QStringLiteral("8091"));
  QCommandLineOption workspaceOption(QStringLiteral("workspace"), QStringLiteral("Racine du projet."),
                                     QStringLiteral("chemin"), QDir::currentPath());
  parser.addOptions({hostOption, portOption, workspaceOption});
  parser.process(application);
  bool portValid = false;
  const auto port = parser.value(portOption).toUShort(&portValid);
  if (!portValid) {
    return 2;
  }
  try {
    drone_agricole::px4::HttpServer server(QHostAddress(parser.value(hostOption)), port,
                                           parser.value(workspaceOption));
    return application.exec();
  } catch (const std::exception& error) {
    qCritical("Runner PX4 indisponible : %s", error.what());
    return 1;
  }
}
