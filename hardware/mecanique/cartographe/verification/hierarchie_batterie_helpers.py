"""Lecture et invariants de la hiérarchie batterie/récepteur/principal."""
from pathlib import Path
from collections import Counter
import hashlib
import json
import FreeCAD as A

ROOT = Path(__file__).resolve().parents[4]
MEC = ROOT / 'hardware/mecanique/cartographe'
VER = MEC / 'verification'
TOP = MEC / 'assemblages/Integration_Stack_Revue_20261003.FCStd'
BAT = MEC / 'sous_assemblages/SA02_Cassette20Ah_Coulissante.FCStd'
REC = MEC / 'sous_assemblages/SA02A_Dock20Ah.FCStd'
DIST = MEC / 'sous_assemblages/SA07_Distribution_Systeme_Candidat.FCStd'
DIRECT = ('PM08', 'PDB18138', 'PlateauEnergieInferieur', 'MainSwitchJETI',
          'CommandeMagnetiqueJETI', 'InterfaceBMSIsolee')
MARKER = 'batterie_recepteur_principal'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rel(path):
    return str(Path(path).relative_to(ROOT)).replace('\\', '/')


def dump(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def links(root):
    return [o for o in root.Group if o.TypeId == 'App::Link']


def identity(p):
    return max(abs(a-b) for a,b in zip(p.toMatrix().A, A.Placement().toMatrix().A)) < 1e-9


def row(o, parent=A.Placement(), path=''):
    assert not o.LinkTransform, o.Name
    pose = parent.multiply(o.LinkPlacement)
    result = dict(occurrence=o.Name, parent=path,
                fichier=rel(o.LinkedObject.Document.FileName), objet_source=o.LinkedObject.Name,
                matrice_monde=list(pose.toMatrix().A), mobile=getattr(o, 'Mobile', 'non'),
                expressions=[list(x) for x in o.ExpressionEngine])
    if o.ViewObject:
        result['apparence'] = dict(override=bool(o.ViewObject.OverrideMaterial),
                                  visible=bool(o.Visibility),
                                  materiau=material(o.ViewObject.ShapeMaterial)
                                  if o.ViewObject.OverrideMaterial else [],
                                  override_liste=list(o.ViewObject.OverrideMaterialList),
                                  couleurs_liste=[list(c) for c in o.ViewObject.OverrideColorList],
                                  materiaux_liste=[material(m) for m in o.ViewObject.MaterialList]
                                  if o.ViewObject.OverrideMaterialList else [])
    return result


def material(m):
    return dict(ambiante=list(m.AmbientColor),diffuse=list(m.DiffuseColor),
                speculaire=list(m.SpecularColor),emissive=list(m.EmissiveColor),
                brillance=m.Shininess,transparence=m.Transparency)


def appearance_signature(rows):
    return Counter((r['fichier'], r['objet_source'],
                    tuple(round(v, 9) for v in r['matrice_monde']),
                    json.dumps(r['apparence'], sort_keys=True)) for r in rows)


def bbox(shape):
    b = shape.BoundBox
    return [b.XMin,b.YMin,b.ZMin,b.XMax,b.YMax,b.ZMax]


def affected(top):
    """Décomposer les conteneurs modifiés, garder les quatre autres opaques."""
    assert identity(top.IntegrationRevue.Placement)
    result = []
    for o in links(top.IntegrationRevue):
        filename = Path(o.LinkedObject.Document.FileName)
        if filename in (BAT, REC, DIST):
            r = o.LinkedObject
            assert identity(r.Placement), r.Name
            for child in links(r):
                result.append(row(child, o.LinkPlacement, rel(filename)))
        else:
            result.append(row(o, path=rel(top.FileName)))
    return result


def signature(rows):
    return Counter((r['fichier'], r['objet_source'],
                    tuple(round(v, 9) for v in r['matrice_monde'])) for r in rows)


def native_sources():
    return {rel(d.FileName): sha(d.FileName) for d in A.listDocuments().values()
            if d.FileName and Path(d.FileName).is_relative_to(ROOT)}


def recompute_all():
    for d in A.listDocuments().values():
        for o in d.Objects:
            o.touch()
    for _ in range(2):
        for d in A.listDocuments().values():
            d.recompute()


def check_tree(top):
    group = links(top.IntegrationRevue)
    assert len(group) == 12
    assert not top.getObject('SA07_Distribution_Systeme_Candidat')
    bat = top.getObject('SA02_Cassette20Ah_Coulissante').LinkedObject
    rec = top.getObject('SA02A_Dock20Ah').LinkedObject
    assert len(links(bat)) == 67 and len(links(rec)) == 72
    assert all(o.Mobile == 'oui' for o in links(bat))
    assert all(o.Mobile == 'non' for o in links(rec))
    assert len([o for o in bat.Document.Objects if o.TypeId == 'App::Link']) == 67
    assert len([o for o in rec.Document.Objects if o.TypeId == 'App::Link']) == 72
    for name in DIRECT:
        assert top.getObject(name) in group
        assert '/pieces/' in rel(top.getObject(name).LinkedObject.Document.FileName)
    assert not any(o.Name in DIRECT for o in links(bat) + links(rec))
    assert len(links(top.getObject('SA08_Faisceau_Systeme_Candidat').LinkedObject)) == 37
    invalid = [d.Name+'.'+o.Name for d in A.listDocuments().values()
               for o in d.Objects if 'Invalid' in o.State]
    missing = [d.Name+'.'+o.Name for d in A.listDocuments().values() for o in d.Objects
               if o.TypeId == 'App::Link' and not o.LinkedObject]
    assert not invalid and not missing, (invalid, missing)
    return dict(liens_principal=12, batterie=67, recepteur=72,
                pieces_directes=list(DIRECT), routes=37, erreurs_recalcul=invalid,
                liens_non_resolus=missing)
