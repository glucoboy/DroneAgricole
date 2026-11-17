"""Mesure FreeCAD des fenêtres communes NTC et GNSS, sans écrire les natifs."""

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

import FreeCAD as App
import Part

VERIFICATION = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(VERIFICATION), str(VERIFICATION / 'reconstruction_faisceaux')]
from autonomie_cao import gap, measured_pair
from read_brep_prototype import Reader


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def capsule(start, across, normal, axis, width, length, radius):
    plate = Part.makeBox(width, 2 * radius, length)
    rotation = App.Rotation(across, normal, axis, 'ZXY')
    plate.Placement = App.Placement(start - normal * radius, rotation)
    ends = [Part.makeCylinder(radius, length, start + across * offset, axis)
            for offset in (0, width)]
    return plate.fuse(ends).removeSplitter()


def measure(scene, group, interval, axes, radii, inner_radius, thickness):
    begin, end = interval
    start = App.Vector(axes[0][0], begin, axes[0][1])
    finish = App.Vector(axes[1][0], begin, axes[1][1])
    across = finish - start
    width = across.Length
    across.normalize()
    axis = App.Vector(0, 1, 0)
    normal = axis.cross(across)
    length = end - begin
    outer_radius = inner_radius + thickness
    args = (start, across, normal, axis, width, length)
    inner = capsule(*args, inner_radius)
    outer = capsule(*args, outer_radius)
    wall = outer.cut(inner).removeSplitter()
    if wall.isNull() or not wall.isValid() or len(wall.Solids) != 1:
        raise RuntimeError('Paroi invalide')

    # Délimiter l'occurrence du tronçon sur le câble, y compris latéralement.
    # Les deux branches éloignées NTC au voisinage de x=±30 n'en font pas partie.
    border = outer_radius + 1
    aperture = Part.makeBox(width + 2 * border, 2 * border, length)
    rotation = App.Rotation(across, normal, axis, 'ZXY')
    aperture.Placement = App.Placement(start - (normal + across) * border, rotation)
    result = {
        'id': f'{group}_{begin}_{end}', 'group': group, 'interval_y_mm': interval,
        'axis_xz_mm': axes, 'length_mm': length, 'inner_radius_mm': inner_radius,
        'wall_mm': thickness, 'aperture_box_mm': [width + 2 * border, 2 * border, length],
        'inner_section_mm': [width + 2 * inner_radius, 2 * inner_radius],
        'outer_section_mm': [width + 2 * outer_radius, 2 * outer_radius],
        'equivalent_diameter_at_wall_midline_mm': 2 * (inner_radius + thickness / 2) + 2 * width / math.pi,
        'nominal_area_fill': math.pi * sum(r * r for r in radii.values()) /
        (math.pi * inner_radius ** 2 + 2 * inner_radius * width),
        'wall_volume_mm3': wall.Volume, 'inclusion': [], 'pairs': [],
        'unknown': [], 'aabb_disjoint': 0,
    }
    lower_bounds = []
    for key, name, shape in scene:
        member = '/SA07_' in key and name in radii
        lower = gap(wall.BoundBox, shape.BoundBox)
        if lower > 1e-6 and not member:
            result['aabb_disjoint'] += 1
            lower_bounds.append(lower)
            continue
        try:
            if shape.isNull() or not shape.isValid() or not shape.Solids:
                raise RuntimeError('Solide d’entrée invalide')
            pair = measured_pair(wall, shape)
            result['pairs'].append({'occurrence': key, **pair})
            if not member:
                lower_bounds.append(pair['distance_mm'])
                continue
            section = shape.common(aperture)
            outside = section.cut(inner)
            if section.isNull() or not section.isValid() or (not outside.isNull() and not outside.isValid()):
                raise RuntimeError('Tranche non mesurable')
            nominal = math.pi * radii[name] ** 2 * length
            result['inclusion'].append({
                'member': name, 'occurrence': key, 'section_volume_mm3': section.Volume,
                'expected_volume_mm3': nominal, 'section_volume_delta_mm3': section.Volume - nominal,
                'outside_inner_mm3': outside.Volume, 'wall_intersection_mm3': pair['volume_mm3'],
                'wall_distance_mm': pair['distance_mm'],
            })
        except RuntimeError as error:
            result['unknown'].append({'occurrence': key, 'error': str(error)})
    result['non_member_gap_lower_bound_mm'] = None if result['unknown'] else min(lower_bounds)
    result['collisions'] = [p for p in result['pairs'] if p['volume_mm3'] > 1e-4]
    result['nominal_geometry_pass'] = (
        {r['member'] for r in result['inclusion']} == set(radii) and
        len(result['inclusion']) == len(radii) and
        not result['unknown'] and not result['collisions'] and
        all(abs(r['section_volume_delta_mm3']) <= 1e-4 and r['outside_inner_mm3'] <= 1e-4
            for r in result['inclusion'])
    )
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('copy', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    build = args.copy / 'verification/construction_prototype.json'
    rows = json.loads(build.read_text(encoding='utf-8'))['occurrences']
    reader = Reader(args.copy)
    scene = [(row['parent'] + '#' + row['occurrence'], row['occurrence'], reader.occurrence(row))
             for row in rows if row['parent'].startswith('sous_assemblages/')]
    ntc = [('NTC', interval, [(-3, -16), (3, -16)], {'NTC1': 0.9, 'NTC2': 0.9}, 1.2, 0.9)
           for interval in [(35, 41), (35, 44), (34.5, 44.5)]]
    gnss = [('GNSS', interval, [(-5, 100), (5, 100)], {'F21': 1.5, 'F36': 1.3}, 1.8, 0.9)
            for interval in [(82, 87), (81, 90)]]
    report = {
        'schema': 'cartographe.etude-corridors-ntc-gnss.v1',
        'input_copy': args.copy.as_posix(), 'freecad_version': App.Version(),
        'construction_sha256': sha(build), 'script_sha256': sha(Path(__file__)),
        'scene_sources_sha256': {r['source']: sha(args.copy / r['source']) for r in rows
                                 if r['parent'].startswith('sous_assemblages/')},
        'scope': 'Tranches BRep bornées dans le repère global et contrôle nominal de paroi. Aucune sauvegarde CAO.',
        'models': 'Axes mesurés CAO, diamètres extérieurs modélisés candidats, rayon intérieur et paroi idéalisée hypothétiques.',
        'pose_mm': 'Repère global du prototype, Y axe longitudinal des deux gaines étudiées.',
        'occurrences': len(scene),
        'history': 'L’ancienne tranche NTC non bornée latéralement interceptait aussi la branche à x=±30. La clé parent#occurrence distingue le câble NTC1 dans SA07 de la sonde dans SA02.',
        'physical_unknowns': ['approvisionnement de textile de forme utile, couture et fermeture',
                              'stabilité axiale, effilochage, abrasion et démontabilité',
                              'tolérances réelles des cordons et capteurs',
                              'CEM CAN/alimentation et PPS sur GNSS'],
        'supplier_analogue': {'url': 'https://www.hellermanntyton.com/products/open-woven-sleeves/twist-in-08/170-01001',
                              'documented': 'PET ouvrable, diamètre de faisceau 5 à 8 mm, paroi 0,9 mm',
                              'limitation': 'Analogie de paroi. Aptitude au profil ovale et à la coupe courte non établies.'},
        'gnss_supplier': 'https://docs.holybro.com/gps-and-rtk-system/f9p-h-rtk-series/dronecan-f9p/specification',
        'selection_rule': 'Accepter en géométrie conditionnelle si volumes complets sans paroi pénétrée. Conserver canaux GNSS séparés faute de caractérisation CEM et bénéfice limité à une fenêtre courte.',
        'candidates': [measure(scene, *spec) for spec in ntc + gnss],
    }
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
