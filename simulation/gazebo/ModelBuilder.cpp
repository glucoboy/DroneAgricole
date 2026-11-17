#include <QCoreApplication>
#include <QCryptographicHash>
#include <QDir>
#include <QFile>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QSaveFile>
#include <QXmlStreamReader>
#include <array>
#include <cmath>
#include <iostream>
#include <stdexcept>
#include "../mass/MassProperties.hpp"
#include "ModelBuilder.hpp"

namespace {
void need(bool b,const QString &m){if(!b)throw std::runtime_error(m.toStdString());}
QByteArray bytes(const QString&p){QFile f(p);need(f.open(QIODevice::ReadOnly),p);return f.readAll();}
QString hash(const QString&p){QFile f(p);need(f.open(QIODevice::ReadOnly),p);QCryptographicHash h(QCryptographicHash::Sha256);need(h.addData(&f),p);return QString::fromLatin1(h.result().toHex());}
QJsonObject json(const QString&p){QJsonParseError e;auto d=QJsonDocument::fromJson(bytes(p),&e);need(e.error==QJsonParseError::NoError&&d.isObject(),"invalid JSON "+p);return d.object();}
void save(const QString&p,const QByteArray&b){QDir().mkpath(QFileInfo(p).absolutePath());QSaveFile f(p);need(f.open(QIODevice::WriteOnly)&&f.write(b)==b.size()&&f.commit(),"save "+p);}
QString n(double v){need(std::isfinite(v),"nonfinite parameter");return QString::number(v,'g',15);}
QString vec(QJsonArray a){need(a.size()==3,"vector length");return n(a[0].toDouble())+" "+n(a[1].toDouble())+" "+n(a[2].toDouble());}
QString inertia(double x,double y,double z){need(x>0&&y>0&&z>0&&x+y>=z-1e-12&&x+z>=y-1e-12&&y+z>=x-1e-12,"inadmissible inertia");return "<inertia><ixx>"+n(x)+"</ixx><iyy>"+n(y)+"</iyy><izz>"+n(z)+"</izz><ixy>0</ixy><ixz>0</ixz><iyz>0</iyz></inertia>";}
QString visual(QString name,QString path){return "<visual name='"+name+"'><geometry><mesh><uri>model://cartographe/"+path+"</uri><scale>1 1 1</scale></mesh></geometry></visual>";}
void generate(const QString&root,bool physical,const QString&dir,const QString&airframe){
  auto g=json(dir+"/geometry/geometry_manifest.json"),c=json(dir+"/dynamics_preview.json");
  auto ledger=json(dir+"/geometry/mass_ledger.json");
  need(!physical,"physical mode unavailable: mass/CG/inertias and exact propulsion are not identified");
  // The preview remains an explicit synthetic fixture. A reconciled BOM may
  // acquire a complete mass without silently changing these dynamics.
  need(ledger.contains("mass_complete_g"),"mass ledger contract missing");
  need(g["finalized"].toBool()&&g["frame"].toObject()["scale"].toDouble()==.001,"unfinalized geometry/units");
  auto sources=g["sources"].toObject();need(hash(root+"/hardware/mecanique/cartographe/manifest.json")==sources["cad_manifest_sha256"],"stale CAD manifest");
  auto deps=sources["dependencies_relative_to_cad_directory"].toObject();for(auto it=deps.begin();it!=deps.end();++it)need(hash(root+"/hardware/mecanique/cartographe/"+it.key())==it.value(),"stale dependency "+it.key());
  auto geometry=g["geometry"].toObject();auto body=geometry["body_mesh"].toObject();need(hash(dir+"/"+body["path"].toString())==body["sha256"],"stale body mesh");
  double total=c["total_mass_kg"].toDouble(),rm=c["rotor_mass_kg"].toDouble(),r=c["rotor_nominal_radius_m"].toDouble();double bm=total-4*rm;
  need(bm>0&&rm>0&&r>0,"invalid masses");auto box=c["body_equivalent_box_m"].toArray();need(box.size()==3,"box size");double x=box[0].toDouble(),y=box[1].toDouble(),z=box[2].toDouble();need(x>0&&y>0&&z>0,"box dimensions");
  QString xml="<?xml version='1.0'?><sdf version='1.9'><model name='cartographe'><pose>0 0 0.32 0 0 0</pose><self_collide>false</self_collide><static>false</static><link name='base_link'><inertial><pose>"+vec(c["body_centre_m"].toArray())+" 0 0 0</pose><mass>"+n(bm)+"</mass>"+inertia(bm*(y*y+z*z)/12,bm*(x*x+z*z)/12,bm*(x*x+y*y)/12)+"</inertial>"+visual("cad_body",body["path"].toString());
  auto collisionModel=json(dir+"/geometry/collision_model.json");need(collisionModel["geometry_manifest_sha256"]==hash(dir+"/geometry/geometry_manifest.json"),"stale collisions");
  auto collisions=collisionModel["boxes"].toArray();need(!collisions.isEmpty(),"collision proxies missing");
  for(auto v:collisions){auto a=v.toObject();xml+="<collision name='"+a["name"].toString()+"'><pose>"+vec(a["centre_m"].toArray())+" 0 0 0</pose><geometry><box><size>"+vec(a["size_m"].toArray())+"</size></box></geometry></collision>";}
  // Synthetic integration fixture, NOT calibrated sensor performance. Perfectly
  // constant readings trigger PX4's stuck-sensor validator at rest. Keep checks
  // enabled and perturb the simulated measurements instead.
  auto noise=[](double sigma){return "<noise type='gaussian'><mean>0</mean><stddev>"+n(sigma)+"</stddev></noise>";};
  auto axes=[&](double sigma){QString s;for(auto axis:{"x","y","z"})s+="<"+QString(axis)+">"+noise(sigma)+"</"+axis+">";return s;};
  xml+="<sensor name='imu_sensor' type='imu'><always_on>true</always_on><update_rate>250</update_rate><imu><angular_velocity>"+axes(.001)+"</angular_velocity><linear_acceleration>"+axes(.01)+"</linear_acceleration></imu></sensor>";
  xml+="<sensor name='magnetometer_sensor' type='magnetometer'><always_on>true</always_on><update_rate>100</update_rate><magnetometer>"+axes(.0001)+"</magnetometer></sensor>";
  xml+="<sensor name='air_pressure_sensor' type='air_pressure'><always_on>true</always_on><update_rate>50</update_rate><air_pressure><pressure>"+noise(1)+"</pressure></air_pressure></sensor><sensor name='navsat_sensor' type='navsat'><always_on>true</always_on><update_rate>30</update_rate></sensor></link>";
  double omega=c["max_rpm"].toDouble()*2*std::acos(-1.)/60,k=c["max_thrust_per_rotor_n"].toDouble()/(omega*omega),km=c["moment_constant_m"].toDouble();need(omega>0&&k>0&&km>0,"motor params");
  QString air="#!/bin/sh\n# ORCH-GZ-1 SITL ONLY: hypothetical dynamics, no flight qualification\n. ${R}etc/init.d/rc.mc_defaults\nPX4_SIMULATOR=gz\nPX4_GZ_WORLD=cartographe_flat\nPX4_SIM_MODEL=cartographe\nparam set-default SIM_GZ_EN 1\nparam set-default CA_AIRFRAME 0\nparam set-default CA_ROTOR_COUNT 4\n";
  auto rotors=geometry["rotors"].toArray(),order=c["rotor_order_cad"].toArray();need(rotors.size()==4&&order.size()==4,"four rotors required");QJsonArray allocation;
  double sx=0,sy=0,skm=0;std::array<bool,4> used{};
  using namespace cartographe::mass;
  Tensor bi{{{bm*(y*y+z*z)/12,0,0},{0,bm*(x*x+z*z)/12,0},{0,0,bm*(x*x+y*y)/12}}};
  auto bc=c["body_centre_m"].toArray();std::vector<Component> masses{{"body","",bm,Vector{bc[0].toDouble(),bc[1].toDouble(),bc[2].toDouble()},bi}};
  for(int i=0;i<4;++i){int ci=order[i].toInt()-1;need(ci>=0&&ci<4&&!used[ci],"invalid rotor order");used[ci]=true;auto a=rotors[ci].toObject();need(hash(dir+"/"+a["mesh"].toString())==a["sha256"],"stale rotor mesh");auto p=a["position_m"].toArray();auto axis=a["axis_flu"].toArray();need(axis==QJsonArray{0,0,1},"unexpected rotor axis");QString direction=a["cad_label_rotation"].toString().toLower();need(direction=="cw"||direction=="ccw","rotor direction");double moment=direction=="ccw"?km:-km; sx+=p[0].toDouble();sy+=p[1].toDouble();skm+=moment;
    QString index=QString::number(i),name="rotor_"+index,joint=name+"_joint";
    Tensor ri{{{rm*r*r/4,0,0},{0,rm*r*r/4,0},{0,0,rm*r*r/2}}};masses.push_back({name.toStdString(),"",rm,Vector{p[0].toDouble(),p[1].toDouble(),p[2].toDouble()},ri});
    xml+="<link name='"+name+"'><pose>"+vec(p)+" 0 0 0</pose><inertial><mass>"+n(rm)+"</mass>"+inertia(rm*r*r/4,rm*r*r/4,rm*r*r/2)+"</inertial>"+visual(name+"_visual",a["mesh"].toString())+"<collision name='rotor_swept_preview'><geometry><cylinder><radius>0.19685</radius><length>0.012</length></cylinder></geometry></collision></link><joint name='"+joint+"' type='revolute'><parent>base_link</parent><child>"+name+"</child><axis><xyz>0 0 1</xyz><limit><lower>-1e16</lower><upper>1e16</upper></limit></axis></joint>";
    xml+="<plugin filename='gz-sim-multicopter-motor-model-system' name='gz::sim::systems::MulticopterMotorModel'><jointName>"+joint+"</jointName><linkName>"+name+"</linkName><turningDirection>"+direction+"</turningDirection><timeConstantUp>"+n(c["response_up_s"].toDouble())+"</timeConstantUp><timeConstantDown>"+n(c["response_down_s"].toDouble())+"</timeConstantDown><maxRotVelocity>"+n(omega)+"</maxRotVelocity><motorConstant>"+n(k)+"</motorConstant><momentConstant>"+n(km)+"</momentConstant><commandSubTopic>command/motor_speed</commandSubTopic><motorNumber>"+index+"</motorNumber><rotorDragCoefficient>0</rotorDragCoefficient><rollingMomentCoefficient>0</rollingMomentCoefficient><rotorVelocitySlowdownSim>10</rotorVelocitySlowdownSim><motorType>velocity</motorType></plugin>";
    for(auto pair:QList<QPair<QString,double>>{{"PX",p[0].toDouble()},{"PY",-p[1].toDouble()},{"PZ",-p[2].toDouble()},{"AX",0},{"AY",0},{"AZ",-1},{"KM",moment}})air+="param set-default CA_ROTOR"+index+"_"+pair.first+" "+n(pair.second)+"\n";
    air+="param set-default SIM_GZ_EC_FUNC"+QString::number(i+1)+" "+QString::number(101+i)+"\nparam set-default SIM_GZ_EC_MIN"+QString::number(i+1)+" 0\nparam set-default SIM_GZ_EC_MAX"+QString::number(i+1)+" "+n(omega)+"\n";
    allocation.append(QJsonObject{{"px4_motor_index",i},{"function",101+i},{"cad_occurrence",a["cad_occurrence"]},{"position_flu_m",p},{"position_frd_m",QJsonArray{p[0],-p[1].toDouble(),-p[2].toDouble()}},{"axis_frd",QJsonArray{0,0,-1}},{"rotation",direction},{"km",moment}});
  }
  need(std::abs(sx)<1e-8&&std::abs(sy)<1e-8&&std::abs(skm)<1e-8,"unbalanced allocation");
  auto aggregateMass=aggregate(masses);need(aggregateMass.complete,"preview mass incomplete");
  xml+="</model></sdf>";QXmlStreamReader reader(xml);while(!reader.atEnd())reader.readNext();need(!reader.hasError(),"generated XML invalid");
  double hover=std::sqrt(total*9.80665/(4*c["max_thrust_per_rotor_n"].toDouble()));need(hover>=.1&&hover<=.9,"preview outside MPC hover parameter domain; revise declared scenario");
  air+="# Linear normalized motor speed, quadratic thrust. No identified nonlinear compensation.\nparam set-default THR_MDL_FAC 0\nparam set-default MPC_THR_HOVER "+n(hover)+"\n# Six-cell metadata for this prototype scenario; forfait battery is not an endurance model.\nparam set-default BAT1_N_CELLS 6\n";
  save(dir+"/model.sdf",xml.toUtf8());save(airframe,air.toUtf8());
  QJsonObject proof{{"test_id","T-CARTO-GZ-01"},{"status","préliminaire"},{"sdf_xml_valid",true},{"gazebo_loaded",false},{"mass_scenario_kg",total},{"body_mass_kg",bm},{"rotor_mass_kg",rm},{"physical_mass_identified",false},{"body_inertia_kg_m2",QJsonArray{bm*(y*y+z*z)/12,bm*(x*x+z*z)/12,bm*(x*x+y*y)/12}},{"motor_constant_n_s2_rad2",k},{"rotor_allocation",allocation},{"zero_collective_moment",true},{"geometry_manifest_sha256",hash(dir+"/geometry/geometry_manifest.json")},{"dynamics_sha256",hash(dir+"/dynamics_preview.json")},{"sdf_sha256",hash(dir+"/model.sdf")},{"airframe_sha256",hash(airframe)}};
  proof["scenario_aggregate_centre_m"]=QJsonArray{(*aggregateMass.centre)[0],(*aggregateMass.centre)[1],(*aggregateMass.centre)[2]};
  QJsonArray tensor;for(auto row:*aggregateMass.inertia)tensor.append(QJsonArray{row[0],row[1],row[2]});proof["scenario_aggregate_inertia_kg_m2"]=tensor;
  save(dir+"/model_checks.json",QJsonDocument(proof).toJson());
#ifndef DRONE_AGRICOLE_MODEL_LIBRARY
  std::cout<<"Generated SDF preview, 4 motors, source hashes and inertia constraints checked. Physical fidelity unvalidated.\n";
#endif
}
}
void cartographe::gazebo::generateModel(const QString& root,const QString& directory,const QString& airframe) {
  generate(QDir(root).absolutePath(),false,directory,airframe);
}
#ifndef DRONE_AGRICOLE_MODEL_LIBRARY
int main(int argc,char**argv){QCoreApplication app(argc,argv);try{auto a=app.arguments();need(a.size()>1,"usage: cartographe-model WORKSPACE [--physical]");auto root=QDir(a[1]).absolutePath();generate(root,a.contains("--physical"),root+"/simulation/gazebo/models/cartographe",root+"/simulation/px4_sitl/airframes/40000_gz_cartographe");return 0;}catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
#endif
