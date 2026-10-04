"""Conducteurs cuivre et protections natifs de la cassette ; infrastructure CAO.

Les conducteurs rigides évitent un départ de fil axial vers le softpack.
Leur tenue thermique, leur fabrication pliée et les câbles frontaux sont à valider.
"""
import json, math
from cad_dock20_helpers import *

z0=69.745; z1=86.255; tail=-118.25
refs={}; rows=[]
def finish(d,r,s):
    save(d,r,s);refs[d.Name]=r
    rows.append({'reference':d.Name,'volume_mm3':s.Shape.Volume,
        'fichier':'pieces/fabriquees/'+d.Name+'.FCStd','valide':s.Shape.isValid(),
        'solides':len(s.Shape.Solids),'sha256':sha(d.FileName)})

d,r=new('P42_ConducteurCuCassette20Ah','Cuivre C101, épaisseur1mm, section10mm2 ; fabrication et courant à valider',
    {'Epaisseur':1,'SectionHauteur':10,'RayonPliInterieur':1,'LongueurLongitudinale':251.25})
parts=[box(d,r,'BrancheTerminaison',(1,65.1535,10),(tail,-43.5,-5)),
       box(d,r,'PadContact',(1,12,12),(tail,15.6535,-6)),
       box(d,r,'BrancheLongitudinale',(251.25,1,10),(-116.25,-45.5,-5)),
       box(d,r,'PadFrontal',(12,1,12),(129,-45.5,-6))]
# Pli à90°, rayonintérieur1 : secteur de tube, extrusion native.
outer=cyl(d,r,'PliExterieur',2,10,(-116.25,-43.5,-5))
inner=cyl(d,r,'PliInterieur',1,12,(-116.25,-43.5,-6))
ring=cut(d,r,'AnneauPli',outer,[inner])
q=box(d,r,'QuadrantPli',(2,2,10),(tail,-45.5,-5))
bend=d.addObject('Part::Common','Pli90');r.addObject(bend);bend.Base=ring;bend.Tool=q
ring.Visibility=False;q.Visibility=False;parts.append(bend)
body=fuse(d,r,'ConducteurPlie',parts)
holes=[cyl(d,r,'M5Contact',2.65,3,(tail-1,21.6535,0),(1,0,0)),
       cyl(d,r,'M5Frontal',2.65,3,(135,-46.5,0),(0,1,0))]
final=cut(d,r,'Resultat',body,holes)
meta(r,'Fabrication','Découpe de cuivre C101 ép1mm, ébavurage et pli90°Rint1mm ; montageM5. Géométrie pliée définie, développé et procédé à vérifier par fabricant.')
meta(r,'Isolation','Entièrement sousP43/P44/P45, jeuxnominal0.5mm ; l’échange porte la cassette et ces conducteurs.')
finish(d,r,final)

# Boîtier arrière et canal longitudinal : deux canaux séparés, accès de maintenance.
d,r=new('P43_ProtectionConducteurs20Ah','PA12 SLS ; rigidité et isolation à valider')
body=fuse(d,r,'Boitier',[box(d,r,'ProtectionArriere',(9.65,77.1535,38.51),(-120.8,-47.5,61.745)),
    box(d,r,'ProtectionLongue',(258.8,5,37.51),(-120.8,-47.5,62.745)),
    box(d,r,'FixationArriere',(26,8,2),(-126,-37,48)),
    box(d,r,'MontantArriere',(5,8,16),(-124,-37,49)),
    box(d,r,'FixationAvant',(3,10,26),(112.5,-45,43)),
    box(d,r,'PontAvant',(12.5,5,5),(103,-47.5,64))])
tools=[]
for i,z in enumerate((z0,z1)):
    tools.extend([box(d,r,'CaviteArriere'+str(i),(12,75.1535,13),(-119.8,-46.5,z-6.5)),
        box(d,r,'Canal'+str(i),(260,4,13),(-120.8,-46.5,z-6.5)),
        cyl(d,r,'PassageContact'+str(i),5.5,10,(-122,21.6535,z),(1,0,0)),
        cyl(d,r,'PassageFrontal'+str(i),5.2,12,(135,-49,z),(0,1,0))])
# Ouverture du côté+Y du rail et de la face+X du boîtier.
tools.extend([box(d,r,'OuvertureRail',(263,2,39),(-122,-43,62)),
    box(d,r,'OuvertureArriere',(2,72,29),(-112.15,-45,63.5)),
    cyl(d,r,'VisPartageeFond',1.6,8,(-104,-33,45)),
    cyl(d,r,'VisPartageePoignee',1.6,6,(111.5,-36,55),(1,0,0))])
for i,x in enumerate((-105,122,134)):
    tools.append(cyl(d,r,'TrouCouvercle'+str(i),1.1,11,(x,-50,97),(0,1,0)))
# Captures réelles des écrous M2, hors des deux canaux cuivre.
# Les entrées de montage restent accessibles depuis le haut/les bords.
def pocket_m2(name,pos,axis):
    pts=[A.Vector(4.2/math.sqrt(3)*math.cos(k*math.pi/3),4.2/math.sqrt(3)*math.sin(k*math.pi/3),0) for k in range(6)];pts.append(pts[0])
    pf=d.addObject('Part::Feature',name+'Profil');r.addObject(pf);pf.Shape=Part.makePolygon(pts)
    pf.Placement=A.Placement(A.Vector(*pos),A.Rotation(A.Vector(0,0,1),A.Vector(*axis)))
    ex=d.addObject('Part::Extrusion',name);r.addObject(ex);ex.Base=pf;ex.Dir=A.Vector(*axis)*1.8;ex.Solid=True;pf.Visibility=False
    return ex
for i,y in enumerate((-29,26)):
    tools.append(cyl(d,r,'TrouArriereM2'+str(i),1.1,12,(-121,y,97),(1,0,0)))
    tools.append(pocket_m2('EcrouArriereM2_'+str(i),(-115.9,y,97),(1,0,0)))
    tools.append(box(d,r,'AccesEcrouArriere'+str(i),(1.8,5.5,4.8),(-115.9,-49 if y<0 else y,94.6)))
for i,x in enumerate((-105,122,134)):
    # Bossage extérieur isolé ne traverse pas la trajectoire des colonnes x±52.
    pad=box(d,r,'BossageEcrouLateral'+str(i),(5.5,2.8,5.5),(x-2.75,-47.5,94.25))
    body=fuse(d,r,'BoitierAvecBossage'+str(i),[body,pad])
    tools.append(pocket_m2('EcrouLateralM2_'+str(i),(x,-47.4,97),(0,1,0)))
    tools.append(box(d,r,'AccesEcrouLateral'+str(i),(5,1.8,4),(x-2.5,-47.4,97)))
tools.append(box(d,r,'DegagementBrasPoignee',(4,4,5),(112,-38,46)))
tools.append(cyl(d,r,'DegagementVisHousingM4',2.3,5,(-122,-36.0045,78),(1,0,0)))
final=cut(d,r,'Resultat',body,tools)
meta(r,'Fixations','UneM3×16 partagée avecP40/fond àX−104/Y−33 ; vispoignéeGauche M3×16 depuisX115.5 enremplacementM3×12 ; oreilleP43X112.5..115.5 contreP33, trouZ55 ; troisM2×8 pourP45. Vismaintenancesecouvertureshorséchange.')
finish(d,r,final)

d,r=new('P44_CouvercleArriereConducteurs20Ah','PA12 SLS ; accès et isolation à valider')
b=box(d,r,'Plaque',(1,71.6535,37.755),(-111.15,-42,61.745))
# Deux perçages permettent la fixation du couvercle au support par vis traversantes.
hs=[cyl(d,r,'Trou'+str(i),1.1,3,(-112.15,y,97),(1,0,0)) for i,y in enumerate((-29,26))]
finish(d,r,cut(d,r,'Resultat',b,hs))

d,r=new('P45_CouvercleLateralConducteurs20Ah','PA12 SLS ; accès et isolation à valider')
b=box(d,r,'Plaque',(258.8,1,37.51),(-120.8,-43,62.745))
hs=[cyl(d,r,'Trou'+str(i),1.1,3,(x,-44,97),(0,1,0)) for i,x in enumerate((-105,122,134))]
hs.extend(cyl(d,r,'DegagementEcrouPuissance'+str(i),5.2,3,(135,-44,z),(0,1,0)) for i,z in enumerate((z0,z1)))
hs.extend(box(d,r,'PassageCuivre'+str(i),(2,3,11),(-118.75,-44,z-5.5)) for i,z in enumerate((z0,z1)))
finish(d,r,cut(d,r,'Resultat',b,hs))

proof={'date':'2026-10-02','statut':'À valider','CAO':'Implémenté','references':rows,
    'section_conducteur_mm2':10,'cuivre_densite_hypothese_g_cm3':8.96,
    'positions_conducteurs_mm':[[0,0,z0],[0,0,z1]],
    'fixations_a_integrer':['1 M3x16 remplacevisfondP40gaucheM3x14','1 vispoignéeGaucheM3×16 trouZ55',
        '3 ISO4762M2x8 + écrousISO4032M2 captifs','2 ISO4762M2x10 + écrousISO4032M2 captifsP44'],
    'limites':['Modèle de conducteurs et boîtier, pas qualification électrique.',
        'Cosses, cordons frontaux et accèsborneM5 à intégrer et vérifier sur leur forme réelle.',
        'PochesécrousM2 natives ajoutées et fixations remontéesZ97 ; disponibilitémontage à vérifier au prototype.',
        'ContactspacketmoduleJETI sanscourbechargequalifiée.']}
(MEC/'verification/construction_conducteurs20Ah_20261002.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(rows,ensure_ascii=False))




