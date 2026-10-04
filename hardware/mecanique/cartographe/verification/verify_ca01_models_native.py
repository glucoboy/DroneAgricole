"""Validation FreeCAD en processus neuf des modèles et de la stack CA01."""
from pathlib import Path
import json,hashlib
import FreeCAD as A,Part
ROOT=Path(__file__).resolve().parents[4];MEC=ROOT/'hardware/mecanique/cartographe';CARD=ROOT/'hardware/electronique/cartographe/carte_avionique'
def sha(f):return hashlib.sha256(f.read_bytes()).hexdigest()
def read(f):return json.loads(f.read_text(encoding='utf-8'))
def write(f,x):f.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
inventory=read(CARD/'modeles_3d.json');proofpath=MEC/'verification/modeles_3d_ca01_20261001.json';proof=read(proofpath)
native=MEC/'pieces/fabriquees/CA01_PCB_Preplacement.FCStd';stackfile=MEC/'sous_assemblages/SA03_CA01_Holybro_candidat.FCStd'
files=[native,stackfile,MEC/'sous_assemblages/SA03_Avionique.FCStd']
files+=sorted(set(ROOT/x['native'] for x in inventory['models_by_ref'].values() if 'native' in x))
hashes={f:sha(f) for f in files}
card=A.openDocument(str(native));stack=A.openDocument(str(stackfile))
for d in list(A.listDocuments().values()):d.recompute()
errors=[{'document':d.Name,'object':o.Name,'state':list(o.State)} for d in A.listDocuments().values() for o in d.Objects if 'Invalid' in o.State]
assert not errors,errors
assert stack.getObject('CA01').LinkedObject==card.getObject('CarteCA01')
assert stack.getObject('Holybro').LinkedObject is not None
board=card.getObject('PCB')
assert board.Shape.isValid()
assert sum(o.TypeId=='PartDesign::AdditiveBox' for o in board.Group)==1
assert sum(o.TypeId=='PartDesign::SubtractiveCylinder' for o in board.Group)==8
step=MEC/'exports/ca01_modeles3d_20261001/CA01_placement.step';shape=Part.read(str(step))
substrate=max(shape.Solids,key=lambda s:s.Volume)
components=Part.makeCompound([s for s in shape.Solids if not s.isSame(substrate)])
stored=card.getObject('ComposantsKiCad')
assert stored.SourceSHA256==sha(step)
assert len(components.Solids)==len(stored.Shape.Solids)==proof['component_solids']
assert abs(components.Volume-stored.Shape.Volume)<1e-5
for x,y in [(20.4,-8.65),(17.8,-8.65),(15.2,-8.65),(12.6,-8.65)]:
 assert not board.Shape.isInside(A.Vector(x,y,.8),1e-6,True)
 assert not substrate.isInside(A.Vector(x,y,.8),1e-6,True)
modelresults=[]
for f in files[3:]:
 d=A.openDocument(str(f));d.recompute()
 invalid=[o.Name for o in d.Objects if 'Invalid' in o.State]
 assert not invalid,(f,invalid)
 shapes=[o for o in d.Objects if hasattr(o,'Shape') and not o.Shape.isNull()]
 assert all(o.Shape.isValid() for o in shapes)
 modelresults.append({'file':str(f.relative_to(ROOT)).replace('\\','/'),'sha256':sha(f),'errors':invalid,'parametric_objects':sum(o.TypeId in ['Part::Box','Part::Cylinder','PartDesign::AdditiveBox'] for o in d.Objects),'source_import_objects':sum(o.TypeId=='Part::Feature' for o in d.Objects),'passed':True})
 A.closeDocument(d.Name)
world=Part.makeCompound([board.Shape,stored.Shape]);world.Placement=stack.getObject('CA01').LinkPlacement.multiply(world.Placement)
holy=stack.getObject('Holybro').LinkedObject.Shape
volume=holy.common(world).Volume;distance=holy.distToShape(world)[0]
assert volume<1e-6
assert all(sha(f)==hashes[f] for f in files)
proof.update({'passed':True,'reopening_pending':False,'fresh_process_reopening':{'errors':errors,'external_links_resolved':True,'files_unchanged':True,'model_native_results':modelresults,'native_board_preserved':True,'radio_holes_match_step':True},
 'nominal_stack_common_volume_mm3':volume,'nominal_stack_min_distance_mm':distance,
 'bbox_z_intervals_disjoint':False,'bbox_intervals_note':'Les queues THT pénètrent la bande Z de la Holybro : vérifier les formes réelles ; ancienne borne1.9446mm de boîtes non applicable.',
 'native_component_volume_difference_mm3':abs(components.Volume-stored.Shape.Volume),'represented_radio_count':1})
write(proofpath,proof)
rp=MEC/'verification/revue_stack_ca01_20261001.json';r=read(rp);ns=r['native_stack']
ns['reopening_pending']=False;ns['reopening']=proof['fresh_process_reopening']
ns['reopening']['success']=True
ns['nominal_stack_min_distance_mm']=distance;ns['nominal_stack_common_volume_mm3']=volume
ns['bbox_z_intervals_disjoint']=False
ns['final_step_native_consistency']['volume_difference_mm3']=abs(components.Volume-stored.Shape.Volume)
write(rp,r)
print(json.dumps({'passed':True,'models_native':len(modelresults),'component_solids':len(components.Solids),'stack_min_distance_mm':distance,'stack_common_volume_mm3':volume,'files_unchanged':True}))
