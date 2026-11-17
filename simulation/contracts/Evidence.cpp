#include <QCoreApplication>
#include <QCryptographicHash>
#include <QDateTime>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QProcess>
#include <QRegularExpression>
#include <QSaveFile>
#include <QSet>
#include <QSysInfo>
#include <QTemporaryDir>
#include <cmath>
#include <functional>
#include <iostream>
#include <stdexcept>

namespace {
void require(bool condition, const QString &message) { if (!condition) throw std::runtime_error(message.toStdString()); }
QByteArray read(const QString &p) { QFile f(p); require(f.open(QIODevice::ReadOnly), "open: " + p); return f.readAll(); }
QJsonObject object(const QString &p) { QJsonParseError e; auto d=QJsonDocument::fromJson(read(p), &e); require(e.error==QJsonParseError::NoError && d.isObject(), "JSON object: "+p); return d.object(); }
void write(const QString &p, const QJsonObject &v) { QSaveFile f(p); auto b=QJsonDocument(v).toJson(); require(f.open(QIODevice::WriteOnly) && f.write(b)==b.size() && f.commit(), "atomic write: "+p); }
QString sha(const QString &p) { QFile f(p); require(f.open(QIODevice::ReadOnly), "hash open: "+p); QCryptographicHash h(QCryptographicHash::Sha256); require(h.addData(&f), "hash: "+p); return QString::fromLatin1(h.result().toHex()); }
QString stamp() { return QDateTime::currentDateTimeUtc().toString(Qt::ISODateWithMs); }
QString safePath(const QString &root, const QString &relative) {
  require(!relative.isEmpty() && !relative.contains('\\') && !QDir::isAbsolutePath(relative) && !relative.contains(':'), "unsafe path: "+relative);
  auto p=QDir::cleanPath(QDir(root).absoluteFilePath(relative)); auto r=QDir(root).absolutePath()+"/";
  require(p.startsWith(r) && QFileInfo(p).isFile(), "missing or escaping file: "+p);
  auto canonical=QFileInfo(p).canonicalFilePath(); auto canonicalRoot=QFileInfo(root).canonicalFilePath()+"/";
  require(canonical.startsWith(canonicalRoot), "escaping symlink: "+p); return p;
}

// Implements every assertion keyword used by the five canonical T0 schemas.
// Unknown assertion keywords are rejected instead of silently weakening validation.
class Schemas {
  QString directory;
  QJsonObject resolve(QJsonObject s, QJsonObject &document) const {
    if (!s.contains("$ref")) return s;
    auto ref=s["$ref"].toString(); auto pieces=ref.split('#');
    require(pieces.size()<=2, "invalid schema ref");
    if (!pieces[0].isEmpty()) { require(!pieces[0].contains('/') && !pieces[0].contains(':'), "nonlocal schema ref"); document=object(directory+"/"+pieces[0]); }
    QJsonValue value=document;
    if(pieces.size()==2 && !pieces[1].isEmpty()) {
      require(pieces[1].startsWith('/'), "invalid JSON pointer");
      for(auto key:pieces[1].mid(1).split('/')) value=value.toObject()[key.replace("~1","/").replace("~0","~")];
    }
    require(value.isObject(), "unresolved schema ref: "+ref); return value.toObject();
  }
  bool type(const QJsonValue &v, const QString &t) const {
    if(t=="object")return v.isObject(); if(t=="array")return v.isArray(); if(t=="string")return v.isString();
    if(t=="number")return v.isDouble(); if(t=="integer")return v.isDouble() && std::floor(v.toDouble())==v.toDouble();
    if(t=="boolean")return v.isBool(); if(t=="null")return v.isNull(); throw std::runtime_error("unknown schema type");
  }
  void check(const QJsonValue &v, QJsonObject s, QJsonObject document, const QString &p, int depth=0) const {
    require(depth<64, "schema recursion");
    if(s.contains("$ref")) { auto target=resolve(s,document); check(v,target,document,p,depth+1); s.remove("$ref"); }
    static const QStringList keys={"$schema","$id","$defs","title","description","type","const","enum","required","properties","additionalProperties","items","uniqueItems","minItems","maxItems","minimum","maximum","exclusiveMinimum","exclusiveMaximum","minLength","maxLength","pattern","format","oneOf","anyOf","allOf","default","examples"};
    for(auto it=s.begin();it!=s.end();++it)require(keys.contains(it.key()),"unsupported schema keyword: "+it.key());
    if(s.contains("type")) { auto t=s["type"]; bool ok=false; if(t.isString())ok=type(v,t.toString()); else for(auto x:t.toArray())ok=ok||type(v,x.toString()); require(ok,p+": type"); }
    if(s.contains("const"))require(v==s["const"],p+": const");
    if(s.contains("enum"))require(s["enum"].toArray().contains(v),p+": enum");
    for(auto keyword:{"oneOf","anyOf","allOf"}) if(s.contains(keyword)) {
      int count=0; auto variants=s[keyword].toArray();
      for(auto x:variants) { try{check(v,x.toObject(),document,p,depth+1);++count;}catch(const std::exception&){} }
      require(QString(keyword)=="oneOf" ? count==1 : QString(keyword)=="allOf" ? count==variants.size() : count>0,p+": "+keyword);
    }
    if(v.isObject()) {
      auto o=v.toObject(); for(auto x:s["required"].toArray())require(o.contains(x.toString()),p+": missing "+x.toString());
      auto props=s["properties"].toObject();
      for(auto it=o.begin();it!=o.end();++it) {
        if(props.contains(it.key())) check(it.value(),props[it.key()].toObject(),document,p+"/"+it.key(),depth+1);
        else if(s.contains("additionalProperties")) { auto a=s["additionalProperties"]; require(a!=QJsonValue(false),p+": unexpected "+it.key()); if(a.isObject())check(it.value(),a.toObject(),document,p+"/"+it.key(),depth+1); }
      }
    }
    if(v.isArray()) {
      auto a=v.toArray(); if(s.contains("minItems"))require(a.size()>=s["minItems"].toInt(),p+": minItems"); if(s.contains("maxItems"))require(a.size()<=s["maxItems"].toInt(),p+": maxItems");
      for(qsizetype i=0;i<a.size();++i) { if(s.contains("items"))check(a[i],s["items"].toObject(),document,p+"/"+QString::number(i),depth+1); if(s["uniqueItems"].toBool()) for(qsizetype j=0;j<i;++j)require(a[i]!=a[j],p+": uniqueItems"); }
    }
    if(v.isString()) {
      auto t=v.toString(); if(s.contains("minLength"))require(t.size()>=s["minLength"].toInt(),p+": minLength"); if(s.contains("maxLength"))require(t.size()<=s["maxLength"].toInt(),p+": maxLength");
      if(s.contains("pattern")){ QRegularExpression re(s["pattern"].toString());require(re.isValid()&&re.match(t).hasMatch(),p+": pattern"); }
      if(s.contains("format")){require(s["format"]=="date-time","unsupported format");QRegularExpression re("^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d+)?(?:Z|[+-]\\d{2}:\\d{2})$");require(re.match(t).hasMatch()&&QDateTime::fromString(t,Qt::ISODateWithMs).isValid(),p+": date-time");}
    }
    if(v.isDouble()) {
      double n=v.toDouble(); require(std::isfinite(n),p+": nonfinite");
      if(s.contains("minimum"))require(n>=s["minimum"].toDouble(),p+": minimum"); if(s.contains("maximum"))require(n<=s["maximum"].toDouble(),p+": maximum");
      if(s.contains("exclusiveMinimum"))require(n>s["exclusiveMinimum"].toDouble(),p+": exclusiveMinimum"); if(s.contains("exclusiveMaximum"))require(n<s["exclusiveMaximum"].toDouble(),p+": exclusiveMaximum");
    }
  }
 public:
  explicit Schemas(QString dir):directory(std::move(dir)){}
  void validate(const QJsonValue &v,const QString &file)const { auto doc=object(directory+"/"+file);check(v,doc,doc,file); }
};
const QStringList filenames={"run_request.json","t0_run_manifest.json","t0_metrics.json","artifacts.json"};
const QStringList schemafiles={"run_request.schema.json","run_manifest.schema.json","metrics.schema.json","artifacts.schema.json"};
void validateSitlRunArtifacts(const QString &run,const QString &root,const QJsonObject &request,const QJsonObject &manifest);
void validateRun(const QString &run,const QString &workspace) {
  Schemas schemas(workspace+"/configs/visualization/schemas"); QVector<QJsonObject> docs;
  for(int i=0;i<4;++i){auto o=object(run+"/"+filenames[i]); schemas.validate(o,schemafiles[i]);docs.push_back(o);}
  const auto &request=docs[0];const auto &manifest=docs[1];auto id=manifest["run_id"].toString();
  require(manifest["request_id"]==request["request_id"],"request id mismatch");
  for(auto key:{"simulation_id","variant_id","inputs","parameters"})require(manifest[key]==request[key],QString("request/manifest mismatch: ")+key);
  for(int i:{2,3})require(docs[i]["run_id"]==id,"run id mismatch");require(docs[2]["simulation_id"]==manifest["simulation_id"],"metrics simulation mismatch");
  auto state=manifest["state"].toString();require(QStringList{"completed","cancelled","failed"}.contains(state),"run not finalized");
  auto start=QDateTime::fromString(manifest["started_at_utc"].toString(),Qt::ISODateWithMs);auto end=QDateTime::fromString(manifest["finished_at_utc"].toString(),Qt::ISODateWithMs);
  require(start.isValid()&&end.isValid()&&end>=start,"invalid final timestamps");
  require(QDateTime::fromString(request["requested_at_utc"].toString(),Qt::ISODateWithMs)<=start&&QDateTime::fromString(manifest["created_at_utc"].toString(),Qt::ISODateWithMs)<=start,"request or creation occurs after execution start");
  if(state=="completed")require(docs[2]["status"]=="complete","completed run metrics incomplete");
  for(auto x:manifest["inputs"].toArray()) { auto o=x.toObject();auto ref=o["reference"].toObject();require(ref.contains("path")&&o["checksums"].toObject().contains("sha256"),"input path/hash missing");require(sha(safePath(workspace,ref["path"].toString()))==o["checksums"].toObject()["sha256"],"input hash mismatch"); }
  QSet<QString> artifactIds; for(auto x:docs[3]["items"].toArray()){auto a=x.toObject();auto aid=a["artifact_id"].toString();require(!artifactIds.contains(aid),"duplicate artifact id");artifactIds.insert(aid);require(a.contains("checksum_sha256"),"artifact hash missing");require(sha(safePath(run,a["path"].toString()))==a["checksum_sha256"],"artifact hash mismatch");}
  for(auto x:manifest["files"].toObject())if(!x.isNull())safePath(run,x.toString());
  auto lines=read(run+"/events.jsonl").split('\n');int sequence=0;QString last;
  for(auto line:lines)if(!line.trimmed().isEmpty()){QJsonParseError e;auto d=QJsonDocument::fromJson(line,&e);require(e.error==QJsonParseError::NoError&&d.isObject(),"event JSON");auto event=d.object();schemas.validate(event,"event.schema.json");require(event["run_id"]==id && event["sequence"].toInt()==sequence++,"event identity/sequence");last=event["state"].toString();}
  require(sequence>0&&last==state,"missing matching terminal event");
  if(request["simulation_id"]=="px4_offboard")validateSitlRunArtifacts(run,workspace,request,manifest);
}
QString git(const QString &root,QStringList args){QProcess p;p.setWorkingDirectory(root);p.start("git",args);require(p.waitForFinished(10000)&&p.exitCode()==0,"git provenance unavailable");return QString::fromUtf8(p.readAllStandardOutput()).trimmed();}
QJsonArray inputReferences(const QString &root){
  QJsonArray inputs;for(auto path:QStringList{"simulation/energy/calibration_proxy.json","simulation/energy/evaluation_campaign.json","simulation/gazebo/models/cartographe/geometry/geometry_manifest.json","simulation/gazebo/models/cartographe/geometry/mass_ledger.json","simulation/gazebo/models/cartographe/geometry/collision_model.json","simulation/gazebo/models/cartographe/dynamics_preview.json","simulation/gazebo/models/cartographe/model.sdf"}){auto f=safePath(root,path);inputs.append(QJsonObject{{"input_id",QFileInfo(path).completeBaseName().replace('.','_')},{"kind","model"},{"reference",QJsonObject{{"path",path}}},{"checksums",QJsonObject{{"sha256",sha(f)}}}});}return inputs;
}
void prepare(const QString &run,const QString &root){
  require(!QFileInfo::exists(run+"/run_request.json")&&!QFileInfo::exists(run+"/t0_run_manifest.json"),"refuse existing request/run");require(QDir().mkpath(run),"prepare directory");auto id=QFileInfo(run).fileName();
  QJsonObject request{{"schema","drone_agricole.run_request.v1"},{"request_id",id+"_request"},{"simulation_id","cartographe_energy"},{"variant_id","proxy"},{"requested_at_utc",stamp()},{"inputs",inputReferences(root)},{"parameters",QJsonObject{{"execution","offline_energy"},{"physical_fidelity","unvalidated"}}}};
  Schemas(root+"/configs/visualization/schemas").validate(request,"run_request.schema.json");write(run+"/run_request.json",request);
}
void seal(const QString &raw,const QString &run,const QString &root) {
  auto campaign=object(raw);QDir().mkpath(run);require(!QFileInfo::exists(run+"/t0_run_manifest.json"),"refuse overwrite finalized run");
  require(campaign["kind"]=="cartographe_energy_campaign" && campaign["execution"]=="offline_deterministic_cpp17" && campaign["simulation_finalized"]==true && campaign["px4_connected"]==false,"unfinalized or unexpected raw campaign");
  require(campaign["calibration_sha256"]==sha(root+"/simulation/energy/calibration_proxy.json")&&campaign["evaluation_sha256"]==sha(root+"/simulation/energy/evaluation_campaign.json"),"raw campaign configuration mismatch");
  auto csvPath=QFileInfo(raw).absolutePath()+"/samples.csv";require(campaign["csv_sha256"]==sha(csvPath),"raw CSV hash mismatch");
  auto runs=campaign["runs"].toArray();require(!runs.isEmpty()&&campaign["run_count"].toInt()==runs.size(),"raw campaign run count");
  for(auto value:runs){auto r=value.toObject();require(r["simulation_finalized"]==true&&!r["end_reason"].toString().isEmpty()&&r["elapsed_s"].isDouble()&&r["landing_observed"]==false,"raw run not finalized");}
  auto executionPath=QDir(root).relativeFilePath(campaign["executable_path"].toString());require(campaign["executable_sha256"]==sha(safePath(root,executionPath)),"execution binary unavailable or changed before sealing");
  auto now=stamp();auto id=QFileInfo(run).fileName(); auto inputs=inputReferences(root);
  QJsonObject parameters{{"execution","offline_energy"},{"physical_fidelity","unvalidated"}};
  auto request=object(run+"/run_request.json");Schemas(root+"/configs/visualization/schemas").validate(request,"run_request.schema.json");
  require(request["inputs"].toArray()==inputs&&request["parameters"].toObject()==parameters&&request["simulation_id"]=="cartographe_energy"&&request["variant_id"]=="proxy"&&request["request_id"]==id+"_request","prepared request changed or mismatched");
  auto commit=git(root,{"rev-parse","HEAD"}); auto status=git(root,{"status","--porcelain"});
  QJsonObject sources;QDir sourceDir(root+"/simulation");for(auto sub:{"energy","contracts"})for(auto f:QDir(sourceDir.filePath(sub)).entryList({"*.cpp","*.hpp"},QDir::Files))sources[QString(sub)+"/"+f]=sha(sourceDir.filePath(QString(sub)+"/"+f));
  QJsonObject manifest{{"schema","drone_agricole.run_manifest.v1"},{"run_id",id},{"request_id",request["request_id"]},{"simulation_id",request["simulation_id"]},{"variant_id",request["variant_id"]},{"runner_id","cartographe_energy_cpp17"},{"domain","simulation"},{"state","completed"},{"created_at_utc",now},{"started_at_utc",now},{"finished_at_utc",now},{"inputs",inputs},{"parameters",parameters},{"software",QJsonObject{{"git_commit",commit},{"git_dirty",!status.isEmpty()},{"source_sha256",sources},{"qt_version",qVersion()},{"compiler",__VERSION__},{"architecture",QSysInfo::currentCpuArchitecture()},{"os",QSysInfo::prettyProductName()},{"docker_image",QJsonValue::Null}}},{"files",QJsonObject{{"campaign","campaign.json"},{"metrics","t0_metrics.json"},{"events","events.jsonl"}}},{"compatibility",QJsonObject{{"comparison_group","cartographe_proxy_offline"},{"result_contract_version",1}}},{"metadata",QJsonObject{{"conclusion","préliminaire"},{"sitl_executed",false},{"timestamp_scope","T0 packaging time; simulation has no wall-time flight"}}}};
  QJsonObject metrics{{"schema","drone_agricole.metrics.v1"},{"run_id",id},{"simulation_id",request["simulation_id"]},{"status","complete"},{"summary",QJsonArray{}},{"groups",QJsonObject{{"energy_campaign",campaign}}}};
  auto csv=read(csvPath);{QSaveFile f(run+"/samples.csv");require(f.open(QIODevice::WriteOnly)&&f.write(csv)==csv.size()&&f.commit(),"CSV commit");}
  auto start=campaign["started_at_utc"].toString(),finish=campaign["finished_at_utc"].toString();require(QDateTime::fromString(start,Qt::ISODateWithMs).isValid()&&QDateTime::fromString(finish,Qt::ISODateWithMs).isValid(),"campaign timestamps missing");manifest["started_at_utc"]=start;manifest["finished_at_utc"]=finish;
  manifest["created_at_utc"]=request["requested_at_utc"];
  auto software=manifest["software"].toObject();software["execution_binary_sha256"]=campaign["executable_sha256"];software["execution_binary_path"]=executionPath;software["source_hash_scope"]="sources observed at sealing; actual execution identified by binary SHA in raw campaign";manifest["software"]=software;
  manifest["metadata"]=QJsonObject{{"conclusion","préliminaire"},{"sitl_executed",false},{"timestamp_scope","energy CLI wall time, synthetic simulation time in campaign"},{"sealed_at_utc",now}};
  write(run+"/campaign.json",campaign);write(run+"/run_request.json",request);write(run+"/t0_metrics.json",metrics);
  QJsonObject event{{"schema","drone_agricole.event.v1"},{"run_id",id},{"sequence",0},{"timestamp_utc",now},{"event_type","campaign_finalized"},{"severity","warning"},{"state","completed"},{"message","Offline synthetic energy campaign; no PX4 or physical fidelity claim"},{"data",QJsonObject{}}};
  {QSaveFile f(run+"/events.jsonl");auto b=QJsonDocument(event).toJson(QJsonDocument::Compact)+"\n";require(f.open(QIODevice::WriteOnly)&&f.write(b)==b.size()&&f.commit(),"events commit");}
  QJsonArray artifacts;for(auto file:QStringList{"campaign.json","events.jsonl","t0_metrics.json","run_request.json","samples.csv"})artifacts.append(QJsonObject{{"artifact_id",file.split('.').first()},{"kind",file=="events.jsonl"?"events":file=="t0_metrics.json"?"metrics":"configuration"},{"label",file},{"path",file},{"media_type",file.endsWith("csv")?"text/csv":"application/json"},{"role","output"},{"replayable",true},{"checksum_sha256",sha(run+"/"+file)}});
  write(run+"/artifacts.json",QJsonObject{{"schema","drone_agricole.artifacts.v1"},{"run_id",id},{"items",artifacts}});
  write(run+"/t0_run_manifest.json",manifest);
  try{validateRun(run,root);}catch(...){manifest["state"]="failed";manifest["metadata"]=QJsonObject{{"finalization_validated",false}};write(run+"/t0_run_manifest.json",manifest);throw;}
}
void execute(const QString &rawDirectory,const QString &run,const QString &root){
  prepare(run,root);auto executable=QFileInfo(QCoreApplication::applicationFilePath()).absolutePath()+"/cartographe-energy";
#ifdef Q_OS_WIN
  executable+=".exe";
#endif
  QProcess p;p.setWorkingDirectory(root);p.start(executable,{"--calibration",root+"/simulation/energy/calibration_proxy.json","--campaign",root+"/simulation/energy/evaluation_campaign.json","--output",rawDirectory});
  require(p.waitForStarted(5000),"energy CLI unavailable");if(!p.waitForFinished(60000)){p.kill();p.waitForFinished(5000);throw std::runtime_error("energy process wall-time exceeded; no completion declared");}
  require(p.exitStatus()==QProcess::NormalExit&&p.exitCode()==0,"energy process failed; no completion declared");seal(rawDirectory+"/energy_raw.json",run,root);std::cout<<p.readAllStandardOutput().toStdString();
}

QString sitlModel(QString model){if(model=="carto")model="cartographe";require(model=="x500"||model=="cartographe","SITL model must be x500 or cartographe");return model;}
QJsonObject sitlParameters(const QString &model,const QString &mode){
  require(QStringList{"square","failsafe","cancel"}.contains(mode),"SITL mode must be square, failsafe or cancel");
  return {{"model",sitlModel(model)},{"mode",mode},{"runner_mode",mode=="cancel"?"square":mode},{"takeoff_altitude_m",2.0},{"leg_m",2.0},{"warmup_s",2.0},{"hover_s",3.0},{"stage_timeout_s",12.0},{"execute",true},{"DRONE_AGRICOLE_SITL","1"}};
}
QJsonArray sitlInputs(const QString &root,const QString &model){
  QStringList paths{"compose.yaml","software/docker/Dockerfile","simulation/px4_sitl/preflight.ps1"};
  const QString ros="software/src/drone_agricole_px4_bridge/";
  for(auto file:{"CMakeLists.txt","package.xml","src/RunnerServer.cpp","src/RunnerContract.cpp","src/OffboardTest.cpp","src/OffboardPlan.cpp","src/Frames.cpp","include/drone_agricole_px4_bridge/OffboardSafety.hpp","include/drone_agricole_px4_bridge/OffboardPlan.hpp","include/drone_agricole_px4_bridge/RunnerContract.hpp","include/drone_agricole_px4_bridge/Frames.hpp"})paths.append(ros+file);
  if(model=="cartographe")paths.append({"simulation/compose.cartographe.yaml","simulation/px4_sitl/airframes/40000_gz_cartographe","simulation/gazebo/models/cartographe/model.sdf","simulation/gazebo/worlds/cartographe_flat.sdf","simulation/gazebo/models/cartographe/dynamics_preview.json"});
  QJsonArray inputs;int n=0;for(const auto &path:paths)inputs.append(QJsonObject{{"input_id",QString("sitl_source_%1").arg(n++)},{"kind","other"},{"reference",QJsonObject{{"path",path}}},{"checksums",QJsonObject{{"sha256",sha(safePath(root,path))}}}});return inputs;
}
QString insideWorkspaceDirectory(const QString &run,const QString &root){
  auto relative=QDir(root).relativeFilePath(QDir(run).absolutePath());require(!QDir::isAbsolutePath(relative)&&relative!=".."&&!relative.startsWith("../")&&!relative.contains(':'),"SITL run directory must stay in workspace");
  auto ancestor=QFileInfo(QDir(run).absolutePath());while(!ancestor.exists()){auto parent=QFileInfo(ancestor.absolutePath());require(parent.absoluteFilePath()!=ancestor.absoluteFilePath(),"SITL output has no existing workspace ancestor");ancestor=parent;}
  auto canonical=ancestor.canonicalFilePath(),canonicalRoot=QFileInfo(root).canonicalFilePath();require(canonical==canonicalRoot||canonical.startsWith(canonicalRoot+"/"),"SITL output escapes workspace through a symlink");return relative;
}
void writeBytes(const QString &path,const QByteArray &bytes);
QJsonArray snapshotSitlInputs(const QString &run,const QString &root,const QJsonArray &liveInputs){
  const auto prefix=insideWorkspaceDirectory(run,root)+"/source_snapshot/";QJsonArray references,inventory;
  for(const auto &value:liveInputs){
    auto input=value.toObject();auto sourcePath=input["reference"].toObject()["path"].toString();const auto source=safePath(root,sourcePath);auto bytes=read(source);
    const auto relative="source_snapshot/"+sourcePath;const auto target=QDir(run).filePath(relative);require(!QFileInfo::exists(target),"refuse existing SITL source snapshot: "+relative);require(QDir().mkpath(QFileInfo(target).absolutePath()),"source snapshot directory");writeBytes(target,bytes);
    const QJsonValue checksum=input["checksums"].toObject()["sha256"];require(sha(target)==checksum&&sha(source)==checksum,"SITL source changed while preparing snapshot");
    input["reference"]=QJsonObject{{"path",prefix+sourcePath},{"source_path",sourcePath},{"source_scope","workspace source copied before execution"}};references.append(input);
    inventory.append(QJsonObject{{"input_id",input["input_id"]},{"source_path",sourcePath},{"snapshot_path",relative},{"sha256",checksum}});
  }
  write(run+"/source_snapshot/manifest.json",QJsonObject{{"schema","drone_agricole.sitl_source_snapshot.v1"},{"created_at_utc",stamp()},{"items",inventory}});return references;
}
QJsonArray validateSitlSnapshots(const QString &run,const QString &root,const QJsonObject &request,bool checkLiveSources){
  auto inventory=object(safePath(run,"source_snapshot/manifest.json"));require(inventory["schema"]=="drone_agricole.sitl_source_snapshot.v1"&&inventory["items"].isArray(),"invalid SITL source snapshot inventory");
  auto inputs=request["inputs"].toArray(),items=inventory["items"].toArray();require(!inputs.isEmpty()&&inputs.size()==items.size(),"SITL snapshot inventory/input count mismatch");
  const auto prefix=insideWorkspaceDirectory(run,root)+"/";QSet<QString> sources;QJsonArray originalReferences;
  for(qsizetype i=0;i<inputs.size();++i){
    auto input=inputs[i].toObject();auto item=items[i].toObject();auto ref=input["reference"].toObject();auto sourcePath=ref["source_path"].toString();const auto relative="source_snapshot/"+sourcePath;
    require(!sourcePath.isEmpty()&&!sources.contains(sourcePath),"missing or duplicate snapshot source mapping");sources.insert(sourcePath);
    require(item["input_id"]==input["input_id"]&&item["source_path"]==sourcePath&&item["snapshot_path"]==relative&&ref["path"]==prefix+relative,"SITL snapshot source mapping mismatch");
    const QJsonValue expected=input["checksums"].toObject()["sha256"];require(item["sha256"]==expected&&sha(safePath(run,relative))==expected,"SITL source snapshot hash mismatch");
    if(checkLiveSources)require(sha(safePath(root,sourcePath))==expected,"live SITL source changed since preparation: "+sourcePath);
    input["reference"]=QJsonObject{{"path",sourcePath}};originalReferences.append(input);
  }
  return originalReferences;
}
void prepareSitl(const QString &run,const QString &root,const QString &model,const QString &mode){
  insideWorkspaceDirectory(run,root);require(!QFileInfo::exists(run+"/run_request.json")&&!QFileInfo::exists(run+"/t0_run_manifest.json"),"refuse existing SITL request/run");
  auto parameters=sitlParameters(model,mode);auto id=QFileInfo(run).fileName();
  auto inputs=snapshotSitlInputs(run,root,sitlInputs(root,parameters["model"].toString()));
  QJsonObject request{{"schema","drone_agricole.run_request.v1"},{"request_id",id+"_request"},{"simulation_id","px4_offboard"},{"variant_id",parameters["model"].toString()+"_"+mode},{"requested_at_utc",stamp()},{"inputs",inputs},{"parameters",parameters},{"tags",QJsonArray{"sitl_only","orch_gz_1"}},{"note","Prepared before execution. Sources are frozen under source_snapshot; reference.source_path records their original workspace locations. Does not start any process, API request or flight command."}};
  Schemas(root+"/configs/visualization/schemas").validate(request,"run_request.schema.json");require(QDir().mkpath(run),"prepare SITL directory");write(run+"/run_request.json",request);
}
QDateTime sitlTime(const QJsonValue &value,const QString &label){
  require(value.isString(),"missing SITL timestamp: "+label);auto text=value.toString();QRegularExpression re("^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d+)?(?:Z|[+-]\\d{2}:\\d{2})$");auto date=QDateTime::fromString(text,Qt::ISODateWithMs);require(re.match(text).hasMatch()&&date.isValid(),"invalid SITL timestamp: "+label);return date;
}
QJsonObject validateSitlPayload(const QJsonObject &status,const QJsonObject &result,const QJsonObject &environment,const QJsonObject &request,const QString &id){
  auto parameters=request["parameters"].toObject();auto model=sitlModel(parameters["model"].toString());auto mode=parameters["mode"].toString();
  require(request["simulation_id"]=="px4_offboard"&&request["request_id"]==id+"_request"&&request["variant_id"]==model+"_"+mode&&parameters==sitlParameters(model,mode),"SITL prepared identity/parameters mismatch");
  auto state=status["state"].toString();require(QStringList{"completed","cancelled","failed"}.contains(state),"SITL API state is not final");
  require(status["run_id"]==id,"SITL API/request run ID mismatch");require(status["mode"]==parameters["runner_mode"],"SITL runner mode mismatch");
  require(status["exit_code"].isDouble()&&std::floor(status["exit_code"].toDouble())==status["exit_code"].toDouble(),"SITL exit code unavailable");
  require(status["result"].isObject()&&status["result"].toObject()==result,"SITL API result differs from result.json on disk");
  require(result["schema"]=="drone_agricole.px4_offboard_test.v1"&&result["success"].isBool()&&result["mode"]==parameters["runner_mode"]&&result["observations"].isObject()&&result["events"].isArray(),"invalid SITL result structure");
  for(auto key:{"takeoff_altitude_m","leg_m","warmup_s","hover_s","stage_timeout_s"}){
    require(status["parameters"].toObject()[key]==parameters[key],QString("API parameter mismatch: ")+key);
    require(result["parameters"].toObject()[key]==parameters[key],QString("result parameter mismatch: ")+key);
  }
  auto requested=sitlTime(request["requested_at_utc"],"request"),started=sitlTime(status["started_at"],"start"),finished=sitlTime(status["finished_at"],"finish"),created=sitlTime(result["created_utc"],"result");
  require(requested<=started&&started<=created&&created<=finished,"SITL request/start/result/finish timestamp order");
  require(environment["identity_verified"]==true&&environment["model"]==model,"SITL identity not verified or wrong model");
  auto images=environment["image_ids"].toObject();require(images.contains("px4")&&images.contains("ros"),"SITL PX4 and ROS exact image IDs missing");QRegularExpression imagePattern("^sha256:[a-f0-9]{64}$");
  for(auto value:images)require(value.isString()&&imagePattern.match(value.toString()).hasMatch(),"SITL image ID must be exact sha256");
  for(auto key:{"preflight","px4_parameters","topic_freshness","battery"})require(environment[key].isObject()&&!environment[key].toObject().isEmpty(),QString("SITL environment missing: ")+key);
  auto observations=result["observations"].toObject();
  if(state=="completed"||state=="cancelled")require(observations["landing_confirmed"]==true&&observations["landed"]==true,"SITL final state lacks fresh landed/disarmed confirmation");
  if(state=="completed")require(status["exit_code"]==0&&result["success"]==true&&observations["offboard_entered"]==true&&mode!="cancel","SITL completed state inconsistent with outcome");
  if(state=="cancelled")require(mode=="cancel"&&(status["exit_code"]==0||status["exit_code"]==1)&&result["reason"]=="signal_interrupt","SITL cancellation lacks matching requested interrupt/outcome");
  auto resultDirectory=status["result_directory"].toString();require(!QDir::isAbsolutePath(resultDirectory)&&!resultDirectory.contains('\\')&&QDir::cleanPath(resultDirectory)==resultDirectory&&resultDirectory.startsWith("results/simulation/px4_lot_a/")&&!resultDirectory.contains("/../")&&QFileInfo(resultDirectory).fileName()==id,"SITL result directory/identity mismatch");
  double previous=-1;auto wallDuration=started.msecsTo(finished)/1000.0;for(auto event:result["events"].toArray()){
    require(event.isObject(),"SITL source event is not an object");auto item=event.toObject();auto time=item["elapsed_s"];require(time.isDouble()&&std::isfinite(time.toDouble())&&time.toDouble()>=0&&time.toDouble()>=previous&&time.toDouble()<=wallDuration+1,"SITL event time is invalid or outside execution");require(item["event"].isString()&&!item["event"].toString().isEmpty(),"SITL source event name missing");previous=time.toDouble();
  }
  require(!result["events"].toArray().isEmpty()&&result["events"].toArray().last().toObject()["event"]=="test_finished","SITL result has no terminal test_finished source event");
  if(state=="completed"&&mode=="failsafe"){
    bool streamStopped=false,expectedLanding=false;
    for(auto value:result["events"].toArray()){
      auto event=value.toObject();if(event["event"]=="offboard_stream_stopped")streamStopped=true;
      if(event["event"]=="offboard_loss_action"){require(streamStopped&&event["expected_land"]==true,"SITL failsafe action lacks preceding stream stop or expected LAND");expectedLanding=true;}
    }
    require(streamStopped&&expectedLanding,"SITL completed failsafe lacks stop-stream then expected-LAND action evidence");
  }
  return parameters;
}
void validateSitlRunArtifacts(const QString &run,const QString &root,const QJsonObject &request,const QJsonObject &manifest){
  auto status=object(safePath(run,"sitl_status.json")),environment=object(safePath(run,"sitl_environment.json")),result=object(safePath(run,"result.json"));
  validateSitlPayload(status,result,environment,request,manifest["run_id"].toString());
  require(manifest["state"]==status["state"]&&manifest["started_at_utc"]==status["started_at"]&&manifest["finished_at_utc"]==status["finished_at"],"SITL manifest/API finalization mismatch");
  auto metrics=object(run+"/t0_metrics.json");require(metrics["status"]==(status["state"]=="completed"?"complete":"partial"),"SITL metrics terminal status mismatch");
  require(metrics["groups"].toObject()["observations"]==result["observations"]&&metrics["groups"].toObject()["api_state"]==status["state"],"SITL metrics/result mismatch");
  // Archived snapshot validation deliberately never consults the current checkout.
  // Legacy proofs keep their original live input semantics and are not rewritten.
  bool snapshots=manifest["software"].toObject().contains("source_snapshot_manifest");
  for(auto input:request["inputs"].toArray())snapshots=snapshots||input.toObject()["reference"].toObject().contains("source_path");
  if(snapshots)validateSitlSnapshots(run,root,request,false);
}
void writeBytes(const QString &path,const QByteArray &bytes){QSaveFile file(path);require(file.open(QIODevice::WriteOnly)&&file.write(bytes)==bytes.size()&&file.commit(),"atomic copy: "+path);}
void sealSitl(const QString &statusPath,const QString &run,const QString &environmentPath,const QString &root){
  insideWorkspaceDirectory(run,root);require(!QFileInfo::exists(run+"/t0_run_manifest.json"),"refuse overwrite finalized SITL run");
  auto request=object(run+"/run_request.json");Schemas(root+"/configs/visualization/schemas").validate(request,"run_request.schema.json");
  auto status=object(statusPath),environment=object(environmentPath);auto id=QFileInfo(run).fileName();
  auto resultDirectory=status["result_directory"].toString();auto resultPath=safePath(root,resultDirectory+"/result.json");auto result=object(resultPath);
  auto parameters=validateSitlPayload(status,result,environment,request,id);
  require(validateSitlSnapshots(run,root,request,true)==sitlInputs(root,parameters["model"].toString()),"SITL source inventory changed since request preparation");
  auto state=status["state"].toString(),now=stamp();auto observations=result["observations"].toObject();
  QJsonArray summary;for(auto key:{"max_altitude_m","offboard_entered","landed","landing_confirmed","failsafe","offboard_loss_flag"})if(observations.contains(key))summary.append(QJsonObject{{"metric_id",key},{"label",key},{"value",observations[key]},{"unit",QString(key)=="max_altitude_m"?"m":""},{"direction","neutral"},{"status",state=="completed"?"good":"warning"}});
  QJsonObject metrics{{"schema","drone_agricole.metrics.v1"},{"run_id",id},{"simulation_id","px4_offboard"},{"status",state=="completed"?"complete":"partial"},{"summary",summary},{"groups",QJsonObject{{"observations",observations},{"api_state",state},{"exit_code",status["exit_code"]},{"reason",result["reason"]}}},{"source",QJsonObject{{"result_path",resultDirectory+"/result.json"},{"result_sha256",sha(resultPath)}}}};
  QJsonObject software{{"git_commit",git(root,{"rev-parse","HEAD"})},{"git_dirty",!git(root,{"status","--porcelain"}).isEmpty()},{"image_ids",environment["image_ids"]},{"sealer_binary_sha256",sha(QCoreApplication::applicationFilePath())},{"source_snapshot_manifest","source_snapshot/manifest.json"},{"source_scope","request inputs reference immutable copies; original workspace paths are recorded in reference.source_path"},{"qt_version",qVersion()},{"architecture",QSysInfo::currentCpuArchitecture()},{"os",QSysInfo::prettyProductName()}};
  QJsonObject manifest{{"schema","drone_agricole.run_manifest.v1"},{"run_id",id},{"request_id",request["request_id"]},{"simulation_id","px4_offboard"},{"variant_id",request["variant_id"]},{"runner_id","px4_offboard_api_cpp17"},{"domain","simulation"},{"state",state},{"created_at_utc",request["requested_at_utc"]},{"started_at_utc",status["started_at"]},{"finished_at_utc",status["finished_at"]},{"inputs",request["inputs"]},{"parameters",parameters},{"software",software},{"files",QJsonObject{{"result","result.json"},{"api_status","sitl_status.json"},{"environment","sitl_environment.json"},{"metrics","t0_metrics.json"},{"events","events.jsonl"}}},{"compatibility",QJsonObject{{"comparison_group","px4_offboard_"+parameters["model"].toString()},{"result_contract_version",1}}},{"metadata",QJsonObject{{"sitl_executed",true},{"physical_qualification",false},{"sealed_at_utc",now},{"conclusion",state=="completed"?"conforme":state=="cancelled"?"préliminaire":"non conforme"},{"landing_confirmed",observations["landing_confirmed"]},{"battery_scope","See captured source; SITL discharge is not a physical autonomy estimate."}}}};
  QByteArray events;int sequence=0;auto start=sitlTime(status["started_at"],"start");
  for(auto source:result["events"].toArray()){
    auto item=source.toObject();QJsonObject event{{"schema","drone_agricole.event.v1"},{"run_id",id},{"sequence",sequence++},{"timestamp_utc",start.addMSecs(qRound64(item["elapsed_s"].toDouble()*1000)).toString(Qt::ISODateWithMs)},{"elapsed_s",item["elapsed_s"]},{"event_type","px4_runner_event"},{"severity","info"},{"state",item["state"]},{"message",item["event"]},{"data",item}};events+=QJsonDocument(event).toJson(QJsonDocument::Compact)+"\n";
  }
  QJsonObject terminal{{"schema","drone_agricole.event.v1"},{"run_id",id},{"sequence",sequence},{"timestamp_utc",status["finished_at"]},{"event_type","sitl_finalized"},{"severity",state=="failed"?"error":state=="cancelled"?"warning":"info"},{"state",state},{"message","Actual API state and disk result sealed; landing confirmation preserved."},{"data",QJsonObject{{"exit_code",status["exit_code"]},{"landing_confirmed",observations["landing_confirmed"]}}}};events+=QJsonDocument(terminal).toJson(QJsonDocument::Compact)+"\n";
  // Freeze external inputs byte-for-byte before hashing the output inventory.
  const auto statusBytes=read(statusPath),environmentBytes=read(environmentPath),resultBytes=read(resultPath);
  require(QJsonDocument::fromJson(statusBytes).object()==status&&QJsonDocument::fromJson(environmentBytes).object()==environment&&QJsonDocument::fromJson(resultBytes).object()==result,"SITL inputs changed while sealing");
  writeBytes(run+"/sitl_status.json",statusBytes);writeBytes(run+"/sitl_environment.json",environmentBytes);writeBytes(run+"/result.json",resultBytes);write(run+"/t0_metrics.json",metrics);writeBytes(run+"/events.jsonl",events);
  QJsonArray artifacts;for(const auto &file:QStringList{"run_request.json","result.json","sitl_status.json","sitl_environment.json","t0_metrics.json","events.jsonl"})artifacts.append(QJsonObject{{"artifact_id",file.split('.').first()},{"kind",file=="events.jsonl"?"events":file=="t0_metrics.json"?"metrics":"configuration"},{"label",file},{"path",file},{"media_type",file=="events.jsonl"?"application/x-ndjson":"application/json"},{"role",file=="result.json"?"source":"output"},{"replayable",true},{"checksum_sha256",sha(run+"/"+file)}});
  artifacts.append(QJsonObject{{"artifact_id","source_snapshot_inventory"},{"kind","configuration"},{"label","Frozen SITL source inventory"},{"path","source_snapshot/manifest.json"},{"media_type","application/json"},{"role","source"},{"replayable",true},{"checksum_sha256",sha(run+"/source_snapshot/manifest.json")}});
  for(auto value:request["inputs"].toArray()){
    auto input=value.toObject();auto source=input["reference"].toObject()["source_path"].toString();auto relative="source_snapshot/"+source;
    artifacts.append(QJsonObject{{"artifact_id",input["input_id"]},{"kind","configuration"},{"label",source},{"path",relative},{"media_type","text/plain"},{"role","source"},{"replayable",true},{"checksum_sha256",sha(safePath(run,relative))},{"metadata",QJsonObject{{"original_workspace_path",source}}}});
  }
  write(run+"/artifacts.json",QJsonObject{{"schema","drone_agricole.artifacts.v1"},{"run_id",id},{"items",artifacts}});write(run+"/t0_run_manifest.json",manifest);
  try{validateRun(run,root);}catch(...){manifest["state"]="failed";auto metadata=manifest["metadata"].toObject();metadata["finalization_validated"]=false;manifest["metadata"]=metadata;write(run+"/t0_run_manifest.json",manifest);throw;}
}

void selfTestSitl(const QString &root){
  const auto directory=root+"/.runtime";require(QDir().mkpath(directory),"SITL fixture root");QTemporaryDir temp(directory+"/sitl-t0-XXXXXX");require(temp.isValid(),"SITL temporary fixture");
  const auto rawBase=root+"/results/simulation/px4_lot_a";require(QDir().mkpath(rawBase),"SITL raw fixture root");QTemporaryDir results(rawBase+"/sitl-fixture-XXXXXX");require(results.isValid(),"SITL raw temporary fixture");
  int positive=0,negative=0,index=0;
  auto fixture=[&](QString state,QString mode,const std::function<void(QJsonObject&,QJsonObject&,QJsonObject&,QJsonObject&)>& mutate,bool reject){
    auto id=QString("sitl_fixture_%1").arg(index++);auto run=temp.path()+"/"+id;prepareSitl(run,root,"x500",mode);auto req=object(run+"/run_request.json");auto p=req["parameters"].toObject();QJsonObject numeric;for(auto key:{"takeoff_altitude_m","leg_m","warmup_s","hover_s","stage_timeout_s"})numeric[key]=p[key];
    auto begin=QDateTime::currentDateTimeUtc().addSecs(1);auto end=begin.addSecs(4);
    QJsonObject result{{"schema","drone_agricole.px4_offboard_test.v1"},{"created_utc",end.addMSecs(-50).toString(Qt::ISODateWithMs)},{"success",state=="completed"},{"reason",mode=="cancel"?"signal_interrupt":state=="failed"?"test_failure":"mission_complete"},{"mode",p["runner_mode"]},{"parameters",numeric},{"observations",QJsonObject{{"offboard_entered",true},{"landed",state!="failed"},{"landing_confirmed",state!="failed"},{"max_altitude_m",2.0}}},{"events",QJsonArray{QJsonObject{{"event","test_finished"},{"elapsed_s",3.9},{"state","finished"}}}}};
    if(state=="completed"&&mode=="failsafe")result["events"]=QJsonArray{QJsonObject{{"event","offboard_stream_stopped"},{"elapsed_s",0.5},{"state","failsafe_gap"}},QJsonObject{{"event","offboard_loss_action"},{"elapsed_s",1.0},{"expected_land",true},{"state","failsafe_gap"}},QJsonObject{{"event","test_finished"},{"elapsed_s",3.9},{"state","finished"}}};
    auto raw=results.path()+"/"+id;require(QDir().mkpath(raw),"SITL raw fixture mkdir");auto relative=QDir(root).relativeFilePath(raw);
    QJsonObject status{{"state",state},{"run_id",id},{"mode",p["runner_mode"]},{"parameters",numeric},{"result_directory",relative},{"started_at",begin.toString(Qt::ISODateWithMs)},{"finished_at",end.toString(Qt::ISODateWithMs)},{"exit_code",state=="completed"?0:1},{"result",result}};
    QJsonObject environment{{"identity_verified",true},{"model","x500"},{"image_ids",QJsonObject{{"px4","sha256:"+QString(64,'a')},{"ros","sha256:"+QString(64,'b')}}},{"preflight",QJsonObject{{"fixture",true}}},{"px4_parameters",QJsonObject{{"fixture",true}}},{"topic_freshness",QJsonObject{{"fixture",true}}},{"battery",QJsonObject{{"source","fixture_only"}}}};
    mutate(status,result,environment,req);write(raw+"/result.json",result);write(run+"/run_request.json",req);auto statusPath=temp.path()+"/status.json",envPath=temp.path()+"/environment.json";write(statusPath,status);write(envPath,environment);
    bool refused=false;try{sealSitl(statusPath,run,envPath,root);validateRun(run,root);}catch(const std::exception&){refused=true;}
    require(refused==reject,QString("SITL fixture unexpected outcome %1").arg(id));if(reject)++negative;else{++positive;require(object(run+"/t0_run_manifest.json")["state"]==state,"SITL failed/cancelled state rewritten");}
  };
  auto noop=[](QJsonObject&,QJsonObject&,QJsonObject&,QJsonObject&){};
  fixture("completed","square",noop,false);fixture("cancelled","cancel",noop,false);fixture("failed","failsafe",noop,false);fixture("completed","failsafe",noop,false);
  fixture("completed","square",[](auto&,auto&,auto& env,auto&){env["identity_verified"]=false;},true);
  fixture("completed","square",[](auto&,auto&,auto& env,auto&){env["model"]="cartographe";},true);
  fixture("completed","square",[](auto& status,auto& result,auto&,auto&){auto obs=result["observations"].toObject();obs["landing_confirmed"]=false;result["observations"]=obs;status["result"]=result;},true);
  fixture("completed","square",[](auto& status,auto& result,auto&,auto&){auto obs=result["observations"].toObject();obs["landed"]=false;result["observations"]=obs;status["result"]=result;},true);
  fixture("completed","square",[](auto& status,auto&,auto&,auto&){status["run_id"]="wrong_id";},true);
  fixture("completed","square",[](auto& status,auto&,auto&,auto&){status["result_directory"]="results/simulation/px4_lot_a/wrong_id";},true);
  fixture("completed","square",[](auto& status,auto&,auto&,auto&){status["started_at"]="2000-01-01T00:00:00Z";},true);
  fixture("completed","square",[](auto& status,auto&,auto&,auto&){status["finished_at"]="invalid";},true);
  fixture("completed","square",[](auto& status,auto&,auto&,auto&){status["exit_code"]=2;},true);
  fixture("completed","square",[](auto& status,auto&,auto&,auto&){status["mode"]="failsafe";},true);
  fixture("completed","square",[](auto&,auto& result,auto&,auto&){result["success"]=false;},true);
  fixture("completed","square",[](auto&,auto&,auto& env,auto&){env["image_ids"]=QJsonObject{{"px4","latest"}};},true);
  fixture("completed","square",[](auto&,auto&,auto&,auto& req){auto inputs=req["inputs"].toArray();auto in=inputs[0].toObject();in["checksums"]=QJsonObject{{"sha256",QString(64,'0')}};inputs[0]=in;req["inputs"]=inputs;},true);
  fixture("completed","square",[](auto& status,auto& result,auto&,auto&){result["events"]=QJsonArray{};status["result"]=result;},true);
  fixture("completed","square",[](auto& status,auto& result,auto&,auto&){result["events"]=QJsonArray{QJsonObject{{"event","test_finished"},{"elapsed_s",-1}}};status["result"]=result;},true);
  fixture("completed","square",[](auto& status,auto& result,auto&,auto&){result["created_utc"]="2000-01-01T00:00:00Z";status["result"]=result;},true);
  fixture("completed","square",[](auto&,auto&,auto& env,auto&){env.remove("topic_freshness");},true);
  fixture("completed","square",[](auto& status,auto&,auto&,auto&){auto p=status["parameters"].toObject();p["stage_timeout_s"]=30;status["parameters"]=p;},true);
  fixture("completed","square",[](auto&,auto&,auto&,auto& req){req["inputs"]=QJsonArray{};},true);
  fixture("completed","square",[&](auto&,auto&,auto&,auto& req){auto path=req["inputs"].toArray().first().toObject()["reference"].toObject()["path"].toString();require(QFile::remove(safePath(root,path)),"remove snapshot fixture");},true);
  fixture("completed","square",[&](auto&,auto&,auto&,auto& req){auto path=req["inputs"].toArray().first().toObject()["reference"].toObject()["path"].toString();writeBytes(safePath(root,path),"changed snapshot\n");},true);
  fixture("completed","square",[&](auto&,auto&,auto&,auto& req){auto path=req["inputs"].toArray().first().toObject()["reference"].toObject()["path"].toString();auto inventory=path.left(path.indexOf("/source_snapshot/"))+"/source_snapshot/manifest.json";require(QFile::remove(safePath(root,inventory)),"remove snapshot inventory fixture");},true);
  fixture("completed","square",[](auto& status,auto& result,auto&,auto&){auto p=result["parameters"].toObject();p.remove("stage_timeout_s");result["parameters"]=p;status["result"]=result;},true);
  fixture("completed","failsafe",[](auto& status,auto& result,auto&,auto&){auto events=result["events"].toArray();events.removeFirst();result["events"]=events;status["result"]=result;},true);
  fixture("completed","failsafe",[](auto& status,auto& result,auto&,auto&){auto events=result["events"].toArray();auto action=events[1].toObject();action["expected_land"]=false;events[1]=action;result["events"]=events;status["result"]=result;},true);
  fixture("completed","failsafe",[](auto& status,auto& result,auto&,auto&){auto events=result["events"].toArray();auto action=events[1].toObject();action.remove("expected_land");events[1]=action;result["events"]=events;status["result"]=result;},true);
  fixture("completed","failsafe",[](auto& status,auto& result,auto&,auto&){auto events=result["events"].toArray();auto action=events[1].toObject();action["elapsed_s"]=0.25;auto stopped=events[0].toObject();stopped["elapsed_s"]=0.5;result["events"]=QJsonArray{action,stopped,events[2]};status["result"]=result;},true);
  {bool refused=false;try{sealSitl(temp.path()+"/status.json",temp.path()+"/missing_request",temp.path()+"/environment.json",root);}catch(const std::exception&){refused=true;}require(refused,"SITL result accepted without pre-execution request");++negative;}
  // Independent miniature checkout: only a temporary source is edited. An
  // archived snapshot must remain verifiable when that checkout evolves.
  {
    auto source=temp.path()+"/original_source.cpp";writeBytes(source,"original source\n");auto sourceRelative=QDir(root).relativeFilePath(source);auto archive=temp.path()+"/archived_snapshot";
    QJsonArray live{QJsonObject{{"input_id","temporary_source"},{"kind","other"},{"reference",QJsonObject{{"path",sourceRelative}}},{"checksums",QJsonObject{{"sha256",sha(source)}}}}};
    QJsonObject request{{"inputs",snapshotSitlInputs(archive,root,live)}};validateSitlSnapshots(archive,root,request,true);
    writeBytes(source,"later checkout source\n");validateSitlSnapshots(archive,root,request,false);++positive;
    bool refused=false;try{validateSitlSnapshots(archive,root,request,true);}catch(const std::exception&){refused=true;}require(refused,"changed live source accepted before sealing");++negative;
    require(QFile::remove(source),"remove temporary original source");validateSitlSnapshots(archive,root,request,false);++positive;
  }
  std::cout<<"SITL T0: "<<positive<<" terminal fixtures accepted and "<<negative<<" adversarial fixtures rejected; no flight commands emitted\n";
}
void selfTest(const QString &root) {
  Schemas s(root+"/configs/visualization/schemas");int negative=0;
  QJsonObject req{{"schema","drone_agricole.run_request.v1"},{"request_id","request"},{"simulation_id","sim"},{"variant_id","proxy"},{"requested_at_utc",stamp()},{"inputs",QJsonArray{}},{"parameters",QJsonObject{}}};
  s.validate(req,schemafiles[0]);
  auto rejects=[&](QJsonObject o,QString schema){bool failed=false;try{s.validate(o,schema);}catch(const std::exception&){failed=true;}require(failed,"negative accepted: "+schema);++negative;};
  for(auto key:req.keys()){auto o=req;o.remove(key);rejects(o,schemafiles[0]);}
  auto o=req;o["unexpected"]=1;rejects(o,schemafiles[0]);o=req;o["inputs"]=42;rejects(o,schemafiles[0]);o=req;o["requested_at_utc"]="tomorrow";rejects(o,schemafiles[0]);o=req;o["request_id"]="Bad ID";rejects(o,schemafiles[0]);
  // Whole-run adversarial fixtures use the actual sealer, then corrupt one invariant.
  require(QDir().mkpath(root+"/.runtime"),"runtime directory unavailable");
  QTemporaryDir temp(QDir(root).filePath(".runtime/t0-test-XXXXXX"));require(temp.isValid(),"tempdir");auto raw=temp.path()+"/raw.json";
  {QFile f(temp.path()+"/samples.csv");require(f.open(QIODevice::WriteOnly)&&f.write("fixture\n")==8,"CSV fixture");}
  auto run=temp.path()+"/fixture";prepare(run,root);
  write(raw,QJsonObject{{"kind","cartographe_energy_campaign"},{"execution","offline_deterministic_cpp17"},{"simulation_finalized",true},{"px4_connected",false},{"calibration_sha256",sha(root+"/simulation/energy/calibration_proxy.json")},{"evaluation_sha256",sha(root+"/simulation/energy/evaluation_campaign.json")},{"csv_sha256",sha(temp.path()+"/samples.csv")},{"executable_path",QCoreApplication::applicationFilePath()},{"executable_sha256",sha(QCoreApplication::applicationFilePath())},{"started_at_utc",stamp()},{"finished_at_utc",stamp()},{"run_count",1},{"runs",QJsonArray{QJsonObject{{"simulation_finalized",true},{"end_reason","test_fixture"},{"elapsed_s",0},{"landing_observed",false}}}}});
  seal(raw,run,root);validateRun(run,root);
  const auto rawFixture=object(raw);
  auto rejectRaw=[&](QString key,QJsonValue value){auto bad=rawFixture;bad[key]=value;write(raw,bad);auto badRun=temp.path()+"/bad_"+QString::number(negative);prepare(badRun,root);bool refused=false;try{seal(raw,badRun,root);}catch(const std::exception&){refused=true;}require(refused,"bad raw sealed: "+key);++negative;write(raw,rawFixture);};
  rejectRaw("calibration_sha256","stale");rejectRaw("evaluation_sha256","stale");rejectRaw("csv_sha256","stale");rejectRaw("simulation_finalized",false);rejectRaw("run_count",0);rejectRaw("runs",QJsonArray{});rejectRaw("runs",QJsonArray{QJsonObject{{"simulation_finalized",false}}});rejectRaw("started_at_utc","invalid");
  rejectRaw("executable_sha256","stale");
  rejectRaw("started_at_utc","2000-01-01T00:00:00Z");
  auto mutate=[&](QString file,QString key,QJsonValue value){auto original=read(run+"/"+file);auto doc=object(run+"/"+file);doc[key]=value;write(run+"/"+file,doc);bool failed=false;try{validateRun(run,root);}catch(const std::exception&){failed=true;}QFile f(run+"/"+file);require(f.open(QIODevice::WriteOnly)&&f.write(original)==original.size(),"restore fixture");f.close();require(failed,"corrupt run accepted: "+key);++negative;};
  mutate("t0_run_manifest.json","run_id","different");mutate("t0_run_manifest.json","finished_at_utc",QJsonValue::Null);mutate("t0_run_manifest.json","state","running");mutate("t0_run_manifest.json","unexpected",true);mutate("t0_metrics.json","summary",false);mutate("t0_metrics.json","simulation_id","different");mutate("artifacts.json","items",42);mutate("run_request.json","parameters",QJsonObject{{"changed",true}});
  QJsonObject event{{"schema","drone_agricole.event.v1"},{"run_id","fixture"},{"sequence",0},{"elapsed_s",0},{"event_type","done"},{"severity","info"},{"message","fixture"},{"data",QJsonObject{}}};s.validate(event,"event.schema.json");o=event;o["severity"]="oops";rejects(o,"event.schema.json");o=event;o.remove("data");rejects(o,"event.schema.json");o=event;o["sequence"]=-1;rejects(o,"event.schema.json");o=event;o["unexpected"]=true;rejects(o,"event.schema.json");
  {QFile f(run+"/events.jsonl");require(f.open(QIODevice::Append)&&f.write("{}\n")==3,"event fixture mutation");}bool failed=false;try{validateRun(run,root);}catch(const std::exception&){failed=true;}require(failed,"event corruption accepted");++negative;
  std::cout<<"T0: valid fixtures accepted, "<<negative<<" negative cases rejected; hashes, IDs, terminal state and dates checked\n";
}
}
int main(int argc,char **argv){
  QCoreApplication app(argc,argv);auto args=app.arguments();QString root=QDir(QStringLiteral(WORKSPACE_ROOT)).absolutePath();
  try{
    require(args.size()>=2,"usage: cartographe-evidence self-test | self-test-sitl | validate RUN [WORKSPACE] | prepare RUN | execute RAW_DIRECTORY RUN | seal RAW RUN [WORKSPACE] | prepare-sitl RUN MODEL MODE | seal-sitl STATUS_JSON RUN ENVIRONMENT_JSON");
    if(args[1]=="self-test")selfTest(root);
    else if(args[1]=="self-test-sitl")selfTestSitl(root);
    else if(args[1]=="prepare-sitl"){require(args.size()==5,"prepare-sitl RUN MODEL MODE");prepareSitl(QDir(args[2]).absolutePath(),root,args[3],args[4]);std::cout<<"SITL request prepared; no execution started\n";}
    else if(args[1]=="seal-sitl"){require(args.size()==5,"seal-sitl STATUS_JSON RUN ENVIRONMENT_JSON");sealSitl(args[2],QDir(args[3]).absolutePath(),args[4],root);std::cout<<"SITL terminal result sealed and five T0 contracts validated\n";}
    else if(args[1]=="prepare"){require(args.size()==3,"run missing");prepare(QDir(args[2]).absolutePath(),root);}
    else if(args[1]=="execute"){require(args.size()==4,"raw/run missing");execute(QDir(args[2]).absolutePath(),QDir(args[3]).absolutePath(),root);std::cout<<"T0 validated before execution and after finalization\n";}
    else if(args[1]=="validate"){require(args.size()>=3,"run missing");validateRun(QDir(args[2]).absolutePath(),args.size()>3?QDir(args[3]).absolutePath():root);std::cout<<"T0 valid\n";}
    else if(args[1]=="seal"){require(args.size()>=4,"raw/run missing");seal(args[2],QDir(args[3]).absolutePath(),args.size()>4?QDir(args[4]).absolutePath():root);std::cout<<"T0 finalized and validated\n";}
    else throw std::runtime_error("unknown command");return 0;
  }catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}
}
