"""Infrastructure CAO : dock6S20Ah complet, composants et faisceau candidat. Aucun vol qualifié."""
from pathlib import Path
from etage_batterie_helpers import require_legacy_layout
require_legacy_layout('build_dock20Ah_20261003.py')
import json,math
import FreeCAD as A,Part
from cad_dock20_helpers import *
refs={};rows=[]
def loadref(name,folder='commerce'):
 doc=A.openDocument(str(MEC/'pieces'/folder/(name+'.FCStd')));return doc.getObject('Reference')
def retain(name,r):refs[name]=r;return r
def finish(dd,rr,out,kind='fabriquees'):
 save(dd,rr,out,kind);return retain(dd.Name,rr)
def bolt(name,diam,L,D,H):
 dd,rr=new(name,'Acier8.8',{'Diametre':diam,'Longueur':L,'TeteD':D,'TeteH':H})
 return finish(dd,rr,fuse(dd,rr,'Resultat',[cyl(dd,rr,'Tete',D/2,H,(0,0,-H)),cyl(dd,rr,'Tige',diam/2,L,(0,0,0))]),'commerce')
def nut(name,diam,AF,H):
 dd,rr=new(name,'Acierclasse8',{'Diametre':diam,'Surplats':AF,'Hauteur':H})
 pts=[A.Vector(AF/math.sqrt(3)*math.cos(k*math.pi/3),AF/math.sqrt(3)*math.sin(k*math.pi/3),0)for k in range(6)];pts.append(pts[0])
 pp=dd.addObject('Part::Feature','ProfilHex');rr.addObject(pp);pp.Shape=Part.makePolygon(pts)
 ex=dd.addObject('Part::Extrusion','Hexagone');rr.addObject(ex);ex.Base=pp;ex.Dir=A.Vector(0,0,H);ex.Solid=True;pp.Visibility=False
 return finish(dd,rr,cut(dd,rr,'Resultat',ex,[cyl(dd,rr,'Trou',diam/2,H+1,(0,0,-.5))]),'commerce')
def washer(name,di,do,h):
 dd,rr=new(name,'Acier200HV',{'Dinterieur':di,'Dexterieur':do,'Epaisseur':h})
 return finish(dd,rr,cut(dd,rr,'Resultat',cyl(dd,rr,'Anneau',do/2,h,(0,0,0)),[cyl(dd,rr,'Trou',di/2,h+1,(0,0,-.5))]),'commerce')
m2x8=bolt('EQ_ISO4762_M2x8_Dock20A',2,8,3.8,2)
m2x10=bolt('EQ_ISO4762_M2x10_Dock20A',2,10,3.8,2)
m2x6=bolt('EQ_ISO4762_M2x6_Dock20A',2,6,3.8,2)
m3x8=bolt('EQ_ISO4762_M3x8_Dock20A',3,8,5.5,3)
m3x16=bolt('EQ_ISO4762_M3x16_Dock20A',3,16,5.5,3)
m5x8=bolt('EQ_ISO4762_M5x8_Dock20A',5,8,8.5,5)
m2nut=nut('EQ_ISO4032_M2_Dock20A',2,4,1.6)
m3nut=nut('EQ_ISO4032_M3_Dock20A',3,5.5,2.4)
m5wash=washer('EQ_ISO7089_M5_Dock20A',5.3,10,1)
# PhoenixAWG10 : dimensionsprimaire3240028 ; isolationOD9 réservationàmesurer.
dd,rr=new('EQ_Phoenix3240028_Dock20A','Cuivre étamé + PA isolant',{'Longueur':26.7,'Largeur':9.5,'MetalT':1,'TrouD':5.3,'ManchonL':14,'ManchonDmaxEtude':9})
eye=cyl(dd,rr,'Oeil',4.75,1,(0,0,0),(0,1,0))
neck=box(dd,rr,'Patte',(8,1,9.5),(0,0,-4.75))
bar=cyl(dd,rr,'ManchonEnvelope',4.5,14,(7.95,.5,0),(1,0,0))
base=fuse(dd,rr,'CosseEnveloppe',[eye,neck,bar]);out=cut(dd,rr,'Resultat',base,[cyl(dd,rr,'TrouM5',2.65,3,(0,-1,0),(0,1,0)),cyl(dd,rr,'EntreeFil',3.3,15,(7.5,.5,0),(1,0,0))])
meta(rr,'MPN','3240028');meta(rr,'Source','https://www.phoenixcontact.com/en-us/products/ring-cable-lug-c-rci-6-m5-3240028');meta(rr,'Limite','Enveloppe dérivée dimensions primaires, aucune géométrie STEP. ODmanchon9 étude à mesurer ; vrai profil de sertissage et contact non qualifiés.')
lug=finish(dd,rr,out,'commerce')
# Boîtierprotecteur frontal, les têtesM5 restent entièrement dansleboot.
dd,rr=new('P46_ProtectionBornesFront20Ah','PA12 SLS candidat',{'Longueur':53,'Largeur':13.5,'Hauteur':38.51})
base=box(dd,rr,'Exterieur',(44,17,40.51),(116,-54.5,61.745))
tools=[box(dd,rr,'VideOuvertArriere',(43.5,15,38.51),(115.5,-53.5,62.745))]
# Biseau natif réduisant coin rotor avant−Y, sans couper manchon cosse nominal.
pts=[A.Vector(147,-54.5,60),A.Vector(161,-54.5,60),A.Vector(161,-50.5,60),A.Vector(147,-54.5,60)]
pf=dd.addObject('Part::Feature','ProfilBiseauRotor');rr.addObject(pf);pf.Shape=Part.makePolygon(pts)
ex=dd.addObject('Part::Extrusion','BiseauRotor');rr.addObject(ex);ex.Base=pf;ex.Dir=A.Vector(0,0,42.5);ex.Solid=True;pf.Visibility=False;tools.append(ex)
for i,z in enumerate([69.745,86.255]):tools.append(cyl(dd,rr,'SortieFil'+str(i),4.75,3,(158.5,-46,z),(1,0,0)))
for i,x in enumerate([122,134]):
 boss=box(dd,rr,'BossageClamp'+str(i),(6,4.5,6),(x-3,-42,94));base=fuse(dd,rr,'AvecBossage'+str(i),[base,boss])
 tools.append(cyl(dd,rr,'TrouClamp'+str(i),1.1,17,(x,-55,97),(0,1,0)))
 tools.append(cyl(dd,rr,'TrouClampBossage'+str(i),1.1,6,(x,-43,97),(0,1,0)))
for i,x in enumerate([148,155]):tools.append(cyl(dd,rr,'FixationP47_'+str(i),1.6,4,(x,-46,100)))
boot=finish(dd,rr,cut(dd,rr,'Resultat',base,tools))
# Support retourné connectorXT90, corps sous plafond, deuxcolliersrapprochentcorpsauplafond.
dd,rr=new('P47_SupportXT90Front20Ah','PA12 SLS candidat')
parts=[box(dd,rr,'Plafond',(27.5,65.9,3),(181.35,-10.4,87.45)),box(dd,rr,'FlancG',(3,65.9,8.45),(181.35,-10.4,82)),box(dd,rr,'FlancD',(3,65.9,8.45),(205.85,-10.4,82)),box(dd,rr,'Pied',(19,9,3),(144,-50,102.255)),box(dd,rr,'BrasLong',(7,43,3),(154,-50,102.255)),box(dd,rr,'BrasTraverse',(30.35,3,3),(154,-10,102.255)),box(dd,rr,'Montant',(3,3,17.805),(181.35,-10,87.45))]
body=fuse(dd,rr,'SupportPorteAFaux',parts);holes=[cyl(dd,rr,'M3_'+str(i),1.6,5,(x,-46,101.255))for i,x in enumerate([148,155])]
holes.append(box(dd,rr,'PassageFilsPack',(4,35.5,8.5),(181,20,79)))
meta(rr,'Limite','Porte-à-faux natif, rigidité/vibration/clampcolliers et effort câble à valider au banc. Connecteurs paire62mm est enveloppe conservatrice, longueurmating noncotée.')
holder=finish(dd,rr,cut(dd,rr,'Resultat',body,holes))
# BoîtiersAmass exactsdimensions des plans ; formesd’enveloppe seulement.
for name,mpn,L,W,H in [('EQ_AmassXT90HM_Dock20A','XT90H-M.G.Y',30.7,21.3,10.7),('EQ_AmassXT90SF_Dock20A','XT90S-F.G.Y',31.2,21.5,9.9)]:
 dd,rr=new(name,'PAAmass contactsCu',{'Longueur':L,'Largeur':W,'Hauteur':H});meta(rr,'MPN',mpn);meta(rr,'Limite','Enveloppe rectangulaire primaire Amass2025. Paire abuttée réservéeconservatrice ; vraie longueur pleinementmated etsortiescâbles à mesurer. Contacts/polaritéfonctionnelleàvalider.')
 body=box(dd,rr,'Enveloppe',(W,L,H),(-W/2,0,-H/2))
 ports=[cyl(dd,rr,'ReservationFil'+str(i),2.1 if 'HM_'in name else 2.8,12 if 'HM_'in name else 3,(x,-1 if 'HM_'in name else L-1,0),(0,1,0))for i,x in enumerate([-5.05,4.95])]
 finish(dd,rr,cut(dd,rr,'Resultat',body,ports),'commerce')
# Colliersdansposesmontées ; géométrie déformée correspondantau mêmeMPNcommercial.
def tie(name,W,H):
 dd,rr=new(name,'PA612 noir HellermannTyton',{'LargeurPose':W,'HauteurPose':H,'LargSangle':4.6,'EppEtude':1})
 outer=box(dd,rr,'Boucle',(4.6,W+2,H+2),(-2.3,-W/2-1,-1));inner=box(dd,rr,'Vide',(6,W,H),(-3,-W/2,0))
 meta(rr,'MPN','111-05012');meta(rr,'Limite','Représentation déformée MPN T50R200mm. Épaisseur1mm est réservation, dents/tête serrageetcheminexact nonreprésentés ; mesure etserrageauprototype.')
 return finish(dd,rr,cut(dd,rr,'Resultat',outer,[inner]),'commerce')
tiem= tie('EQ_T50R11105012_PoseModule20A',36,26)
tiec= tie('EQ_T50R11105012_PoseCommande20A',25.5,14)
tief= tie('EQ_T50R11105012_PoseXT9020A',27.5,13.9)
tiep= tie('EQ_T50R11105012_PoseReprise20A',44,32)
tieg= tie('EQ_T50R11105012_PoseGaines20A',26.5,13.5)
# Cordons10AWG : chemin3Dcandidat, continuité électrique sanspouvoirqualifierla courbure réelle.
for name,z0,R in [('EQ_Cordon10AWG_Plus_Dock20A',69.745,33.1),('EQ_Cordon10AWG_Moins_Dock20A',86.255,43.1)]:
 dd,rr=new(name,'TE55A0111 conducteur10AWG',{'DiametreMax':3.4,'RayonProjection':R,'DepartZ':z0,'FinZ':82})
 pts=[A.Vector(156.95+R*math.sin(t*math.pi/2),-46.5+38.1*(1-math.cos(t*math.pi/2)),z0+(82-z0)*t)for t in [i/20 for i in range(21)]]
 # Dernier point connectorfilaire : adaptateur bornes distinctesX190.05/200.05.
 cv=Part.BSplineCurve();cv.interpolate(pts);path=dd.addObject('Part::Feature','Chemin');rr.addObject(path);path.Shape=Part.Wire(cv.toShape())
 cir=dd.addObject('Part::Feature','SectionFil');rr.addObject(cir);cir.Shape=Part.Wire(Part.makeCircle(1.7,pts[0],A.Vector(1,0,(82-z0)/(R*math.pi/2))))
 sw=dd.addObject('Part::Sweep','Cordon');rr.addObject(sw);sw.Sections=[cir];sw.Spine=(path,['Edge1']);sw.Solid=True;sw.Frenet=False;path.Visibility=False;cir.Visibility=False
 meta(rr,'Limite','Chemin3Dinterpolé candidat pourencombrement. Rayoncourburecouplé R33.1/43.1mm, pas spécification minimumvalidée ; TEcoldbendmandrelØ76.2 necertifiepasce routage. Soudure10AWGAmass/Cosses3240028 àvalider.')
 finish(dd,rr,sw,'commerce')
# Packleads conservés : diamètreAWG8 isolantétude5mm, extrémités / sortielotàmesurer.
for name,y0,xend in [('EQ_LeadPack8AWG_Plus20A',-5,190.05),('EQ_LeadPack8AWG_Moins20A',5,200.05)]:
 dd,rr=new(name,'Câbles intégrés packTattuAWG8 150mm',{'DiametreEtude':5,'LongueurOrigine':150})
 pts=[A.Vector(99,y0,90),A.Vector(115,y0,90),A.Vector(145,30 if y0<0 else 40,85 if y0<0 else 94),A.Vector(xend,60 if y0<0 else 65,82),A.Vector(xend,53.5,82)]
 cv=Part.BSplineCurve();cv.interpolate(pts);p=dd.addObject('Part::Feature','Chemin');rr.addObject(p);p.Shape=Part.Wire(cv.toShape())
 c=dd.addObject('Part::Feature','Section');rr.addObject(c);c.Shape=Part.Wire(Part.makeCircle(2.5,pts[0],A.Vector(1,0,0)))
 sw=dd.addObject('Part::Sweep','Cordon');rr.addObject(sw);sw.Sections=[c];sw.Spine=(p,['Edge1']);sw.Solid=True;sw.Frenet=False;p.Visibility=False;c.Visibility=False
 meta(rr,'Limite','Départpack99/Y±2/Z90 est hypothèse à mesurer sur batterie. Faisceau150mm original nonmodifié ; cheminenveloppe tracé, longeurcad vérifiéeavantassemblage.');meta(rr,'LongueurChemin_mm',cv.toShape().Length)
 finish(dd,rr,sw,'commerce')
# Dernierscompléments fixes TE vers JETI ; les ports du module restent enveloppes à confirmer sur le kit8mm².
m5x20=bolt('EQ_ISO4762_M5x20_Dock20A',5,20,8.5,5)
m3x12=bolt('EQ_ISO4762_M3x12_Dock20A',3,12,5.5,3)
m3wash=washer('EQ_ISO7089_M3_Dock20A',3.2,7,.5)
frontnut=loadref('EQ_DIN934_M5_Dock')
dd,rr=new('P48_EntretoiseConductriceCuM5_Dock20Ah','CuivreC101',{'Longueur':12,'Diametre':9,'Alesage':5.3})
spacer=finish(dd,rr,cut(dd,rr,'Resultat',cyl(dd,rr,'Corps',4.5,12,(0,0,0)),[cyl(dd,rr,'Alésage',2.65,14,(0,0,-1))]))
# CosseAWG8dimensionsPhoenix ; ODcollerette10 est uniquement margeprovisoire.
dd,rr=new('EQ_Phoenix3240219_Dock20A','Cuivreétamé + PA',{'Longueur':31.3,'Largeur':8.8,'MetalT':1.1,'TrouD':5.3,'ManchonL':16,'ManchonDmaxEtude':10})
e=cyl(dd,rr,'Oeil',4.4,1.1,(0,0,0),(0,1,0));neck=box(dd,rr,'Patte',(10.9,1.1,8.8),(0,0,-4.4));man=cyl(dd,rr,'Manchon',5,16,(10.9,.55,0),(1,0,0))
meta(rr,'MPN','3240219');meta(rr,'Source','https://www.phoenixcontact.com/en-pc/products/ring-cable-lug-c-rci-10-m5-3240219');meta(rr,'Limite','Enveloppe primaire L31.3/W8.8/metal1.1 ; ODmanchon10hypothèse à mesurer. AWG8prévu adaptateurfixe.')
lug8=finish(dd,rr,cut(dd,rr,'Resultat',fuse(dd,rr,'CorpsCosse',[e,neck,man]),[cyl(dd,rr,'Trou',2.65,3,(0,-1,0),(0,1,0)),cyl(dd,rr,'EntreeCable',3.3,17,(10.4,.55,0),(1,0,0))]),'commerce')
# Boîtierfixe etsoncapot : interfacesdusupportP39 horslargeurhousing.
dd,rr=new('P49_ProtectionFixeTE20Ah','PA12 SLS candidat')
parts=[box(dd,rr,'Boitier',(17,45,60),(-191,-14,61))]
for i,z in enumerate([69.745,86.255]):parts.append(cyl(dd,rr,'TunnelBorne'+str(i),6,12,(-180,21.6535,z),(1,0,0)))
parts += [box(dd,rr,'PontNeg',(17,33,3),(-191,-47,82.5)),box(dd,rr,'PontPos',(17,18,3),(-191,29,82.5))]
for i,y in enumerate([-47,43]):parts += [box(dd,rr,'Bras'+str(i),(31,4,3),(-191,y,82.5)),box(dd,rr,'Bride'+str(i),(3,8,8),(-163,-49 if y<0 else 41,80))]
for i,(y,z) in enumerate([(-11,64),(28,118)]):parts.append(box(dd,rr,'BossageCap'+str(i),(8,6,6),(-191,y-3,z-3)))
base=fuse(dd,rr,'Protection',parts)
tools=[box(dd,rr,'Vide',(17.3,43,58),(-192,-13,62)),cyl(dd,rr,'SortieFilPlus',3.2,5,(-179.9,-16,70.5),(0,1,0)),cyl(dd,rr,'SortieFilMoins',3.2,4,(-179.9,21.6535,119)),box(dd,rr,'PassageArcPlus',(8.4,12.8,5.4),(-184.1,-47.2,81.8))]
for i,z in enumerate([69.745,86.255]):tools.append(cyl(dd,rr,'VideTunnel'+str(i),5.25,14,(-181,21.6535,z),(1,0,0)))
for i,y in enumerate([-45,45]):
 tools.append(cyl(dd,rr,'FixationSupport'+str(i),1.6,5,(-164,y,84),(1,0,0)))
 tools.append(cyl(dd,rr,'DegagementTeteSupport'+str(i),3.7,4,(-167,y,84),(1,0,0)))
# LesécrousM2reposentdansbossages etrestentaccessibles depuisbords externes.
for i,(y,z) in enumerate([(-11,64),(28,118)]):
 tools.append(cyl(dd,rr,'TrouCap'+str(i),1.1,11,(-193,y,z),(1,0,0)))
 pts=[A.Vector(-187,y+4.2/math.sqrt(3)*math.cos(k*math.pi/3),z+4.2/math.sqrt(3)*math.sin(k*math.pi/3))for k in range(6)];pts.append(pts[0])
 pp=dd.addObject('Part::Feature','ProfilEcrou'+str(i));rr.addObject(pp);pp.Shape=Part.makePolygon(pts)
 ex=dd.addObject('Part::Extrusion','PocheEcrou'+str(i));rr.addObject(ex);ex.Base=pp;ex.Dir=A.Vector(1.8,0,0);ex.Solid=True;pp.Visibility=False;tools.append(ex)
 tools.append(box(dd,rr,'AccesEcrou'+str(i),(1.8,5,4.8),(-187,-16 if y<0 else y,z-2.4)))
guard=finish(dd,rr,cut(dd,rr,'Resultat',base,tools))
dd,rr=new('P50_CapotProtectionFixeTE20Ah','PA12 SLS candidat')
base=box(dd,rr,'Plaque',(1,45,60),(-192,-14,61))
tools=[]
for i,(y,z) in enumerate([(-11,64),(28,118)]):tools.append(cyl(dd,rr,'TrouCap'+str(i),1.1,3,(-193,y,z),(1,0,0)))
guardcap=finish(dd,rr,cut(dd,rr,'Resultat',base,tools))
# SpliceTE34321exacte etgaineétude, utiliséeuniquementsurkitJETI8mm²confirmé.
dd,rr=new('EQ_TE34321_Splice8AWG_Dock20A','Cuivreétamé',{'Longueur':21.01,'DiametreExt':7.52,'DiametreInt':4.37})
meta(rr,'MPN','34321');meta(rr,'Source','https://www.te.com/en/product-34321.html');meta(rr,'Limite','Sertissageoutillage34321et sectionréelleJETI8mm²àvérifier ; nonutilisablepourfil6mm²sansvariantevalidée.')
splice=finish(dd,rr,cut(dd,rr,'Resultat',cyl(dd,rr,'Corps',3.76,21.01,(0,0,0)),[cyl(dd,rr,'Alésage',2.185,23,(0,0,-1))]),'commerce')
# ToussegmentsfixessontX<−175 tantqueZ<110, puisau-dessusplateau103.
fixedpaths={
 'EQ_CordonFixe8AWG_Plus20A':[(-179.9,-5.2465,69.745),(-185,-10,77),(-202,-10,98),(-218,-10,128),(-213,-8,145),(-192,-8,145),(-174,-8,145)],
 'EQ_CordonFixe8AWG_Moins20A':[(-179.9,21.6535,113.155),(-183,21.65,127),(-203,18,144),(-193,8,154),(-192,8,145),(-174,8,145)],
 'EQ_FactoryJETI_IN_Plus20A':[(-152.99,-8,145),(-142,-8,145),(-137,-8,139),(-135,-8,129),(-130,-8,123.5)],
 'EQ_FactoryJETI_IN_Moins20A':[(-152.99,8,145),(-142,8,145),(-137,8,139),(-135,8,129),(-130,8,123.5)]}
for name,pts0 in fixedpaths.items():
 dd,rr=new(name,'TE55A0111-8 (oustockJETI8mm² confirmé)',{'DiametreEtude':5})
 pts=[A.Vector(*x)for x in pts0];cv=Part.BSplineCurve();cv.interpolate(pts)
 pa=dd.addObject('Part::Feature','Chemin');rr.addObject(pa)
 if name.startswith('EQ_CordonFixe'):
  plus='Plus'in name; y=-55.2465 if plus else 21.6535
  edges=[]
  if plus:
   edges.append(Part.Arc(A.Vector(-179.9,-5.2465,69.745),A.Vector(-179.9,-40.601839,84.389661),A.Vector(-179.9,y,119.745)).toShape())
   start=A.Vector(-179.9,y,119.745)
  else:start=A.Vector(-179.9,y,113.155)
  edges.append(Part.makeLine(start,A.Vector(-179.9,y,155)))
  edges.append(Part.Arc(A.Vector(-179.9,y,155),A.Vector(-254.9,y,230),A.Vector(-329.9,y,155)).toShape())
  edges.append(Part.Arc(A.Vector(-329.9,y,155),A.Vector(-315.255339,y,119.644661),A.Vector(-279.9,y,105)).toShape())
  origin=A.Vector(-279.9,y,105);dy=(-8 if plus else 8)-y;dz=40
  delta=math.hypot(dy,dz);theta=math.acos(1-delta/100);unit=A.Vector(0,dy/delta,dz/delta);axis=A.Vector(1,0,0)
  mid1=origin+axis*(50*math.sin(theta/2))+unit*(50*(1-math.cos(theta/2)))
  join=origin+axis*(50*math.sin(theta))+unit*(delta/2)
  end=origin+axis*(100*math.sin(theta))+unit*delta
  mid2=end-axis*(50*math.sin(theta/2))-unit*(50*(1-math.cos(theta/2)))
  edges.extend([Part.Arc(origin,mid1,join).toShape(),Part.Arc(join,mid2,end).toShape(),Part.makeLine(end,A.Vector(-174,-8 if plus else 8,145))])
  pa.Shape=Part.Wire(edges);pts[0]=pa.Shape.Vertexes[0].Point
  tangent=A.Vector(0,-1,0)if plus else A.Vector(0,0,1)
 else:
  yy=-8 if 'Plus'in name else 8
  start=A.Vector(-152.99,yy,145);bend=A.Vector(-141.5,yy,145)
  middle=A.Vector(-141.5+11.5/math.sqrt(2),yy,133.5+11.5/math.sqrt(2));end=A.Vector(-130,yy,133.5)
  pa.Shape=Part.Wire([Part.makeLine(start,bend),Part.Arc(bend,middle,end).toShape(),Part.makeLine(end,A.Vector(-130,yy,123.5))])
  pts[0]=start;tangent=A.Vector(1,0,0)
 ci=dd.addObject('Part::Feature','Section');rr.addObject(ci);ci.Shape=Part.Wire(Part.makeCircle(2.5,pts[0],tangent))
 sw=dd.addObject('Part::Sweep','Cordon');rr.addObject(sw);sw.Sections=[ci];sw.Spine=(pa,[]);sw.Solid=True;sw.Frenet=False;pa.Visibility=False;ci.Visibility=False
 meta(rr,'LongueurChemin_mm',pa.Shape.Length);meta(rr,'Limite','TE fixe arcs tangentsR50minimum pourØétude5, longueur libre>152.4mm. Boucle externe hauteZ232.5 : retenue, vibration et masse à valider. PortsINJETI réservésX−130/Y±8/Z123.5, coudesstockR11.5 à contrôler selon notice réelle du kit. Aucunfilmodulecertifié8mm²avantmesure.')
 finish(dd,rr,sw,'commerce')

# Réservation d'entrée des fils, dérivée de l'enveloppe native du kit.
# Le produit commercial n'est ni percé ni modifié : ses ports doivent être mesurés.
dd,rr=new('EQ_JetiMainSwitch100_PortsEtude20A','Enveloppe du kit JETI, interfaces à mesurer')
dd.saveAs(str(MEC/'pieces/commerce/EQ_JetiMainSwitch100_PortsEtude20A.FCStd'))
original=link(dd,rr,'EnveloppeOriginale',loadref('EQ_JetiMainSwitch100'),(-130,-18,112))
tools=[cyl(dd,rr,'ReservationPort'+str(i),3,13,(-130,y,122.5))for i,y in enumerate([-8,8])]
meta(rr,'MPN','J-MSW-100-MS');meta(rr,'Limite','Ports réservés uniquement pour analyse d’intégration, non cotés par fabricant. Ne pas usiner le module. Relever sorties du lot et refaire le routage si elles diffèrent ; aucun accouplement réel qualifié.')
jetiports=finish(dd,rr,cut(dd,rr,'Resultat',original,tools),'commerce')

# Docktotal : touslienscomposantsavecflagsmobile et matrices pourauditindépendant.
d=A.newDocument('SA02A_Dock20Ah');root=d.addObject('App::Part','Ensemble');p=d.addObject('Spreadsheet::Sheet','Parametres');root.addObject(p);p.set('A60','ExtractionX');p.set('B60','0 mm');p.setAlias('B60','ExtractionX');d.saveAs(str(MEC/'sous_assemblages/SA02A_Dock20Ah.FCStd'))
meta(root,'Etat','À valider');meta(root,'RealisationCAO','Implémenté');meta(root,'Limite','ContactsTEanomalie STEP guides335mm3/dérivé1.99mm3, interfacesinternespartielles. Faisceau, tenue porte-à-faux etbornes nonqualifiés. Aucunequalificationvol.')
occrows=[]
def occ(name,ref,pos=(0,0,0),rot=None,mob=False):
 ll=link(d,root,name,ref,pos,rot);meta(ll,'Mobile','oui' if mob else 'non')
 if mob:ll.setExpression('LinkPlacement.Base.x',str(pos[0])+' mm + Parametres.ExtractionX')
 occrows.append({'objet':name,'reference':ref.Document.Name,'fichier':str(Path(ref.Document.FileName).relative_to(MEC)).replace('\\','/'),'source_objet':ref.Name,'mobile':mob,'placement_matrice':list(ll.LinkPlacement.toMatrix().A)});return ll
cass=A.openDocument(str(MEC/'sous_assemblages/SA02_Cassette20Ah_Coulissante.FCStd'))
proofcass=json.loads((MEC/'verification/construction_cassette20Ah_20261002.json').read_text(encoding='utf-8'))
skip={'VisFond0','VisFond1','EcrouFond0','EcrouFond1','VisSupportButee0','VisSupportButee1','VisPoignee1'}
# Une expression surtranslation signalele vrai mouvement dansla source.
for ll in cass.Objects:
 if ll.TypeId=='App::Link' and ll.Name not in skip:
  moving=bool(ll.ExpressionEngine) and any('ExtractionX' in x[1] for x in ll.ExpressionEngine)
  occ('Cass_'+ll.Name,ll.LinkedObject,tuple(ll.LinkPlacement.Base),ll.LinkPlacement.Rotation,moving)
contact=A.openDocument(str(MEC/'sous_assemblages/SA02_Contacts20Ah.FCStd'))
for ll in contact.Objects:
 if ll.TypeId=='App::Link':
  pos=tuple(ll.LinkPlacement.Base);rot=ll.LinkPlacement.Rotation
  if ll.Name=='VisFondMobile0':ref=m3x16;pos=(-104,-33,50)
  else:ref=ll.LinkedObject
  if ll.Name.startswith('EcrouSousFondMobile'):rot=A.Rotation(A.Vector(0,0,1),30)
  occ('Conn_'+ll.Name,ref,pos,rot,getattr(ll,'Mobile','non')=='oui')
# Printedprotections+2polaritésconducteurs.
for name in ['P43_ProtectionConducteurs20Ah','P44_CouvercleArriereConducteurs20Ah','P45_CouvercleLateralConducteurs20Ah']:
 occ(name,loadref(name,'fabriquees'),mob=True)
bar=loadref('P42_ConducteurCuCassette20Ah','fabriquees')
for i,z in enumerate([69.745,86.255]):
 occ('Conducteur'+str(i),bar,(0,0,z),mob=True)
 occ('CosseFrontal'+str(i),lug,(135,-46.5,z),mob=True)
 occ('VisM5ContactMobile'+str(i),m5x8,(-116.25,21.6535,z),A.Rotation(A.Vector(0,0,1),A.Vector(-1,0,0)),True)
 occ('RondelleM5ContactMobile'+str(i),m5wash,(-117.25,21.6535,z),A.Rotation(A.Vector(0,0,1),A.Vector(1,0,0)),True)
 occ('VisM5Frontal'+str(i),m5x8,(135,-47.5,z),A.Rotation(A.Vector(0,0,1),A.Vector(0,1,0)),True)
 occ('RondelleM5Frontal'+str(i),m5wash,(135,-47.5,z),A.Rotation(A.Vector(0,0,1),A.Vector(0,1,0)),True)
occ('VisPoigneeGaucheP43',m3x16,(115.5,-36,55),A.Rotation(A.Vector(0,0,1),A.Vector(-1,0,0)),True)
occ('BootFrontal',boot,mob=True);occ('PorteXT90',holder,mob=True)
for i,y in enumerate([-29,26]):
 occ('VisCapRear'+str(i),m2x10,(-110.15,y,97),A.Rotation(A.Vector(0,0,1),A.Vector(-1,0,0)),True)
 occ('EcrouCapRear'+str(i),m2nut,(-115.8,y,97),A.Rotation(A.Vector(0,0,1),A.Vector(1,0,0)),True)
for i,x in enumerate([-105,122,134]):
 occ('VisCapLat'+str(i),m2x10 if i>0 else m2x6,(x,-42 if i==0 else -37.5,97),A.Rotation(A.Vector(0,0,1),A.Vector(0,-1,0)),True)
 occ('EcrouCapLat'+str(i),m2nut,(x,-47.3,97),A.Rotation(A.Vector(0,0,1),A.Vector(0,1,0)),True)
for i,x in enumerate([148,155]):
 occ('VisPorteXT90_'+str(i),m3x8,(x,-46,105.255),A.Rotation(A.Vector(0,0,1),A.Vector(0,0,-1)),True)
 occ('EcrouPorteXT90_'+str(i),m3nut,(x,-46,98.855),A.Rotation(A.Vector(0,0,1),30),True)
occ('XT90Male',refs['EQ_AmassXT90HM_Dock20A'],(195.1,-8.4,82),mob=True)
occ('XT90FemellePack',refs['EQ_AmassXT90SF_Dock20A'],(195.1,22.3,82),mob=True)
for name in ['EQ_Cordon10AWG_Plus_Dock20A','EQ_Cordon10AWG_Moins_Dock20A','EQ_LeadPack8AWG_Plus20A','EQ_LeadPack8AWG_Moins20A']:occ(name,refs[name],mob=True)
# JETIfixed au-dessusplateau, 4collierscapturentcorps réelsaprèsrainuresP41.
occ('SupportJETI',loadref('P41_Support_Jeti_Dock20','fabriquees'))
occ('MainSwitchJETI',jetiports)
occ('CommandeMagnetiqueJETI',loadref('EQ_JetiMagneticSwitch'),(-125,35,112))
for i,x in enumerate([-112.4,-62.4]):occ('CollierJETI'+str(i),tiep if i==0 else tiem,(x,0,109))
for i,x in enumerate([-114.4,-86.4]):occ('CollierMag'+str(i),tiec,(x,47.75,109))
for i,y in enumerate([2,42]):occ('CollierXT90_'+str(i),tief,(195.1,y,76.55),A.Rotation(A.Vector(0,0,1),90),True)
for i,z in enumerate([69.745,86.255]):
 occ('EcrouBorneFront'+str(i),frontnut,(135,-44.5,z),A.Rotation(A.Vector(0,0,1),A.Vector(0,1,0)),True)
 occ('EntretoiseCuFixe'+str(i),spacer,(-179.353,21.6535,z),A.Rotation(A.Vector(0,0,1),A.Vector(1,0,0)))
 occ('CosseFixe'+str(i),lug8,(-180.453,21.6535,z),A.Rotation(A.Vector(1,0,0),-90 if i else 0).multiply(A.Rotation(A.Vector(0,0,1),-90)))
 occ('RondelleBorneFixe'+str(i),m5wash,(-181.453,21.6535,z),A.Rotation(A.Vector(0,0,1),A.Vector(1,0,0)))
 occ('VisBorneFixe'+str(i),m5x20,(-181.453,21.6535,z),A.Rotation(A.Vector(0,0,1),A.Vector(1,0,0)))
 occ('SpliceJETI'+str(i),splice,(-174,-8 if i==0 else 8,145),A.Rotation(A.Vector(0,0,1),A.Vector(1,0,0)))
occ('ProtectionFixeTE',guard);occ('CapotProtectionFixeTE',guardcap)
for i,y in enumerate([-45,45]):
 occ('VisProtectionFixe'+str(i),m3x12,(-163.5,y,84),A.Rotation(A.Vector(0,0,1),A.Vector(1,0,0)))
 occ('RondelleProtectionFixe'+str(i),m3wash,(-163.5,y,84),A.Rotation(A.Vector(0,0,1),A.Vector(1,0,0)))
 occ('EcrouProtectionFixe'+str(i),m3nut,(-158.9,y,84),A.Rotation(A.Vector(0,0,1),A.Vector(1,0,0)).multiply(A.Rotation(A.Vector(0,0,1),30)))
for i,(y,z) in enumerate([(-11,64),(28,118)]):
 occ('VisCapFixe'+str(i),m2x8,(-192,y,z),A.Rotation(A.Vector(0,0,1),A.Vector(1,0,0)))
 occ('EcrouCapFixe'+str(i),m2nut,(-187,y,z),A.Rotation(A.Vector(0,0,1),A.Vector(1,0,0)).multiply(A.Rotation(A.Vector(0,0,1),30)))
for name in fixedpaths:occ(name,refs[name])
occ('RepriseFaisceauFixe',loadref('P53_RepriseFaisceauFixe20Ah','fabriquees'))
occ('CollierRepriseGaines',tieg,(-163.4,0,136.75))
for i,y in enumerate([-8,8]):occ('IsolationSplice'+str(i),loadref('EQ_ATUM12_3_IsolationSplice20Ah'),(-185.5,y,145),A.Rotation(A.Vector(0,0,1),A.Vector(1,0,0)))
for name in ['P51_RetenueEquilibrage20Ah','P52_CapotEquilibrage20Ah']:occ(name,loadref(name,'fabriquees'),mob=True)
for name in ['EQ_EquilibragePack20Ah_Reservation','EQ_BoucleEquilibragePack20Ah_Reservation']:occ(name,loadref(name),mob=True)
for i,y in enumerate([-25,-11]):
 occ('VisRetenueEquilibrage'+str(i),m2x8,(131,y,48.5),A.Rotation(A.Vector(0,0,1),A.Vector(-1,0,0)),True)
 occ('EcrouRetenueEquilibrage'+str(i),m2nut,(123.4,y,48.5),A.Rotation(A.Vector(0,0,1),A.Vector(1,0,0)),True)
for i,(x,y) in enumerate([(133,-25.5),(152,-10.5)]):
 occ('VisCapotEquilibrage'+str(i),m2x6,(x,y,101.5),A.Rotation(A.Vector(0,0,1),A.Vector(0,0,-1)),True)
 occ('EcrouCapotEquilibrage'+str(i),m2nut,(x,y,96.5),A.Rotation(A.Vector(0,0,1),30),True)
d.recompute();d.save()
proof={'schema_version':1,'date':'2026-10-03','statut':'À valider','CAO':'Implémenté','assemblage':'sous_assemblages/SA02A_Dock20Ah.FCStd','root':'Ensemble','fichier_sha256':sha(d.FileName),'occurrences':occrows,'limites':['STEPTEbrutguides334.917mm3/dérivéguide1.98878mm3 documentés ; pas0blocageassertécontacts.','ComposantsPhoenix/XT90enveloppesprimaires, mandrels/courburescordon etpositionpacklead àmesurer.','FaisceauJETI fixe candidat construit pour kit8mm² à confirmer ; aucunby-passgroundautorisé.','6colliers111-05012 posesdéformées, épaisseurétude1mm etclamp àvalider.','Prototypeetqualificationthermique/structure non exécutés.']}
for n,r in refs.items():proof.setdefault('references',[]).append({'reference':n,'file':str(Path(r.Document.FileName).relative_to(MEC)).replace('\\','/'),'volume_mm3':r.Shape.Volume,'valid':r.Shape.isValid(),'solides':len(r.Shape.Solids),'sha256':sha(r.Document.FileName)})
(MEC/'verification/construction_dock20Ah_20261003.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'file':d.FileName,'occurrences':len(occrows),'references_new':len(refs)},ensure_ascii=False))



