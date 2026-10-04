"""Contrôle en lecture seule du classeur exporté contre les valeurs de la BOM technique."""
from pathlib import Path
import json,hashlib
import openpyxl
ROOT=Path(__file__).resolve().parents[4];V=ROOT/'hardware/mecanique/cartographe/verification'
P=ROOT/'outputs/dock20Ah_20261002/BOM_Dock20Ah.xlsx'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
b=json.loads((V/'bom_dock20Ah_20261002.json').read_text(encoding='utf-8'))
book=openpyxl.load_workbook(P,read_only=True,data_only=False)
spec=lambda r:r.get('specification_native')or r.get('matiere_native')or''
expected={
 'Fabrication':[[r['quantite_installee'],r['reference'],spec(r),'À valider']for r in b['pieces_fabriquees']],
 'Achats':[[r['quantite_installee'],r['quantite_achat_unitaire'],r.get('fabricant',''),r.get('mpn',''),r.get('designation',''),'À valider',r.get('source','')]for r in b['composants_commerce']],
 'Visserie':[[r['quantite_installee'],r['reference'],spec(r),'À valider']for r in b['visserie_modelee']]}
errors=[]
if book.sheetnames!=list(expected):errors.append('Feuilles différentes de la définition')
for name,rows in expected.items():
    sheet=book[name]
    for i,row in enumerate(rows,6):
        actual=[sheet.cell(i,j).value for j in range(1,len(row)+1)]
        if [(v if v is not None else'')for v in actual]!=row:errors.append(name+' ligne '+str(i))
    for cells in sheet.iter_rows():
        for c in cells:
            if c.data_type=='e' or c.data_type=='f':errors.append('Erreur ou formule inattendue : '+name+'!'+c.coordinate)
    meaningful=sum(any(c.value is not None for c in cells)for cells in sheet.iter_rows(min_row=6))
    if meaningful!=len(rows):errors.append('Nombre de lignes renseignées : '+name)
book.close()
proof={'date':'2026-10-03','perimetre':'Relecture du fichier XLSX exporté ; valeurs, quantités et absence de cellules en erreur',
    'sources_sha256':{'bom_dock20Ah_20261002.json':sha(V/'bom_dock20Ah_20261002.json'),'BOM_Dock20Ah.xlsx':sha(P)},
    'lignes':{k:len(v)for k,v in expected.items()},'erreurs':errors,
    'limite':'Aucune ouverture dans MicrosoftExcel, ni qualification physique.'}
(V/'controle_classeur_bom20Ah_20261003.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(proof,ensure_ascii=True));raise SystemExit(bool(errors))
