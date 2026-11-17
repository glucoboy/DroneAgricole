"""Adaptateur de CAO. Les hypothèses d'architecture sont dans les JSON voisins."""
from pathlib import Path
import hashlib
import json
import math
import os
import sys
import traceback

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
COPY = ROOT / 'hardware/mecanique/cartographe_faisceaux_refonte'
BASE = ROOT / 'hardware/mecanique/cartographe_faisceaux_autonome'
OLD = HERE.parent / 'reconstruction_faisceaux'
RUN = ROOT / '.runtime/refonte-faisceaux'
ENTRY = 'assemblages/Prototype_Cartographe.FCStd'
SA = 'sous_assemblages/SA07_Prototype_Faisceaux.FCStd'
BUILD = 'verification/construction_prototype.json'
ROUTES = 'verification/routes_prototype.json'
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path[:0] = [str(COPY / 'verification'),
                str(ROOT / '.agents/skills/electromechanical-integration/scripts')]

import FreeCAD as App
import Part
import FreeCADGui as Gui
from cable_workbench_prototype import bootstrap_paths, make_native_cable, cable_geometry
from freecad_geometry import inspect_route, rebuild_cable_in_isolated_document
from read_brep_prototype import Reader
from workspace_guard import dependencies, verify_sources


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    temp.replace(path)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(ok, why):
    if not ok:
        raise RuntimeError(why)


def boot():
    Gui.showMainWindow()
    Gui.getMainWindow().hide()
    version = bootstrap_paths()
    require(version['freecad'][:3] == ['1','1','3'] and version['version'] == '0.3.7', str(version))
    return version


def add(obj, kind, name, value):
    if name not in obj.PropertiesList:
        obj.addProperty('App::Property' + kind, name, 'Architecture des faisceaux')
    setattr(obj, name, value)


def point(vector):
    return list(vector)


def frame(spec):
    a, b = (App.Vector(*p) for p in spec['axes_bords_mm'])
    z = App.Vector(*spec['direction']).normalize()
    x = (b - a).normalize()
    require(abs(x.dot(z)) < 1e-8, 'Section oblique au trajet')
    return App.Placement(a, App.Rotation(x, z.cross(x), z, 'ZXY')), (b-a).Length


def capsule(doc, name, path, placement, span, outside):
    radius = path.Name + '.RayonInterieur' + (' + ' + path.Name + '.Paroi' if outside else '')
    objects = []
    for index, x in enumerate((0, span)):
        end = doc.addObject('Part::Cylinder', name + 'Bout' + str(index))
        end.Placement = placement.multiply(App.Placement(App.Vector(x,0,0), App.Rotation()))
        end.setExpression('Radius', radius)
        end.setExpression('Height', path.Name + '.Length')
        objects.append(end)
    rect = doc.addObject('Part::Box', name + 'Pont')
    nominal_radius = path.RayonInterieur.Value + (path.Paroi.Value if outside else 0)
    rect.Placement = placement.multiply(App.Placement(App.Vector(0,-nominal_radius,0), App.Rotation()))
    # Le rectangle suit la valeur du rayon même après édition. La rotation
    # initiale transforme le décalage selon la normale locale de la capsule.
    transverse = placement.Rotation.multVec(App.Vector(0,1,0))
    for axis, origin, normal in zip('xyz', placement.Base, transverse):
        rect.setExpression('Placement.Base.' + axis, f'{origin:.12g} mm - ({radius}) * {normal:.12g}')
    rect.setExpression('Length', path.Name + '.Entraxe')
    rect.setExpression('Width', '2 * (' + radius + ')')
    rect.setExpression('Height', path.Name + '.Length')
    objects.append(rect)
    fuse = doc.addObject('Part::MultiFuse', name)
    fuse.Shapes = objects
    fuse.Refine = True
    return fuse


def make_sleeve(doc, spec, prefix=''):
    from freecad.cables import wireFlex

    App.setActiveDocument(doc.Name)
    placement, span = frame(spec)
    start = placement.multVec(App.Vector(span / 2, 0, 0))
    finish = placement.multVec(App.Vector(span / 2, 0, spec['longueur_mm']))
    path = wireFlex.make_wireflex_from_vectors([start, finish])
    path.Label = prefix + 'Axe de référence du tronçon commun'
    add(path, 'Length', 'LongueurTroncon', spec['longueur_mm'])
    add(path, 'Length', 'RayonInterieur', spec['rayon_interieur_mm'])
    add(path, 'Length', 'Entraxe', span)
    add(path, 'Length', 'Paroi', spec['paroi_mm'])
    # La ligne médiane est une vue du dimensionnement de la gaine, pas un
    # parcours de câble partagé. Les centres des câbles restent distincts.
    outer = capsule(doc, prefix + 'Exterieur', path, placement, span, True)
    inner = capsule(doc, prefix + 'Interieur', path, placement, span, False)
    wall = doc.addObject('Part::Cut', prefix + 'Protection')
    wall.Base = outer
    wall.Tool = inner
    wall.Refine = True
    wall.Label = spec['occurrence'] + ' · paroi candidate'
    add(wall, 'Link', 'AxeReference', path)
    add(wall, 'StringList', 'ParcoursCouverts', spec['membres'])
    add(wall, 'String', 'Limites', 'Enveloppe textile ouvrable candidate. Couture, tolérances et tenue en service à vérifier.')
    require(doc.recompute() and fresh_solid(wall.Shape), 'Paroi native non générée')
    if not prefix:
        radius = spec['rayon_interieur_mm'] + spec['paroi_mm'] + 0.4
        window = doc.addObject('Part::Box', 'FenetreLocale')
        window.Length = span + 2*radius
        window.Width = 2*radius
        window.Height = spec['longueur_mm']
        window.Placement = placement.multiply(App.Placement(App.Vector(-radius,-radius,0), App.Rotation()))
        add(wall, 'Link', 'FenetreControle', window)
        require(doc.recompute(), 'Fenêtre de contrôle native non générée')
        for obj in doc.Objects:
            obj.Visibility = obj == wall
        wall.ViewObject.ShapeColor = (0.15, 0.72, 0.42)
    return wall, inner


def fresh_solid(shape):
    return (not shape.isNull() and shape.isValid() and len(shape.Solids) == 1
            and math.isfinite(shape.Volume) and shape.Volume > 0)


def intersects_bbox(a, b, tolerance=1e-7):
    return all(getattr(a, k+'Min') <= getattr(b, k+'Max') + tolerance
               and getattr(b, k+'Min') <= getattr(a, k+'Max') + tolerance for k in 'XYZ')


def common(a, b):
    if not intersects_bbox(a.BoundBox, b.BoundBox):
        return 0.0
    result = a.common(b)
    require(result.isNull() or result.isValid(), 'BRep commun invalide')
    require(math.isfinite(result.Volume), 'BRep commun non fini')
    return result.Volume


def check_pairs(target, obstacles, tolerance):
    contacts, errors = [], []
    screened = 0
    for key, shape in obstacles.items():
        if not intersects_bbox(target.BoundBox, shape.BoundBox):
            continue
        screened += 1
        try:
            volume = sum(common(target, solid) for solid in shape.Solids)
            if volume > tolerance:
                contacts.append({'occurrence': key, 'volume_mm3': volume})
        except Exception as error:
            errors.append({'occurrence': key, 'error': str(error)})
    return {'obstacles': len(obstacles), 'aabb_candidates': screened, 'recouvrements': contacts, 'inconnues': errors}


def scene(root):
    reader = Reader(root)
    construction = read(root / BUILD)
    shapes = {}
    for row in construction['occurrences']:
        parent = row['parent']
        if parent.startswith('sous_assemblages/'):
            shapes[(parent, row['occurrence'])] = reader.occurrence(row)
    routes = {r['id']: r for r in read(root / ROUTES)['routes']}
    require(len(routes) == 53 and all((SA, key) in shapes for key in routes), 'Bijection routes/occurrences')
    require(all(s.Solids for s in shapes.values()), 'Occurrence sans solide')
    return construction, routes, shapes, reader


def main_points(route, spec):
    points = [p.copy() for p in route['points_mm']]
    delta = main_delta(route['id'], spec)
    for index in (3,4):
        points[index][0] += delta
    return points


def main_delta(cid, spec):
    return spec.get('translations_main_x_mm', {}).get(cid, spec.get('translation_main_x_mm', 0))


def relief_spec(spec, placement):
    direction = App.Vector(*spec['direction']).normalize()
    clearance = spec['degagement_guide_mm']
    inverse = placement.inverse()
    axes = [inverse.multVec(App.Vector(*p) - direction * clearance) for p in spec['axes_bords_mm']]
    return dict(spec, axes_bords_mm=[point(p) for p in axes],
                direction=point(inverse.Rotation.multVec(direction)),
                longueur_mm=spec['longueur_mm'] + 2 * clearance,
                rayon_interieur_mm=spec['rayon_interieur_mm'] + clearance)


def inclusion(spec, inner, wall, shape, diameter, tolerance):
    placement, span = frame(spec)
    length = spec['longueur_mm']
    radius = spec['rayon_interieur_mm'] + spec['paroi_mm'] + 0.4
    # Fenêtre latérale : un autre segment du même câble peut traverser le
    # même intervalle axial loin du corridor (notamment sur NTC1/2).
    window = Part.makeBox(span+2*radius, 2*radius, length, App.Vector(-radius,-radius,0))
    window.Placement = placement.multiply(window.Placement)
    section = shape.common(window)
    require(fresh_solid(section), 'Section locale non identifiée de façon univoque')
    outside = section.cut(inner)
    require(outside.isNull() or outside.isValid(), 'Différence cavité invalide')
    measured = section.Volume
    expected = math.pi * (diameter/2)**2 * length
    penetration = common(section, wall)
    clearance = section.distToShape(wall)[0]
    require(math.isfinite(clearance), 'Distance cavité non finie')
    return {'volume_section_mm3': measured, 'volume_section_droite_mm3': expected,
            'hors_cavite_mm3': outside.Volume, 'paroi_mm3': penetration, 'distance_paroi_mm': clearance,
            'ok': abs(measured-expected) <= tolerance and outside.Volume <= tolerance and penetration <= tolerance}


def trial(spec, routes, shapes, tolerance):
    doc = App.newDocument(spec['id'])
    result = {'id': spec['id'], 'parametres': spec, 'ok': False, 'parcours_modifies': {}}
    try:
        wall, inner = make_sleeve(doc, spec)
        obstacles = {key: shape for key, shape in shapes.items() if key != (SA, spec['occurrence'])}
        replaced = set()
        if spec.get('degagement_guide_mm'):
            guide = (SA, spec['supports'][0])
            relief_doc = App.newDocument(spec['id'] + 'Guide')
            try:
                relief, _ = make_sleeve(relief_doc, relief_spec(spec, App.Placement()))
                old = obstacles[guide]
                new = old.cut(relief.Base.Shape)
                require(fresh_solid(new), 'Guide interrompu ou invalide après ouverture')
                result['guide'] = {'occurrence': guide[1], 'volume_initial_mm3': old.Volume,
                                   'volume_retrait_mm3': old.Volume - new.Volume,
                                   'jeu_candidate_mm': spec['degagement_guide_mm']}
                obstacles[guide] = new
            finally:
                App.closeDocument(relief_doc.Name)
        for cid in spec['membres']:
            if main_delta(cid, spec):
                route = routes[cid]
                pts = main_points(route, spec)
                cable, _ = make_native_cable(doc, None, cid, pts, route['diametre_mm'], route['rayon_courbure_mm'])
                geo = cable_geometry(cable)
                result['parcours_modifies'][cid] = {'points_mm': pts, 'longueur_mm': geo['longueur_courbe_mm'],
                                                     'rayons_mm': geo['rayons_arcs_mm']}
                obstacles[(SA, cid)] = cable.Shape.copy()
                replaced.add((SA, cid))
        for key in replaced:
            checks = check_pairs(obstacles[key], {'#'.join(k): s for k,s in obstacles.items() if k != key}, tolerance)
            result['parcours_modifies'][key[1]]['paires'] = checks
        members = {cid: inclusion(spec, inner.Shape, wall.Shape, obstacles[(SA,cid)], routes[cid]['diametre_mm'], tolerance)
                   for cid in spec['membres']}
        pairs = check_pairs(wall.Shape, {'#'.join(k): s for k,s in obstacles.items()}, tolerance)
        changed_ok = all(not (r['paires']['recouvrements'] or r['paires']['inconnues'])
                         for r in result['parcours_modifies'].values())
        result.update(inclusions=members, paires=pairs, volume_paroi_mm3=wall.Shape.Volume,
                      ok=changed_ok and not (pairs['recouvrements'] or pairs['inconnues']) and all(r['ok'] for r in members.values()))
    except Exception as error:
        result['erreur'] = str(error)
    finally:
        App.closeDocument(doc.Name)
    return result


def try_variants(ids):
    environment = boot()
    cfg = read(HERE / 'variantes.json')
    _, routes, shapes, _ = scene(BASE)
    for spec in cfg['candidats']:
        if not ids or spec['id'] in ids:
            result = trial(spec, routes, shapes, cfg['tolerance_volume_mm3'])
            result.update(environment=environment, source_sha256=sha(BASE / 'experiment.json'),
                          parametres_sha256=sha(HERE / 'variantes.json'), finalized=True)
            write(RUN / (spec['id'] + '.json'), result)
            print(spec['id'], result['ok'], result.get('erreur'), result.get('paires',{}).get('recouvrements'), flush=True)


if __name__ == '__main__':
    try:
        try_variants(sys.argv[1:])
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(0)
    except Exception:
        traceback.print_exc()
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(2)
