"""Point de retour local avant migration énergie, sans changer l'index utilisateur."""
from pathlib import Path
import json, os, subprocess, tempfile
ROOT=Path(__file__).resolve().parents[4]; VER=Path(__file__).resolve().parent
def git(*args,env=None): return subprocess.check_output(['git',*args],cwd=ROOT,env=env,text=True,encoding='utf-8').strip()
branch='codex/batterie-avant-etage-inferieur'
if subprocess.run(['git','show-ref','--verify','--quiet','refs/heads/'+branch],cwd=ROOT).returncode==0: raise SystemExit('Point de retour déjà présent')
files=[r['fichier'] for r in json.loads((VER/'dependances_git_dock20Ah.json').read_text(encoding='utf-8'))['fichiers']]
files += ['hardware/mecanique/cartographe/'+p for p in ['sous_assemblages/SA07_Distribution_Systeme_Candidat.FCStd','assemblages/Integration_Stack_Revue_20261003.FCStd','pieces/commerce/EQ_PM08_CAN_Enveloppe_Systeme_Candidat.FCStd','pieces/commerce/EQ_Holybro_PDB18138_Systeme_Candidat.FCStd','manifest.json'] if (ROOT/'hardware/mecanique/cartographe'/p).exists()]
files += ['docs/architecture/ARCHITECTURE_MECANIQUE.md','docs/architecture/ARCHITECTURE_ELECTRIQUE_RESEAUX.md','docs/VALIDATION_QUALIFICATION.md','.gitignore']
files=list(dict.fromkeys(files))
parent=json.loads((VER/'suivi_git_dock20Ah.json').read_text(encoding='utf-8'))['commit_avant']
fd,name=tempfile.mkstemp(prefix='etage-index-',dir=ROOT);os.close(fd);Path(name).unlink()
env=dict(os.environ,GIT_INDEX_FILE=name)
try:
 git('read-tree',parent,env=env);git('add','-f','--',*files,env=env)
 commit=git('commit-tree',git('write-tree',env=env),'-p',parent,'-m','Batterie colorée compacte avant migration énergie sous batterie',env=env)
 git('update-ref','refs/heads/'+branch,commit,'')
finally: Path(name).unlink(missing_ok=True)
(VER/'suivi_git_etage_batterie.json').write_text(json.dumps(dict(branche=branch,commit=commit,fichiers=files,index_utilisateur_preserve=True),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(commit)
