"""Support à captures périphériques et colliers, sans perçage du module JETI."""
import json
from cad_dock20_helpers import *

d,r=new('P41_Support_Jeti_Dock20','PA12 SLS ; tenue et température à valider',{'Epaisseur':3,'CorpsL':80,'CorpsW':36,'CorpsH':23})
parts=[box(d,r,'Fond',(87,42,3),(-134,-21,109))]
for i,y in enumerate((-21,18)):
    parts.append(box(d,r,'Paroi'+str(i),(87,3,26),(-134,y,112)))
for i,x in enumerate((-134,-50)):
    parts.append(box(d,r,'CaptureBout'+str(i),(3,42,5),(x,-21,112)))
for i,y in enumerate((-34,18)):
    parts.append(box(d,r,'Oreille'+str(i),(24,16,2),(-60,y,108)))
# Cadre de commande magnétique, retenu par colliers, sans trous fournisseur inventés.
parts.append(box(d,r,'FondCommande',(51,31.5,3),(-128,32,109)))
for i,y in enumerate((32,60.5)):
    parts.append(box(d,r,'BordCommande'+str(i),(51,3,12),(-128,y,112)))
for i,x in enumerate((-128,-80)):
    parts.append(box(d,r,'BoutCommande'+str(i),(3,31.5,5),(x,32,112)))
parts.append(box(d,r,'PontCommande',(12,15,3),(-120,18,109)))
body=fuse(d,r,'Structure',parts)
holes=[cyl(d,r,'Fixation'+str(i),1.1,5,(-43,y,107)) for i,y in enumerate((-29,29))]
for i,x in enumerate((-115,-65)):
    for j,y in enumerate((-22,17)):
        holes.append(box(d,r,'PassageCollier'+str(i)+str(j),(5.2,7 if i==0 and j==1 else 5,31),(x,y,108.5)))
for i,x in enumerate((-117,-89)):
    for j,y in enumerate((31.5,60)):
        holes.append(box(d,r,'PassageCollierCommande'+str(i)+str(j),(5.2,4.5,17),(x,y,108.5)))
result=cut(d,r,'Resultat',body,holes)
meta(r,'Fixations','Deux vis ISO4762 M2x10 en remplacement des deux M2x8 de P27 à X=-43,Y=±29 ; quatre colliers HellermannTyton T50R 111-05012.')
meta(r,'Limite','Capture géométrique et support construits ; tenue des colliers, feu, thermique, variante exacte commande et câbles à contrôler au banc. Aucun perçage dans les produits JETI.')
save(d,r,result)
p=MEC/'verification/construction_support_jeti20Ah_20261002.json'
p.write_text(json.dumps({'date':'2026-10-02','statut':'À valider','realisation_CAO':'Implémenté','script_sha256':sha(__file__),'reference':d.Name,'volume_mm3':result.Shape.Volume,'forme_valide':result.Shape.isValid(),'fixations':['2 ISO4762 M2x10 partagées P27','4 HellermannTyton T50R 111-05012'],'module_position_mm':[-130,-18,112],'commande_position_mm':[-125,35,112]},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(d.Name,result.Shape.Volume)


