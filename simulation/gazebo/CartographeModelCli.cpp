#include "ModelBuilder.hpp"
#include "SnapshotPaths.hpp"
#include "drone_agricole/adapters/LocalGazeboExportBackend.hpp"

#include <QCoreApplication>
#include <QCryptographicHash>
#include <QFile>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QProcess>
#include <iostream>

namespace {
const auto cad = QStringLiteral("hardware/mecanique/cartographe/");
const auto model = QStringLiteral("simulation/gazebo/models/cartographe/");
const auto airframe = QStringLiteral("simulation/px4_sitl/airframes/40000_gz_cartographe");

QString digest(const QByteArray& data) {
  return QString::fromLatin1(QCryptographicHash::hash(data, QCryptographicHash::Sha256).toHex());
}

QJsonObject readObject(const QString& path) {
  QFile file(path);
  if (!file.open(QIODevice::ReadOnly)) {
    throw std::runtime_error(QStringLiteral("Fichier illisible : %1").arg(path).toStdString());
  }
  const auto object = QJsonDocument::fromJson(file.readAll());
  if (!object.isObject()) {
    throw std::runtime_error(QStringLiteral("JSON invalide : %1").arg(path).toStdString());
  }
  return object.object();
}

QJsonObject auditLink(const QString& root, const QString& source, const QString& consumer,
                      const QJsonValue& expected = QJsonValue()) {
  using cartographe::gazebo::snapshotPath;
  QJsonObject result{{"source", source}, {"consumer", consumer}, {"expected_sha256", expected}};
  QString path;
  try {
    path = snapshotPath(root, source);
  } catch (const std::exception&) {
    result.insert("status", "NON_CANONICAL_PATH");
    return result;
  }
  if (!QFileInfo::exists(path)) {
    result.insert("status", "MISSING");
    result.insert("observed_sha256", QJsonValue::Null);
    return result;
  }
  result.insert("canonical_path_relative_to_workspace", QDir(root).relativeFilePath(QFileInfo(path).canonicalFilePath()));
  QFile file(path);
  QCryptographicHash hash(QCryptographicHash::Sha256);
  if (!file.open(QIODevice::ReadOnly) || !hash.addData(&file)) {
    result.insert("status", "UNREADABLE");
    return result;
  }
  const auto observed = QString::fromLatin1(hash.result().toHex());
  result.insert("observed_sha256", observed);
  result.insert("bytes", file.size());
  if (!expected.isString()) {
    result.insert("status", "OBSERVED");
  } else if (observed == expected.toString()) {
    result.insert("status", "MATCH");
  } else {
    result.insert("status", "STALE");
    if (source.endsWith(QStringLiteral(".json")) && file.seek(0)) {
      const auto lf = file.readAll().replace("\r\n", "\n");
      const auto crlf = QByteArray(lf).replace("\n", "\r\n");
      const auto lfSha = digest(lf);
      const auto crlfSha = digest(crlf);
      const bool eolOnly = expected == lfSha || expected == crlfSha;
      result.insert("eol_diagnostic", QJsonObject{{"lf_sha256", lfSha}, {"crlf_sha256", crlfSha},
                    {"matches_expected_after_eol_conversion", eolOnly}});
      if (eolOnly) {
        result.insert("status", "STALE_EOL_ONLY");
      }
    }
  }
  return result;
}

QJsonObject diagnose(const QString& root, const QString& python) {
  using cartographe::gazebo::snapshotPath;
  const auto geometryPath = model + QStringLiteral("geometry/geometry_manifest.json");
  const auto collisionPath = model + QStringLiteral("geometry/collision_model.json");
  const auto historicalPath = model + QStringLiteral("model_manifest.json");
  const auto geometryManifest = readObject(snapshotPath(root, geometryPath));
  const auto collision = readObject(snapshotPath(root, collisionPath));
  const auto historical = readObject(snapshotPath(root, historicalPath));
  const auto sources = geometryManifest.value("sources").toObject();
  const auto geometry = geometryManifest.value("geometry").toObject();
  QJsonArray links;
  links.append(auditLink(root, cad + "manifest.json", geometryPath, sources.value("cad_manifest_sha256")));
  links.append(auditLink(root, cad + "nomenclature_prototype.json", geometryPath, sources.value("bom_sha256")));
  links.append(auditLink(root, cad + "verification/read_brep_prototype.py", geometryPath, sources.value("saved_brep_reader_sha256")));
  links.append(auditLink(root, "simulation/gazebo/tools/cad_export_cartographe.py", geometryPath, sources.value("export_adapter_sha256")));
  links.append(auditLink(root, "simulation/gazebo/tools/cad_export_collisions.py", collisionPath, collision.value("adapter_sha256")));
  const auto dependencies = sources.value("dependencies_relative_to_cad_directory").toObject();
  QJsonObject dependencyStatuses;
  for (auto source = dependencies.begin(); source != dependencies.end(); ++source) {
    const auto link = auditLink(root, cad + source.key(), geometryPath, source.value());
    const auto status = link.value("status").toString();
    dependencyStatuses.insert(status, dependencyStatuses.value(status).toInt() + 1);
    links.append(link);
  }
  const auto body = geometry.value("body_mesh").toObject();
  links.append(auditLink(root, model + body.value("path").toString(), geometryPath, body.value("sha256")));
  for (const auto& entry : geometry.value("rotors").toArray()) {
    const auto rotor = entry.toObject();
    links.append(auditLink(root, model + rotor.value("mesh").toString(), geometryPath, rotor.value("sha256")));
  }
  links.append(auditLink(root, geometryPath, collisionPath, collision.value("geometry_manifest_sha256")));
  links.append(auditLink(root, historicalPath, "ORCH-GZ-1"));
  links.append(auditLink(root, model + "model.config", historicalPath));
  const auto historicalHashes = historical.value("files_sha256").toObject();
  for (const auto& path : {geometryPath, collisionPath, model + "geometry/mass_ledger.json",
                          model + "dynamics_preview.json", model + "model.sdf",
                          QStringLiteral("simulation/gazebo/worlds/cartographe_flat.sdf"), airframe}) {
    links.append(auditLink(root, path, historicalPath, historicalHashes.value(path)));
  }
  QJsonObject environment{{"active_generator_qt", QString::fromLatin1(qVersion())},
                          {"historical_freecad", geometryManifest.value("versions")},
                          {"freecad_probe", "NOT_RUN"}};
  if (!python.isEmpty()) {
    QProcess process;
    process.start(python, {"-B", "-c", "import FreeCAD as A, MeshPart, Part, json, sys; print(json.dumps(dict(freecad=A.Version(), occt=Part.OCC_VERSION, python=sys.version)))"});
    if (process.waitForStarted(5000) && process.waitForFinished(15000) &&
        process.exitStatus() == QProcess::NormalExit && process.exitCode() == 0) {
      const auto versions = QJsonDocument::fromJson(process.readAllStandardOutput().trimmed()).object();
      environment.insert("freecad_probe", versions.isEmpty() ? "UNREADABLE" : "AVAILABLE");
      environment.insert("available_freecad", versions);
    } else {
      if (process.state() != QProcess::NotRunning) {
        process.kill();
        process.waitForFinished(3000);
      }
      environment.insert("freecad_probe", "UNAVAILABLE");
    }
  }
  const auto cadStatus = links.first().toObject().value("status");
  return {{"schema", "drone_agricole.gazebo_snapshot_diagnosis.v1"},
          {"profile", "ORCH-GZ-1"}, {"canonical_root", "."},
          {"cad_manifest_status", cadStatus}, {"dependency_status_counts", dependencyStatuses},
          {"environment", environment}, {"links", links}};
}

void printJson(const QJsonObject& object) {
  std::cout << QJsonDocument(object).toJson(QJsonDocument::Indented).constData();
}
}

int main(int argc, char** argv) {
  QCoreApplication app(argc, argv);
  const auto args = app.arguments();
  using namespace cartographe::gazebo;
  try {
    const auto command = args.value(1);
    if ((args.size() == 3 || args.size() == 4) && command == "diagnose") {
      const auto root = QFileInfo(args[2]).canonicalFilePath();
      printJson(diagnose(root, args.value(3)));
      return 0;
    }
    if (args.size() == 5 && command == "rebuild") {
      drone_agricole::adapters::LocalGazeboExportBackend backend(args[2]);
      drone_agricole::application::GazeboExportRequest request;
      request.pythonProgram = args[3];
      request.outputDirectory = args[4];
      const std::atomic_bool cancelled{false};
      auto result = backend.execute(request, cancelled, [](int percent, const QString& message) {
        std::cerr << percent << "% " << message.toStdString() << '\n';
      });
      result.remove("preview");
      printJson(result);
      return 0;
    }
    if ((args.size() == 4 || (args.size() == 5 && args[4] == "--physical")) && command == "verify") {
      const auto root = QFileInfo(args[2]).canonicalFilePath();
      verifyModel(root, snapshotPath(root, args[3]), args.size() == 5);
      return 0;
    }
    if (args.size() == 2 || (args.size() == 3 && args[2] == "--physical")) {
      const auto root = QFileInfo(args[1]).canonicalFilePath();
      const auto directory = snapshotPath(root, QString(model).chopped(1));
      if (args.size() == 3) {
        verifyModel(root, directory, true);
      } else {
        generateModel(root, directory, snapshotPath(root, airframe));
        std::cout << "Generated SDF preview, 4 motors, source hashes and inertia constraints checked. Physical fidelity unvalidated.\n";
      }
      return 0;
    }
    throw std::runtime_error(
      "usage: cartographe-model WORKSPACE [--physical]\n"
      "       cartographe-model diagnose WORKSPACE [FREECAD_PYTHON]\n"
      "       cartographe-model rebuild WORKSPACE FREECAD_PYTHON DESTINATION\n"
      "       cartographe-model verify WORKSPACE MODEL_DIRECTORY [--physical]");
  } catch (const std::exception& error) {
    std::cerr << error.what() << '\n';
    return 1;
  }
}
