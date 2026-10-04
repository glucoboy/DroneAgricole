"""Captures natives FreeCADGui après chargement des couleurs persistantes."""
from pathlib import Path
import json
import hashlib
import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

ROOT = Path(__file__).resolve().parents[4]
MEC = ROOT / 'hardware/mecanique/cartographe'
VER = MEC / 'verification'
Gui.showMainWindow()
Gui.getMainWindow().hide()
doc = App.openDocument(str(MEC/'sous_assemblages/SA02A_Dock20Ah.FCStd'))
doc.recompute()
color_proof = json.loads((VER/'couleurs_dock20Ah.json').read_text(encoding='utf-8'))
for row in color_proof['references_colorees']:
    source = next(d for d in App.listDocuments().values() if Path(d.FileName) == ROOT/row['fichier'])
    expected = color_proof['palette'][row['famille']]
    for name in row['objets']:
        actual = source.getObject(name).ViewObject.ShapeAppearance[0].DiffuseColor
        assert all(abs(actual[i]-expected[i]) < 1/255 for i in range(3)), (source.Name, name, actual, expected)
App.setActiveDocument(doc.Name)
view = Gui.getDocument(doc.Name).activeView()
rows = []
for direction in ['isometrique', 'profil']:
    if direction == 'isometrique':
        view.viewAxonometric()
    else:
        view.viewFront()
    view.fitAll()
    Gui.updateGui()
    loop = QtCore.QEventLoop()
    QtCore.QTimer.singleShot(1000, loop.quit)
    loop.exec()
    view.redraw()
    path = VER/('dock20Ah_compact_'+direction+'.png')
    view.saveImage(str(path), 1800, 1100, 'White')
    rows.append({'fichier': str(path.relative_to(ROOT)).replace('\\', '/'),
                 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'vue': direction})
(VER/'rendu_dock20Ah_courant.json').write_text(json.dumps({
    'date': '2026-10-04', 'moteur': 'FreeCADGui/Coin3D', 'version': App.Version(),
    'images': rows, 'references_couleurs_verifiees': len(color_proof['references_colorees']),
    'couleurs': 'Matériaux ShapeAppearance persistants des références ; aucune couleur ajoutée au rendu',
    'sources_non_sauvegardees_par_rendu': True, 'finalisation_correcte': True,
}, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
print(json.dumps({'images': len(rows), 'finalisation_correcte': True}))
