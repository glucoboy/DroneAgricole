"""Expérience isolée F16 : copie native, calcul et preuves, jamais de sauvegarde source."""
from pathlib import Path
import hashlib, json, math, os, shutil, sys
import FreeCAD as App
import FreeCADGui as Gui

HERE = Path(__file__).resolve().parent
MEC = HERE.parents[1]
VER = MEC / 'verification'
SOURCE = MEC / 'pieces/commerce/W_F16_Prototype.FCStd'
COPY = HERE / 'F16_copie.FCStd'
sys.path.insert(0, str(VER))
from cable_workbench_prototype import bootstrap_paths

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def measure(cable):
    w = cable.Base.Shape.Wires[0]
    curvature = []
    for e in w.Edges:
        for i in range(1001):
            u = e.FirstParameter + (e.LastParameter-e.FirstParameter)*i/1000
            curvature.append(abs(e.curvatureAt(u)))
    k = max(curvature)
    return dict(longueur_mm=w.Length, rayon_min_echantillonne_mm=1/k if k else None,
                nombre_echantillons_par_arete=1001, types_aretes=[e.Curve.TypeId for e in w.Edges],
                longueur_addon_mm=cable.Length.Value, solides=len(cable.Shape.Solids),
                forme_valide=cable.Shape.isValid(), chemin_valide=w.isValid(),
                etats={o.Name:list(o.State) for o in [cable,cable.Base]},
                points_mm=[[v.x,v.y,v.z] for v in cable.Base.Points],
                diametre_mm=cable.ProfilExterieur.DiametreExterieur.Value)

def run():
    Gui.showMainWindow()
    Gui.getMainWindow().hide()
    provenance = bootstrap_paths()
    initial_sha = sha(SOURCE)
    shutil.copy2(SOURCE, COPY)
    doc = App.openDocument(str(COPY))
    App.setActiveDocument(doc.Name)
    doc.recompute()
    cable = doc.getObject('Cable')
    wire = cable.Base
    before = measure(cable)
    candidate = json.loads((HERE/'candidats.json').read_text(encoding='utf8'))[0]
    wire.Points = [wire.Placement.inverse().multVec(App.Vector(*p)) for p in candidate['points']]
    wire.PathType = 'BSpline_P'
    wire.BoundarySegmentStart = 0
    wire.BoundarySegmentEnd = 0
    wire.BoundaryTangents = True
    wire.InnerTangents = True
    doc.recompute()
    after = measure(cable)
    after.update(path_type=wire.PathType, boundary_start_mm=wire.BoundarySegmentStart.Value,
                 boundary_end_mm=wire.BoundarySegmentEnd.Value,
                 rayon_addon_mm=cable.BaseWireFilletRadius.Value,
                 tangences=wire.BoundaryTangents, fixation_debut=str(wire.Vrtx_start),
                 fixation_fin=str(wire.Vrtx_end))
    doc.recompute()
    doc.save()
    App.closeDocument(doc.Name)
    proof = dict(source=str(SOURCE.relative_to(MEC)), source_sha256=initial_sha,
                 source_inchangee=sha(SOURCE)==initial_sha, copie=COPY.name,
                 copie_sha256=sha(COPY), provenance=provenance, avant=before, apres=after,
                 limites=['Points et directions initiales conservés comme hypothèses, pas de ports mesurés.',
                          'Rayon estimé par échantillonnage, sans borne garantie entre échantillons.',
                          'B-spline géométrique, aucune simulation physique.',
                          'Longueur de service et rayon admissible fournisseur non établis.'])
    (HERE/'mesures.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps(proof,ensure_ascii=False),flush=True)

if __name__ == '__main__':
    run()
    os._exit(0)
