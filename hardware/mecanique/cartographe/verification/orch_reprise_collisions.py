"""Adaptateur FreeCAD de reprise des collisions, sans calcul de masse.

Explore en mémoire, puis applique la même définition aux natifs existants.
Les bornes externes de réservations ne deviennent pas des interfaces fabricant.
"""
from pathlib import Path
import argparse
import copy
import hashlib
import json
import os
import sys
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

ARGS=sys.argv[1:];sys.argv=[sys.executable]
import FreeCAD as A
import Part
from read_brep_prototype import Reader
from cable_workbench_prototype import bootstrap_paths,cable_geometry,_check_polyline
from orch_integrate_cao import save_assembly

ROOT=Path(__file__).resolve().parents[4]
MEC=ROOT/'hardware/mecanique/cartographe';VER=MEC/'verification'
BASE=ROOT/'.runtime/orch-cao-masse-1/reprise_baseline/hardware/mecanique/cartographe'
OUT=VER/'orch_reprise_collisions.json'
EPS=1e-5
POSES={'PM08':[5.5,-39,39],'Fusible_CA01':[37,-50,39],'UART_isole':[-78,-34.5,39]}
ROUTES={
 'F37_POS':[[74.5,-79,-40],[101,-89,-40],[128,-89,-40],[128,40,-40],[108,40,-51],[108,19,-51]],
 'F37_NEG':[[66.25,20,-16],[98,20,-16],[118,33,-16],[118,33,-51],[118,19,-51]],
 'F38_POS':[[108,-43,-51],[108,-66,-51],[98,-66,-17],[98,-66,52],[98,-94,52],[-65,-94,52],[-65,-73.75,55.89512218961],[-40,-73.75,55.89512218961]],
 'F38_NEG':[[118,-43,-51],[118,-79,-51],[106,-79,-17],[106,-79,52],[106,-104,52],[-77,-104,52],[-77,-50,52],[-58,-45.25,55.89512218961],[-40,-45.25,55.89512218961]],
 'F05_POS':[[6,-73.75,55.89512218961],[16.5,-73.75,55.89512218961],[16.5,-70,77],[69,-70,77],[69,-14,77],[69,-14,63]],
 'F05_NEG':[[6,-45.25,55.89512218961],[11,-45.25,55.89512218961],[11,-45.25,77],[45,-45.25,77],[45,14,77],[45,14,63]],
 'F08_AVAL':[[27,-43,59],[27,-43,65],[27,-35,73],[-94,-35,73],[-94,-35,117],[-94,-22,117],[-61,-22,117],[-61,-22,106]],
 'F08_AMONT':[[65,-28,63],[65,-28,70],[81,-28,70],[81,-70,70],[25,-70,70],[37,-70,51],[37,-63.5,51]],
}

def read(p):return json.loads(Path(p).read_text('utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n','utf-8')
def bb(s):
 b=s.BoundBox;return [b.XMin,b.YMin,b.ZMin,b.XMax,b.YMax,b.ZMax]
def overlap(a,b):return all(min(getattr(a,k+'Max'),getattr(b,k+'Max'))>max(getattr(a,k+'Min'),getattr(b,k+'Min'))+1e-8 for k in 'XYZ')
def common(a,b):
 if a.isNull() or b.isNull():return 0.
 if not overlap(a.BoundBox,b.BoundBox):return 0.
 return sum(a.common(p).Volume for p in (b.Solids if len(b.Solids)>30 else [b]) if overlap(a.BoundBox,p.BoundBox))
def save_piece(d,previous,final):
 save_assembly(d)
 path=Path(d.FileName)
 with zipfile.ZipFile(path) as z:payload={n:z.read(n) for n in z.namelist()}
 gui=ET.fromstring(payload['GuiDocument.xml']);providers=gui.find('ViewProviderData')
 old=next(v for v in providers if v.get('name')==previous.Name)
 old.find("Properties/Property[@name='Visibility']/Bool").set('value','false')
 if not any(v.get('name')==final.Name for v in providers):
  new=copy.deepcopy(old);new.set('name',final.Name)
  new.find("Properties/Property[@name='Visibility']/Bool").set('value','true');providers.append(new)
 providers.set('Count',str(len(providers)));payload['GuiDocument.xml']=ET.tostring(gui,encoding='utf-8',xml_declaration=True)
 temp=path.with_suffix('.reprise.tmp')
 with zipfile.ZipFile(temp,'w',compression=zipfile.ZIP_DEFLATED) as z:
  for n,data in payload.items():z.writestr(n,data)
 temp.replace(path)
def run(apply):
 bootstrap_paths()
 # Charger les véritables classes de proxies avant restauration App : Draft
 # n'expose pas ses ViewProviders lorsqu'aucune fenêtre GUI n'est initialisée.
 import Draft
 from draftviewproviders.view_wire import ViewProviderWire
 Draft.ViewProviderWire=ViewProviderWire
 from freecad.cables import wireFlex,archCable
 build=read(VER/'construction_prototype.json')
 rows={o['occurrence']:copy.deepcopy(o) for o in build['occurrences'] if o['parent']!=build['assemblage']}
 reader=Reader(MEC);shapes={n:reader.occurrence(o) for n,o in rows.items()}
 changed=set(POSES)|set(ROUTES)|{'F08_AMONT','F08_AVAL'}
 before={n:shapes[n].copy() for n in changed}
 files={rows[n]['source']:sha(MEC/rows[n]['source']) for n in changed}
 changes=[];checks=[];documents=[]
 for n,xyz in POSES.items():
  row=rows[n];matrix=list(A.Placement(A.Vector(*xyz),A.Rotation(A.Vector(0,0,1),180) if n=='PM08' else A.Rotation()).toMatrix().A)
  target=dict(row,matrice=matrix);shapes[n]=reader.occurrence(target)
  changes.append({'parent':row['parent'],'occurrence':n,'matrice_avant':row['matrice'],'matrice':matrix})
  row['matrice']=matrix
 for n in sorted(changed-set(POSES)):
  row=rows[n];d=A.openDocument(str(MEC/row['source']));documents.append(d)
  w=d.getObject('Wire');c=d.getObject('Cable')
  if w.Proxy is None or c.Proxy is None:raise ValueError('Proxies natifs non restaurés : '+n)
  points=[list(w.Placement.multVec(v)) for v in w.Points]
  # Points de départ/arrivée suivent l'équipement déplacé ; le reste du chemin
  # reste sur ses retenues. Les interfaces électriques non cotées restent ouvertes.
  if n in ROUTES:points=ROUTES[n]
  elif n=='F08_AMONT':
   for p in points[-2:]:p[0]+=8
  elif n=='F08_AVAL':
   points[0][0]+=8
  if n=='F05_NEG':c.BaseWireFilletRadius=4.5
  if n=='F38_POS':c.BaseWireFilletRadius=8
  if n=='F08_AVAL':c.BaseWireFilletRadius=6
  _check_polyline([A.Vector(*p) for p in points],c.ProfilExterieur.DiametreExterieur.Value,c.BaseWireFilletRadius.Value)
  w.Points=[w.Placement.inverse().multVec(A.Vector(*p)) for p in points]
  w.touch();c.touch();d.recompute(None,True,True);data=cable_geometry(c)
  if not data['solide_valide'] or data['solides']!=1 or data['erreurs']:raise ValueError((n,data))
  shapes[n]=c.Shape.copy()
  ends=[v.Point for v in w.Shape.Vertexes]
  if any(min((v-A.Vector(*p)).Length for v in ends)>1e-6 for p in [points[0],points[-1]]):raise ValueError('Extrémité recalculée différente : '+n)
  checks.append(dict(occurrence=n,points_mm=points,controle=data))
  if apply:save_assembly(d)
 print('Parcours recalcules',len(checks),flush=True)
 # Dégager les seuls guides projet traversés par les nouveaux parcours : outils
 # dérivés des solides extérieurs recalculés, marge de passage nominale0,5mm.
 fabricated=[]
 for name in ['P73_Guide','P75_Cadre','Isolation']:
  row=rows[name];source=MEC/row['source'];files[row['source']]=sha(source)
  d=A.openDocument(str(source));documents.append(d);root=d.Ensemble
  visible=[o for o in root.Group if hasattr(o,'Shape') and not o.Shape.isNull() and o.Visibility]
  assert len(visible)==1,(name,[o.Name for o in visible]);previous=visible[0]
  tools=[]
  if name=='Isolation':
   for i,(x,y) in enumerate([(-43.95,-59.5),(9.95,-59.5)]):
    tool=d.addObject('Part::Cylinder','PassagePM08Reprise'+str(i));tool.Radius=1.7;tool.Height=5;tool.Placement.Base=A.Vector(x,y,-1);tools.append(tool)
    recess=d.addObject('Part::Cylinder','LamageDessousPM08Reprise'+str(i));recess.Radius=2.9;recess.Height=.6;recess.Placement.Base=A.Vector(x,y,-.1);tools.append(recess)
  else:
   for n in sorted(changed):
    if n not in ROUTES:continue
    if common(shapes[n],shapes[name])<=EPS:continue
    print('Intersection '+name+'/'+n+' : '+str(bb(shapes[n].common(shapes[name]))),flush=True)
    global_tool=shapes[n].makeOffsetShape(.5,.001)
    local_pose=A.Placement(A.Matrix(*row['matrice'])).inverse();global_tool.Placement=local_pose.multiply(global_tool.Placement)
    tool=d.addObject('Part::Feature','Passage_'+n+'_Reprise');tool.Shape=global_tool
    tool.addProperty('App::PropertyString','SourceParcours','Provenance');tool.SourceParcours=rows[n]['source']
    tool.addProperty('App::PropertyLength','JeuNominal','Provenance');tool.JeuNominal=.5;tools.append(tool)
  if tools:
   print('Decoupe '+name+' : '+str([o.Name for o in tools]),flush=True)
   union=tools[0]
   if len(tools)>1:
    union=d.addObject('Part::MultiFuse','OutilsPassageReprise');union.Shapes=tools
   final=d.addObject('Part::Cut','ResultatPassagesReprise');final.Base=previous;final.Tool=union;final.Refine=True
   root.removeObject(previous);root.addObject(final)
   for o in tools+[union,previous]:o.Visibility=False
   final.Visibility=True;d.recompute()
   assert final.Shape.isValid() and len(final.Shape.Solids)==1,(name,'guide déconnecté ou invalide')
   shapes[name]=final.Shape.copy();shapes[name].Placement=A.Placement(A.Matrix(*row['matrice'])).multiply(shapes[name].Placement)
   changed.add(name);before[name]=reader.occurrence(row)
   fabricated.append({'occurrence':name,'fichier':row['source'],'volume_avant_mm3':previous.Shape.Volume,'volume_apres_mm3':final.Shape.Volume,'solide_unique_valide':True,'outils':[o.Name for o in tools]})
   if apply:save_piece(d,previous,final)
 print('Supports repris',fabricated,flush=True)
 additions=[]
 for i,(x,y) in enumerate([(-43.95,-59.5),(9.95,-59.5)]):
  for kind,source,z in [('Vis','EQ_ISO4762_M3x12_Prototype',36.7),('RondelleDessus','EQ_ISO7089_M3_Prototype',42),('Ecrou','EQ_ISO10511_M3_Prototype',42.5)]:
   n=kind+'PM08Reprise'+str(i);rotation=A.Rotation(A.Vector(1,0,0),180) if kind=='Vis' else A.Rotation()
   row={'parent':'sous_assemblages/SA03_Prototype_Energie.FCStd','occurrence':n,'source':'pieces/commerce/'+source+'.FCStd','objet_source':'Ensemble','matrice':list(A.Placement(A.Vector(x,y,z),rotation).toMatrix().A),'bom_ids':['MEC-SUPPORTS-ENERGIE']}
   rows[n]=row;shapes[n]=reader.occurrence(row);before[n]=Part.Shape();changed.add(n);additions.append(row)
 hits=[];new=[];removed=[]
 for n in sorted(changed):
  # Ces trois reprises enlèvent seulement de la matière, à pose inchangée.
  # Leur rencontre avec les nouveaux câbles/fixations est déjà évaluée depuis
  # ces occurrences ; aucun volume ajouté ne peut créer une autre collision.
  if n in ['P73_Guide','P75_Cadre','Isolation']:continue
  print('Controle '+n,flush=True)
  for other,s in shapes.items():
   if n==other or (other in changed and other<n):continue
   v=common(shapes[n],s)
   v0=common(before[n],before.get(other,s))
   if v>EPS:hits.append(dict(a=n,b=other,intersection_mm3=v,avant_mm3=v0))
   if v>v0+EPS:new.append(dict(a=n,b=other,intersection_mm3=v,avant_mm3=v0))
   if v0>EPS and v<=EPS:removed.append(dict(a=n,b=other,avant_mm3=v0))
 result={'lot':'ORCH-CAO-MASSE-1','date_utc':datetime.now(timezone.utc).isoformat(),
  'statut':'Implémenté' if apply else 'Planifié','qualification':'À valider','application':apply,
  'script_sha256':sha(__file__),'changements_occurrences':changes,'ajouts_occurrences':additions,'parcours':checks,'pieces_reprises':fabricated,
  'interferences_restantes':hits,'interferences_nouvelles':new,'interferences_supprimees':removed,
  'entrees_avant_sha256':files,'finalisation_correcte':True,
  'limites':['QS8 : parcours arrêtés à 0,55mm de l’enveloppe externe documentée, au lieu de pénétrer un volume plein ; les demi-corps, soudures et segments de raccordement non documentés restent absents et bloquants.',
   'PM08 : aucune réduction de diamètre de câble ni attribution arbitraire de polarité aux sorties du carter.',
   'PM08 : préassembler module/plateau hors châssis, vis M3x12 depuis dessous dans lamages Ø5,8 profondeur0,5mm, rondelles et écrous au-dessus. Puis monter P64 sur ses ancrages ; aucun accès outil sous P64 installé revendiqué. Web G10 restant2,3mm, tenue et tolérances À valider.',
   'La correction des interférences ne qualifie pas les interfaces électriques, tolérances ou la tenue physique.']}
 dump(OUT if apply else ROOT/'.runtime/orch-cao-masse-1/reprise_collisions_exploration.json',result)
 for d in documents:A.closeDocument(d.Name)
 print(json.dumps({'application':apply,'supprimees':len(removed),'restantes':hits,'nouvelles':new},ensure_ascii=False),flush=True)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--apply',action='store_true');args=p.parse_args(ARGS)
 run(args.apply);sys.stdout.flush();sys.stderr.flush();os._exit(0)
