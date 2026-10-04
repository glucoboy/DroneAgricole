"""Infrastructure FreeCAD : variante durable complète20Ah, liens externes."""
from pathlib import Path
import json,hashlib
import FreeCAD as A,Part
ROOT=Path(__file__).resolve().parents[4];MEC=ROOT/'hardware/mecanique/cartographe'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def ref(name):
 p=MEC/'sous_assemblages'/(name+'.FCStd');d=A.openDocument(str(p))
 return d.getObject('Ensemble')or d.getObject('Reference')
d=A.newDocument('Drone_Cartographe_20Ah');r=d.addObject('App::Part','Ensemble')
r.addProperty('App::PropertyString','Etat').Etat='À valider';r.addProperty('App::PropertyString','RealisationCAO').RealisationCAO='Implémenté'
d.saveAs(str(MEC/'assemblages/Drone_Cartographe_20Ah.FCStd'))
names=['SA01_Chassis_Rehausse20','SA02_Cassette20Ah_Coulissante','SA03_Avionique_Rehausse20','SA04_Calcul','SA05_Capteurs_Isoles','SA06_RTK']
if (MEC/'sous_assemblages/SA02A_Dock20Ah.FCStd').exists():names[1]='SA02A_Dock20Ah'
for name in names:
 target=ref(name);o=d.addObject('App::Link',name);r.addObject(o);o.setLink(target);o.LinkTransform=False;o.LinkPlacement=A.Placement()
for dd in A.listDocuments().values():dd.recompute()
d.save()
old=A.openDocument(str(MEC/'assemblages/Systeme_Cartographie.FCStd'))
system=A.newDocument('Systeme_Cartographie_20Ah');sr=system.addObject('App::Part','Ensemble')
sr.addProperty('App::PropertyString','Etat').Etat='À valider';sr.addProperty('App::PropertyString','RealisationCAO').RealisationCAO='Implémenté'
system.saveAs(str(MEC/'assemblages/Systeme_Cartographie_20Ah.FCStd'))
for source in old.Objects:
 if source.TypeId!='App::Link':continue
 target=r if 'Drone'in source.Name else source.LinkedObject
 o=system.addObject('App::Link',source.Name);sr.addObject(o);o.setLink(target);o.LinkTransform=False;o.LinkPlacement=source.LinkPlacement
system.recompute();system.save()
reachable={};queue=[system]
while queue:
 dd=queue.pop()
 if dd.Name in reachable:continue
 reachable[dd.Name]=dd
 for obj in dd.Objects:
  if obj.TypeId=='App::Link'and obj.LinkedObject:queue.append(obj.LinkedObject.Document)
rows=[]
for dd in reachable.values():
 if not dd.FileName:continue
 for o in dd.Objects:
  if o.TypeId=='App::Link'and o.LinkedObject:
   rows.append({'assemblage':str(Path(dd.FileName).relative_to(MEC)).replace('\\','/'),'nom':o.Name,'source_fichier':str(Path(o.LinkedObject.Document.FileName).relative_to(MEC)).replace('\\','/'),'source_objet':o.LinkedObject.Name,'matrice_placement':list(o.LinkPlacement.toMatrix().A),'LinkTransform':o.LinkTransform})
proof={'date':'2026-10-02','statut':'À valider','realisation_CAO':'Implémenté','racine':'assemblages/Systeme_Cartographie_20Ah.FCStd','racine_drone':'assemblages/Drone_Cartographe_20Ah.FCStd','source_objet':'Ensemble','occurrences':rows,'fichiers':[{'fichier':str(Path(dd.FileName).relative_to(MEC)).replace('\\','/'),'sha256':sha(Path(dd.FileName))}for dd in reachable.values()if dd.FileName],'erreurs':[{'document':dd.Name,'objet':o.Name,'etat':list(o.State)}for dd in reachable.values()for o in dd.Objects if 'Invalid'in o.State]}
(MEC/'verification/hierarchie_20Ah_20261002.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'liens':len(rows),'erreurs':proof['erreurs'],'sous_assemblages':names}),flush=True)

