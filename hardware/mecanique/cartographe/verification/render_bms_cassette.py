"""Vues natives courantes ; vue ouverte cache seulement P44 sans sauver la CAO."""
from garde_hierarchie_batterie import require_monolithic_layout
require_monolithic_layout('render_bms_cassette.py')
from etage_batterie_helpers import *
from PySide import QtCore
import json,hashlib
top=load('assemblages','Integration_Stack_Revue_20261003','IntegrationRevue').Document
dock=load('sous_assemblages','SA02A_Dock20Ah','Ensemble').Document
dist=load('sous_assemblages','SA07_Distribution_Systeme_Candidat').Document
chassis=load('sous_assemblages','SA01_Chassis_Stack_Revue_20261003','Ensemble').Document
sources={str(Path(doc.FileName).relative_to(ROOT)).replace('\\','/'):hashlib.sha256(Path(doc.FileName).read_bytes()).hexdigest() for doc in A.listDocuments().values() if doc.FileName}
for doc in A.listDocuments().values():
 for obj in doc.Objects:obj.touch()
for _ in range(2):
 for doc in A.listDocuments().values():doc.recompute()
d=A.newDocument('VueBMSCassette');r=d.addObject('App::Part','Ensemble')
tmp=VER/'.vue_bms.FCStd';d.saveAs(str(tmp))
link(d,r,'Dock',dock.Ensemble);link(d,r,'Etage',dist.Reference)
plateau=chassis.Part__Feature311
o=link(d,r,'PlateauRehausse',plateau.LinkedObject);o.LinkPlacement=plateau.LinkPlacement
plateau.LinkedObject.ViewObject.Transparency=80
for src in chassis.Objects:
 if src.Name.startswith('Colonne70_'):
  o=link(d,r,src.Name,src.LinkedObject);o.LinkPlacement=src.LinkPlacement
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
sources_inchangees=all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in sources.items())
assert sources_inchangees,'Une source CAO a changé pendant le rendu'
(VER/'rendu_bms_cassette.json').write_text(json.dumps(dict(date='2026-10-05',moteur='FreeCADGui/Coin3D',images=rows,sources_sha256=sources,sources_non_modifiees=sources_inchangees,finalisation_correcte=True),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
A.closeDocument(d.Name);tmp.unlink(missing_ok=True)
print('Deux vues natives actuelles produites')
