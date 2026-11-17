"""Instantané du découpage revu ; conserve branche et index de travail."""
from pathlib import Path
import hashlib,json,os,subprocess,tempfile
ROOT=Path(__file__).resolve().parents[4]
VER=Path(__file__).resolve().parent

def read(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None
def git(*args,env=None):
    return subprocess.check_output(['git',*args],cwd=ROOT,env=env,text=True,encoding='utf-8').strip()

review=read(VER/'revue_hierarchie_batterie.json')
assert review['revue_finalisee'] and not review['points_P1_non_resolus'] and not review['points_P2_non_resolus']
for group in ('fichiers_revus_sha256','sources_natives_revalidees_sha256'):
    for f,h in review[group].items():assert sha(ROOT/f)==h,('Revue périmée',f)
for name in ('decoupage_sous_assemblages_batterie.json','controle_hierarchie_batterie.json',
             'hierarchie_batterie_recepteur.json','controle_rejeux_hierarchie_batterie.json'):
    assert read(VER/name)['finalisation_correcte'],name
branch='codex/batterie-etage-inferieur'
parent=git('rev-parse','refs/heads/'+branch)
assert parent==read(VER/'decoupage_sous_assemblages_batterie.json')['reference_git']
small_sources={p for p in review['sources_natives_revalidees_sha256'] if (ROOT/p).stat().st_size<1000000}
files=sorted(set(review['fichiers_revus_sha256']) | small_sources |
             {'hardware/mecanique/cartographe/verification/revue_hierarchie_batterie.json'})
assert not any(f=='AGENTS.md' or f.endswith('.history') or '/exports/' in f or
               '/sources_fabricants/' in f or f.endswith('.png') for f in files)
assert all((ROOT/f).is_file() for f in files)
assert all((ROOT/f).stat().st_size<1000000 for f in files if f.endswith('.FCStd'))
index=ROOT/'.git/index'
initial_index=sha(index)
initial_branch=git('rev-parse','--abbrev-ref','HEAD')
unrelated=['AGENTS.md','hardware/electronique/cartographe/carte_avionique/.history']
def unrelated_state(p):
    if (ROOT/p).is_dir():
        return dict(diff=git('diff','--raw','--',p),statut=git('status','--short','--',p))
    return sha(ROOT/p)
initial_unrelated={p:unrelated_state(p) for p in unrelated}
fd,name=tempfile.mkstemp(prefix='hierarchie-index-',dir=ROOT)
os.close(fd);Path(name).unlink()
env=dict(os.environ,GIT_INDEX_FILE=name)
try:
    git('read-tree',parent,env=env)
    git('add','-f','--',*files,env=env)
    commit=git('commit-tree',git('write-tree',env=env),'-p',parent,'-m',
               'Séparer batterie et récepteur ; monter les équipements énergie dans le principal',env=env)
    git('update-ref','refs/heads/'+branch,commit,parent)
finally:
    Path(name).unlink(missing_ok=True)
assert sha(index)==initial_index and git('rev-parse','--abbrev-ref','HEAD')==initial_branch
assert {p:unrelated_state(p) for p in unrelated}==initial_unrelated
for f in files:
    if f.endswith('.FCStd'):
        blob=subprocess.check_output(['git','show',commit+':'+f],cwd=ROOT)
        assert hashlib.sha256(blob).hexdigest()==sha(ROOT/f),f
    else:
        assert git('rev-parse',commit+':'+f)==git('hash-object','--path='+f,f),f
proof=dict(branche_courante=branch,commit_courant=commit,commit_avant=parent,fichiers=files,
           index_utilisateur_preserve=True,branche_de_travail_preservee=True,
           modifications_non_liees_preservees=True,natifs_git_octets_identiques=True,
           textes_git_equivalents_apres_normalisation=True,
           sources_natives_lourdes_exclues=sorted(set(review['sources_natives_revalidees_sha256'])-small_sources),
           revue_sha256=sha(VER/'revue_hierarchie_batterie.json'),finalisation_correcte=True)
(VER/'suivi_git_hierarchie_batterie.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(commit=commit,branche=branch,fichiers=len(files)),ensure_ascii=False))
