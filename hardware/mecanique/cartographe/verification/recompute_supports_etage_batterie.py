"""Recalcul forcé headless des supports fabriqués, GUI courante préservée."""
from pathlib import Path
import zipfile,xml.etree.ElementTree as ET,json
import FreeCAD as A
from etage_batterie_helpers import require_legacy_layout
require_legacy_layout('recompute_supports_etage_batterie.py')
ROOT=Path(__file__).resolve().parents[4];MEC=ROOT/'hardware/mecanique/cartographe';rows=[]
for name in ['P39_SupportFixeContacts20Ah','P40_SupportMobileContacts20Ah']:
 p=MEC/'pieces/fabriquees'/(name+'.FCStd')
 with zipfile.ZipFile(p) as z:old={n:z.read(n) for n in z.namelist()}
 d=A.openDocument(str(p))
 for o in d.Objects:
  if o.TypeId not in ['Part::Box','Part::Cylinder','Part::Cone','Part::Feature']:continue
  if o.Name.startswith(('TrouPiedM3','FraisureM3')):x=-117.5
  elif o.Name.startswith('TrouFondM3'):x=-104
  elif o.TypeId=='Part::Feature':x=-82
  elif name.startswith('P39'):x=-242 if o.Name.startswith(('Bride','Pied','Montant')) else -243
  else:x=-212.65 if o.Name.startswith(('Bride','Bras','Montant')) else -213.65
  if o.TypeId=='Part::Box':o.setExpression('Placement.Base.x',None)
  placement=o.Placement;o.Placement=A.Placement(A.Vector(x,placement.Base.y,placement.Base.z),placement.Rotation)
 for o in d.Objects:o.touch()
 d.recompute()
 assert d.Resultat.Shape.isValid() and not any('Invalid' in o.State for o in d.Objects),name
 rows.append(dict(reference=name,bbox=str(d.Resultat.Shape.BoundBox),volume=d.Resultat.Shape.Volume))
 d.save();A.closeDocument(d.Name)
 with zipfile.ZipFile(p) as z:payload={n:z.read(n) for n in z.namelist()}
 gui=ET.fromstring(old['GuiDocument.xml']);payload['GuiDocument.xml']=old['GuiDocument.xml']
 for el in gui.iter():
  f=el.attrib.get('file')
  if f and f in old:payload[f]=old[f]
 tmp=p.with_suffix('.recalcul.tmp')
 with zipfile.ZipFile(tmp,'w',compression=zipfile.ZIP_DEFLATED) as z:
  for n,data in payload.items():z.writestr(n,data)
 tmp.replace(p)
(MEC/'verification/recalcul_supports_etage_batterie.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(rows))
