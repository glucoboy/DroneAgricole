"""Contrôle BREP en lecture seule des interfaces modifiées par ORCH-CAO-MASSE-1.

Lit les pièces actuelles et les placements canoniques du manifeste ; n'ouvre
et ne sauvegarde aucun document FreeCAD. Seule la preuve JSON voisine est écrite.
Les contacts géométriques ne sont jamais assimilés à une qualification physique.
"""
from pathlib import Path
import hashlib
import json
import math
from datetime import datetime, timezone
import FreeCAD as A
import Part
from read_brep_prototype import Reader

ROOT=Path(__file__).resolve().parents[4]
MEC=ROOT/'hardware/mecanique/cartographe'
VER=MEC/'verification'
OUT=VER/'orch_interfaces_equipements.json'
MANIFEST=MEC/'manifest.json'
EPS_VOLUME=1e-5
NEAR_MM=.3
FOCUS=['PM08','EQ_Basler_Occurrence','ObjectifFujinon','OrinFan','UART_isole','GNSS_Helical','SSD']


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def bbox(s):
    b=s.BoundBox
    return [b.XMin,b.YMin,b.ZMin,b.XMax,b.YMax,b.ZMax]


def overlap(a,b,tol=0):
    return all(min(getattr(a,k+'Max'),getattr(b,k+'Max'))+tol>=
               max(getattr(a,k+'Min'),getattr(b,k+'Min')) for k in 'XYZ')


def common(a,b):
    # Limiter les booléens au voisinage réel des pièces OEM composées.
    parts=b.Solids if len(b.Solids)>30 else [b]
    pieces=[];errors=[]
    for i,p in enumerate(parts):
        if overlap(a.BoundBox,p.BoundBox):
            try:
                c=a.common(p)
                if not c.isNull() and c.Volume>EPS_VOLUME:pieces.append(c)
            except Exception as e:errors.append({'solide':i,'erreur':str(e)})
    return pieces,errors


def distance_near(a,b):
    # Une distance globale au composé OEM de 2059 solides peut être très lente.
    # Tout solide à distance <= NEAR_MM possède nécessairement une AABB dont
    # l'écart selon chaque axe est <= NEAR_MM : cette présélection est conservative.
    if len(b.Solids)<=30:return a.distToShape(b)[0]
    candidates=[p for p in b.Solids if overlap(a.BoundBox,p.BoundBox,NEAR_MM)]
    return min((a.distToShape(p)[0] for p in candidates),default=None)


def classify(a,b,volume):
    names={a,b}
    if names=={'ObjectifFujinon','EQ_Basler_Occurrence'}:
        return 'engagement_et_appui_C_voulus' if volume<=EPS_VOLUME else 'interference_monture_a_resoudre'
    if 'OrinFan' in names and 'Holybro6XOrin' in names:
        return 'interface_thermique_et_fixations_internes_non_documentees'
    if 'SSD' in names and 'Holybro6XOrin' in names:
        return 'engagement_KeyM_candidat_non_valide'
    if names=={'OrinFan','F20'}:
        return 'depart_fan_reserve_non_qualifie'
    if any(x.startswith(('Vis','Rondelle','Ecrou','Collier')) for x in names):
        return 'interference_fixation_ou_retenue_a_examiner' if volume>EPS_VOLUME else 'contact_fixation_ou_retenue_candidat'
    if a=='GNSS_Helical' or b=='GNSS_Helical':
        return 'interference_modele_GNSS_a_examiner' if volume>EPS_VOLUME else 'contact_support_GNSS_candidat'
    if any(x.startswith('Cable/') for x in names):
        return 'interference_ou_depart_faisceau_a_examiner' if volume>EPS_VOLUME else 'contact_faisceau_candidat'
    return 'interference_geometrique_nominale' if volume>EPS_VOLUME else 'contact_ou_jeu_inferieur_0_3mm'


def actual_ports(rows):
    data={}
    def point(name,p):
        pose=A.Placement(A.Matrix(*rows[name]['matrice']))
        return list(pose.multVec(A.Vector(*p)))
    # Les coordonnées sont dans les repères locaux conservés des équipements.
    data['Basler']={
      'appui_objectif_mm':point('EQ_Basler_Occurrence',(0,0,10.570258993911898)),
      'axes_M3_centres_mm':[point('EQ_Basler_Occurrence',(x,-14.5,10.570258993911898-8.8)) for x in [-10.5,10.5]],
      'USB_face_centre_mm':point('EQ_Basler_Occurrence',(8.285,.525,10.570258993911898-42.8-.95)),
      'M8_face_centre_mm':point('EQ_Basler_Occurrence',(-5.8,-8.1,10.570258993911898-42.8-5.3)),
      'limite':'Centres cotés/repère conservé ; corps et profondeur des connecteurs restent déduits.'}
    data['OrinFan']={'axes_M2_centres_bas_mm':[point('OrinFan',(x,y,0)) for x in [-21.6,21.6] for y in [-14.4,14.4]],
      'diametre_nominal_M2_mm':2,'entraxe_mm':[43.2,28.8],
      'limite':'M2 du dissipateur ; profondeur filet et bride non documentées.'}
    data['GNSS']={'SMA_point_extreme_mm':point('GNSS_Helical',(-31.85,0,9.2)),
      'antenne_base_reservee_mm':point('GNSS_Helical',(0,0,22.9)),
      'axe_SMA_local':[-1,0,0],'axe_antenne_local':[0,0,1],'interface_valide':False,
      'limite':'Les axes sont orthogonaux et les bases distinctes ; aucun adaptateur n’est présent ni inventé.'}
    return data


def proposals(rows,shapes):
    changes=[]
    camera=shapes['EQ_Basler_Occurrence']
    for name in ['VisBasler0','VisBasler1']:
        target_z=-144.770258993911898
        delta=[0,0,target_z-rows[name]['matrice'][11]]
        matrix=list(rows[name]['matrice']);matrix[11]=target_z
        s=shapes[name].copy();s.translate(A.Vector(*delta))
        checks={n:s.common(shapes[n]).Volume for n in ['EQ_Basler_Occurrence','PlatineAluminium']}
        changes.append({'occurrence':name,'parent':rows[name]['parent'],
          'matrice_avant':rows[name]['matrice'],'matrice_apres':matrix,'translation_mm':delta,
          'applicable':True,'deja_appliquee':abs(delta[2])<1e-9,
          'applicable_sans_autre_modification':True,
          'justification':'Aligner le centre de vis à Z=-144,770258993912 du trou FrontII coté, au lieu de -144,75.',
          'verification_en_memoire':{'intersections_mm3':checks,'axes_coaxiaux_nominaux':True,
            'engagement_nominal_mm':3,'profondeur_taraudage_documentee_mm':4,
            'qualification':'Alignement géométrique ; filetage et tolérances non qualifiés.'}})
    delta=[-8,-6,0];matrix=list(rows['PM08']['matrice'])
    for i,dv in zip([3,7,11],delta):matrix[i]+=dv
    s=shapes['PM08'].copy();s.translate(A.Vector(*delta));collisions=[];near=[]
    for name,other in shapes.items():
        if name=='PM08' or not overlap(s.BoundBox,other.BoundBox,.3):continue
        pieces,errors=common(s,other);v=sum(x.Volume for x in pieces)
        if v>EPS_VOLUME:collisions.append({'occurrence':name,'intersection_mm3':v})
        elif name in ['OEM_Part__Feature085','UART_isole','Fusible_CA01']:
            near.append({'occurrence':name,'distance_mm':s.distToShape(other)[0]})
    near=[{'occurrence':n,'distance_mm':s.distToShape(shapes[n])[0]}
          for n in ['OEM_Part__Feature085','UART_isole','Fusible_CA01']]
    pose=A.Placement(A.Matrix(*matrix))
    holes=[list(pose.multVec(A.Vector(x,20.5,0))) for x in [-4.45,49.45]]
    sections=[]
    for p in holes:
        tool=Part.makeCylinder(1.7,20,A.Vector(p[0],p[1],25))
        section=tool.common(shapes['Isolation'])
        sections.append({'centre_XY_mm':p[:2], 'diametre_passage_candidat_mm':3.4,
          'bbox_matiere_support_interceptee_mm':None if section.isNull() else bbox(section)})
    pm08={'occurrence':'PM08','parent':rows['PM08']['parent'],
      'matrice_avant':rows['PM08']['matrice'],'matrice_apres':matrix,'translation_mm':delta,
      'applicable':False,
      'applicable_sans_autre_modification':False,
      'justification':'Pose candidate du boîtier OEM évitant colonne OEM, isolateur et protection CA01 ; aucune pièce ne change de référence.',
      'bbox_mm':bbox(s),'interferences_restantes_routes_actuelles':collisions,
      'structure_et_equipements_hors_faisceaux_sans_interference':all(x['occurrence'].startswith(('F38_','F05_','F06','F31','F32')) for x in collisions),
      'controles_proximite':near,
      'fixation_OEM':{'source':'Holybro_CAN_PM08_Case_v003.step',
        'centres_locaux_mm':[[-4.45,20.5,0],[49.45,20.5,0]],'centres_globaux_mm':holes,
        'entraxe_mm':53.9,'lumieres_largeur_mm':3.1,'lumieres_longueur_mm':8.1,
        'usinage_support_candidat':sections,
        'limite':'Diamètre3,4mm candidat de passage M3 cohérent avec règles CAO projet ; visserie, appuis, tolérances et maintien à définir par propriétaire fabrication.'},
      'ports_geometriques':{'sorties_X_moins_mm':[list(pose.multVec(A.Vector(.35,y,16.89512218961))) for y in [6.25,34.75]],
        'sorties_X_plus_mm':[list(pose.multVec(A.Vector(44.65,y,16.89512218961))) for y in [6.25,34.75]],
        'diametre_traverse_carter_mm':6.2,
        'limite':'Axes des passages de fils du boîtier seulement ; attribution électrique +/− et plans de sortie réels des fils non établis.'},
      'routes_a_reprendre':[{'id':n,'action':'Reprendre les départs/arrivées PM08 après pose et identification des sorties réelles ; recontrôler rayons, retenues et longueurs.'}
          for n in ['F38_POS','F38_NEG','F05_POS','F05_NEG','F06','F31','F32']],
      'conditions_integration':['Ne pas accepter les collisions F38 actuelles comme contacts voulus.',
        'Réconcilier diamètre6,5mm des volumes de câble avec passagesØ6,2 du boîtier : diamètre OEM réellement livré indispensable.',
        'PM08-CAN15029 et boîtier v003 doivent correspondre à la même révision.',
        'Créer et vérifier deux fixations sur P64 avec propriétaire fabrication ; aucun natif partagé écrit ici.']}
    changes.append(pm08)
    holy=shapes['Holybro6XOrin'];details={}
    for name in ['OrinFan','SSD']:
        a=shapes[name];hits=[]
        for i,solid in enumerate(holy.Solids):
            if not overlap(a.BoundBox,solid.BoundBox):continue
            c=a.common(solid)
            if c.Volume>EPS_VOLUME:
                hits.append({'solide_derive_index':i,'intersection_mm3':c.Volume,
                  'bbox_solide_mm':bbox(solid),'bbox_intersection_mm':bbox(c)})
        details[name]=hits
    target_x=-33.81
    fan_delta=[target_x-rows['OrinFan']['matrice'][3],0,0]
    fan_matrix=list(rows['OrinFan']['matrice']);fan_matrix[3]=target_x
    fan=shapes['OrinFan'].copy();fan.translate(A.Vector(*fan_delta));pc,_=common(fan,holy)
    before=[];after=[];new_defects=[]
    for name,other in shapes.items():
        if name=='OrinFan':continue
        volumes=[]
        for state in [shapes['OrinFan'],fan]:
            pieces,errors=common(state,other) if overlap(state.BoundBox,other.BoundBox) else ([],[])
            assert not errors,(name,errors)
            volumes.append(sum(x.Volume for x in pieces))
        if volumes[0]>EPS_VOLUME:before.append({'occurrence':name,'intersection_mm3':volumes[0]})
        if volumes[1]>EPS_VOLUME:after.append({'occurrence':name,'intersection_mm3':volumes[1]})
        if volumes[1]>volumes[0]+EPS_VOLUME:new_defects.append({'occurrence':name,'augmentation_mm3':volumes[1]-volumes[0]})
    fan_pose=A.Placement(A.Matrix(*fan_matrix))
    fan_axes=[list(fan_pose.multVec(A.Vector(x,y,0))) for x in [-21.6,21.6] for y in [-14.4,14.4]]
    screw_axes=[];screw_cylinders=[]
    for index in [1430,1431,1725,1726]:
        cylinders=[f.Surface for f in holy.Solids[index].Faces if isinstance(f.Surface,Part.Cylinder)
                   and abs(f.Surface.Radius-1)<1e-8 and abs(abs(f.Surface.Axis.z)-1)<1e-8]
        assert cylinders,('axe M2 OEM absent',index)
        surface=cylinders[0];screw_axes.append([surface.Center.x,surface.Center.y])
        screw_cylinders.append({'index_solide':index,'rayon_tige_mm':surface.Radius,
          'point_axe_mm':list(surface.Center),'direction':list(surface.Axis)})
    fan_cylinders=[]
    for face in fan.Faces:
        surface=face.Surface
        if isinstance(surface,Part.Cylinder) and abs(surface.Radius-1)<1e-8 and abs(abs(surface.Axis.z)-1)<1e-8:
            p=[surface.Center.x,surface.Center.y]
            if not any(math.hypot(p[0]-q[0],p[1]-q[1])<1e-8 for q in fan_cylinders):fan_cylinders.append(p)
    assert len(fan_cylinders)==4,('axes M2 fan',fan_cylinders)
    coaxial_errors=[min(math.hypot(p[0]-q[0],p[1]-q[1]) for q in screw_axes) for p in fan_cylinders]
    changes.append({'occurrence':'OrinFan','parent':rows['OrinFan']['parent'],
      'matrice_avant':rows['OrinFan']['matrice'],'matrice_apres':fan_matrix,'translation_mm':fan_delta,
      'applicable':True,'deja_appliquee':abs(fan_delta[0])<1e-9,
      'applicable_sans_autre_modification':True,
      'justification':'Aligner les quatre trous M2 du plan Waveshare sur les axes des vis du modèle Holybro ; correction indépendante de pose nominale.',
      'sources_axes':{'fan_plan_id':'FAN_DRAWING','fan_plan_fichier':'sources_fabricants/orch_cao_masse_equipements/Waveshare_Orin_FAN_PWM_dimensions.jpg',
        'fan_entraxes_mm':[43.2,28.8],'tolerance_entraxes_documentee_mm':.05,
        'fan_axes_locaux_mm':[[x,y,0] for x in [-21.6,21.6] for y in [-14.4,14.4]],
        'holybro_source':'sources_fabricants/Pixhawk-Jetson-Baseboard-3D.stp',
        'holybro_preuve_source':'verification/holybro_stack_source_20261001.json',
        'holybro_source_sha256_attendue':'dfee72717b735c4b10089435ae1019482878f6607051f1a3b8397da7721ed6ee',
        'holybro_derivee':rows['Holybro6XOrin']['source'],
        'holybro_indices_solides_vis':[[1430,1740],[1431,1741],[1725,2035],[1726,2036]],
        'axes_vis_globaux_XY_mm':screw_axes,'surfaces_cylindriques_mesurees':screw_cylinders,
        'limite':'Axes mesurés dans le BREP OEM conservé ; correspondance de révision commerciale Holybro à confirmer.'},
      'verification_en_memoire':{'axes_fan_globaux_mm':fan_axes,'axes_fan_mesures_BREP_XY_mm':fan_cylinders,
        'ecarts_coaxialite_XY_mm':coaxial_errors,
        'intersections_avant_mm3':before,'intersections_apres_mm3':after,'nouveaux_defauts_induits':new_defects,
        'interface_fixation_nominale_conforme':max(coaxial_errors)<1e-8 and sum(x.Volume for x in pc)<EPS_VOLUME and not new_defects},
      'limites':['F20 demeure un départ réservé non qualifié, recouvrant le carter sur 1,5 mm ; coordonnées et sortie OEM non documentées.',
        'Le contrôle nominal ne qualifie ni tolérances cumulées, ni serrage, ni interfaces thermiques, ni révision matérielle.']})
    details['interpretation_fan']={'doublons_OEM_detectes':[[1430,1740],[1431,1741],[1725,2035],[1726,2036]],
      'corps_en_conflit':'Quatre vis OEM avec têtesØ4,7 et axe de tigeØ2 ; chacune est géométriquement dupliquée dans la porteuse dérivée.',
      'axes_vis_globaux_mm':screw_axes,
      'dessus_tetes_Z_mm':143.61443237557717,
      'pose_cible_X_mm':target_x,
      'translation_qui_aligne_axes_M2_mm':fan_delta,
      'intersection_apres_alignement_axes_mm3':sum(x.Volume for x in pc),
      'correction_pose_applicable':True,
      'interpretation':'L’alignement des axes supprime entièrement l’intersection avec les quatre vis. Aucun agrandissement des trous ni remplacement des vis OEM n’est proposé.',
      'information_necessaire':'Plan de montage, profondeur des taraudages et géométrie de sortie F20 Waveshare pour qualifier le montage complet.'}
    details['interpretation_ssd']={'corps_en_conflit':'Solide1401, connecteur M.2 KeyM de la porteuse ; aucun autre solide ne recoupe le SSD.',
      'qualification':'Engagement candidat de la languette du PCB ; profilKeyM/contact exact et épaisseurPCB inconnus empêchent de valider l’accouplement.',
      'correction_autorisee':False}
    return changes,details


def main():
    manifest_bytes=MANIFEST.read_bytes()
    manifest=json.loads(manifest_bytes.decode('utf-8-sig'))['prototype_cartographe']
    rows=[r for r in manifest['occurrences'] if r['parent'].startswith('sous_assemblages/')]
    keyed={r['occurrence']:r for r in rows}
    assert set(FOCUS).issubset(keyed)
    paths={str(MANIFEST.relative_to(ROOT)),str(Path(__file__).relative_to(ROOT))}
    for p in ['sources_fabricants/orch_cao_masse_equipements/Waveshare_Orin_FAN_PWM_dimensions.jpg',
              'sources_fabricants/Pixhawk-Jetson-Baseboard-3D.stp',
              'verification/holybro_stack_source_20261001.json']:
        paths.add(str((MEC/p).relative_to(ROOT)))
    for row in rows:paths.add(str((MEC/row['source']).relative_to(ROOT)))
    routes_path=VER/'routes_prototype.json';routes_already_covered=[];extra_routes=[];routes_bytes=None
    if routes_path.exists():
        routes_bytes=routes_path.read_bytes();routes=json.loads(routes_bytes.decode('utf-8-sig'))
        paths.add(str(routes_path.relative_to(ROOT)))
        for row in routes['routes']:
            if row['id'] in keyed and keyed[row['id']]['source']==row['fichier']:
                routes_already_covered.append(row['id'])
                continue
            paths.add(str((MEC/row['fichier']).relative_to(ROOT)));extra_routes.append(row)
    inputs={p.replace('\\','/'):sha(ROOT/p) for p in sorted(paths)}
    # Le manifeste et les routes sont hachés depuis les octets réellement lus.
    # Les autres empreintes sont capturées AVANT les lectures BREP.
    inputs[str(MANIFEST.relative_to(ROOT)).replace('\\','/')]=hashlib.sha256(manifest_bytes).hexdigest()
    if routes_bytes is not None:
        inputs[str(routes_path.relative_to(ROOT)).replace('\\','/')]=hashlib.sha256(routes_bytes).hexdigest()
    reader=Reader(MEC);shapes={};errors=[]
    for row in rows:
        name=row['occurrence']
        try:shapes[name]=reader.occurrence(row)
        except Exception as e:errors.append({'occurrence':name,'lecture':str(e)})
    for row in extra_routes:
        name='Cable/'+row['id']
        try:shapes[name]=reader.shape(row['fichier'],row['objet_cable'])
        except Exception as e:errors.append({'occurrence':name,'lecture':str(e)})
    pairs=[];seen=set();tests=0
    for name in FOCUS:
        a=shapes[name]
        for other,b in shapes.items():
            key=tuple(sorted([name,other]))
            if other==name or key in seen:continue
            seen.add(key)
            if not overlap(a.BoundBox,b.BoundBox,NEAR_MM):continue
            tests+=1
            pieces,failures=common(a,b);volume=sum(x.Volume for x in pieces)
            distance=None
            if volume<=EPS_VOLUME:
                try:distance=distance_near(a,b)
                except Exception as e:failures.append({'distance':str(e)})
            if failures:errors.append({'a':name,'b':other,'booleen':failures})
            if volume>EPS_VOLUME or distance is not None and distance<=NEAR_MM:
                item={'a':name,'b':other,'intersection_mm3':volume,'distance_mm':distance,
                      'classe':classify(name,other,volume)}
                if pieces:item['bbox_intersection_mm']=bbox(Part.makeCompound(pieces))
                pairs.append(item)
        print(name+' : '+str(len(pairs))+' contacts/interférences cumulés',flush=True)
    changes,details=proposals(keyed,shapes)
    reprise_path=VER/'controle_reprise_collisions.json'
    reprise=json.loads(reprise_path.read_text('utf-8')) if reprise_path.exists() else {}
    if reprise.get('correction_geometrique_conforme'):
        changes=[row for row in changes if row.get('occurrence')!='PM08']
    result={'schema_version':'drone-agricole.orch-interfaces-equipements.v1',
      'lot':'ORCH-CAO-MASSE-1','date_utc':datetime.now(timezone.utc).isoformat(),
      'configuration':'prototype_cartographe','statut':'À valider',
      'environnement':{'os':'Windows','architecture':'amd64','freecad':A.Version()},
      'protocole':'Pièces FCStd actuelles, BREP sauvegardés et placements du manifeste ; aucun assemblage ni natif écrit. Présélection AABB augmentée de0,3mm puis booléens et distances BREP.',
      'entrees_sha256':inputs,'nombre_occurrences':len(rows),'formes_lues':len(shapes),
      'routes_deja_couvertes_par_occurrences':routes_already_covered,
      'tests_brep':tests,'seuil_numerique_volume_mm3':EPS_VOLUME,
      'focus':[{'occurrence':n,'source':keyed[n]['source'],'objet_source':keyed[n]['objet_source'],
                'bbox_mm':bbox(shapes[n]),'forme_valide':shapes[n].isValid()} for n in FOCUS],
      'interfaces':actual_ports(keyed),'contacts_et_interferences':pairs,'erreurs':errors,
      'modifications_occurrences':changes,'analyse_solides_Holybro':details,
      'blocages_interfaces':[
        {'id':'PM08-POSE-FIXATION-PORTS','occurrences':['PM08','UART_isole','Fusible_CA01','OEM_Part__Feature085','F38_POS','F38_NEG'],
         'information_fabricant_necessaire':'Correspondance PM08-CAN livré (15029 ou variante exacte) avec boîtier v003 ; plans et coordonnées des sorties +/−, BEC1/BEC2/CAN ; diamètre extérieur et longueur nette des fils livrés.',
         'travail_projet_necessaire':'Pose, routes extérieures et deux fixations P64 corrigées dans controle_reprise_collisions.json. Restent les interfaces internes, diamètres réels8AWG, tolérances, engagement des contacts et tenue physique.'},
        {'id':'FAN-SORTIE-F20','occurrences':['OrinFan','F20'],
         'information_fabricant_necessaire':'Coordonnées et direction du départ réel PWM, rayon de courbure et géométrie connecteur ; profondeur utile des taraudages M2 et plan de montage.'},
        {'id':'SSD-KEYM','occurrences':['SSD','Holybro6XOrin'],
         'information_fabricant_necessaire':'Référence du connecteur Key M de la révision Holybro retenue, modèle/plan d’engagement, épaisseur et profil exacts de languette Samsung. Le volume intersecté correspond au PCB dans le connecteur, sans validation des contacts.'},
        {'id':'BASLER-PRISES','occurrences':['EQ_Basler_Occurrence','ConnecteurF16Camera','ConnecteurM8Camera'],
         'information_fabricant_necessaire':'Plans exacts des connecteurs mâles retenus et des interfaces USB3 Micro-B à vis / M8 A6 femelles : volumes d’engagement, épaulements, détrompeurs et dégagements. Les très faibles distances mesurées ne valident pas le branchement.'},
        {'id':'GNSS-SMA','occurrences':['GNSS_Helical'],
         'information_fabricant_necessaire':'Identifier la révision G4/S32K1 et l’antenne effectivement livrée ; plan SMA de l’antenne et orientation du montage direct possible. La réservation verticale actuelle ne s’accouple pas au SMA horizontal ; aucun adaptateur inventé.'}],
      'sources_inchangees_pendant_controle':all(sha(ROOT/p)==digest for p,digest in inputs.items()),
      'absence_interferences_demontree':False,'qualification_physique':False,
      'conclusion_controle':'Reprise PM08/QS8/F20 contrôlée séparément sur BREP sauvegardés dans controle_reprise_collisions.json ; interfaces réelles, engagements SSD et GNSS encore À valider. Les limites de raccordement ne deviennent pas des interfaces fabricant.',
      'limites':['Les volumes d’intersection sont des diagnostics géométriques, pas des masses ni des volumes matériau fiables.',
                 'Une enveloppe de boîtier fermé peut recouvrir des interfaces internes inconnues ; ces cas restent À valider.',
                 'La proximité géométrique ne prouve ni un accouplement, ni une fixation, ni une connexion électrique.',
                 'Les anciens exports/assemblages sauvegardés peuvent être périmés ; seules pièces actuelles et poses référencées sont évaluées.']}
    OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'preuve':str(OUT),'contacts':len(pairs),'erreurs':len(errors)},ensure_ascii=True),flush=True)


if __name__=='__main__':main()
