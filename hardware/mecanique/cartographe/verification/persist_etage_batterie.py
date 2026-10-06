"""Infrastructure : synchroniser visibilité App/GUI et matériaux sans toucher aux BRep."""
from garde_hierarchie_batterie import require_monolithic_layout
require_monolithic_layout('persist_etage_batterie.py')
from pathlib import Path
import hashlib,json,struct,zipfile,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[4];VER=Path(__file__).resolve().parent
def table(rgb):
 r,g,b=(round(v*255) for v in rgb);return struct.pack('<IIIIIffIII',1,0x555555FF,(r<<24)|(g<<16)|(b<<8)|255,0x888888FF,0x000000FF,.9,0,0,0,0)
def persist():
 old=json.loads((VER/'couleurs_dock20Ah.json').read_text(encoding='utf-8'));families={row['fichier']:old['palette'][row['famille']] for row in old['references_colorees']}
 families.update({'hardware/mecanique/cartographe/pieces/commerce/EQ_Klauke742F5_Cosse90_TE.FCStd':[.76,.67,.36],'hardware/mecanique/cartographe/pieces/fabriquees/P57_PlateauEnergieInferieur.FCStd':[.12,.43,.48],'hardware/mecanique/cartographe/pieces/commerce/EQ_PM08_CAN_Enveloppe_Systeme_Candidat.FCStd':[.18,.47,.51],'hardware/mecanique/cartographe/pieces/commerce/EQ_Holybro_PDB18138_Systeme_Candidat.FCStd':[.28,.58,.25]})
 rows=[]
 for filename,rgb in families.items():
  p=ROOT/filename
  with zipfile.ZipFile(p) as z:payload={n:z.read(n) for n in z.namelist()}
  xml=ET.fromstring(payload['Document.xml']);types={o.attrib['name']:o.attrib['type'] for o in xml.find('Objects') if 'type' in o.attrib};data={o.attrib['name']:o for o in xml.find('ObjectData')}
  root=data.get('Reference');final=None
  if root is not None:
   prop=next((pr for pr in root.iter('Property') if pr.attrib.get('name')=='ObjetFinal'),None)
   if prop is not None and prop.find('String') is not None:final=prop.find('String').attrib['value']
  if not final:final=next((n for n in ['Resultat','Cordon','FabricantSTEP'] if n in data),None)
  if not final:continue
  hidden={name for name,t in types.items() if t.startswith(('Part::','PartDesign::')) or t=='App::Link'}
  for name in hidden:
   for prop in data[name].iter('Property'):
    if prop.attrib.get('name')=='Visibility' and prop.find('Bool') is not None:prop.find('Bool').set('value','true' if name==final else 'false')
  gui=ET.fromstring(payload['GuiDocument.xml']);colored=[]
  for vp in gui.iter('ViewProvider'):
   name=vp.attrib['name']
   for prop in vp.iter('Property'):
    if prop.attrib.get('name')=='Visibility' and name in hidden and prop.find('Bool') is not None:prop.find('Bool').set('value','true' if name==final else 'false')
    if prop.attrib.get('name')=='ShapeAppearance' and types.get(name,'').startswith(('Part::','PartDesign::')):
     f=prop.find('MaterialList').attrib.get('file')
     if f:payload[f]=table(rgb);colored.append(name)
  payload['Document.xml']=ET.tostring(xml,encoding='utf-8',xml_declaration=True);payload['GuiDocument.xml']=ET.tostring(gui,encoding='utf-8',xml_declaration=True)
  tmp=p.with_suffix('.persist.tmp')
  with zipfile.ZipFile(tmp,'w',compression=zipfile.ZIP_DEFLATED) as z:
   for n,data0 in payload.items():z.writestr(n,data0)
  tmp.replace(p);rows.append(dict(fichier=filename,final=final,couleur=rgb,objets_colores=colored,sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
 (VER/'finalisation_etage_batterie.json').write_text(json.dumps(dict(references=rows,BRep_preserves=True,finalisation_correcte=True),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
if __name__=='__main__':persist()
