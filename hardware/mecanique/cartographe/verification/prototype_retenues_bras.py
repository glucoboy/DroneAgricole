"""Selles paramétriques sur tubes OEM Ø20, retenues par colliers démontables.

Les selles gardent les parcours et les bras OEM inchangés. Géométrie nominale
de définition ; TPU, serrage, jeu et comportement vibratoire À valider.
"""
import json
import math
import FreeCAD as A


def make_saddle(api, document, root, kind):
    heights={'amont':32.3,'aval':28.8}
    if kind not in heights:
        raise ValueError('Selle de bras inconnue : '+kind)
    top=heights[kind]
    members=[api.box(document,'Pont',(8,24,top-24),(-4,-12,24))]
    for sign in (-1,1):
        members.append(api.box(document,'Joue',(8,3.5,9),(-4,-13 if sign<0 else 9.5,16)))
        members.append(api.box(document,'AppuiLED',(8,7,4),(-4,-18.5 if sign<0 else 11.5,16)))
    union=document.addObject('Part::MultiFuse','SelleBrute')
    union.Shapes=members;union.Refine=True
    tools=[]
    def bore(name,radius,y,z):
        tool=api.cylinder(document,name,radius,10,(-5,y,z))
        tool.Placement.Rotation=A.Rotation(A.Vector(0,0,1),A.Vector(1,0,0))
        tools.append(tool)
    bore('PassageTubeOEM',10.15,0,16.5)
    for sign in (-1,1):
        y=sign*24/math.sqrt(2)
        bore('GorgeLED',1.4,y,18)
        tools.append(api.box(document,'OuvertureLED',(10,4,2.8),(-5,-20.97 if sign<0 else 16.97,16.6)))
    if kind=='amont':
        bore('GorgePuissance',2.7,0,32)
    if kind=='amont':
        for sign in (-1,1):
            y=sign*8/math.sqrt(2)
            bore('GorgeSignal',1.0,y,30)
            tools.append(api.box(document,'BoucheSoupleSignal',(10,8,1.4),
                (-5,y-8 if sign<0 else y,29.3)))
    result=api.boolean(document,root,union,tools,'SelleAjouree')
    document.recompute()
    for obj in members+[union]+tools:obj.Visibility=False
    api.color(result,(.16,.35,.65))
    spec={'type':kind,'largeur_axiale_mm':8,'diametre_tube_nominal_mm':20,
          'jeu_radial_tube_mm':.15,'matiere_candidate':'TPU 95A',
          'fixation':'Un collier T50R autour du tube, de la selle et des gaines à chaque occurrence.',
          'symetrie':'Deux gorges LED latérales et deux gorges signal amont permettent la même référence sur les quatre bras.',
          'retenue_signal':'Amont : gorge Ø2 avec toit de 1,3 mm et bouche latérale de 1,4 mm pour la gaine Ø1,6 ; encliquetage TPU candidat, sans présumer un serrage direct par le collier commun.',
          'appui_puissance':'Amont : gorge ouverte pour F02. Aval : face plane Z28,8 sous F03 Ø6 à Z32, jeu nominal0,2 mm.',
          'limites':['Jeu radial absorbé au serrage souple, adhérence et fluage À valider.',
                     'Préserver le débattement de pliage ; débrancher ou libérer le faisceau avant pliage.',
                     'Montage sans perçage OEM ; boucle et tête du collier à contrôler sur matériel.',
                     'Les rayons et longueurs des parcours restent inchangés.'],
          'qualification':'À valider'}
    # Points dans le repère de la selle, transformés par l'occurrence du bras.
    # Ces stations servent au contrôle du parcours effectif Cable Workbench.
    spec['stations']=[{'id':'LED_'+label,'point_mm':[0,sign*24/math.sqrt(2),18],
                       'support':'Gorge LED latérale','famille_cable':'LED'}
                      for label,sign in [('PLUS',1),('MOINS',-1)]]
    spec['stations'].append({'id':'F02' if kind=='amont' else 'F03',
        'point_mm':[0,0,32],'support':'Gorge puissance' if kind=='amont' else 'Face plane puissance'})
    if kind=='amont':
        spec['stations'] += [{'id':'F04_'+label,'point_mm':[0,sign*8/math.sqrt(2),30],
                             'support':'Gorge signal à bouche souple'}
                            for label,sign in [('PLUS',1),('MOINS',-1)]]
    api.meta(root,'InterfacesFixation',json.dumps(spec,ensure_ascii=False))
    return result,spec


def build_arm_retainers(api,document,root):
    definitions=[('amont','P79_Selle_Bras_Amont_Prototype'),
                 ('aval','P80_Selle_Bras_Aval_Prototype')]
    targets={};report={'references':{},'stations':[],'colliers':12,'vis_supplementaires':0,'qualification':'À valider'}
    for kind,name in definitions:
        d,r=api.doc(name,'pieces/fabriquees','Selle de bras '+kind+' — TPU candidat')
        _,spec=make_saddle(api,d,r,kind)
        targets[kind]=api.save(d,r,['ELEC-PASSEFILS'],'fabriquee','Selle sur tube OEM Ø20 ; un collier par occurrence, sans perçage. Tenue physique À valider.')
        report['references'][name]=spec
    for arm,(sx,sy) in enumerate([(-1,-1),(1,1),(-1,1),(1,-1)],1):
        rotation=A.Rotation(A.Vector(0,0,1),math.degrees(math.atan2(sy,sx)))
        for number,(kind,u) in enumerate([('amont',180),('aval',250),('aval',280)],1):
            pose=A.Placement(A.Vector(sx*u/math.sqrt(2),sy*u/math.sqrt(2),0),rotation)
            name='SelleBras'+str(arm)+'_'+str(number)
            api.link(document,root,name,targets[kind],pose,['ELEC-PASSEFILS'])
            cables=['LED_'+str(arm)]
            if kind=='amont':cables+=['F02_'+str(arm),'F04_'+str(arm)]
            if kind=='aval' and u==250:cables+=['F03_'+str(arm)]
            report['stations'].append({'id':name,'support':targets[kind].Document.Name,
                'cables':cables,'distance_radiale_mm':u,'largeur_collier_mm':4.6,
                'fixation':'Un collier autour du tube, de la selle et des gaines affectées.',
                'matrice':list(pose.toMatrix().A)})
    return report
