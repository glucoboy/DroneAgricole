"""Cherche une marge réelle au nominal sans déplacer le passage bas F25."""
import os
import sys
from essayer_faces import App, Checks, COPY, HERE, PAIRS, Scene, boot, load, make_native_cable, require, write

def main():
    scene=Scene(COPY)
    source=scene.hashes()
    checks=Checks(scene)
    boot()
    results={}
    for route,targets in {"F25":[(79,148),(80,149),(81,147.5)],"F12":[None]}.items():
        row=scene.routes[route]
        records=results[route]=[]
        for values in targets:
            pts=[list(p) for p in row["points_mm"]]
            if route=="F25":
                pts[2][2],pts[-3][2],pts[-2][2]=values[0],values[1],values[1]
            else:
                pts[-1][2]=137.35232
            doc=App.newDocument("CorrectionMarge")
            try:
                cable,wire=make_native_cable(doc,None,route,pts,row["diametre_mm"],row["rayon_courbure_mm"])
                proof=checks.pairs(cable.Shape,wire.Shape,row["diametre_mm"],{route})
                records.append({"points":pts,"tested":proof,"length_mm":wire.Shape.Length})
                print(route,values,[(key,[(r["name"],r.get("gap_mm")) for r in value]) for key,value in proof.items() if key!="tested"],flush=True)
            except Exception as error:
                records.append({"points":pts,"error":str(error)})
                print(route,values,error,flush=True)
            finally:
                App.closeDocument(doc.Name)
    require(scene.hashes()==source,"Copie modifiée")
    write(HERE/"essais_marges.json",{"complete":True,"source_sha256":source,"routes":results})

if __name__=="__main__":
    try:
        main()
    finally:
        PAIRS.close()
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0)
