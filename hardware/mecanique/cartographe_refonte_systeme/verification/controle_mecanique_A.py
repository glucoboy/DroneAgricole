"""Contrôles nominaux différentiels et poses de perception sur les BRep sauvegardés."""
from types import SimpleNamespace
from pathlib import Path

from adapter_implantation import (
    App, COPY, HERE, LEGACY, PAIRS, Part, Scene, V, bounds, distance_bound, load,
    report_pairs, require, sha, write,
)
from controle_porteuse_A import board_pairs
from controles_mobilite import pose_transform, moved


def main():
    scene = Scene(COPY)
    before = scene.hashes()
    require(load(HERE / "installation_A.json")["final_sha256"] == before, "CAO différente de l'installation")
    by_name = {item.name:item for item in scene.items.values()}
    shapes = {name:item.shape for name,item in by_name.items()}
    changed = ("F25", "F31", "SupportSecurite", "BoutonBuzzerLED")
    changed_set = set(changed)
    pairs = {}
    for name in changed:
        obstacles = {key:shape for key,shape in shapes.items() if key != name}
        if name in scene.routes:
            del obstacles["Holybro6XOrin"]
        pairs[name] = report_pairs(shapes[name], obstacles, nearby=1.0)
    board = {name:board_pairs(scene.routes[name], SimpleNamespace(Shape=scene.wires[name]),
                              shapes[name], by_name["Holybro6XOrin"]) for name in ("F25","F31")}
    access = Part.makeBox(30, 24, 35, V(15,-132,105))
    access_check = report_pairs(access, {name:shape for name,shape in shapes.items() if name != "BoutonBuzzerLED"})
    kinematics = LEGACY.parent / "reconstruction_faisceaux/recherche_suspension.json"
    pose_file = LEGACY.parent / "reconstruction_faisceaux/poses_autonomie.json"
    pose_rows = load(pose_file)["candidates"]
    moving_groups = load(kinematics)["kinematics"]
    moving_names = moving_groups["mobile_sa04_occurrences"] + moving_groups["mobile_sa07_occurrences"]
    require(set(moving_names) <= set(by_name), "Liste des volumes mobiles non raccordée")
    # F16/F_M8 restent à leur définition courante. Leur balayage continu
    # reste ouvert. Le test ici porte sur les volumes rigides attachés.
    mobile_min = []
    for row in pose_rows:
        pose = pose_transform(row)
        moved_boxes = [moved(shapes[name], pose).BoundBox for name in moving_names]
        lower = min(distance_bound(shapes[k].BoundBox, box) for k in changed_set for box in moved_boxes)
        mobile_min.append({"pose":row["id"], "aabb_min_lower_bound_mm":lower})
    sensor_scope = {"moving_occurrences":len(moving_names), "poses":len(pose_rows),
                    "parameters_sha256":sha(pose_file), "kinematics_sha256":sha(kinematics),
                    "status":"pass" if all(r["aabb_min_lower_bound_mm"] > 0 for r in mobile_min) else "unknown",
                    "poses_results":mobile_min,
                    "limit":"Volumes rigides aux poses historiques. Pas de mouvement continu ni de modélisation des efforts ou de la déformation des cordons."}
    output = {"complete":True, "cao_sha256":before, "nominal_changed_pairs":pairs,
              "holybro_local_pairs":board, "usl_access_exploratory_volume":access_check,
              "candidate_mount_material_mm3":shapes["SupportSecurite"].Volume,
              "perception_mobility":sensor_scope, "before_and_after_native_read_only":before == scene.hashes(),
              "unknowns":["rayons et portées OEM", "efforts et tolérances", "tenue des retenues en vibration",
                          "FOV/LiDAR et CEM physique", "ventilation et thermique Jetson", "course réelle, F16 et M8",
                          "raccordement et service F41", "position des prises réelles"]}
    write(HERE / "controle_mecanique_A.json", output)
    print("Paires", sum(row["tested"] for row in pairs.values()), "poses", len(mobile_min), flush=True)


if __name__ == "__main__":
    try:
        main()
    finally:
        PAIRS.close()
