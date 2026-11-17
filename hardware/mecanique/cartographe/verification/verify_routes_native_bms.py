"""Réouverture indépendante des routes effectivement sauvegardées dans SA08."""
from update_routes_systeme_candidat import obstacles,sha,relative,MEC,VER,dump,geometry
import FreeCAD as A,Part,json,sys
dump(VER/'controle_faisceau_natif_bms.json',dict(date='2026-10-05',test='T-CARTO-FAISCEAU-NATIF-01',finalisation_correcte=False,etat_execution='Vérification non finalisée ; en cours, interrompue ou échouée',qualification='À valider'))
top,obs=obstacles()
sa=top.getObject('SA08_Faisceau_Systeme_Candidat');assert sa and sa.LinkedObject
h=sa.LinkedObject.Document;data=json.loads((VER/'routes_systeme_candidat_20261003.json').read_text(encoding='utf-8'))
reuse='--reutiliser-candidats' in sys.argv
candidate_proof=None
if reuse:
 candidate_proof=json.loads((VER/'controle_routes_systeme_courant.json').read_text(encoding='utf-8'))
 assert candidate_proof['finalisation_correcte'] and candidate_proof['mode']=='natifs enregistrés'
 assert candidate_proof['recette_sha256']==sha(VER/'update_routes_systeme_candidat.py')
 for group in ['sources_lues_sha256','fichiers_courants_sha256']:
  for name,expected in candidate_proof[group].items():assert sha(MEC.parents[2]/name)==expected,name
 assert {r['id'] for r in candidate_proof['routes']}=={r['id'] for r in data['routes']}
rows=[]
for row in data['routes']:
 o=h.getObject(row['id']);assert o and o.LinkedObject,row['id'];src=o.LinkedObject.Document
 wire=src.CheminArrondi.Shape;s=o.Shape;assert s.isValid() and len(s.Solids)==1,row['id']
 s.check(True)
 hits=[]
 equivalence=None
 if reuse:
  cw,cs,solid,cr=geometry(row)
  equivalence=s.cut(solid).Volume+solid.cut(s).Volume
  assert equivalence<1e-5,(row['id'],equivalence)
  tested=next(r for r in candidate_proof['routes'] if r['id']==row['id'])
  assert not tested['intersections'] and abs(wire.Length-tested['longueur_route_mm'])<1e-5,row['id']
 else:
  for name,obstacle in obs:
   if s.BoundBox.intersect(obstacle.BoundBox):
    v=s.common(obstacle).Volume
    if v>1e-6:hits.append(dict(objet=name,volume_mm3=v))
 radii=[e.Curve.Radius for e in wire.Edges if isinstance(e.Curve,Part.Circle)]
 rows.append(dict(id=row['id'],wxx=row['wxx'],fichier=relative(src.FileName),sha256=sha(src.FileName),longueur_mm=wire.Length,rayons_mm=radii,forme_valide=s.isValid(),controle_auto_intersections_BOP=True,solides=len(s.Solids),intersections=hits,volume_difference_symetrique_candidat_mm3=equivalence))
 print(row['id']+': '+str(len(hits))+' intersections',flush=True)
invalid=[d.Name+'.'+o.Name for d in A.listDocuments().values() for o in d.Objects if 'Invalid' in o.State]
missing=[d.Name+'.'+o.Name for d in A.listDocuments().values() for o in d.Objects if o.TypeId=='App::Link' and not o.LinkedObject]
proof=dict(date='2026-10-05',test='T-CARTO-FAISCEAU-NATIF-01',FreeCAD='.'.join(A.Version()[:3]),processus_neuf=True,assemblage_final=relative(top.FileName),faisceau=relative(h.FileName),routes=rows,erreurs_recalcul=invalid,liens_non_resolus=missing,sources_sha256={relative(d.FileName):sha(d.FileName) for d in A.listDocuments().values() if d.FileName},qualification='À valider',limites=['Ports et contacts accouplés candidats, aucunecoupe ni fabricationautorisée','Rayons mesurés ne prouvent pas respect de spécificationcâble/connecteur','Repli des bras, coursecontinue, terminaisonslot, vibrothermique etCEMnonexécutés','Recouvrementsentrelesroutesdegaine nonqualifiés, balayagesdevolumesréservés'],finalisation_correcte=not invalid and not missing and all(not row['intersections'] for row in rows))
proof['methode_collision']='Candidats sans collision, empreintes de tous les obstacles et natifs identiques, différence symétrique natif/candidat inférieure à1e-5mm³' if reuse else 'Booléens natifs contre tous les obstacles contrôlés'
proof['collisions_obstacles_recalculees_dans_ce_processus']=not reuse
proof['preuve_candidats_sha256']=sha(VER/'controle_routes_systeme_courant.json') if reuse else None
proof['preuve_candidats_fichier']=relative(VER/'controle_routes_systeme_courant.json') if reuse else None
proof['recette_verification_sha256']=sha(__file__)
dump(VER/'controle_faisceau_natif_bms.json',proof)
assert proof['finalisation_correcte'],proof
print('37 routes sauvegardées relues, valides et sans collision avec obstacles contrôlés')
