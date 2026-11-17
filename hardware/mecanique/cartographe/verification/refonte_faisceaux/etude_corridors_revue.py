"""Revue indépendante des preuves et du modèle sauvegardé, sans recomputation ni écriture CAO."""

from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import sys

import FreeCAD as App
import Part

here = Path(__file__).resolve().parent
root = here.parents[4]
sys.path[:0] = [str(here.parent), str(root / '.agents/skills/electromechanical-integration/scripts')]
from read_brep_prototype import Reader
from workspace_guard import dependencies, verify_sources
from etude_corridors import capsule

base = root / 'hardware/mecanique/cartographe_faisceaux_autonome'
copy = root / 'hardware/mecanique/cartographe_faisceaux_refonte'
run = root / '.runtime/refonte-faisceaux'
build_path = 'verification/construction_prototype.json'
routes_path = 'verification/routes_prototype.json'
sa_path = 'sous_assemblages/SA07_Prototype_Faisceaux.FCStd'
volume_tol = 1e-4


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def near(a, b, tol=1e-6):
    return all(abs(x-y) <= tol for x, y in zip(a, b)) and len(a) == len(b)


def good(shape):
    return not shape.isNull() and shape.isValid() and len(shape.Solids) == 1 and math.isfinite(shape.Volume)


def common_volume(a, b):
    intersection = a.common(b)
    if not intersection.isNull() and not intersection.isValid():
        raise RuntimeError('Intersection BRep invalide')
    return intersection.Volume


def partition(architecture, inventory):
    ids = [item['id'] for item in inventory['routes']]
    grouped = [name for group in architecture['groupes'] for name in group['routes']]
    connections = [item['id'] for item in inventory['connections']]
    return {
        'electrical_catalog_count': len(connections), 'electrical_catalog_unique': len(set(connections)),
        'scope_counts': dict(Counter(item['scope'] for item in inventory['connections'])),
        'route_count': len(ids), 'architecture_group_count': len(architecture['groupes']),
        'missing': sorted(set(ids) - set(grouped)), 'extra': sorted(set(grouped) - set(ids)),
        'duplicates': sorted(name for name, count in Counter(grouped).items() if count != 1),
    }


def inspect_graph(graph, paths):
    path_by_id = {row['id']: row for row in paths}
    route_ids = [row['id'] for row in graph['routes']]
    troubles = []
    included_by_route = {}
    for row in graph['routes']:
        seq = row['segments']
        path = path_by_id[row['id']]
        if (not seq or not near(seq[0]['point_depart_mm'], path['points_mm'][0]) or
                not near(seq[-1]['point_arrivee_mm'], path['points_mm'][-1])):
            troubles.append([row['id'], 'extrémité'])
        if any(a['destination'] != b['origine'] or not near(a['point_arrivee_mm'], b['point_depart_mm'])
               for a, b in zip(seq, seq[1:])):
            troubles.append([row['id'], 'chaîne de segments non contiguë'])
        if any(s['longueur_mm'] <= 0 for s in seq) or abs(sum(s['longueur_mm'] for s in seq)-row['longueur_mm']) > 1e-6:
            troubles.append([row['id'], 'longueur'])
        included_by_route[row['id']] = [s['id'] for s in seq if s['nature'] == 'gaine_commune']
    checked = []
    for spec in graph['gaines']:
        cable_ids = [cid for cid, sleeves in included_by_route.items() if spec['occurrence'] in sleeves]
        if set(cable_ids) != set(spec['membres']) or len(cable_ids) != len(spec['membres']):
            troubles.append([spec['occurrence'], 'composition graphe'])
        checked.append({'gaine': spec['occurrence'], 'length_mm': spec['longueur_mm'], 'members': cable_ids})
    return {'route_count': len(route_ids), 'missing': sorted(set(path_by_id) - set(route_ids)),
            'duplicates': sorted(key for key, count in Counter(route_ids).items() if count > 1),
            'issues': troubles, 'sleeves': checked,
            'common_length_mm': sum(row['length_mm'] for row in checked),
            'cumulative_route_length_mm': sum(r['longueur_mm'] for r in graph['routes'])}


def property_links(props, name):
    return [item.get('value') for item in props[name].find('LinkList').findall('Link')]


def inspect_native_model(native, final, original, architecture, graph, installation):
    types, objects = native.xml(sa_path)
    occurrences = {r['occurrence']: r for r in final if r['parent'] == sa_path}
    original_map = {(r['parent'], r['occurrence']): r for r in original}
    final_map = {(r['parent'], r['occurrence']): r for r in final}
    transform_changes = []
    for key, old in original_map.items():
        if key not in final_map or not near(final_map[key]['matrice'], old['matrice'], 1e-9):
            transform_changes.append(key)
    group_errors = []
    for group in architecture['groupes']:
        key = 'Groupe_' + group['id']
        props = objects[key]
        assigned = property_links(props, 'Group')
        expected = group['routes'] + [s['occurrence'] for s in graph['gaines'] if s['groupe'] == group['id']]
        if types[key] != 'App::Part' or not set(expected).issubset(assigned):
            group_errors.append([key, sorted(set(expected)-set(assigned))])
    link_errors = []
    for name, row in occurrences.items():
        props = objects[name]
        linked = props['LinkedObject'].find('XLink')
        rel = linked.get('file')
        actual = ((copy / sa_path).parent / rel).resolve()
        if (types[name] != 'App::Link' or actual != (copy / row['source']).resolve() or
                linked.get('name') != row['objet_source'] or
                not near(native.placement(sa_path, name).toMatrix().A, row['matrice'], 1e-8)):
            link_errors.append(name)
    sleeve_errors = []
    for spec in graph['gaines']:
        name = spec['occurrence']
        props = objects[name]
        if set(property_links(props, 'CablesContenus')) != set(spec['membres']):
            sleeve_errors.append([name, 'membres natifs'])
        for end in ('Entree', 'Sortie'):
            derivation = objects['Derivation' + name + end]
            if set(property_links(derivation, 'BranchesIndividuelles')) != set(spec['membres']):
                sleeve_errors.append([name, 'dérivation ' + end])
    closure = {p.relative_to(copy).as_posix(): sha(p) for p in dependencies(copy, [installation['entree']])}
    return {'closure_count': len(closure), 'closure_matches_receipt': closure == installation['modeles_natifs_sha256'],
            'source_baseline_matches': verify_sources(read(copy / 'experiment.json'))['sources_unchanged'],
            'source_original_matches': verify_sources(read(base / 'experiment.json'))['sources_unchanged'],
            'preserved_placements': len(original_map) - len(transform_changes), 'transform_changes': transform_changes,
            'native_groups_issues': group_errors, 'native_links_checked': len(occurrences),
            'native_links_issues': link_errors, 'native_sleeves_issues': sleeve_errors}


def inspect_guide(guide_id, parts, installation, original_map, final_map):
    before_reader, after_reader = Reader(base), Reader(copy)
    before_row, after_row = original_map[guide_id], final_map[guide_id]
    prior, result = before_reader.occurrence(before_row), after_reader.occurrence(after_row)
    if not good(prior) or not good(result):
        raise RuntimeError('Guide d’entrée ou sortie non monobloc ' + guide_id)
    intersection = common_volume(prior, result)
    removed = prior.cut(result)
    if not good(removed) and (removed.isNull() or not removed.isValid() or removed.Volume <= 0):
        raise RuntimeError('Retrait non mesurable ' + guide_id)
    checks = []
    for name in parts:
        p = before_reader.shape(before_row['source'], name)
        source_pose = before_reader.placement(before_row['source'], before_row['objet_source'])
        occurrence_pose = App.Placement(App.Matrix(*before_row['matrice']))
        p.Placement = occurrence_pose.multiply(source_pose.inverse()).multiply(p.Placement)
        checks.append({'feature': name, 'volume_mm3': p.Volume,
                       'removed_overlap_mm3': common_volume(removed, p)})
    return {'id': guide_id, 'old_mm3': prior.Volume, 'new_mm3': result.Volume,
            'removed_mm3': prior.Volume - intersection, 'added_mm3': result.Volume - intersection,
            'removed_brep_mm3': removed.Volume, 'removed_brep_solids': len(removed.Solids),
            'matches_installation': abs(prior.Volume - intersection - installation['guides_modifies'][guide_id]['volume_retrait_mm3']) <= volume_tol,
            'features_before_relief': checks}


def station_window(point, width, across=8):
    x, y, z = point
    return Part.makeBox(width, across * 2, across * 2, App.Vector(x-width/2, y-across, z-across))


def sleeve_wall(spec):
    start, end = (App.Vector(*point) for point in spec['axes_bords_mm'])
    across = end - start
    width = across.Length
    across.normalize()
    axis = App.Vector(*spec['direction']).normalize()
    normal = axis.cross(across)
    length = spec['longueur_mm']
    radius = spec['rayon_interieur_mm']
    wall = capsule(start, across, normal, axis, width, length, radius + spec['paroi_mm']).cut(
        capsule(start, across, normal, axis, width, length, radius))
    if not good(wall):
        raise RuntimeError('Gaine station non mesurable')
    return wall


def preview_guide(shape, spec):
    clearance = spec['degagement_guide_mm']
    start, end = (App.Vector(*point) for point in spec['axes_bords_mm'])
    across = end - start
    width = across.Length
    across.normalize()
    axis = App.Vector(*spec['direction']).normalize()
    normal = axis.cross(across)
    length = spec['longueur_mm'] + 2 * clearance
    radius = spec['rayon_interieur_mm'] + spec['paroi_mm'] + clearance
    tool = capsule(start - axis * clearance, across, normal, axis, width, length, radius)
    return shape.cut(tool).removeSplitter()


def inspect_stations(graph, original_map, final_map, previews=None):
    before_reader = Reader(base)
    after_reader = before_reader if previews else Reader(copy)
    p75_old = before_reader.occurrence(original_map['P75_Cadre'])
    p73_old = before_reader.occurrence(original_map['P73_Guide'])
    p75 = p75_old, previews['P75_Cadre'] if previews else after_reader.occurrence(final_map['P75_Cadre'])
    p73 = p73_old, previews['P73_Guide'] if previews else after_reader.occurrence(final_map['P73_Guide'])
    specs = {s['occurrence']: s for s in graph['gaines']}
    selection = []
    if 'GaineSignalNord' in specs:
        for site, cable, point, feature in [
            ('F24A_AR_35', 'F24A', (35,55,118), 'CaleF24A35'),
            ('F24A_AR_65', 'F24A', (64.5,55,118), 'CaleF24A65'),
            ('F24C_AR_40', 'F24C', (40,61,116), 'LisseF24CArriere'),
            ('F24C_AR_65', 'F24C', (65,61,116), 'LisseF24CArriere'),
        ]:
            selection.append((site, cable, point, feature, p75, 'P75_Cadre', 'GaineSignalNord', True))
    if 'ProtectionF38' in specs:
        for x in (-5, 40):
            for polarity, y in (('Pos',-94), ('Neg',-104)):
                cable = 'F38_' + polarity.upper()
                selection.append((f'{cable}_X{x}', cable, (x,y,52), 'PontF38' + polarity,
                                  p73, 'P73_Guide', 'ProtectionF38', False))
    results = []
    for site, cable, point, feature, (before, after), guide_id, protection, documented_width in selection:
        width = 4.6  # bande P75 documentée, largeur de fenêtre d'analyse seulement pour F38
        window = station_window(point, width)
        before_section = before.common(window)
        after_section = after.common(window)
        feature_row = original_map[guide_id]
        feature_shape = before_reader.shape(feature_row['source'], feature)
        source_pose = before_reader.placement(feature_row['source'], feature_row['objet_source'])
        occurrence_pose = App.Placement(App.Matrix(*feature_row['matrice']))
        feature_shape.Placement = occurrence_pose.multiply(source_pose.inverse()).multiply(feature_shape.Placement)
        feature_section = feature_shape.common(window)
        spec = specs[protection]
        candidate_wall = sleeve_wall(spec).common(window)
        baseline_wall = before_reader.occurrence(original_map[protection]).common(window) if protection in original_map else None
        cable_section = after_reader.occurrence(final_map[cable]).common(window)
        if any(shape.isNull() or not shape.isValid() for shape in (before_section, after_section, feature_section,
                                                                   cable_section, candidate_wall)):
            raise RuntimeError('Section station invalide ' + site)
        x0 = spec['axes_bords_mm'][0][0]
        x1 = x0 + spec['longueur_mm']
        left, right = point[0]-width/2, point[0]+width/2
        outside_band = max(0, x0-left) + max(0, right-x1)
        removed = max(0., before_section.Volume - after_section.Volume)
        feature_before = common_volume(before_section, feature_section)
        feature_after = common_volume(after_section, feature_section)
        results.append({'id': site, 'cable': cable, 'guide': guide_id, 'feature': feature, 'point_mm': point,
                        'window_mm': [left, right], 'band_width_class': 'documentée' if documented_width else 'fenêtre de contrôle hypothétique',
                        'length_of_window_outside_sleeve_mm': outside_band,
                        'before_local_guide_volume_mm3': before_section.Volume, 'after_local_guide_volume_mm3': after_section.Volume,
                        'guide_removed_in_window_mm3': removed, 'support_before_in_window_mm3': feature_before,
                        'support_after_in_window_mm3': feature_after,
                        'guide_to_cable_before_mm': before_section.distToShape(cable_section)[0],
                        'guide_to_cable_after_mm': after_section.distToShape(cable_section)[0],
                        'guide_to_candidate_sleeve_after_mm': after_section.distToShape(candidate_wall)[0],
                        'guide_to_candidate_sleeve_intersection_mm3': common_volume(after_section, candidate_wall),
                        'guide_to_baseline_sleeve_mm': before_section.distToShape(baseline_wall)[0] if baseline_wall else None,
                        'classification': ('CANDIDATE_GAINE_COMMUNE_A_REDEFINIR' if documented_width else
                                           'SITE_F38_CANDIDAT_REPRISE_LOCALE' if removed > volume_tol else
                                           'SITE_F38_CANDIDAT_GEOMETRIE_PRESERVEE'),
                        'limits': 'Section locale de volumes et distances. Bande, tête, chemin de fermeture, maintien axial et serrage non démontrés.'})
    return results


def main():
    architecture = read(here / 'architecture.json')
    inventory = read(here / 'inventaire.json')
    report = {'schema': 'cartographe.refonte.revue-independante.v1', 'scope': 'Relecture des preuves, mesures BRep sauvegardées et fermeture XLink sans modification de natif.',
              'partition': partition(architecture, inventory),
              'physical_limits': [
                  'Un retrait petit et un guide monobloc ne garantissent ni ligament utile, ni rigidité, ni tenue des colliers.',
                  'Enveloppes de gaine idéalisées. Couture, ouverture, maintien axial, tolérances, abrasion et extraction à valider.',
                  'Courant et déclassement F38, immunité PPS/référence CSI et dommage commun des quatre commandes MAIN à caractériser.',
                  'Modes mobiles, mouvements continus, vibrations et fatigue à valider séparément du contrôle nominal.',
                  'Les fichiers sources électriques couvrent plus de liaisons que les volumes CAO. Les lignes non résolues restent ouvertes.',
              ],
              'decisions_reviewed': [
                  {'subject': 'NTC', 'verdict': 'cohérent pour un candidat nominal', 'evidence': 'etude_corridors.json',
                   'rationale': '9 mm, marge radiale 0,30 mm et borne aux non-membres 2,25 mm. Retenues distantes conservées; maintien textile propre non démontré.'},
                  {'subject': 'GNSS', 'verdict': 'séparation justifiée dans le périmètre', 'evidence': 'etude_corridors.json',
                   'rationale': 'La géométrie permet une gaine courte. Bénéfice limité à 9 mm, et cohabitation DroneCAN/alimentation et UART2/GPRMC/PPS non établie.'},
                  {'subject': 'MAIN', 'verdict': 'choix conditionnel à comparer au repli intact', 'evidence': 'etude_corridors_variante_main_paire.json',
                   'rationale': 'Deux branches reroutées sans modifier P75 pour MAIN donnent 8,5 mm avec +24 mm de câble. La solution 8 mm à une branche et retrait de guide réduit l’allongement à +12 mm; comparer accès et résistance.'},
                  {'subject': 'signal nord', 'verdict': 'cohérent pour un candidat nominal', 'evidence': 'SIGNAL_NORD_RELIEF_L30.json',
                   'rationale': 'F24A PPS et F24C référence 3,3 V/masse, sans canal vidéo CSI. Retours distincts, accessibilité à l’extracteur et couplage à contrôler.'},
                  {'subject': 'alimentations de vol', 'verdict': 'séparation maintenue', 'evidence': 'architecture.json et etude_corridors_droites.json',
                   'rationale': 'Proximité F06/F32 en montée ouest sans gaine commune. La proximité seule ne démontre aucune indépendance face aux dommages.'},
              ],
              'freecad_version': App.Version(), 'script_sha256': sha(Path(__file__)), 'saved_copy_reviewed': False}
    installation_path = here / 'installation.json'
    if installation_path.exists():
        installation = read(installation_path)
        graph_path = here / 'graphe_physique.json'
        graph = read(graph_path)
        construction = read(copy / build_path)
        baseline_construction = read(base / build_path)
        routes = read(copy / routes_path)['routes']
        saved = inspect_native_model(Reader(copy), construction['occurrences'], baseline_construction['occurrences'],
                                     architecture, graph, installation)
        original_map = {row['occurrence']: row for row in baseline_construction['occurrences'] if row['parent'] == sa_path}
        final_map = {row['occurrence']: row for row in construction['occurrences'] if row['parent'] == sa_path}
        report.update(saved_copy_reviewed=True, native=saved, graph=inspect_graph(graph, routes),
                      reviewed_hashes={'installation': sha(installation_path), 'graph': sha(graph_path),
                                       'assembly': sha(copy / installation['entree']), 'construction': sha(copy / build_path)},
                      final_guide_checks=[])
        for guide_id, features in {
            'P75_Cadre': ('PeigneMAINIncline', 'AppuiPeigneAvant', 'AppuiPeigneArriere'),
            'P73_Guide': ('PontF38Pos', 'PontF38Neg'),
        }.items():
            if guide_id in installation['guides_modifies']:
                try:
                    report['final_guide_checks'].append(inspect_guide(guide_id, features, installation, original_map, final_map))
                except (RuntimeError, ValueError, KeyError) as error:
                    report['final_guide_checks'].append({'id': guide_id, 'unknown': str(error)})
        try:
            report['retention_stations'] = inspect_stations(graph, original_map, final_map)
        except (RuntimeError, ValueError, KeyError) as error:
            report['retention_stations'] = {'unknown': str(error)}
        report['numerical_scope'] = 'Contrôle nominal des fichiers finalisés. Les appuis documentés sont distincts des efforts de serrage et d’une preuve de maintien.'
    else:
        specs = {s['id']: s for s in read(here / 'variantes.json')['candidats']}
        f38 = specs['F38_RELIEF_Xm40_65']
        north = specs['SIGNAL_NORD_RELIEF_L30']
        main_sleeve = specs['MAIN_4_RELIEF_L8']
        original_map = {row['occurrence']: row for row in read(base / build_path)['occurrences'] if row['parent'] == sa_path}
        reader = Reader(base)
        previews = {'P73_Guide': preview_guide(reader.occurrence(original_map['P73_Guide']), f38),
                    'P75_Cadre': preview_guide(preview_guide(reader.occurrence(original_map['P75_Cadre']), north), main_sleeve)}
        try:
            report['retention_stations_preview'] = inspect_stations({'gaines': [north, f38]}, original_map, original_map, previews)
        except (RuntimeError, ValueError, KeyError) as error:
            report['retention_stations_preview'] = {'unknown': str(error)}
    output = here / 'etude_corridors_revue.json'
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
