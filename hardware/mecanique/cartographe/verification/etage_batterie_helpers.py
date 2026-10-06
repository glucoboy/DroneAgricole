"""Infrastructure FreeCAD : sauvegarde native avec apparences persistantes actuelles."""
from pathlib import Path
import struct, zipfile, xml.etree.ElementTree as ET
import FreeCAD as A
import FreeCADGui as G
G.showMainWindow(); G.getMainWindow().hide()
ROOT=Path(__file__).resolve().parents[4]; MEC=ROOT/'hardware/mecanique/cartographe'; VER=MEC/'verification'
def meta(o,k,v):
 if k not in o.PropertiesList:o.addProperty('App::PropertyString',k)
 setattr(o,k,str(v))

def require_legacy_layout(recipe):
 """Empêche une ancienne recette de rétablir silencieusement le dock sans BMS."""
 from garde_hierarchie_batterie import require_monolithic_layout
 require_monolithic_layout(recipe)
 p=MEC/'sous_assemblages/SA02A_Dock20Ah.FCStd'
 if p.exists():
  with zipfile.ZipFile(p) as z:
   if b'BMSIntegre' in z.read('Document.xml'):
    raise RuntimeError(recipe+' est historique sans BMS. Utiliser update_bms_cassette.py et le faisceau courant ; retour antérieur par Git.')
def packed(rgb):
 r,g,b=(round(float(v)*255) for v in rgb[:3]); return (r<<24)|(g<<16)|(b<<8)|255
def material_table(colors):
 return struct.pack('<I',len(colors))+b''.join(struct.pack('<IIIIffIII',0x555555FF,packed(c),0x888888FF,0x000000FF,.9,0,0,0,0) for c in colors)
def save_native(d,path=None):
 """Répare les seules tables de matériaux vides, sans ancien arbre ou géométrie."""
 d.recompute()
 colors={o.Name:[tuple(m.DiffuseColor) for m in o.ViewObject.ShapeAppearance] for o in d.Objects if hasattr(o.ViewObject,'ShapeAppearance')}
 p=Path(path or d.FileName)
 d.saveAs(str(p)) if path else d.save()
 with zipfile.ZipFile(p) as z:payload={n:z.read(n) for n in z.namelist()}
 gui=ET.fromstring(payload['GuiDocument.xml'])
 for vp in gui.iter('ViewProvider'):
  for prop in vp.iter('Property'):
   if prop.attrib.get('name')=='ShapeAppearance' and vp.attrib['name'] in colors:
    f=prop.find('MaterialList').attrib.get('file')
    if f:payload[f]=material_table(colors[vp.attrib['name']])
 tmp=p.with_suffix('.apparence.tmp')
 with zipfile.ZipFile(tmp,'w',compression=zipfile.ZIP_DEFLATED) as z:
  for n,data in payload.items():z.writestr(n,data)
 tmp.replace(p)
 return p
def color(o,rgb):
 if hasattr(o.ViewObject,'ShapeAppearance'):
  m=A.Material();m.DiffuseColor=tuple(rgb);o.ViewObject.ShapeAppearance=[m]
def shift_placement(o,property_name,delta):
 p=getattr(o,property_name);p.Base=p.Base+A.Vector(*delta);setattr(o,property_name,p)
def set_rotation(o,property_name,rotation):
 p=getattr(o,property_name);p.Rotation=rotation;setattr(o,property_name,p)
def load(folder,name,root='Reference'):
 p=MEC/folder/(name+'.FCStd')
 d=next((x for x in A.listDocuments().values() if x.FileName and Path(x.FileName)==p),None) or A.openDocument(str(p))
 return d.getObject(root)
def link(d,r,name,target,pos=(0,0,0),rot=None):
 o=d.addObject('App::Link',name);r.addObject(o);o.setLink(target);o.LinkTransform=False
 o.LinkPlacement=A.Placement(A.Vector(*pos),rot or A.Rotation());o.ViewObject.OverrideMaterial=False;o.Visibility=True
 return o
