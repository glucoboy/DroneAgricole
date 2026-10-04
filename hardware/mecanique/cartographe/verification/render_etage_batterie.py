"""Rendus natifs de la batterie et de l'étage énergie, sans mutation des sources."""
from etage_batterie_helpers import *
import hashlib,json
from PySide import QtCore
d=A.newDocument('VueBatterieEtage'); r=d.addObject('App::Part','Ensemble')
temporary=VER/'.vue_etage_batterie.FCStd';d.saveAs(str(temporary))
for name,root in [('SA02A_Dock20Ah','Ensemble'),('SA07_Distribution_Systeme_Candidat','Reference')]:
 link(d,r,name,load('sous_assemblages',name,root))
d.recompute(); A.setActiveDocument(d.Name);v=G.activeDocument().activeView()
rows=[]
for direction in ['isometrique','profil']:
 v.viewAxonometric() if direction=='isometrique' else v.viewFront()
 v.fitAll();G.updateGui();loop=QtCore.QEventLoop();QtCore.QTimer.singleShot(1000,loop.quit);loop.exec();v.redraw()
 p=VER/('etage_batterie_'+direction+'.png');v.saveImage(str(p),1800,1100,'White')
 rows.append(dict(fichier=str(p.relative_to(ROOT)).replace('\\','/'),sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
(VER/'rendu_etage_batterie.json').write_text(json.dumps(dict(images=rows,moteur='FreeCADGui/Coin3D',sources_non_modifiees=True,finalisation_correcte=True),indent=2)+'\n',encoding='utf-8')
print('Rendus natifs enregistrés')
A.closeDocument(d.Name);temporary.unlink(missing_ok=True)
