"""Projection des interconnexions sur une copie XLink FreeCAD en lecture seule."""

from __future__ import annotations

import argparse
import csv
import inspect
import json
import os
from pathlib import Path
import subprocess
import sys

from .freecad import PROJECT, guard, load_helper


CARTO = PROJECT / 'hardware/mecanique/cartographe'
ENTRY = 'assemblages/Prototype_Cartographe.FCStd'
CABLE_ASSEMBLY = 'sous_assemblages/SA07_Prototype_Faisceaux.FCStd'
BOM = PROJECT / 'docs/verification/go3a/GO3A_CONNECTOR_BOM.csv'
RECONCILIATION = PROJECT / 'docs/electromechanical_v2/L2_RECONCILIATION.json'
USB_REGISTER = 'verification/connecteurs_coudes_camera_prototype.json'
USB_STEP = 'sources_fabricants/usbfirewire/RR-ASMUK-XXGRHF_3dConn1.stp'
BANC = PROJECT / 'hardware/mecanique/banc_interconnexion/verification/freecad_adapter.py'
BUILDER_INPUTS = (PROJECT / 'electromechanical_engine/freecad_worker.py',
                  PROJECT / '.agents/skills/electromechanical-integration/scripts/workspace_guard.py',
                  PROJECT / '.agents/skills/electromechanical-integration/scripts/freecad_geometry.py',
                  PROJECT / 'hardware/mecanique/cartographe/verification/cable_workbench_prototype.py')


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def observations(output):
    from . import freecad_worker as native

    App = native.App
    environment = native.cables_environment(gui=False)
    if environment['version'] != '0.3.7':
        raise RuntimeError('Cables 0.3.7 est la cible de ce contrôle de signatures.')
    from freecad.cables import archCableConnector, archElectricalDevice, cableTerminal, cableutils

    for module in (archCableConnector, archElectricalDevice, cableTerminal, cableutils):
        path = Path(module.__file__)
        environment['sha256_modules'][path.name] = guard.sha256(path)
    for factory in (archCableConnector.makeCableConnector, archElectricalDevice.makeElectricalDevice,
                    cableTerminal.makeCableTerminal, cableutils.attach_in_place):
        environment['api'][factory.__name__] = str(inspect.signature(factory))
    target = output / 'copie'
    receipt = read_json(target / 'experiment.json')
    mapping = read_json(output / 'projection.json')
    doc = App.openDocument(str(target / ENTRY))
    native.complete_dependencies(doc, target)
    documents = {guard.inside(target, item.FileName).relative_to(target).as_posix(): item
                 for item in App.listDocuments().values()}
    expected = set(receipt['inputs_sha256']) - {USB_REGISTER, USB_STEP}
    if set(documents) != expected:
        raise RuntimeError('La fermeture ouverte par FreeCAD diffère de la copie XLink.')

    def key(obj):
        return guard.inside(target, obj.Document.FileName).relative_to(target).as_posix() + '#' + obj.Name

    def object_at(identifier):
        file, name = identifier.split('#', 1)
        document = documents.get(file)
        return document.getObject(name) if document else None

    # Ces mesures portent les occurrences immédiates sous les sous-assemblages
    # directs du cartographe. Les placements globaux FreeCAD incluent les groupes locaux.
    def link_index(document):
        links = {}
        for obj in document.Objects:
            if obj.TypeId != 'App::Link' or obj.LinkedObject is None:
                continue
            file = key(obj.LinkedObject).split('#', 1)[0]
            links.setdefault(file, []).append(obj)
        return links

    top_links = link_index(doc)

    def document_placement(obj):
        if obj.TypeId != 'App::Link':
            return obj.getGlobalPlacement()
        parent = obj.Document.getObject('Ensemble')
        if parent is None or obj not in parent.Group or obj.LinkTransform:
            raise RuntimeError(f'Composition du placement du lien non prise en charge : {key(obj)}')
        # App::Link n'expose pas getGlobalPlacement dans cette installation.
        return parent.getGlobalPlacement().multiply(obj.LinkPlacement)

    def assembly_transform(obj):
        if obj.Document == doc:
            return App.Placement()
        choices = top_links[key(obj).split('#', 1)[0]]
        if len(choices) != 1:
            raise RuntimeError(f'Occurrence de sous-assemblage ambiguë : {key(obj)}')
        top = choices[0]
        return document_placement(top).multiply(document_placement(top.LinkedObject).inverse())

    def placement(obj):
        return assembly_transform(obj).multiply(document_placement(obj))

    cable_links = link_index(documents[CABLE_ASSEMBLY])
    axes, reverse = {}, {}
    for axis in mapping['axes']:
        source = Path(axis['active_native']['path']).relative_to(CARTO.relative_to(PROJECT)).as_posix()
        if receipt['inputs_sha256'].get(source) != axis['active_native']['sha256']:
            raise RuntimeError(f"Empreinte L2 différente du natif lu pour {axis['id']}")
        choices = cable_links[source]
        if len(choices) != 1:
            raise RuntimeError(f"Occurrence d'axe ambiguë : {axis['id']}")
        occurrence = choices[0]
        cable = documents[source].getObject(axis['native_object'])
        route = cable.Base
        if type(cable.Proxy).__name__ != 'ArchCable' or type(route.Proxy).__name__ != 'WireFlex':
            raise RuntimeError(f"Type de câble ou parcours inattendu : {axis['id']}")
        vertices = native.builder.effective_wire(cable).OrderedVertexes
        transform = placement(occurrence).multiply(document_placement(occurrence.LinkedObject).inverse())
        ends = [native.coordinates(transform.multVec(v.Point)) for v in (vertices[0], vertices[-1])]
        attachments = []
        for attribute in ('Vrtx_start', 'Vrtx_end'):
            link = getattr(route, attribute)
            attachments.append({'object': key(link[0]), 'subelements': list(link[1]),
                                'proxy': type(getattr(link[0], 'Proxy', None)).__name__} if link else None)
        axes[axis['id']] = {'occurrence': key(occurrence), 'cable': key(cable), 'wire': key(route),
                           'line_ids': axis['line_ids'], 'endpoints_mm': ends,
                           'wire_attachments': attachments}
        reverse[key(occurrence)] = {'axis_id': axis['id'], 'line_ids': axis['line_ids']}

    interfaces = {}
    for item in mapping['ends']:
        occurrence = None
        pose = json.loads(item['repere_equipement_vers_assemblage'] or 'null')
        if pose and pose.get('valeur', {}).get('occurrence'):
            identifier = pose['valeur']['occurrence']
            obj = object_at(identifier)
            if obj is not None and (obj.Document == doc or key(obj).split('#')[0] in top_links):
                occurrence = {'object': key(obj), 'matrix': list(placement(obj).toMatrix().A),
                              'source': pose['source'], 'class': 'NATIVE_OBSERVATION'}
                reverse.setdefault(key(obj), {}).setdefault('interface_ids', []).append(item['cle_interface'])
        line = mapping['lines'][item['liaison_id']]
        interfaces[item['cle_interface']] = {
            'port': item['port_fonctionnel'], 'device_mount_frame': occurrence, 'path': line['path'],
            'path_kind': line['path_kind'], 'status': 'INCONCLUSIVE',
            'receptacle_frame': None, 'mating_frame': None, 'plug_frame': None, 'wire_exit_frame': None,
            'extraction_sweep': None, 'tool_access_envelope': None, 'contacts_bound_to_occurrences': None}

    candidate = measure_usb(native, target, object_at, placement)
    interfaces['W16/B']['candidate_geometry_ref'] = '#/usb_microb_candidate'
    reverse.setdefault(candidate['occurrence'], {}).setdefault('interface_ids', []).append('W16/B')
    load_helper(BANC).publish_json(output / 'observations.json', {
        'status': 'INCONCLUSIVE', 'pid': os.getpid(), 'scope': 'prototype_cartographe',
        'environment': environment, 'documents_loaded': len(documents), 'axes': axes,
        'interfaces': interfaces, 'reverse_objects': reverse, 'usb_microb_candidate': candidate,
        'interactive': 'NOT_EXECUTED', 'physical': 'NOT_EXECUTED'})


def measure_usb(native, target, object_at, placement):
    """Mesurer le STEP candidat dans le repère de l'équipement natif observé."""
    App, Part = native.App, native.Part
    register = read_json(target / USB_REGISTER)
    source = register['usb']['source_step']
    plug_occ = object_at(CABLE_ASSEMBLY + '#ConnecteurF16Camera')
    camera = object_at('sous_assemblages/SA04_Prototype_Perception.FCStd#EQ_Basler_Occurrence')
    if plug_occ is None or camera is None:
        raise RuntimeError('Occurrence W16/B attendue absente du natif de référence.')
    plug_pose = placement(plug_occ)
    camera_pose = placement(camera)
    step_path = target / USB_STEP
    imported = Part.read(str(step_path))
    if not imported.isValid() or len(imported.Solids) != source['solides_total']:
        raise RuntimeError('Structure STEP différente du registre géométrique F16.')

    def in_world(shape):
        result = shape.copy()
        result.Placement = plug_pose.multiply(shape.Placement)
        return result

    local_body = imported.Solids[source['a_reutiliser_microB'][0]]
    body = in_world(local_body)
    # La course est exploratoire. Le nez et les vis éventuellement engagés
    # sont traités à part par le registre. Le jeu du corps n'implique aucun appairage.
    travel = register['usb']['dimensions_plan_mm']['nez_microB']
    course = float(travel[0] + travel[1])
    local_axis = App.Vector(-1, 0, 0)
    delta = plug_pose.Rotation.multVec(local_axis * course)
    minimum, maximum = native.bounds(body)
    shift = native.coordinates(delta)
    low = [min(x, x + s) for x, s in zip(minimum, shift)]
    high = [max(x, x + s) for x, s in zip(maximum, shift)]
    swept = Part.makeBox(*(b - a for a, b in zip(low, high)), App.Vector(*low))
    tool_radius, tool_length = 2.0, 50.0
    datums = source['datums_source']
    tools = [Part.makeCylinder(tool_radius, tool_length,
                              plug_pose.multVec(App.Vector(-5, datums['axes_vis_y'], z)),
                              plug_pose.Rotation.multVec(local_axis)) for z in datums['axes_vis_z']]
    obstacles = (
        camera,
        object_at('sous_assemblages/SA02_Prototype_Batterie.FCStd#Pack6S20Ah'),
        object_at('sous_assemblages/SA04_Prototype_Perception.FCStd#P10_Retenue_cable_Occurrence'),
        object_at('sous_assemblages/SA04_Prototype_Perception.FCStd#P10_Retenue_cable_Occurrence001'),
        object_at(CABLE_ASSEMBLY + '#F_M8'),
    )
    if any(obj is None for obj in obstacles):
        raise RuntimeError('Un obstacle déclaré dans le périmètre F16 manque dans le natif.')
    sizes = {'mated_body': body, 'extraction_sweep': swept,
             'tool_access_1': tools[0], 'tool_access_2': tools[1]}
    checks = {}
    for kind, shape in sizes.items():
        checks[kind] = []
        for obj in obstacles:
            obstacle = obj.Shape.copy()
            obstacle.Placement = placement(obj).multiply(obj.LinkPlacement.inverse()).multiply(obstacle.Placement)
            checks[kind].append(native.geometry.inspect_pair(shape, obstacle, kind, obj.Name))
    return {
        'status': 'INCONCLUSIVE', 'class': 'SUPPLIER_GEOMETRY_AND_CONSERVATIVE_ENVELOPE',
        'candidate_mpn': register['usb']['candidate'], 'step_sha256': guard.sha256(step_path),
        'solids_imported': len(imported.Solids), 'occurrence': CABLE_ASSEMBLY + '#' + plug_occ.Name,
        'source': f'{USB_REGISTER}#/usb/source_step', 'plug_frame_to_assembly': list(plug_pose.toMatrix().A),
        'plug_frame_to_device': list(camera_pose.inverse().multiply(plug_pose).toMatrix().A),
        'wire_exit_mm': native.coordinates(plug_pose.multVec(App.Vector(*source['coordonnees_source_sortie_gaine_microB']))),
        'wire_exit_direction': native.coordinates(plug_pose.Rotation.multVec(App.Vector(*source['direction_source_sortie_microB']))),
        'checks': checks, 'native_attachment_probe': probe_usb_attachment(
            native, local_body, camera.Shape, camera_pose, plug_pose, step_path),
        'extraction': {'translation_mm': shift, 'method': 'continuous_bounding_box_of_molded_body',
                       'course_source': f'{USB_REGISTER}#/usb/dimensions_plan_mm/nez_microB'},
        'tool': {'radius_mm': tool_radius, 'length_mm': tool_length,
                 'class': 'ASSUMPTION', 'scope': 'two screw axes and a cylindrical tool envelope'},
        'limits': ['Pose nominale. Choix de l’outil et séquence de déverrouillage inconnus.',
                   'Mesure du corps moulé, de la caméra modélisée et des obstacles indiqués.',
                   'Nez, vis engagées, contacts, cinématique réelle et montage complet à valider.']}


def probe_usb_attachment(native, body, camera_shape, camera_pose, plug_pose, step_path):
    """Vérifier le suivi de pose Cables sur les géométries candidates, en mémoire."""
    from freecad.cables import archCableConnector, archElectricalDevice, cableutils

    App = native.App
    banc = load_helper(BANC)
    doc = App.newDocument('V21_USB_DryRun')
    try:
        device_base = doc.addObject('Part::Feature', 'CameraCandidateGeometry')
        camera_local = camera_shape.copy()
        camera_local.Placement = camera_pose.inverse().multiply(camera_local.Placement)
        device_base.Shape = camera_local
        body_base = doc.addObject('Part::Feature', 'MicroBCandidateGeometry')
        body_base.Shape = body
        device = archElectricalDevice.makeElectricalDevice(
            baseobj=device_base, preset='Customized', placement=camera_pose)
        plug = archCableConnector.makeCableConnector(baseobj=body_base, preset='Customized', placement=plug_pose)
        cableutils.attach_in_place([plug, device])
        banc.recompute(doc)
        shape, _ = plug.Proxy.readExtShape(plug, step_path.name, libdirs=[str(step_path.parent)])
        banc.require(shape.isValid() and len(shape.Solids) == 7, 'Import STEP Cables du candidat incomplet.')
        banc.check_shape(plug, 1)
        delta = App.Placement(App.Vector(1, 2, 3), App.Rotation(App.Vector(0, 0, 1), 12))
        device.Placement = delta.multiply(camera_pose)
        banc.recompute(doc)
        banc.check_shape(plug, 1)
        pose = banc.check_pose(plug, list(delta.multiply(plug_pose).toMatrix().A))
        banc.require(banc.attached_to(plug, device) and pose['status'] == 'PASS',
                     'La fiche candidate ne suit pas la pose de l’équipement.')
        return {'status': 'PASS', 'scope': 'attachement mécanique en mémoire du corps moulé',
                'source_solids_imported_through_cables': len(shape.Solids),
                'device_proxy': type(device.Proxy).__name__, 'plug_proxy': type(plug.Proxy).__name__,
                'equipment_delta': list(delta.toMatrix().A), 'observed_plug_matrix': pose['matrix'],
                'finalized_native_file': None}
    finally:
        App.closeDocument(doc.Name)


def run(output, freecad, reconciliation):
    files = (BOM, reconciliation, BANC, Path(__file__), *BUILDER_INPUTS)
    before = {p.resolve().relative_to(PROJECT).as_posix(): guard.sha256(p) for p in files}
    receipt = guard.stage(CARTO, ENTRY, output / 'copie', [USB_REGISTER, USB_STEP])
    data = read_json(reconciliation)
    with BOM.open(encoding='utf-8-sig', newline='') as stream:
        ends = list(csv.DictReader(stream))
    lines = {line['id']: line for line in data['lines']}
    if len(lines) != len(data['lines']) or len(ends) != 2 * len(lines) or (
            {item['cle_interface'] for item in ends} != {f'{line}/{side}' for line in lines for side in 'AB'}):
        raise RuntimeError('Les extrémités GO3A ne couvrent pas les lignes L2 en A/B.')
    (output / 'projection.json').write_text(json.dumps({
        'axes': data['axes'], 'lines': lines, 'ends': ends}, ensure_ascii=False, allow_nan=False), encoding='utf-8')
    env = dict(os.environ, QT_QPA_PLATFORM='offscreen', PYTHONUTF8='1', PYTHONPATH=str(PROJECT))
    try:
        with (output / 'freecad.log').open('wb') as log:
            execution = subprocess.run([str(freecad), '-B', '-m', 'electromechanical_engine.connector_native',
                                        str(output), '--worker'], cwd=output, env=env, stdout=log,
                                       stderr=subprocess.STDOUT, timeout=60, check=False,
                                       creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        if execution.returncode:
            raise RuntimeError(f'FreeCAD a terminé avec le code {execution.returncode} ; consulter freecad.log.')
        observed = read_json(output / 'observations.json')
    finally:
        integrity = guard.verify_sources(receipt)
        if any(guard.sha256(PROJECT / file) != digest for file, digest in before.items()):
            raise RuntimeError('Une entrée de la projection a changé pendant le rejeu.')
        if any(guard.sha256(output / 'copie' / file) != digest
               for file, digest in receipt['inputs_sha256'].items()):
            raise RuntimeError('La copie de mesure FreeCAD a été modifiée.')
    load_helper(BANC).publish_json(output / 'connector_native.json', {
        **observed, **integrity, 'inputs_sha256': before,
        'native_receipt_sha256': guard.sha256(output / 'copie/experiment.json'),
        'freecad_returncode': execution.returncode})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--freecad', type=Path)
    parser.add_argument('--reconciliation', type=Path, default=RECONCILIATION)
    parser.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    output = guard.inside(PROJECT / '.runtime', args.output)
    if args.worker:
        observations(output)
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(0)
    if args.freecad is None:
        parser.error('--freecad est requis.')
    output.mkdir(parents=True, exist_ok=False)
    run(output, args.freecad.resolve(), args.reconciliation.resolve())


if __name__ == '__main__':
    main()
