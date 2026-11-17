"""Contrôle les volumes modifiés sur les poses documentées et sonde le M8."""
import os
import sys
import traceback

from adapter_freecad import (
    App, BASE, COPY, HERE, OLD, Part, Reader, SA, boot, cable_geometry,
    check_pairs, fresh_solid, make_native_cable, read, require, scene, sha, write,
)


def pose_transform(parameters):
    tx = App.Vector(*parameters['translation_mm'])
    pivot = App.Vector(*parameters['rotation_center_mm'])
    a, b, c = parameters['rotation_xyz_deg']
    rotation = App.Rotation(App.Vector(0,0,1), c).multiply(
        App.Rotation(App.Vector(0,1,0), b)).multiply(App.Rotation(App.Vector(1,0,0), a))
    return App.Placement(pivot+tx-rotation.multVec(pivot), rotation)


def moved(shape, pose):
    copy = shape.copy()
    copy.Placement = pose.multiply(copy.Placement)
    return copy


def run():
    proof = read(HERE / 'installation.json')
    graph = read(HERE / 'graphe_physique.json')
    require(sha(HERE / 'graphe_physique.json')==proof['graphe_sha256'], 'Graphe différent de la copie')
    before_reader = Reader(BASE)
    _, routes, shapes, _ = scene(COPY)
    kinematics = read(OLD / 'recherche_suspension.json')['kinematics']
    sa04 = 'sous_assemblages/SA04_Prototype_Perception.FCStd'
    mobile = {(sa04,key):shapes[(sa04,key)] for key in kinematics['mobile_sa04_occurrences']}
    mobile.update({(SA,key):shapes[(SA,key)] for key in kinematics['mobile_sa07_occurrences']})
    additions = {s['occurrence']:shapes[(SA,s['occurrence'])] for s in graph['gaines']}
    additions.update({cid:shapes[(SA,cid)] for cid in proof['parcours_modifies']})
    for guide in proof['guides_modifies'].values():
        require(guide['volume_ajoute_mm3']<=0.0001, 'Le guide a des ajouts à vérifier en mouvement')
    pose_data = read(OLD / 'poses_autonomie.json')['candidates']
    outputs = []
    for row in pose_data:
        key = row['id']
        data = read(OLD / ('autonomie_' + key + '.json'))
        require(data['complete'] and data['collision']['complete'] and
                sha(BASE/data['file'])==data['sha256'], 'Preuve F16 différente du natif de pose ' + key)
        pose = pose_transform(row)
        moving = {'#'.join(k):moved(s,pose) for k,s in mobile.items()}
        for side in ('mobile','fixed'):
            moving['F16_'+side] = before_reader.shape(data['file'],data['object_'+side])
        checks = {name:check_pairs(s,moving,0.0001) for name,s in additions.items()}
        outputs.append({'id':key,'translation_mm':row['translation_mm'],'rotation_xyz_deg':row['rotation_xyz_deg'],
                        'sha256_f16_pose':data['sha256'],'controle':checks})
    environment = boot()
    m8 = routes['F_M8']
    chosen = {'POSE_NOMINAL','POSE_AXE_1','POSE_AXE_2','POSE_AXE_3','POSE_AXE_4','POSE_AXE_5','POSE_AXE_6',
              'POSE_AXE_7','POSE_AXE_8','POSE_AXE_9','POSE_AXE_10','POSE_AXE_11','POSE_AXE_12',
              'POSE_COMB_13','POSE_COMB_20','POSE_SOUS_CHARGE'}
    m8_checks = []
    for row in pose_data:
        if row['id'] not in chosen:
            continue
        pose = pose_transform(row)
        # Seuls les deux points imposant la sortie de la fiche sont entraînés.
        # Ce sondage de sensibilité ne résout pas l'équilibre d'un câble de longueur fixée.
        points = [list(p) for p in m8['points_mm']]
        for index in (0,1):
            points[index] = list(pose.multVec(App.Vector(*points[index])))
        d = App.newDocument('EssaiM8')
        result = {'id':row['id'],'generation':None}
        try:
            cable, _ = make_native_cable(d,None,'M8',points,m8['diametre_mm'],52)
            geom = cable_geometry(cable)
            result.update(generation='pass',length_mm=geom['longueur_courbe_mm'],
                          length_delta_mm=geom['longueur_courbe_mm']-m8['longueur_courbe_mm'],
                          radius_mm=min(geom['rayons_arcs_mm']))
            # Voisinage mobile, supports P78/P75 et tout nouveau volume.
            # La collision globale nominale est couverte par la recette séparée.
            obstacles = {'#'.join(k):moved(s,pose) for k,s in mobile.items()}
            f16 = read(OLD / ('autonomie_' + row['id'] + '.json'))
            for side in ('mobile','fixed'):
                obstacles['F16_'+side] = before_reader.shape(f16['file'],f16['object_'+side])
            obstacles.update(additions)
            for name in ('P78_RetenueCameraM8','P75_Cadre'):
                obstacles[name] = shapes[(SA,name)]
            result['paires'] = check_pairs(cable.Shape,obstacles,0.0001)
        except (ValueError, RuntimeError) as error:
            result.update(generation='fail',erreur=str(error))
        finally:
            App.closeDocument(d.Name)
        m8_checks.append(result)
        print('M8',row['id'],result['generation'],flush=True)
    write(HERE / 'mobilite.json', {'schema':'cartographe.refonte-mobilite.v1','finalized':True,
            'installation_sha256':sha(HERE / 'installation.json'), 'environment':environment,
            'scope_f16':'Contrôle différentiel des nouveaux volumes contre F16 et les 31 volumes mobiles. Les collisions rigides de référence et la course réelle restent ouvertes.',
            'scope_m8':'Sensibilité à 16 poses discrètes, sortie de fiche transformée, points fixes conservés. Rayon cible 52 mm, longueur libre. Absence d’essai de traction, torsion, pince, cycles ou amplitude admissible.',
            'f16':outputs,'m8':m8_checks,'validation_physique':'not_executed'})


if __name__=='__main__':
    try:
        run()
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(0)
    except Exception:
        traceback.print_exc()
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(2)
