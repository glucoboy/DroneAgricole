"""Extraction de preuves et rapprochement documentaire, sans écriture CAO."""
import collections
import csv
import hashlib
import json
import math
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile


def load(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def native(path):
    with ZipFile(path) as arc:
        return ET.fromstring(arc.read('Document.xml'))


mec = Path('hardware/mecanique/cartographe')
elec = Path('hardware/electronique/cartographe')
ver = mec / 'verification'
prev = ver / 'reconstruction_faisceaux'
schem = elec / 'carte_avionique'
out = ver / 'refonte_faisceaux'
bom_file = mec / 'nomenclature_prototype.json'
elec_file = elec / 'cablage_global.json'
routes_file = ver / 'routes_prototype.json'
proof_file = prev / 'bilan_faisceau_complet.json'
net_file = schem / 'verification/netlist.xml'
reconciliation_file = out / 'inventaire_correspondances.json'


def ref(path, section, ident):
    return f'{path.as_posix()}#/{section}/{ident}'


def parameter(value, unit, data_class, source, scope, confidence):
    return {'value': value, 'unit': unit, 'data_class': data_class, 'source': source,
            'confidence': confidence, 'scope': scope, 'revision': None,
            'uncertainty': None, 'input_refs': [], 'method': None}


def main():
    bom = load(bom_file)
    elec_data = load(elec_file)
    proof = load(proof_file)
    decisions = load(reconciliation_file)
    rows = {r['id']: r for r in bom['liaisons']}
    items = {r['id']: r for r in bom['items']}
    register = {r['id']: r for r in load(routes_file)['routes']}
    previous = {r['id']: r for r in load(prev / 'analyse_connectivite.json')['geometric_routes']}
    measured = {r['id']: r for r in proof['routes']}
    base = Path(proof['copy_root'])
    entry = base / proof['entry']
    sa07 = base / 'sous_assemblages/SA07_Prototype_Faisceaux.FCStd'
    assert sha(entry) == proof['entry_sha256']
    assert len(register) == len(measured) == 53 and set(register) == set(measured) == set(previous)

    connections = []
    covered_sources = set()
    usage = collections.defaultdict(list)
    for decision in decisions['connections']:
        ident, source_id, origin, destination, function, scope, axes, integration, reason = decision[:9]
        more = decision[9] if len(decision) > 9 else {}
        source_ids = [source_id, *more.get('source_ids', [])]
        covered_sources.update(source_ids)
        source = rows.get(source_id, {})
        sources = [ref(bom_file, 'liaisons', source_id)] if source else []
        for section in ['connections', 'internal_connections', 'retired_connections']:
            sources.extend(ref(elec_file, section, row['id']) for row in elec_data[section]
                           if row['id'] in source_ids)
        sources.extend(ref(bom_file, 'items', x) for x in source_ids if x in items)
        sources.extend(more.get('sources', []))
        path = [{'route_id': route.lstrip('-'), 'sense': 'inverse' if route.startswith('-') else 'direct'}
                for route in axes]
        route_ids = [step['route_id'] for step in path]
        cable_ids = sorted({x for route in route_ids for x in register[route]['bom_ids']}
                           | set(more.get('cable_ids', [])))
        for route in route_ids:
            usage[route].append(ident)
        connections.append({'id': ident, 'source_ids': source_ids, 'sources': sources,
                            'scope': scope, 'origin': origin, 'destination': destination,
                            'function': function or source['fonction'], 'cable_ids': cable_ids,
                            'route_ids': route_ids, 'path': path, 'junctions': more.get('junctions', []),
                            'conductors_or_pins': more.get('pins', source.get('connectique')),
                            'path_kind': more.get('path_kind', 'serie'), 'baseline_integration': integration,
                            'integration': integration, 'reason': reason or source.get('adaptation_prototype'),
                            'validation': 'hors_recette_de_cablage' if scope in {'retire', 'reserve_non_montee'}
                            else 'A_VALIDER_PHYSIQUEMENT'})

    assert len({c['id'] for c in connections}) == len(connections)
    assert set(rows) <= covered_sources and set(usage) == set(register)
    assert all(r['sources'] and r['function'] and r['reason'] for r in connections)
    assert all(row['id'] in covered_sources for section in ['connections', 'internal_connections', 'retired_connections']
               for row in elec_data[section])
    junctions = decisions['junctions']
    assert all(set(row['junctions']) <= {j['id'] for j in junctions} for row in connections)

    sa07_xml = native(sa07)
    route_data = []
    for ident, row in register.items():
        metric = measured[ident]
        link = sa07_xml.find(f'./ObjectData/Object[@name="{ident}"]/Properties/Property[@name="LinkedObject"]/XLink')
        assert link is not None, ident
        actual = (sa07.parent / link.attrib['file']).resolve()
        assert actual == (base / metric['file']).resolve() and sha(actual) == metric['sha256'], ident
        proxy = native(actual).find(f'.//Object[@name="{metric["source_object"]}"]/Properties/Property[@name="Proxy"]/Python')
        assert proxy is not None and proxy.attrib['class'] == 'ArchCable', ident
        route_data.append({
            'id': ident, 'connection_ids': usage[ident], 'bom_harness_ids': row['bom_ids'],
            'cad_port_refs': previous[ident]['connector_refs'],
            'native_path': metric['file'], 'native_object': metric['source_object'],
            'assembly_occurrence': f'{sa07.relative_to(base).as_posix()}#{ident}',
            'linked_object': link.attrib['name'], 'baseline_native_sha256': metric['sha256'],
            'baseline_length': parameter(metric['length_mm'], 'mm', 'MESURÉE', ref(proof_file, 'routes', ident),
                                         'Axe CAO recalculé', 'measured'),
            'baseline_min_radius': parameter(metric['radius_mm'], 'mm', 'MESURÉE', ref(proof_file, 'routes', ident),
                                             'Axe CAO recalculé. Limite admissible indépendante généralement inconnue.', 'measured'),
            'nominal_outside_diameter': parameter(row.get('diametre_mm', row.get('diameter_mm')), 'mm', 'HYPOTHÈSE',
                                                  ref(routes_file, 'routes', ident), 'Réservation CAO', 'candidate'),
            'cut_length': parameter(None, 'mm', 'INCONNUE', ref(bom_file, 'items', row['bom_ids'][0]),
                                    'Longueur de coupe avec terminaisons et réserve de pose', 'unknown'),
            'retention_candidates': row.get('supports', row.get('substrat')),
            'baseline_recomputed': metric['recomputed'],
            'baseline_endpoint_deviation_mm': metric['endpoint_errors_mm'],
            'geometry_findings': metric['geometry_findings'],
        })
    by_route = {row['id']: row for row in route_data}
    for ident, parameters in decisions['route_parameters'].items():
        by_route[ident]['route_parameters'] = {
            name: parameter(*definition) for name, definition in parameters.items()}
    usb = by_route['F16']['route_parameters']
    usb['conservative_jacket_budget']['method'] = '508 − 12,5 − 40,8 − 26,2 mm'
    usb['conservative_jacket_budget']['input_refs'] = [
        'F16/total_catalog_length', usb['conservative_jacket_budget']['source']]
    usb['custom_length_study']['method'] = 'Arrondi de 1,05 × 494,608 + (508 − 428,5) mm'
    usb['custom_length_study']['input_refs'] = [
        'F16/baseline_length', 'F16/total_catalog_length', 'F16/conservative_jacket_budget']

    native_docs = {}
    files = [entry.resolve()]
    cable_classes = {'ArchCable', 'CableConduit', 'WireFlex', 'CompoundPath'}
    while files:
        path = files.pop()
        if path in native_docs:
            continue
        assert path.is_relative_to(base.resolve()), path
        doc = native(path)
        native_docs[path] = sorted({p.attrib.get('class') for p in doc.findall('.//Python')} & cable_classes)
        files.extend((path.parent / link.attrib['file']).resolve()
                     for link in doc.findall('.//XLink') if link.attrib.get('file'))
    registered_paths = {r['native_path'] for r in route_data}
    outside = [{'path': p.relative_to(base.resolve()).as_posix(), 'classes': c} for p, c in sorted(native_docs.items())
               if c and p.relative_to(base.resolve()).as_posix() not in registered_paths]

    groups = []
    group_ids = sorted({x for r in connections for x in r['cable_ids']})
    for ident in group_ids:
        item = items[ident]
        groups.append({'id': ident, 'designation': item['designation'],
                       'manufacturer_reference_or_candidate': item.get('reference_fabricant'),
                       'bom_quantity': item.get('quantite'), 'quantity_status': item.get('quantite_statut'),
                       'scope': item.get('perimetre'), 'bom_source': ref(bom_file, 'items', ident),
                       'connection_ids': [r['id'] for r in connections if ident in r['cable_ids']],
                       'route_ids': [r['id'] for r in route_data if ident in r['bom_harness_ids']],
                       'mass_status': item.get('mode_comptage_massique'), 'included_in': item.get('masse_incluse_dans'),
                       'mass_complete_g': item.get('masse_unitaire_g') if item.get('masse_complete_connue_dans_definition') else None,
                       'material_validation': item.get('controle_minimal')})

    nets = collections.defaultdict(dict)
    refs = {'J103', 'J104', 'J201', 'J301', 'J402', 'MOD401', *(f'J50{i}' for i in range(1, 10))}
    for net in ET.parse(net_file).findall('nets/net'):
        for pin in net.findall('node'):
            if pin.attrib['ref'] in refs:
                nets[pin.attrib['ref']][pin.attrib['pin']] = net.attrib['name']
    assert set(nets) == refs and nets['J502']['3'].endswith('BASLER_OPTO_RETURN') and nets['J502']['6'] == 'GND'

    sources = [bom_file, elec_file, routes_file, proof_file, net_file, sa07, entry, reconciliation_file,
               out / 'inventaire_extract.py',
               ver / 'build_prototype.py', ver / 'prototype_routage.py', ver / 'cable_workbench_prototype.py',
               ver / 'definition_bom_electrique.json', ver / 'configuration_faisceau_haut_prototype.json',
               ver / 'connecteurs_coudes_camera_prototype.json', ver / 'interfaces_capteurs_prototype.json',
               ver / 'retenues_faisceaux_prototype.json', ver / 'controle_faisceaux_prototype.json',
               ver / 'controle_registres_prototype.json', ver / 'couverture_bom_cao_prototype.json',
               ver / 'controle_orch_cao_masse_1.json', ver / 'orch_interfaces_equipements.json',
               ver / 'orch_reprise_f20.json', prev / 'analyse_connectivite.json', prev / 'bilan_autonomie.json',
               prev / 'stations_faisceau_complet.json', prev / 'reouverture_faisceau_complet.json',
               prev / 'mouvement_retenues_completes.json', elec / 'contrat_uart_bms.json',
               elec / 'faisceau_systeme_cible_20261003.json', elec / 'verification/controle_recharge_bms_prototype.json',
               elec / 'verification/controle_connecteur_ventilateur_jetson.json',
               mec / 'manifest.json', mec / proof['entry'], mec / sa07.relative_to(base),
               schem / 'verification/connectivity_rules.json', schem / 'bom_candidate.json',
               *sorted(schem.glob('*.kicad_sch'))]
    summary = {'original_bom_connections': len(rows), 'original_bom_connections_mapped': len(rows),
               'global_connections_mapped': len(elec_data['connections']),
               'baseline_route_occurrences': len(register), 'baseline_route_occurrences_mapped': len(usage),
               'baseline_axis_sum_mm': sum(row['baseline_length']['value'] for row in route_data),
               'baseline_native_documents': len(native_docs),
               'baseline_cables_workbench_documents': sum(bool(c) for c in native_docs.values()),
               'baseline_cables_workbench_documents_outside_route_register': outside,
               'onboard_harness_bom_lines': sum(bool(r['route_ids']) for r in groups),
               'connections': len(connections), 'by_scope': dict(collections.Counter(r['scope'] for r in connections)),
               'onboard_baseline_integration': dict(collections.Counter(r['integration'] for r in connections
                                                                       if r['scope'] == 'faisceau_embarque'))}
    result = {'schema': 'cartographe.refonte_faisceaux.inventaire.v1',
              'configuration': 'prototype_cartographe_sans_dock',
              'authority': decisions['authority'], 'counts': summary,
              'sources': [{'path': p.as_posix(), 'sha256': sha(p)} for p in sources],
              'manufacturer_checks': decisions['manufacturer_checks'],
              'connections': connections, 'junctions': junctions, 'routes': route_data, 'harnesses': groups,
              'candidate_ca01_netlist_pins': dict(sorted(nets.items())),
              'nonconformities_and_unknowns': decisions['nonconformities_and_unknowns']}
    net_check = out / 'inventaire_netlist_ca01.json'
    if net_check.is_file():
        regenerated = load(net_check)
        assert all(sha(Path(row['path'])) == row['sha256'] for row in regenerated['scheme_sources'])
        assert regenerated['old_netlist_sha256'] == sha(net_file)
        result['candidate_ca01_netlist_pins'] = regenerated['candidate_ca01_netlist_pins']
        result['ca01_netlist_check'] = {'path': net_check.as_posix(), 'sha256': sha(net_check),
                                       'differences': regenerated['compare_selected_ports']['differences']}
    architecture_file = out / 'architecture.json'
    if architecture_file.is_file():
        planned_groups = {route: group['id'] for group in load(architecture_file)['groupes']
                          for route in group['routes']}
        assert set(planned_groups) == set(register)
        result['target_architecture'] = {'path': architecture_file.as_posix(), 'sha256': sha(architecture_file)}
        for row in connections:
            row['group_ids'] = list(dict.fromkeys(planned_groups[route] for route in row['route_ids']))
    graph_file = out / 'graphe_physique.json'
    if graph_file.is_file():
        attach_candidate(result, graph_file)
    (out / 'inventaire.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    columns = ['id', 'source_ids', 'scope', 'origin', 'destination', 'function', 'cable_ids',
               'route_ids', 'path_kind', 'group_ids', 'segment_ids', 'junctions', 'baseline_integration',
               'integration', 'validation', 'reason']
    with (out / 'inventaire_couverture.csv').open('w', newline='', encoding='utf-8-sig') as output:
        writer = csv.DictWriter(output, columns, delimiter=';')
        writer.writeheader()
        for row in connections:
            writer.writerow({k: ', '.join(row[k]) if isinstance(row.get(k), list) else row.get(k) for k in columns})
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def attach_candidate(result, graph_file):
    graph = load(graph_file)
    routes = {route['id']: route for route in graph['routes']}
    assert len(routes) == len(graph['routes']) and set(routes) == {row['id'] for row in result['routes']}
    groups = {r: group['id'] for group in graph['groupes'] for r in group['routes']}
    assert set(groups) == set(routes) and sum(len(g['routes']) for g in graph['groupes']) == len(routes)
    sleeve_members = collections.defaultdict(set)
    largest_segment_gap_mm = 0.0
    for route in routes.values():
        assert groups[route['id']] == route['groupe']
        segments = route['segments']
        assert segments and all(seg['longueur_mm'] > 0 for seg in segments)
        assert abs(sum(seg['longueur_mm'] for seg in segments) - route['longueur_mm']) < 1e-6
        for first, second in zip(segments, segments[1:]):
            gap_mm = math.dist(first['point_arrivee_mm'], second['point_depart_mm'])
            assert gap_mm < 1e-5 and first['destination'] == second['origine'], route['id']
            largest_segment_gap_mm = max(gap_mm, largest_segment_gap_mm)
        for seg in segments:
            if seg['nature'] == 'gaine_commune':
                sleeve_members[seg['id']].add(route['id'])
    assert dict(sleeve_members) == {sleeve['occurrence']: set(sleeve['membres']) for sleeve in graph['gaines']}
    result['candidate_graph'] = {'path': graph_file.as_posix(), 'sha256': sha(graph_file)}
    result['candidate_graph']['segment_checks'] = {
        'routes_checked': len(routes), 'max_gap_mm': largest_segment_gap_mm,
        'geometry_tolerance_mm': 1e-5, 'length_balance_tolerance_mm': 1e-6,
        'sleeve_members_checked': len(sleeve_members)}
    for row in result['routes']:
        row['candidate'] = {k: routes[row['id']].get(k) for k in
                            ['groupe', 'segments', 'integration', 'longueur_mm', 'appuis', 'justification']}
    for row in result['connections']:
        if not row['route_ids']:
            continue
        path = []
        for step in row['path']:
            route = routes[step['route_id']]
            segments = route.get('segments', [])
            if step['sense'] == 'inverse':
                segments = segments[::-1]
            path.append({'route_id': route['id'], 'group_id': route.get('groupe'),
                         'segment_ids': [s['id'] for s in segments], 'sense': step['sense'],
                         'geometry_integration': route.get('integration')})
        row['candidate_path'] = path
        row['group_ids'] = list(dict.fromkeys(step['group_id'] for step in path))
        row['segment_ids'] = [segment for step in path for segment in step['segment_ids']]
        if row['integration'] != 'non_resolue' and any(step['geometry_integration'] == 'reconstruite' for step in path):
            row['integration'] = 'reconstruite'
    result['counts']['onboard_candidate_integration'] = dict(collections.Counter(
        row['integration'] for row in result['connections'] if row['scope'] == 'faisceau_embarque'))
    result['counts']['candidate_axis_sum_mm'] = sum(row['longueur_mm'] for row in routes.values())


if __name__ == '__main__':
    main()
