"""Inventaire natif en lecture seule pour la migration énergie sous batterie."""
from pathlib import Path
import json
import FreeCAD as A
ROOT=Path(__file__).resolve().parents[4]
MEC=ROOT/'hardware/mecanique/cartographe'
def bb(s):
 b=s.BoundBox
 return [round(v,4) for v in (b.XMin,b.YMin,b.ZMin,b.XMax,b.YMax,b.ZMax)]
for folder,name in [('sous_assemblages','SA02A_Dock20Ah'),('sous_assemblages','SA02_Cassette20Ah_Coulissante'),('sous_assemblages','SA02_Contacts20Ah'),('sous_assemblages','SA07_Distribution_Systeme_Candidat'),('assemblages','Integration_Stack_Revue_20261003')]:
 d=A.openDocument(str(MEC/folder/(name+'.FCStd')));d.recompute()
 rows=[]
 for o in d.Objects:
  if o.TypeId=='App::Link':
   rows.append(dict(name=o.Name,target=o.LinkedObject.Document.Name+'.'+o.LinkedObject.Name,pos=list(o.LinkPlacement.Base),rot=list(o.LinkPlacement.Rotation.Q),bbox=bb(o.Shape)))
  elif o.TypeId=='App::Part':
   rows.append(dict(name=o.Name,group=[x.Name for x in o.Group],props={k:str(getattr(o,k)) for k in o.PropertiesList if k not in ['Group','Placement','Shape','ExpressionEngine','Visibility']},bbox=bb(o.Shape)))
 print(json.dumps(dict(document=name,objects=rows),ensure_ascii=False))
