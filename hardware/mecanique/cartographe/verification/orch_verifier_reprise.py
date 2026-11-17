"""Contre-vérification des BREP sauvegardés, dans un processus neuf, sans CAO écrite."""
from pathlib import Path
from datetime import datetime,timezone
import json,hashlib,os,sys
import FreeCAD as A
from read_brep_prototype import Reader
from orch_reprise_collisions import common,POSES,ROUTES
ROOT=Path(__file__).resolve().parents[4];MEC=ROOT/'hardware/mecanique/cartographe';VER=MEC/'verification'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text('utf-8-sig'))
build=read(VER/'construction_prototype.json');correction=read(VER/'orch_reprise_collisions.json')
rows={(o['parent'],o['occurrence']):o for o in build['occurrences'] if o['parent']!=build['assemblage']}
reader=Reader(MEC);shapes={key:reader.occurrence(row) for key,row in rows.items()}
inputs={r['fichier']:sha(MEC/r['fichier']) for r in build['references']}
inputs.update({p:sha(MEC/p) for p in build['sources_preservees']})
names=set(POSES)|set(ROUTES)|{r['occurrence'] for r in correction['ajouts_occurrences']}
if (VER/'orch_reprise_f20_application.json').exists():names.add('F20')
if (VER/'orch_reprise_vis_fraisees_application.json').exists():
 for r in read(VER/'orch_reprise_vis_fraisees_application.json')['changements_occurrences']:names.add(r['occurrence'])
if (VER/'orch_reprise_tetes_chc_application.json').exists():
 for r in read(VER/'orch_reprise_tetes_chc_application.json')['occurrences_inchangees']:names.add(r['occurrence'])
seen=set();collisions=[];tests=0
chc_checks=[]
if (VER/'orch_reprise_tetes_chc_application.json').exists():
 applied_chc=read(VER/'orch_reprise_tetes_chc_application.json')
 for change in applied_chc['natifs_modifies']:
  assert sha(MEC/change['fichier'])==change['sha256_apres']
  types,objects=reader.xml(change['fichier'])
  radius=float(objects['Tete']['Radius'].find('Float').get('value'))
  height=float(objects['Tete']['Height'].find('Float').get('value'))
  length=float(objects['Tige']['Height'].find('Float').get('value'))
  assert abs(radius-change['rayon_apres_mm'])<1e-8 and abs(height-change['hauteur_inchangee_mm'])<1e-8 and abs(length-change['longueur_tige_inchangee_mm'])<1e-8
  for obj,field in [('Tete','placement_tete'),('Tige','placement_tige')]:
   assert max(abs(a-b) for a,b in zip(reader.placement(change['fichier'],obj).toMatrix().A,change[field]))<1e-8
  chc_checks.append({'fichier':change['fichier'],'rayon_tete_mm':radius,'hauteur_tete_mm':height,'longueur_tige_mm':length,'placements_locaux_conserves':True})
 for occurrence in applied_chc['occurrences_inchangees']:
  key=(occurrence['parent'],occurrence['occurrence'])
  assert rows[key]['matrice']==occurrence['matrice_inchangee']
  chc_checks.append({'occurrence':key,'placement_global_conserve':True})
fraisure_checks=[]
if (VER/'orch_reprise_vis_fraisees_application.json').exists():
 applied=read(VER/'orch_reprise_vis_fraisees_application.json')
 for change in applied['natifs_modifies']:
  assert sha(MEC/change['fichier'])==change['sha256_apres']
  types,objects=reader.xml(change['fichier'])
  for name in change['objets']:
   properties=objects[name]
   values={k:(float(properties['Placement'].find('PropertyPlacement').get('Pz')) if k=='PlacementZ' else float(properties[k].find('Float').get('value'))) for k in change['apres']}
   assert all(abs(values[k]-v)<1e-7 for k,v in change['apres'].items())
   assert abs(abs(values['Radius2']-values['Radius1'])-values['Height'])<1e-7
   fraisure_checks.append({'fichier':change['fichier'],'objet':name,'parametres_sauvegardes':values,'angle_nominal_90deg':True})
 for change in applied['changements_occurrences']:
  key=(change['parent'],change['occurrence'])
  assert max(abs(a-b) for a,b in zip(rows[key]['matrice'],change['matrice']))<1e-7
  seat='Semelle' if change['occurrence'].startswith('Ancrage') else 'Interface'
  target=next(k for k,r in rows.items() if r['occurrence']==seat)
  distance=shapes[key].distToShape(shapes[target])[0];volume=common(shapes[key],shapes[target])
  assert distance<1e-6 and volume<1e-5,(key,distance,volume)
  fraisure_checks.append({'occurrence':key,'siege':target,'distance_mm':distance,'intersection_mm3':volume,'contact_gabarit_uniquement':True})
for key,row in rows.items():
 if row['occurrence'] not in names:continue
 print('BREP sauvegarde '+key[1],flush=True)
 for other in rows:
  pair=tuple(sorted([key,other]))
  if key==other or pair in seen:continue
  seen.add(pair);tests+=1;volume=common(shapes[key],shapes[other])
  if volume>1e-5:collisions.append({'a':key,'b':other,'intersection_mm3':volume})
result={'lot':'ORCH-CAO-MASSE-1','test_id':'T-REPRISE-COLLISIONS-01','date_utc':datetime.now(timezone.utc).isoformat(),
 'script_sha256':sha(__file__),'correction_sha256':sha(VER/'orch_reprise_collisions.json'),'construction_sha256':sha(VER/'construction_prototype.json'),
 'environnement':{'freecad':A.Version(),'os':'Windows','architecture':'amd64'},'natifs_sha256':inputs,
 'occurrences_lues':len(rows),'paires_examinees':tests,'focus':sorted(names),'interferences':collisions,
 'fraisures_sauvegardees':fraisure_checks,
 'tetes_chc_sauvegardees':chc_checks,
 'natifs_non_modifies':all(sha(MEC/p)==h for p,h in inputs.items()),'correction_geometrique_conforme':not collisions,
 'finalisation_correcte':True,'qualification':'À valider','lot_clos':False,
 'limites':correction['limites']+['Contrôle des occurrences touchées contre toutes les autres ; aucune qualification physique.']}
(VER/'controle_reprise_collisions.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n','utf-8')
print(json.dumps({'occurrences':len(rows),'paires':tests,'interferences':collisions}),flush=True)
sys.stdout.flush();sys.stderr.flush();os._exit(0)
