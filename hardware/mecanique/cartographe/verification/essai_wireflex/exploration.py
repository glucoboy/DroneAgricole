"""Balayage de paramètres natifs en mémoire ; ne sauvegarde aucun document."""
from pathlib import Path
import json, os, sys
import FreeCAD as App
import FreeCADGui as Gui
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[1]/'verification'))
from cable_workbench_prototype import bootstrap_paths
from experience import measure
Gui.showMainWindow(); Gui.getMainWindow().hide(); bootstrap_paths()
d=App.openDocument(str(HERE/'F16_copie.FCStd')); c=d.getObject('Cable'); w=c.Base
results=[]
for kind in ['BSpline_P','BSpline_K']:
    for boundary in [0.0, 5.0, 10.0]:
        for inner in [False,True]:
            for factor in [0.0,0.5,1.0]:
                try:
                    w.PathType=kind; w.BoundarySegmentStart=boundary; w.BoundarySegmentEnd=boundary
                    w.InnerTangents=inner; w.TangencyCoefficient=factor
                    d.recompute()
                    m=measure(c)
                    results.append(dict(kind=kind,boundary=boundary,inner=inner,factor=factor,
                                        length=m['longueur_mm'],radius=m['rayon_min_echantillonne_mm'],valid=m['forme_valide']))
                except Exception as e:
                    results.append(dict(kind=kind,boundary=boundary,inner=inner,factor=factor,error=str(e)))
(HERE/'exploration.json').write_text(json.dumps(results,indent=2),encoding='utf8')
print(json.dumps(results),flush=True)
App.closeDocument(d.Name)
os._exit(0)
