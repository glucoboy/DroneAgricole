// Calculs préliminaires du lot ORCH-CAO-MASSE-1. Aucune entrée/sortie BOM partagée.
// Usage : orch_reprise_masses_fournitures < donnees.tsv > resultats.json
// TSV : identifiant methode quantite valeur [densite] ; methodes : g, mg, mm3, mm.
// mm3 : valeur=volume mm3, densite=g/cm3 ; mm : valeur=longueur mm, densite=g/m.
#include <cmath>
#include <iomanip>
#include <iostream>
#include <map>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

struct Ligne { std::string id, methode; double quantite{}, valeur{}, coefficient{1.0}; std::string parent; };
double unitaire(const Ligne& x) {
    if (!std::isfinite(x.quantite) || x.quantite<=0 || !std::isfinite(x.valeur) || x.valeur<=0)
        throw std::runtime_error("Quantite ou valeur inconnue/non positive : "+x.id);
    if(x.methode=="g")return x.valeur;
    if(x.methode=="mg")return x.valeur/1000.;
    if((x.methode=="mm3"||x.methode=="mm")&&std::isfinite(x.coefficient)&&x.coefficient>0)
        return x.valeur*x.coefficient/1000.;
    throw std::runtime_error("Methode ou coefficient inconnu : "+x.id);
}
void require(bool value,const char* message){if(!value)throw std::runtime_error(message);}
int main(){try{
    require(std::abs(unitaire({"test","mm3",1,1000,1.330,""})-1.330)<1e-12,"Conversion mm3 incorrecte");
    require(std::abs(unitaire({"test","mm",1,1000,34,""})-34)<1e-12,"Conversion longueur incorrecte");
    require(std::abs(unitaire({"test","mg",1,506,1,""})-.506)<1e-12,"Conversion mg incorrecte");
    bool rejete=false;try{unitaire({"inconnue","g",1,0,1,""});}catch(...){rejete=true;}
    require(rejete,"Inconnue assimilee a zero");
    // Vérification indépendante des volumes CAO Sorbothane contre les plans en pouces.
    const double pi=std::acos(-1.0),inch=25.4;
    const auto cyl=[&](double d,double h){return pi/4*d*d*h;};
    const double v0030=cyl(.50*inch,.19*inch)+cyl(.22*inch,(.39-.19)*inch)-cyl(.12*inch,.39*inch);
    const double v0010=cyl(.50*inch,.19*inch)-cyl(.22*inch,.19*inch);
    require(std::abs(v0030-663.6477570854576)<1e-8,"Plan Sorbothane0510030 different du solide");
    require(std::abs(v0010-492.986651295504)<1e-8,"Plan Sorbothane0510010 different du solide");
    std::vector<Ligne> lignes;std::map<std::string,double> partiels;std::string s;
    while(std::getline(std::cin,s)){
        if(s.empty()||s[0]=='#')continue;
        Ligne l;std::istringstream in(s);
        require(bool(in>>l.id>>l.methode>>l.quantite>>l.valeur),"TSV incomplet");
        if(l.methode=="mm"||l.methode=="mm3")require(bool(in>>l.coefficient),"Coefficient absent");
        in>>l.parent;
        for(const auto& prior:lignes)require(l.id!=prior.id,"ID duplique");
        (void)unitaire(l);lignes.push_back(l);
        if(!l.parent.empty())partiels[l.parent]+=unitaire(l)*l.quantite;
    }
    std::cout<<std::setprecision(17)<<"{\n  \"tests_conversions_et_inconnues\":true,\n  \"volumes_plans_sorbothane_mm3\":{\"0510030\":"<<v0030<<",\"0510010\":"<<v0010<<"},\n  \"resultats\":[\n";
    for(std::size_t i=0;i<lignes.size();++i){const auto& l=lignes[i];const auto g=unitaire(l);
        std::cout<<"    {\"id\":\""<<l.id<<"\",\"methode\":\""<<l.methode<<"\",\"quantite\":"<<l.quantite<<",\"valeur_entree\":"<<l.valeur<<",\"coefficient\":"<<l.coefficient<<",\"masse_unitaire_g\":"<<g<<",\"contribution_g\":"<<g*l.quantite<<"}"<<(i+1<lignes.size()?",":"")<<"\n";
    }
    std::cout<<"  ],\n  \"sous_totaux_groupes_g\":{\n";
    std::size_t n=0;for(const auto& p:partiels)std::cout<<"    \""<<p.first<<"\":"<<p.second<<(++n<partiels.size()?",":"")<<"\n";
    std::cout<<"  }\n}\n";
    return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
