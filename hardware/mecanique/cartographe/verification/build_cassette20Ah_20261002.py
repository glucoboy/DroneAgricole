"""Infrastructure CAO candidate : cassette 6S20Ah coulissante, sans contacts.
Ne modifie ni drone actif ni manifeste. Paramètres natifs et liens externes.
"""
from pathlib import Path
import json, math, hashlib, itertools
from cassette20_fasteners import refs as hardware_refs,occurrences as hardware_occ
import FreeCAD as A
import Part
ROOT=Path(__file__).resolve().parents[4]; MEC=ROOT/'hardware/mecanique/cartographe'
PROOF=MEC/'verification/construction_cassette20Ah_20261002.json'
PARAM={'RailL':220,'RailInnerY':42,'RailOuterY':48,'ChannelOuterY':45.5,'FloorZ':33,'ShelfZ':36.5,'RoofZ':39.5,'RailTop':42,'CassetteL':202,'CassetteW':90,'BaseZ':37,'BaseT':2,'PackBaseZ':40,'PackMaxL':198,'PackMaxW':78,'PackMaxH':60,'WallInnerY':40,'WallOuterY':42,'WallBaseZ':39,'WallTopZ':100,'CapT':2,'EndInnerX':101,'EndOuterX':103,'EarOuterX':107,'EarHoleX':104,'EarHoleY':33,'M3D':3.2,'M4D':4.5,'StopY':25,'StopZ':35.5,'LatchX':105,'LatchY':60.5,'LatchZ':91,'StrikerX':116.85,'StrikerY':63.5,'StrikerZ':68,'ReleaseStroke':7,'ChamferEntry':1.5}
REFS={}; ROWS=[]
def init(name,params=None,material='Matière candidate, à valider'):
 d=A.newDocument(name);r=d.addObject('App::Part','Reference')
 for key,val in {'Etat':'À valider','RealisationCAO':'Implémenté','Materiau':material,'Limites':'Géométrie candidate ; tenue, visserie, gonflement softpack, commande avec gants et verrouillage physique non qualifiés.'}.items():
  r.addProperty('App::PropertyString',key);setattr(r,key,val)
 s=d.addObject('Spreadsheet::Sheet','Parametres');r.addObject(s)
 for i,(k,v) in enumerate((params or PARAM).items(),1):
  s.set('A'+str(i),k);s.set('B'+str(i),str(v)+' mm');s.setAlias('B'+str(i),k)
 return d,r
def ex(o,p,v):o.setExpression(p,str(v))
def box(d,n,dim,pos):
 o=d.addObject('Part::Box',n)
 for p,v in zip(('Length','Width','Height'),dim):ex(o,p,v)
 for p,v in zip(('Placement.Base.x','Placement.Base.y','Placement.Base.z'),pos):ex(o,p,v)
 return o
def cyl(d,n,rad,h,pos,axis=(0,0,1)):
 o=d.addObject('Part::Cylinder',n);ex(o,'Radius',rad);ex(o,'Height',h);o.Placement.Rotation=A.Rotation(A.Vector(0,0,1),A.Vector(*axis))
 for p,v in zip(('Placement.Base.x','Placement.Base.y','Placement.Base.z'),pos):ex(o,p,v)
 return o
def hexpocket(d,n,pos,axis=(0,0,1)):
 o=d.addObject('Part::Prism',n);o.Polygon=6;o.Circumradius=5.7/math.sqrt(3);o.Height=2.6
 o.Placement=A.Placement(A.Vector(*pos),A.Rotation(A.Vector(0,0,1),A.Vector(*axis)));return o
def fuse(d,n,parts):
 if len(parts)==1:return parts[0]
 o=d.addObject('Part::MultiFuse',n);o.Shapes=parts;o.Refine=True
 for q in parts:q.Visibility=False
 return o
def cut(d,n,base,tool):
 o=d.addObject('Part::Cut',n);o.Base=base;o.Tool=tool;o.Refine=True
 base.Visibility=False;tool.Visibility=False;return o
def final(d,r,out,folder='fabriquees'):
 if out.Name!='Resultat':
  f=d.addObject('Part::Compound','Resultat');f.Links=[out];out.Visibility=False;out=f
 r.addObject(out)
 for q in d.Objects:
  if q.TypeId.startswith('Part::') and q!=out:q.Visibility=False
 out.Visibility=True;d.recompute()
 assert out.Shape.isValid() and out.Shape.Volume>0,d.Name
 if folder=='fabriquees':assert len(out.Shape.Solids)==1,(d.Name,'Référence fabriquée discontinue')
 assert abs(r.Shape.Volume-out.Shape.Volume)<1e-6
 p=MEC/'pieces'/folder/(d.Name+'.FCStd');d.saveAs(str(p))
 export=MEC/'exports/cassette20Ah_20261002';export.mkdir(parents=True,exist_ok=True)
 Part.export([out],str(export/(d.Name+'.step')))
 REFS[d.Name]=r
 b=out.Shape.BoundBox
 ROWS.append({'id':d.Name,'file':str(p.relative_to(MEC)).replace('\\','/'),'source_objet':'Reference','final':'Resultat','volume_mm3':out.Shape.Volume,'bbox_mm':[b.XMin,b.YMin,b.ZMin,b.XMax,b.YMax,b.ZMax],'valid':out.Shape.isValid(),'solids':len(out.Shape.Solids),'expressions':sum(len(q.ExpressionEngine) for q in d.Objects),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
 return r
def rail(name,side):
 d,r=init(name,material='PA12 SLS ; usure/rigidité/fluage à valider')
 y0='Parametres.RailInnerY' if side>0 else '-Parametres.RailOuterY'
 outer='Parametres.ChannelOuterY' if side>0 else '-Parametres.RailOuterY'
 roof=box(d,'Toit',('Parametres.RailL','Parametres.RailOuterY-Parametres.RailInnerY','Parametres.RailTop-Parametres.RoofZ'),('-Parametres.RailL/2',y0,'Parametres.RoofZ'))
 # Biseau natif sur l'arête d'entrée +X à la sous-face du toit.
 d.recompute()
 candidates=[i+1 for i,e in enumerate(roof.Shape.Edges) if abs(e.CenterOfMass.x-110)<1e-6 and abs(e.CenterOfMass.z-39.5)<1e-6]
 assert len(candidates)==1,candidates
 cham=d.addObject('Part::Chamfer','BiseauEntree');cham.Base=roof;cham.Edges=[(candidates[0],PARAM['ChamferEntry'],PARAM['ChamferEntry'])];roof.Visibility=False
 parts=[cham,box(d,'Semelle',('Parametres.RailL','Parametres.RailOuterY-Parametres.RailInnerY','Parametres.ShelfZ-Parametres.FloorZ'),('-Parametres.RailL/2',y0,'Parametres.FloorZ')),box(d,'Dos',('Parametres.RailL','Parametres.RailOuterY-Parametres.ChannelOuterY','Parametres.RoofZ-Parametres.ShelfZ'),('-Parametres.RailL/2',outer,'Parametres.ShelfZ'))]
 # Pieds OEM : matière autour des axes M3 ±40/±45,5.
 for j,x in enumerate([-40,40]):
  parts.append(box(d,'PiedOEM'+str(j),(12,12,'Parametres.ShelfZ-Parametres.FloorZ'),(str(x-6)+' mm',str(side*51.5-6)+' mm','Parametres.FloorZ')))
 # Plateau support butée arrière, et patte extérieure de support loquet droite.
 for j,x0 in enumerate([-120,-111]):parts.append(box(d,'PiedButeeArriere'+str(j),(5 if j==0 else 3,6.5,'Parametres.ShelfZ-Parametres.FloorZ'),(str(x0)+' mm','42.5 mm' if side>0 else '-49 mm','Parametres.FloorZ')))
 # Pont extérieur : contourne le montantP35Y±49 sans pièce isolée.
 parts.append(box(d,'PontArriereExterieur',(16,6,'Parametres.ShelfZ-Parametres.FloorZ'),('-120 mm','49 mm'if side>0 else'-55 mm','Parametres.FloorZ')))
 parts.append(box(d,'RaccordPontRail',(4,8,'Parametres.ShelfZ-Parametres.FloorZ'),('-108 mm','47 mm'if side>0 else'-55 mm','Parametres.FloorZ')))
 if side>0:parts.append(box(d,'PiedSupportVerrou',(35,14,'Parametres.RailTop-Parametres.FloorZ'),('99 mm','45.5 mm','Parametres.FloorZ')))
 main=fuse(d,'RailAvecPieds',parts)
 holes=[cyl(d,'TrouOEM'+str(j),'Parametres.M3D/2','Parametres.RailTop-Parametres.FloorZ+2 mm',(str(x)+' mm',str(side*51.5)+' mm','Parametres.FloorZ-1 mm')) for j,x in enumerate([-40,40])]
 holes.append(cyl(d,'TrouButee','Parametres.M3D/2','11 mm',('-117.5 mm',str(side*46)+' mm','32 mm')))
 for i,x in enumerate([-66.2114,66.2114]):holes.append(cyl(d,'DegagementTeteOEM'+str(i),3.25,3,(str(x)+' mm',str(side*50.6551)+' mm','32.9 mm')))
 if side>0:
  for j,x in enumerate([101.5,131.5]):holes.append(cyl(d,'TrouSupportVerrou'+str(j),'Parametres.M3D/2','11 mm',(str(x)+' mm','49.5 mm','32 mm')))
 return final(d,r,cut(d,'Resultat',main,fuse(d,'OutilsPercage',holes)))

rail('P28_RailDroit20Ah',1);rail('P29_RailGauche20Ah',-1)
d,r=init('P30_FondCassetteG10_20Ah',material='G10 2 mm candidat')
parts=[box(d,'Plaque',('Parametres.CassetteL','Parametres.CassetteW','Parametres.BaseT'),('-Parametres.CassetteL/2','-Parametres.CassetteW/2','Parametres.BaseZ'))]
holes=[]
for i,(x,y) in enumerate(itertools.product([-1,1],[-1,1])):
 parts.append(box(d,'Oreille'+str(i),(8,8,2),('-109 mm' if x<0 else '101 mm',str(y*33-4)+' mm','Parametres.BaseZ')))
 holes.append(cyl(d,'TrouOreille'+str(i),'Parametres.M3D/2','4 mm',(str(x*104)+' mm',str(y*33)+' mm','36 mm')))
for i,y in enumerate([-38.5,33.5]):holes.append(box(d,'DegagementVisButee'+str(i),(7,5,1.6),('-108 mm',str(y)+' mm','36 mm')))
for i,y in enumerate([-33,33]):
 holes.append(cyl(d,'TrouBarreButee'+str(i),1.35,4,('-98 mm',str(y)+' mm','36 mm')))
 cone=d.addObject('Part::Cone','FraisureM25_'+str(i));cone.Radius1=2.35;cone.Radius2=0.85;cone.Height=1.5
 cone.Placement=A.Placement(A.Vector(-98,y,39),A.Rotation(A.Vector(1,0,0),180));holes.append(cone)
main=fuse(d,'FondAvecOreilles',parts);final(d,r,cut(d,'Resultat',main,fuse(d,'OutilsPercage',holes)))

d,r=init('P31_CaptureCassette20Ah',material='PA12 SLS ; surfaces softpack à protéger/arrondir')
parts=[box(d,'Paroi'+str(i),('Parametres.CassetteL','Parametres.WallOuterY-Parametres.WallInnerY','Parametres.WallTopZ-Parametres.WallBaseZ'),('-101 mm',y,'Parametres.WallBaseZ')) for i,y in enumerate(['-42 mm','40 mm'])]
parts += [box(d,'Extremite'+str(i),('Parametres.EndOuterX-Parametres.EndInnerX','84 mm','61 mm'),(x,'-42 mm','39 mm')) for i,x in enumerate(['-103 mm','101 mm'])]
for i,(sx,sy) in enumerate(itertools.product([-1,1],[-1,1])):
 parts.append(box(d,'BossageBas'+str(i),(8,8,6),('-109 mm' if sx<0 else '101 mm',str(sy*33-4)+' mm','39 mm')))
 parts.append(box(d,'BossageHaut'+str(i),(9,8,6),('-110 mm' if sx<0 else '101 mm',str(sy*36-4)+' mm','94 mm')))
for i,y in enumerate([33,-36]):parts.append(box(d,'BossagePoignee'+str(i),(8,8,8),('101 mm',str(y-4)+' mm','51 mm')))
main=fuse(d,'CapturePermanente',parts)
windows=[]
for i,y in enumerate([-43,39]):
 for j,x in enumerate([-93,5]):windows.append(box(d,'FenetreLaterale'+str(i)+str(j),(88,4,50),(str(x)+' mm',str(y)+' mm','45 mm')))
for i,x in enumerate([-104,100]):
 windows.append(box(d,'FenetreExtremite'+str(i),(4,48,50),(str(x)+' mm','-24 mm','45 mm')))
holes=[]
for i,(sx,sy) in enumerate(itertools.product([-1,1],[-1,1])):
 holes.append(cyl(d,'TrouBas'+str(i),'Parametres.M3D/2','8 mm',(str(sx*104)+' mm',str(sy*33)+' mm','38 mm')))
 holes.append(cyl(d,'TrouHaut'+str(i),'Parametres.M3D/2','9 mm',(str(sx*105)+' mm',str(sy*36)+' mm','93 mm')))
 holes.append(hexpocket(d,'EcrouCaptifBas'+str(i),(sx*104,sy*33,42.4)))
 holes.append(hexpocket(d,'EcrouCaptifHaut'+str(i),(sx*105,sy*36,94)))
for i,y in enumerate([33,-36]):
 holes.append(cyl(d,'TrouPoigneeAxeX'+str(i),1.6,13,('100 mm',str(y)+' mm','55 mm'),(1,0,0)))
 holes.append(hexpocket(d,'EcrouCaptifPoignee'+str(i),(101,y,55),(1,0,0)))
for i,y in enumerate([-37.2,28.8]):holes.append(box(d,'EncocheBrasContacts'+str(i),(2.4,8.4,8.2),('-103.2 mm',str(y)+' mm','45 mm')))
# Fixation permanente poignée et portées de butée, axeY, hors pack.
for i,(x,z) in enumerate([(102,46),(-100,47)]):
 holes.append(cyl(d,'TrouLateralD'+str(i),'Parametres.M3D/2','6 mm',(str(x)+' mm','39 mm',str(z)+' mm'),(0,1,0)))
 holes.append(cyl(d,'TrouLateralG'+str(i),'Parametres.M3D/2','6 mm',(str(x)+' mm','-45 mm',str(z)+' mm'),(0,1,0)))
main=cut(d,'CaptureAjouree',main,fuse(d,'OutilsFenetres',windows))
final(d,r,cut(d,'Resultat',main,fuse(d,'OutilsPercage',holes)))

d,r=init('P32_CapG10Capture20Ah',material='G10 2 mm')
parts=[box(d,'BandeLongitudinale',(206,6,'Parametres.CapT'),('-103 mm','36 mm','Parametres.WallTopZ'))]
holes=[]
for i,sx in enumerate([-1,1]):
 parts.append(box(d,'OreilleCap'+str(i),(7,8,2),('-110 mm' if sx<0 else '103 mm','32 mm','100 mm')))
 holes.append(cyl(d,'TrouCap'+str(i),'Parametres.M3D/2','4 mm',(str(sx*105)+' mm','36 mm','99 mm')))
 cone=d.addObject('Part::Cone','FraisureCap_'+str(i));cone.Radius1=2.8;cone.Radius2=1.15;cone.Height=1.65
 cone.Placement=A.Placement(A.Vector(sx*105,36,102),A.Rotation(A.Vector(1,0,0),180));holes.append(cone)
final(d,r,cut(d,'Resultat',fuse(d,'CapAvecOreilles',parts),fuse(d,'OutilsPercage',holes)))

d,r=init('P33_PoigneePorteGache20Ah',material='PA12 SLS ; résistance poignée/écrous captifs à valider')
parts=[box(d,'BrasDroit',(25,17.1,5),('103 mm','28 mm','46 mm')),box(d,'BrasGauche',(25,6,5),('103 mm','-38 mm','46 mm')),box(d,'Poignee',(3,73.6,5),('125 mm','-38 mm','46 mm')),box(d,'SupportGache',(12,3,24),('111 mm','42.1 mm','48 mm'))]
# Connexion des bras aux oreilles sur la face avant, sans pousser dans le softpack.
parts += [box(d,'PiedDroit',(3.5,12,19),('109 mm','28 mm','40 mm')),box(d,'PiedGauche',(3.5,10,19),('109 mm','-42 mm','40 mm'))]
holes=[cyl(d,'TrouGacheM5',2.6,5,('Parametres.StrikerX','41.1 mm','Parametres.StrikerZ'),(0,1,0))]
# Connexion par vis axesX, correspondante à l'extrémité avant P31.
for i,y in enumerate([33,-36]):holes.append(cyl(d,'TrouPoignee'+str(i),'Parametres.M3D/2',5,('108 mm',str(y)+' mm','55 mm'),(1,0,0)))
for i,y in enumerate([-25,-11]):holes.append(cyl(d,'FixationEquilibrage'+str(i),1.1,5,('124 mm',str(y)+' mm','48.5 mm'),(1,0,0)))
final(d,r,cut(d,'Resultat',fuse(d,'PoigneeAvecPorteGache',parts),fuse(d,'OutilsPercage',holes)))

d,r=init('P34_SupportFixeSouthco20Ah',material='Aluminium6061-T6 usiné ; rayons outil et tenue mécanique à valider')
panel=box(d,'Panneau',(23,3,46),('105 mm','60.5 mm','45 mm'))
foot=box(d,'Pied',(35,18,3),('99 mm','45.5 mm','42 mm'))
main=fuse(d,'SupportVerrou',[panel,foot])
mouth=cyl(d,'DegagementTete',6,5,('Parametres.StrikerX','59.5 mm','Parametres.StrikerZ'),(0,1,0))
entry=box(d,'EntreeTete',(13,5,12),('Parametres.StrikerX','59.5 mm','Parametres.StrikerZ-6 mm'))
holes=[mouth,entry]
for i,z in enumerate([55.3,80.7]):holes.append(cyl(d,'TrouM4'+str(i),'Parametres.M4D/2',5,('Parametres.StrikerX','59.5 mm',str(z)+' mm'),(0,1,0)))
for i,x in enumerate([101.5,131.5]):holes.append(cyl(d,'TrouPied'+str(i),'Parametres.M3D/2',5,(str(x)+' mm','49.5 mm','41 mm')))
final(d,r,cut(d,'Resultat',main,fuse(d,'OutilsPercage',holes)))

d,r=init('P35_SupportButee20Ah',material='Aluminium6061-T6 usiné ; rayons outil et tenue mécanique à valider')
feet=[box(d,'Pied'+str(i),(10,6.5,2.5),('-120 mm',str(y)+' mm','36.5 mm'))for i,y in enumerate([-49,42.5])]
wall=box(d,'Montant',(4,98,9),('-115 mm','-49 mm','31 mm'))
holes=[]
for i,y in enumerate([-25,25]):holes.append(cyl(d,'TrouReglageM4'+str(i),'Parametres.M4D/2',6,('-116 mm',str(y)+' mm','35.5 mm'),(1,0,0)))
for i,y in enumerate([-46,46]):holes.append(cyl(d,'TrouPiedM3'+str(i),'Parametres.M3D/2',5,('-117.5 mm',str(y)+' mm','35.5 mm')))
for i,y in enumerate([-46,46]):holes.append(cyl(d,'DegagementEcrouPied'+str(i),3.4,3.2,('-117.5 mm',str(y)+' mm','30 mm')))
for i,y in enumerate([-49,42.5]):holes.append(box(d,'DegagementP39'+str(i),(6,6.5,2),('-116 mm',str(y)+' mm','39 mm')))
final(d,r,cut(d,'Resultat',fuse(d,'SupportButee',feet+[wall]),fuse(d,'OutilsPercage',holes)))
d,r=init('P36_PorteeMobileButee20Ah',material='Aluminium6061-T6 usiné ; rayons outil et tenue mécanique à valider')
pad=box(d,'Portee',(6,78,3),('-101 mm','-39 mm','34 mm'))
holes=[cyl(d,'TrouM25_'+str(i),1.35,5,('-98 mm',str(y)+' mm','33 mm'))for i,y in enumerate([-33,33])]
for i,y in enumerate([-33,33]):
 h=d.addObject('Part::Prism','EcrouCaptifBarre'+str(i));h.Polygon=6;h.Circumradius=5.2/math.sqrt(3);h.Height=2.2;h.Placement.Base=A.Vector(-98,y,34);holes.append(h)
final(d,r,cut(d,'Resultat',pad,fuse(d,'OutilsPercage',holes)))

# Pack local, nominal fabricant ; le maximum'étude 198×78×60 n'est pas fabricant.
d,r=init('EQ_Tattu20Ah6S_Dock',{'Longueur':193,'Largeur':76,'Hauteur':58},material='Batterie commerciale NMC 6S 20Ah, 1950±20g')
r.addProperty('App::PropertyString','MPN').MPN='TAA200006S5X9S'
r.addProperty('App::PropertyString','Source').Source='https://gensace.de/collections/semi-solid-state/products/tattu-nmc-20000mah-22-2v-5c-6s1p-lipo-battery-pack-with-xt90-s-plug'
final(d,r,box(d,'PackNominal',('Parametres.Longueur','Parametres.Largeur','Parametres.Hauteur'),('-Parametres.Longueur/2','-Parametres.Largeur/2','0 mm')),'commerce')
d,r=init('EQ_MousseEPDM1_Dock',{'Longueur':198,'Largeur':78,'Hauteur':1},material='Réservation EPDM 1 mm ; qualité feu/électrique/compression inconnue')
final(d,r,box(d,'Reservation',('Parametres.Longueur','Parametres.Largeur','Parametres.Hauteur'),('-Parametres.Longueur/2','-Parametres.Largeur/2','39 mm')),'commerce')
d,r=init('EQ_VisButeeM4x20_Dock',{'Diametre':4,'Longueur':20},material='ISO4026 M4×20 acier ; vis sans tête bout plat, empreinte et filet simplifiés')
final(d,r,cyl(d,'TigeVis','Parametres.Diametre/2','Parametres.Longueur',('-121 mm','25 mm','35.5 mm'),(1,0,0)),'commerce')

# Charger références réelles de loquet ; ne les régénère pas ici.
for name in ['EQ_SouthcoR405','EQ_SouthcoGacheR490']:
 dd=A.openDocument(str(MEC/'pieces/commerce'/(name+'.FCStd')));REFS[name]=dd.getObject('Reference')
REFS.update(hardware_refs())

d,r=init('SA02_Cassette20Ah_Coulissante')
d.Parametres.set('A60','ExtractionX');d.Parametres.set('B60','0 mm');d.Parametres.setAlias('B60','ExtractionX')
r.addProperty('App::PropertyString','Usage').Usage='Candidate inactive. Parametres.ExtractionX pilote uniquement translation +X cassette. Pas d’engagement interne du loquet ni contacts électriques.'
path=MEC/'sous_assemblages/SA02_Cassette20Ah_Coulissante.FCStd';d.saveAs(str(path))
IDENTITY=A.Placement();RX=A.Rotation(A.Vector(1,0,0),180)
occ=[
 ('RailDroit','P28_RailDroit20Ah',False,IDENTITY),('RailGauche','P29_RailGauche20Ah',False,IDENTITY),
 ('FondCassette','P30_FondCassetteG10_20Ah',True,IDENTITY),('Capture','P31_CaptureCassette20Ah',True,IDENTITY),
 ('CapG10D','P32_CapG10Capture20Ah',True,IDENTITY),('CapG10G','P32_CapG10Capture20Ah',True,A.Placement(A.Vector(0,0,202),RX)),('PoigneeGache','P33_PoigneePorteGache20Ah',True,IDENTITY),
 ('SupportLoquet','P34_SupportFixeSouthco20Ah',False,IDENTITY),
 ('SupportButee','P35_SupportButee20Ah',False,IDENTITY),
 ('PorteeButee','P36_PorteeMobileButee20Ah',True,IDENTITY),
 ('Batterie','EQ_Tattu20Ah6S_Dock',True,A.Placement(A.Vector(0,0,40),A.Rotation())),
 ('Mousse','EQ_MousseEPDM1_Dock',True,IDENTITY),
 ('Loquet','EQ_SouthcoR405',False,A.Placement(A.Vector(105,60.5,91),RX)),
 ('Gache','EQ_SouthcoGacheR490',True,A.Placement(A.Vector(116.85,63.5,68),RX)),
 ('VisButeeD','EQ_VisButeeM4x20_Dock',False,IDENTITY),('VisButeeG','EQ_VisButeeM4x20_Dock',False,A.Placement(A.Vector(0,-50,0),A.Rotation()))]
occ+=hardware_occ()
for name,key,mobile,p in occ:
 link=d.addObject('App::Link',name);link.setLink(REFS[key]);r.addObject(link);link.LinkPlacement=p
 if mobile:link.setExpression('LinkPlacement.Base.x',str(p.Base.x)+' mm+Parametres.ExtractionX')
d.recompute();d.save()
def collisions(shapes):
 hits=[]
 for (n,a),(m,b) in itertools.combinations(shapes.items(),2):
  if a.BoundBox.intersect(b.BoundBox):
   v=a.common(b).Volume
   if v>1e-6:hits.append({'a':n,'b':m,'volume_mm3':v})
 return hits
samples=[]
for dx in [0,1,5,10,20,50,100,150,200,220,230,300]:
 d.Parametres.set('B60',str(dx)+' mm');d.recompute()
 fixed={n:d.getObject(n).Shape.copy() for n,k,m,p in occ if not m}
 moving={n:d.getObject(n).Shape.copy() for n,k,m,p in occ if m}
 hits=[]
 for n,a in moving.items():
  for m,b in fixed.items():
   if a.BoundBox.intersect(b.BoundBox):
    v=a.common(b).Volume
    if v>1e-6:hits.append({'mobile':n,'fixe':m,'volume_mm3':v})
 samples.append({'extraction_x_mm':dx,'collisions_mobile_fixe':hits})
d.Parametres.set('B60','0 mm');d.recompute();d.save()
nominal=collisions({n:d.getObject(n).Shape.copy() for n,k,m,p in occ})
maxpack=Part.makeBox(198,78,60,A.Vector(-99,-39,40))
maxhits=[]
for n,k,m,p in occ:
 if n not in ['Batterie','Mousse']:
  v=maxpack.common(d.getObject(n).Shape).Volume
  if v>1e-6:maxhits.append({'a':'PackMaximumEtude','b':n,'volume_mm3':v})
# Reouverture de l'assemblage et rappel des matrices au verrouillage X0.
A.closeDocument(d.Name);d=A.openDocument(str(path));d.recompute()
matrices=[{'nom':n,'reference':k,'mobile':m,'source_objet':'Reference','matrice':list(d.getObject(n).LinkPlacement.toMatrix().A),'volume_reference_egale_lien':abs(d.getObject(n).Shape.Volume-REFS[k].Shape.Volume)<1e-6} for n,k,m,p in occ]
report={'schema_version':1,'date_utc':'2026-10-02','status':'À valider','realisation_CAO':'Implémenté','recette':str(Path(__file__).relative_to(MEC)).replace('\\','/'),'references':ROWS,'assemblage':str(path.relative_to(MEC)).replace('\\','/'),'occurrences':matrices,'reouverture_recalcul':'Réussi','collisions_nominales':nominal,'collisions_pack_maximum':maxhits,'mouvement':samples,'interfaces':{'canal_y_par_cote_mm':3.5,'flange_y_mm':3,'jeu_lateral_flange_mm':0.5,'jeu_sous_flange_mm':0.5,'jeu_dessus_flange_mm':0.5,'pack_max_etude_mm':[198,78,60],'pack_base_z_mm':40,'haut_pack_max_mm':100,'dessous_capture_haute_mm':100,'haut_cap_mm':102,'dessous_plateau_rehausse_mm':103,'tetes_fixation_cap_fraisees_flush_Z102':True,'loquet_rx180':True,'gache_translation_mm':[116.85,59.5,68],'filetage_gache_vers_Y_negatif':True},'limites':['Aucun engagement interne du loquet commercial simulé. Les cotes de course d’insertion entre stages ne sont pas fournies.','Aucun contact électrique présent ; butée mécanique candidate doit être réglée sans charger les futurs contacts.','Visserie ISO modélisée ; filetages, empreintes et freinage simplifiés ; les trous et BOM sont explicites mais assemblage physique non qualifié.','Maximum pack198×78×60 est une hypothèse tolérancée d’étude, pas une tolérance fabricant.','Pack nominal laisse2mm sous capture ; cales individuelles mesurées à ajouter, pas compression forcée de l’enveloppe maximum.','Support et fixations sur plateaux/avionique/hélices contrôlés par audit externe ; rigidité, masse installée, poussière/gants, vibration et tenue de vol non qualifiées.','Les chanfreins d’entrée sont natifs mais leurs distances sont définies par recette ; les rayons complets de protection softpack restent à détailler.']}
PROOF.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
from collections import Counter
bom={'schema_version':2,'date_utc':'2026-10-02','status':'À valider','pieces_fabriquees':[{'reference':row['id'],'quantite':2 if row['id'].startswith('P32_') else 1,'fichier':row['file'],'volume_mm3':row['volume_mm3']} for row in ROWS if row['id'].startswith('P')],'visserie':[{'reference':key,'quantite':count,'fichier':'pieces/commerce/'+key+'.FCStd','designation':key.replace('EQ_','').replace('_Dock','').replace('_',' ').replace('M25','M2.5')} for key,count in Counter(k for n,k,m,p in occ if 'ISO'in k or 'DIN'in k or 'VisButee'in k).items()],'note':'Écrous M3 ISO4032 captifs AF5.7 profondeur2.6 ; pas inserts. Vis M2.5x5 fraisées ; nutscaptifsdansbarre. Filets, empreintes et freinage simplifiés ; essais serrage/rigidité requis.'}
(MEC/'verification/bom_visserie_dock20Ah_20261002.json').write_text(json.dumps({'lignes':bom['visserie'],'total_occurrences':sum(x['quantite']for x in bom['visserie'])},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
(MEC/'verification/bom_cassette20Ah_20261002.json').write_text(json.dumps(bom,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'native_refs':len(ROWS),'occurrences':len(occ),'nominal_collisions':nominal,'maximum_collisions':maxhits,'motion_collision_counts':[[s['extraction_x_mm'],len(s['collisions_mobile_fixe'])] for s in samples]},ensure_ascii=False))
















