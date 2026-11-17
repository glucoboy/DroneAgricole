"""Variantes des supports F05/F08 sur natifs de la copie. Les axes des câbles restent fixes."""
import json
import math
import os
import sys

from autonomie_cao import App, COPY, OUT, Part, Reader, gap, gui, inspect_solid, measured_pair, read, sha, write
from integrer_autonomie import BUILD, ROUTES, isolation, preserve


def cylinder(obj, start, end):
    a, b = App.Vector(*start), App.Vector(*end)
    obj.Height = (b-a).Length
    obj.Placement = App.Placement(a, App.Rotation(App.Vector(0,0,1), b-a))


def native_stations(root, property_name, points):
    data = json.loads(getattr(root, property_name))
    for row in data['stations']:
        if row['id'] in points:
            row['point_mm'] = points[row['id']]
    setattr(root, property_name, json.dumps(data, ensure_ascii=False))


def parameters(variant, doc):
    root = doc.getObject('Ensemble')
    stations = []
    if variant.startswith('P73'):
        points = {'F05_NEG_T_15':[20,-45.25,77], 'F05_NEG_T_30':[30,-45.25,77]}
        bar = doc.getObject('AppuiF05NegHorizontal')
        bar.Placement.Base += App.Vector(0,-3.75,0)
        first_foot = -20 if variant == 'P73_F05_F08_B' else -25
        for suffix, x in [('',first_foot), ('001',-35)]:
            cylinder(doc.getObject('PiedAppuiF05Neg'+suffix), [x,55.5,69], [x,40.3,69])
            cylinder(doc.getObject('MontantAppuiF05Neg'+suffix), [x,40.3,69], [x,40.3,77])
        if variant != 'P73_F05':
            last_top = 81 if variant == 'P73_F05_F08_B' else 85.5
            for suffix, x, top in [('',65,81),('001',25,81),('002',-5,last_top)]:
                cylinder(doc.getObject('ConsoleF08AvalMontant'+suffix), [x,55.5,69], [x,55.5,top])
                cylinder(doc.getObject('ConsoleF08AvalReprise'+suffix), [x,55.5,top], [x,31,top])
                cylinder(doc.getObject('ConsoleF08AvalBas'+suffix), [x,31,top], [x,31,73])
                points[f'F08_AVAL_T_{-x}'] = [-x,-35,73]
        native_stations(root, 'RetenuesDistribution', points)
    else:
        points = {f'F08_AVAL_MON_{z}':[-94,-35,z] for z in (85,103)}
        cylinder(doc.getObject('MontanteF08Aval'), [-90,-35,78], [-90,-35,109])
        cylinder(doc.getObject('RepriseF08Aval'), [-80,-43,112], [-90,-35,105])
        native_stations(root, 'RetenuesHautes', points)
    for name, point in points.items():
        stations.append({'station': name, 'point_mm': point, 'route': 'F05_NEG' if name.startswith('F05') else 'F08_AVAL'})
    return stations


def generate(variant):
    gui()
    build = read(COPY/BUILD)
    guide = next(row for row in build['occurrences'] if row['occurrence'] == ('P73_Guide' if variant.startswith('P73') else 'P75_Cadre'))
    source = COPY/guide['source']
    doc = App.openDocument(str(source))
    isolation()
    stations = parameters(variant, doc)
    recomputed = doc.recompute()
    visible = doc.getObject('ResultatPassagesReprise')
    proof = {'id': variant, 'target': guide, 'source_sha256': sha(source), 'recomputed': recomputed,
             'solid': inspect_solid(visible.Shape), 'stations': stations,
             'errors': [o.Name for o in doc.Objects if any(s in ('Error','Invalid') for s in o.State)]}
    if not recomputed or proof['solid']['status'] != 'pass' or proof['errors']:
        write(OUT/('retenues_'+variant+'.json'),proof)
        raise RuntimeError('Guide invalide '+variant)
    path = COPY/'verification/candidats'/('Retenues_'+variant+'.FCStd')
    doc.saveAs(str(path))
    proof.update(file=path.relative_to(COPY).as_posix(), sha256=sha(path))
    write(OUT/('retenues_'+variant+'.json'),proof)


def check(variant):
    proof_path = OUT/('retenues_'+variant+'.json')
    proof = read(proof_path)
    guide = proof['target']
    reader = Reader(COPY)
    old = reader.occurrence(guide)
    new = reader.occurrence({**guide, 'source':proof['file']})
    if variant.startswith('P75'):
        # Le booléen sur les deux cadres complets échoue dans OCCT. Les deux
        # seules primitives modifiées donnent une borne de toute matière ajoutée.
        added = Part.makeCompound([reader.shape(proof['file'], name) for name in ('MontanteF08Aval','RepriseF08Aval')])
        difference_scope = 'Borne supérieure constituée des deux primitives modifiées, avant découpe finale.'
        removed = None
    else:
        added = new.cut(old)
        difference_scope = 'Différence exacte entre guide candidat et guide sauvegardé.'
        removed = old.cut(new).Volume
    if added.isNull() or not added.isValid() or not math.isfinite(added.Volume):
        raise RuntimeError('Différence non mesurable '+variant)
    pairs = []
    rows = read(COPY/BUILD)['occurrences']
    for row in rows:
        if not row['parent'].startswith('sous_assemblages/') or row['occurrence'] == guide['occurrence']:
            continue
        shape = reader.occurrence(row)
        if gap(added.BoundBox,shape.BoundBox)>1e-6:
            continue
        pair = measured_pair(added,shape)
        pairs.append({'occurrence':row['occurrence'],**pair})
    routes = {r['id']:r for r in read(COPY/ROUTES)['routes']}
    for station in proof['stations']:
        route = routes[station['route']]
        point = Part.Vertex(App.Vector(*station['point_mm']))
        axis = reader.shape(route['fichier'],route['objet_parcours'])
        station['axis_error_mm'] = point.distToShape(axis)[0]
        station['distance_to_guide_less_radius_mm'] = point.distToShape(new)[0]-route['diametre_mm']/2
    proof.update(pairs=pairs, collisions=sum(p['volume_mm3']>1e-4 for p in pairs), added_bound_mm3=added.Volume,
                 removed_mm3=removed, difference_scope=difference_scope, construction_sha256=sha(COPY/BUILD), preservation=preserve(),
                 scope='Contrôle des volumes ajoutés contre les occurrences existantes; écart nominal de station, sans collier ni tolérance physique.')
    write(proof_path, proof)
    print(variant, 'collisions', proof['collisions'], flush=True)


if __name__ == '__main__':
    {'generate':generate, 'check':check}[sys.argv[1]](sys.argv[2])
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0)
