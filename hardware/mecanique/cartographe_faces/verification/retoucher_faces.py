"""Installe les retouches de marge sur la copie déjà assemblée."""
from pathlib import Path
import math
import os
import sys
import traceback

from essayer_faces import App, COPY, HERE, Scene, boot, load, require, sha, write
import adapter_implantation as adapter
from installer_faces import BUILD, ENTRY, ROUTES, SA07, clear


def main():
    proof=load(HERE/"essais_marges.json")
    installation=load(HERE/"installation.json")
    require(proof["complete"] and proof["source_sha256"]==installation["native_sha256"]==Scene(COPY).hashes(),
            "Preuve de retouche et CAO divergentes")
    rows={name:proof["routes"][name][0] for name in ("F25","F12")}
    for name,row in rows.items():
        require("error" not in row and clear(row["tested"]), "Retouche non recevable "+name)
    boot()
    adapter.COPY=COPY
    reg=load(COPY/BUILD)
    doc=load(COPY/ROUTES)
    support_rows={
        "F12":(["ClipColonneF12"],"Clip P83 existant, tenue et accès TELEM1 à vérifier."),
        "F25":(["RetenueP85F25"],"Retenue P85 de tranche, autres points de maintien et seuils à définir."),
        "F24A":([],"Traversée entre cartes et terminaison sous-face, appui intermédiaire à définir."),
        "F24B":([],"Entre-cartes sud. Écart à F08_AVAL et découplage mécanique/CEM à confirmer."),
        "F24C":([],"Flanc est. Position finale du breakout FFC et appuis à définir.")
    }
    for row in doc["routes"]:
        name=row["id"]
        if name in rows:
            adapter.rebuild_route(row,rows[name]["points"],reg["references"])
        if name in support_rows:
            holders,limitations=support_rows[name]
            row["longueur_polyline_mm"]=round(sum(math.dist(a,b) for a,b in zip(row["points_mm"],row["points_mm"][1:])),4)
            row["substrat"]=holders
            row["retentions"]="; ".join(holders) if holders else "À valider"
            row["limites"]=limitations
    entry=App.openDocument(str(COPY/ENTRY))
    adapter.check_isolation()
    sa=next(d for d in App.listDocuments().values() if Path(d.FileName).resolve()==COPY/SA07)
    sa.recompute()
    sa.save()
    entry.recompute()
    entry.save()
    write(COPY/BUILD,reg)
    write(COPY/ROUTES,doc)
    m=load(COPY/"manifest.json")
    m.update(references=reg["references"],definition_bom="nomenclature_prototype.json",
             definition_interfaces="../verification/decision_faces.json")
    write(COPY/"manifest.json",m)
    bpath=COPY/"nomenclature_prototype.json"
    bom=load(bpath)
    bom["variante_cao_isolee"]={"nature":"Nomenclature de référence du prototype sans dock. Pour les éléments additionnels de la copie, lire definition_cao et nomenclature_candidats.",
        "definition_cao":"manifest.json","assemblage":"assemblages/Prototype_Cartographe.FCStd",
        "nomenclature_candidats":"../verification/decision_faces.json"}
    write(bpath,bom)
    previous_sha=installation["native_sha256"]
    installation["retouche"]={"script_sha256":sha(__file__),"proof_sha256":sha(HERE/"essais_marges.json"),
        "before_sha256":previous_sha,"routes":{name:row["points"] for name,row in rows.items()}}
    installation["native_sha256"]=Scene(COPY).hashes()
    write(HERE/"installation.json",installation)
    require(adapter.verify_sources(load(COPY/"experiment.json"))["sources_unchanged"],"Référence A altérée")
    print("Retouches sauvegardées",flush=True)


if __name__=="__main__":
    try:
        main()
        code=0
    except Exception:
        traceback.print_exc()
        code=2
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(code)
