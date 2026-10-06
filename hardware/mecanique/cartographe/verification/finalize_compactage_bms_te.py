"""Consolider les preuves du raccord compact, sans qualifier le matériel."""
from garde_hierarchie_batterie import require_monolithic_layout
require_monolithic_layout('finalize_compactage_bms_te.py')
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parents[4]
VER = ROOT / 'hardware/mecanique/cartographe/verification'


def read(name):
    return json.loads((VER / name).read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


current = read('compactage_raccord_bms_te.json')
geometry = read('controle_bms_cassette.json')
assert geometry['finalisation_correcte'] and geometry['raccord_compact']['entrees_cosses_axiales']
assert current['reference_git'] == '1ccbad81' and current['avant']['nombre_sources'] == 147
for path, digest in geometry['sources_sha256'].items():
    assert sha(ROOT / path) == digest, path

names = ['controle_bms_cassette.json', 'controle_faisceau_natif_bms.json',
         'controle_routes_systeme_courant.json', 'controle_registres_bms.json',
         'controle_rejeux_bms_dessus.json', 'rendu_bms_cassette.json',
         'correction_protection_p49.json']
for name in names:
    assert read(name)['finalisation_correcte'], name
correction = read('correction_protection_p49.json')
assert sha(ROOT / correction['fichier']) == correction['sha256_apres']
assert sha(ROOT / correction['recette']) == correction['recette_sha256']
assert correction['solides_apres'] == 1 and correction['BOP_sain']
render = read('rendu_bms_cassette.json')
assert render['sources_non_modifiees'] and render['sources_sha256'] == geometry['sources_sha256']
for image in render['images']:
    assert sha(ROOT / image['fichier']) == image['sha256'], image['fichier']
current['sources_apres_verification_sha256'] = geometry['sources_sha256']
current['preuves_finales_sha256'] = {name: sha(VER / name) for name in names}
current['apres'].setdefault('sources_immediat_enregistrement_sha256', current['apres']['sources_sha256'])
current['apres']['sources_sha256'] = geometry['sources_sha256']
for scope in ['dock', 'cassette_mobile']:
    key = 'bbox_' + scope + '_mm'
    current['apres'].setdefault(key + '_immediat_enregistrement', current['apres'][key])
    current['apres'][key] = current['bbox_apres_verification_mm'][scope]
current['apres']['methode_bbox_final'] = 'Réouverture, touch et deux recalculs de toutes les dépendances ; contrôle_bms_cassette'
current['comparaison_depuis_reference'] = {}
for scope, before in current['avant']['bbox_mm'].items():
    if scope not in current['bbox_apres_verification_mm']:
        continue
    after = current['bbox_apres_verification_mm'][scope]
    a = [before[i + 3] - before[i] for i in range(3)]
    b = [after[i + 3] - after[i] for i in range(3)]
    current['comparaison_depuis_reference'][scope] = {
        'dimensions_avant_mm': a, 'dimensions_apres_mm': b,
        'variation_dimensions_mm': [b[i] - a[i] for i in range(3)]}
current['apres']['relecture_independante'] = 'Voir revue_bms_cassette.json ; distincte de la qualification physique'
current['qualification'] = 'À valider'
current['finalisation_correcte'] = True
(VER / 'compactage_raccord_bms_te.json').write_text(
    json.dumps(current, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(current['comparaison_depuis_reference'], ensure_ascii=False))
