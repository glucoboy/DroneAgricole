"""Adaptateur XLink V3-A. Toutes les ouvertures FreeCAD portent sur une copie."""

from __future__ import annotations

import argparse
from collections import Counter
from graphlib import CycleError, TopologicalSorter
import importlib.metadata
import json
import math
import os
from pathlib import Path, PureWindowsPath
import subprocess
import sys
import traceback
from xml.etree import ElementTree
from zipfile import ZipFile

from .freecad import PROJECT, guard
from .xlink_native import check_files, collect, publish, read, reopen, route_measurement


SCHEMA = 'v3.native/1'
LINKS = {'App::Link', 'App::LinkElement'}
MATRIX_TOLERANCE = 1e-7


def serialized_dependencies(root, native_paths):
    """Conserver la propriété d'origine et le chemin relatif réellement sérialisé."""
    objects, references, embedded_assets = {}, [], []
    document_graph = {name: set() for name in native_paths}
    for name in sorted(native_paths):
        path = guard.relative_file(root, name)
        with ZipFile(path) as archive:
            xml = ElementTree.fromstring(archive.read('Document.xml'))
            members = set(archive.namelist())
        for item in xml.findall('Objects/Object'):
            key = f'{name}#{item.attrib["name"]}'
            if key in objects:
                raise ValueError(f'Identité native dupliquée : {key}')
            objects[key] = item.attrib['type']
        for item in xml.findall('ObjectData/Object'):
            origin = f'{name}#{item.attrib["name"]}'
            for prop in item.findall('Properties/Property'):
                for element in prop.iter():
                    if element.tag == 'FileIncluded':
                        asset = element.get('file', element.get('value'))
                        if asset and asset not in members:
                            raise ValueError(f'Fichier inclus manquant de l’archive : {origin} / {asset}')
                        embedded_assets.append({'object': origin, 'property': prop.attrib['name'],
                                                'archive_entry': asset})
                    if element.tag == 'File' and element.get('value'):
                        raise ValueError(f'Fichier externe non intégré à la fermeture : {origin} / {prop.attrib["name"]}')
                    if element.tag not in {'XLink', 'Link', 'LinkSub'}:
                        continue
                    external = element.get('file', '')
                    if external:
                        if Path(external).is_absolute() or PureWindowsPath(external).is_absolute():
                            raise ValueError(f'XLink absolu : {external}')
                        filename = os.path.relpath(path.parent / external.replace('\\', '/'), root)
                        document = guard.relative_file(root, filename).relative_to(root).as_posix()
                        if document != name:
                            document_graph[name].add(document)
                    else:
                        document = name
                    target = element.get('name', element.get('value', ''))
                    if target or external:
                        references.append(dict(origin=origin, target=f'{document}#{target}',
                                               property=prop.attrib['name'], type=element.tag,
                                               serialized_file=external or None,
                                               subobjects=[child.attrib for child in element]))
    documents = dependency_order(document_graph, 'documents natifs')
    missing = []
    object_graph = {key: set() for key in objects}
    for reference in references:
        if reference['target'] not in objects:
            missing.append(reference)
        elif reference['origin'] in object_graph:
            object_graph[reference['origin']].add(reference['target'])
    dependency_order(object_graph, 'objets sérialisés')
    return objects, references, missing, documents, embedded_assets


def dependency_order(graph, scope):
    try:
        return list(TopologicalSorter(graph).static_order())
    except CycleError as exc:
        raise ValueError(f'Cycle dans les {scope} : {exc.args[1]}') from exc


def placement_or_identity(obj, app, property_name='Placement'):
    pose = getattr(obj, property_name, None)
    return pose.toMatrix() if pose is not None else app.Matrix()


def target_placement(link, app):
    if not link.LinkTransform:
        return app.Matrix()
    target = link.LinkedObject
    if target is None or target == link:
        raise ValueError('Placement de la cible du lien indisponible.')
    if target.TypeId in LINKS:
        raise ValueError('Chaîne de liens imbriqués à résoudre séparément.')
    return placement_or_identity(target, app)


def scale_matrix(vector, app):
    matrix = app.Matrix()
    if vector is not None:
        matrix.scale(vector)
    return matrix


def nominal_local(obj, parent, segment, effective_leaf, app):
    """Composer à partir des propriétés écrites et du contexte d'occurrence."""
    matrix = app.Matrix()
    if parent is not None and parent.TypeId in LINKS:
        if parent.ElementCount > 0:
            if segment.isdecimal():
                index = int(segment)
            elif obj in parent.ElementList:
                index = parent.ElementList.index(obj)
            else:
                raise ValueError(f'Élément d’array natif sans indice : {segment}')
            placements = parent.PlacementList
            scales = parent.ScaleList
            if index < len(placements):
                matrix = placements[index].toMatrix()
            if index < len(scales):
                matrix = matrix.multiply(scale_matrix(scales[index], app))
            return matrix.multiply(target_placement(parent, app))
        matrix = target_placement(parent, app)

    if obj.TypeId not in LINKS:
        return matrix.multiply(placement_or_identity(obj, app))
    matrix = matrix.multiply(placement_or_identity(obj, app, 'LinkPlacement'))
    matrix = matrix.multiply(scale_matrix(obj.ScaleVector, app))
    if effective_leaf:
        matrix = matrix.multiply(target_placement(obj, app))
    return matrix


def verify_occurrence_placements(doc, records, app):
    """Comparer la composition des propriétés à getSubObject/Part.getShape."""
    composed, source_objects = {}, {}
    for key, record in sorted(records.items()):
        chain = key.split('#', 1)[1].split('/')
        parent = key.rsplit('/', 1)[0] if len(chain) > 1 else None
        record['parent'] = parent
        try:
            top = doc.getObject(chain[0])
            path = ''.join(name + '.' for name in chain[1:])
            obj = top.getSubObject(path, 1)
            source_objects[key] = obj
            if (record.get('type') == 'Part::Plane' and 'matrix' in record
                    and record['status'] == 'INCONCLUSIVE' and not record['terminal_shape']):
                # The V2 BRep inventory expects solids. A native plane has a
                # valid pose but cannot prove a volumetric clearance.
                record['volume_limitation'] = record.pop('reason')
                record.update(status='PASS', geometry_scope='datum_surface')
            if record['status'] != 'PASS':
                raise ValueError(record.get('reason', 'Chemin natif incomplet.'))
            parent_source = source_objects[parent] if parent else None
            active_shape = record.get('geometry_scope') in {'solid', 'non_volume'}
            local = nominal_local(obj, parent_source, chain[-1], active_shape, app)
            world = composed[parent].multiply(local) if parent else local
            composed[key] = world
            error = max(abs(left - right) for left, right in zip(world.A, record['matrix'], strict=True))
            if not math.isfinite(error):
                raise ValueError('Composition non finie.')
            record['local_matrix'] = list(local.A)
            record['independent_matrix'] = list(world.A)
            record['placement_check'] = {'status': 'PASS' if error <= MATRIX_TOLERANCE else 'MISMATCH',
                                         'maximum_absolute_difference': error}
        except (AttributeError, IndexError, KeyError, RuntimeError, TypeError, ValueError) as exc:
            record['placement_check'] = {'status': 'INCONCLUSIVE', 'reason': str(exc)}


def definition_inventory(root, app, serialized):
    """Recenser aussi les objets auxiliaires masqués et les proxies restaurés."""
    definitions, modules = {}, {}

    def identifier(obj):
        name = guard.inside(root, obj.Document.FileName).relative_to(root).as_posix()
        return f'{name}#{obj.Name}'

    for doc in app.listDocuments().values():
        for obj in doc.Objects:
            key = identifier(obj)
            proxy = getattr(obj, 'Proxy', None)
            module_name = type(proxy).__module__ if proxy is not None else None
            module_file = getattr(sys.modules.get(module_name), '__file__', None)
            if module_file and module_name not in modules and Path(module_file).is_file():
                path = Path(module_file)
                modules[module_name] = {'file': path.name, 'sha256': guard.sha256(path)}
            definition = {'type': obj.TypeId, 'label': obj.Label, 'native_id': obj.ID,
                          'visible': bool(obj.Visibility), 'native_states': list(obj.State),
                          'proxy': type(proxy).__name__ if proxy is not None else None,
                          'proxy_module': module_name, 'serialized': key in serialized,
                          'dependencies': sorted({identifier(dependent) for dependent in obj.OutList})}
            metadata = {name: getattr(obj, name) for name in obj.PropertiesList if name.startswith('ORCH_')
                        and obj.getTypeIdOfProperty(name) == 'App::PropertyString'}
            if metadata:
                definition['geometry_limits'] = metadata
            definitions[key] = definition
    return definitions, modules


def observe_box(record, obj, app):
    dimensions = [float(obj.Length.Value), float(obj.Width.Value), float(obj.Height.Value)]
    matrix = app.Matrix()
    matrix.A = tuple(record['matrix'])
    inverse = matrix.inverse()
    faces = {}
    for axis, name in enumerate('XYZ'):
        for side, sign in [('Min', -1), ('Max', 1)]:
            center = [length / 2 for length in dimensions]
            center[axis] = dimensions[axis] if sign > 0 else 0.0
            # The inverse transpose also gives the correct normal under
            # nonuniform link scaling.
            outward = app.Vector(*(sign * inverse.A[4 * axis + i] for i in range(3)))
            outward.normalize()
            faces[name + side] = {'local_mm': center,
                                  'global_mm': list(matrix.multVec(app.Vector(*center))),
                                  'outward_global': list(outward)}
    return {'method': 'native_box_dimensions_and_resolved_placement', 'source': record['definition'],
            'native_sha256': record['definition_sha256'], 'dimensions_mm': dimensions, 'faces': faces,
            'scope': 'CAD_BOX_PROXY_ONLY'}


def observe_axis(record, obj, app, builder, geometry):
    result = route_measurement(record, obj)
    pose = app.Matrix()
    pose.A = tuple(record['matrix'])
    wire = builder.effective_wire(obj).transformShape(
        pose.multiply(obj.Placement.inverse().toMatrix()), True, True)
    edges = wire.OrderedEdges
    start, _, start_sign = geometry._ends(edges[0])
    _, end, end_sign = geometry._ends(edges[-1])
    result['outward_directions'] = [list(geometry._tangent(edges[0], start, start_sign)),
                                    list(-geometry._tangent(edges[-1], end, end_sign))]
    result.update(scope='AXIS_RESERVATION_ONLY', native_sha256=record['definition_sha256'])
    return result


def inspect_copy(copy):
    from . import freecad_worker as native

    receipt = read(copy / 'experiment.json')
    if Path(receipt['copy_root']).resolve() != copy:
        raise ValueError('Le reçu de copie ne désigne pas le répertoire ouvert.')
    inputs = receipt['inputs_sha256']
    native_paths = [name for name in inputs if name.lower().endswith('.fcstd')]
    serialized, references, broken, order, embedded_assets = serialized_dependencies(copy, native_paths)
    doc, report = reopen(copy, receipt, False)
    if report['before_sha256'] != inputs:
        raise ValueError('La copie courante diverge des entrées gelées.')
    records, shapes, objects = collect(doc, copy, inputs)
    verify_occurrence_placements(doc, records, native.App)
    definitions, proxy_modules = definition_inventory(copy, native.App, serialized)
    dependency_order({key: item['dependencies'] for key, item in definitions.items()}, 'objets recalculés')
    boxes, axes = {}, {}
    for key, record in sorted(records.items()):
        obj = objects.get(key)
        record['proxy'] = definitions.get(record.get('definition'), {}).get('proxy')
        if obj is None or record['placement_check']['status'] != 'PASS':
            continue
        if obj.TypeId == 'Part::Box':
            boxes[key] = observe_box(record, obj, native.App)
        if record['visible'] and record.get('route', {}).get('object') == record.get('definition'):
            try:
                axes[key] = observe_axis(record, obj, native.App, native.builder, native.geometry)
            except (AttributeError, IndexError, RuntimeError, TypeError, ValueError) as exc:
                axes[key] = {'status': 'unknown', 'reason': str(exc), 'scope': 'AXIS_RESERVATION_ONLY'}
    if check_files(copy, receipt) != inputs:
        raise ValueError('Une entrée a changé pendant la projection.')
    report.update(schema=SCHEMA, entry=receipt['entry'], occurrences=records, definitions=definitions,
                  dependencies=references, broken_serialized_links=broken, document_order=order,
                  embedded_assets=embedded_assets,
                  unavailable_definitions=sorted(serialized.keys() - definitions.keys()),
                  proxy_modules=proxy_modules, boxes=boxes, axes=axes, worker_pid=os.getpid(),
                  python_packages={item.metadata['Name']: item.version
                                   for item in importlib.metadata.distributions()})
    usage = Counter(item['definition'] for item in records.values() if 'definition' in item)
    report['shared_definitions'] = {key: value for key, value in sorted(usage.items()) if value > 1}
    report['occurrence_counts'] = {'total': len(records), 'solid': len(shapes),
                                   'hidden': sum(not item['visible'] for item in records.values()),
                                   'placement': dict(Counter(item['placement_check']['status']
                                                             for item in records.values()))}
    report['status'] = 'PASS' if (report['status'] == 'PASS' and not broken
                                  and not report['unavailable_definitions']
                                  and set(report['occurrence_counts']['placement']) <= {'PASS'}
                                  and all('endpoints_mm' in item for item in axes.values())) else 'INCONCLUSIVE'
    return report


def worker(python, copy, output, timeout):
    if output.exists():
        raise ValueError(f'Le rapport du processus doit être nouveau : {output}')
    trace = output.with_suffix('.log')
    with trace.open('wb') as log:
        result = subprocess.run(
            [str(python), '-B', '-m', 'electromechanical_engine.v3_native',
             '--worker', str(copy), str(output)], cwd=PROJECT, stdout=log, stderr=subprocess.STDOUT,
            timeout=timeout, check=False, env=dict(os.environ, QT_QPA_PLATFORM='offscreen', PYTHONUTF8='1'),
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    if result.returncode or not output.is_file():
        raise RuntimeError(f'Projection native sans rapport finalisé (code {result.returncode}, {trace}).')
    report = read(output)
    if report.get('finalized') is not True:
        raise RuntimeError(f'Projection native incomplète ({trace}).')
    return report


def project(python, source, entry, work, output, extras=(), timeout=180):
    source = guard.inside(PROJECT, source)
    work = guard.inside(PROJECT / '.runtime', work)
    output = guard.inside(PROJECT / '.runtime', output)
    work.mkdir(parents=True, exist_ok=False)
    first, second = work / 'staged', work / 'transfer' / 'cad'
    receipt = guard.stage(source, entry, first, extras, parameters={'extras': list(extras)})
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        original = worker(python, first, work / 'staged.json', timeout)
        transferred = guard.stage(first, entry, second, extras, parameters={'extras': list(extras)})
        if transferred['inputs_sha256'] != receipt['inputs_sha256']:
            raise ValueError('Le transfert d’emplacement a modifié une entrée.')
        reopened = worker(python, second, work / 'transfer.json', timeout)
        comparison = ['documents', 'occurrences', 'definitions', 'dependencies', 'embedded_assets', 'boxes', 'axes',
                      'environment', 'proxy_modules', 'python_packages', 'status']
        differences = [key for key in comparison if original[key] != reopened[key]]
        distinct = original['worker_pid'] != reopened['worker_pid']
        original['transfer'] = {'status': 'PASS' if distinct and not differences else 'FAIL',
                                'from': first.relative_to(PROJECT).as_posix(),
                                'to': second.relative_to(PROJECT).as_posix(),
                                'separate_processes': distinct, 'differences': differences,
                                'native_report_sha256': guard.sha256(work / 'transfer.json')}
        if differences or not distinct:
            original['status'] = 'INCONCLUSIVE'
    finally:
        verified = guard.verify_sources(receipt)
    source_prefix = source.relative_to(PROJECT).as_posix()
    original.update(source_prefix=source_prefix, entry_repository=f'{source_prefix}/{entry}',
                    source_immutability=verified)
    publish(output, original)
    return original


def main():
    if len(sys.argv) == 4 and sys.argv[1] == '--worker':
        copy, output = map(Path, sys.argv[2:])
        try:
            report = inspect_copy(guard.inside(PROJECT / '.runtime', copy))
            report['finalized'] = True
        except Exception:
            traceback.print_exc()
            report = {'finalized': False, 'error': traceback.format_exc()}
        publish(output, report)
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(0 if report['finalized'] else 1)

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--freecad-python', required=True, type=Path)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--entry', required=True)
    parser.add_argument('--work', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--extra', action='append', default=[])
    parser.add_argument('--timeout', type=int, default=180)
    options = parser.parse_args()
    report = project(options.freecad_python.resolve(), options.source, options.entry,
                     options.work, options.output, options.extra, options.timeout)
    print(json.dumps({'status': report['status'], 'documents': len(report['documents']),
                      'occurrences': report['occurrence_counts'], 'axes': len(report['axes']),
                      'transfer': report['transfer']['status']}, ensure_ascii=False))
    return 0 if report['status'] == 'PASS' else 2


if __name__ == '__main__':
    raise SystemExit(main())
