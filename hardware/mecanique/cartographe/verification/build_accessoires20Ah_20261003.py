"""Infrastructure CAO : isolation épissures et retenue du faisceau d'équilibrage."""
import json
from cad_dock20_helpers import *
rows=[]
def done(d,r,out,kind='fabriquees'):
    save(d,r,out,kind)
    rows.append({'reference':d.Name,'fichier':str(Path(d.FileName).relative_to(MEC)).replace('\\','/'),'sha256':sha(d.FileName),'solides':len(out.Shape.Solids),'valid':out.Shape.isValid()})

d,r=new('EQ_ATUM12_3_IsolationSplice20Ah','TE ATUM polyoléfine adhésive',{'LongueurPose':44,'DiametreEtude':10.5})
out=cut(d,r,'Resultat',cyl(d,r,'Exterieur',5.25,44,(0,0,0)),[cyl(d,r,'Interieur',3.8,46,(0,0,-1))])
meta(r,'MPN','ATUM-12/3-0-50MM');meta(r,'Source','https://www.te.com/en/product-NB08926001.html')
meta(r,'Limite','Réservation de gaine posée44mm autoursplice21.01mm, Ø10.5mm étude. Préparer50mm ; rétreint effectif sursplice7.52 etfils4.78/lotJETI à valider, ne pas chauffer le module ni la batterie.')
done(d,r,out,'commerce')

d,r=new('P51_RetenueEquilibrage20Ah','PA12 SLS candidat')
parts=[box(d,r,'Coffret',(33,14,13),(125,-25,87)),box(d,r,'Montant',(3,3,36),(128,-25,51)),box(d,r,'Pied',(3,22,8),(128,-29,46))]
for i,(x,y) in enumerate([(133,-25.5),(152,-10.5)]):parts.append(box(d,r,'Bossage'+str(i),(6,6,5),(x-3,y-3,95)))
base=fuse(d,r,'Support',parts)
tools=[box(d,r,'Vide',(30,11,12),(126.5,-23.5,88.5)),box(d,r,'EntreeFaisceau',(3,5,5),(124,-21,90))]
for i,y in enumerate([-25,-11]):tools.append(cyl(d,r,'FixationPoignee'+str(i),1.1,5,(127,y,48.5),(1,0,0)))
for i,(x,y) in enumerate([(133,-25.5),(152,-10.5)]):
    tools.append(cyl(d,r,'FixationCapot'+str(i),1.1,7,(x,y,94)))
    tools.append(box(d,r,'PocheEcrou'+str(i),(4.2,4.2,1.8),(x-2.1,y-2.1,96.5)))
    tools.append(box(d,r,'AccesEcrou'+str(i),(4.2,5,1.8),(x-2.1,y if i else y-5,96.5)))
meta(r,'Limite','Retenue de la prise et boucle d’équilibrage fournies avec le pack ; position réelle du départ, genre et dimensions à mesurer. Aucun branchement de charge dans le drone.')
done(d,r,cut(d,r,'Resultat',base,tools))
d,r=new('P52_CapotEquilibrage20Ah','PA12 SLS candidat')
base=box(d,r,'Plaque',(33,21,1.5),(125,-29,100))
tools=[cyl(d,r,'Trou'+str(i),1.1,3,(x,y,99))for i,(x,y)in enumerate([(133,-25.5),(152,-10.5)])]
done(d,r,cut(d,r,'Resultat',base,tools))
d,r=new('EQ_EquilibragePack20Ah_Reservation','Prise et fils fournis dans BAT20',{'LongueurEtude':22,'LargeurEtude':8,'HauteurEtude':10})
meta(r,'Limite','Enveloppe22×8×10mm, genre JST-XH7 positions à confirmer sur lot. Ce volume n’est pas un STEP fabricant.')
done(d,r,box(d,r,'Enveloppe',(22,8,10),(133,-22,89)),'commerce')
d,r=new('EQ_BoucleEquilibragePack20Ah_Reservation','Fils AWG22 fournis dans BAT20')
pts=[A.Vector(99,-18,92),A.Vector(115,-18,92),A.Vector(131,-18,92)]
path=d.addObject('Part::Feature','Chemin');r.addObject(path);path.Shape=Part.makePolygon(pts)
sec=d.addObject('Part::Feature','Section');r.addObject(sec);sec.Shape=Part.Wire(Part.makeCircle(1.75,pts[0],A.Vector(1,0,0)))
sw=d.addObject('Part::Sweep','Faisceau');r.addObject(sw);sw.Sections=[sec];sw.Spine=(path,[]);sw.Solid=True;path.Visibility=False;sec.Visibility=False
meta(r,'Limite','Réservation du bundle tenu en coffret, point de sortie étudié à mesurer. Le mou des fils150mm doit être rangé dans le coffret avant insertion ; contrôle réel indispensable.')
done(d,r,sw,'commerce')
(MEC/'verification/construction_accessoires20Ah_20261003.json').write_text(json.dumps({'date':'2026-10-03','statut':'À valider','realisation_CAO':'Implémenté','references':rows},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(rows,ensure_ascii=False))

# Reprise fixe après la longueur libre TE : capture de la plaque sur le cadre
# JETI par un collier partagé, retenue des deux gaines par un second collier.
d,r=new('P53_RepriseFaisceauFixe20Ah','PA12 SLS candidat')
parts=[box(d,r,'Plateau',(85,30,3),(-190,-15,136.75))]
for i,y in enumerate([-14,11]):parts.append(box(d,r,'PorteeModule'+str(i),(8,3,1.75),(-116,y,135)))
for i,y in enumerate([-22,14]):parts.append(box(d,r,'AppuiCadre'+str(i),(29,8,3),(-134,y,138)))
base=fuse(d,r,'Reprise',parts)
tools=[box(d,r,'PassageCollier'+str(i),(5.2,2,6),(-166,y,135.75))for i,y in enumerate([-14.75,12.75])]
for i,y in enumerate([-8,8]):tools.append(box(d,r,'PassageFilKit'+str(i),(14,6.4,6),(-140,y-3.2,135.75)))
meta(r,'Fixations','Premier collier JETI partagé, boucle44×32mm autourP41 et appuisP53 ; deux portées sousP53 chargent le dessus du module. Un collier supplémentaire autour des deux gainesATUM et plateau. Aucune vis ni perforation du kit.')
meta(r,'Limite','Reprise située près des épissures après559/476mm libres ; rigidité, calage des portées sur boîtier réel, dissipation et tenue de la boucle sous vibration à contrôler. La longueur libre TE152.4mm est conservée.')
done(d,r,cut(d,r,'Resultat',base,tools))
(MEC/'verification/construction_accessoires20Ah_20261003.json').write_text(json.dumps({'date':'2026-10-03','statut':'À valider','realisation_CAO':'Implémenté','references':rows},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
