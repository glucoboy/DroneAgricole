"""Tester des FCStd de câbles candidats contre le prototype sauvegardé.

Usage : python verify_candidats_faisceaux_prototype.py --candidats candidates.json
        --output .runtime/.../controle.json [--ids F06,F31] [--distances]

JSON d'entrée : {"routes":[{"id":"F06","fichier":"chemin.FCStd",
"objet_cable":"Cable","objet_parcours":"Wire"}]}. Les champs absents sont
repris dans routes_prototype.json. Les candidats remplacent seulement les routes
de même id pour le calcul. Aucune CAO ni registre de conception n'est modifié.
"""
import argparse
from datetime import datetime, timezone
import itertools
import json
from pathlib import Path
import sys
import FreeCAD as App
import Part
from read_brep_prototype import Reader
from verify_faisceaux_prototype import (MEC, VER, sha, overlap, intersection,
    sample_wire, point_box_distance, box_values, VOLUME_TOL, FAR_DISTANCE,
    END_ZONE, progress)


def run(args):
    build=json.loads((VER/'construction_prototype.json').read_text('utf-8'))
    baseline=json.loads((VER/'routes_prototype.json').read_text('utf-8'))
    configuration=json.loads(Path(args.candidats).read_text('utf-8'))
    candidates=configuration['routes']
    requested={x for x in args.ids.split(',') if x} if args.ids else {r['id'] for r in candidates}
    by_id={r['id']:r for r in baseline['routes']}
    for row in candidates:
        if row['id'] in requested:
            merged=dict(by_id.get(row['id'],{}));merged.update(row)
            by_id[row['id']]=merged
    if not requested.issubset({r['id'] for r in candidates}):
        raise ValueError('Identifiant demandé sans candidat.')
    ignored={x for x in (args.ignorer_baseline or '').split(',') if x} - requested
    by_id={k:v for k,v in by_id.items() if k not in ignored}
    files={r['fichier']:r['sha256'] for r in build['references']}
    files.update(build['sources_preservees'])
    reader=Reader(MEC)
    original_cable_ids={r['id'] for r in baseline['routes']}
    physical=[dict(o) for o in build['occurrences'] if o['parent'].startswith('sous_assemblages/')
              and not ('SA07_' in o['parent'] and o['occurrence'] in original_cable_ids)]
    for override in configuration.get('occurrences',[]):
        matches=[o for o in physical if o['parent']==override['parent'] and o['occurrence']==override['occurrence']]
        if len(matches)!=1:raise ValueError('Override occurrence ambigu ou absent : '+str(override))
        if set(override)-{'parent','occurrence','matrice'}:
            raise ValueError('Seule la matrice peut être remplacée dans un candidat.')
        matches[0].update(override)
    checked_files={}
    for row in physical:
        for path in (row['parent'],row['source']):
            if path not in checked_files:
                digest=sha(MEC/path)
                if digest!=files[path]:raise ValueError('Obstacle modifié depuis construction : '+path)
                checked_files[path]=digest
    cables={}
    for cid,row in by_id.items():
        cable=reader.shape(row['fichier'],row.get('objet_cable','Cable'))
        wire=reader.shape(row['fichier'],row.get('objet_parcours','Wire')).Wires[0]
        cables[cid]=dict(row=row,shape=cable,wire=wire)
        checked_files[row['fichier']]=sha(MEC/row['fichier'])
    targets={k:v for k,v in cables.items() if k in requested}
    report=dict(date_utc=datetime.now(timezone.utc).isoformat(),
                construction_sha256=sha(VER/'construction_prototype.json'),
                routes_sha256=sha(VER/'routes_prototype.json'),
                candidats_sha256=sha(args.candidats),fichiers_sha256=checked_files,
                occurrences_candidates=configuration.get('occurrences',[]),
                cables_baseline_ignores=sorted(ignored),
                ids_controles=sorted(requested),collisions_physique=[],collisions_cables=[],
                geometrie=[dict(id=k,valide=v['shape'].isValid(),solides=len(v['shape'].Solids),
                    longueur_mm=v['wire'].Length,rayons_mm=sorted({e.Curve.Radius for e in v['wire'].Edges if hasattr(e.Curve,'Radius')}))
                    for k,v in targets.items()],distances=[],finalisation_correcte=False)
    output=Path(args.output);output.parent.mkdir(parents=True,exist_ok=True)
    def save():output.write_text(json.dumps(report,ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf-8')
    supports=[]
    for index,row in enumerate(physical,1):
        shape=reader.occurrence(row);name=Path(row['parent']).stem+'/'+row['occurrence']
        for cid,item in targets.items():
            volume,solids,boxes=intersection(item['shape'],shape)
            if volume>VOLUME_TOL:
                report['collisions_physique'].append(dict(cable=cid,obstacle=name,
                    volume_mm3=round(volume,5),solides_locaux=solids,bbox_intersections_mm=boxes))
        if args.distances and (('SA01_' in row['parent'] and row['occurrence'].startswith('OEM_')) or
            ('/fabriquees/' in row['source'] and row['occurrence']!='CA01') or 'SA07_' in row['parent']):
            supports.extend((name,s) for s in shape.Solids)
        report.update(etape='physique',obstacles_controles=index);save()
    # Pièces nouvelles explicitement fournies par la variante de travail.
    # Elles s'ajoutent aux obstacles de référence ; rien n'est masqué.
    report['obstacles_ajoutes']=configuration.get('obstacles_ajoutes',[])
    for row in configuration.get('obstacles_ajoutes',[]):
        shape=reader.occurrence(row);name=row['occurrence']
        checked_files[row['source']]=sha(MEC/row['source'])
        for cid,item in targets.items():
            volume,solids,boxes=intersection(item['shape'],shape)
            if volume>VOLUME_TOL:
                report['collisions_physique'].append(dict(cable=cid,obstacle=name,
                    volume_mm3=round(volume,5),solides_locaux=solids,bbox_intersections_mm=boxes))
        if args.distances:supports.extend((name,s) for s in shape.Solids)
        save()
    for (a,sa),(b,sb) in itertools.combinations(cables.items(),2):
        if not requested.intersection((a,b)) or not overlap(sa['shape'].BoundBox,sb['shape'].BoundBox):continue
        common=sa['shape'].common(sb['shape'])
        if common.Volume>VOLUME_TOL:
            report['collisions_cables'].append(dict(a=a,b=b,volume_mm3=round(common.Volume,5),bbox_mm=box_values(common)))
            report.update(etape='cables');save()
    if args.distances:
        bounds=[s.BoundBox for _,s in supports]
        for cid,item in targets.items():
            rows=[]
            for position,point in sample_wire(item['wire']):
                ordered=sorted((point_box_distance(point,bb),i) for i,bb in enumerate(bounds))
                best,nearest=float('inf'),None;vertex=Part.Vertex(point)
                for lower,i in ordered:
                    if lower>best+1e-5:break
                    distance=vertex.distToShape(supports[i][1])[0]
                    if distance<best:best,nearest=distance,supports[i][0]
                rows.append(dict(s_mm=round(position,2),point_mm=[round(v,2) for v in (point.x,point.y,point.z)],
                    distance_mm=round(best,2),support=nearest,
                    zone_terminale=min(position,item['wire'].Length-position)<=END_ZONE))
            report['distances'].append(dict(cable=cid,max_mm=max(r['distance_mm'] for r in rows),
                points_lointains=[r for r in rows if r['distance_mm']>FAR_DISTANCE],table=rows))
            report.update(etape='distances');save()
    report.update(finalisation_correcte=True,
        fichiers_non_modifies=all(sha(MEC/p)==h for p,h in checked_files.items()),
        avertissement='Comparaison de candidats ; aucune qualification. Les jonctions et contacts de connecteurs restent tous signalés.')
    save()
    progress('candidats_termines',cables=len(targets),physique=len(report['collisions_physique']),paires=len(report['collisions_cables']))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--candidats',required=True);parser.add_argument('--output',required=True)
    parser.add_argument('--ids');parser.add_argument('--distances',action='store_true')
    parser.add_argument('--ignorer-baseline',help='IDs séparés par virgules ; uniquement routes non candidates')
    run(parser.parse_args())
