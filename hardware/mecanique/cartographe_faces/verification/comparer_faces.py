"""Compare la référence et la copie sur les mêmes boîtes, axes et niveaux."""
from pathlib import Path
import math

from essayer_faces import COPY, HERE, PARAMS, Scene, V, load, metrics, require, sha, write
from adapter_implantation import verify_sources

LEVELS=(85,110.22,130.052)
ZONES={
    **load(PARAMS)["zones"],
    "sous_P66_emprise_stricte":[[-70,-47,39],[70,47,85]],
    "sous_porteuse_emprise_stricte":[[-63,-41,110.22],[63,40.52,123.72]]
}


def crossings(wire):
    counts={str(z):0 for z in LEVELS}
    for edge in wire.Edges:
        count=2 if edge.Curve.TypeId=="Part::GeomLine" else 96
        start,end=edge.ParameterRange
        zs=[edge.valueAt(start+(end-start)*k/(count-1)).z for k in range(count)]
        for z in LEVELS:
            counts[str(z)] += sum((a < z <= b) or (b < z <= a) for a,b in zip(zs,zs[1:]))
    return counts


def inspect(scene, reused=None, changed=None):
    rows=dict(reused) if reused else {}
    for key in (changed if changed is not None else scene.routes):
        wire=scene.wires[key]
        d=scene.routes[key]["diametre_mm"]
        row=metrics(scene.cables[key].shape,wire,ZONES)
        row["volume_proxy_above_cm3"]=math.pi*d*d*row["length_by_zone_mm"]["above"]/4000
        row["transitions_z"]=crossings(wire)
        row["diameter_mm"]=d
        row["radius_nominal_mm"]=scene.routes[key].get("rayon_demande_mm")
        row["radius_supplier_mm"]=None
        rows[key]=row
    return rows


def summarize(rows):
    return {"routes":len(rows),
       "axis_sum_mm":sum(x["length_mm"] for x in rows.values()),
       "height_max_mm":max(x["height_mm"] for x in rows.values()),
       "length_by_zone_mm":{z:sum(x["length_by_zone_mm"][z] for x in rows.values()) for z in ZONES},
       "volume_proxy_above_cm3":sum(x["volume_proxy_above_cm3"] for x in rows.values()),
       "transitions_z":{str(z):sum(x["transitions_z"][str(z)] for x in rows.values()) for z in LEVELS}}


def main():
    receipt=load(COPY/"experiment.json")
    a,b=Scene(Path(receipt["source_root"])),Scene(COPY)
    ah,bh=a.hashes(),b.hashes()
    install=load(HERE/"installation.json")
    require(install["native_sha256"]==bh,"CAO différente de l'installation")
    changed={k for k,row in b.routes.items() if row["points_mm"]!=a.routes[k]["points_mm"]}
    require(set(a.routes)==set(b.routes) and len(a.routes)==53 and changed==set(install["reprise"]),"Périmètre divergent")
    require(all(a.routes[k]["bom_ids"]==b.routes[k]["bom_ids"] for k in a.routes),"BOM modifiée")
    for k in set(a.routes)-changed:
        require(ah[a.routes[k]["fichier"]]==bh[b.routes[k]["fichier"]]
                and a.cables[k].pose.toMatrix().A==b.cables[k].pose.toMatrix().A,"Axe hérité divergent "+k)
    first=inspect(a)
    last=inspect(b,first,changed)
    clip=install["clip"]
    volume=clip["selection"]["volume_mm3"]/1000 if clip.get("installable") else 0.0
    roi={"zone_reference":"X±118, Y±108, Z130,052–250 mm pour dessus.",
         "sous_plan":"Boîte inter-niveau large distincte de la stricte emprise P66 X±70 Y±47.",
         "traversees":"Franchissements des plans Z, y compris hors emprise. Ne comptent ni trous ni accouplements.",
         "rayon":"Les paramètres nominaux sont documentés par FreeCAD. Le rayon admissible dépend du cordon réel."}
    check=verify_sources(receipt)
    require(check["sources_unchanged"],"Sources altérées")
    report={"complete":True,"zones_mm":ZONES,"definitions":roi,"before":summarize(first),"after":summarize(last),
            "axes_a":first,"axes_apres":last,"changed":sorted(changed),"source_files":len(receipt["inputs_sha256"]),
            "source_sha256":ah,"candidate_sha256":bh,"a_unchanged":True,
            "supports":{"new_physical_concept":int(clip.get("installable",False)),"volume_added_cm3":volume,
                        "mass_estimate_g":volume*.93,"density_g_cm3":.93,
                        "density_reference":"https://www.eos.info/polymer-solutions/data-sheets/mds-pa-2200",
                        "status":"Hypothèse de PA12 EOS PA 2200, masse du seul solide ajouté."},
            "connector_templates_count":sum(k.startswith("Gabarit") for k in install["new_occurrences"]),
            "new_connector_electrical_matings":0,"new_electronic_board":0,"added_structural_holes":0,
            "mass_wiring_or_complete_drone_g":None,"mechanical_CG_mm":None}
    write(HERE/"comparaison_faces.json",report)
    roles=load(COPY/"verification/roles_controle.json")
    for key,row in b.routes.items():
        pts=[V(*p) for p in row["points_mm"]]
        roles[key]={"source_file":row["fichier"],"minimum_radius_mm":row.get("rayon_demande_mm"),
                    "start_axis":list((pts[1]-pts[0]).normalize()),"end_axis":list((pts[-2]-pts[-1]).normalize()),
                    "scope":"Valeurs de définition numérique, sans qualification du cordon."}
    if clip.get("installable"):
        roles["RetenueP85F25"]={"role":"fixation","source_file":"pieces/fabriquees/P85_Retenue_Chant_P66.FCStd",
                               "fresh_objects":["Resultat"]}
    write(HERE/"roles_validation.json",roles)
    print(report["before"],report["after"],flush=True)


if __name__=="__main__":
    main()
