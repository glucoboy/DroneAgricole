"""Contrôle BRep borné par occurrence ; reprise de la preuve interrompue.

Adaptateur infrastructure OCCT. Une expiration produit unknown, jamais pass.
"""
from mesurer_copie import *
import subprocess
import time

ROWS=read(COPY/'verification/routes_prototype.json')['routes']
IDS={r['id'] for r in ROWS}
OCC=[o for o in read(COPY/'verification/construction_prototype.json')['occurrences'] if o['parent'].startswith('sous_assemblages/')]
TEMP=ROOT/'.runtime/reconstruction-faisceaux/volume-workers'
TEMP.mkdir(parents=True,exist_ok=True)

def worker(index):
    reader=Reader(COPY)
    cables={r['id']:reader.shape(r['fichier'],r['objet_cable']) for r in ROWS}
    row=OCC[index];name=row['parent']+'#'+row['occurrence']
    pose=reader.placement(row['parent'],row['occurrence']).toMatrix().A
    if max(abs(a-b) for a,b in zip(pose,row['matrice']))>1e-6:raise RuntimeError('Pose incoherente')
    props=reader.xml(row['parent'])[1][row['occurrence']]
    if props['LinkTransform'].find('Bool').get('value')!='false':raise RuntimeError('LinkTransform non supporté')
    item=dict(row,id=name)
    checks=[];disjoint=0
    if row['occurrence'] in IDS and 'SA07_' in row['parent']:item['role']='cable'
    else:
        shape=reader.occurrence(row)
        item.update(role='obstacle',bbox_mm=[getattr(shape.BoundBox,k) for k in ['XMin','YMin','ZMin','XMax','YMax','ZMax']],
                    solids=len(shape.Solids),valid=shape.isValid())
        for cid,cable in cables.items():
            if gap(cable.BoundBox,shape.BoundBox)>1e-6:disjoint+=1;continue
            checks.append(inspect_pair(cable,shape,cid,name,volume_tolerance_mm3=1e-4))
    data={'occurrence':item,'checks':checks,'disjoint':disjoint,'complete':True}
    (TEMP/f'{index}.json').write_text(json.dumps(data,ensure_ascii=False,allow_nan=False),encoding='utf-8')

def run():
    result=read(OUT/'baseline_volumes.json')
    verify_sources(read(COPY/'experiment.json'))
    if result.get('complete'):raise RuntimeError('Déjà finalisé')
    first=len(result['occurrences'])
    result['bounded_resume']={'first':first,'timeout_seconds_per_occurrence':35,'script_sha256':sha(__file__)}
    result['distance_scope']='Minima sur paires aux AABB recouvrantes du lot repris ; seules valeurs nulles mesurées sont des minima globaux certifiés. Autres minima globaux inconnus.'
    distances={cid:[] for cid in IDS}
    for index in range(first,len(OCC)):
        row=OCC[index];name=row['parent']+'#'+row['occurrence']
        try:
            started=time.monotonic()
            run=subprocess.run([sys.executable,'-B',str(Path(__file__).resolve()),'worker',str(index)],capture_output=True,timeout=35)
            if run.returncode:raise RuntimeError(run.stderr.decode('utf-8',errors='replace')[-1500:])
            data=read(TEMP/f'{index}.json');result['occurrences'].append(data['occurrence'])
            if data['occurrence']['role']=='obstacle':result['pair_checks']+=len(IDS)
            result['bbox_disjoint']+=data['disjoint']
            for check in data['checks']:
                if check['status']=='unknown':result['unknown_pairs'].append(check)
                if check.get('intersection_volume_mm3',0)>1e-4:result['collisions'].append(check)
                if 'clearance_mm' in check:distances[check['pair'][0]].append((check['clearance_mm'],name))
        except Exception as exc:
            result['occurrences'].append(dict(row,id=name,role='obstacle',error=str(exc)))
            result['pair_checks']+=len(IDS)
            result['unknown_pairs'].extend({'pair':[cid,name],'status':'unknown','error':str(exc),'reason':'bounded_worker_failed'} for cid in IDS)
        result['progress']=index;write('baseline_volumes.json',result)
        print(index,len(OCC),'collisions',len(result['collisions']),'unknown',len(result['unknown_pairs']),flush=True)
    # Toutes les paires entre câbles sont assez petites pour un contrôle commun dédié.
    reader=Reader(COPY);cables=[(r['id'],reader.shape(r['fichier'],r['objet_cable'])) for r in ROWS]
    for i,(aid,a) in enumerate(cables):
        for bid,b in cables[i+1:]:
            result['pair_checks']+=1
            if gap(a.BoundBox,b.BoundBox)>1e-6:result['bbox_disjoint']+=1;continue
            check=inspect_pair(a,b,aid,bid,volume_tolerance_mm3=1e-4)
            result['cable_pairs'].append(check)
            if check['status']=='unknown':result['unknown_pairs'].append(check)
            if check.get('intersection_volume_mm3',0)>1e-4:result['collisions'].append(check)
        write('baseline_volumes.json',result)
    result['minimum_distances']={cid:{'distance_mm':0.0 if any(d<=1e-9 for d,n in rows) else None,
      'observed_near_pair_minimum_mm':min([d for d,n in rows],default=None),'status':'measured_global_zero' if any(d<=1e-9 for d,n in rows) else 'NON_VERIFIE'} for cid,rows in distances.items()}
    result['sources_after']=verify_sources(read(COPY/'experiment.json'));result['complete']=True
    write('baseline_volumes.json',result)

if __name__=='__main__':
    try:
        if sys.argv[1]=='worker':worker(int(sys.argv[2]))
        else:run()
        sys.stdout.flush();sys.stderr.flush();os._exit(0)
    except Exception:
        traceback.print_exc();sys.stdout.flush();sys.stderr.flush();os._exit(2)
