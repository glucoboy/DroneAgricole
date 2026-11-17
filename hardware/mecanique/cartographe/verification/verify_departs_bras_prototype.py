"""Passage des bandes de départ et des douze selles, sur natifs sauvegardés.

Sans argument : preuve finale sur construction_prototype.json fraîche.
--candidate : contrôle de la définition des huit départs en mémoire ; seules
les huit lumières P64 sont soustraites en mémoire, aucun natif n'est modifié.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import json
import math
import FreeCAD as A
import Part
from read_brep_prototype import Reader
from prototype_retenues_departs import energy_departure_interfaces, layout
from verify_retenues_faisceaux_prototype import ordered_edges, project

VER = Path(__file__).resolve().parent
MEC = VER.parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def cross(a, b, c):
    return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])


def hull(points):
    points = sorted(set(points)); lower, upper = [], []
    for point in points:
        while len(lower) > 1 and cross(lower[-2], lower[-1], point) <= 0:
            lower.pop()
        lower.append(point)
    for point in reversed(points):
        while len(upper) > 1 and cross(upper[-2], upper[-1], point) <= 0:
            upper.pop()
        upper.append(point)
    return lower[:-1] + upper[:-1]


def offset(poly, amount):
    lines = []
    for a, b in zip(poly, poly[1:]+poly[:1]):
        dy, dz = b[0]-a[0], b[1]-a[1]; length = math.hypot(dy, dz)
        normal = (dz/length, -dy/length)
        lines.append(((a[0]+amount*normal[0], a[1]+amount*normal[1]), (dy, dz)))
    result = []
    for (p, a), (q, b) in zip(lines[-1:]+lines[:-1], lines):
        den = a[0]*b[1]-a[1]*b[0]
        t = ((q[0]-p[0])*b[1]-(q[1]-p[1])*b[0])/den
        result.append((p[0]+t*a[0], p[1]+t*a[1]))
    return result


def circle(x, y, radius, count=64):
    # Polygone circonscrit ; le jeu numérique ne sert pas à absorber un câble.
    radius /= math.cos(math.pi/count)
    return [(x+radius*math.cos(i*math.tau/count),
             y+radius*math.sin(i*math.tau/count)) for i in range(count)]


def band(points, origin, tangent, normal):
    tangent, normal = A.Vector(*tangent), A.Vector(*normal)
    tangent.normalize(); normal.normalize()
    vertical = tangent.cross(normal); vertical.normalize()
    origin = A.Vector(*origin)
    contour = hull(points)

    def face(poly):
        vertices = [origin+normal*x+vertical*y-tangent*2.3 for x, y in poly]
        return Part.Face(Part.makePolygon(vertices+[vertices[0]]))

    inner, outer = offset(contour, .02), offset(contour, 1.22)
    result = face(outer).cut(face(inner)).extrude(tangent*4.6)
    length = sum(math.dist(a, b) for a, b in zip(inner, inner[1:]+inner[:1]))
    return result, length


def station_band(station, energy=False):
    p = station['point_mm']; t = A.Vector(*station['tangente']); t.normalize()
    if energy:
        n = A.Vector(-t.y, t.x, 0)
        points = [(-3, -4.2), (3, -4.2), (3, -1.4), (-3, -1.4)]
        points += circle(0, 0, .8)
    else:
        n = A.Vector(*station['decalage_appui_mm']); n.normalize()
        points = circle(0, 0, station['rayon_cable_mm'])
        points += circle(A.Vector(*station['decalage_appui_mm']).Length, 0, 1.5)
    return band(points, p, t, n)


def saddle_band(u):
    top = 32.3 if u == 180 else 28.8
    points = [(sign*y, z) for sign in (-1, 1)
              for y, z in [(12, top), (13, 25), (13, 16), (18.5, 20), (18.5, 16)]]
    points += circle(0, 16.5, 10, 128)
    if u == 180:
        points += circle(0, 32, 2.5, 128)
    if u == 250:
        points += circle(0, 32, 3, 128)
    return band(points, (0, 0, 0), (1, 0, 0), (0, 1, 0))


def overlap(a, b):
    return all(min(getattr(a.BoundBox, k+'Max'), getattr(b.BoundBox, k+'Max')) -
               max(getattr(a.BoundBox, k+'Min'), getattr(b.BoundBox, k+'Min')) > 1e-6
               for k in 'XYZ')


def metadata(reader, reference, name):
    _, objects = reader.xml(reference['fichier'])
    return json.loads(objects[reference['objet']][name].find('String').get('value'))


def run(args):
    build = json.loads((VER/'construction_prototype.json').read_text('utf8'))
    routes = json.loads((VER/'routes_prototype.json').read_text('utf8'))['routes']
    reader = Reader(MEC)
    refs = {row['reference']: row for row in build['references']}
    hashes = {row['fichier']: row['sha256'] for row in build['references']}
    hashes.update(build['sources_preservees'])
    if not build.get('finalisation_correcte') or any(sha(MEC/p) != h for p, h in hashes.items()):
        raise ValueError('Construction non finalisée ou natif périmé')
    if not args.candidate and any(sha(VER/p) != h for p, h in build['recettes_sha256'].items()):
        raise ValueError('Recette différente de la construction')
    energy = energy_departure_interfaces() if args.candidate else metadata(
        reader, refs['P64_Plateau_Energie_Prototype'], 'RetenuesDepartsBras')
    departures = {'stations': layout()[1]} if args.candidate else metadata(
        reader, refs['P75_Guide_Avionique_Prototype'], 'RetenuesDepartsBras')
    energy_occurrences = [o for o in build['occurrences']
        if o['parent'].startswith('sous_assemblages/') and
        o['source'] == refs['P64_Plateau_Energie_Prototype']['fichier']]
    if len(energy_occurrences) != 1:
        raise ValueError('Occurrence P64 absente ou ambiguë')
    energy_occurrence = energy_occurrences[0]
    pose = A.Placement(A.Matrix(*energy_occurrence['matrice']))
    pose = pose.multiply(reader.placement(energy_occurrence['source'],
                                         energy_occurrence['objet_source']).inverse())
    energy_shape = reader.occurrence(energy_occurrence)
    for station in energy['stations']:
        station['point_mm'] = list(pose.multVec(A.Vector(*station['point_mm'])))
    if args.candidate:
        for x, y, width, height in energy['lumieres_P64_mm']:
            energy_shape = energy_shape.cut(Part.makeBox(width, height, 10,
                A.Vector(x-width/2, y-height/2, 33)))
    instances = []
    for row in energy['stations'] + departures['stations']:
        shape, length = station_band(row, row in energy['stations'])
        instances.append((row['id'], shape, length))
    if len(energy['stations']) != 4 or len(departures['stations']) != 8 \
            or len({name for name, _, _ in instances}) != 12:
        raise ValueError('Les douze colliers des huit départs sont requis, sans doublon')
    if not args.candidate:
        for occurrence in build['occurrences']:
            if not occurrence['occurrence'].startswith('SelleBras'):
                continue
            pose = A.Placement(A.Matrix(*occurrence['matrice']))
            u = math.hypot(pose.Base.x, pose.Base.y)
            shape, length = saddle_band(min((180, 250, 280), key=lambda q: abs(q-u)))
            shape.Placement = pose
            instances.append((occurrence['occurrence'], shape, length))
        if len(instances) != 24 or len({name for name, _, _ in instances}) != 24:
            raise ValueError('Les douze selles P79/P80 sont requises, sans doublon')
    report = {'date_utc': datetime.now(timezone.utc).isoformat(),
        'script_sha256': sha(__file__), 'construction_sha256': sha(VER/'construction_prototype.json'),
        'routes_sha256': sha(VER/'routes_prototype.json'),
        'recette_depart_sha256': sha(VER/'prototype_retenues_departs.py'),
        'natifs_sha256': hashes, 'candidat': args.candidate,
        'bande': {'largeur_mm': 4.6, 'epaisseur_mm': 1.2, 'jeu_numerique_mm': .02,
            'critere_volume_intersection_max_mm3': 1e-4,
            'modele': 'Contour convexe circonscrit des sections ; bande pleine fermée ; tête exclue.'},
        'stations': [], 'collisions': [], 'erreurs': [], 'finalisation_correcte': False,
        'qualification': 'À valider'}
    rows_by_id = {r['id']: r for r in routes}
    for row in energy['stations'] + departures['stations']:
        route = rows_by_id[row['cables'][0]]
        wire = reader.shape(route['fichier'], route['objet_parcours'])
        ordered = ordered_edges(wire, A.Vector(*route['points_mm'][0]))
        distance, s, _, _ = project(ordered, A.Vector(*row['point_mm']))
        report['stations'].append({'id': row['id'], 'projection_mm': distance, 's_mm': s})
        if distance > .6:
            report['erreurs'].append('Station hors parcours : '+row['id'])

    def check(identifier, obstacle):
        for name, shape, _ in instances:
            if not overlap(shape, obstacle):
                continue
            for index, solid in enumerate(obstacle.Solids):
                if not overlap(shape, solid) or shape.distToShape(solid)[0] > 1e-6:
                    continue
                volume = shape.common(solid).Volume
                if volume > 1e-4:
                    report['collisions'].append({'bande': name, 'obstacle': identifier,
                        'solide': index, 'volume_mm3': volume})

    for row in routes:
        check(row['id'], reader.shape(row['fichier'], row['objet_cable']))
    report['cables_controles'] = len(routes)
    physical = [o for o in build['occurrences'] if o['parent'].startswith('sous_assemblages/')
                and not ('SA07_' in o['parent'] and o['occurrence'] in rows_by_id)]
    for index, occurrence in enumerate(physical, 1):
        if occurrence['source'] == refs['P64_Plateau_Energie_Prototype']['fichier']:
            obstacle = energy_shape
        else:
            obstacle = reader.occurrence(occurrence)
        check(occurrence['occurrence'], obstacle)
    report['obstacles_controles'] = len(physical)
    for index, (name, shape, _) in enumerate(instances):
        for other_name, other, _ in instances[index+1:]:
            if overlap(shape, other) and shape.distToShape(other)[0] <= 1e-6:
                volume = shape.common(other).Volume
                if volume > 1e-4:
                    report['collisions'].append({'bande': name, 'autre_bande': other_name,
                        'volume_mm3': volume})
    if args.candidate:
        # Toutes les nouvelles reprises sont contrôlées par la recette dédiée
        # de candidature, puis par le contrôle global de l'assemblage reconstruit.
        pass
    report['bandes'] = [{'id': name, 'valide': shape.isValid(), 'solides': len(shape.Solids),
                        'perimetre_interieur_mm': length} for name, shape, length in instances]
    report['fichiers_non_modifies'] = all(sha(MEC/p) == h for p, h in hashes.items())
    report['limites'] = ['Têtes, cliquets, accès des doigts et serrage à vérifier sur matériel.',
        'Lumières G10 et ligaments : finition, tolérances, abrasion et tenue vibratoire À valider.',
        'Les selles TPU et les longes PA12 ne sont pas qualifiées par ces contrôles de définition.']
    report['finalisation_correcte'] = True
    report['conforme'] = not report['erreurs'] and not report['collisions'] and report['fichiers_non_modifies'] \
        and all(b['valide'] and b['solides'] == 1 for b in report['bandes'])
    output = Path(args.output) if args.output else VER/'controle_departs_bras_prototype.json'
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', 'utf8')
    print(json.dumps({k: report[k] for k in ('conforme', 'collisions', 'erreurs', 'cables_controles', 'obstacles_controles')}, ensure_ascii=False), flush=True)
    return report['conforme']


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--candidate', action='store_true')
    parser.add_argument('--output')
    raise SystemExit(0 if run(parser.parse_args()) else 1)
