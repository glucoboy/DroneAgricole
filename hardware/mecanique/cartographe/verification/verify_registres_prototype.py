"""Réconciliation finale des preuves, des natifs et des registres du prototype.

Lecture seule des livrables. Les gardes de publication sont réutilisées sans
exécuter la synchronisation ; les contrôles supplémentaires portent sur le
classeur sauvegardé, les sources préservées et les captures effectivement lues.
"""
from pathlib import Path
from datetime import datetime, timezone
import ast
import hashlib
import json
import math
import traceback

ROOT = Path(__file__).resolve().parents[4]
MEC = ROOT/'hardware/mecanique/cartographe'
VER = MEC/'verification'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text('utf-8'))


def run():
    checks = []
    inputs = set()
    def load(path):
        inputs.add(path)
        return read(path)
    def check(name, value):
        checks.append(dict(id=name, reussi=bool(value)))
        if not value:
            raise ValueError(name)
    build = load(VER/'construction_prototype.json')
    routes = load(VER/'routes_prototype.json')
    bom = load(MEC/'nomenclature_prototype.json')
    manifest = load(MEC/'manifest.json')
    coverage = load(VER/'couverture_bom_cao_prototype.json')
    assembly = load(VER/'controle_assemblage_prototype.json')
    reviews = load(VER/'review_assemblage_prototype.json')
    fixations = reviews['review_finale_fixations']
    contract = load(VER/'retenues_faisceaux_prototype.json')
    # Extraire les seules fonctions pures de contrôle : aucun effet de bord
    # de sync_prototype, aucune réécriture du manifeste lors de ce contrôle.
    source = VER/'sync_prototype.py'
    inputs.add(source)
    names = {'validate_recettes', 'validate_fixations_guides_evidence',
             'validate_retenues_evidence', 'validate_faisceau_evidence',
             'validate_equipements_evidence','validate_colliers_evidence'}
    tree = ast.parse(source.read_text('utf-8'))
    nodes = [n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names]
    namespace = dict(Path=Path, math=math, json=json, sha=sha, read=read, MEC=MEC, VER=VER)
    exec(compile(ast.Module(body=nodes,type_ignores=[]),str(source),'exec'),namespace)
    namespace['validate_recettes'](build)
    check('recettes_courantes', True)
    guards=load(VER/'controle_gardes_sync_prototype.json')
    check('gardes_publication_testes',guards['finalisation_correcte'] and guards['resultat']=='Réussi'
        and guards['controles_reussis']>0 and not guards['gui_ouverte']
        and not guards['registres_reels_modifies']
        and all(sha(VER/path)==digest for path,digest in guards['scripts_sha256'].items()))
    for function, file in [('validate_faisceau_evidence','controle_faisceaux_prototype.json'),
                           ('validate_fixations_guides_evidence','controle_fixations_guides_prototype.json'),
                           ('validate_equipements_evidence','controle_fixations_equipements_prototype.json')]:
        namespace[function](build,routes,load(VER/file))
        check(file, True)
    namespace['validate_retenues_evidence'](build,routes,contract,
        load(VER/'controle_retenues_faisceaux_prototype.json'))
    check('retenues_courantes_et_completes',True)
    namespace['validate_colliers_evidence'](build,routes,contract,
        load(VER/'controle_colliers_prototype.json'),bom)
    check('colliers_courants_et_comptage_bom',True)
    native_files={r['fichier']:r['sha256'] for r in build['references']}
    native_files.update(build['sources_preservees'])
    check('natifs_courants',all(sha(MEC/path)==digest for path,digest in native_files.items()))
    for file,script in [('controle_pieces_prototype.json','verify_pieces_prototype.py'),
                        ('controle_departs_bras_prototype.json','verify_departs_bras_prototype.py'),
                        ('controle_colliers_prototype.json','verify_colliers_prototype.py')]:
        proof=load(VER/file)
        check(file,all(proof.get(k) is True for k in ('conforme','finalisation_correcte','fichiers_non_modifies'))
            and proof.get('collisions')==[] and proof.get('erreurs')==[]
            and proof.get('construction_sha256')==sha(VER/'construction_prototype.json')
            and proof.get('script_sha256')==sha(VER/script) and proof.get('natifs_sha256')==native_files
            and not proof.get('candidat',False) and not proof.get('candidats',False))
    check('assemblage_courant',assembly['sha256']==sha(MEC/build['assemblage']))
    check('liens_poses_collisions',assembly['finalisation_correcte'] and not any(assembly[k] for k in
        ('erreurs_recalcul_liens','erreurs_poses','collisions_equipements','collisions_structure'))
        and assembly['sources_non_modifiees'] and assembly['fichiers_non_modifies_par_verification'])
    check('fixations_courantes',fixations['construction_sha256']==sha(VER/'construction_prototype.json')
        and fixations['assemblage_sha256']==sha(MEC/build['assemblage'])
        and fixations['script_sha256']==sha(VER/'verify_fixations_prototype.py')
        and fixations['finalisation_correcte'] and fixations['fichiers_non_modifies']
        and not fixations['collisions'] and not fixations['erreurs'])
    independent=reviews['revue_finale_refonte']
    check('revue_independante_conforme',all(independent.get(k) is True for k in ('conforme','finalisation_correcte'))
        and independent.get('erreurs')==[] and independent.get('collisions')==[]
        and independent.get('construction_sha256')==sha(VER/'construction_prototype.json')
        and independent.get('routes_sha256')==sha(VER/'routes_prototype.json')
        and independent.get('contrat_sha256')==sha(VER/'retenues_faisceaux_prototype.json')
        and independent.get('assemblage_sha256')==sha(MEC/build['assemblage'])
        and independent.get('natifs_sha256')==native_files)
    reviewed_inputs=independent['entrees_sha256']
    check('revue_independante_dependances_courantes',bool(reviewed_inputs)
        and all(sha(MEC/path)==digest for path,digest in reviewed_inputs.items()))
    fixations_digest=hashlib.sha256(json.dumps(fixations,ensure_ascii=False,
        sort_keys=True,separators=(',',':')).encode('utf-8')).hexdigest()
    check('revue_independante_fixations_courantes',independent['entrees_cles_sha256'][
        'verification/review_assemblage_prototype.json#review_finale_fixations']==fixations_digest)
    counter=reviews['contre_verification_corps']
    check('contre_verification_corps_courante',all(counter.get(k) is True for k in
        ('conforme','finalisation_correcte','fichiers_non_modifies'))
        and counter['erreurs']==[] and counter['collisions']==[]
        and counter['construction_sha256']==sha(VER/'construction_prototype.json')
        and counter['colliers_sha256']==sha(VER/'controle_colliers_prototype.json')
        and counter['script_sha256']==sha(ROOT/counter['script_fichier'])
        and counter['scene_sha256']==sha(ROOT/counter['scene_fichier'])
        and counter['natifs_sha256']==native_files
        and {m['id'] for m in counter['mesures']}=={'QS8_P76','ANTENNE_RF0','ANTENNE_RF1'})
    counter_digest=hashlib.sha256(json.dumps(counter,ensure_ascii=False,
        sort_keys=True,separators=(',',':')).encode('utf-8')).hexdigest()
    check('revue_independante_corps_courante',independent['entrees_cles_sha256'][
        'verification/review_assemblage_prototype.json#contre_verification_corps']==counter_digest)
    active = manifest['prototype_cartographe']
    check('manifeste_actif',manifest['configuration_active']=='prototype_cartographe'
        and all(active[k]==build[k] for k in ('references','occurrences','sources_preservees','assemblage')))
    check('couverture_bom',coverage['bom_sha256']==sha(MEC/'nomenclature_prototype.json')
        and coverage['construction_sha256']==sha(VER/'construction_prototype.json')
        and {i['id'] for i in bom['items']}=={i['id'] for i in coverage['postes']})
    inventory = load(VER/'inventaire_reconstruction_prototype.json')
    check('sources_initiales_preservees',all(sha(ROOT/r['path'])==r['sha256'] for r in inventory['files']))
    previous_root=ROOT/'.runtime/finalisation_prototype/avant/hardware/mecanique/cartographe'
    previous=load(previous_root/'verification/construction_prototype.json')
    before_routes=load(previous_root/'verification/routes_prototype.json')
    camera=lambda b:next(o for o in b['occurrences'] if o['occurrence']=='EQ_Basler_Occurrence')
    check('camera_position_conservee',camera(previous)['matrice']==camera(build)['matrice'])
    check('energie_etage_superieur_conserve',next(o for o in previous['occurrences'] if o['occurrence']=='Isolation')['matrice']
        ==next(o for o in build['occurrences'] if o['occurrence']=='Isolation')['matrice'])
    # La recette acquise précède la reconstruction : le registre initial peut
    # encore décrire les anciens natifs. Ne pas assimiler sa persistance à la
    # suppression des corrections déjà présentes dans les sources.
    previous_recipe=previous_root/'verification/prototype_routage.py'
    inputs.add(previous_recipe)
    previous_tree=ast.parse(previous_recipe.read_text('utf-8'))
    route_function=next(n for n in previous_tree.body if isinstance(n,ast.FunctionDef)
        and n.name=='routes_basses')
    previous_namespace=dict(math=math)
    exec(compile(ast.Module(body=[route_function],type_ignores=[]),str(previous_recipe),'exec'),previous_namespace)
    acquired=previous_namespace['routes_basses']()+load(
        previous_root/'verification/configuration_faisceau_haut_prototype.json')['routes']
    profiles=lambda rows:{r['id']:(r['points_mm'],r['rayon_courbure_mm'],r['diametre_mm']) for r in rows}
    check('parcours_recettes_acquises_conserves',profiles(acquired)==profiles(routes['routes']))
    initial_profiles=profiles(before_routes['routes'])
    rebuilt_profiles=profiles(routes['routes'])
    reconstructed=[name for name,value in rebuilt_profiles.items() if initial_profiles.get(name)!=value]
    check('terminal_sol_hors_cao',not any(Path(o['source']).stem.startswith('SOL_') for o in build['occurrences']))
    previous_manifest=load(previous_root/'manifest.json')
    historical={k:v for k,v in previous_manifest.items() if k not in
        {'date_mise_a_jour','configuration_active','portee_champs_historiques','prototype_cartographe'}}
    check('manifeste_historique_preserve',all(manifest.get(k)==v for k,v in historical.items()))
    workbook = load(VER/'controle_nomenclature_prototype.json')
    check('export_bom_courant',workbook['entrees'][0]['sha256']==sha(MEC/'nomenclature_prototype.json')
        and all(e['sha256']==sha(ROOT/e['fichier']) for e in workbook['exports'])
        and all(c['reussi'] for c in workbook['controles']))
    rendered = load(VER/'rendu_prototype.json')
    check('vues_courantes',rendered['construction_sha256']==sha(VER/'construction_prototype.json')
        and rendered['routes_sha256']==sha(VER/'routes_prototype.json')
        and rendered['script_sha256']==sha(VER/'render_prototype.py')
        and rendered['lecteur_sha256']==sha(VER/'read_brep_prototype.py')
        and rendered['natifs_sha256']==native_files
        and rendered['finalisation_correcte'] and rendered['fichiers_non_modifies']
        and all(sha(MEC/r['fichier'])==r['sha256'] for r in rendered['vues']+build['vues']))
    appearances=load(VER/'controle_apparences_prototype.json')
    check('apparences_courantes',appearances['finalisation_correcte']
        and appearances['fichiers_non_modifies'] and appearances['erreurs']==[]
        and appearances['construction_sha256']==sha(VER/'construction_prototype.json')
        and appearances['routes_sha256']==sha(VER/'routes_prototype.json')
        and appearances['helper_sha256']==sha(VER/'etage_batterie_helpers.py')
        and appearances['nombre_cables']==len(routes['routes'])
        and all(table['table_conforme'] and table['sha256']==sha(MEC/table['fichier'])
                for table in appearances['tables_courantes']))
    check('limites_physiques_explicites',not bom['configuration']['fabrication_liberee']
        and not bom['configuration']['achat_libere'] and not assembly['validation_physique'])
    result = dict(date_utc=datetime.now(timezone.utc).isoformat(), reference='T-CARTO-REG-PROTO-01',
        script_fichier='verification/verify_registres_prototype.py',script_sha256=sha(__file__),
        resultat='Réussi',finalisation_correcte=True,controles=checks,
        entrees=[dict(fichier=p.relative_to(ROOT).as_posix(),sha256=sha(p)) for p in sorted(inputs)],
        natifs_initiaux_preserves=len(inventory['files']),
        parcours_actualises_depuis_recette_preexistante=reconstructed,
        portee_comparaison_parcours='Points, rayons et diamètres comparés aux recettes présentes avant cette tâche ; les écarts du registre initial sont listés, pas reconstruits comme décisions nouvelles.',
        limites=['Réconciliation numérique uniquement ; aucune qualification physique.'])
    (VER/'controle_registres_prototype.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n','utf-8')
    print(json.dumps(dict(resultat=result['resultat'],controles=len(checks),natifs_initiaux_preserves=len(inventory['files']))))


if __name__ == '__main__':
    try:
        run()
    except Exception:
        (VER/'controle_registres_prototype.json').write_text(json.dumps(dict(
            date_utc=datetime.now(timezone.utc).isoformat(),finalisation_correcte=False,
            resultat='Non conforme',erreur=traceback.format_exc()),ensure_ascii=False,indent=2)+'\n','utf-8')
        raise
