// C++17 : scénarios géométriques exploratoires, pas modèle mécanique du cordon.
#include <QCoreApplication>
#include <QFile>
#include <QJsonDocument>
#include <QJsonArray>
#include <QJsonObject>
#include <cmath>
#include <vector>
#include <algorithm>
#include <stdexcept>
#include <iostream>
struct V { double x,y,z; V operator+(V b)const{return{x+b.x,y+b.y,z+b.z};} V operator-(V b)const{return{x-b.x,y-b.y,z-b.z};} V operator*(double s)const{return{x*s,y*s,z*s};} };
double norm(V p){return std::sqrt(p.x*p.x+p.y*p.y+p.z*p.z);}
double dot(V a,V b){return a.x*b.x+a.y*b.y+a.z*b.z;}
QJsonArray j(V p){return{p.x,p.y,p.z};}
V rot(V v,V deg){double a=deg.x*M_PI/180,b=deg.y*M_PI/180,c=deg.z*M_PI/180; V w{v.x,v.y*cos(a)-v.z*sin(a),v.y*sin(a)+v.z*cos(a)}; V q{w.x*cos(b)+w.z*sin(b),w.y,-w.x*sin(b)+w.z*cos(b)}; return{q.x*cos(c)-q.y*sin(c),q.x*sin(c)+q.y*cos(c),q.z};}
struct M {double length=0,margin=1e9;bool feasible=true;};
M measure(const std::vector<V>&p,double r){M m;std::vector<double> cuts(p.size());for(size_t i=1;i<p.size();++i)m.length+=norm(p[i]-p[i-1]); for(size_t i=1;i+1<p.size();++i){V a=p[i]-p[i-1],b=p[i+1]-p[i];double theta=acos(std::clamp(dot(a,b)/(norm(a)*norm(b)),-1.,1.));cuts[i]=r*tan(theta/2);m.length+=r*theta-2*cuts[i];}for(size_t i=1;i<p.size();++i)m.margin=std::min(m.margin,norm(p[i]-p[i-1])-cuts[i-1]-cuts[i]);m.feasible=m.margin>0.001;return m;}
std::vector<V> lower(double x,double z,V shift={},V angle={}){V pivot{10,0,-128.5},start{109.785,-0.525,-96.82};start=pivot+rot(start-pivot,angle)+shift;V axis=rot({1,0,0},angle);return{start,start+axis*((x-start.x)/axis.x),{x,-54,z},{96,-54,z},{96,-54,75}};}
QJsonObject candidate(QString id,double x,double z,double r,V shift={},V angle={},double target=-1){
 if(target>0){double lo=175,hi=280;if(!(measure(lower(lo,z,shift,angle),r).length<=target&&target<=measure(lower(hi,z,shift,angle),r).length))throw std::runtime_error("Longueur cible non encadree");for(int k=0;k<70;++k){double mid=(lo+hi)/2;if(measure(lower(mid,z,shift,angle),r).length<target)lo=mid;else hi=mid;}x=(lo+hi)/2;}
 auto pts=lower(x,z,shift,angle);auto m=measure(pts,r);if(!std::isfinite(m.length)||(target>0&&std::abs(m.length-target)>1e-6))throw std::runtime_error("Longueur non finie ou cible non atteinte");QJsonArray arr;for(auto p:pts)arr.append(j(p));
 std::vector<V> top{{96,-54,75},{96,-54,90},{96,-105,140.5},{7,-105,140.5},{7,-79.95,140.5}};QJsonArray upper;for(auto p:top)upper.append(j(p));auto t=measure(top,24);
 return{{"id",id},{"lower_points_mm",arr},{"upper_points_mm",upper},{"radius_mobile_mm",r},{"radius_fixed_mm",24},{"x_loop_mm",x},{"z_return_mm",z},{"translation_mm",j(shift)},{"rotation_xyz_deg",j(angle)},{"rotation_center_mm",j({10,0,-128.5})},{"start_axis",j(rot({1,0,0},angle))},{"analytic_length_mm",m.length+t.length},{"mobile_length_mm",m.length},{"constant_length_error_mm",target<0?0:m.length-target},{"fillet_margin_mm",std::min(m.margin,t.margin)},{"polyline_feasible",m.feasible&&t.feasible},{"data_class","HYPOTHÈSE"}};
}
int main(int argc,char**argv){QCoreApplication app(argc,argv);try{if(argc!=3&&argc!=4)throw std::runtime_error("explorer_f16 nominal|poses sortie.json [selected.json]");QJsonArray rows;
 if(QString(argv[1])=="nominal"){for(double r:{50.,52.})for(double x:{200.,220.,240.})for(double z:{-10.,0.,10.,20.})rows.append(candidate(QString("F16_R%1_X%2_Z%3").arg(r).arg(x).arg(z),x,z,r));}
 else{if(QString(argv[1])!="poses"||argc!=4)throw std::runtime_error("poses exige selected.json");QFile f(argv[3]);if(!f.open(QIODevice::ReadOnly))throw std::runtime_error("selected missing");QJsonParseError error;auto doc=QJsonDocument::fromJson(f.readAll(),&error);if(error.error!=QJsonParseError::NoError||!doc.isObject())throw std::runtime_error("JSON selection invalide");auto s=doc.object();for(auto key:{"x_loop_mm","z_return_mm","radius_mobile_mm","mobile_length_mm"})if(!s[key].isDouble()||!std::isfinite(s[key].toDouble()))throw std::runtime_error("Champ selection absent/non fini");double x=s["x_loop_mm"].toDouble(),z=s["z_return_mm"].toDouble(),r=s["radius_mobile_mm"].toDouble(),len=s["mobile_length_mm"].toDouble();if(r<48||len<=0)throw std::runtime_error("Selection hors domaine");rows.append(candidate("POSE_NOMINAL",x,z,r,{}, {},len));int n=0;for(int axis=0;axis<6;++axis)for(double sign:{-1.,1.}){V d{},a{};V& v=axis<3?d:a;if(axis%3==0)v.x=sign;else if(axis%3==1)v.y=sign;else v.z=sign;rows.append(candidate(QString("POSE_AXE_%1").arg(++n),x,z,r,d,a,len));}for(double sx:{-1.,1.})for(double sy:{-1.,1.})for(double sz:{-1.,1.})rows.append(candidate(QString("POSE_COMB_%1").arg(++n),x,z,r,{sx*.5,sy*.5,sz*.5},{sx*.5,sy*.5,sz*.5},len));rows.append(candidate("REJET_Z_PLUS_2",x,z,r,{0,0,2},{},len));rows.append(candidate("REJET_X_PLUS_1_5",x,z,r,{1.5,0,0},{},len));rows.append(candidate("REJET_Z_MOINS_5",x,z,r,{0,0,-5},{},len));rows.append(candidate("POSE_PLAFOND",x,z,r,{0,0,1},{0,-.5,0},len));rows.append(candidate("POSE_PLAFOND_COMB",x,z,r,{0,0,.5},{.5,-.5,.5},len));rows.append(candidate("POSE_SOUS_CHARGE",x,z,r,{0,0,-.724},{},len));}
 QJsonObject out{{"schema","f16-parametric-v1"},{"model","Polyligne raccordée par arcs circulaires, longueur sum(L)-sum(2Rtan(theta/2)-Rtheta). Poses discrètes; ni élasticité ni fatigue ni couverture continue."},{"hypotheses","Scénarios exploratoires; enveloppe réelle inconnue. Rotation RzRyRx autour centre géométrique. Huit combinaisons à signes couplés seulement, pas les64coins de6DDL."},{"candidates",rows}};
 if(QString(argv[1])=="poses"){
  double length=rows[0].toObject()["analytic_length_mm"].toDouble();double d=.127*pow(92.,(36.-24.)/39.);double section=M_PI*d*d/4;QJsonArray electrical;
  for(double temperature:{20.,80.})for(double current:{.5,.9}){double rho=(1./58.)*(1+.00393*(temperature-20));double resistance=rho*2*length/1000/section;double deltaR=rho*2*(length-425.17384217864503)/1000/section;electrical.append(QJsonObject{{"temperature_C_hypothesis",temperature},{"current_A_hypothesis",current},{"conductor_loop_ohm",resistance},{"voltage_drop_V",current*resistance},{"joule_W",current*current*resistance},{"additional_drop_vs_baseline_V",current*deltaR}});}
  out["electrical_scenarios"]=QJsonObject{{"data_class","CALCULÉE"},{"input_class","HYPOTHÈSE pour courant/température/cuivre analogue; AWG24 documentaire fabricant USB"},{"section_AWG24_mm2",section},{"formula","R=rho(T)*2L/S; U=IR; P=I²R. Aller+retour chacun une fois."},{"sources","recherche_suspension.json#USB et recherche_groupes.json#NBS-COPPER"},{"contact_resistance_ohm",QJsonValue::Null},{"actual_current_A",QJsonValue::Null},{"admissible_voltage_drop_V",QJsonValue::Null},{"signal_integrity","NON_VERIFIE; cordon custom à confirmer par fabricant et essai USB3"},{"values",electrical}};
 }
 QFile f(argv[2]);if(!f.open(QIODevice::WriteOnly))throw std::runtime_error("write");if(f.write(QJsonDocument(out).toJson())<0)throw std::runtime_error("write failed");return 0;}catch(const std::exception&e){std::cerr<<e.what()<<std::endl;return 2;}}
