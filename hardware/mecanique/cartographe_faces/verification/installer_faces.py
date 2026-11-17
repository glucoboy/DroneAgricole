"""Valide la combinaison en mémoire, puis installe uniquement sur la copie."""
from pathlib import Path
import os
import sys
import traceback

from essayer_faces import App, Checks, COPY, HERE, PAIRS, PARAMS, Scene, V, boot, bounds, load, make_native_cable, metrics, require, sha, write
import adapter_implantation as previous
from adapter_implantation import Part, report_pairs
from essayer_retenue import make_support
from combiner_faces import PORTS

ENTRY = previous.ENTRY
BUILD = previous.BUILD
ROUTES = previous.ROUTES
SA07 = "sous_assemblages/SA07_Prototype_Faisceaux.FCStd"
SELECTION = HERE / "selection.json"


def clear(test):
    return not (test["collisions"] or test["unknowns"])


def select():
    plan = load(SELECTION)
    chosen = {}
    for key,row in plan["routes"].items():
        path = HERE / row["proof"]
        proof = load(path)
        require(proof["complete"],"Essais incomplets "+key)
        if "cases" in proof:
            candidate = next(r for r in proof["cases"] if r["route"]==key and r["id"]==row["candidate"])
        else:
            candidate = proof["routes"][row["candidate"]]
        require("points" in candidate and "error" not in candidate, "Route non générée "+key)
        chosen[key]=candidate["points"]
    return plan, chosen


def dimensions():
    return {
        "GabaritF25_GH10": ("F25",V(52.825-2.075,9.5-6.875,134.303),(4.15,13.75,3.04932),"JST GHR-10V-S"),
        "GabaritF12_GH6": ("F12",V(59.825-2.075,25-4.375,134.303),(4.15,8.75,3.04932),"JST GHR-06V-S"),
        "GabaritF24A_GH6": ("F24A",V(-59.825-2.075,15-4.375,120.700),(4.15,8.75,3.049),"JST GHR-06V-S, embase GPIO présumée"),
    }


def make_clip(doc):
    result=make_support(doc, seat_z=79.95)
    group=doc.getObject("Ensemble")
    group.Placement.Base=V(0.0,29.0,0.0)
    # La prise P66 reste fixe en X. Seule la gorge suit le centre F25 X78.
    for name in ("Gorge","Entree","Berceau"):
        item=doc.getObject(name)
        p=item.Placement
        p.Base += V(0.9,0,0)
        item.Placement=p
    doc.recompute()
    require(result.Shape.isValid() and len(result.Shape.Solids)==1,"P85 non recalculé")
    return group, result


def preflight(scene, points):
    old = {item.name:item.shape for item in scene.items.values()}
    excluded=set(points)
    shapes={}
    route_metrics={}
    static=Checks(scene)
    comparisons={}
    zones=load(PARAMS)["zones"]
    for name,vertices in points.items():
        row=scene.routes[name]
        doc=App.newDocument("Preflight")
        try:
            cable,wire=make_native_cable(doc,None,name,vertices,row["diametre_mm"],row["rayon_courbure_mm"])
            comparisons[name]=static.pairs(cable.Shape,wire.Shape,row["diametre_mm"],excluded)
            require(clear(comparisons[name]),f"{name} : {comparisons[name]}")
            route_metrics[name]={"old":metrics(scene.cables[name].shape,scene.wires[name],zones),
                                 "new":metrics(cable.Shape,wire.Shape,zones)}
            shapes[name]=cable.Shape.copy()
        finally:
            App.closeDocument(doc.Name)
    mutual={}
    for i,(name,a) in enumerate(shapes.items()):
        for other,b in list(shapes.items())[i+1:]:
            check=report_pairs(a,{other:b},0.65)
            require(clear(check),f"Conflit {name}/{other} {check}")
            mutual[name+"|"+other]=check
    plugs={}
    context={k:v for k,v in old.items() if k not in excluded | {"Holybro6XOrin"}}
    for name,(route,origin,size,ref) in dimensions().items():
        shape=Part.makeBox(*size,origin)
        board={f"Holybro:{i}":s for i,(s,b) in enumerate(static.board)
               if b.intersect(shape.BoundBox)}
        fit=report_pairs(shape,{**context,**shapes,**board},0.35)
        require(clear(fit),f"Gabarit {name} {fit}")
        lower=origin-V(0,0,8) if route=="F24A" else origin
        service=Part.makeBox(size[0],size[1],size[2]+8,lower)
        access=report_pairs(service,{**context,**{k:v for k,v in shapes.items() if k!=route}},0.35)
        require(clear(access),f"Accès exploratoire {name} {access}")
        plugs[name]={"body":fit,"access_8mm":access,"bbox_mm":bounds(shape),"reference":ref}
    d=App.newDocument("PreflightClip")
    try:
        _,result=make_clip(d)
        fit=report_pairs(result.Shape,{**{k:v for k,v in old.items() if k not in excluded},**shapes},0.65)
        clip={"installable":clear(fit),"fit":fit,"volume_mm3":result.Shape.Volume,"bbox_mm":bounds(result.Shape)}
    finally:
        App.closeDocument(d.Name)
    output={"complete":True,"source_sha256":scene.hashes(),"cable_fixed":comparisons,
            "cable_mutual":mutual,"plugs":plugs,"clip":clip,"route_metrics":route_metrics}
    write(HERE/"controle_avant_sauvegarde.json",output)
    return output


def add_reference(reg, file, target, shape, kind, limits):
    reg["references"].append({"reference":Path(file).stem,"fichier":file,"objet":target.Name,
         "bom_ids":[],"type":kind,"statut":"Implémenté","qualification":"À valider","limites":limits,
         "sha256":sha(COPY/file),"bbox_mm":bounds(shape),"compose_valide":True})


def add_link(reg,doc,group,name,file,obj,pose,label):
    link=doc.addObject("App::Link",name)
    link.LinkedObject=obj
    link.LinkTransform=False
    link.Placement=pose
    link.Label=label
    group.addObject(link)
    link.Visibility=True
    reg["occurrences"].append({"parent":SA07,"occurrence":link.Name,"source":file,
                    "objet_source":obj.Name,"matrice":list(pose.toMatrix().A),"bom_ids":[],"statut":"À valider"})


def install(scene, plan, points, verified, receipt):
    previous.COPY=COPY
    reg=load(COPY/BUILD)
    route_doc=load(COPY/ROUTES)
    for row in route_doc["routes"]:
        name=row["id"]
        if name in points:
            previous.rebuild_route(row, points[name], reg["references"])
            row["terminaisons"]=plan["roles"][name]
            row["statut"]="À valider"
    accessories=[]
    for name,(route,origin,size,ref) in dimensions().items():
        d=App.newDocument(name)
        target=d.addObject("Part::Box","Enveloppe")
        target.Length,target.Width,target.Height=size
        target.Placement.Base=origin
        target.Label="Gabarit de fiche accouplée — "+ref
        target.addProperty("App::PropertyString","NatureRepresentation")
        target.NatureRepresentation="Portion externe rectangulaire estimée. Verrou, contacts et toron non représentés."
        d.recompute()
        target.ViewObject.ShapeColor=(.91,.59,.18)
        file="pieces/commerce/"+name+".FCStd"
        d.saveAs(str(COPY/file))
        add_reference(reg,file,target,target.Shape,"commerce_enveloppe",target.NatureRepresentation)
        accessories.append((name,file,target,target.Placement,"Gabarit approximatif "+route))
    if verified["clip"]["installable"]:
        d=App.newDocument("P85")
        group,target=make_clip(d)
        target.ViewObject.ShapeColor=(.22,.62,.38)
        file="pieces/fabriquees/P85_Retenue_Chant_P66.FCStd"
        d.saveAs(str(COPY/file))
        add_reference(reg,file,group,target.Shape,"fabriquee","Clip local sur tranche P66, montage et matière à vérifier.")
        accessories.append(("RetenueP85F25",file,group,group.Placement,"P85 · maintien local F25"))
    entry=App.openDocument(str(COPY/ENTRY))
    previous.check_isolation()
    sa=next(doc for doc in App.listDocuments().values() if Path(doc.FileName).resolve()==COPY/SA07)
    group=sa.addObject("App::Part","InterfacesFaces")
    group.Label="Retenue locale et gabarits de fiches accouplées"
    sa.getObject("Ensemble").addObject(group)
    for name,file,obj,pose,label in accessories:
        add_link(reg,sa,group,name,file,obj,pose,label)
    sa.recompute()
    sa.save()
    entry.Label="Cartographe — implantation par faces — À valider"
    entry.recompute()
    require(not any(set(o.State)&{"Error","Invalid"} for d in (entry,sa) for o in d.Objects),"État natif invalide")
    entry.save()
    route_doc["nature"]="Variante par faces. Les enveloppes et coupes réelles restent à valider."
    reg["integration_faces"]={"status":"À valider","routes":list(points),"roles":plan["roles"],
                             "gabarits":[v[0] for v in accessories]}
    write(COPY/BUILD,reg)
    write(COPY/ROUTES,route_doc)
    modfile=COPY/"verification/modules_electriques.json"
    modules=load(modfile)
    modules["configuration"]="cartographe_faces"
    modules["integration_faces"]={"routes":plan["roles"],"origine_connectivite":"Matrice électrique A, aucun changement logique."}
    write(modfile,modules)
    m=load(COPY/"manifest.json")
    m.update(configuration="cartographe_faces",promotion=False,qualification="À valider",
             references=reg["references"],occurrences=reg["occurrences"],controle="../verification/validation_natifs.json")
    write(COPY/"manifest.json",m)
    # Essai F31 indépendant sans référence dans l'assemblage retenu.
    row=scene.routes["F31"]
    alt=load(HERE/"parametres_combinaison.json")["F31_sous_P66"]
    doc=App.newDocument("EssaiF31SousP66")
    cable,_=make_native_cable(doc,None,"F31_Reservation",alt["points"],row["diametre_mm"],row["rayon_courbure_mm"])
    doc.Label="F31 sous P66 — origine PM08 et service à valider"
    cable.addProperty("App::PropertyString","Limite")
    cable.Limite=plan["alternate"]["F31"]
    altfile=COPY/"verification/candidats/F31_Sous_P66.FCStd"
    doc.saveAs(str(altfile))
    App.closeDocument(doc.Name)
    require(previous.verify_sources(receipt)["sources_unchanged"],"Référence A modifiée")
    final=Scene(COPY)
    write(HERE/"installation.json",{"complete":True,"source_sha256":verified["source_sha256"],
          "native_sha256":final.hashes(),"selection_sha256":sha(SELECTION),"script_sha256":sha(__file__),
          "reprise":list(points),"new_occurrences":[v[0] for v in accessories],"clip":verified["clip"],
          "essai_F31_sha256":sha(altfile),"geometry":verified["route_metrics"]})


def main():
    receipt=load(COPY/"experiment.json")
    require(Path(receipt["copy_root"]).resolve()==COPY and previous.verify_sources(receipt)["sources_unchanged"],
            "Garde copie et sources")
    require(all(sha(COPY/p)==h for p,h in receipt["inputs_sha256"].items()),"Copie initiale requise")
    scene=Scene(COPY)
    plan,points=select()
    boot()
    result=preflight(scene,points)
    print("Contrôles combinés finalisés. P85",result["clip"]["installable"],flush=True)
    if "--install" in sys.argv:
        install(scene,plan,points,result,receipt)
        print("Installation finalisée",flush=True)


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
