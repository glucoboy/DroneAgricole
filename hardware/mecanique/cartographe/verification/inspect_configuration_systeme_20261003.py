"""Infrastructure FreeCAD : inventaire récursif en lecture seule de la CAO active."""
from pathlib import Path
import hashlib
import json
import FreeCAD as A

ROOT = Path(__file__).resolve().parents[4]
MEC = ROOT / 'hardware/mecanique/cartographe'
OUT = MEC / 'verification/inventaire_systeme_20261003.json'
TOP = MEC / 'assemblages/Drone_Cartographe_20Ah.FCStd'

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def rel(path):
    return str(Path(path).relative_to(ROOT)).replace('\\', '/')

top = A.openDocument(str(TOP))
for doc in list(A.listDocuments().values()):
    doc.recompute()

rows = []
def visit(obj, placement, names, stack=()):
    if obj.TypeId == 'App::Link':
        target = obj.LinkedObject
        assert target is not None, '/'.join(names + [obj.Name])
        key = (target.Document.Name, target.Name)
        assert key not in stack, 'Cycle : ' + str(key)
        # LinkTransform=False remplace le Placement de la racine liée.
        p = placement.multiply(obj.LinkPlacement)
        if obj.LinkTransform:
            p = p.multiply(target.Placement)
        filename = Path(target.Document.FileName)
        if 'pieces' in filename.parts:
            if not hasattr(target, 'Shape'):
                rows.append({'occurrence':'/'.join(names + [obj.Name]),
                             'reference':filename.stem,'fichier':rel(filename),
                             'objet':target.Name,'matrice_placement':list(p.toMatrix().A),
                             'type_geometrie':target.TypeId,'bbox_mm':None,
                             'volume_unitaire_mm3':None,'solides':None,'valide':None,
                             'limite':'Objet non BRep ; non contrôlé par les booléens OCCT.'})
                return
            shape = target.Shape.copy()
            # Shape de l'App::Part inclut déjà le Placement de la racine.
            shape.Placement = p.multiply(target.Placement.inverse()).multiply(shape.Placement)
            b = shape.BoundBox
            rows.append({'occurrence': '/'.join(names + [obj.Name]),
                         'reference': filename.stem, 'fichier': rel(filename),
                         'objet': target.Name, 'matrice_placement': list(p.toMatrix().A),
                         'bbox_mm': [b.XMin,b.YMin,b.ZMin,b.XMax,b.YMax,b.ZMax],
                         'volume_unitaire_mm3': shape.Volume,
                         'solides': len(shape.Solids), 'valide': shape.isValid()})
            return
        for child in getattr(target, 'Group', []):
            visit(child, p, names + [obj.Name], stack + (key,))
    else:
        for child in getattr(obj, 'Group', []):
            visit(child, placement.multiply(obj.Placement) if hasattr(obj,'Placement') else placement,
                  names, stack)

visit(top.getObject('Ensemble'), A.Placement(), [])
files = {rel(d.FileName): sha(d.FileName) for d in A.listDocuments().values() if d.FileName}
proof = {'date':'2026-10-03','statut':'À valider','conclusion':'préliminaire',
         'configuration':rel(TOP),'outil':{'nom':'FreeCAD','version':A.Version()},
         'script_sha256':sha(__file__),'lecture_seule':True,'sources_sha256':files,
         'occurrences':rows,
         'erreurs_recalcul':[{'fichier':rel(d.FileName),'objet':o.Name,'etat':list(o.State)}
                            for d in A.listDocuments().values() for o in d.Objects if 'Invalid' in o.State],
         'limites':['Inventaire de la configuration active historique, pas BOM de la cible Holybro.',
                    'Feuilles OEM X650 : occurrences internes du même kit, pas autant de kits à acheter.',
                    'Volume seul ne fournit aucune masse d’un équipement multi-matériaux.']}
assert all(sha(ROOT / f) == h for f,h in files.items()), 'Source changée pendant la lecture'
OUT.write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'sortie':rel(OUT),'occurrences':len(rows),'sources':len(files),
                  'erreurs':proof['erreurs_recalcul']},ensure_ascii=False),flush=True)
