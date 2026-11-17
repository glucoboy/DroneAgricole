"""Compléments des huit départs de bras, sur les montantes existantes P75.

Les quatre parcours LED et les quatre commandes MAIN restent inchangés.
Deux colliers MAIN par départ ferment l'intervalle initial de 100 à 109 mm :
un sur un ligament du plateau P64, l'autre hors plateau sur P75. Le critère
de portée guidée de 50 mm reste inchangé.
"""
import json
import FreeCAD as A


def energy_departure_interfaces():
    points = [(-80.26666666666667, -72, 40.4), (74.66666666666667, 68, 40.4),
              (-76, 74, 40.4), (76, -74, 40.4)]
    directions = [(8, -30, 0), (2, 30, 0), (0, 1, 0), (0, -1, 0)]
    stations, slots = [], []
    for arm, (point, direction) in enumerate(zip(points, directions), 1):
        tangent = A.Vector(*direction); tangent.normalize()
        normal = A.Vector(-tangent.y, tangent.x, 0)
        stations.append({'id': 'F04_' + str(arm) + '_DEP_1',
            'cables': ['F04_' + str(arm)], 'point_mm': [point[0], point[1], 4.2],
            'repere': 'local P64 ; pose nominale de l’occurrence Z36,2 mm',
            'tangente': list(tangent), 'support': 'P64/LigamentDepart' + str(arm),
            'type': 'collier autour ligament G10 et gaine', 'largeur_collier_mm': 4.6,
            'jeu_nominal_mm': .6})
        for sign in (-1, 1):
            center = A.Vector(*point) + normal * (sign * 3.65)
            # Boîte englobant le passage tourné 5,2 × 1,8 ; la lumière
            # rectangulaire reste directement éditable avec le plateau.
            width = abs(tangent.x) * 5.2 + abs(normal.x) * 1.8
            height = abs(tangent.y) * 5.2 + abs(normal.y) * 1.8
            slots.append((center.x, center.y, width, height))
    return {'stations': stations, 'lumieres_P64_mm': slots, 'colliers_cables': 4,
        'vis_supplementaires': 0, 'qualification': 'À valider',
        'montage': 'Bande sous P64 dans le jeu OEM, deux passages par ligament ; aucune cale ni perçage OEM.',
        'limites': ['Ligaments, serrage, finition des lumières et abrasion à valider sur le G10 réel.',
                    'Bandes 4,6 × 1,2 mm ; têtes et verrouillage non représentés.']}


def layout():
    members, stations = [], []

    def bar(name, start, end):
        members.append({'nom': name, 'debut_mm': list(start),
                        'fin_mm': list(end), 'diametre_mm': 3.0})

    def station(name, cable, point, tangent, offset, radius, support):
        stations.append({'id': name, 'cables': [cable], 'point_mm': list(point),
            'tangente': list(tangent), 'decalage_appui_mm': list(offset),
            'rayon_cable_mm': radius, 'support': 'P75/' + support,
            'type': 'collier autour appui rond et gaine',
            'largeur_collier_mm': 4.6, 'jeu_nominal_mm': .2})

    montants = [(-81.5, -58), (74, 60.5), (-76, 68.5), (73.5, -66)]
    for arm, (sx, sy) in enumerate([(-1, -1), (1, 1), (-1, 1), (1, -1)], 1):
        bx, by = montants[arm - 1]
        tag = 'F04_' + str(arm)
        arm_y = by + sy * (22 if arm == 1 else 14)
        bar(tag + '_ARCH1', (bx, by, 84), (bx, arm_y, 84))
        bar(tag + '_ARCH2', (bx, arm_y, 84), (sx * 130, arm_y, 84))

        def connect(identifier, axis, tangent):
            end = axis + tangent * 6
            normal = A.Vector(-tangent.y, tangent.x, 0); normal.normalize()
            if identifier.startswith('LED_'):
                normal = A.Vector(sx, -sy, 0); normal.normalize()
            elif normal.y * sy < 0:
                normal = -normal
            elbow = end + normal * 8
            bar(identifier + 'H1', (sx * 130, arm_y, 84), (sx * 130, elbow.y, 84))
            bar(identifier + 'H2', (sx * 130, elbow.y, 84), (elbow.x, elbow.y, 84))
            bar(identifier + 'V', (elbow.x, elbow.y, 84), elbow)
            bar(identifier + 'R', elbow, end)

        point = A.Vector(sx * 96, sy * (88 + 20 * 19 / 23), 40.4)
        tangent = A.Vector(sx * 23, sy * 19, 0); tangent.normalize()
        offset = A.Vector(-tangent.y, tangent.x, 0)
        if offset.y * sy < 0:
            offset = -offset
        offset *= 2.5
        axis = point + offset
        support = tag + '_AP2'
        bar(support, axis - tangent * 6, axis + tangent * 6)
        connect(tag + '_RE2', axis, tangent)
        station(tag + '_DEP_2', tag, point, tangent, offset, .8, support)

        tag = 'LED_' + str(arm)
        point = A.Vector(sx * 116, sy * 92, 33.625)
        tangent = A.Vector(sx * 16, sy * 16, -25); tangent.normalize()
        offset = A.Vector(sx, -sy, 0); offset.normalize(); offset *= 2.9
        axis = point + offset
        support = tag + '_AP'
        bar(support, axis - tangent * 6, axis + tangent * 6)
        connect(tag + '_RE', axis, tangent)
        station(tag + '_DEP', tag, point, tangent, offset, 1.2, support)
    return members, stations


def extend_departures(api, document, root, base):
    definitions, stations = layout()
    members = []
    for item in definitions:
        start, end = A.Vector(*item['debut_mm']), A.Vector(*item['fin_mm'])
        direction = end - start
        obj = api.cylinder(document, item['nom'], item['diametre_mm'] / 2,
                           direction.Length, item['debut_mm'])
        obj.Placement.Rotation = A.Rotation(A.Vector(0, 0, 1), direction)
        members.append(obj)
    result = document.addObject('Part::MultiFuse', 'P75AvecDepartsBras')
    result.Shapes = [base] + members
    result.Refine = False
    if base in root.Group:
        root.removeObject(base)
    root.addObject(result)
    document.recompute()
    for obj in [base] + members:
        obj.Visibility = False
    result.Visibility = True
    api.color(result, (.34, .38, .43))
    spec = {'stations': stations, 'departs_fonctionnels': 8,
        'colliers_cables': 8, 'vis_supplementaires': 0,
        'reference_reutilisee': 'P75_Guide_Avionique_Prototype',
        'montage': 'Colliers aux milieux des appuis ; reprises aux extrémités, hors largeur de bande.',
        'qualification': 'À valider',
        'limites': ['PA12 candidat ; rigidité, fluage, finition, serrage et vibration à vérifier sur matériel.',
                    'Libérer les faisceaux avant le pliage des bras ; aucun nouveau perçage OEM.',
                    'Les boucles témoins contrôlent la bande 4,6 × 1,2 mm, sans tête ni verrouillage.']}
    api.meta(root, 'RetenuesDepartsBras', json.dumps(spec, ensure_ascii=False))
    return result, spec
