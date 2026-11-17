"""Affinage BRep : validité des entrées mise en cache, aucun contrôle désactivé."""
from mesurer_copie import *

def run():
    reader=Reader(COPY);base=read(OUT/'baseline_volumes.json')
    routes=read(COPY/'verification/routes_prototype.json')['routes']
    cables={r['id']:reader.shape(r['fichier'],r['objet_cable']) for r in routes}
    valid={cid:inspect_solid(s)['status']=='pass' for cid,s in cables.items()}
    result={'baseline_sha256':sha(OUT/'baseline_volumes.json'),'method':'Mêmes volumes ; validité entrée calculée une fois, common/distance par paire ; AABB disjointe certifie seulement non-intersection',
      'refined_pairs':[],'airy_junctions':[],'complete':False,'volume_tolerance_mm3':1e-4,'sources_before':verify_sources(read(COPY/'experiment.json'))}
    if (OUT/'affinage_volumes.json').exists():
        old=read(OUT/'affinage_volumes.json')
        if old.get('complete'):raise RuntimeError('Affinage déjà finalisé')
        if old['baseline_sha256']!=result['baseline_sha256']:raise RuntimeError('Baseline modifiée')
        result=old
    result['split_solid_method']='Après blocage booléen de composé : common par solide proche ; distance minimale aux solides, bornes AABB pour élagage. Somme des intersections = borne supérieure si solides obstacle se recouvrent.'
    completed={tuple(p['pair']) for p in result['refined_pairs']}
    targets={p['pair'][1] for p in base['unknown_pairs'] if 'pair' in p}
    for row in base['occurrences']:
        name=row['id']
        if name not in targets:continue
        shape=reader.occurrence(row)
        obstacle_valid=not shape.isNull() and shape.isValid() and bool(shape.Solids) and shape.Volume>0
        for cid,cable in cables.items():
            if (cid,name) in completed:continue
            item={'pair':[cid,name],'status':'unknown'}
            lower=gap(cable.BoundBox,shape.BoundBox)
            print(cid,name,flush=True)
            try:
                if lower>1e-6:item.update(status='pass',method='AABB_disjoint',intersection_volume_mm3=0,clearance_mm=None,clearance_lower_bound_mm=lower)
                elif not valid[cid] or not obstacle_valid:item.update(error='invalid_input_solid')
                else:
                    v=0.;d=None;count=0
                    for bound,_,solid in sorted((gap(cable.BoundBox,s.BoundBox),i,s) for i,s in enumerate(shape.Solids)):
                        if bound<=1e-6:
                            common=cable.common(solid);count+=1
                            if not common.isNull() and not common.isValid():raise RuntimeError('Invalid intersection')
                            v+=common.Volume
                        if d is None or bound<=d+1e-6:
                            measured=cable.distToShape(solid)[0]
                            d=measured if d is None else min(d,measured)
                    if d is None:raise RuntimeError('No distance')
                    if not math.isfinite(v) or not math.isfinite(d):raise RuntimeError('Nonfinite measurement')
                    item.update(status='fail' if v>1e-4 else 'pass',method='BRep_per_solid',intersection_volume_mm3=v,
                       volume_semantics='upper_bound_sum_zero_certifies_no_volume_intersection',solids_boolean_checked=count,clearance_mm=d)
            except Exception as exc:item['error']=str(exc)
            result['refined_pairs'].append(item);write('affinage_volumes.json',result)
    # Reprendre seulement la relation de jonction nominale déjà documentée,
    # avec identités, centre et volumes hors zone. Aucune exemption équipement.
    for collision in base['collisions']:
        aid,bid=collision['pair']
        if aid not in {'AIRY','AIRY_ETH','AIRY_PWR','AIRY_SYNC'} or bid not in {'AIRY','AIRY_ETH','AIRY_PWR','AIRY_SYNC'}:continue
        ar=next(r for r in routes if r['id']==aid);br=next(r for r in routes if r['id']==bid)
        aw=reader.shape(ar['fichier'],ar['objet_parcours']).Wires[0];bw=reader.shape(br['fichier'],br['objet_parcours']).Wires[0]
        shared=[v.Point for v in (aw.Vertexes[0],aw.Vertexes[-1]) if any((v.Point-w.Point).Length<1e-5 for w in (bw.Vertexes[0],bw.Vertexes[-1]))]
        overlap=cables[aid].common(cables[bid]);outside=overlap
        radius=max(ar['diametre_mm'],br['diametre_mm'])
        for p in shared:outside=outside.cut(Part.makeSphere(radius,p))
        result['airy_junctions'].append({'pair':[aid,bid],'shared_points_mm':[[p.x,p.y,p.z] for p in shared],
          'nominal_zone_radius_mm':radius,'overlap_mm3':overlap.Volume,'outside_nominal_zone_mm3':outside.Volume,
          'source':'verification/verify_faisceaux_prototype.py AIRY_JUNCTION et nomenclature ELEC-F-AIRY',
          'interpretation':'Recouvrement des enveloppes de branches dans éclatement OEM nominal ; géométrie interne réelle NON_VERIFIE, pas une autorisation de conducteurs superposés'})
    result['sources_after']=verify_sources(read(COPY/'experiment.json'));result['complete']=True;write('affinage_volumes.json',result)

if __name__=='__main__':
    try:run();sys.stdout.flush();sys.stderr.flush();os._exit(0)
    except Exception:traceback.print_exc();sys.stdout.flush();sys.stderr.flush();os._exit(2)
