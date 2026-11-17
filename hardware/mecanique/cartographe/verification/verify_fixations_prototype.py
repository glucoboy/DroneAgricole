"""Revue géométrique indépendante des fixations sauvegardées du prototype.

Exécuter avec le Python de FreeCAD. Aucun natif n'est sauvegardé. Le résultat
actualise seulement review_assemblage_prototype.json, clé review_finale_fixations.
Ce contrôle ne qualifie ni les filetages, ni les couples, ni la tenue physique.
"""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import itertools
import json

import FreeCAD as App
from etage_batterie_helpers import G
from cable_workbench_prototype import bootstrap_paths
bootstrap_paths()


MEC = Path(__file__).resolve().parents[1]
VER = MEC / "verification"
SEUIL_MM3 = 1e-4


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def bbox(shape):
    box = shape.BoundBox
    return [getattr(box, axis) for axis in
            ("XMin", "YMin", "ZMin", "XMax", "YMax", "ZMax")]


def bbox_overlap(a, b):
    return all(min(getattr(a, k + "Max"), getattr(b, k + "Max"))
               - max(getattr(a, k + "Min"), getattr(b, k + "Min")) > 1e-5
               for k in "XYZ")


def run():
    proof_path = VER / "construction_prototype.json"
    proof = json.loads(proof_path.read_text(encoding="utf-8"))
    if not proof["finalisation_correcte"]:
        raise RuntimeError("Construction non finalisée : aucun contrôle des fichiers en cours.")
    files = {r["fichier"] for r in proof["references"]}
    files.update(proof["sources_preservees"])
    before = {p: sha(MEC / p) for p in files}
    App.openDocument(str(MEC / proof["assemblage"]))
    names = [(1, "Structure"), (2, "Batterie"), (3, "Energie"),
             (4, "Perception"), (5, "Avionique"), (6, "Navigation")]
    documents = [App.getDocument(f"SA{i:02d}_Prototype_{name}")
                 for i, name in names]
    errors = []
    all_objects = []
    for document in documents:
        document.recompute()
        for obj in document.Objects:
            if any(state in ("Invalid", "Error") for state in obj.State):
                errors.append(f"{document.Name}/{obj.Name}: {list(obj.State)}")
        for obj in document.Ensemble.Group:
            if obj.TypeId == "App::Link":
                if obj.LinkedObject is None:
                    errors.append(f"{document.Name}/{obj.Name}: lien non résolu")
                else:
                    all_objects.append((f"{document.Name}/{obj.Name}", obj))

    prefixes = {
        "SA02_Prototype_Batterie":
            ("VisColonneBMS", "RondelleColonneBMS", "EcrouColonneBMS"),
        "SA05_Prototype_Avionique":
            ("VisStack", "RondelleStack", "EcrouStack"),
    }
    focus = [(name, obj) for name, obj in all_objects
             if obj.Document.Name in prefixes
             and obj.Name.startswith(prefixes[obj.Document.Name])]
    fixations_count = len(focus)
    if fixations_count != 32:
        errors.append(f"{fixations_count} fixations contrôlées au lieu de32 "
                      "(8vis,16rondelles,8écrous).")
    for doc_name, object_name in [
        ("SA02_Prototype_Batterie", "Semelle"),
        ("SA02_Prototype_Batterie", "PlateauBMS"),
        ("SA05_Prototype_Avionique", "Interface"),
    ]:
        focus.append((doc_name + "/" + object_name,
                      App.getDocument(doc_name).getObject(object_name)))

    shapes = {name: obj.Shape.copy() for name, obj in all_objects}
    plates = []
    for doc_name, object_name in [
        ("SA02_Prototype_Batterie", "Semelle"),
        ("SA02_Prototype_Batterie", "PlateauBMS"),
        ("SA05_Prototype_Avionique", "Interface"),
    ]:
        name = doc_name + "/" + object_name
        shape = shapes[name]
        plates.append({"objet": name, "solides": len(shape.Solids),
                       "valide": shape.isValid(), "bbox_mm": bbox(shape)})
        if len(shape.Solids) != 1 or not shape.isValid():
            errors.append(name + ": terminal de fabrication non unique ou invalide")

    hits = []
    candidates = 0
    seen = set()
    for name, obj in focus:
        a = shapes[name]
        for other_name, other in all_objects:
            pair = tuple(sorted((name, other_name)))
            if name == other_name or pair in seen:
                continue
            seen.add(pair)
            b = shapes[other_name]
            if not bbox_overlap(a.BoundBox, b.BoundBox):
                continue
            candidates += 1
            detail = []
            if len(b.Solids) > 100:
                volume = 0
                for index, solid in enumerate(b.Solids):
                    if not bbox_overlap(a.BoundBox, solid.BoundBox):
                        continue
                    partial = a.common(solid).Volume
                    volume += partial
                    if partial > 1e-5:
                        detail.append({"indice_derive": index,
                                       "volume_mm3": round(partial, 6)})
            else:
                volume = a.common(b).Volume
            if volume > SEUIL_MM3:
                hit = {"a": name, "b": other_name,
                       "volume_mm3": round(volume, 6), "solides": detail}
                hits.append(hit)
                print(json.dumps(hit, ensure_ascii=False), flush=True)

    unchanged = all(sha(MEC / p) == digest for p, digest in before.items())
    if not unchanged:
        errors.append("Des fichiers ont changé pendant le contrôle ; résultat à rejouer.")
    result = {
        "date_utc": datetime.now(timezone.utc).isoformat(),
        "construction_sha256": sha(proof_path), "script_sha256": sha(__file__),
        "references": len(proof["references"]),
        "occurrences": len(proof["occurrences"]),
        "assemblage_sha256": before[proof["assemblage"]],
        "fixations_controlees": fixations_count,
        "focales": [name for name, obj in focus],
        "paires_presel_bbox_controlees": candidates,
        "plateaux_controles": plates, "collisions": hits,
        "erreurs": errors, "fichiers_non_modifies": unchanged,
        "methode": (
            "Réouverture sans sauvegarde des natifs finaux. Intersections exactes OCCT "
            "après présélection des boîtes, seuil1e-4mm3. Huit vis traversantes BMS/stack, "
            "16rondelles et8écrous, ainsi queP60/P62/P66 sont comparés à tous les liens "
            "des six sous-ensembles solides. Aucun volume positif n'est exempté : "
            "les filetages simplifiés partagent seulement une frontière cylindrique nominale."
        ),
        "limites": [
            "Contacts filetés, classe des vis, précharge et couples non qualifiés.",
            "Routes de câbles, tolérances, flexion et accès outil hors périmètre.",
            "Absence d'une fixation non prescrite dans ce protocole non détectée automatiquement.",
        ],
        "conclusion": "Conforme au contrôle géométrique déclaré" if not hits and not errors
                      else "Non conforme au contrôle géométrique déclaré",
        "qualification": "À valider", "finalisation_correcte": True,
    }
    path = VER / "review_assemblage_prototype.json"
    review = json.loads(path.read_text(encoding="utf-8"))
    review["review_finale_fixations"] = result
    review["etat"] = "Revue initiale conservée ; contrôle final des fixations après corrections dans review_finale_fixations"
    review["portee_historique"] = "source_construction, sources et faits_geometriques décrivent la revue initiale et ses défauts ; les empreintes et résultats courants sont ceux de review_finale_fixations et controle_assemblage_prototype.json."
    review["finalisation_correcte"] = not hits and not errors
    path.write_text(json.dumps(review, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: result[key] for key in
                      ("conclusion", "fixations_controlees", "paires_presel_bbox_controlees",
                       "fichiers_non_modifies")}, ensure_ascii=False), flush=True)
    return 0 if not hits and not errors else 1


if __name__ == "__main__":
    raise SystemExit(run())
