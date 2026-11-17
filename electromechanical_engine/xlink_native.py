"""Interface de processus et mesures natives FreeCAD pour le validateur XLink."""

from __future__ import annotations

import csv
import json
import math
import os
from pathlib import Path
import sys
import traceback
from uuid import uuid4

from .freecad import PROJECT, guard


def publish(path, value):
    temp = path.with_name(f'{path.name}.{uuid4().hex}.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, allow_nan=False) + '\n', encoding='utf-8')
    temp.replace(path)


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def hash_copy(root, receipt):
    return {name: guard.sha256(guard.relative_file(root, name)) for name in receipt['inputs_sha256']}


def check_files(root, receipt):
    guard.verify_sources(receipt)
    copy = hash_copy(root, receipt)
    entrypoints = [receipt['entry'], *receipt.get('parameters', {}).get('extras', ())]
    dependencies = {path.relative_to(root).as_posix() for path in guard.dependencies(root, entrypoints)
                    if path.suffix.lower() == '.fcstd'}
    expected = {name for name in copy if name.lower().endswith('.fcstd')}
    if dependencies != expected:
        raise ValueError(f'Fermeture XLink différente du reçu : {sorted(dependencies ^ expected)}')
    if any(copy[name] != digest for name, digest in receipt['inputs_sha256'].items() if name != receipt['entry']):
        raise ValueError('Une dépendance de la copie diffère de la source gelée.')
    return copy


def collect(doc, root, hashes):
    """Lire les transformations et BRep via les chemins natifs de la racine."""
    from . import freecad_worker as native

    app = native.App
    records, shapes, native_objects = {}, {}, {}
    root_file = guard.inside(root, doc.FileName).relative_to(root).as_posix()

    def reference(obj):
        name = guard.inside(root, obj.Document.FileName).relative_to(root).as_posix()
        return f'{name}#{obj.Name}', hashes[name]

    def walk(top, subname, ancestors, visible):
        ident = root_file + '#' + top.Name + ('/' + subname.rstrip('.').replace('.', '/') if subname else '')
        if ident in records:
            raise ValueError(f'Chemin FreeCAD dupliqué : {ident}')
        record = {'status': 'INCONCLUSIVE', 'terminal_shape': False, 'visible': visible}
        records[ident] = record
        try:
            obj, matrix = top.getSubObject(subname, 1, app.Matrix(), True)
            object_key, object_hash = reference(obj)
            record.update(object=object_key, document_sha256=object_hash, label=obj.Label,
                          type=obj.TypeId, native_id=obj.ID, native_states=list(obj.State))
            if {'Invalid', 'Error'} & set(obj.State):
                raise ValueError('État natif invalide.')
            is_link = obj.TypeId in ('App::Link', 'App::LinkElement')
            link_array = is_link and getattr(obj, 'ElementCount', 0) > 0
            definition = obj if link_array else obj.getLinkedObject(True) if is_link else obj
            if definition is None or (is_link and not link_array and definition == obj):
                raise ValueError('Cible de lien absente ou rompue.')
            definition_key, definition_hash = reference(definition)
            record.update(definition=definition_key, definition_sha256=definition_hash,
                          definition_label=definition.Label, matrix=list(matrix.A))
            # getSubObject retType=1 returns the occurrence matrix. For a leaf
            # link, Part.getShape resolves the additional target transform too.
            group = definition.TypeId in ('App::Part', 'App::DocumentObjectGroup')
            children = obj.getSubObjects() if group or link_array else ()
            if not children and group:
                children = definition.getSubObjects()
            native_objects[ident] = definition
            proxy = type(getattr(definition, 'Proxy', None)).__name__
            if proxy == 'ArchCable':
                record['route'] = {'object': definition_key}
            if proxy == 'CableTerminal':
                record['native_terminal'] = {'id': getattr(definition, 'L2Id', None)}
            if children:
                if definition_key in ancestors:
                    raise ValueError('Cycle de conteneurs ou de liens.')
                for child in children:
                    # FreeCAD exposes instance visibility separately for arrays.
                    element_visible = obj.isElementVisible(child.rstrip('.'))
                    child_obj = top.getSubObject(subname + child, 1)
                    child_visible = element_visible if element_visible >= 0 else getattr(child_obj, 'Visibility', True)
                    walk(top, subname + child, (*ancestors, definition_key), visible and bool(child_visible))
                routes = [records[ident + '/' + child.rstrip('.').replace('.', '/')]['route']
                          for child in children
                          if 'route' in records[ident + '/' + child.rstrip('.').replace('.', '/')]]
                if len(routes) == 1:
                    record['route'] = routes[0]
                record['geometry_scope'] = 'children'
            elif group or link_array:
                record['geometry_scope'] = 'empty_container'
            elif visible:
                shape, resolved_matrix, resolved = native.Part.getShape(top, subname, retType=2)
                if resolved is not None:
                    record['matrix'] = list(resolved_matrix.A)
                if not shape.isNull() and shape.Solids:
                    limits = native.bounds(shape)
                    if not all(math.isfinite(value) for corner in limits for value in corner):
                        raise ValueError('Boîte englobante non finie.')
                    record.update(terminal_shape=True, bounds_mm=limits,
                                  geometry_scope='solid' if visible else 'hidden_solid')
                    shapes[ident] = shape
                elif (visible and definition.isDerivedFrom('Part::Feature')
                      and (shape.isNull() or shape.Faces)):
                    raise ValueError('Forme partielle ou sans solide fermé.')
                else:
                    record['geometry_scope'] = 'non_volume'
            else:
                record['geometry_scope'] = 'hidden_geometry'
            record['status'] = 'PASS'
        except (AttributeError, KeyError, RuntimeError, TypeError, ValueError) as error:
            record['reason'] = str(error)

    for top in sorted(doc.RootObjects, key=lambda obj: obj.Name):
        walk(top, '', (), bool(top.Visibility))
    # Cables attachments also use incoming property links. Some installed
    # objects in the root document therefore do not appear in RootObjects.
    present = {row.get('object') for row in records.values()}
    for obj in doc.Objects:
        proxy = type(getattr(obj, 'Proxy', None)).__name__
        if (reference(obj)[0] not in present and obj.Visibility and
                proxy in ('ArchElectricalDevice', 'ArchCableConnector', 'CableTerminal')):
            walk(obj, '', (), True)
    resolve_contacts(records, native_objects)
    return records, shapes, native_objects


def resolve_contacts(records, objects):
    """Follow native attachment properties to a uniquely instanced device."""
    equipment = {}
    for ident, obj in objects.items():
        if type(getattr(obj, 'Proxy', None)).__name__ == 'ArchElectricalDevice':
            equipment.setdefault(records[ident]['definition'], []).append(ident)

    def attached_parent(obj):
        support = getattr(obj, 'AttachmentSupport', ())
        return support[0][0] if getattr(obj, 'MapMode', None) == 'ObjectXY' and len(support) == 1 else None

    for ident, obj in objects.items():
        record = records[ident]
        terminal = record.get('native_terminal', {}).get('id')
        if not terminal or not record['visible']:
            continue
        connector = attached_parent(obj)
        if connector is None or connector != getattr(obj, 'ParentElement', None):
            continue
        port = getattr(connector, 'L2Port', None)
        chain = set()
        while (connector is not None and connector not in chain and
               type(getattr(connector, 'Proxy', None)).__name__ == 'ArchCableConnector' and
               getattr(connector, 'L2Port', None) == port):
            chain.add(connector)
            connector = attached_parent(connector)
        if not port or not chain or connector is None or not getattr(connector, 'Visibility', False):
            continue
        # Use the deepest shared assembly branch. Ties require an explicit
        # native path and remain unbound here.
        matches = []
        for key, candidates in equipment.items():
            for candidate in candidates:
                if objects[candidate] != connector or records[candidate]['status'] != 'PASS':
                    continue
                depth = 0
                for left, right in zip(ident.split('/'), candidate.split('/')):
                    if left != right:
                        break
                    depth += 1
                matches.append((depth, candidate, key))
        matches.sort(reverse=True)
        if matches and (len(matches) == 1 or matches[0][0] > matches[1][0]):
            record['contact'] = {'id': terminal, 'port': port, 'equipment_occurrence': matches[0][1],
                                 'attachment_source': 'CableTerminal.ParentElement + AttachmentSupport'}


def reopen(root, receipt, save):
    from . import freecad_worker as native

    before = check_files(root, receipt)
    print('Cables Workbench, ouverture et recalcul de la fermeture', flush=True)
    cables = native.cables_environment(False)
    doc = native.App.openDocument(str(root / receipt['entry']))
    promoted = native.complete_dependencies(doc, root)
    documents, recomputed = native.recalculate(doc, root)
    loaded, broken, invalid = {}, [], []
    for document in documents:
        file = guard.inside(root, document.FileName).relative_to(root).as_posix()
        loaded[file] = {'sha256': before[file], 'label': document.Label,
                        'objects': len(document.Objects), 'partial': bool(document.Partial)}
        for obj in document.Objects:
            ident = file + '#' + obj.Name
            if {'Invalid', 'Error'} & set(obj.State):
                invalid.append(ident)
            if obj.TypeId in ('App::Link', 'App::LinkElement') and obj.LinkedObject is None:
                if not getattr(obj, 'ElementCount', 0):
                    broken.append(ident)
    expected = {name for name in before if name.lower().endswith('.fcstd')}
    complete = expected == loaded.keys() and not any(item['partial'] for item in loaded.values())
    healthy = complete and not broken and not invalid
    saved = save and healthy
    if saved:
        print('Sauvegarde exclusive de la racine de copie', flush=True)
        doc.save()
    after = check_files(root, receipt)
    if not saved and before != after:
        raise ValueError('La copie de lecture a changé.')
    report = {'status': 'PASS' if healthy else 'INCONCLUSIVE', 'documents': loaded,
              'inventory_complete': complete, 'recompute_ok': healthy,
              'completed_partial_documents': promoted, 'recomputed_features': recomputed,
              'broken_links': broken, 'invalid_objects': invalid, 'before_sha256': before,
              'after_sha256': after, 'save_performed': saved,
              'environment': {'FreeCAD': '.'.join(native.App.Version()[:3]), 'OCCT': native.Part.OCC_VERSION,
                              'Python': sys.version, 'Cables': cables}}
    return doc, report


def route_measurement(record, obj, criteria=None):
    from . import freecad_worker as native

    wire = native.builder.effective_wire(obj)
    # The native wire is in its document coordinates. Undo its object
    # placement before applying the resolved occurrence transformation.
    pose = native.App.Matrix()
    pose.A = tuple(record['matrix'])
    local = obj.Placement.inverse().toMatrix()
    world = wire.transformShape(pose.multiply(local), True, True)
    criteria = criteria or {}
    observed = native.geometry.inspect_route(
        world, criteria.get('minimum_radius_mm'), criteria.get('start_axis'), criteria.get('end_axis'),
        start_position=criteria.get('start_mm'), end_position=criteria.get('end_mm'),
        position_tolerance_mm=criteria.get('position_tolerance_mm', 1e-5),
        tangent_tolerance_deg=criteria.get('tangent_tolerance_deg', 1e-3))
    vertices = world.OrderedVertexes
    observed['endpoints_mm'] = [native.coordinates(v.Point) for v in (vertices[0], vertices[-1])]
    observed['native_object'] = record['object']
    if observed['status'] == 'pass' and not all(key in criteria for key in
                                               ('start_mm', 'end_mm', 'start_axis', 'end_axis')):
        observed['status'] = 'unknown'
        observed['unknowns'].append('terminal_criteria_missing')
    return observed


def measure(tasks, destination, records, shapes, objects, criteria, cache_key):
    from . import freecad_worker as native

    for task in tasks:
        ident, a = task['id'], task['a']
        print(f'{ident}: {a} {task.get("b", "")}', flush=True)
        try:
            if task['kind'] == 'pair':
                b = task['b']
                result = native.measure_pair(shapes[a], shapes[b], a, b, criteria['clearance_mm'],
                                             criteria['volume_tolerance_mm3'], criteria['distance_tolerance_mm'],
                                             task.get('relation'))
            elif task['kind'] == 'route':
                result = route_measurement(records[a], objects[a], task.get('criteria'))
            elif task['kind'] == 'solid':
                shape = shapes[a]
                result = {'status': 'pass' if shape.isValid() and shape.Volume > 0 else 'fail',
                          'solid_count': len(shape.Solids), 'volume_mm3': shape.Volume}
            else:
                raise ValueError(f'Tâche native inconnue : {task["kind"]}')
        except (AttributeError, IndexError, KeyError, RuntimeError, TypeError, ValueError) as error:
            result = {'status': 'unknown', 'reason': str(error)}
        publish(destination / (ident + '.json'), {'cache_key': cache_key, 'task': task,
                                                   'observation': result, 'worker_pid': os.getpid()})


def execute(request, output):
    action = request['action']
    if action == 'projection':
        register = guard.inside(PROJECT, request['register'])
        equipment, keys = {}, set()
        with register.open(encoding='utf-8-sig', newline='') as stream:
            for row in csv.DictReader(stream):
                key = row['cle_interface']
                if key in keys:
                    raise ValueError(f'Interface dupliquée : {key}')
                keys.add(key)
                frame = json.loads(row['repere_equipement_vers_assemblage'] or 'null')
                if frame and frame.get('valeur', {}).get('occurrence'):
                    equipment[key] = {'object': frame['valeur']['occurrence'], 'source': frame.get('source')}
        return {'equipment': equipment, 'register_interfaces': sorted(keys), 'register_sha256': guard.sha256(register)}
    root = guard.inside(PROJECT, request['copy'])
    if action == 'stage':
        source = guard.inside(PROJECT, request['source'])
        extras = request.get('extras', [])
        return guard.stage(source, request['entry'], root, extras, parameters={'extras': extras})
    receipt = read(root / 'experiment.json')
    if action == 'verify':
        return {'after_sha256': check_files(root, receipt), **guard.verify_sources(receipt)}
    doc, report = reopen(root, receipt, action == 'save')
    if action == 'save':
        return report
    if report['before_sha256'] != request['native_sha256']:
        raise ValueError('La mesure ne correspond pas aux empreintes de la copie sauvegardée.')
    if action == 'measure' and report['environment'] != request['environment']:
        raise ValueError('Environnement FreeCAD différent de celui de l’inventaire.')
    print('Lecture des occurrences et formes terminales', flush=True)
    records, shapes, objects = collect(doc, root, report['before_sha256'])
    if action == 'inventory':
        report.update(occurrences=records, occurrence_count=len(records), root=receipt['entry'])
    elif action == 'measure':
        checkpoints = guard.inside(output.parent.parent / 'cache', request['checkpoints'])
        measure(request['tasks'], checkpoints, records, shapes, objects, request['criteria'], request['cache_key'])
    else:
        raise ValueError(f'Opération native inconnue : {action}')
    if check_files(root, receipt) != report['before_sha256']:
        raise ValueError('La fermeture a changé pendant la mesure.')
    return report


def main():
    request, output = map(Path, sys.argv[1:])
    try:
        report = execute(read(request), output)
        report['finalized'] = True
    except Exception:
        report = {'finalized': False, 'reason': traceback.format_exc()}
    report.update(pid=os.getpid(), worker_id=uuid4().hex)
    publish(output, report)
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0 if report['finalized'] else 1)


if __name__ == '__main__':
    main()
