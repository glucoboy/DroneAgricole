"""Tests bornés des fonctions de validation, sans importer FreeCAD ni écrire de registre réel."""
from pathlib import Path
import ast
import copy
import hashlib
import json
import math
from datetime import datetime, timezone

root = Path(__file__).resolve().parents[4]
real_mec = root/'hardware/mecanique/cartographe'
real_ver = real_mec/'verification'
fixture = root/'.runtime/faisceau_structure/test_gardes_sync'
mec = fixture/'hardware/mecanique/cartographe'
ver = mec/'verification'
ver.mkdir(parents=True, exist_ok=True)

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def read(path):
    return json.loads(path.read_text('utf-8'))

def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), 'utf-8')

def functions_from(path, names, namespace):
    source = path.read_text('utf-8')
    compile(source, str(path), 'exec')
    tree = ast.parse(source)
    selected = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
    assert {node.name for node in selected} == set(names)
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(path), 'exec'), namespace)

length_ns = {'math': math}
functions_from(real_ver/'verify_faisceaux_prototype.py', ['issue', 'measure_catalog_lengths'], length_ns)
measure = length_ns['measure_catalog_lengths']
count = 0

errors = []
result = measure({'id': 'F16', 'longueur_catalogue_mm': 508, 'longueur_max_catalogue_mm': 1000}, 443, errors)
assert result['catalogue_mm'] == 508 and result['marge_longueur_totale_mm'] == 65
assert result['longueur_restante_a_ranger_mm'] is None and not errors
assert 'inconnue' in result['validation_longueur_gaine']
count += 1
errors = []
result = measure({'id': 'F16', 'longueur_catalogue_mm': 508, 'longueur_gaine_utile_min_mm': 421.2,
                  'longueur_gaine_utile_mm': 500}, 443, errors)
assert result['depassement_gaine_utile_mm'] == 21.8
assert [e['type'] for e in errors] == ['gaine_utile_trop_courte']
assert result['source_longueur_gaine_utile'] == 'longueur_gaine_utile_min_mm'
count += 1
errors = []
result = measure({'id': 'F16', 'longueur_catalogue_mm': 508}, 600, errors)
assert result['depassement_catalogue_mm'] == 92 and errors[0]['type'] == 'cordon_trop_court'
count += 1
errors = []
result = measure({'id': 'F16', 'longueur_catalogue_mm': None, 'longueur_max_catalogue_mm': 1000}, 600, errors)
assert result['catalogue_mm'] is None and result['marge_longueur_totale_mm'] is None and not errors
count += 1
errors = []
result = measure({'id': 'F13A', 'longueur_max_catalogue_mm': 65}, 60, errors)
assert result['catalogue_mm'] == 65 and result['longueur_restante_a_ranger_mm'] is None
count += 1
errors = []
result = measure({'id': 'F16'}, 443, errors)
assert result['catalogue_mm'] is None
count += 1
errors = []
result = measure({'id': 'F16', 'longueur_catalogue_mm': 508, 'longueur_gaine_utile_mm': 520}, 400, errors)
assert errors[0]['type'] == 'longueurs_catalogue_incoherentes'
count += 1
for value in [-1, 0, float('nan'), True, '508']:
    try:
        measure({'id': 'F16', 'longueur_catalogue_mm': value}, 443, [])
    except ValueError:
        count += 1
    else:
        raise AssertionError(('Longueur invalide acceptée', value))

for name in ['verify_faisceaux_prototype.py', 'verify_faisceaux_brep_prototype.py',
             'verify_fixations_guides_prototype.py', 'verify_retenues_faisceaux_prototype.py',
             'verify_fixations_equipements_prototype.py','verify_colliers_prototype.py','read_brep_prototype.py']:
    (ver/name).write_bytes((real_ver/name).read_bytes())
recipe_names = ['build_prototype.py', 'prototype_routage.py', 'prototype_guides.py',
                'cable_workbench_prototype.py', 'configuration_faisceau_haut_prototype.json',
                'prototype_retenues.py', 'prototype_retenues_puissance.py',
                'prototype_retenues_capteurs.py', 'prototype_retenues_locales.py',
                'prototype_retenues_bras.py', 'prototype_retenues_basses.py',
                'prototype_retenues_hautes.py', 'prototype_retenues_reserves.py',
                'prototype_retenues_departs.py', 'prototype_fixations_equipements.py', 'prototype_connecteurs.py',
                'connecteurs_coudes_camera_prototype.json', 'etage_batterie_helpers.py']
for name in recipe_names:
    (ver/name).write_text('Recette factice : ' + name, 'utf-8')
native_path = mec/'pieces/test.dat'
native_path.parent.mkdir(parents=True, exist_ok=True)
native_path.write_text('natif de test', 'utf-8')
build = {'references': [{'reference':'SUPPORT', 'fichier': 'pieces/test.dat', 'sha256': sha(native_path)}],
         'sources_preservees': {},
         'finalisation_correcte': True,
         'recettes_sha256': {name: sha(ver/name) for name in recipe_names},
         'script_sha256': sha(ver/'build_prototype.py'),
         'occurrences': [{'parent': 'sous_assemblages/SA01_Prototype_Structure.FCStd', 'occurrence': 'OEM_Test', 'source':'pieces/test.dat'},
                         {'parent': 'sous_assemblages/SA07_Prototype_Faisceaux.FCStd', 'occurrence': 'F16'}]}
routes = {'routes': [{'id': 'F16', 'longueur_catalogue_mm': 508, 'longueur_courbe_mm':100}]}
write(ver/'construction_prototype.json', build)
write(ver/'routes_prototype.json', routes)
report = {'finalisation_correcte': True, 'fichiers_non_modifies': True,
          'construction_sha256': sha(ver/'construction_prototype.json'),
          'routes_sha256': sha(ver/'routes_prototype.json'),
          'erreurs_geometrie_registres': [], 'collisions_cables_physique': [], 'collisions_cable_cable': [],
          'natifs_sha256': {'pieces/test.dat': sha(native_path)}, 'nombre_cables': 1, 'nombre_obstacles': 1,
          'geometrie_longueurs': [{'id': 'F16', 'solide_unique_valide': True, 'continuite': True,
                                  'longueur_reelle_mm': 400}],
          'distances_echantillonnees': [{'cable': 'F16', 'table': [[0, 0, 0, 0, 1, 'OEM_Test', True]]}],
          'script_sha256': sha(ver/'verify_faisceaux_prototype.py')}
guard_ns = {'MEC': mec, 'VER': ver, 'sha': sha, 'read': read, 'Path': Path, 'math':math}
functions_from(real_ver/'sync_prototype.py',
               ['validate_recettes', 'validate_faisceau_evidence', 'validate_fixations_guides_evidence',
                'validate_retenues_evidence','validate_equipements_evidence','validate_colliers_evidence'], guard_ns)
validate = guard_ns['validate_faisceau_evidence']
validate(build, routes, report)
count += 1

def rejected(changes, expected):
    global count
    candidate = copy.deepcopy(report)
    candidate.update(changes)
    try:
        validate(build, routes, candidate)
    except ValueError as error:
        assert expected in str(error), str(error)
        count += 1
    else:
        raise AssertionError(('Preuve invalide acceptée', changes))

for changes, expected in [
    ({'finalisation_correcte': False}, 'non finalisé'),
    ({'fichiers_non_modifies': False}, 'modifiés pendant'),
    ({'routes_sha256': 'ancien'}, 'routes périmées'),
    ({'construction_sha256': 'ancien'}, 'construction périmée'),
    ({'collisions_cables_physique': [{'cable': 'F16', 'admise': True}]}, 'collisions_cables_physique'),
    ({'collisions_cable_cable': [{'a': 'F16'}]}, 'collisions_cable_cable'),
    ({'erreurs_geometrie_registres': [{'type': 'gaine_utile_trop_courte'}]}, 'erreurs_geometrie_registres'),
    ({'erreurs_geometrie_registres': None}, 'erreurs_geometrie_registres'),
    ({'natifs_sha256': {}}, 'périmètre des natifs'),
    ({'nombre_cables': 0}, 'nombre de câbles'),
    ({'nombre_obstacles': 0}, 'obstacles incomplet'),
    ({'geometrie_longueurs': []}, 'mesures géométriques'),
    ({'distances_echantillonnees': []}, 'distances incomplet'),
    ({'script_sha256': 'ancien'}, 'recette du contrôle natif'),
]:
    rejected(changes, expected)

native_cache = dict(finalisation_correcte=True, script_sha256=sha(ver/'verify_faisceaux_prototype.py'),
                    construction_sha256=report['construction_sha256'], routes_sha256=report['routes_sha256'],
                    natifs_sha256=report['natifs_sha256'], erreurs_geometrie_registres=[],
                    geometrie_longueurs=report['geometrie_longueurs'])
cache_path = fixture/'.runtime/faisceau_structure/geometrie_native_acquise.json'
write(cache_path, native_cache)
brep = dict(report, script_sha256=sha(ver/'verify_faisceaux_brep_prototype.py'),
            lecteur_sha256=sha(ver/'read_brep_prototype.py'), recalcul_natif_acquis_sha256=sha(cache_path),
            obstacles_controles=1, cables_distances_controles=1)
validate(build, routes, brep)
count += 1
bad_cache = dict(native_cache, routes_sha256='ancien')
write(cache_path, bad_cache)
brep['recalcul_natif_acquis_sha256'] = sha(cache_path)
try:
    validate(build, routes, brep)
except ValueError as error:
    assert 'd’autres routes' in str(error)
    count += 1
else:
    raise AssertionError('Cache natif périmé accepté')

def must_reject(function, args, expected):
    global count
    try:
        function(*args)
    except ValueError as error:
        assert expected in str(error), str(error)
        count += 1
    else:
        raise AssertionError(('Donnée invalide acceptée', expected))

recipes = guard_ns['validate_recettes']
recipes(build); count += 1
for field, value, expected in [('recettes_sha256', None, 'absentes'),
                               ('recettes_sha256', {}, 'incomplètes'),
                               ('script_sha256', 'ancien', 'constructeur incohérente')]:
    bad = dict(build, **{field: value})
    must_reject(recipes, (bad,), expected)
for name in ('prototype_retenues_puissance.py', 'prototype_retenues_capteurs.py',
             'prototype_retenues_locales.py', 'prototype_retenues_bras.py',
             'prototype_retenues_basses.py', 'prototype_retenues_hautes.py', 'prototype_retenues_reserves.py'):
    bad = copy.deepcopy(build); del bad['recettes_sha256'][name]
    must_reject(recipes, (bad,), 'incomplètes')
bad = copy.deepcopy(build); bad['recettes_sha256']['prototype_guides.py'] = 'ancien'
must_reject(recipes, (bad,), 'recette absente')
for name in ('prototype_retenues_locales.py', 'prototype_retenues_bras.py',
             'prototype_retenues_basses.py', 'prototype_retenues_hautes.py', 'prototype_retenues_reserves.py'):
    bad = copy.deepcopy(build); bad['recettes_sha256'][name] = 'ancien'
    must_reject(recipes, (bad,), 'recette absente')
    recipe = ver/name
    recipe_bytes = recipe.read_bytes()
    recipe.write_text('Recette modifiée après construction', 'utf-8')
    must_reject(recipes, (build,), 'recette absente')
    recipe.write_bytes(recipe_bytes)
bad = copy.deepcopy(build); bad['recettes_sha256']['../hors_perimetre.py'] = 'x'
must_reject(recipes, (bad,), 'hors périmètre')

# Une preuve de retenue doit couvrir les stations et tous les intervalles réels.
contract = {'schema_version':1, 'routes':[{'id':'F16', 'retenues':[
    {'station_id':'S', 'reference':'SUPPORT', 'cle_id':'NATIVE_S', 'mode':'individuel',
     'etat_integration':'Implémenté', 'collier_id':'COLLIER_S'}],
    'portions':[{'debut':'DEBUT', 'fin':'S', 'type':'transition_courte'},
                {'debut':'S', 'fin':'FIN', 'type':'guidee'}],
    'limites':{'portee_max_mm':{'transition_courte':60, 'guidee':50}, 'jeu_support_max_mm':1.0}}]}
write(ver/'retenues_faisceaux_prototype.json', contract)
retained = {'finalisation_correcte':True, 'conforme':True, 'fichiers_non_modifies':True, 'erreurs':[],
    'entrees_sha256':{n:sha(ver/n) for n in ('construction_prototype.json','routes_prototype.json','retenues_faisceaux_prototype.json')},
    'script_sha256':sha(ver/'verify_retenues_faisceaux_prototype.py'), 'lecteur_sha256':sha(ver/'read_brep_prototype.py'),
    'natifs_sha256':report['natifs_sha256'], 'nombre_routes':1, 'nombre_affectations':1, 'nombre_colliers_identifies':1,
    'routes':[{'id':'F16', 'longueur_mm':100, 'stations':[
        {'station_id':'S', 'collier_id':'COLLIER_S', 'station_native':'NATIVE_S', 'mode':'individuel',
         'support':'sous_assemblages/SA01_Prototype_Structure.FCStd#OEM_Test', 's_mm':50,
         'distance_projection_mm':.2, 'tolerance_projection_mm':.6, 'jeu_surface_appui_mm':.2,
         'jeu_max_mm':1.0, 'erreurs':[]}], 'portions':[
        {'debut':'DEBUT', 'fin':'S', 'type':'transition_courte', 's_debut_mm':0, 's_fin_mm':50,
         'longueur_mm':50, 'portee_max_mm':60, 'conforme':True},
        {'debut':'S', 'fin':'FIN', 'type':'guidee', 's_debut_mm':50, 's_fin_mm':100,
         'longueur_mm':50, 'portee_max_mm':50, 'conforme':True}]}]}
retentions = guard_ns['validate_retenues_evidence']
retentions(build, routes, contract, retained); count += 1
for changes, expected in [
    ({'finalisation_correcte':False},'non finalisé'), ({'conforme':False},'non conforme'),
    ({'fichiers_non_modifies':False},'modifiés pendant'), ({'erreurs':[{'type':'portee_depassee'}]},'erreurs'),
    ({'entrees_sha256':{}},'entrées'), ({'script_sha256':'ancien'},'recette de contrôle'),
    ({'lecteur_sha256':'ancien'},'lecteur BRep'), ({'natifs_sha256':{}},'périmètre des natifs'),
    ({'routes':[]},'couverture des routes'), ({'routes':retained['routes']*2},'couverture des routes'),
    ({'nombre_routes':0},'comptage'), ({'nombre_affectations':0},'comptage'),
    ({'nombre_colliers_identifies':0},'comptage')]:
    must_reject(retentions, (build,routes,contract,dict(retained,**changes)), expected)
for name in retained['entrees_sha256']:
    bad=copy.deepcopy(retained); bad['entrees_sha256'][name]='ancien'
    must_reject(retentions,(build,routes,contract,bad),'entrées')
for field,value,expected in [('longueur_mm',float('nan'),'longueur'), ('stations',[],'retenues absentes'),
                            ('portions',[],'portions absentes')]:
    bad=copy.deepcopy(retained); bad['routes'][0][field]=value
    must_reject(retentions,(build,routes,contract,bad),expected)
for field,value,expected in [('mode','commun','affectation'), ('collier_id','AUTRE','affectation'),
    ('support','autre#occurrence','affectation'), ('station_native','autre','affectation'),
    ('s_mm',float('nan'),'mesure'), ('distance_projection_mm',.7,'mesure'),
    ('jeu_surface_appui_mm',-.01,'mesure'), ('jeu_surface_appui_mm',1.1,'mesure'),
    ('erreurs',['appui_trop_eloigne'],'mesure')]:
    bad=copy.deepcopy(retained); bad['routes'][0]['stations'][0][field]=value
    must_reject(retentions,(build,routes,contract,bad),expected)
for field,value in [('s_fin_mm',49), ('longueur_mm',49), ('portee_max_mm',61), ('conforme',False)]:
    bad=copy.deepcopy(retained); bad['routes'][0]['portions'][0][field]=value
    must_reject(retentions,(build,routes,contract,bad),'portion non conforme')
bad_contract=copy.deepcopy(contract); bad_contract['routes'][0]['retenues'][0]['etat_integration']='À intégrer'
must_reject(retentions,(build,routes,bad_contract,retained),'station non intégrée')
bad_contract=copy.deepcopy(contract); bad_contract['routes']*=2
must_reject(retentions,(build,routes,bad_contract,retained),'couverture des routes du contrat')
bad_contract=copy.deepcopy(contract); bad_contract['routes'][0]['retenues'].append(
    dict(bad_contract['routes'][0]['retenues'][0],station_id='S2',cle_id='NATIVE_S2'))
bad=copy.deepcopy(retained); bad['routes'][0]['stations'].append(
    dict(bad['routes'][0]['stations'][0],station_id='S2',station_native='NATIVE_S2',s_mm=60))
must_reject(retentions,(build,routes,bad_contract,bad),'ancrages incompatibles')
# Même si les lignes sont cohérentes entre elles, une portion supprimée laisse un trou.
bad_contract=copy.deepcopy(contract); bad_contract['routes'][0]['portions'].pop()
bad=copy.deepcopy(retained); bad['routes'][0]['portions'].pop()
must_reject(retentions,(build,routes,bad_contract,bad),'extrémité du parcours non couverte')
native_bytes=native_path.read_bytes(); native_path.write_text('modification après contrôle','utf-8')
must_reject(retentions,(build,routes,contract,retained),'natif absent ou changé')
native_path.write_bytes(native_bytes)

# Preuve de fixations autonome et complète : 34 éléments des guides + 8 de butée.
sa2, sa7 = 'SA02_Prototype_Batterie/', 'SA07_Prototype_Faisceaux/'
guide_fix = {sa7+'VisGuide'+str(i) for i in range(10)}
guide_fix |= {sa7+'RondelleGuide'+str(i) for i in range(14)}
guide_fix |= {sa7+'EcrouGuide'+str(i) for i in range(10)}
right = {sa2+p+str(i) for i in (2,3) for p in ('VisButee','RondelleButeeH','RondelleButeeB','EcrouButee')}
supports = {sa7+'P72_Guide',sa7+'P73_Guide',sa7+'P75_Cadre',sa2+'BerceauQS8',
            sa2+'Semelle','SA03_Prototype_Energie/Isolation','SA05_Prototype_Avionique/Interface',
            sa7+'P77_BerceauReserveUSB',sa7+'P78_RetenueCameraM8'}
focus = guide_fix | right | supports
guide_build = copy.deepcopy(build)
guide_build['occurrences'] = [{'parent':'sous_assemblages/'+n.split('/')[0]+'.FCStd',
                               'occurrence':n.split('/')[1]} for n in sorted(focus | {sa2+'QS8_manuel',sa7+'F16'})]
write(ver/'construction_prototype.json', guide_build)
stations = [f'GuideBas{i}' for i in range(4)] + [f'GuideMilieu{i}' for i in range(2)]
stations += [f'GuideHaut{i}' for i in range(4)] + ['ButeeDroite2','ButeeDroite3']
guide_report = dict(finalisation_correcte=True, fichiers_non_modifies=True,
    construction_sha256=sha(ver/'construction_prototype.json'),
    script_sha256=sha(ver/'verify_fixations_guides_prototype.py'), lecteur_sha256=sha(ver/'read_brep_prototype.py'),
    recettes_sha256=guide_build['recettes_sha256'], natifs_sha256=report['natifs_sha256'], erreurs=[], collisions=[],
    fixations_guides={'VisGuide':10,'RondelleGuide':14,'EcrouGuide':10},fixations_butee_droite=8,fixations_total=42,
    occurrences_controlees=sorted(focus), pieces_controlees=[{'objet':n,'valide':True,'solides':1} for n in sorted(supports)],
    empilements=[{'id':n,'couches':[{'objet':'fixture'}],'contacts':[{'distance_mm':0}]} for n in stations],
    obstacles_controles=len(focus)+1, appui_qs8_mm=0)
fixations = guard_ns['validate_fixations_guides_evidence']
fixations(guide_build, routes, guide_report); count += 1
for changes, expected in [
    ({'finalisation_correcte':False},'non finalisé'),
    ({'fichiers_non_modifies':False},'modifiés pendant'),
    ({'construction_sha256':'ancien'},'construction périmée'),
    ({'script_sha256':'ancien'},'recette de contrôle périmée'),
    ({'lecteur_sha256':'ancien'},'lecteur BRep périmé'),
    ({'recettes_sha256':{}},'recettes de construction différentes'),
    ({'natifs_sha256':{}},'périmètre des natifs'),
    ({'erreurs':[{'type':'engagement_ecrou'}]},'erreurs absent ou non vide'),
    ({'collisions':[{'a':'guide','b':'butée','admise':True}]},'collisions absent ou non vide'),
    ({'fixations_total':41},'comptage de la preuve'),
    ({'occurrences_controlees':[]},'périmètre contrôlé'),
    ({'pieces_controlees':[]},'contrôle des pièces'),
    ({'empilements':guide_report['empilements'][:-1]},'empilements incomplets'),
    ({'obstacles_controles':1},'obstacles incomplet'),
    ({'appui_qs8_mm':.01},'appui QS8'),
    ({'appui_qs8_mm':float('nan')},'appui QS8'),
]:
    must_reject(fixations, (guide_build, routes, dict(guide_report, **changes)), expected)
bad_build=copy.deepcopy(guide_build);bad_build['occurrences']=[o for o in bad_build['occurrences'] if o['occurrence']!='VisGuide0']
must_reject(fixations,(bad_build,routes,guide_report),'comptage des guides')
for missing in ('P77_BerceauReserveUSB','P78_RetenueCameraM8'):
    bad_build=copy.deepcopy(guide_build)
    bad_build['occurrences']=[o for o in bad_build['occurrences'] if o['occurrence']!=missing]
    must_reject(fixations,(bad_build,routes,guide_report),'occurrences requises absentes')
    bad_report=copy.deepcopy(guide_report)
    bad_report['pieces_controlees']=[p for p in bad_report['pieces_controlees'] if p['objet']!=sa7+missing]
    must_reject(fixations,(guide_build,routes,bad_report),'contrôle des pièces incomplet')
native_path.write_text('natif modifié après contrôle','utf-8')
must_reject(fixations,(guide_build,routes,guide_report),'natif absent ou changé')

# Les supports ancrés, leurs quatre boucles et les quatre empilements M2
# forment un périmètre supplémentaire obligatoire, sans succès repris du passé.
native_path.write_bytes(native_bytes)
eq_collars={'CollierAncrageRF0','CollierAncrageRF1','CollierMIDI0','CollierMIDI1'}
eq_supports={'SupportGNSS','SupportSecurite','SupportRF0','SupportRF1'}
eq_hardware={prefix+kind+suffix+str(i) for kind in ('GNSS','Securite') for i in (0,1)
             for prefix,suffix in [('VisSupport',''),('RondelleSupport','B'),('RondelleSupport','H'),('EcrouSupport','')]}
eq_focus=eq_collars|eq_supports|eq_hardware
eq_build=copy.deepcopy(build)
eq_build['occurrences']=[{'parent':'sous_assemblages/SA06_Prototype_Navigation.FCStd','occurrence':n}
                         for n in sorted(eq_focus)]
write(ver/'construction_prototype.json',eq_build)
eq_pairs=[('SupportGNSS','Interface'),('SupportSecurite','Interface'),
          ('SupportRF0','P75_Cadre'),('SupportRF1','P75_Cadre'),('Protection_amont','P73_Guide')]
eq_z={'vis':[80.7,94.7],'rondelle_basse':[82.7,83],'rondelle_haute':[91,91.3],'ecrou':[91.3,92.9]}
eq_report=dict(schema_version=1,finalisation_correcte=True,conforme=True,fichiers_non_modifies=True,
    erreurs=[],collisions=[],construction_sha256=sha(ver/'construction_prototype.json'),
    routes_sha256=sha(ver/'routes_prototype.json'),script_sha256=sha(ver/'verify_fixations_equipements_prototype.py'),
    module_sha256=sha(ver/'prototype_fixations_equipements.py'),lecteur_sha256=sha(ver/'read_brep_prototype.py'),
    natifs_sha256=report['natifs_sha256'],occurrences_controlees=sorted(eq_focus),
    obstacles_controles=len(eq_focus),colliers=sorted(eq_collars),
    pieces_controlees=[{'objet':n,'valide':True,'solides':1} for n in sorted(eq_collars|eq_supports)],
    contacts=[{'a':a,'b':b,'distance_mm':0} for a,b in eq_pairs],
    empilements=[{'id':kind+str(i),'axe_mm':[x,y],'mesures_z_mm':copy.deepcopy(eq_z),'saillie_mm':1.8}
                 for kind,y in [('GNSS',29),('Securite',-29)] for i,x in enumerate((-43,43))])
equipments=guard_ns['validate_equipements_evidence']
equipments(eq_build,routes,eq_report);count+=1
for changes,expected in [
    ({'schema_version':0},'schéma'),({'finalisation_correcte':False},'non finalisé'),
    ({'conforme':False},'non conforme'),({'fichiers_non_modifies':False},'fichiers modifiés'),
    ({'erreurs':None},'erreurs ou collisions'),({'collisions':[{'admise':True}]},'erreurs ou collisions'),
    ({'construction_sha256':'ancien'},'construction ou routes périmées'),
    ({'routes_sha256':'ancien'},'construction ou routes périmées'),
    ({'module_sha256':'ancien'},'recette ou lecteur périmé'),
    ({'script_sha256':'ancien'},'recette ou lecteur périmé'),
    ({'lecteur_sha256':'ancien'},'recette ou lecteur périmé'),
    ({'natifs_sha256':{}},'périmètre des natifs'),
    ({'obstacles_controles':0},'obstacles incomplet'),
    ({'occurrences_controlees':[]},'périmètre des fixations'),
    ({'colliers':sorted(eq_collars)[:-1]},'colliers incomplets'),
    ({'pieces_controlees':[]},'formes non validées'),
    ({'contacts':[]},'appuis absents'),({'empilements':[]},'empilements absents')]:
    must_reject(equipments,(eq_build,routes,dict(eq_report,**changes)),expected)
for field,value in [('distance_mm',.1),('distance_mm',float('nan')),('distance_mm',True)]:
    bad=copy.deepcopy(eq_report);bad['contacts'][0][field]=value
    must_reject(equipments,(eq_build,routes,bad),'appuis absents')
for field,value in [('axe_mm',[0,29]),('saillie_mm',0),('saillie_mm',float('nan'))]:
    bad=copy.deepcopy(eq_report);bad['empilements'][0][field]=value
    must_reject(equipments,(eq_build,routes,bad),'empilement ou saillie')
bad=copy.deepcopy(eq_report);bad['empilements'][0]['mesures_z_mm']['ecrou']=[91.3,96]
must_reject(equipments,(eq_build,routes,bad),'empilement ou saillie')
bad_build=copy.deepcopy(eq_build);bad_build['occurrences'].pop()
must_reject(equipments,(bad_build,routes,eq_report),'occurrences de fixation absentes')
native_path.write_text('natif changé après contrôle équipements','utf-8')
must_reject(equipments,(eq_build,routes,eq_report),'périmètre des natifs')

# Les trois captures de corps sont obligatoires indépendamment des douze
# autres bandes ; les quantités sont l'union des identités, sans addition
# du QS8/F37 ni de l'antenne tenue par la boucle native RF1.
native_path.write_bytes(native_bytes)
collar_build=copy.deepcopy(build)
native_collars={'CollierAncrageRF0','CollierAncrageRF1','CollierMIDI0','CollierMIDI1'}
collar_build['occurrences']=[{'parent':'sous_assemblages/SA07_Prototype_Faisceaux.FCStd','occurrence':n}
                             for n in sorted(native_collars)]
write(ver/'construction_prototype.json',collar_build)
reserve_ids={'P77_Berceau_Reserve_USB_Prototype/'+n for n in ('NO','SO','E')}
link_ids={'P75_P72_BAS','P75_P72_HAUT','P73_P72_DIST_AV','P73_P72_DIST_ARR',
          'P73_P72_DIST_MONTANT','P73_P72_F01','P73_P72_F38_POS','P73_P72_F38_NEG','P78_P64'}
contract_ids=sorted(reserve_ids|{'P75_P72_BAS','P75_P72_HAUT','QS8_P76'}|{f'C{i}' for i in range(263)})
assert len(contract_ids)==269
collar_contract={'routes':[{'id':'F37_POS','retenues':[
    {'station_id':n,'collier_id':n,'largeur_collier_mm':2.5 if n=='C0' else 4.6} for n in contract_ids]}]}
write(ver/'retenues_faisceaux_prototype.json',collar_contract)
def band_row(key):
    return dict(collier_id=key,valide=True,solides=1,perimetre_interieur_mm=40)
collar_report=dict(schema_version=1,candidats=False,finalisation_correcte=True,conforme=True,fichiers_non_modifies=True,
    erreurs=[],collisions=[],construction_sha256=sha(ver/'construction_prototype.json'),
    routes_sha256=sha(ver/'routes_prototype.json'),contrat_sha256=sha(ver/'retenues_faisceaux_prototype.json'),
    script_fichier='verification/verify_colliers_prototype.py',script_sha256=sha(ver/'verify_colliers_prototype.py'),
    natifs_sha256=report['natifs_sha256'],bande=dict(largeur_mm=4.6,epaisseur_mm=1.2,volume_commun_max_mm3=1e-5),
    colliers=[dict(band_row(n),passage_lumieres=True,enveloppement_pile=True) for n in sorted(reserve_ids)],
    liaisons=[band_row(n) for n in sorted(link_ids)],retenues_boitiers_antennes=[],tetes=[],
    comptage=dict(colliers_reserve=3,liaisons_supports=9,liaisons_deja_comptees_faisceaux=2,
        liaisons_supplementaires=7,retenues_boitiers_antennes=3,retenues_corps_deja_comptees_faisceaux=1,
        retenues_corps_deja_comptees_ancrages_natifs=1,retenues_corps_supplementaires=1,bandes_controlees=15,tetes_controlees=15))
for key,sections in [('QS8_P76',['BerceauQS8','QS8_manuel','P73_Guide','F37_POS']),
                     ('ANTENNE_RF0',['P75_Cadre','AntenneRF0']),('ANTENNE_RF1',['AntenneRF1'])]:
    row=dict(band_row(key),collier_physique_id='CollierAncrageRF1' if key=='ANTENNE_RF1' else key,
        capture_corps=True,passage=True,tete_controlee=True,sans_collision=True,type_collier='T50R',
        reference_achat='111-05012',largeur_mm=4.6,epaisseur_mm=1.2,partage_faisceau=key=='QS8_P76',
        partage_collier_natif=key=='ANTENNE_RF1',stations_partagees=[],
        sections=[dict(occurrence=n,volume_section_mm3=1,volume_hors_boucle_mm3=0,capture=True) for n in sections])
    if key=='QS8_P76':
        row['stations_partagees']=[dict(cable='F37_POS',station_id='F37_POS_-20',centre_dans_boucle=True)]
    if key=='ANTENNE_RF1':
        row['contacts']=[dict(occurrence=n,appui=True,distance_mm=0,volume_commun_mm3=0) for n in ('SupportRF1','P75_Cadre')]
    collar_report['retenues_boitiers_antennes'].append(row)
body_ids={r['collier_id'] for r in collar_report['retenues_boitiers_antennes']}
collar_report['tetes']=[dict(collier_id=n,valide=True,solides=1,dimensions_mm=[7.3,7.6,5.9],
    matrice=[1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1]) for n in sorted(reserve_ids|link_ids|body_ids)]
collar_bom={'items':[{'id':'ELEC-COLLIERS','dimensions':dict(quantite_nominale_conception=281,
    quantite_perimetre_controle=281,par_largeur_nominal={'2.5':1,'4.6':280},
    par_largeur_perimetre_controle={'2.5':1,'4.6':280},quantite_posee=None)}]}
collars=guard_ns['validate_colliers_evidence']
collar_args=(collar_build,routes,collar_contract,collar_report,collar_bom)
collars(*collar_args);count+=1
for changes,expected in [({'candidats':True},'preuve candidate'),({'conforme':False},'non conforme'),
    ({'contrat_sha256':'ancien'},'entrées périmées'),({'script_sha256':'ancien'},'recette périmée'),
    ({'collisions':[{}]},'erreurs ou collisions'),({'tetes':[]},'têtes absentes'),
    ({'retenues_boitiers_antennes':[]},'retenues_boitiers_antennes incomplets'),({'comptage':{}},'comptage')]:
    must_reject(collars,(collar_build,routes,collar_contract,dict(collar_report,**changes),collar_bom),expected)
for key,value,expected in [('capture_corps',False,'capture, passage ou tête'),
    ('tete_controlee',False,'capture, passage ou tête'),('sans_collision',False,'capture, passage ou tête'),
    ('sections',[],'sections de corps'),('partage_faisceau',False,'partage QS8/F37')]:
    bad=copy.deepcopy(collar_report);bad['retenues_boitiers_antennes'][0][key]=value
    must_reject(collars,(collar_build,routes,collar_contract,bad,collar_bom),expected)
bad=copy.deepcopy(collar_report);bad['retenues_boitiers_antennes'][2]['contacts'][0]['distance_mm']=.01
must_reject(collars,(collar_build,routes,collar_contract,bad,collar_bom),'sandwich RF1')
bad=copy.deepcopy(collar_report);bad['retenues_boitiers_antennes'][1]['sections'][0]['volume_hors_boucle_mm3']=.01
must_reject(collars,(collar_build,routes,collar_contract,bad,collar_bom),'sections de corps')
bad=copy.deepcopy(collar_report);bad['bande']['volume_commun_max_mm3']=1e-3
must_reject(collars,(collar_build,routes,collar_contract,bad,collar_bom),'section ou seuil')
bad=copy.deepcopy(collar_report);bad['tetes'][0]['matrice'][0]=float('nan')
must_reject(collars,(collar_build,routes,collar_contract,bad,collar_bom),'têtes absentes')
for qty in (283,280):
    bad=copy.deepcopy(collar_bom);bad['items'][0]['dimensions']['quantite_nominale_conception']=qty
    must_reject(collars,(collar_build,routes,collar_contract,collar_report,bad),'quantités BOM')

evidence={'date_utc':datetime.now(timezone.utc).isoformat(), 'controles_reussis':count,
          'resultat':'Réussi', 'finalisation_correcte':True, 'gui_ouverte':False,
          'registres_reels_modifies':False, 'donnees':'Fixtures synthétiques dans .runtime ; aucune qualification CAO ou physique.',
          'scripts_sha256':{n:sha(real_ver/n) for n in ['test_gardes_sync_prototype.py','sync_prototype.py','verify_faisceaux_prototype.py','verify_retenues_faisceaux_prototype.py','verify_colliers_prototype.py','verify_fixations_equipements_prototype.py']},
          'perimetre':['Priorité longueur catalogue et budget distinct de gaine utile',
                      'Fraîcheur, finalisation et complétude des preuves natives/BRep',
                      'Empreintes des recettes y compris retenues puissance/capteurs/locales/bras/basses/hautes/réserves ; absence et péremption refusées',
                      'Preuve des fixations guides incluant P77/P78, absence d’erreurs et de collisions',
                      'Preuve obligatoire des retenues : fraîcheur, stations, ancrages communs et couverture complète des intervalles',
                      'Ancrages équipements : fraîcheur,24occurrences,quatre boucles,appuis et quatre empilementsM2',
                      'Quinze bandes/têtes : captures USB,neuf liaisons,trois corps,partages QS8/RF1 et quantités BOM dédupliquées']}
write(real_ver/'controle_gardes_sync_prototype.json', evidence)
print(json.dumps(evidence, ensure_ascii=False))

