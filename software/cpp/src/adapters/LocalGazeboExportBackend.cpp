#include "drone_agricole/adapters/LocalGazeboExportBackend.hpp"
#include "ModelBuilder.hpp"
#include <QCryptographicHash>
#include <QDateTime>
#include <QDir>
#include <QElapsedTimer>
#include <QFile>
#include <QFileInfo>
#include <QJsonArray>
#include <QJsonDocument>
#include <QLockFile>
#include <QProcess>
#include <QSaveFile>
#include <QStandardPaths>
#include <QTemporaryDir>
#include <QUuid>
#include <QXmlStreamReader>
#include <QXmlStreamWriter>
#include <QtEndian>
#include <cmath>
#include <cstring>
#include <stdexcept>

namespace drone_agricole::adapters {
namespace {
void require(bool condition,const QString& message) { if(!condition) throw std::runtime_error(message.toStdString()); }
QJsonObject read(const QString& path) {
  QFile f(path); require(f.open(QIODevice::ReadOnly),QStringLiteral("Fichier absent ou illisible : %1").arg(path));
  QJsonParseError error; auto doc=QJsonDocument::fromJson(f.readAll(),&error);
  require(error.error==QJsonParseError::NoError && doc.isObject(),QStringLiteral("JSON invalide : %1").arg(path)); return doc.object();
}
void write(const QString& path,const QJsonObject& object) {
  QSaveFile f(path); auto bytes=QJsonDocument(object).toJson(QJsonDocument::Indented);
  require(f.open(QIODevice::WriteOnly)&&f.write(bytes)==bytes.size()&&f.commit(),QStringLiteral("Écriture impossible : %1").arg(path));
}
QString confined(const QString& root,const QString& path) {
  auto absolute=QDir::cleanPath(QFileInfo(path).isAbsolute()?path:QDir(root).filePath(path));
  QString existing=absolute;
  while(!QFileInfo::exists(existing)) { auto parent=QFileInfo(existing).absolutePath(); require(parent!=existing,QStringLiteral("Chemin sans parent")); existing=parent; }
  const auto canonical=QFileInfo(existing).canonicalFilePath();
#ifdef Q_OS_WIN
  constexpr auto sensitivity=Qt::CaseInsensitive;
#else
  constexpr auto sensitivity=Qt::CaseSensitive;
#endif
  const auto inside=[&](const QString& p){return p.compare(root,sensitivity)==0||p.startsWith(root+QLatin1Char('/'),sensitivity);};
  require(inside(absolute)&&inside(canonical),QStringLiteral("Le chemin doit rester dans le projet : %1").arg(path)); return absolute;
}
QString findPython() {
  const auto configured=qEnvironmentVariable("DRONE_AGRICOLE_FREECAD_PYTHON"); if(!configured.isEmpty())return configured;
#ifdef Q_OS_WIN
  const auto base=qEnvironmentVariable("ProgramFiles",QStringLiteral("C:/Program Files"));
  const auto dirs=QDir(base).entryList({QStringLiteral("FreeCAD*")},QDir::Dirs|QDir::NoDotAndDotDot,QDir::Name|QDir::Reversed);
  for(const auto& d:dirs) { auto p=QDir(base).filePath(d+QStringLiteral("/bin/python.exe"));if(QFileInfo::exists(p))return p; }
#endif
  return QStandardPaths::findExecutable(QStringLiteral("python3"));
}
QString fileHash(const QString& path) {
  QFile file(path);require(file.open(QIODevice::ReadOnly),QStringLiteral("Source absente : %1").arg(path));
  QCryptographicHash hash(QCryptographicHash::Sha256);require(hash.addData(&file),QStringLiteral("Source illisible"));
  return QString::fromLatin1(hash.result().toHex());
}
}
LocalGazeboExportBackend::LocalGazeboExportBackend(QString workspace)
    :workspace_(QFileInfo(workspace).canonicalFilePath()) {}

QJsonObject LocalGazeboExportBackend::preview(const QString& directory) {
  const auto geometry=read(directory+QStringLiteral("/geometry/geometry_manifest.json")).value(QStringLiteral("geometry")).toObject();
  QJsonArray parts;auto body=geometry.value(QStringLiteral("body_mesh")).toObject();
  parts.append(QJsonObject{{QStringLiteral("path"),body.value(QStringLiteral("path"))},{QStringLiteral("position"),QJsonArray{0,0,0}}});
  for(const auto& r:geometry.value(QStringLiteral("rotors")).toArray()) {auto rotor=r.toObject();parts.append(QJsonObject{{QStringLiteral("path"),rotor.value(QStringLiteral("mesh"))},{QStringLiteral("position"),rotor.value(QStringLiteral("position_m"))}});}
  QJsonArray vertices,triangles,colors;int index=0;
  for(const auto& v:parts) {
    const auto part=v.toObject();const auto name=part.value(QStringLiteral("path")).toString();
    require(name.startsWith(QStringLiteral("meshes/"))&&!name.contains(QStringLiteral("..")),QStringLiteral("Chemin de maillage invalide"));
    QFile file(confined(QFileInfo(directory).canonicalFilePath(),directory+QLatin1Char('/')+name));
    require(file.open(QIODevice::ReadOnly),QStringLiteral("Maillage absent"));auto head=file.read(84);
    require(head.size()==84,QStringLiteral("En-tête STL incomplet"));const auto count=qFromLittleEndian<quint32>(reinterpret_cast<const uchar*>(head.constData()+80));
    require(count>0 && file.size()==84+qint64(count)*50,QStringLiteral("STL binaire invalide"));
    const quint32 limit=index==0?18000U:2000U;const quint32 stride=std::max(1U,(count+limit-1)/limit);
    const auto position=part.value(QStringLiteral("position")).toArray();require(position.size()==3,QStringLiteral("Repère absent"));
    for(quint32 i=0;i<count;i+=stride) {
      require(file.seek(84+qint64(i)*50),QStringLiteral("Lecture STL impossible"));auto record=file.read(50);require(record.size()==50,QStringLiteral("STL tronqué"));
      QJsonArray triangle;
      for(int vertex=0;vertex<3;++vertex) {QJsonArray point;for(int axis=0;axis<3;++axis) {
        quint32 raw=qFromLittleEndian<quint32>(reinterpret_cast<const uchar*>(record.constData()+12+12*vertex+4*axis));float number;std::memcpy(&number,&raw,4);
        require(std::isfinite(number),QStringLiteral("STL non fini"));point.append(double(number)+position[axis].toDouble());
      }triangle.append(vertices.size());vertices.append(point);}triangles.append(triangle);colors.append(index==0?QStringLiteral("#8295a6"):QStringLiteral("#168b7b"));
    }++index;
  }
  return {{QStringLiteral("vertices"),vertices},{QStringLiteral("triangles"),triangles},{QStringLiteral("colors"),colors},{QStringLiteral("units"),QStringLiteral("m")}};
}
QJsonObject LocalGazeboExportBackend::inspect() const {
  auto source=workspace_+QStringLiteral("/hardware/mecanique/cartographe/assemblages/Prototype_Cartographe.FCStd");
  auto model=workspace_+QStringLiteral("/simulation/gazebo/models/cartographe");
  QJsonObject info{{QStringLiteral("source"),source},{QStringLiteral("source_available"),QFileInfo::exists(source)},
    {QStringLiteral("python_program"),findPython()},{QStringLiteral("model_directory"),model},
    {QStringLiteral("preview_available"),QFileInfo::exists(model+QStringLiteral("/meshes/cartographe_body.stl"))},
    {QStringLiteral("profile"),QStringLiteral("Prototype cartographe · CAO active")},
    {QStringLiteral("physical_status"),QStringLiteral("À valider · scénario synthétique 6 kg, batterie non couplée")}};
  QDir exports(workspace_+QStringLiteral("/results/simulation/model_exports"));
  for(const auto& entry:exports.entryList(QDir::Dirs|QDir::NoDotAndDotDot,QDir::Time)) {
    const auto directory=exports.filePath(entry+QStringLiteral("/cartographe"));
    if(!QFileInfo::exists(directory+QStringLiteral("/export_manifest.json")))continue;
    try {
      const auto manifest=read(directory+QStringLiteral("/export_manifest.json"));
      if(!manifest.value(QStringLiteral("finalized")).toBool())continue;
      const auto path=confined(workspace_,directory+QStringLiteral("/preview.json"));
      QFile f(path);require(f.size()<16000000,QStringLiteral("Aperçu trop volumineux"));
      require(f.open(QIODevice::ReadOnly),QStringLiteral("Aperçu absent"));
      const auto actual=QString::fromLatin1(QCryptographicHash::hash(f.readAll(),QCryptographicHash::Sha256).toHex());
      require(actual==manifest.value(QStringLiteral("files_sha256")).toObject().value(QStringLiteral("preview.json")).toString(),QStringLiteral("Aperçu altéré"));
      const auto sources=manifest.value(QStringLiteral("sources_sha256")).toObject();
      bool current=!sources.isEmpty();
      for(auto i=sources.begin();i!=sources.end();++i) {
        try { current=current&&fileHash(confined(workspace_,i.key()))==i.value().toString(); }
        catch(const std::exception&) {current=false;}
      }
      info.insert(QStringLiteral("preview_stale"),!current);
      info.insert(QStringLiteral("preview_source_manifest_sha256"),sources.value(QStringLiteral("hardware/mecanique/cartographe/manifest.json")));
      info.insert(QStringLiteral("directory"),directory);info.insert(QStringLiteral("preview"),read(path));break;
    } catch(const std::exception&) { /* An incomplete package is not offered. */ }
  }
  return info;
}
QJsonObject LocalGazeboExportBackend::execute(const application::GazeboExportRequest& request,const std::atomic_bool& cancelled,Progress progress) {
  require(!workspace_.isEmpty(),QStringLiteral("Projet absent"));QElapsedTimer timer;timer.start();
  auto checkpoint=[&] {require(!cancelled.load(),QStringLiteral("Export annulé"));require(timer.elapsed()<900000,QStringLiteral("Budget total de 15 minutes dépassé"));};
  auto sha=[&](const QString& path) {QFile f(path);require(f.open(QIODevice::ReadOnly),QStringLiteral("Source absente : %1").arg(path));QCryptographicHash h(QCryptographicHash::Sha256);while(!f.atEnd()){checkpoint();auto b=f.read(1024*1024);require(!b.isEmpty()||f.atEnd(),QStringLiteral("Lecture impossible"));h.addData(b);}return QString::fromLatin1(h.result().toHex());};
  auto copy=[&](const QString& from,const QString& to) {QFile input(from);require(input.open(QIODevice::ReadOnly),QStringLiteral("Source absente : %1").arg(from));QDir().mkpath(QFileInfo(to).absolutePath());QSaveFile output(to);require(output.open(QIODevice::WriteOnly),QStringLiteral("Sortie inaccessible"));while(!input.atEnd()){checkpoint();auto b=input.read(1024*1024);require(!b.isEmpty()||input.atEnd(),QStringLiteral("Lecture impossible"));require(output.write(b)==b.size(),QStringLiteral("Copie impossible"));}require(output.commit(),QStringLiteral("Copie non finalisée"));};
  const auto destination=confined(workspace_,request.outputDirectory.isEmpty()?QStringLiteral("results/simulation/model_exports/%1/cartographe").arg(QDateTime::currentDateTimeUtc().toString(QStringLiteral("yyyyMMdd_HHmmss_"))+QUuid::createUuid().toString(QUuid::Id128).left(8)):request.outputDirectory);
  require(QFileInfo(destination).fileName()==QStringLiteral("cartographe"),QStringLiteral("Le dossier du modèle doit se nommer cartographe"));
  require(!QFileInfo::exists(destination),QStringLiteral("Le dossier existe déjà ; choisissez une nouvelle destination"));
  const auto exports=confined(workspace_,QStringLiteral("results/simulation/model_exports"));require(QDir().mkpath(exports),QStringLiteral("Dossier des exports inaccessible"));
  QLockFile lock(exports+QStringLiteral("/.export.lock"));lock.setStaleLockTime(0);
  require(lock.tryLock(0),QStringLiteral("Un autre export est déjà en cours"));
  QTemporaryDir staging(exports+QStringLiteral("/.prepare-XXXXXX"));require(staging.isValid(),QStringLiteral("Préparation inaccessible"));
  const auto model=staging.path()+QStringLiteral("/cartographe");QDir().mkpath(model);
  progress(2,QStringLiteral("Vérification des sources CAO"));
  const auto cad=workspace_+QStringLiteral("/hardware/mecanique/cartographe/");
  auto canonical=read(cad+QStringLiteral("manifest.json")).value(QStringLiteral("prototype_cartographe")).toObject();
  QJsonObject sources;const auto remember=[&](const QString& relative){auto path=confined(workspace_,relative);auto hash=sha(path);sources.insert(relative,hash);return hash;};
  remember(QStringLiteral("hardware/mecanique/cartographe/manifest.json"));remember(QStringLiteral("hardware/mecanique/cartographe/nomenclature_prototype.json"));
  for(const auto& key:{QStringLiteral("references"),QStringLiteral("assemblages")})for(const auto& value:canonical.value(key).toArray()) {
    auto row=value.toObject();auto relative=QStringLiteral("hardware/mecanique/cartographe/")+row.value(QStringLiteral("fichier")).toString();
    require(remember(relative)==row.value(QStringLiteral("sha256")).toString(),QStringLiteral("CAO modifiée sans mise à jour du manifeste : %1").arg(relative));
  }
  auto originals=canonical.value(QStringLiteral("sources_preservees")).toObject();for(auto i=originals.begin();i!=originals.end();++i)require(remember(QStringLiteral("hardware/mecanique/cartographe/")+i.key())==i.value().toString(),QStringLiteral("Source fabricant divergente"));
  const auto base=workspace_+QStringLiteral("/simulation/gazebo/models/cartographe");
  for(const auto& name:{QStringLiteral("dynamics_preview.json"),QStringLiteral("geometry/mass_ledger.json"),QStringLiteral("model.config")}){remember(QStringLiteral("simulation/gazebo/models/cartographe/")+name);copy(base+QLatin1Char('/')+name,model+QLatin1Char('/')+name);}
  for(const auto& script:{QStringLiteral("cad_export_cartographe.py"),QStringLiteral("cad_export_collisions.py")})remember(QStringLiteral("simulation/gazebo/tools/")+script);
  remember(QStringLiteral("hardware/mecanique/cartographe/verification/read_brep_prototype.py"));
  remember(QStringLiteral("simulation/gazebo/ModelBuilder.cpp"));remember(QStringLiteral("simulation/gazebo/ModelBuilder.hpp"));
  if(request.regenerateMeshes) {
    const auto python=request.pythonProgram.isEmpty()?findPython():request.pythonProgram;
    require(!python.isEmpty()&&QFileInfo::exists(python),QStringLiteral("Python de FreeCAD introuvable ; indiquez son exécutable"));
    for(const auto& script:{QStringLiteral("cad_export_cartographe.py"),QStringLiteral("cad_export_collisions.py")}) {
      progress(script.startsWith(QStringLiteral("cad_export_cartographe"))?10:65,script.startsWith(QStringLiteral("cad_export_cartographe"))?QStringLiteral("Conversion de la CAO en maillages…"):QStringLiteral("Préparation des collisions…"));
      QProcess process;process.setWorkingDirectory(workspace_);process.setProcessChannelMode(QProcess::MergedChannels);
      process.start(python,{workspace_+QStringLiteral("/simulation/gazebo/tools/")+script,QStringLiteral("--workspace"),workspace_,QStringLiteral("--output-dir"),model});
      require(process.waitForStarted(5000),QStringLiteral("FreeCAD ne démarre pas : %1").arg(process.errorString()));QByteArray output;
      while(!process.waitForFinished(100)) {
        output+=process.readAll();output=output.right(64000);
        if(cancelled||timer.elapsed()>=900000){process.kill();process.waitForFinished(3000);checkpoint();}
      }
      output+=process.readAll();require(process.exitStatus()==QProcess::NormalExit&&process.exitCode()==0,QStringLiteral("Échec FreeCAD : %1").arg(QString::fromUtf8(output.right(8000))));
    }
  } else {
    progress(15,QStringLiteral("Réutilisation des maillages vérifiés"));
    const auto g=read(base+QStringLiteral("/geometry/geometry_manifest.json"));
    const auto dep=g.value(QStringLiteral("sources")).toObject().value(QStringLiteral("dependencies_relative_to_cad_directory")).toObject();
    for(auto i=dep.begin();i!=dep.end();++i)require(sha(confined(workspace_,cad+i.key()))==i.value().toString(),QStringLiteral("Maillages périmés ; relancez depuis la CAO"));
    for(const auto& name:{QStringLiteral("geometry/geometry_manifest.json"),QStringLiteral("geometry/collision_model.json")}){remember(QStringLiteral("simulation/gazebo/models/cartographe/")+name);copy(base+QLatin1Char('/')+name,model+QLatin1Char('/')+name);}
    auto geometry=g.value(QStringLiteral("geometry")).toObject();QStringList meshes{geometry.value(QStringLiteral("body_mesh")).toObject().value(QStringLiteral("path")).toString()};
    for(const auto& rotor:geometry.value(QStringLiteral("rotors")).toArray())meshes.append(rotor.toObject().value(QStringLiteral("mesh")).toString());
    for(const auto& name:meshes){require(name.startsWith(QStringLiteral("meshes/"))&&!name.contains(QStringLiteral("..")),QStringLiteral("Maillage hors profil"));remember(QStringLiteral("simulation/gazebo/models/cartographe/")+name);copy(base+QLatin1Char('/')+name,model+QLatin1Char('/')+name);}
  }
  checkpoint();progress(80,QStringLiteral("Construction du véhicule SDF et de son airframe"));
  cartographe::gazebo::generateModel(workspace_,model,model+QStringLiteral("/40000_gz_cartographe"));
  const auto worldHash=remember(QStringLiteral("simulation/gazebo/worlds/cartographe_flat.sdf"));
  copy(workspace_+QStringLiteral("/simulation/gazebo/worlds/cartographe_flat.sdf"),model+QStringLiteral("/cartographe_flat.sdf"));
  require(sha(model+QStringLiteral("/cartographe_flat.sdf"))==worldHash,QStringLiteral("Monde modifié pendant sa copie"));
  QFile worldFile(model+QStringLiteral("/cartographe_flat.sdf"));require(worldFile.open(QIODevice::ReadOnly),QStringLiteral("Monde absent"));
  QByteArray previewWorld;QXmlStreamReader xml(worldFile.readAll());QXmlStreamWriter xmlOut(&previewWorld);int worlds=0;
  worldFile.close(); // Windows forbids renaming a directory with an open child.
  while(!xml.atEnd()) {
    xml.readNext();
    if(xml.isEndElement()&&xml.name()==QStringLiteral("world")) {
      xmlOut.writeStartElement(QStringLiteral("include"));xmlOut.writeTextElement(QStringLiteral("uri"),QStringLiteral("model://cartographe"));xmlOut.writeEndElement();++worlds;
    }
    if(!xml.hasError())xmlOut.writeCurrentToken(xml);
  }
  require(!xml.hasError()&&worlds==1,QStringLiteral("Monde SDF invalide"));
  QSaveFile worldOutput(model+QStringLiteral("/preview_world.sdf"));
  require(worldOutput.open(QIODevice::WriteOnly)&&worldOutput.write(previewWorld)==previewWorld.size()&&worldOutput.commit(),QStringLiteral("Monde de visualisation non finalisé"));
  progress(88,QStringLiteral("Création de l’aperçu 3D"));write(model+QStringLiteral("/preview.json"),preview(model));
  QJsonObject files;QDir dir(model);QStringList names{QStringLiteral("model.sdf"),QStringLiteral("model.config"),QStringLiteral("model_checks.json"),QStringLiteral("dynamics_preview.json"),QStringLiteral("40000_gz_cartographe"),QStringLiteral("cartographe_flat.sdf"),QStringLiteral("preview_world.sdf"),QStringLiteral("preview.json"),QStringLiteral("geometry/geometry_manifest.json"),QStringLiteral("geometry/collision_model.json"),QStringLiteral("geometry/mass_ledger.json")};
  for(const auto& mesh:QDir(model+QStringLiteral("/meshes")).entryList(QDir::Files))names.append(QStringLiteral("meshes/")+mesh);
  for(const auto& name:names)files.insert(name,sha(dir.filePath(name)));
  progress(95,QStringLiteral("Contrôle final et publication du dossier"));
  for(auto i=sources.begin();i!=sources.end();++i)require(sha(confined(workspace_,i.key()))==i.value().toString(),QStringLiteral("Source modifiée pendant la préparation : %1").arg(i.key()));
  QJsonObject manifest{{QStringLiteral("schema"),QStringLiteral("drone_agricole.gazebo_export.v1")},{QStringLiteral("finalized"),true},{QStringLiteral("model"),QStringLiteral("cartographe")},
    {QStringLiteral("created_at_utc"),QDateTime::currentDateTimeUtc().toString(Qt::ISODateWithMs)},{QStringLiteral("regenerated_from_cad"),request.regenerateMeshes},
    {QStringLiteral("physical_fidelity"),QStringLiteral("À valider")},{QStringLiteral("mass_scenario_kg"),read(model+QStringLiteral("/dynamics_preview.json")).value(QStringLiteral("total_mass_kg"))},{QStringLiteral("units"),QStringLiteral("m, kg, kg m² ; FLU ; CAO mm × 0.001")},
    {QStringLiteral("sources_sha256"),sources},{QStringLiteral("files_sha256"),files},{QStringLiteral("airframe"),QStringLiteral("40000_gz_cartographe")},
    {QStringLiteral("limits"),QJsonArray{QStringLiteral("Profil du prototype actif uniquement, quatre rotors séparés"),QStringLiteral("Scénario synthétique, aucune masse réelle identifiée ni autonomie calculée"),QStringLiteral("Collisions conservatrices pour sol plat ; capteurs synthétiques non calibrés"),QStringLiteral("Préparation uniquement : aucun lancement Docker, PX4 ou armement")}}};
  write(model+QStringLiteral("/export_manifest.json"),manifest);checkpoint();
  require(QDir().mkpath(QFileInfo(destination).absolutePath()),QStringLiteral("Destination inaccessible"));
  require(QDir().rename(model,destination),QStringLiteral("Publication impossible ; aucune sortie finalisée"));
  manifest.insert(QStringLiteral("directory"),destination);manifest.insert(QStringLiteral("preview"),read(destination+QStringLiteral("/preview.json")));return manifest;
}
}
