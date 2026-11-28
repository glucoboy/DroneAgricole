#include "drone_agricole/adapters/LocalGazeboExportBackend.hpp"
#include <QCoreApplication>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <iostream>

int main(int argc, char** argv) {
  QCoreApplication app(argc, argv);
  if (app.arguments().size() != 2) {
    return 2;
  }
  const auto root = app.arguments()[1];
  const auto destination = QStringLiteral(".runtime/changed/cartographe");
  drone_agricole::adapters::LocalGazeboExportBackend backend(root);
  drone_agricole::application::GazeboExportRequest request;
  request.regenerateMeshes = false;
  request.outputDirectory = destination;
  bool changed = false;
  try {
    const std::atomic_bool cancelled{false};
    backend.execute(request, cancelled, [&](int percent, const QString&) {
      if (percent == 95) {
        QFile source(root + QStringLiteral("/simulation/gazebo/worlds/cartographe_flat.sdf"));
        changed = source.open(QIODevice::WriteOnly | QIODevice::Append) && source.write("\n", 1) == 1;
      }
    });
  } catch (const std::exception& error) {
    const auto message = QString::fromUtf8(error.what());
    const auto stage = QDir(root + QStringLiteral("/results/simulation/model_exports"));
    if (changed && message.startsWith(QStringLiteral("STALE_SOURCE_DURING_EXPORT:")) &&
        !QFileInfo::exists(QDir(root).filePath(destination)) &&
        stage.entryList({QStringLiteral(".prepare-*")}, QDir::Dirs | QDir::Hidden).isEmpty()) {
      std::cout << error.what() << '\n';
      return 0;
    }
    std::cerr << error.what() << '\n';
    return 1;
  }
  std::cerr << "A changed source was published\n";
  return 1;
}
