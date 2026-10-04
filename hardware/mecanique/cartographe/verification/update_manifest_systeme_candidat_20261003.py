"""Infrastructure de synchronisation du manifeste de la variante de revue.

Préserve tous les champs existants et les quantités de la configuration active.
À lancer après construction puis contrôle dans des processus indépendants.
"""
from pathlib import Path
import hashlib
import json
from collections import Counter

ROOT = Path(__file__).resolve().parents[4]
MEC = ROOT / 'hardware/mecanique/cartographe'
VER = MEC / 'verification'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


construction = read(VER / 'construction_systeme_faisceau_20261003.json')
controle = read(VER / 'controle_systeme_faisceau_20261003.json')
assert controle['finalisation_correcte']
assert controle['construction_sha256'] == sha(VER / 'construction_systeme_faisceau_20261003.json')
assert all(sha(ROOT / r['fichier']) == r['sha256'] for r in construction['nouveaux_fichiers'])
assert all(sha(ROOT / f) == h for f, h in construction['sources_preservees_sha256'].items())
registre_path = ROOT / 'hardware/electronique/cartographe/faisceau_systeme_cible_20261003.json'
registre = read(registre_path)
liaisons_path = ROOT / registre['source_liaisons']
attendues = {r['id'] for r in read(liaisons_path)['connections']}
comptees = Counter(w for g in registre['groupes'] for w in g['wxx'])
assert set(comptees) == attendues and all(n == 1 for n in comptees.values())
assert len(construction['routes']) == controle['routes_natives']
assert len(construction['occurrences']) == 45

manifest_path = MEC / 'manifest.json'
before = read(manifest_path)
protected = {k: v for k, v in before.items() if k != 'configuration_systeme_candidate'}
before['configuration_systeme_candidate'] = {
    'reference': 'CFG-CARTO-CIBLE-20261003',
    'date': '2026-10-03',
    'active': False,
    'statut': 'Implémenté en maquette ; À valider',
    'assemblage': 'assemblages/Drone_Cartographe_Systeme_Candidat.FCStd',
    'besoins': ['MEC-ARC-001', 'MEC-AVI-001', 'MEC-MAS-001', 'CAB-CARTO-001', 'ELEC-PWR-002'],
    'documentation': ['docs/architecture/ARCHITECTURE_MECANIQUE.md#45-points-restant-à-fermer-pour-le-drone-cartographe',
                      'docs/architecture/ARCHITECTURE_ELECTRIQUE_RESEAUX.md',
                      'docs/VALIDATION_QUALIFICATION.md#1214-configuration-et-faisceau-système-candidats-3-octobre-2026'],
    'bom': 'configuration_cible_20261003.json',
    'faisceau': '../../electronique/cartographe/faisceau_systeme_cible_20261003.json',
    'recette_routes': 'verification/routes_systeme_candidat_20261003.json',
    'references_nouvelles': [{**r, 'type': ('Assemblage lié' if '/assemblages/' in r['fichier'] or '/sous_assemblages/' in r['fichier']
                                         else 'Cordon à balayage natif' if 'EQ_Route_' in r['fichier']
                                         else 'Référence commerciale ou enveloppe nominale'),
                             'statut': 'Implémenté en maquette ; À valider', 'quantite_drone_actif': 0}
                            for r in construction['nouveaux_fichiers']],
    'occurrences': construction['occurrences'],
    'preuves': ['verification/construction_systeme_faisceau_20261003.json',
                'verification/controle_systeme_faisceau_20261003.json',
                'verification/bilan_masse_systeme_candidat_20261003.json',
                'verification/rendu_systeme_faisceau_20261003.json',
                'verification/revue_systeme_faisceau_20261003.json'],
    'fixations_completes': False, 'faisceau_complet': False, 'passages_valides': False,
    'limites': construction['limites']
}
write(manifest_path, before)
after = read(manifest_path)
assert protected == {k: v for k, v in after.items() if k != 'configuration_systeme_candidate'}
write(VER / 'controle_manifest_systeme_candidat_20261003.json', {
    'date': '2026-10-03', 'statut': 'Implémenté ; conception À valider',
    'finalisation_correcte': True, 'champs_preexistants_preserves': True,
    'references_nouvelles': len(construction['nouveaux_fichiers']),
    'occurrences': len(construction['occurrences']),
    'sources_CAO_preservees': len(construction['sources_preservees_sha256']),
    'manifest_sha256': sha(manifest_path), 'construction_sha256': sha(VER / 'construction_systeme_faisceau_20261003.json'),
    'controle_sha256': sha(VER / 'controle_systeme_faisceau_20261003.json'),
    'script_sha256': sha(Path(__file__)),
    'entrees_registre_sha256': {
        'configuration_cible_20261003.json': sha(MEC / 'configuration_cible_20261003.json'),
        str(registre_path.relative_to(ROOT)).replace('\\', '/'): sha(registre_path),
        str(liaisons_path.relative_to(ROOT)).replace('\\', '/'): sha(liaisons_path),
        'verification/routes_systeme_candidat_20261003.json': sha(VER / 'routes_systeme_candidat_20261003.json')
    },
    'couverture_Wxx_unique': len(comptees),
    'limite': 'Cohérence et préservation du manifeste ; aucune qualification de montage.'
})
print(json.dumps({'references': len(construction['nouveaux_fichiers']),
                  'occurrences': len(construction['occurrences']), 'champs_preexistants_preserves': True}))
