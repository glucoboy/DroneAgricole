import sys,os,json,hashlib
sys.path.insert(0,r'C:/Program Files/FreeCAD 1.1/lib');os.add_dll_directory(r'C:/Program Files/FreeCAD 1.1/bin')
import FreeCAD as A,Part,Import
from pathlib import Path
root=Path(__file__).resolve().parent.parent;src=root/'sources_fabricants/ca01_modeles_connecteurs';out=root/'exports/ca01_modeles3d_20261001';out.mkdir(exist_ok=True)
pcs=root/'pieces/commerce';pcs.mkdir(exist_ok=True)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def box(o):
 b=o.Shape.BoundBox;return [b.XMin,b.YMin,b.ZMin,b.XMax,b.YMax,b.ZMax]
def metadata(doc,label):
 doc.Label=label
 x=doc.addObject('App::FeaturePython','Provenance');x.addProperty('App::PropertyString','Statut').Statut='À valider';x.addProperty('App::PropertyString','Limites').Limites='Modèle détaillé candidat ; non OEM ; géométrie interne simplifiée ; ne qualifie ni montage ni fabrication.'
 return x
def set_color(o,color):
 if o.ViewObject: o.ViewObject.ShapeColor=color
def set_hide(o):
 if o.ViewObject: o.ViewObject.Visibility=False
def cube(doc,name,x,y,z,a,b,c,color):
 o=doc.addObject('Part::Box',name);o.Length=a;o.Width=b;o.Height=c;o.Placement.Base=A.Vector(x,y,z);set_color(o,color);return o
def cyl(doc,name,x,y,z,r,h,direction=(0,0,1),color=(0.76,0.76,0.78)):
 o=doc.addObject('Part::Cylinder',name);o.Radius=r;o.Height=h;o.Placement=A.Placement(A.Vector(x,y,z),A.Rotation(A.Vector(0,0,1),A.Vector(*direction)));set_color(o,color);return o
def cut(doc,name,base,tool,color):
 o=doc.addObject('Part::Cut',name);o.Base=base;o.Tool=tool;set_color(o,color);set_hide(base);set_hide(tool);return o
def save(doc,name,objects,proof):
 doc.recompute();assert all(not x.Shape.isNull() and x.Shape.isValid() for x in objects)
 native=pcs/(name+'.FCStd');step=out/(name+'.step');doc.recompute();doc.saveAs(str(native.resolve()));Import.export(objects,str(step.resolve()))
 native_bounds=[min(box(x)[i] for x in objects) for i in range(3)]+[max(box(x)[i] for x in objects) for i in range(3,6)]
 reread=Part.Shape();reread.read(str(step));b=reread.BoundBox;step_bounds=[b.XMin,b.YMin,b.ZMin,b.XMax,b.YMax,b.ZMax]
 assert reread.isValid() and max(abs(a-b) for a,b in zip(native_bounds,step_bounds))<1e-6, (name,native_bounds,step_bounds)
 proof[name]={'native_file':str(native),'step_file':str(step),'native_sha256':sha(native),'step_sha256':sha(step),'object_count':len(doc.Objects),'export_solids':len(reread.Solids),'bounds_3d_mm':step_bounds,'export_bbox_checked_from_reloaded_step':True,'native_objects':[{'name':x.Name,'type':x.TypeId} for x in doc.Objects]}
 A.closeDocument(doc.Name)
proof={};yellow=(1.,0.76,0.13);ivory=(0.91,0.89,0.81);metal=(0.75,0.74,0.68)
# XT30PW M30: original auteur conservé, repéré aux centres de l'empreinte et jambes prolongées de 1 mm.
d=A.newDocument('XT30PWM30');m=metadata(d,'CA01 XT30PW M30 dérivé auteur, à valider');m.addProperty('App::PropertyString','Source').Source='issus/altium-library: AMASS - XT30PW-M.step (modèle de broches 2 mm)'
s=Part.Shape();s.read(str(src/'AMASS_XT30PW-M_Celestial.step'));o=d.addObject('Part::Feature','SourceAuteur');o.Shape=s;o.Placement=A.Placement(A.Vector(-2.5,13,0),A.Rotation(A.Vector(0,0,1),180));set_color(o,yellow)
objects=[o]
for i,(x,y,r) in enumerate([(0,0,.6),(-5,0,.6),(-8,10,.25),(3,10,.25)]):objects.append(cyl(d,'ProlongementBroche'+str(i+1),x,y,-3,r,1.001,color=metal))
save(d,'CA01_Modele_XT30PW_M30_Derive',objects,proof)
# XT30PW F30: plan nominal AMASS + cavités/contacts et flange/plots de maintien simplifiés.
d=A.newDocument('XT30PWF30');m=metadata(d,'CA01 XT30PW F30 dérivé du plan, à valider');m.addProperty('App::PropertyString','Source').Source='AMASS biao/273 : dessin 1731372577569243.png, implantation empreinte KiCad'
body=cube(d,'BoitierNominal',-3.15,4,0,11.3,10.05,5.15,yellow)
for i,x in enumerate([0,5]):
 hole=cyl(d,'OuvertureContact'+str(i+1),x,7,2.575,1.65,7.1,(0,1,0));body=cut(d,'CaviteFemelle'+str(i+1),body,hole,yellow)
objects=[body]
for i,x in enumerate([0,5]):
 objects.append(cyl(d,'BrochePCB'+str(i+1),x,0,-3,.75,5.6,color=metal))
 objects.append(cyl(d,'CoudeContact'+str(i+1),x,0,1.85,.75,7.5,(0,1,0),metal))
 sleeve=cyl(d,'DouilleExterne'+str(i+1),x,7,2.575,1.45,6.85,(0,1,0),metal)
 bore=cyl(d,'DouilleVide'+str(i+1),x,7,2.575,.95,6.9,(0,1,0));objects.append(cut(d,'DouilleFemelle'+str(i+1),sleeve,bore,metal))
for i,x in enumerate([-3,8]):
 objects.append(cube(d,'FlasqueMaintien'+str(i+1),x-1.15,4.2,.1,2.3,1.6,.65,yellow));objects.append(cyl(d,'AncragePCB'+str(i+1),x,5,-3,.4,3.8,color=metal))
save(d,'CA01_Modele_XT30PW_F30_Plan',objects,proof)
# VH B2PS : header nu, bloc arrière, languette verrouillage et deux broches coudées candidates 1.14 mm.
d=A.newDocument('JSTVHB2PS');m=metadata(d,'CA01 JST VH B2PS dérivé du plan, à valider');m.addProperty('App::PropertyString','Source').Source='JST eVH.pdf p3 ; empreinte officielle KiCad B2PS horizontal'
objects=[cube(d,'BaseIsolante',-1.95,-7.2,0,7.86,3.2,8.5,ivory),cube(d,'LanguetteVerrouillage',-.9,-13.4,7.4,5.76,6.2,1.1,ivory)]
for i,x in enumerate([0,3.96]):
 objects.append(cube(d,'BrocheVerticale'+str(i+1),x-.57,-.57,-3.6,1.14,1.14,8.47,metal));objects.append(cube(d,'BrocheHorizontale'+str(i+1),x-.57,-14.9,3.73,1.14,15.47,1.14,metal))
save(d,'CA01_Modele_JST_VH_B2PS_Plan',objects,proof)
# PH exact référence auteur : translation native pour couvrir les pads soudables de KiCad.
d=A.newDocument('JSTPH6');m=metadata(d,'CA01 JST PH S6B PH SM4 TB modèle auteur, à valider');m.addProperty('App::PropertyString','Source').Source='Mark Harris / Celestial Altium Library, S6B-PH-SM4-TB.step ; translation Y -1.6 mm'
s=Part.Shape();s.read(str(src/'JST_S6B-PH-SM4-TB_Celestial.step'));mat=A.Matrix();mat.move(A.Vector(0,-1.6,0));o=d.addObject('Part::Feature','SourceAuteur');o.Shape=s.transformGeometry(mat);o.Placement=A.Placement();set_color(o,ivory)
save(d,'CA01_Modele_JST_PH_S6B_SM4_Auteur', [o],proof)
(src/'modeles_derives_geometrie.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:{q:v[q] for q in ['step_file','export_solids','bounds_3d_mm']} for k,v in proof.items()},indent=2))


