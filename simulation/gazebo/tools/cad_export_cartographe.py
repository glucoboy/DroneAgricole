"""FreeCAD export adapter: saved BREP -> visual meshes and geometry evidence.

No design, mass calculation, aerodynamics, native recompute or native save.
Run with the Python bundled with FreeCAD (Part and MeshPart required).
The existing audited saved-BREP reader owns link/placement interpretation.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

import FreeCAD as App
import Mesh
import MeshPart
import Part


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def bounds(box):
    return [box.XMin, box.YMin, box.ZMin, box.XMax, box.YMax, box.ZMax]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument('--linear-deflection-mm', type=float, default=0.5)
    parser.add_argument('--output-dir', type=Path, help='Nouveau dossier du modèle, dans le workspace')
    args = parser.parse_args()
    workspace = args.workspace.resolve()
    if not workspace.is_dir() or not (workspace / 'AGENTS.md').is_file():
        raise ValueError('Workspace racine absent ou sans AGENTS.md')
    if not 0.05 <= args.linear_deflection_mm <= 2.0:
        raise ValueError('Déflexion autorisée : 0,05..2 mm')
    base = workspace / 'hardware/mecanique/cartographe'
    out = args.output_dir.resolve() if args.output_dir else workspace / 'simulation/gazebo/models/cartographe'
    if not out.is_relative_to(workspace) or out == workspace:
        raise ValueError('Sortie hors du workspace refusée')
    evidence = out / 'geometry'
    meshes = out / 'meshes'
    evidence.mkdir(parents=True, exist_ok=True)
    meshes.mkdir(parents=True, exist_ok=True)
    native_manifest = base / 'manifest.json'
    bom_path = base / 'nomenclature_prototype.json'
    canonical = json.loads(native_manifest.read_text(encoding='utf-8-sig'))['prototype_cartographe']
    reader_path = base / 'verification/read_brep_prototype.py'
    spec = importlib.util.spec_from_file_location('saved_brep_reader', reader_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    reader = module.Reader(base)
    final = canonical['assemblage']
    parent_rows = [r for r in canonical['occurrences'] if r['parent'] == final]
    identity = [1., 0., 0., 0., 0., 1., 0., 0., 0., 0., 1., 0., 0., 0., 0., 1.]
    if len(parent_rows) != 7 or any(r['matrice'] != identity for r in parent_rows):
        raise ValueError('Configuration non supportée : sept sous-assemblages à pose identité requis')
    leaves = [r for r in canonical['occurrences'] if r['parent'] != final]
    keys = [(r['parent'], r['occurrence']) for r in leaves]
    if len(keys) != len(set(keys)):
        raise ValueError('Occurrence CAO dupliquée')
    declared = {r['fichier']: r['sha256'] for r in canonical['references'] + canonical['assemblages']}
    declared.update(canonical['sources_preservees'])
    for relative, expected in declared.items():
        if sha(base / relative) != expected:
            raise ValueError('Empreinte CAO différente du manifeste : ' + relative)
    before = {relative: sha(base / relative) for relative in declared}
    body = Mesh.Mesh()
    rotor_meshes = []
    occurrences = []
    errors = []
    invalid = []
    union_native = App.BoundBox()
    sub_boxes = {}
    for index, row in enumerate(leaves):
        print(f'[{index + 1}/{len(leaves)}] {row["occurrence"]}', flush=True) if index % 25 == 0 else None
        shape = reader.occurrence(row)
        if shape is None or shape.isNull():
            raise ValueError('Forme absente : ' + row['occurrence'])
        valid = shape.isValid()
        if not valid:
            invalid.append({'parent': row['parent'], 'occurrence': row['occurrence'], 'source': row['source']})
        mesh = MeshPart.meshFromShape(Shape=shape, LinearDeflection=args.linear_deflection_mm,
                                      AngularDeflection=0.35, Relative=False)
        if mesh.CountFacets == 0:
            raise ValueError('Maillage vide : ' + row['occurrence'])
        # OCCT may use inflated B-spline control poles before triangulation.
        # optimalBoundingBox explicitly excludes that coarse estimate.
        exact = shape.optimalBoundingBox(False, False)
        union_native.add(exact)
        sub_boxes.setdefault(row['parent'], App.BoundBox()).add(exact)
        mesh_bbox_mm = bounds(mesh.BoundBox)
        exact_bbox_mm = bounds(exact)
        error = max(abs(x-y) for x, y in zip(mesh_bbox_mm, exact_bbox_mm))
        if error > args.linear_deflection_mm + 0.1:
            errors.append({'occurrence': row['occurrence'], 'bbox_error_mm': error})
        occurrences.append({'parent': row['parent'], 'occurrence': row['occurrence'],
                            'source': row['source'], 'source_object': row['objet_source'],
                            'bom_ids': row['bom_ids'], 'cad_pose_mm': row['matrice'],
                            'native_bbox_mm': exact_bbox_mm, 'mesh_bbox_mm': mesh_bbox_mm,
                            'bbox_error_mm': error, 'facets': mesh.CountFacets, 'native_valid': valid})
        if row['occurrence'].startswith('Helice_'):
            origin = [row['matrice'][3], row['matrice'][7], row['matrice'][11]]
            transform = App.Matrix()
            transform.move(App.Vector(*[-x for x in origin]))
            mesh.transform(transform)
            rotor_meshes.append((row, origin, mesh))
        else:
            body.addMesh(mesh)
    if errors:
        raise ValueError('Écart géométrique de maillage hors seuil : ' + json.dumps(errors))
    if len(rotor_meshes) != 4:
        raise ValueError('Quatre rotors distincts requis')
    scale = App.Matrix()
    scale.scale(0.001, 0.001, 0.001)
    body.transform(scale)
    body_path = meshes / 'cartographe_body.stl'
    body.write(str(body_path))
    rotor_rows = []
    for row, origin, mesh in rotor_meshes:
        mesh.transform(scale)
        number = int(row['occurrence'].split('_')[-1])
        path = meshes / f'rotor_{number}.stl'
        mesh.write(str(path))
        rotor_rows.append({'cad_occurrence': row['occurrence'], 'position_m': [x * .001 for x in origin],
                           'axis_flu': [0, 0, 1], 'cad_label_rotation': 'CCW' if 'CCW' in row['source'] else 'CW',
                           'rotation_label_view': 'hypothèse vue depuis +Z, vérifier le lot réel',
                           'mesh': path.relative_to(out).as_posix(), 'sha256': sha(path),
                           'facets': mesh.CountFacets, 'local_bbox_m': bounds(mesh.BoundBox),
                           'mesh_units': 'm', 'cad_envelope_diameter_m': .3937,
                           'nominal_candidate_diameter_m': .381,
                           'physical_geometry_validated': False})
    for relative, expected in before.items():
        if sha(base / relative) != expected:
            raise ValueError('Source modifiée pendant export : ' + relative)
    dependencies = set(declared)
    dependencies.update(path.relative_to(base).as_posix() for path in reader.documents)
    dependency_hashes = {relative: sha(base / relative) for relative in sorted(dependencies)}
    final_box = next(r['bbox_mm'] for r in canonical['assemblages'] if r['fichier'] == final)
    bbox_difference = max(abs(a-b) for a, b in zip(bounds(union_native), final_box))
    if bbox_difference > 1.0:
        raise ValueError('Enveloppe finale différente du manifeste de plus de 1 mm')
    result = {
        'schema_version': 1, 'test_id': 'T-CARTO-GZ-01', 'status': 'Implémenté',
        'physical_fidelity': 'À valider', 'finalized': True,
        'created_utc': datetime.now(timezone.utc).isoformat(),
        'configuration': 'prototype_cartographe',
        'sources': {'cad_manifest': str(native_manifest.relative_to(workspace)).replace('\\', '/'),
                    'cad_manifest_sha256': sha(native_manifest), 'bom_sha256': sha(bom_path),
                    'export_adapter_sha256': sha(__file__), 'saved_brep_reader_sha256': sha(reader_path),
                    'dependencies_relative_to_cad_directory': dependency_hashes},
        'versions': {'freecad': App.Version(), 'occt': Part.OCC_VERSION, 'python': sys.version},
        'frame': {'source': 'CAO mm', 'target': 'Gazebo FLU m', 'scale': .001,
                  'rotation_row_major': [1,0,0,0,1,0,0,0,1],
                  'origin': 'Origine CAO conservée, distincte du centre de masse',
                  'front': '+X CAO conventionnel pour SITL ; cap physique À valider',
                  'px4_frd_from_flu': [1,0,0,0,-1,0,0,0,-1]},
        'counts': {'native_references': len(canonical['references']), 'native_occurrences': len(canonical['occurrences']),
                   'assembly_links_excluded_from_leaf_count': len(parent_rows), 'leaf_occurrences': len(leaves),
                   'body_leaf_occurrences': len(leaves)-4, 'rotors': 4, 'source_dependencies': len(dependencies)},
        'geometry': {'native_bbox_mm': bounds(union_native), 'published_bbox_mm': final_box,
                     'published_bbox_max_error_mm': bbox_difference,
                     'linear_deflection_mm': args.linear_deflection_mm, 'angular_deflection_rad': .35,
                     'body_mesh': {'path': body_path.relative_to(out).as_posix(), 'sha256': sha(body_path),
                                   'facets': body.CountFacets, 'bbox_m': bounds(body.BoundBox)},
                     'rotors': sorted(rotor_rows, key=lambda x: x['cad_occurrence']),
                     'subassembly_bbox_m': {k:[x*.001 for x in bounds(b)] for k,b in sub_boxes.items()}},
        'checks': {'source_hashes_match_manifest': True, 'sources_unchanged': True,
                   'no_native_open_recompute_save': True, 'duplicate_leaf_keys': 0,
                   'all_meshes_nonempty': True, 'mesh_bbox_errors_within_deflection_plus_point_one_mm': True,
                   'invalid_source_shapes_tessellated_for_visual_only': invalid},
        'limits': ['Visuel uniquement ; aucune masse/densité/inertie déduite des maillages.',
                   'Le profil CAO des hélices reste une enveloppe provisoire Ø393,7 mm, différente du nominal candidat Ø381 mm.',
                   'Les formes invalides OCCT, notamment la source Basler, sont tessellées sans réparation ni sauvegarde.',
                   'Les surfaces détaillées, tolérances, pales et fixation de lot restent À valider.'],
        'occurrences': occurrences}
    output_path = evidence / 'geometry_manifest.json'
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'finalized': True, 'evidence': str(output_path), 'body_facets': body.CountFacets,
                      'dependencies':len(dependencies), 'invalid_sources':len(invalid)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
