"""Réouverture indépendante des routes effectivement sauvegardées dans SA08."""
from update_routes_systeme_candidat import obstacles,sha,relative,MEC,VER,dump
import FreeCAD as A,Part,json
top,obs=obstacles()
sa=top.getObject('SA08_Faisceau_Systeme_Candidat');assert sa and sa.LinkedObject
h=sa.LinkedObject.Document;data=json.loads((VER/'routes_systeme_candidat_20261003.json').read_text(encoding='utf-8'))
rows=[]
for row in data['routes']:
 o=h.getObject(row['id']);assert o and o.LinkedObject,row['id'];src=o.LinkedObject.Document
 wire=src.CheminArrondi.Shape;s=o.Shape;assert s.isValid() and len(s.Solids)==1,row['id']
 hits=[]
 for name,obstacle in obs:
  if s.BoundBox.intersect(obstacle.BoundBox):
   v=s.common(obstacle).Volume
   if v>1e-6:hits.append(dict(objet=name,volume_mm3=v))
 radii=[e.Curve.Radius for e in wire.Edges if isinstance(e.Curve,Part.Circle)]
 rows.append(dict(id=row['id'],wxx=row['wxx'],fichier=relative(src.FileName),sha256=sha(src.FileName),longueur_mm=wire.Length,rayons_mm=radii,forme_valide=s.isValid(),solides=len(s.Solids),intersections=hits))
 print(row['id']+': '+str(len(hits))+' intersections',flush=True)
invalid=[d.Name+'.'+o.Name for d in A.listDocuments().values() for o in d.Objects if 'Invalid' in o.State]
missing=[d.Name+'.'+o.Name for d in A.listDocuments().values() for o in d.Objects if o.TypeId=='App::Link' and not o.LinkedObject]
proof=dict(date='2026-10-05',test='T-CARTO-FAISCEAU-NATIF-01',FreeCAD='.'.join(A.Version()[:3]),processus_neuf=True,assemblage_final=relative(top.FileName),faisceau=relative(h.FileName),routes=rows,erreurs_recalcul=invalid,liens_non_resolus=missing,sources_sha256={relative(d.FileName):sha(d.FileName) for d in A.listDocuments().values() if d.FileName},qualification='À valider',limites=['Ports et contacts accouplés candidats, aucunecoupe ni fabricationautorisée','Rayons mesurés ne prouvent pas respect de spécificationcâble/connecteur','Repli des bras, coursecontinue, terminaisonslot, vibrothermique etCEMnonexécutés','Recouvrementsentrelesroutesdegaine nonqualifiés, balayagesdevolumesréservés'],finalisation_correcte=not invalid and not missing and all(not row['intersections'] for row in rows))
dump(VER/'controle_faisceau_natif_bms.json',proof)
assert proof['finalisation_correcte'],proof
print('37 routes sauvegardées relues, valides et sans collision avec obstacles contrôlés')
