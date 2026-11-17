"""Synchroniser les métadonnées des seuls parcours repris avec les natifs sauvegardés."""
from pathlib import Path
import json,sys,hashlib,os
import FreeCAD as A
import Part
from cable_workbench_prototype import bootstrap_paths,cable_geometry
bootstrap_paths()
import Draft
from draftviewproviders.view_wire import ViewProviderWire
Draft.ViewProviderWire=ViewProviderWire
from freecad.cables import wireFlex,archCable
ROOT=Path(__file__).resolve().parents[4];MEC=ROOT/'hardware/mecanique/cartographe';VER=MEC/'verification'
def read(p):return json.loads(Path(p).read_text('utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
data=read(VER/'routes_prototype.json');reprise=read(VER/'orch_reprise_collisions.json')
ids={p['occurrence'] for p in reprise['parcours']}
if (VER/'orch_reprise_f20_application.json').exists() and read(VER/'orch_reprise_f20_application.json').get('application_root'):ids.add('F20')
checks=[]
for row in data['routes']:
 if row['id'] not in ids:continue
 path=MEC/row['fichier'];before=sha(path);doc=A.openDocument(str(path));c=doc.getObject(row['objet_cable']);w=c.Base
 assert c.Proxy is not None and w.Proxy is not None
 doc.recompute();points=[list(w.Placement.multVec(v)) for v in w.Points];geometry=cable_geometry(c)
 assert geometry['solide_valide'] and geometry['continuite'] and not geometry['erreurs']
 row.update(geometry);row['points_mm']=points;row['rayon_courbure_mm']=geometry['rayon_demande_mm'];row['diametre_mm']=geometry['diametre_exterieur_mm']
 row['longueur_trace_mm']=Part.makePolygon([A.Vector(*p) for p in points]).Length
 row['preuve_reprise']='verification/orch_reprise_collisions.json' if row['id']!='F20' else 'verification/orch_reprise_f20.json'
 assert before==sha(path);checks.append({'id':row['id'],'sha256':before,'parcours_valide':True})
 A.closeDocument(doc.Name)
(VER/'routes_prototype.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n','utf-8')
print(json.dumps({'parcours_actualises':checks}),flush=True);os._exit(0)
