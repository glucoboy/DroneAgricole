"""Consolidation en place des contrats, de la nomenclature et des docs vivants."""
from pathlib import Path
from etage_batterie_helpers import require_legacy_layout
require_legacy_layout('update_registres_etage_batterie.py')
import json,hashlib,re,zipfile,sys,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[4];MEC=ROOT/'hardware/mecanique/cartographe';VER=MEC/'verification'
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
control=read(VER/'controle_etage_batterie.json');assert control['finalisation_correcte'] and not control['erreurs_recalcul']
mob=read(VER/'raccordement_direct_batterie.json');fixed=read(VER/'faisceau_etage_batterie.json');dist=read(VER/'distribution_etage_batterie.json')
refs={};occurrences=[]
for filename in ['sous_assemblages/SA02A_Dock20Ah.FCStd','sous_assemblages/SA07_Distribution_Systeme_Candidat.FCStd']:
 with zipfile.ZipFile(MEC/filename) as z:xml=ET.fromstring(z.read('Document.xml'))
 types={o.attrib['name']:o.attrib.get('type') for o in xml.find('Objects') if 'name' in o.attrib}
 for obj in xml.find('ObjectData'):
  if types.get(obj.attrib['name'])!='App::Link':continue
  prop=next(p for p in obj.iter('Property') if p.attrib.get('name')=='LinkedObject');entry=next(iter(prop));file=entry.attrib.get('file','')
  if not file:continue
  path=(MEC/Path(filename).parent/file).resolve();ref=path.stem
  refs[ref]=refs.get(ref,0)+1;occurrences.append(dict(assemblage=filename,occurrence=obj.attrib['name'],reference=ref,fichier=str(path.relative_to(ROOT)).replace('\\','/'),sha256=sha(path)))
write(VER/'nomenclature_etage_batterie.json',dict(date='2026-10-04',statut='À valider',scope='Dock + étage énergie ; quantités CAO, pas commandes ni fixations qualifiées',quantites=refs,occurrences=occurrences,finalisation_correcte=True))
p=VER/'faisceau_dock20Ah_20261002.json';f=read(p);f['date_utc']='2026-10-04';f['objet']='Pack préparé pour raccordement direct TE, sans XT90-S frontal ; étage énergie inférieur candidat'
for row in f['netlist'][:2]:row['connexion']='Fil AWG8 du pack vers cosse90 candidate742F5 puis contactTE M5 mobile ; sortie et sertissage lot À valider'
for key in ['39_centre_monde_mm','40_centre_monde_mm']:f['positions_TE'][key][0]=-200.2548
f['terminaisons']['puissance_TE']='Quatre terminaisons M5 : deux cosses90 mobiles et deux cossesPhoenix3240219 fixes ; P42/AWG10/XT90-S retirés de cette variante.'
f['terminaisons']['dimensions_faisceaux']='Chemins CAO mobiles89.70/90.56mm, fixes354.42/354.07mm ; préparation, dénudage et coupe à définir sur lot/gabarit. Pas intervention sur cellules scellées.'
f['terminaisons']['cosse_mobile_candidate']={'mpn':'742F5','fabricant':'Klauke','nominal_mm2':10,'AWG8_sertissage_confirme':False,'trou_M5_mm':5.3,'geometrie':'enveloppe coude étude'}
f['routes_mobiles']=mob['routes_mobiles'];f.pop('fils_pack_conserves',None);f['fils_pack_preparation']={'XT90_S':'retiré de la définitionCAO','fils_scelles_cellules':'hors périmètre','longueur_usine_mm':150,'coupe_finale_mm':None,'statut':'À valider'}
f['segment_fixe_TE_JETI']={'routes':fixed['routes'],'destination':'JETI IN étage inférieur','stock_JETI_section_mm2':None,'section_kit_a_confirmer_mm2':8,'raccords_et_retention':'À définir sur sorties réelles ; anciennesépissures/P53 non posées danscourant','TE_152_4mm':'distance spatiale au collier si présent, pas longueur bouclée ; aucun collier procheTE enCAO','dressage_TE':'Orientation−Y des cossesfixes et liberté desdeuxmoitiés à approuver/valider selon114-13206 ; R50 ne prouvepas conformité.'}
f['retenues']={'puissance_mobile':'P43/P44 candidats','equilibrage':'P51/P52 danscorridor intérieur ; anciennesvisretenue retirées, fixation àdéfinir','modules_fixes':'P57 appuis/butées/lumières ; vis/sangles et reprise de traction àsélectionner','statut':'À valider'}
f['contraintes_implantation']=['JETI/PM08-CAN/PDB dans SA07 sous la batterie ; dégagements des corps contrôlés, faisceaux aval à recoter', 'Préparation directe du pack vers TE, lot et sertissage des cosses candidates À valider', 'Dressage et flottement TE À valider selon 114-13206 ; aucun collier proche TE représenté']
f['limites_courant'].pop('XT90_catalogue_A',None);f['limites_courant'].pop('condition_XT90',None)
f['limites_courant']['conclusion']='XT90-S retiré de cette variante ; les calibres catalogue TE/JETI/pack ne qualifient pas le courant continu de la chaîne complète. Mesurer résistance, transitoires, courant mission et échauffement sur le lot et le montage réel.'
f['charge_hors_drone']={'statut':'Planifié','interface':'Adaptateur TE protégé vers les deux voies de puissance et chargeur compatible 6S NMC, avec équilibrage séparé','limite':'JST d’équilibrage seul insuffisant ; jamais charger via JETI OUT. Adaptateur, polarités, isolement et protocole À valider.'}
f['perimetre_geometrique']={'pack_nominal_mm':[193,76,58],'enveloppe_etude_mm':[198,78,60],'controle':'Pack nominal uniquement ; enveloppe maximale, sorties du lot et tolérances À valider'}
f['sources_sha256']={r['fichier']:r['sha256'] for r in occurrences};write(p,f)
sources=read(VER/'sources_bom_dock20Ah_20261002.json');sources['sources'].append({'fabricant':'Klauke','mpn':'742F5','url':'https://www.klauke.com/be/de/winkelrohrkabelschuhe-cu-90-und-45-abgewinkelt-f-reihe','donnees':{'section_nominale_mm2':10,'classes':'5/6','M5_trou_mm':5.3,'angle_deg':90},'limite':'Compatibilité exacteAWG8, outillage et sertissage à confirmer ; modèlecoudeétude.'}) if not any(x.get('mpn')=='742F5' for x in sources['sources']) else None;write(VER/'sources_bom_dock20Ah_20261002.json',sources)
b=read(VER/'bom_dock20Ah_20261002.json');b['date_utc']='2026-10-04';b['objet']='Nomenclature dock directTE et étageénergie inférieur candidat';b['assemblage_inventorie'].update(sha256=sha(MEC/'sous_assemblages/SA02A_Dock20Ah.FCStd'),occurrences=refs,perimetre='SA02A + SA07 ; détail nominatif verification/nomenclature_etage_batterie.json')
for category in ['pieces_fabriquees','visserie_modelee','composants_commerce']:
 for row in b[category]:
  ref=Path(row.get('fichier','') or '').stem or row.get('reference','');count=refs.get(ref,0)
  if ref=='EQ_JetiMainSwitch100':count=refs.get('EQ_JetiMainSwitch100_PortsEtude20A',0)
  row['quantite_installee']=count;row['configuration_courante']='active' if count else 'hors configurationcourante, référencecatalogue historique'
  path=ROOT/(row.get('fichier','') or '')
  if path.is_file():row['sha256']=sha(path)
  if row.get('reference')=='BAT20':row['designation']='NMC6S20Ah sélectionnée ; préparation directeTE candidate, XT90-S retiré de cette variante'
  if not count and 'quantite_achat_unitaire' in row:
   row.setdefault('quantite_achat_historique',row['quantite_achat_unitaire']);row['quantite_achat_unitaire']=0
for ref in ['P57_PlateauEnergieInferieur','EQ_Klauke742F5_Cosse90_TE','EQ_PM08_CAN_Enveloppe_Systeme_Candidat','EQ_Holybro_PDB18138_Systeme_Candidat']:
 row=next(r for r in occurrences if r['reference']==ref);category='pieces_fabriquees' if ref.startswith('P57') else 'composants_commerce'
 if not any(x.get('reference')==ref for x in b[category]):b[category].append(dict(reference=ref,quantite_installee=refs[ref],fichier=row['fichier'],sha256=row['sha256'],statut_CAO='Implémenté',statut_physique='À valider',designation='Supportcandidat' if ref.startswith('P57') else 'Référencecandidate, lotetfixation àconfirmer'))
b['alternative_etude']['raison_non_active']='Option de pack historique ; la définition courante utilise le TAA200006S5X9S préparé pour raccordement direct TE, sans conserver son XT90-S.'
b['faisceau']='verification/faisceau_dock20Ah_20261002.json';b['bilan_masse_partiel']['validite_courante']='Historique ; ne couvre pas les pièces recoupées ou nouvelles. Bilan physique à refaire.';b['elements_a_synchroniser']=['Longueurs finales, cosses90/AWG8, kitJETI, faisceaux aval, fixation coffrets/P57, masse et qualification physique'];b['sources_sha256']=f['sources_sha256'];write(VER/'bom_dock20Ah_20261002.json',b)
m=read(MEC/'manifest.json');m['configuration_dock20Ah']['evolution_courante']={'date':'2026-10-04','noms_stables':True,'realisation_CAO':'Implémenté','statut':'À valider','assemblage':'sous_assemblages/SA02A_Dock20Ah.FCStd','distribution':'sous_assemblages/SA07_Distribution_Systeme_Candidat.FCStd','verification':'verification/controle_etage_batterie.json','rendu':'verification/rendu_etage_batterie.json','nomenclature':'verification/nomenclature_etage_batterie.json','dimensions_batterie_et_energie_mm':control['dimensions_batterie_et_energie_mm'],'TE_recul_mm':82,'pack_rotation_Z_deg':180,'limites':control['limites'],'branche_Git_avant':read(VER/'suivi_git_etage_batterie.json')['branche'],'DOC_MEC':'§4.1.3.2','DOC_VAL':'§12.1.8'}
for row in m['catalogue_courant_20261004']['selection']:
 path=MEC/row['fichier'] if 'fichier' in row else None
 if path and path.is_file():row['sha256']=sha(path)
 if row['reference'] in ['SA02A_Dock20Ah','SA07_Distribution_Systeme_Candidat','Integration_Stack_Revue_20261003']:row['verification']='verification/controle_etage_batterie.json'
write(MEC/'manifest.json',m)
extra=[r['fichier'] for r in occurrences if r['reference'] in ['P57_PlateauEnergieInferieur','EQ_Klauke742F5_Cosse90_TE','EQ_PM08_CAN_Enveloppe_Systeme_Candidat','EQ_Holybro_PDB18138_Systeme_Candidat']]+['hardware/mecanique/cartographe/sous_assemblages/SA07_Distribution_Systeme_Candidat.FCStd','hardware/mecanique/cartographe/assemblages/Integration_Stack_Revue_20261003.FCStd']
extra=list(dict.fromkeys(extra))
p=ROOT/'.gitignore';text=p.read_text(encoding='utf-8');text+='\n# Étage énergie inférieur : petits natifs suivis explicitement\n'+'\n'.join('!/'+s for s in extra if '!/'+s not in text)+'\n' if any('!/'+s not in text for s in extra) else '';p.write_text(text,encoding='utf-8')

if '--sans-docs' in sys.argv:
 print(json.dumps(dict(occurrences=len(occurrences),registres_actualises=True,documents_preserves=True)));raise SystemExit(0)
p=ROOT/'docs/architecture/ARCHITECTURE_MECANIQUE.md';text=p.read_text(encoding='utf-8')
text=text.replace('| chemin électrique mobile | conducteurs cuivreC101 P42, section10mm², sous protections P43–P45, raccordement frontal | procédé de pliage, isolation, serrage et échauffement à qualifier |','| chemin électrique mobile | packretourné, filsAWG8 courts et cosses90 candidates surTE ; P43/P44 arrière | lot, sertissage, isolation etéchauffementÀvalider |')
text=text.replace('| coupure fixe | JETIMainSwitch100 et commande magnétique sur P41, captures et colliers |','| coupure fixe | JETIMainSwitch100 et commande magnétique àétageinférieur surP57 candidat |')
text=text.replace('| raccordement pack | protection P46, porte-à-faux XT90 P47, fils d\'origine conservés | sorties du lot, mou, courbures et tenue du porte-à-faux à contrôler |','| raccordement pack | XT90-S/P42/P45–P47 retirés ; TE/P39/P40 reculés82mm | supports rallongés, lot etpréparationpackÀvalider |')
start=text.index('Sept colliers T50R');end=text.index('Le choix s\'appuie',start);text=text[:start]+"La configuration courante est décrite au§4.1.3.2. L'ancienne implantation\nP41/P53, les sept colliers et les épissures frontales ne définissent plus\nles quantités courantes ; voir la BOM actualisée et Git pour leur historique.\n\n"+text[end:]
text=text.replace('Les longueurs libres480,91/425,75mm dépassent152,4mm ; cela ne démontre pas\nla liberté réelle de la fixation flottante TE.','La longueur480,91/425,75mm ne démontre ni la distance spatiale152,4mm\nau premier collier ni la liberté réelle de la fixation flottanteTE.')
text=text.replace('Le compactage physique complet reste **À valider** ; aucun changement de\ncapacité batterie, de connecteur commercial ou de mécanisme de coupure n\'est engagé.','Cette première étape est historique ; l\'orientation du pack et son\nraccordement sont maintenant repris au§4.1.3.2. La capacité et le mécanisme\nde coupure sont conservés ; le compactage physique reste **À valider**.')
section="""##### 4.1.3.2 Énergie à l'étage inférieur et pack directement au TE — 4 octobre 2026

Choix utilisateur **Implémenté en CAO**, physique **À valider** : JETI,
commande magnétique, PM08-CAN et PDB18138 sont placés dans SA07 sous la
batterie, autour de la pilecentrale. Le plateauP57 candidat comporte trois
îlots étagés, appuis, butées, lumières et attaches sur deux axes OEM ; vis,
sangles, maintien vertical/axial, dissipation et procédure restent à définir.
Les modules débordent latéralement de l'empreinte du pack. Une implantation
centrale entre les plateaux a été écartée pour collisions et manque de place
aux prises. Les sources fabricant ne sont pas usinées.

Le pack est tourné180° autourdeZ. Le TE et les panneaux P39/P40 reculent82mm ;
leurs bras sont allongés vers les ancrages existants. Cette concession donne
la place aux deux filsAWG8 directs et aux cosses90 candidates Klauke742F5.
Le XT90-S frontal, les deux adaptateursAWG10, les longues barresP42 et leurs
protections longitudinales sont retirés. Les chemins mobiles sont89,70/90,56mm
avec arcsR50. La742F5 est nominale10mm² : sa compatibilité exacteAWG8, son
sertissage et la géométrie du coude ne sont pas confirmés. Les sorties du
lot pack ne sont pas cotées ; aucun travail sur les cellules scellées.

P43/P44 deviennent un coffretarrière court sousZ102,5 ; le plateau commence
àZ103 (jeu nominal0,5mm, tolérances **À valider**). P51/P52 et la boucle
d'équilibrage sont dans le corridorintérieur, pour éviter les colonnesY±52
pendant l'extraction. Des passages sont ajoutés à P31 ; les fixations des
coffrets, protections anti-frottement et la résistance du cantilever82mm
restent **À valider**. Les anciennesvisretenueéquilibrage ne sont plus posées.

Les deux filsfixes R50 descendent versJETI :354,42/354,07mm. Leur dressage
et les sorties du kit doivent être approuvés avant fabrication ; la distance
TE152,4mm concerne le premier collier si utilisé, pas la longueur bouclée.
Les faisceauxJETI→PM08→PDB restent à recoter, ainsi que les prisesaccouplées.
PM08-CAN est conservé : PM08D désigne une autre famille de module.

Natifs conservés enplace : SA02A, SA02Cassette, SA02Contacts, SA07 et
Integration_Stack_Revue_20261003. PointGit avant migration :
`codex/batterie-avant-etage-inferieur`. Manifeste et BOM courants renvoient
au contrôle et à la nomenclature dansverification ; les preuves antérieures
et leurs empreintes sont historiques. Mesures et limites : DOC-VAL§12.1.8.

"""
if '##### 4.1.3.2 ' not in text:text=text.replace('### 4.2 Isolation du bloc capteurs',section+'### 4.2 Isolation du bloc capteurs')
text=text.replace('| 4 octobre 2026 | Couleurs natives', '| 4 octobre 2026 | Étage énergie inférieur et liaison directeAWG8/cosses90 auTE ; packretourné, supportsrecullés82mm, coffrets et passages repris ; réalisationCAO, fixations/lot/thermiqueÀvalider (§4.1.3.2, DOC-VAL§12.1.8) |\n| 4 octobre 2026 | Couleurs natives');p.write_text(text,encoding='utf-8')
p=ROOT/'docs/architecture/ARCHITECTURE_ELECTRIQUE_RESEAUX.md';text=p.read_text(encoding='utf-8');start=text.index('### 6.1 Dock 20 Ah');end=text.index('## 7. Architecture',start)
text=text[:start]+"""### 6.1 Dock 20 Ah : raccordement direct et coupure, 4 octobre 2026

La chaîne courante est **pack6S AWG8 → cosses90 candidates → TE mobile/fixe →
JETI IN/OUT → PM08-CAN → PDB → toutes les branches**. JETI, commande, PM08 et
PDB sont placés à l'étage inférieur dans SA07 surP57 candidat. Le raccordement
frontal XT90-S, les adaptateursAWG10 et les barresP42 sont retirés. Le schéma
CA01 conserve ses circuits ; cette migration CAO n'est pas un routageKiCad.

TE ELCON125A Middle Drawer : logements1648151-1/1648156-1, broches1766283-1
fixes flottantes survis1650589-1 et douilles6648335-1 mobiles. Positions39=+
et40=− ; aucun signal ni interverrouillage ajouté. ContactsM5×0,8 internes ;
coupleplafond2,9Nm selon114-13206, engagement de vis et talonnage à contrôler.
Rails, butée et verrouSouthco reprennent la cassette ; les contacts ne font
pas fin de course ni retenue. Les calibrescatalogue ne qualifient pas le drone.

La cosse90 Klauke742F5 est candidate : cuivreétamé, M5/trou5,3mm,10mm²,
conducteursfins classes5/6. Son adéquationAWG8, sertissage/outillage et la
forme exacte du coude restent **À valider**. Elle permet un départaxial
court ; la cossePhoenix droite exigeait des contre-coudes trop longs.
Les deux filsdupack ont des cheminsCAO89,70/90,56mm R50, sansprolongation
ni barreslongitudinales. Les150mm usine sont une donnée d'achat ; retrait
XT90-S, préparation, coupe et dénudage doivent être définis sur le lot,
sans intervention sur les cellules scellées. Les bornes sous tension et
la charge horsdrone demandent un adaptateurTE protégé **Planifié**.

Côtéfixe : cossesPhoenix3240219 AWG8, P48 et P49/P50, fils55A0111-8-2/-0
(Ønominal4,78mm, étude5mm), routesR50 de354,42/354,07mm versJETI inférieur.
Les anciennesépissures/gainesP53 ne sont pas représentées dansle courant :
raccords surfilsOEM, sectionkit6/8mm², bridage et sortiesréelles sont à définir.
La variantePM08-CAN àfilsétamés SKU15029 est candidate pour faciliter le
raccordement aval. Le PM08D numériqueI²C est distinct, sans substitution.
Les réservations JETI/PM/PDB ne sont pas des sorties fabricant cotées.

TE114-13206§3.18 impose une liberté des fils qui ne restreignepas le
flottement, un dressage perpendiculaire auconnecteur, R≥10×diamètre et un
collier éventuel à au moins152,4mm du départconnecteur. La longueur d'une
boucle ne démontre pas cette distance spatiale. Aucun premiercollier procheTE
n'est posé danscette CAO ; l'orientation−Y des cossesfixes et les fils courts
côtémobile doivent être approuvés/validés pour cette application. Aucun
respect global de cette spécification n'est revendiqué.

JETI MainSwitch100 fournit coupure et anti-étincelle ; il commute **le négatif
seulement**, le positif demeure raccordé. Aucun retour aval, USB, chargeur
ou auxiliaire ne doit rejoindre le négatifbrut et contourner la coupure.
PM08 et tous les consommateurs restent en aval. Sa télémétrie n'est pas
raccordée ici. Anti-étincelle annoncé, courantd'appel/charge et températures
restent à mesurer ; retirerXT90-S ne qualifie ni85A ni100A système.

Échange : au sol, désarmé, moteurs arrêtés ; JETI OFF vérifié avant
déverrouillage/extraction ; insertion jusqu'àbutée, verrouillage vérifié,
puis ON. L'étatON est mémorisé : il faut commanderOFF avant déconnexion.
Aucun interverrouillageOFF/loquet automatique n'est revendiqué. Charge
horsdrone avecadaptateurTE protégé, jamais parJETI OUT ; priseéquilibrage
rangée sousP51/P52. Le choix du pack et les seuilsPX4/CA01 sont conservés.

[Faisceau courant](../../hardware/mecanique/cartographe/verification/faisceau_dock20Ah_20261002.json),
[BOM](../../hardware/mecanique/cartographe/verification/bom_dock20Ah_20261002.json),
[Klauke fabricant](https://www.klauke.com/be/de/winkelrohrkabelschuhe-cu-90-und-45-abgewinkelt-f-reihe),
[PM08-CAN fabricant](https://holybro.com/collections/power-modules-pdbs/products/dronecan-pm08-power-module-14s-200a).
ValidationCAO et limitesmatérielles : DOC-VAL§12.1.8, DOC-MEC§4.1.3.2.

"""+text[end:]
text=text.replace('contacts M5 TE 1766283-1 / 6648335-1 et adaptateur XT90','contacts M5 TE 1766283-1 / 6648335-1 et cosses90 candidates')
text=text.replace('| 4 octobre 2026 | Repli des deux adaptateurs', '| 4 octobre 2026 | Liaisonpack directeTE par cosses90 candidates, sansXT90-S/AWG10/P42 ; énergie àétageinférieur, PM08-CAN conservé ; dressageTE/lot/fixations/thermiqueÀvalider (§6.1, DOC-VAL§12.1.8) |\n| 4 octobre 2026 | Repli des deux adaptateurs');p.write_text(text,encoding='utf-8')
p=ROOT/'docs/VALIDATION_QUALIFICATION.md';text=p.read_text(encoding='utf-8')
section=f"""### 12.1.8 Étage énergie et raccordement direct du pack — 4 octobre 2026

Chaîne MEC-ARC-001/MEC-BAT-001 → SA02A, SA07 et P31/P39/P40/P43/P44/P51/P57 →
T-CARTO-ETAGE-DIRECT-01 → [contrôle](../hardware/mecanique/cartographe/verification/controle_etage_batterie.json),
[distribution](../hardware/mecanique/cartographe/verification/distribution_etage_batterie.json),
[revue indépendante](../hardware/mecanique/cartographe/verification/revue_etage_batterie.json),
[rendu natif](../hardware/mecanique/cartographe/verification/rendu_etage_batterie.json).
Windows amd64, FreeCAD1.1.3 ; aucune qualification matérielle.

Protocole : réouvrir/recalculer dansun processusneuf ; contrôlerliens,
unicitéJETI/PM/PDB, corps sousbatterie et géométriesfinales ; mesurer quatre
balayagesnatifs, rayonsR50, intersections, puis extraction échantillonnée
contrechâssis etpiècesfixes. Les formesdeconstruction cachées ne doivent
pas gonflerApp::Part.Shape : visibilitéApp etGUI sont synchronisées, BRep
courants conservés et matériauxnatifs relus après sauvegarde.

Résultatscourants : {control['occurrences_dock']} occurrencesdock ; aucun objetInvalid ni
lien nonrésolu dansle contrôle. Filsmobiles89,70/90,56mm ; fixes354,42/354,07mm,
arcsR50. Enveloppe batterie+énergie : {'×'.join(f'{v:.2f}' for v in control['dimensions_batterie_et_energie_mm'])}mm.
Cette boîte inclut le déport latéralSA07 ; ne pas comparer son volume à
l'ancien dockseul ni déduire un gain demasse. Détailsdesintersections et
poses d'extraction dansla preuve etla revue, sans assertionglobale de
conformitéphysique. La réservePDB de22mm est sanscollisionchâssis.

Les collisions détectées avec logementTE/capture/cosse, un tubechâssis et
le plateau pendant extraction ont motivé recoupes descoffrets, routagefixe
plusprécoce, passages dansP31 et équilibrage dans le corridor intérieur.
Le jeu nominalP44/plateau est0,5mm ; tolérances àvalider. La comparaison
échantillonnée n'est pas une preuve continue générale ; les guidesSTEP TE
gardent leurs limites historiques (ni accouplement ni flottement qualifiés).

Conclusion **préliminaire**, CAO **Implémenté**, matériel **À valider**.
Nonexécutés : réception deslotspack/cosses/kit, compatibilitéAWG8/sertissage,
adaptateurchargeTE, dressage etlibertéTE, finalisationvis/sangles/coffrets,
résistancecantilever82mm, traction, vibration, isolement/courant/thermique,
hélices etvol ; absence defournitures etde banc. FaisceauxavalJETI/PM/PDB à
recoter. Les anciennespréparations150/600/520mm et tableaux7colliers ne
définissent pas les coupes ou quantitésactuelles ; BOM/faisceau misàjour.
Le seuil152,4mm TE est spatial au collieréventuel ; mêmeR50 et une longueur
totale suffisante ne démontrent pas conformité du dressageperpendiculaire.

PointGit avant migration : codex/batterie-avant-etage-inferieur ; nomsdes
assemblages conservés. Les preuves§12.1.3/12.1.6/12.1.7 sont historiques et
leurs empreintes ne certifient pas les fichierscourants. Le contrôlecourant
porte les nouvellesempreintes ; aucunequalificationdronecomplète ajoutée.

"""
if '### 12.1.8 ' not in text:text=text.replace('### 12.2 Carte avionique CA01',section+'### 12.2 Carte avionique CA01')
text=text.replace('solides valides, rayons circulaires50mm, longueurs libres>152,4mm,','solides valides, rayons circulaires50mm, longueurs dechemin relevées,')
text=text.replace('| 4 octobre 2026 | Dock coloré', '| 4 octobre 2026 | CAO étageénergie et packdirectTE : suppressionXT90-S/P42, cosses90 candidates et supportsrepris ; réouverture/contrôles/rendu ; physiqueÀvalider (§12.1.8) |\n| 4 octobre 2026 | Dock coloré')
text=text.replace('| MEC-ARC-001, MEC-BAT-001 | dock courant coloré', '| MEC-ARC-001, MEC-BAT-001 | étageénergie et packdirectTE | T-CARTO-ETAGE-DIRECT-01, §12.1.8 | liens/rayons/implantation/collisions/extraction contrôlés ; lot etfixations àvalider | CAO **Implémenté**, préliminaire |\n| MEC-ARC-001, MEC-BAT-001 | dock historique coloré');p.write_text(text,encoding='utf-8')
print(json.dumps(dict(quantites=refs,documents=3,finalisation_correcte=True),ensure_ascii=False))
