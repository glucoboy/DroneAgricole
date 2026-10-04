"""Instantané Git local de la conception, sans changer branche ni index utilisateur."""
from pathlib import Path
import hashlib,json,os,subprocess,tempfile
ROOT=Path(__file__).resolve().parents[4];MEC=ROOT/'hardware/mecanique/cartographe';VER=MEC/'verification'
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None
def git(*args,env=None):return subprocess.check_output(['git',*args],cwd=ROOT,env=env,text=True,encoding='utf-8').strip()
review=read(VER/'revue_etage_batterie.json');assert not review['p1_non_resolus'] and not review['p2_non_resolus']
assert read(VER/'controle_registres_etage_batterie.json')['finalisation_correcte']
branch='codex/batterie-etage-inferieur';before=read(VER/'suivi_git_etage_batterie.json')
m=read(MEC/'manifest.json');m['configuration_dock20Ah']['evolution_courante']['branche_Git_courante']=branch
(MEC/'manifest.json').write_text(json.dumps(m,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
files=before['fichiers']+[r['fichier'] for r in read(VER/'nomenclature_etage_batterie.json')['occurrences']]
files+=['hardware/mecanique/README.md','hardware/mecanique/cartographe/README.md','AGENTS.md']
files+=['hardware/mecanique/cartographe/sous_assemblages/'+s+'.FCStd' for s in ['SA02_Cassette20Ah_Coulissante','SA02_Contacts20Ah']]
files+=git('ls-files','--others','--exclude-standard','--','hardware/mecanique/cartographe/verification').splitlines()
files+=git('diff','--name-only','--','hardware/mecanique/cartographe/verification').splitlines()
files=[f for f in dict.fromkeys(files) if f and (ROOT/f).is_file() and not f.endswith('/suivi_git_etage_batterie_courant.json')]
assert all((ROOT/f).stat().st_size<1000000 for f in files if Path(f).suffix=='.FCStd'),'Un natif CAO volumineux ne doit pas être versionné'
assert not any(f.endswith('.history') or '/sources_fabricants/' in f or '/exports/' in f for f in files)
index=ROOT/'.git/index';unrelated='hardware/electronique/cartographe/carte_avionique/.history'
initial_index=sha(index);initial_unrelated=git('diff','--raw','--',unrelated);initial_branch=git('rev-parse','--abbrev-ref','HEAD')
fd,name=tempfile.mkstemp(prefix='etage-courant-index-',dir=ROOT);os.close(fd);Path(name).unlink();env=dict(os.environ,GIT_INDEX_FILE=name)
old=subprocess.run(['git','rev-parse','--verify','refs/heads/'+branch],cwd=ROOT,capture_output=True,text=True)
parent=old.stdout.strip() if old.returncode==0 else before['commit']
try:
 git('read-tree',parent,env=env);git('add','-f','--',*files,env=env)
 commit=git('commit-tree',git('write-tree',env=env),'-p',parent,'-m','Batterie directe TE et énergie à étage inférieur, conception CAO candidate',env=env)
 git('update-ref','refs/heads/'+branch,commit,old.stdout.strip() if old.returncode==0 else '')
finally:Path(name).unlink(missing_ok=True)
assert sha(index)==initial_index and git('diff','--raw','--',unrelated)==initial_unrelated and git('rev-parse','--abbrev-ref','HEAD')==initial_branch
proof={'branche_courante':branch,'commit_courant':commit,'branche_avant':before['branche'],'commit_avant':before['commit'],'fichiers':files,'index_utilisateur_preserve':True,'branche_de_travail_preservee':True,'modification_electronique_preservee':True,'sources_lourdes_et_exports_exclus':True,'finalisation_correcte':True}
(VER/'suivi_git_etage_batterie_courant.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'branche':branch,'commit':commit,'fichiers':len(files),'index_utilisateur_preserve':True}))
