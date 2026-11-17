"""Contrôle des retenues sur les parcours courbes sauvegardés Cable Workbench.

Les stations viennent des métadonnées des pièces natives. Le contrat affecte
ces stations aux câbles et explicite les portions guidées et boucles souples.
Ce contrôle de définition ne qualifie ni les colliers ni la tenue vibratoire.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import json
import math
import traceback
import FreeCAD as App
import Part
from read_brep_prototype import Reader

VER = Path(__file__).resolve().parent
MEC = VER.parent
CONTRACT = VER / 'retenues_faisceaux_prototype.json'
OUTPUT = VER / 'controle_retenues_faisceaux_prototype.json'
KINDS = {'guidee', 'transition_courte', 'boucle_souple'}
MODES = {'individuel', 'commun', 'reserve'}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def finite_positive(value, name, zero=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) \
            or value < 0 or (not zero and value == 0):
        raise ValueError('Valeur positive finie requise : ' + name)
    return float(value)


def vector(values):
    if len(values) != 3 or any(isinstance(v, bool) or not isinstance(v, (int, float))
                             or not math.isfinite(v) for v in values):
        raise ValueError('Point 3D invalide')
    return App.Vector(*values)


def coords(point):
    return [round(v, 6) for v in (point.x, point.y, point.z)]


def ordered_edges(wire, start):
    """Chaîner les arêtes par leurs extrémités, indépendamment de leur stockage."""
    remaining = list(wire.Edges)
    ordered = []
    current = start
    while remaining:
        matches = []
        for index, edge in enumerate(remaining):
            first = edge.valueAt(edge.FirstParameter)
            last = edge.valueAt(edge.LastParameter)
            if (first-current).Length < 1e-5:
                matches.append((index, False, last))
            if (last-current).Length < 1e-5:
                matches.append((index, True, first))
        if len(matches) != 1:
            raise ValueError('Parcours non continu, fermé ou ambigu')
        index, reverse, current = matches[0]
        ordered.append((remaining.pop(index), reverse))
    return ordered


def project(ordered, point):
    """Distance OCCT et abscisse curviligne, y compris sur les congés réels."""
    candidates = []
    offset = 0.0
    vertex = Part.Vertex(point)
    for index, (edge, reverse) in enumerate(ordered):
        distance, pairs, infos = edge.distToShape(vertex)
        for (projected, _), info in zip(pairs, infos):
            # Le paramètre de l'arête fourni par OCCT conserve sa période,
            # contrairement à Curve.parameter() sur un arc traversant 2π.
            if info[0] == 'Edge':
                parameter = info[2]
            elif info[0] == 'Vertex':
                parameter = min((edge.FirstParameter, edge.LastParameter),
                    key=lambda value:(edge.valueAt(value)-projected).Length)
            else:
                raise ValueError('Projection sur une topologie inattendue')
            parameter = min(edge.LastParameter, max(edge.FirstParameter, parameter))
            local = edge.Curve.length(edge.FirstParameter, parameter)
            s = offset + (edge.Length-local if reverse else local)
            candidates.append((distance, s, index, projected))
        offset += edge.Length
    candidates.sort(key=lambda x: (x[0], x[1]))
    best = candidates[0]
    # Les extrémités communes de deux arêtes ont la même abscisse, contrairement
    # à deux passages distincts d'une réserve : ces derniers doivent être levés.
    if any(abs(c[0]-best[0]) < 1e-6 and abs(c[1]-best[1]) > 1e-4 for c in candidates[1:]):
        raise ValueError('Projection ambiguë sur plusieurs passages du câble')
    return best


def get_station(reader, refs, occurrences, entry):
    reference = refs[entry['reference']]
    file, obj = reference['fichier'], reference['objet']
    candidates = [o for o in occurrences if o['source'] == file and
                  o['parent'].startswith('sous_assemblages/') and
                  (not entry.get('occurrence') or o['occurrence'] == entry['occurrence'])]
    if len(candidates) != 1:
        raise ValueError('Occurrence de support absente ou ambiguë : ' + entry['reference'])
    occurrence = candidates[0]
    _, objects = reader.xml(file)
    node = objects[obj][entry['propriete']].find('String')
    data = json.loads(node.get('value'))
    collection = data
    for key in entry.get('collection', 'stations').split('.'):
        collection = collection[key]
    stations = [s for s in collection if s.get(entry.get('id_key', 'id')) == entry['cle_id']]
    if len(stations) != 1:
        raise ValueError('Station native absente ou ambiguë : ' + entry['cle_id'])
    station = stations[0]
    point = vector(station[entry.get('point_key', 'point_mm')])
    point += vector(entry.get('translation_point_mm', [0, 0, 0]))
    pose = App.Placement(App.Matrix(*occurrence['matrice']))
    if entry.get('repere', 'global') == 'local':
        point = pose.multVec(point)
    elif entry.get('repere', 'global') == 'global':
        # Les métadonnées globales des guides ont été définies dans leur pose
        # native ; prendre également en compte tout déplacement de l'occurrence.
        point = pose.multiply(reader.placement(file, obj).inverse()).multVec(point)
    else:
        raise ValueError('Repère de station inconnu')
    actual = reader.placement(occurrence['parent'], occurrence['occurrence']).toMatrix().A
    if max(abs(a-b) for a, b in zip(actual, occurrence['matrice'])) > 1e-6:
        raise ValueError('Matrice du support différente du FCStd')
    return point, station, occurrence


def check_portions(contract, length, stations):
    positions = {'DEBUT':0.0, 'FIN':length, **{s['station_id']:s['s_mm'] for s in stations}}
    intervals = []
    for portion in contract['portions']:
        a, b = positions[portion['debut']], positions[portion['fin']]
        kind = portion['type']
        if kind not in KINDS or b-a < 1e-5:
            raise ValueError('Portion inconnue, nulle ou inversée')
        limit = finite_positive(portion.get('portee_max_mm',
            contract['limites']['portee_max_mm'].get(kind)), 'portee_max_mm')
        if kind == 'boucle_souple' and not portion.get('justification'):
            raise ValueError('Boucle souple sans justification')
        intervals.append(dict(debut=portion['debut'], fin=portion['fin'], type=kind,
            s_debut_mm=a, s_fin_mm=b, longueur_mm=b-a, portee_max_mm=limit,
            conforme=b-a <= limit+1e-4, justification=portion.get('justification', '')))
    intervals.sort(key=lambda p: p['s_debut_mm'])
    position = 0.0
    for p in intervals:
        if abs(position-p['s_debut_mm']) > 1e-4:
            raise ValueError('Trou ou recouvrement dans la couverture des portions')
        position = p['s_fin_mm']
    if abs(position-length) > 1e-4:
        raise ValueError('Parcours non couvert jusqu’à son extrémité')
    return intervals


def reserve_evidence(contract, build, files):
    """Charger la preuve physique du collier commun, sans élargir le jeu d'appui."""
    expected = {}
    for route in contract['routes']:
        for entry in route['retenues']:
            if entry['mode'] == 'reserve':
                key = entry.get('collier_id', entry['station_id'])
                expected.setdefault(key, set()).add((route['id'], entry['station_id']))
    if not expected:
        return {}, []
    path = (MEC/contract.get('preuve_enveloppement_reserves', '')).resolve()
    if path.parent != VER.resolve() or path.suffix != '.json' or not path.is_file():
        raise ValueError('Preuve d’enveloppement des réserves absente ou hors périmètre')
    proof = json.loads(path.read_text('utf-8'))
    if proof.get('schema_version') != 1 or any(proof.get(k) is not True for k in
            ('finalisation_correcte', 'conforme', 'fichiers_non_modifies')) \
            or proof.get('erreurs') != [] or proof.get('collisions') != []:
        raise ValueError('Preuve d’enveloppement non finalisée ou non conforme')
    script = (MEC/proof.get('script_fichier', '')).resolve()
    if script.parent != VER.resolve() or script.suffix != '.py' or not script.is_file() \
            or sha(script) != proof.get('script_sha256'):
        raise ValueError('Recette d’enveloppement absente ou périmée')
    if proof.get('construction_sha256') != sha(VER/'construction_prototype.json') \
            or proof.get('routes_sha256') != sha(VER/'routes_prototype.json') \
            or proof.get('contrat_sha256') != sha(CONTRACT) \
            or proof.get('natifs_sha256') != files:
        raise ValueError('Preuve d’enveloppement portant sur une autre construction')
    collars = proof.get('colliers', [])
    if len(collars) != len(expected) or {c['collier_id'] for c in collars} != set(expected):
        raise ValueError('Colliers de réserve absents, incomplets ou dupliqués')
    result = {}
    for collar in collars:
        stations = collar.get('stations', [])
        identifiers = {(s['cable'], s['station_id']) for s in stations}
        if identifiers != expected[collar['collier_id']] or len(stations) != len(identifiers) \
                or any(collar.get(k) is not True for k in ('valide', 'passage_lumieres', 'enveloppement_pile')) \
                or collar.get('solides') != 1:
            raise ValueError('Boucle de réserve ou couverture des spires non conforme')
        for station in stations:
            vector(station['point_mm'])
        result[collar['collier_id']] = collar
    return result, [path, script]


def run():
    inputs = [VER/'construction_prototype.json', VER/'routes_prototype.json', CONTRACT]
    hashes = {p.name:sha(p) for p in inputs}
    build, routes_doc, contract = [json.loads(p.read_text('utf-8')) for p in inputs]
    if not build.get('finalisation_correcte') or contract.get('schema_version') != 1:
        raise ValueError('Construction non finalisée ou contrat non pris en charge')
    recipes=build.get('recettes_sha256', {})
    if not recipes or any(Path(p).name != p or sha(VER/p) != h for p,h in recipes.items()):
        raise ValueError('Recette de construction absente ou modifiée depuis la construction')
    refs = {r['reference']:r for r in build['references']}
    files = {r['fichier']:r['sha256'] for r in build['references']}
    files.update(build['sources_preservees'])
    if any(sha(MEC/p) != h for p, h in files.items()):
        raise ValueError('Natif modifié depuis la construction')
    reserves, reserve_inputs = reserve_evidence(contract, build, files)
    inputs.extend(reserve_inputs)
    hashes.update({p.name:sha(p) for p in reserve_inputs})
    actual_ids = [r['id'] for r in routes_doc['routes']]
    contract_ids = [r['id'] for r in contract['routes']]
    if len(set(actual_ids)) != len(actual_ids) or len(set(contract_ids)) != len(contract_ids) \
            or set(actual_ids) != set(contract_ids):
        raise ValueError('Le contrat doit couvrir exactement tous les parcours, une seule fois')
    routes = {r['id']:r for r in routes_doc['routes']}
    report = dict(date_utc=datetime.now(timezone.utc).isoformat(), script_sha256=sha(__file__),
        lecteur_sha256=sha(VER/'read_brep_prototype.py'), entrees_sha256=hashes,
        natifs_sha256=files, finalisation_correcte=False, erreurs=[], routes=[],
        protocole='Projection OCCT sur chaque arête WireFlex ordonnée depuis le port de départ ; stations lues dans les FCStd ; contrôle exhaustif des intervalles déclarés.',
        qualification='À valider', limites=[
            'Les seuils de portée sont des critères de définition candidats, pas une qualification mécanique.',
            'La proximité d’un appui ne prouve pas le montage de la tête ni la tenue d’un collier.',
            'Les boucles de découplage capteurs restent souples ; abrasion, vibrations et serrage à vérifier sur matériel.'])
    reader = Reader(MEC)
    shapes, anchors = {}, {}
    for item in contract['routes']:
        identifier = item['id']
        row = routes[identifier]
        result = dict(id=identifier, stations=[], portions=[])
        try:
            saved = reader.shape(row['fichier'], row['objet_parcours'])
            if len(saved.Wires) != 1 or not saved.isValid() or saved.Wires[0].isClosed():
                raise ValueError('Un seul parcours ouvert et valide est requis')
            wire = saved.Wires[0]
            if abs(wire.Length-row['longueur_courbe_mm']) > 1e-4:
                raise ValueError('Longueur native différente du registre')
            ordered = ordered_edges(wire, vector(row['points_mm'][0]))
            seen = set()
            for entry in item['retenues']:
                sid = entry['station_id']
                if sid in seen or sid in ('DEBUT', 'FIN') or entry['mode'] not in MODES:
                    raise ValueError('Identifiant de station dupliqué/réservé ou mode inconnu')
                seen.add(sid)
                point, station, occurrence = get_station(reader, refs, build['occurrences'], entry)
                if station.get('cables') and identifier not in station['cables']:
                    raise ValueError('Station native affectée à un autre câble : ' + sid)
                distance, s, edge, projected = project(ordered, point)
                tolerance = finite_positive(entry.get('tol_projection_mm', .6), 'tol_projection_mm', True)
                key = occurrence['parent']+'#'+occurrence['occurrence']
                collier_id=entry.get('collier_id',sid)
                physical_anchor=(key,entry['mode'],entry.get('ancrage_commun',entry['cle_id']))
                if collier_id in anchors and anchors[collier_id] != physical_anchor:
                    raise ValueError('Identifiant de collier partagé entre ancrages incompatibles : '+collier_id)
                anchors[collier_id]=physical_anchor
                if key not in shapes:
                    shapes[key] = reader.occurrence(occurrence)
                distance_support = Part.Vertex(projected).distToShape(shapes[key])[0]
                gap = distance_support-row['diametre_mm']/2
                allowed_gap = finite_positive(entry.get('jeu_support_max_mm',
                    item['limites'].get('jeu_support_max_mm', 1.0)), 'jeu_support_max_mm', True)
                errors = []
                if distance > tolerance+1e-4: errors.append('projection_hors_tolerance')
                support_mode = 'direct'
                if entry['mode'] == 'reserve':
                    collar = reserves[collier_id]
                    evidence = next(s for s in collar['stations']
                                    if s['cable'] == identifier and s['station_id'] == sid)
                    if collar.get('support') != key or (vector(evidence['point_mm'])-point).Length > 1e-4:
                        raise ValueError('Preuve de réserve affectée à un autre support ou point')
                    if gap > allowed_gap+1e-4:
                        support_mode = 'enveloppement_reserve'
                elif gap > allowed_gap+1e-4:
                    errors.append('appui_trop_eloigne')
                if gap < -1e-3: errors.append('axe_dans_appui')
                if entry.get('etat_integration') != 'Implémenté': errors.append('station_non_integree')
                result['stations'].append(dict(station_id=sid, collier_id=collier_id,
                    support=key, station_native=entry['cle_id'], mode=entry['mode'], mode_appui=support_mode,
                    point_nominal_mm=coords(point), point_projete_mm=coords(projected),
                    s_mm=s, distance_projection_mm=distance, tolerance_projection_mm=tolerance,
                    jeu_surface_appui_mm=gap, jeu_max_mm=allowed_gap, erreurs=errors))
                report['erreurs'].extend(dict(cable=identifier, station=sid, type=e) for e in errors)
            if not result['stations']:
                raise ValueError('Aucune retenue affectée au parcours')
            result['stations'].sort(key=lambda s:s['s_mm'])
            result['longueur_mm'] = wire.Length
            result['portions'] = check_portions(item, wire.Length, result['stations'])
            report['erreurs'].extend(dict(cable=identifier, type='portee_depassee',
                debut=p['debut'], fin=p['fin'], longueur_mm=p['longueur_mm'], limite_mm=p['portee_max_mm'])
                for p in result['portions'] if not p['conforme'])
        except Exception as exc:
            report['erreurs'].append(dict(cable=identifier, type='contrat_ou_geometrie', message=str(exc)))
        report['routes'].append(result)
    # Une preuve d'enveloppement ne remplace pas l'appui de la pile sur P77.
    for collier_id in reserves:
        if not any(s['collier_id'] == collier_id and s['mode_appui'] == 'direct' and not s['erreurs']
                   for r in report['routes'] for s in r['stations']):
            report['erreurs'].append(dict(collier=collier_id, type='reserve_sans_appui_direct'))
    report['fichiers_non_modifies'] = not (any(sha(p) != hashes[p.name] for p in inputs) \
        or any(sha(MEC/p) != h for p,h in files.items()) or any(sha(VER/p) != h for p,h in recipes.items()))
    if not report['fichiers_non_modifies']:
        report['erreurs'].append(dict(type='source_modifiee_pendant_controle'))
    report['nombre_routes'] = len(report['routes'])
    report['nombre_affectations'] = sum(len(r['stations']) for r in report['routes'])
    report['nombre_colliers_identifies'] = len({s['collier_id'] for r in report['routes'] for s in r['stations']})
    report['finalisation_correcte'] = True
    report['conforme'] = not report['erreurs']
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({k:report[k] for k in ['nombre_routes','nombre_affectations','nombre_colliers_identifies','conforme','erreurs']},ensure_ascii=False))
    return report['conforme']


def self_test():
    # Un aller-retour spatial peut rester continu sans revenir au même point :
    # la projection doit conserver l'abscisse et ne pas compter la corde droite.
    a,b,c = App.Vector(0,0,0),App.Vector(10,0,0),App.Vector(10,10,0)
    wire = Part.Wire([Part.makeLine(a,b),Part.makeLine(b,c)])
    for origin, target in [(a, 13), (c, 7)]:
        distance,s,_,_ = project(ordered_edges(wire, origin), App.Vector(12,3,0))
        assert abs(distance-2)<1e-8 and abs(s-target)<1e-8
    arc = Part.Arc(App.Vector(10,0,0),App.Vector(2**.5*5,2**.5*5,0),App.Vector(0,10,0)).toShape()
    _,s,_,_ = project(ordered_edges(Part.Wire([arc]),App.Vector(10,0,0)), App.Vector(8,8,0))
    assert abs(s-5*math.pi/2)<1e-7
    crossing=Part.makeCircle(10,App.Vector(),App.Vector(0,0,1),350,370)
    for parameter in (crossing.FirstParameter,crossing.LastParameter):
        _,s,_,_=project(ordered_edges(Part.Wire([crossing]),crossing.valueAt(parameter)),App.Vector(10,0,0))
        assert abs(s-10*math.pi/18)<1e-7
    contract={'portions':[{'debut':'DEBUT','fin':'S','type':'guidee'},
                           {'debut':'S','fin':'FIN','type':'transition_courte'}],
              'limites':{'portee_max_mm':{'guidee':10,'transition_courte':12}}}
    assert all(p['conforme'] for p in check_portions(contract,20,[{'station_id':'S','s_mm':9}]))
    contract['portions'][1]['debut']='DEBUT'
    try: check_portions(contract,20,[{'station_id':'S','s_mm':9}])
    except ValueError: pass
    else: raise AssertionError('Recouvrement de portions accepté')
    print('Contrôles projection droite/inversée/arc et couverture : réussis')


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--self-test', action='store_true')
    args=parser.parse_args()
    if args.self_test:
        self_test()
    else:
        try:
            success=run()
        except Exception:
            OUTPUT.write_text(json.dumps({'finalisation_correcte':False,'conforme':False,
                'erreur':traceback.format_exc()},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
            raise
        raise SystemExit(0 if success else 1)
