"""Infrastructure : inscrire l'évolution courante sans réécrire les preuves historiques."""
from pathlib import Path
import json
import hashlib

MEC = Path(__file__).resolve().parents[1]
VER = MEC/'verification'
manifest_path = MEC/'manifest.json'
manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
control = json.loads((VER/'controle_compacite_dock20Ah.json').read_text(encoding='utf-8'))
colors = json.loads((VER/'couleurs_dock20Ah.json').read_text(encoding='utf-8'))
git = json.loads((VER/'suivi_git_dock20Ah.json').read_text(encoding='utf-8'))
assert control['finalisation_correcte'] and control['erreurs_recalcul'] == []
manifest['configuration_dock20Ah']['evolution_courante'] = {
    'date': '2026-10-04', 'noms_stables': True, 'assemblage': 'sous_assemblages/SA02A_Dock20Ah.FCStd',
    'realisation_CAO': 'Implémenté', 'statut': 'À valider',
    'verification': 'verification/controle_compacite_dock20Ah.json',
    'couleurs': 'verification/couleurs_dock20Ah.json', 'rendu': 'verification/rendu_dock20Ah_courant.json',
    'dimensions_conservatrices_mm': control['dimensions_mm'],
    'cordons_fixes': control['routes'], 'placements_modifies': False,
    'longueurs_preparation_mm': None, 'limite_preparation': 'Coupe à déterminer sur gabarit et lot réel.',
    'registre_faisceau_historique': 'verification/faisceau_dock20Ah_20261002.json',
    'branche_Git_etat_initial': git['branche_avant'], 'commit_Git_etat_initial': git['commit_avant'],
    'limites': control['limites'], 'DOC_MEC': '§4.1.3.1', 'DOC_VAL': '§12.1.7',
}
for row in manifest['catalogue_courant_20261004']['selection']:
    if row['reference'] == 'SA02A_Dock20Ah':
        row.update({'sha256': colors['sha256_apres'], 'verification': 'verification/controle_compacite_dock20Ah.json'})
manifest['catalogue_courant_20261004']['politique_noms'] = 'Fichiers évolués en place ; retours arrière Git des petits natifs explicitement suivis.'
manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
proof = {'date': '2026-10-04', 'finalisation_correcte': True, 'occurrences_preservees': control['occurrences_dock'],
         'manifest_sha256': hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
         'controle_sha256': hashlib.sha256((VER/'controle_compacite_dock20Ah.json').read_bytes()).hexdigest(),
         'limite': 'Aucun placement, comptage historique ou archive réécrit.'}
(VER/'controle_manifest_compacite_dock20Ah.json').write_text(json.dumps(proof, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
print(json.dumps(proof))
