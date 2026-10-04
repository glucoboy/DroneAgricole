"""Infrastructure de vérification : relire les liens natifs, matrices et inventaire déclaré."""
from pathlib import Path
from collections import Counter
import hashlib,json
import FreeCAD as A
ROOT=Path(__file__).resolve().parents[4];MEC=ROOT/'hardware/mecanique/cartographe';V=MEC/'verification'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
m=json.loads((MEC/'manifest.json').read_text(encoding='utf-8'))
h=json.loads((V/'hierarchie_20Ah_20261002.json').read_text(encoding='utf-8'))
errors=[]
for r in h['fichiers']:
    p=MEC/r['fichier']
    if not p.exists() or sha(p)!=r['sha256']:errors.append('Empreinte hiérarchie périmée : '+r['fichier'])
A.openDocument(str(MEC/'assemblages/Systeme_Cartographie_20Ah.FCStd'))
docs={str(Path(d.FileName).relative_to(MEC)).replace('\\','/'):d for d in A.listDocuments().values()if d.FileName}
declared={(r['fichier_assemblage'],r['occurrence']):r for r in m['occurrences']}
for row in h['occurrences']:
    key=(row['assemblage'],row['nom']);r=declared.get(key)
    d=docs.get(key[0]);o=d.getObject(key[1])if d else None
    if not o or not r:errors.append('Lien manquant : '+str(key));continue
    target=o.LinkedObject
    file=str(Path(target.Document.FileName).relative_to(MEC)).replace('\\','/')
    if file!=r['source_fichier']or target.Name!=r['source_objet']:errors.append('Source de lien incohérente : '+str(key))
    if o.LinkTransform!=r['LinkTransform']or any(abs(a-b)>1e-8 for a,b in zip(o.LinkPlacement.toMatrix().A,r['placement_matrice'])):
        errors.append('Placement incohérent : '+str(key))
counts=Counter(r['source_fichier']for r in m['occurrences']if r['actif_drone']and r['source_fichier'].startswith('pieces/'))
for row in m['references']:
    file=row['fichier'].replace('\\','/')
    if file=='pieces/commerce/EQ_Chassis_X650.FCStd':continue
    if row.get('quantite_drone_actif',0)!=counts.get(file,0):errors.append('Quantité manifeste : '+row['reference'])
if len(declared)!=len(h['occurrences']):errors.append('Nombre de liens manifeste différent')
proof={'date':'2026-10-03','statut':'À valider','perimetre':'Liens, matrices, quantités et empreintes ; aucun essai physique',
    'liens_controles':len(declared),'erreurs':errors,
    'sources_sha256':{'manifest.json':sha(MEC/'manifest.json'),'hierarchie_20Ah_20261002.json':sha(V/'hierarchie_20Ah_20261002.json'),
    'verify_manifest_dock20Ah_20261003.py':sha(Path(__file__))}}
(V/'controle_manifest_dock20Ah_20261003.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'liens':len(declared),'erreurs':errors},ensure_ascii=True));raise SystemExit(bool(errors))
