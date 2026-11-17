"""Inspection native sans mutation pour le réaménagement vertical du BMS."""
from etage_batterie_helpers import *
import json
top=load('assemblages','Integration_Stack_Revue_20261003','IntegrationRevue').Document
rows=[]
for d in list(A.listDocuments().values()):
 if Path(d.FileName).stem not in ['SA02A_Dock20Ah','SA01_Chassis_Stack_Revue_20261003','SA03_CA01_Holybro_Revue_20261003']:continue
 for o in d.Objects:
  if o.TypeId!='App::Link':continue
  b=o.Shape.BoundBox
  rows.append(dict(doc=d.Name,name=o.Name,source=Path(o.LinkedObject.Document.FileName).stem,pose=list(o.LinkPlacement.Base),bbox=[b.XMin,b.YMin,b.ZMin,b.XMax,b.YMax,b.ZMax],mobile=getattr(o,'Mobile',None)))
(VER/'inspection_bms_dessus.json').write_text(json.dumps(rows,indent=2)+'\n',encoding='utf-8')
print(json.dumps([r for r in rows if not r['source'].startswith(('EQ_Chassis','EQ_ISO','EQ_DIN'))],ensure_ascii=True))
