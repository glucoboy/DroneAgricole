"""Adaptateur de mesure FreeCAD V3 A2, sur copies XLink et sans sauvegarde."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys

from .freecad import PROJECT, guard
from .v3_native import (
    MATRIX_TOLERANCE, observe_axis, observe_box, serialized_dependencies,
    verify_occurrence_placements,
)
from .xlink_native import check_files, collect, read, reopen


REFERENCE = 'hardware/mecanique/cartographe'
ENTRY = 'assemblages/Prototype_Cartographe.FCStd'
A_RECEIPT = 'docs/verification/v3/a/native_receipt.json'
GO3B_MANIFEST = 'docs/verification/v21_go3b_manifest.json'
GO3B_REVIEW = 'docs/verification/v21_go3b/interfaces_review.json'
SCRIPT = 'electromechanical_engine/v3_a2_native.py'
PREFIX = f'{ENTRY}#Ensemble/'
CASES = ('reference', 'H03-A', 'H03-B', 'consolidee')
PORTS = {'F40': ('ORCH_BornierTTL', 'XMax'), 'F41': ('ORCH_USB_B', 'XMin')}
GROUPS = {
    'SA02_Prototype_Batterie': ('Pack6S20Ah', 'BMS', 'PlateauBMS', 'Semelle'),
    'SA03_Prototype_Energie': ('UART_isole', 'PDB', 'Isolation', 'PM08'),
    'SA05_Prototype_Avionique': ('Interface', 'Holybro6XOrin'),
    'SA07_Prototype_Faisceaux': ('P72_Guide', 'P73_Guide', 'P75_Cadre', 'F31', 'F35', 'F40', 'F41'),
}
CANDIDATE_SURFACES = ('Isolation', 'Interface', 'Semelle', 'P72_Guide', 'P73_Guide')
ARCHIVE_FALLBACK = '.runtime/v21-go3b'


def footprint(hashes):
    payload = json.dumps(hashes, sort_keys=True, ensure_ascii=True, separators=(',', ':'))
    return hashlib.sha256(payload.encode('ascii')).hexdigest()


def repository_path(path):
    return path.relative_to(PROJECT).as_posix()


def locate(case):
    if case == 'reference':
        receipt = read(PROJECT / A_RECEIPT)
        return [PROJECT / REFERENCE], receipt['inputs_sha256'], A_RECEIPT
    archive = read(PROJECT / GO3B_MANIFEST)['archives'][case]
    roots = [PROJECT / archive['root'], PROJECT / ARCHIVE_FALLBACK / case / 'cad']
    return roots, archive['native_sha256'], GO3B_MANIFEST


def expected_inputs(case, root, expected):
    extras = [name for name in expected if not name.lower().endswith('.fcstd')]
    measured = {
        path.relative_to(root).as_posix(): guard.sha256(path)
        for path in guard.dependencies(root, [ENTRY, *extras])
    }
    if measured != expected:
        changed = sorted(name for name in measured.keys() | expected.keys()
                         if measured.get(name) != expected.get(name))
        raise ValueError(f'{case} : la fermeture diffère de son reçu : {changed}')
    return extras


def source_inputs(case):
    roots, expected, authority = locate(case)
    failures = []
    for root in roots:
        if not (root / ENTRY).is_file():
            failures.append(f'{repository_path(root)} : assemblage absent')
            continue
        try:
            extras = expected_inputs(case, root, expected)
        except (OSError, ValueError) as error:
            failures.append(str(error))
        else:
            return root, expected, authority, extras
    if case == 'reference':
        raise ValueError(' ; '.join(failures))
    return None, expected, authority, failures


def summaries(cad, case):
    from . import freecad_worker as native

    app, part, geometry = native.App, native.Part, native.geometry
    receipt = read(cad / 'experiment.json')
    hashes = receipt['inputs_sha256']
    native_files = [name for name in hashes if name.lower().endswith('.fcstd')]
    _, _, unresolved_xml, _, _ = serialized_dependencies(cad, native_files)
    doc, reopened = reopen(cad, receipt, False)
    if unresolved_xml or reopened['status'] != 'PASS':
        raise ValueError(f'Fermeture {case} incomplète : {unresolved_xml}, {reopened["broken_links"]}, '
                         f'{reopened["invalid_objects"]}')
    records, solids, objects = collect(doc, cad, hashes)
    verify_occurrence_placements(doc, records, app)
    positions, shapes = {}, {}

    def position(path):
        row = records[path]
        check = row['placement_check']
        if check['status'] != 'PASS':
            raise ValueError(f'Pose {path} : {check}')
        return {key: row[key] for key in ('object', 'definition', 'document_sha256', 'definition_sha256',
                                          'local_matrix', 'matrix', 'independent_matrix', 'visible',
                                          'placement_check')}

    def solid(path):
        if path in solids:
            return solids[path]
        members = [shape for key, shape in solids.items() if key.startswith(path + '/')]
        if not members:
            raise ValueError(f'Solide BRep absent : {path}')
        return members[0] if len(members) == 1 else part.makeCompound(members)

    for group, names in GROUPS.items():
        for name in names:
            positions[name] = f'{PREFIX}{group}/{name}'
    support = f'{PREFIX}SA07_Prototype_Faisceaux/ASSUMED_ServiceGO3B'
    if support in records:
        positions['ASSUMED_ServiceGO3B'] = support

    dimensions = {}
    for name, path in positions.items():
        shape = solid(path)
        if shape.isNull() or not shape.Solids or not shape.isValid():
            raise ValueError(f'BRep invalide : {path}')
        shapes[name] = shape
        dimensions[name] = {
            'occurrence': path, **position(path), 'bounds_mm': native.bounds(shape),
            'volume_mm3': shape.Volume, 'solids': len(shape.Solids),
            'brep_sha256': geometry.shape_sha256(shape),
            'evidence_class': 'ASSUMED' if name == 'ASSUMED_ServiceGO3B' else 'MEASURED',
            'scope': 'BRep nominal dans la référence CAO ou le candidat historique.',
        }

    ports = {}
    iso_path = positions['UART_isole']
    for harness, (feature, face) in PORTS.items():
        proxy_path = f'{iso_path}/{feature}'
        proxy = observe_box(records[proxy_path], objects[proxy_path], app)
        axis_path = f'{positions[harness]}/Cable'
        position(axis_path)
        axis = observe_axis(records[axis_path], objects[axis_path], app, native.builder, geometry)
        face_vector = app.Vector(*proxy['faces'][face]['global_mm'])
        distances = [(app.Vector(*end) - face_vector).Length for end in axis['endpoints_mm']]
        nearest = min(range(len(distances)), key=distances.__getitem__)
        angle = app.Vector(*axis['outward_directions'][nearest]).getAngle(
            app.Vector(*proxy['faces'][face]['outward_global']))
        ports[harness] = {
            'face_occurrence': proxy_path, 'face_pose': position(proxy_path),
            'face_dimensions_mm': proxy['dimensions_mm'], 'face': face,
            'face_frame_proxy': proxy['faces'][face], 'face_evidence_class': 'ASSUMED',
            'axis_occurrence': axis_path, 'axis_pose': position(axis_path),
            'axis_ends_mm': axis['endpoints_mm'], 'axis_outward_global': axis['outward_directions'],
            'axis_length_mm': axis['length_mm'], 'nearest_axis_end': nearest,
            'axis_radius_observed_mm': axis['minimum_radius_mm'],
            'axis_radius_evidence': axis['radius_evidence'],
            'nearest_axis_end_distance_mm': distances[nearest],
            'proxy_to_axis_angle_deg': math.degrees(angle),
            'mating_frame': None, 'wire_exit_frame': None, 'tool_envelope': None,
            'scope': 'Face du volume de réservation et axe sauvegardé. Accouplement non prouvé.',
        }

    def compare(left, right):
        a, b = shapes[left], shapes[right]
        report = geometry.inspect_pair(a, b, left, right)
        if report['unknowns']:
            raise ValueError(f'Comparaison BRep incomplète : {report}')
        return {key: report[key] for key in ('intersection_volume_mm3', 'clearance_mm')}

    pairs = []
    if case == 'reference':
        pairs += [('P72_Guide', 'P73_Guide')]
        for guide in ('P72_Guide', 'P73_Guide'):
            pairs += [(guide, obstacle) for obstacle in
                      ('PDB', 'Isolation', 'Interface', 'Semelle', 'Pack6S20Ah', 'F31', 'F35', 'F40', 'F41')]
        pairs += [('UART_isole', obstacle) for obstacle in
                  ('Isolation', 'Interface', 'PDB', 'P72_Guide', 'P73_Guide', 'Pack6S20Ah', 'F31', 'F35')]
    if 'ASSUMED_ServiceGO3B' in positions:
        pairs += [('ASSUMED_ServiceGO3B', obstacle) for obstacle in
                  ('UART_isole', 'P72_Guide', 'P73_Guide', 'Interface', 'Isolation', 'P75_Cadre', 'PDB')]
        pairs += [('UART_isole', 'P72_Guide'), ('F40', 'P72_Guide')]
    observations = {f'{left}/{right}': compare(left, right) for left, right in pairs}

    surfaces = {}
    for name in CANDIDATE_SURFACES if case == 'reference' else ():
        for sign in (1, -1):
            candidates = []
            for index, face in enumerate(shapes[name].Faces, 1):
                if not isinstance(face.Surface, part.Plane):
                    continue
                u0, u1, v0, v1 = face.ParameterRange
                normal = face.normalAt((u0 + u1) / 2, (v0 + v1) / 2)
                if normal.z * sign < 1 - MATRIX_TOLERANCE:
                    continue
                candidates.append((face.Area, index, face, normal))
            candidates.sort(key=lambda item: (-item[0], item[1]))
            surfaces[f"{name}/{'Z+' if sign > 0 else 'Z-'}"] = [
                {'face_in_measured_brep': f'Face{index}', 'area_mm2': area,
                 'center_mm': list(face.CenterOfMass), 'normal_global': list(normal),
                 'bounds_mm': native.bounds(face)}
                for area, index, face, normal in candidates[:3]
            ]

    features = {}
    primitive_sets = {
        'P72_Guide': ('PatteP60', 'PatteP64', 'PatteP66'),
        'P73_Guide': ('PatteP60', 'PatteP64', 'PatteP66'),
        'UART_isole': ('ORCH_PlatineFixation', 'ORCH_ReserveLumiere_0', 'ORCH_ReserveLumiere_1',
                       'ORCH_ReserveLumiere_2', 'ORCH_ReserveLumiere_3'),
    }
    if case == 'reference':
        # Les outils de découpe localisent les perçages potentiels sans
        # accorder d'autorité aux surfaces ni qualifier la fixation.
        for name in ('Isolation', 'Interface', 'Semelle'):
            prefix = positions[name] + '/'
            primitive_sets[name] = [path[len(prefix):] for path in records
                                    if path.startswith(prefix + 'Percage')]
    for name, suffixes in primitive_sets.items() if case == 'reference' else ():
        for suffix in suffixes:
            path = f'{positions[name]}/{suffix}'
            shape = objects[path].Shape.copy()
            record = position(path)
            local = objects[path].Placement.inverse().toMatrix()
            world = app.Matrix()
            world.A = tuple(record['matrix'])
            global_shape = shape.transformShape(world.multiply(local), True, True)
            features[f'{name}/{suffix}'] = {
                'occurrence': path, **record, 'bounds_mm': native.bounds(global_shape),
                'brep_sha256': geometry.shape_sha256(global_shape), 'evidence_class': 'ASSUMED',
                'scope': 'Primitive de construction masquée. Fixation physique et tenue à établir.',
            }

    for key in ('BMS', 'Holybro6XOrin'):
        features[key] = {
            'features_in_occurrence': [records[path]['definition'] for path in records
                                       if path.startswith(positions[key] + '/')],
            'validated_mating_frame': None,
        }

    if check_files(cad, receipt) != hashes:
        raise ValueError(f'Octets modifiés après les mesures : {case}')
    return {
        'status': 'MEASURED', 'recompute_ok': reopened['recompute_ok'],
        'loaded_documents': len(reopened['documents']),
        'completed_partial_documents': reopened['completed_partial_documents'],
        'broken_native_links': reopened['broken_links'], 'broken_serialized_links': unresolved_xml,
        'invalid_objects': reopened['invalid_objects'], 'source_unchanged': True,
        'copy_unchanged': True, 'save_performed': False, 'environment': reopened['environment'],
        'occurrences': dimensions, 'interfaces': ports, 'brep_pairs': observations,
        'surface_candidates': surfaces, 'construction_features': features,
    }


def observations(case, source, expected, authority, details, work, python):
    input_receipt = {'authority_path': authority, 'authority_sha256': guard.sha256(PROJECT / authority),
                     'verified_inputs_count': len(expected), 'closure_map_sha256': footprint(expected),
                     'expected_root_sha256': expected[ENTRY]}
    if source is None:
        return {'status': 'NOT_RUN', 'reasons': details, 'required_inputs': input_receipt}
    cad = work / case / 'cad'
    staged = guard.stage(source, ENTRY, cad, details, {'extras': details})
    if staged['inputs_sha256'] != expected:
        raise ValueError(f'Copie différente des entrées vérifiées : {case}')
    # La fermeture lue est une copie ordinaire et devient en lecture seule avant ouverture.
    for name in expected:
        (cad / name).chmod(0o444)
    result_path = cad.parent / 'native.json'
    with (cad.parent / 'worker.log').open('wb') as log:
        result = subprocess.run(
            [str(python), '-B', '-m', 'electromechanical_engine.v3_a2_native', '--worker',
             case, str(cad), str(result_path)], check=False, cwd=PROJECT, stdout=log,
            stderr=subprocess.STDOUT, timeout=240,
            env=dict(os.environ, QT_QPA_PLATFORM='offscreen', PYTHONUTF8='1'),
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    if result.returncode or not result_path.is_file():
        raise RuntimeError(f'{case} sans résultat finalisé : {cad.parent / "worker.log"}')
    report = read(result_path)
    if report.get('status') != 'MEASURED':
        raise ValueError(f'Rapport natif non finalisé : {case}')
    print(f'{case} : {report["loaded_documents"]} natifs contrôlés', flush=True)
    input_receipt.update(source_root=repository_path(source), copy_root=repository_path(cad),
                         receipt=repository_path(cad / 'experiment.json'),
                         worker_output_sha256=guard.sha256(result_path),
                         worker_log_sha256=guard.sha256(cad.parent / 'worker.log'))
    return {'inputs': input_receipt, **report}


def main():
    if len(sys.argv) == 5 and sys.argv[1] == '--worker':
        case, cad, output = sys.argv[2:]
        cad = guard.inside(PROJECT / '.runtime', cad)
        result = summaries(cad, case)
        Path(output).write_text(json.dumps(result, ensure_ascii=False, allow_nan=False) + '\n', encoding='utf-8')
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(0)

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--freecad-python', type=Path, required=True)
    parser.add_argument('--work', type=Path, required=True)
    options = parser.parse_args()
    work = guard.inside(PROJECT / '.runtime', options.work)
    work.mkdir(parents=True, exist_ok=False)
    report = {case: observations(case, *source_inputs(case), work, options.freecad_python.resolve(strict=True))
              for case in CASES}
    (work / 'measurements.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
