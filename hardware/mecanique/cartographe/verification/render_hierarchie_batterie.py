"""Vues de la batterie, de son récepteur et du principal, sans sauvegarde native."""
from hierarchie_batterie_helpers import *
from etage_batterie_helpers import G
from PySide import QtCore

top = A.openDocument(str(TOP))
for doc in (top.SA02_Cassette20Ah_Coulissante.LinkedObject.Document,
            top.SA02A_Dock20Ah.LinkedObject.Document,top):
    doc.recompute()
check_tree(top)
sources = native_sources()
images = []
for name,doc in [('batterie_sous_assemblage',top.SA02_Cassette20Ah_Coulissante.LinkedObject.Document),
                 ('recepteur_batterie_sous_assemblage',top.SA02A_Dock20Ah.LinkedObject.Document),
                 ('integration_hierarchie_batterie',top)]:
    A.setActiveDocument(doc.Name); G.setActiveDocument(doc.Name)
    view = G.activeDocument().activeView()
    if view is None:
        G.activeDocument().createView('Gui::View3DInventor')
        view = G.activeDocument().activeView()
    view.viewAxonometric(); view.fitAll(); G.updateGui()
    loop = QtCore.QEventLoop(); QtCore.QTimer.singleShot(500,loop.quit); loop.exec()
    view.redraw()
    path = VER/(name+'.png')
    view.saveImage(str(path),1800,1100,'White')
    images.append(dict(fichier=rel(path),sha256=sha(path),vue=name))
assert native_sources() == sources
dump(VER/'rendu_hierarchie_batterie.json',dict(date='2026-10-05',moteur='FreeCADGui/Coin3D',
     images=images,sources_sha256=sources,sources_non_modifiees=True,finalisation_correcte=True))
print('Trois vues natives de la hiérarchie actuelle produites',flush=True)
