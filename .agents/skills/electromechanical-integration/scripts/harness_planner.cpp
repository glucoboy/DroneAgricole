// C++17 : proposition topologique uniquement, aucune écriture FreeCAD.
#include "harness_planner.hpp"
#include <QCoreApplication>
#include <QCryptographicHash>
#include <QFile>
#include <QFileInfo>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonParseError>
#include <QSaveFile>
#include <QTextStream>
#include <algorithm>
#include <cmath>
#include <functional>
#include <limits>
#include <map>
#include <set>
#include <stdexcept>
#include <vector>

namespace harness {
namespace {
using Path = std::vector<QString>;
struct Link { QString id, from, to, category; QJsonObject raw; };
struct Edge { QString id, from, to; double length; QJsonValue width; };
struct Network {
    QJsonObject raw;
    std::map<QString, Link> links;
    std::map<QString, Edge> edges;
    std::map<QString, QString> connectorNodes;
    std::map<QString, bool> accessible;
    std::map<QString, std::vector<QString>> adjacent;
    std::map<std::pair<QString,QString>, QString> compatibility;
    int maxPaths=8, maxExpansions=10000, maxCandidates=3;
    double fill=0.0;
    QStringList objectives;
};
void require(bool ok,const QString& reason) { if(!ok) throw std::runtime_error(reason.toStdString()); }
double finite(double value,const QString& name) {require(std::isfinite(value),"Calcul non fini : "+name);return value;}
QString str(const QJsonObject& o,const char* key) {
    auto v=o.value(key); require(v.isString()&&!v.toString().isEmpty(),QString("Chaîne manquante : ")+key); return v.toString();
}
QJsonArray array(const QJsonObject& o,const char* key) {
    auto v=o.value(key); require(v.isArray(),QString("Tableau manquant : ")+key); return v.toArray();
}
double positive(const QJsonValue& v,const QString& name) {
    require(v.isDouble()&&std::isfinite(v.toDouble())&&v.toDouble()>0,"Valeur positive requise : "+name); return v.toDouble();
}
QJsonArray strings(const Path& p) { QJsonArray a;for(const auto& x:p)a.append(x);return a; }
std::pair<QString,QString> key(QString a,QString b) { if(b<a)std::swap(a,b);return {a,b}; }
QString compatibility(const Network& n,const QString& a,const QString& b) {
    auto k=key(n.links.at(a).category,n.links.at(b).category);auto it=n.compatibility.find(k);
    return it==n.compatibility.end()?"unknown":it->second;
}
bool vector3(const QJsonValue& v,bool axis=false) {
    if(!v.isArray()||v.toArray().size()!=3)return false;double sq=0;
    for(auto x:v.toArray()){if(!x.isDouble()||!std::isfinite(x.toDouble()))return false;sq+=x.toDouble()*x.toDouble();}
    return !axis||sq>0;
}
Network parse(const QJsonObject& input) {
    require(input.value("schema_version").isDouble()&&input.value("schema_version").toDouble()==1.0,"schema_version doit être l'entier 1");Network n;n.raw=input;
    std::set<QString> connectors;
    for(auto v:array(input,"connectors")){
        auto c=v.toObject();auto id=str(c,"id");require(connectors.insert(id).second,"Connecteur dupliqué : "+id);
        require(c.value("position_mm").isNull()||vector3(c.value("position_mm")),"Position invalide : "+id);
        require(c.value("exit_axis").isNull()||vector3(c.value("exit_axis"),true),"Axe invalide : "+id);
    }
    for(auto v:array(input,"nodes")){
        auto o=v.toObject();auto id=str(o,"id");require(n.accessible.emplace(id,o.value("accessible").toBool(false)).second,"Nœud dupliqué : "+id);
        auto c=o.value("connector_id").toString();if(!c.isEmpty()){
            require(connectors.count(c),"Connecteur de nœud inconnu : "+c);
            require(n.connectorNodes.emplace(c,id).second,"Connecteur associé à plusieurs nœuds : "+c);
        }
    }
    for(auto v:array(input,"links")){
        auto o=v.toObject();Link l{str(o,"id"),str(o,"from"),str(o,"to"),str(o,"category"),o};
        require(n.links.emplace(l.id,l).second,"Liaison dupliquée : "+l.id);
        require(l.from!=l.to&&n.connectorNodes.count(l.from)&&n.connectorNodes.count(l.to),"Extrémités de liaison invalides : "+l.id);
        for(auto p:{"outer_diameter_mm","min_bend_radius_mm"}){
            require(o.value(p).isObject(),"Paramètre absent (utiliser value:null) : "+QString(p));auto q=o.value(p).toObject();
            require(q.contains("value")&&q.contains("source")&&q.contains("confidence"),"Provenance incomplète : "+l.id+"/"+p);
            if(!q.value("value").isNull())positive(q.value("value"),l.id+"/"+p);
            require(QStringList{"supplier","measured","candidate","unknown"}.contains(q.value("confidence").toString()),"Confiance invalide : "+l.id);
            require(q.value("source").isNull()||q.value("source").isString(),"Source invalide : "+l.id);
        }
    }
    require(!n.links.empty(),"Au moins une liaison requise");
    for(auto v:array(input,"edges")){
        auto o=v.toObject();Edge e{str(o,"id"),str(o,"from"),str(o,"to"),positive(o.value("length_mm"),"length_mm"),o.value("usable_width_mm")};
        require(n.accessible.count(e.from)&&n.accessible.count(e.to)&&e.from!=e.to,"Extrémités arête invalides : "+e.id);
        require(e.width.isNull()||e.width.isDouble(),"usable_width_mm absent/invalide : "+e.id);
        if(!e.width.isNull())positive(e.width,e.id+"/usable_width_mm");
        require(n.edges.emplace(e.id,e).second,"Arête dupliquée : "+e.id);
        n.adjacent[e.from].push_back(e.id);n.adjacent[e.to].push_back(e.id);
    }
    for(auto& p:n.adjacent)std::sort(p.second.begin(),p.second.end());
    for(auto v:array(input,"compatibility")){
        auto o=v.toObject();auto cats=array(o,"categories");require(cats.size()==2&&cats[0].isString()&&cats[1].isString(),"Paire de catégories invalide");
        auto d=str(o,"decision");require(QStringList{"allow","deny","unknown"}.contains(d),"Décision compatibilité invalide");
        if(d!="unknown"){str(o,"source");str(o,"reason");}
        require(n.compatibility.emplace(key(cats[0].toString(),cats[1].toString()),d).second,"Règle compatibilité dupliquée");
    }
    auto settings=input.value("settings").toObject();n.fill=positive(settings.value("fill_ratio"),"fill_ratio");require(n.fill<=1,"fill_ratio > 1");
    auto integer=[&](const char* name,int fallback,int limit){auto v=settings.value(name);if(v.isUndefined())return fallback;require(v.isDouble()&&v.toDouble()==std::floor(v.toDouble())&&v.toInt()>0&&v.toInt()<=limit,QString("Budget invalide : ")+name);return v.toInt();};
    n.maxPaths=integer("max_paths_per_link",8,1000);n.maxExpansions=integer("max_expansions",10000,1000000);n.maxCandidates=integer("max_candidates",3,3);
    auto order=settings.value("objective_order").toArray();if(order.isEmpty())order=QJsonArray{"bundle_segments","support_sites","envelope_mm3","cable_length_mm"};
    for(auto v:order){auto s=v.toString();require(QStringList{"bundle_segments","support_sites","envelope_mm3","cable_length_mm","branch_count","shared_length_mm"}.contains(s),"Objectif inconnu : "+s);require(!n.objectives.contains(s),"Objectif dupliqué : "+s);n.objectives.append(s);}
    return n;
}
double length(const Network& n,const Path& p){double x=0;for(auto e:p)x=finite(x+n.edges.at(e).length,"route_length_mm");return x;}
std::vector<Path> paths(const Network& n,const Link& link,bool& truncated) {
    std::vector<Path> out;Path route;std::set<QString> visited;int expansions=0;
    const auto target=n.connectorNodes.at(link.to);const auto start=n.connectorNodes.at(link.from);
    // Budget explicite : exploration DFS de chemins simples, puis tri. Pas k-shortest garanti.
    std::function<void(const QString&)> walk=[&](const QString& node){
        if(expansions>=n.maxExpansions){truncated=true;return;}++expansions;
        if(node==target){out.push_back(route);return;}visited.insert(node);
        auto adj=n.adjacent.find(node);if(adj!=n.adjacent.end())for(auto id:adj->second){auto e=n.edges.at(id);auto next=e.from==node?e.to:e.from;if(!visited.count(next)){route.push_back(id);walk(next);route.pop_back();}}
        visited.erase(node);
    };walk(start);
    std::sort(out.begin(),out.end(),[&](const auto& a,const auto& b){double la=length(n,a),lb=length(n,b);return la==lb?a<b:la<lb;});
    if(static_cast<int>(out.size())>n.maxPaths){out.resize(n.maxPaths);truncated=true;}return out;
}
QJsonObject candidate(const QString& id,const std::map<QString,Path>& routes,bool separate) {
    QJsonArray rows;for(auto& p:routes)rows.append(QJsonObject{{"link_id",p.first},{"edge_ids",strings(p.second)}});
    return {{"id",id},{"routes",rows},{"grouping",separate?"separate":"compatible"}};
}
QJsonObject evaluate(const Network& n,const QJsonObject& c) {
    QJsonArray errors,unknowns,segments;std::map<QString,Path> routes;std::map<QString,Path> members;std::map<QString,std::set<QString>> nodeMembership;
    auto err=[&](const QString& s){errors.append(s);};auto unk=[&](const QString& s){unknowns.append(s);};
    require(c.value("routes").isArray(),"Candidate routes absent");QString id=str(c,"id");auto grouping=c.value("grouping").toString("compatible");require(grouping=="compatible"||grouping=="separate","grouping invalide");
    for(auto v:c.value("routes").toArray()){
        auto o=v.toObject();auto lid=str(o,"link_id");if(!n.links.count(lid)){err("unknown_link:"+lid);continue;}
        if(routes.count(lid)){err("duplicate_link:"+lid);continue;}Path p;auto raw=array(o,"edge_ids");auto l=n.links.at(lid);QString node=n.connectorNodes.at(l.from);std::set<QString> seen{node};bool good=true;
        for(auto x:raw){auto eid=x.toString();p.push_back(eid);if(!n.edges.count(eid)){err("unknown_edge:"+lid+":"+eid);good=false;break;}auto e=n.edges.at(eid);
            if(node!=e.from&&node!=e.to){err("discontinuous_path:"+lid);good=false;break;}node=node==e.from?e.to:e.from;
            if(!seen.insert(node).second){err("cyclic_path:"+lid);good=false;break;}
        }
        routes[lid]=p;if(node!=n.connectorNodes.at(l.to)||p.empty()){err("wrong_endpoint:"+lid);good=false;}
        if(good)for(auto e:p){members[e].push_back(lid);nodeMembership[n.edges.at(e).from].insert(lid);nodeMembership[n.edges.at(e).to].insert(lid);}
    }
    for(auto& l:n.links){if(!routes.count(l.first))err("missing_link:"+l.first);
        for(auto param:{"outer_diameter_mm","min_bend_radius_mm"}){auto q=l.second.raw.value(param).toObject();if(q.value("value").isNull()||q.value("source").isNull()||q.value("source").toString().isEmpty()||!QStringList{"supplier","measured"}.contains(q.value("confidence").toString()))unk("unconfirmed_parameter:"+l.first+":"+param);}
    }
    double cableLength=0,sharedLength=0,envelope=0;int bundles=0,shared=0;bool envelopeKnown=true;
    for(auto& p:members){auto& e=n.edges.at(p.first);std::vector<Path> groups;std::sort(p.second.begin(),p.second.end());
        for(auto lid:p.second){bool placed=false;if(grouping=="compatible")for(auto& group:groups){bool ok=true;for(auto other:group)if(compatibility(n,lid,other)!="allow")ok=false;if(ok){group.push_back(lid);placed=true;break;}}if(!placed)groups.push_back({lid});}
        // Unknown compatibility never authorises common protection. Separate groups still require spatial verification.
        for(size_t a=0;a<p.second.size();++a)for(size_t b=a+1;b<p.second.size();++b){auto d=compatibility(n,p.second[a],p.second[b]);if(d=="unknown")unk("compatibility_unknown:"+p.second[a]+":"+p.second[b]+":"+e.id);else if(d=="deny")unk("separation_geometry_required:"+p.second[a]+":"+p.second[b]+":"+e.id);}
        double occupiedWidth=0;bool widthKnown=true;
        for(auto group:groups){double sumsq=0,individualDiameter=0;bool known=true;const bool bundled=group.size()>1;for(auto lid:group){auto q=n.links.at(lid).raw.value("outer_diameter_mm").toObject();auto v=q.value("value");if(v.isNull())known=false;else if(bundled)sumsq=finite(sumsq+finite(v.toDouble()*v.toDouble(),"diameter_squared"),"sum_diameters_squared");else individualDiameter=v.toDouble();}
            double diameter=bundled?std::sqrt(finite(sumsq/n.fill,"bundle_area_bound")):individualDiameter;finite(diameter,"required_width_mm");QJsonValue width=known?QJsonValue(diameter):QJsonValue(QJsonValue::Null);
            QJsonValue sleeve=known&&bundled?QJsonValue(diameter):QJsonValue(QJsonValue::Null);
            segments.append(QJsonObject{{"edge_ids",QJsonArray{e.id}},{"link_ids",strings(group)},{"length_mm",e.length},{"inner_diameter_estimate_mm",sleeve},{"required_width_mm",width},{"dimensioning_status",bundled?"preliminary_area_bound":"individual_cable"}});++bundles;
            if(known){occupiedWidth=finite(occupiedWidth+diameter,"occupied_width_mm");envelope=finite(envelope+3.14159265358979323846/4*diameter*diameter*e.length,"envelope_mm3");}else{widthKnown=false;envelopeKnown=false;}
            if(bundled){++shared;sharedLength=finite(sharedLength+e.length,"shared_length_mm");}cableLength=finite(cableLength+e.length*group.size(),"cable_length_mm");
        }
        if(e.width.isNull()||!widthKnown)unk("corridor_capacity_unknown:"+e.id);else if(occupiedWidth>e.width.toDouble()+1e-9)err("corridor_capacity_exceeded:"+e.id);
    }
    QJsonArray branches;std::set<QString> usedNodes;for(auto& p:members){usedNodes.insert(n.edges.at(p.first).from);usedNodes.insert(n.edges.at(p.first).to);}
    for(auto node:usedNodes){std::set<QString> signatures;int degree=0;for(auto eid:n.adjacent.at(node)){auto it=members.find(eid);if(it==members.end())continue;++degree;QStringList sig;for(auto l:it->second)sig.append(l);signatures.insert(sig.join("|"));}
        if(degree>=3&&signatures.size()>1){branches.append(node);if(!n.accessible.at(node))err("inaccessible_branch:"+node);}
    }
    for(auto v:n.raw.value("connectors").toArray()){auto q=v.toObject();if(q.value("position_mm").isNull()||q.value("exit_axis").isNull())unk("connector_pose_unknown:"+q.value("id").toString());}
    QJsonObject metrics{{"bundle_segments",bundles},{"shared_segments",shared},{"shared_length_mm",sharedLength},{"cable_length_mm",cableLength},{"branch_count",branches.size()},{"support_sites",static_cast<int>(usedNodes.size())},{"envelope_mm3",envelopeKnown?QJsonValue(envelope):QJsonValue(QJsonValue::Null)},{"mass_g",QJsonValue::Null}};
    return {{"id",id},{"routes",c.value("routes")},{"grouping",grouping},{"segments",segments},{"branches",branches},{"metrics",metrics},{"errors",errors},{"unknowns",unknowns},{"decision",errors.isEmpty()?(unknowns.isEmpty()?"candidate":"unresolved"):"rejected"}};
}
QJsonObject baseReport(const QJsonObject& input) {
    auto bytes=QJsonDocument(input).toJson(QJsonDocument::Compact);return {{"schema_version",1},{"input_sha256",QString::fromLatin1(QCryptographicHash::hash(bytes,QCryptographicHash::Sha256).toHex())},{"hash_scope","Qt canonical compact parsed JSON; input file SHA256 recorded separately by CLI"},{"execution",QJsonObject{{"offline","executed"},{"geometry","not_executed"},{"freecad_recompute","not_executed"},{"interactive","not_executed"},{"physical","not_executed"}}},{"qualification","not_assessed"}};
}
}
QJsonObject validate(const QJsonObject& input,const QJsonObject& c) {
    auto n=parse(input);auto r=baseReport(input);auto e=evaluate(n,c);r["candidates"]=QJsonArray{e};r["selected_candidate_id"]=e.value("decision")=="rejected"?QJsonValue(QJsonValue::Null):e.value("id");r["selection_scope"]="preliminary_topology_only";return r;
}
QJsonObject plan(const QJsonObject& input) {
    auto n=parse(input);std::map<QString,std::vector<Path>> options;bool truncated=false;std::map<QString,Path> baseline;
    for(auto& l:n.links){options[l.first]=paths(n,l.second,truncated);require(!options[l.first].empty(),"Aucun chemin trouvé dans budget : "+l.first);baseline[l.first]=options[l.first][0];}
    QJsonArray proposals;proposals.append(evaluate(n,candidate("baseline_separate",baseline,true)));
    auto pooled=[&](bool reverse){std::map<QString,Path> routes;std::map<QString,Path> users;Path order;for(auto& l:n.links)order.push_back(l.first);if(reverse)std::reverse(order.begin(),order.end());
        for(auto lid:order){double best=std::numeric_limits<double>::infinity();Path chosen;
            for(auto p:options[lid]){double score=0;for(auto eid:p){bool common=!users[eid].empty();for(auto other:users[eid])if(compatibility(n,lid,other)!="allow")common=false;score=finite(score+n.edges.at(eid).length*(common?0.1:1.0),"pooling_score");}if(score<best){best=score;chosen=p;}}
            routes[lid]=chosen;for(auto eid:chosen)users[eid].push_back(lid);
        }return evaluate(n,candidate(reverse?"pooled_reverse":"pooled_forward",routes,false));};
    if(n.maxCandidates>=2)proposals.append(pooled(false));if(n.maxCandidates>=3)proposals.append(pooled(true));
    int selected=-1;for(int i=0;i<proposals.size();++i){auto a=proposals[i].toObject();if(a.value("decision")=="rejected")continue;if(selected<0){selected=i;continue;}auto b=proposals[selected].toObject();
        // Unresolved candidates cannot outrank fully checked offline candidates through shorter paths.
        int ar=a.value("unknowns").toArray().isEmpty()?0:1,br=b.value("unknowns").toArray().isEmpty()?0:1;
        if(ar!=br){if(ar<br)selected=i;continue;}
        for(auto obj:n.objectives){auto av=a.value("metrics").toObject().value(obj),bv=b.value("metrics").toObject().value(obj);if(av.isNull()||bv.isNull())continue;double x=av.toDouble(),y=bv.toDouble();if(obj=="shared_length_mm"){x=-x;y=-y;}if(x<y){selected=i;break;}if(x>y)break;}
    }
    auto r=baseReport(input);r["candidates"]=proposals;r["selected_candidate_id"]=selected<0?QJsonValue(QJsonValue::Null):proposals[selected].toObject().value("id");r["selection_scope"]="preliminary_topology_only";r["search_truncated"]=truncated;r["search_budget"]=QJsonObject{{"max_paths_per_link",n.maxPaths},{"max_expansions_per_link",n.maxExpansions},{"max_candidates",n.maxCandidates}};r["optimality_proven"]=false;
    QJsonArray objectives;for(auto o:n.objectives)objectives.append(o);r["objective_order"]=objectives;return r;
}
QString markdown(const QJsonObject& report) {
    QString out="# Comparaison topologique préliminaire\n\nAucune validation géométrique, interactive ou physique exécutée par cet outil.\n\n";
    out+="Entrée SHA256 canonique : `"+report.value("input_sha256").toString()+"`.\n\n";
    out+="| Candidat | Décision hors ligne | Tronçons/groupes | Partagés (mm) | Câbles (mm) | Erreurs | Réserves |\n|---|---|---:|---:|---:|---:|---:|\n";
    for(auto v:report.value("candidates").toArray()){auto c=v.toObject(),m=c.value("metrics").toObject();out+="| "+c.value("id").toString()+" | "+c.value("decision").toString()+" | "+QString::number(m.value("bundle_segments").toInt())+" | "+QString::number(m.value("shared_length_mm").toDouble())+" | "+QString::number(m.value("cable_length_mm").toDouble())+" | "+QString::number(c.value("errors").toArray().size())+" | "+QString::number(c.value("unknowns").toArray().size())+" |\n";}
    out+="\nProposition : "+report.value("selected_candidate_id").toString("aucune")+". Heuristique bornée, optimalité non démontrée.\n";
    for(auto v:report.value("candidates").toArray()){auto c=v.toObject();out+="\n## "+c.value("id").toString()+"\n";for(auto label:{"errors","unknowns"})for(auto item:c.value(label).toArray())out+="\n- `"+item.toString()+"`";out+="\n";}return out;
}
}
#ifndef HARNESS_PLANNER_LIBRARY
namespace {
QJsonObject read(const QString& path,QByteArray* bytes=nullptr){QFile f(path);if(!f.open(QIODevice::ReadOnly))throw std::runtime_error("Lecture impossible");auto b=f.readAll();if(bytes)*bytes=b;QJsonParseError e;auto doc=QJsonDocument::fromJson(b,&e);if(e.error!=QJsonParseError::NoError||!doc.isObject())throw std::runtime_error("JSON invalide");return doc.object();}
void save(const QString& path,const QByteArray& bytes){QSaveFile f(path);if(!f.open(QIODevice::WriteOnly)||f.write(bytes)!=bytes.size()||!f.commit())throw std::runtime_error("Écriture/finalisation impossible");}
QString resolved(const QString& path){QFileInfo f(path);auto p=f.canonicalFilePath();if(p.isEmpty())p=f.absoluteFilePath();
#ifdef Q_OS_WIN
return p.toCaseFolded();
#else
return p;
#endif
}
}
int main(int argc,char** argv){QCoreApplication app(argc,argv);try{auto args=app.arguments();bool validate=args.value(1)=="validate";if((!validate&&args.value(1)!="plan")||args.size()!=(validate?6:5)){QTextStream(stderr)<<"harness-planner plan input.json report.json report.md\nharness-planner validate input.json candidate.json report.json report.md\n";return 2;}
    int offset=validate?1:0;QStringList inputs{resolved(args[2])};if(validate)inputs.append(resolved(args[3]));auto jsonOut=resolved(args[3+offset]),mdOut=resolved(args[4+offset]);
    if(jsonOut==mdOut||inputs.contains(jsonOut)||inputs.contains(mdOut))throw std::runtime_error("Sorties confondues avec entrées ou entre elles");
    QByteArray bytes,candidateBytes;auto input=read(args[2],&bytes);auto r=validate?harness::validate(input,read(args[3],&candidateBytes)):harness::plan(input);r["input_file_sha256"]=QString::fromLatin1(QCryptographicHash::hash(bytes,QCryptographicHash::Sha256).toHex());
    if(validate)r["candidate_file_sha256"]=QString::fromLatin1(QCryptographicHash::hash(candidateBytes,QCryptographicHash::Sha256).toHex());
    save(args[3+offset],QJsonDocument(r).toJson(QJsonDocument::Indented));save(args[4+offset],harness::markdown(r).toUtf8());return r.value("selected_candidate_id").isNull()?1:0;
}catch(const std::exception& e){QTextStream(stderr)<<e.what()<<"\n";return 2;}}
#endif
