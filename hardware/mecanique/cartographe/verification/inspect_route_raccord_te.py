"""Explorer le dégagement PM→PDB contre les nouveaux cordons fixes, sans sauver."""
import json
import FreeCAD as A
from update_routes_systeme_candidat import MEC, candidate_recipe, geometry

dock = A.openDocument(str(MEC / 'sous_assemblages/SA02A_Dock20Ah.FCStd'))
dist = A.openDocument(str(MEC / 'sous_assemblages/SA07_Distribution_Systeme_Candidat.FCStd'))
for d in A.listDocuments().values():
    for o in d.Objects:
        o.touch()
for _ in range(2):
    for d in A.listDocuments().values():
        d.recompute()
row = next(r for r in candidate_recipe()['routes'] if r['id'] == 'PM_OUT_PDB')
for z in [-12, -10, -8, -4, 0]:
    candidate = dict(row)
    candidate['points_mm'] = [[-84,-62,-6], [-84,-90,z], [-84,-165,z], [120,-165,z], [120,-100,-20]]
    try:
        _, _, shape, radii = geometry(candidate)
        hits = []
        for o in list(dock.Objects) + list(dist.Objects):
            if o.TypeId != 'App::Link' or not shape.BoundBox.intersect(o.Shape.BoundBox):
                continue
            common = shape.common(o.Shape)
            if common.Volume > 1e-6:
                hits.append(dict(objet=o.Name,volume_mm3=common.Volume))
        print(json.dumps(dict(z=z,hits=hits,rayons=radii)),flush=True)
    except Exception as exc:
        print(json.dumps(dict(z=z,erreur=str(exc))),flush=True)
