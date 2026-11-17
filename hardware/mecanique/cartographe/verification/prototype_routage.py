"""Infrastructure FreeCAD : implantation du faisceau contre les supports du prototype.

Les points décrivent des passages mécaniques, pas des brochages de fabrication.
Les coordonnées fabricant disponibles sont reprises dans la configuration haute.
"""
import json, math
from pathlib import Path


def routes_basses():
    routes=[]
    def add(name, ids, points, diameter, radius, support, **extra):
        routes.append(dict(id=name,bom_ids=ids,points_mm=points,diametre_mm=diameter,
            rayon_courbure_mm=radius,supports=support,statut='À valider',
            terminaisons='Faces de sortie réservées ; fiches, orientation et brochage à confirmer sur matériel',**extra))
    # Deux conducteurs séparés : aucun négatif ne traverse le fusible B+.
    add('F01_NEG',['ELEC-F01'],[[-97.5,12,-50],[-111,12,-50],[-111,53,-50],[-111,53,-16],[-111,34,-16],[-80,34,-16],[-80,15,-16],[-66.25,15,-16]],6.5,8,['P60','P62','P72'],fonction='BAT B− vers BMS B− brut')
    add('F01_POS',['ELEC-F01'],[[-97.5,0,-50],[-117,0,-50],[-117,-44,-50],[-105,-44,-5],[30,-44,-5],[30,-70,-5],[30,-70,-27]],6.5,10,['P60','P62'],fonction='BAT B+ vers entrée MIDI')
    add('F37_POS',['ELEC-F37'],[[74.5,-79,-40],[101,-89,-40],[128,-89,-40],[128,40,-40],[108,40,-51],[108,10,-51]],6.5,10,['P60','P76'],fonction='Sortie MIDI vers QS8 B+')
    add('F37_NEG',['ELEC-F37'],[[66.25,20,-16],[98,20,-16],[118,25,-16],[118,25,-51],[118,10,-51]],6.5,10,['P62','P76'],fonction='BMS C− protégé vers QS8 ; aucun passage dans MIDI')
    incoming=[[[108,-34,-51],[108,-66,-51],[98,-66,-17],[98,-66,52],[98,-94,52],[-65,-94,52],[-65,-66,52],[-45.5,-66,52]],
              [[118,-34,-51],[118,-79,-51],[106,-79,-17],[106,-79,52],[106,-104,52],[-77,-104,52],[-77,-50,52],[-45.5,-50,52]]]
    outgoing=[[[ -7,-70,66],[-7,-70,77],[69,-70,77],[69,-14,77],[69,-14,63]],
              [[ -7,-49,66],[-7,-49,77],[45,-49,77],[45,14,77],[45,14,63]]]
    for index,(suffix,tint) in enumerate([('POS',[.75,.10,.06]),('NEG',[.08,.08,.10])]):
        add('F38_'+suffix,['ELEC-F38'],incoming[index],6.5,12,
            ['P60','P72','P64'],fonction='QS8 drone vers PM08 IN',couleur=tint)
        add('F05_'+suffix,['ELEC-F05'],outgoing[index],6.5,10,
            ['P64'],fonction='PM08 OUT vers PDB',couleur=tint)
    add('F08_AMONT',['ELEC-F08'],[[65,-28,63],[65,-28,70],[81,-28,70],[81,-70,70],[25,-70,70],[25,-70,51],[25,-63.5,51]],4.6,6,['P64'],fonction='PDB vers protection CA01')
    add('F08_AVAL',['ELEC-F08'],[[15,-43,59],[15,-43,69],[-94,-43,69],[-94,-43,117],[-94,-22,117],[-61,-22,117],[-61,-22,106]],4.6,8,['P64','P66'],fonction='Protection vers CA01 J103')
    add('F40',['ELEC-F40'],[[-66.25,-10,-13],[-96,-10,-10],[-96,-34,-10],[-96,-34,60],[-96,-20,60],[-79,-20,54]],2.8,6,['P62','P72','P64'],fonction='UART brut BMS vers côté isolé ; aucune dérivation USB')
    add('BALANCE',['ELEC-F-BALANCE'],[[-97.5,21,-45],[-105,21,-45],[-105,21,-5],[-105,36,-5],[-80,36,-5],[-55,44,-5],[-44,44,-16],[-44,33.75,-16]],3.5,7,['P60','P62'],fonction='Mesures B0..B6 vers BMS, câblage réel selon lot')
    for i,x in enumerate([-30,30],1):
        pin=-3 if x<0 else 3
        add('NTC'+str(i),['ELEC-NTC'],[[x,40,-33],[x,49.1,-33],[x,49.1,-23],
            [-10 if x<0 else 10,49.1,-23],[pin,49.1,-16],[pin,33.75,-16]],
            1.8,4,['P62'],fonction='Sonde température vers BMS ; deux retenues au chant P62, sortie au-dessus du bord')
    # Branche propulsion : départ et arrivée de chaque bras, fils fixés au tube.
    power_paths=[
        [[20,-20,63],[20,-20,79],[-70,-20,79],[-70,-84,79],[-95,-84,79],[-108,-108,44],[-122,-122,32],[-133.7,-133.7,32]],
        [[73,24,52],[84,24,52],[84,74,50],[108,108,50],[122,122,32],[133.7,133.7,32]],
        [[32,45,52],[32,83,44],[-84,83,44],[-108,108,44],[-122,122,32],[-133.7,133.7,32]],
        [[62,-37,52],[62,-79,44],[108,-108,44],[122,-122,32],[133.7,-133.7,32]]]
    signal_paths=[
        [[58,-37,135],[74,-37,135],[74,-58,116],[-58,-58,116],[-58,-58,50],[-80,-80,46],[-105,-97,42],[-117,-109,29],[-129,-121,29]],
        [[58,-34,135],[78,-34,135],[78,58,116],[58,58,116],[58,58,50],[80,80,46],[105,97,42],[117,109,29],[129,121,29]],
        [[58,-31,135],[86,-31,135],[86,62,116],[-58,62,116],[-58,62,50],[-80,84,46],[-105,97,42],[-117,109,29],[-129,121,29]],
        [[58,-28,135],[90,-28,135],[90,-62,116],[58,-62,116],[58,-62,50],[80,-84,46],[105,-97,42],[117,-109,29],[129,-121,29]]]
    for i,(sx,sy) in enumerate([(-1,-1),(1,1),(-1,1),(1,-1)],1):
        add('F02_'+str(i),['ELEC-F02'],power_paths[i-1],5,10,
            ['P64','bras'+str(i)],fonction='PDB vers ESC'+str(i))
        add('F03_'+str(i),['ELEC-F03'],[[170.5*sx,170.5*sy,32],[189*sx,189*sy,32],[201*sx,201*sy,47],[210*sx,210*sy,47]],6,10,
            ['bras'+str(i)],fonction='Trois phases ESC vers moteur, enveloppe groupée')
        yy=-40+3*i
        lane=58 if i in [1,2] else 66
        col=84 if i==1 else 74 if i==2 else 76
        zrow=128 if i==4 else 116
        signal_paths[i-1]=[[58,yy,136],[66,yy,136],[70,yy,160+3*i],[96+3*i,yy,160+3*i],
            [96+3*i,sy*lane,zrow],[col*sx,sy*lane,zrow],[col*sx,sy*lane,40.4],
            [76*sx,88*sy,40.4],[99*sx,107*sy,40.4],[113*sx,121*sy,30],[127*sx,135*sy,30]]
        add('F04_'+str(i),['ELEC-F04'],signal_paths[i-1],1.6,5,
            ['P66','P64','bras'+str(i)],fonction='Signal et retour MAIN vers ESC'+str(i))
        add('LED_'+str(i),['ELEC-F-LED'],[[75*sx,78*sy,43],[110*sx,86*sy,43],[126*sx,102*sy,18],[212*sx,188*sy,18],[224*sx,200*sy,20]],2.4,7,
            ['P64','bras'+str(i)],fonction='Branche OEM LED ; affectation et distribution à confirmer')
    # Les blocs isolés gardent une courte boucle souple entre deux retenues.
    add('AIRY',['ELEC-F-AIRY'],[[-35,34,-143],[-60,64,-143],[-104,64,-110],[-104,64,100],[-80,64,120]],7,14,
        ['P65/P10','P73','P66'],fonction='Tronc Airy aviation vers éclatement, avec boucle de découplage')
    add('AIRY_ETH',['ELEC-F-AIRY'],[[-80,64,120],[-80,64,160],[13,74,160],[13,51,160],[13,51,137],[13,40.5,137]],5.5,10,['P75','porteuse'],fonction='Éclatement Airy Ethernet vers Jetson')
    add('AIRY_PWR',['ELEC-F-AIRY'],[[-80,64,120],[-88,55,124],[-88,-68,128],[3,-68,128],[3,-68,105],[3,-40,105]],3.4,8,['P75'],fonction='CA01 J201 vers éclatement Airy')
    add('AIRY_SYNC',['ELEC-F-AIRY'],[[-80,64,120],[94,64,120],[94,17,108],[65,17,104]],2.5,5,['P75'],fonction='CA01 J504 vers éclatement Airy')
    add('F_M8',['ELEC-F-M8'],[[74.2,31.1,-90.855],[74.2,35,-90.855],[72.5,48,-90.855],[72.5,106,-90.855],[72.5,106,113],[41,43,103]],5.2,52,
        ['P65/P10','P64','P75'],fonction='Cordon commun M8 blindé : trigger et retour exposition vers J502',
        reference_candidate='Phoenix Contact SAC-6P-M8MR/1,5-PUR SH — 1522341',
        limite_connecteurs='Engagement 6 mm uniquement hypothèse de montage, à mesurer ; dégagement local de semelle et pad nécessaire. Rayon 52 mm du fabricant ; extrémité ouverte coupée à longueur après montage. Compatibilité électrique des paires à confirmer.')
    # Réserves des cordons complets rangées dans la baie libérée Z2..31.
    # Hélices de rangement à grand rayon ; les rayons sont ceux des arcs CAO.
    def coil(cx, cy, radius, z, turns, pitch, start=0):
        return [[cx+radius*math.cos(start+i*math.pi/8),cy+radius*math.sin(start+i*math.pi/8),z+pitch*i/16]
                for i in range(int(turns*16)+1)]
    add('F16',['ELEC-F16'],[[109.785,-.525,-96.82],[132,-.525,-96.82],[132,-54,-96.82],[96,-54,-67],[96,-54,90],[96,-105,140.5],[7,-105,140.5],[7,-79.95,140.5]],
        5.5,22,['P65/P10','P73','P75'],fonction='USB3 coudé vers extérieur, chemin sur flanc droit et arrivée dans la gaine du type A',
        longueur_catalogue_mm=508,longueur_gaine_utile_min_mm=428.5,
        reference_candidate='USBFireWire RR-ASMUK-20GRHF',
        limite_connecteurs='Caméra conservée ; épaulement microB Z−109,82 et sortie de gaine issue du STEP. Type A : épaulement Y−39,35 et queue 40,6 mm. Longueur utile minimale conservatrice ; révision de définition L, engagement et polarisation à confirmer avant achat.')
    add('F41',['ELEC-F41'],[[-79,24,54],[-124,24,54],[-124,24,8],[-100,46,8],[-63.5,46,8]]+
        coil(-40,0,23.5,8,3.5,5.5,math.pi)+[[-16.5,38,27.25],[-112,38,27.25],[-112,56,60],[-112,56,113],[-112,-88,131.5],[7,-88,131.5],[7,-42,131.5]],
        5,20,['P64','plateau central inférieur','P73','P66'],fonction='USB2 isolateur entier, réserve fixée dans baie centrale',
        longueur_catalogue_mm=1200)
    return routes


def all_routes(api):
    routes=routes_basses()
    file=api.VER/'configuration_faisceau_haut_prototype.json'
    high=json.loads(file.read_text(encoding='utf-8'))
    routes.extend(high['routes'])
    return routes


def build_routes(api,assemblies):
    from cable_workbench_prototype import make_native_cable, cable_geometry, bootstrap_paths
    from prototype_guides import build_guides, build_top_guide
    d,r=api.doc('SA07_Prototype_Faisceaux','sous_assemblages','07 — Faisceaux Cable Workbench et retenues')
    guides=build_guides(api,d,r)
    guides['cadre_avionique']=build_top_guide(api,d,r)
    from prototype_retenues import build_usb_reserve_cradle
    db,rb=api.doc('P77_Berceau_Reserve_USB_Prototype','pieces/fabriquees','Berceau de réserve USB — PA12 candidat')
    _,guides['berceau_reserve_usb']=build_usb_reserve_cradle(api,db,rb)
    cradle=api.save(db,rb,['ELEC-PASSEFILS'],'fabriquee','Trois selles et trois colliers dans les lumières OEM existantes ; matériau, finition et serrage À valider.')
    api.link(d,r,'P77_BerceauReserveUSB',cradle,api.A.Placement(),['ELEC-PASSEFILS'])
    from prototype_retenues_capteurs import build_camera_m8_support
    dc,rc=api.doc('P78_Retenue_Camera_M8_Prototype','pieces/fabriquees','Retenue caméra M8 sur P64 — PA12 candidat')
    _,guides['retenue_camera_m8']=build_camera_m8_support(api,dc,rc)
    camera_support=api.save(dc,rc,['ELEC-PASSEFILS'],'fabriquee','Rebord sur P64 et collier dans la lumière existante ; trois stations de gaine M8, rigidité et serrage À valider.')
    api.link(d,r,'P78_RetenueCameraM8',camera_support,api.A.Placement(),['ELEC-PASSEFILS'])
    from prototype_retenues_bras import build_arm_retainers
    guides['retenues_bras']=build_arm_retainers(api,d,r)
    from prototype_connecteurs import build_connectors
    connectors=build_connectors(api,d,r)
    from prototype_fixations_equipements import build_equipment_collars
    guides['colliers_equipements']=build_equipment_collars(api,d,r)
    # Fixations des guides : références existantes réemployées, axes communs
    # P72/P73/P75 comptés une seule fois.
    screw=api.A.getDocument('EQ_ISO4762_M3x12_Prototype').getObject('Ensemble')
    washer=api.A.getDocument('EQ_ISO7089_M3_Prototype').getObject('Ensemble')
    nut=api.A.getDocument('EQ_ISO10511_M3_Prototype').getObject('Ensemble')
    flat=api.bolt('EQ_ISO10642_M3x16_Prototype',3,16,True)
    ids=['ELEC-PASSEFILS'];up=api.A.Rotation(api.A.Vector(1,0,0),180)
    for i,(x,y) in enumerate([(-88,43),(-96,43),(88,-43),(96,-43)]):
        api.link(d,r,'VisGuideBas'+str(i),screw,api.A.Placement(api.A.Vector(x,y,-83.5),api.A.Rotation()),ids)
        for suffix,z in [('H',-84),('B',-90.5)]:api.at(d,r,'RondelleGuideBas'+suffix+str(i),washer,(x,y,z),ids)
        api.at(d,r,'EcrouGuideBas'+str(i),nut,(x,y,-94.5),ids)
    for i,(x,y) in enumerate([(-80,56),(80,-56)]):
        api.link(d,r,'VisGuideMilieu'+str(i),screw,api.A.Placement(api.A.Vector(x,y,36.2),up),ids)
        api.at(d,r,'RondelleGuideMilieu'+str(i),washer,(x,y,42),ids)
        api.at(d,r,'EcrouGuideMilieu'+str(i),nut,(x,y,42.5),ids)
    for i,(x,y) in enumerate([(x,y) for x in [-66,66] for y in [-43,43]]):
        api.link(d,r,'VisGuideHaut'+str(i),flat,api.A.Placement(api.A.Vector(x,y,85.12),up),ids)
        api.at(d,r,'RondelleGuideHaut'+str(i),washer,(x,y,94),ids)
        api.at(d,r,'EcrouGuideHaut'+str(i),nut,(x,y,94.5),ids)
    result=[]
    for row in all_routes(api):
        name=row['id']; ids=row['bom_ids']
        dr,rr=api.doc('W_'+name+'_Prototype','pieces/commerce','Faisceau '+name+' — Cable Workbench')
        c,route=make_native_cable(dr,rr,name,row['points_mm'],row['diametre_mm'],row['rayon_courbure_mm'],
            row.get('couleur',(.14,.19,.24)))
        api.meta(c,'BOM_ID',','.join(ids));api.meta(c,'Fonction',row.get('fonction',''))
        api.meta(c,'Supports',','.join(row.get('supports',[])))
        api.meta(rr,'Limites',row.get('terminaisons','Terminaisons mécaniques et électriques À valider'))
        geo=cable_geometry(c)
        ref=api.save(dr,rr,ids,'faisceau_cable_workbench','Encombrement extérieur, rayon de définition et points éditables ; contacts, matériaux et tenue À valider.')
        api.link(d,r,name,ref,api.A.Placement(),ids)
        result.append(dict(row,**geo,fichier=api.rel(dr.FileName),objet_cable=c.Name,objet_parcours=route.Name,
            longueur_trace_mm=round(geo['longueur_courbe_mm'],3)))
    api.save(d,r,kind='sous_assemblage');assemblies.append((d,r))
    api.dump(api.VER/'routes_prototype.json',{'date':api.datetime.now().date().isoformat(),
        'nature':'Faisceaux natifs Cable Workbench, implantation À valider','extension':bootstrap_paths(),
        'routes':result,'guides':guides,'connecteurs_camera':connectors,'limites':['Encombrements extérieurs sans détail des conducteurs ; trois fiches caméra USB/M8 représentées, autres terminaisons réservées',
        'Interfaces OEM réservées tant que non cotées','Serrage, vibration, matériaux et essais électriques non qualifiés']})

