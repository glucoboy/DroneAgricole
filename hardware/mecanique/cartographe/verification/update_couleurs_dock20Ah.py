"""Infrastructure FreeCAD : couleurs persistantes du dock, sans changer la géométrie.

Exécuter avec le Python fourni par FreeCAD ; --apply sauvegarde en place.
Le mode par défaut ne fait qu'inventorier les dépendances et leurs tailles.
"""
from pathlib import Path
import hashlib
import json
import os
import sys

ROOT = Path(__file__).resolve().parents[4]
MEC = ROOT / 'hardware/mecanique/cartographe'
VER = MEC / 'verification'
TARGET = MEC / 'sous_assemblages/SA02A_Dock20Ah.FCStd'
PALETTE = {
    'pack': (0.12, 0.36, 0.78),
    'rails': (0.12, 0.43, 0.48),
    'isolants': (0.78, 0.62, 0.33),
    'protections': (0.32, 0.35, 0.40),
    'retenue': (0.95, 0.48, 0.12),
    'cuivre': (0.78, 0.43, 0.20),
    'contacts': (0.76, 0.67, 0.36),
    'connecteurs': (0.96, 0.77, 0.08),
    'jeti': (0.52, 0.21, 0.47),
    'plus': (0.85, 0.08, 0.09),
    'moins': (0.10, 0.11, 0.14),
    'mousse': (0.18, 0.22, 0.24),
    'visserie': (0.67, 0.70, 0.74),
}


def category(name):
    n = name.lower()
    if 'batterie' in n:
        return 'pack'
    if 'plus' in n:
        return 'plus'
    if 'moins' in n:
        return 'moins'
    if 'rail' in n:
        return 'rails'
    if n.startswith(('vis', 'ecrou', 'rondelle', 'conn_vis', 'conn_ecrou',
                     'conn_rondelle', 'cass_vis', 'cass_ecrou', 'cass_rondelle')):
        return 'visserie'
    if 'mousse' in n or 'collier' in n:
        return 'mousse'
    if 'xt90' in n and not n.startswith(('vis', 'ecrou', 'porte')):
        return 'connecteurs'
    if 'fond' in n or 'capg10' in n or 'capture' in n:
        return 'isolants'
    if any(k in n for k in ('loquet', 'gache', 'poignee', 'butee')):
        return 'retenue'
    if any(k in n for k in ('conducteur0', 'conducteur1', 'entretoisecu', 'cosse', 'splice')):
        return 'cuivre'
    if any(k in n for k in ('broche', 'douille', 'contact39', 'contact40')):
        return 'contacts'
    if 'jeti' in n:
        return 'jeti'
    return 'protections'


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def rel(p):
    return str(Path(p).relative_to(ROOT)).replace('\\', '/')


apply = '--apply' in sys.argv
if apply:
    os.environ['QT_QPA_PLATFORM'] = 'offscreen'
import FreeCAD as App
if apply:
    import FreeCADGui as Gui
    Gui.showMainWindow()
    Gui.getMainWindow().hide()
doc = App.openDocument(str(TARGET))
doc.recompute()
files = sorted({Path(d.FileName) for d in App.listDocuments().values() if d.FileName})
dependencies = [{'fichier': rel(p), 'octets': p.stat().st_size, 'sha256': sha(p)} for p in files]
if not apply:
    out = {'fichiers': dependencies, 'total_octets': sum(r['octets'] for r in dependencies)}
    (VER / 'dependances_git_dock20Ah.json').write_text(json.dumps(out, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'fichiers': len(files), 'total_octets': out['total_octets'], 'max_octets': max(p.stat().st_size for p in files)}))
    raise SystemExit(0)

before = {p: sha(p) for p in files}
rows = []
source_categories = {}
for link in doc.Ensemble.Group:
    if link.TypeId != 'App::Link':
        continue
    kind = category(link.Name)
    vo = link.ViewObject
    mat = vo.ShapeMaterial
    mat.DiffuseColor = PALETTE[kind]
    vo.ShapeMaterial = mat
    # Les références App::Part contiennent des formes dont l'apparence doit
    # être colorée aussi. L'override du lien seul ne colore pas leur rendu.
    vo.OverrideMaterial = False
    source_categories[link.LinkedObject.Document.Name] = kind
    rows.append({'objet': link.Name, 'famille': kind, 'rgb': PALETTE[kind]})
assert len(rows) == 181
changed_sources = []
for name, kind in source_categories.items():
    source = App.getDocument(name)
    if source.Name.startswith('SA'):
        continue
    changed_objects = []
    for obj in source.Objects:
        if not hasattr(obj.ViewObject, 'ShapeAppearance') or not obj.TypeId.startswith(('Part::', 'PartDesign::')):
            continue
        # Matériau de présentation sans UUID de matériau physique : une
        # apparence catalogue héritée peut rétablir sa couleur au recalcul.
        materials = [App.Material()]
        for material in materials:
            material.DiffuseColor = PALETTE[kind]
        obj.ViewObject.ShapeAppearance = materials
        # N'afficher que les sorties natives, pas les outils/intermédiaires
        # superposés qui masquent les couleurs ou le résultat d'un balayage.
        obj.ViewObject.Visibility = not any(
            parent.Document == source and hasattr(parent, 'Shape') and
            parent.TypeId != 'App::Part' for parent in obj.InList)
        changed_objects.append(obj.Name)
    source.recompute()
    source.save()
    path = Path(source.FileName)
    changed_sources.append({'fichier': rel(path), 'sha256_avant': before[path],
                            'sha256_apres': sha(path), 'objets': changed_objects, 'famille': kind})
doc.recompute()
doc.save()
changed_paths = {ROOT/r['fichier'] for r in changed_sources} | {TARGET}
assert all(sha(p) == before[p] for p in files if p not in changed_paths)
proof = {'date': '2026-10-04', 'besoin': 'MEC-ARC-001', 'controle': 'T-CARTO-DOCK-COULEURS-01',
         'fichier': rel(TARGET), 'sha256_avant': before[TARGET], 'sha256_apres': sha(TARGET),
         'palette': PALETTE, 'occurrences': rows, 'references_colorees': changed_sources,
         'autres_dependances_preservees': True,
         'geometrie_modifiee': False, 'realisation_CAO': 'Implémenté', 'qualification_physique': 'À valider',
         'recette_sha256': sha(Path(__file__)), 'finalisation_correcte': True}
(VER / 'couleurs_dock20Ah.json').write_text(json.dumps(proof, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
print(json.dumps({'occurrences_colorees': len(rows), 'fichier': rel(TARGET), 'finalisation_correcte': True}))
