"""Project saved CAD bounding envelopes to conservative SDF box primitives.

Infrastructure adapter, no flight/energy logic. No native document is opened.
These boxes target flat-ground contact and coarse noncontact obstacles only.
"""
import hashlib
import argparse
import importlib.util
import itertools
import json
from datetime import datetime, timezone
from pathlib import Path

import FreeCAD as App
import Part
from cad_export_cartographe import sealed_reader

ROOT = Path(__file__).resolve().parents[3]
CAD = ROOT / 'hardware/mecanique/cartographe'
OUT = ROOT / 'simulation/gazebo/models/cartographe/geometry'
GEOMETRY = OUT / 'geometry_manifest.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    global ROOT, CAD, OUT, GEOMETRY
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', type=Path, default=ROOT)
    parser.add_argument('--output-dir', type=Path)
    args = parser.parse_args()
    ROOT = args.workspace.resolve()
    CAD = ROOT / 'hardware/mecanique/cartographe'
    model = args.output_dir.resolve() if args.output_dir else ROOT / 'simulation/gazebo/models/cartographe'
    if not model.is_relative_to(ROOT) or model == ROOT:
        raise ValueError('Sortie hors du workspace refusée')
    OUT = model / 'geometry'
    GEOMETRY = OUT / 'geometry_manifest.json'
    geometry = json.loads(GEOMETRY.read_text(encoding='utf-8-sig'))
    if not geometry['finalized'] or not geometry['checks']['sources_unchanged']:
        raise ValueError('Export géométrique non finalisé')
    sources = geometry['sources']
    if sha(CAD / 'manifest.json') != sources['cad_manifest_sha256']:
        raise ValueError('stale CAD manifest')
    canonical = json.loads((CAD / 'manifest.json').read_text(encoding='utf-8-sig'))['prototype_cartographe']
    spec = importlib.util.spec_from_file_location('reader', CAD / 'verification/read_brep_prototype.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    reader = sealed_reader(module.Reader, CAD, sources['dependencies_relative_to_cad_directory'])
    # Eight rubber contact pads, two legs, four arm/motor assemblies and centre.
    selected = [f'OEM_Part__Feature{i:03d}' for i in (10,11,12,13,26,27,28,29,1,17)]
    selected += ['OEM_X650_ZHEDIE_JIBI_2024_ASM'+suffix for suffix in ('','001','002','003')]
    selected += ['OEM__07190001_ASM']
    boxes = []
    for name in selected:
        measured = next(r for r in geometry['occurrences'] if r['occurrence'] == name)
        original = next(r for r in canonical['occurrences'] if r['occurrence'] == name)
        shape = reader.occurrence(original)
        bbox = measured['native_bbox_mm']
        corners = itertools.product(*[(bbox[i],bbox[i+3]) for i in range(3)])
        sampled_excess = max(Part.Vertex(App.Vector(*p)).distToShape(shape)[0] for p in corners) * .001
        boxes.append({'name': name, 'type': 'box', 'source_occurrence': name,
                      'centre_m': [(bbox[i]+bbox[i+3])*.0005 for i in range(3)],
                      'size_m': [(bbox[i+3]-bbox[i])*.001 for i in range(3)],
                      'bbox_m': [x*.001 for x in bbox], 'native_bbox_error_m': 0.,
                      'corner_distance_to_source_max_m': sampled_excess,
                      'is_ground_contact_pad': name in [f'OEM_Part__Feature{i:03d}' for i in (10,11,12,13,26,27,28,29)]})
    for source, bbox in geometry['geometry']['subassembly_bbox_m'].items():
        if 'Structure' in source:
            continue
        boxes.append({'name': Path(source).stem, 'type':'box', 'source_subassembly':source,
                      'centre_m':[(bbox[i]+bbox[i+3])*.5 for i in range(3)],
                      'size_m':[bbox[i+3]-bbox[i] for i in range(3)], 'bbox_m':bbox,
                      'native_bbox_error_m':0., 'corner_distance_to_source_max_m':None,
                      'is_ground_contact_pad':False})
    lowest = min(b['bbox_m'][2] for b in boxes)
    source_lowest = geometry['geometry']['native_bbox_mm'][2]*.001
    if abs(lowest-source_lowest) > 1e-8:
        raise ValueError('Contact au sol incohérent')
    result = {'schema_version':1, 'test_id':'T-CARTO-GZ-01', 'status':'Implémenté',
              'physical_fidelity':'À valider', 'finalized':True,
              'created_utc':datetime.now(timezone.utc).isoformat(),
              'geometry_manifest_sha256':sha(GEOMETRY), 'adapter_sha256':sha(Path(__file__)),
              'frame':'Gazebo FLU m, origine CAO', 'purpose':'Contact sur sol plat pour la première campagne SITL',
              'boxes':boxes, 'body_collision_count':len(boxes),
              'rotor_collisions':[{'cad_occurrence':r['cad_occurrence'], 'type':'cylinder',
                                   'position_m':r['position_m'], 'radius_m':.19685, 'length_m':.012,
                                   'geometry':'enveloppe balayée provisoire, pas une pale physique'}
                                  for r in geometry['geometry']['rotors']],
              'checks':{'ground_contact_pad_count':8, 'lowest_collision_z_m':lowest,
                        'lowest_native_z_m':source_lowest, 'ground_contact_height_error_m':abs(lowest-source_lowest),
                        'selected_box_native_bbox_errors_m':0., 'all_box_sizes_positive':all(all(x>0 for x in b['size_m']) for b in boxes)},
              'limits':['Les AABB englobent du vide et donnent des contacts anticipés sur obstacle ou forte inclinaison.',
                        'Les distances aux huit coins sont un échantillon, pas une erreur de Hausdorff globale.',
                        'Les bras AABB sont volontairement conservateurs ; ni évitement fin ni choc ni déformation évalués.',
                        'Les six enveloppes équipements ne représentent pas chaque câble ni chaque fixation.',
                        'Aucune masse, densité ou inertie automatique issue de ces collisions.',
                        'Les disques de rotor conservent Ø393,7 mm CAO par prudence géométrique, nominal candidat381 mm distinct.']}
    (OUT/'collision_model.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'finalized':True,'boxes':len(boxes),'ground_height_error_m':abs(lowest-source_lowest)}))


if __name__ == '__main__':
    main()
