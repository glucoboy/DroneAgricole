"""Contrôle géométrique dans un processus neuf, indépendant des sauvegardes."""
from pathlib import Path
import hashlib,json
import FreeCAD as A
import Part
ROOT=Path(__file__).resolve().parents[4];MEC=ROOT/'hardware/mecanique/cartographe';VER=MEC/'verification'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def bb(s):
 b=s.BoundBox;return [b.XMin,b.YMin,b.ZMin,b.XMax,b.YMax,b.ZMax]
def common(a,b):
 if not a.BoundBox.intersect(b.BoundBox):return 0
 return a.common(b).Volume
def inspect():
 integration=A.openDocument(str(MEC/'assemblages/Integration_Stack_Revue_20261003.FCStd'))
 for d in A.listDocuments().values():d.recompute()
 dock=next(d for d in A.listDocuments().values() if Path(d.FileName).stem=='SA02A_Dock20Ah')
 dist=next(d for d in A.listDocuments().values() if Path(d.FileName).stem=='SA07_Distribution_Systeme_Candidat')
 bad=[d.Name+'.'+o.Name for d in A.listDocuments().values() for o in d.Objects if 'Invalid' in o.State]
 links=[d.Name+'.'+o.Name for d in A.listDocuments().values() for o in d.Objects if o.TypeId=='App::Link' and (not o.LinkedObject or (hasattr(o,'Shape') and o.Shape.isNull()))]
 assert not bad and not links,(bad,links)
 forbidden=['XT90Male','XT90FemellePack','Conducteur0','Conducteur1','EQ_Cordon10AWG_Plus_Dock20A','MainSwitchJETI','SupportJETI']
 assert all(not dock.getObject(n) for n in forbidden)
 assert all(dist.getObject(n) for n in ['MainSwitchJETI','PM08','PDB18138'])
 assert all(dist.getObject(n).Shape.BoundBox.ZMax<dock.Cass_Batterie.Shape.BoundBox.ZMin for n in ['MainSwitchJETI','PM08','PDB18138'])
 names=['EQ_LeadPack8AWG_Plus20A','EQ_LeadPack8AWG_Moins20A','EQ_CordonFixe8AWG_Plus20A','EQ_CordonFixe8AWG_Moins20A']
 routes=[];hits=[]
 for name in names:
  cable=dock.getObject(name);src=cable.LinkedObject.Document;sw=src.Cordon;wire=sw.Spine[0].Shape
  assert sw.Shape.isValid() and len(sw.Shape.Solids)==1,name
  radii=[e.Curve.Radius for e in wire.Edges if isinstance(e.Curve,Part.Circle)];assert radii and min(radii)>49.999
  routes.append(dict(reference=name,longueur_mm=wire.Length,rayons_mm=radii,bbox_mm=bb(cable.Shape)))
  for o in dock.Objects:
   if o.TypeId=='App::Link' and o.Name!=name:
    v=common(cable.Shape,o.Shape)
    if v>1e-4:hits.append(dict(cable=name,autre='dock.'+o.Name,volume_mm3=v))
  for o in integration.Objects:
   if o.TypeId=='App::Link' and o.Name!='SA02A_Dock20Ah':
    v=common(cable.Shape,o.Shape)
    if v>1e-4:hits.append(dict(cable=name,autre='integration.'+o.Name,volume_mm3=v))
 # Dégagements des terminaisons et du faisceau d'équilibrage dans les coffrets.
 terminations=[]
 for name in ['CosseMobileDirecte0','CosseMobileDirecte1','Conn_ContactSocket39Plus','Conn_ContactSocket40Moins','EQ_BoucleEquilibragePack20Ah_Reservation']:
  source=dock.getObject(name)
  assert source,name
  for target in ['P43_ProtectionConducteurs20Ah','P44_CouvercleArriereConducteurs20Ah','P51_RetenueEquilibrage20Ah','P52_CapotEquilibrage20Ah']:
   obstacle=dock.getObject(target)
   if not obstacle:continue
   volume=common(source.Shape,obstacle.Shape)
   if volume>1e-4:terminations.append(dict(source=name,coffret=target,volume_mm3=volume))
 assert not hits and not terminations,(hits,terminations)
 # Extraction échantillonnée uniquement sur nouveaux coffrets/fils, pas preuve continue.
 samples=[]
 moving=[o for o in dock.Objects if o.TypeId=='App::Link' and getattr(o,'Mobile','non')=='oui']
 for shift in [0,10,25,50,100,200,350,500]:
  sample=[]
  for o in moving:
   if not (o.Name in names[:2] or o.Name.startswith(('P43','P44','P51','P52'))):continue
   s=o.Shape.copy();s.translate(A.Vector(shift,0,0))
   for fixed in ['Conn_SupportFixe','ProtectionFixeTE','CapotProtectionFixeTE']:
    v=common(s,dock.getObject(fixed).Shape)
    if v>1e-4:sample.append(dict(mobile=o.Name,fixe=fixed,volume_mm3=v))
  samples.append(dict(extraction_mm=shift,intersections=sample))
 assert all(not s['intersections'] for s in samples),samples
 bbox=bb(dock.Ensemble.Shape);allshape=Part.makeCompound([dock.Ensemble.Shape,dist.Reference.Shape]);combined=bb(allshape)
 proof=dict(date='2026-10-04',controle='T-CARTO-ETAGE-DIRECT-01',environnement='Windows amd64 / FreeCAD '+'.'.join(A.Version()[:3]),realisation_CAO='Implémenté',qualification='À valider',processus_neuf=True,erreurs_recalcul=bad,liens_non_resolus=links,occurrences_dock=len([o for o in dock.Objects if o.TypeId=='App::Link']),bbox_dock_mm=bbox,dimensions_dock_mm=[bbox[i+3]-bbox[i] for i in range(3)],bbox_batterie_et_energie_mm=combined,dimensions_batterie_et_energie_mm=[combined[i+3]-combined[i] for i in range(3)],positions_energie={n:bb(dist.getObject(n).Shape) for n in ['MainSwitchJETI','CommandeMagnetiqueJETI','PM08','PDB18138']},routes=routes,intersections_brutes=hits,extraction_echantillonnee=samples,sources_sha256={str(Path(d.FileName).relative_to(ROOT)).replace('\\','/'):sha(d.FileName) for d in A.listDocuments().values() if d.FileName and Path(d.FileName).stat().st_size<500000},finalisation_correcte=True,conclusion='préliminaire',limites=['Interfaces borne/fil intentionnelles à distinguer des collisions.','Échantillons extraction ne constituent pas preuve continue.','Cosses90/AWG8 et ports lot non qualifiés ; fixation coffrets/équilibrage, cantilever82mm et supportsP57 à valider.','TE152.4mm est une distance spatiale au premier bridage ; aucun bridage câble fixé procheTE représenté.','Sorties JETI/PM/PDB et faisceaux aval candidats à compléter ; pas de qualification matérielle.'])
 proof['intersections_terminaisons_coffrets']=terminations
 (VER/'controle_etage_batterie.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(json.dumps({k:proof[k] for k in ['dimensions_dock_mm','dimensions_batterie_et_energie_mm','intersections_brutes','extraction_echantillonnee']},ensure_ascii=False))
if __name__=='__main__':inspect()
