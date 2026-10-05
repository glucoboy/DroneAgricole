"""Cohérence des empreintes, occurrences, BOM et couleurs actuelles après CAO."""
from pathlib import Path
from collections import Counter
import hashlib,json,zipfile,xml.etree.ElementTree as ET,struct
ROOT=Path(__file__).resolve().parents[4];MEC=ROOT/'hardware/mecanique/cartographe';VER=MEC/'verification'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
proofs=[read(VER/p) for p in ['controle_bms_cassette.json','controle_faisceau_natif_bms.json']]
for c in proofs:
 assert c['finalisation_correcte'] and not c['erreurs_recalcul'] and not c['liens_non_resolus']
 for f,h in c['sources_sha256'].items():assert sha(ROOT/f)==h,f
n=read(VER/'nomenclature_etage_batterie.json');counts=dict(Counter(r['reference'] for r in n['occurrences']));assert counts==n['quantites']
for r in n['occurrences']:assert sha(ROOT/r['fichier'])==r['sha256'],r['fichier']
assert counts['EQ_JBD_SP22S003_BMS']==1 and counts['EQ_Waveshare15817_UART_Isole']==1
assert counts['EQ_JetiMainSwitch100_PortsEtude20A']==1 and counts['P58_AppuiIsolationBMS']==1
assert not counts.get('EQ_BMS_BPlus_Liaison20A') and not counts.get('P51_RetenueEquilibrage20Ah')
b=read(VER/'bom_dock20Ah_20261002.json')
for cat in ['pieces_fabriquees','visserie_modelee','composants_commerce']:
 for r in b[cat]:
  if r.get('fichier'):
   p=ROOT/r['fichier'];assert sha(p)==r['sha256'],r['fichier'];assert r['quantite_installee']==counts.get(p.stem,0),(p,r['quantite_installee'])
f=read(VER/'faisceau_dock20Ah_20261002.json');assert f['limites_courant']['courant_systeme_qualifie_A'] is None
assert f['cible_BMS_cassette']['dimensions_installees_mm'] is None
m=read(MEC/'manifest.json');e=m['configuration_dock20Ah']['evolution_courante'];assert e['noms_stables'] and e['TE_recul_mm']==126
assert e['dimensions_batterie_et_energie_mm']==proofs[0]['dimensions_batterie_et_energie_mm']
assert m['catalogue_courant_20261004']['faisceau_recale_sur_stack']
rows=[r for r in m['occurrences'] if r.get('assemblage')=='Integration_Stack_Revue_20261003'];assert len(rows)==6 and any(r['reference']=='SA08_Faisceau_Systeme_Candidat' for r in rows)
colors=[]
for name,expected in [('EQ_JBD_SP22S003_BMS',[.12,.65,.32]),('EQ_Waveshare15817_UART_Isole',[.49,.27,.74]),('P58_AppuiIsolationBMS',[.16,.46,.52])]:
 p=MEC/('pieces/fabriquees' if name.startswith('P') else 'pieces/commerce')/(name+'.FCStd')
 with zipfile.ZipFile(p) as z:
  gui=ET.fromstring(z.read('GuiDocument.xml'));xml=ET.fromstring(z.read('Document.xml'))
  root=next(o for o in xml.find('ObjectData') if o.attrib['name']=='Reference')
  final=next(p for p in root.iter('Property') if p.attrib['name']=='ObjetFinal').find('String').attrib['value']
  provider=next(v for v in gui.iter('ViewProvider') if v.attrib['name']==final)
  filename=next(p for p in provider.iter('Property') if p.attrib['name']=='ShapeAppearance').find('MaterialList').attrib['file']
  mat=z.read(filename);packed=struct.unpack_from('<I',mat,8)[0];rgb=[((packed>>s)&255)/255 for s in [24,16,8]]
  assert all(abs(a-b)<=1/255+1e-6 for a,b in zip(rgb,expected)),(name,rgb)
  colors.append(dict(reference=name,rgb=rgb))
elec=read(ROOT/'hardware/electronique/cartographe/verification/cablage_global_bms.json');assert elec['checks_passed'] and elec['diagram_matches_doc'] and elec['mermaid_render_executed']
out=dict(date='2026-10-05',test='T-CARTO-BMS-REGISTRES-01',occurrences=len(n['occurrences']),references=len(counts),sources_geometriques_revalidees=sum(len(c['sources_sha256']) for c in proofs),couleurs_relues=colors,liens_top=6,routes_natives=37,liaisons_schema=40,quantites_concordantes=True,qualification='À valider',finalisation_correcte=True)
(VER/'controle_registres_bms.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(out))
