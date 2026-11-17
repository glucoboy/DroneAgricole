from etage_batterie_helpers import *
import json
d=load('sous_assemblages','SA02A_Dock20Ah','Ensemble').Document
rows=[]
for o in d.Objects:
 if o.TypeId=='App::Link' and any(k in o.Name for k in ['Conn_','Cosse','Cordon','P43','P44','Protection','Equilibrage','Cass_Batterie']):
  b=o.Shape.BoundBox
  rows.append(dict(name=o.Name,source=o.LinkedObject.Document.Name,pose=list(o.LinkPlacement.Base),bbox=[b.XMin,b.YMin,b.ZMin,b.XMax,b.YMax,b.ZMax],mobile=getattr(o,'Mobile',None)))
(VER/'inspection_implantation_bms.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
print(json.dumps(rows))
