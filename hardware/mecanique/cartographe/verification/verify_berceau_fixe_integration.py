"""Contrôle géométrique candidat, FreeCAD séparé, sans sauvegarde de CAO.

Exécution : Python fourni avec FreeCAD 1.1, depuis n'importe quel répertoire.
Les positions de mouvement sont discrètes et ne qualifient pas un mécanisme.
"""
from pathlib import Path
import argparse
import hashlib
import json
import math
import sys
import time

sys.path.insert(0, 'C:/Program Files/FreeCAD 1.1/bin')
import FreeCAD as A
import Part

ROOT = Path(__file__).resolve().parents[4]
MEC = ROOT / 'hardware/mecanique/cartographe'
SEUIL = 1e-6


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bbox(shape):
    b = shape.BoundBox
    return [b.XMin, b.XMax, b.YMin, b.YMax, b.ZMin, b.ZMax]


def bbox_gap(a, b):
    aa, bb = bbox(a), bbox(b)
    gaps = [max(aa[2*i] - bb[2*i+1], bb[2*i] - aa[2*i+1], 0.0) for i in range(3)]
    return math.sqrt(sum(x*x for x in gaps))


def item(name, obj, shape, category):
    return {'name': name, 'object': obj, 'shape': shape, 'category': category}


def links(doc, category):
    result = []
    for obj in doc.Objects:
        if obj.TypeId != 'App::Link' or not hasattr(obj, 'Shape') or obj.Shape.isNull():
            continue
        target = obj.LinkedObject
        result.append(item(obj.Name, obj, obj.Shape.copy(), category))
    return result


def describe(x):
    obj = x['object']
    target = obj.LinkedObject if obj.TypeId == 'App::Link' else obj
    placement = obj.getGlobalPlacement() if hasattr(obj, 'getGlobalPlacement') else obj.Placement
    return {'occurrence': x['name'], 'categorie': x['category'],
            'fichier_source': str(Path(target.Document.FileName).relative_to(ROOT)).replace('\\', '/'),
            'objet_source': target.Name, 'bbox_mm': bbox(x['shape']),
            'volume_mm3': x['shape'].Volume,
            'forme_valide': x['shape'].isValid() if x['category'] == 'candidat' else None,
            'validation_forme': 'Contrôlée' if x['category'] == 'candidat' else 'Non répétée sur les sources OEM et voisins',
            'matrice_occurrence_globale': list(placement.toMatrix().A)}


def collision(a, b):
    gap = bbox_gap(a['shape'], b['shape'])
    if gap > 1e-7:
        return None
    common = a['shape'].common(b['shape'])
    volume = common.Volume
    reservation = ('Loquet' in b['name'] or 'Southco' in Path(b['object'].LinkedObject.Document.FileName).name) if b['object'].TypeId == 'App::Link' else False
    return {'a': a['name'], 'b': b['name'], 'categorie_obstacle': b['category'],
            'volume_commun_mm3': volume, 'collision_volumique': volume > SEUIL,
            'bbox_intersection_mm': bbox(common) if volume > SEUIL else None,
            'interpretation': 'Intersection avec réservation loquet : accrochage ou conflit à interpréter, cinématique non démontrée' if reservation else
                              'Intersection géométrique à interpréter ; les contacts fonctionnels ne sont pas qualifiés par ce contrôle'}


def rotate(x, angle, axis):
    s = x['shape'].copy()
    s.rotate(A.Vector(*axis), A.Vector(0, 1, 0), -angle)
    return item(x['name'], x['object'], s, x['category'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate', default='sous_assemblages/SA02_BerceauFixe_Candidat.FCStd')
    parser.add_argument('--moving-prefixes', default='P25', help='Références mobiles avec le capot, séparées par virgules')
    parser.add_argument('--axis', nargs=3, type=float, default=[-110, 0, 161.5])
    parser.add_argument('--anchor-x', type=float, default=36)
    parser.add_argument('--anchor-y', type=float, default=33.5)
    parser.add_argument('--output', default='verification/integration_berceau_fixe_20261002.json')
    parser.add_argument('--variant', default='16Ah')
    parser.add_argument('--append', action='store_true', help='Ajouter cette variante à la preuve multi-variantes existante')
    args = parser.parse_args()
    start = time.monotonic()
    drone = A.openDocument(str(MEC / 'assemblages/Drone_Cartographe.FCStd'))
    candidate = A.openDocument(str(MEC / args.candidate))
    for d in A.listDocuments().values():
        d.recompute()
    native_angles = [{'document': d.Name, 'objet': o.Name, 'AngleOuvertureCandidat_deg': float(o.AngleOuvertureCandidat.Value)}
                     for d in A.listDocuments().values() for o in d.Objects if hasattr(o, 'AngleOuvertureCandidat')]
    if any(abs(x['AngleOuvertureCandidat_deg']) > 1e-7 for x in native_angles):
        raise RuntimeError('Le candidat doit être enregistré fermé pour ce protocole sans modification CAO')
    initial_hashes = {Path(d.FileName): sha(Path(d.FileName)) for d in A.listDocuments().values() if d.FileName}
    errors = [{'document': d.Name, 'objet': o.Name, 'etat': list(o.State)}
              for d in A.listDocuments().values() for o in d.Objects if 'Invalid' in o.State]
    new = links(candidate, 'candidat')
    if not new:
        raise RuntimeError('Aucune occurrence BRep candidate lisible')
    moving_prefixes = tuple(args.moving_prefixes.split(','))
    moving = [x for x in new if Path(x['object'].LinkedObject.Document.FileName).name.startswith(moving_prefixes)]
    fixed = [x for x in new if x not in moving]
    if not moving:
        raise RuntimeError('Référence(s) mobile(s) introuvable(s)')
    anchors = []
    frames = [x for x in fixed if Path(x['object'].LinkedObject.Document.FileName).name.startswith('P23')]
    for frame in frames:
        for x in [-args.anchor_x, args.anchor_x]:
            for y in [-args.anchor_y, args.anchor_y]:
                z = 87.0
                centre = frame['shape'].isInside(A.Vector(x, y, z), 1e-7, False)
                surrounding = [frame['shape'].isInside(A.Vector(x + 2.5*math.cos(t*math.pi/8),
                               y + 2.5*math.sin(t*math.pi/8), z), 1e-7, False) for t in range(16)]
                anchors.append({'centre_mm': [x,y,z], 'centre_occuper_par_matiere': centre,
                                'rayon_sondage_matiere_mm': 2.5, 'points_matiere_16': surrounding,
                                'matiere_presente_tout_autour_a_rayon_2_5': all(surrounding),
                                'limite': 'Sondage discret géométrique ; ne dimensionne pas la fixation.'})
    native_finals = []
    final_names = {'P23': 'Resultat', 'P24': 'PlaqueG10', 'P25': 'Resultat', 'P26': 'Cale20Ah'}
    for x in new:
        link = x['object']
        target = link.LinkedObject
        prefix = Path(target.Document.FileName).name[:3]
        if prefix not in final_names:
            continue
        final = target.Document.getObject(final_names[prefix])
        s = final.Shape.copy()
        s.Placement = link.Placement.multiply(s.Placement)
        native_finals.append({'occurrence': x['name'], 'objet_final': final.Name,
                              'volume_lien_mm3': x['shape'].Volume, 'volume_final_mm3': s.Volume,
                              'difference_volume_mm3': abs(x['shape'].Volume - s.Volume),
                              'difference_symetrique_mm3': x['shape'].cut(s).Volume + s.cut(x['shape']).Volume,
                              'matrice_lien': list(link.Placement.toMatrix().A)})

    # Feuilles OEM, sans les équipements historiques explicitement exclus.
    legacy = json.loads((MEC / 'verification/avionique_empilee_20260916.json').read_text(encoding='utf-8'))
    excluded = set(legacy['protocole']['exclusions_chassis'])
    chassis = next(d for d in A.listDocuments().values() if Path(d.FileName).name == 'EQ_Chassis_X650.FCStd')
    obstacles = []
    missing_brep = []
    for o in chassis.Objects:
        if o.TypeId != 'Part::Feature' or o.Name in excluded or not hasattr(o, 'Shape') or o.Shape.isNull():
            continue
        s = o.Shape.copy()
        s.Placement = o.getGlobalPlacement()
        obstacles.append(item(o.Name, o, s, 'OEM'))
    for name in ['SA03_Avionique', 'SA04_Calcul', 'SA05_Capteurs', 'SA06_RTK']:
        link = drone.getObject(name)
        obstacles.extend(links(link.LinkedObject.Document, name))
        for obj in link.LinkedObject.Document.Objects:
            if obj.TypeId == 'App::Link' and (not hasattr(obj, 'Shape') or obj.Shape.isNull()):
                missing_brep.append({'sous_assemblage': name, 'occurrence': obj.Name,
                                     'raison': 'Occurrence sans Shape BRep, non contrôlée par intersections de solides'})
    # Le connecteur courant reste un voisin pour cette vérification de variante.
    sbs = A.openDocument(str(MEC / 'sous_assemblages/SA02A_Connecteur_SBSX75A.FCStd'))
    obstacles.extend(links(sbs, 'P15_SBS_courant'))
    for d in A.listDocuments().values():
        if d.FileName and Path(d.FileName) not in initial_hashes:
            initial_hashes[Path(d.FileName)] = sha(Path(d.FileName))

    nominal = []
    for a in new:
        print('NOMINAL', a['name'], flush=True)
        for b in obstacles:
            c = collision(a, b)
            if c is not None:
                nominal.append(c)
    sweep = []
    for angle in range(0, 111, 5):
        print('CAPOT', angle, flush=True)
        checks = []
        for a in moving:
            current = rotate(a, angle, args.axis)
            for b in obstacles + fixed:
                c = collision(current, b)
                if c is not None:
                    checks.append(c)
        sweep.append({'ouverture_deg': angle, 'rotation_autour_Y_deg': -angle, 'paires_bbox_proches': checks})

    # Distances exactes limitées aux trois petites feuilles OEM proches des bords Y.
    distances = []
    selected_oem = [x for x in obstacles if x['category'] == 'OEM' and x['name'] in
                    {'Part__Feature147', 'Part__Feature158', 'Part__Feature159'}]
    for a in moving:
        for angle in [0, 55, 110]:
            current = rotate(a, angle, args.axis)
            for b in selected_oem:
                print('DISTANCE_FEUILLE', a['name'], angle, b['name'], flush=True)
                distances.append({'a': a['name'], 'b': b['name'], 'ouverture_deg': angle,
                                  'borne_inferieure_bbox_mm': bbox_gap(current['shape'], b['shape']),
                                  'distance_BRep_mm': current['shape'].distToShape(b['shape'])[0]})
    unchanged = all(sha(p) == h for p, h in initial_hashes.items())
    allchecks = nominal + [c for step in sweep for c in step['paires_bbox_proches']]
    result = {'date': '2026-10-02', 'statut': 'À valider',
              'protocole': {'FreeCAD': list(A.Version()), 'processus': 'Python FreeCAD séparé sans sauvegarde ni session GUI',
                            'script': str(Path(__file__).relative_to(ROOT)).replace('\\', '/'),
                            'script_sha256': sha(Path(__file__)),
                            'selection': 'Liens BRep par occurrence, feuilles Part::Feature OEM en placement global',
                            'exclusions_OEM_historiques': sorted(excluded), 'seuil_volume_mm3': SEUIL,
                            'nombre_exclusions_OEM': len(excluded),
                            'source_exclusions': 'verification/avionique_empilee_20260916.json ; aucun inventaire équivalent trouvé dans manifest.json',
                            'plateau_OEM_feature311_conserve': 'Part__Feature311' not in excluded,
                            'axe_capot_mm': args.axis, 'angles_ouverture_deg': list(range(0,111,5)),
                            'sens': 'Rotation négative autour de +Y pour lever le capot vers +Z',
                            'distances': 'Seulement capot contre trois feuilles OEM, trois positions ; aucun agrégat'},
              'erreurs_recalcul': errors, 'fichiers_CAO_inchanges': unchanged,
              'sources_sha256': {str(p.relative_to(ROOT)).replace('\\', '/'): h for p, h in initial_hashes.items()},
              'entrees_protocole_sha256': {str(p.relative_to(ROOT)).replace('\\', '/'): sha(p) for p in
                                         [MEC / 'manifest.json', MEC / 'verification/avionique_empilee_20260916.json']},
              'candidat': [describe(x) for x in new], 'obstacles': [describe(x) for x in obstacles],
              'occurrences_non_BRep_non_controlees': missing_brep,
              'sondages_ancrages_P23': anchors,
              'liens_vs_solides_finaux': native_finals,
              'angles_natifs_apres_reouverture': native_angles,
              'nominal_paires_bbox_proches': nominal, 'capot_positions_discretes': sweep,
              'distances_feuilles_BRep': distances,
              'collisions_volumiques': [c for c in allchecks if c['collision_volumique']],
              'limites': ['Échantillonnage discret ; absence de collision ne prouve pas tout le mouvement continu.',
                         'Vis, écrous, rondelles et accès sous-face des quatre fixations non représentés : reprise OEM et montage à valider.',
                         'Mains, câbles, sortie verticale batterie, connexion/déconnexion et cinématique du verrou non vérifiés ici.',
                         'Les contacts fonctionnels et axes de charnière nécessitent une interprétation ; volume commun ne suffit pas à conclure au montage.',
                         'Aucune qualification physique, rigidité, vibrations, tenue du verrou ou essai en vol.'],
              'duree_s': time.monotonic() - start}
    out = MEC / args.output
    proof = json.loads(out.read_text(encoding='utf-8')) if args.append and out.exists() else {
        'date': '2026-10-02', 'statut': 'À valider', 'variantes': {},
        'conclusion': 'Contrôles géométriques discrets seulement ; montage et mécanisme réels non qualifiés'}
    proof['variantes'][args.variant] = result
    out.write_text(json.dumps(proof, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'preuve': str(out), 'collisions': len(result['collisions_volumiques']),
                      'CAO_inchangee': unchanged, 'erreurs': len(errors)}), flush=True)
    for d in list(A.listDocuments().values()):
        A.closeDocument(d.Name)
    return 0 if unchanged and not errors else 1


if __name__ == '__main__':
    raise SystemExit(main())
