"""Infrastructure FreeCAD : repli des deux cordons fixes, fichiers et arbres conservés."""
from pathlib import Path
import hashlib
import json
import FreeCAD as App
import Part
from explore_compacite_dock20Ah import route

ROOT = Path(__file__).resolve().parents[4]
MEC = ROOT / 'hardware/mecanique/cartographe'
VER = MEC / 'verification'
DOCK = MEC / 'sous_assemblages/SA02A_Dock20Ah.FCStd'


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def rel(p):
    return str(Path(p).relative_to(ROOT)).replace('\\', '/')


def bbox(s):
    b = s.BoundBox
    return [b.XMin, b.YMin, b.ZMin, b.XMax, b.YMax, b.ZMax]


doc = App.openDocument(str(DOCK))
doc.recompute()
before_box = bbox(doc.Ensemble.Shape)
before = {Path(d.FileName): sha(Path(d.FileName)) for d in App.listDocuments().values() if d.FileName}
matrices = {o.Name: list(o.LinkPlacement.toMatrix().A) for o in doc.Objects if o.TypeId == 'App::Link'}
rows = []
changed = []
for plus in (True, False):
    name = 'EQ_CordonFixe8AWG_'+('Plus' if plus else 'Moins')+'20A'
    source = doc.getObject(name).LinkedObject.Document
    wire, section, expected, metrics = route(plus)
    source.Chemin.Shape = wire
    source.Section.Shape = section
    assert source.Cordon.TypeId == 'Part::Sweep'
    source.Cordon.Sections = [source.Section]
    source.Cordon.Spine = (source.Chemin, [])
    source.Reference.LongueurChemin_mm = str(wire.Length)
    source.Reference.Limite = ('Arcs tangents R50 pour diamètre étude5mm ; boucle inclinée et S. '
                              'Points de raccordement conservés, liberté flottante, retenue, vibration et thermique À valider. '
                              'Intersection préexistante du positif avec P49 non résolue ; ports JETI à mesurer, aucun usinage du module.')
    source.Chemin.Visibility = False
    source.Section.Visibility = False
    source.recompute()
    assert source.Cordon.Shape.isValid() and len(source.Cordon.Shape.Solids) == 1
    assert abs(source.Cordon.Shape.Volume-expected.Volume) < 1e-3
    assert source.Cordon.Shape.cut(expected).Volume < 1e-3
    source.save()
    path = Path(source.FileName)
    Part.export([source.Cordon], str(MEC/'exports/cassette20Ah_20261002'/(name+'.step')))
    changed.append(path)
    rows.append({'reference': name, 'fichier': rel(path), 'sha256_avant': before[path],
                 'sha256_apres': sha(path), 'arbre': ['Chemin', 'Section', 'Cordon'], 'mesures': metrics})
doc.recompute()
after_box = bbox(doc.Ensemble.Shape)
assert matrices == {o.Name: list(o.LinkPlacement.toMatrix().A) for o in doc.Objects if o.TypeId == 'App::Link'}
assert all(sha(p) == h for p, h in before.items() if p not in changed)
proof = {'date': '2026-10-04', 'besoin': ['MEC-ARC-001', 'MEC-BAT-001'],
         'controle': 'T-CARTO-DOCK-COMPACT-01', 'realisation_CAO': 'Implémenté', 'qualification': 'À valider',
         'version_FreeCAD': App.Version(), 'recette_sha256': sha(Path(__file__)),
         'exploration_sha256': sha(VER/'explore_compacite_dock20Ah.py'),
         'bbox_avant_mm': before_box, 'bbox_apres_mm': after_box, 'pieces': rows,
         'placements_preserves': True, 'autres_natifs_preserves': True, 'exports_STEP_regeneres': True,
         'finalisation_correcte': True, 'limite': 'Implémentation CAO seulement ; vérification indépendante en processus neuf requise.'}
(VER/'compacite_dock20Ah.json').write_text(json.dumps(proof, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
print(json.dumps({'bbox_avant': before_box, 'bbox_apres': after_box, 'finalisation_correcte': True}))
