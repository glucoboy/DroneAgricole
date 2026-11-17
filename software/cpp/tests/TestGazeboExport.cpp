#include "drone_agricole/adapters/LocalGazeboExportBackend.hpp"
#include <QCryptographicHash>
#include <QDataStream>
#include <QDir>
#include <QFile>
#include <QJsonArray>
#include <QJsonDocument>
#include <QLockFile>
#include <QSignalSpy>
#include <QTemporaryDir>
#include <QtTest>
#include <stdexcept>
using namespace drone_agricole;
namespace {
void file(const QString& path,const QByteArray& data){QDir().mkpath(QFileInfo(path).absolutePath());QFile f(path);if(!f.open(QIODevice::WriteOnly)||f.write(data)!=data.size())throw std::runtime_error((path+QStringLiteral(": ")+f.errorString()).toStdString());}
void json(const QString& path,const QJsonObject& value){file(path,QJsonDocument(value).toJson());}
QString hash(const QString& p){QFile f(p);f.open(QIODevice::ReadOnly);return QString::fromLatin1(QCryptographicHash::hash(f.readAll(),QCryptographicHash::Sha256).toHex());}
QByteArray stl(){QByteArray b(80,' ');QDataStream s(&b,QIODevice::Append);s.setByteOrder(QDataStream::LittleEndian);s.setFloatingPointPrecision(QDataStream::SinglePrecision);s<<quint32(1);for(float x:{0.f,0.f,1.f,0.f,0.f,0.f,.2f,0.f,0.f,0.f,.2f,0.f})s<<x;s<<quint16(0);return b;}
QString fixture(const QString& root){
 auto cad=root+QStringLiteral("/hardware/mecanique/cartographe/");auto model=root+QStringLiteral("/simulation/gazebo/models/cartographe");
 file(cad+QStringLiteral("assemblages/Prototype_Cartographe.FCStd"),QByteArrayLiteral("synthetic fixture"));
 json(cad+QStringLiteral("manifest.json"),{{QStringLiteral("prototype_cartographe"),QJsonObject{{QStringLiteral("assemblages"),QJsonArray{QJsonObject{{QStringLiteral("fichier"),QStringLiteral("assemblages/Prototype_Cartographe.FCStd")},{QStringLiteral("sha256"),hash(cad+QStringLiteral("assemblages/Prototype_Cartographe.FCStd"))}}}}}}});
 json(cad+QStringLiteral("nomenclature_prototype.json"),{});file(cad+QStringLiteral("verification/read_brep_prototype.py"),QByteArrayLiteral("# fixture"));
 for(const auto& script:{QStringLiteral("cad_export_cartographe.py"),QStringLiteral("cad_export_collisions.py")})file(root+QStringLiteral("/simulation/gazebo/tools/")+script,QByteArrayLiteral("# fixture"));
 file(root+QStringLiteral("/simulation/gazebo/ModelBuilder.cpp"),QByteArrayLiteral("// fixture provenance"));file(root+QStringLiteral("/simulation/gazebo/ModelBuilder.hpp"),QByteArrayLiteral("// fixture provenance"));
 file(root+QStringLiteral("/simulation/gazebo/worlds/cartographe_flat.sdf"),QByteArrayLiteral("<sdf version='1.9'><world name='cartographe_flat'/></sdf>"));
 json(model+QStringLiteral("/geometry/mass_ledger.json"),{{QStringLiteral("mass_complete_g"),QJsonValue::Null}});
 json(model+QStringLiteral("/dynamics_preview.json"),{{QStringLiteral("total_mass_kg"),6},{QStringLiteral("rotor_mass_kg"),.022},{QStringLiteral("rotor_nominal_radius_m"),.1905},{QStringLiteral("body_equivalent_box_m"),QJsonArray{.46,.46,.25}},{QStringLiteral("body_centre_m"),QJsonArray{0,0,0}},{QStringLiteral("max_rpm"),6000},{QStringLiteral("max_thrust_per_rotor_n"),18.8},{QStringLiteral("moment_constant_m"),.02},{QStringLiteral("response_up_s"),.05},{QStringLiteral("response_down_s"),.05},{QStringLiteral("rotor_order_cad"),QJsonArray{4,3,2,1}}});
 file(model+QStringLiteral("/model.config"),QByteArrayLiteral("<model><name>cartographe</name><sdf version='1.9'>model.sdf</sdf></model>"));
 file(model+QStringLiteral("/meshes/body.stl"),stl());QJsonArray rotors;const double positions[4][2]={{-.23,-.23},{.23,.23},{-.23,.23},{.23,-.23}};
 for(int i=0;i<4;++i){auto name=QStringLiteral("meshes/rotor_%1.stl").arg(i);file(model+QLatin1Char('/')+name,stl());rotors.append(QJsonObject{{QStringLiteral("mesh"),name},{QStringLiteral("sha256"),hash(model+QLatin1Char('/')+name)},{QStringLiteral("position_m"),QJsonArray{positions[i][0],positions[i][1],.0655}},{QStringLiteral("axis_flu"),QJsonArray{0,0,1}},{QStringLiteral("cad_label_rotation"),i<2?QStringLiteral("cw"):QStringLiteral("ccw")},{QStringLiteral("cad_occurrence"),QStringLiteral("rotor%1").arg(i)}});}
 json(model+QStringLiteral("/geometry/geometry_manifest.json"),{{QStringLiteral("finalized"),true},{QStringLiteral("frame"),QJsonObject{{QStringLiteral("scale"),.001}}},{QStringLiteral("sources"),QJsonObject{{QStringLiteral("cad_manifest_sha256"),hash(cad+QStringLiteral("manifest.json"))},{QStringLiteral("dependencies_relative_to_cad_directory"),QJsonObject{{QStringLiteral("assemblages/Prototype_Cartographe.FCStd"),hash(cad+QStringLiteral("assemblages/Prototype_Cartographe.FCStd"))}}}}},{QStringLiteral("geometry"),QJsonObject{{QStringLiteral("body_mesh"),QJsonObject{{QStringLiteral("path"),QStringLiteral("meshes/body.stl")},{QStringLiteral("sha256"),hash(model+QStringLiteral("/meshes/body.stl"))}}},{QStringLiteral("rotors"),rotors}}}});
 json(model+QStringLiteral("/geometry/collision_model.json"),{{QStringLiteral("geometry_manifest_sha256"),hash(model+QStringLiteral("/geometry/geometry_manifest.json"))},{QStringLiteral("boxes"),QJsonArray{QJsonObject{{QStringLiteral("name"),QStringLiteral("pad")},{QStringLiteral("centre_m"),QJsonArray{0,0,-.3}},{QStringLiteral("size_m"),QJsonArray{.1,.1,.02}}}}}});return model;
}
class Fake final:public application::IGazeboExportBackend {
 public:bool fail=false;QJsonObject inspect()const override{return {};}
 QJsonObject execute(const application::GazeboExportRequest&,const std::atomic_bool& cancel,Progress p)override{p(20,QStringLiteral("started"));for(int i=0;i<20;++i){QThread::msleep(5);if(cancel)throw std::runtime_error("cancelled");}if(fail)throw std::runtime_error("failed");return {{QStringLiteral("finalized"),true}};}
};
}
class TestGazeboExport:public QObject {
 Q_OBJECT
 private slots:
 void reconciledMassKeepsSyntheticPreview(){
  QTemporaryDir temp(QStringLiteral("gazebo-mass-fixture-XXXXXX"));auto source=fixture(temp.path());
  json(source+QStringLiteral("/geometry/mass_ledger.json"),{{QStringLiteral("mass_complete_g"),7200}});
  adapters::LocalGazeboExportBackend backend(temp.path());std::atomic_bool cancel=false;
  application::GazeboExportRequest request;request.regenerateMeshes=false;
  auto result=backend.execute(request,cancel,[](int,const QString&){});
  QCOMPARE(result.value(QStringLiteral("mass_scenario_kg")).toDouble(),6.);
  QVERIFY(!backend.inspect().value(QStringLiteral("preview_stale")).toBool());
  file(temp.path()+QStringLiteral("/hardware/mecanique/cartographe/assemblages/Prototype_Cartographe.FCStd"),QByteArrayLiteral("changed CAD"));
  QVERIFY(backend.inspect().value(QStringLiteral("preview_stale")).toBool());
  QVERIFY(backend.inspect().contains(QStringLiteral("preview")));
 }
 void exportFixture(){QTemporaryDir temp(QStringLiteral("gazebo-fixture-XXXXXX"));auto source=fixture(temp.path());adapters::LocalGazeboExportBackend backend(temp.path());std::atomic_bool cancel=false;application::GazeboExportRequest r;r.regenerateMeshes=false;r.outputDirectory=QStringLiteral("results/package/cartographe");auto result=backend.execute(r,cancel,[](int,const QString&){});QVERIFY(result.value(QStringLiteral("finalized")).toBool());auto dest=result.value(QStringLiteral("directory")).toString();QVERIFY(QFileInfo::exists(dest+QStringLiteral("/model.sdf")));QVERIFY(QFileInfo::exists(dest+QStringLiteral("/40000_gz_cartographe")));QCOMPARE(hash(source+QStringLiteral("/meshes/body.stl")),hash(dest+QStringLiteral("/meshes/body.stl")));QVERIFY(!QFileInfo::exists(temp.path()+QStringLiteral("/simulation/px4_sitl/airframes/40000_gz_cartographe")));QCOMPARE(result.value(QStringLiteral("preview")).toObject().value(QStringLiteral("triangles")).toArray().size(),5);QVERIFY_EXCEPTION_THROWN(backend.execute(r,cancel,[](int,const QString&){}),std::runtime_error);}
 void badInputs(){QTemporaryDir temp(QStringLiteral("gazebo-fixture-XXXXXX"));auto source=fixture(temp.path());adapters::LocalGazeboExportBackend backend(temp.path());std::atomic_bool cancel=false;application::GazeboExportRequest r;r.regenerateMeshes=false;r.outputDirectory=temp.path()+QStringLiteral("/../outside/cartographe");QVERIFY_EXCEPTION_THROWN(backend.execute(r,cancel,[](int,const QString&){}),std::runtime_error);r.outputDirectory=QStringLiteral("results/test/cartographe");file(source+QStringLiteral("/meshes/body.stl"),QByteArrayLiteral("corrupt"));QVERIFY_EXCEPTION_THROWN(backend.execute(r,cancel,[](int,const QString&){}),std::runtime_error);QVERIFY(!QFileInfo::exists(temp.path()+QLatin1Char('/')+r.outputDirectory));}
 void staleCad(){QTemporaryDir temp(QStringLiteral("gazebo-fixture-XXXXXX"));fixture(temp.path());file(temp.path()+QStringLiteral("/hardware/mecanique/cartographe/assemblages/Prototype_Cartographe.FCStd"),QByteArrayLiteral("changed"));adapters::LocalGazeboExportBackend backend(temp.path());std::atomic_bool cancel=false;application::GazeboExportRequest r;r.regenerateMeshes=false;QVERIFY_EXCEPTION_THROWN(backend.execute(r,cancel,[](int,const QString&){}),std::runtime_error);}
 void missingPython(){QTemporaryDir temp(QStringLiteral("gazebo-fixture-XXXXXX"));fixture(temp.path());adapters::LocalGazeboExportBackend backend(temp.path());std::atomic_bool cancel=false;application::GazeboExportRequest r;r.pythonProgram=QStringLiteral("/nonexistent/python");QVERIFY_EXCEPTION_THROWN(backend.execute(r,cancel,[](int,const QString&){}),std::runtime_error);}
 void cancelledPackage(){QTemporaryDir temp(QStringLiteral("gazebo-fixture-XXXXXX"));fixture(temp.path());adapters::LocalGazeboExportBackend backend(temp.path());std::atomic_bool cancel=true;application::GazeboExportRequest r;r.regenerateMeshes=false;r.outputDirectory=QStringLiteral("results/cancel/cartographe");QVERIFY_EXCEPTION_THROWN(backend.execute(r,cancel,[](int,const QString&){}),std::runtime_error);QVERIFY(!QFileInfo::exists(temp.path()+QLatin1Char('/')+r.outputDirectory));}
 void lock(){QTemporaryDir temp(QStringLiteral("gazebo-fixture-XXXXXX"));fixture(temp.path());QDir().mkpath(temp.path()+QStringLiteral("/results/simulation/model_exports"));QLockFile lock(temp.path()+QStringLiteral("/results/simulation/model_exports/.export.lock"));QVERIFY(lock.tryLock());adapters::LocalGazeboExportBackend backend(temp.path());std::atomic_bool cancel=false;application::GazeboExportRequest r;r.regenerateMeshes=false;QVERIFY_EXCEPTION_THROWN(backend.execute(r,cancel,[](int,const QString&){}),std::runtime_error);}
 void lifecycle(){Fake backend;application::GazeboExportService service(backend);QSignalSpy done(&service,&application::GazeboExportService::completed);QVERIFY(service.start({}));QVERIFY(!service.start({}));QTRY_COMPARE(done.count(),1);QCOMPARE(service.state(),QStringLiteral("completed"));QTRY_VERIFY(!service.findChild<QThread*>());}
 void cancelLifecycle(){Fake backend;application::GazeboExportService service(backend);QSignalSpy done(&service,&application::GazeboExportService::completed);service.start({});service.cancel();QTRY_COMPARE(done.count(),1);QCOMPARE(service.state(),QStringLiteral("cancelled"));QVERIFY(service.result().isEmpty());}
 void restartOnCompleted(){Fake backend;application::GazeboExportService service(backend);int count=0;bool restarted=false;connect(&service,&application::GazeboExportService::completed,&service,[&]{if(++count==1)restarted=service.start({});});service.start({});QTRY_COMPARE(count,2);QVERIFY(restarted);QVERIFY(!service.active());}
 void failureLifecycle(){Fake backend;backend.fail=true;application::GazeboExportService service(backend);QSignalSpy done(&service,&application::GazeboExportService::completed);service.start({});QTRY_COMPARE(done.count(),1);QCOMPARE(service.state(),QStringLiteral("failed"));QCOMPARE(service.message(),QStringLiteral("failed"));}
};
QTEST_GUILESS_MAIN(TestGazeboExport)
#include "TestGazeboExport.moc"
