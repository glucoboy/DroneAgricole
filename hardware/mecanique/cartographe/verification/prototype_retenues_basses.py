"""Échelle native commune des départs de distribution, portée par P73.

Les deux appuis gauches reposent sur la longe F38 de P72 et se lient par
colliers démontables. Le modèle ne fusionne jamais les deux documents.
"""
import json
import math
import FreeCAD as A


def extend_distribution_ladder(api, document, root, base):
    """Prolonger P73 après ses retenues locales ; coordonnées globales."""
    inverse = root.getGlobalPlacement().inverse()
    parts, history, stations = [], [], []

    def box(name, size, pos):
        obj = api.box(document, name, size, pos)
        obj.Placement = inverse.multiply(obj.Placement)
        history.append(obj)
        return obj

    def beam(name, a, b, width=3, height=8):
        dx, dy = b[0]-a[0], b[1]-a[1]
        angle = math.atan2(dy, dx)
        obj = api.box(document, name, (math.hypot(dx, dy), width, height),
                      (a[0]+width/2*math.sin(angle), a[1]-width/2*math.cos(angle), a[2]-height/2))
        obj.Placement.Rotation = A.Rotation(A.Vector(0,0,1), math.degrees(angle))
        obj.Placement = inverse.multiply(obj.Placement)
        history.append(obj)
        parts.append(obj)
        return obj

    def bar(name, a, b, radius=1.5):
        delta = A.Vector(*b)-A.Vector(*a)
        obj = api.cylinder(document, name, radius, delta.Length, a)
        obj.Placement.Rotation = A.Rotation(A.Vector(0,0,1), delta)
        obj.Placement = inverse.multiply(obj.Placement)
        history.append(obj)
        parts.append(obj)
        return obj

    def station(identifier, cable, point, support):
        stations.append({'id':identifier, 'cables':[cable], 'point_mm':list(point),
            'support':'P73/'+support, 'type':'collier autour appui et gaine',
            'largeur_collier_mm':4.6, 'statut':'À valider'})

    # Échelle sous les gaines, éloignée des deux voies de sortie PM08.
    # Le pied gauche repose sur la longe de P72 à Z66,5, sans intersection.
    for y in (-55.5,-82):
        if y == -55.5:
            # Détour local autour des montantes P75 ; les appuis terminaux
            # restent aux mêmes coordonnées, sans fusion entre documents.
            detour=[beam('TraverseDistributionDepart',(-89,y,69),(-85,y,69),3,5),
                    beam('TraverseDistributionDetourA',(-85,y,69),(-85,-51.5,69),3,5),
                    beam('TraverseDistributionDetourB',(-85,-51.5,69),(-74,-51.5,69),3,5),
                    beam('TraverseDistributionDetourC',(-74,-51.5,69),(-74,y,69),3,5),
                    beam('TraverseDistributionSuite',(-74,y,69),(88,y,69),3,5)]
            rail=document.addObject('Part::MultiFuse','TraverseDistributionDetour')
            rail.Shapes=detour;rail.Refine=True;history.append(rail)
            for member in detour:parts.remove(member)
            parts.append(rail)
        else:
            rail=beam('TraverseDistribution',(-89,y,69),(88,y,69),3,5)
        if y == -55.5:
            # Renfort sous la gorge du cordon 5V amont.
            pad=box('RenfortGorgeF08',(10,3,1.5),(76,y-1.5,65))
            joined=document.addObject('Part::MultiFuse','TraverseRenforceeF08')
            joined.Shapes=[rail,pad];joined.Refine=True;history.append(joined)
            tool=api.cylinder(document,'GorgeF08Amont',2.5,7,(81,y-3.5,70))
            tool.Placement.Rotation=A.Rotation(A.Vector(0,0,1),A.Vector(0,1,0))
            tool.Placement=inverse.multiply(tool.Placement);history.append(tool)
            cut=document.addObject('Part::Cut','TraverseAvecGorgeF08')
            cut.Base,cut.Tool=joined,tool;history.append(cut)
            parts.remove(rail);parts.append(cut)
        foot=box('AppuiTerminalP72',(3,3,5),(-90.5,y-1.5,66.5));parts.append(foot)
    beam('RepriseP73Echelle',(88,-82,69),(88,-55.5,69),3,5)

    beam('AppuiF05PosHorizontal',(10,-65.05,77),(55,-65.05,77))
    for x in (20,50):
        bar('PiedAppuiF05Pos',(x,-55.5,69),(x,-65.05,69))
        bar('MontantAppuiF05Pos',(x,-65.05,69),(x,-65.05,77))
        station('F05_POS_T_'+str(x),'F05_POS',(x,-70,77),'AppuiF05PosHorizontal')
    beam('LisseF05Pos',(73.95,-54.5,77),(73.95,-24,77))
    bar('PiedLisseF05Pos',(73.95,-55.5,69),(73.95,-54.5,77))
    for y in (-50,-30):station('F05_POS_L_'+str(y),'F05_POS',(69,y,77),'LisseF05Pos')

    beam('AppuiF05NegHorizontal',(0,-44.05,77),(35,-44.05,77))
    for x in (25,35):
        bar('PiedAppuiF05Neg',(x,-55.5,69),(x,-44.05,69))
        bar('MontantAppuiF05Neg',(x,-44.05,69),(x,-44.05,77))
    for x in (15,30):station('F05_NEG_T_'+str(x),'F05_NEG',(x,-49,77),'AppuiF05NegHorizontal')
    beam('LisseF05Neg',(49.95,-35,77),(49.95,4,77))
    bar('PiedLisseF05NegA',(47.3,-55.5,69),(47.3,-46,69))
    bar('PiedLisseF05NegB',(47.3,-46,69),(49.95,-46,69))
    bar('PiedLisseF05NegC',(49.95,-46,69),(49.95,-35,77))
    for y in (-30,0):station('F05_NEG_L_'+str(y),'F05_NEG',(45,y,77),'LisseF05Neg')

    beam('LisseF08Amont',(85,-65,70),(85,-33,70),3,5)
    for y in (-55,-40):station('F08_AMONT_L_'+str(y),'F08_AMONT',(81,y,70),'LisseF08Amont')
    beam('AppuiF08AmontHorizontal',(35,-66,70),(55,-66,70),3,3)
    for x in (35,55):
        bar('RepriseF08AmontHorizontal',(x,-55.5,69),(x,-66,70))
        station('F08_AMONT_T_'+str(x),'F08_AMONT',(x,-70,70),'AppuiF08AmontHorizontal')
    for x,height in [(-65,77),(-25,77),(5,81.5)]:
        bar('ConsoleF08AvalMontant',(x,-55.5,69),(x,-55.5,height))
        bar('ConsoleF08AvalReprise',(x,-55.5,height),(x,-39,height),1 if x==5 else 1.5)
        bar('ConsoleF08AvalBas',(x,-39,height),(x,-39,69))
        station('F08_AVAL_T_'+str(x),'F08_AVAL',(x,-43,69),'ConsoleF08AvalBas')

    saddle=box('SelleDepartESC1',(6,3,9.8),(-73,-57,66.5));parts.append(saddle)
    station('F02_1_ECHELLE_ARR','F02_1',(-70,-55.5,79),'SelleDepartESC1')
    bar('RepriseDepartESC1Avant',(-65.8,-82,69),(-65.8,-76,79))
    bar('LongeDepartESC1Avant',(-65.8,-76,79),(-65.8,-68,79))
    station('F02_1_ECHELLE_AV','F02_1',(-70,-70,79),'LongeDepartESC1Avant')

    # Les départs ESC suivent des longes communes, avant les selles des bras.
    beam('LongeESC1Transverse',(-60,-24.2,79),(15,-24.2,79),3,5)
    for x in (-44,-25):
        bar('MontantLongeESC1',(x,-55.5,69),(x,-55.5,79))
        bar('RepriseLongeESC1',(x,-55.5,79),(x,-24.2,79))
    for x in (-55,-15,10):station('F02_1_TRANS_'+str(x),'F02_1',(x,-20,79),'LongeESC1Transverse')

    beam('LongeESCEst',(88.2,-56,51),(88.2,68,51),3,8)
    for y in (35,65):station('F02_2_EST_'+str(y),'F02_2',(84,y,52-(y-24)*.04),'LongeESCEst')
    beam('LongeESCArriere',(-78,87.2,47),(18,87.2,47),3,6)
    # Contourner la contrefiche du retour caméra P78, sans changer les
    # ancrages ni les stations de gaine portées par cette traverse.
    bar('RepriseESCArriereEst',(18,87.2,54.2),(78,87.2,54.2))
    bar('DetourESCArriereEstA',(78,87.2,54.2),(78,91,54.2))
    bar('DetourESCArriereEstB',(78,91,54.2),(90,91,54.2))
    bar('DetourESCArriereEstC',(90,91,54.2),(90,87.2,54.2))
    bar('DetourESCArriereEstD',(90,87.2,54.2),(88.2,87.2,54.2))
    bar('MontantRepriseESCArriereEst',(18,87.2,47),(18,87.2,54.2))
    bar('RepriseESCEstCourbe',(88.2,87.2,54.2),(88.2,68,54.2))
    bar('JonctionESCEstArriere',(88.2,68,54.2),(88.2,68,51))
    # Appui latéral sur le montant de P72, accessible au collier au-dessus P64.
    beam('ContactESCArriereP72',(-86,61.5,46),(-80,61.5,46),3,6)
    bar('PiedESCArriereP72',(-80,61.5,46),(-80,61.5,48.2))
    bar('RetourESCArriereP72',(-80,61.5,48.2),(-80,87.2,48.2))
    for x in (-65,-25,15):station('F02_3_ARR_'+str(x),'F02_3',(x,83,44),'LongeESCArriere')
    bar('LongeESC4Avant',(66.2,-72,45.3333333333),(66.2,-42,51.0476190476))
    bar('RepriseESC4Avant',(66.2,-55.5,69),(66.2,-55.5,48.4761904762))
    for y in (-50,-65):station('F02_4_AV_'+str(y),'F02_4',(62,y,52+(y+37)*8/42),'LongeESC4Avant')
    for cable,point,direction,origin in [
        ('F02_2',(100,96.6666666667,50),(24,34,0),(88.2,87.2,54.2)),
        ('F02_3',(-96,95.5,44),(24,-25,0),(-78,87.2,47)),
        ('F02_4',(90,-96.652173913,44),(46,-29,0),(88,-88,44))]:
        unit=A.Vector(*direction);unit.normalize()
        normal=A.Vector(-unit.y,unit.x,0)*4.2
        axis=A.Vector(*point)+normal
        bar('LongeTransition'+cable,tuple(axis-unit*6),tuple(axis+unit*6))
        bar('RepriseTransition'+cable,origin,tuple(axis))
        station(cable+'_DIAG',cable,point,'LongeTransition'+cable)
    bar('PiedTransitionF02_4',(88,-88,59.5),(88,-88,44))

    # Dégager les deux colonnes OEM proches du bord de la traverse arrière.
    rear=next(o for o in parts if o.Name.startswith('TraverseAvecGorgeF08'))
    for x in (-52,52):
        tool=api.cylinder(document,'DegagementColonneOEM',2.7,10,(x,-52,64))
        tool.Placement=inverse.multiply(tool.Placement);history.append(tool)
        cut=document.addObject('Part::Cut','TraverseHorsColonnesOEM')
        cut.Base,cut.Tool=rear,tool;history.append(cut);parts.remove(rear);parts.append(cut);rear=cut

    # Retenues proches du coupe-circuit, portées par la traverse basse F37.
    beam('RetourF37PosAvant',(102,-84.05,-40),(114,-84.05,-40))
    bar('RepriseRetourF37PosVerticale',(104,-84.05,-40),(104,-84.05,-66))
    bar('RepriseRetourF37PosBasse',(104,-84.05,-66),(104,-64,-66))
    station('F37_POS_AV','F37_POS',(108,-89,-40),'RetourF37PosAvant')
    for cable,x,ys in [('F38_POS',103.05,(-55,-42)),('F38_NEG',113.05,(-66,-42))]:
        beam('LongeSortieQS8'+cable,(x,ys[0],-51),(x,ys[1],-51),3,6)
        bar('RepriseSortieQS8'+cable,(x,-64,-66),(x,-50,-51))
        station(cable+'_QS8',cable,(108 if cable=='F38_POS' else 118,-50 if cable=='F38_POS' else -55,-51),'LongeSortieQS8'+cable)
    for cable,a,b,point,axis in [
        ('F38_POS',(104,-61.05,-37.4),(99.5,-61.05,-22.1),(101.8235294118,-66,-30),(101.8235294118,-61.05,-30)),
        ('F38_NEG',(114,-74.05,-39.6666666667),(107.5,-74.05,-21.25),(108.8235294118,-79,-25),(108.8235294118,-74.05,-25))]:
        bar('LongeRemontee'+cable,a,b)
        bar('PiedRemontee'+cable,(axis[0],-64,-66),(axis[0],axis[1],-66))
        bar('MontantRemontee'+cable,(axis[0],axis[1],-66),axis)
        station(cable+'_BIAIS',cable,point,'LongeRemontee'+cable)

    result=document.addObject('Part::MultiFuse','P73AvecEchelleDistribution')
    result.Shapes=[base]+parts;result.Refine=True
    if base in root.Group:root.removeObject(base)
    root.addObject(result);document.recompute()
    for obj in [base]+history:obj.Visibility=False
    result.Visibility=True;api.color(result,(.34,.38,.43))
    spec={'reference_porteuse':'P73','stations':stations,'colliers_cables':len(stations),
        'colliers_liaison_P72':3,'vis_supplementaires':0,
        'contacts_P72_mm':[[-89,-55.5,66.5],[-89,-82,66.5],[-86,61.5,46]],
        'montage':'Deux colliers de liaison entourent les pieds terminaux et la longe F38 de P72 ; un troisième entoure le montant de P72 et sa reprise arrière à Z46, au-dessus de P64. Aucun collage ni fusion interdocuments.',
        'matiere_candidate':'PA12','qualification':'À valider',
        'limites':['Appuis nominaux ; rigidité, fluage, tenue vibratoire et tolérances non qualifiés.',
                   'Les boucles et têtes des colliers restent à contrôler sans écrasement des gaines.',
                   'Ébavurer et adoucir les surfaces ; aucun appui sur carte électronique.']}
    api.meta(root,'RetenuesDistribution',json.dumps(spec,ensure_ascii=False))
    return result,spec


def extend_battery_branches(api, document, root, base):
    """Appuis F01 positif/négatif et BALANCE sur P72, sans toucher au pack."""
    inverse=root.getGlobalPlacement().inverse()
    members,stations=[],[]
    def beam(name,a,b,width=3,height=6):
        dx,dy=b[0]-a[0],b[1]-a[1];angle=math.atan2(dy,dx)
        obj=api.box(document,name,(math.hypot(dx,dy),width,height),
                    (a[0]+width/2*math.sin(angle),a[1]-width/2*math.cos(angle),a[2]-height/2))
        obj.Placement.Rotation=A.Rotation(A.Vector(0,0,1),math.degrees(angle))
        obj.Placement=inverse.multiply(obj.Placement);members.append(obj);return obj
    def bar(name,a,b):
        delta=A.Vector(*b)-A.Vector(*a)
        obj=api.cylinder(document,name,1.5,delta.Length,a)
        obj.Placement.Rotation=A.Rotation(A.Vector(0,0,1),delta)
        obj.Placement=inverse.multiply(obj.Placement);members.append(obj);return obj
    def station(identifier,cable,point,support):
        stations.append({'id':identifier,'cables':[cable],'point_mm':list(point),
            'support':'P72/'+support,'type':'collier autour appui et gaine',
            'largeur_collier_mm':4.6,'statut':'À valider'})

    # Deux montants reprennent le ruban F01 existant, en dehors du softpack.
    beam('LongeF01PosBasse',(-112.05,-34,-50),(-112.05,-10,-50))
    for y in (-34,-10):
        bar('MontantF01PosBas',(-112.05,y,-50),(-112.05,y,-6.5))
    for y in (-30,-15):
        station('F01_POS_BAS_'+str(y),'F01_POS',(-117,y,-50),'LongeF01PosBasse')

    # F01 négatif : la remontée et son retour passent au-delà des faces du pack.
    beam('DoigtF01NegVertical',(-107.55,53,-34),(-88,53,-34),6,6)
    beam('LongeF01NegRetour',(-102,38.95,-16),(-87,38.95,-16))
    beam('LongeF01NegBasse',(-106.05,20,-50),(-106.05,40,-50))
    bar('RepriseF01NegBasse',(-106.05,40,-50),(-106.05,53,-34))
    station('F01_NEG_BAS','F01_NEG',(-111,30,-50),'LongeF01NegBasse')
    bar('LongeF01PosBiais',(-114.5,-39.05,-40.625),(-107.5,-39.05,-14.375))
    bar('RepriseF01PosBiaisBas',(-114.5,-39.05,-40.625),(-112.05,-34,-50))
    bar('RepriseF01PosBiaisHaut',(-107.5,-39.05,-14.375),(-112.5,-38,-6.5))
    station('F01_POS_BIAIS','F01_POS',(-111,-44,-27.5),'LongeF01PosBiais')
    station('F01_NEG_M','F01_NEG',(-111,53,-34),'DoigtF01NegVertical')
    station('F01_NEG_H','F01_NEG',(-96,34,-16),'LongeF01NegRetour')

    # BALANCE rejoint le même doigt par l'extérieur X-101,55, hors softpack.
    bar('LongeBalanceVerticale',(-101.55,21,-37),(-101.55,21,-12))
    bar('RepriseBalanceExterieure',(-101.55,21,-34),(-101.55,53,-34))
    beam('DoigtBalanceHaut',(-102,39.45,-5),(-81.2,39.45,-5))
    normal=A.Vector(-8,25,0);normal.normalize();normal=normal*3.45
    a=A.Vector(-76,37.28,-5)+normal;b=A.Vector(-60,42.4,-5)+normal
    beam('LongeBalanceDiagonale',(a.x,a.y,a.z),(b.x,b.y,b.z))
    beam('RepriseBalanceDiagonale',(-88,a.y,-5),(a.x,a.y,-5))
    station('BALANCE_D','BALANCE',(-65,40.8,-5),'LongeBalanceDiagonale')
    station('BALANCE_V','BALANCE',(-105,21,-25),'LongeBalanceVerticale')
    station('BALANCE_H','BALANCE',(-96,36,-5),'DoigtBalanceHaut')
    beam('LongeRetourF38Neg',(-81.95,-92,52),(-81.95,-60,52))
    bar('RepriseRetourF38Neg',(-91,-80,64.5),(-81.95,-80,52))
    for y in (-85,-65):station('F38_NEG_RETOUR_'+str(y),'F38_NEG',(-77,y,52),'LongeRetourF38Neg')
    beam('LongeRetourF38Pos',(-69.95,-83,52),(-69.95,-74,52))
    bar('RepriseRetourF38PosHaute',(-91,-80,64.5),(-69.95,-80,64.5))
    bar('RepriseRetourF38PosBasse',(-69.95,-80,64.5),(-69.95,-80,52))
    station('F38_POS_RETOUR','F38_POS',(-65,-80,52),'LongeRetourF38Pos')

    point=A.Vector(-100,-93.2307692308,65.5384615385)
    direction=A.Vector(-13,-24,-35);direction.normalize()
    normal=A.Vector(24,-13,0);normal.normalize()
    axis=point+normal*4.2
    bar('LongeTransitionF02_1',tuple(axis-direction*6),tuple(axis+direction*6))
    bar('RepriseTransitionF02_1',(-91,axis.y,64.5),tuple(axis))
    station('F02_1_DIAG','F02_1',tuple(point),'LongeTransitionF02_1')

    result=document.addObject('Part::MultiFuse','P72AvecBranchesBatterie')
    result.Shapes=[base]+members;result.Refine=True
    if base in root.Group:root.removeObject(base)
    root.addObject(result);document.recompute()
    for obj in [base]+members:obj.Visibility=False
    result.Visibility=True;api.color(result,(.34,.38,.43))
    spec={'reference_porteuse':'P72','stations':stations,'colliers_cables':len(stations),
          'vis_supplementaires':0,'matiere_candidate':'PA12','qualification':'À valider',
          'limites':['Appuis nominaux ; jeu, abrasion, rigidité et vibration À valider.',
                     'Aucun ancrage ni serrage dans le softpack ; colliers démontables sur les guides.',
                     'Boucles et têtes des colliers, extraction batterie et décharge de traction à vérifier au montage.']}
    api.meta(root,'RetenuesBranchesBatterie',json.dumps(spec,ensure_ascii=False))
    return result,spec
