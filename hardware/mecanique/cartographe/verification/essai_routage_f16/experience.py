"""Essai sur copie : interpolation native du parcours F16 existant."""
from pathlib import Path
import hashlib, json, math, os, shutil, sys
import FreeCAD as App
import FreeCADGui as Gui

HERE = Path(__file__).resolve().parent
MEC = HERE.parents[1]
sys.path.insert(0, str(MEC / 'verification'))
from cable_workbench_prototype import bootstrap_paths

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def measure(cable):
    path = cable.Base.Shape.Wires[0]
    curvature = [abs(e.curvatureAt(e.FirstParameter + (e.LastParameter-e.FirstParameter)*i/2000))
                 for e in path.Edges for i in range(2001)]
    k = max(curvature)
    return {'longueur_mm': path.Length, 'rayon_min_echantillonne_mm': 1/k if k else None,
            'echantillons_par_arete': 2001, 'aretes': [e.Curve.TypeId for e in path.Edges],
            'solides': len(cable.Shape.Solids), 'solide_valide': cable.Shape.isValid(),
            'chemin_valide': path.isValid(), 'etats': {o.Name:list(o.State) for o in (cable,cable.Base)}}

def run():
    Gui.showMainWindow()
    Gui.getMainWindow().hide()
    provenance = bootstrap_paths()
    source = MEC/'pieces/commerce/W_F16_Prototype.FCStd'
    target = HERE/'F16_copie.FCStd'
    original = sha(source)
    shutil.copy2(source, target)
    doc = App.openDocument(str(target)); App.setActiveDocument(doc.Name); doc.recompute()
    cable = doc.getObject('Cable'); wire = cable.Base
    avant = measure(cable)
    # Interpoler les points de l'axe initial par distance constante ; conserver
    # les segments terminaux comme directions candidates des connecteurs.
    initial = wire.Shape.Wires[0]
    pts = initial.discretize(Distance=8.0)
    wire.Points = [wire.Placement.inverse().multVec(p) for p in pts]
    wire.PathType = 'BSpline_K'
    wire.BoundarySegmentStart = 0
    wire.BoundarySegmentEnd = 0
    wire.BoundaryTangents = True
    wire.InnerTangents = False
    doc.recompute()
    apres = measure(cable)
    apres.update(path_type=wire.PathType, points=len(wire.Points),
                 boundary_start_mm=wire.BoundarySegmentStart.Value,
                 boundary_end_mm=wire.BoundarySegmentEnd.Value,
                 tangences_extremites=wire.BoundaryTangents)
    doc.save(); App.closeDocument(doc.Name)
    result = {'source_sha256':original,'source_inchangee':sha(source)==original,
              'copie_sha256':sha(target),'provenance':provenance,'avant':avant,'apres':apres,
              'limites':['Interpolation géométrique et non simulation physique.',
                         'Rayon échantillonné sans borne entre échantillons.',
                         'Axes et points de raccordement candidats, sans référence physique mesurée.',
                         'Réserve, tenue des attaches, tolérances et rayon fabricant à valider.']}
    (HERE/'mesures.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps(result,ensure_ascii=False),flush=True)

if __name__ == '__main__':
    run()
    os._exit(0)
