"""Apply an admitted V3 mutation job to one strictly private FreeCAD document."""

from __future__ import annotations

import argparse
import hashlib
import math
import os
from pathlib import Path, PurePosixPath
import re
import sys
import traceback
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from electromechanical_engine import freecad_worker as native
from electromechanical_engine.contracts import decode
from electromechanical_engine.freecad import PROJECT, guard
from electromechanical_engine.v3_native import serialized_dependencies, target_placement
from electromechanical_engine.xlink_native import publish


App, Part = native.App, native.Part
PLACEMENT_TOLERANCE = 1e-6
LINK = 'App::Link'
GROUPS = {'App::Part', 'App::DocumentObjectGroup'}
NATIVE_NAME = re.compile(r'[A-Za-z_][A-Za-z0-9_]*\Z')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def numeric(value, name, minimum, maximum):
    require(type(value) in (int, float) and math.isfinite(value) and minimum <= value <= maximum,
            f'{name} hors domaine [{minimum}, {maximum}].')
    return float(value)


def vector(value, name):
    require(isinstance(value, (list, tuple)) and len(value) == 3, f'Vecteur invalide : {name}.')
    return App.Vector(*(numeric(item, name, -1e6, 1e6) for item in value))


def pose(value):
    require(set(value) == {'translation_mm', 'rotation_xyzw'}, 'Placement typé invalide.')
    values = value['rotation_xyzw']
    require(len(values) == 4, 'Quaternion XYZW attendu.')
    quat = [numeric(item, 'quaternion XYZW', -1, 1) for item in values]
    require(abs(sum(item * item for item in quat) - 1) <= 1e-8, 'Quaternion non unitaire.')
    return App.Placement(vector(value['translation_mm'], 'translation'), App.Rotation(*quat))


def describe_pose(matrix):
    placement = App.Placement(matrix)
    return {'matrix': list(matrix.A), 'translation_mm': list(placement.Base),
            'rotation_xyzw': list(placement.Rotation.Q)}


def equal_matrix(left, right):
    return max(abs(a - b) for a, b in zip(left.A, right.A, strict=True)) <= PLACEMENT_TOLERANCE


def canonical_file(root, name):
    path = PurePosixPath(name)
    require(path.as_posix() == name and not {'..', '.'}.intersection(path.parts)
            and not any(token in name for token in ('\\', ':', '\x00')),
            f'Chemin de document non canonique : {name}.')
    file = guard.relative_file(root, name)
    require(file == root / path and file.stat().st_nlink == 1 and file.suffix.lower() == '.fcstd',
            f'Document redirigé, partagé ou de type invalide : {name}.')
    return file


def verify_closure(root, entry, dependencies):
    require(entry in dependencies and 0 < len(dependencies) <= 200, 'Fermeture du job invalide.')
    files = {path: canonical_file(root, path) for path in dependencies}
    resolved = guard.dependencies(root, [entry])
    require(set(resolved) == set(files.values()), 'Fermeture XLink hors du manifeste du job.')
    # V3-A also checks non-XLink external file properties and references to
    # embedded resources before FreeCAD can restore any document proxy.
    _, _, unresolved, _, _ = serialized_dependencies(root, files)
    require(not unresolved, f'Cibles XLink sérialisées introuvables : {unresolved}.')
    return {path: guard.sha256(file) for path, file in files.items()}


class Assembly:
    def __init__(self, document, occurrences):
        self.document = document
        self.occurrences = occurrences

    def chain(self, ident):
        names = self.occurrences[ident].split('/')
        require(all(NATIVE_NAME.fullmatch(name) for name in names), f'Chemin natif invalide : {ident}.')
        return names

    def resolve(self, names):
        if not names:
            return None, App.Matrix()
        top = self.document.getObject(names[0])
        require(top is not None, f'Racine native absente : {names[0]}.')
        subname = ''.join(item + '.' for item in names[1:])
        obj, matrix = top.getSubObject(subname, 1, App.Matrix(), True)
        require(obj is not None, f'Occurrence native absente : {"/".join(names)}.')
        return obj, matrix

    def occurrence(self, ident):
        return self.resolve(self.chain(ident))[0]

    def native_definition(self, obj):
        return obj.getLinkedObject(True) if obj.TypeId == LINK else obj

    def world(self, ident):
        obj, matrix = self.resolve(self.chain(ident))
        if obj.TypeId == LINK:
            require(obj.ElementCount == 0 and max(abs(value - 1) for value in obj.ScaleVector) <= 1e-9,
                    f'Lien matriciel ou échelle non rigide hors périmètre : {ident}.')
            matrix = matrix.multiply(target_placement(obj, App))
        return matrix

    def parent(self, ident):
        names = self.chain(ident)[:-1]
        for length in range(1, len(names) + 1):
            parent, _ = self.resolve(names[:length])
            require(parent.Document == self.document and parent.TypeId in GROUPS,
                    f'Parent non modifiable ou définition réutilisée : {ident}.')
            self.assert_unshared(parent, ident)
        return self.resolve(names)

    def assert_unshared(self, obj, ident):
        require(not any(link.TypeId == LINK and self.native_definition(link) == obj for link in obj.InList),
                f'Définition partagée non modifiable : {ident}.')

    def writable(self, ident):
        self.parent(ident)
        obj = self.occurrence(ident)
        require(obj.Document == self.document and obj.TypeId != 'App::LinkElement',
                f'Occurrence non possédée par le document de transaction : {ident}.')
        self.assert_unshared(obj, ident)
        return obj

    def set_world(self, ident, desired):
        obj = self.writable(ident)
        _, parent = self.parent(ident)
        local = parent.inverse().multiply(desired)
        if obj.TypeId == LINK:
            # The effective pose includes the definition pose when the link
            # explicitly asks for it. Edit the occurrence, never the target.
            self.world(ident)
            obj.LinkPlacement = App.Placement(local.multiply(target_placement(obj, App).inverse()))
        else:
            require(hasattr(obj, 'Placement') and getattr(obj, 'MapMode', 'Deactivated') == 'Deactivated',
                    f'Placement local absent ou piloté par une attache : {ident}.')
            obj.Placement = App.Placement(local)
        require(equal_matrix(self.world(ident), desired), f'Placement natif réalisé différent : {ident}.')

    def add(self, type_id, ident):
        parent, _ = self.parent(ident)
        return self.add_in_parent(type_id, self.chain(ident)[-1], parent)

    def add_in_parent(self, type_id, name, parent):
        require(self.document.getObject(name) is None, f'Création sur un nom natif occupé : {name}.')
        obj = self.document.addObject(type_id, name)
        if parent is not None:
            parent.addObject(obj)
        require(obj.Name == name, f'Nom FreeCAD alloué différent : {name}.')
        return obj

    def snapshot(self, ident, expectation):
        names = self.chain(ident)
        if self.document.getObject(names[-1]) is None:
            require(expectation == {'exists': False}, f'Occurrence attendue absente : {ident}.')
            return {'exists': False}
        obj, _ = self.resolve(names)
        matrix = self.world(ident)
        evidence = {'exists': True, 'object': obj.Name, 'type': obj.TypeId, **describe_pose(matrix)}
        require(set(expectation) <= {'exists', 'placement', 'points_mm', 'shape_sha256'},
                f'State attendu non pris en charge : {ident}.')
        if 'exists' in expectation:
            require(expectation['exists'] is True, f'Occurrence attendue absente mais présente : {ident}.')
        if 'placement' in expectation:
            require(equal_matrix(matrix, pose(expectation['placement']).toMatrix()),
                    f'État attendu de placement divergent : {ident}.')
        definition = self.native_definition(obj)
        if hasattr(definition, 'Shape') and not definition.Shape.isNull():
            top = self.document.getObject(names[0])
            subname = ''.join(item + '.' for item in names[1:])
            shape = Part.getShape(top, subname)
            evidence.update(shape_sha256=native.geometry.shape_sha256(shape), bounds_mm=native.bounds(shape))
        if 'shape_sha256' in expectation:
            require(evidence.get('shape_sha256') == expectation['shape_sha256'], f'BRep différent : {ident}.')
        if is_native_cable(definition):
            cable_to_world = matrix.multiply(definition.Placement.inverse().toMatrix())
            route_to_world = cable_to_world.multiply(definition.Base.getGlobalPlacement().toMatrix())
            points = [route_to_world.multVec(point) for point in definition.Base.Points]
            evidence.update(points_mm=[list(point) for point in points],
                            wire=definition.Base.Name, cable=definition.Name)
        if 'points_mm' in expectation:
            expected = expectation['points_mm']
            require('points_mm' in evidence and len(points) == len(expected)
                    and all((point - vector(value, 'point attendu')).Length <= PLACEMENT_TOLERANCE
                            for point, value in zip(points, expected)), f'Points natifs différents : {ident}.')
        return evidence


def recompute(document):
    result = document.recompute()
    require(result is not False and result >= 0, 'Échec de recalcul de la transaction FreeCAD.')
    invalid = [obj.Name for obj in document.Objects if {'Invalid', 'Error'} & set(obj.State)]
    require(not invalid, f'Objets natifs invalides : {invalid}.')


def reposition(assembly, action, model):
    ident, parameters = action['occurrence'], action['parameters']
    frame = parameters['frame']
    require(frame in ('ROOT', 'PARENT'), f'Repère de pose non pris en charge : {frame}.')
    desired = pose(parameters['placement']).toMatrix()
    if frame == 'PARENT':
        _, parent = assembly.parent(ident)
        desired = parent.multiply(desired)
    before = assembly.world(ident)
    require(not equal_matrix(before, desired), f'La pose ne modifie pas l’occurrence : {ident}.')
    delta = desired.multiply(before.inverse())
    companions = model.get('moving_with', {}).get(ident, [])
    require(len(set(companions)) == len(companions) and ident not in companions,
            f'Associations de volumes de service ambiguës : {ident}.')
    companion_poses = {name: assembly.world(name) for name in companions}
    assembly.set_world(ident, desired)
    for name, previous in companion_poses.items():
        assembly.set_world(name, delta.multiply(previous))
    return {'moved': [ident, *companions]}


def is_native_cable(obj):
    return type(getattr(obj, 'Proxy', None)).__name__ == 'ArchCable'


def set_native_link(obj, property_name, target, plural=False, across_groups=False):
    type_name = 'App::PropertyLinkList' if plural else 'App::PropertyLink'
    if across_groups:
        type_name += 'Global'
    if property_name not in obj.PropertiesList:
        obj.addProperty(type_name, property_name, 'V3 B.1')
    require(obj.getTypeIdOfProperty(property_name) == type_name, f'Lien natif incompatible : {property_name}.')
    setattr(obj, property_name, target)


def update_route(assembly, ident, cable, points, diameter, radius):
    route = cable.Base
    require(route.Document == assembly.document and type(getattr(route, 'Proxy', None)).__name__ == 'WireFlex',
            f'Base WireFlex privée requise : {ident}.')
    require({client.Name for client in route.InList if is_native_cable(client)} == {cable.Name},
            f'Parcours partagé entre plusieurs câbles : {ident}.')
    require(not route.Vrtxs_mid, f'Attaches intermédiaires préexistantes hors périmètre : {ident}.')
    profile = cable.ProfilExterieur
    if abs(profile.DiametreExterieur.Value - diameter) > 1e-8:
        require(profile.Document == assembly.document and set(profile.InList) == {cable},
                f'Modification d’un profil partagé ou externe : {ident}.')
        profile.DiametreExterieur = diameter
    cable_to_world = assembly.world(ident).multiply(cable.Placement.inverse().toMatrix())
    route_to_world = cable_to_world.multiply(route.getGlobalPlacement().toMatrix())
    inverse = route_to_world.inverse()
    route.PathType = 'Wire'
    route.Points = [inverse.multVec(point) for point in points]
    route.FilletRadius = radius
    cable.BaseWireFilletRadius = radius
    return route


def replace_linked_reservation(assembly, ident, link, points, diameter, radius, model):
    definition = assembly.native_definition(link)
    require(link.TypeId == LINK and not is_native_cable(definition),
            f'Un câble natif partagé nécessite une autorité de subdivision explicite : {ident}.')
    _, parent = assembly.parent(ident)
    inverse = parent.inverse()
    cable, route = native.builder.make_native_cable(
        assembly.document, None, 'B1_Cable_' + link.Name,
        [inverse.multVec(point) for point in points], diameter, radius)
    link.setLink(cable)
    link.LinkPlacement = App.Placement()
    # The workspace copy has one physical occurrence of this cable, the link.
    cable.Visibility = False
    link.Visibility = True
    provenance = model.get('route_links', {}).get(ident)
    if provenance is not None:
        for edge, prop in (('start', 'Vrtx_start'), ('end', 'Vrtx_end')):
            setattr(route, prop, (assembly.occurrence(provenance[edge]), 'Vertex1'))
        set_native_link(cable, 'L2Conductors', [assembly.occurrence(key) for key in provenance['conductors']], True)
    return cable, route


def port_datums(assembly, ident, model):
    rules = model.get('validation', {})
    ports = [rules['ports'][name] for name in rules.get('routes', {}).get(ident, {}).get('ports', [])]
    if not any('datum' in port for port in ports):
        return []
    require(len(ports) == 2 and all('datum' in port for port in ports),
            'Deux repères natifs indépendants sont requis pour le couplage.')
    observations = []
    for port in ports:
        owner_id, datum_name = port['equipment'], port['datum']
        require(NATIVE_NAME.fullmatch(datum_name), f'Nom de repère de port invalide : {datum_name}.')
        owner = assembly.occurrence(owner_id)
        definition = assembly.native_definition(owner)
        if definition.TypeId == 'App::Part':
            datum, measured = assembly.resolve([*assembly.chain(owner_id), datum_name])
            require(datum in definition.Group and datum.MapMode == 'Deactivated' and not datum.AttachmentSupport,
                    f'Repère {datum_name} sans placement rigide dans la définition.')
        else:
            datum, measured = assembly.resolve([datum_name])
            require(owner == definition and datum.MapMode == 'ObjectXY' and
                    datum.AttachmentSupport == [(owner, ('',))],
                    f'Repère {datum_name} sans attache rigide à son équipement.')
        require(datum.TypeId == 'PartDesign::CoordinateSystem', f'Repère de port natif requis : {datum_name}.')
        expected = assembly.world(owner_id).multiply(pose(port['local_pose']).toMatrix())
        require(equal_matrix(measured, expected), f'Pose locale scellée divergente : {datum_name}.')
        terminal_path = assembly.occurrences.get(port['frame'], port['frame']).split('/')
        require(all(NATIVE_NAME.fullmatch(name) for name in terminal_path), 'Chemin de terminaison invalide.')
        terminal, attachment_pose = assembly.resolve(terminal_path)
        require(terminal != datum and equal_matrix(measured, attachment_pose),
                f'Terminaison WireFlex divergente du repère natif : {datum_name}.')
        placement = App.Placement(measured)
        normal = placement.Rotation.multVec(vector(port['outward_local'], 'normale de port'))
        tangent = placement.Rotation.multVec(vector(port.get('tangent_local', port['outward_local']),
                                                     'tangente de sortie locale'))
        require(abs(normal.Length - 1) <= 1e-8 and abs(tangent.Length - 1) <= 1e-8,
                f'Normale ou tangente de port non unitaire : {datum_name}.')
        observations.append({'datum': datum_name, 'matrix': list(measured.A), 'origin': placement.Base,
                             'normal': normal, 'tangent': tangent, 'terminal': terminal})
    return observations


def reroute(assembly, action, model):
    ident, parameters = action['occurrence'], action['parameters']
    require(parameters['frame'] == 'ROOT', 'Le parcours doit être donné dans le repère ROOT.')
    require(2 <= len(parameters['points_mm']) <= 256, 'Nombre de points de parcours hors domaine.')
    points = [vector(point, 'point de parcours') for point in parameters['points_mm']]
    require(all((one - two).Length > 1e-5 for i, one in enumerate(points) for two in points[i + 1:]),
            'Deux points du parcours sont confondus.')
    diameter = numeric(parameters['diameter_mm'], 'diamètre extérieur', 1e-3, 1e3)
    radius = numeric(parameters['bend_radius_mm'], 'rayon de fillet', 1e-3, 1e4)
    minimum = numeric(parameters['minimum_radius_mm'], 'rayon minimal', 1e-3, 1e4)
    sections = parameters.get('conductor_sections_mm2')
    if sections is None:
        sections = [parameters['conductor_section_mm2']]
    require(0 < len(sections) <= 128, 'Nombre de sections de conducteurs hors domaine.')
    sections = [numeric(section, 'section du conducteur', 1e-6, 1e6) for section in sections]
    require(sum(sections) < math.pi * diameter ** 2 / 4, 'Somme des sections hors du profil extérieur.')
    start_axis = vector(parameters['start_axis'], 'axe de sortie début')
    end_axis = vector(parameters['end_axis'], 'axe de sortie fin')
    require(abs(start_axis.Length - 1) <= 1e-8 and abs(end_axis.Length - 1) <= 1e-8,
            'Les deux tangentes signées doivent être unitaires.')
    ports = port_datums(assembly, ident, model)
    for index, axis, port in zip((0, -1), (start_axis, end_axis), ports):
        require((points[index] - port['origin']).Length <= PLACEMENT_TOLERANCE
                and (axis - port['tangent']).Length <= PLACEMENT_TOLERANCE,
                f'Extrémité ou axe déclaré divergent du port natif : {port["datum"]}.')
        points[index] = port['origin']
    if ports:
        start_axis, end_axis = (port['tangent'] for port in ports)
    native.builder._check_polyline(points, diameter, radius)
    occurrence = assembly.writable(ident)
    if is_native_cable(occurrence):
        cable = occurrence
        route = update_route(assembly, ident, cable, points, diameter, radius)
    else:
        require(occurrence.TypeId == LINK, f'Réservation XLink ou câble natif requis : {ident}.')
        cable, route = replace_linked_reservation(assembly, ident, occurrence, points, diameter, radius, model)
    for name, port in zip(('Vrtx_start', 'Vrtx_end'), ports):
        binding = getattr(route, name, None)
        require(binding and binding[0] == port['terminal'] and list(binding[1]) == ['Vertex1'],
                f'Attache WireFlex étrangère au port : {port["datum"]}.')
    conductors = getattr(cable, 'L2Conductors', [])
    require(not conductors or len(conductors) == len(sections), 'Sections et conducteurs natifs en nombre différent.')
    if 'B1_ConductorSections' not in cable.PropertiesList:
        cable.addProperty('App::PropertyFloatList', 'B1_ConductorSections', 'V3 B.1',
                          'Sections déclarées des conducteurs, dans l’ordre de la liste native, en mm².')
    cable.B1_ConductorSections = sections
    fresh = native.geometry.rebuild_cable_in_isolated_document(assembly.document, cable)
    require(fresh['status'] == 'pass', f'Échec de régénération native du câble : {fresh}.')
    actual_diameter = float(cable.ProfilExterieur.DiametreExterieur.Value)
    require(abs(actual_diameter - diameter) <= 1e-8, 'Diamètre réellement généré différent du plan.')
    cable_to_world = assembly.world(ident).multiply(cable.Placement.inverse().toMatrix())
    wire = native.builder.effective_wire(cable).transformShape(cable_to_world, True, True)
    check = native.geometry.inspect_route(wire, minimum, start_axis, end_axis,
                                          start_position=points[0], end_position=points[-1])
    result = {'path': route.Name, 'cable': cable.Name, 'fresh_solid': fresh, 'route_diagnostic': check,
              'diameter_mm': actual_diameter, 'conductor_sections_mm2': sections}
    if ports:
        result['native_ports'] = [
            {'datum': port['datum'], 'matrix': port['matrix'], 'origin_mm': list(port['origin']),
             'normal': list(port['normal']), 'outward': list(port['tangent']), 'attachment': port['terminal'].Name}
            for port in ports
        ]
    return result


def support_links(assembly, support, params, fasteners):
    for field, prop in (('anchor', 'B1_Anchor'), ('carrier', 'B1_Carrier')):
        set_native_link(support, prop, assembly.occurrence(params[field]))
    set_native_link(support, 'B1_Retains', [assembly.occurrence(name) for name in params['retains']],
                    plural=True, across_groups=True)
    set_native_link(support, 'B1_Fasteners', fasteners, True)


def relocate(assembly, action, _model):
    ident, params = action['occurrence'], action['parameters']
    support = assembly.writable(ident)
    target = assembly.world(params['anchor']).multiply(pose(params['placement']).toMatrix())
    before = assembly.world(ident)
    require(not equal_matrix(before, target), 'La relocalisation doit modifier la pose du support.')
    fastener_ids = params.get('fasteners', [])
    fasteners = [assembly.writable(name) for name in fastener_ids]
    existing_fasteners = getattr(support, 'B1_Fasteners', [])
    require(not existing_fasteners or existing_fasteners == fasteners, 'Liste des fixations changée par relocalisation.')
    delta = target.multiply(before.inverse())
    for name in fastener_ids:
        assembly.set_world(name, delta.multiply(assembly.world(name)))
    assembly.set_world(ident, target)
    support_links(assembly, support, params, fasteners)
    return {'support': support.Name, 'anchor': params['anchor'], 'carrier': params['carrier'],
            'fasteners': fastener_ids, 'retains': params['retains']}


def create_plate(assembly, action, _model):
    params = action['parameters']
    ident = params['support']
    require(params['anchor'] == action['occurrence'], 'La cible du plan de création doit être l’ancrage.')
    size = vector(params['size_mm'], 'dimensions de platine')
    require(min(size) >= 0.5 and max(size) <= 500, 'Dimensions de platine hors domaine.')
    require(1 <= len(params['fasteners']) <= 8, 'Une platine requiert une à huit fixations.')
    length, width, thickness = size
    target = assembly.world(params['anchor']).multiply(pose(params['placement']).toMatrix())
    support = assembly.add('Part::Cut', ident)
    document = assembly.document
    parent, _ = assembly.parent(ident)
    plate = assembly.add_in_parent('Part::Box', support.Name + '_Blank', parent)
    plate.Length, plate.Width, plate.Height = length, width, thickness
    holes, fasteners, centres = [], [], []
    for index, spec in enumerate(params['fasteners'], 1):
        x, y = spec['center_mm']
        x, y = numeric(x, 'position X de fixation', 0, length), numeric(y, 'position Y de fixation', 0, width)
        hole_diameter = numeric(spec['hole_diameter_mm'], 'diamètre de trou', 0.1, min(length, width))
        shank_diameter = numeric(spec['diameter_mm'], 'diamètre de fixation', 0.1, hole_diameter)
        embed = numeric(spec['embed_mm'], 'engagement de fixation', 0.1, 50)
        hole_radius = hole_diameter / 2
        require(min(x, y, length - x, width - y) > hole_radius + 0.1, 'Trou débouchant du bord de platine.')
        require(all(math.hypot(x - cx, y - cy) > hole_radius + cr + 0.1 for cx, cy, cr in centres),
                'Trous de fixation de platine qui se recouvrent.')
        centres.append((x, y, hole_radius))
        hole = assembly.add_in_parent('Part::Cylinder', f'{support.Name}_Hole{index}', parent)
        hole.Radius, hole.Height = hole_radius, thickness + 2
        hole.Placement.Base = App.Vector(x, y, -1)
        holes.append(hole)
        offset = App.Placement(App.Vector(x, y, -embed), App.Rotation())
        stud = assembly.add('Part::Cylinder', spec['id'])
        stud.Radius, stud.Height = shank_diameter / 2, embed + thickness
        assembly.set_world(spec['id'], target.multiply(offset.toMatrix()))
        fasteners.append(stud)
    tool = assembly.add_in_parent('Part::Compound', support.Name + '_Holes', parent)
    tool.Links = holes
    support.Base, support.Tool = plate, tool
    recompute(document)
    assembly.set_world(ident, target)
    support_links(assembly, support, params, fasteners)
    for item in [plate, tool, *holes]:
        item.Visibility = False
    support.Visibility = True
    recompute(document)
    solid = native.geometry.inspect_solid(support.Shape)
    require(solid['status'] == 'pass', f'Le solide paramétrique de la platine est invalide : {solid}.')
    return {'support': support.Name, 'anchor': params['anchor'], 'carrier': params['carrier'],
            'fasteners': [spec['id'] for spec in params['fasteners']], 'retains': params['retains'], 'solid': solid}


OPERATORS = {'REPOSITION_DEVICE': reposition, 'REROUTE_HARNESS': reroute,
             'RELOCATE_SUPPORT': relocate, 'CREATE_SUPPORT': create_plate}


def subject(action):
    return action['parameters']['support'] if action['operation'] == 'CREATE_SUPPORT' else action['occurrence']


def mutate(root, job, report):
    entry, dependencies = job['entry'], job['dependencies']
    model, actions = job['model'], job['actions']
    require(0 < len(actions) <= 32, 'Nombre d’opérations hors domaine.')
    require(all(action['operation'] in OPERATORS for action in actions), 'Opérateur natif non pris en charge.')
    before = verify_closure(root, entry, dependencies)
    require(before == dependencies, 'Fichiers natifs préparés différents des SHA admis.')
    report.update(entry=entry, before_sha256=before)
    report['environment'] = {'FreeCAD': '.'.join(App.Version()[:3]), 'OCCT': Part.OCC_VERSION,
                             'Python': sys.version, 'Cables': native.cables_environment(gui=True)}
    report['native_helpers_sha256'] = {
        Path(module.__file__).relative_to(PROJECT).as_posix(): guard.sha256(module.__file__)
        for module in (native, native.builder, native.geometry, guard)
    }
    document = App.openDocument(str(root / entry))
    native.complete_dependencies(document, root)
    documents, _ = native.recalculate(document, root)
    opened = sorted(guard.inside(root, item.FileName).relative_to(root).as_posix() for item in documents)
    require(opened == sorted(dependencies), 'Les documents effectivement ouverts diffèrent du manifeste.')
    report['opened'] = opened
    for item in documents:
        require(not item.Partial and not any({'Invalid', 'Error'} & set(obj.State) for obj in item.Objects),
                f'Document de référence partiel ou invalide : {item.Name}.')
    assembly = Assembly(document, model['occurrences'])
    rows = report['operations']
    for action in actions:
        ident = subject(action)
        rows.append({'id': action['id'], 'operation': action['operation'], 'occurrence': ident,
                     'before': assembly.snapshot(ident, action['expected_before']), 'status': 'NOT_RUN'})
    document.openTransaction('V3 B.1')
    committed = False
    try:
        for row, action in zip(rows, actions, strict=True):
            row['status'] = 'STARTED'
            row['effect'] = OPERATORS[action['operation']](assembly, action, model)
            recompute(document)
            row['status'] = 'APPLIED_IN_MEMORY'
        for row, action in zip(rows, actions, strict=True):
            row['after'] = assembly.snapshot(subject(action), action['expected_after'])
            previous, current = row['before'], row['after']
            require(any(previous.get(key) != current.get(key) for key in ('matrix', 'shape_sha256')),
                    f'Aucun placement ni BRep modifié : {row["occurrence"]}.')
        require(verify_closure(root, entry, dependencies) == before,
                'Une copie d’entrée a changé avant la sauvegarde.')
        document.commitTransaction()
        committed = True
        report['memory_transaction'] = 'COMMITTED'
        document.save()
        after = verify_closure(root, entry, dependencies)
        require(before[entry] != after[entry] and all(after[key] == sha for key, sha in before.items() if key != entry),
                'Sauvegarde absente ou modification inattendue d’une dépendance privée.')
        report.update(after_sha256=after, save_performed=True)
        for row in rows:
            row['status'] = 'SAVED'
    finally:
        if not committed:
            document.abortTransaction()
            report['memory_transaction'] = 'ABORTED'


def private_path(path):
    absolute = path.absolute()
    safe = guard.inside(PROJECT, absolute)
    require(safe == absolute and safe.relative_to(PROJECT).parts[0] in ('.runtime', 'results'),
            f'Chemin hors périmètre de travail privé : {path}.')
    for parent in (safe, *safe.parents):
        if parent == PROJECT:
            break
        require(not parent.is_symlink() and not getattr(parent, 'is_junction', lambda: False)(),
                f'Chemin de travail redirigé : {parent}.')
    return safe


def close_all():
    names = list(App.listDocuments())
    for name in names:
        if name in App.listDocuments():
            App.closeDocument(name)
    return not App.listDocuments()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--job', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    root, job_path, output = map(private_path, (args.root, args.job, args.output))
    require(root.is_dir() and job_path.is_file() and job_path.stat().st_nlink == 1
            and output.parent.is_dir() and not output.exists()
            and not job_path.is_relative_to(root) and not output.is_relative_to(root),
            'Chemins d’entrée/sortie natifs incompatibles.')
    source = job_path.read_bytes()
    digest = hashlib.sha256(source).hexdigest()
    report = {'schema': 'v3.b1.native_build/1', 'finalized': False, 'status': 'INCONCLUSIVE',
              'job_sha256': digest, 'pid': os.getpid(), 'worker_id': uuid4().hex,
              'builder_sha256': guard.sha256(__file__), 'save_performed': False,
              'memory_transaction': 'NOT_STARTED', 'operations': []}
    code = 1
    try:
        job = decode(job_path.name, source)
        report['plan_id'] = job['plan_id']
        mutate(root, job, report)
        require(guard.sha256(job_path) == digest, 'Le job natif a changé pendant la mutation.')
        report.update(finalized=True, status='PASS')
        code = 0
    except (AttributeError, KeyError, Part.OCCError, RuntimeError, TypeError, ValueError) as error:
        report.update(finalized=True, status='FAIL', reason=str(error))
        traceback.print_exc()
        code = 2
    finally:
        report['documents_closed'] = close_all()
        if not report['documents_closed']:
            report.update(finalized=False, status='INCONCLUSIVE', reason='Documents natifs encore ouverts.')
            code = 1
        publish(output, report)
    sys.stdout.flush()
    sys.stderr.flush()
    # FreeCAD may deadlock during offscreen Qt shutdown after all files close.
    os._exit(code)


if __name__ == '__main__':
    main()
