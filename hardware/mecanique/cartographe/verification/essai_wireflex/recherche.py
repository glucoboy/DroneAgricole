"""Recherche bornée de pôles B-spline, sans modification de document FreeCAD."""
from pathlib import Path
import json, math, random, sys
import FreeCAD as A
import Part
HERE=Path(__file__).resolve().parent
routes=json.loads((HERE.parents[1]/'verification/routes_prototype.json').read_text('utf8'))['routes']
base=next(r['points_mm'] for r in routes if r['id']=='F16')
random.seed(1601)
best=[]
for trial in range(3000):
    points=[p[:] for p in base]
    points[1][0]=points[0][0]+random.uniform(20,65)
    points[-2][1]=points[-1][1]-random.uniform(20,65)
    for i in range(2,6):
        for k in range(3): points[i][k]+=random.uniform(-35,35)
    curve=Part.BSplineCurve()
    try:
        curve.buildFromPoles([A.Vector(*p) for p in points])
        edge=curve.toShape()
        k=max(abs(edge.curvatureAt(edge.FirstParameter+(edge.LastParameter-edge.FirstParameter)*i/500)) for i in range(501))
        radius=1/k if k else 1e9
        if radius>=22.5 and edge.Length<=428.5:
            best.append(dict(radius=radius,length=edge.Length,points=points))
    except Exception:
        pass
best.sort(key=lambda x:sum((x['points'][i][j]-base[i][j])**2 for i in range(8) for j in range(3)))
(HERE/'candidats.json').write_text(json.dumps(best[:20],indent=2),encoding='utf8')
print('candidats',len(best),'retained',len(best[:20]),flush=True)
