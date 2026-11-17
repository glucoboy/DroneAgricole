"""Compare des variantes du départ M8 sans enregistrer de nouvelle CAO."""
import os
import sys

from adapter_freecad import App, BASE, COPY, HERE, OLD, SA, Reader, boot, check_pairs, make_native_cable, read, scene, sha, write
from cable_workbench_prototype import _check_polyline
from controles_mobilite import moved, pose_transform


def posed_points(points, pose):
    return [pose.multVec(App.Vector(*p)) if i < 2 else App.Vector(*p) for i, p in enumerate(points)]


def main():
    environment = boot()
    _, routes, shapes, _ = scene(COPY)
    m8 = routes['F_M8']
    diameter = m8['diametre_mm']
    used = {r['id'] for r in read(HERE/'mobilite.json')['m8']}
    poses = {r['id']: pose_transform(r) for r in read(OLD/'poses_autonomie.json')['candidates'] if r['id'] in used}
    trials = []
    for straight in (3.9, 4.5, 5.0, 5.5, 6.0, 6.5, 7.0, 8.0, 10.0):
        for lead_x in (72.5, 73.0, 73.5, 74.0):
            points = [p.copy() for p in m8['points_mm']]
            points[1][1] = points[0][1]+straight
            points[2][0] = lead_x
            row = {'depart_droit_mm':straight, 'x_transition_mm':lead_x, 'points_mm':points, 'poses_incompatibles':{}}
            for key, pose in poses.items():
                try:
                    _check_polyline(posed_points(points,pose),diameter,52)
                except ValueError as error:
                    row['poses_incompatibles'][key] = str(error)
            trials.append(row)
    best = sorted(trials, key=lambda row:(len(row['poses_incompatibles']),
                   abs(row['depart_droit_mm']-3.9)+abs(row['x_transition_mm']-72.5)))[:4]
    for row in best:
        doc = App.newDocument('M8DepartVariante')
        try:
            cable, axis = make_native_cable(doc,None,'M8',row['points_mm'],diameter,52)
            obstacles = {'#'.join(key): shape for key,shape in shapes.items() if key!=(SA,'F_M8')}
            row['longueur_nominale_mm'] = axis.Shape.Length
            row['controle_nominal'] = check_pairs(cable.Shape,obstacles,0.0001)
        except (ValueError, RuntimeError) as error:
            row['erreur_nominale'] = str(error)
        finally:
            App.closeDocument(doc.Name)
        print('M8 variante',row['depart_droit_mm'],row['x_transition_mm'],len(row['poses_incompatibles']),flush=True)
    kinematics = read(OLD/'recherche_suspension.json')['kinematics']
    sa04 = 'sous_assemblages/SA04_Prototype_Perception.FCStd'
    moving_keys = {(sa04, key) for key in kinematics['mobile_sa04_occurrences']}
    moving_keys.update((SA,key) for key in kinematics['mobile_sa07_occurrences'])
    reader = Reader(BASE)
    for row in best:
        nominal = row.get('controle_nominal')
        if not nominal or nominal['recouvrements'] or nominal['inconnues']:
            continue
        row['essais_poses'] = []
        for key, pose in poses.items():
            d = App.newDocument('M8PoseVariante')
            test = {'id':key}
            try:
                cable, axis = make_native_cable(d,None,'M8',posed_points(row['points_mm'],pose),diameter,52)
                f16 = read(OLD/('autonomie_'+key+'.json'))
                if sha(BASE/f16['file']) != f16['sha256']:
                    raise RuntimeError('Empreinte F16 de pose non conforme')
                obstacles = {'#'.join(k):moved(shape,pose) if k in moving_keys else shape
                             for k,shape in shapes.items() if k not in {(SA,'F_M8'),(SA,'F16')}}
                for part in ('mobile','fixed'):
                    obstacles['F16_'+part] = reader.shape(f16['file'],f16['object_'+part])
                test.update(longueur_mm=axis.Shape.Length,
                            delta_longueur_mm=axis.Shape.Length-row['longueur_nominale_mm'],
                            paires=check_pairs(cable.Shape,obstacles,0.0001))
            except (ValueError, RuntimeError) as error:
                test['erreur'] = str(error)
            finally:
                App.closeDocument(d.Name)
            row['essais_poses'].append(test)
            print('M8 pose',row['depart_droit_mm'],row['x_transition_mm'],key,flush=True)
    write(HERE/'mobilite_variantes_m8.json',{'schema':'cartographe.refonte.mobilite-variantes-m8.v1',
          'finalized':True, 'installation_sha256':sha(HERE/'installation.json'), 'environment':environment,
          'portee':'Préfiltre natif de faisabilité R52, BRep nominal sur les quatre meilleurs candidats, puis BRep de toutes les poses pour les candidats passés au nominal. Longueur non imposée en mouvement. Aucun changement de la copie.',
          'poses':list(poses),'variantes':trials})


if __name__=='__main__':
    main()
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0)
