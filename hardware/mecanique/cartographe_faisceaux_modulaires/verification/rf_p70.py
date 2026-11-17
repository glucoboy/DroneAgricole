"""Relever les appuis P70 et mesurer des variantes locales BRep en mémoire."""
import hashlib
import json
from pathlib import Path

import FreeCAD as App
import Part

from read_brep_prototype import Reader


VERIFICATION = Path(__file__).resolve().parent
COPY = VERIFICATION.parent
CONSTRUCTION = VERIFICATION / 'construction_prototype.json'
ROUTES = VERIFICATION / 'routes_prototype.json'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def box(xmin, xmax, ymin, ymax, zmin, zmax):
    return Part.makeBox(xmax - xmin, ymax - ymin, zmax - zmin,
                        App.Vector(xmin, ymin, zmin))


def cylinder(radius, height, origin):
    return Part.makeCylinder(radius, height, App.Vector(*origin))


def bbox(shape):
    bounds = shape.BoundBox
    return [bounds.XMin, bounds.YMin, bounds.ZMin,
            bounds.XMax, bounds.YMax, bounds.ZMax]


def box_gap(left, right):
    a, b = bbox(left), bbox(right)
    return sum(max(0, a[i] - b[i+3], b[i] - a[i+3]) ** 2
               for i in range(3)) ** .5


def describe(shape):
    return {'bbox_mm': bbox(shape), 'solides': len(shape.Solids),
            'volume_mm3': shape.Volume, 'valide': shape.isValid()}


def measure(body, scene, excludes=(), clearance=0.00001):
    observations, errors = [], []
    count = 0
    for key, compound in scene.items():
        if key in excludes or box_gap(body, compound) > clearance:
            continue
        for index, obstacle in enumerate(compound.Solids, 1):
            if box_gap(body, obstacle) > clearance:
                continue
            try:
                volume = 0
                if body.BoundBox.intersect(obstacle.BoundBox):
                    intersection = body.common(obstacle)
                    if not intersection.isNull() and not intersection.isValid():
                        raise RuntimeError('Intersection BRep invalide')
                    volume = intersection.Volume
                distance, points, _ = body.distToShape(obstacle)
                count += 1
                if distance <= clearance or volume > 0.0001:
                    observations.append({'occurrence': key, 'solide': index,
                                         'distance_mm': distance,
                                         'points_mm': [list(p) for p in points[0]],
                                         'volume_intersection_mm3': volume})
            except (RuntimeError, ValueError) as error:
                errors.append({'occurrence': key, 'solide': index, 'erreur': str(error)})
    return {'paires_sous_solides': count,
            'observations': sorted(observations, key=lambda row: row['distance_mm']),
            'erreurs': errors}


def make_clamp(cy):
    block = box(-65.7, -55.7, cy-4.5, cy+4.5, 103, 109)
    bore = cylinder(3.1, 8, (-60, cy, 102))
    mouth = box(-60, -54, cy-2.5, cy+2.5, 102, 110)
    return block.cut(bore).cut(mouth).removeSplitter()


def make_socket_rf0():
    origin = (-76, 28, 106)
    sleeve = cylinder(3.4, 7, origin).cut(cylinder(1.7, 7, origin))
    return sleeve.cut(box(-80, -76, 26.75, 29.25, 105, 114)).removeSplitter()


def make_band_rf1():
    low, high = -17.3, -15.3
    bottom = box(-81.3, -70.7, low, high, 101.8, 103)
    left = box(-81.3, -80.1, low, high, 103, 110)
    right = box(-71.9, -70.7, low, high, 103, 110)
    top = box(-81.3, -70.7, low, high, 110, 111.2)
    return bottom.fuse([left, right, top]).removeSplitter()


def main():
    reader = Reader(COPY)
    rows = [r for r in read(CONSTRUCTION)['occurrences']
            if r['parent'].startswith('sous_assemblages/')]
    scene = {f"{row['parent']}#{row['occurrence']}": reader.occurrence(row)
             for row in rows}
    if len(scene) != len(rows):
        raise ValueError('Occurrence CAO dupliquée dans le même sous-assemblage')
    route_ids = {row['id'] for row in read(ROUTES)['routes']}
    cable_keys = {key for key in scene
                  if 'SA07_' in key and key.split('#')[-1] in route_ids}
    if len(cable_keys) != len(route_ids):
        raise ValueError('La projection des parcours SA07 ne couvre pas les IDs attendus')

    navigation = 'sous_assemblages/SA06_Prototype_Navigation.FCStd#'
    avionics = 'sous_assemblages/SA05_Prototype_Avionique.FCStd#'
    results = {}
    for i, cy in enumerate((37, -37)):
        support = navigation + f'SupportRF{i}'
        antenna = navigation + f'AntenneRF{i}'
        column = avionics + f'ColonnePorteuse_{1-i}'
        support_before = scene[support]
        original = {key: {'forme': describe(scene[key]),
                          'contacts': measure(scene[key], scene, {key}, .25)}
                    for key in (support, antenna)}
        ymin, ymax = (29, 37) if i == 0 else (-37, -24)
        bridge = box(-69, -64.2, ymin, ymax, 103, 106)
        clamp = make_clamp(cy)
        body = support_before.fuse([clamp, bridge]).removeSplitter()
        static = measure(body, scene, {support}, .1)
        insertion = {}
        # Prépositionnement rigide sans l’antenne et les câbles. Le franchissement
        # élastique de la gorge autour de la colonne reste un essai matériel.
        before_wiring = {support, antenna, column} | cable_keys
        for offset in range(0, 11, 2):
            moved = body.copy()
            moved.translate(App.Vector(-offset, 0, 0))
            insertion[str(offset)] = measure(moved, scene, before_wiring)
        if i == 0:
            retainer = body.fuse(make_socket_rf0()).removeSplitter()
            retention = {'type': 'Prise élastique intégrée, tige Ø3,2 mm',
                         'forme': describe(retainer),
                         'statique': measure(retainer, scene, {support}, .1)}
        else:
            band = make_band_rf1()
            with_body = {**scene, support: body}
            retention = {'type': 'Bande latérale ouverte en pose, section 2 × 1,2 mm',
                         'forme': describe(band), 'statique': measure(band, with_body, clearance=.1)}
        results[support] = {
            'existant': original,
            'variante_locale': {'colonne': column, 'axe_colonne_xy_mm': [-60, cy],
                               'diamètre_colonne_mm': 6, 'diamètre_empreinte_mm': 6.2,
                               'gorge_mm': 5, 'ouverture': '+X', 'forme': describe(body),
                               'montage': 'Insérer depuis −X avant raccordement. Retirer côté ouest après avoir libéré l’antenne.',
                               'pont_bbox_mm': bbox(bridge), 'statique': static,
                               'translation_ouest_mm': insertion,
                               'retenue_antenne': retention}}

    result = {
        'exigence': 'CAB-CARTO-001', 'version_freecad': App.Version(),
        'empreintes': {'construction': sha256(CONSTRUCTION), 'routes': sha256(ROUTES),
                       'lecteur': sha256(VERIFICATION / 'read_brep_prototype.py'),
                       'recette': sha256(Path(__file__))},
        'portée': f'{len(scene)} occurrences lues en mémoire par identifiant de document et de lien, aucun enregistrement natif.',
        'candidat_livré': 'NON_CONFORME pour la fixation des deux antennes. P75 était leur unique ancrage mécanique documenté. Après sa dépose, les contacts relevés ne relient aucun P70 à une pièce structurelle.',
        'origine': 'hardware/mecanique/cartographe/verification/prototype_fixations_equipements.py#extend_radio_mount et verify_colliers_prototype.py pour le sandwich RF1.',
        'variante_mesurée': 'CANDIDAT_CONDITIONNEL séparé, jamais enregistré dans les natifs. Les jeux, le clip axial, le montage élastique, le maintien en vibration, le desserrage, l’accès à la tête de bande et le comportement RF doivent être vérifiés.',
        'critères': {'intersection_mm3': 0.0001, 'voisinage_avant_mm': .25,
                     'pose_échantillonnée_mm': [0, 2, 4, 6, 8, 10],
                     'limite': 'Aucun balayage continu, aucune preuve physique. Les contacts nominaux voulus antenne/support sont distincts des collisions.'},
        'résultats': results}
    (VERIFICATION / 'rf_p70.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n',
                                               encoding='utf-8')


if __name__ == '__main__':
    main()
