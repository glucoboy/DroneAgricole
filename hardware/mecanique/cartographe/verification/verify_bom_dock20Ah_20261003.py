"""Infrastructure de review indépendante : cohérence et fraîcheur des preuves BOM.
Ne charge ni ne modifie les modèles ; pas qualification mécanique ou électrique.
"""
from pathlib import Path
from collections import Counter
import hashlib,json
ROOT=Path(__file__).resolve().parents[4]
VER=ROOT/'hardware/mecanique/cartographe/verification'
def read(name):return json.loads((VER/name).read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
bom=read('bom_dock20Ah_20261002.json')
assembly=read('construction_dock20Ah_20261003.json')
wire=read('faisceau_dock20Ah_20261002.json')
failures=[]
def check(ok,description):
    if not ok:failures.append(description)
actual=Counter(x['reference']for x in assembly['occurrences'])
represented={x['reference']:x['quantite_installee']for x in bom['pieces_fabriquees']+bom['visserie_modelee']}
for ref,count in actual.items():
    if ref.startswith(('P','EQ_ISO','EQ_DIN','EQ_Vis')):
        check(represented.get(ref)==count,'Quantité incohérente : '+ref)
for row in bom['pieces_fabriquees']+bom['visserie_modelee']+bom['composants_commerce']:
    if row.get('sha256') and row.get('fichier'):
        path=ROOT/row['fichier'];check(path.exists()and sha(path)==row['sha256'],'Empreinte périmée : '+row['reference'])
    if row['reference']in ['P28_RailDroit20Ah','P29_RailGauche20Ah']:
        check(row.get('solides_geometriques')==1,'Pied arrière non solidaire du rail : '+row['reference'])
path=ROOT/bom['assemblage_inventorie']['fichier']
check(sha(path)==bom['assemblage_inventorie']['sha256'],'Assemblage BOM périmé')
check(sha(path)==assembly['fichier_sha256'],'Preuve de construction assemblage périmée')
check(bom['anomalies_generation']==[],'Anomalies de génération BOM')
check(actual.get('P32_CapG10Capture20Ah')==2,'Deux bandes de cap requises')
check(actual.get('P42_ConducteurCuCassette20Ah')==2,'Deux polarités Cu requises')
check(wire['positions_TE']['utilisees']==[39,40],'Positions de puissance incohérentes')
check(wire['terminaisons']['couple_max_TE_M5_Nm']==2.9,'Couple contactTE mal attribué')
check(wire['memoire_ON']['interverrouillage_OFF_materiel']is False,'Interverrouillage automatique inventé')
check(bom['alternative_etude']['active']is False,'Alternative AS150 comptée active')
check(not str(wire.get('segment_fixe_TE_JETI',{}).get('statut','')).startswith('À compléter'), 'Faisceau fixeTE→JETI incomplet')
proof={'schema_version':1,'date':'2026-10-03','statut':'À valider','validation':'Cohérence déclarative et empreintes, sans qualification physique',
 'sources_sha256':{p.name:sha(p)for p in [VER/'bom_dock20Ah_20261002.json',VER/'construction_dock20Ah_20261003.json',VER/'faisceau_dock20Ah_20261002.json',Path(__file__)]},
 'erreurs':failures,'occurrences_CAO':sum(actual.values()),'references_CAO':len(actual),
 'limites':['Ne démontre ni absence de collision ni tenue des fixations.', 'TE STEP cavités et géométrie contacts à contrôler physiquement.',
 'XT90 45A sous conditions catalogue ; thermique et courant mission non qualifiés.',
 'Budget masse partiel ; conformité6,3kg non démontrée.', 'Segment fixe du faisceau vérifié séparément selon sa preuve finale.']}
(VER/'review_bom_dock20Ah_20261003.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(proof,ensure_ascii=True))
raise SystemExit(1 if failures else 0)
