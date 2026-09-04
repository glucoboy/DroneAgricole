#include "drone_agricole/ui/MainWindow.hpp"

#include <QApplication>
#include <QCommandLineOption>
#include <QCommandLineParser>
#include <QDir>
#include <QFileInfo>
#include <QMessageBox>
#include <QSurfaceFormat>
#include <QTimer>

namespace {

QString discoverWorkspace(QString start) {
  QDir directory(QFileInfo(std::move(start)).absoluteFilePath());
  while (directory.exists()) {
    if (QFileInfo(directory.filePath(QStringLiteral("configs/visualization/simulations"))).isDir() &&
        QFileInfo(directory.filePath(QStringLiteral("results"))).isDir()) {
      return directory.absolutePath();
    }
    if (!directory.cdUp()) {
      break;
    }
  }
  return {};
}

}  // namespace

int main(int argc, char* argv[]) {
  QSurfaceFormat format;
  format.setSamples(4);
  QSurfaceFormat::setDefaultFormat(format);
  QApplication application(argc, argv);
  QApplication::setApplicationName(QStringLiteral("Drone Agricole Dashboard"));
  QApplication::setOrganizationName(QStringLiteral("Drone Agricole"));
  QApplication::setApplicationVersion(QStringLiteral(DRONE_AGRICOLE_VERSION));
  QApplication::setStyle(QStringLiteral("Fusion"));

  QCommandLineParser parser;
  parser.setApplicationDescription(QStringLiteral("Station de mission desktop C++17 / Qt 6 du projet Drone Agricole"));
  parser.addHelpOption();
  parser.addVersionOption();
  const QCommandLineOption workspaceOption({QStringLiteral("w"), QStringLiteral("workspace")},
                                           QStringLiteral("Racine du workspace"), QStringLiteral("path"));
  const QCommandLineOption smokeOption(QStringLiteral("smoke-test-ms"),
                                       QStringLiteral("Ferme automatiquement l'application après ce délai de test"),
                                       QStringLiteral("ms"));
  const QCommandLineOption screenshotOption(QStringLiteral("screenshot"),
                                            QStringLiteral("Enregistre une capture de validation puis ferme l'application"),
                                            QStringLiteral("path"));
  parser.addOption(workspaceOption);
  parser.addOption(smokeOption);
  parser.addOption(screenshotOption);
  parser.process(application);
  auto workspace = parser.value(workspaceOption);
  if (workspace.isEmpty()) {
    workspace = discoverWorkspace(QDir::currentPath());
  }
  if (workspace.isEmpty()) {
    QMessageBox::critical(nullptr, QStringLiteral("Workspace introuvable"),
                          QStringLiteral("Lancez l'application depuis le projet ou utilisez --workspace."));
    return 2;
  }
  drone_agricole::ui::MainWindow window(workspace);
  window.show();
  if (parser.isSet(screenshotOption)) {
    const auto screenshotPath = QFileInfo(parser.value(screenshotOption)).absoluteFilePath();
    QTimer::singleShot(1000, &application, [&application, &window, screenshotPath] {
      application.exit(window.grab().save(screenshotPath, "PNG") ? 0 : 3);
    });
  }
  if (parser.isSet(smokeOption)) {
    bool valid = false;
    const auto delay = parser.value(smokeOption).toInt(&valid);
    if (!valid || delay < 0 || delay > 60000) {
      return 2;
    }
    QTimer::singleShot(delay, &application, &QCoreApplication::quit);
  }
  return application.exec();
}
