"""Adaptateur FreeCAD : paramètres C++ vers natifs, mesures BRep sur copie seulement.
Recette : Python FreeCAD -B autonomie_cao.py generate|check|reopen fichier_params index
Chaque appel dédié doit être borné à60s ; aucun constructeur source modifié.
"""
from pathlib import Path
import sys, os, json, hashlib, traceback
ROOT=Path(__file__).resolve().parents[5]
OUT=Path(__file__).resolve().parent
COPY=ROOT/'hardware/mecanique/cartographe_faisceaux_autonome'
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
sys.path[:0]=[str(COPY/'verification'),str(ROOT/'.agents/skills/electromechanical-integration/scripts')]
import FreeCAD as App
import Part
from read_brep_prototype import Reader
from freecad_geometry import inspect_route,inspect_solid,rebuild_cable_in_isolated_document
def read(p):return json.loads(Path(p).read_text('utf-8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,d):Path(p).write_text(json.dumps(d,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
def gui():
 import FreeCADGui as Gui
 Gui.showMainWindow();Gui.getMainWindow().hide()
 import cable_workbench_prototype as builder
 return builder,builder.bootstrap_paths()
def path(c):return COPY/'verification/candidats'/ (c['id']+'.FCStd')
def report(c):return OUT/('autonomie_'+c['id']+'.json')
def gap(a,b):return sum(max(0,getattr(a,k+'Min')-getattr(b,k+'Max'),getattr(b,k+'Min')-getattr(a,k+'Max'))**2 for k in 'XYZ')**.5
def generate(c):
 result={'id':c['id'],'parameters':c,'parameters_sha256':sha(sys.argv[2]),'complete':False}
 if not c['polyline_feasible']:
  result.update(status='NON_CONFORME',reason='rayon impossible sur segments proposés',generation='not_executed',complete=True);write(report(c),result);return
 builder,env=gui();result['environment']=env
 doc=App.newDocument(c['id'].replace('-','m'))
 from freecad.cables import compoundPath,archCable
 low,lw=builder.make_native_cable(doc,None,'Mobile',c['lower_points_mm'],5.5,c['radius_mobile_mm'])
 top,tw=builder.make_native_cable(doc,None,'Fixe',c['upper_points_mm'],5.5,c['radius_fixed_mm'])
 cp=compoundPath.make_compoundpath([lw,tw]);cp.ConnectionOffsetDist=0;cp.PathType='Complex';doc.recompute()
 cable=archCable.makeCable(baseobj=cp,profileobj=low.ProfilExterieur,name='Cable')
 cable.addProperty('App::PropertyLink','ProfilExterieur','Encombrement');cable.ProfilExterieur=low.ProfilExterieur
 cable.StrippedWireLength=0;cable.ShowSubLines=False
 result['fresh']=rebuild_cable_in_isolated_document(doc,cable)
 result['mobile']=inspect_route(lw.Shape.Wires[0],minimum_radius_mm=48,start_axis=c['start_axis'],end_axis=[0,0,-1],start_position=c['lower_points_mm'][0],end_position=[96,-54,75])
 result['fixed']=inspect_route(tw.Shape.Wires[0],minimum_radius_mm=22,start_axis=[0,0,1],end_axis=[0,-1,0],start_position=[96,-54,75],end_position=[7,-79.95,140.5])
 result['whole']=inspect_route(cp.Shape.Wires[0],minimum_radius_mm=22,start_axis=c['start_axis'],end_axis=[0,-1,0],start_position=c['lower_points_mm'][0],end_position=[7,-79.95,140.5])
 result['length_mm']=cp.Shape.Length;result['analytic_delta_mm']=cp.Shape.Length-c['analytic_length_mm']
 for o in doc.Objects:
  if hasattr(o,'Visibility'):o.Visibility=False
 cable.Visibility=True;cable.ViewObject.ShapeColor=(0.65,0.2,0.85)
 dest=path(c);dest.parent.mkdir(parents=True,exist_ok=True);doc.recompute();doc.saveAs(str(dest))
 result.update(file=str(dest.relative_to(COPY)),sha256=sha(dest),object_cable=cable.Name,object_mobile=low.Name,object_fixed=top.Name,object_path=cp.Name,complete=True,generation='passed')
 write(report(c),result);print(c['id'],result['length_mm'],result['fresh']['status'],flush=True)
def reopen(c):
 builder,env=gui();doc=App.openDocument(str(path(c)))
 if any(d.FileName and not Path(d.FileName).resolve().is_relative_to(COPY) for d in App.listDocuments().values()):raise RuntimeError('Hors copie')
 result=read(report(c));cab=doc.getObject(result.get('object_cable','Cable002'))
 if cab.Base.Name!=result.get('object_path','CompoundPath') or abs(cab.Base.Shape.Length-result['length_mm'])>1e-5:raise RuntimeError('Mauvais câble complet')
 saved=cab.Shape.copy()
 for child in cab.Base.Links:child.touch()
 fresh=rebuild_cable_in_isolated_document(doc,cab)
 result['reopened']={'fresh':fresh,'saved_solid':inspect_solid(saved),'removed_mm3':saved.cut(cab.Shape).Volume,'added_mm3':cab.Shape.cut(saved).Volume,'length_mm':cab.Base.Shape.Length,'errors':[o.Name for o in doc.Objects if any(s in ('Error','Invalid') for s in o.State)]}
 write(report(c),result)
def transform(c):
 a=c['rotation_xyz_deg'];r=App.Rotation(App.Vector(0,0,1),a[2]).multiply(App.Rotation(App.Vector(0,1,0),a[1])).multiply(App.Rotation(App.Vector(1,0,0),a[0]));p=App.Vector(*c['rotation_center_mm']);d=App.Vector(*c['translation_mm']);return App.Placement(p+d-r.multVec(p),r)
def measured_pair(a,b):
 # Somme par solide : borne supérieure du recouvrement si composé chevauchant.
 distance=None;volume=0.;checks=0
 for _,_,s in sorted((gap(a.BoundBox,s.BoundBox),i,s) for i,s in enumerate(b.Solids)):
  lower=gap(a.BoundBox,s.BoundBox)
  measured=None
  if lower<1e-7 or distance is None or lower<=distance+1e-6:
   measured=a.distToShape(s)[0]
   distance=min(distance if distance is not None else 1e99,measured)
  if lower<1e-7 and measured<=1e-7:
   v=a.common(s);checks+=1
   if not v.isNull() and not v.isValid():raise RuntimeError('boolean invalide')
   volume+=v.Volume
 return {'volume_mm3':volume,'distance_mm':distance,'boolean_count':checks,'method':'Distance BRep positive certifie séparation; common par solide pour contact/intersection. Somme volumique borne supérieure.'}
def check(c):
 from verifier_partition import check_partition
 check_partition(c)
def check_full(c):
 reader=Reader(COPY);result=read(report(c));object_name=result.get('object_cable','Cable002');a=reader.shape(result['file'],object_name);build=read(COPY/'verification/construction_prototype.json')
 props=reader.xml(result['file'])[1][object_name];base=props['Base'].find('Link').get('value')
 if base!=result.get('object_path','CompoundPath') or abs(reader.shape(result['file'],base).Length-result['length_mm'])>1e-5:raise RuntimeError('Mauvais câble complet')
 kin=read(OUT/'recherche_suspension.json')['kinematics'];pose=transform(c)
 checks=[];minimum=None;noncontact=None;near=None;count=0;bb=0
 for row in build['occurrences']:
  if not row['parent'].startswith('sous_assemblages/') or row['occurrence']=='F16':continue
  name=row['occurrence'];s=reader.occurrence(row);count+=1
  moving=('SA04' in row['parent'] and name in kin['mobile_sa04_occurrences']) or ('SA07' in row['parent'] and name in kin['mobile_sa07_occurrences'])
  if moving:s.Placement=pose.multiply(s.Placement)
  lower=gap(a.BoundBox,s.BoundBox)
  if lower>0:bb+=1
  if lower>1e-6 and noncontact is not None and lower>noncontact+1e-6:continue
  try:
   check=measured_pair(a,s);check.update(obstacle=row['parent']+'#'+name,moving=moving)
   if check['distance_mm'] is not None and (minimum is None or check['distance_mm']<minimum):minimum=check['distance_mm'];near=name
   if name not in ('ConnecteurF16Camera','ConnecteurF16TypeA') and check['distance_mm'] is not None:noncontact=min(noncontact if noncontact is not None else 1e99,check['distance_mm'])
   checks.append(check)
  except Exception as ex:checks.append({'obstacle':name,'error':str(ex)})
 result['collision']={'complete':True,'object_cable':object_name,'path_length_verified_mm':result['length_mm'],'occurrences':count,'bbox_disjoint':bb,'pairs':checks,'collisions':sum(p.get('volume_mm3',0)>1e-4 for p in checks),'unknown':sum('error'in p for p in checks),'minimum_mm':minimum,'non_connector_minimum_mm':noncontact,'nearest':near,'tolerance_volume_mm3':1e-4,'clearance_acceptance_mm':None,'scope':'Toutes occurrences source; F16 original remplacé. Guides historiques conservés pour détecter le besoin de déplacement. Eléments mobiles transformés seulement aux poses données. Autres câbles inchangés, aucune admissibilité dynamique globale.'}
 write(report(c),result);print(c['id'],result['collision']['collisions'],flush=True)
if __name__=='__main__':
 try:
  candidates=read(sys.argv[2])['candidates'];globals()[sys.argv[1]](candidates[int(sys.argv[3])]);sys.stdout.flush();sys.stderr.flush();os._exit(0)
 except Exception:traceback.print_exc();sys.stdout.flush();sys.stderr.flush();os._exit(2)
