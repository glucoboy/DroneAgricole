"""Compléments natifs de retenue P72/P75 et berceau USB indépendant.

Ce module ne charge ni ne réécrit les pièces existantes. La fonction reçoit le
dernier résultat natif des guides et le prolonge par des primitives éditables. Les
coordonnées concernent les candidats de faisceau de la passe 9 ; toute reprise
du tracé impose un nouveau contrôle câble/support et câble/câble.
"""
import json
import math
import FreeCAD as A


def extend_top_guide(api, document, root, base, include_f41=True):
    """Ajouter le peigne MAIN et, en option, les retenues de sortie USB F41.

    Renvoie (résultat natif, interfaces). Les appuis F41 sur P72 sont des contacts
    terminaux plans à serrer par collier, jamais des collages sur électronique.
    Aucun changement des parcours ou des fixations P66 n'est fait ici.
    """
    members = []
    stations = []

    def bar(name, start, end, diameter=4.0):
        delta = A.Vector(*end) - A.Vector(*start)
        if delta.Length < 1e-6:
            raise ValueError('Retenue sans longueur : '+name)
        obj = api.cylinder(document, name, diameter/2, delta.Length, start)
        obj.Placement.Rotation = A.Rotation(A.Vector(0,0,1),delta)
        members.append(obj)
        return obj

    # Les quatre centres sont coplanaires : Z-Y=200. Le dessus de l'appui est
    # parallèle, Z-Y=198,5, donc jeu normal 1,5/sqrt(2)-0,8 = 0,261 mm.
    # La tablette s'arrête X90 avant le départ des quatre coudes R5.
    comb = api.box(document,'PeigneMAINIncline',(14,18,2),
                   (76,-36,198.5-36-2*math.sqrt(2)))
    comb.Placement.Rotation = A.Rotation(A.Vector(1,0,0),45)
    members.append(comb)
    # X89 laisse libres F24C (X78/Z153) et F31 (X85/Z158).
    # Les deux traverses de pied sont sous ces câbles, au niveau de P75.
    bar('PontPeigneAvant',(80,-34,145),(89,-34,145))
    bar('PontPeigneArriere',(80,-28,145),(89,-28,145))
    bar('AppuiPeigneAvant',(89,-34,145),(89,-34,162.5))
    bar('AppuiPeigneArriere',(89,-28,145),(89,-28,168.5))
    for x in [79,84.3]:
        stations.append({'id':'MAIN_'+str(x),'cables':['F04_1','F04_2','F04_3','F04_4'],
            'point_mm':[x,-32.5,167.5],'type':'collier commun autour tablette et quatre fils',
            'largeur_collier_mm':4.6,'acces':'passage sous tablette incliné, entre les deux appuis',
            'support':'P75/PeigneMAINIncline'})
    if include_f41:
        # Guidage à 4,7 mm de l'axe du câble Ø5 ; support rond Ø4 : jeu 0,2 mm.
        # Les appuis se terminent avant les coudes : aucun angle vif n'est
        # substitué au rayon R20 Cable Workbench.
        bar('MontanteF41',(-107.3,56,58),(-107.3,56,96))
        bar('RepriseP72Bas',(-107.3,56,60),(-90,56,60))
        bar('RepriseP72Haut',(-107.3,56,85),(-90,56,85))
        slope_end_z = 113 + (56+68)*18.5/144
        bar('LongeF41',(-107.3,56,113),(-107.3,-68,slope_end_z))
        bar('RaccordMontanteF41',(-107.3,56,94),(-107.3,56,114))
        bar('RepriseP75Gauche',(-107.3,55,112),(-80,55,112))
        bar('TraverseF41',(-90,-83.3,131.5),(-13,-83.3,131.5))
        bar('RepriseTraverseF41Gauche',(-70,-83.3,131.5),(-70,-55,145))
        bar('RepriseTraverseF41Droite',(-20,-83.3,131.5),(-20,-55,145))
        for z in [64,85]:
            stations.append({'id':'F41_M_'+str(z),'cables':['F41'],
                'point_mm':[-112,56,z],'type':'collier autour longe ronde et câble',
                'largeur_collier_mm':4.6,'support':'P75/MontanteF41'})
        for y in [30,0,-30,-60]:
            stations.append({'id':'F41_L_'+str(y),'cables':['F41'],
                'point_mm':[-112,y,113+(56-y)*18.5/144],
                'type':'collier autour longe ronde et câble','largeur_collier_mm':4.6,
                'support':'P75/LongeF41'})
        for x in [-75,-45,-15]:
            stations.append({'id':'F41_T_'+str(x),'cables':['F41'],
                'point_mm':[x,-88,131.5],'type':'collier autour traverse ronde et câble',
                'largeur_collier_mm':4.6,'support':'P75/TraverseF41'})
    union=document.addObject('Part::MultiFuse','P75AvecRetenues')
    union.Shapes=[base]+members
    union.Refine=True
    if base in root.Group:
        root.removeObject(base)
    root.addObject(union)
    document.recompute()
    for obj in [base]+members:
        obj.Visibility=False
    union.Visibility=True
    api.color(union,(.34,.38,.43))
    spec={'peigne':{'cables':['F04_'+str(i) for i in range(1,5)],
            'surface':'Z-Y=198,5 ; normale à 45 degrés ; X76..90',
            'jeu_normal_cable_mm':round(1.5/math.sqrt(2)-.8,4),
            'colliers_communs':2,'appuis_P75_mm':[[80,-34,145],[80,-28,145]]},
          'f41_sortie':{'active':include_f41,'colliers_cable':9 if include_f41 else 0,
            'colliers_liaison_P72':2 if include_f41 else 0,
            'surfaces_contact_P72_mm':[[-90,56,60],[-90,56,85]] if include_f41 else [],
            'jeu_nominal_cable_support_mm':.2},
          'stations':stations,
          'comptage':{'SA07_colliers_cables':len(stations),
            'SA07_colliers_appui_P72':2 if include_f41 else 0,
            'vis_supplementaires':0},
          'hors_perimetre':['F16 et F_M8 en cours de reprise par le constructeur',
            'Entrée F41 et bobine : fonctions extend_left_guide et build_usb_reserve_cradle séparées'],
          'limites':['PA12 candidat ; procédé, fluage, rigidité des longes et résistance vibratoire non qualifiés.',
            'Colliers 4,6 mm autour des barres ; ne pas écraser les gaines USB ni bloquer leur maintenance.',
            'Rayons des câbles conservés ; ébavurage/adoucissement des surfaces de contact requis.',
            'Finition, tolérances de fabrication et serrage à vérifier sur pièce réelle.'],
          'qualification':'À valider'}
    api.meta(root,'RetenuesComplements',json.dumps(spec,ensure_ascii=False))
    return union,spec


def extend_left_guide(api, document, root, base):
    """Prolonger P72 par les appuis de l'entrée F41, sans toucher au câble.

    Les longes sont dans un plan décalé de 4,7 mm de l'axe USB. Deux bras
    rejoignent l'âme de P72 et une traverse suit l'entrée basse vers la réserve.
    Les coudes R20 restent libres et les colliers prennent les parties droites.
    """
    members=[]
    def bar(name,start,end):
        delta=A.Vector(*end)-A.Vector(*start)
        obj=api.cylinder(document,name,2,delta.Length,start)
        obj.Placement.Rotation=A.Rotation(A.Vector(0,0,1),delta)
        members.append(obj)
        return obj
    bar('EntreeF41Horizontale',(-122,19.3,54),(-80,19.3,54))
    bar('EntreeF41Descente',(-122,19.3,3),(-122,19.3,54))
    bar('EntreeF41BrasBas',(-122,19.3,3),(-88,50,3))
    bar('EntreeF41BrasHaut',(-122,19.3,54),(-88,56,72))
    bar('EntreeF41LongeBasse',(-92.2,50.7,8),(-83.5,50.7,8))
    bar('EntreeF41RepriseBasse',(-88,50.7,8),(-88,56,8))
    union=document.addObject('Part::MultiFuse','P72AvecRetenuesF41')
    union.Shapes=[base]+members;union.Refine=True
    if base in root.Group:root.removeObject(base)
    root.addObject(union);document.recompute()
    for obj in [base]+members:obj.Visibility=False
    union.Visibility=True;api.color(union,(.34,.38,.43))
    stations=[
        {'id':'F41_E_H','point_mm':[-92,24,54],'support':'EntreeF41Horizontale'},
        {'id':'F41_E_V','point_mm':[-124,24,31],'support':'EntreeF41Descente'},
        {'id':'F41_E_B','point_mm':[-87.86,46,8],'support':'EntreeF41LongeBasse'}]
    spec={'cable':'F41','diametre_cable_mm':5,'diametre_longes_mm':4,
          'decalage_plan_mm':4.7,'stations':stations,
          'colliers_T50R_4_6_mm':3,'vis_supplementaires':0,
          'statut':'À valider',
          'limites':['PA12 candidat ; tenue vibratoire et flexion des bras non qualifiées.',
                     'Entrée USB conservée ; changement de fiche ou de parcours impose un nouveau contrôle.',
                     'Réserve fondée sur longueur nominale approximative 1200 mm embout à embout ; longueur de gaine du lot inconnue.']}
    api.meta(root,'RetenuesEntreeF41',json.dumps(spec,ensure_ascii=False))
    return union,spec


def build_usb_reserve_cradle(api, document, root):
    """Trois selles PA12 capturées par colliers dans les lumières OEM existantes.

    Pièce candidate indépendante, posée sur le plateau Z2. Les trois colliers
    encerclent chaque paquet de spires et traversent les ouvertures du plateau ;
    aucun perçage, adhésif ou serrage sur une carte électronique n'est ajouté.
    """
    members=[];cuts=[];saddles=[]
    hub=api.cylinder(document,'MoyeuBerceauUSB',8,2,(-40,0,2));members.append(hub)
    for name,angle,z in [('SO',225,8.6875),('NO',135,12.8125),('E',0,10.75)]:
        # Axe réel après congés R20 Cable Workbench, mesuré au milieu de chaque
        # arc ; le sommet du polygone R23,5 se situe 0,391257 mm plus à l'extérieur.
        theta=math.radians(angle);x=-40+23.10874299668821*math.cos(theta);y=23.10874299668821*math.sin(theta)
        arm=api.box(document,'BrancheBerceau'+name,(23.5,6,2),(-40,0,2))
        arm.Placement.Rotation=A.Rotation(A.Vector(0,0,1),angle)
        # Le décalage transversal appartient au repère local de chaque branche.
        arm.Placement.Base=A.Vector(-40+3*math.sin(theta),-3*math.cos(theta),2)
        members.append(arm)
        saddle=api.box(document,'SelleUSB'+name,(8,8,z-3),(x-4,y-4,2));members.append(saddle)
        tangent=A.Vector(-math.sin(theta),math.cos(theta),5.5/(2*math.pi*23.5));tangent.normalize()
        start=A.Vector(x,y,z)-tangent*8
        channel=api.cylinder(document,'GorgeUSB'+name,3.0,16,(start.x,start.y,start.z))
        channel.Placement.Rotation=A.Rotation(A.Vector(0,0,1),tangent);cuts.append(channel)
        saddles.append({'id':name,'axe_mm':[round(x,5),round(y,5),z],
                        'gorge_rayon_mm':3.0,'jeu_radial_nominal_mm':.5})
    # Les jambes internes des deux colliers diagonaux rencontrent les branches
    # du berceau. Deux passages natifs, bordés de matière, évitent de compter
    # une bande traversant le moyeu comme un montage possible. OEM inchangé.
    for name,sign in [('NO',1),('SO',-1)]:
        x,y=-46.5,sign*5.0
        theta=math.atan2(-sign*18.7,22)
        def passage_box(label,length,width,height,z):
            obj=api.box(document,label,(length,width,height),
                (x-length/2*math.cos(theta)+width/2*math.sin(theta),
                 y-length/2*math.sin(theta)-width/2*math.cos(theta),z))
            obj.Placement.Rotation=A.Rotation(A.Vector(0,0,1),math.degrees(theta))
            return obj
        members.append(passage_box('RenfortPassageCollier'+name,8,10,2,2))
        cuts.append(passage_box('LumiereCollier'+name,1.6,4.8,4,1))
    joined=document.addObject('Part::MultiFuse','BerceauUSBUni');joined.Shapes=members;joined.Refine=True
    final=joined
    for i,tool in enumerate(cuts):
        cut=document.addObject('Part::Cut','BerceauUSBGorge'+str(i+1));cut.Base=final;cut.Tool=tool
        final.Visibility=False;tool.Visibility=False;final=cut
    root.addObject(final);document.recompute()
    for member in members:member.Visibility=False
    final.Visibility=True;api.color(final,(.34,.38,.43))
    spec={'cable':'F41','appui_plateau_mm':2,'selles':saddles,
          'colliers_T50R_4_6_mm':3,'vis_supplementaires':0,'percages_OEM':0,
          'ancrages_colliers':[{'selle':'NO','passages_plateau_xy_mm':[[-68.5,23.7],[-46.5,5]]},
                              {'selle':'SO','passages_plateau_xy_mm':[[-68.5,-23.7],[-46.5,-5]]},
                              {'selle':'E','passages_plateau_xy_mm':[[-52,0],[0,0]]}],
          'passages_berceau_mm':{'largeur':4.8,'epaisseur':1.6,
              'centres_xy':[[-46.5,5],[-46.5,-5]],'renforts_xy':[8,10]},
          'ouvertures_OEM':'Deux oblongs X−74..−64 / Y9..27 et −27..−9 ; ouverture X−64..−40 / Y−8..8 ; trou central Ø6.',
          'statut':'À valider',
          'limites':['Colliers à enfiler dans le plateau avant montage de la réserve ; têtes et tension à vérifier sur prototype.',
                     'PA12 candidat ; interfaces adoucies, tolérances et tenue vibratoire à valider.',
                     'Gaine réelle du cordon 1200 mm embout à embout à mesurer ; réserve ouverte à révision.']}
    api.meta(root,'RetenuesReserveUSB',json.dumps(spec,ensure_ascii=False))
    return final,spec
