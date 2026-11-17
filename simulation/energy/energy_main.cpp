#include "EnergyModel.hpp"

#include <QCoreApplication>
#include <QCryptographicHash>
#include <QDir>
#include <QDateTime>
#include <QFile>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QSaveFile>
#include <QTextStream>

#include <cmath>
#include <iostream>
#include <limits>
#include <stdexcept>

using namespace cartographe::energy;
namespace {
void require(bool condition,const char* message){if(!condition)throw std::runtime_error(message);}
QJsonObject object(const QJsonValue& value){require(value.isObject(),"expected JSON object");return value.toObject();}
QJsonArray array(const QJsonObject& o,const char* key){const auto value=o.value(QString::fromLatin1(key));require(value.isArray(),"missing/non-array field");return value.toArray();}
double number(const QJsonObject& o,const char* key){auto value=o.value(QString::fromLatin1(key));require(value.isDouble()&&std::isfinite(value.toDouble()),"missing/non-numeric/finite field");return value.toDouble();}
QString string(const QJsonObject& o,const char* key){auto v=o.value(QString::fromLatin1(key));require(v.isString()&&!v.toString().isEmpty(),"missing/empty string");return v.toString();}
std::string identifier(const QJsonObject& o,const char* key){auto value=string(o,key).toStdString();for(char x:value)require((x>='a'&&x<='z')||(x>='A'&&x<='Z')||(x>='0'&&x<='9')||x=='_'||x=='-'||x=='.',"identifier contains unsupported characters");return value;}
struct Input {QJsonObject data;QByteArray bytes;};
Input read(const QString& path){QFile f(path);require(f.open(QIODevice::ReadOnly),"cannot open configuration");const auto bytes=f.readAll();QJsonParseError error;auto json=QJsonDocument::fromJson(bytes,&error);require(error.error==QJsonParseError::NoError&&json.isObject(),"invalid JSON configuration");auto o=json.object();require(number(o,"schema_version")==1,"unsupported schema_version");return {o,bytes};}
QString sha(const QByteArray& bytes){return QString::fromLatin1(QCryptographicHash::hash(bytes,QCryptographicHash::Sha256).toHex());}
void save(const QString& path,const QByteArray& bytes){require(!QFile::exists(path),"output file already exists; choose a new run directory");QSaveFile file(path);require(file.open(QIODevice::WriteOnly),"cannot create output");require(file.write(bytes)==bytes.size(),"incomplete output write");require(file.commit(),"output finalization failed");}
Configuration configuration(const QJsonObject& o){
 require(string(o,"role")==QStringLiteral("calibration_proxy"),"expected calibration proxy role");
 Configuration c;
 const double count=number(o,"rotor_count");require(count==4,"rotor count must equal four");c.rotor_count=4;
 c.reference_voltage_v=number(o,"reference_voltage_v");c.propulsion_power_factor=number(o,"propulsion_power_factor");
 for(auto value:array(o,"propulsion_curve")){auto p=object(value);c.propulsion.push_back({number(p,"thrust_g")*.001*9.80665,number(p,"dc_power_w"),number(p,"rpm")});}
 for(auto value:array(o,"auxiliaries")){auto p=object(value);c.auxiliaries.push_back({identifier(p,"id"),number(p,"useful_power_w"),number(p,"efficiency")});}
 auto b=object(o.value(QStringLiteral("battery")));
 c.battery.nominal_capacity_ah=number(b,"nominal_capacity_ah");c.battery.capacity_factor=number(b,"capacity_factor");
 c.battery.pack_resistance_ohm=number(b,"pack_resistance_ohm");c.battery.path_resistance_ohm=number(b,"path_resistance_ohm");
 c.battery.reserve_soc=number(b,"reserve_soc");c.battery.minimum_bus_voltage_v=number(b,"minimum_bus_voltage_v");c.battery.maximum_current_a=number(b,"maximum_current_a");
 for(auto value:array(b,"ocv")){auto p=object(value);c.battery.ocv.push_back({number(p,"soc"),number(p,"voltage_v")});}
 return c;
}
QJsonObject phaseJson(const PhaseEnergy& p){return {{QStringLiteral("id"),QString::fromStdString(p.id)},{QStringLiteral("duration_s"),p.duration_s},{QStringLiteral("propulsion_wh"),p.propulsion_wh},{QStringLiteral("auxiliary_wh"),p.auxiliary_wh},{QStringLiteral("pack_loss_wh"),p.pack_loss_wh},{QStringLiteral("path_loss_wh"),p.path_loss_wh}};}
QJsonObject resultJson(const Result& r,const Scenario& s,const std::string& variant){
 QJsonArray phases;for(auto& p:r.phases)phases.append(phaseJson(p));
 return {{QStringLiteral("id"),QString::fromStdString(s.id)},{QStringLiteral("variant"),QString::fromStdString(variant)},{QStringLiteral("mass_kg"),s.mass_kg},{QStringLiteral("mass_source"),QStringLiteral("synthetic sensitivity case; not reconciled prototype BOM")},{QStringLiteral("initial_soc"),s.initial_soc},{QStringLiteral("end_reason"),QString::fromLatin1(name(r.reason))},{QStringLiteral("mission_completed"),r.completed},{QStringLiteral("simulation_finalized"),r.finalized},{QStringLiteral("landing_observed"),false},{QStringLiteral("elapsed_s"),r.elapsed_s},{QStringLiteral("final_soc"),r.final_soc},{QStringLiteral("consumed_ah"),r.consumed_ah},{QStringLiteral("bus_energy_wh"),r.bus_energy_wh},{QStringLiteral("pack_loss_wh"),r.pack_loss_wh},{QStringLiteral("path_loss_wh"),r.path_loss_wh},{QStringLiteral("minimum_bus_voltage_v"),r.minimum_voltage_v},{QStringLiteral("maximum_current_a"),r.maximum_current_a},{QStringLiteral("minimum_thrust_margin_per_rotor_n"),r.minimum_thrust_margin_n},{QStringLiteral("saturation_count"),static_cast<double>(r.saturation_count)},{QStringLiteral("sample_count"),static_cast<double>(r.samples.size())},{QStringLiteral("phase_energy"),phases}};
}
}

int main(int argc,char** argv){QCoreApplication app(argc,argv);try{
 const QString startedAt=QDateTime::currentDateTimeUtc().toString(Qt::ISODateWithMs);
 const QString executablePath=QCoreApplication::applicationFilePath();
 QFile executable(executablePath);require(executable.open(QIODevice::ReadOnly),"cannot fingerprint running executable");
 QCryptographicHash binaryHash(QCryptographicHash::Sha256);require(binaryHash.addData(&executable),"cannot hash running executable");
 const QString executableSha=QString::fromLatin1(binaryHash.result().toHex());
 const auto args=app.arguments();QString calibrationPath,campaignPath,outputPath;double cancelAfter=std::numeric_limits<double>::infinity();
 for(int i=1;i<args.size();++i){auto a=args[i];require(i+1<args.size(),"argument requires a value");auto v=args[++i];if(a==QStringLiteral("--calibration"))calibrationPath=v;else if(a==QStringLiteral("--campaign"))campaignPath=v;else if(a==QStringLiteral("--output"))outputPath=v;else if(a==QStringLiteral("--cancel-after")){bool ok=false;cancelAfter=v.toDouble(&ok);require(ok&&std::isfinite(cancelAfter)&&cancelAfter>=0,"invalid cancellation time");}else throw std::runtime_error("unknown command argument");}
 require(!calibrationPath.isEmpty()&&!campaignPath.isEmpty()&&!outputPath.isEmpty(),"usage: cartographe-energy --calibration FILE --campaign FILE --output NEW_DIRECTORY [--cancel-after SECONDS]");
 const auto calibration=read(calibrationPath),campaign=read(campaignPath);const auto base=configuration(calibration.data);
 require(string(campaign.data,"role")==QStringLiteral("synthetic_evaluation"),"expected synthetic evaluation role");
 require(string(calibration.data,"id")!=string(campaign.data,"id"),"calibration and evaluation identities must differ");
 const auto masses=array(campaign.data,"masses_kg"),socs=array(campaign.data,"initial_soc"),profiles=array(campaign.data,"profiles"),variants=array(campaign.data,"uncertainty_variants");
 require(!masses.isEmpty()&&!socs.isEmpty()&&!profiles.isEmpty()&&!variants.isEmpty(),"empty evaluation matrix");
 require(static_cast<qint64>(masses.size())*socs.size()*profiles.size()*variants.size()<=100,"evaluation run budget exceeded");
 QJsonArray results;QByteArray csv("run_id,phase,time_s,dt_s,soc,bus_voltage_v,current_a,propulsion_w,auxiliary_w,pack_loss_w,path_loss_w,thrust_per_rotor_n,rpm,thrust_margin_n\n");
 QTextStream stream(&csv,QIODevice::WriteOnly|QIODevice::Append);stream.setRealNumberPrecision(12);
 std::size_t runNumber=0;
 for(auto vv:variants){const auto variant=object(vv);const auto variantId=identifier(variant,"id");auto c=base;c.propulsion_power_factor=number(variant,"propulsion_power_factor");c.battery.capacity_factor=number(variant,"capacity_factor");c.battery.pack_resistance_ohm=number(variant,"pack_resistance_ohm");c.battery.path_resistance_ohm=number(variant,"path_resistance_ohm");const double auxFactor=number(variant,"auxiliary_power_factor");require(auxFactor>0,"invalid auxiliary factor");for(auto& load:c.auxiliaries)load.useful_power_w*=auxFactor;
  for(auto mm:masses)for(auto ss:socs)for(auto pp:profiles){require(mm.isDouble()&&ss.isDouble(),"matrix entries must be numeric");const auto profile=object(pp);Scenario s;s.id=identifier(profile,"id")+"_"+variantId+"_"+std::to_string(++runNumber);s.mass_kg=mm.toDouble();s.initial_soc=ss.toDouble();s.time_step_s=number(campaign.data,"time_step_s");s.maximum_duration_s=number(campaign.data,"maximum_duration_s");
   for(auto ph:array(profile,"phases")){const auto p=object(ph);s.phases.push_back({identifier(p,"id"),number(p,"duration_s"),number(p,"thrust_weight_ratio")});}
   const auto result=simulate(c,s,[&](double time){return time>=cancelAfter;});results.append(resultJson(result,s,variantId));
   for(const auto& row:result.samples)stream<<QString::fromStdString(s.id)<<','<<QString::fromStdString(row.phase)<<','<<row.time_s<<','<<row.duration_s<<','<<row.soc<<','<<row.voltage_v<<','<<row.current_a<<','<<row.propulsion_w<<','<<row.auxiliary_w<<','<<row.pack_loss_w<<','<<row.path_loss_w<<','<<row.thrust_per_rotor_n<<','<<row.rpm<<','<<row.thrust_margin_n<<'\n';
  }
 }
 stream.flush();require(stream.status()==QTextStream::Ok,"CSV serialization failed");
 const QJsonObject raw{{QStringLiteral("schema_version"),1},{QStringLiteral("kind"),QStringLiteral("cartographe_energy_campaign")},{QStringLiteral("execution"),QStringLiteral("offline_deterministic_cpp17")},{QStringLiteral("executable_path"),executablePath},{QStringLiteral("executable_sha256"),executableSha},{QStringLiteral("physical_qualification"),false},{QStringLiteral("px4_connected"),false},{QStringLiteral("battery_source"),QStringLiteral("local Thevenin proxy; not injected into PX4")},{QStringLiteral("started_at_utc"),startedAt},{QStringLiteral("finished_at_utc"),QDateTime::currentDateTimeUtc().toString(Qt::ISODateWithMs)},{QStringLiteral("calibration_id"),string(calibration.data,"id")},{QStringLiteral("evaluation_id"),string(campaign.data,"id")},{QStringLiteral("calibration_sha256"),sha(calibration.bytes)},{QStringLiteral("evaluation_sha256"),sha(campaign.bytes)},{QStringLiteral("csv_sha256"),sha(csv)},{QStringLiteral("finalized"),true},{QStringLiteral("simulation_finalized"),true},{QStringLiteral("run_count"),static_cast<double>(runNumber)},{QStringLiteral("limits"),calibration.data.value(QStringLiteral("limits"))},{QStringLiteral("runs"),results}};
 QDir dir(outputPath);require(dir.exists()||QDir().mkpath(outputPath),"cannot create output directory");
 save(dir.filePath(QStringLiteral("samples.csv")),csv);save(dir.filePath(QStringLiteral("energy_raw.json")),QJsonDocument(raw).toJson(QJsonDocument::Indented));
 std::cout<<"Finalized "<<runNumber<<" offline sensitivity runs; physical qualification remains unvalidated\n";return 0;
 }catch(const std::exception& error){std::cerr<<"energy campaign rejected: "<<error.what()<<'\n';return 2;}}
