// Réconciliation documentaire du lot ORCH-CAO-MASSE-1 ; aucun simulateur lancé.
#include <QCoreApplication>
#include <QCryptographicHash>
#include <QDateTime>
#include <QDir>
#include <QFile>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QSaveFile>
#include <QSet>
#include <QTemporaryDir>
#include <cmath>
#include <iostream>
#include <stdexcept>
#include "MassProperties.hpp"

namespace {
void require(bool b,const QString& m){if(!b)throw std::runtime_error(m.toStdString());}
QJsonObject read(const QString& p){QFile f(p);require(f.open(QIODevice::ReadOnly),"Lecture impossible: "+p);QJsonParseError e;auto d=QJsonDocument::fromJson(f.readAll(),&e);require(e.error==QJsonParseError::NoError&&d.isObject(),"JSON invalide: "+p);return d.object();}
QString sha(const QString& p){QFile f(p);require(f.open(QIODevice::ReadOnly),"Source absente: "+p);QCryptographicHash h(QCryptographicHash::Sha256);require(h.addData(&f),"Empreinte impossible: "+p);return QString::fromLatin1(h.result().toHex());}
void write(const QString& p,const QJsonObject& o){QDir().mkpath(QFileInfo(p).absolutePath());QSaveFile f(p);auto b=QJsonDocument(o).toJson();require(f.open(QIODevice::WriteOnly)&&f.write(b)==b.size()&&f.commit(),"Publication impossible: "+p);}
double grams(double volumeMm3,double densityGcm3){require(std::isfinite(volumeMm3)&&volumeMm3>0&&std::isfinite(densityGcm3)&&densityGcm3>0,"Volume ou densité invalide");return volumeMm3*densityGcm3/1000.;}
double linearGrams(double lengthMm,double gramsPerM){require(std::isfinite(lengthMm)&&lengthMm>0&&std::isfinite(gramsPerM)&&gramsPerM>0,"Longueur ou masse linéique invalide");return lengthMm*gramsPerM/1000.;}
bool nominal(const QJsonObject& m){auto q=m["qualificatif"].toString();return m["applicable"].toBool()&&m["valeur_g"].isDouble()&&QStringList{"nominale","approximative","mesuree","calculee"}.contains(q);}
bool excludedQuantity(const QJsonValue& q){return q.isDouble()&&q.toDouble()==0.;}
bool knownQuantity(const QJsonValue& q){return q.isDouble()&&std::isfinite(q.toDouble())&&q.toDouble()>0.;}
QString shapeKey(const QString& file,const QString& object){require(!file.isEmpty()&&!object.isEmpty(),"Référence géométrique incomplète");return file+"#"+object;}
QJsonObject candidateRecipe(const QJsonObject& row,const QJsonObject& materials,const QJsonObject& oem){
 const auto id=row["id"].toString();auto recipe=oem[id].toObject();
 if(!recipe.isEmpty()){
  require(recipe["fichier"]==row["source"]&&recipe["objet_source"]==row["objet_source"]&&recipe["bom_id"]==row["proprietaire_masse_bom"],"Recette OEM affectée à une autre occurrence: "+id);
 }else recipe=materials[row["source"].toString()].toObject();
 return recipe;
}
QString ownerFromInclusions(const QJsonArray& candidates,const QJsonObject& items){
 QString result;
 for(const auto& value:candidates){const auto candidate=value.toString();if(!items.contains(candidate))continue;bool covers=true;
  for(const auto& child:candidates){auto current=child.toString();QSet<QString> visited;
   while(!current.isEmpty()&&current!=candidate){require(!visited.contains(current),"Cycle d'inclusion");visited.insert(current);current=items[current].toObject()["masse_incluse_dans"].toString();}
   if(current!=candidate)covers=false;
  }
  if(covers){require(result.isEmpty(),"Propriétaire d'ensemble ambigu");result=candidate;}
 }
 return result;
}
void integrationTests();
void selfTest(){
 require(std::abs(grams(1000,1.77)-1.77)<1e-12,"conversion mm3/cm3");
 require(std::abs(linearGrams(1000,34)-34)<1e-12,"conversion mm/m du faisceau");
 require(!nominal({{"valeur_g",85},{"qualificatif","maximale"},{"applicable",true}}),"une borne devient nominale");
 require(!nominal({{"valeur_g",185},{"qualificatif","nominale"},{"applicable",false}}),"périmètre non confirmé compté");
 require(!nominal({{"valeur_g",QJsonValue::Null},{"qualificatif","inconnue"},{"applicable",true}}),"inconnue comptée");
 require(!excludedQuantity(QJsonValue(QJsonValue::Null))&&!knownQuantity(QJsonValue(QJsonValue::Null)),"quantité inconnue assimilée à zéro");
 bool rejected=false;try{grams(0,1);}catch(const std::runtime_error&){rejected=true;}require(rejected,"volume nul accepté");
 using namespace cartographe::mass;Component a{"piece","",1.,{},{}},b{"accessoire","piece",.1,{},{}};auto x=aggregate({a,b});require(x.massComplete&&x.knownMass==1&&!x.complete,"masse sans distribution/inclusion");
 integrationTests();
 std::cout<<"Conversions, bornes, applicabilité, inconnues et inclusion : conformes\n";
}
void run(const QString& root,bool publish){
 const QString cad="hardware/mecanique/cartographe/",ver=cad+"verification/";
 const auto bomPath=root+"/"+cad+"nomenclature_prototype.json";
 auto bom=read(bomPath),manifest=read(root+"/"+cad+"manifest.json")["prototype_cartographe"].toObject();
 auto geo=read(root+"/"+ver+"orch_cao_masse_geometrie.json");
 require(geo["finalisation_correcte"].toBool(),"Extraction géométrique non finalisée");
 auto expected=geo["natifs_sha256"].toObject();require(!expected.isEmpty(),"Fermeture des natifs absente");
 QSet<QString> nativeScope;
 for(const auto& v:manifest["references"].toArray())nativeScope.insert(v.toObject()["fichier"].toString());
 const auto preserved=manifest["sources_preservees"].toObject();for(auto i=preserved.begin();i!=preserved.end();++i)nativeScope.insert(i.key());
 require(!nativeScope.isEmpty()&&nativeScope.size()==expected.size(),"Périmètre natif différent du manifeste");
 for(auto i=expected.begin();i!=expected.end();++i){require(nativeScope.contains(i.key()),"Natif hors manifeste: "+i.key());require(sha(root+"/"+cad+i.key())==i.value().toString(),"Natif modifié depuis extraction: "+i.key());}
 require(sha(root+"/"+ver+"orch_integrate_cao.py")==geo["script_sha256"].toString(),"Extracteur modifié depuis extraction");
 require(sha(root+"/"+ver+"read_brep_prototype.py")==geo["lecteur_sha256"].toString(),"Lecteur BRep modifié depuis extraction");
 QJsonArray results,unknown,bounded,calculated,unallocated,coverage;QJsonObject subtotals,subassemblies,inputs,byReference,byBom;
 std::vector<cartographe::mass::Component> homogeneousCandidates;
 inputs.insert(cad+"manifest.json",sha(root+"/"+cad+"manifest.json"));inputs.insert(ver+"orch_cao_masse_geometrie.json",sha(root+"/"+ver+"orch_cao_masse_geometrie.json"));
 inputs.insert(ver+"orch_integrate_cao.py",geo["script_sha256"]);inputs.insert(ver+"read_brep_prototype.py",geo["lecteur_sha256"]);
 auto definitions=bom["orch_cao_masse_1"].toObject();auto materials=definitions["fabrications_candidates"].toObject();
 const auto oemCandidates=definitions["estimations_geometrie_oem"].toObject();
 const auto harnesses=definitions["faisceaux_calcules_partiels"].toObject();
 const auto componentMasses=definitions["recettes_composants_documentaires"].toObject();
 auto proofs=definitions["preuves_sources_sha256"].toObject();require(!proofs.isEmpty(),"Provenance des investigations absente");
 for(auto i=proofs.begin();i!=proofs.end();++i){require(!i.key().contains("..")&&!QFileInfo(i.key()).isAbsolute(),"Chemin source hors projet");require(sha(root+"/"+i.key())==i.value().toString(),"Source ou recette périmée: "+i.key());inputs.insert(i.key(),i.value());}
 for(const auto& p:QStringList{"simulation/mass/BomMass.cpp","simulation/mass/MassProperties.hpp"})inputs.insert(p,sha(root+"/"+p));
 for(const auto& v:geo["references"].toArray()){auto r=v.toObject();const auto file=r["fichier"].toString(),key=shapeKey(file,r["objet"].toString());require(!byReference.contains(key),"Forme source dupliquée: "+key);require(expected.contains(file)&&expected[file]==r["sha256"],"Forme source hors fermeture native: "+key);byReference.insert(key,r);}
 auto physical=geo["occurrences_physiques"].toArray();QSet<QString> physicalIds;QJsonArray resolvedPhysical;
 auto items=bom["items"].toArray();QSet<QString> ids;QJsonObject itemsById;for(const auto& v:items){auto row=v.toObject();auto id=row["id"].toString();require(!id.isEmpty()&&!ids.contains(id),"ID BOM dupliqué");ids.insert(id);itemsById.insert(id,row);if(row["quantite"].isDouble())require(std::isfinite(row["quantite"].toDouble())&&row["quantite"].toDouble()>=0,"Quantité invalide");}
 for(const auto& v:physical){auto r=v.toObject();auto id=r["id"].toString();require(!id.isEmpty()&&!physicalIds.contains(id),"Occurrence physique dupliquée");physicalIds.insert(id);require(byReference.contains(shapeKey(r["source"].toString(),r["objet_source"].toString())),"Occurrence sans forme source: "+id);auto owner=r["proprietaire_masse_bom"].toString();if(owner.isEmpty()){owner=ownerFromInclusions(r["bom_ids"].toArray(),itemsById);r.insert("proprietaire_masse_bom",owner);if(!owner.isEmpty())r.insert("regle_proprietaire","Parent unique couvrant les autres ID par inclusion explicite BOM");}resolvedPhysical.append(r);const auto item=itemsById[owner].toObject();if(owner.isEmpty()||!ids.contains(owner)||item["perimetre"]!="embarque"||excludedQuantity(item["quantite"])){
  r.insert("blocage",owner.isEmpty()?"Propriétaire massique indéterminé":"Propriétaire absent ou hors périmètre embarqué");unallocated.append(r);continue;
 }auto a=byBom[owner].toArray();a.append(r);byBom.insert(owner,a);}
 physical=resolvedPhysical;
 for(auto i=oemCandidates.begin();i!=oemCandidates.end();++i){
  require(physicalIds.contains(i.key()),"Estimation OEM hors occurrences physiques: "+i.key());
  const auto recipe=i.value().toObject();require(recipe["methode"]=="volume_solide_terminal"&&recipe["densite_g_cm3"].toDouble()>0,"Estimation OEM invalide: "+i.key());
 }
 std::vector<cartographe::mass::Component> graph;
 for(const auto& v:items){auto r=v.toObject();if(r["perimetre"]!="embarque"||excludedQuantity(r["quantite"]))continue;auto parent=r["masse_incluse_dans"].toString();require(parent.isEmpty()||ids.contains(parent),"Inclusion sans parent");graph.push_back({r["id"].toString().toStdString(),parent.toStdString(),{},{},{}});}
 cartographe::mass::aggregate(graph); // Références et absence de cycle.
 double known=0,documentedSubtotal=0,candidateSubtotal=0;int applicable=0,partial=0,included=0,completeCalculated=0;QSet<QString> allocatedGeometry,completeCalculatedIds;
 // La couverture d'un parent calculable ne dépend pas de l'ordre des lignes.
 for(const auto& value:items){const auto item=value.toObject();const auto id=item["id"].toString();const auto rows=byBom[id].toArray();if(!item["detail_physique_complet"].toBool()||rows.isEmpty()||!knownQuantity(item["quantite"]))continue;bool complete=true;
  for(const auto& row:rows){const auto r=row.toObject();const auto file=r["source"].toString();const auto recipe=candidateRecipe(r,materials,oemCandidates);const auto shape=byReference[shapeKey(file,r["objet_source"].toString())].toObject();const auto doc=componentMasses[file].toObject();
   const bool calculated=(recipe["methode"]=="volume_solide_terminal"&&recipe["densite_g_cm3"].isDouble()&&shape["volume_mm3"].toDouble()>0&&shape["valide"].toBool())||(recipe["methode"]=="tranchage"&&recipe["volume_extrude_piece_mm3"].isDouble());
   if(!calculated&&!nominal(doc))complete=false;
  }if(complete)completeCalculatedIds.insert(id);
 }
 for(int n=0;n<items.size();++n){auto item=items[n].toObject();if(item["perimetre"]!="embarque"||excludedQuantity(item["quantite"]))continue;
  const auto id=item["id"].toString();auto rows=byBom[id].toArray();auto m=item["donnee_massique"].toObject();
  if(!nominal(m))item.insert("masse_unitaire_g",QJsonValue::Null);
  QJsonArray contents,missing;double partialG=0,partialDocumentedG=0;bool hasPartial=false,partialHarness=false;
  QJsonArray documentaryParts;QSet<QString> documentaryPartIds;
  for(const auto& value:definitions["contributions_documentaires_partielles"].toArray()){
   const auto part=value.toObject();if(part["bom_id"]!=id)continue;
   const auto partId=part["id"].toString();require(!partId.isEmpty()&&!documentaryPartIds.contains(partId),"Contribution documentaire partielle dupliquée: "+id);documentaryPartIds.insert(partId);
   require(knownQuantity(part["quantite_absolue_drone"])&&nominal(part["donnee_massique"].toObject()),"Contribution documentaire partielle invalide: "+id);
   const double g=part["quantite_absolue_drone"].toDouble()*part["donnee_massique"].toObject()["valeur_g"].toDouble();
   require(std::isfinite(g)&&g>0,"Contribution documentaire non positive");partialDocumentedG+=g;documentaryParts.append(part);
  }
  for(const auto& v:rows){auto r=v.toObject();QJsonObject entry{{"occurrence",r["id"]},{"reference",r["source"]},{"objet",r["objet_source"]},{"quantite_absolue_drone",1},{"geometrie_valide",r["valide"]}};
   auto recipe=candidateRecipe(r,materials,oemCandidates);auto shape=byReference[shapeKey(r["source"].toString(),r["objet_source"].toString())].toObject();
   if(recipe.isEmpty())recipe=harnesses[r["source"].toString()].toObject();
   if(!recipe.isEmpty())require(recipe["sha256_natif"].toString()==shape["sha256"].toString(),"Recette de fabrication périmée: "+r["source"].toString());
   if(oemCandidates.contains(r["id"].toString()))require(std::abs(recipe["volume_reference_mm3"].toDouble()-shape["volume_mm3"].toDouble())<1e-6,"Volume OEM divergent: "+r["id"].toString());
   if(!recipe.isEmpty()&&recipe["densite_g_cm3"].isDouble()&&shape["valide"].toBool()&&shape["volume_mm3"].toDouble()>0&&recipe["methode"]=="volume_solide_terminal"){
    double g=grams(shape["volume_mm3"].toDouble(),recipe["densite_g_cm3"].toDouble());entry.insert("masse_calculee_candidate_g",g);entry.insert("fabrication_candidate",recipe);partialG+=g;hasPartial=true;
   }else if(!recipe.isEmpty()&&recipe["methode"]=="tranchage"&&recipe["volume_extrude_piece_mm3"].isDouble()){
    double g=grams(recipe["volume_extrude_piece_mm3"].toDouble(),recipe["densite_g_cm3"].toDouble());entry.insert("masse_calculee_candidate_g",g);entry.insert("fabrication_candidate",recipe);partialG+=g;hasPartial=true;
   }else if(recipe["methode"]=="masse_lineique_parcours"){
    partialHarness=true;
    double g=linearGrams(recipe["longueur_parcours_mm"].toDouble(),recipe["masse_lineique_g_m"].toDouble());entry.insert("masse_calculee_candidate_g",g);entry.insert("fabrication_candidate",recipe);entry.insert("portee","Segment de câble du parcours, faisceau complet inconnu");partialG+=g;hasPartial=true;
   }else if(nominal(componentMasses[r["source"].toString()].toObject())){
    const auto document=componentMasses[r["source"].toString()].toObject();require(document["sha256_natif"]==shape["sha256"],"Source native de composant documentaire périmée");require(document["objet_source"]==r["objet_source"],"Objet de composant documentaire différent");const double g=document["valeur_g"].toDouble();require(g>0&&std::isfinite(g),"Masse de composant invalide");entry.insert("masse_documentee_g",g);entry.insert("source_massique",document);partialDocumentedG+=g;
   }else {entry.insert("masse_calculee_candidate_g",QJsonValue::Null);missing.append(r["id"]);}
   entry.insert("centre_volume_global_mm",r["centre_volume_global_mm"]);
   entry.insert("inertie_volumique_globale_mm5",r["inertie_volumique_globale_mm5"]);
   contents.append(entry);
  }
  item.insert("contenu_physique",contents);item.insert("convention_quantites_contenu","Quantités absolues pour un drone ; ne pas multiplier par la quantité de la ligne parent.");
  if(!documentaryParts.isEmpty()){require(!hasPartial,"Périmètre documentaire partiel et géométrie calculée à ventiler avant addition");for(const auto& v:contents)require(!v.toObject()["masse_documentee_g"].isDouble(),"Périmètre documentaire partiel et composant documenté à ventiler avant addition");}
  auto inclusion=item["masse_incluse_dans"].toString();double contribution=0;QString mode="inconnue";
  bool covered=false;
  for(auto parent=inclusion;!parent.isEmpty();parent=itemsById[parent].toObject()["masse_incluse_dans"].toString()){
   const auto p=itemsById[parent].toObject();if((nominal(p["donnee_massique"].toObject())&&knownQuantity(p["quantite"]))||completeCalculatedIds.contains(parent)){covered=true;break;}
  }
  const bool nominalItem=nominal(m)&&knownQuantity(item["quantite"]);
  if(covered){++included;mode="incluse";}
  else if(nominalItem){contribution=m["valeur_g"].toDouble()*item["quantite"].toDouble();require(contribution>0&&std::isfinite(contribution),"Masse nominale invalide");if(m["nature"]=="calcul"){candidateSubtotal+=contribution;++completeCalculated;}else{documentedSubtotal+=contribution;++applicable;}mode="ensemble_documente";}
  else if(hasPartial||partialDocumentedG>0){contribution=partialG+partialDocumentedG;candidateSubtotal+=partialG;documentedSubtotal+=partialDocumentedG;++partial;mode="composants_connus_partiels";
   if(!documentaryParts.isEmpty()){QSet<QString> parents;for(const auto& v:rows)parents.insert(v.toObject()["id"].toString().section('#',0,0));const QString parent=parents.size()==1?*parents.begin():"non_localise_sans_repartition_inventee";subassemblies.insert(parent,subassemblies[parent].toDouble()+partialDocumentedG);}
   for(const auto& v:contents){auto r=v.toObject();if(r["masse_documentee_g"].isDouble()){const auto key=r["occurrence"].toString();require(!allocatedGeometry.contains(key),"Composant documenté compté deux fois");allocatedGeometry.insert(key);const auto parent=key.section('#',0,0);subassemblies.insert(parent,subassemblies[parent].toDouble()+r["masse_documentee_g"].toDouble());}if(r["masse_calculee_candidate_g"].isDouble()){
   auto key=r["occurrence"].toString();require(!allocatedGeometry.contains(key),"Géométrie comptée deux fois");allocatedGeometry.insert(key);calculated.append(r);
   const auto parent=key.section('#',0,0);subassemblies.insert(parent,subassemblies[parent].toDouble()+r["masse_calculee_candidate_g"].toDouble());
   const auto recipe=r["fabrication_candidate"].toObject();const auto centre=r["centre_volume_global_mm"].toArray(),tensor=r["inertie_volumique_globale_mm5"].toArray();
   if(recipe["methode"]=="volume_solide_terminal"&&centre.size()==3&&tensor.size()==16){
    cartographe::mass::Tensor inertia{};const double density=recipe["densite_g_cm3"].toDouble();
    for(int i=0;i<3;++i)for(int j=0;j<3;++j)inertia[i][j]=tensor[i*4+j].toDouble()*density*1e-12;
    homogeneousCandidates.push_back({key.toStdString(),"",r["masse_calculee_candidate_g"].toDouble()/1000.,cartographe::mass::Vector{centre[0].toDouble()/1000.,centre[1].toDouble()/1000.,centre[2].toDouble()/1000.},inertia});
   }
  }}}
  if(mode=="ensemble_documente"){
   QSet<QString> parents;for(const auto& v:physical){auto r=v.toObject();if(r["bom_ids"].toArray().contains(id))parents.insert(r["id"].toString().section('#',0,0));}
   const QString parent=parents.size()==1?*parents.begin():"non_localise_sans_repartition_inventee";subassemblies.insert(parent,subassemblies[parent].toDouble()+contribution);
  }
  const bool calculatedComplete=!covered&&!nominalItem&&(hasPartial||partialDocumentedG>0)&&!partialHarness&&missing.isEmpty()&&completeCalculatedIds.contains(id);
  if(calculatedComplete){mode="composants_calcules_complets";++completeCalculated;--partial;item.insert("masse_unitaire_g",contribution/item["quantite"].toDouble());item.insert("masse_nature","Somme complète du contenu défini : masses documentaires et/ou matériaux/procédés candidats ; aucune mesure physique");}
  const bool complete=covered||nominalItem||calculatedComplete;
  if(!complete){unknown.append(id);auto problem=item["probleme_massique"].toObject();problem.insert("statut","À valider");problem.insert("masse_complete_inconnue",true);problem.insert("occurrences_sans_masse_individuelle",missing);if(problem["information_manquante"].toString().isEmpty())problem.insert("information_manquante",hasPartial?"Compléter les composants non chiffrés et confirmer le périmètre de la ligne ; contributions candidates séparées.":"Masse nette de la référence et de la variante retenues, avec contenu inclus et accessoires conservés.");if(!knownQuantity(item["quantite"]))problem.insert("quantite_inconnue",true);else problem.remove("quantite_inconnue");item.insert("probleme_massique",problem);}
  else item.insert("probleme_massique",QJsonValue::Null);
  item.insert("masse_complete_connue_dans_definition",complete);item.insert("contributions_documentaires_partielles",documentaryParts);
  if(m["valeur_g"].isDouble()&&!nominalItem)bounded.append(QJsonObject{{"id",id},{"donnee",m},{"comptee_dans_sous_total",false}});
  known+=contribution;const auto subsystem=item["sous_systeme"].toString();subtotals.insert(subsystem,subtotals[subsystem].toDouble()+contribution);
  item.insert("masse_partielle_documentee_g",partialDocumentedG>0?QJsonValue(partialDocumentedG):QJsonValue(QJsonValue::Null));item.insert("masse_partielle_calculee_g",hasPartial?QJsonValue(partialG):QJsonValue(QJsonValue::Null));item.insert("contribution_connue_g",contribution>0?QJsonValue(contribution):QJsonValue(QJsonValue::Null));item.insert("mode_comptage_massique",mode);items[n]=item;
  QJsonObject out{{"id",id},{"quantity",item["quantite"]},{"unit",item["unite"]},{"canonical_unit_mass_g",item["masse_unitaire_g"]},{"included_mass_in",inclusion.isEmpty()?QJsonValue(QJsonValue::Null):QJsonValue(inclusion)},{"donnee_massique",m},{"counting_mode",mode},{"known_contribution_g",contribution>0?QJsonValue(contribution):QJsonValue(QJsonValue::Null)},{"physical_content",contents},{"missing_component_masses",missing},{"complete",mode=="ensemble_documente"},{"physical_centre_of_mass_m",QJsonValue::Null},{"physical_inertia_kg_m2",QJsonValue::Null}};
  out.insert("complete",complete);out.insert("probleme_massique",item["probleme_massique"]);out.insert("contributions_documentaires_partielles",documentaryParts);
  results.append(out);coverage.append(QJsonObject{{"id",id},{"occurrences_physiques",rows.size()},{"masse_applicable",complete},{"inclusion",out["included_mass_in"]},{"detail_physique_complet",item["detail_physique_complet"].toBool(false)}});
 }
 const bool massComplete=unknown.isEmpty()&&unallocated.isEmpty()&&known>0;
 for(auto i=subtotals.begin();i!=subtotals.end();++i)if(i.value().toDouble()==0.)i.value()=QJsonValue::Null;
 for(const auto& v:manifest["occurrences"].toArray()){const auto occurrence=v.toObject();if(occurrence["parent"]==manifest["assemblage"]&&!subassemblies.contains(occurrence["source"].toString()))subassemblies.insert(occurrence["source"].toString(),QJsonValue::Null);}
 bom.insert("items",items);auto cfg=bom["configuration"].toObject();cfg.insert("masse_complete_g",massComplete?QJsonValue(known):QJsonValue(QJsonValue::Null));bom.insert("configuration",cfg);
 QJsonObject summary{{"lot","ORCH-CAO-MASSE-1"},{"configuration","prototype_cartographe"},{"statut","Implémenté"},{"qualification","À valider"},{"lot_clos",false},{"known_subtotal_g",known},{"mass_complete_g",QJsonValue::Null},{"centre_of_mass_m",QJsonValue::Null},{"inertia_kg_m2",QJsonValue::Null},{"subtotals_by_subsystem_g",subtotals},{"applicable_documented_items",applicable},{"partially_calculated_items",partial},{"included_items",included},{"unknown_or_incomplete_items",unknown},{"conditional_or_bounded_values",bounded},{"calculated_components",calculated},{"items",results},{"rules",QJsonArray{"Sous-total disponible, jamais masse complète ni borne garantie.","Matières et procédés candidats : calculs préliminaires, incertitudes non publiées inconnues.","Somme massique indépendante de la disponibilité du centrage ou des inerties.","Parentage d'achat distinct de l'inclusion massique.","Les valeurs maximales et les périmètres non confirmés sont exclus du sous-total nominal.","Les masses manquantes restent null ; aucune masse de kit complet ou scénario 6 kg ajouté."}}};
 summary.insert("subtotals_by_subassembly_g",subassemblies);
 summary.insert("subtotals_scope","Contributions disponibles seulement ; null si aucune contribution connue. Tous les sous-ensembles restent incomplets tant que leurs éléments manquants ne sont pas résolus.");
 summary.insert("documented_applicable_subtotal_g",documentedSubtotal);summary.insert("candidate_calculated_subtotal_g",candidateSubtotal);
 const auto scenario=definitions["scenario_propulsion"].toObject();
 if(!scenario.isEmpty()){
  const double esc=scenario["contribution_esc_cartes_g"].toDouble(),prop=scenario["contribution_helices_g"].toDouble(),extra=scenario["contribution_supplementaire_si_hypotheses_g"].toDouble();
  require(esc>0&&prop>0&&std::isfinite(extra)&&std::abs(esc+prop-extra)<1e-9&&!scenario["comptabilise_dans_sous_total"].toBool(),"Scénario propulsion incohérent");
  summary.insert("scenario_exploratoire_propulsion",QJsonObject{{"sous_total_avec_hypotheses_g",known+extra},{"ajout_conditionnel_g",extra},
   {"contribution_esc_cartes_g",esc},{"contribution_helices_g",prop},{"conditions",scenario["conditions"]},
   {"masse_complete_g",QJsonValue::Null},{"borne_garantie",false},{"comptabilise_dans_sous_total",false}});
 }
 summary.insert("completely_calculated_items",completeCalculated);
 summary.insert("unallocated_physical_occurrences",unallocated);
 summary.insert("mass_complete_g",massComplete?QJsonValue(known):QJsonValue(QJsonValue::Null));
 if(!homogeneousCandidates.empty()){
  auto properties=cartographe::mass::aggregate(homogeneousCandidates);QJsonArray tensor;for(const auto& row:*properties.inertia)tensor.append(QJsonArray{row[0],row[1],row[2]});
  summary.insert("homogeneous_candidate_parts_only",QJsonObject{{"occurrences",int(homogeneousCandidates.size())},{"mass_kg",properties.knownMass},{"centre_m",QJsonArray{(*properties.centre)[0],(*properties.centre)[1],(*properties.centre)[2]}},{"inertia_kg_m2",tensor},{"limite","Sous-ensemble calculé de pièces fabriquées supposées homogènes ; ce n'est ni le drone ni l'ensemble des masses connues."}});
 }
 if(publish){write(bomPath,bom);inputs.insert(cad+"nomenclature_prototype.json",sha(bomPath));summary.insert("sources_sha256",inputs);summary.insert("schema_version",2);summary.insert("test_id","T-CARTO-MASSE-BOM-01");summary.insert("finalisation_correcte",true);write(root+"/simulation/gazebo/models/cartographe/geometry/mass_ledger.json",summary);write(root+"/"+ver+"controle_masse_prototype.json",summary);write(root+"/"+ver+"couverture_massique_prototype.json",{{"lot","ORCH-CAO-MASSE-1"},{"sources_sha256",inputs},{"postes",coverage},{"couverture_complete",false}});}
 if(publish){
  QJsonArray inventory,absent,inverse;
  for(const auto& value:items){const auto row=value.toObject();const auto id=row["id"].toString();QJsonArray occurrences;QSet<QString> refs;
   for(const auto& v:physical){const auto p=v.toObject();if(p["bom_ids"].toArray().contains(id)||p["proprietaire_masse_bom"]==id){occurrences.append(p["id"]);refs.insert(shapeKey(p["source"].toString(),p["objet_source"].toString()));}}
   QJsonArray references;auto ordered=refs.values();ordered.sort();for(const auto& ref:ordered)references.append(ref);
   const bool embarked=row["perimetre"]=="embarque"&&!excludedQuantity(row["quantite"]);if(embarked&&occurrences.isEmpty())absent.append(id);
   inventory.append(QJsonObject{{"id",id},{"quantite_bom",row["quantite"]},{"unite",row["unite"]},{"perimetre",row["perimetre"]},{"references",references},{"occurrences",occurrences},{"contenu_physique_detaille",row["contenu_physique"]},{"completude_demontree",false},{"etat",!embarked?"Hors aéronef actif":occurrences.isEmpty()?"Absent ou inclus sans détail géométrique identifié":"Rattachement identifié ; détail et interfaces À valider"}});
  }
  for(const auto& v:physical){const auto p=v.toObject();inverse.append(QJsonObject{{"occurrence",p["id"]},{"source",p["source"]},{"objet_source",p["objet_source"]},{"bom_ids",p["bom_ids"]},{"proprietaire_masse_bom",p["proprietaire_masse_bom"]}});}
  write(root+"/"+ver+"couverture_bom_cao_prototype.json",{{"lot","ORCH-CAO-MASSE-1"},{"bom_sha256",sha(bomPath)},{"sources_sha256",inputs},{"postes",inventory},{"inverse_cao_bom",inverse},{"postes_embarques_sans_rattachement_detaille",absent},{"occurrences_non_attribuees",unallocated},{"couverture_complete",false},{"finalisation_correcte",true},{"limites",QJsonArray{"Un rattachement à un ensemble ne prouve pas la présence de tous ses composants.","Les jeux, faisceaux et consommables non identifiés restent ouverts ; aucun comptage par étiquette ne ferme la définition.","Quantités des contenus physiques absolues pour un drone ; ne pas multiplier par le parent."}}});
 }
 std::cout<<QJsonDocument(QJsonObject{{"known_subtotal_g",known},{"applicable_documented_items",applicable},{"partially_calculated_items",partial},{"included_items",included},{"unknown_items",unknown.size()},{"unallocated_physical_occurrences",unallocated.size()},{"calculated_occurrences",calculated.size()},{"mass_complete_g",summary["mass_complete_g"]},{"published",publish}}).toJson().toStdString();
}
void integrationTests(){
 QTemporaryDir tmp;require(tmp.isValid(),"Dossier de test indisponible");const auto root=tmp.path();
 const QString cad="hardware/mecanique/cartographe/",ver=cad+"verification/",native="pieces/fabriquees/A.FCStd";
 for(const auto& path:QStringList{cad+native,ver+"orch_integrate_cao.py",ver+"read_brep_prototype.py","simulation/mass/BomMass.cpp","simulation/mass/MassProperties.hpp"}){
  QDir().mkpath(QFileInfo(root+"/"+path).absolutePath());QFile f(root+"/"+path);require(f.open(QIODevice::WriteOnly)&&f.write("fixture")>0,"Fixture impossible");
 }
 const auto hash=sha(root+"/"+cad+native);
 QJsonObject manifest{{"prototype_cartographe",QJsonObject{{"references",QJsonArray{QJsonObject{{"fichier",native}}}},{"sources_preservees",QJsonObject{}}}}};
 write(root+"/"+cad+"manifest.json",manifest);
 QJsonObject mass{{"valeur_g",2.},{"qualificatif","nominale"},{"applicable",true}};
 QJsonObject item{{"id","PIECE"},{"perimetre","embarque"},{"quantite",1},{"donnee_massique",mass}};
 QJsonObject bom{{"items",QJsonArray{item}},{"orch_cao_masse_1",QJsonObject{{"preuves_sources_sha256",QJsonObject{{ver+"read_brep_prototype.py",sha(root+"/"+ver+"read_brep_prototype.py")}}}}}};
 QJsonObject reference{{"fichier",native},{"objet","A"},{"sha256",hash},{"volume_mm3",1000.},{"valide",true}};
 QJsonObject occurrence{{"id","sa#piece"},{"source",native},{"objet_source","A"},{"proprietaire_masse_bom","PIECE"},{"bom_ids",QJsonArray{"PIECE"}}};
 QJsonObject geo{{"finalisation_correcte",true},{"natifs_sha256",QJsonObject{{native,hash}}},{"script_sha256",sha(root+"/"+ver+"orch_integrate_cao.py")},{"lecteur_sha256",sha(root+"/"+ver+"read_brep_prototype.py")},{"references",QJsonArray{reference}},{"occurrences_physiques",QJsonArray{occurrence}}};
 auto execute=[&](const QJsonObject& geometry,const QJsonObject& definition){write(root+"/"+ver+"orch_cao_masse_geometrie.json",geometry);write(root+"/"+cad+"nomenclature_prototype.json",definition);run(root,true);return read(root+"/simulation/gazebo/models/cartographe/geometry/mass_ledger.json");};
 auto result=execute(geo,bom);require(result["mass_complete_g"].toDouble()==2.,"Masse complète documentaire perdue sans inertie");
 auto scenarioBom=bom;auto scenarioDefs=scenarioBom["orch_cao_masse_1"].toObject();
 scenarioDefs.insert("scenario_propulsion",QJsonObject{{"contribution_esc_cartes_g",2.},{"contribution_helices_g",3.},{"contribution_supplementaire_si_hypotheses_g",5.},{"comptabilise_dans_sous_total",false}});scenarioBom.insert("orch_cao_masse_1",scenarioDefs);
 auto scenarioResult=execute(geo,scenarioBom);require(scenarioResult["known_subtotal_g"].toDouble()==2.&&scenarioResult["scenario_exploratoire_propulsion"].toObject()["sous_total_avec_hypotheses_g"].toDouble()==7.,"Scénario conditionnel ajouté au sous-total canonique");
 auto wrongScenario=scenarioDefs["scenario_propulsion"].toObject();wrongScenario.insert("contribution_supplementaire_si_hypotheses_g",6.);scenarioDefs.insert("scenario_propulsion",wrongScenario);scenarioBom.insert("orch_cao_masse_1",scenarioDefs);
 bool invalidScenarioAccepted=false;try{execute(geo,scenarioBom);invalidScenarioAccepted=true;}catch(const std::runtime_error&){}require(!invalidScenarioAccepted,"Scénario conditionnel incohérent accepté");
 auto child=item;child.insert("id","ACCESS");child.insert("masse_incluse_dans","PIECE");child.insert("donnee_massique",QJsonObject{});auto bundle=bom;bundle.insert("items",QJsonArray{item,child});auto composite=occurrence;composite.insert("proprietaire_masse_bom","");composite.insert("bom_ids",QJsonArray{"PIECE","ACCESS"});auto grouped=geo;grouped.insert("occurrences_physiques",QJsonArray{composite});result=execute(grouped,bundle);require(result["mass_complete_g"].toDouble()==2.&&result["unallocated_physical_occurrences"].toArray().isEmpty(),"Propriétaire d'ensemble explicite non résolu");
 auto reject=[&](QJsonObject geometry){bool failed=false;try{execute(geometry,bom);}catch(const std::runtime_error&){failed=true;}require(failed,"Cache géométrique incohérent accepté");};
 auto bad=geo;bad.insert("natifs_sha256",QJsonObject{});reject(bad);bad=geo;bad.insert("script_sha256","périmé");reject(bad);bad=geo;bad.insert("lecteur_sha256","périmé");reject(bad);
 bad=geo;bad.insert("references",QJsonArray{reference,reference});reject(bad);
 auto orphan=occurrence;orphan.insert("proprietaire_masse_bom","INEXISTANT");bad=geo;bad.insert("occurrences_physiques",QJsonArray{occurrence, QJsonObject{{"id","orphelin"},{"source",native},{"objet_source","A"},{"proprietaire_masse_bom","INEXISTANT"}}});
 result=execute(bad,bom);require(result["mass_complete_g"].isNull()&&result["unallocated_physical_occurrences"].toArray().size()==1,"Occurrence sans BOM omise");
 auto refB=reference;refB.insert("objet","B");refB.insert("volume_mm3",2000.);auto occB=occurrence;occB.insert("id","sa#piece2");occB.insert("objet_source","B");bad=geo;bad.insert("references",QJsonArray{reference,refB});bad.insert("occurrences_physiques",QJsonArray{occurrence,occB});
 item.insert("donnee_massique",QJsonObject{});auto calculated=bom;calculated.insert("items",QJsonArray{item});auto defs=calculated["orch_cao_masse_1"].toObject();defs.insert("fabrications_candidates",QJsonObject{{native,QJsonObject{{"methode","volume_solide_terminal"},{"densite_g_cm3",1.},{"sha256_natif",hash}}}});calculated.insert("orch_cao_masse_1",defs);
 result=execute(bad,calculated);require(std::abs(result["known_subtotal_g"].toDouble()-3.)<1e-12,"Objets du même fichier écrasés");
 // Deux solides d'un même fichier OEM peuvent avoir des densités différentes.
 auto specific=calculated;auto specificDefs=defs;specificDefs.remove("fabrications_candidates");
 QJsonObject estimateA{{"fichier",native},{"objet_source","A"},{"bom_id","PIECE"},{"methode","volume_solide_terminal"},{"densite_g_cm3",1.5},{"volume_reference_mm3",1000.},{"sha256_natif",hash}};
 QJsonObject estimateB{{"fichier",native},{"objet_source","B"},{"bom_id","PIECE"},{"methode","volume_solide_terminal"},{"densite_g_cm3",2.},{"volume_reference_mm3",2000.},{"sha256_natif",hash}};
 specificDefs.insert("estimations_geometrie_oem",QJsonObject{{"sa#piece",estimateA},{"sa#piece2",estimateB}});specific.insert("orch_cao_masse_1",specificDefs);
 result=execute(bad,specific);require(std::abs(result["known_subtotal_g"].toDouble()-5.5)<1e-12,"Densités OEM par occurrence incorrectes");
 auto wrongEstimate=estimateB;wrongEstimate.insert("bom_id","AUTRE");specificDefs.insert("estimations_geometrie_oem",QJsonObject{{"sa#piece",estimateA},{"sa#piece2",wrongEstimate}});specific.insert("orch_cao_masse_1",specificDefs);
 bool wronglyAccepted=false;try{execute(bad,specific);wronglyAccepted=true;}catch(const std::runtime_error&){}require(!wronglyAccepted,"Estimation attribuée à un autre propriétaire acceptée");
 auto full=calculated;auto defined=item;defined.insert("detail_physique_complet",true);full.insert("items",QJsonArray{defined});result=execute(bad,full);require(result["mass_complete_g"].toDouble()==3.,"Contenu intégral calculable non fermé");
 auto thermal=defined;thermal.insert("id","THERMAL");thermal.insert("masse_incluse_dans","PIECE");thermal.insert("donnee_massique",mass);full.insert("items",QJsonArray{thermal,defined});result=execute(bad,full);require(result["known_subtotal_g"].toDouble()==3.&&result["included_items"].toInt()==1,"Inclusion d'un parent calculé dépend de l'ordre");
 auto stale=read(root+"/"+cad+"nomenclature_prototype.json");auto staleItem=stale["items"].toArray()[1].toObject();staleItem.insert("detail_physique_complet",false);staleItem.insert("probleme_massique",QJsonObject{{"quantite_inconnue",true}});stale.insert("items",QJsonArray{staleItem});execute(bad,stale);const auto reset=read(root+"/"+cad+"nomenclature_prototype.json")["items"].toArray()[0].toObject();require(reset["masse_unitaire_g"].isNull()&&!reset["probleme_massique"].toObject().contains("quantite_inconnue"),"Masse ou problème périmé conservé");
 auto partialDefinition=bom;auto unknownItem=item;unknownItem.insert("detail_physique_complet",true);partialDefinition.insert("items",QJsonArray{unknownItem});auto partialDefs=partialDefinition["orch_cao_masse_1"].toObject();const QJsonObject body{{"id","CORPS"},{"bom_id","PIECE"},{"quantite_absolue_drone",3},{"donnee_massique",mass}};partialDefs.insert("contributions_documentaires_partielles",QJsonArray{body});partialDefinition.insert("orch_cao_masse_1",partialDefs);result=execute(geo,partialDefinition);require(result["known_subtotal_g"].toDouble()==6.&&result["mass_complete_g"].isNull(),"Corps partiel assimilé à ensemble complet");require(result["subtotals_by_subassembly_g"].toObject()["sa"].toDouble()==6.,"Contribution documentaire absente du sous-total SA");
 auto rejectsDefinition=[&](QJsonObject definition){bool failed=false;try{execute(geo,definition);}catch(const std::runtime_error&){failed=true;}require(failed,"Définition massique avec doublon acceptée");};
 partialDefs.insert("contributions_documentaires_partielles",QJsonArray{body,body});auto duplicated=partialDefinition;duplicated.insert("orch_cao_masse_1",partialDefs);rejectsDefinition(duplicated);
 auto docMass=mass;docMass.insert("sha256_natif",hash);docMass.insert("objet_source","A");partialDefs.insert("contributions_documentaires_partielles",QJsonArray{body});partialDefs.insert("recettes_composants_documentaires",QJsonObject{{native,docMass}});duplicated.insert("orch_cao_masse_1",partialDefs);rejectsDefinition(duplicated);
 partialDefs.insert("contributions_documentaires_partielles",QJsonArray{});auto components=partialDefinition;components.insert("orch_cao_masse_1",partialDefs);result=execute(geo,components);require(result["mass_complete_g"].toDouble()==2.&&result["subtotals_by_subassembly_g"].toObject()["sa"].toDouble()==2.,"Composant documentaire mal agrégé");
}
}
int main(int argc,char** argv){QCoreApplication app(argc,argv);try{auto a=app.arguments();if(a.contains("--self-test")){selfTest();return 0;}require(a.size()>1,"Usage: cartographe-bom-mass WORKSPACE [--publish]");run(QDir(a[1]).absolutePath(),a.contains("--publish"));return 0;}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
