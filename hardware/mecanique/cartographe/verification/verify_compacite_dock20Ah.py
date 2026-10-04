"""Vérification indépendante des natifs sauvegardés, sans modification de CAO."""
from pathlib import Path
import hashlib
import io
import json
import subprocess
import zipfile
import FreeCAD as App
from explore_compacite_dock20Ah import route

ROOT = Path(__file__).resolve().parents[4]
MEC = ROOT/'hardware/mecanique/cartographe'
VER = MEC/'verification'
snapshot = json.loads((VER/'suivi_git_dock20Ah.json').read_text(encoding='utf-8'))
colors = json.loads((VER/'couleurs_dock20Ah.json').read_text(encoding='utf-8'))
doc = App.openDocument(str(MEC/'sous_assemblages/SA02A_Dock20Ah.FCStd'))
integration = App.openDocument(str(MEC/'assemblages/Integration_Stack_Revue_20261003.FCStd'))
for d in App.listDocuments().values():
    d.recompute()
errors = [d.Name+'/'+o.Name for d in App.listDocuments().values() for o in d.Objects if 'Invalid' in o.State]
links = [o for o in doc.Objects if o.TypeId == 'App::Link']
assert len(links) == 181 and not errors
assert all(o.LinkedObject is not None for d in App.listDocuments().values() for o in d.Objects if o.TypeId == 'App::Link')
cables = {}
routes = []
for plus in (True, False):
    name = 'EQ_CordonFixe8AWG_'+('Plus' if plus else 'Moins')+'20A'
    source = doc.getObject(name).LinkedObject.Document
    wire, section, expected, metrics = route(plus)
    assert source.Cordon.TypeId == 'Part::Sweep' and source.Chemin.TypeId == 'Part::Feature'
    assert source.Section.TypeId == 'Part::Feature'
    assert source.Cordon.Shape.isValid() and len(source.Cordon.Shape.Solids) == 1
    assert source.Cordon.Shape.cut(expected).Volume < 1e-3
    assert expected.cut(source.Cordon.Shape).Volume < 1e-3
    assert source.Chemin.Shape.Length > 152.4
    arcs = [edge.Curve.Radius for edge in source.Chemin.Shape.Edges if hasattr(edge.Curve, 'Radius')]
    assert all(abs(r-50) < 1e-6 for r in arcs)
    cables[name] = doc.getObject(name).Shape
    routes.append({'reference': name, 'longueur_libre_mm': source.Chemin.Shape.Length,
                  'rayons_arcs_mm': arcs, 'arbre_natif_preserve': True})
assert list(cables.values())[0].common(list(cables.values())[1]).Volume < 1e-6
mobile_min = min(o.Shape.BoundBox.XMin for o in links if getattr(o, 'Mobile', 'non') == 'oui')
fixed_max = max(s.BoundBox.XMax for s in cables.values())
assert mobile_min > fixed_max
hits = []
external_hits = []
for name, shape in cables.items():
    for o in links:
        if o.Name in cables or not shape.BoundBox.intersect(o.Shape.BoundBox):
            continue
        volume = shape.common(o.Shape).Volume
        if volume > 1e-3:
            hits.append({'cordon': name, 'autre': o.Name, 'volume_mm3': volume})
    for o in integration.Objects:
        if o.TypeId != 'App::Link' or o.LinkedObject.Document == doc:
            continue
        if shape.BoundBox.intersect(o.Shape.BoundBox):
            volume = shape.common(o.Shape).Volume
            if volume > 1e-3:
                external_hits.append({'cordon': name, 'autre': o.Name, 'volume_mm3': volume})
assert not external_hits
assert all(h['autre'] in ['ProtectionFixeTE', 'SpliceJETI0', 'SpliceJETI1', 'IsolationSplice0', 'IsolationSplice1'] for h in hits)
sources = {}
preserved_breps = 0
for row in snapshot['fichiers']:
    path = ROOT/row['fichier']
    sources[row['fichier']] = hashlib.sha256(path.read_bytes()).hexdigest()
    if 'EQ_CordonFixe8AWG_' in path.name:
        continue
    baseline = subprocess.check_output(['git', 'show', snapshot['commit_avant']+':'+row['fichier']], cwd=ROOT)
    with zipfile.ZipFile(io.BytesIO(baseline)) as old, zipfile.ZipFile(path) as current:
        for name in old.namelist():
            if name.lower().endswith('.brp'):
                assert old.read(name) == current.read(name), (row['fichier'], name)
                preserved_breps += 1
assert sources[colors['fichier']] == colors['sha256_apres']
assert all(sources[r['fichier']] == r['sha256_apres'] for r in colors['references_colorees'])
b = doc.Ensemble.Shape.BoundBox
proof = {'date': '2026-10-04', 'besoin': ['MEC-ARC-001', 'MEC-BAT-001'],
         'controle': 'T-CARTO-DOCK-COMPACT-01', 'environnement': 'Windows amd64 / FreeCAD 1.1.3',
         'version_FreeCAD': App.Version(), 'processus_neuf': True, 'finalisation_correcte': True,
         'conclusion': 'préliminaire', 'qualification_physique': 'À valider',
         'occurrences_dock': len(links), 'documents_charges': len(App.listDocuments()),
         'erreurs_recalcul': errors, 'liens_non_resolus': [], 'routes': routes,
         'bbox_mm': [b.XMin, b.YMin, b.ZMin, b.XMax, b.YMax, b.ZMax],
         'dimensions_mm': [b.XLength, b.YLength, b.ZLength],
         'course_continue_plus_X': {'separation_conservative_mm': mobile_min-fixed_max, 'conforme_geometriquement': True},
         'intersections_integration': external_hits, 'intersections_dock': hits,
         'BRep_inchanges_hors_deux_cordons': preserved_breps, 'sources_sha256': sources,
         'recette_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
         'limites': ['Intersection préexistante positif/P49 de 84.525mm³ non résolue ; aucune absence globale d’interférence revendiquée.',
                     'Épissures et gaines modélisées en recouvrement ; montage réel à mesurer.',
                     'Liberté flottante TE, rayons réels, accès, vibration, thermique, hélices et vol non qualifiés.']}
target = VER/'controle_compacite_dock20Ah.json'
target.write_text(json.dumps(proof, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
assert json.loads(target.read_text(encoding='utf-8')) == proof
print(json.dumps({k: proof[k] for k in ['finalisation_correcte', 'occurrences_dock', 'dimensions_mm', 'BRep_inchanges_hors_deux_cordons']}))
