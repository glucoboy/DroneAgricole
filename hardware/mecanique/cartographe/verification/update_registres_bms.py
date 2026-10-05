"""Registres durables tirés des liens natifs courants, sans refaire la géométrie."""
from pathlib import Path
from collections import Counter
import json,hashlib
import FreeCAD as A
ROOT=Path(__file__).resolve().parents[4];MEC=ROOT/'hardware/mecanique/cartographe';VER=MEC/'verification'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def rel(p):return str(Path(p).relative_to(ROOT)).replace('\\','/')
def main():
 top=A.openDocument(str(MEC/'assemblages/Integration_Stack_Revue_20261003.FCStd'))
 for name in ['SA02_Contacts20Ah','SA02_Cassette20Ah_Coulissante']:
  p=MEC/'sous_assemblages'/(name+'.FCStd')
  if not any(d.FileName and Path(d.FileName)==p for d in A.listDocuments().values()):A.openDocument(str(p))
 for d in A.listDocuments().values():d.recompute()
 parents=['SA02A_Dock20Ah','SA07_Distribution_Systeme_Candidat','SA08_Faisceau_Systeme_Candidat']
 docs=[d for d in A.listDocuments().values() if Path(d.FileName).stem in parents]
 assert len(docs)==3,'Le faisceauSA08 doit être lié au top courant'
 occ=[];registries=[];refs={}
 for d in A.listDocuments().values():
  if not d.FileName or not Path(d.FileName).is_relative_to(MEC):continue
  for o in d.Objects:
   if o.TypeId!='App::Link' or not o.LinkedObject:continue
   src=o.LinkedObject.Document;p=Path(src.FileName)
   if not p.is_relative_to(MEC):continue
   row=dict(assemblage=Path(d.FileName).stem,fichier_assemblage=str(Path(d.FileName).relative_to(MEC)).replace('\\','/'),occurrence=o.Name,reference=p.stem,source_fichier=str(p.relative_to(MEC)).replace('\\','/'),source_objet=o.LinkedObject.Name,placement_matrice=list(o.LinkPlacement.toMatrix().A),LinkTransform=o.LinkTransform,courant_catalogue=True,statut='À valider')
   registries.append(row)
   refs[p.stem]=dict(reference=p.stem,fichier=str(p.relative_to(MEC)).replace('\\','/'),type=o.LinkedObject.TypeId,realisation_CAO='Implémenté',statut='À valider',sha256=sha(p))
   if d in docs:occ.append(dict(assemblage=row['fichier_assemblage'],occurrence=o.Name,reference=p.stem,fichier=rel(p),sha256=sha(p)))
 counts=dict(Counter(r['reference'] for r in occ));write(VER/'nomenclature_etage_batterie.json',dict(date='2026-10-05',scope='Dock+BMS+SA07+SA08, liens directs installés dans intégration locale ; pas commandes ni bilan physique',statut='À valider',quantites=counts,occurrences=occ,finalisation_correcte=True))
 b=read(VER/'bom_dock20Ah_20261002.json');b.update(date_utc='2026-10-05',objet='CassetteBMS JBD/TE etétagefixe+faisceauSA08 candidats',sources_sha256={r['fichier']:r['sha256'] for r in occ})
 b['assemblage_inventorie'].update(sha256=sha(MEC/'sous_assemblages/SA02A_Dock20Ah.FCStd'),occurrences=counts,perimetre='SA02A+SA07+SA08 ; liensdirects nomenclature_etage_batterie.json')
 seen=set()
 for cat in ['pieces_fabriquees','visserie_modelee','composants_commerce']:
  for row in b[cat]:
   ref=Path(row.get('fichier','')).stem or row['reference'];seen.add(ref)
   row['quantite_installee']=counts.get(ref,0);row['configuration_courante']='active' if counts.get(ref) else 'historique noninstallée'
   p=ROOT/row.get('fichier','')
   if p.is_file():row['sha256']=sha(p)
 for ref,n in counts.items():
  if ref in seen:continue
  row=next(r for r in occ if r['reference']==ref)
  cat='pieces_fabriquees' if ref.startswith('P') else 'composants_commerce'
  b[cat].append(dict(reference=ref,designation=ref,quantite_installee=n,fichier=row['fichier'],sha256=row['sha256'],statut_CAO='Implémenté',statut_physique='À valider',configuration_courante='active',limite='Référencecourante ; lots/terminaisons/maintien/qualifications etquantitéachatàconfirmer'))
 b['elements_a_synchroniser']=['RéceptionJBD100A_A01, adaptation6S, niveauUART/NTC','CavitésTE#20, sertissageAWG8 etretenue','Ports/rayons/priseUSB/fixations/dissipateur/masse/thermique de lot','DécodeurdiagnosticC++17, arbitragebatteriePX4Planifiés'];write(VER/'bom_dock20Ah_20261002.json',b)
 f=read(VER/'faisceau_dock20Ah_20261002.json');f.update(date_utc='2026-10-05',objet='Pack6S+BMSmobile commun→TE→JETI→PM08 ; diagnosticUARTisolé',sources_sha256=b['sources_sha256'])
 f['netlist']=[dict(net='BAT_PLUS_BRUT',origine='Tattu.+',destination='TE39',connexion='AWG8 continu ; BMS positif parBC22=B6 viafaisceaucellulesinterne, pasdepiquageB+ bulk'),dict(net='BAT_MOINS_BRUT',origine='Tattu.-',destination='JBD.B-',connexion='AWG8 usine court versentréeBMS'),dict(net='P_MINUS_PROTEGE',origine='JBD.C- portcommun A01 (P- logique)',destination='TE40 puisJETI.IN-',connexion='LiaisonrapportéeAWG8, aucuneconnexionretouravalàB- brut'),dict(net='BAT_PLUS_BRUT',origine='TE39 fixe',destination='JETI.IN+'),dict(net='BUS_MOINS_AVAL',origine='JETI.OUT-',destination='PM08 puisPDB etavionique'),dict(net='BUS_PLUS_AVAL',origine='JETI.OUT+',destination='PM08 puisPDB etavionique'),dict(net='UART_ISOLE',origine='JBD.TX/RX/B- brut',destination='TE3signaux puisTTLcôtéisoléWaveshare15817',connexion='VDDJBD/5VTTLNC, USBJetsonaval ; aucunevoieàGNDavionique'),dict(net='PRESENCE_PASSIVE',origine='TE2contacts postmate',destination='bouclemobile, NCcôtéfixe',connexion='indépendanteB- brut, pasinterlock')]
 f['positions_TE']['utilisees']=[39,40];f['positions_TE']['affectation']='39=B+ continu ;40=P−protégé. 5contacts#20 candidats, cavitésnumérotées null'
 f['positions_TE']['contacts_signaux_1_38']='Cinq contacts #20 candidats : S_GND, S_TX, S_RX, S_PRESENT_A/B ; 1..32 logements #20, numéros de cavités nonconfirmés (null). 33..38 autrespuissancesinutilisées ; boucleprésencefixeNC, aucuninterlock.'
 f['positions_TE']['signaux_candidats']=[dict(logical_id=k,cavity_number=None) for k in ['S_GND','S_TX','S_RX','S_PRESENT_A','S_PRESENT_B']]
 for key in ['39_centre_monde_mm','40_centre_monde_mm']:f['positions_TE'][key][0]=-170.2548
 dock=next(d for d in docs if Path(d.FileName).stem=='SA02A_Dock20Ah');route_rows=[]
 for o in dock.Objects:
  if o.TypeId=='App::Link' and o.Name.startswith(('EQ_LeadPack','EQ_BMS_','EQ_CordonFixe','EQ_BoucleEquilibrage')):
   src=o.LinkedObject.Document;sw=src.getObject('Cordon')
   if not sw:continue
   wire=sw.Spine[0].Shape
   route_rows.append(dict(reference=src.Name,fichier=rel(src.FileName),longueur_chemin_mm=wire.Length,diametre_etude_mm=5 if '8AWG' in o.Name or 'PMoins' in o.Name else None,rayon_fabrication_valide=False,mobile=getattr(o,'Mobile','non')=='oui',statut='À valider'))
 f['routes_mobiles']=[r for r in route_rows if r['mobile']];f['segment_fixe_TE_JETI']['routes']=[r for r in route_rows if not r['mobile']]
 f['terminaisons']['dimensions_faisceaux']='Longueurscourantes dansroutes_mobiles etsegment_fixe_TE_JETI ; pascoupesfabrication, anciens89.7/90.56/354mmhistoriques.'
 f['retenues']['equilibrage']='InterneP43, P51/P52 retirés ; adaptation6SJST7→faisceau22Sàvalider'
 f['retenues']['BMS']='AppuiP58 1mm ; maintienpositif/dissipation/fixationsÀvalider'
 f['charge_hors_drone'].update(interface='AdaptateurTE versB+ etP−portcommun protégéeparJBD, chargeur6SNMCcompatible',limite='NejamaischargerparB−brut, priseUART ouJETI.OUT ; adaptateur/protectionPlanifiés, cellulesJSTinternes cassette')
 f['limites_courant']['BMS_catalogue_A']=100;f['limites_courant']['courant_systeme_qualifie_A']=None
 f['contraintes_implantation']=['BMSPCBmax130.5×65.5×12mm, prises/dissipation nonincluses','BMS au-dessus du pack Z107..119 ; coffret supérieur170×76 et protection courte cosses','Plateau+25mm, colonnes95mm ; TE rapproché74mm, recul total52mm','Surplus du positif usine150mm non affecté ; coupe/terminaisons/rayons À valider','Ports/terminaisons/rayons SA08candidats, aucunequalificationmatérielle']
 f['cible_BMS_cassette'].update(statut='Implémenté enCAO/schéma, physiqueÀvalider',reference='JBD-SP22S003 Li-ion A01 100A',dimensions_PCB_max_mm=[130.5,65.5,12],dimensions_installees_mm=None,CAO_actuelle='BMSmobileP43+P58 ; TEconservé5signaux ; SA07isolation+SA08 actuel',charge='PortcommunB+/P−protégé',communication='UART9600 8N1 isolédonnéesetDC/DC, VDD/5VNC ; décodeurPlanifié')
 write(VER/'faisceau_dock20Ah_20261002.json',f)
 m=read(MEC/'manifest.json');active={r['fichier_assemblage'] for r in registries}
 m['occurrences']=[r for r in m['occurrences'] if str(r.get('fichier_assemblage','')).replace('\\','/') not in active]+registries
 oldrefs={r.get('reference') or r.get('nom') or Path(r.get('fichier','')).stem or 'heritage_'+str(i):r for i,r in enumerate(m['references'])}
 for name,row in refs.items():oldrefs[name]=dict(oldrefs.get(name,{}),**row)
 m['references']=list(oldrefs.values());m['date_mise_a_jour']='2026-10-05'
 for row in m['assemblages']:
  if row.get('reference')=='Integration_Stack_Revue_20261003':row.update(role='integration_locale_avec_faisceau_SA08',verification='verification/controle_bms_cassette.json',sha256=sha(top.FileName))
 control=read(VER/'controle_bms_cassette.json')
 e=m['configuration_dock20Ah']['evolution_courante'];e.update(date='2026-10-05',verification='verification/controle_bms_cassette.json',TE_recul_mm=52,dimensions_batterie_et_energie_mm=control['dimensions_batterie_et_energie_mm'],DOC_MEC='§4.1.3.3',DOC_VAL='§12.1.9',limites=control['limites'],assemblage_final='assemblages/Integration_Stack_Revue_20261003.FCStd',faisceau='sous_assemblages/SA08_Faisceau_Systeme_Candidat.FCStd',implantation_BMS='Au-dessus du pack',rehausse_plateau_mm=25,colonne_longueur_mm=95,comparaison_compacite='verification/implantation_bms_dessus.json')
 e['rendu']='verification/rendu_bms_cassette.json';e['verification_registres']='verification/controle_registres_bms.json';e['verification_faisceau']='verification/controle_faisceau_natif_bms.json'
 m['configuration_dock20Ah']['cible_BMS_cassette'].update(statut='Implémenté enCAO/schéma, physiqueÀvalider',reference_BMS='JBD-SP22S003 Li-ion A01 100A',implantation_candidate='PCB au-dessus du pack Z107..119, coffret supérieur170×76, appuiP58, plateau+25 et TE rapproché74mm',mise_a_jour_CAO=True,connecteur_selectionne_CAO='TE1648156-1/1648151-1+5signaux#20candidats',interface_isolee='Waveshare15817, dimensionsinstalléesréservées90×80×26')
 cat=m['catalogue_courant_20261004'];cat.update(faisceau_recale_sur_stack=True,qualification_physique=False)
 for row in cat['selection']:
  p=MEC/row.get('fichier','')
  if p.is_file():row['sha256']=sha(p)
  if row['reference']=='Integration_Stack_Revue_20261003':row['role']='integration_locale_avec_faisceau_SA08';row['verification']='verification/controle_bms_cassette.json'
  if row['reference']=='SA08_Faisceau_Systeme_Candidat':row['role']='faisceau_courant_recote_candidat'
 write(MEC/'manifest.json',m)
 cfg=read(MEC/'configuration_cible_20261003.json');cfg['configuration']['limite_stack_revue']='BMSmobile/TE5signaux, énergieinférieure etSA08recoté liés àintégrationlocale ; ports/fixations/masse/thermiqueÀvalider, GNSSnonimplanté';cfg['configuration']['tri_sous_assemblages']='Implémenté ; SA08recoté liéau top, GNSSsurplateauxPlanifié';cfg['BMS_cassette']={'reference':'JBD-SP22S003 Li-ion A01 100A','connecteur':'TE1648156-1/1648151-1','statut':'CAO/schémaImplémentés, physiqueÀvalider','diagnostic':'UARTisolé, décodeurPlanifié'};write(MEC/'configuration_cible_20261003.json',cfg)
 # Dépendancesnatives petites ajoutéesexplicitement ; sourcesOEM/exportsrestentexclus.
 p=ROOT/'.gitignore';t=p.read_text(encoding='utf-8');extra=[rel(MEC/r['fichier']) for r in refs.values() if (MEC/r['fichier']).stat().st_size<1000000]
 for filename in dict.fromkeys(extra):
  if '!/'+filename not in t:t+='\n!/'+filename
 p.write_text(t.rstrip()+'\n',encoding='utf-8')
 readme=MEC/'README.md';t=readme.read_text(encoding='utf-8');t=t.replace('bloc capteurs et distribution. GNSS et faisceau restent des sous-assemblages\nséparés','bloc capteurs, distribution et faisceau SA08 recoté. Le GNSS reste un sous-assemblage\nséparé')
 if 'update_bms_cassette.py' not in t:t+='\nPour faire évoluer la configuration BMS en place, exécuter avec Python FreeCAD\n`verification/update_bms_cassette.py`, puis la recette SA08 courante,\n`verification/verify_bms_cassette.py` et `verification/update_registres_bms.py`.\nLes anciennes recettes sans BMS refusent cette configuration ; retours par Git.\nLe BMS et les contacts de signal restent des enveloppes candidates ;\nutiliser le manifeste et DOC-ELEC§6.2 pour les limites et le contrat UART.\n'
 readme.write_text(t,encoding='utf-8')
 print(json.dumps(dict(occurrences=len(occ),references=len(counts),placements_synchronises=len(registries))))
if __name__=='__main__':main()
