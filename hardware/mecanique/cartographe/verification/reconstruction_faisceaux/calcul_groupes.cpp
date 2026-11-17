// Calcul exploratoire C++17 : sections, pertes et protections droites.
// Ne prouve ni ampacite, ni temperature, ni compatibilite CEM.
#include <QCoreApplication>
#include <QFile>
#include <QJsonDocument>
#include <QJsonObject>
#include <QJsonArray>
#include <QCryptographicHash>
#include <QSaveFile>
#include <cmath>
#include <stdexcept>
QByteArray read(const QString&p){QFile f(p);if(!f.open(QIODevice::ReadOnly))throw std::runtime_error("read");return f.readAll();}
int main(int argc,char**argv){QCoreApplication app(argc,argv);try{
 if(argc!=4)throw std::runtime_error("usage routes.json recherche_groupes.json resultat.json");
 auto rb=read(argv[1]),db=read(argv[2]);
 auto routes=QJsonDocument::fromJson(rb).object()["routes"].toArray();
 auto design=QJsonDocument::fromJson(db).object();QJsonArray results,losses;
 for(auto gv:design["groups"].toArray()){
  auto g=gv.toObject();double sum=0,squares=0,length=0;QJsonArray members;
  for(auto id:g["members"].toArray()){
   bool found=false;for(auto rv:routes){auto r=rv.toObject();if(r["id"]!=id)continue;found=true;
    double d=r["diametre_mm"].toDouble(),l=r["longueur_courbe_mm"].toDouble();if(d<=0||l<=0)throw std::runtime_error("invalid route");
    sum+=d;squares+=d*d;length+=l;members.append(QJsonObject{{"id",id},{"diameter_cad_mm",d},{"historical_curve_length_mm",l}});
   }if(!found)throw std::runtime_error("missing member");
  }
  QJsonArray protections;
  for(auto pv:g["straight_protection_candidates"].toArray()){
   auto p=pv.toObject();double id=p["inner_envelope_mm"].toDouble(),wall=p["wall_mm"].toDouble();
   double spread=p["center_spacing_mm"].toDouble();auto ds=p["member_diameters_mm"].toArray();
   double bundle=spread+(ds[0].toDouble()+ds[1].toDouble())/2.;
   double fill=(ds[0].toDouble()*ds[0].toDouble()+ds[1].toDouble()*ds[1].toDouble())/(id*id);
   protections.append(QJsonObject{{"id",p["id"]},{"bundle_envelope_mm",bundle},{"inner_envelope_mm",id},{"outer_envelope_mm",id+2*wall},{"radial_nominal_margin_mm",(id-bundle)/2},{"area_fill_fraction",fill},{"surface_gap_mm",spread-(ds[0].toDouble()+ds[1].toDouble())/2},{"nominal_section_pass",bundle<id},{"cad_collision_check","not_executed_by_this_calculator"}});
  }
  results.append(QJsonObject{{"id",g["id"]},{"members",members},{"historical_member_length_sum_mm",length},{"packed_inline_min_mm",sum},{"area_bound_40percent_mm",std::sqrt(squares/.4)},{"protection_sections",protections}});
  if(g["id"].toString().startsWith("PWR-")){
   // AWG geometric area, standard annealed copper scenario; no contact term assigned zero.
   double awg_d=.127*std::pow(92.,(36.-8.)/39.);double area=std::acos(-1.)*awg_d*awg_d/4.;
   for(double temp:{20.,80.})for(double current:{20.,50.,100.}){
    double rho=(1./58.)*(1.+.00393*(temp-20.));double r=rho*length/1000./area;
    losses.append(QJsonObject{{"group",g["id"]},{"current_hypothesis_A",current},{"conductor_temperature_hypothesis_C",temp},{"section_calculated_AWG8_mm2",area},{"conductor_loop_resistance_ohm",r},{"conductor_voltage_drop_V",current*r},{"conductor_joule_W",current*current*r},{"contact_resistance_ohm",QJsonValue::Null},{"total_loop_resistance_ohm",QJsonValue::Null},{"thermal_pass",QJsonValue::Null}});
   }
  }
 }
 QJsonObject out{{"schema","cartographe.groupes.calcul.v1"},{"language","C++17"},{"qt",qVersion()},{"date","2026-10-29"},{"input_hash_routes",QString(QCryptographicHash::hash(rb,QCryptographicHash::Sha256).toHex())},{"input_hash_research",QString(QCryptographicHash::hash(db,QCryptographicHash::Sha256).toHex())},{"groups",results},{"power_scenarios",losses},{"status","CANDIDAT_CONDITIONNEL"},{"limits","Calculs sur diametres et longueurs historiques, sans nouvelles mesures FreeCAD; cuivre recuit ideal et AWG8 nominal, profil courant/contacts/temperature reelle inconnus. Aucun courant admissible deduit."}};
 QSaveFile f(argv[3]);if(!f.open(QIODevice::WriteOnly))throw std::runtime_error("write");f.write(QJsonDocument(out).toJson());if(!f.commit())throw std::runtime_error("commit");return 0;
}catch(const std::exception&){return 1;}}
