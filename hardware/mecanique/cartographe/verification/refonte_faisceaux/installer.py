"""Applique les variantes mesurées à la copie isolée et construit son graphe."""
import json
import math
import os
from pathlib import Path
import sys
import traceback

from adapter_freecad import (
    App, BASE, BUILD, COPY, ENTRY, HERE, OLD, ROUTES, RUN, SA, Part, Reader,
    add, boot, cable_geometry, common, dependencies, frame, fresh_solid, inclusion,
    inspect_route, make_sleeve, point, read, rebuild_cable_in_isolated_document,
    relief_spec, require, sha, verify_sources, write,
)


def isolation():
    for doc in App.listDocuments().values():
        require(doc.FileName and Path(doc.FileName).resolve().is_relative_to(COPY.resolve()),
                'Document chargé hors copie: ' + str(doc.FileName))


def errors(*docs):
    return [(d.Name, o.Name, list(o.State)) for d in docs for o in d.Objects
            if any(state in ('Error', 'Invalid') for state in o.State)]


def open_copy(relative):
    path = (COPY / relative).resolve()
    require(path.is_relative_to(COPY.resolve()), str(path))
    return App.openDocument(str(path))


def box_values(shape):
    box = shape.BoundBox
    return [getattr(box, k+b) for b in ('Min','Max') for k in 'XYZ']


def volume_delta(a, b):
    require(fresh_solid(a) and fresh_solid(b), 'Entrée BRep invalide pour la comparaison')
    shared = a.common(b)
    require(fresh_solid(shared), 'Intersection de comparaison BRep invalide')
    return [abs(a.Volume-shared.Volume), abs(b.Volume-shared.Volume)]


def adapt_guide(doc, parent, specs, tolerance):
    root = doc.getObject('Ensemble')
    previous = doc.getObject('ResultatPassagesReprise')
    require(previous.Visibility, 'Résultat actif du guide introuvable')
    before = previous.Shape.copy()
    current = previous
    for index, spec in enumerate(specs):
        prior = {o.Name for o in doc.Objects}
        # L'outil suit la gaine dans le repère local du guide. Seule de la
        # matière est enlevée du guide. Son arbre de construction est conservé.
        tool, _ = make_sleeve(doc, relief_spec(spec, parent.Placement), 'Outil' + str(index))
        cut = doc.addObject('Part::Cut', 'Degagement' + spec['occurrence'])
        cut.Base = current
        cut.Tool = tool.Base
        cut.Refine = True
        for item in list(doc.Objects):
            if item.Name not in prior:
                root.addObject(item)
                item.Visibility = False
        require(doc.recompute() and fresh_solid(cut.Shape), 'Guide non monobloc après ouverture')
        current = cut
    previous.Visibility = False
    current.Visibility = True
    root.Visibility = True
    require(doc.recompute(), 'Recalcul final du guide')
    delta = volume_delta(before, current.Shape)
    require(delta[1] <= tolerance and not errors(doc), 'Modification du guide invalide')
    return {'etat': 'CANDIDAT_CONDITIONNEL', 'volume_initial_mm3': before.Volume,
            'volume_retrait_mm3': delta[0], 'volume_ajoute_mm3': delta[1], 'objet_resultat': current.Name,
            'limite': 'Continuité BRep contrôlée. Résistance, ligaments, fluage et tenue du collier à vérifier.'}


def group_model(sa, architecture, route_rows, guide_members, sleeve_specs):
    root = sa.getObject('Ensemble')
    groups = {}
    for config in architecture['groupes']:
        group = sa.addObject('App::Part', 'Groupe_' + config['id'])
        group.Label = config['label']
        root.addObject(group)
        add(group, 'String', 'Corridor', config['zone'])
        add(group, 'String', 'DecisionIntegration', config['decision'])
        add(group, 'String', 'Qualification', 'À valider')
        groups[config['id']] = group
        for cid in config['routes']:
            link = sa.getObject(cid)
            root.removeObject(link)
            group.addObject(link)
            link.Visibility = True
            add(link, 'String', 'IdentifiantParcours', cid)
            add(link, 'String', 'FonctionPhysique', config['id'])
            if cid in route_rows:
                add(link, 'String', 'EtatIntegration', route_rows[cid]['integration'])
            add(link, 'LinkListGlobal', 'RetenuesIdentifiees', [sa.getObject(g) for g in sorted(guide_members.get(cid, []))])
    for spec in sleeve_specs:
        occ = sa.getObject(spec['occurrence'])
        root.removeObject(occ)
        groups[spec['groupe']].addObject(occ)
        occ.Visibility = True
        add(occ, 'LinkList', 'CablesContenus', [sa.getObject(cid) for cid in spec['membres']])
        add(occ, 'LinkListGlobal', 'GuidesVoisins', [sa.getObject(cid) for cid in spec.get('supports', [])])
        add(occ, 'String', 'CompatibiliteCandidate', spec['compatibilite'])
        branch_objects = []
        for end in ('Entree', 'Sortie'):
            branch = sa.addObject('App::FeaturePython', 'Derivation' + spec['occurrence'] + end)
            branch.Label = 'Dérivation ' + end.lower() + ' · ' + spec['occurrence']
            groups[spec['groupe']].addObject(branch)
            branch.Visibility = False
            add(branch, 'Link', 'Gaine', occ)
            add(branch, 'LinkList', 'BranchesIndividuelles', [sa.getObject(cid) for cid in spec['membres']])
            placement, span = frame(spec)
            add(branch, 'Vector', 'CentreSection', placement.multVec(App.Vector(span/2, 0, 0 if end=='Entree' else spec['longueur_mm'])))
            branch_objects.append(branch)
        # Les jonctions pointent sur la gaine et ses membres. La gaine ne
        # pointe pas vers les jonctions, afin de conserver un graphe natif acyclique.
        for cid in spec['membres']:
            link = sa.getObject(cid)
            previous = list(link.TronconsCommuns) if 'TronconsCommuns' in link.PropertiesList else []
            add(link, 'StringList', 'TronconsCommuns', previous + [spec['occurrence']])
    for junction in architecture['jonctions']:
        obj = sa.addObject('App::FeaturePython', 'Jonction_' + junction['id'])
        obj.Label = junction['nature']
        groups[junction['groupe']].addObject(obj)
        obj.Visibility = False
        add(obj, 'Link', 'Entrant', sa.getObject(junction['entrant']))
        add(obj, 'LinkList', 'Sortants', [sa.getObject(cid) for cid in junction['sortants']])
        if junction['point_mm'] is not None:
            add(obj, 'Vector', 'PointNominal', App.Vector(*junction['point_mm']))
    return groups


def stations_in(value):
    if isinstance(value, dict):
        if ('cable' in value or 'cables' in value) and ('support' in value or 'id' in value):
            yield value
        for v in value.values():
            yield from stations_in(v)
    elif isinstance(value, list):
        for v in value:
            yield from stations_in(v)


def holders(routes_data, routes, construction):
    lookup = {
        'cadre_avionique': 'P75_Cadre', 'retenues_puissance_droite': 'P73_Guide',
        'retenues_locales_droite': 'P73_Guide', 'retenues_basses_droite': 'P73_Guide',
        'retenues_puissance_gauche': 'P72_Guide', 'retenues_locales_gauche': 'P72_Guide',
        'retenues_basses_gauche': 'P72_Guide', 'retenues_entree_f41': 'P72_Guide',
        'berceau_reserve_usb': 'P77_BerceauReserveUSB', 'retenue_camera_m8': 'P78_RetenueCameraM8',
    }
    ids = {r['occurrence'] for r in construction['occurrences']}
    output = {}
    for key, value in routes_data['guides'].items():
        for row in stations_in(value):
            holder = row.get('id') if row.get('id') in ids else lookup.get(key)
            for cid in row.get('cables', [row.get('cable')]):
                if cid in routes and holder in ids:
                    output.setdefault(cid, set()).add(holder)
    return output


def find_section(wire, spec, diameter):
    placement, span = frame(spec)
    length = spec['longueur_mm']
    inverse = placement.inverse()
    passed = 0.0
    matches = []
    for edge in wire.Edges:
        if edge.Curve.TypeId == 'Part::GeomLine':
            a, b = [edge.valueAt(t) for t in (edge.FirstParameter, edge.LastParameter)]
            if edge.Orientation == 'Reversed':
                a, b = b, a
            u, v = inverse.multVec(a), inverse.multVec(b)
            radial = math.hypot(u.y, max(0, -u.x, u.x-span))
            if (abs(u.x-v.x) < 1e-7 and abs(u.y-v.y) < 1e-7 and radial + diameter/2 <= spec['rayon_interieur_mm'] + 1e-7
                    and min(u.z,v.z) <= 1e-7 and max(u.z,v.z) >= length-1e-7):
                offsets = [(abs(z-u.z)+passed, a+(b-a)*((z-u.z)/(v.z-u.z)), side)
                           for z,side in ((0,'A'),(length,'B'))]
                matches.append(sorted(offsets, key=lambda x:x[0]))
        passed += edge.Length
    require(len(matches) == 1, 'Segment commun sans axe local unique: ' + spec['occurrence'])
    return matches[0]


def graph_for(routes, architecture, sleeve_specs, guide_members, geometries, changed):
    groups = {cid: g['id'] for g in architecture['groupes'] for cid in g['routes']}
    count = sum(len(g['routes']) for g in architecture['groupes'])
    require(set(groups) == set(routes) and count == len(routes), 'Partition physique incomplète ou redondante')
    graph = []
    joints = {name: j['id'] for j in architecture['jonctions'] if j['point_mm'] for name in j['sortants']}
    exits = {j['entrant']: j['id'] for j in architecture['jonctions'] if j['point_mm']}
    for cid, row in routes.items():
        wire = geometries[cid]
        start = joints.get(cid, cid+':origine')
        end = exits.get(cid, cid+':destination')
        itinerary = []
        intervals = []
        for spec in sleeve_specs:
            if cid in spec['membres']:
                a, b = find_section(wire, spec, row['diametre_mm'])
                intervals.append((a,b,spec['occurrence']))
        cursor = 0.0
        current = start
        current_position = row['points_mm'][0]
        for index, (a,b,shared) in enumerate(sorted(intervals, key=lambda x:x[0][0])):
            require(a[0] > cursor and b[0] < wire.Length, 'Segments communs superposés ou terminaux : ' + cid)
            dest = shared + ':' + a[2]
            itinerary.append({'id':cid + ':branche_' + str(index+1), 'origine':current,'destination':dest,
                              'nature':'branche_individuelle','longueur_mm':a[0]-cursor,
                              'point_depart_mm':current_position,'point_arrivee_mm':point(a[1])})
            current = shared + ':' + b[2]
            itinerary.append({'id':shared, 'origine':dest,'destination':current,
                              'nature':'gaine_commune','longueur_mm':b[0]-a[0],
                              'point_depart_mm':point(a[1]),'point_arrivee_mm':point(b[1])})
            cursor = b[0]
            current_position = point(b[1])
        nature = 'tronc_oem' if cid=='AIRY' else 'branche_individuelle'
        itinerary.append({'id':cid + ':terminal', 'origine':current,'destination':end,
                          'nature':nature, 'longueur_mm':wire.Length-cursor,
                          'point_depart_mm':current_position,'point_arrivee_mm':row['points_mm'][-1]})
        graph.append({'id':cid,'groupe':groups[cid],'segments':itinerary,'longueur_mm':wire.Length,
                      'appuis':sorted(guide_members.get(cid, [])), 'support_documente':row.get('supports', []),
                      'integration':'reconstruite' if cid in changed else 'conservee',
                      'justification': 'Géométrie native recalculée sur la nouvelle branche MAIN.' if cid in changed else
                        'Axe et interfaces conservés. La décision de groupe et les contrôles restent applicables.',
                      'objet':row['objet_cable'],'fichier':row['fichier'],
                      'validation':'À valider'})
    return {'schema':'cartographe.graphe-physique.v1','groupes':architecture['groupes'],
            'jonctions':architecture['jonctions'],'gaines':sleeve_specs,'routes':graph}


def mermaid(graph):
    rows = ['flowchart LR']
    nodes = {}
    def node(name):
        if name not in nodes:
            nodes[name] = 'n' + str(len(nodes))
            rows.append(f'  {nodes[name]}["{name}"]')
        return nodes[name]
    for item in graph['routes']:
        for seg in item['segments']:
            a, b = node(seg['origine']), node(seg['destination'])
            # Le JSON conserve les extrémités déportées de chacun des câbles.
            rows.append(f'  {a} -->|{item["id"]} · {seg["longueur_mm"]:.1f} mm| {b}')
    return '\n'.join(rows) + '\n'


def install(ids):
    environment = boot()
    selection = read(HERE / 'variantes.json')
    tolerance = selection['tolerance_volume_mm3']
    architecture = read(HERE / 'architecture.json')
    selected = [c for c in selection['candidats'] if c['id'] in ids]
    require(len(selected) == len(ids) and len({c['occurrence'] for c in selected}) == len(ids), 'Sélection contradictoire')
    receipt = read(COPY / 'experiment.json')
    require(verify_sources(receipt)['sources_unchanged'], 'Baseline modifiée')
    for path, expected in receipt['inputs_sha256'].items():
        require(sha(COPY / path)==expected, 'Copie déjà modifiée, repartir d’une copie neuve : ' + path)
    for spec in selected:
        result = read(RUN / (spec['id'] + '.json'))
        require(result['ok'] and result['parametres']==spec and result['finalized'], 'Variante non admissible : ' + spec['id'])
        require(not spec['compatibilite'].startswith('INCONNUE'), 'Cohabitation sans justification : ' + spec['id'])
    routes_data = read(COPY / ROUTES)
    routes = {r['id']: r for r in routes_data['routes']}
    construction = read(COPY / BUILD)
    references = construction['references']
    occurrences = {r['occurrence']: r for r in construction['occurrences'] if r['parent']==SA}
    guide_members = holders(routes_data, routes, construction)
    native_docs = {}
    for spec in selected:
        result = read(RUN / (spec['id'] + '.json'))
        for cid in result['parcours_modifies']:
            native_docs[cid] = open_copy(routes[cid]['fichier'])
        if spec.get('degagement_guide_mm'):
            guide = spec['supports'][0]
            if guide not in native_docs:
                native_docs[guide] = open_copy(occurrences[guide]['source'])
    main = open_copy(ENTRY)
    sa = next(d for d in App.listDocuments().values() if Path(d.FileName).resolve()==(COPY / SA).resolve())
    isolation()
    print('Dépendances résolues dans la copie', flush=True)
    changed = {}
    sleeve_specs = []
    protection_meta = {}
    new_docs = {}
    for spec in selected:
        checked = read(RUN / (spec['id'] + '.json'))
        for cid, result in checked['parcours_modifies'].items():
            row = routes[cid]
            doc = native_docs[cid]
            cable = doc.getObject(row['objet_cable'])
            wire = cable.Base
            wire.Points = [wire.Placement.inverse().multVec(App.Vector(*p)) for p in result['points_mm']]
            check = rebuild_cable_in_isolated_document(doc, cable)
            geo = cable_geometry(cable)
            require(check['status']=='pass' and abs(geo['longueur_courbe_mm']-result['longueur_mm'])<1e-6,
                    'Reconstruction native différente de la variante : ' + cid)
            require(result['points_mm'][0]==row['points_mm'][0] and result['points_mm'][-1]==row['points_mm'][-1],
                    'Extrémité modifiée : ' + cid)
            changed[cid] = {'longueur_initiale_mm':row['longueur_courbe_mm'],
                            'longueur_finale_mm':geo['longueur_courbe_mm']}
            row.update(geo, points_mm=result['points_mm'], longueur_trace_mm=round(geo['longueur_courbe_mm'],3),
                       longueur_polyline_mm=sum((App.Vector(*b)-App.Vector(*a)).Length for a,b in zip(result['points_mm'],result['points_mm'][1:])))
        name = spec['occurrence']
        doc = App.newDocument(name)
        wall, inner = make_sleeve(doc, spec)
        native_path = 'pieces/commerce/' + name + '.FCStd'
        doc.saveAs(str(COPY / native_path))
        new_docs[name] = doc
        link = sa.getObject(name) or sa.addObject('App::Link', name)
        link.LinkedObject = wall
        link.LinkTransform = False
        link.Placement = wall.getGlobalPlacement()
        link.Label = name + ' · gaine commune'
        sa.getObject('Ensemble').addObject(link)
        link.Visibility = True
        rec = occurrences.get(name, {})
        if not rec:
            construction['occurrences'].append(rec)
        elif name=='ProtectionF38':
            references[:] = [ref for ref in references if ref['fichier']!=rec['source']]
        rec.update(parent=SA, occurrence=name, source=native_path, objet_source=wall.Name,
                   matrice=list(link.Placement.toMatrix().A), bom_ids=[], statut='À valider')
        references.append({'reference':name,'fichier':native_path,'objet':wall.Name,'bom_ids':[],
                           'type':'protection_textile_enveloppe','statut':'Implémenté','qualification':'À valider',
                           'sha256':sha(COPY / native_path),'bbox_mm':box_values(wall.Shape),'compose_valide':True})
        sleeve_specs.append(spec)
        protection_meta[name] = {'role':'gaine','members':spec['membres'],'axis_object':wall.AxeReference.Name,
                                 'cavity_object':inner.Name,'window_object':wall.FenetreControle.Name,
                                 'fresh_objects':[o.Name for o in doc.Objects if hasattr(o,'Shape')]}
    if not any(s['occurrence']=='ProtectionF38' for s in sleeve_specs):
        original = architecture['gaines_heritees'][0]
        sleeve_specs.append(dict(original, id='F38_ORIGINAL_L80', axes_bords_mm=[[-30,-104,52],[-30,-94,52]],
                                 occurrence='ProtectionF38', direction=[1,0,0], rayon_interieur_mm=4, longueur_mm=80,
                                 supports=['P73_Guide'], compatibilite='CANDIDAT_CONDITIONNEL, aller et retour F38, thermique et retenue ouverts'))
        protection_meta['ProtectionF38'] = {'role':'gaine','members':original['membres'],'axis_length_mm':80,
                                            'cavity_object':'Interieur','window_x_mm':[-30,50],
                                            'fresh_objects':['ExterieurBout0','ExterieurBout1','ExterieurMilieu','Exterieur',
                                                             'InterieurBout0','InterieurBout1','InterieurMilieu','Interieur','Protection']}
    guides = {}
    for gid in sorted({s['supports'][0] for s in selected if s.get('degagement_guide_mm')}):
        specs = [s for s in selected if s.get('degagement_guide_mm') and s['supports'][0]==gid]
        guides[gid] = adapt_guide(native_docs[gid], sa.getObject(gid), specs, tolerance)
        protection_meta[gid] = {'role':'fixation', 'fresh_objects':[guides[gid]['objet_resultat']]}
        print(gid, guides[gid]['volume_retrait_mm3'], flush=True)
    baseline_reader = Reader(BASE)
    geometries = {}
    for cid,row in routes.items():
        shape = (native_docs[cid].getObject(row['objet_parcours']).Shape if cid in changed else
                 baseline_reader.shape(row['fichier'], row['objet_parcours']))
        require(len(shape.Wires)==1, 'Axe natif indisponible : ' + cid)
        geometries[cid] = shape.Wires[0]
    graph = graph_for(routes, architecture, sleeve_specs, guide_members, geometries, changed)
    route_rows = {r['id']:r for r in graph['routes']}
    groups = group_model(sa, architecture, route_rows, guide_members, sleeve_specs)
    sa.getObject('Ensemble').touch()
    main.getObject('Ensemble').touch()
    require(sa.recompute() and main.recompute(), 'Recalcul du modèle intégré')
    isolation()
    require(not errors(sa, main, *native_docs.values(), *new_docs.values()), 'Objet natif en erreur')
    require(all(g.Placement.isIdentity() for g in groups.values()), 'Placement d’un groupe intermédiaire')
    for cid,row in occurrences.items():
        link = sa.getObject(cid)
        require(link and link.Visibility and link.LinkedObject and
                Path(link.LinkedObject.Document.FileName).resolve()==(COPY / row['source']).resolve() and
                link.LinkedObject.Name==row['objet_source'] and
                max(abs(a-b) for a,b in zip(row['matrice'], link.Placement.toMatrix().A))<1e-8,
                'Identité, visibilité ou pose modifiée : ' + cid)
    for key, doc in native_docs.items():
        doc.save()
        row = occurrences[key]
        for ref in references:
            if ref['fichier']==row['source']:
                ref['sha256'] = sha(COPY / ref['fichier'])
                obj = doc.getObject(guides[key]['objet_resultat'] if key in guides else routes[key]['objet_cable'])
                ref['bbox_mm'] = box_values(obj.Shape)
    sa.save()
    main.save()
    write(COPY / ROUTES, routes_data)
    construction['refonte_faisceaux'] = {'groupes':architecture['groupes'],'gaines':sleeve_specs,'guides':guides}
    write(COPY / BUILD, construction)
    manifest = read(COPY / 'manifest.json')
    prototype = manifest['prototype_cartographe']
    prototype.update(references=construction['references'], occurrences=construction['occurrences'],
                     refonte_faisceaux=construction['refonte_faisceaux'])
    manifest['qualification'] = 'À valider'
    manifest['date_mise_a_jour'] = '2026-11-09'
    write(COPY / 'manifest.json', manifest)
    write(HERE / 'graphe_physique.json', graph)
    (HERE / 'graphe_physique.mmd').write_text(mermaid(graph),encoding='utf-8')
    write(HERE / 'metadonnees_controle.json', protection_meta)
    final = {p.relative_to(COPY).as_posix():sha(p) for p in dependencies(COPY,[ENTRY])}
    proof = {'schema':'cartographe.refonte-installation.v1','finalized':True,'environment':environment,
             'entree':ENTRY,'variantes':ids,'parcours_modifies':changed,'guides_modifies':guides,
             'modeles_natifs_sha256':final,'registre_construction_sha256':sha(COPY / BUILD),
             'source_originale':verify_sources(read(BASE / 'experiment.json')),
             'source_candidat_8_novembre':verify_sources(receipt),
             'metadata_sha256':sha(HERE / 'metadonnees_controle.json'),
             'graphe_sha256':sha(HERE / 'graphe_physique.json'),
             'comparaison_longueur_mm':{'avant':sum(r['longueur_courbe_mm'] for r in read(BASE / ROUTES)['routes']),
                                        'apres':sum(w.Length for w in geometries.values())}}
    require(proof['source_originale']['sources_unchanged'] and proof['source_candidat_8_novembre']['sources_unchanged'],
            'Empreinte originale altérée')
    write(HERE / 'installation.json', proof)
    print('Installation finalisée',len(final),len(graph['routes']),ids,flush=True)


if __name__=='__main__':
    try:
        install(sys.argv[1:])
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(0)
    except Exception:
        traceback.print_exc()
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(2)
