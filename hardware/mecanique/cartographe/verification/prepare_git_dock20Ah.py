"""Infrastructure Git : instantané local des petits natifs avant édition.

La branche courante et l'index de l'utilisateur ne sont jamais modifiés.
Les exceptions de suivi sont limitées aux dépendances inventoriées du dock.
"""
from pathlib import Path
import json
import os
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[4]
VER = Path(__file__).resolve().parent
data = json.loads((VER / 'dependances_git_dock20Ah.json').read_text(encoding='utf-8'))
files = [r['fichier'] for r in data['fichiers']]
assert data['total_octets'] < 5_000_000
assert all((ROOT / f).resolve().is_relative_to(ROOT.resolve()) for f in files)
assert all(f.endswith('.FCStd') and (ROOT / f).stat().st_size < 500_000 for f in files)
branch = 'codex/batterie-avant-evolution-20261004'


def git(*args, env=None):
    return subprocess.check_output(['git', *args], cwd=ROOT, env=env, text=True, encoding='utf-8').strip()


existing = subprocess.run(['git', 'show-ref', '--verify', '--quiet', 'refs/heads/'+branch], cwd=ROOT).returncode == 0
if existing:
    raise SystemExit('Instantané déjà présent ; ne pas écraser la branche '+branch)
head = git('rev-parse', 'HEAD')
fd, index_name = tempfile.mkstemp(prefix='dock-git-index-', dir=ROOT)
os.close(fd)
index_path = Path(index_name)
index_path.unlink()
env = dict(os.environ, GIT_INDEX_FILE=str(index_path))
try:
    git('read-tree', head, env=env)
    git('add', '-f', '--', *files, env=env)
    tree = git('write-tree', env=env)
    commit = git('commit-tree', tree, '-p', head, '-m', 'Instantané des natifs batterie avant couleurs et compacité', env=env)
    git('update-ref', 'refs/heads/'+branch, commit, '')
finally:
    index_path.unlink(missing_ok=True)

ignore = ROOT / '.gitignore'
text = ignore.read_text(encoding='utf-8')
marker = '# Petits natifs du dock batterie : suivi Git explicite, noms stables\n'
assert marker not in text
ignore.write_text(text.rstrip()+'\n\n'+marker+'\n'.join('!/'+f for f in files)+'\n', encoding='utf-8')
proof = {'date': '2026-10-04', 'branche_avant': branch, 'commit_avant': commit,
         'index_utilisateur_preserve': True, 'branche_courante_preservee': True,
         'fichiers': data['fichiers'], 'total_octets': data['total_octets'],
         'limite': 'Sources fabricant lourdes, archives et exports exclus ; instantané local sans publication.'}
(VER / 'suivi_git_dock20Ah.json').write_text(json.dumps(proof, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
print(json.dumps({'branche': branch, 'commit': commit, 'fichiers': len(files), 'octets': data['total_octets']}))
