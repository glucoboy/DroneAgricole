"""Projette le graphe natif dans le contrat du planificateur C++17 existant."""
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def save(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8')


def project(target):
    graph = load(HERE/'graphe_physique.json')
    source = 'graphe_physique.json et registre natif routes_prototype.json de la copie'
    cable_data = {r['id']:r for r in load(HERE.parents[2]/'cartographe_faisceaux_refonte'/'verification/routes_prototype.json')['routes']}
    compat, nodes, ports, edges, links, routes = [], {}, {}, {}, [], []
    categories = {}
    for sleeve in graph['gaines']:
        group = sleeve['occurrence']
        compat.append({'categories':[group,group],'decision':'allow','source':'graphe_physique.json',
                       'reason':'Autorisation de modéliser le candidat, physique ouverte. '+sleeve['compatibilite']})
        for member in sleeve['membres']:
            if member in categories:
                raise ValueError('Projection v1 limitée à une catégorie de protection par axe : '+member)
            categories[member] = group
    for route in graph['routes']:
        itinerary = route['segments']
        for seg in itinerary:
            a,b = seg['origine'],seg['destination']
            for n in (a,b):
                nodes.setdefault(n,{'id':n,'accessible': True})
            edge = {'id':seg['id'],'from':a,'to':b,'length_mm':seg['longueur_mm'],'usable_width_mm':None}
            if seg['id'] in edges:
                prior = edges[seg['id']]
                if {prior['from'],prior['to']}!={a,b} or abs(prior['length_mm']-edge['length_mm'])>1e-6:
                    raise ValueError('Tronçon partagé incohérent : '+seg['id'])
            else:
                edges[seg['id']] = edge
        a,b = itinerary[0]['origine'],itinerary[-1]['destination']
        for node, xyz in ((a,itinerary[0]['point_depart_mm']),(b,itinerary[-1]['point_arrivee_mm'])):
            ports.setdefault(node,{'id':node,'position_mm':xyz,'exit_axis':None})
            nodes[node]['connector_id'] = node
        cid = route['id']
        links.append({'id':cid,'from':a,'to':b,'category':categories.get(cid,'distinct_'+cid),
                      'outer_diameter_mm':{'value':cable_data[cid]['diametre_mm'],'source':source,'confidence':'measured'},
                      'min_bend_radius_mm':{'value':None,'source':None,'confidence':'unknown'}})
        routes.append({'link_id':cid,'edge_ids':[x['id'] for x in itinerary]})
    target.mkdir(parents=True,exist_ok=True)
    save(target/'projection.json',{'schema_version':1,'connectors':list(ports.values()),'nodes':list(nodes.values()),
                                  'links':links,'edges':list(edges.values()),'compatibility':compat,
                                  'settings':{'fill_ratio':.55,'max_candidates':3,'objective_order':['bundle_segments','support_sites','shared_length_mm','cable_length_mm']}})
    for mode in ('separate','compatible'):
        save(target/(mode+'.json'),{'id':mode,'routes':routes,'grouping':mode})


if __name__ == '__main__':
    project(Path(sys.argv[1]))
