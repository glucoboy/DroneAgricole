"""Consolider les preuves légères des réouvertures et mesures indépendantes GO3B."""

from collections import Counter
from hashlib import file_digest
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
WORK = ROOT / '.runtime/v21-go3b-validation'
TARGET = ROOT / 'docs/verification/v21_go3b/independent_evidence.json'
CASES = ['baseline', 'H03-A', 'H03-B', 'H02-A', 'H02-B', 'H01-A-reprise', 'H01-B-reprise', 'consolidee']
STATUSES = ['PASS', 'FAIL', 'INCONCLUSIVE', 'NOT_RUN']


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def sha(path):
    with path.open('rb') as stream:
        return file_digest(stream, 'sha256').hexdigest()


def artifact(path):
    return {'path': path.relative_to(ROOT).as_posix(), 'sha256': sha(path)}


def status_counts(values):
    counts = Counter(values)
    return {status: counts[status] for status in STATUSES}


def main():
    model = read(ROOT / 'docs/verification/go3a/GO3A_SYSTEM_MODEL.json')
    active = ROOT / 'hardware/mecanique/cartographe'
    hashes = model['cad']['native_sha256']
    changed_active = [path for path, digest in hashes.items() if sha(active / path) != digest]
    if changed_active:
        raise RuntimeError(f'La source active a changé : {changed_active}')
    evidence = {
        'schema': 'drone-agricole.v21.go3b.independent-evidence.v1',
        'date': '2026-11-17', 'test_id': 'T-CARTO-V21-GO3B-INDEPENDENT',
        'verdict': 'GO3B_CAO_NO_GO_MOTIVE',
        'scope': 'Copies natives du prototype cartographe sans dock, Windows AMD64, FreeCAD 1.1.3, Cables 0.3.7, OCCT 7.8.1',
        'reference_sha256': '3fc4260910647d3ab5ccffdb1406847ffb310dfec6e45fb221186274fe8535b9',
        'read_only': {'active_files_verified_unchanged': len(hashes), 'changed_active': changed_active},
        'method': {
            'reference': 'Critères B.2 gelés, tolérance de volume 0 mm³, garde nominale 0 mm et tolérance de distance 1e-6 mm.',
            'reopening': 'Chaque copie sauvegardée est relue, complétée et recalculée dans un nouveau processus FreeCAD. Aucun fichier candidat n’est sauvegardé par la mesure indépendante.',
            'reuse': 'Une paire B.2 n’est réemployée que si les deux occurrences ont mêmes identités, BRep sérialisés SHA-256, matrices, visibilité, boîtes et définition d’axe. L’environnement et les critères gelés sont contrôlés. Les sept défauts historiques sont remesurés sur chaque copie.',
            'aabb': 'Toutes les combinaisons de solides visibles avec au moins un câble sont énumérées. Un écart AABB au-delà du seuil est une exclusion de criblage géométrique.',
            'solid_status': 'Validité et volume strictement positif du solide rouvert. PASS est limité au contrôle de solide.',
            'pair_status': 'Une intersection positive non autorisée donne FAIL. Un volume nul au criblage nominal donne INCONCLUSIVE pour l’admission. Une paire prévue sans mesure donne NOT_RUN.',
            'bounded_measurement': '42 mesures de paires nouvelles par variante, 86 mesures conservées pour H03-A. Le lot de consolidation est borné à 45 mesures et en finalise 36 avant interruption du couple porteur/F12. Les couples porteur/F12, porteur/F25 et porteur/F35 bloquants restent différés avec leurs checkpoints. Les mesures sauvegardées sont reprises sans répétition.',
            'metrics': 'Longueurs exactes des axes natifs. Longueurs par zone approximées avec 96 et 384 points par courbe et clipping des segments, mêmes zones et repère sur chaque copie. Les valeurs 96 points reproduisent la baseline historique arrondie.',
            'service': 'Les boîtes ASSUMED de service sont des racines indépendantes du natif d’essai hors du groupe lié. Elles ne sont pas incluses dans les solides physiques du contrôle B.2. Le criblage de service possède ses propres preuves, seuils et hypothèses.',
            'ranking': 'Aucune variante n’est admissible. Les nombres de défauts mesurés sont des bornes inférieures avec des couvertures différentes. Ils ne fondent pas un classement de conformité.'},
        'cases': {}, 'artifacts': {},
        'not_run': ['Assemblage physique et continuité mesurée aux contacts', 'Mesures de courant et isolement électrique',
                    'Domaine mobile continu qualifié F16/M8', 'Vibration, fatigue, CEM, thermique et vol'],
        'execution_corrections': [{'issue': 'Identifiant de portée avec lettres majuscules refusé par le contrat T0 sur le premier L4 H03-A.',
                                   'resolution': 'Nouvelle session L4 avec identifiant en minuscules, finalisation et validation T0 exécutées.'}],
    }
    for case in CASES:
        directory = WORK / case / 'independent'
        report_path, pairs_path, metrics_path = (directory / name for name in ('report.json', 'pairs.json', 'metrics.json'))
        report, pairs, metrics = read(report_path), read(pairs_path), read(metrics_path)
        if not report['finalized'] or not report['closure']['unchanged']:
            raise RuntimeError(f'Relecture non finalisée pour {case}')
        if any(sha(ROOT / report['scope'] / name) != digest
               for name, digest in report['closure']['before_sha256'].items()):
            raise RuntimeError(f'La copie a changé depuis sa mesure {case}')
        historical = report['known_b2_failures']
        if len(historical) != 7 or any(row['status'] != 'FAIL' for row in historical):
            raise RuntimeError(f'Échecs B.2 non réconciliés pour {case}')
        counts = report['counts']
        observed_status = status_counts(row['status'] for row in pairs)
        if observed_status != counts['by_status']:
            raise RuntimeError(f'Comptage des paires divergent pour {case}')
        native_counts = status_counts({'pass': 'PASS', 'fail': 'FAIL', 'unknown': 'INCONCLUSIVE'}[row['observation']['status']]
                                      if 'observation' in row else 'NOT_RUN' for row in pairs)
        row = {'status': 'FAIL', 'native_count': len(report['closure']['documents']),
               'source_candidate_root_sha256': report['closure']['before_sha256']['assemblages/Prototype_Cartographe.FCStd'],
               'fresh_worker_pid': report['pid'],
               'closure': {'status': report['closure']['status'], 'recompute_ok': report['closure']['recompute_ok'],
                           'broken_links': report['closure']['broken_links'], 'invalid_objects': report['closure']['invalid_objects'],
                           'saved_copy_unchanged': report['closure']['unchanged']},
               'counts': counts, 'native_pair_measurement_counts': native_counts,
               'historical_failure_count': len(historical),
               'new_observed_failure_count': len(report['observed_failures']) - len(historical),
               'known_failures': report['observed_failures'],
               'unavailable_visible_occurrences': report['unavailable_visible_occurrences'],
               'metrics': {key: value for key, value in metrics.items() if key != 'axes'},
               'criteria_open': report['criteria_open'],
               'artifacts': {name: artifact(path) for name, path in [('report', report_path), ('pairs', pairs_path), ('metrics', metrics_path)]}}
        l4_receipt = WORK / case / 'l4_receipt.json'
        if l4_receipt.exists():
            l4 = read(l4_receipt)
            if not l4.get('finalized') or l4.get('t0_exit_code') != 0:
                raise RuntimeError(f'L4/T0 non finalisé pour {case}')
            row['l4'] = {key: l4[key] for key in ('status', 'exit_code', 't0_exit_code', 'electrical', 'nominal_equipment_poses', 'campaign', 't0_manifest')}
            row['artifacts']['l4_receipt'] = artifact(l4_receipt)
        evidence['cases'][case] = row
    for name in ('independent_replay.py', 'independent_l4.py', 'independent_finalize.py'):
        evidence['artifacts'][name] = artifact(TARGET.with_name(name))
    evidence['conclusion'] = ('La consolidation conservatrice sauvegardée comporte encore les sept interférences B.2 nominales. '
                              'Les six variantes détaillées introduisent des défauts supplémentaires mesurés. '
                              'Les contrôles non exécutés restent dans leur dénominateur. '
                              'La contre-validation soutient un NO_GO sur cette réception CAO.')
    TARGET.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(artifact(TARGET))


if __name__ == '__main__':
    main()
