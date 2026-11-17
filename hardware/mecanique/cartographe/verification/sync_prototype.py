"""Synchronisation déclarative du catalogue et de la couverture BOM après contrôle CAO."""
from pathlib import Path
import json, hashlib, math
from datetime import date

MEC=Path(__file__).resolve().parents[1]
VER=MEC/'verification'
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

if (MEC/'manifest.json').exists() and read(MEC/'manifest.json').get('prototype_cartographe', {}).get('orch_cao_masse_1'):
    raise RuntimeError('Synchronisation initiale refusée : elle supprimerait les métadonnées ORCH-CAO-MASSE-1. Utiliser orch_integrate_cao.py puis les contrôles du lot ; les preuves historiques sont conservées séparément.')


def validate_recettes(build, ver=VER):
    """Lier toute nouvelle publication aux recettes complètes de construction."""
    recipes = build.get('recettes_sha256')
    required = {'build_prototype.py', 'prototype_routage.py', 'prototype_guides.py',
                'cable_workbench_prototype.py', 'configuration_faisceau_haut_prototype.json',
                'prototype_retenues.py', 'prototype_retenues_puissance.py',
                'prototype_retenues_capteurs.py', 'prototype_retenues_locales.py',
                'prototype_retenues_bras.py', 'prototype_retenues_basses.py',
                'prototype_retenues_hautes.py', 'prototype_retenues_reserves.py',
                'prototype_retenues_departs.py', 'prototype_fixations_equipements.py', 'prototype_connecteurs.py',
                'connecteurs_coudes_camera_prototype.json', 'etage_batterie_helpers.py'}
    if not isinstance(recipes, dict) or not required.issubset(recipes):
        raise ValueError('Synchronisation refusée : empreintes des recettes absentes ou incomplètes.')
    for name, digest in recipes.items():
        if Path(name).name != name or not (ver/name).is_file() or sha(ver/name) != digest:
            raise ValueError('Synchronisation refusée : recette absente, hors périmètre ou modifiée : ' + name)
    if build.get('script_sha256') != recipes['build_prototype.py']:
        raise ValueError('Synchronisation refusée : empreinte du constructeur incohérente.')


def validate_fixations_guides_evidence(build, routes, report, mec=MEC, ver=VER):
    """Exiger le contrôle complet et courant des guides et de leur visserie."""
    def require(condition, message):
        if not condition:
            raise ValueError('Synchronisation fixations guides refusée : ' + message)

    require(build.get('finalisation_correcte') is True, 'construction non finalisée')
    require(report.get('finalisation_correcte') is True, 'contrôle non finalisé')
    require(report.get('fichiers_non_modifies') is True, 'fichiers modifiés pendant le contrôle')
    require(report.get('construction_sha256') == sha(ver/'construction_prototype.json'), 'construction périmée')
    require(report.get('script_sha256') == sha(ver/'verify_fixations_guides_prototype.py'), 'recette de contrôle périmée')
    require(report.get('lecteur_sha256') == sha(ver/'read_brep_prototype.py'), 'lecteur BRep périmé')
    require(report.get('recettes_sha256') == build.get('recettes_sha256'), 'recettes de construction différentes')
    validate_recettes(build, ver)
    expected_files = {r['fichier']: r['sha256'] for r in build['references']}
    expected_files.update(build['sources_preservees'])
    require(report.get('natifs_sha256') == expected_files, 'périmètre des natifs différent')
    require(all((mec/p).is_file() and sha(mec/p) == h for p, h in expected_files.items()),
            'natif absent ou changé depuis le contrôle')
    for field in ('erreurs', 'collisions'):
        require(report.get(field) == [], field + ' absent ou non vide')
    sa2, sa7 = 'SA02_Prototype_Batterie/', 'SA07_Prototype_Faisceaux/'
    occurrences = {Path(o['parent']).stem+'/'+o['occurrence']: o for o in build['occurrences']
                   if o['parent'].startswith('sous_assemblages/')}
    guides = {n for n in occurrences if n.startswith(sa7) and
              n.split('/')[-1].startswith(('VisGuide', 'RondelleGuide', 'EcrouGuide'))}
    counts = {p: sum(n.split('/')[-1].startswith(p) for n in guides)
              for p in ('VisGuide', 'RondelleGuide', 'EcrouGuide')}
    require(counts == {'VisGuide': 10, 'RondelleGuide': 14, 'EcrouGuide': 10}, 'comptage des guides incorrect')
    right = {sa2+p+str(i) for i in (2, 3)
             for p in ('VisButee', 'RondelleButeeH', 'RondelleButeeB', 'EcrouButee')}
    supports = {sa7+'P72_Guide', sa7+'P73_Guide', sa7+'P75_Cadre', sa2+'BerceauQS8',
                sa2+'Semelle', 'SA03_Prototype_Energie/Isolation', 'SA05_Prototype_Avionique/Interface',
                sa7+'P77_BerceauReserveUSB', sa7+'P78_RetenueCameraM8'}
    focus = guides | right | supports
    require((focus | {sa2+'QS8_manuel'}).issubset(occurrences), 'occurrences requises absentes')
    require(report.get('fixations_guides') == counts and report.get('fixations_butee_droite') == 8
            and report.get('fixations_total') == 42, 'comptage de la preuve incomplet')
    controlled = report.get('occurrences_controlees', [])
    require(len(controlled) == len(focus) and set(controlled) == focus, 'périmètre contrôlé incomplet')
    pieces = report.get('pieces_controlees', [])
    require(len(pieces) == len(supports) and {r['objet'] for r in pieces} == supports
            and all(r.get('valide') is True and r.get('solides') == 1 for r in pieces), 'contrôle des pièces incomplet')
    stations = {f'GuideBas{i}' for i in range(4)} | {f'GuideMilieu{i}' for i in range(2)}
    stations |= {f'GuideHaut{i}' for i in range(4)} | {'ButeeDroite2', 'ButeeDroite3'}
    stacks = report.get('empilements', [])
    require(len(stacks) == len(stations) and {r['id'] for r in stacks} == stations
            and all(r.get('couches') and r.get('contacts') for r in stacks), 'empilements incomplets')
    ids = {r['id'] for r in routes['routes']}
    physical = [o for n, o in occurrences.items() if not (n.startswith(sa7) and o['occurrence'] in ids)]
    require(report.get('obstacles_controles') == len(physical), 'contrôle des obstacles incomplet')
    seat = report.get('appui_qs8_mm')
    require(isinstance(seat, (int, float)) and not isinstance(seat, bool) and 0 <= seat <= 1e-4,
            'appui QS8 absent ou non conforme')


def validate_retenues_evidence(build, routes, contract, report, mec=MEC, ver=VER):
    """Exiger une preuve courante couvrant chaque retenue et tout le parcours."""
    def require(condition, message):
        if not condition:
            raise ValueError('Synchronisation retenues refusée : ' + message)

    def number(value, minimum=0):
        return isinstance(value, (int, float)) and not isinstance(value, bool) \
            and math.isfinite(value) and value >= minimum

    require(build.get('finalisation_correcte') is True, 'construction non finalisée')
    require(report.get('finalisation_correcte') is True and report.get('conforme') is True,
            'contrôle non finalisé ou non conforme')
    require(report.get('fichiers_non_modifies') is True, 'fichiers modifiés pendant le contrôle')
    require(report.get('erreurs') == [], 'erreurs absentes ou non vides')
    expected_inputs = {name: sha(ver/name) for name in
                       ('construction_prototype.json', 'routes_prototype.json', 'retenues_faisceaux_prototype.json')}
    reserve_stations = {}
    for item in contract['routes']:
        for entry in item['retenues']:
            if entry['mode'] == 'reserve':
                reserve_stations.setdefault(entry.get('collier_id', entry['station_id']), set()).add(
                    (item['id'], entry['station_id']))
    reserve_collars, reserve_direct = {}, set()
    reserve_proof = None
    if reserve_stations:
        proof_path = (mec/contract.get('preuve_enveloppement_reserves', '')).resolve()
        require(proof_path.parent == ver.resolve() and proof_path.suffix == '.json' and proof_path.is_file(),
                'preuve d’enveloppement absente ou hors périmètre')
        reserve_proof = read(proof_path)
        script = (mec/reserve_proof.get('script_fichier', '')).resolve()
        require(script.parent == ver.resolve() and script.suffix == '.py' and script.is_file()
                and sha(script) == reserve_proof.get('script_sha256'), 'recette d’enveloppement périmée')
        require(reserve_proof.get('schema_version') == 1 and all(reserve_proof.get(k) is True for k in
                ('finalisation_correcte', 'conforme', 'fichiers_non_modifies'))
                and reserve_proof.get('erreurs') == [] and reserve_proof.get('collisions') == [],
                'preuve d’enveloppement non conforme')
        require(reserve_proof.get('construction_sha256') == expected_inputs['construction_prototype.json']
                and reserve_proof.get('routes_sha256') == expected_inputs['routes_prototype.json']
                and reserve_proof.get('contrat_sha256') == expected_inputs['retenues_faisceaux_prototype.json'],
                'preuve d’enveloppement périmée')
        expected_inputs.update({proof_path.name:sha(proof_path), script.name:sha(script)})
        rows = reserve_proof.get('colliers', [])
        require(len(rows) == len(reserve_stations) and {r['collier_id'] for r in rows} == set(reserve_stations),
                'colliers de réserve incomplets ou dupliqués')
        for row in rows:
            points = row.get('stations', [])
            require(len(points) == len(reserve_stations[row['collier_id']])
                    and {(s['cable'], s['station_id']) for s in points} == reserve_stations[row['collier_id']]
                    and all(row.get(k) is True for k in ('valide', 'passage_lumieres', 'enveloppement_pile'))
                    and row.get('solides') == 1, 'boucle de réserve ou couverture des spires non conforme')
            reserve_collars[row['collier_id']] = row
    require(report.get('entrees_sha256') == expected_inputs, 'entrées absentes ou périmées')
    require(report.get('script_sha256') == sha(ver/'verify_retenues_faisceaux_prototype.py'),
            'recette de contrôle périmée')
    require(report.get('lecteur_sha256') == sha(ver/'read_brep_prototype.py'), 'lecteur BRep périmé')
    validate_recettes(build, ver)
    expected_files = {r['fichier']: r['sha256'] for r in build['references']}
    expected_files.update(build['sources_preservees'])
    require(report.get('natifs_sha256') == expected_files, 'périmètre des natifs différent')
    require(reserve_proof is None or reserve_proof.get('natifs_sha256') == expected_files,
            'périmètre des natifs de réserve différent')
    require(all((mec/p).is_file() and sha(mec/p) == h for p, h in expected_files.items()),
            'natif absent ou changé depuis le contrôle')
    require(contract.get('schema_version') == 1, 'schéma du contrat non pris en charge')
    route_ids = [r['id'] for r in routes['routes']]
    require(bool(route_ids) and len(set(route_ids)) == len(route_ids), 'routes absentes ou dupliquées')
    for label, rows in [('contrat', contract.get('routes', [])), ('preuve', report.get('routes', []))]:
        identifiers = [r['id'] for r in rows]
        require(len(identifiers) == len(route_ids) and set(identifiers) == set(route_ids),
                'couverture des routes du ' + label + ' incomplète ou dupliquée')
    native_routes = {r['id']: r for r in routes['routes']}
    measures = {r['id']: r for r in report['routes']}
    references = {r['reference']: r for r in build['references']}
    anchors, assignments = {}, 0
    for item in contract['routes']:
        measured = measures[item['id']]
        length = measured.get('longueur_mm')
        require(number(length, 1e-5) and abs(length-native_routes[item['id']]['longueur_courbe_mm']) <= 1e-4,
                'longueur absente ou différente du parcours')
        stations, entries = measured.get('stations', []), item.get('retenues', [])
        ids = [e['station_id'] for e in entries]
        require(bool(ids) and len(set(ids)) == len(ids) and not {'DEBUT', 'FIN'}.intersection(ids)
                and len(stations) == len(ids) and {s['station_id'] for s in stations} == set(ids),
                'retenues absentes, incomplètes ou dupliquées')
        positions = {'DEBUT': 0.0, 'FIN': length}
        for entry in entries:
            station = next(s for s in stations if s['station_id'] == entry['station_id'])
            require(entry.get('etat_integration') == 'Implémenté', 'station non intégrée')
            source = references[entry['reference']]['fichier']
            supports = [o for o in build['occurrences'] if o.get('source') == source
                        and o['parent'].startswith('sous_assemblages/')
                        and (not entry.get('occurrence') or o['occurrence'] == entry['occurrence'])]
            require(len(supports) == 1, 'occurrence du support absente ou ambiguë')
            support = supports[0]['parent']+'#'+supports[0]['occurrence']
            collar = entry.get('collier_id', entry['station_id'])
            mode = entry.get('mode')
            require(mode in ('individuel', 'commun', 'reserve') and station.get('mode') == mode
                    and station.get('support') == support and station.get('collier_id') == collar
                    and station.get('station_native') == entry['cle_id'], 'affectation de retenue différente')
            anchor = (support, mode, entry.get('ancrage_commun', entry['cle_id']))
            require(collar not in anchors or anchors[collar] == anchor, 'collier partagé entre ancrages incompatibles')
            anchors[collar] = anchor
            s, distance, gap = station.get('s_mm'), station.get('distance_projection_mm'), station.get('jeu_surface_appui_mm')
            tolerance = entry.get('tol_projection_mm', .6)
            allowed = entry.get('jeu_support_max_mm', item['limites'].get('jeu_support_max_mm', 1.0))
            support_mode = station.get('mode_appui', 'direct')
            if mode == 'reserve':
                reserve = reserve_collars[collar]
                point = next(s['point_mm'] for s in reserve['stations']
                             if s['cable'] == item['id'] and s['station_id'] == entry['station_id'])
                nominal = station.get('point_nominal_mm', [])
                require(reserve.get('support') == support and len(nominal) == len(point) == 3
                        and all(number(a, -float('inf')) and number(b, -float('inf')) and abs(a-b) <= 1e-4
                                for a,b in zip(nominal, point)), 'point ou support de réserve différent')
                require(support_mode in ('direct', 'enveloppement_reserve'), 'mode d’appui de réserve inconnu')
                if support_mode == 'direct':
                    reserve_direct.add(collar)
            else:
                require(support_mode == 'direct', 'enveloppement utilisé hors réserve')
            require(station.get('erreurs') == [] and number(s) and s <= length+1e-4
                    and number(tolerance) and number(allowed) and number(distance) and number(gap, -1e-3)
                    and station.get('tolerance_projection_mm') == tolerance and station.get('jeu_max_mm') == allowed
                    and distance <= tolerance+1e-4
                    and (gap <= allowed+1e-4 or (mode == 'reserve' and support_mode == 'enveloppement_reserve')),
                    'mesure de retenue non conforme')
            positions[entry['station_id']] = s
        portions = measured.get('portions', [])
        expected = {(p['debut'], p['fin'], p['type']): p for p in item['portions']}
        require(bool(expected) and len(expected) == len(item['portions']) == len(portions)
                and {(p['debut'], p['fin'], p['type']) for p in portions} == set(expected),
                'portions absentes, incomplètes ou dupliquées')
        intervals = []
        for portion in portions:
            original = expected[portion['debut'], portion['fin'], portion['type']]
            kind = portion['type']
            a, b = positions[portion['debut']], positions[portion['fin']]
            limit = original.get('portee_max_mm', item['limites']['portee_max_mm'].get(kind))
            require(kind in ('guidee', 'transition_courte', 'boucle_souple') and number(limit, 1e-5)
                    and b-a >= 1e-5 and b-a <= limit+1e-4 and portion.get('conforme') is True
                    and portion.get('portee_max_mm') == limit
                    and all(number(portion.get(key)) and abs(portion[key]-value) <= 1e-4
                            for key, value in [('s_debut_mm', a), ('s_fin_mm', b), ('longueur_mm', b-a)]),
                    'portion non conforme')
            require(kind != 'boucle_souple' or bool(original.get('justification')), 'boucle souple sans justification')
            intervals.append((a, b))
        end = 0.0
        for a, b in sorted(intervals):
            require(abs(a-end) <= 1e-4, 'trou ou recouvrement dans les portions')
            end = b
        require(abs(end-length) <= 1e-4, 'extrémité du parcours non couverte')
        assignments += len(stations)
    require(reserve_direct == set(reserve_collars), 'réserve sans appui direct')
    require(report.get('nombre_routes') == len(route_ids) and report.get('nombre_affectations') == assignments
            and report.get('nombre_colliers_identifies') == len(anchors), 'comptage de la preuve incomplet')


def validate_equipements_evidence(build, routes, report, mec=MEC, ver=VER):
    """Refuser une preuve périmée ou partielle des ancrages et quatre boucles."""
    def require(condition, message):
        if not condition:
            raise ValueError('Synchronisation fixations équipements refusée : '+message)
    def number(value):
        return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value)
    validate_recettes(build,ver)
    require(build.get('finalisation_correcte') is True and
            all(report.get(k) is True for k in ('finalisation_correcte','conforme','fichiers_non_modifies')),
            'contrôle non finalisé, non conforme ou fichiers modifiés')
    require(report.get('schema_version')==1,'schéma de preuve absent ou inconnu')
    require(report.get('erreurs')==[] and report.get('collisions')==[], 'erreurs ou collisions absentes/non vides')
    require(report.get('construction_sha256')==sha(ver/'construction_prototype.json') and
            report.get('routes_sha256')==sha(ver/'routes_prototype.json'),'construction ou routes périmées')
    for field,name in [('script_sha256','verify_fixations_equipements_prototype.py'),
                       ('module_sha256','prototype_fixations_equipements.py'),
                       ('lecteur_sha256','read_brep_prototype.py')]:
        require(report.get(field)==sha(ver/name),'recette ou lecteur périmé : '+name)
    files={r['fichier']:r['sha256'] for r in build['references']}
    files.update(build['sources_preservees'])
    require(report.get('natifs_sha256')==files and all((mec/p).is_file() and sha(mec/p)==h for p,h in files.items()),
            'périmètre des natifs différent ou natif périmé')
    collars={'CollierAncrageRF0','CollierAncrageRF1','CollierMIDI0','CollierMIDI1'}
    supports={'SupportGNSS','SupportSecurite','SupportRF0','SupportRF1'}
    hardware={prefix+kind+suffix+str(i) for kind in ('GNSS','Securite') for i in (0,1)
              for prefix,suffix in [('VisSupport',''),('RondelleSupport','B'),('RondelleSupport','H'),('EcrouSupport','')]}
    focus=collars|supports|hardware
    occurrences=[o for o in build['occurrences'] if o['parent'].startswith('sous_assemblages/')]
    require(focus.issubset({o['occurrence'] for o in occurrences}), 'occurrences de fixation absentes')
    require(report.get('obstacles_controles')==len(occurrences),'périmètre des obstacles incomplet')
    controlled=report.get('occurrences_controlees',[])
    require(len(controlled)==len(focus) and set(controlled)==focus, 'périmètre des fixations incomplet ou dupliqué')
    require(len(report.get('colliers',[]))==4 and set(report['colliers'])==collars,'colliers incomplets ou dupliqués')
    pieces=report.get('pieces_controlees',[])
    require(len(pieces)==8 and {r['objet'] for r in pieces}==collars|supports
            and all(r.get('valide') is True and r.get('solides')==1 for r in pieces),'formes non validées ou multiples')
    expected_pairs={('SupportGNSS','Interface'),('SupportSecurite','Interface'),
                    ('SupportRF0','P75_Cadre'),('SupportRF1','P75_Cadre'),('Protection_amont','P73_Guide')}
    contacts=report.get('contacts',[])
    require(len(contacts)==5 and {(r['a'],r['b']) for r in contacts}==expected_pairs
            and all(number(r.get('distance_mm')) and 0<=r['distance_mm']<=1e-4 for r in contacts),
            'appuis absents, incomplets ou hors contact')
    stacks=report.get('empilements',[])
    required={kind+str(i):[x,y] for kind,y in [('GNSS',29),('Securite',-29)] for i,x in enumerate((-43,43))}
    require(len(stacks)==4 and {r['id'] for r in stacks}==set(required), 'empilements absents ou dupliqués')
    expected_z={'vis':[80.7,94.7],'rondelle_basse':[82.7,83],'rondelle_haute':[91,91.3],'ecrou':[91.3,92.9]}
    for stack in stacks:
        measures=stack.get('mesures_z_mm',{})
        require(stack.get('axe_mm')==required[stack['id']] and set(measures)==set(expected_z)
                and all(isinstance(measures[k],list) and len(measures[k])==2 and
                        all(number(a) and abs(a-b)<=1e-5 for a,b in zip(measures[k],value))
                        for k,value in expected_z.items())
                and number(stack.get('saillie_mm')) and abs(stack['saillie_mm']-1.8)<=1e-5,
                'empilement ou saillie non conforme')


def validate_colliers_evidence(build, routes, contract, report, bom, mec=MEC, ver=VER):
    """Exiger USB, neuf liaisons et les trois corps, puis dédupliquer la BOM."""
    def require(condition, message):
        if not condition:
            raise ValueError('Synchronisation colliers refusée : ' + message)

    def number(value, minimum=0, maximum=math.inf):
        return isinstance(value, (int, float)) and not isinstance(value, bool) \
            and math.isfinite(value) and minimum <= value <= maximum

    require(report.get('schema_version') == 1 and report.get('candidats') is False,
            'schéma ou preuve candidate')
    require(all(report.get(key) is True for key in ('finalisation_correcte', 'conforme', 'fichiers_non_modifies')),
            'preuve non finalisée, non conforme ou fichiers modifiés')
    require(report.get('erreurs') == [] and report.get('collisions') == [], 'erreurs ou collisions')
    require(report.get('construction_sha256') == sha(ver/'construction_prototype.json')
            and report.get('routes_sha256') == sha(ver/'routes_prototype.json')
            and report.get('contrat_sha256') == sha(ver/'retenues_faisceaux_prototype.json'), 'entrées périmées')
    require(report.get('script_fichier') == 'verification/verify_colliers_prototype.py'
            and report.get('script_sha256') == sha(ver/'verify_colliers_prototype.py'), 'recette périmée')
    validate_recettes(build, ver)
    expected_files = {r['fichier']: r['sha256'] for r in build['references']}
    expected_files.update(build['sources_preservees'])
    require(report.get('natifs_sha256') == expected_files
            and all((mec/p).is_file() and sha(mec/p) == h for p,h in expected_files.items()), 'natifs périmés')
    band = report.get('bande', {})
    require(band.get('largeur_mm') == 4.6 and band.get('epaisseur_mm') == 1.2
            and band.get('volume_commun_max_mm3') == 1e-5, 'section ou seuil de collision modifié')
    reserve_ids = {'P77_Berceau_Reserve_USB_Prototype/'+name for name in ('NO','SO','E')}
    link_ids = {'P75_P72_BAS','P75_P72_HAUT','P73_P72_DIST_AV','P73_P72_DIST_ARR',
                'P73_P72_DIST_MONTANT','P73_P72_F01','P73_P72_F38_POS','P73_P72_F38_NEG','P78_P64'}
    body_ids = {'QS8_P76','ANTENNE_RF0','ANTENNE_RF1'}
    groups = []
    for key, expected in [('colliers',reserve_ids), ('liaisons',link_ids), ('retenues_boitiers_antennes',body_ids)]:
        rows = report.get(key, [])
        require(len(rows) == len(expected) and {r.get('collier_id') for r in rows} == expected,
                key + ' incomplets ou dupliqués')
        require(all(row.get('valide') is True and row.get('solides') == 1
                    and number(row.get('perimetre_interieur_mm'), 1e-5, math.pi*50) for row in rows),
                key + ' : bande invalide ou trop longue')
        groups.extend(rows)
    require(all(row.get('passage_lumieres') is True and row.get('enveloppement_pile') is True
                for row in report['colliers']), 'passage ou capture USB non conforme')
    heads = report.get('tetes', [])
    all_ids = reserve_ids | link_ids | body_ids
    require(len(heads) == 15 and {r.get('collier_id') for r in heads} == all_ids
            and all(r.get('valide') is True and r.get('solides') == 1 and r.get('dimensions_mm') == [7.3,7.6,5.9]
                    and len(r.get('matrice', [])) == 16 and all(number(v, -math.inf) for v in r['matrice'])
                    for r in heads), 'têtes absentes, invalides ou dupliquées')
    expected_sections = {'QS8_P76':{'BerceauQS8','QS8_manuel','P73_Guide','F37_POS'},
                         'ANTENNE_RF0':{'P75_Cadre','AntenneRF0'}, 'ANTENNE_RF1':{'AntenneRF1'}}
    bodies = {row['collier_id']:row for row in report['retenues_boitiers_antennes']}
    for key,row in bodies.items():
        require(all(row.get(flag) is True for flag in ('capture_corps','tete_controlee','sans_collision','passage')),
                'capture, passage ou tête du corps non conforme')
        sections = row.get('sections', [])
        require(len(sections) == len(expected_sections[key])
                and {s.get('occurrence') for s in sections} == expected_sections[key]
                and all(s.get('capture') is True and number(s.get('volume_section_mm3'),1e-8)
                        and number(s.get('volume_hors_boucle_mm3'),0,1e-5) for s in sections),
                'sections de corps absentes ou hors boucle')
        require(row.get('type_collier') == 'T50R' and row.get('reference_achat') == '111-05012'
                and row.get('largeur_mm') == 4.6 and row.get('epaisseur_mm') == 1.2, 'type de collier corps différent')
    qs8,rf0,rf1 = (bodies[key] for key in ('QS8_P76','ANTENNE_RF0','ANTENNE_RF1'))
    require(qs8.get('collier_physique_id') == 'QS8_P76' and qs8.get('partage_faisceau') is True
            and qs8.get('partage_collier_natif') is False and len(qs8.get('stations_partagees',[])) == 1
            and qs8['stations_partagees'][0].get('cable') == 'F37_POS'
            and qs8['stations_partagees'][0].get('station_id') == 'F37_POS_-20'
            and qs8['stations_partagees'][0].get('centre_dans_boucle') is True, 'partage QS8/F37 non démontré')
    require(rf0.get('collier_physique_id') == 'ANTENNE_RF0' and rf0.get('partage_faisceau') is False
            and rf0.get('partage_collier_natif') is False, 'identité RF0 incohérente')
    contacts = rf1.get('contacts', [])
    require(rf1.get('collier_physique_id') == 'CollierAncrageRF1' and rf1.get('partage_collier_natif') is True
            and rf1.get('partage_faisceau') is False and len(contacts) == 2
            and {r.get('occurrence') for r in contacts} == {'SupportRF1','P75_Cadre'}
            and all(r.get('appui') is True and number(r.get('distance_mm'),0,1e-6)
                    and number(r.get('volume_commun_mm3'),0,1e-5) for r in contacts), 'sandwich RF1 non démontré')
    widths = {}
    for route in contract['routes']:
        for entry in route['retenues']:
            key = entry.get('collier_id', entry['station_id'])
            width = entry.get('largeur_collier_mm')
            require(width in (2.5,4.6) and (key not in widths or widths[key] == width), 'largeur du contrat incohérente')
            widths[key] = width
    require(reserve_ids <= widths.keys() and {'P75_P72_BAS','P75_P72_HAUT','QS8_P76'} <= widths.keys(),
            'partages absents du contrat')
    native = {'CollierAncrageRF0','CollierAncrageRF1','CollierMIDI0','CollierMIDI1'}
    occurrences = {o['occurrence'] for o in build['occurrences'] if o['parent'].startswith('sous_assemblages/')}
    require(native <= occurrences, 'boucles natives absentes')
    for key in link_ids | native | {r['collier_physique_id'] for r in bodies.values()}:
        require(key not in widths or widths[key] == 4.6, 'largeur d’un collier partagé incohérente')
        widths[key] = 4.6
    require(report.get('comptage') == dict(colliers_reserve=3, liaisons_supports=9,
            liaisons_deja_comptees_faisceaux=2, liaisons_supplementaires=7, retenues_boitiers_antennes=3,
            retenues_corps_deja_comptees_faisceaux=1, retenues_corps_deja_comptees_ancrages_natifs=1,
            retenues_corps_supplementaires=1, bandes_controlees=15, tetes_controlees=15), 'comptage des partages différent')
    total,by_width = len(widths), {str(w):sum(value==w for value in widths.values()) for w in (2.5,4.6)}
    item = next((r for r in bom.get('items',[]) if r.get('id') == 'ELEC-COLLIERS'), {})
    quantities = item.get('dimensions', {})
    require(quantities.get('quantite_nominale_conception') == total
            and quantities.get('quantite_perimetre_controle') == total
            and quantities.get('par_largeur_nominal') == by_width
            and quantities.get('par_largeur_perimetre_controle') == by_width
            and quantities.get('quantite_posee') is None, 'quantités BOM différentes de l’union prouvée')


def validate_faisceau_evidence(build, routes, report, mec=MEC, ver=VER):
    """Refuser une preuve incomplète, périmée ou comportant des intersections.

    Les seules jonctions locales admises sont déjà isolées par le protocole
    Airy dans un champ distinct. Une collision n'est jamais acceptée au seul
    motif que le calcul s'est terminé ou que le modèle de fiche est plein.
    """
    def require(condition, message):
        if not condition:
            raise ValueError("Synchronisation faisceau refusée : " + message)

    build_hash = sha(ver/'construction_prototype.json')
    routes_hash = sha(ver/'routes_prototype.json')
    require(report.get('finalisation_correcte') is True, 'contrôle non finalisé')
    require(report.get('fichiers_non_modifies') is True, 'fichiers modifiés pendant le contrôle')
    require(report.get('construction_sha256') == build_hash, 'construction périmée')
    require(report.get('routes_sha256') == routes_hash, 'routes périmées')
    for name in ('erreurs_geometrie_registres', 'collisions_cables_physique', 'collisions_cable_cable'):
        require(name in report and report[name] == [], name + ' absent ou non vide')
    expected_files = {r['fichier']: r['sha256'] for r in build['references']}
    expected_files.update(build['sources_preservees'])
    require(report.get('natifs_sha256') == expected_files, 'périmètre des natifs différent')
    require(all(sha(mec/p) == h for p, h in expected_files.items()), 'natif changé depuis le contrôle')
    ids = [r['id'] for r in routes['routes']]
    require(bool(ids) and len(set(ids)) == len(ids), 'identifiants de routes absents ou dupliqués')
    require(report.get('nombre_cables') == len(ids), 'nombre de câbles incomplet')
    physical = [o for o in build['occurrences'] if o['parent'].startswith('sous_assemblages/')
                and not ('SA07_' in o['parent'] and o['occurrence'] in set(ids))]
    require(report.get('nombre_obstacles') == len(physical), 'périmètre des obstacles incomplet')
    measures = report.get('geometrie_longueurs', [])
    require(len(measures) == len(ids) and {r['id'] for r in measures} == set(ids),
            'mesures géométriques incomplètes ou dupliquées')
    require(all(r.get('solide_unique_valide') is True and r.get('continuite') is True
                and r.get('longueur_reelle_mm', 0) > 0 for r in measures), 'géométrie non conforme')
    samples = report.get('distances_echantillonnees', [])
    require(len(samples) == len(ids) and {r['cable'] for r in samples} == set(ids)
            and all(r.get('table') for r in samples), 'contrôle des distances incomplet')

    native_script = ver/'verify_faisceaux_prototype.py'
    brep_script = ver/'verify_faisceaux_brep_prototype.py'
    if 'recalcul_natif_acquis_sha256' in report:
        require(report.get('obstacles_controles') == len(physical)
                and report.get('cables_distances_controles') == len(ids), 'contrôle BRep incomplet')
        require(report.get('script_sha256') == sha(brep_script), 'recette BRep périmée')
        require(report.get('lecteur_sha256') == sha(ver/'read_brep_prototype.py'), 'lecteur BRep périmé')
        cache_path = mec.parents[2]/'.runtime/faisceau_structure/geometrie_native_acquise.json'
        require(cache_path.is_file() and report['recalcul_natif_acquis_sha256'] == sha(cache_path),
                'preuve de recalcul native absente ou modifiée')
        native = read(cache_path)
        require(native.get('finalisation_correcte') is True, 'recalcul natif non finalisé')
        require(native.get('script_sha256') == sha(native_script), 'recette de recalcul native périmée')
        require(native.get('construction_sha256') == build_hash and native.get('routes_sha256') == routes_hash,
                'recalcul natif portant sur une autre construction ou d’autres routes')
        require(native.get('natifs_sha256') == expected_files, 'recalcul natif de périmètre différent')
        require(native.get('erreurs_geometrie_registres') == [], 'erreurs du recalcul natif')
        require(native.get('geometrie_longueurs') == measures, 'mesures différentes du recalcul natif')
    else:
        require(report.get('script_sha256') == sha(native_script), 'recette du contrôle natif périmée')


build=read(VER/'construction_prototype.json')
validate_recettes(build)
check=read(VER/'controle_assemblage_prototype.json')
bom=read(MEC/'nomenclature_prototype.json')
assert build['finalisation_correcte'] and check['finalisation_correcte']
assert check['sha256']==sha(MEC/build['assemblage'])
assert not check['erreurs_recalcul_liens'] and not check['erreurs_poses']
assert not check['collisions_equipements'] and not check['collisions_structure']
assert check['sources_non_modifiees']
review=read(VER/'review_assemblage_prototype.json')['review_finale_fixations']
assert review['finalisation_correcte'] and not review['collisions'] and not review['erreurs']
assert review['construction_sha256']==sha(VER/'construction_prototype.json')
assert review['assemblage_sha256']==sha(MEC/build['assemblage'])
for ref in build['references']:assert ref['sha256']==sha(MEC/ref['fichier']),ref['fichier']
routes=read(VER/'routes_prototype.json')
faisceau=read(VER/'controle_faisceaux_prototype.json')
validate_faisceau_evidence(build,routes,faisceau)
fixations_guides=read(VER/'controle_fixations_guides_prototype.json')
validate_fixations_guides_evidence(build,routes,fixations_guides)
retenues=read(VER/'controle_retenues_faisceaux_prototype.json')
validate_retenues_evidence(build,routes,read(VER/'retenues_faisceaux_prototype.json'),retenues)
validate_equipements_evidence(build,routes,read(VER/'controle_fixations_equipements_prototype.json'))
validate_colliers_evidence(build,routes,read(VER/'retenues_faisceaux_prototype.json'),
                           read(VER/'controle_colliers_prototype.json'),bom)
known={i['id'] for i in bom['items']}
unmapped=sorted({i for row in build['references']+build['occurrences'] for i in row['bom_ids']} - known)
assert not unmapped,unmapped

coverage=[]
for item in bom['items']:
    refs=[r['fichier'] for r in build['references'] if item['id'] in r['bom_ids']]
    occ=[r['parent']+'#'+r['occurrence'] for r in build['occurrences'] if item['id'] in r['bom_ids']]
    if item['perimetre']!='embarque':state='Hors assemblage aéronef : '+item['perimetre']
    elif refs or occ:state='Représentation présente, détail et validation selon la référence'
    elif item.get('achat')=='inclus' or item.get('parent'):state='Inclus dans un ensemble ; pas de géométrie autonome identifiée'
    else:state='Définition BOM sans représentation géométrique autonome'
    coverage.append({'id':item['id'],'quantite_bom':item['quantite'],'unite':item['unite'],
      'etat':state,'references':refs,'occurrences':occ,'detail_bom_ouvert':item.get('definition_detaillee_a_terminer',False)})
write(VER/'couverture_bom_cao_prototype.json',{
 'date':date.today().isoformat(),'bom_sha256':sha(MEC/'nomenclature_prototype.json'),
 'construction_sha256':sha(VER/'construction_prototype.json'),
 'limites':['Un ID porté par un sous-assemblage démontre un rattachement, pas la présence de chaque détail physique.',
            'Consommables, protections, terminaisons et fixations résiduelles non représentés exhaustivement.',
            'Quantités de jeux et sources fabricant incluses ne s’additionnent pas aux occurrences CAO.'],
 'postes':coverage})

manifest=read(MEC/'manifest.json')
manifest['date_mise_a_jour']=date.today().isoformat()
manifest['configuration_active']='prototype_cartographe'
manifest['portee_champs_historiques']='Les clés references/occurrences/assemblages et les variantes datées antérieures décrivent les études conservées avec dock ; la configuration active est exclusivement prototype_cartographe.'
manifest['prototype_cartographe']={
 'reference_bom':bom['reference'],'nomenclature':'nomenclature_prototype.json',
 'assemblage':build['assemblage'],'statut':'Implémenté','qualification':'À valider',
 'validation':'verification/controle_assemblage_prototype.json',
 'couverture_bom':'verification/couverture_bom_cao_prototype.json',
 'construction':'verification/construction_prototype.json',
 'inventaire_initial':'verification/inventaire_reconstruction_prototype.json',
 'preservation_sources_initiales':'verification/preservation_sources_prototype.json',
 'tri':'Réemploi par liens externes ; études historiques conservées hors configuration active, aucun effacement de sources.',
 'references':build['references'],'occurrences':build['occurrences'],
 'sources_preservees':build['sources_preservees'],
 'limites_construction_declarees':build['limites'],
 'limites':[
   'Supports, fixations et retenues nominales contrôlés dans les périmètres des preuves courantes ; aucune qualification physique déduite.',
   'Cotes de réservation et interfaces fabricant des modules à confronter aux plans et aux lots ; aucune bride pressant un PCB ou un composant inconnu prescrite.',
   'Piges Airy non posées sans coordonnées constructeur ; engagements SSD, microSD et M8 caméra À valider sur matériel.',
   'Terminaisons, brochages, protections de bornes et d’arêtes, accès réel, tolérances, serrage et tenue physique des faisceaux À valider.',
   'Masse installée, centrage, efforts, vibrations, thermique et vol non qualifiés.'],
 'derivation_holybro':build['derivation_holybro'],
 'review_fixations':'verification/review_assemblage_prototype.json#review_finale_fixations',
 'validation_faisceaux':'verification/controle_faisceaux_prototype.json',
 'validation_fixations_guides':'verification/controle_fixations_guides_prototype.json',
 'validation_fixations_equipements':'verification/controle_fixations_equipements_prototype.json',
 'validation_retenues':'verification/controle_retenues_faisceaux_prototype.json',
 'validation_pieces':'verification/controle_pieces_prototype.json',
 'validation_departs_bras':'verification/controle_departs_bras_prototype.json',
 'validation_colliers':'verification/controle_colliers_prototype.json',
 'validation_apparences':'verification/controle_apparences_prototype.json',
 'rendus_inspection':'verification/rendu_prototype.json',
 'revue_independante':'verification/review_assemblage_prototype.json#revue_finale_refonte',
 'contre_verification_corps':'verification/review_assemblage_prototype.json#contre_verification_corps',
 'validation_registres':'verification/controle_registres_prototype.json',
 'contrat_retenues':'verification/retenues_faisceaux_prototype.json',
 'routes_faisceaux':'verification/routes_prototype.json',
 'assemblages':[r for r in build['references'] if r['type'] in ('sous_assemblage','assemblage_final')]}
write(MEC/'manifest.json',manifest)
print(json.dumps({'postes_bom':len(coverage),'references':len(build['references']),
                  'occurrences':len(build['occurrences']),'controle':check['conclusion']},ensure_ascii=False))
