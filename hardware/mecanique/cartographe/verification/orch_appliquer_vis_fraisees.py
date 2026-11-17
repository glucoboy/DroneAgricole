"""Applique les paramètres documentés de fraisure, sans calcul de masse."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,os,sys,zipfile
import xml.etree.ElementTree as ET
import FreeCAD as App
from orch_integrate_cao import save_assembly
ROOT=Path(__file__).resolve().parents[4];MEC=ROOT/'hardware/mecanique/cartographe';VER=MEC/'verification'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text('utf-8-sig'))
proposal=read(VER/'orch_reprise_vis_fraisees.json')
assert proposal['finalisation_correcte']
assert not proposal['contre_verification_brep']['intersections_positives']
changes=[]
def update(file,names,expected,values):
 p=MEC/file;before=sha(p)
 expected_hash=proposal['contre_verification_brep']['entrees_sha256'][p.relative_to(ROOT).as_posix()]
 assert before==expected_hash,('Source différente de la proposition',file)
 doc=App.openDocument(str(p))
 for name in names:
  obj=doc.getObject(name);assert obj is not None,name
  for k,v in expected.items():
   actual=obj.Placement.Base.z if k=='PlacementZ' else getattr(obj,k).Value
   assert abs(actual-v)<1e-7,(file,name,k,actual,v)
  for k,v in values.items():
   if k=='PlacementZ':obj.Placement.Base.z=v
   else:setattr(obj,k,v)
  obj.touch()
 root=doc.Ensemble
 if 'LimiteGeometrique' not in root.PropertiesList:root.addProperty('App::PropertyString','LimiteGeometrique','Provenance')
 root.LimiteGeometrique='Reprise90deg depuis verification/orch_reprise_vis_fraisees.json ; tête théorique conservatriceØ6,72, contour réel Fabory et tolérances inconnus. Fraisure projetØ6,92 ; appui/tenue réels À valider. Masse fournisseur indépendante du volume du gabarit.'
 doc.recompute(None,True,True)
 fusion=None
 if '/commerce/' in file:
  fusion=doc.addObject('Part::MultiFuse','GabaritTete90');fusion.Shapes=[doc.Tige,doc.Tete];fusion.Refine=True
  root.removeObject(doc.Tige);root.removeObject(doc.Tete);root.addObject(fusion)
  doc.Tige.Visibility=False;doc.Tete.Visibility=False;fusion.Visibility=True
  doc.recompute(None,True,True)
 assert root.Shape.isValid() and len(root.Shape.Solids)==1,file
 errors=[o.Name for o in doc.Objects if any(s in ('Invalid','Error') for s in o.State)];assert not errors,errors
 if fusion:
  from orch_reprise_collisions import save_piece
  save_piece(doc,doc.Tete,fusion)
  with zipfile.ZipFile(p) as z:payload={n:z.read(n) for n in z.namelist()}
  gui=ET.fromstring(payload['GuiDocument.xml'])
  gui.find("ViewProviderData/ViewProvider[@name='Tige']/Properties/Property[@name='Visibility']/Bool").set('value','false')
  payload['GuiDocument.xml']=ET.tostring(gui,encoding='utf-8',xml_declaration=True)
  temp=p.with_suffix('.fraisure.tmp')
  with zipfile.ZipFile(temp,'w',compression=zipfile.ZIP_DEFLATED) as z:
   for name,data in payload.items():z.writestr(name,data)
  temp.replace(p)
 else:save_assembly(doc)
 changes.append({'fichier':file,'sha256_avant':before,'sha256_apres':sha(p),'objets':names,'avant':expected,'apres':values,'solide_unique_valide':True,'volume_apres_mm3':root.Shape.Volume})
for spec in proposal['proposition']['vis']:
 for file in spec['sources']:update(file,[spec['objet']],spec['avant'],spec['apres'])
for spec in proposal['proposition']['fraisures']:update(spec['source'],spec['objets'],spec['avant'],spec['apres'])
build=read(VER/'construction_prototype.json');poses=[]
for spec in proposal['proposition']['poses']:
 for name in spec['occurrences']:
  row=next(r for r in build['occurrences'] if r['parent']==spec['parent'] and r['occurrence']==name)
  assert abs(row['matrice'][11]-spec['avant_z_mm'])<1e-7
  matrix=list(row['matrice']);matrix[11]=spec['apres_z_mm']
  poses.append({'parent':row['parent'],'occurrence':name,'matrice_avant':row['matrice'],'matrice':matrix})
out={'lot':'ORCH-CAO-MASSE-1','date_utc':datetime.now(timezone.utc).isoformat(),'script_sha256':sha(__file__),'proposition_sha256':sha(VER/'orch_reprise_vis_fraisees.json'),'application':True,'natifs_modifies':changes,'changements_occurrences':poses,'finalisation_correcte':True,'qualification':'À valider','limites':proposal['limites']+proposal['cotes']['inconnues']}
(VER/'orch_reprise_vis_fraisees_application.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n','utf-8')
print(json.dumps({'natifs':len(changes),'poses_a_integrer':len(poses),'valides':True}),flush=True)
sys.stdout.flush();sys.stderr.flush();os._exit(0)
