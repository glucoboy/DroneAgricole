"""Vérifie et ajoute la retenue locale à l'assemblage final par faces."""
import os
from pathlib import Path
import sys
import traceback

from essayer_faces import App, COPY, HERE, PAIRS, Scene, V, boot, bounds, load, require, sha, write
from adapter_implantation import report_pairs, verify_sources
from essayer_retenue import make_support
from installer_faces import BUILD, ENTRY, SA07, add_link, add_reference, clear

FILE="pieces/fabriquees/P85_Retenue_Chant_P66.FCStd"
NOMINAL="RetenueP85F25"
PRIMITIVES=("PatinHaut","PatinBas","Dos","BrasCourt","Berceau","Gorge","Entree")


def support_at(doc,y):
    z=76+5*(y+60)/69.5
    result=make_support(doc,seat_z=z)
    for name in PRIMITIVES:
        obj=doc.getObject(name)
        pose=obj.Placement
        pose.Base+=V(.9 if name in {"Berceau","Gorge","Entree"} else 0,y+34,0)
        obj.Placement=pose
    doc.recompute()
    require(result.Shape.isValid() and len(result.Shape.Solids)==1,"P85 sans solide")
    return result


def main():
    scene=Scene(COPY)
    initial=scene.hashes()
    evidence=load(HERE/"installation.json")
    require(initial==evidence["native_sha256"] and NOMINAL not in evidence["new_occurrences"],"Copie déjà modifiée")
    boot()
    outcomes=[]
    shapes={o.name:o.shape for o in scene.items.values()}
    selected=None
    for y in (-5,-1,-8):
        doc=App.newDocument("P85Essai")
        item=support_at(doc,y)
        checked=report_pairs(item.Shape,shapes,.6)
        outcomes.append({"position_y_mm":y,"checks":checked,"volume_mm3":item.Shape.Volume,
                         "bbox_mm":bounds(item.Shape)})
        if clear(checked):
            selected=(doc,item,outcomes[-1])
            break
        App.closeDocument(doc.Name)
    record={"complete":True,"initial_cao_sha256":initial,"essais":outcomes,"installed":selected is not None}
    if selected:
        doc,item,accepted=selected
        root=doc.getObject("Ensemble")
        item.ViewObject.ShapeColor=(.22,.62,.38)
        doc.saveAs(str(COPY/FILE))
        reg=load(COPY/BUILD)
        add_reference(reg,FILE,root,item.Shape,"fabriquee",
                      "Maintien local conditionnel par clip sur le chant P66. PA12 et tenue à valider.")
        entry=App.openDocument(str(COPY/ENTRY))
        require(all(Path(d.FileName).resolve().is_relative_to(COPY) for d in App.listDocuments().values()),
                "Document hors copie")
        sa=next(d for d in App.listDocuments().values() if Path(d.FileName).resolve()==COPY/SA07)
        add_link(reg,sa,sa.getObject("InterfacesFaces"),NOMINAL,FILE,root,root.Placement,"P85 · maintien local F25")
        sa.recompute()
        sa.save()
        entry.recompute()
        entry.save()
        reg["integration_faces"]["retenue"]=NOMINAL
        write(COPY/BUILD,reg)
        m=load(COPY/"manifest.json")
        m.update(references=reg["references"],occurrences=reg["occurrences"])
        write(COPY/"manifest.json",m)
        evidence["new_occurrences"].append(NOMINAL)
        evidence["clip"]={"installable":True,"selection":accepted}
        evidence["native_sha256"]=Scene(COPY).hashes()
        evidence["retention_adapter_sha256"]=sha(__file__)
        write(HERE/"installation.json",evidence)
    require(verify_sources(load(COPY/"experiment.json"))["sources_unchanged"],"Source A altérée")
    record["final_cao_sha256"]=Scene(COPY).hashes()
    write(HERE/"retenue_finale.json",record)
    print("P85",record["installed"],flush=True)


if __name__=="__main__":
    try:
        main()
        code=0
    except Exception:
        traceback.print_exc()
        code=2
    finally:
        PAIRS.close()
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(code)
