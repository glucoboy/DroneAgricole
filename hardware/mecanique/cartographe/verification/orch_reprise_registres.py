"""Consolidation déclarative de la reprise ; les sommes restent en C++17."""
from pathlib import Path
import hashlib
import json
import copy
from datetime import datetime,timezone

ROOT=Path(__file__).resolve().parents[4]
MEC=ROOT/'hardware/mecanique/cartographe';VER=MEC/'verification'
def read(p):return json.loads(Path(p).read_text('utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def source_path(value):
 p=Path(value)
 if not p.is_absolute():p=(ROOT if value.startswith(('hardware/','.runtime/','simulation/')) else MEC)/p
 p=p.resolve();p.relative_to(ROOT);return p
def enrich(bom,build):
 bom['date']=datetime.now(timezone.utc).date().isoformat()
 definitions=bom['orch_cao_masse_1'];proofs={};problems={};overrides={};component_masses={}
 hashes=definitions['preuves_sources_sha256'];source_ids={s['id']:s for s in definitions['sources']}
 fraisures_file=VER/'orch_reprise_vis_fraisees_application.json'
 fraisures=read(fraisures_file) if fraisures_file.exists() else {}
 evolutions={r['fichier']:r for r in fraisures.get('natifs_modifies',[])}
 chc_file=VER/'orch_reprise_tetes_chc_application.json';chc=read(chc_file) if chc_file.exists() else {}
 if chc:
  if chc['script_sha256']!=sha(VER/'orch_appliquer_tetes_chc.py') or chc['proposition_sha256']!=sha(VER/'orch_reprise_tetes_chc.json'):raise ValueError('Reprise CHC divergente')
  evolutions.update({r['fichier']:r for r in chc['natifs_modifies']})
 if fraisures:
  if fraisures['script_sha256']!=sha(VER/'orch_appliquer_vis_fraisees.py') or fraisures['proposition_sha256']!=sha(VER/'orch_reprise_vis_fraisees.json'):raise ValueError('Reprise fraisures divergente')
 for axis in ('structure','fournitures','equipements','visserie_complement','waveshare'):
  file=VER/('orch_reprise_perimetres_waveshare.json' if axis=='waveshare' else 'orch_reprise_masses_'+axis+'.json');proof=read(file)
  if not proof.get('finalisation_correcte'):raise ValueError('Recherche de reprise non finalisée : '+axis)
  originals=proof.get('sources',[])+proof.get('sources_preexistantes',[])
  mapping={s['id']:'REPRISE-'+axis.upper()+'-'+s['id'] for s in originals}
  def normalize(value):
   if isinstance(value,list):return [normalize(v) for v in value]
   if isinstance(value,dict):return {k:([mapping.get(v,v) for v in val] if k=='source_ids' and isinstance(val,list) else mapping.get(val,val) if k=='source_id' and isinstance(val,str) else normalize(val)) for k,val in value.items()}
   return value
  proof=normalize(proof)
  originals=proof.get('sources',[])+proof.get('sources_preexistantes',[])
  for source in originals:source['id_dans_preuve']=source['id'];source['id']=mapping[source['id']]
  proofs[axis]=proof;hashes[file.relative_to(ROOT).as_posix()]=sha(file)
  for s in originals:
   s=dict(s)
   if s.get('fichier'):
    p=source_path(s['fichier']);actual=sha(p)
    if s.get('sha256') and s['sha256']!=actual:raise ValueError('Source de reprise divergente : '+str(p))
    s['fichier']=p.relative_to(ROOT).as_posix();s['sha256']=actual;hashes[s['fichier']]=actual
   if s['id'] in source_ids and s!=source_ids[s['id']]:raise ValueError('ID source à réconcilier : '+s['id'])
   if s['id'] not in source_ids:definitions['sources'].append(s);source_ids[s['id']]=s
  for row in proof.get('propositions_normalisees',[]):
   if axis=='waveshare':
    row.update(qualificatif='inconnue',conditions=row['probleme_massique'],inclusions=[],exclusions=['Périmètre net et emballage non établis ; aucune contribution retenue.'])
    overrides[row['bom_id']]=row
    problems.setdefault(row['bom_id'],[]).insert(0,dict(row,preuve=file.relative_to(ROOT).as_posix()))
   elif row.get('applicable') and row.get('masse_unitaire_g') is not None:
    previous=overrides.get(row['bom_id'],{})
    if previous.get('applicable') and previous.get('masse_unitaire_g') is not None and previous!=row:raise ValueError('Deux masses applicables : '+row['bom_id'])
    overrides[row['bom_id']]=row
   elif row.get('masse_incluse_dans'):
    previous=overrides.get(row['bom_id'],{})
    if previous.get('applicable') and previous.get('masse_unitaire_g') is not None:raise ValueError('Inclusion et masse autonome concurrentes : '+row['bom_id'])
    overrides[row['bom_id']]=row
   elif row['bom_id'] not in overrides:overrides[row['bom_id']]=row
  for problem in proof.get('problemes_massiques',proof.get('problemes',[])):
   identifiers=problem.get('bom_ids',[problem.get('bom_id')])
   for identifier in identifiers:
    if identifier:problems.setdefault(identifier,[]).append(dict(problem,preuve=file.relative_to(ROOT).as_posix()))
  for record in proof.get('recettes_composants_documentaires',[]):
   r=dict(record);p=source_path(r['fichier'])
   if sha(p)!=r['sha256_natif']:
    evolution=evolutions.get(p.relative_to(MEC).as_posix(),{})
    if evolution.get('sha256_avant')!=r['sha256_natif'] or evolution.get('sha256_apres')!=sha(p):raise ValueError('Composant documentaire modifié sans preuve : '+str(p))
    r['sha256_natif_avant_reprise']=r['sha256_natif'];r['sha256_natif']=sha(p)
    r['reprise_geometrique']='verification/orch_reprise_vis_fraisees_application.json' if 'ISO10642' in p.name else 'verification/orch_reprise_tetes_chc_application.json'
    r['limite_geometrique']='Gabarit théorique conservateur90°, diamètre6,72mm ; contour exact fabricant inconnu, masse nominale documentaire indépendante du volume de réservation.' if 'ISO10642' in p.name else 'Diamètre de tête documentaire corrigé ; filets, empreinte, chanfreins et congés simplifiés, masse fournisseur indépendante du volume.'
    if r.get('dimensions_documentaires_et_ecarts'):
     r['dimensions_documentaires_et_ecarts_avant_reprise']=dict(r['dimensions_documentaires_et_ecarts'])
     current=r['dimensions_documentaires_et_ecarts']=dict(r['dimensions_documentaires_et_ecarts'])
     if 'ISO10642' in p.name:
      current.update(tete_cao_hauteur_mm=1.86,tete_cao_rayons_mm=[1.5,3.36],diametre_theorique_gabarit_mm=6.72,contour_exact_fabricant_connu=False)
     else:current['diametre_tete_cao_mm']=current['diametre_tete_documentaire_mm']
   r['valeur_g']=r['masse_unitaire_g'];component_masses[p.relative_to(MEC).as_posix()]=r
  if axis=='waveshare':
   overrides['ELEC-F41']={'bom_id':'ELEC-F41','masse_unitaire_g':None,'nature':'inconnue','qualificatif':'inconnue','applicable':False,'masse_incluse_dans':'ELEC-ISO','source_ids':[mapping['WS-P01']],
    'conditions':'Cordon USB A/B fourni conservé entier ; inclusion prévue dans ELEC-ISO, dont la masse nette reste inconnue. Les228,6g commerciaux ne sont pas une masse nette démontrée.',
    'inclusions':[],'exclusions':[],'incertitude_g':None}
 definitions['recettes_composants_documentaires']=component_masses
 # La masse du kit est une donnée d'approvisionnement connue ; elle n'est pas
 # celle du prototype modifié et ne doit pas être additionnée à ses composants.
 kit=next(item for item in bom['items'] if item['id']=='MEC-X650-KIT')
 assert kit['perimetre']=='approvisionnement' and 'REPRISE-EQUIPEMENTS-X650_CONTENTS' in source_ids
 kit['masse_unitaire_g']=2000.0
 kit['masse_nature']='Fabricant : kit complet sans batterie ; référence d’approvisionnement, non additionnée au drone modifié.'
 kit['donnee_massique']={'valeur_g':2000.0,'nature':'fabricant','qualificatif':'nominale','applicable':True,
  'perimetre_application':'Kit X650 Development Kit complet, sans batterie ; variantes Pixhawk 6C/6X non ventilées dans cette indication.',
  'incertitude_g':None,'source_ids':['REPRISE-EQUIPEMENTS-X650_CONTENTS'],
  'inclusions':['Structure X650, quatre moteurs, quatre ESC, quatre hélices, LED, PDB et avionique du kit selon liste fabricant.'],
  'exclusions':['Batterie ; poids d’emballage non présenté comme masse du drone.'],
  'conditions':'Valeur publiée pour le kit complet sans batterie, ni mesure de l’exemplaire ni masse du prototype modifié. Contenu précis, tolérance et différences de variante restent à confirmer.'}
 kit['contribution_connue_g']=None
 kit['mode_comptage_massique']='reference_approvisionnement_non_additionnee'
 kit['masse_complete_connue_dans_definition']=None
 # Estimations X650 : les analogies et les observations photographiques
 # restent explicites et chaque forme OEM est associée à une occurrence unique.
 newproofs={}
 for axis in ('kit_densites','kit_aluminium','propulsion_moteurs_esc','propulsion_helices'):
  file=VER/('orch_reprise_'+axis+'.json');proof=read(file);newproofs[axis]=proof
  hashes[file.relative_to(ROOT).as_posix()]=sha(file)
  for src in proof['sources']:
   sid='ESTIMATION-'+src['id'];record=dict(src);record['id_dans_preuve']=src['id'];record['id']=sid
   value=src.get('fichier') or src.get('fichier_extrait') or src.get('fichier_original')
   expected=src.get('sha256') or src.get('sha256_extrait') or src.get('sha256_original')
   if value:
    path=source_path(value);actual=sha(path)
    if expected!=actual:raise ValueError('Source estimation divergente : '+str(path))
    record['fichier']=path.relative_to(ROOT).as_posix();record['sha256']=actual;hashes[record['fichier']]=actual
    if src.get('fichier_extrait'):record['precision_conservation']='Extrait factuel ; original fournisseur indisponible, aucun original prétendu.'
   else:record['limite_capture']=src.get('limite_conservation') or src.get('motif_original_absent') or 'Source consultée, original non conservé dans le workspace.'
   if sid in source_ids:raise ValueError('Source estimation dupliquée : '+sid)
   definitions['sources'].append(record);source_ids[sid]=record
  for name,expected in proof.get('empreintes_entrees',{}).items():
   path=source_path(name)
   if sha(path)!=expected:raise ValueError('Entrée estimation différente : '+str(path))
   hashes[path.relative_to(ROOT).as_posix()]=expected
 geometry=read(VER/'orch_cao_masse_geometrie.json')
 physical={r['id']:r for r in geometry['occurrences_physiques']}
 shapes={(r['fichier'],r['objet']):r for r in geometry['references']}
 oem={}
 for row in newproofs['kit_densites']['pieces']:
  occurrence=row['occurrence'];p=physical[occurrence];native=source_path(row['reference_cao']).relative_to(MEC).as_posix()
  shape=shapes[(native,row['objet_source'])]
  if occurrence in oem or p['source']!=native or p['objet_source']!=row['objet_source'] or p['proprietaire_masse_bom']!=row['bom_id'] or not shape['valide'] or abs(shape['volume_mm3']-row['volume_mm3'])>1e-6:raise ValueError('Périmètre géométrique OEM divergent : '+occurrence)
  oem[occurrence]={'fichier':native,'objet_source':row['objet_source'],'bom_id':row['bom_id'],
   'methode':'volume_solide_terminal','volume_reference_mm3':row['volume_mm3'],'densite_g_cm3':row['densite_candidate_g_cm3'],
   'sha256_natif':shape['sha256'],'source_ids':['ESTIMATION-'+row['densite_source_id'],'REPRISE-EQUIPEMENTS-X650_CONTENTS'],
   'grade':'Carbone/époxy analogue, composition exacte OEM inconnue','procede':'Stratifié ou tube composite analogue, procédé OEM à confirmer',
   'conditions':row['conditions'],'incertitude_g':None,'estimation_candidate_non_mesuree':True,
   'preuve':'verification/orch_reprise_kit_densites.json'}
 definitions['estimations_geometrie_oem']=oem
 aluminium=newproofs['kit_aluminium'];geo_proof=aluminium['preuve_geometrie']
 for name,expected in [(geo_proof['fichier'],geo_proof['sha256']),(geo_proof['natif'],geo_proof['natif_sha256'])]:
  path=source_path(name)
  if sha(path)!=expected:raise ValueError('Entrée aluminium différente : '+str(path))
  hashes[path.relative_to(ROOT).as_posix()]=expected
 for row in aluminium['pieces_candidats']:
  occurrence=row['occurrence'];p=physical[occurrence];native=source_path(geo_proof['natif']).relative_to(MEC).as_posix();shape=shapes[(native,row['objet'])]
  if occurrence in oem or p['source']!=native or p['objet_source']!=row['objet'] or p['proprietaire_masse_bom']!=row['bom_id'] or not shape['valide'] or abs(shape['volume_mm3']-row['volume_mm3'])>1e-6:raise ValueError('Périmètre aluminium divergent : '+occurrence)
  oem[occurrence]={'fichier':native,'objet_source':row['objet'],'bom_id':row['bom_id'],'methode':'volume_solide_terminal',
   'volume_reference_mm3':row['volume_mm3'],'densite_g_cm3':row['densite_candidate_g_cm3'],'sha256_natif':shape['sha256'],
   'source_ids':['ESTIMATION-'+row['source_materiau'],'ESTIMATION-'+row['source_densite']],
   'grade':'Aluminium 6061 analogue, nuance exacte OEM inconnue','procede':'Pièce aluminium OEM, procédé et finition à confirmer',
   'conditions':row['condition']+' Des intersections avec des pièces exclues restent ouvertes ; aucune soustraction arbitraire.',
   'incertitude_g':None,'estimation_candidate_non_mesuree':True,'preuve':'verification/orch_reprise_kit_aluminium.json'}
 interferences_file=VER/'orch_verifier_interferences_oem.json';interferences=read(interferences_file)
 if interferences['script_sha256']!=sha(VER/'orch_verifier_interferences_oem.py') or interferences['proposition_sha256']!=sha(VER/'orch_reprise_kit_aluminium.json') or interferences['densites_sha256']!=sha(VER/'orch_reprise_kit_densites.json') or interferences['natif_sha256']!=sha(source_path(interferences['natif'])):raise ValueError('Contrôle global OEM périmé')
 if interferences['candidats']['intersections'] or interferences['candidats']['erreurs'] or interferences['candidats_contre_tubes']['intersections'] or interferences['candidats_contre_tubes']['erreurs']:raise ValueError('Candidats OEM en conflit entre eux ou avec les tubes comptés')
 for path in (interferences_file,VER/'orch_verifier_interferences_oem.py'):hashes[path.relative_to(ROOT).as_posix()]=sha(path)
 definitions['interferences_internes_oem']={'preuve':'verification/orch_verifier_interferences_oem.json','paires_testees':interferences['nombre_paires'],
  'paires_positives':interferences['nombre_intersections'],'paires_non_conclues':len(interferences['erreurs']),'qualification':'À valider',
  'nature':'Intersections BRep internes aux bras en placements globaux ; contact voulu ou erreur non établi.',
  'limite':'Aucune pièce exclue n’est comptée par l’estimation aluminium ; deux booléens non conclus, fonction et volume physique des intersections à résoudre.'}
 definitions['blocages'].append({'id':'STR-X650-INTERFERENCES-INTERNES','bom_ids':['MEC-OEM-BRAS','MEC-OEM-FIXATIONS','KIT-LED'],
  'information_necessaire':'Identifier les quatre feuilles 212/244/276/308, les bagues et filetages ; justifier ou corriger les 22 intersections BRep internes aux bras, résoudre deux booléens non conclus et leur comptage.',
  'preuve':'verification/orch_verifier_interferences_oem.json'})
 definitions['scenario_propulsion']={'preuve_esc':'verification/orch_reprise_propulsion_moteurs_esc.json','preuve_helices':'verification/orch_reprise_propulsion_helices.json',
  'contribution_esc_cartes_g':23.2,'contribution_helices_g':88.0,'conditions':'Hypothèses distinctes sur identité de la carte ESC et variante/unité de masse des hélices ; accessoires et câbles exclus.',
  'contribution_supplementaire_si_hypotheses_g':111.2,'comptabilise_dans_sous_total':False,'borne_garantie':False}
 if fraisures:
  geometric=read(VER/'orch_reprise_vis_fraisees.json')
  for source in geometric['sources']:
   s=dict(source);s['id_dans_preuve']=s['id'];s['id']='REPRISE-FRAISURES-'+s['id']
   p=source_path(s['fichier'])
   if sha(p)!=s['sha256']:raise ValueError('Source fraisure divergente')
   s['fichier']=p.relative_to(ROOT).as_posix();hashes[s['fichier']]=s['sha256'];definitions['sources'].append(s);source_ids[s['id']]=s
  definitions['reprise_fraisures']={'preuve':'verification/orch_reprise_vis_fraisees_application.json','nature':geometric['proposition']['nature'],'cotes':geometric['cotes'],'qualification':'À valider'}
 motor=next(r for r in proofs['structure']['masses_proposees'] if r['bom_id']=='MEC-MOTEUR')
 definitions['contributions_documentaires_partielles']=[{
  'id':'MN4014-CORPS-SANS-CABLES','bom_id':'MEC-MOTEUR','quantite_absolue_drone':motor['quantite'],
  'donnee_massique':{'valeur_g':motor['masse_unitaire_corps_documentaire_g'],'qualificatif':'nominale','nature':'fabricant','applicable':True,
   'source_ids':motor['source_ids'],'incertitude_g':None,'inclusions':motor['inclusions'],'exclusions':motor['exclusions']},
  'conditions':motor['applicabilite'],'masse_complete_installee_g':None}]
 for record in proofs['fournitures'].get('composants_conditionnels_et_partiels',[]):
  if record.get('bom_id')=='ELEC-F-M8':
   definitions['contribution_m8_deja_couverte']={'donnee_recherche':record,'comptage':'Déjà calculée en C++ depuis longueur et masse linéique ; ne pas ajouter cette seconde citation.'}
   continue
  if record.get('applicable') and record.get('masse_unitaire_g') is not None:
   definitions['contributions_documentaires_partielles'].append({'id':record['composant'],'bom_id':record['bom_id'],'quantite_absolue_drone':record['quantite_absolue_drone'],'donnee_massique':dict(valeur_g=record['masse_unitaire_g'],applicable=True,qualificatif='nominale',nature='fabricant',source_ids=record['source_ids'],conditions=record['conditions'],incertitude_g=None)})
 for record in proofs['equipements'].get('propositions_sous_bom',[]):
  if record.get('applicable') and record.get('masse_unitaire_g') is not None:
   definitions['contributions_documentaires_partielles'].append({'id':record['repere_sous_bom'],'bom_id':record['parent_bom_id'],'quantite_absolue_drone':1,'donnee_massique':dict(valeur_g=record['masse_unitaire_g'],applicable=True,qualificatif='nominale',nature='fabricant',source_ids=record['source_ids'],conditions=record['conditions'],incertitude_g=None)})
 complete_fabricated={'MEC-BATTERIE-SUPPORT','MEC-PLATINE-CAPTEURS','MEC-SUPPORT-ISOLATION','MEC-MANCHON','MEC-RONDELLE-CAPTURE','MEC-RETENUES-CAPTEURS','MEC-SUPPORTS-RF','MEC-ANCRAGES-CAPTEURS','MEC-VIS-ISOLATION','MEC-ECROU-ISOLATION','MEC-SUPPORT-AVIONIQUE'}
 current_mass_definitions={
  'MEC-ANCRAGES-CAPTEURS':('Quatre ISO10642 M3×40 à 2,10 g et leurs rondelles/écrous documentés ; ensemble défini couvert par recettes candidates.','Masse documentaire disponible ; tolérances et montage physique À valider.'),
  'MEC-SUPPORT-AVIONIQUE':('P66/P67/P68, quatre M3×55 à 3,09 g, huit rondelles et quatre écrous couverts par recettes candidates. Les fixations des guides et des pattes GNSS/USL sont comptées dans leurs postes distincts.','Contenu défini couvert ; interfaces, matériaux candidats et fabrication À valider, sans masse manquante déduite de cette seule absence de qualification.'),
  'MEC-SUPPORTS-ENERGIE':('Pièces fabriquées, quatre M3×75 à 4,15 g et leur visserie documentés ; six composants de fixation PM08 intégrés (deux M3×12, deux rondelles, deux écrous).','Définir les fixations réellement montées du BMS, PDB, UART et fusible CA01, avec références, quantités et masses. Les fixations PM08 sont désormais incluses ; le berceau QS8 conserve une interface à documenter.'),
  'MEC-SUPPORT-GNSS':('P69 et deux M2×12, quatre rondelles M2 et deux écrous M2 documentés ; ces vis fixent P69 à P66.','Définir la liaison du module GNSS 12037 à P69 : pièces, quantités et masses ou inclusion fabricant. Ne pas confondre cette liaison avec les deux M2×12 de la patte.'),
  'MEC-SUPPORTS-SECURITE':('P71 et deux M2×12, quatre rondelles M2 et deux écrous M2 documentés ; ces vis fixent P71 à P66.','Définir la fixation du module USL à P71, avec références, quantités et masses ; interface du module non documentée.'),
  'ELEC-PASSEFILS':('Dix-sept pièces de guidage et visserie documentées, dont quatre ISO10642 M3×16 à 0,83 g. Protections de chants EPDM encore indéfinies.','Obtenir référence, section, masse linéique, nombre et longueurs de coupe des protections EPDM. Ne pas recompter P76, les colliers ni les vis partagées.'),
  'ELEC-F20':('Cordon OEM 37 ± 3 mm prévu dans le refroidissement ; ni masse nette de ce kit ni masse individuelle du cordon démontrée. Rallonge éventuelle distincte.','Obtenir la masse nette du kit 24076 avec contenu précis et pièces conservées, ou les masses séparées du cordon et des accessoires ; identifier le connecteur réel et le segment terminal.'),
  'ELEC-F41':('Cordon fourni conservé entier ; inclusion prévue dans ELEC-ISO, dont la masse nette reste inconnue.','Obtenir la masse nette du cordon exact ou de l’ensemble isolateur avec cordon conservé. Le périmètre net des 228,6 g commerciaux est ambigu ; aucune assimilation à un poids net ou de colis.')}
 for item in bom['items']:
  if item['perimetre']!='embarque':continue
  row=overrides.get(item['id'])
  if row:
   m=dict(item['donnee_massique']);m.update({k:row[k] for k in ('nature','qualificatif','applicable','source_ids','conditions','inclusions','exclusions','incertitude_g','valeurs_documentaires_conditionnelles') if k in row})
   m['valeur_g']=row.get('masse_unitaire_g');m['applicable']=bool(m.get('applicable') and m['valeur_g'] is not None)
   m['preuve_reprise']=[('verification/orch_reprise_perimetres_waveshare.json' if axis=='waveshare' else 'verification/orch_reprise_masses_'+axis+'.json') for axis,p in proofs.items() if row in p.get('propositions_normalisees',[])]
   for sid in m.get('source_ids',[]):
    if sid not in source_ids:raise ValueError('Source de masse de reprise inconnue : '+sid)
   item['donnee_massique']=m;item['masse_unitaire_g']=m['valeur_g'] if m['applicable'] and m.get('qualificatif') in ('nominale','approximative','calculee','mesuree') else None
   item['masse_nature']='Donnée de reprise : '+m.get('nature','inconnue')+' / '+m.get('qualificatif','inconnue')
   if m.get('valeur_g') is not None and not m['applicable']:item['masse_nature']='Valeur documentaire conditionnelle, non additionnée ; masse installée inconnue.'
   elif m.get('qualificatif')=='maximale':item['masse_nature']='Borne fabricant par composant, non additionnée ; masse nominale inconnue.'
   if 'masse_incluse_dans' in row:item['masse_incluse_dans']=row['masse_incluse_dans']
   item['definition_massique_candidate']=row.get('conditions')
  item['detail_physique_complet']=item['id'] in complete_fabricated
  if item['detail_physique_complet']:item['portee_completude_massique']='Contenu physique déclaré de cette ligne couvert ; les pièces comptées par d’autres lignes ne sont pas réadditionnées. Matériaux/procédés candidats, interfaces et fabrication À valider.'
  records=problems.get(item['id'],[])
  if item['id'] in current_mass_definitions:
   observation,need=current_mass_definitions[item['id']]
   item['definition_massique_candidate']=observation
   item['donnee_massique']['conditions']=observation
   if item['id']=='ELEC-F20':
    item['donnee_massique'].update(nature='inconnue',qualificatif='inconnue',applicable=False,valeur_g=None)
    item['masse_nature']='Inclusion prévue dans le refroidissement ; masse du cordon et masse nette du parent inconnues.'
   for record in records:
    if record.get('id','').startswith('MASSE-FOURNITURES-') or record.get('id')=='EQ-MASS-FAN-ACCESSOIRES':
     record['constat_avant_reprise']={k:record[k] for k in ('observation','information_necessaire','probleme_massique') if k in record}
     record.update(observation=observation,information_necessaire=need,consolidation='Recettes de visserie et contrelecture Waveshare de la reprise ; preuves originales conservées.')
     if 'probleme_massique' in record:record['probleme_massique']=need
   if not records:records.append({'id':'REPRISE-CONTENU-'+item['id'],'observation':observation,'information_necessaire':need})
  if item['id']=='MEC-REFROIDISSEMENT-JETSON':
   for record in records:
    if record.get('id')=='EQ-MASS-FAN-ACCESSOIRES':
     record['constat_avant_reprise']=record.get('probleme_massique')
     record['probleme_massique']='Le périmètre net des 72 g commerciaux est ambigu ; ni masse du ventilateur ni masse nette du kit démontrée.'
     record['information_necessaire']=current_mass_definitions['ELEC-F20'][1]
     record['preuve_consolidation']='hardware/mecanique/cartographe/verification/orch_reprise_perimetres_waveshare.json'
  if item['id'].startswith('MEC-SORBOTHANE-'):
   item['definition_massique_candidate']=item['definition_massique_candidate'].replace('Correction rattachementBAS0510030/HAUT0510010 annoncée parroot.','Rattachement BAS 0510030 / HAUT 0510010 appliqué et contrôlé dans les occurrences sauvegardées.')
  if item['id'] in ('MEC-OEM-PLATEAUX','MEC-OEM-BRAS','MEC-OEM-TRAIN'):
   amounts=newproofs['kit_densites']['sous_totaux_candidats_g'];value=amounts[item['id']]
   count=sum(1 for r in newproofs['kit_densites']['pieces'] if r['bom_id']==item['id'])
   if item['id']=='MEC-OEM-BRAS':value+=aluminium['total_candidat_g'];count+=len(aluminium['pieces_candidats'])
   item['definition_massique_candidate']=f'Estimation CAO par densités analogues : {value:.3f} g pour les pièces identifiées ; densités et procédés OEM réels inconnus, aucun résultat mesuré ni borne garantie. Voir les preuves kit_densites et kit_aluminium.'
   item['estimation_cao_candidate']={'contribution_g':round(value,3),'quantite_absolue_drone':count,
    'condition':'Densité de matériau analogue ; composition, nuance et procédés OEM exacts inconnus.'+(' Intersections internes des bras non qualifiées.' if item['id']=='MEC-OEM-BRAS' else ''),
    'comptabilisee_dans_sous_total':True,'incertitude_g':None,'preuve':'verification/orch_reprise_kit_densites.json',
    'preuve_complementaire':'verification/orch_reprise_kit_aluminium.json' if item['id']=='MEC-OEM-BRAS' else None}
   for record in records:
    if record.get('bom_id')==item['id']:
     record['constat_avant_estimation']=record.get('probleme_massique')
     record['probleme_massique']=item['definition_massique_candidate']
     record['action_necessaire']='Confirmer densité, stratification, révision et masse des composants OEM retenus ; compléter les raccords et fixations non couverts.' if item['id']!='MEC-OEM-PLATEAUX' else 'Confirmer densité et stratification OEM et masse réelle des quatre plateaux ; estimation de leur contenu géométrique seulement.'
   if item['id']=='MEC-OEM-BRAS':records.append({'id':'STR-X650-INTERFERENCES-INTERNES','observation':'22 intersections positives et deux booléens non conclus sur 216 paires locales aux groupes, en placements globaux. Les douze solides estimés ne se recoupent pas entre eux ni avec les quatre tubes carbone.',
    'information_necessaire':'Identifier les quatre feuilles orphelines et les bagues ; vérifier les filetages, résoudre les deux booléens non conclus et justifier ou corriger les intersections et leur comptage.',
    'preuve':'verification/orch_verifier_interferences_oem.json'})
  if item['id']=='MEC-ESC':
   item['estimation_conditionnelle']={'masse_unitaire_g':5.8,'quantite':4,'contribution_g':23.2,'perimetre':'Carte seule, hors fils, prises, soudures, gaine et condensateur éventuel.','condition':'Carte du 31230 identique au 31104 non démontrée ; photo 31104 nu : 5,6 g ; nominal catalogue 5,8 g.','comptabilisee_dans_sous_total':False,'incertitude_g':None,'preuve':'verification/orch_reprise_propulsion_moteurs_esc.json'}
  if item['id'] in ('MEC-HELICE-CW','MEC-HELICE-CCW'):
   item['estimation_conditionnelle']={'masse_unitaire_g':22.0,'quantite':2,'contribution_g':44.0,'perimetre':'Deux hélices, fixations exclues.','condition':'Variante PMCF1555-T et masse 22 g par hélice non confirmées ; annonces divergentes.','comptabilisee_dans_sous_total':False,'incertitude_g':None,'preuve':'verification/orch_reprise_propulsion_helices.json'}
  if item['id']=='MEC-MOTEUR':
   item['information_pesee_reprise']='Corps 150 g déjà compté ; fils courts et MR30 visibles sur les photos OEM, masse complète à déterminer. La masse générique 171 g avec 600 mm de fils ne s’ajoute pas au corps.'
  if fraisures:
   for record in records:
    if record.get('id')=='GEO-TETES-FRAISEES':
     record['constat_avant_reprise']=record.get('observation')
     record['observation']='Angle nominal corrigé à90° sur vis, P60/P66 et huit placements ; gabarit théorique conservateur, contour réel et qualification des appuis non démontrés.'
     record['information_necessaire']='Plan3D exact des têtes Fabory, congés/rive, tolérances et confirmation de la portée mécanique réelle. Voir verification/orch_reprise_vis_fraisees_application.json.'
  if chc:
   for record in records:
    if record.get('id')=='GEO-TETES-CHC':
     record['constat_avant_reprise']=record.get('observation')
     record['observation']='Diamètres de tête corrigés selon les sources : M2×12 Ø3,8 et M3×55/M3×75 Ø5,5 ; hauteurs, axes et placements conservés.'
     record['information_necessaire']='Filets, empreintes, congés et chanfreins exacts restent non représentés ; masse fournisseur indépendante de ces cylindres simplifiés. Tolérances et tenue physique À valider.'
  item['reserves_geometriques_reprise']=[p for p in records if any(word in str(p).lower() for word in ('géométri','geometri','fraisur','cône','cone','pige'))]
  previous=[b for b in definitions['blocages'] if item['id'] in b.get('bom_ids',[])]
  item['probleme_massique']={'statut':'À valider','information_manquante':' ; '.join(dict.fromkeys(str(p.get('information_manquante') or p.get('information_necessaire') or p.get('action_necessaire') or p.get('observation') or p.get('probleme_massique') or '') for p in records)) or ' ; '.join(str(p.get('information_necessaire','')) for p in previous),
    'recherches_et_constats':records,'blocages_sources':previous,
    'impact':'Masse complète de la ligne et du drone non démontrée ; contributions connues distinctes, aucune assimilation à zéro.'}
  if item['donnee_massique'].get('qualificatif')=='maximale':
   item['probleme_massique']['information_manquante']='Obtenir la masse nominale nette de la référence exacte, ou une mesure existante documentée : la source disponible ne donne qu’une borne et aucune valeur nominale ne peut en être déduite. '+item['probleme_massique']['information_manquante']
  if item['id']=='MEC-SUPPORTS-ENERGIE':
   text='PM08 repris sur P64 : deux ISO4762M3x12 depuis dessous, deux ISO7089M3 et deux ISO10511M3 au-dessus ; lamagesØ5,8 profondeur0,5mm, webG10 restant2,3mm. Préassemblage hors châssis avant pose de P64 ; tenue mécanique et tolérances À valider.'
   item['definition_fixations_pm08']=text
  if item['id'] in ('ELEC-F37','ELEC-F38'):
   item['limite_geometrique_terminaison']='Parcours extérieur arrêté à0,55mm de la réservation QS8 pleine ; segment de raccordement, demi-corps et soudures non documentés, masse non incluse.'
  if item['id'] in ('ELEC-F38','ELEC-F05'):
   item['limite_geometrique_pm08']='Arrêt du parcours à0,5mm du boîtier ; diamètre extérieur8AWG inconnu, traversée interne non qualifiée. Entrée/sortie identifiées par déduction photo/STEP, sans connecteur inventé.'
  if item['id']=='ELEC-F20':
   item['limite_geometrique_terminaison']='Réservation du parcours déplacée à0,1mm du volume extérieur du ventilateur ; raccordement au connecteur réel et segment terminal non documentés, sans déduction de masse depuis ce raccourcissement.'
  reconcile_description(item,build)
 bom['resolution_definition']['date']=bom['date']
 definitions['reprise_attribution']={'preuves':list(proofs),'problemes_dans_chaque_ligne_bom':True,'tolérance_non_publiée':'Incertitude inconnue ; une masse nominale applicable reste utilisable.'}
 hashes['hardware/mecanique/cartographe/verification/orch_reprise_registres.py']=sha(__file__)
 for name in ['orch_reprise_collisions.json','orch_reprise_collisions.py','orch_reprise_f20.json','orch_reprise_f20.py','orch_reprise_f20_application.json','orch_appliquer_f20.py','controle_reprise_collisions.json','orch_verifier_reprise.py','orch_reprise_routes.py','orch_reprise_vis_fraisees.json','orch_reprise_vis_fraisees_application.json','orch_appliquer_vis_fraisees.py','orch_reprise_tetes_chc.json','orch_reprise_tetes_chc_application.json','orch_appliquer_tetes_chc.py']:
  p=VER/name
  if p.exists():hashes[p.relative_to(ROOT).as_posix()]=sha(p)

def reconcile_description(item,build):
 """Métadonnées de définition ; aucune somme massique exécutée ici."""
 identifier=item['id'];old_definition=item.get('definition');old_control=item.get('controle_minimal')
 touched=identifier in ('MEC-ANCRAGES-CAPTEURS','MEC-SUPPORTS-ENERGIE','MEC-SUPPORT-AVIONIQUE','ELEC-PASSEFILS')
 if touched:
  item.setdefault('definition_avant_reprise',copy.deepcopy({k:item.get(k) for k in ('definition','dimensions_mm','detail','controle_minimal','definition_origine')}))
  item['preuve_definition_courante']='verification/construction_prototype.json'
 if identifier=='MEC-SUPPORTS-ENERGIE':
  item['definition']='P64 G10 188×176×2,8 à Z36,2..39 sur quatre P74 ; PM08 déplacé et tourné de 180°, UART et fusible CA01 déplacés selon les matrices canoniques ci-dessous. Deux perçages Ø3,4 et lamages inférieurs Ø5,8 profondeur 0,5 mm reprennent les six composants de fixation PM08. P62 et quatre P63 de 63 mm conservent leurs quatre M3×75, huit rondelles et quatre écrous. P76 réemploie les deux vis de butée droite, comptées dans MEC-BATTERIE-FIXATIONS, et le collier F37_POS_-20, compté dans ELEC-COLLIERS. MIDI et boucles natives de maintien conservés sur P73.'
  dims=item['dimensions_mm']
  for key in ('centres_modules_energie_xy','enveloppe_pm08','enveloppe_uart','enveloppe_pdb','garde_superieure_pm08_uart_nominale'):dims.pop(key,None)
  modules=[r for r in build['occurrences'] if r['parent'].endswith('SA03_Prototype_Energie.FCStd') and any(x in r.get('bom_ids',[]) for x in ('ELEC-PM08','ELEC-ISO','ELEC-PDB','ELEC-PROTECTION-W08'))]
  dims['placements_modules_matrices_mm']={r['occurrence']:r['matrice'] for r in modules}
  dims['boites_sources_modules_mm']={r['reference']:r.get('bbox_mm') for r in build['references'] if r['fichier'] in {o['source'] for o in modules}}
  dims['fixation_pm08']={'axes_xy':[[-43.95,-59.5],[9.95,-59.5]],'passage':3.4,'lamage_diametre':5.8,'lamage_profondeur':0.5,'epaisseur_g10_restante':2.3}
  item['detail']=[d for d in item['detail'] if not d.get('occurrences_reprise_pm08')]
  for prefix,reference in [('VisPM08Reprise','ISO4762 M3×12, PM08'),('RondelleDessusPM08Reprise','ISO7089 M3, PM08'),('EcrouPM08Reprise','ISO10511 M3, PM08')]:
   item['detail'].append({'quantite':2,'reference':reference,'occurrences_reprise_pm08':[prefix+'0',prefix+'1']})
  item['controle_minimal']=item['controle_minimal'].replace('BMS/PDB/PM08/UART/fusible','BMS/PDB/UART/fusible').replace('42×24×15','60,9×29,7×15,4')
  suffix=' Fixation PM08 préassemblée hors châssis, puis P64 posée ; accès, tenue et tolérances physiques À valider.'
  if suffix not in item['controle_minimal']:item['controle_minimal']+=suffix
  item['interfaces_fabricant_a_definir']=['BMS','PDB','UART','fusible CA01']
 elif identifier=='MEC-ANCRAGES-CAPTEURS':
  item['definition']='Quatre ancrages communs P17 / plateau batterie OEM / semelle G10 aux axes X±60/Y±37. Les ISO10642 M3×40 sont représentées par un gabarit théorique conservateur à 90°, plan supérieur à Z−87,1 et pointe à Z−127,1. Rondelles et écrous sous P17 conservés ; contour exact et appui réel des têtes À valider. Aucun double compte dans MEC-BATTERIE-FIXATIONS.'
  dims=item['dimensions_mm'];dims.pop('depassement_nominal_sous_ecrou',None);dims.pop('z_tete_affleurante',None)
  dims.update(diametre_tete_reservation=6.72,z_plan_superieur_gabarit=-87.1,z_pointe=-127.1,angle_gabarit_deg=90)
 elif identifier=='MEC-SUPPORT-AVIONIQUE':
  suffix=' Reprise : quatre fraisures inférieures P66 à 90°, profondeur 1,86 mm, épaisseur résiduelle nominale 1,14 mm ; plans de gabarits VisGuideHaut à Z85,1. Contour réel des têtes et appuis physiques À valider.'
  if suffix not in item['definition']:item['definition']+=suffix
 elif identifier=='ELEC-PASSEFILS':
  suffix=' Reprise : évidements natifs P73/P75 autour des parcours puissance, quatre vis fraisées de guides à 90° et poses ajustées ; voir contrôle des BRep sauvegardés.'
  if suffix not in item['definition']:item['definition']+=suffix
 if touched:
  extras=[s for s in item.get('reserves',[]) if s!=old_definition and s!=('Contrôles : '+str(old_control)) and not s.startswith(('Détail :','Détail par jeu :'))]
  detail=item.get('detail') or item.get('detail_par_jeu') or []
  item['reserves']=[item['definition']]+(['Détail : '+' ; '.join(str(d['quantite'])+' × '+d['reference'] for d in detail)+'.'] if detail else [])+['Contrôles : '+item['controle_minimal']]+extras
 if identifier=='SEN-GNSS':
  item['reserves']=[s.replace('58 g groupés publiés dans le dossier ; inclusion antenne et câbles à clarifier avant total.','61,2 g nominaux : module G4 SKU12037 et antenne hélicoïdale, selon la page produit actuelle. Ancienne valeur générique 58 g conservée comme divergence documentaire ; aucune tolérance inventée.') for s in item.get('reserves',[])]
 if identifier=='MEC-REFROIDISSEMENT-JETSON':
  item['reserves']=[s.replace('Provision Holybro 190 g avionique inclut un refroidissement illustratif ; ne pas ajouter sa masse à cette provision.','Ancienne provision Holybro 190 g historique, exclue du bilan courant. La porteuse seule est comptée à 85 g ; les 72 g commerciaux du kit restent conditionnels, sans contribution.') for s in item.get('reserves',[])]

def refresh_geometry_labels():
 """Actualiser seulement les libellés hérités ; natifs et matrices inchangés."""
 for path,section in [(VER/'construction_prototype.json',None),(MEC/'manifest.json','prototype_cartographe')]:
  data=read(path);active=data[section] if section else data;changed=False
  for ref in active['references']:
   if ref['fichier']=='pieces/commerce/EQ_QS8S_B9310_Prototype.FCStd' and '42×24×15' in ref.get('limites',''):
    ref['limites_avant_reprise']=ref['limites']
    ref['limites']='Réservation extérieure documentée B9310 60,9×29,7×15,4 mm ; demi-corps, joint, capots, bornes et débattement non documentés. Voir orch_cao_masse_fabrication.json et orch_reprise_collisions.json.'
    changed=True
  if changed:
   active['libelles_actualises_par']='verification/orch_reprise_registres.py'
   path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n','utf-8')
