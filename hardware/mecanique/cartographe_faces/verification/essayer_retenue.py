"""Retenue locale candidate sur le chant de P66, à géométrie paramétrique."""
import os
import sys

from essayer_faces import App, COPY, HERE, PAIRS, Scene, V, boot, load, make_native_cable, require, write
from adapter_implantation import Part, report_pairs


def make_support(doc, seat_z=77.8):
    group = doc.addObject("App::Part", "Ensemble")
    group.Label = "P85 — retenue locale de F25 sur chant P66"
    items = []
    for name, dims, origin in (
        ("PatinHaut",(6,8,1.8),(66,-38,88.05)),
        ("PatinBas",(6,8,1.8),(66,-38,83.15)),
        ("Dos",(3,8,6.7),(70.05,-38,83.15)),
        ("BrasCourt",(5.2,8,6.8),(72,-38,seat_z+0.3)),
        ("Berceau",(5.8,8,6),(74.3,-38,seat_z-3)),
    ):
        obj = doc.addObject("Part::Box",name)
        obj.Length,obj.Width,obj.Height=dims
        obj.Placement.Base=V(*origin)
        group.addObject(obj)
        items.append(obj)
    body = doc.addObject("Part::MultiFuse","Corps")
    body.Shapes=items
    body.Refine=True
    bore=doc.addObject("Part::Cylinder","Gorge")
    bore.Radius,bore.Height=2.2,8.4
    bore.Placement=App.Placement(V(77.1,-38.2,seat_z),App.Rotation(V(0,0,1),V(0,1,0)))
    opening=doc.addObject("Part::Box","Entree")
    opening.Length,opening.Width,opening.Height=3.5,8.4,2.7
    opening.Placement.Base=V(77.1,-38.2,seat_z-1.35)
    tools=doc.addObject("Part::MultiFuse","Evidement")
    tools.Shapes=[bore,opening]
    final=doc.addObject("Part::Cut","Resultat")
    final.Base,final.Tool=body,tools
    final.Refine=True
    final.Label="P85 — clip ouvrable sur chant P66, PA12 candidat"
    final.addProperty("App::PropertyString","Maturite")
    final.Maturite="À valider : procédé, serrage, tenue, arête et dépose."
    for obj in [body,bore,opening,tools,final]:
        group.addObject(obj)
    doc.recompute()
    require(final.Shape.isValid() and len(final.Shape.Solids)==1,"Clip sans solide unique")
    for obj in [*items,body,bore,opening,tools]:
        obj.Visibility=False
    return final


def main():
    scene=Scene(COPY)
    original=scene.hashes()
    boot()
    doc=App.newDocument("Retenue")
    support=make_support(doc)
    others={i.name:i.shape for i in scene.items.values() if i.name!="F25"}
    shape=support.Shape.copy()
    record={"occurrences":report_pairs(shape,others,0.65),"volume_mm3":shape.Volume,
            "scope":"Clip candidat serré sur chant P66, sans perçage. Réserve nominale 0,05 mm par face. Tenue à définir."}
    App.closeDocument(doc.Name)
    doc=App.newDocument("F25_essai")
    row=scene.routes["F25"]
    spec=load(HERE/"parametres_combinaison.json")["F25_D"]
    cable,_=make_native_cable(doc,None,"F25",spec["points"],row["diametre_mm"],row["rayon_courbure_mm"])
    record["f25"]=report_pairs(shape,{"F25_D":cable.Shape},0.65)
    App.closeDocument(doc.Name)
    require(scene.hashes()==original,"Copie modifiée")
    write(HERE/"essai_retenue_P85.json",{"complete":True,"source_sha256":original,**record})
    print(record,flush=True)


if __name__ == "__main__":
    try:
        main()
    finally:
        PAIRS.close()
    sys.stdout.flush()
    os._exit(0)
