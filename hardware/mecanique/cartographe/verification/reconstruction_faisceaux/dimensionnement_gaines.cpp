// Calcul preliminaire de sections, sans autorisation de regroupement ni generation CAO.
#include <QCoreApplication>
#include <QCryptographicHash>
#include <QFile>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QMap>
#include <QSaveFile>
#include <QTextStream>
#include <algorithm>
#include <cmath>
#include <stdexcept>

static QByteArray bytes(const QString &path) {
    QFile f(path);
    if (!f.open(QIODevice::ReadOnly)) throw std::runtime_error("Lecture impossible");
    return f.readAll();
}
static QString hash(const QString &path) {
    return QString::fromLatin1(QCryptographicHash::hash(bytes(path), QCryptographicHash::Sha256).toHex());
}
static QJsonObject object(const QString &path) {
    QJsonParseError err;
    const auto d=QJsonDocument::fromJson(bytes(path), &err);
    if (err.error!=QJsonParseError::NoError || !d.isObject()) throw std::runtime_error("JSON invalide");
    return d.object();
}
static QJsonObject parameter(double value, const QString &unit, const QString &source) {
    return {{"value",value},{"unit",unit},{"source",source},{"confidence","candidate"}};
}
int main(int argc,char **argv) {
    QCoreApplication app(argc,argv);
    try {
        if (argc!=5) throw std::runtime_error("Usage: executable analyse.json routes.json source.cpp sortie.json");
        const QString analysisPath=QString::fromLocal8Bit(argv[1]);
        const QString routesPath=QString::fromLocal8Bit(argv[2]);
        const QString sourcePath=QString::fromLocal8Bit(argv[3]);
        const QString outputPath=QString::fromLocal8Bit(argv[4]);
        const QString aHash=hash(analysisPath),rHash=hash(routesPath);
        const auto analysis=object(analysisPath);
        QMap<QString,QJsonObject> routes;
        for(const auto &v:object(routesPath)["routes"].toArray()) {
            const auto r=v.toObject();const auto id=r["id"].toString();
            if(id.isEmpty() || routes.contains(id))throw std::runtime_error("Identite route invalide");
            routes.insert(id,r);
        }
        constexpr double fill=0.4;
        QJsonArray groups;
        for(const auto &v:analysis["proposed_common_sleeves"].toArray()) {
            const auto g=v.toObject(); const auto members=g["members"].toArray();
            if(members.size()<2)throw std::runtime_error("Groupe sans au moins deux membres");
            QJsonArray diameters;double squares=0,sum=0;
            for(const auto &m:members) {
                const QString id=m.toString();
                if(!routes.contains(id))throw std::runtime_error("Route de groupe absente");
                const auto r=routes[id];
                const auto diameter=r["diametre_mm"];
                if(!diameter.isDouble() || !std::isfinite(diameter.toDouble()) || diameter.toDouble()<=0)
                    throw std::runtime_error("Diametre CAO manquant ou invalide");
                const double d=diameter.toDouble();sum+=d;squares+=d*d;
                diameters.append(QJsonObject{{"route_id",id},{"bom_ids",r["bom_ids"]},
                    {"diameter",parameter(d,"mm",routesPath+"#/routes/id="+id+"/diametre_mm")},
                    {"function",r["fonction"]},{"actual_supplier_tolerance_mm",QJsonValue::Null}});
            }
            const double area=std::sqrt(squares/fill),candidate=std::max(area,sum);
            if(!std::isfinite(candidate))throw std::runtime_error("Depassement numerique");
            QJsonArray packing;double x=-sum/2;
            for(const auto &m:members) {
                const QString id=m.toString();const double d=routes[id]["diametre_mm"].toDouble();
                packing.append(QJsonObject{{"route_id",id},{"nominal_center_xy_mm",QJsonArray{x+d/2,0}},
                    {"nominal_radius_mm",d/2}});x+=d;
            }
            groups.append(QJsonObject{{"id",g["id"]},{"members",members},{"input_diameters",diameters},
                {"area_bound_inner_diameter",parameter(area,"mm","sqrt(sum(di^2)/0.4)")},
                {"inline_nominal_packing_diameter",parameter(sum,"mm","sum(di), disques tangents alignes")},
                {"candidate_inner_diameter",parameter(candidate,"mm","max(borne aire, disposition alignee)")},
                {"nominal_packing",packing},{"actual_fill_fraction_nominal",squares/(candidate*candidate)},
                {"physical_status","NON_VERIFIE"},{"compatibility_decision","unknown"},
                {"packing_scope","Section nominale droite uniquement ; contacts tangents, aucune marge de tolerance ni preuve de courbure/insertion"},
                {"assembly_candidate","Gaine ouvrable/fendue a etudier pour cordons pretermines ; pas de coupe ni depose implicite de connecteur"},
                {"wall_thickness_mm",QJsonValue::Null},{"outside_diameter_mm",QJsonValue::Null},
                {"supplier_reference",QJsonValue::Null},{"diameter_tolerance_mm",QJsonValue::Null},
                {"mass_g",QJsonValue::Null},{"corridor_capacity_mm",QJsonValue::Null},
                {"conditions_before_geometry",g["conditions"]}});
        }
        if(groups.size()!=8)throw std::runtime_error("Huit groupes attendus");
        if(hash(analysisPath)!=aHash || hash(routesPath)!=rHash)throw std::runtime_error("Entree modifiee pendant calcul");
        QJsonObject report{{"schema","cartographe.dimensionnement_gaines.v1"},{"date","2026-10-28"},
            {"status","NON_VERIFIE"},{"maturity","A valider"},
            {"scope","Predimensionnement nominal des huit hypotheses ; aucune gaine choisie, routee ou autorisee CEM"},
            {"fill_ratio",parameter(fill,"1","Hypothese exploratoire commune au planificateur, non exigence fournisseur")},
            {"source_hashes",QJsonObject{{analysisPath,aHash},{routesPath,rHash},{sourcePath,hash(sourcePath)},
                {app.applicationFilePath(),hash(app.applicationFilePath())}}},
            {"environment",QJsonObject{{"language","C++17"},{"qt",QT_VERSION_STR}}},
            {"groups",groups},{"sources_unchanged",true},
            {"limitations",QJsonArray{"Diametres de representation CAO, non mesures de lot fournisseur", 
                "Le taux 0.4 est une hypothese de comparaison, sans qualification thermique", 
                "Disposition droite nominale explicite ; decalages sur courbes, tolerance, frottement et mouvement non controles", 
                "Diametre exterieur inconnu sans paroi ; enveloppe de reservation et collisions non demontrables", 
                "Les criteres CEM, thermique, independance et maintenance conditionnent chaque partage"}}};
        QSaveFile file(outputPath);
        if(!file.open(QIODevice::WriteOnly))throw std::runtime_error("Sortie inaccessible");
        if(file.write(QJsonDocument(report).toJson(QJsonDocument::Indented))<0 || !file.commit())throw std::runtime_error("Sortie non finalisee");
        const auto check=object(outputPath);
        if(check["groups"].toArray().size()!=8)throw std::runtime_error("Relecture sortie incorrecte");
        QTextStream(stdout)<<"8 groupes dimensionnes, JSON finalise et relu ; aucune autorisation de partage.\n";
        return 0;
    }catch(const std::exception &e){QTextStream(stderr)<<e.what()<<'\n';return 2;}
}
