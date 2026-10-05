"""Instantané Git local de la conception, sans changer branche ni index utilisateur."""
from pathlib import Path
import hashlib,json,os,subprocess,tempfile,sys
ROOT=Path(__file__).resolve().parents[4];MEC=ROOT/'hardware/mecanique/cartographe';VER=MEC/'verification'
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None
def git(*args,env=None):return subprocess.check_output(['git',*args],cwd=ROOT,env=env,text=True,encoding='utf-8').strip()
is_bms='--bms' in sys.argv
review=read(VER/('revue_bms_cassette.json' if is_bms else 'revue_etage_batterie.json'))
if is_bms:
 assert review['revue_finalisee'] and not review['points_P1_non_resolus'] and not review['points_P2_non_resolus']
 assert read(VER/'compactage_raccord_bms_te.json')['finalisation_correcte'],'Raccord compact non finalisé'
 for group in ['fichiers_revus_sha256','sources_natives_revalidees_sha256']:
  for f,h in review[group].items():assert sha(ROOT/f)==h,('Revue périmée',f)
else:assert not review['p1_non_resolus'] and not review['p2_non_resolus']
assert read(VER/('controle_registres_bms.json' if is_bms else 'controle_registres_etage_batterie.json'))['finalisation_correcte']
branch='codex/batterie-etage-inferieur';before=read(VER/'suivi_git_etage_batterie.json')
m=read(MEC/'manifest.json')
assert m['configuration_dock20Ah']['evolution_courante']['branche_Git_courante']==branch,'Synchroniser la branche du manifeste avant la revue finale'
files=before['fichiers']+[r['fichier'] for r in read(VER/'nomenclature_etage_batterie.json')['occurrences']]
files+=['hardware/mecanique/README.md','hardware/mecanique/cartographe/README.md','docs/architecture/HLD.md','AGENTS.md']
if is_bms:
 files+=list(review['sources_natives_revalidees_sha256'])
 files+=['.agents/skills/drone-agricole-freecad/SKILL.md']
 files+=['docs/architecture/ARCHITECTURE_LOGICIELLE.md','hardware/mecanique/cartographe/configuration_cible_20261003.json']
 files+=['hardware/electronique/cartographe/'+s for s in ['cablage_global.json','cablage_global.mmd','contrat_uart_bms.json','faisceau_systeme_cible_20261003.json','verification/verify_cablage.ps1','verification/cablage_global_bms.json','verification/sync_doc_cablage_bms.py','verification/render_cablage_bms.mjs','verification/rendu_cablage_bms.json','verification/cablage_global_bms.png']]
files+=['hardware/mecanique/cartographe/sous_assemblages/'+s+'.FCStd' for s in ['SA02_Cassette20Ah_Coulissante','SA02_Contacts20Ah']]
files+=git('ls-files','--others','--exclude-standard','--','hardware/mecanique/cartographe/verification').splitlines()
files+=git('diff','--name-only','--','hardware/mecanique/cartographe/verification').splitlines()
files=[f for f in dict.fromkeys(files) if f and (ROOT/f).is_file() and f!='AGENTS.md' and not f.endswith('/suivi_git_etage_batterie_courant.json')]
files=[f for f in files if not (Path(f).suffix=='.FCStd' and (ROOT/f).stat().st_size>=1000000)]
assert all((ROOT/f).stat().st_size<1000000 for f in files if Path(f).suffix=='.FCStd'),'Un natif CAO volumineux ne doit pas être versionné'
assert not any(f.endswith('.history') or '/sources_fabricants/' in f or '/exports/' in f for f in files)
index=ROOT/'.git/index';unrelated='hardware/electronique/cartographe/carte_avionique/.history'
initial_index=sha(index);initial_unrelated=git('diff','--raw','--',unrelated);initial_branch=git('rev-parse','--abbrev-ref','HEAD')
fd,name=tempfile.mkstemp(prefix='etage-courant-index-',dir=ROOT);os.close(fd);Path(name).unlink();env=dict(os.environ,GIT_INDEX_FILE=name)
old=subprocess.run(['git','rev-parse','--verify','refs/heads/'+branch],cwd=ROOT,capture_output=True,text=True)
parent=old.stdout.strip() if old.returncode==0 else before['commit']
try:
 git('read-tree',parent,env=env);git('add','-f','--',*files,env=env)
 title='Compacter le raccord BMS–TE, aligner les contacts et ajuster la protection des cosses' if is_bms else ('Planifier le BMS de cassette et comparer les connecteurs blind-mate' if '--plan-bms' in sys.argv else 'Batterie directe TE et énergie à étage inférieur, conception CAO candidate')
 commit=git('commit-tree',git('write-tree',env=env),'-p',parent,'-m',title,env=env)
 git('update-ref','refs/heads/'+branch,commit,old.stdout.strip() if old.returncode==0 else '')
finally:Path(name).unlink(missing_ok=True)
assert sha(index)==initial_index and git('diff','--raw','--',unrelated)==initial_unrelated and git('rev-parse','--abbrev-ref','HEAD')==initial_branch
proof={'branche_courante':branch,'commit_courant':commit,'branche_avant':before['branche'],'commit_avant':before['commit'],'fichiers':files,'index_utilisateur_preserve':True,'branche_de_travail_preservee':True,'modification_electronique_preservee':True,'sources_lourdes_et_exports_exclus':True,'finalisation_correcte':True}
(VER/'suivi_git_etage_batterie_courant.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'branche':branch,'commit':commit,'fichiers':len(files),'index_utilisateur_preserve':True}))
