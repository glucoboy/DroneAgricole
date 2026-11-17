"""Contrôles des parcours et des stations dans l'assemblage candidat."""
import math

from autonomie_cao import App, COPY, OUT, Part, Reader, gui, inspect_route, read, sha, write
from integrer_autonomie import BUILD, ROUTES, equivalent, fresh_f16, isolation, occurrences, preserve, route_map
from freecad_geometry import rebuild_cable_in_isolated_document


def stations():
    reader = Reader(COPY)
    routes = route_map(read(COPY/ROUTES))
    shapes = {key: reader.shape(row['fichier'], row['objet_parcours']) for key, row in routes.items()}
    build = read(COPY/BUILD)
    station_rows = []
    for row in build['occurrences']:
        if not row['parent'].startswith('sous_assemblages/'):
            continue
        props = reader.xml(row['source'])[1][row['objet_source']]
        for name, prop in props.items():
            if not name.startswith('Retenue'):
                continue
            string = prop.find('String')
            if string is None or not string.get('value', '').startswith('{'):
                continue
            import json
            metadata = json.loads(string.get('value'))
            for station in metadata.get('stations', []):
                if not isinstance(station, dict):
                    continue
                point = station.get('point_mm')
                frame = station.get('repere') or metadata.get('repere') or 'global implicite'
                if isinstance(point,list) and len(point)==3 and frame.casefold().startswith('local'):
                    point = list(App.Placement(App.Matrix(*row['matrice'])).multVec(App.Vector(*point)))
                members = station.get('cables', [station.get('cable') or metadata.get('cable')])
                if not isinstance(members, list):
                    members = [members]
                for member in members:
                    if member not in shapes or not isinstance(point, list) or len(point) != 3:
                        continue
                    distance = Part.Vertex(App.Vector(*point)).distToShape(shapes[member])[0]
                    if not math.isfinite(distance):
                        raise ValueError('Distance de station non finie')
                    station_rows.append({'id': station.get('id'), 'occurrence': row['occurrence'],
                                         'property': name, 'route': member, 'point_mm': point, 'declared_frame':frame,
                                         'distance_mm': distance, 'support': station.get('support')})
    write(OUT/'stations_faisceau_complet.json', {'routes_count': len(routes), 'measurements': station_rows,
          'scope': 'Propriétés natives Retenue*, membres et point explicites. Les repères locaux déclarés sont transformés par la pose d’occurrence. Sans repère déclaré, convention globale de l’inventaire à confirmer. Distance axe/site, pas un contrôle de contact ou de fixation installée.',
          'route_register_sha256': sha(COPY/ROUTES), 'construction_sha256': sha(COPY/BUILD)})
    print('Stations mesurées', len(station_rows), flush=True)


def fresh(first, last):
    routes = route_map(read(COPY/ROUTES))
    build = read(COPY/BUILD)
    links = occurrences(build, routes)
    reader = Reader(COPY)
    _, environment = gui()
    results = []
    selection = read(OUT/'selection_f16.json')
    for cid in list(routes)[first:last]:
        row, link = routes[cid], links[cid]
        path = COPY/row['fichier']
        before = sha(path)
        if link['source'] != row['fichier']:
            raise RuntimeError('Registres désaccordés pour '+cid)
        saved_link = reader.xml(link['parent'])[1][cid]['LinkedObject'].find('XLink')
        if (COPY/link['parent']).parent.joinpath(saved_link.get('file')).resolve() != path.resolve() or saved_link.get('name') != link['objet_source']:
            raise RuntimeError('Cible native incorrecte pour '+cid)
        matrix = reader.placement(link['parent'], cid).toMatrix().A
        if max(abs(a-b) for a,b in zip(matrix, link['matrice'])) > 1e-7:
            raise RuntimeError('Pose de lien incorrecte pour '+cid)
        doc = App.openDocument(str(path))
        isolation()
        cable = doc.getObject(row['objet_cable'])
        target = doc.getObject(link['objet_source'])
        if target != cable and (cable not in target.Group or not cable.Visibility):
            raise RuntimeError('Câble absent du groupe lié '+cid)
        if cid == 'F16':
            checked = fresh_f16(cable, selection, read(OUT/('autonomie_'+selection['id']+'.json')))
            geom = checked['whole']
        else:
            saved = cable.Shape.copy()
            generated = rebuild_cable_in_isolated_document(doc, cable)
            if generated['status'] != 'pass':
                raise RuntimeError('Câble non reconstruit '+cid)
            geom = inspect_route(cable.Base.Shape.Wires[0], start_position=row['points_mm'][0], end_position=row['points_mm'][-1])
            checked = {'fresh': generated, 'delta': equivalent(saved, cable.Shape), 'length_mm': cable.Base.Shape.Length}
        App.closeDocument(doc.Name)
        if sha(path) != before:
            raise RuntimeError('Le recalcul a modifié le disque '+cid)
        results.append({'id': cid, 'file': row['fichier'], 'sha256': before, 'source_object': row['objet_cable'],
                        'recomputed': checked['fresh']['status'], 'volume_equivalence': checked['delta'],
                        'length_mm': checked['length_mm'], 'radius_mm': geom.get('minimum_radius_mm'),
                        'endpoint_errors_mm': [geom.get('start_position_error_mm'), geom.get('end_position_error_mm')],
                        'geometry_status': geom['status'], 'geometry_findings': geom['failures']+geom.get('unknowns', []),
                        'bom_ids': row['bom_ids'], 'terminations': row.get('terminaisons')})
        print(cid, checked['fresh']['status'], flush=True)
    write(OUT/f'recalcul_complet_{first:02d}.json', {'routes': results, 'range': [first,last], 'environment': environment,
          'register_sha256': sha(COPY/ROUTES), 'preservation': preserve()})


if __name__ == '__main__':
    import os
    import sys
    if sys.argv[1] == 'stations':
        stations()
    else:
        fresh(int(sys.argv[2]), int(sys.argv[3]))
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0)
