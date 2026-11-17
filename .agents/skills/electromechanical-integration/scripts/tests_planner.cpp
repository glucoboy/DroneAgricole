#include "harness_planner.hpp"
#include <QCoreApplication>
#include <QJsonArray>
#include <QJsonDocument>
#include <QTextStream>
#include <cmath>
#include <stdexcept>

namespace {
int assertions=0;
void check(bool condition,const char* what){++assertions;if(!condition)throw std::runtime_error(what);}
QJsonObject param(double x){return {{"value",x},{"source","synthetic-test"},{"confidence","supplier"}};}
QJsonObject fixture(){
 QJsonArray connectors,nodes,links,edges;
 for(auto id:{"A","B","C","D","E","F"}){connectors.append(QJsonObject{{"id",id},{"position_mm",QJsonArray{0,0,0}},{"exit_axis",QJsonArray{1,0,0}}});nodes.append(QJsonObject{{"id",id},{"connector_id",id},{"accessible",true}});}
 nodes.append(QJsonObject{{"id","P"},{"accessible",true}});nodes.append(QJsonObject{{"id","Q"},{"accessible",true}});
 auto edge=[&](const char* id,const char* a,const char* b,double length){edges.append(QJsonObject{{"id",id},{"from",a},{"to",b},{"length_mm",length},{"usable_width_mm",30}});};
 edge("AP","A","P",10);edge("BP","B","P",10);edge("CP","C","P",10);edge("PQ","P","Q",100);edge("QD","Q","D",10);edge("QE","Q","E",10);edge("QF","Q","F",10);
 auto link=[&](const char* id,const char* a,const char* b){links.append(QJsonObject{{"id",id},{"from",a},{"to",b},{"category","data"},{"outer_diameter_mm",param(3)},{"min_bend_radius_mm",param(20)}});};
 link("L1","A","D");link("L2","B","E");
 return {{"schema_version",1},{"connectors",connectors},{"nodes",nodes},{"links",links},{"edges",edges},{"compatibility",QJsonArray{QJsonObject{{"categories",QJsonArray{"data","data"}},{"decision","allow"},{"source","synthetic-test"},{"reason","fixture-compatible"}}}},{"settings",QJsonObject{{"fill_ratio",0.4},{"max_paths_per_link",8},{"max_candidates",3},{"max_expansions",1000}}}};
}
QJsonObject pooled(const QJsonObject& r){for(auto v:r.value("candidates").toArray())if(v.toObject().value("id")=="pooled_forward")return v.toObject();throw std::runtime_error("missing pooled");}
QJsonObject only(const QJsonObject& r){return r.value("candidates").toArray()[0].toObject();}
bool has(const QJsonObject& o,const char* field,const QString& prefix){for(auto v:o.value(field).toArray())if(v.toString().startsWith(prefix))return true;return false;}
}
int main(int argc,char** argv){QCoreApplication app(argc,argv);try{
 auto input=fixture();auto r=harness::plan(input);auto p=pooled(r);auto metrics=p.value("metrics").toObject();
 check(metrics.value("shared_segments").toInt()==1,"two compatible share exactly corridor");
 check(std::abs(metrics.value("shared_length_mm").toDouble()-100)<1e-9,"shared length observable");
 check(std::abs(metrics.value("cable_length_mm").toDouble()-240)<1e-9,"logical individual lengths preserved");
 check(p.value("routes").toArray().size()==2,"two links conserved");
 check(r.value("selected_candidate_id").toString()=="pooled_forward","pooling selected");
 check(r.value("execution").toObject().value("geometry")=="not_executed","offline no geometry claim");
 check(QJsonDocument(r).toJson()==QJsonDocument(harness::plan(input)).toJson(),"deterministic report");
 auto three=input;auto links=three.value("links").toArray();auto l3=links[0].toObject();l3["id"]="L3";l3["from"]="C";l3["to"]="F";links.append(l3);three["links"]=links;
 auto triple=pooled(harness::plan(three));check(triple.value("routes").toArray().size()==3,"three connections conserved");check(triple.value("branches").toArray().size()==2,"branch nodes found");
 bool found3=false;for(auto v:triple.value("segments").toArray())if(v.toObject().value("link_ids").toArray().size()==3)found3=true;check(found3,"three cables share corridor");
 auto denied=input;auto rules=denied.value("compatibility").toArray();auto rule=rules[0].toObject();rule["decision"]="deny";rules[0]=rule;denied["compatibility"]=rules;auto dp=pooled(harness::plan(denied));
 check(dp.value("metrics").toObject().value("shared_segments").toInt()==0,"denied cables never grouped");check(has(dp,"unknowns","separation_geometry_required:"),"denied shared corridor requires spatial separation");
 auto missing=input;links=missing.value("links").toArray();auto first=links[0].toObject();first["min_bend_radius_mm"]=QJsonObject{{"value",QJsonValue::Null},{"source",QJsonValue::Null},{"confidence","unknown"}};links[0]=first;missing["links"]=links;auto mp=pooled(harness::plan(missing));
 check(mp.value("decision")=="unresolved","unknown supplier not compliant");check(has(mp,"unknowns","unconfirmed_parameter:L1:min_bend_radius_mm"),"unknown parameter exact scope");
 auto lost=p;auto routes=lost.value("routes").toArray();routes.removeLast();lost["routes"]=routes;auto lr=only(harness::validate(input,lost));check(lr.value("decision")=="rejected","lost connection rejected");check(has(lr,"errors","missing_link:L2"),"lost connection identified");
 auto dup=p;routes=p.value("routes").toArray();routes.append(routes[0]);dup["routes"]=routes;check(has(only(harness::validate(input,dup)),"errors","duplicate_link:"),"duplicate connection rejected");
 auto wrong=p;routes=p.value("routes").toArray();first=routes[0].toObject();first["edge_ids"]=QJsonArray{"AP","QE","PQ"};routes[0]=first;wrong["routes"]=routes;check(has(only(harness::validate(input,wrong)),"errors","discontinuous_path:"),"discontinuous route rejected");
 auto wrongEnd=p;routes=p.value("routes").toArray();first=routes[0].toObject();first["edge_ids"]=QJsonArray{"AP","PQ","QE"};routes[0]=first;wrongEnd["routes"]=routes;check(has(only(harness::validate(input,wrongEnd)),"errors","wrong_endpoint:"),"electrical endpoint not silently changed");
 auto noRule=input;noRule["compatibility"]=QJsonArray{};auto np=pooled(harness::plan(noRule));check(np.value("metrics").toObject().value("shared_segments").toInt()==0,"same category not implicitly compatible");check(has(np,"unknowns","compatibility_unknown:"),"compatibility unknown retained");
 auto thin=input;auto edges=thin.value("edges").toArray();for(int i=0;i<edges.size();++i){auto e=edges[i].toObject();if(e.value("id")=="PQ"){e["usable_width_mm"]=1;edges[i]=e;}}thin["edges"]=edges;auto tr=harness::plan(thin);check(tr.value("selected_candidate_id").isNull(),"capacity failure cannot be compensated by length");
 auto inaccessible=three;auto nodes=inaccessible.value("nodes").toArray();for(int i=0;i<nodes.size();++i){auto n=nodes[i].toObject();if(n.value("id")=="Q"){n["accessible"]=false;nodes[i]=n;}}inaccessible["nodes"]=nodes;check(has(pooled(harness::plan(inaccessible)),"errors","inaccessible_branch:Q"),"inaccessible branch rejected");
 bool estimated=false;for(auto v:p.value("segments").toArray()){auto s=v.toObject();if(s.value("link_ids").toArray().size()==2){check(std::abs(s.value("inner_diameter_estimate_mm").toDouble()-std::sqrt(18/0.4))<1e-10,"sleeve area bound");estimated=true;}}check(estimated,"sleeve dimension present");
 auto bad=input;links=bad.value("links").toArray();links.append(links[0]);bad["links"]=links;bool failed=false;try{harness::plan(bad);}catch(...){failed=true;}check(failed,"duplicate input links rejected");
 auto bounded=input;auto settings=bounded.value("settings").toObject();settings["max_expansions"]=1;bounded["settings"]=settings;failed=false;try{harness::plan(bounded);}catch(...){failed=true;}check(failed,"search budget exhaustion not success");
 auto reordered=input;settings=reordered.value("settings").toObject();settings["objective_order"]=QJsonArray{"cable_length_mm","bundle_segments"};reordered["settings"]=settings;check(harness::plan(reordered).value("objective_order").toArray()[0]=="cable_length_mm","objective configuration retained");
 check(!harness::markdown(r).isEmpty(),"markdown rendered");
 auto single=input;links=single.value("links").toArray();links.removeLast();single["links"]=links;edges=single.value("edges").toArray();for(int i=0;i<edges.size();++i){auto e=edges[i].toObject();e["usable_width_mm"]=4;edges[i]=e;}single["edges"]=edges;
 auto sp=pooled(harness::plan(single));check(sp.value("decision")=="candidate","single 3mm cable fits 4mm corridor without invented sleeve");check(!has(sp,"unknowns","corridor_capacity_unknown:"),"single capacity known");
 for(auto v:sp.value("segments").toArray()){auto s=v.toObject();check(s.value("required_width_mm").toDouble()==3&&s.value("inner_diameter_estimate_mm").isNull()&&s.value("dimensioning_status")=="individual_cable","single physical envelope equals cable OD");}
 for(int i=0;i<edges.size();++i){auto e=edges[i].toObject();e["usable_width_mm"]=2;edges[i]=e;}single["edges"]=edges;check(harness::plan(single).value("selected_candidate_id").isNull(),"single 3mm cable rejected in 2mm corridor");
 auto expectFailure=[&](QJsonObject x,const char* reason){bool caught=false;try{harness::plan(x);}catch(...){caught=true;}check(caught,reason);};
 auto overflow=input;links=overflow.value("links").toArray();for(int i=0;i<links.size();++i){auto l=links[i].toObject();l["outer_diameter_mm"]=param(1e308);links[i]=l;}overflow["links"]=links;expectFailure(overflow,"nonfinite area/envelope rejected");
 overflow=input;edges=overflow.value("edges").toArray();for(int i=0;i<edges.size();++i){auto e=edges[i].toObject();e["length_mm"]=1e308;edges[i]=e;}overflow["edges"]=edges;expectFailure(overflow,"nonfinite route length rejected");
 overflow=input;settings=overflow.value("settings").toObject();settings["fill_ratio"]=1e-320;overflow["settings"]=settings;expectFailure(overflow,"nonfinite area quotient rejected");
 auto schema=input;schema["schema_version"]=1.5;expectFailure(schema,"fractional schema version rejected");schema["schema_version"]="1";expectFailure(schema,"string schema version rejected");schema["schema_version"]=true;expectFailure(schema,"boolean schema version rejected");
 QTextStream(stdout)<<"PASS "<<assertions<<" assertions; compatible, branch, deny, unknown, conservation, continuity, capacity, accessibility, determinism, budget\n";return 0;
 }catch(const std::exception& e){QTextStream(stderr)<<"FAIL after "<<assertions<<": "<<e.what()<<"\n";return 1;}}
