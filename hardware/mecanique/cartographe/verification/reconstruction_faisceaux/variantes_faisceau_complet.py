"""Création et mesure des variantes de parcours à extrémités conservées."""
import os
import sys

from autonomie_cao import App, COPY, OUT, Part, Reader, gap, gui, inspect_route, measured_pair, read, sha, write
from integrer_autonomie import BUILD, ROUTES, route_map
from freecad_geometry import rebuild_cable_in_isolated_document


def run(index):
    config = read(OUT/'variantes_faisceau_complet.json')
    trial = config['routes'][index]
    cid, name, radius = trial['route'], trial['id'], trial['radius_mm']
    routes = route_map(read(COPY/ROUTES))
    route = routes[cid]
    is_m8 = cid == 'F_M8'
    points = config['m8_points_mm'] if is_m8 else route['points_mm']
    assert points[0] == route['points_mm'][0] and points[-1] == route['points_mm'][-1]
    builder, environment = gui()
    doc = App.newDocument(name)
    cable, wire = builder.make_native_cable(doc, None, cid, points, route['diametre_mm'], radius)
    fresh = rebuild_cable_in_isolated_document(doc, cable)
    previous = route['points_mm']
    axis = lambda i,j: list(App.Vector(*previous[j])-App.Vector(*previous[i]))
    geom = inspect_route(wire.Shape.Wires[0], minimum_radius_mm=config['m8_radius_min_mm'] if is_m8 else None,
                         start_position=previous[0],end_position=previous[-1],start_axis=axis(0,1),end_axis=axis(-1,-2))
    if fresh['status'] != 'pass' or geom['failures']:
        raise RuntimeError('Parcours non généré '+str(geom['failures']))
    cable.Visibility = True
    wire.Visibility = False
    dest = COPY/'verification/candidats'/(name+'.FCStd')
    doc.saveAs(str(dest))
    reader = Reader(COPY)
    pairs = []
    a = cable.Shape
    for row in read(COPY/BUILD)['occurrences']:
        if not row['parent'].startswith('sous_assemblages/') or row['occurrence'] == cid:
            continue
        obstacle = reader.occurrence(row)
        if gap(a.BoundBox, obstacle.BoundBox)>1e-6:
            continue
        pair = {'obstacle':row['occurrence'],**measured_pair(a,obstacle)}
        if cid == 'AIRY' and row['occurrence'] in ('AIRY_ETH','AIRY_PWR','AIRY_SYNC') and pair['volume_mm3']>1e-4:
            zone = Part.makeSphere(route['diametre_mm'], App.Vector(*points[-1]))
            pair['outside_airy_breakout_mm3'] = a.common(obstacle).cut(zone).Volume
        pairs.append(pair)
    collisions = [p for p in pairs if p.get('outside_airy_breakout_mm3',p['volume_mm3'])>1e-4]
    result = {**trial,'geometry':geom,'fresh':fresh,'native':dest.relative_to(COPY).as_posix(),'sha256':sha(dest),
              'pairs':pairs,'collisions_outside_breakout':collisions,'environment':environment,'start_straight_mm':wire.Shape.Edges[0].Length,
              'end_straight_mm':wire.Shape.Edges[-1].Length,'construction_sha256':sha(COPY/BUILD),
              'scope':'Pose nominale. Éclatement Airy local contrôlé séparément, composition interne inconnue. La tenue des colliers et la dynamique ne sont pas évaluées.'}
    write(OUT/('variante_'+name+'.json'),result)
    print(name, [(p['obstacle'],p['volume_mm3']) for p in collisions],flush=True)


if __name__ == '__main__':
    run(int(sys.argv[1]))
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0)
