"""Infrastructure : contrôler la fraîcheur et la finalisation des preuves numériques publiées."""
from pathlib import Path
import json,hashlib
ROOT=Path(__file__).resolve().parents[4];MEC=ROOT/'hardware/mecanique/cartographe';V=MEC/'verification'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf-8'))
errors=[];checks={}
i=read(V/'integration20Ah_20261002.json')
checks['integration_finalisee']=i['finalisation_correcte']and i['fichiers_inchanges']and i['absence_obstacle_hors_interfaces_TE_dans_modeles_representes']
checks['course_complete']=i['insertion_course_mm']==300 and i['poses_denses_1mm']==301 and i['dock']['occurrences_liees']==181
for f,h in i['fichiers_sha256'].items():
    if sha(ROOT/f)!=h:errors.append('Empreinte intégration périmée : '+f)
checks['script_integration_frais']=sha(V/'verify_integration20Ah_20261002.py')==i['script_sha256']
checks['preservation']=read(V/'preservation_dock20Ah_20261002.json')['tous_inchanges']
for f in ['review_bom_dock20Ah_20261003.json','controle_manifest_dock20Ah_20261003.json','controle_classeur_bom20Ah_20261003.json']:
    r=read(V/f);checks[f]=r['erreurs']==[]
    for file,h in r['sources_sha256'].items():
        p=MEC/file if file=='manifest.json' else ROOT/'outputs/dock20Ah_20261002'/file if file=='BOM_Dock20Ah.xlsx' else V/file
        if sha(p)!=h:errors.append('Preuve périmée : '+f+' / '+file)
checks['rehausse']=read(V/'reouverture_rehausse20_avionique_20261002.json')['erreurs_recalcul']==[]
b=read(V/'bom_dock20Ah_20261002.json')
missing_steps=[]
for r in b['pieces_fabriquees']:
    matches=list((MEC/'exports').rglob(r['reference']+'.step'))
    if not matches:missing_steps.append(r['reference'])
checks['STEP_fabrication']=not missing_steps
if missing_steps:errors.append('STEP manquants : '+','.join(missing_steps))
for name,ok in checks.items():
    if not ok:errors.append('Échec : '+name)
refs=['integration20Ah_20261002.json','bom_dock20Ah_20261002.json','faisceau_dock20Ah_20261002.json',
 'hierarchie_20Ah_20261002.json','review_bom_dock20Ah_20261003.json','controle_manifest_dock20Ah_20261003.json',
 'controle_classeur_bom20Ah_20261003.json','preservation_dock20Ah_20261002.json','rendu_dock20Ah_20261002.json']
proof={'date':'2026-10-03','realisation_CAO':'Implémenté','statut_physique':'À valider','controles':checks,
 'erreurs':errors,'sources_sha256':{f:sha(V/f)for f in refs},
 'limites':['Résultat de course limité aux volumes représentés et interfaces TE déclarées.',
 'Pales parquées parallèlesX obligatoires ; largeur et configuration réelles non mesurées.',
 'Verrou, engagement contacts, flexibilité, tenue, masse, courant et thermique non testés physiquement.',
 'Kit JETI8mm² et ports à mesurer, aucune instruction d’usinage du module.',
 'Compatibilité de vol non démontrée : masse partielle6,112–6,726kg, XT90 catalogue45A sous conditions.']}
(V/'finalisation_dock20Ah_20261003.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'controles':checks,'erreurs':errors},ensure_ascii=True));raise SystemExit(bool(errors))
