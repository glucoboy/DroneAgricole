"""Vues natives courantes ; vue ouverte cache seulement P44 sans sauver la CAO."""
from etage_batterie_helpers import *
from PySide import QtCore
import json,hashlib
top=load('assemblages','Integration_Stack_Revue_20261003','IntegrationRevue').Document
dock=load('sous_assemblages','SA02A_Dock20Ah','Ensemble').Document
dist=load('sous_assemblages','SA07_Distribution_Systeme_Candidat').Document
d=A.newDocument('VueBMSCassette');r=d.addObject('App::Part','Ensemble')
tmp=VER/'.vue_bms.FCStd';d.saveAs(str(tmp))
link(d,r,'Dock',dock.Ensemble);link(d,r,'Etage',dist.Reference)
dock.P44_CouvercleArriereConducteurs20Ah.Visibility=False
# Isolerla visualisation, sourcesgéométriques restentidentiques surdisque.
for n in ['P43_ProtectionConducteurs20Ah']:
 o=dock.getObject(n);src=o.LinkedObject;src.Document.getObject(src.ObjetFinal).ViewObject.Transparency=80
rows=[]
for scene,doc in [('bms_cassette_ouverte',d),('integration_bms_faisceau',top)]:
 A.setActiveDocument(doc.Name);doc.recompute();v=G.activeDocument().activeView();v.viewAxonometric();v.fitAll();G.updateGui()
 loop=QtCore.QEventLoop();QtCore.QTimer.singleShot(500,loop.quit);loop.exec();v.redraw()
 p=VER/(scene+'.png');v.saveImage(str(p),1800,1100,'White')
 rows.append(dict(fichier=str(p.relative_to(ROOT)).replace('\\','/'),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),vue='ouverte avec capotmasqué' if doc==d else 'assemblagelocalcourant'))
(VER/'rendu_bms_cassette.json').write_text(json.dumps(dict(date='2026-10-05',moteur='FreeCADGui/Coin3D',images=rows,sources_non_modifiees=True,finalisation_correcte=True),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
A.closeDocument(d.Name);tmp.unlink(missing_ok=True)
print('Deux vues natives actuelles produites')
