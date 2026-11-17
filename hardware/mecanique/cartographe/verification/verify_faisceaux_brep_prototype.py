"""Contrôle OCCT des formes sauvegardées, sans document ni scène graphique.

Complète le recalcul natif Cable Workbench acquis séparément, avec empreintes
identiques exigées. Les obstacles sont chargés un par un pour borner la mémoire.
"""
from pathlib import Path
from datetime import datetime, timezone
import itertools
import json
import sys
import traceback
import FreeCAD as App
import Part
from read_brep_prototype import Reader
from verify_faisceaux_prototype import (MEC, VER, OUTPUT, sha, overlap, intersection,
    sample_wire, point_box_distance, box_values, VOLUME_TOL, FAR_DISTANCE,
    END_ZONE, SAMPLE_STEP, AIRY_JUNCTION, progress)

RUNTIME = MEC.parents[2] / '.runtime/faisceau_structure'
CACHE = RUNTIME / 'geometrie_native_acquise.json'
PROGRESS = RUNTIME / 'controle_brep_progression.json'


def save(data, path=PROGRESS):
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')


def run():
    reader = Reader(MEC)
    build_path, routes_path = VER/'construction_prototype.json', VER/'routes_prototype.json'
    build_hash, routes_hash = sha(build_path), sha(routes_path)
    build = json.loads(build_path.read_text('utf-8'))
    routes = json.loads(routes_path.read_text('utf-8'))
    native = json.loads(CACHE.read_text('utf-8'))
    if not build.get('finalisation_correcte') or native['construction_sha256'] != build_hash:
        raise RuntimeError('Recalcul natif acquis absent ou périmé.')
    files = {r['fichier']: r['sha256'] for r in build['references']}
    files.update(build['sources_preservees'])
    if any(sha(MEC/p) != h for p,h in files.items()):
        raise RuntimeError('Natif modifié depuis la construction.')
    errors = list(native['erreurs_geometrie_registres'])
    if len(native['geometrie_longueurs']) != len(routes['routes']):
        raise RuntimeError('Recalcul incomplet.')
    # Comparer chaque forme BRep au volume et à la longueur issus du constructeur.
    # Contrairement aux boîtes GUI triangulées, BoundBox BRep peut être conservatrice.
    cables = {}
    occurrences = build['occurrences']
    for row in routes['routes']:
        shape = reader.shape(row['fichier'], row['objet_cable'])
        wire = reader.shape(row['fichier'], row['objet_parcours']).Wires[0]
        if abs(shape.Volume-row['volume_mm3']) > 1e-4 or abs(wire.Length-row['longueur_courbe_mm']) > 1e-4:
            raise RuntimeError('Extraction différente de la géométrie native : '+row['id'])
        occurrence = next(o for o in occurrences if 'SA07_' in o['parent'] and o['occurrence']==row['id'])
        if not App.Placement(App.Matrix(*occurrence['matrice'])).isIdentity():
            raise RuntimeError('Occurrence câble transformée non prise en charge.')
        cables[row['id']] = dict(row=row, shape=shape, wire=wire)
    report = dict(date_utc=datetime.now(timezone.utc).isoformat(),
        script_sha256=sha(__file__), lecteur_sha256=sha(Path(__file__).with_name('read_brep_prototype.py')),
        construction_sha256=build_hash, routes_sha256=routes_hash,
        recalcul_natif_acquis_sha256=sha(CACHE), natifs_sha256=files,
        geometrie_longueurs=native['geometrie_longueurs'], nombre_cables=len(cables),
        erreurs_geometrie_registres=errors, collisions_cables_physique=[],
        collisions_cable_cable=[], jonctions_airy_localisees=[],
        eloignements_a_revoir=[], distances_echantillonnees=[],
        obstacles_bboxes_mm=[], finalisation_correcte=False,
        protocole={'lecture':'BRep des FCStd empreintés, placement local retiré puis matrice de lien appliquée ; groupes visibles sauvegardés',
                  'collision':'Intersections OCCT, aucune exemption câble/équipement ; sous-solides OEM détaillés',
                  'seuil_volume_mm3':VOLUME_TOL,
                  'distance':'Distances exactes points/solides OEM, supports fabriqués et guides ; échantillonnage des axes',
                  'pas_max_mm':SAMPLE_STEP,'signal_eloignement_mm':FAR_DISTANCE,
                  'longueur_zone_terminale_mm':END_ZONE,
                  'colonnes_echantillons':['s_mm','x_mm','y_mm','z_mm','distance_axe_support_mm','support','zone_terminale']},
        qualification='À valider')
    save(report)
    supports=[]
    physical=[o for o in occurrences if o['parent'].startswith('sous_assemblages/') and
              not ('SA07_' in o['parent'] and o['occurrence'] in cables)]
    for index, row in enumerate(physical,1):
        name=Path(row['parent']).stem+'/'+row['occurrence']
        _, objects=reader.xml(row['parent'])
        props=objects[row['occurrence']]
        if props['LinkTransform'].find('Bool').get('value')!='false':
            raise RuntimeError('LinkTransform=True inattendu : '+name)
        actual_pose=reader.placement(row['parent'],row['occurrence']).toMatrix().A
        if max(abs(x-y) for x,y in zip(actual_pose,row['matrice']))>1e-6:
            raise RuntimeError('Placement du registre différent du natif : '+name)
        shape=reader.occurrence(row)
        report['obstacles_bboxes_mm'].append(dict(obstacle=name,bbox_mm=box_values(shape)))
        for cable_id, item in cables.items():
            volume, solids, boxes=intersection(item['shape'],shape)
            if volume>VOLUME_TOL:
                collision=dict(cable=cable_id,obstacle=name,volume_mm3=round(volume,5),
                               solides_locaux=solids,bbox_intersections_mm=boxes)
                report['collisions_cables_physique'].append(collision)
                progress('collision',**collision)
        if ('SA01_' in row['parent'] and row['occurrence'].startswith('OEM_')) or \
                ('/fabriquees/' in row['source'] and row['occurrence']!='CA01') or 'SA07_' in row['parent']:
            supports.extend((name,s) for s in shape.Solids)
        report.update(etape='collisions_physique',obstacles_controles=index,nombre_obstacles=len(physical))
        save(report)
        if index%10==0:progress('obstacles',controle=index,total=len(physical),collisions=len(report['collisions_cables_physique']))
    report['nombre_solides_supports']=len(supports)
    progress('collisions_physique_terminees',nombre=len(report['collisions_cables_physique']))
    for index, ((name_a,a),(name_b,b)) in enumerate(itertools.combinations(cables.items(),2),1):
        if not overlap(a['shape'].BoundBox,b['shape'].BoundBox):continue
        common=a['shape'].common(b['shape'])
        if common.Volume<=VOLUME_TOL:continue
        outside=common
        if name_a in AIRY_JUNCTION and name_b in AIRY_JUNCTION:
            ends_a=[a['wire'].Vertexes[0].Point,a['wire'].Vertexes[-1].Point]
            ends_b=[b['wire'].Vertexes[0].Point,b['wire'].Vertexes[-1].Point]
            shared=[u for u in ends_a if any((u-v).Length<1e-5 for v in ends_b)]
            radius=max(a['row']['diametre_mm'],b['row']['diametre_mm'])
            for point in shared:outside=outside.cut(Part.makeSphere(radius,point))
            if shared:report['jonctions_airy_localisees'].append(dict(a=name_a,b=name_b,
                points_communs_mm=[[p.x,p.y,p.z] for p in shared],rayon_zone_locale_mm=radius,
                volume_local_mm3=round(common.Volume-outside.Volume,5),statut='Jonction nominale Airy ; connecteur réel À valider'))
        if outside.Volume>VOLUME_TOL:
            collision=dict(a=name_a,b=name_b,volume_total_mm3=round(common.Volume,5),
                           volume_hors_jonction_mm3=round(outside.Volume,5),bbox_mm=box_values(outside))
            report['collisions_cable_cable'].append(collision)
            progress('collision_cable_cable',**collision)
        report.update(etape='collisions_cable_cable',paires_controlees=index)
        save(report)
    progress('collisions_cable_cable_terminees',nombre=len(report['collisions_cable_cable']))
    bounds=[s.BoundBox for _,s in supports]
    for index,(cable_id,item) in enumerate(cables.items(),1):
        rows,far=[],[]
        for position,point in sample_wire(item['wire']):
            ordered=sorted((point_box_distance(point,b),i) for i,b in enumerate(bounds))
            best,nearest=float('inf'),None
            vertex=Part.Vertex(point)
            for lower,i in ordered:
                if lower>best+1e-5:break
                distance=vertex.distToShape(supports[i][1])[0]
                if distance<best:best,nearest=distance,supports[i][0]
            terminal=min(position,item['wire'].Length-position)<=END_ZONE+1e-5
            r=[round(position,2),round(point.x,2),round(point.y,2),round(point.z,2),round(best,2),nearest,terminal]
            rows.append(r)
            if best>FAR_DISTANCE:far.append(dict(s_mm=r[0],point_mm=r[1:4],distance_mm=r[4],zone_terminale=terminal))
        report['distances_echantillonnees'].append(dict(cable=cable_id,table=rows))
        if far:report['eloignements_a_revoir'].append(dict(cable=cable_id,
            points_lointains_corps=sum(not p['zone_terminale'] for p in far),
            points_lointains_terminaisons=sum(p['zone_terminale'] for p in far),points=far))
        report.update(etape='distances',cables_distances_controles=index)
        save(report)
        if index%5==0:progress('distances',cables=index,eloignes=len(report['eloignements_a_revoir']))
    changed=[p for p,h in files.items() if sha(MEC/p)!=h]
    report['fichiers_non_modifies']=not changed and sha(build_path)==build_hash and sha(routes_path)==routes_hash
    if not report['fichiers_non_modifies']:errors.append(dict(type='fichiers_modifies_pendant_controle',fichiers=changed))
    report['finalisation_correcte']=True
    report['conclusion']='Intersections ou erreurs à corriger' if errors or report['collisions_cables_physique'] or report['collisions_cable_cable'] else 'Contrôles géométriques déclarés réussis ; intégration physique À valider'
    report['limites']=['Surplus catalogue issu du recalcul ; rangement et connecteurs à confirmer sur matériel.',
                      'Échantillonnage indicatif des distances, pas une preuve de retenue continue.',
                      'Abrasion, vibration, serrage et rayons admissibles fabricant non qualifiés.',
                      'Toutes les intersections équipement sont signalées, y compris connecteurs représentés pleins.']
    save(report,OUTPUT);save(report)
    progress('final',conclusion=report['conclusion'],physique=len(report['collisions_cables_physique']),cables=len(report['collisions_cable_cable']))


if __name__=='__main__':
    try:run()
    except Exception:
        traceback.print_exc()
        sys.exit(2)
