"""Contrôle de combinaison, déport CUAV, gabarits et réservation PM08."""
import os
from pathlib import Path
import sys

from essayer_faces import App, Checks, COPY, HERE, PAIRS, PARAMS, Scene, V, boot, bounds, load, make_native_cable, metrics, require, sha, write
from adapter_implantation import Part, report_pairs
from essayer_reimplantation import rotated

COMBINATION = HERE / "parametres_combinaison.json"
P71 = "pieces/fabriquees/P71_Support_Securite_Prototype.FCStd"
PORTS = {
    "GHR10_GPS1": {"route":"F25","origin":[52.825,9.5,134.302],"size":[4.15,13.75,3.05032]},
    "GHR06_TELEM1": {"route":"F12","origin":[59.825,25,134.302],"size":[4.15,8.75,3.05032]},
    "GHR04_CAN1": {"route":"F31","origin":[52.85,-14.5,134.302],"size":[4.15,6.25,3.05032]},
}
TOL = 1e-4


def rotated_p71(doc):
    for name in ("Plaque", "Percage", "Percage001"):
        item = doc.getObject(name)
        p = item.Placement
        rot = App.Rotation(V(0,0,1),-90)
        center = V(30,-20,0)
        new = App.Placement(center-rot.multVec(center),rot).multiply(p)
        if name == "Plaque":
            for axis in "xy":
                item.setExpression("Placement.Base."+axis, None)
        item.Placement = new
    doc.recompute()
    final = doc.getObject("SupportAncreM21").Shape
    require(final.isValid() and len(final.Solids)==1,"P71 sans solide unique")
    return final.copy()


def plug(spec, extra=0):
    x,y,z = spec["origin"]
    a,b,c = spec["size"]
    return Part.makeBox(a,b,c+extra,V(x-a/2,y-b/2,z))


def trial(scene):
    source = scene.hashes()
    items = {o.name:o for o in scene.items.values()}
    checks = Checks(scene)
    all_shapes = {key:v.shape for key,v in items.items()}
    env = boot()
    spec = load(COMBINATION)
    doc = App.openDocument(str(COPY / P71))
    require(all(Path(d.FileName).resolve().is_relative_to(COPY) for d in App.listDocuments().values()),
            "Source hors copie")
    local = rotated_p71(doc)
    support = local.copy()
    support.Placement = items["SupportSecurite"].pose.multiply(support.Placement)
    App.closeDocument(doc.Name)
    switch,_ = rotated(items["BoutonBuzzerLED"],-90,V(30,-120,97.5))
    old_shapes = {name:shape for name,shape in all_shapes.items() if name not in {"SupportSecurite","BoutonBuzzerLED","F25"}}
    moving = {"support":report_pairs(support,old_shapes),
              "button":report_pairs(switch,{**old_shapes,"P71_Candidat":support}),
              "access":report_pairs(Part.makeBox(30,34,35,V(15,-137,105)),old_shapes),
              "volume_mm3":support.Volume,"support_bbox_mm":bounds(support),"switch_bbox_mm":bounds(switch)}
    print("USL",[(k,[r["name"] for r in v["collisions"]]) for k,v in moving.items() if isinstance(v,dict)],flush=True)
    route_shapes, routes = {}, {}
    zones = load(PARAMS)["zones"]
    mask = {row["route"] for row in spec.values()} - {"F31"}
    for identifier,row in spec.items():
        key = row["route"]
        props = scene.routes[key]
        doc = App.newDocument("Combi")
        result = routes[identifier] = dict(row)
        try:
            cable,path = make_native_cable(doc,None,key,row["points"],props["diametre_mm"],props["rayon_courbure_mm"])
            shape = cable.Shape.copy()
            result["metrics"] = metrics(shape,path.Shape,zones)
            result["checks"] = checks.pairs(shape,path.Shape,props["diametre_mm"],
                                            (mask | {key,"SupportSecurite","BoutonBuzzerLED"}) if row.get("rotate_usl") else mask | {key})
            if row.get("rotate_usl"):
                result["new_support_pairs"] = report_pairs(shape,{"P71":support,"CUAV":switch})
            result["start_end_reservations_mm"] = [list(cable.Base.Shape.Vertexes[i].Point) for i in (0,-1)]
            route_shapes[identifier] = shape
        except Exception as error:
            result["error"] = str(error)
        finally:
            App.closeDocument(doc.Name)
        print(identifier, [x["name"] for x in result.get("checks",{}).get("collisions",[])],
              result.get("error"),flush=True)
    mutual = {}
    for i,(id_a,a) in enumerate(route_shapes.items()):
        for id_b,b in list(route_shapes.items())[i+1:]:
            if spec[id_a]["route"] != spec[id_b]["route"]:
                mutual[id_a+"|"+id_b] = report_pairs(a,{id_b:b},0.8)
    port_results = {}
    choices = {"GHR10_GPS1":"F25_D","GHR06_TELEM1":"F12_TELEM1","GHR04_CAN1":"F31_sous_P66"}
    for name,port in PORTS.items():
        fit = {key:shape for key,shape in all_shapes.items() if key not in mask | {port["route"],"Holybro6XOrin"}}
        # Une paire borne le volume hors embase. Les solides de la porteuse
        # sont traités séparément au voisinage pour éviter un booléen global.
        model = plug(port)
        board = {}
        for index,(solid,box) in enumerate(checks.board):
            if box.intersect(model.BoundBox):
                board[str(index)] = solid
        port_results[name] = {"definition":port,"housing":report_pairs(model,{**fit,**board}),
                              "service_8mm":report_pairs(plug(port,8),fit),
                              "scope":"Gabarit externe de fiche et translation axiale exploratoire. Forme rectangulaire, verrou, fils et doigts exclus."}
        for identifier,shape in route_shapes.items():
            if spec[identifier]["route"] != port["route"]:
                port_results[name].setdefault("cables_candidats",{})[identifier] = report_pairs(model,{identifier:shape})
    # Les deux orientations PM08 sont examinées à ports documentés, avant toute reprise de puissance.
    pm=items["PM08"]
    flip,_ = rotated(pm,180,V(-17,-59.5,39))
    electrical = {"F05_POS","F05_NEG","F06","F32","F31","F38_POS","F38_NEG","F08_AMONT","PM08"}
    pm_fit=report_pairs(flip,{key:shape for key,shape in all_shapes.items() if key not in electrical},0.6)
    pm_plugs = {}
    for cx in (-27,-7):
        for branch, y, pos in (("actuel",-38.7,True),("demi_tour",-80.3,False)):
            target_x = cx if pos else -34-cx
            volume = Part.makeBox(15,10,7,V(target_x-7.5,y if pos else y-10,44.1414))
            pm_plugs[f"{branch}_{cx}"] = report_pairs(volume,{key:shape for key,shape in all_shapes.items() if key!="PM08"},0.6)
    require(scene.hashes()==source,"Copie modifiée pendant les essais")
    write(HERE/"essais_combinaison.json",{"complete":True,"environment":env,"source_sha256":source,
         "parameters_sha256":sha(COMBINATION),"script_sha256":sha(__file__),
         "usl_rotation":moving,"routes":routes,"mutual":mutual,"plug_envelopes":port_results,
         "pm08":{"pose_180_fit":pm_fit,"engagement_scenarios":pm_plugs,
          "unknown":"Ordre des ports POWER, prise réelle, perte et protection des câbles F38/F05 après rotation"}})


if __name__ == "__main__":
    try:
        trial(Scene(COPY))
    finally:
        PAIRS.close()
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0)
