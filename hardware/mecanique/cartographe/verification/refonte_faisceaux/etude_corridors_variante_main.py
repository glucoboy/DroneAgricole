"""Mesure en mémoire de quatre variantes du départ de F04_1 depuis le tronc MAIN."""

import hashlib
import json
import os
from pathlib import Path
import sys

verification = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(verification), str(verification / 'reconstruction_faisceaux')]
from autonomie_cao import App, COPY, Reader, gap, gui, measured_pair
from freecad_geometry import inspect_route, rebuild_cable_in_isolated_document


def main(out):
    routes_path = COPY / 'verification/routes_prototype.json'
    scene_path = COPY / 'verification/construction_prototype.json'
    source = next(r for r in json.loads(routes_path.read_text(encoding='utf-8'))['routes'] if r['id'] == 'F04_1')
    rows = json.loads(scene_path.read_text(encoding='utf-8'))['occurrences']
    reader = Reader(COPY)
    scene = [(r, reader.occurrence(r)) for r in rows if r['parent'].startswith('sous_assemblages/')
             and not ('/SA07_' in r['parent'] and r['occurrence'] == 'F04_1')]
    builder, environment = gui()
    doc = App.newDocument('VarianteMain')
    result = {'scope': 'Pose nominale, seuls deux points internes F04_1 changent. Aucun natif enregistré.',
              'route_source_sha256': hashlib.sha256(routes_path.read_bytes()).hexdigest(),
              'scene_sha256': hashlib.sha256(scene_path.read_bytes()).hexdigest(), 'environment': environment,
              'tested_occurrences_per_variant': len(scene), 'complete': False, 'variants': []}
    start_axis = App.Vector(*source['points_mm'][1]) - App.Vector(*source['points_mm'][0])
    end_axis = App.Vector(*source['points_mm'][-2]) - App.Vector(*source['points_mm'][-1])
    for trial in (102, 105, 108, 111):
        points = [list(p) for p in source['points_mm']]
        points[3][0] = points[4][0] = trial
        cable, wire = builder.make_native_cable(doc, None, f'F04_1_X{trial}', points,
                                               source['diametre_mm'], source['rayon_courbure_mm'])
        fresh = rebuild_cable_in_isolated_document(doc, cable)
        geometry = inspect_route(wire.Shape.Wires[0], minimum_radius_mm=source['rayon_courbure_mm'],
                                 start_position=points[0], end_position=points[-1],
                                 start_axis=list(start_axis), end_axis=list(end_axis))
        report = {'points_mm': points, 'baseline_length_mm': source['longueur_courbe_mm'], 'trial_x_mm': trial,
                  'recompute': fresh, 'route': geometry, 'pairs': [], 'aabb_disjoint': 0}
        for row, shape in scene:
            if gap(cable.Shape.BoundBox, shape.BoundBox) > 1e-6:
                report['aabb_disjoint'] += 1
                continue
            key = row['parent'] + '#' + row['occurrence']
            try:
                if shape.isNull() or not shape.isValid() or not shape.Solids:
                    raise RuntimeError('Solide d’entrée invalide')
                pair = measured_pair(cable.Shape, shape)
                report['pairs'].append({'id': key, **pair})
            except RuntimeError as error:
                report['pairs'].append({'id': key, 'error': str(error)})
        report['failures'] = [p for p in report['pairs'] if p.get('volume_mm3', 0) > 1e-4 or 'error' in p]
        result['variants'].append(report)
        out.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
        print(trial, report['route']['length_mm'], report['failures'], flush=True)
    result['complete'] = True
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main(Path(sys.argv[1]))
    os._exit(0)
