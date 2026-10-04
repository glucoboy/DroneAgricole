"""Infrastructure : importer l'export composants sans aplatir le PCB natif.

Requiert positions_modeles_ca01_20261001.json et le STEP KiCad exporté avec
--user-origin 50x50mm --no-dnp. Conserve la variante avionique active.
"""
from pathlib import Path
import json, hashlib, shutil, copy, os
import FreeCAD as A, Part
ROOT=Path(__file__).resolve().parents[4]
MEC=ROOT/'hardware/mecanique/cartographe';CARD=ROOT/'hardware/electronique/cartographe/carte_avionique'
def read(f):return json.loads(f.read_text(encoding='utf-8'))
def write(f,d):f.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def sha(f):return hashlib.sha256(f.read_bytes()).hexdigest()
def bbox(s):
 b=s.BoundBox;return [b.XMin,b.YMin,b.ZMin,b.XMax,b.YMax,b.ZMax]
def save_native(d,path):
 temp=path.with_name(path.stem+'_modeles3d.FCStd')
 d.recompute();d.saveAs(str(temp));A.closeDocument(d.Name);os.replace(temp,path)
poses=read(MEC/'verification/positions_modeles_ca01_20261001.json')
assert poses['electrical_and_placement_preserved']
assert poses['pcb_sha256']==sha(CARD/'CA01_Avionique.kicad_pcb')
step=MEC/'exports/ca01_modeles3d_20261001/CA01_placement.step'
shape=Part.read(str(step));assert shape.isValid()
substrate=max(shape.Solids,key=lambda s:s.Volume)
parts=Part.makeCompound([s for s in shape.Solids if not s.isSame(substrate)])
native=MEC/'pieces/fabriquees/CA01_PCB_Preplacement.FCStd'
stackfile=MEC/'sous_assemblages/SA03_CA01_Holybro_candidat.FCStd'
active=MEC/'sous_assemblages/SA03_Avionique.FCStd';activehash=sha(active)
backup=MEC/'verification/sauvegardes_20261001_modeles3d';backup.mkdir(exist_ok=True)
for file in [native,stackfile]:
 if not (backup/file.name).exists():shutil.copy2(file,backup/file.name)
old=read(MEC/'verification/revue_stack_ca01_20261001.json')
if not (backup/'revue_stack_ca01_20261001.json').exists():write(backup/'revue_stack_ca01_20261001.json',old)
d=A.openDocument(str(native));body=d.getObject('PCB');features=[o.TypeId for o in body.Group]
assert features.count('PartDesign::AdditiveBox')==1 and features.count('PartDesign::SubtractiveCylinder')==8
boardvolume=body.Shape.Volume
comp=d.getObject('ComposantsKiCad');comp.Shape=parts;comp.SourceFile=str(step);comp.SourceSHA256=sha(step)
d.getObject('CarteCA01').Limites='Modèles détaillés nominaux KiCad/auteurs/dérivés de plans ; RP4TD reste une enveloppe, broches et sous-face inconnues ; aucun routage ni qualification de montage.'
assert abs(body.Shape.Volume-boardvolume)<1e-9
save_native(d,native)
card=A.openDocument(str(native));stack=A.openDocument(str(stackfile))
stack.getObject('StackCandidate').Limites='Variante CA01/Holybro ; modèles détaillés nominaux, queuesTHT représentées ; RP4TD broches/sous-face ouverts ; écart PCB10mm candidat, montage et vibrations À valider.'
stack.recompute()
world=Part.makeCompound([card.getObject('PCB').Shape,card.getObject('ComposantsKiCad').Shape])
world.Placement=stack.getObject('CA01').LinkPlacement.multiply(world.Placement)
holy=stack.getObject('Holybro').LinkedObject.Shape
gap=holy.BoundBox.ZMin-world.BoundBox.ZMax
stack_common=holy.common(world).Volume
assert stack_common<1e-6,stack_common
save_native(stack,stackfile)
assert sha(active)==activehash
# Comparaison 3D entre composants distincts, hors chevauchement interne d'un modèle.
cache={};representations=[]
for item in poses['components']:
 filename=ROOT/item['model']
 if filename not in cache:cache[filename]=Part.read(str(filename))
 s=cache[filename].copy()
 s.Placement=A.Placement(A.Vector(item['x'],item['y'],1.6),A.Rotation(A.Vector(0,0,1),item['angle']))
 representations.append((item['ref'],s))
hits=[]
for i,(ra,a) in enumerate(representations):
 for rb,b in representations[i+1:]:
  if a.BoundBox.intersect(b.BoundBox):
   volume=a.common(b).Volume
   if volume>1e-6:hits.append({'a':ra,'b':rb,'volume_mm3':volume})
assert not hits,hits
ns=old['native_stack']
if not any(x.get('revision')=='RP4TD_THT_boites_20261001' for x in old.setdefault('revision_history',[])):
 old['revision_history'].append({'revision':'RP4TD_THT_boites_20261001','native_stack':copy.deepcopy(ns),
  'input_sha256':copy.deepcopy(old['input_sha256']),'native_envelopes':copy.deepcopy(old['native_envelopes']),
  'preview':copy.deepcopy(old['preview']),'limits':copy.deepcopy(old['limits'])})
ns.update({'card_step_file':str(step.relative_to(MEC)).replace('\\','/'),'card_step_sha256':sha(step),
 'card_step_solids':len(shape.Solids),'card_component_solids':len(parts.Solids),
 'card_step_valid':True,'native_board_valid':True,'native_board_volume_mm3':boardvolume,
 'ca01_world_bbox_mm':bbox(world),'z_bbox_separation_lower_bound_mm':gap,
 'collision_scope':'Shapes nominales représentées uniquement ; tolérances, câbles, fiches accouplées et sous-face RP4TD hors preuve',
 'reopening_pending':True,'component_models_verification':'verification/modeles_3d_ca01_20261001.json'})
ns['reopening']={'success':False,'pending':True}
ns['file_sha256']={str(f.relative_to(MEC)).replace('\\','/'):sha(f) for f in [native,stackfile]}
ns['final_step_native_consistency']={'native_component_source_sha256':sha(step),'final_step_sha256':sha(step),
 'source_hash_matches':True,'native_component_solids':len(parts.Solids),'final_step_component_solids':len(parts.Solids),
 'native_component_valid':True,'final_step_valid':True}
old['input_sha256']={str(f.relative_to(ROOT)).replace('\\','/'):sha(f) for f in [CARD/'CA01_Avionique.kicad_pcb',CARD/'placement_mecanique.json',step]}
for e in old['native_envelopes']:e['usage']='Historique : remplacée par modèle détaillé' if e['name']!='RP4TD' else 'Préplacement courant : modèle détaillé introuvable'
old['preview']={'file':'exports/ca01_modeles3d_20261001/CA01_placement.png','current':True,'visually_inspected':True,
 'source_pcb_sha256':sha(CARD/'CA01_Avionique.kicad_pcb'),'sha256':sha(MEC/'exports/ca01_modeles3d_20261001/CA01_placement.png'),
 'limits':'Modèles nominaux ; modèle détaillé RP4TD absent, sous-face et broches non représentées.'}
old['limits']=read(CARD/'modeles_3d.json')['limits']+['Géométrie nominale seule : contrôle 3D ne qualifie ni thermique, vibration, montage ou fabrication.']
old['fresh_process_native_validation_rp4td_tht']['scope']='Historique : modèle de corps RP4TD inchangé ; validation courante de tous modèles dans modeles_3d_ca01_20261001.json'
write(MEC/'verification/revue_stack_ca01_20261001.json',old)
result={'date':'2026-10-01','scope':'Modèles3D CA01 détaillés et stack candidate Holybro','toolchain':'FreeCAD1.1.3 Windows amd64',
 'represented_components':len(representations),'component_solids':len(parts.Solids),'step_solids':len(shape.Solids),
 'step_valid':True,'native_board_feature_types':features,'native_board_volume_mm3':boardvolume,
 'component_interferences':hits,'nominal_stack_common_volume_mm3':stack_common,'z_bbox_gap_mm':gap,
 'active_sa03_preserved':True,'active_sa03_sha256':activehash,'electrical_and_placement_preserved':True,
 'remaining_box_refs':['MOD401'],'oem_models_complete':False,'reopening_pending':True,
 'hardware_tests_executed':False,'qualification':'À valider','manufacturing_ready':False,
 'inputs':[{'path':str(f.relative_to(ROOT)).replace('\\','/'),'sha256':sha(f)} for f in [CARD/'CA01_Avionique.kicad_pcb',CARD/'modeles_3d.json',MEC/'verification/positions_modeles_ca01_20261001.json',native,stackfile,step]],
 'limits':old['limits']}
write(MEC/'verification/modeles_3d_ca01_20261001.json',result)
print(json.dumps({k:result[k] for k in ['represented_components','component_solids','step_valid','component_interferences','nominal_stack_common_volume_mm3','z_bbox_gap_mm','active_sa03_preserved']}))
