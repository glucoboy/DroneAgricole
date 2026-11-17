"""Contrôle indépendant des fichiers sauvegardés du prototype, sans écriture CAO."""
from pathlib import Path
import FreeCAD as A
from cable_workbench_prototype import bootstrap_paths
bootstrap_paths()
import Draft
from draftviewproviders.view_wire import ViewProviderWire
Draft.ViewProviderWire=ViewProviderWire
from freecad.cables import wireFlex,archCable
import json, hashlib, itertools, platform, time, math, os, sys
from datetime import datetime, timezone
MEC=Path(__file__).resolve().parents[1]
VER=MEC/'verification'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def bb(s):
 b=s.BoundBox
 return [b.XMin,b.YMin,b.ZMin,b.XMax,b.YMax,b.ZMax]
def intersects(a,b):
 x,y=a.BoundBox,b.BoundBox
 return all(min(getattr(x,n+'Max'),getattr(y,n+'Max'))-max(getattr(x,n+'Min'),getattr(y,n+'Min'))>1e-5 for n in 'XYZ')
proof=json.loads((VER/'construction_prototype.json').read_text(encoding='utf-8'))
assert proof['finalisation_correcte'],'Construction non finalisée'
before={p:sha(MEC/p) for p in set([r['fichier'] for r in proof['references']]+list(proof['sources_preservees']))}
doc=A.openDocument(str(MEC/proof['assemblage']))
errors=[]; links=[]
for d in list(A.listDocuments().values()):
 if any(r['fichier']==Path(d.FileName).relative_to(MEC).as_posix() for r in proof['references']):
  d.recompute()
  for o in d.Objects:
   if any(t in ['Invalid','Error'] for t in o.State):errors.append({'document':d.Name,'objet':o.Name,'etat':list(o.State)})
   if o.TypeId=='App::Link':
    links.append((d,o))
    if o.LinkedObject is None:errors.append({'document':d.Name,'objet':o.Name,'etat':'Lien non résolu'})
matrix_errors=[]
for expected in proof['occurrences']:
 d=next(x for x in A.listDocuments().values() if Path(x.FileName).resolve()==(MEC/expected['parent']).resolve())
 o=d.getObject(expected['occurrence'])
 if o is None or o.LinkedObject is None:continue
 if Path(o.LinkedObject.Document.FileName).resolve()!=(MEC/expected['source']).resolve() or o.LinkedObject.Name!=expected['objet_source'] or any(abs(a-b)>1e-7 for a,b in zip(o.LinkPlacement.toMatrix().A,expected['matrice'])):
  matrix_errors.append(expected['occurrence'])

# Contrôler les collisions entre équipements ajoutés ; les fixations/contact
# fonctionnels et les réservations filaires sont séparés de ce périmètre.
names={
 'SA02_Prototype_Batterie':['Pack6S20Ah','BMS','QS8_manuel','Protection_amont'],
 'SA03_Prototype_Energie':['PM08','PDB','UART_isole','Fusible_CA01'],
 'SA04_Prototype_Perception':['EQ_Airy_Occurrence','EQ_Basler_Occurrence','ObjectifFujinon'],
 'SA05_Prototype_Avionique':['CA01','Holybro6XOrin','OrinFan','SSD','microSD'],
 'SA06_Prototype_Navigation':['GNSS_Helical','AntenneRF0','AntenneRF1','BoutonBuzzerLED']}
major=[]
for dn,object_names in names.items():
 d=A.getDocument(dn)
 for name in object_names:
  o=d.getObject(name);assert o is not None,(dn,name)
  major.append((dn+'/'+name,o.Shape.copy()))
collisions=[]; candidates=[]; connection_envelopes=[]
for (n,a),(m,b) in itertools.combinations(major,2):
 if not intersects(a,b):continue
 # Le composé fabricant détaillé est contrôlé séparément par ses solides
 # proches de l'autre équipement pour éviter un booléen global inutile.
 volume=0.0; solids_hit=[]
 if len(a.Solids)>100 or len(b.Solids)>100:
  detailed,other=(a,b) if len(a.Solids)>100 else (b,a)
  for index,s in enumerate(detailed.Solids):
   if intersects(s,other):
    v=s.common(other).Volume;volume+=v
    if v>1e-6:solids_hit.append({'indice_derive':index,'volume_mm3':round(v,6)})
 else:volume=a.common(b).Volume
 candidates.append({'a':n,'b':m,'volume_commun_mm3':round(volume,6),'solides_touches':solids_hit})
 if volume>1e-4:
  kept=[i for i in range(2079) if i not in proof['derivation_holybro']['solides_source_retires']]
  original_allowed={1401} if m.endswith('/SSD') else {2071,2072} if m.endswith('/microSD') else set()
  allowed={kept.index(i) for i in original_allowed}
  verified_source=proof['sources_preservees'].get('pieces/commerce/EQ_Holybro_Pixhawk_Jetson_Baseboard_candidat.FCStd')=='2cade6f15f64465ef031ff52a14f7328d2acbe05b04614fecd60dd3327be299d'
  if n.endswith('/Holybro6XOrin') and allowed and verified_source and solids_hit and all(s['indice_derive'] in allowed for s in solids_hit):
   connection_envelopes.append(dict(candidates[-1],statut='À valider',interpretation='Interférence limitée aux formes du connecteur attendu ; engagement réel, détrompeur et contacts non démontrés.'))
  else:collisions.append(candidates[-1])
print(json.dumps({'collisions_equipements':collisions}),flush=True)
structure_doc=A.getDocument('SA01_Prototype_Structure')
extra=[('SA01_Prototype_Structure/'+n,structure_doc.getObject(n).Shape.copy()) for n in ['ESC_'+str(i) for i in range(1,5)]]
nav=A.getDocument('SA06_Prototype_Navigation')
extra += [('SA06_Prototype_Navigation/'+n,nav.getObject(n).Shape.copy()) for n in ['SupportGNSS','SupportSecurite']]
energy=A.getDocument('SA03_Prototype_Energie')
extra.append(('SA03_Prototype_Energie/Isolation',energy.Isolation.Shape.copy()))
structure_collisions=[]
for name,shape in major+extra:
 for o in structure_doc.Ensemble.Group:
  if not o.Name.startswith('OEM_') or not intersects(shape,o.Shape):continue
  volume=shape.common(o.Shape).Volume
  if volume>1e-4:structure_collisions.append({'equipement':name,'structure':o.Name,'volume_commun_mm3':round(volume,6)})
# Les hélices sont alignées sur l'axe et le plan d'appui rotor, pas sur la bbox du moteur.
prop_checks=[]
rotors=[]
for i,(x,y) in enumerate([(-229.906638,-229.906638),(229.906638,229.906638),(-229.906638,229.906638),(229.906638,-229.906638)],1):
 p=structure_doc.getObject('Helice_'+str(i)).LinkPlacement.Base
 prop_checks.append({'helice':i,'axe_et_appui_conformes':abs(p.x-x)<1e-6 and abs(p.y-y)<1e-6 and abs(p.z-65.5)<1e-6})
 o=structure_doc.getObject('Helice_'+str(i))
 radius=max(math.hypot(v.Point.x-p.x,v.Point.y-p.y) for v in o.Shape.Vertexes)
 axis=o.LinkPlacement.Rotation.multVec(A.Vector(0,0,1))
 rotors.append({'helice':i,'centre_mm':[p.x,p.y,p.z],'axe':[axis.x,axis.y,axis.z],'rayon_enveloppe_modele_mm':radius})
separations=[]
for a,b in itertools.combinations(rotors,2):
 distance=math.hypot(a['centre_mm'][0]-b['centre_mm'][0],a['centre_mm'][1]-b['centre_mm'][1])
 gap=distance-a['rayon_enveloppe_modele_mm']-b['rayon_enveloppe_modele_mm']
 separations.append({'rotors':[a['helice'],b['helice']],'entraxe_projete_mm':distance,'jeu_disques_modeles_mm':gap,'separes_nominalement':gap>0})
# Vérifier jeu au sol / hélices à partir des poses effectivement sauvegardées.
structure=A.getDocument('SA01_Prototype_Structure').Ensemble
root=doc.Ensemble
report={'date':datetime.now().date().isoformat(),'date_utc':datetime.now(timezone.utc).isoformat(),'exigences':['MEC-ARC-001','MEC-INT-001','MEC-MAS-001','CAB-CARTO-001'],
 'script_sha256':sha(__file__),'construction_sha256':sha(VER/'construction_prototype.json'),'natifs_sha256':before,
 'environnement':{'os':platform.platform(),'architecture':platform.machine(),'freecad':A.Version()},
 'assemblage':proof['assemblage'],'sha256':sha(MEC/proof['assemblage']),
 'protocole':{'reouverture':'Nouveau processus FreeCAD, fichiers finaux et liens externes','recalcul':'Chaque document nouvellement construit',
             'collision':'Équipements majeurs listés, présélection boîtes puis intersection exacte OCCT, seuil numérique1e-4mm3',
             'hors_perimetre_collision':['Connexions et contacts montés','Faisceaux contrôlés séparément dans controle_faisceaux_prototype.json','Détail interne sources fabricant','Débattements dynamiques et tolérances']},
 'nombre_documents_ouverts':len(A.listDocuments()),'liens_controles':len(links),'poses_controlees':len(proof['occurrences']),
 'erreurs_recalcul_liens':errors,'erreurs_poses':matrix_errors,'equipements_controles':len(major),
 'collisions_equipements':collisions,'paires_bbox_recoupantes':candidates,
 'interferences_enveloppes_connexion':connection_envelopes,
 'collisions_structure':structure_collisions,'controle_helices':prop_checks,
 'rotors':rotors,'separation_rotors':separations,
 'compatibilite_helices':'À valider : variante1555, alésages/vis et diamètre fabricant non résolus ; la séparation des disques modélisés ne démontre pas cette compatibilité.',
 'enveloppe_drone_mm':bb(root.Shape),
 'garde_sol_objectif_mm':round(A.getDocument('SA04_Prototype_Perception').ObjectifFujinon.Shape.BoundBox.ZMin-structure.Shape.BoundBox.ZMin,3),
 'sources_non_modifiees':all(sha(MEC/p)==h for p,h in proof['sources_preservees'].items()),
 'fichiers_non_modifies_par_verification':all(sha(MEC/p)==h for p,h in before.items()),
 'validation_physique':False,'qualification':'À valider',
 'limites':['Tolérances, interfaces non publiées, cotes de réservation et accès outil à vérifier sur matériel',
            'Pas de masse/centrage/endurance, tenue, thermique, radio, électrique ou vol qualifié'],
 'finalisation_correcte':True}
report['conclusion']='conforme pour les contrôles déclarés' if not(errors or matrix_errors or collisions or structure_collisions) and all(p['axe_et_appui_conformes'] for p in prop_checks) and report['sources_non_modifiees'] else 'non conforme'
if report['conclusion'].startswith('conforme') and connection_envelopes:report['conclusion']='Liens et placements conformes ; aucune collision hors interfaces déclarées, engagements SSD/microSD À valider'
(VER/'controle_assemblage_prototype.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:report[k] for k in ['conclusion','liens_controles','equipements_controles','garde_sol_objectif_mm','enveloppe_drone_mm']}),flush=True)
for d in list(A.listDocuments().values()):A.closeDocument(d.Name)
sys.stdout.flush();sys.stderr.flush();os._exit(0)
