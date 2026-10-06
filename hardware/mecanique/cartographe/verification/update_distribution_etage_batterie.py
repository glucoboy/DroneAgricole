"""Infrastructure CAO : distribution et support isolant de l'étage batterie, fichiers évolués en place."""
from garde_hierarchie_batterie import require_monolithic_layout
require_monolithic_layout('update_distribution_etage_batterie.py')
from pathlib import Path
import hashlib, json, math
import FreeCAD as A, Part
from etage_batterie_helpers import MEC, VER, meta, color, save_native, load, link

def bbox(s):
 b=s.BoundBox
 return [b.XMin,b.YMin,b.ZMin,b.XMax,b.YMax,b.ZMax]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 from etage_batterie_helpers import require_legacy_layout
 require_legacy_layout('update_distribution_etage_batterie.py')
 assembly=A.openDocument(str(MEC/'assemblages/Integration_Stack_Revue_20261003.FCStd'))
 chassis=assembly.getObject('SA01_Chassis_Rehausse20').LinkedObject.Document
 stack=assembly.getObject('Stack_Holybro_CA01').Shape
 sensors=assembly.getObject('SA05_Capteurs_Isoles').Shape
 inputs={str(Path(d.FileName).relative_to(MEC)).replace('\\','/'):sha(d.FileName) for d in A.listDocuments().values() if d.FileName and Path(d.FileName).is_relative_to(MEC)}
 previous=next((x for x in A.listDocuments().values() if x.FileName and Path(x.FileName)==MEC/'pieces/fabriquees/P57_PlateauEnergieInferieur.FCStd'),None)
 if previous:A.closeDocument(previous.Name)
 sd=A.newDocument('P57_PlateauEnergieInferieur')
 root=sd.addObject('App::Part','Reference'); sheet=sd.addObject('Spreadsheet::Sheet','Parametres');root.addObject(sheet)
 params={'EpaisseurPlateaux':3,'FondPM_Z':-32,'FondJETI_Z':-32,'FondPDB_Z':-56,'DiametreFixationPDB':3.3,'DiametreFixationOEM':3.2,'DiametreMontantOEM':10}
 for i,(k,v) in enumerate(params.items(),1):sheet.set('A'+str(i),k);sheet.set('B'+str(i),('='+str(v) if v<0 else str(v))+' mm');sheet.setAlias('B'+str(i),k)
 parts=[]; tools=[]
 def box(n,dim,pos):
  o=sd.addObject('Part::Box',n);root.addObject(o)
  for k,v in zip(('Length','Width','Height'),dim):o.setExpression(k,str(v))
  for k,v in zip(('Placement.Base.x','Placement.Base.y','Placement.Base.z'),pos):o.setExpression(k,str(v))
  return o
 def cyl(n,r,h,pos):
  o=sd.addObject('Part::Cylinder',n);root.addObject(o);o.Radius=r;o.Height=h;o.Placement.Base=A.Vector(*pos);return o
 def beam(n,a,b,width,z=-32,t=3):
  dx=b[0]-a[0];dy=b[1]-a[1];l=math.hypot(dx,dy);nx=-dy/l*width/2;ny=dx/l*width/2
  pts=[A.Vector(a[0]+nx,a[1]+ny,z),A.Vector(b[0]+nx,b[1]+ny,z),A.Vector(b[0]-nx,b[1]-ny,z),A.Vector(a[0]-nx,a[1]-ny,z)];pts.append(pts[0])
  p=sd.addObject('Part::Feature',n+'Profil');root.addObject(p);p.Shape=Part.makePolygon(pts)
  e=sd.addObject('Part::Extrusion',n);root.addObject(e);e.Base=p;e.Dir=A.Vector(0,0,t);e.Solid=True;p.Visibility=False;return e
 parts.extend([box('IlotPM',(51,47,'Parametres.EpaisseurPlateaux'),(-141,-85,'Parametres.FondPM_Z')),box('IlotJETI',(88,42,'Parametres.EpaisseurPlateaux'),(-44,-128,'Parametres.FondJETI_Z')),box('IlotPDB',(66,86,'Parametres.EpaisseurPlateaux'),(87,-138,'Parametres.FondPDB_Z')),box('IlotCommande',(50,32,3),(40,-127,-32))])
 parts.extend([beam('LiaisonPMJETI',(-100,-65),(-40,-105),8),beam('LiaisonJETIPDB',(40,-107),(88,-107),8),box('MarchePDB',(5,14,27),(84,-114,-56))])
 anchors=[(-66.2114,-50.6551),(59.1399,-74.6966)]
 for i,(x,y) in enumerate(anchors):
  parts.append(cyl('MontantOEM'+str(i),5,32,(x,y,-32)))
  parts.append(beam('BrasOEM'+str(i),(x,y),(-100,-65) if i==0 else (65,-107),8))
  tools.extend([cyl('TrouOEM'+str(i),1.6,34,(x,y,-33)),cyl('DegagementVisOEM'+str(i),3.7,8,(x,y,-7))])
 # Calage local; ni taraudage ni trou ajouté dans un équipement commercial.
 for i,(x,y) in enumerate([(-132,-76),(-101,-47)]):parts.append(box('PatinPM'+str(i),(6,6,1),(x,y,-29)))
 for i,(x,y) in enumerate([(-32,-121),(26,-98)]):parts.append(box('PatinJETI'+str(i),(6,6,1),(x,y,-29)))
 for i,(x,y) in enumerate([(48,-120),(75,-105)]):parts.append(box('PatinCommande'+str(i),(6,6,1),(x,y,-29)))
 pdb_mount=[(95.00001,-109.99995),(95.00001,-59.99985),(145.00011,-109.99995),(145.00011,-59.99985)]
 for i,(x,y) in enumerate(pdb_mount):
  parts.append(cyl('AppuiPDB'+str(i),3,2.682397764797,(x,y,-53)))
  tools.append(cyl('TrouPDB'+str(i),1.65,8,(x,y,-57)))
 # Butées latérales ouvertes, passage de sangles d'étude indépendant du corps.
 for n,dim,pos in [('ButeePMExterne',(3,47,7),(-141,-85,-29)),('ButeePMArriere',(51,3,7),(-141,-85,-29)),('ButeeJETIArriere',(3,42,7),(-44,-128,-29)),('ButeeJETIFront',(88,3,7),(-44,-128,-29)),('ButeeCommande',(50,3,7),(40,-127,-29))]:parts.append(box(n,dim,pos))
 for i,(x,y,dim) in enumerate([(-134,-81,(6,3,5)),(-104,-42,(6,3,5)),(-24,-127,(6,3,5)),(20,-90,(6,3,5)),(50,-125,(6,3,5)),(76,-100,(6,3,5))]):tools.append(box('LumiereSangle'+str(i),dim,(x,y,-33)))
 tools.append(box('DegagementSupportCameraOEM075',(21,126,43.5),(-146,-63,-48)))
 union=sd.addObject('Part::MultiFuse','UnionSupports');root.addObject(union);union.Shapes=parts;union.Refine=True
 cuts=sd.addObject('Part::MultiFuse','Outils');root.addObject(cuts);cuts.Shapes=tools
 final=sd.addObject('Part::Cut','Resultat');root.addObject(final);final.Base=union;final.Tool=cuts;final.Refine=True
 for o in parts+tools+[union,cuts]:o.Visibility=False
 for o in sd.Objects:
  if o.Name.endswith('Profil'):o.Visibility=False
 final.Visibility=True;color(final,(.18,.47,.51))
 meta(root,'Etat','À valider');meta(root,'RealisationCAO','Implémenté');meta(root,'Materiau','Support isolant usiné G10 candidat; assemblage de niveaux et procédé à valider')
 meta(root,'Montage','Deux attaches sur trous OEM310 Ø3 existants : (-66.2114,-50.6551),(59.1399,-74.6966). Alésages3.2/counterbore7.4; vis, profondeur, serrage et maintien axial/vertical modules à valider. Ne pas remplacer la visserie sans inspection du lot.')
 meta(root,'Limites','Supports, jeux, procédé, flambage/rigidité, thermique et sangles non qualifiés; aucun trou ni taraudage inventé dans PM/JETI/commande/PDB.')
 sd.recompute();assert final.Shape.isValid() and final.Shape.Volume>0
 save_native(sd,MEC/'pieces/fabriquees/P57_PlateauEnergieInferieur.FCStd')
 dist=load('sous_assemblages','SA07_Distribution_Systeme_Candidat').Document;dr=dist.getObject('Reference')
 # Évolution des deux occurrences existantes.
 pm=dist.getObject('PM08');pm.LinkPlacement=A.Placement(A.Vector(-138,-82,-28),A.Rotation())
 pd=dist.getObject('PDB18138');b=pd.LinkedObject.Shape.BoundBox;pd.LinkPlacement=A.Placement(A.Vector(90-b.XMin,-135-b.YMin,-52-b.ZMin),A.Rotation())
 dock=load('sous_assemblages','SA02A_Dock20Ah','Ensemble').Document
 specs=[('PlateauEnergieInferieur',root,(0,0,0)),('MainSwitchJETI',load('pieces/commerce','EQ_JetiMainSwitch100_PortsEtude20A'),(90,-107,-140)),('CommandeMagnetiqueJETI',load('pieces/commerce','EQ_JetiMagneticSwitch'),(42,-124,-28))]
 for name,target,pos in specs:
  o=dist.getObject(name)
  if o:o.setLink(target);o.LinkPlacement=A.Placement(A.Vector(*pos),A.Rotation())
  else:o=link(dist,dr,name,target,pos)
  o.ViewObject.OverrideMaterial=True
  color(o,(.18,.47,.51) if name=='PlateauEnergieInferieur' else (.2,.25,.28) if name=='MainSwitchJETI' else (.28,.58,.25))
 meta(dr,'Etat','À valider');meta(dr,'RealisationCAO','Implémenté');meta(dr,'Limite','Étage énergie inférieur candidat; JETI/PM08-CAN/PDB et supportP57. Retirer occurrencesJETI doublonnées du dock avant intégration finale; connectique, sections, sangles, maintien vertical et thermique à qualifier.')
 dist.recompute();save_native(dist)
 # Contrôles sur les volumes, pas seulement boîtes englobantes.
 hits=[];checks=[]
 targets=[o for o in dist.Objects if o.TypeId=='App::Link']
 for o in targets:
  print('CHECK '+o.Name,flush=True)
  s=o.Shape
  for c in chassis.Objects:
   if c.TypeId=='App::Link' and s.BoundBox.intersect(c.Shape.BoundBox):
    v=s.common(c.Shape).Volume
    if v>.001:hits.append({'objet':o.Name,'autre':c.Name,'volume_mm3':v})
  for n,t in [('Stack_Holybro_CA01',stack),('SA05_Capteurs_Isoles',sensors)]:
   v=s.common(t).Volume if s.BoundBox.intersect(t.BoundBox) else 0
   if v>.001:hits.append({'objet':o.Name,'autre':n,'volume_mm3':v})
 for i,o in enumerate(targets):
  for q in targets[i+1:]:
   if o.Shape.BoundBox.intersect(q.Shape.BoundBox):
    v=o.Shape.common(q.Shape).Volume
    if v>.001:hits.append({'objet':o.Name,'autre':q.Name,'volume_mm3':v})
 # Volume conservateur de prise/câble PDB au-dessus de l'ensemble commercial.
 reservation=Part.makeBox(60,80,22,A.Vector(90,-135,-29));reserved_hits=[]
 for c in chassis.Objects:
  if c.TypeId=='App::Link' and reservation.BoundBox.intersect(c.Shape.BoundBox):
   v=reservation.common(c.Shape).Volume
   if v>.001:reserved_hits.append({'autre':c.Name,'volume_mm3':v})
 ports={'JETI_IN_PLUS':[-40,-115,-16.5],'JETI_IN_MOINS':[-40,-99,-16.5],'JETI_OUT_PLUS':[40,-115,-16.5],'JETI_OUT_MOINS':[40,-99,-16.5],'statut':'Réservations sans cotes fabricant; relever les sorties du lot avant fabrication'}
 output={'schema_version':1,'date':'2026-10-04','statut':'À valider','CAO':'Implémenté','recette':'verification/update_distribution_etage_batterie.py','recette_sha256':sha(__file__),'sha256_inputs':inputs,'fichiers_sha256':{str(Path(x.FileName).relative_to(MEC)).replace('\\','/'):sha(x.FileName) for x in [sd,dist]},'occurrences':[{'objet':o.Name,'reference':Path(o.LinkedObject.Document.FileName).stem,'fichier':str(Path(o.LinkedObject.Document.FileName).relative_to(MEC)).replace('\\','/'),'source_objet':o.LinkedObject.Name,'placement_matrice':list(o.LinkPlacement.toMatrix().A),'bbox_mm':bbox(o.Shape)} for o in targets],'support':{'valid':final.Shape.isValid(),'solides':len(final.Shape.Solids),'volume_mm3':final.Shape.Volume,'arbres_natifs':['Part::Box','Part::Cylinder','Part::Extrusion','Part::MultiFuse','Part::Cut'],'degagement_camera_OEM075_bbox_mm':[-146,-63,-48,-125,63,-4.5],'attaches_OEM310_xy_mm':anchors,'trous_PDB_xy_mm':pdb_mount,'statut_attaches':'À valider, vis et sangles non sélectionnées'},'ports_etude':ports,'intersections_volumiques':hits,'reservation_PDB_bbox_mm':bbox(reservation),'reservation_PDB_intersections':reserved_hits,'bbox_distribution_mm':bbox(dr.Shape),'limites':['Aucune fabrication, réception de lot, traction, vibration ni thermique exécutée','Les lumières et butées ne constituent pas un maintien vertical/axial qualifié; fixation et procédure d’assemblage à finaliser','La suppression des doublonsJETI du dock et l’intégration finale sont réalisées par la recette dock distincte','Réservation conservatrice22 mm au-dessusPDB; fiches accouplées et rayons de câble réels à mesurer']}
 (VER/'distribution_etage_batterie.json').write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps({'hits':hits,'ports':ports,'bbox':output['bbox_distribution_mm'],'support_solides':len(final.Shape.Solids)},ensure_ascii=True),flush=True)
if __name__=='__main__':main()




