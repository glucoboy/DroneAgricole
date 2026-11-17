"""Infrastructure CAO : deux guides de faisceau ajourés du prototype.

Appel par le constructeur principal : ``build_guides(api, d7, r7)``.
Les pièces sont construites par primitives, expressions et booléens natifs.
Ce module ne modifie aucun plateau : ses perçages et dégagements requis sont
retournés au constructeur, qui garde la responsabilité de leur intégration.
"""
import json
import FreeCAD as A


def build_qs8_cradle(api, document, root):
    """Berceau QS8 porté par les deux axes de la butée droite, sans percer le pack."""
    d,r=api.doc('P76_Berceau_QS8_Prototype','pieces/fabriquees','Berceau QS8 sur butée batterie — PA12 candidat')
    api.params(d,r,{'Epaisseur':3,'PiedBas':-85,'TableBas':-62,'TableHaut':-59,'PassageM3':3.2})
    members=[api.box(d,'PiedButee',(8,70,3),(101.5,-35,-85)),
             api.box(d,'Table',(33,46,3),(99,-35,-62))]
    for y in [-35,7]:
        # Le montant avant recule au-delà de la rondelle/tête de butée.
        # Il conserve 2 mm de recouvrement sur le pied et la table.
        members.append(api.box(d,'Montant',(3,3 if y<0 else 4,23),(106.5,-36 if y<0 else y,-82)))
        members.append(api.box(d,'Rebord',(33,2,4),(99,y if y<0 else 9,-59)))
    union=d.addObject('Part::MultiFuse','Brut');union.Shapes=members;union.Refine=True
    holes=[api.cylinder(d,'PassageVis',1.6,5,(105,y,-86)) for y in [-29,29]]
    holes.extend(api.box(d,'LumiereCollier',(2,4.8,5),(x,-22.4,-63)) for x in [99.3,128.5])
    result=api.boolean(d,r,union,holes,'Berceau')
    for o in members+[union]:o.Visibility=False
    api.color(result,(.34,.38,.43))
    api.meta(r,'Interfaces','Pied Z−85 sur butée P61 ; deux axes M3 X105/Y±29. Table Z−59 sous QS8 orienté −90°, centre (113,−12).')
    api.meta(r,'Retenue','Deux rebords et un collier de largeur ≤4,6 mm dans deux lumières. Géométrie nominale ; lot QS8, extraction, tenue et protection des contacts À valider.')
    target=api.save(d,r,['MEC-SUPPORTS-ENERGIE'],'fabriquee','Berceau natif ; reprise des deux vis de butée droite par M3×16, aucune fixation dans le pack.')
    api.link(document,root,'BerceauQS8',target,A.Placement(),['MEC-SUPPORTS-ENERGIE'])
    return target


def build_guides(api, d7, r7):
    """Crée P72/P73 et leurs liens, puis retourne les interfaces à contrôler."""
    level = float(getattr(api, 'ENERGY_PLATE_TOP', 39.0))
    ids = ['ELEC-PASSEFILS']
    # Gauche à Y positif ; droite obtenue par demi-tour autour de Z.
    interfaces = {
        'configuration': 'P64 base 36,2 / épaisseur 2,8 ; PDB centre (42,4)',
        'materiau_candidat': 'PA12 ; procédé, anisotropie et tenue À valider',
        'guide_centres_xy_mm': [[-88, 56], [88, -56]],
        'surfaces_cable_xy_mm': [[-90, 56], [90, -56]],
        'axes_cable_recommandes_xy_mm': [[-94, 56], [94, -56]],
        'P64_encoches_traversantes_mm': [[-94, 56, 20, 42], [94, -56, 20, 42]],
        'P64_trous_mm': [[-80, 56, 3.2], [80, -56, 3.2]],
        'P60_trous_mm': [[-88, 43, 3.2], [-96, 43, 3.2], [88, -43, 3.2], [96, -43, 3.2]],
        'P66_trous_mm': [[-66, 43, 3.2], [66, -43, 3.2]],
        'appuis_z_mm': {'P60': -87.0, 'P64': level, 'P66': 88.0},
        'liaisons': '8 vis M3 au total : 4 P60, 2 P64, 2 P66 ; longueurs selon empilements intégrés',
        'fixations_integration': {
            'P60': {'vis':'4 M3×12 tête cylindrique simplifiée depuis dessus',
                    'z_appui_tete_mm':-83.5, 'rondelles':8, 'ecrous_frein':4,
                    'z_rondelles_mm':[[-84,-83.5],[-90.5,-90]], 'z_ecrous_mm':[-94.5,-90.5]},
            'P64': {'vis':'2 M3×12 tête cylindrique simplifiée depuis dessous',
                    'z_appui_tete_mm':36.2, 'rondelles':2, 'ecrous_frein':2,
                    'z_rondelles_mm':[[42,42.5]], 'z_ecrous_mm':[42.5,46.5],
                    'note':'Aucune rondelle sous P64 : la tête simplifiée haute de 3 mm occupe Z33,2..36,2, soit 0,2 mm au-dessus du plateau OEM. La rondelle inférieure créerait une interférence.'},
            'P66_avec_P75': {'vis':'Les 2 M3×12 autonomes sont remplacées par 2 des 4 M3×16 fraisées du support P75.',
                            'comptage':'Ensemble P72/P73/P75 : 10 vis, 10 écrous et 14 rondelles ; ne pas compter deux fois les axes communs.'}
        },
        'rilsans': {'largeur_max_mm': 4.6, 'lumiere_mm': [8.0, 4.8], 'stations_z_mm': [-72, -47, -22, 3, 28, 53, 78, 93]},
        'limites': [
            'Réservations nominales ; couple, résistance, fatigue, abrasion et température À valider.',
            'Deux encoches ouvertes P64 20×42 obligatoires ; aucun contre-perçage OEM.',
            'Fixations et colliers à matérialiser et compter après intégration.',
            'Le support ne remplace pas la décharge de traction près de chaque connecteur.',
            'Absence de collision à confirmer contre la construction finale et les enveloppes des connecteurs.'
        ],
    }
    for ref, label, angle in [
        ('P72_Guide_Faisceau_Gauche_Prototype', 'Guide faisceau gauche — PA12 candidat', 0),
        ('P73_Guide_Faisceau_Droit_Prototype', 'Guide faisceau droit — PA12 candidat', 180),
    ]:
        d, root = api.doc(ref, 'pieces/fabriquees', label)
        parameters = d.addObject('Spreadsheet::Sheet', 'Parametres')
        root.addObject(parameters)
        values = {'X': -88, 'Y': 56, 'Bas': -87, 'Haut': 98, 'Epaisseur': 4,
                  'Largeur': 14, 'EpaisseurPattes': 3, 'ZMilieu': level,
                  'ZHaut': 88, 'PassageVis': 3.2, 'LumiereLargeur': 8, 'LumiereHauteur': 4.8}
        for row, (key, value) in enumerate(values.items(), 1):
            parameters.set('A' + str(row), key)
            parameters.set('B' + str(row), '=' + str(value) + ' mm')
            parameters.setAlias('B' + str(row), key)
        parameters.Visibility = False
        web = api.box(d, 'Montant', (4, 14, 185), (-90, 49, -87))
        for prop, expr in [('Length', 'Parametres.Epaisseur'), ('Width', 'Parametres.Largeur'),
                           ('Height', 'Parametres.Haut-Parametres.Bas'),
                           ('Placement.Base.x', 'Parametres.X-Parametres.Epaisseur/2'),
                           ('Placement.Base.y', 'Parametres.Y-Parametres.Largeur/2'),
                           ('Placement.Base.z', 'Parametres.Bas')]:
            web.setExpression(prop, expr)
        # Pattes superposées sur les seules pièces projet : P60, P64 et P66.
        low = api.box(d, 'PatteP60', (17, 24, 3), (-101, 39, -87))
        mid = api.box(d, 'PatteP64', (14, 14, 3), (-90, 49, level))
        top = api.box(d, 'PatteP66', (28, 24, 3), (-90, 39, 88))
        low.setExpression('Placement.Base.z', 'Parametres.Bas')
        mid.setExpression('Placement.Base.z', 'Parametres.ZMilieu')
        top.setExpression('Placement.Base.z', 'Parametres.ZHaut')
        for p in [low, mid, top]:
            p.setExpression('Height', 'Parametres.EpaisseurPattes')
        # Les articulations traversent Y63..73 à Z4..30. Deux volets larges
        # reprennent les câbles hors de ce volume ; l'âme centrale reste étroite.
        lower_wing = api.box(d, 'VoletBas', (4, 34, 87), (-90, 39, -87))
        upper_wing = api.box(d, 'VoletHaut', (4, 34, 61.8), (-90, 39, 36.2))
        lower_wing.setExpression('Height', '-Parametres.Bas')
        lower_wing.setExpression('Placement.Base.z', 'Parametres.Bas')
        upper_wing.setExpression('Height', 'Parametres.Haut-36.2 mm')
        details = [lower_wing, upper_wing]
        # Reprises latérales pour les cordons USB du côté gauche : contact
        # tangent nominal, maintien par collier, aucun étranglement du câble.
        if angle == 0:
            for index, z in enumerate([53, 78, 93]):
                details.append(api.box(d, 'AppuiUSB2_' + str(index), (13.5, 4, 3), (-99.5, 66, z - 1.5)))
                details.append(api.box(d, 'AppuiUSB3_' + str(index), (5.15, 7, 3), (-91.15, 70, z - 1.5)))
        union = d.addObject('Part::MultiFuse', 'CorpsEtPattes')
        union.Shapes = [web, low, mid, top] + details
        union.Refine = True
        cuts = []
        # Le pied élargi pour les rondelles passe près de la butée P61.
        # Évider son seul angle, hors des portées des deux axes M3.
        cuts.append(api.box(d,'DegagementButee',(2.7,1.2,5),(-101,39,-88)))
        if angle == 0:
            # Le coude d'entrée AIRY frôle le coin arrière du pied P60.
            cuts.append(api.box(d,'DegagementAIRYPied',(2,3,5),(-102,60.5,-88)))
        # Le volet longe le premier axe bas : dégager rondelle et tête au-dessus
        # du pied, sans retirer la portée de serrage Z−87..−84.
        cuts.append(api.cylinder(d,'DegagementTeteP60',3.7,7,(-88,43,-84)))
        for index, (x, y, z) in enumerate([(-88, 43, -87), (-96, 43, -87), (-80, 56, level), (-66, 43, 88)]):
            hole = api.cylinder(d, 'PassageM3_' + str(index), 1.6, 5, (x, y, z - 1))
            hole.setExpression('Radius', 'Parametres.PassageVis/2')
            if index == 2:
                hole.setExpression('Placement.Base.z', 'Parametres.ZMilieu-1 mm')
            cuts.append(hole)
        # Dégagement du pilier CA01 (centre -60,+37), sans amincir le bord du trou M3.
        cuts.append(api.cylinder(d, 'DegagementPilierCA01', 4.2, 5, (-60, 37, 87)))
        for index, z in enumerate(interfaces['rilsans']['stations_z_mm']):
            slot = api.box(d, 'PassageCollier_' + str(index), (6, 8, 4.8), (-91, 52, z - 2.4))
            slot.setExpression('Width', 'Parametres.LumiereLargeur')
            slot.setExpression('Height', 'Parametres.LumiereHauteur')
            cuts.append(slot)
        # Fente supplémentaire sur chaque retour pour la retenue locale.
        for index, (x, y, z) in enumerate([(-88, 55, -87), (-83, 57, level), (-76, 51, 88)]):
            # Hors axes des vis ; la fente P64 est omise car elle réduirait le ligament de la patte.
            if index == 1:
                continue
            cuts.append(api.box(d, 'CollierRetour_' + str(index), (4.8, 8, 5), (x - 2.4, y - 4, z - 1)))
        result = api.boolean(d, root, union, cuts, 'GuideAjoure')
        d.recompute()
        for primitive in [web, low, mid, top, union] + details:
            primitive.Visibility = False
        result.Visibility = True
        root.Placement = A.Placement(A.Vector(), A.Rotation(A.Vector(0, 0, 1), angle))
        api.color(result, (.34, .38, .43))
        if angle == 0:
            from prototype_retenues import extend_left_guide
            result,retention = extend_left_guide(api,d,root,result)
            interfaces['retenues_entree_f41']=retention
        from prototype_retenues_puissance import extend_low
        result,retention_power = extend_low(api,d,root,result,'left' if angle == 0 else 'right')
        interfaces['retenues_puissance_'+('gauche' if angle == 0 else 'droite')]=retention_power
        from prototype_retenues_locales import extend_local_supports
        result,retention_local = extend_local_supports(api,d,root,result,'left' if angle == 0 else 'right')
        interfaces['retenues_locales_'+('gauche' if angle == 0 else 'droite')]=retention_local
        from prototype_retenues_basses import extend_battery_branches,extend_distribution_ladder
        if angle == 0:
            result,retention_basse = extend_battery_branches(api,d,root,result)
            from prototype_retenues_reserves import extend_reserve_supports
            result,retention_reserve = extend_reserve_supports(api,d,root,result)
            interfaces['retenues_reserves']=retention_reserve
        else:
            result,retention_basse = extend_distribution_ladder(api,d,root,result)
            from prototype_fixations_equipements import extend_midi_shelf
            result,retention_midi = extend_midi_shelf(api,d,root,result)
            interfaces['support_midi']=retention_midi
        interfaces['retenues_basses_'+('gauche' if angle == 0 else 'droite')]=retention_basse
        api.meta(root, 'MateriauCandidat', interfaces['materiau_candidat'])
        api.meta(root, 'InterfacesFixation', json.dumps(interfaces, ensure_ascii=False))
        api.meta(root, 'Limites', ' / '.join(interfaces['limites']))
        target = api.save(d, root, ids, note='Guidage nominal avec trous et lumières natifs ; validation finale intégrée requise.')
        api.link(d7, r7, ref[:3] + '_Guide', target, target.getGlobalPlacement(), ids,
                 'Appuis sur P60/P64/P66 ; contre-perçages des seules pièces projet.')
    return interfaces


def build_top_guide(api, document, root):
    """Support ajouré extérieur à l'avionique, porté uniquement par P66.

    Deux pieds reposent sur P72/P73. Les deux autres ont un talon intégré de
    3 mm : tous les écrous sont au même niveau. Les évidements des colonnes
    évitent de transformer leurs flancs en appuis involontaires. Les œillets
    définissent des stations de retenue ; les colliers restent démontables.
    """
    d, r = api.doc('P75_Guide_Avionique_Prototype', 'pieces/fabriquees',
                   'Support ouvert des câbles avioniques — PA12 candidat')
    api.params(d, r, {'DemiLongueur':80, 'DemiLargeur':55, 'Section':4,
                     'ZPieds':91, 'ZBas':88, 'Sommet':153,
                     'TraverseBasse':112, 'TraverseHaute':145,
                     'PassageVis':3.2, 'PassageCollier':4.8})
    members, holes, stations = [], [], []
    feet = []
    for sx in [-1, 1]:
        for sy in [-1, 1]:
            shared = sx * sy < 0
            foot = api.box(d, 'Pied', (22,18,3),
                           (60 if sx > 0 else -82, 39 if sy > 0 else -57, 91))
            foot.setExpression('Placement.Base.z', 'Parametres.ZPieds')
            members.append(foot)
            if not shared:
                heel = api.box(d, 'TalonP66', (10,10,3), (sx*66-5,sy*43-5,88))
                heel.setExpression('Height', 'Parametres.ZPieds-Parametres.ZBas')
                heel.setExpression('Placement.Base.z', 'Parametres.ZBas')
                members.append(heel)
            post = api.box(d, 'Montant', (4,4,62), (sx*80-2,sy*55-2,91))
            for prop, expr in [('Length','Parametres.Section'), ('Width','Parametres.Section'),
                    ('Height','Parametres.Sommet-Parametres.ZPieds'),
                    ('Placement.Base.x',str(sx)+'*Parametres.DemiLongueur-Parametres.Section/2'),
                    ('Placement.Base.y',str(sy)+'*Parametres.DemiLargeur-Parametres.Section/2'),
                    ('Placement.Base.z','Parametres.ZPieds')]:
                post.setExpression(prop, expr)
            members.append(post)
            hole = api.cylinder(d, 'PassageM3', 1.6, 8, (sx*66,sy*43,87))
            hole.setExpression('Radius', 'Parametres.PassageVis/2')
            holes.append(hole)
            holes.append(api.cylinder(d, 'DegagementColonne', 4.2, 8, (sx*60,sy*37,87)))
            feet.append({'xy_mm':[sx*66,sy*43], 'appui':'P72/P73' if shared else 'P66',
                         'bas_mm':91 if shared else 88, 'haut_mm':94})
    for level, alias in [(112,'TraverseBasse'), (145,'TraverseHaute')]:
        for sy in [-1,1]:
            rail = api.box(d, 'TraverseX', (164,4,4), (-82,sy*55-2,level-2))
            for prop, expr in [('Length','2*Parametres.DemiLongueur+Parametres.Section'),
                    ('Width','Parametres.Section'), ('Height','Parametres.Section'),
                    ('Placement.Base.x','-Parametres.DemiLongueur-Parametres.Section/2'),
                    ('Placement.Base.y',str(sy)+'*Parametres.DemiLargeur-Parametres.Section/2'),
                    ('Placement.Base.z','Parametres.'+alias+'-Parametres.Section/2')]:
                rail.setExpression(prop, expr)
            members.append(rail)
            for x in [-60,-30,0,30,60]:
                if level == 145 and sy == -1 and x == 0:
                    continue  # accès de la fiche USB3 : aucun œillet utilisable ici
                if level == 112 and sy == 1 and x == 30:
                    continue  # sortie F24C : œillet et traverse ajourés localement
                y = sy * 62
                tab = api.box(d, 'OeilletTraverseX', (10,12,3),
                              (x-5,53 if sy>0 else -65,level-1.5))
                members.append(tab)
                slot = api.box(d, 'PassageRilsanX', (4.8,4.8,5), (x-2.4,y-2.4,level-2.5))
                slot.setExpression('Length','Parametres.PassageCollier')
                slot.setExpression('Width','Parametres.PassageCollier')
                holes.append(slot)
                stations.append({'type':'traverse_X','oeillet_mm':[x,y,level],
                                 'appui_cable_mm':[x,sy*55,level+2]})
        for sx in [-1,1]:
            rail = api.box(d, 'TraverseY', (4,114,4), (sx*80-2,-57,level-2))
            for prop, expr in [('Length','Parametres.Section'),
                    ('Width','2*Parametres.DemiLargeur+Parametres.Section'), ('Height','Parametres.Section'),
                    ('Placement.Base.x',str(sx)+'*Parametres.DemiLongueur-Parametres.Section/2'),
                    ('Placement.Base.y','-Parametres.DemiLargeur-Parametres.Section/2'),
                    ('Placement.Base.z','Parametres.'+alias+'-Parametres.Section/2')]:
                rail.setExpression(prop, expr)
            members.append(rail)
            for y in [-35,0,35]:
                x = sx * 87
                members.append(api.box(d, 'OeilletTraverseY', (12,10,3),
                                       (78 if sx>0 else -90,y-5,level-1.5)))
                slot = api.box(d, 'PassageRilsanY', (4.8,4.8,5), (x-2.4,y-2.4,level-2.5))
                slot.setExpression('Length','Parametres.PassageCollier')
                slot.setExpression('Width','Parametres.PassageCollier')
                holes.append(slot)
                stations.append({'type':'traverse_Y','oeillet_mm':[x,y,level],
                                 'appui_cable_mm':[sx*80,y,level+2]})
    # Les quatre montants assurent le changement d'étage entre deux retenues.
    # Le collier entoure leur section 4×4 ; pas de perforation affaiblissante.
    for sx in [-1,1]:
        for sy in [-1,1]:
            for z in [99,127,150]:
                stations.append({'type':'autour_montant','axe_montant_mm':[sx*80,sy*55,z],
                                 'face_appui_exterieure_mm':[sx*82,sy*55,z]})
    union = d.addObject('Part::MultiFuse', 'SupportBrut')
    union.Shapes = members
    union.Refine = True
    # Dégagement de la descente Ethernet près de la face RJ45. Les deux
    # demi-traverses restent liées au cadre par leurs montants respectifs.
    holes.append(api.box(d,'PassageDescenteEthernet',(10,12,10),(8,49,140)))
    # Le type A USB3 passe sous la traverse avant : garder 2,3 mm de matière
    # en partie haute, avec 0,2 mm nominal au-dessus du surmoulage fabricant.
    holes.append(api.box(d,'DegagementFicheUSB3',(18,14,5),(-2,-66,139.7)))
    holes.append(api.box(d,'DegagementSortieF24C',(6,10,10),(24,51,108)))
    final = api.boolean(d,r,union,holes,'SupportAjoure')
    d.recompute()
    for o in members + [union]:
        o.Visibility = False
    api.color(final, (.34,.38,.43))
    from prototype_retenues import extend_top_guide
    final,retention = extend_top_guide(api,d,r,final)
    from prototype_retenues_capteurs import extend_camera_usb_support
    final,retention_usb = extend_camera_usb_support(api,d,r,final)
    from prototype_retenues_hautes import extend_high
    final,retention_haute = extend_high(api,d,r,final)
    from prototype_retenues_departs import extend_departures
    final,retention_departs = extend_departures(api,d,r,final)
    interfaces = {'reference':d.Name, 'pieds':feet,'retenues_complementaires':retention,
        'retenue_camera_usb':retention_usb,
        'retenues_hautes':retention_haute,
        'retenues_departs_bras':retention_departs,
        'P66_trous_mm':[[sx*66,sy*43,3.2] for sx in [-1,1] for sy in [-1,1]],
        'P66_fraisures_dessous':{'z_face_mm':85,'diametre_entree_mm':6.2,
            'diametre_sortie_mm':3.2,'profondeur_mm':1.8,'note':'Enveloppe compatible avec la vis simplifiée de la recette ; norme/lot et épaisseur résiduelle G10 à confirmer.'},
        'fixations':{'vis':'4 M3×16 tête fraisée depuis dessous P66, dont 2 communes avec P72/P73',
            'rondelles':4,'ecrous_frein':4,'z_face_tete_mm':85.12,'retrait_tete_mm':0.12,
            'z_rondelle_mm':[94,94.5],'z_ecrou_mm':[94.5,98.5],
            'z_extremite_vis_mm':101.12,'saillie_nominale_mm':2.62,
            'appui_conique':'Pose +0,12 mm dans la fraisure : compensation du jeu radial nominal de 0,1 mm ; appui géométrique sur les cônes simplifiés.'},
        'rilsans':{'largeur_nominale_max_mm':4.6,'passage_mm':4.8,
            'oeillets':30,'stations':stations,'pas_max_oeillets_mm':60,
            'exception':'Œillet avant X0/Z145 supprimé pour USB3 ; œillet arrière X30/Z112 supprimé pour F24C. Intervalle local maximal60 mm entre œillets restants.'},
        'surfaces_appui':{'traverses_X':{'x_mm':[-80,80],'y_mm':[-55,55],'z_dessus_mm':[114,147]},
                         'traverses_Y':{'x_mm':[-80,80],'y_mm':[-55,55],'z_dessus_mm':[114,147]},
                         'montants':{'axes_xy_mm':[[sx*80,sy*55] for sx in [-1,1] for sy in [-1,1]],'z_mm':[94,153]}},
        'regle_routage':'Axe câble à rayon extérieur au-dessus de la surface d’appui, avec protection souple. Croisements superposés et parcours qui quittent le cadre à contrôler explicitement ; les œillets ne prouvent pas leur retenue.',
        'qualification':'À valider',
        'limites':['Arêtes au contact des gaines à adoucir R0,5 minimum avant montage ; finition non représentée.',
            'PA12 candidat ; procédé, tolérances, fluage, vibration et tenue des ligaments à valider.',
            '30 œillets percés et 12 stations autour montants ; quantité réelle de colliers dépend du regroupement des faisceaux.',
            'Pas d’appui sur PCB/composant ; les coaxiaux nécessitent une bride souple sans serrage direct.']}
    api.meta(r,'Materiau','PA12 candidat ; profil 4×4, procédé et tenue À valider')
    api.meta(r,'InterfacesFixation',json.dumps(interfaces,ensure_ascii=False))
    api.meta(r,'Limites',' / '.join(interfaces['limites']))
    target=api.save(d,r,['ELEC-PASSEFILS'],'fabriquee',
        'Support dédié aux câbles, porté par quatre pattes P66 ; arbres natifs et œillets éditables. Tenue physique non qualifiée.')
    api.link(document,root,'P75_Cadre',target,A.Placement(),['ELEC-PASSEFILS'])
    return interfaces
