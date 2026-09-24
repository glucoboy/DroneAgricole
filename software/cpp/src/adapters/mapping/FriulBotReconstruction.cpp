#include "drone_agricole/adapters/FriulBotSensors.hpp"
#include "drone_agricole/algorithms/ScanReconstruction.hpp"
#include "drone_agricole/core/JsonUtils.hpp"
#include "drone_agricole/core/ResultAdapter.hpp"
#include "drone_agricole/core/Ros1Bag.hpp"
#include "drone_agricole/core/Ros1Messages.hpp"
#include <QCryptographicHash>
#include <QDateTime>
#include <QDir>
#include <QFileInfo>
#include <QJsonArray>
#include <QJsonDocument>
#include <QSaveFile>
#include <QTextStream>
#include <algorithm>
#include <cmath>

namespace drone_agricole::core {
namespace {
QString s(const char* value) { return QString::fromUtf8(value); }
QString required(const QJsonObject& o,const char* key) {
  const auto value=o.value(s(key)).toString();
  if(value.isEmpty())throw ContractError(s("Option manquante : ")+s(key));
  return value;
}
double number(const QJsonObject& p,const char* key,double fallback,double low,double high) {
  const auto v=p.value(s(key));
  const double value=v.isUndefined()?fallback:v.toDouble(std::numeric_limits<double>::quiet_NaN());
  if(!std::isfinite(value)||value<low||value>high)throw ContractError(s("Paramètre de reconstruction invalide : ")+s(key));
  return value;
}
QJsonArray xyz(const QVector3D& p) { return {p.x(),p.y(),p.z()}; }
QJsonArray pointsJson(const QList<QVector3D>& points) {
  QJsonArray output;for(const auto& p:points)output.append(xyz(p));return output;
}
struct Frame { qint64 time; QByteArray bytes; int image{-1}; };
struct Scan { QList<QVector3D> points; QList<int> rings; QString frame; };
Scan decode(const Frame& frame,double range) {
  const auto cloud=deserializeRos1PointCloud2(frame.bytes);
  if(std::none_of(cloud.fields.begin(),cloud.fields.end(),[](const auto& field){return field.name==s("ring");}))
    throw ContractError(s("Le maillage exige le champ ring du LiDAR"));
  Scan scan;scan.frame=cloud.header.frameId;
  const auto count=static_cast<qsizetype>(cloud.width)*cloud.height;
  if(count>200000)throw ContractError(s("Scan trop volumineux pour cette reconstruction bornée"));
  for(qsizetype i=0;i<count;++i) {
    const auto x=ros1PointFieldAsDouble(cloud,i,s("x")),y=ros1PointFieldAsDouble(cloud,i,s("y")),z=ros1PointFieldAsDouble(cloud,i,s("z"));
    const auto ring=ros1PointFieldAsDouble(cloud,i,s("ring"));
    const auto distance=std::sqrt(x*x+y*y+z*z);
    if(!std::isfinite(distance)||distance<0.8||distance>range||!std::isfinite(ring)||ring<0||ring>127)continue;
    scan.points.append({static_cast<float>(x),static_cast<float>(y),static_cast<float>(z)});
    scan.rings.append(static_cast<int>(ring));
  }
  return scan;
}
QJsonObject metric(const char* id,const QString& label,double value,const char* unit) {
  return {{s("metric_id"),s(id)},{s("label"),label},{s("value"),value},{s("unit"),s(unit)},
          {s("direction"),s("neutral")},{s("status"),s("warning")},{s("metadata"),QJsonObject{{s("preliminary"),true}}}};
}
QJsonObject artifact(const char* id,const char* path,const char* kind,const QString& label,bool replayable=false) {
  return {{s("artifact_id"),s(id)},{s("path"),s(path)},{s("kind"),s(kind)},{s("label"),label},
          {s("media_type"),s("application/octet-stream")},{s("role"),s("result")},{s("replayable"),replayable}};
}
void writeMesh(const QString& path,const algorithms::SurfaceMap& map) {
  QSaveFile file(path);if(!file.open(QIODevice::WriteOnly))throw ContractError(s("Export PLY impossible"));
  QTextStream out(&file);out.setLocale(QLocale::c());out.setRealNumberPrecision(9);
  const auto& mesh=map.mesh();
  out << "ply\nformat ascii 1.0\ncomment observed_lidar_surface_not_watertight\nelement vertex " << mesh.vertices.size()
      << "\nproperty float x\nproperty float y\nproperty float z\nproperty uchar red\nproperty uchar green\nproperty uchar blue\n"
      << "element face " << mesh.triangles.size() << "\nproperty list uchar int vertex_indices\nend_header\n";
  for(qsizetype i=0;i<mesh.vertices.size();++i) {const auto p=mesh.vertices[i];const auto c=map.colors()[i];
    out<<p.x()<<' '<<p.y()<<' '<<p.z()<<' '<<c.red()<<' '<<c.green()<<' '<<c.blue()<<'\n';}
  for(const auto& face:mesh.triangles)out<<"3 "<<face[0]<<' '<<face[1]<<' '<<face[2]<<'\n';
  out.flush();if(out.status()!=QTextStream::Ok||!file.commit())throw ContractError(s("Écriture PLY incomplète"));
}
}

QJsonObject runFriulBotReconstruction(const QJsonObject& options) {
  const auto request=readJsonObject(required(options,"request"));
  requireSchema(request,s("drone_agricole.run_request.v1"),s("Requête de reconstruction"));
  if(request.value(s("simulation_id"))!=s("vineyard_capture_mapping")||request.value(s("variant_id"))!=s("scan_surface_v1"))
    throw ContractError(s("Variante de reconstruction incorrecte"));
  const auto directory=required(options,"run-dir"),runId=safeIdentifier(required(options,"run-id"),s("reconstruction"));
  if(QFileInfo::exists(directory))throw ContractError(s("Le dossier de reconstruction existe déjà"));
  const auto p=request.value(s("parameters")).toObject();
  const double offset=number(p,"capture_offset_s",120,0,1250),duration=number(p,"assembly_duration_s",10,1,60);
  const double interval=number(p,"scan_interval_s",0.5,0.1,1),range=number(p,"maximum_range_m",20,5,100);
  const double voxel=number(p,"surface_voxel_m",0.15,0.05,0.5),edge=number(p,"surface_max_edge_m",0.8,0.2,2);
  if(duration/interval>350)throw ContractError(s("Réduisez la durée ou augmentez l'intervalle : 350 scans maximum"));
  const auto started=QDateTime::currentDateTimeUtc().toString(Qt::ISODateWithMs);
  QTextStream(stdout)<<"MAP_PROGRESS stage=scans percent=3"<<Qt::endl;
  Ros1Bag bag(required(options,"bag"));bag.open();
  const auto start=bag.startNanoseconds()+static_cast<qint64>(offset*1e9),stop=start+static_cast<qint64>(duration*1e9);
  if(start>=bag.endNanoseconds()||stop>bag.endNanoseconds())throw ContractError(s("La fenêtre dépasse la durée du bag"));
  const auto imageSets=friulBotImageSets(required(options,"images"));
  quint64 triggers=0;for(const auto& c:bag.connections())if(c.topic==s("micasense_capture_lidar_points"))triggers+=c.messageCount;
  const bool paired=triggers==static_cast<quint64>(imageSets.size());
  QList<Frame> frames;int captureIndex=0;qint64 lastRaw=0,totalBytes=0;
  bag.forEachMessage({s("velodyne_points"),s("micasense_capture_lidar_points")},bag.startNanoseconds(),stop,
    [&](const Ros1Connection& c,const Ros1Message& message) {
      const bool camera=c.topic==s("micasense_capture_lidar_points");
      const int image=camera?captureIndex++:-1;
      if(message.timestampNanoseconds<start)return;
      if(!camera&&lastRaw!=0&&message.timestampNanoseconds-lastRaw<static_cast<qint64>(interval*1e9))return;
      if(!camera)lastRaw=message.timestampNanoseconds;
      totalBytes+=message.data.size();
      if(totalBytes>256LL*1024*1024||frames.size()>=400)throw ContractError(s("Fenêtre de reconstruction trop volumineuse"));
      frames.append({message.timestampNanoseconds,message.data,paired?image:-1});
    });
  std::sort(frames.begin(),frames.end(),[](const auto& a,const auto& b){return a.time<b.time;});
  QList<Frame> selected;
  for(const auto& frame:frames) {
    if(!selected.isEmpty()&&frame.time-selected.last().time<50000000LL){
      if(frame.image>=0)selected.last()=frame;
    }else selected.append(frame);
  }
  frames.clear();
  if(selected.size()<2)throw ContractError(s("Au moins deux scans sont nécessaires"));
  algorithms::SurfaceMap map(static_cast<float>(voxel));
  algorithms::RigidPose worldPose,lastDelta;
  QList<QVector3D> previous,path;
  QJsonArray poses,diagnostics,warnings;
  QString frameId,stopReason;
  int accepted=0,coloredCaptures=0;double worstRmse=0,minOverlap=1;
  for(qsizetype i=0;i<selected.size();++i) {
    const auto scan=decode(selected[i],range);
    if(i==0)frameId=scan.frame;
    if(scan.frame!=frameId)throw ContractError(s("Changement de repère LiDAR dans la fenêtre"));
    if(i>0) {
      if(selected[i].time-selected[i-1].time>1500000000LL){stopReason=s("Interruption temporelle des scans");break;}
      const auto registration=algorithms::registerScan(previous,scan.points,lastDelta);
      diagnostics.append(QJsonObject{{s("timestamp_ns"),QString::number(selected[i].time)},
        {s("accepted"),registration.accepted},{s("rmse_m"),registration.rmse},{s("overlap"),registration.overlap},
        {s("converged"),registration.converged},{s("iterations"),registration.iterations}});
      if(!registration.accepted){stopReason=s("Recalage ICP insuffisant : arrêt avant ce scan");break;}
      lastDelta=registration.previousFromCurrent;worldPose=algorithms::compose(worldPose,lastDelta);
      worstRmse=std::max(worstRmse,registration.rmse);minOverlap=std::min(minOverlap,registration.overlap);
    }
    const auto mesh=algorithms::triangulateScan(scan.points,scan.rings,static_cast<float>(edge));
    if(!map.integrate(mesh,worldPose)){stopReason=s("Budget de sommets ou de faces atteint");break;}
    if(selected[i].image>=0&&selected[i].image<imageSets.size()) {
      try {
        const auto colors=colorFriulBotScan(scan.points,imageSets[selected[i].image],required(options,"calibration"));
        map.colorize(colors.points,colors.colors,worldPose);
        if(!colors.points.isEmpty())++coloredCaptures;
      }catch(const std::exception& e){warnings.append(s("Couleurs caméra indisponibles : ")+QString::fromUtf8(e.what()));}
    }
    ++accepted;previous=scan.points;path.append(worldPose.translation);
    poses.append(QJsonObject{{s("timestamp_ns"),QString::number(selected[i].time)},
      {s("elapsed_s"),(selected[i].time-start)*1e-9},{s("translation_m"),xyz(worldPose.translation)},
      {s("quaternion_xyzw"),QJsonArray{worldPose.rotation.x(),worldPose.rotation.y(),worldPose.rotation.z(),worldPose.rotation.scalar()}}});
    QTextStream(stdout)<<"MAP_PROGRESS stage=assembly percent="<<(8+78*accepted/selected.size())<<Qt::endl;
  }
  if(accepted<2||map.mesh().triangles.isEmpty())throw ContractError(s("Aucune surface assemblée exploitable : ")+stopReason);
  const bool complete=accepted==selected.size();
  if(!complete)warnings.append(s("RECONSTRUCTION PARTIELLE : ")+stopReason);
  if(!paired)warnings.append(s("Captures et images en nombre différent : projection couleur refusée"));
  warnings.append(s("Odométrie LiDAR ICP sans IMU, deskew ni fermeture de boucle ; dérive et calibration À valider."));
  warnings.append(s("Surface des mesures observées, non fermée : les trous restent inconnus, pas des passages libres."));
  warnings.append(s("Trajectoire d'acquisition estimée, jamais un ordre de vol ni une trajectoire de traitement validée."));
  const auto& mesh=map.mesh();QJsonArray faces,colors,coloredPoints,coloredRgb;
  for(const auto& face:mesh.triangles)faces.append(QJsonArray{face[0],face[1],face[2]});
  for(qsizetype i=0;i<mesh.vertices.size();++i) {
    const auto c=map.colors()[i];const QJsonArray rgb{c.red(),c.green(),c.blue()};colors.append(rgb);
    if(map.colorCounts()[i]>0){coloredPoints.append(xyz(mesh.vertices[i]));coloredRgb.append(rgb);}
  }
  const QJsonObject metadata{{s("coordinate_frame"),s("first_lidar_scan")},{s("source_frame"),frameId},
    {s("reconstruction_status"),complete?s("complete_window"):s("partial")},{s("stop_reason"),stopReason},
    {s("selected_scans"),selected.size()},{s("accepted_scans"),accepted},{s("colored_captures"),coloredCaptures},
    {s("requested_duration_s"),duration},{s("assembled_duration_s"),(selected[accepted-1].time-selected[0].time)*1e-9},
    {s("worst_registration_rmse_m"),worstRmse},{s("minimum_overlap"),minOverlap},
    {s("pose_convention"),s("p_map = R_map_lidar * p_lidar + t_map_lidar; origin first accepted scan")},
    {s("timestamp_source"),s("rosbag_record_time")},{s("prediction_inputs"),QJsonArray{s("velodyne_points"),s("micasense_capture_lidar_points"),s("raw_multispectral_tiff")}},
    {s("excluded_topics"),QJsonArray{s("ublox_position_receiver/fix"),s("odom"),s("map_base_link/odometry"),s("lio_sam/mapping/odometry")}},
    {s("surface_method"),s("observed_ring_angular_triangles_voxel_weld")},{s("watertight"),false},{s("flight_authorized"),false}};
  QJsonObject prediction{{s("schema"),s("drone_agricole.map_prediction.v1")},{s("run_id"),runId},{s("domain"),s("mapping")},
    {s("local_origin"),QJsonArray{0,0,0}},{s("point_cloud"),pointsJson(mesh.vertices)},
    {s("camera_projected_points"),coloredPoints},{s("camera_point_colors"),coloredRgb},
    {s("surface"),QJsonObject{{s("vertices"),pointsJson(mesh.vertices)},{s("triangles"),faces},{s("colors"),colors}}},
    {s("polylines"),QJsonArray{QJsonObject{{s("label"),s("Trajectoire d'acquisition estimée")},{s("role"),s("acquisition_trajectory")},{s("points"),pointsJson(path)}}}},
    {s("metadata"),metadata}};
  auto canonical=prediction;canonical.remove(s("run_id"));
  const auto hash=QString::fromLatin1(QCryptographicHash::hash(QJsonDocument(canonical).toJson(QJsonDocument::Compact),QCryptographicHash::Sha256).toHex());
  if(!QDir().mkpath(directory))throw ContractError(s("Création du dossier impossible"));
  writeJsonObjectAtomically(QDir(directory).filePath(s("map_prediction.json")),prediction);
  auto replay=prediction;replay.insert(s("schema"),s("drone_agricole.map_replay.v1"));replay.insert(s("warnings"),warnings);
  writeJsonObjectAtomically(QDir(directory).filePath(s("map_replay.json")),replay);
  writeJsonObjectAtomically(QDir(directory).filePath(s("estimated_poses.json")),QJsonObject{{s("schema"),s("drone_agricole.estimated_scan_poses.v1")},{s("metadata"),metadata},{s("poses"),poses},{s("registrations"),diagnostics}});
  writeMesh(QDir(directory).filePath(s("surface.ply")),map);
  const QJsonArray summary{metric("assembled_scans",s("Scans assemblés"),accepted,"scan"),
    metric("surface_vertices",s("Sommets de surface"),mesh.vertices.size(),"point"),metric("surface_faces",s("Triangles observés"),mesh.triangles.size(),"triangle"),
    metric("colored_vertices",s("Sommets colorés par caméra"),coloredPoints.size(),"point"),
    metric("registration_rmse",s("Résidu ICP maximal (pas une erreur absolue)"),worstRmse,"m"),
    metric("assembled_duration",s("Durée assemblée"),(selected[accepted-1].time-selected[0].time)*1e-9,"s")};
  const auto finished=QDateTime::currentDateTimeUtc().toString(Qt::ISODateWithMs);
  QJsonObject manifest{{s("schema"),s("drone_agricole.run_manifest.v1")},{s("run_id"),runId},
    {s("simulation_id"),s("vineyard_capture_mapping")},{s("variant_id"),s("scan_surface_v1")},{s("runner_id"),s("friulbot_capture_rows")},
    {s("domain"),s("mapping")},{s("state"),s("completed")},{s("created_at_utc"),started},{s("started_at_utc"),started},{s("finished_at_utc"),finished},
    {s("inputs"),request.value(s("inputs"))},{s("parameters"),p},{s("software"),QJsonObject{{s("implementation"),s("cpp17_scan_surface_v1")}}},
    {s("files"),QJsonObject{{s("map_replay"),s("map_replay.json")},{s("surface"),s("surface.ply")},{s("poses"),s("estimated_poses.json")}}},
    {s("compatibility"),QJsonObject{{s("comparison_group"),s("vineyard_scan_surface_v1")},{s("result_contract_version"),1}}},
    {s("metadata"),QJsonObject{{s("mapping_safe"),false},{s("reconstruction_status"),metadata.value(s("reconstruction_status"))},
      {s("prediction_content_sha256"),hash},{s("warnings"),warnings},{s("tags"),QJsonArray{s("friulbot"),s("surface"),s("preliminary")}}}}};
  QJsonObject metrics{{s("schema"),s("drone_agricole.metrics.v1")},{s("run_id"),runId},{s("simulation_id"),s("vineyard_capture_mapping")},
    {s("status"),s("partial")},{s("summary"),summary},{s("groups"),QJsonObject{{s("reconstruction"),metadata}}}};
  QJsonObject artifacts{{s("schema"),s("drone_agricole.artifacts.v1")},{s("run_id"),runId},
    {s("items"),QJsonArray{artifact("map_replay","map_replay.json","map",s("Carte assemblée et surface"),true),
      artifact("surface","surface.ply","model",s("Surface observée PLY")),artifact("poses","estimated_poses.json","trajectory",s("Poses et diagnostics ICP")),
      artifact("map_prediction","map_prediction.json","map",s("Géométrie assemblée figée"))}}};
  writeNativeContracts(NormalizedResult{s("t0_native"),directory,manifest,metrics,artifacts,{}},request);
  QTextStream(stdout)<<"MAP_PROGRESS stage=complete percent=100"<<Qt::endl;
  return {{s("result_directory"),directory},{s("accepted_scans"),accepted},{s("surface_faces"),mesh.triangles.size()},
    {s("reconstruction_status"),metadata.value(s("reconstruction_status"))},{s("stop_reason"),stopReason},{s("mapping_safe"),false}};
}
} // namespace drone_agricole::core
