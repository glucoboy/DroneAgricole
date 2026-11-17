from etage_batterie_helpers import *
import Part,json
o=load('sous_assemblages','SA02A_Dock20Ah','Ensemble').Document.Conn_HousingSocket
rows=[]
for f in o.Shape.Faces:
 s=f.Surface
 if isinstance(s,Part.Cylinder) and abs(s.Axis.x)>.99:
  rows.append([round(s.Center.y,5),round(s.Center.z,5),round(s.Radius,5)])
print(json.dumps(sorted({tuple(p) for p in rows})))
