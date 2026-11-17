"""Inventaire et planches des formes sauvegardées, sans ouvrir ni écrire un natif."""

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import sys


ROOT = next(parent for parent in Path(__file__).resolve().parents if (parent / "AGENTS.md").is_file())
REFERENCE = ROOT / "hardware/mecanique/cartographe/verification"
HISTORY = REFERENCE / "refonte_faisceaux"
sys.path.insert(0, str(HISTORY))

from controles_geometrie import App, ENTRY, Scene, bounds, read, sha, write
from controles_vues import (
    BACKGROUND, FIXATION, dimension_scale, footer, heading, mesh_scene,
    plt, projection, render, save, set_panel,
)


ORANGE = {"P72_Guide", "P73_Guide", "P75_Cadre", "P77_BerceauReserveUSB", "P78_RetenueCameraM8"}
SLEEVES = {"ProtectionF38", "GaineNTC", "GaineSignalNord", "GaineMAIN"}
ROUTE_CONNECTORS = {"ConnecteurF16Camera", "ConnecteurF16TypeA", "ConnecteurM8Camera"}
P10_BOM = {"MEC-RETENUES-CAPTEURS", "MEC-RETENUES-CAPTEURS-FIXATIONS"}
DATUMS = {"App::Origin", "App::Line", "App::Plane", "App::Point"}

PIECES = {
    "P72": ("P60, P64, P66", "Montant de 185 mm, pattes à trois étages. Appuis et lumière F41, retenues puissance, locales, basses et réserves fusionnés.", "Écarter le montant continu et réexaminer les retenues fonctionnelles sur chaque étage."),
    "P73": ("P60, P64, P66", "Montant de 185 mm. Retenues puissance, distribution basse, appuis et tablette du porte-fusible MIDI fusionnés.", "Écarter le montant continu. Le retrait libère le MIDI ; sa tablette de 72,5 × 30 × 3 mm et les colliers d'équipement demandent une reprise locale."),
    "P75": ("P66, quatre axes (±66, ±43), dont deux partagés avec P72/P73", "Cadre de quatre montants, huit traverses, 30 œillets et 12 stations de montant avant extensions. Peigne, longs appuis USB, retenues hautes et départs de bras fusionnés.", "Écarter le cadre et remplacer ses fonctions ponctuelles après vérification. Le retrait libère les deux supports RF P70 et leurs colliers d'ancrage."),
    "P77": ("Plateau OEM à Z2, trois colliers par lumières existantes", "Trois selles PA12 pour la réserve du cordon USB F41 ; fonction liée à la longueur commerciale héritée.", "Comparer au cordon à longueur ajustée. Une réserve à trois spires ne constitue pas une exigence électrique."),
    "P78": ("P64, lumière X84/Y78,6 et retour au bord X94", "Pied à un collier, bras et contrefiches pour quatre stations du câble M8 sur partie fixe.", "Rechercher un ancrage local sur P64, conserver la décharge de traction et la liberté de la boucle mobile ; évaluer le besoin en poses."),
    "P79": ("Tube OEM Ø20 à 180 mm radial", "Selle amont à gorges séparées, un collier autour du tube, de la selle et des gaines.", "Comparer à un lien direct protégé ; conserver séparation, maintien local et dégagement de pliage."),
    "P80": ("Tube OEM Ø20 à 250 ou 280 mm radial", "Selle aval à gorges séparées, un collier autour du tube, de la selle et des gaines.", "Comparer à un lien direct protégé ; vérifier l'accès près de l'ESC et du moteur."),
    "P10": ("Platine capteurs, quatre axes de fixation M3 en SA04", "Retenues historiques de perception sur leur propre sous-ensemble.", "Distinguer du cadre et conserver leurs interfaces jusqu'à mesure de l'usage réel."),
}

CAUSES = [
    {"source": "cable_workbench_prototype.py#make_native_cable", "observation": "Crée WireFlex, profil extérieur et ArchCable ; les profils et parcours sont masqués. Aucun support physique n'est créé par ce module."},
    {"source": "prototype_guides.py#build_guides", "observation": "Deux guides verticaux reprennent d'emblée P60/P64/P66. Les lumières sont répétées à huit altitudes par guide. Les extensions appuient les cordons successivement, puis fusionnent les pièces au montant. Le MIDI est aussi repris par cette fusion côté droit."},
    {"source": "prototype_guides.py#build_top_guide", "observation": "Un cadre reprend les quatre coins par deux niveaux de traverses, avec 30 œillets et 12 sites de montant avant les extensions. Les retours USB, rails haut, peigne et départs de bras sont fusionnés dans la même pièce."},
    {"source": "prototype_retenues.py#extend_top_guide", "observation": "Barres longues et peigne dimensionnés depuis les axes du câble, avec des reprises vers P75 ou P72. Le retrait d'une branche peut supprimer le besoin correspondant."},
    {"source": "prototype_routage.py", "observation": "Le routage historique associe des listes de supports et réserve des volumes, puis installe P77 et P78. Les fonctions portées par une même pièce se multiplient sans séparation selon l'ordre de dépose des équipements."},
    {"source": "retenues_faisceaux_prototype.json", "observation": "Règle historique de portée guidée 50 mm et transition terminale 60 mm. Ces valeurs candidates ont suscité la multiplication de sites ; elles ne constituent pas une qualification de tenue."},
    {"source": "refonte_faisceaux/installer.py#adapt_guide", "observation": "La dernière refonte reprend les cadres hérités. Deux dégagements sont découpés dans P73/P75 pour maintenir l'architecture antérieure autour de gaines nouvelles."},
    {"source": "refonte_faisceaux/installer.py#group_model", "observation": "Les groupes App::Part, dérivations et jonctions sont de la visualisation et des métadonnées. Les dix marqueurs n'ajoutent pas de supports."},
]


def occurrence_role(item):
    name = item.name
    ids = set(item.row["bom_ids"])
    reference = Path(item.row["source"]).stem
    if name in ORANGE or name.startswith("SelleBras") or reference.startswith("P10_"):
        return "support_fabrique"
    if name.startswith(("CollierMIDI", "CollierAncrageRF")):
        return "collier_equipement"
    if "ELEC-PASSEFILS" in ids or ids.intersection(P10_BOM):
        return "quincaillerie_support"
    if item.role == "cable" or name in ROUTE_CONNECTORS:
        return "enveloppe_liaison"
    if item.role == "gaine":
        return "gaine_candidate"
    return "chassis_equipement_interface"


def fitting(item):
    reference = Path(item.row["source"]).stem.split("_")[0]
    interface, function, decision = PIECES[reference]
    volume = item.shape.Volume
    return {"occurrence": item.key, "reference": reference,
            "rendu_orange_initial": item.name in ORANGE,
            "interface": interface, "fonction": function, "decision": decision,
            "pose_matrice": list(item.pose.toMatrix().A),
            "boite_mm": bounds(item.shape), "volume_mm3": volume,
            "solides": len(item.shape.Solids), "forme_sauvegardee_valide": item.shape.isValid(),
            "statut": "À valider"}


def object_audit(scene, items):
    used_sources = defaultdict(dict)
    path_axes = defaultdict(set)
    for key, item in scene.items.items():
        role = items[key]
        if role == "chassis_equipement_interface" and not item.name.startswith("SupportRF"):
            continue
        path, obj = item.row["source"], item.row["objet_source"]
        if item.name in scene.routes:
            route = scene.routes[item.name]
            path_axes[path].add(route["objet_parcours"])
            obj = route["objet_cable"]
        for leaf in scene.visible_members(path, obj):
            used_sources[path][leaf] = role
        used_sources[path][obj] = role
    parents = {item.row["parent"] for item in scene.items.values()
               if items[item.key] in {"support_fabrique", "collier_equipement", "quincaillerie_support", "gaine_candidate"}}
    for key, item in scene.items.items():
        if item.row["parent"] in parents:
            used_sources[item.row["parent"]][item.name] = items[key]
    classes = {"support_fabrique": "pièce de fixation réellement conçue",
               "collier_equipement": "pièce de fixation réellement conçue",
               "quincaillerie_support": "pièce de fixation réellement conçue",
               "chassis_equipement_interface": "élément mécanique existant",
               "gaine_candidate": "protection physique candidate",
               "enveloppe_liaison": "volume d'encombrement"}
    result = {}
    for path, targets in sorted(used_sources.items()):
        records = []
        types, props = scene.reader.xml(path)
        for name, kind in types.items():
            prop = props[name]
            visibility = prop.get("Visibility")
            visible = None if visibility is None else visibility.find("Bool").get("value") == "true"
            is_solid_brep = "Shape" in prop and prop["Shape"].find("Part") is not None
            if name in targets and kind not in {"App::Part", "App::DocumentObjectGroup"} and (kind == "App::Link" or is_solid_brep):
                category = classes[targets[name]]
            elif (name in path_axes[path] or name.startswith(("Wire", "CompoundPath", "Derivation", "Jonction"))
                  or kind in DATUMS or (path in used_sources and name == "Line" and any(x in path for x in SLEEVES))):
                category = "guide CAO virtuel"
            else:
                category = "élément de construction provisoire"
            records.append({"objet": name, "type": kind, "classe": category,
                            "visible_enregistre": visible})
        result[path] = records
    return result


def audit_views(output, meshes, roles):
    full_view = projection(-48, 30)
    center_view = projection(-63, 40)
    crop = ((-145, 175), (-145, 140), (-133, 158))
    configurations = [
        ("audit_baseline_supports.png", "Retenues et fixations du candidat précédent",
         "Solides sauvegardés, ensemble et détail au centre du châssis",
         {"support_fabrique", "quincaillerie_support", "collier_equipement"}, FIXATION,
         "Les bandes seulement décrites par des stations CAO ne figurent pas. La quincaillerie et les boucles modélisées sont en gris."),
        ("audit_baseline_structure.png", "Châssis et équipements du candidat précédent",
         "Interfaces existantes de l’assemblage et fixations dédiées aux équipements",
         {"chassis_equipement_interface"}, "#637f99",
         "Les plateaux, entretoises et interfaces de montage sont visibles. Les supports dédiés aux câbles sont isolés dans l’autre planche."),
    ]
    outputs = []
    for filename, title, subtitle, selected_roles, color, note in configurations:
        selected = [(key, "audit", color if roles[key] not in {"quincaillerie_support", "collier_equipement"} else "#6d7884",
                     color, triangles) for key, triangles in meshes if roles[key] in selected_roles]
        fig, (a, b) = plt.subplots(1, 2, figsize=(14, 7), facecolor=BACKGROUND)
        fig.subplots_adjust(left=.05, right=.96, top=.79, bottom=.12, wspace=.09)
        heading(fig, title, subtitle)
        set_panel(a, "Ensemble des occurrences filtrées")
        set_panel(b, "Zone centrale · mêmes limites pour les deux planches")
        render(a, selected, full_view)
        render(b, selected, center_view, crop=crop)
        dimension_scale(a, 100)
        dimension_scale(b, 50)
        footer(fig, note)
        save(fig, output / filename)
        outputs.append({"fichier": filename, "sha256": sha(output / filename),
                        "occurrences": sorted(name for name, *_ in selected)})
    return outputs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    scene = Scene(args.baseline)
    hashes = scene.hashes()
    items = {key: occurrence_role(item) for key, item in scene.items.items()}
    supports = [fitting(item) for key, item in scene.items.items() if items[key] == "support_fabrique"]
    obj = object_audit(scene, items)
    assert {item.name for item in scene.items.values() if item.role == "gaine"} == SLEEVES
    assert {item.name for item in scene.items.values() if item.name in ORANGE} == ORANGE
    assert len(supports) == 21
    arch = json.loads(read(HISTORY / "architecture.json"))
    meshes = []
    for (key, item), mesh in zip(scene.items.items(), mesh_scene(scene, arch), strict=True):
        name, _, _, _, triangles = mesh
        if name != item.name:
            raise RuntimeError("Ordre des maillages différent de l'inventaire des occurrences")
        meshes.append((key, triangles))
    views = audit_views(args.output, meshes, items)
    del meshes
    if hashes != scene.hashes():
        raise RuntimeError("Les natifs de référence ont changé pendant l'audit.")
    p10 = [support for support in supports if support["reference"] == "P10"]
    hardware = [item for key, item in scene.items.items() if items[key] == "quincaillerie_support"]
    contract = json.loads(read(REFERENCE / "retenues_faisceaux_prototype.json"))
    stations = [station for route in contract["routes"] for station in route["retenues"]]
    historical_refs = {route["id"]: {station["reference"].split("_")[0]
                                      for station in route["retenues"]}
                       for route in contract["routes"]}
    removed_refs = {"P72", "P73", "P75", "P77", "P78"}
    affected = {route: sorted(refs & removed_refs) for route, refs in historical_refs.items()
                if refs & removed_refs}
    lost = sorted(route for route in affected if historical_refs[route] <= removed_refs)
    report = {
        "schema": "cartographe.audit-baseline-faisceaux.v1", "finalise": True,
        "source": args.baseline.resolve().relative_to(ROOT).as_posix(), "entree": ENTRY,
        "environnement_freecad": App.Version(), "natifs_et_registres_sha256": hashes,
        "adaptateur_sha256": sha(__file__),
        "sources_recettes_sha256": {source: sha(REFERENCE / source) for source in {
            "refonte_faisceaux/controles_vues.py", "refonte_faisceaux/controles_geometrie.py",
            "refonte_faisceaux/architecture.json", *[cause["source"].split("#")[0] for cause in CAUSES],
        }},
        "comptage": {
            "cables_enveloppes": len(scene.cables), "axes_cumules_mm": sum(s.Length for s in scene.wires.values()),
            "gaines_physiques_candidates": len(SLEEVES), "groupes_app_part_sa07": len(arch["groupes"]),
            "occurrences_par_role": dict(Counter(items.values())),
            "supports_fabriques_dedies_sa07": len(supports) - len(p10),
            "supports_fabriques_perception_p10": len(p10),
            "references_distinctes_support_fabrique": len({s["reference"] for s in supports}),
            "cadres_ou_guides_massifs": 3,
            "volume_brep_cumule_trois_cadres_mm3": sum(s["volume_mm3"] for s in supports if s["reference"] in {"P72", "P73", "P75"}),
            "quincaillerie_sa07": dict(Counter(item.name.split("Guide")[0] for item in hardware if "Guide" in item.name)),
            "quincaillerie_p10_sa04": sum("P10" in item.name for item in hardware),
            "affectations_de_station_contrat_herite": len(stations),
            "colliers_ids_contrat_herite": len({s["collier_id"] for s in stations if s.get("collier_id")}),
            "objets_natifs_audites": sum(map(len, obj.values())),
            "classes_objets_natifs": dict(Counter(o["classe"] for records in obj.values() for o in records)),
        },
        "supports": supports,
        "impact_retrait_des_cinq_occurrences_orange": {
            "classification": "CALCULÉE, projection d'un contrat historique, hors preuve de montage",
            "affectations_par_reference": dict(Counter(s["reference"].split("_")[0] for s in stations)),
            "affectations_perdues": sum(s["reference"].split("_")[0] in removed_refs for s in stations),
            "routes_avec_station_historique_a_reexaminer": affected,
            "routes_sans_station_historique_residuelle": lost,
            "limite": "Le retrait de sites ne prouve pas la perte du maintien réel. Il impose un nouveau bilan de retenue et de pose, avec prise en compte de la traction et du mouvement.",
        },
        "ancrages_quincaillerie": [{"occurrence": item.key, "xyz_mm": list(item.pose.Base),
                                    "source": item.row["source"]} for item in hardware],
        "dependances_equipement": {
            "MIDI": {"equipement": "SA02#Protection_amont", "support": "P73#TabletteMIDI",
                     "colliers": ["CollierMIDI0", "CollierMIDI1"], "axes_X_mm": [39, 63],
                     "surfaces_appui_mm": [17.5, -86, -55, 90, -56, -52],
                     "source": "prototype_fixations_equipements.py#extend_midi_shelf"},
            "RF": {"equipements": ["SupportRF0", "SupportRF1"], "support": "P75_Cadre",
                   "colliers": ["CollierAncrageRF0", "CollierAncrageRF1"],
                   "source": "prototype_fixations_equipements.py"},
            "QS8": {"support": "P76#BerceauQS8", "interface": "P61, deux axes M3 X105/Y±29",
                    "source": "prototype_guides.py#build_qs8_cradle"},
        },
        "causes": CAUSES, "objets_par_natif": obj, "occurrences_par_role": items,
        "rendu_initial": {"couleur_retenues": FIXATION, "occurrences": sorted(ORANGE),
                           "limite": "L'ancienne palette peint aussi certains câbles en ocre selon le groupe. Les fonctions support sont déterminées par le nom d'occurrence et les sources."},
        "comparaison": {
            "rejet_architecture": "Les trois cadres sont des pièces physiques conçues mais les traverses, montants et retours fusionnés multiplient les interfaces et pontent des étages démontables. Leur échelle et leur cumul sont rejetés pour cette intégration.",
            "elements_virtuels": "Un repère, une dérivation logique, une courbe WireFlex ou un outil booléen n'entre pas dans la nomenclature physique. Une primitive fusionnée ne représente pas une fixation distincte.",
            "geometrie_artificielle": "Aucune occurrence orange n'est un objet virtuel ou flottant par défaut. La justification mécanique de la superstructure est rejetée au niveau architectural. L'inventaire conserve les primitives séparément pour examen sans leur attribuer une quantité physique.",
            "comparabilite": "17 supports SA07 à comparer à un même périmètre. Les 4 P10, 4 colliers d'équipement et 34 quincailleries SA07 ont leur décompte séparé. Les 269 identifiants de colliers sont contractuels et historiques ; certains sites demandent une reprise et aucun taux de diminution des colliers installés n'en découle.",
        },
        "vues": views,
        "validation": "Lecture des BRep et vérification des liens/poses enregistrés ; aucun recalcul, montage, accès outillage ou validation physique pendant l'audit.",
    }
    write(args.output / "audit_baseline.json", report)
    print(json.dumps(report["comptage"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
