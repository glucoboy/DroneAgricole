"""Relecture native neuve et collisions BMS/cassette ; jamais qualification physique."""
from pathlib import Path
import hashlib,json,sys
import FreeCAD as A,Part
ROOT=Path(__file__).resolve().parents[4];MEC=ROOT/'hardware/mecanique/cartographe';VER=MEC/'verification'
def bb(s):
 b=s.BoundBox;return [b.XMin,b.YMin,b.ZMin,b.XMax,b.YMax,b.ZMax]
def common(a,b):return a.common(b).Volume if a.BoundBox.intersect(b.BoundBox) else 0
def main():
 top=A.openDocument(str(MEC/'assemblages/Integration_Stack_Revue_20261003.FCStd'))
 for d in A.listDocuments().values():d.recompute()
 dock=next(d for d in A.listDocuments().values() if Path(d.FileName).stem=='SA02A_Dock20Ah');dist=next(d for d in A.listDocuments().values() if Path(d.FileName).stem=='SA07_Distribution_Systeme_Candidat')
 invalid=[d.Name+'.'+o.Name for d in A.listDocuments().values() for o in d.Objects if 'Invalid' in o.State]
 broken=[d.Name+'.'+o.Name for d in A.listDocuments().values() for o in d.Objects if o.TypeId=='App::Link' and (not o.LinkedObject or o.Shape.isNull())]
 assert not invalid and not broken,(invalid,broken)
 new=[o for o in dock.Objects if o.TypeId=='App::Link' and (o.Name.startswith(('BMS_','P43_','P44_','EQ_BMS_','EQ_LeadPack','EQ_BoucleEquilibrage','EQ_BouclePresence','EQ_CordonFixe','AppuiIsolationBMS')))]
 hits=[]
 others=[o for o in dock.Objects if o.TypeId=='App::Link']
 for o in new:
  for q in others:
   if q==o:continue
   if q in new and q.Name<o.Name:continue
   v=common(o.Shape,q.Shape)
   if v>.001:hits.append(dict(objet=o.Name,autre=q.Name,volume_mm3=v))
  for q in top.Objects:
   if q.TypeId=='App::Link' and q.Name not in ['SA02A_Dock20Ah','SA08_Faisceau_Systeme_Candidat']:
    v=common(o.Shape,q.Shape)
    if v>.001:hits.append(dict(objet=o.Name,autre='integration.'+q.Name,volume_mm3=v))
 iso=dist.InterfaceBMSIsolee
 for q in top.Objects:
  if q.TypeId=='App::Link' and q.Name not in ['SA07_Distribution_Systeme_Candidat','SA08_Faisceau_Systeme_Candidat']:
   v=common(iso.Shape,q.Shape)
   if v>.001:hits.append(dict(objet=iso.Name,autre='integration.'+q.Name,volume_mm3=v))
 for q in dist.Objects:
  if q.TypeId=='App::Link' and q!=iso:
   v=common(iso.Shape,q.Shape)
   if v>.001:hits.append(dict(objet=iso.Name,autre=q.Name,volume_mm3=v))
 # BMS/coffret/fils doivent suivre la même extraction ; contacts électriquescandidats exclus.
 samples=[]
 for x in [0,10,25,50,100,200,350,500]:
  found=[]
  for o in new:
   if getattr(o,'Mobile','non')!='oui':continue
   s=o.Shape.copy();s.translate(A.Vector(x,0,0))
   for q in [dock.Conn_SupportFixe,dock.ProtectionFixeTE,dock.CapotProtectionFixeTE]:
    v=common(s,q.Shape)
    if v>.001:found.append(dict(objet=o.Name,autre=q.Name,volume_mm3=v))
  samples.append(dict(extraction_mm=x,intersections=found))
 shape=Part.makeCompound([dock.Ensemble.Shape,dist.Reference.Shape]);bounds=bb(shape)
 proof=dict(date='2026-10-05',test='T-CARTO-BMS-02-CAO',processus_neuf=True,FreeCAD='.'.join(A.Version()[:3]),erreurs_recalcul=invalid,liens_non_resolus=broken,bbox_BMS_mm=bb(dock.BMS_JBD.Shape),bbox_coffret_mm=bb(dock.P43_ProtectionConducteurs20Ah.Shape),bbox_batterie_et_energie_mm=bounds,dimensions_batterie_et_energie_mm=[bounds[i+3]-bounds[i] for i in range(3)],intersections_brutes=hits,extraction_echantillonnee=samples,sources_sha256={str(Path(d.FileName).relative_to(ROOT)).replace('\\','/'):hashlib.sha256(Path(d.FileName).read_bytes()).hexdigest() for d in A.listDocuments().values() if d.FileName and Path(d.FileName).is_relative_to(ROOT)},qualification='À valider',limites=['EnveloppePCBtolérancée seulement, bornes/prises/dissipateurBMSnonconfirmés.','InterfaceWaveshareenréservation90×80×26, contacts#20enveloppesprovisoires,cavitésnumérotéesàconfirmer.','Ports/sections/rayons/sertissages/maintien/touchsafe/thermiqueetlotaqualifier.','Échantillonnageextractionneprouvepascontinuitédecourse niinterférencesprototypeslot.'],finalisation_correcte=False)
 intended={frozenset(['EQ_BoucleEquilibragePack20Ah_Reservation','EQ_EquilibragePack20Ah_Reservation']):'Entrée du câble dans réservation JST ; accouplement physique à valider',frozenset(['EQ_BMS_PMoins_TE20A','CosseMobileDirecte1']):'Fil dans fut de cosse négative ; sertissage à valider',frozenset(['EQ_BMS_BPlus_Liaison20A','EQ_LeadPack8AWG_Plus20A']):'Jonction B+ commune réservée ; terminaison de branche et isolation à définir'}
 proof['interfaces_intentionnelles']=[dict(h,justification=intended[frozenset([h['objet'],h['autre']])]) for h in hits if frozenset([h['objet'],h['autre']]) in intended]
 proof['intersections_non_resolues']=[h for h in hits if frozenset([h['objet'],h['autre']]) not in intended]
 proof['finalisation_correcte']=not invalid and not broken and not proof['intersections_non_resolues'] and all(not s['intersections'] for s in samples)
 (VER/'controle_bms_cassette.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(json.dumps({k:proof[k] for k in ['intersections_brutes','extraction_echantillonnee','dimensions_batterie_et_energie_mm','finalisation_correcte']},ensure_ascii=False))
if __name__=='__main__':main()
