"""Essai du tronc MAIN étendu par deux branches reroutées et P75 préservé."""

import json
import math
import os
from pathlib import Path
import sys

from etude_corridors import App, Part, Reader, capsule, gap, measured_pair, sha
from autonomie_cao import COPY, gui
from freecad_geometry import inspect_route, rebuild_cable_in_isolated_document


def main(output):
    build_path = COPY / 'verification/construction_prototype.json'
    routes_path = COPY / 'verification/routes_prototype.json'
    routes = {row['id']: row for row in json.loads(routes_path.read_text(encoding='utf-8'))['routes']}
    rows = [row for row in json.loads(build_path.read_text(encoding='utf-8'))['occurrences']
            if row['parent'].startswith('sous_assemblages/')]
    reader = Reader(COPY)
    scene = {row['parent'] + '#' + row['occurrence']: reader.occurrence(row) for row in rows}
    builder, environment = gui()
    doc = App.newDocument('VarianteMainPaire')
    results = []
    for name, x in [('F04_1', 105), ('F04_2', 108)]:
        source = routes[name]
        points = [list(point) for point in source['points_mm']]
        points[3][0] = points[4][0] = x
        start_axis = App.Vector(*points[1]) - App.Vector(*points[0])
        end_axis = App.Vector(*points[-2]) - App.Vector(*points[-1])
        cable, wire = builder.make_native_cable(doc, None, name, points, source['diametre_mm'], source['rayon_courbure_mm'])
        fresh = rebuild_cable_in_isolated_document(doc, cable)
        geo = inspect_route(wire.Shape.Wires[0], minimum_radius_mm=source['rayon_courbure_mm'],
                            start_position=points[0], end_position=points[-1],
                            start_axis=list(start_axis), end_axis=list(end_axis))
        key = next(key for key in scene if '/SA07_' in key and key.endswith('#' + name))
        scene[key] = cable.Shape.copy()
        results.append({'id': name, 'occurrence': key, 'x_mm': x, 'points_mm': points, 'recompute': fresh,
                        'baseline_length_mm': source['longueur_courbe_mm'], 'geometry': geo})

    members = [key for key in scene if '/SA07_' in key and key.split('#')[-1] in {'F04_1', 'F04_2', 'F04_3', 'F04_4'}]
    if len(members) != 4:
        raise RuntimeError('Composition MAIN incorrecte')
    axis = App.Vector(1, 0, 0)
    across = App.Vector(0, 1, 1).normalize()
    normal = axis.cross(across)
    start = App.Vector(91, -37, 163)
    width = 9 * math.sqrt(2)
    length = 8.5
    inner_radius = 1.05
    outer_radius = 1.65
    args = (start, across, normal, axis, width, length)
    inner = capsule(*args, inner_radius)
    wall = capsule(*args, outer_radius).cut(inner).removeSplitter()
    if wall.isNull() or not wall.isValid() or len(wall.Solids) != 1:
        raise RuntimeError('Paroi MAIN invalide')

    box_border = outer_radius + 1
    aperture = Part.makeBox(width + 2 * box_border, 2 * box_border, length)
    aperture.Placement = App.Placement(start - (across + normal) * box_border,
                                       App.Rotation(across, normal, axis, 'ZXY'))
    nominal_volume = math.pi * 0.8 ** 2 * length
    inclusion = []
    for key in members:
        section = scene[key].common(aperture)
        outside = section.cut(inner)
        if section.isNull() or not section.isValid() or (not outside.isNull() and not outside.isValid()):
            raise RuntimeError('Tranche MAIN invalide ' + key)
        inclusion.append({'occurrence': key, 'nominal_volume_mm3': nominal_volume, 'section_volume_mm3': section.Volume,
                          'outside_inner_mm3': outside.Volume})

    sleeve_key = 'GaineMAIN_x91_99_5'
    scene[sleeve_key] = wall
    checked = set()
    failures = []
    proximity = []
    excluded = 0
    for key in [sleeve_key, *[result['occurrence'] for result in results]]:
        shape = scene[key]
        for other_key, other in scene.items():
            pair = tuple(sorted((key, other_key)))
            if key == other_key or pair in checked:
                continue
            checked.add(pair)
            if gap(shape.BoundBox, other.BoundBox) > 1e-6:
                excluded += 1
                continue
            try:
                if other.isNull() or not other.isValid() or not other.Solids:
                    raise RuntimeError('Solide d’entrée invalide')
                measurement = {'pair': [key, other_key], **measured_pair(shape, other)}
                proximity.append(measurement)
                if measurement['volume_mm3'] > 1e-4:
                    failures.append(measurement)
            except RuntimeError as error:
                failures.append({'pair': [key, other_key], 'error': str(error)})

    report = {'schema': 'cartographe.etude-corridors-main-paire.v1', 'environment': environment,
              'construction_sha256': sha(build_path), 'routes_sha256': sha(routes_path), 'script_sha256': sha(Path(__file__)),
              'scope': 'Pose nominale, P75 intact, deux parcours régénérés et paroi candidate. Aucun natif sauvegardé.',
              'routes': results, 'members': members, 'sleeve': {'interval_x_mm': [91, 99.5], 'length_mm': length,
                                                               'inner_radius_mm': inner_radius, 'wall_mm': outer_radius-inner_radius,
                                                               'axes_bords_mm': [[91,-37,163], [91,-28,172]]},
              'inclusion': inclusion, 'pairs_checked': len(checked), 'aabb_disjoint': excluded,
              'proximity': proximity, 'failures': failures, 'complete': True,
              'nominal_geometry_pass': not failures and
              all(item['outside_inner_mm3'] <= 1e-4 and abs(item['section_volume_mm3'] - nominal_volume) <= 1e-4 for item in inclusion)
              and all(item['recompute']['status'] == 'pass' and not item['geometry']['failures'] for item in results)}
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    print('MAIN paire', report['nominal_geometry_pass'], failures, flush=True)


if __name__ == '__main__':
    main(Path(sys.argv[1]))
    os._exit(0)
