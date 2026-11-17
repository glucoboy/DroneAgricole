"""Appuis courts natifs pour les montées AIRY et USB3 sur P72/P73.

La fonction prolonge le dernier résultat natif d'un guide. Les câbles et
leurs rayons ne sont pas modifiés. Les lumières existantes restent ouvertes.
"""
import json
import FreeCAD as A


def extend_local_supports(api, document, root, base, side):
    """Ajouter les doigts après les retenues puissance, en coordonnées globales.

    ``side`` vaut ``left`` pour P72 et ``right`` pour P73. Le placement du
    groupe P73 (demi-tour) doit être défini avant l'appel. Aucun fichier n'est
    chargé ni enregistré par cette fonction.
    """
    if side not in ('left', 'right'):
        raise ValueError('side doit être left ou right')
    inverse = root.getGlobalPlacement().inverse()
    members, construction, stations = [], [], []
    cable = 'AIRY' if side == 'left' else 'F16'
    levels = (-70, -30, 10, 50, 90) if side == 'left' else (-45, 0, 35, 75)

    def box(name, size, position):
        obj = api.box(document, name, size, position)
        obj.Placement = inverse.multiply(obj.Placement)
        construction.append(obj)
        return obj

    for number, z in enumerate(levels, 1):
        if side == 'left':
            # Face X-100,3 : 0,2 mm de jeu devant la gaine AIRY Ø7.
            # La reprise s'arrête X-89 pour éviter l'articulation OEM à Z10.
            finger = box('DoigtAIRY' + str(number), (11.3, 6, 6),
                         (-100.3, 61, z - 3))
            point = [-104, 64, z]
        else:
            # Face X93,05 : 0,2 mm de jeu devant la gaine USB3 Ø5,5.
            finger = box('DoigtUSB3' + str(number), (5.25, 8, 6),
                         (87.8, -58, z - 3))
            point = [96, -54, z]
            # Évider seulement le doigt, jamais la base ni ses extensions :
            # cela prolonge les passages existants sans entailler la puissance.
            for slot_z in (-72, -47, -22, 3, 28, 53, 78, 93):
                if min(z + 3, slot_z + 2.4) <= max(z - 3, slot_z - 2.4):
                    continue
                tool = box('MaintienLumiereUSB3', (9.5, 8, 4.8),
                           (85, -60, slot_z - 2.4))
                cut = document.addObject('Part::Cut', 'DoigtUSB3Ajoure')
                cut.Base, cut.Tool = finger, tool
                construction.append(cut)
                finger = cut
        members.append(finger)
        stations.append({
            'id': cable + '_V_' + str(z), 'cables': [cable],
            'point_mm': point, 'support': ('P72' if side == 'left' else 'P73') + '/' + finger.Name,
            'type': 'collier autour du montant, du doigt et de la gaine',
            'largeur_collier_mm': 4.6,
            'montage': 'Un collier par station ; tête hors gaine, serrage sans écrasement. Les lumières du guide restent libres.',
        })

    result = document.addObject('Part::MultiFuse', 'GuideAvecRetenuesLocales')
    result.Shapes = [base] + members
    result.Refine = True
    if base in root.Group:
        root.removeObject(base)
    root.addObject(result)
    document.recompute()
    for obj in [base] + construction:
        obj.Visibility = False
    result.Visibility = True
    api.color(result, (.34, .38, .43))
    specification = {
        'cote': side, 'cable': cable, 'stations': stations,
        'colliers_cables': len(stations), 'vis_supplementaires': 0,
        'jeu_nominal_mm': .2, 'pas_max_stations_mm': 40 if side == 'left' else 45,
        'percages_OEM': 0, 'matiere_candidate': 'PA12',
        'limites': [
            'Appuis nominaux ; rigidité, tolérances, abrasion et tenue vibratoire À valider.',
            'Les chemins et têtes des colliers souples sont à vérifier au montage ; les doigts ne prouvent pas seuls la retenue.',
            'Adoucir les arêtes en contact et ne pas écraser la gaine lors du serrage.',
            'Les portions courbes et les raccords aux capteurs restent souples ; aucune liaison rigide à la suspension caméra.',
            'Le pas de stations est un choix de conception provisoire, pas une qualification du faisceau.',
        ],
        'qualification': 'À valider',
    }
    api.meta(root, 'RetenuesLocales', json.dumps(specification, ensure_ascii=False))
    return result, specification
