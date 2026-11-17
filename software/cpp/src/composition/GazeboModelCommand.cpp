#include "drone_agricole/composition/StationCommand.hpp"
#include "drone_agricole/adapters/LocalGazeboExportBackend.hpp"
#include <QDir>
#include <QEventLoop>
#include <QJsonDocument>
#include <QTextStream>
#include <QTimer>
#include <csignal>
#include <stdexcept>
namespace drone_agricole::composition {
namespace { volatile std::sig_atomic_t exportInterrupted=0;void interruptExport(int){exportInterrupted=1;} }
int runGazeboModelCommand(const QJsonObject& options) {
  adapters::LocalGazeboExportBackend backend(options.value(QStringLiteral("workspace")).toString(QDir::currentPath()));
  application::GazeboExportService exporter(backend);
  const auto action=options.value(QStringLiteral("action")).toString(QStringLiteral("inspect"));
  if(action==QStringLiteral("inspect")) {
    auto info=exporter.inspect();info.remove(QStringLiteral("preview"));
    QTextStream(stdout)<<QJsonDocument(info).toJson(QJsonDocument::Indented);return 0;
  }
  if(action!=QStringLiteral("export"))throw std::runtime_error("Action gazebo-model inconnue");
  application::GazeboExportRequest request;
  request.pythonProgram=options.value(QStringLiteral("python")).toString();
  request.outputDirectory=options.value(QStringLiteral("output")).toString();
  request.regenerateMeshes=!options.value(QStringLiteral("reuse-meshes")).toBool();
  QEventLoop loop;
  QObject::connect(&exporter,&application::GazeboExportService::completed,&loop,&QEventLoop::quit);
  QObject::connect(&exporter,&application::GazeboExportService::output,&loop,[](const QString& text){QTextStream(stderr)<<text<<Qt::endl;});
  exportInterrupted=0;auto previousInt=std::signal(SIGINT,interruptExport);auto previousTerm=std::signal(SIGTERM,interruptExport);
  QTimer timer;QObject::connect(&timer,&QTimer::timeout,&loop,[&]{if(exportInterrupted)exporter.cancel();});timer.start(100);
  if(options.contains(QStringLiteral("cancel-after-ms")))QTimer::singleShot(options.value(QStringLiteral("cancel-after-ms")).toInt(),&exporter,&application::GazeboExportService::cancel);
  exporter.start(request);if(exporter.active())loop.exec();
  std::signal(SIGINT,previousInt);std::signal(SIGTERM,previousTerm);
  auto result=exporter.result();result.remove(QStringLiteral("preview"));
  if(!result.isEmpty())QTextStream(stdout)<<QJsonDocument(result).toJson(QJsonDocument::Indented);
  else QTextStream(stderr)<<exporter.message()<<Qt::endl;
  return exporter.state()==QStringLiteral("completed")?0:exporter.state()==QStringLiteral("cancelled")?130:1;
}
}
