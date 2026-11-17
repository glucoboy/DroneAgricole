"""Contrôle différentiel des BRep sauvegardés, sans modifier les natifs."""
from pathlib import Path

from essayer_faces import Checks, COPY, HERE, PAIRS, Scene, distance_bound, load, require, sha, write
from adapter_implantation import report_pairs
from controles_mobilite import moved, pose_transform
from controles_geometrie import REFERENCE


def main():
    scene=Scene(COPY)
    before=scene.hashes()
    install=load(HERE/"installation.json")
    require(install["native_sha256"]==before,"Entrée différente de la sauvegarde")
    items={o.name:o for o in scene.items.values()}
    checks=Checks(scene)
    routes=install["reprise"]
    attached=install["new_occurrences"]
    cable={}
    for name in routes:
        row=scene.routes[name]
        cable[name]=checks.pairs(items[name].shape,scene.wires[name],row["diametre_mm"],{name})
    extra={}
    board=items["Holybro6XOrin"].shape
    board_solids=[(s,s.BoundBox) for s in board.Solids]
    for name in attached:
        shape=items[name].shape
        others={k:v.shape for k,v in items.items() if k not in {name,"Holybro6XOrin"}}
        others.update({f"Holybro:{i}":s for i,(s,b) in enumerate(board_solids) if distance_bound(b,shape.BoundBox)<=.7})
        extra[name]=report_pairs(shape,others,.7)
    folder=REFERENCE/"reconstruction_faisceaux"
    pose_path=folder/"poses_autonomie.json"
    names_path=folder/"recherche_suspension.json"
    data=load(names_path)["kinematics"]
    names=data["mobile_sa04_occurrences"]+data["mobile_sa07_occurrences"]
    moving=[items[k].shape for k in names]
    fixed=[items[k].shape.BoundBox for k in routes+attached]
    limits=[]
    for row in load(pose_path)["candidates"]:
        pose=pose_transform(row)
        boxes=[moved(s,pose).BoundBox for s in moving]
        limits.append({"id":row["id"],"lower_bound_mm":min(distance_bound(a,b) for a in fixed for b in boxes)})
    total=sum(r["tested"] for r in [*cable.values(),*extra.values()])
    collisions=sum(len(r["collisions"]) for r in [*cable.values(),*extra.values()])
    unknowns=sum(len(r["unknowns"]) for r in [*cable.values(),*extra.values()])
    require(before==scene.hashes(),"Natif modifié durant le contrôle")
    write(HERE/"controle_apres_sauvegarde.json",{"complete":True,"cao_sha256":before,
       "total_pairs":total,"collision_results":collisions,"unknown_results":unknowns,
       "cables":cable,"fixtures_and_templates":extra,
       "rigid_poses":{"count":len(limits),"moving_count":len(names),"rows":limits,
                     "min_lower_bound_mm":min(x["lower_bound_mm"] for x in limits),
                     "inputs_sha256":[sha(names_path),sha(pose_path)],
                     "scope":"Volumes rigides aux poses historiques. Flexion, vibrations et course continue non vérifiées."},
       "status":"preliminary","physical":"not_executed"})
    print("Paires",total,"intersections",collisions,"inconnues",unknowns,flush=True)


if __name__=="__main__":
    try:
        main()
    finally:
        PAIRS.close()
