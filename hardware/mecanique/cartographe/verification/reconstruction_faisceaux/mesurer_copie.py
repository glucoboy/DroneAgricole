"""Adaptateur de mesure FreeCAD sur copie isolée ; aucune sauvegarde des sources.

Recette : Python embarqué FreeCAD -B mesurer_copie.py native|brep|assembly.
Les règles de conception restent dans les données et le planificateur C++17.
"""
from pathlib import Path
import os
import sys
import json
import hashlib
import math
import traceback

ROOT = Path(__file__).resolve().parents[5]
COPY = ROOT / 'hardware/mecanique/cartographe_faisceaux'
OUT = Path(__file__).resolve().parent
sys.path[:0] = [str(COPY/'verification'), str(ROOT/'.agents/skills/electromechanical-integration/scripts')]
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import FreeCAD as App
import Part
from read_brep_prototype import Reader
from freecad_geometry import inspect_route, inspect_solid, inspect_pair, rebuild_cable_in_isolated_document
from workspace_guard import verify_sources

def read(path):
    return json.loads(Path(path).read_text('utf-8'))

def write(name, data):
    (OUT/name).write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def assert_copy(doc):
    for loaded in App.listDocuments().values():
        if loaded.FileName and not Path(loaded.FileName).resolve().is_relative_to(COPY):
            raise RuntimeError('Reference hors copie: '+loaded.FileName)

def native():
    import FreeCADGui as Gui
    Gui.showMainWindow(); Gui.getMainWindow().hide()
    import cable_workbench_prototype as builder
    result={'environment':builder.bootstrap_paths(),'sources_before':verify_sources(read(COPY/'experiment.json')),
            'scope':'53 parcours dans copie ; recalcul frais en RAM, aucune sauvegarde des natifs', 'routes':[],'complete':False}
    for row in read(COPY/'verification/routes_prototype.json')['routes']:
        doc=App.openDocument(str(COPY/row['fichier'])); assert_copy(doc)
        cable=doc.getObject(row['objet_cable'])
        before={'length_mm':cable.Base.Shape.Length,'volume_mm3':cable.Shape.Volume}
        fresh=rebuild_cable_in_isolated_document(doc,cable)
        route=inspect_route(cable.Base.Shape.Wires[0],start_position=row['points_mm'][0],end_position=row['points_mm'][-1])
        result['routes'].append({'id':row['id'],'file':row['fichier'],'source_sha256':sha(COPY/row['fichier']),
            'before':before,'fresh':fresh,'route':route,'volume_delta_mm3':cable.Shape.Volume-before['volume_mm3'],
            'length_delta_mm':cable.Base.Shape.Length-before['length_mm']})
        App.closeDocument(doc.Name)
        write('recalcul_natif.json',result)
        print(row['id'],fresh['status'],flush=True)
    result['complete']=True;result['sources_after']=verify_sources(read(COPY/'experiment.json'))
    write('recalcul_natif.json',result)

def gap(a,b):
    return math.sqrt(sum(max(0,getattr(a,k+'Min')-getattr(b,k+'Max'),getattr(b,k+'Min')-getattr(a,k+'Max'))**2 for k in 'XYZ'))

def brep():
    reader=Reader(COPY); routes=read(COPY/'verification/routes_prototype.json')['routes']
    build=read(COPY/'verification/construction_prototype.json'); ids={r['id'] for r in routes}
    occurrences=[o for o in build['occurrences'] if o['parent'].startswith('sous_assemblages/')]
    result={'scope':'Volumes sauvegardes de toutes occurrences des sous-assemblages, placements controles ; aucune exemption volumetrique',
      'tolerances':{'volume_mm3':1e-4,'distance_mm':1e-6,'continuity_mm':1e-5,'tangent_deg':0.1},
      'input_sha256':{n:sha(COPY/'verification'/n) for n in ['routes_prototype.json','construction_prototype.json']},
      'sources_before':verify_sources(read(COPY/'experiment.json')),'occurrences':[], 'routes':[], 'collisions':[],
      'unknown_pairs':[], 'cable_pairs':[], 'complete':False, 'pair_checks':0,'bbox_disjoint':0}
    cables={r['id']:(r,reader.shape(r['fichier'],r['objet_cable'])) for r in routes}
    nearest={r['id']:{'distance_mm':None,'obstacle':None} for r in routes}
    for row in routes:
        wire=reader.shape(row['fichier'],row['objet_parcours']).Wires[0]
        solid=cables[row['id']][1]
        result['routes'].append({'id':row['id'],'bom_ids':row['bom_ids'], 'file':row['fichier'],
          'route':inspect_route(wire,start_position=row['points_mm'][0],end_position=row['points_mm'][-1]),
          'solid':inspect_solid(solid),'diameter_mm':row['diametre_mm'],'physical_status':'A_VALIDER_PHYSIQUEMENT'})
    resume_count=0
    previous=OUT/'baseline_volumes.json'
    if previous.exists():
        saved=read(previous)
        if saved.get('complete'):raise RuntimeError('Baseline déjà finalisée ; ne pas relancer implicitement')
        if saved['input_sha256']!=result['input_sha256']:raise RuntimeError('Entrées différentes du checkpoint')
        verify_sources(read(COPY/'experiment.json'))
        result=saved
        resume_count=len(result['occurrences'])
        result['resume_from_occurrence']=resume_count
        result['resume_script_sha256']=sha(__file__)
        if 'minimum_distances' in result:nearest=result['minimum_distances']
    # Le repère global doit être réellement identique aux repères des sous-assemblages.
    top=[o for o in build['occurrences'] if o['parent'].startswith('assemblages/')]
    for row in top:
        pose=reader.placement(row['parent'],row['occurrence'])
        if not pose.isIdentity() or max(abs(a-b) for a,b in zip(pose.toMatrix().A,row['matrice']))>1e-6:
            raise RuntimeError('Transformation racine non prise en charge '+row['occurrence'])
    result['root_placements_identity_verified']=len(top)
    for i,row in enumerate(occurrences):
        if i<resume_count:continue
        name=row['parent']+'#'+row['occurrence']
        native_pose=reader.placement(row['parent'],row['occurrence']).toMatrix().A
        if max(abs(a-b) for a,b in zip(native_pose,row['matrice']))>1e-6:
            raise RuntimeError('Matrice obsolete '+name)
        props=reader.xml(row['parent'])[1][row['occurrence']]
        if props['LinkTransform'].find('Bool').get('value')!='false':
            raise RuntimeError('LinkTransform non pris en charge '+name)
        item=dict(row);item['id']=name
        if row['occurrence'] in ids and 'SA07_' in row['parent']:
            item['role']='cable';result['occurrences'].append(item);continue
        try:
            shape=reader.occurrence(row)
            item.update(role='obstacle',bbox_mm=[getattr(shape.BoundBox,k) for k in ['XMin','YMin','ZMin','XMax','YMax','ZMax']],
                solids=len(shape.Solids),valid=shape.isValid())
        except Exception as exc:
            item.update(role='obstacle',error=str(exc));result['unknown_pairs'].append({'obstacle':name,'scope':'all cables','error':str(exc)})
            result['occurrences'].append(item);continue
        result['occurrences'].append(item)
        for cid,(r,cable) in cables.items():
            lower=gap(cable.BoundBox,shape.BoundBox); best=nearest[cid]['distance_mm']
            result['pair_checks']+=1
            if lower>1e-6: result['bbox_disjoint']+=1
            if lower>1e-6 and best is not None and lower>best+1e-6: continue
            # Un volume disjoint par AABB ne requiert pas de booleen ; distance exacte pour le minimum.
            if lower>1e-6:
                try:
                    dist=cable.distToShape(shape)[0]
                    if best is None or dist<best:nearest[cid]={'distance_mm':dist,'obstacle':name}
                except Exception as exc:result['unknown_pairs'].append({'pair':[cid,name],'error':str(exc)})
            else:
                check=inspect_pair(cable,shape,cid,name,volume_tolerance_mm3=1e-4)
                if check['status']=='unknown':result['unknown_pairs'].append(check)
                if check.get('intersection_volume_mm3',0)>1e-4:result['collisions'].append(check)
                dist=check.get('clearance_mm')
                if dist is not None and (best is None or dist<best):nearest[cid]={'distance_mm':dist,'obstacle':name}
        if i%10==0:
            result['minimum_distances']=nearest
            result['progress']=i;write('baseline_volumes.json',result); print('obstacle',i,len(occurrences),flush=True)
    # Ancien checkpoint ne contenait pas les minima : reprendre ces distances seulement.
    # Une distance nulle suffit, car aucune distance euclidienne ne peut être négative.
    if resume_count and 'minimum_distances' not in saved:
        for row in occurrences[:resume_count]:
            if row['occurrence'] in ids and 'SA07_' in row['parent']:continue
            shape=reader.occurrence(row);name=row['parent']+'#'+row['occurrence']
            for cid,(_,cable) in cables.items():
                best=nearest[cid]['distance_mm']
                if best==0 or (best is not None and gap(cable.BoundBox,shape.BoundBox)>best+1e-6):continue
                try:
                    dist=cable.distToShape(shape)[0]
                    if best is None or dist<best:nearest[cid]={'distance_mm':dist,'obstacle':name}
                except Exception as exc:result['unknown_pairs'].append({'pair':[cid,name],'error':str(exc)})
        result['pre_resume_distances_recovered']=True
    values=list(cables.items())
    for i,(aid,(ar,a)) in enumerate(values):
        for bid,(br,b) in values[i+1:]:
            result['pair_checks']+=1
            if gap(a.BoundBox,b.BoundBox)>1e-6:result['bbox_disjoint']+=1;continue
            check=inspect_pair(a,b,aid,bid,volume_tolerance_mm3=1e-4)
            result['cable_pairs'].append(check)
            if check['status']=='unknown':result['unknown_pairs'].append(check)
            if check.get('intersection_volume_mm3',0)>1e-4:result['collisions'].append(check)
    result['minimum_distances']=nearest;result['complete']=True
    result['sources_after']=verify_sources(read(COPY/'experiment.json'))
    write('baseline_volumes.json',result)

def assembly():
    import FreeCADGui as Gui
    Gui.showMainWindow();Gui.getMainWindow().hide()
    import cable_workbench_prototype as builder
    builder.bootstrap_paths()
    doc=App.openDocument(str(COPY/'assemblages/Prototype_Cartographe.FCStd'));assert_copy(doc)
    result={'documents':[],'recompute_return':bool(doc.recompute()),'entry':str(doc.FileName)}
    for d in App.listDocuments().values():
        errors=[o.Name for o in d.Objects if any(s in ('Invalid','Error') for s in o.State)]
        result['documents'].append({'file':d.FileName,'objects':len(d.Objects),'errors':errors})
    result['all_resolved_inside_copy']=True
    result['source_preservation']=verify_sources(read(COPY/'experiment.json'))
    write('reouverture_assemblage.json',result)

def equivalence():
    import FreeCADGui as Gui
    Gui.showMainWindow();Gui.getMainWindow().hide()
    import cable_workbench_prototype as builder
    builder.bootstrap_paths();reader=Reader(COPY)
    build=read(COPY/'verification/construction_prototype.json')
    rows=read(COPY/'verification/routes_prototype.json')['routes']
    result={'volume_tolerance_mm3':1e-4,'routes':[],'placements':[],'complete':False,
            'source_preservation':verify_sources(read(COPY/'experiment.json'))}
    for row in build['occurrences']:
        if row['parent'].startswith('assemblages/') or ('SA07_' in row['parent'] and row['occurrence'] in {r['id'] for r in rows}):
            pose=reader.placement(row['parent'],row['occurrence'])
            result['placements'].append({'id':row['parent']+'#'+row['occurrence'],'identity':pose.isIdentity(),
              'matches_register':max(abs(a-b) for a,b in zip(pose.toMatrix().A,row['matrice']))<=1e-6})
            if not pose.isIdentity():raise RuntimeError('Pose câble/racine non identité')
    targets=[(r['id'],r['fichier']) for r in rows]+[('F16_ARCS_R23_5','verification/candidats/F16_ARCS_R23_5.FCStd')]
    for cid,path in targets:
        doc=App.openDocument(str(COPY/path));assert_copy(doc)
        cable=next(o for o in doc.Objects if hasattr(o,'ProfilExterieur'))
        saved=cable.Shape.copy();fresh=rebuild_cable_in_isolated_document(doc,cable)
        row={'id':cid,'fresh_status':fresh['status']}
        try:
            removed=saved.cut(cable.Shape);added=cable.Shape.cut(saved)
            row.update(removed_mm3=removed.Volume,added_mm3=added.Volume,
                       pass_equivalence=removed.Volume<=1e-4 and added.Volume<=1e-4)
        except Exception as exc:row.update(pass_equivalence=False,error=str(exc))
        result['routes'].append(row);App.closeDocument(doc.Name)
        write('equivalence_solides.json',result);print(cid,row.get('pass_equivalence'),flush=True)
    result['complete']=True;write('equivalence_solides.json',result)

if __name__=='__main__':
    try:
        globals()[sys.argv[1]]()
        sys.stdout.flush();sys.stderr.flush();os._exit(0)
    except Exception:
        traceback.print_exc();sys.stdout.flush();sys.stderr.flush();os._exit(2)
