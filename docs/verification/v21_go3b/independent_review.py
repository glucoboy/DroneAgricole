"""Vérifier les reçus publiés, la fermeture des archives et les chiffres GO3B."""

from collections import Counter
from hashlib import file_digest
import importlib.util
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'docs/verification'
DETAIL = OUT / 'v21_go3b'
HASHES = {}


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def sha(path):
    path = path.resolve(strict=True)
    if path not in HASHES:
        with path.open('rb') as stream:
            HASHES[path] = file_digest(stream, 'sha256').hexdigest()
    return HASHES[path]


def artifact(path):
    return {'path': path.relative_to(ROOT).as_posix(), 'sha256': sha(path)}


def main():
    findings, checks = [], []
    paths = [OUT / f'v21_go3b_{name}.json' for name in ('candidates', 'validation', 'manifest')]
    candidate, validation, manifest = map(read, paths)
    independent = read(DETAIL / 'independent_evidence.json')
    source = ROOT / '.agents/skills/electromechanical-integration/scripts/workspace_guard.py'
    spec = importlib.util.spec_from_file_location('go3b_workspace_guard_review', source)
    guard = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(guard)

    def check(ident, condition, reason):
        checks.append({'id': ident, 'status': 'PASS' if condition else 'FAIL'})
        if not condition:
            findings.append({'id': ident, 'reason': reason})

    def artifacts(value, context):
        if isinstance(value, dict):
            if isinstance(value.get('path'), str) and isinstance(value.get('sha256'), str):
                path = ROOT / value['path']
                check(context, path.is_file() and sha(path) == value['sha256'],
                      f'Fichier absent ou empreinte divergente {value["path"]}')
            for key, row in value.items():
                artifacts(row, context + '/' + key)
        elif isinstance(value, list):
            for i, row in enumerate(value):
                artifacts(row, context + '/' + str(i))

    for path, content in zip(paths, (candidate, validation, manifest)):
        artifacts(content, path.name)
        check(path.name + '/verdict', content['verdict'] == independent['verdict'], 'Verdict différent de la contre-validation')
    check('source_before_after', manifest['active_sources']['before'] == manifest['active_sources']['after'], 'Sources avant et après divergentes')
    for relative, digest in manifest['active_sources']['before'].items():
        check('source/' + relative, sha(ROOT / 'hardware/mecanique/cartographe' / relative) == digest,
              'La source active a changé depuis la campagne')
    for name, archive in manifest['archives'].items():
        root = ROOT / archive['root']
        dependencies = {path.relative_to(root).as_posix() for path in guard.dependencies(root, ['assemblages/Prototype_Cartographe.FCStd'])}
        check('closure/' + name, dependencies == archive['native_sha256'].keys(), 'Fermeture XLink de l’archive divergente du manifeste')
        for relative, digest in (archive['native_sha256'] | archive['auxiliary_sha256']).items():
            check('archive/' + name + '/' + relative, sha(root / relative) == digest, 'Archive différente de la copie mesurée')
    for name, value in independent['cases'].items():
        actual = validation['independent_cases'][name]
        check('counts/' + name, actual['counts'] == value['counts'], 'Couverture publiée différente des mesures indépendantes')
        check('native_counts/' + name, actual['native_pair_measurement_counts'] == value['native_pair_measurement_counts'],
              'Statuts des mesures natives et d’admission mélangés')
        for field, status in value['counts']['by_status'].items():
            check('count_nonnegative/' + name + '/' + field, type(status) is int and status >= 0, 'Dénombrement invalide')
    for control in validation['controls']:
        if control['status'] == 'FAIL':
            for requirement in control['requirements']:
                check('failed_requirement/' + requirement + '/' + control['id'], validation['requirements'][requirement]['status'] == 'FAIL',
                      f'{control["id"]} échoue mais {requirement} n’est pas déclaré FAIL')
    check('status_counts', dict(Counter(row['status'] for row in validation['controls'])) == validation['control_status_counts'],
          'Dénombrement des contrôles divergent')
    check('budget', candidate['budget']['spent_experiences'] == sum(row['counted_experience'] for row in candidate['candidates']) == 9,
          'Comptage des expériences différent des expériences réellement lancées')
    service = read(DETAIL / 'service_evidence.json')
    check('service_samples', service['samples'] == sum(len(row['envelopes']) for row in service['cases'].values()) == 93,
          'Couverture des sondes de service divergente')
    check('service_terminal', all(row['status'] == 'COMPLETE' for row in service['cases'].values()),
          'Un contrôle de service n’est pas finalisé')
    report_path = ROOT / 'docs/electromechanical_v2_1/06_GO3B_REPORT.md'
    report = report_path.read_text(encoding='utf-8')
    for href in re.findall(r'\]\(([^)]+)\)', report):
        target, _, anchor = href.partition('#')
        path = (report_path.parent / target).resolve()
        check('report_link/' + href, path.is_file(), 'Lien de rapport absent')
        if anchor and path.is_file():
            content = path.read_text(encoding='utf-8')
            check('report_anchor/' + href, f'id="{anchor}"' in content, 'Ancre de document vivant absente')
    documents = [ROOT / path for path in ('docs/architecture/HLD.md',
                 'docs/architecture/ARCHITECTURE_MECANIQUE.md',
                 'docs/architecture/ARCHITECTURE_ELECTRIQUE_RESEAUX.md', 'docs/VALIDATION_QUALIFICATION.md')]
    for path in documents:
        text = path.read_text(encoding='utf-8')
        check('document_verdict/' + path.name, 'GO3B_CAO_NO_GO_MOTIVE' in text,
              'La décision GO3B courante manque dans le document vivant')
    review = {'schema': 'drone-agricole.v21.go3b.independent-review.v1', 'date': '2026-11-17',
              'status': 'REVIEW_PASS' if not findings else 'REVIEW_CHANGES_REQUESTED',
              'scope': 'Cohérence des livrables, fermeture XLink et empreintes des archives, traçabilité des statuts et des contrôles.',
              'files_hashed': len(HASHES), 'checks': checks, 'findings': findings,
              'reviewed_artifacts': [artifact(path) for path in [*paths, report_path]],
              'reviewed_documents': [artifact(path) for path in documents],
              'manual_review': ['Les nombres de variantes, tentatives et crédits concordent avec les reçus natifs.',
                                'Les mesures nominales favorables et les statuts d’admission sont explicitement séparés.',
                                'Les sondes ASSUMED, la portée de leur seuil et les contrôles physiques non exécutés restent explicites.',
                                'La consolidée conserve les défauts de diagnostic et les sept défauts B.2. Le NO_GO est motivé.',
                                'La comparaison utilise le même inventaire et les zones gelées. Les métriques concordent aux arrondis publiés.'],
              'not_run': ['Réouverture GUI de chaque archive après déplacement', 'Essais physiques et fabrication']}
    path = DETAIL / 'independent_review.json'
    path.write_text(json.dumps(review, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(review['status'], 'checks', len(checks), 'findings', findings)
    return 0 if not findings else 1


if __name__ == '__main__':
    raise SystemExit(main())
