"""Write the B.1 fixture authority for review after preparing native sources."""

import argparse
import math
from pathlib import Path

from replay_v3_b1 import ROOT, digest, load, write


def pose(x, y, z, angle=0):
    radians = math.radians(angle) / 2
    return dict(translation_mm=[x, y, z], rotation_xyzw=[0, 0, math.sin(radians), math.cos(radians)])


def action(identifier, operation, subject, params, before, after, affected, limits, graph_op, target):
    return dict(id=identifier, operation=operation, occurrence=subject, effect={'fixture_case': identifier},
                parameters=params, expected_before=before, expected_after=after, affected=affected,
                domain_limits=limits, graph_operation=graph_op, graph_target=target)


def describe(destination, logical_directory):
    c4 = ROOT / 'docs/electromechanical_v3/bench_b1_c4'
    profile = load(c4 / 'profile.json')
    graph = load(c4 / 'graph.json')
    profile.update(model_id='xlink-workholding-b1', source=f'{logical_directory}/model',
                   graph=f'{logical_directory}/graph.json')
    profile['dependencies'] = {path.relative_to(destination / 'model').as_posix(): digest(path)
                               for path in sorted((destination / 'model').rglob('*.FCStd'))}
    profile['constraints']['SUPPORT_ANCHOR'] = {'applicable': True, 'evidence': 'model.validation.supports'}
    profile['constraints']['SERVICE']['scope'] = 'Extraction TTL synthétique et accès aux nouvelles fixations.'
    model = profile['model']
    additional = {
        'carrier': ('Workholding/Carrier', 'STRUCTURE'),
        'anchor-before': ('Workholding/AnchorBefore', 'ANCHOR'),
        'anchor-relocate': ('Workholding/AnchorRelocate', 'ANCHOR'),
        'anchor-new': ('Workholding/AnchorNew', 'ANCHOR'),
        'plate-existing': ('Workholding/ExistingPlate', 'SUPPORT'),
        'stud-existing': ('Workholding/ExistingStud', 'FASTENER'),
        'plate-new': ('Workholding/NewPlate', 'SUPPORT'),
        'stud-new': ('Workholding/NewStud', 'FASTENER'),
        'payload': ('FixtureRig/Payload', 'DEVICE'),
        'sibling': ('FixtureRig/Sibling', 'DEVICE'),
    }
    model['occurrences'].update({key: value[0] for key, value in additional.items()})
    model['occurrences']['cordon'] = 'HarnessInventory/Cable'
    validation = model['validation']
    validation['routes']['cordon']['conductor_sections_mm2'] = [0.2] * 4
    validation['supports'] = {
        'plate-existing': dict(anchor='anchor-before', carrier='carrier', retains=['cordon'],
                               min_contact_area_mm2=55, min_fasteners=1, retention_max_gap_mm=0.001),
        'plate-new': dict(anchor='anchor-new', carrier='carrier', retains=['cordon'], created_only=True,
                          min_contact_area_mm2=61, min_fasteners=1, retention_max_gap_mm=0.001),
    }
    validation['allowed_interferences'] = [
        {'parts': ['carrier', stud], 'max_volume_mm3': 2, 'reason': 'Engagement du goujon dans le porteur.'}
        for stud in ('stud-existing', 'stud-new')
    ]
    for anchor, x, controlling_action in [('anchor-before', 2, None), ('anchor-relocate', 2, 'relocate'),
                                          ('anchor-new', 4, 'create')]:
        validation['service'].append(dict(anchor=anchor, offset_local_mm=[x, 1.2, 3], radius_mm=0.4,
                                          stroke_mm=7, obstacles=['cordon', 'payload'], clearance_mm=0.2,
                                          required_action=controlling_action))
    actions = []
    for identifier, frame, goal, expected in [
        ('move-root', 'ROOT', pose(78, 42, 7, 135), pose(78, 42, 7, 135)),
        ('move-parent', 'PARENT', pose(12, -3, 2, -30), pose(78, 45, 8, 60)),
        ('collision', 'ROOT', pose(75, 55, 6, 90), pose(75, 55, 6, 90)),
    ]:
        actions.append(action(identifier, 'REPOSITION_DEVICE', 'payload', dict(frame=frame, placement=goal),
                              {'placement': pose(75, 41, 7, 90)}, {'placement': expected},
                              ['payload', 'sibling'], {'pose_autorisee': goal, 'frame': frame}, 'MOVE', 'payload'))
    points = [[14, 0, 0], [27, 0, 0], [34, 9, 0], [46, 9, 0], [55, 0, 0], [86, 0, 0]]
    for identifier, path, radius in [('route', points, 5), ('radius-low', points, 3.5),
                                     ('duplicates', [points[0], *points], 5)]:
        params = dict(frame='ROOT', points_mm=path, diameter_mm=4, bend_radius_mm=radius, minimum_radius_mm=5,
                      conductor_sections_mm2=[0.2] * 4, start_axis=[1, 0, 0], end_axis=[-1, 0, 0])
        actions.append(action(identifier, 'REROUTE_HARNESS', 'cordon', params,
                              {'points_mm': [points[0], points[-1]]}, {'points_mm': path},
                              ['cordon', 'route-axis', 'c1', 'c2', 'c3', 'c4'],
                              {'minimum_radius_mm': 5, 'diameter_mm': 4}, 'FRAME', 'port-b'))
    actions.append(action('relocate', 'RELOCATE_SUPPORT', 'plate-existing',
                          dict(anchor='anchor-relocate', carrier='carrier', retains=['cordon'],
                               fasteners=['stud-existing'], placement=pose(0, 0, 0)),
                          {'placement': pose(60, -4, -5)}, {'placement': pose(68, -4, -5)},
                          ['plate-existing', 'stud-existing', 'anchor-before', 'anchor-relocate', 'carrier', 'cordon'],
                          {'anchors': ['anchor-relocate']}, 'RETENTION', 'plate-existing'))
    for identifier, offset in [('create', 0), ('floating', 0.3)]:
        params = dict(anchor='anchor-new', carrier='carrier', support='plate-new', retains=['cordon'],
                      placement=pose(0, 0, offset), size_mm=[8, 8, 3],
                      fasteners=[dict(id='stud-new', center_mm=[4, 1.2], hole_diameter_mm=1.5,
                                      diameter_mm=1.5, embed_mm=1)])
        actions.append(action(identifier, 'CREATE_SUPPORT', 'anchor-new', params, {'exists': False},
                              {'placement': pose(78, -4, -5 + offset)},
                              ['plate-new', 'stud-new', 'anchor-new', 'carrier', 'cordon'],
                              {'anchor': 'anchor-new', 'max_size_mm': [8, 8, 3]}, 'RETENTION', 'anchor-new'))
    profile['actions'] = actions
    profile['compositions'] = [
        ['move-root', 'route', 'relocate', 'create'], ['move-parent', 'route', 'relocate', 'create'],
        ['collision'], ['radius-low'], ['move-root', 'duplicates'], ['floating'],
    ]
    profile['replay'] = {str(index): {'status': 'FAIL', 'construction': 'FAIL' if index == 5 else 'PASS'}
                         for index in range(3, 7)}
    graph['configuration'] = profile['model_id']
    graph['sources']['b1_native'] = {'path': f"{profile['source']}/{profile['entry']}",
                                      'sha256': profile['dependencies'][profile['entry']]}
    evidence = dict(state='DOCUMENTED', source='b1_native', locator='Occurrence ou définition native sur banc',
                    scope='banc B.1 numérique', unit=None, reception='NOT_RUN')
    for key, (_, kind) in additional.items():
        graph['nodes'].append(dict(id=key, kind=kind, version=1, evidence=evidence, claims=[]))
    controls = [row['id'] for row in graph['nodes'] if row['kind'] == 'CONTROL']
    graph['nodes'].append(dict(id='b1-anchor-check', kind='CONTROL', version=1, evidence=evidence, claims=[]))
    controls.append('b1-anchor-check')
    for subject, dependencies in {
        'payload': ['sibling', *controls],
        'plate-existing': ['stud-existing', 'anchor-before', 'anchor-relocate', 'carrier', 'cordon', *controls],
        'anchor-new': ['plate-new', 'stud-new', 'carrier', 'cordon', *controls],
    }.items():
        graph['edges'].extend(dict(id=f'b1-{subject}-{target}', kind='DEPENDS_ON', impact='FORWARD',
                                   **{'from': subject, 'to': target}, evidence=evidence) for target in dependencies)
    write(destination / 'graph.json', graph)
    profile['graph_sha256'] = digest(destination / 'graph.json')
    write(destination / 'profile.json', profile)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination', type=Path)
    args = parser.parse_args()
    destination = args.destination.resolve()
    if not destination.is_relative_to(ROOT / 'docs/electromechanical_v3'):
        parser.error('Choisir le dossier de référence FreeCAD sous docs/electromechanical_v3')
    describe(destination, destination.relative_to(ROOT).as_posix())
