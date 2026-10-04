"""Synchronisation du manifeste avec la hiérarchie CAO effectivement reconstruite."""
from pathlib import Path
from collections import Counter
import json, hashlib

ROOT=Path(__file__).resolve().parents[4];MEC=ROOT/'hardware/mecanique/cartographe'
P=MEC/'manifest.json';V=MEC/'verification'
def norm(s):return s.replace('\\','/')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
h=json.loads((V/'hierarchie_20Ah_20261002.json').read_text(encoding='utf-8'))
d=json.loads(P.read_text(encoding='utf-8'))
rows=h['occurrences']
assert not h['erreurs'],h['erreurs']
roots={'assemblages/Drone_Cartographe_20Ah.FCStd'}
reachable=set(roots)
while True:
    added={r['source_fichier'] for r in rows if r['assemblage'] in reachable}-reachable
    if not added:break
    reachable.update(added)
counts=Counter(r['source_fichier'] for r in rows if r['assemblage'] in reachable
               and r['assemblage'].startswith(('assemblages/','sous_assemblages/'))
               and r['source_fichier'].startswith('pieces/'))
byfile={norm(r['fichier']):r for r in d['references']}
for r in d['references']:
    f=norm(r['fichier']);r['quantite_drone_actif']=counts.get(f,0)
    if f=='pieces/commerce/EQ_Chassis_X650.FCStd':r['quantite_drone_actif']=1
for row in rows:
    f=row['source_fichier']
    if not f.startswith('pieces/') or f in byfile:continue
    ref={'reference':Path(f).stem,'fichier':f,'source_objet':row['source_objet'],
        'type':'Référence native liée','statut':'À valider','realisation_CAO':'Implémenté',
        'quantite_drone_actif':counts.get(f,0),'configuration':'dock20Ah'}
    d['references'].append(ref);byfile[f]=ref
if 'historique_occurrences_avant_dock20Ah' not in d:
    d['historique_occurrences_avant_dock20Ah']=d['occurrences']
d['occurrences']=[{'assemblage':Path(r['assemblage']).stem,'fichier_assemblage':r['assemblage'],
    'occurrence':r['nom'],'reference':byfile[r['source_fichier']]['reference']
        if r['source_fichier'] in byfile else Path(r['source_fichier']).stem,
    'source_fichier':r['source_fichier'],'source_objet':r['source_objet'],
    'placement_matrice':r['matrice_placement'],'LinkTransform':r['LinkTransform'],
    'actif_drone':r['assemblage'] in reachable and r['assemblage'].startswith(('assemblages/','sous_assemblages/')),
    'usage_construction_reference':r['assemblage'].startswith('pieces/')} for r in rows]
seen={norm(a['fichier']) for a in d['assemblages']}
newassemblages={r['assemblage'] for r in rows if r['assemblage'].startswith(('sous_assemblages/','assemblages/'))}
for f in sorted(newassemblages):
    if f not in seen:d['assemblages'].append({'nom':Path(f).stem,'fichier':f,'statut':'À valider',
        'realisation_CAO':'Implémenté','actif_drone':f in reachable})
for a in d['assemblages']:
    a['actif_drone']=norm(a['fichier']) in reachable
    if Path(norm(a['fichier'])).stem in ['SA01_Chassis','SA02_Energie_EchangeRapide',
            'SA02A_Connecteur_SBSX75A','SA03_Avionique','Drone_Cartographe','Systeme_Cartographie']:
        a['archive_conception']=True
e=d['configuration_energie']
if 'historique_avant_20Ah' not in e:
    e['historique_avant_20Ah']={k:v for k,v in e.items() if k!='historique_avant_20Ah'}
e.update({'active':'SA02A_Dock20Ah','capacite_ah':20,'series':6,
    'batterie_MPN':'TAA200006S5X9S','rehausse_plateau_mm':20,'qualification':'À valider',
    'connecteur':{'sous_assemblage':'SA02A_Dock20Ah','logements':['1648151-1','1648156-1'],
        'contacts':['1766283-1','6648335-1'],'module_coupure':'J-MSW-100-MS',
        'bornes':'39:+ ;40:−','qualification':'À valider'},
    'BOM':'verification/bom_dock20Ah_20261002.json',
    'faisceau':'verification/faisceau_dock20Ah_20261002.json',
    'verification':'verification/integration20Ah_20261002.json',
    'echange':'Au sol, moteurs arrêtés, pales parallèlesX, JETIOFF avant déverrouillage',
    'limites':['Pas de qualification physique ni de tenue de vol.',
        'Cavités STEPTE simplifiées ; géométrie fonctionnelle interne à confirmer.',
        'Masse totale à mesurer ; enveloppe X6506,3kg non démontrée.',
        'XT90 du pack conservé : aucun calibre système85/100A affirmé.']})
if 'variante_berceau_fixe' in e:
    e['variante_berceau_fixe']['choix_capacite']='Archive ; sélection20Ah dans cassette coulissante distincte'
    e['variante_berceau_fixe']['documentation']='../../../docs/architecture/ARCHITECTURE_MECANIQUE.md#411-archive-de-préétude--berceau-fixe-et-capot-2-octobre-2026'
d['configuration_avionique'].setdefault('archive_avant_rehausse',d['configuration_avionique'].get('active'))
d['configuration_avionique']['active']='SA03_Avionique_Rehausse20'
d['configuration_avionique']['limite_dock20Ah']='Pixhawk historique rehaussé surP27 ; nouvelle porteuse Holybro/CA01 non intégrée par ce changement.'
d['date_mise_a_jour']='2026-10-03'
d['configuration_dock20Ah']={'assemblage':'assemblages/Drone_Cartographe_20Ah.FCStd',
    'systeme':'assemblages/Systeme_Cartographie_20Ah.FCStd','statut':'À valider',
    'realisation_CAO':'Implémenté','hierarchie':'verification/hierarchie_20Ah_20261002.json',
    'source_hierarchie_sha256':sha(V/'hierarchie_20Ah_20261002.json'),
    'comptage':'Occurrences effectivement liées des pièces ; OEMX650 compté comme unkit, pas autant de kits que de feuilles STEP.'}
P.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'references':len(d['references']),'occurrences':len(d['occurrences']),
    'documents_actifs_drone':len(reachable),'manifest_sha256':sha(P)},ensure_ascii=False))
