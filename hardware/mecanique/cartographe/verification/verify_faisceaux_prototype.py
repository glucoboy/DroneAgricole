"""Contrôle indépendant du faisceau natif sauvegardé, sans écriture de CAO.

Exécuter avec le Python de FreeCAD après finalisation du constructeur.
Seule la preuve controle_faisceaux_prototype.json est actualisée. Les distances
20/30mm sont des indicateurs de revue d'implantation, pas une qualification.
"""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import gc
import itertools
import json
import math
import os
import sys
import traceback

import FreeCAD as App
import FreeCADGui as Gui


MEC = Path(__file__).resolve().parents[1]
VER = MEC / "verification"
OUTPUT = VER / "controle_faisceaux_prototype.json"
CHECKPOINT = MEC.parents[2] / ".runtime/faisceau_structure/controle_faisceaux_progression.json"
VOLUME_TOL = 1e-4
SAMPLE_STEP = 20.0
FAR_DISTANCE = 30.0
END_ZONE = 20.0
PAIRS = ["F01", "F37", "F38", "F05"]
AIRY_JUNCTION = {"AIRY", "AIRY_ETH", "AIRY_PWR", "AIRY_SYNC"}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def box_values(shape):
    b = shape.BoundBox
    return [round(getattr(b, k), 4) for k in
            ("XMin", "YMin", "ZMin", "XMax", "YMax", "ZMax")]


def overlap(a, b):
    return all(min(getattr(a, k + "Max"), getattr(b, k + "Max"))
               - max(getattr(a, k + "Min"), getattr(b, k + "Min")) > 1e-5
               for k in "XYZ")


def point_box_distance(point, bounds):
    return math.sqrt(sum(max(getattr(bounds, axis + "Min") - value,
                             value - getattr(bounds, axis + "Max"), 0.0) ** 2
                         for axis, value in zip("XYZ", (point.x, point.y, point.z))))


def shape_global_in_document(obj):
    shape = obj.Shape.copy()
    # App::Link.Shape inclut LinkPlacement et la transformation du lien cible.
    # Son wrapper DocumentObject n'expose pas toujours getGlobalPlacement.
    if obj.TypeId == 'App::Link':
        return shape
    shape.Placement = obj.getGlobalPlacement().multiply(obj.Placement.inverse()).multiply(shape.Placement)
    return shape


def intersection(a, b):
    """Présélection par solide pour les composés OEM, sans ignorer leurs détails."""
    if not overlap(a.BoundBox, b.BoundBox):
        return 0.0, [], None
    pieces = b.Solids if len(b.Solids) > 30 else [b]
    volumes = []
    boxes = []
    total = 0.0
    for index, solid in enumerate(pieces):
        if not overlap(a.BoundBox, solid.BoundBox):
            continue
        common = a.common(solid)
        volume = common.Volume
        if volume > VOLUME_TOL:
            total += volume
            boxes.append(box_values(common))
            if len(pieces) > 1:
                volumes.append([index, round(volume, 5)])
    return total, volumes, boxes


def sample_wire(wire, step=SAMPLE_STEP):
    """Échantillonner chaque arête à pas d'abscisse inférieur ou égal à20mm."""
    distance = 0.0
    result = []
    for edge in wire.Edges:
        count = max(1, math.ceil(edge.Length / step))
        for index in range(count):
            local_distance = edge.Length * index / count
            value = edge.Length - local_distance if edge.Orientation == "Reversed" else local_distance
            point = edge.valueAt(edge.getParameterByLength(value))
            result.append((distance + local_distance, point))
        distance += edge.Length
    last = wire.Edges[-1]
    value = 0.0 if last.Orientation == "Reversed" else last.Length
    result.append((distance, last.valueAt(last.getParameterByLength(value))))
    return result


def issue(collection, kind, **details):
    collection.append(dict(type=kind, **details))


def measure_catalog_lengths(row, trace_length, problems):
    """Comparer le tracé aux longueurs déclarées, sans inventer la gaine utile.

    La référence commerciale et sa longueur appartiennent au registre de route.
    Une valeur explicite (y compris null) prime sur l'ancien plafond générique.
    La longueur entre bouts de fiches ne démontre ni la longueur de gaine
    disponible, ni la portée après montage et courbure des sorties de fiches.
    """
    source_key = next((key for key in ("longueur_catalogue_mm", "longueur_max_catalogue_mm")
                       if key in row), None)
    catalog = row.get(source_key) if source_key else None
    usable_key = next((key for key in ("longueur_gaine_utile_min_mm", "longueur_gaine_utile_mm")
                      if key in row), None)
    usable = row.get(usable_key) if usable_key else None
    for name, value in ((source_key or "longueur_catalogue_mm", catalog),
                        (usable_key or "longueur_gaine_utile_mm", usable)):
        if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float))
                                  or not math.isfinite(value) or value <= 0):
            raise ValueError(f"{row['id']} : {name} doit être positif ou null.")
    result = {
        "catalogue_mm": catalog,
        "source_longueur_catalogue": source_key,
        "nature_longueur_catalogue": row.get("nature_longueur_catalogue",
            "Longueur totale ou plafond annoncé ; longueur de gaine non déduite"),
        "longueur_gaine_utile_mm": usable,
        "source_longueur_gaine_utile": usable_key,
        "marge_longueur_totale_mm": None if catalog is None else round(catalog - trace_length, 3),
        "depassement_catalogue_mm": None if catalog is None else round(max(trace_length - catalog, 0), 3),
        "longueur_restante_a_ranger_mm": None if usable is None else round(max(usable - trace_length, 0), 3),
        "depassement_gaine_utile_mm": None if usable is None else round(max(trace_length - usable, 0), 3),
        "validation_longueur_gaine": "À valider : longueur de gaine utile inconnue" if usable is None
            else "Comparaison au budget déclaré ; sorties de fiches, tolérances et montage À valider",
    }
    if catalog is not None and trace_length > catalog + .001:
        issue(problems, "cordon_trop_court", route=row["id"],
              depassement_mm=round(trace_length - catalog, 3),
              limite="Le tracé dépasse même la longueur totale ou le plafond annoncé")
    if usable is not None and trace_length > usable + .001:
        issue(problems, "gaine_utile_trop_courte", route=row["id"],
              depassement_mm=round(trace_length - usable, 3))
    if catalog is not None and usable is not None and usable > catalog + .001:
        issue(problems, "longueurs_catalogue_incoherentes", route=row["id"],
              total_mm=catalog, gaine_utile_mm=usable)
    return result


def progress(stage, **details):
    sys.__stdout__.write(json.dumps(dict(etape=stage, **details), ensure_ascii=False) + "\n")
    sys.__stdout__.flush()


def checkpoint(stage, **details):
    """Conserver les résultats déjà acquis en cas d'arrêt natif OCCT."""
    CHECKPOINT.parent.mkdir(parents=True, exist_ok=True)
    CHECKPOINT.write_text(json.dumps(dict(date_utc=datetime.now(timezone.utc).isoformat(),
        etape=stage, finalisation_correcte=False, **details), ensure_ascii=False,
        separators=(",", ":")) + "\n", encoding="utf-8")


def run():
    # Cables0.3.7 importe Draft.ViewProviderWire : initialisation GUI obligatoire.
    Gui.showMainWindow()
    Gui.getMainWindow().hide()
    from cable_workbench_prototype import bootstrap_paths
    provenance = bootstrap_paths()
    from freecad.cables import archCable, wireFlex  # noqa: F401 : restauration des proxies
    import Part

    construction_path = VER / "construction_prototype.json"
    routes_path = VER / "routes_prototype.json"
    build = json.loads(construction_path.read_text(encoding="utf-8"))
    routes = json.loads(routes_path.read_text(encoding="utf-8"))
    if not build.get("finalisation_correcte"):
        raise RuntimeError("Construction non finalisée : ne pas contrôler une sauvegarde en cours.")
    if not routes.get("extension") or not routes.get("routes"):
        raise RuntimeError("Le registre fourni ne décrit pas un faisceau Cable Workbench finalisé.")
    for row in routes["routes"]:
        if not all(key in row for key in ("fichier", "objet_cable", "objet_parcours")):
            raise RuntimeError("Le registre de route manque ses objets natifs : " + row["id"])

    files = {r["fichier"] for r in build["references"]} | set(build["sources_preservees"])
    before = {path: sha(MEC / path) for path in files}
    initial_build_hash, initial_routes_hash = sha(construction_path), sha(routes_path)
    bad_hashes = [r["fichier"] for r in build["references"]
                  if before[r["fichier"]] != r["sha256"]]
    bad_hashes += [path for path, digest in build["sources_preservees"].items()
                   if before[path] != digest]
    if bad_hashes:
        raise RuntimeError("Natifs différents de la preuve de construction : " + repr(bad_hashes))
    problems, measures, cable_objects = [], [], {}
    # Ouvrir/recalculer les câbles séparément évite de garder53scènes GUI actives.
    # Les occurrences natives sont contrôlées séparément par verify_prototype.py.
    sa7_path='sous_assemblages/SA07_Prototype_Faisceaux.FCStd'
    occurrences={o['occurrence']:o for o in build['occurrences'] if o['parent']==sa7_path}
    identity=list(App.Placement().toMatrix().A)
    for row in routes["routes"]:
        progress('ouverture_cable', cable=row['id'])
        document = App.openDocument(str(MEC/row['fichier']), hidden=True)
        cable = document.getObject(row["objet_cable"])
        route = document.getObject(row["objet_parcours"])
        if not isinstance(cable.Proxy, archCable.ArchCable) or not isinstance(route.Proxy, wireFlex.WireFlex):
            issue(problems, "proxy_non_restaure", route=row["id"])
            App.closeDocument(document.Name)
            continue
        route.touch()
        cable.touch()
        document.recompute()
        errors = [o.Name for o in document.Objects if any(s in ("Invalid", "Error") for s in o.State)]
        if errors:
            issue(problems, "erreur_recalcul", route=row["id"], objets=errors)
        if len(route.Shape.Wires) != 1 or route.Shape.Wires[0].isClosed():
            issue(problems, "parcours_non_unique_ou_ferme", route=row["id"])
            App.closeDocument(document.Name)
            continue
        wire = shape_global_in_document(route).Wires[0]
        occurrence = occurrences.get(row["id"])
        if occurrence is None or occurrence['matrice']!=identity or occurrence['source']!=row['fichier']:
            raise RuntimeError("Occurrence absente ou transformée : " + row["id"])
        shape = document.Ensemble.Shape.copy()
        solid_ok = len(shape.Solids) == 1 and shape.isValid()
        continuity = all(min((u.Point - v.Point).Length for u in a.Vertexes for v in b.Vertexes) < 1e-5
                         for a, b in zip(wire.Edges, wire.Edges[1:]))
        radii = [float(e.Curve.Radius) for e in wire.Edges if hasattr(e.Curve, "Radius")]
        vectors = [b - a for a, b in zip(route.Points, route.Points[1:])]
        expected_arcs = sum(a.cross(b).Length > a.Length * b.Length * 1e-8
                            for a, b in zip(vectors, vectors[1:]))
        unusual = [str(type(e.Curve)) for e in wire.Edges
                   if not hasattr(e.Curve, "Radius") and "Line" not in str(type(e.Curve))]
        radius = float(row["rayon_courbure_mm"])
        if not solid_ok or not wire.isValid() or not continuity:
            issue(problems, "geometrie_invalide", route=row["id"], solide=solid_ok, continuite=continuity)
        if unusual or len(radii) != expected_arcs or any(abs(r - radius) > 1e-4 for r in radii):
            issue(problems, "courbure_differente", route=row["id"], rayon_demande_mm=radius,
                  rayons_observes_mm=radii, courbes_non_circulaires=unusual,
                  arcs_attendus=expected_arcs, arcs_observes=len(radii))
        if abs(cable.Length.Value - wire.Length) > 1e-4:
            issue(problems, "longueur_addon_incoherente", route=row["id"])
        # Comparaison indépendante : tube plein circulaire de diamètre déclaré.
        diameter = float(row["diametre_mm"])
        expected_volume = math.pi * (diameter / 2) ** 2 * wire.Length
        if abs(shape.Volume - expected_volume) > max(.01, expected_volume * 1e-5):
            issue(problems, "section_ou_volume_incoherent", route=row["id"],
                  volume_mm3=round(shape.Volume, 4), attendu_mm3=round(expected_volume, 4))
        measure = {"id": row["id"], "longueur_reelle_mm": round(wire.Length, 3),
                   "rayons_arcs_mm": sorted({round(r, 4) for r in radii}),
                   "nombre_arcs": len(radii), "solide_unique_valide": solid_ok,
                   "continuite": continuity}
        measure.update(measure_catalog_lengths(row, wire.Length, problems))
        measures.append(measure)
        cable_objects[row["id"]] = dict(row=row, cable=row['fichier']+'#'+cable.Name, shape=shape, wire=wire)
        App.closeDocument(document.Name)
        del cable, route, document
        gc.collect()
        Gui.updateGui()
    progress("geometrie_native", cables=len(cable_objects), erreurs=len(problems))
    checkpoint("geometrie_native", construction_sha256=initial_build_hash,
               geometrie_longueurs=measures, erreurs_geometrie_registres=problems)
    if '--geometrie-seule' in sys.argv:
        changed = [path for path, digest in before.items() if sha(MEC / path) != digest]
        registry_changed = (initial_build_hash != sha(construction_path)
                            or initial_routes_hash != sha(routes_path))
        if changed or registry_changed:
            issue(problems, 'fichiers_modifies_pendant_controle', fichiers=changed,
                  registres_modifies=registry_changed)
        cache = CHECKPOINT.parent / 'geometrie_native_acquise.json'
        cache.write_text(json.dumps(dict(date_utc=datetime.now(timezone.utc).isoformat(),
            etape='geometrie_native', finalisation_correcte=True,
            script_sha256=sha(__file__), construction_sha256=initial_build_hash,
            routes_sha256=initial_routes_hash, extension=provenance,
            natifs_sha256=before, geometrie_longueurs=measures,
            erreurs_geometrie_registres=problems,
            qualification='À valider',
            perimetre='Réouverture et recalcul des câbles seulement ; collisions dans le contrôle BRep séparé'),
            ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')
        return 1 if problems else 0

    distinct = []
    for prefix in PAIRS:
        a, b = cable_objects.get(prefix + "_POS"), cable_objects.get(prefix + "_NEG")
        valid = bool(a and b and a["cable"] != b["cable"]
                     and not a["shape"].isSame(b["shape"]))
        distinct.append({"liaison": prefix, "conducteurs_distincts": valid})
        if not valid:
            issue(problems, "conducteurs_non_distincts_ou_absents", liaison=prefix)

    physical, supports = [], []
    sa_names = [(1, "Structure"), (2, "Batterie"), (3, "Energie"),
                (4, "Perception"), (5, "Avionique"), (6, "Navigation")]
    for number, suffix in sa_names:
        document = App.openDocument(str(MEC/f'sous_assemblages/SA{number:02d}_Prototype_{suffix}.FCStd'))
        if not document.Ensemble.Placement.isIdentity():
            raise RuntimeError("Repère SA déplacé : " + document.Name)
        for obj in document.Ensemble.Group:
            if obj.TypeId != "App::Link" or obj.Shape.isNull():
                continue
            name, shape = document.Name + "/" + obj.Name, shape_global_in_document(obj)
            physical.append((name, shape))
            source = Path(obj.LinkedObject.Document.FileName).as_posix()
            if (number == 1 and obj.Name.startswith("OEM_")) or \
                    ("/pieces/fabriquees/" in source and obj.Name != "CA01"):
                supports.extend((name, solid) for solid in shape.Solids)
    route_ids = set(cable_objects)
    for occurrence in occurrences.values():
        if occurrence['occurrence'] not in route_ids:
            doc = App.openDocument(str(MEC/occurrence['source']))
            obj = doc.getObject(occurrence['objet_source'])
            shape=obj.Shape.copy()
            matrix=App.Matrix(*occurrence['matrice'])
            shape.Placement=App.Placement(matrix).multiply(obj.getGlobalPlacement().inverse()).multiply(shape.Placement)
            name='SA07_Prototype_Faisceaux/'+occurrence['occurrence']
            physical.append((name, shape))
            supports.extend((name, solid) for solid in shape.Solids)
    if not supports:
        raise RuntimeError("Aucun support disponible pour la mesure des éloignements.")

    collisions, samples, far_runs = [], [], []
    for cable_index, (cable_id, item) in enumerate(cable_objects.items(), 1):
        progress("collision_cable_debut", cable=cable_id, index=cable_index)
        for target_name, target in physical:
            volume, solid_indices, boxes = intersection(item["shape"], target)
            if volume > VOLUME_TOL:
                collisions.append({"cable": cable_id, "obstacle": target_name,
                    "volume_mm3": round(volume, 5), "solides_locaux": solid_indices,
                    "bbox_intersections_mm": boxes})
        checkpoint("collisions_physique", construction_sha256=initial_build_hash,
                   cables_controles=cable_index, dernier_cable=cable_id,
                   geometrie_longueurs=measures, erreurs_geometrie_registres=problems,
                   collisions_cables_physique=collisions)
        progress("collision_cable_fin", cable=cable_id, index=cable_index,
                 collisions=len(collisions))

    for cable_index, (cable_id, item) in enumerate(cable_objects.items(), 1):
        rows, far = [], []
        for position, point in sample_wire(item["wire"]):
            ordered = sorted((point_box_distance(point, s.BoundBox), name, index)
                             for index, (name, s) in enumerate(supports))
            best, nearest = float("inf"), None
            vertex = Part.Vertex(point)
            for lower_bound, name, index in ordered:
                if lower_bound > best + 1e-5:
                    break
                distance = vertex.distToShape(supports[index][1])[0]
                if distance < best:
                    best, nearest = distance, name
            terminal = min(position, item["wire"].Length - position) <= END_ZONE + 1e-5
            row = [round(position, 2), round(point.x, 2), round(point.y, 2), round(point.z, 2),
                   round(best, 2), nearest, terminal]
            rows.append(row)
            if best > FAR_DISTANCE:
                far.append({"s_mm": row[0], "point_mm": row[1:4], "distance_mm": row[4],
                            "zone_terminale": terminal})
        samples.append({"cable": cable_id, "table": rows})
        if far:
            far_runs.append({"cable": cable_id,
                             "points_lointains_corps": sum(not p["zone_terminale"] for p in far),
                             "points_lointains_terminaisons": sum(p["zone_terminale"] for p in far),
                             "points": far})
        if cable_index % 5 == 0 or cable_index == len(cable_objects):
            progress("collisions_et_distances", cables_controles=cable_index,
                     collisions=len(collisions), cables_eloignes=len(far_runs))
            checkpoint("distances", construction_sha256=initial_build_hash,
                       cables_controles=cable_index, geometrie_longueurs=measures,
                       erreurs_geometrie_registres=problems,
                       collisions_cables_physique=collisions,
                       eloignements_a_revoir=far_runs, distances_echantillonnees=samples)

    cable_collisions, joints = [], []
    for (name_a, a), (name_b, b) in itertools.combinations(cable_objects.items(), 2):
        if not overlap(a["shape"].BoundBox, b["shape"].BoundBox):
            continue
        common = a["shape"].common(b["shape"])
        if common.Volume <= VOLUME_TOL:
            continue
        outside = common
        shared = []
        if name_a in AIRY_JUNCTION and name_b in AIRY_JUNCTION:
            end_a = [a["wire"].Vertexes[0].Point, a["wire"].Vertexes[-1].Point]
            end_b = [b["wire"].Vertexes[0].Point, b["wire"].Vertexes[-1].Point]
            shared = [u for u in end_a if any((u - v).Length < 1e-5 for v in end_b)]
            radius = max(a["row"]["diametre_mm"], b["row"]["diametre_mm"])
            for point in shared:
                outside = outside.cut(Part.makeSphere(radius, point))
            if shared:
                joints.append({"a": name_a, "b": name_b,
                    "points_communs_mm": [[p.x, p.y, p.z] for p in shared],
                    "rayon_zone_locale_mm": radius,
                    "volume_local_mm3": round(common.Volume - outside.Volume, 5),
                    "statut": "Jonction Airy nominale uniquement ; connecteur réel À valider"})
        if outside.Volume > VOLUME_TOL:
            cable_collisions.append({"a": name_a, "b": name_b,
                "volume_total_mm3": round(common.Volume, 5),
                "volume_hors_jonction_mm3": round(outside.Volume, 5),
                "bbox_mm": box_values(outside)})

    changed = [path for path, digest in before.items() if sha(MEC / path) != digest]
    registry_changed = (initial_build_hash != sha(construction_path)
                        or initial_routes_hash != sha(routes_path))
    if changed or registry_changed:
        issue(problems, "fichiers_modifies_pendant_controle", fichiers=changed,
              registres_modifies=registry_changed)
    output = {
        "date_utc": datetime.now(timezone.utc).isoformat(), "script_sha256": sha(__file__),
        "construction_sha256": initial_build_hash, "routes_sha256": initial_routes_hash,
        "extension": provenance, "natifs_sha256": before,
        "protocole": {
            "reouverture": "Processus FreeCAD GUI caché, proxies natifs importés avant ouverture, recalcul forcé",
            "collision": "Intersections OCCT après boîtes englobantes, sous-solides OEM détaillés, aucune exemption câble/équipement",
            "volume_detail": "Volumes cumulés par solide pour les composés détaillés ; les doublons du fichier fabricant peuvent contribuer plusieurs fois, indices conservés.",
            "seuil_volume_mm3": VOLUME_TOL,
            "distance": "Distance exacte entre points de l'axe et solides OEM/pièces fabriquées/guides ; pas maximal20mm par arête",
            "pas_max_mm": SAMPLE_STEP, "signal_eloignement_mm": FAR_DISTANCE,
            "longueur_zone_terminale_mm": END_ZONE,
            "colonnes_echantillons": ["s_mm", "x_mm", "y_mm", "z_mm", "distance_axe_support_mm", "support", "zone_terminale"],
            "limite": "Échantillonnage non continu ; seuil30mm indicatif, aucune tenue de câble qualifiée.",
        },
        "nombre_cables": len(cable_objects), "routes_attendues": len(routes["routes"]),
        "nombre_obstacles": len(physical), "nombre_solides_supports": len(supports),
        "geometrie_longueurs": measures, "conducteurs_distincts": distinct,
        "erreurs_geometrie_registres": problems,
        "collisions_cables_physique": collisions, "collisions_cable_cable": cable_collisions,
        "jonctions_airy_localisees": joints,
        "eloignements_a_revoir": far_runs, "distances_echantillonnees": samples,
        "fichiers_non_modifies": not changed and not registry_changed,
        "qualification": "À valider", "finalisation_correcte": True,
        "conclusion": "Intersections ou erreurs à corriger" if problems or collisions or cable_collisions
                      else "Contrôles géométriques déclarés réussis ; éloignements et intégration physique à examiner",
        "limites": ["Fixation, serrage, vibration, abrasion et courbure minimale fabricant non qualifiés.",
                    "Enveloppes pleines des connecteurs : toutes les intersections sont signalées pour décision, jamais assimilées automatiquement à un contact autorisé.",
                    "La marge sous longueur commerciale totale ne vaut pas surplus de gaine disponible ; ce dernier reste inconnu sans longueur de gaine utile déclarée."]}
    OUTPUT.write_text(json.dumps(output, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    sys.__stdout__.write(json.dumps({k: output[k] for k in ("nombre_cables", "conclusion")}, ensure_ascii=False) + "\n")
    sys.__stdout__.flush()
    return 1 if problems or collisions or cable_collisions else 0


if __name__ == "__main__":
    try:
        code = run()
    except Exception:
        text = traceback.format_exc()
        OUTPUT.write_text(json.dumps({"date_utc": datetime.now(timezone.utc).isoformat(),
            "finalisation_correcte": False, "erreur_execution": text}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        sys.__stderr__.write(text)
        sys.__stderr__.flush()
        code = 2
    os._exit(code)
