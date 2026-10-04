"""Contrôle des empreintes, quantités et matériaux persistés de la CAO courante."""
from pathlib import Path
import hashlib,json,struct,zipfile,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[4];MEC=ROOT/'hardware/mecanique/cartographe';VER=MEC/'verification'
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
control=read(VER/'controle_etage_batterie.json')
assert control['finalisation_correcte'] and not control['erreurs_recalcul'] and not control['liens_non_resolus']
assert not control['intersections_brutes'] and not control['intersections_terminaisons_coffrets']
assert all(not s['intersections'] for s in control['extraction_echantillonnee'])
for file,digest in control['sources_sha256'].items():assert sha(ROOT/file)==digest,file
n=read(VER/'nomenclature_etage_batterie.json');counts={}
for row in n['occurrences']:
 assert sha(ROOT/row['fichier'])==row['sha256'],row['fichier']
 counts[row['reference']]=counts.get(row['reference'],0)+1
assert counts==n['quantites'] and sum(counts.values())==135
assert counts['EQ_Klauke742F5_Cosse90_TE']==2
assert all(counts.get(s,0)==1 for s in ['EQ_JetiMainSwitch100_PortsEtude20A','EQ_PM08_CAN_Enveloppe_Systeme_Candidat','EQ_Holybro_PDB18138_Systeme_Candidat','P57_PlateauEnergieInferieur'])
assert all(not counts.get(s,0) for s in ['P42_ConducteurCuCassette20Ah','P41_Support_Jeti_Dock20','EQ_AmassXT90HM_Dock20A','EQ_AmassXT90SF_Dock20A'])
b=read(VER/'bom_dock20Ah_20261002.json');f=read(VER/'faisceau_dock20Ah_20261002.json')
for category in ['pieces_fabriquees','visserie_modelee','composants_commerce']:
 for row in b[category]:
  if row.get('fichier'):
   path=ROOT/row['fichier'];assert sha(path)==row['sha256'],str(path)
   assert row['quantite_installee']==counts.get(path.stem,0),(row['reference'],row['quantite_installee'])
assert 'XT90_catalogue_A' not in f['limites_courant']
assert f['limites_courant']['courant_systeme_qualifie_A'] is None
assert f['charge_hors_drone']['statut']=='Planifié'
assert f['perimetre_geometrique']['pack_nominal_mm']==[193,76,58]
palette=read(VER/'finalisation_etage_batterie.json');colors=[]
for row in palette['references']:
 path=ROOT/row['fichier'];assert sha(path)==row['sha256'],str(path)
 with zipfile.ZipFile(path) as z:
  xml=ET.fromstring(z.read('Document.xml'));gui=ET.fromstring(z.read('GuiDocument.xml'))
  data=next(o for o in xml.find('ObjectData') if o.attrib['name']==row['final'])
  visible=next(p for p in data.iter('Property') if p.attrib['name']=='Visibility').find('Bool').attrib['value']
  assert visible=='true',row['fichier']
  provider=next(o for o in gui.iter('ViewProvider') if o.attrib['name']==row['final'])
  prop=next(p for p in provider.iter('Property') if p.attrib['name']=='ShapeAppearance')
  material=z.read(prop.find('MaterialList').attrib['file']);assert struct.unpack_from('<I',material)[0]>=1
  packed=struct.unpack_from('<I',material,8)[0];rgb=[((packed>>shift)&255)/255 for shift in [24,16,8]]
  assert all(abs(a-b)<1/255+1e-7 for a,b in zip(rgb,row['couleur'])),row['fichier']
  colors.append({'fichier':row['fichier'],'objet_final':row['final'],'diffuse_rgb_relu':rgb})
rendu=read(VER/'rendu_etage_batterie.json')
for row in rendu['images']:assert sha(ROOT/row['fichier'])==row['sha256']
m=read(MEC/'manifest.json')
assert m['configuration_dock20Ah']['evolution_courante']['noms_stables']
assert m['configuration_dock20Ah']['evolution_courante']['dimensions_batterie_et_energie_mm']==control['dimensions_batterie_et_energie_mm']
proof={'date':'2026-10-04','controle':'T-CARTO-ETAGE-REGISTRES-01','sources_geometriques_revalidees_par_empreinte':len(control['sources_sha256']),'occurrences':len(n['occurrences']),'quantites_concordantes':True,'couleurs_natives_relues':colors,'rendus_empreintes_concordantes':True,'pack_controle_mm':[193,76,58],'enveloppe_et_lot':'À valider','qualification_physique':'À valider','finalisation_correcte':True}
(VER/'controle_registres_etage_batterie.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'occurrences':len(n['occurrences']),'references_colorees':len(colors),'finalisation_correcte':True}))
