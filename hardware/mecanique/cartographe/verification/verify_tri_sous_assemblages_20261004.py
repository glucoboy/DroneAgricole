"""Infrastructure de vérification : ouverture FreeCAD séparée courant/archive."""
from pathlib import Path
import hashlib
import json
import sys
import time
import FreeCAD as A

sys.stdout.reconfigure(encoding='utf-8')
ROOT = Path(__file__).resolve().parents[4]
MEC = ROOT / 'hardware/mecanique/cartographe'
VER = MEC / 'verification'
PLAN = json.loads((VER / 'plan_tri_sous_assemblages_20261004.json').read_text(encoding='utf-8'))
ARCHIVE = Path(PLAN['archive'])
mode = sys.argv[1] if len(sys.argv) > 1 else 'courant'
assert mode in ['courant', 'archive', 'source_stack']
start = time.monotonic()

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def rel(p):
    return str(Path(p).relative_to(ROOT)).replace('\\', '/')

preserved = []
for row in PLAN['operations']:
    if row['fichier'].endswith(('.FCStd', '.FCBak')):
        assert sha(Path(row['destination'])) == row['sha256'], row['fichier']
        if row['operation'] == 'copy':
            assert sha(Path(row['source'])) == row['sha256'], row['fichier']
        else:
            assert not Path(row['source']).exists(), row['fichier']
        preserved.append(row['fichier'])
if mode == 'courant':
    entries = [MEC / 'sous_assemblages' / (n + '.FCStd') for n in PLAN['sous_assemblages_conserves']]
    entries.append(MEC / 'assemblages' / (PLAN['assemblage_conserve'] + '.FCStd'))
    assert sorted(p.stem for p in (MEC / 'sous_assemblages').glob('*.FCStd')) == sorted(PLAN['sous_assemblages_conserves'])
elif mode == 'archive':
    entries = [ARCHIVE / 'assemblages/Drone_Cartographe_Systeme_Candidat.FCStd']
else:
    from sources_cao_archivees_20261004 import load_chassis_source
    d = load_chassis_source()
    entries = []
for path in entries:
    if not any(d.FileName and Path(d.FileName).resolve() == path.resolve() for d in A.listDocuments().values()):
        A.openDocument(str(path))
for d in list(A.listDocuments().values()):
    d.recompute()
errors, unresolved, links = [], [], []
for d in A.listDocuments().values():
    for o in d.Objects:
        if 'Invalid' in o.State:
            errors.append({'fichier': rel(d.FileName), 'objet': o.Name, 'etat': list(o.State)})
        if o.TypeId == 'App::Link':
            target = o.LinkedObject
            if target is None:
                unresolved.append({'fichier': rel(d.FileName), 'objet': o.Name})
                continue
            source = Path(target.Document.FileName).resolve()
            if mode == 'courant':
                assert not source.is_relative_to(ARCHIVE.resolve()), str(source)
            if mode == 'archive':
                assert source.is_relative_to(ARCHIVE.resolve()), str(source)
            links.append({'assemblage': rel(d.FileName), 'occurrence': o.Name,
                          'source_fichier': rel(source), 'source_objet': target.Name,
                          'LinkTransform': o.LinkTransform,
                          'matrice_placement': list(o.LinkPlacement.toMatrix().A)})
assert not errors and not unresolved, (errors, unresolved)
result = {'date': '2026-10-04', 'mode': mode, 'finalisation_correcte': True,
          'besoin': 'MEC-ARC-001', 'controle': 'T-CARTO-TRI-NATIF-01',
          'version_FreeCAD': A.Version(), 'processus_neuf': True,
          'entrees': [rel(p) for p in entries], 'documents_charges': len(A.listDocuments()),
          'occurrences': links, 'erreurs_recalcul': errors, 'liens_non_resolus': unresolved,
          'empreintes_preservees': len(preserved), 'duree_s': time.monotonic() - start,
          'plan_sha256': sha(VER / 'plan_tri_sous_assemblages_20261004.json'),
          'script_sha256': sha(Path(__file__)),
          'limites': ['Contrôle de rangement et résolution des liens ; aucune nouvelle qualification physique ou géométrique.']}
if mode == 'source_stack':
    result['liens_chassis_vers_archive'] = [r for r in links if '/sous_assemblages/SA01_Chassis_Rehausse20.FCStd' in r['assemblage'] and '/archives/' in r['source_fichier']]
    assert not result['liens_chassis_vers_archive']
    result['helper_sha256'] = sha(VER / 'sources_cao_archivees_20261004.py')
    result['regeneration_stack_executee'] = False
for row in PLAN['operations']:
    if row['fichier'].endswith('.FCStd'):
        assert sha(Path(row['destination'])) == row['sha256']
        if row['operation'] == 'copy':
            assert sha(Path(row['source'])) == row['sha256']
target = VER / f'controle_tri_{mode}_20261004.json'
target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
assert json.loads(target.read_text(encoding='utf-8')) == result
print(json.dumps({k: result[k] for k in ['mode', 'finalisation_correcte', 'documents_charges', 'empreintes_preservees', 'duree_s']}), flush=True)
