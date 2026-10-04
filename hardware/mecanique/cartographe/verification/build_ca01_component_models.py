"""Recette CAO d'infrastructure : modèles nominaux dérivés de plans, sans statut OEM."""
from pathlib import Path
import hashlib
import json
import FreeCAD as App
import Part

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
EXPORT = ROOT / 'exports/ca01_modeles3d_20261001'
EXPORT.mkdir(parents=True, exist_ok=True)

def box(doc, name, label, dims, xyz):
    obj = doc.addObject('Part::Box', name)
    obj.Label = label
    obj.Length, obj.Width, obj.Height = dims
    obj.Placement.Base = App.Vector(*xyz)
    return obj

def metadata(group, mpn, url, limits):
    for name, value in {'Statut':'À valider', 'ReferenceComposant':mpn,
                        'SourceURL':url, 'NatureModele':'Dérivé de plan fabricant ; non OEM',
                        'Limites':limits, 'Repere':'Origine centrée XY, plan montage z=0, unités mm'}.items():
        group.addProperty('App::PropertyString', name, 'Provenance')
        setattr(group, name, value)

def finish(doc, group, stem):
    doc.recompute()
    assert all(x.Shape.isValid() and not x.Shape.isNull() for x in group.Group)
    native = ROOT / 'pieces/commerce' / (stem+'.FCStd')
    step = EXPORT / (stem+'.step')
    doc.saveAs(str(native))
    Part.export(group.Group, str(step))
    shape = Part.read(str(step))
    b = shape.BoundBox
    result = {'native':str(native.relative_to(ROOT)), 'step':str(step.relative_to(ROOT)),
              'step_sha256':hashlib.sha256(step.read_bytes()).hexdigest(),
              'native_sha256':hashlib.sha256(native.read_bytes()).hexdigest(),
              'native_primitives':[{'name':o.Name,'type':o.TypeId} for o in group.Group],
              'valid':shape.isValid(), 'solid_count':len(shape.Solids),
              'bbox_mm':[b.XMin,b.YMin,b.ZMin,b.XMax,b.YMax,b.ZMax],
              'dimensions_mm':[b.XLength,b.YLength,b.ZLength],
              'qualification':'À valider', 'oem_model':False,
              'kicad_transform':{'offset_mm':[0,0,0],'rotation_deg':[0,0,0],'scale':[1,1,1]}}
    App.closeDocument(doc.Name)
    reopened = App.openDocument(str(native))
    reopened.recompute()
    result['reopen_native_valid'] = all(o.Shape.isValid() for o in reopened.Objects if hasattr(o,'Shape') and not o.Shape.isNull())
    result['reopen_error_states'] = [{'name':o.Name,'state':list(o.State)} for o in reopened.Objects if 'Invalid' in o.State]
    assert result['reopen_native_valid'] and not result['reopen_error_states']
    App.closeDocument(reopened.Name)
    return result

results = []
d = App.newDocument('CA01_Modele_CSM3637_Plan')
g = d.addObject('App::DocumentObjectGroup','ModeleDerive')
g.Label = 'CSM3637 nominal / quatre terminaisons / dérivé de plan / À valider'
metadata(g,'Y14880R01000B9R','https://vpgfoilresistors.com/products/current-sense-resistors/csm2512/datasheet',
         'L9.144 W9.398 H0.8 T2.184 A1.549 B0.813 ; plan4138-EN Rev8-July-2025 p2. Vue historiqueRev11-Jan2021 p3 relue pour forme. Aucun congé, marquage, épaisseur de placage ou joint soudé non coté modélisé. La teinte et la matière des primitives ne sont pas un modèle thermique. Sense E1/E2 côté Y natif positif, Y KiCad négatif.')
L,W,H,T,A,B = 9.144,9.398,0.8,2.184,1.549,0.813
body = box(d,'CorpsResistif','Corps central (géométrie nominale)',(L-2*T,W,H),(-L/2+T,-W/2,0))
g.addObject(body)
for side,x in [('1',-L/2),('2',L/2-T)]:
    sense = box(d,'E'+side,'E'+side+' / prise Kelvin / terminaison métallique',(T,A,H),(x,W/2-A,0))
    force = box(d,'I'+side,'I'+side+' / force / terminaison métallique',(T,W-A-B,H),(x,-W/2,0))
    g.addObject(sense)
    g.addObject(force)
results.append(finish(d,g,'CA01_Modele_CSM3637_Plan'))

d = App.newDocument('CA01_Modele_NANO2_451_Plan')
g = d.addObject('App::DocumentObjectGroup','ModeleDerive')
g.Label = 'NANO2 451 nominal / corps céramique et deux capuchons / dérivé de plan / À valider'
metadata(g,'0451010.MRL','https://www.littelfuse.com/assetdocs/fuse-451-and-453-datasheet?assetguid=533cd5cc-956c-4243-867f-6ab5a62f6ba1',
         'L6.10±0.20 W2.69±0.25 H2.69±0.25 et capuchons1.45 ; plan451/453 p4. Corps et capuchons simplifiés sans épaisseur de placage ou congé non coté. Cotes nominales, non enveloppe maximale. Soudure et tenue physique non qualifiées.')
L,W,H,T = 6.1,2.69,2.69,1.45
g.addObject(box(d,'CorpsCeramique','Corps céramique nominal',(L-2*T,W,H),(-L/2+T,-W/2,0)))
g.addObject(box(d,'Terminaison1','Capuchon métallique1 (placage non modélisé)',(T,W,H),(-L/2,-W/2,0)))
g.addObject(box(d,'Terminaison2','Capuchon métallique2 (placage non modélisé)',(T,W,H),(L/2-T,-W/2,0)))
results.append(finish(d,g,'CA01_Modele_NANO2_451_Plan'))
(HERE/'modeles_derives_plan.json').write_text(json.dumps({'date':'2026-10-01','scope':'Deux modèles nominaux de composants CA01 dérivés de plans fabricants ; aucune qualification physique','models':results},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(results))
