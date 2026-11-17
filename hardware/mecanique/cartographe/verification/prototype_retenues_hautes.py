"""Extensions candidates du cadre P75 pour retenir les lignes avioniques.

Primitives natives éditables ; rayons de câbles inchangés. Les stations sont
des interfaces de colliers, jamais une qualification de serrage ou de rigidité.
"""
import json
import FreeCAD as A


def layout():
    members=[];stations=[]
    def bar(name,a,b,d=3):
        members.append({'nom':name,'debut_mm':list(a),'fin_mm':list(b),'diametre_mm':d})
    def station(name,cable,p,support,kind='collier autour barre et gaine'):
        stations.append({'id':name,'cables':[cable],'point_mm':list(p),'support':'P75/'+support,
                         'type':kind,'largeur_collier_mm':4.6,'jeu_nominal_mm':.2})
    # Les deux traverses avant reprennent les grandes portées à leur altitude.
    bar('LisseF31Avant',(-98,-76,154.8),(79,-76,154.8))
    bar('LisseF24BAvant',(-61,-72,116.1),(68,-72,116.1))
    for x in (-60,60):bar('RepriseF31Avant'+str(x),(x,-55,145),(x,-76,154.8))
    for x in (-50,40):bar('RepriseF24BAvant'+str(x),(x,-55,112),(x,-72,116.1))
    for x in (-80,-40,0,40,70):station('F31_AV_'+str(x),'F31',(x,-76,158),'LisseF31Avant')
    for x in (-50,-15,20,55):station('F24B_AV_'+str(x),'F24B',(x,-72,119),'LisseF24BAvant')
    bar('LisseF31Est',(88.2,-68,158),(88.2,-21,158))
    bar('RepriseF31EstA',(80,-55,145),(88.2,-55,150))
    bar('RepriseF31EstB',(88.2,-55,150),(88.2,-55,158))
    for y in (-58,-28):station('F31_EST_'+str(y),'F31',(85,y,158),'LisseF31Est')
    # Échelle gauche : trois montantes, deux traverses communes vers P75.
    for z in (99,139):
        bar('EchelleGauche'+str(z),(-78,-55,z),(-78,-76,z))
        for tag,x,y in [('F06',-88.6,-62),('F32',-94.6,-70),('F31',-100.8,-76)]:
            bar('BrasGauche'+tag+str(z),(-78,y,z),(x,y,z))
    for tag,x,y,zmax,cx in [('F06',-88.6,-62,144.5,-92),('F32',-94.6,-70,143,-98),('F31',-100.8,-76,152,-104)]:
        if tag=='F06':
            bar('Montante'+tag,(x,y,82),(x,y,122))
            bar('Montante'+tag+'Haut',(x,y,134),(x,y,zmax))
        else:bar('Montante'+tag,(x,y,82),(x,y,zmax))
        for z in ((91,139) if tag=='F06' else (91,131)):
            station(tag+'_MON_'+str(z),tag,(cx,y,z),'Montante'+tag+('Haut' if tag=='F06' and z==139 else ''))
    # Traverse basse arrière et cales sur la traverse P75 pour PPS.
    bar('LisseF12Arriere',(-11,43,111),(69,43,111))
    for x in (-10,35,60):bar('RepriseF12'+str(x),(x,55,112),(x,43,111))
    for x in (0,35,65):station('F12_AR_'+str(x),'F12',(x,43,114),'LisseF12Arriere')
    for x in (-60,-30,0,35,65):
        bar('CaleF24A'+str(x),(x,55,113),(x,55,116.6))
        station('F24A_AR_'+str(x),'F24A',(64.5 if x==65 else x,55,118),'CaleF24A'+str(x),
                'collier autour traverse P75 et cale')
    # Grande portée haute côté droit ; reprise aux quatre coins existants.
    bar('LisseF24CEst',(80.9,-55,155),(80.9,55,155))
    for y in (-55,55):bar('RepriseF24CEst'+str(y),(80,y,151),(80.9,y,155))
    for y in (-45,-10,25,50):station('F24C_EST_'+str(y),'F24C',(78,y,155),'LisseF24CEst')
    bar('LisseF24CArriere',(33,61,113.1),(72,61,113.1))
    for x in (35,68):bar('RepriseF24CArriere'+str(x),(x,55,112),(x,61,113.1))
    for x in (40,65):station('F24C_AR_'+str(x),'F24C',(x,61,116),'LisseF24CArriere')
    # Montantes de commande moteur, reprises près des coins P75.
    for tag,cx,cy,bx,by,zmax in [('F04_1',-84,-58,-81.5,-58,108),('F04_2',74,58,74,60.5,108),
                               ('F04_3',-76,66,-76,68.5,108),('F04_4',76,-66,73.5,-66,113)]:
        bar('Montante'+tag,(bx,by,47),(bx,by,zmax))
        sx=-80 if cx<0 else 80;sy=-55 if cy<0 else 55
        if tag=='F04_4':bar('BrasMontante'+tag,(bx,sy,112),(bx,by,99))
        else:
            bar('BrasCoin'+tag,(sx,sy,99),(sx,by,99))
            bar('BrasMontante'+tag,(sx,by,99),(bx,by,99))
        for z in (55,91):station(tag+'_MON_'+str(z),tag,(cx,cy,z),'Montante'+tag)
    # F08 aval : décharge de la montée à gauche du stack.
    bar('MontanteF08Aval',(-90,-43,78),(-90,-43,109))
    bar('RepriseF08Aval',(-80,-43,112),(-90,-43,105))
    for z in (85,103):station('F08_AVAL_MON_'+str(z),'F08_AVAL',(-94,-43,z),'MontanteF08Aval')
    # Retours hauts des alimentations et liaison CA01/Jetson.
    bar('RetourF06',(-88.6,-62,144.5),(-88.6,-56,150.5))
    bar('LisseF06Haut',(-88.6,-56,150.5),(-88.6,-20,150.5))
    for y in (-46,-25):station('F06_HAUT_'+str(y),'F06',(-92,y,150.5),'LisseF06Haut')
    bar('LisseF06Terminal',(-84,-14,147.1),(-66,-14,147.1))
    bar('RepriseF06Terminal',(-80,-14,145),(-80,-14,147.1))
    station('F06_TERM','F06',(-75,-14,150.5),'LisseF06Terminal')
    bar('LisseF32Haut',(-101.4,-64,149),(-101.4,-2,149))
    bar('RepriseF32HautA',(-80,-20,145),(-101.4,-20,145))
    bar('RepriseF32HautB',(-101.4,-20,145),(-101.4,-20,149))
    for y in (-52,-17):station('F32_HAUT_'+str(y),'F32',(-98,y,149),'LisseF32Haut')
    bar('LisseF32Terminal',(-90,4,145.6),(-64,4,145.6))
    station('F32_TERM','F32',(-76,4,149),'LisseF32Terminal')
    bar('MontanteF09',(-89.8,-4,128),(-89.8,-4,146))
    bar('RepriseF09',(-80,-4,145),(-89.8,-4,137))
    station('F09_MON','F09',(-94,-4,137),'MontanteF09')
    for tag,z,az in [('Haut',150.8,145),('Bas',114.8,112)]:
        bar('LisseF09'+tag,(-85,-4,z),(-72,-4,z))
        bar('RepriseF09'+tag,(-80,-4,az),(-80,-4,z))
        station('F09_'+tag,'F09',(-76,-4,z+4.2),'LisseF09'+tag)
    # Compléments arrière/est et retour caméra vers l'extracteur CSI.
    bar('LisseF24CAvant',(41,-60,152.1),(72,-60,152.1))
    bar('RepriseF24CAvant',(45,-55,145),(45,-60,152.1))
    station('F24C_AV','F24C',(54,-60,155),'LisseF24CAvant')
    bar('MontanteF24C',(80.9,61,122),(80.9,61,149))
    bar('RetourF24CHaut',(80.9,55,155),(80.9,61,149))
    bar('RepriseF24CMon',(80,55,127),(80.9,61,127))
    station('F24C_MON','F24C',(78,61,135),'MontanteF24C')
    bar('MontanteF12',(78,30,120),(78,30,143))
    bar('RepriseF12Mon',(80,30,145),(78,30,140))
    station('F12_MON','F12',(75,30,130),'MontanteF12')
    bar('MontanteF33',(77.9,35,128),(77.9,35,147))
    station('F33_MON','F33',(75,35,138),'MontanteF33')
    bar('LisseF33Haut',(72.1,29,153),(72.1,2,153))
    bar('RepriseF33HautA',(72.1,2,153),(72.1,2,145))
    bar('RepriseF33HautB',(72.1,2,145),(80,2,145))
    station('F33_HAUT','F33',(75,16,153),'LisseF33Haut')
    bar('LisseF33Arriere',(23,50.483,119.1),(69,46.517,119.1))
    for x,y in [(35,49.448),(60,47.293)]:
        bar('RepriseF33Arriere'+str(x),(x,55,112),(x,y,119.1))
        station('F33_AR_'+str(x),'F33',(x,y,122),'LisseF33Arriere')
    bar('MontanteF35',(72.9,-45,123),(72.9,-45,137))
    bar('RepriseF35Mon',(80,-45,145),(72.9,-45,132))
    station('F35_MON','F35',(70,-45,126),'MontanteF35')
    bar('LisseF35Haut',(70,-39,140.1),(70,-16.5,140.1))
    bar('RepriseF35HautA',(80,-26,145),(80,-26,140.1))
    bar('RepriseF35HautB',(80,-26,140.1),(70,-26,140.1))
    station('F35_HAUT','F35',(70,-27,143),'LisseF35Haut')
    # F21 Ethernet : échelle arrière et lisse haute indépendante des cartes.
    bar('LisseF21Arriere',(-2,51,92.8),(60.5,51,92.8))
    for x in (0,35):
        bar('RepriseF21Basse'+str(x),(x,51,92.8),(x,55,92.8))
        bar('RepriseF21Verticale'+str(x),(x,55,92.8),(x,55,112))
        station('F21_AR_'+str(x),'F21',(x+5,51,96),'LisseF21Arriere')
    bar('MontanteF21',(63.3,51,102),(63.3,51,151))
    for z in (112,145):
        bar('RepriseF21MonY'+str(z),(63.3,55,z),(63.3,51,z))
    for z in (113,143):station('F21_MON_'+str(z),'F21',(66.5,51,z),'MontanteF21')
    bar('RetourF21Haut',(63.3,51,151),(63.3,45,157))
    bar('LisseF21Haut',(63.3,45,157),(63.3,1.5,157))
    for y in (35,8):station('F21_HAUT_'+str(y),'F21',(66.5,y,157),'LisseF21Haut')
    # F25 : montant, lisse supérieure et décharge proche du port GPS1.
    bar('MontanteF25',(65.3,-48,104),(65.3,-48,156))
    bar('RepriseF25',(65.3,-55,112),(65.3,-48,112))
    for z in (112,145):station('F25_MON_'+str(z),'F25',(62,-48,z),'MontanteF25')
    bar('RetourF25Haut',(65.3,-48,156),(65.3,-42,162))
    bar('LisseF25Haut',(65.3,-42,162),(65.3,16,162))
    for y in (-30,5):station('F25_HAUT_'+str(y),'F25',(62,y,162),'LisseF25Haut')
    bar('RepriseF25Terminal',(65.3,16,165.3),(44.5,16,165.3))
    bar('RepriseF25TerminalZ',(65.3,16,165.3),(65.3,16,162))
    bar('RepriseF25FinaleZ',(44.5,16,165.3),(44.5,16,151))
    bar('RepriseF25FinaleY',(44.5,16,151),(44.5,9.5,151))
    bar('RepriseF25FinaleX',(44.5,9.5,151),(46.6429,9.5,151))
    bar('LisseF25Finale',(46.0967,9.5,154),(47.1892,9.5,148))
    station('F25_TERM','F25',(50.0029,9.5,151),'LisseF25Finale')
    # GNSS court et ventilateur : une bride chacun hors prises.
    bar('LisseF36',(5.75,75,97),(7.25,65,97))
    bar('RepriseF36A',(12,55,112),(12,55,94))
    bar('RepriseF36B',(12,55,94),(12,70,94))
    bar('RepriseF36C',(12,70,94),(6.5,70,97))
    station('F36_L','F36',(6.5,70,100),'LisseF36')
    bar('RepriseF20',(-55,55,145),(-55.2158,38.2,139))
    bar('LisseF20',(-55.3474,38.2,136.5),(-55.0842,38.2,141.5))
    station('F20_LOCAL','F20',(-52.3158,38.2,139),'LisseF20')
    # AIRY : appuis continus des trois branches, indépendants du connecteur.
    bar('MontanteAiryEth',(-84.45,64,126),(-84.45,64,153))
    bar('RepriseAiryEthMonX',(-80,55,127),(-84.45,55,127))
    bar('RepriseAiryEthMonY',(-84.45,55,127),(-84.45,64,127))
    station('AIRY_ETH_MON','AIRY_ETH',(-80,64,140),'MontanteAiryEth')
    bar('LisseAiryEthArriere',(-69,65.183,155.55),(6,73.247,155.55))
    for x,y in [(-60,66.151),(-20,70.452)]:
        bar('RepriseAiryEthArriere'+str(x),(x,55,145),(x,y,155.55))
        station('AIRY_ETH_AR_'+str(x),'AIRY_ETH',(x,y,160),'LisseAiryEthArriere')
    bar('LisseAiryEthRetour',(17.45,66,160),(17.45,58,160))
    bar('MontanteAiryEthFinale',(17.45,51,143),(17.45,51,154))
    bar('RepriseAiryEthFinale',(17.45,55,145),(17.45,51,145))
    bar('RetourAiryEthFinal',(17.45,51,154),(17.45,58,160))
    # Le retour n'offre que 1,87 mm droit : conserver le guide sans collier.
    # La verticale offre 3 mm droits ; réserver ici une bande étroite 2,5 mm.
    station('AIRY_ETH_FIN','AIRY_ETH',(13,51,148.5),'MontanteAiryEthFinale')
    stations[-1]['largeur_collier_mm']=2.5
    bar('LisseAiryPwrOuest',(-84.6,48,124.228),(-84.6,-56,127.61))
    for y,z in [(30,124.813),(-30,126.764)]:
        bar('RepriseAiryPwrOuest'+str(y),(-80,y,112),(-84.6,y,z))
        station('AIRY_PWR_O_'+str(y),'AIRY_PWR',(-88,y,z),'LisseAiryPwrOuest')
    bar('LisseAiryPwrAvant',(-80,-68,124.6),(-5,-68,124.6))
    for x in (-45,-10):
        bar('RepriseAiryPwrAvantZ'+str(x),(x,-55,112),(x,-55,124.6))
        bar('RepriseAiryPwrAvantY'+str(x),(x,-55,124.6),(x,-68,124.6))
        station('AIRY_PWR_AV_'+str(x),'AIRY_PWR',(x,-68,128),'LisseAiryPwrAvant')
    bar('LisseAiryPwrFinale',(3,-61,101.6),(3,-46,101.6))
    bar('RepriseAiryPwrFinaleZ',(-8,-55,112),(-8,-55,101.6))
    bar('RepriseAiryPwrFinaleX',(-8,-55,101.6),(3,-55,101.6))
    station('AIRY_PWR_FIN','AIRY_PWR',(3,-55,105),'LisseAiryPwrFinale')
    bar('LisseAirySyncArriere',(-71,63.75,117.05),(86,63.75,117.05))
    for x in (-40,50):
        bar('RepriseAirySyncArriereY'+str(x),(x,55,112),(x,63.75,112))
        bar('RepriseAirySyncArriereZ'+str(x),(x,63.75,112),(x,63.75,117.05),2)
    for x in (-55,-15,25,65):station('AIRY_SYNC_AR_'+str(x),'AIRY_SYNC',(x,64,120),'LisseAirySyncArriere')
    bar('LisseAirySyncEst',(96.95,58,118.468),(96.95,23,109.532))
    bar('RepriseAirySyncEstX',(80,35,112),(96.95,35,106))
    bar('RepriseAirySyncEstZ',(96.95,35,106),(96.95,35,112.596))
    station('AIRY_SYNC_EST','AIRY_SYNC',(94,35,112.596),'LisseAirySyncEst')
    bar('LisseAirySyncFinale',(88,19.95,107.172),(72,19.95,104.966))
    bar('RepriseAirySyncFinale',(80,21,112),(80,19.95,106.069))
    station('AIRY_SYNC_FIN','AIRY_SYNC',(80,17,106.069),'LisseAirySyncFinale')
    # Retours intermédiaires et proches des prises, avec mou terminal conservé.
    bar('LisseF24BGauche',(-69.9,-66,135),(-69.9,-56,135))
    bar('RepriseF24BGaucheZ',(-69.9,-55,112),(-69.9,-55,135))
    bar('RepriseF24BGaucheY',(-69.9,-55,135),(-69.9,-61,135))
    station('F24B_GAUCHE','F24B',(-67,-61,135),'LisseF24BGauche')
    bar('MontanteF24BHaut',(-69.9,-50,139.5),(-69.9,-50,146.5))
    bar('RepriseF24BHaut',(-69.9,-55,145),(-69.9,-50,145))
    station('F24B_MON_H','F24B',(-67,-50,143),'MontanteF24BHaut')
    bar('LisseF24AGauche',(-69.6,31,125.9),(-69.6,21,125.9))
    bar('RepriseF24AGaucheX',(-80,21,112),(-69.6,21,112))
    bar('RepriseF24AGaucheZ',(-69.6,21,112),(-69.6,21,125.9))
    station('F24A_GAUCHE','F24A',(-72.5,26,125.9),'LisseF24AGauche')
    bar('LisseF24AEst',(74.9,35,105.692),(74.9,48,113.692))
    bar('RepriseF24AEst',(80,40,112),(74.9,40,108.769))
    station('F24A_EST','F24A',(72,40,108.769),'LisseF24AEst')
    bar('LisseF25Basse',(6,-47.097,94.2),(56,-47.903,94.2))
    bar('RepriseF25BasseZ',(30,-55,112),(30,-55,94.2))
    bar('RepriseF25BasseY',(30,-55,94.2),(30,-47.484,94.2))
    for x in (15,45):station('F25_BAS_'+str(x),'F25',(x,-47-x/62,97.5),'LisseF25Basse')
    bar('LisseF25USL',(0,-79,94.2),(0,-53,94.2))
    bar('RepriseF25USL1',(10,-55,112),(10,-65,94.2))
    bar('RepriseF25USL2',(10,-65,94.2),(0,-65,94.2))
    station('F25_USL','F25',(0,-65,97.5),'LisseF25USL')
    bar('LisseF09Terminal',(-64.2,6,155),(-64.2,17.5,155))
    bar('RepriseF09Terminal',(-80,12,145),(-64.2,12,155))
    station('F09_TERM','F09',(-60,12,155),'LisseF09Terminal')
    bar('LisseF31Terminal',(60,-14.5,154.8),(72,-14.5,154.8))
    bar('RepriseF31Terminal',(80,-20,145),(70,-14.5,154.8))
    station('F31_TERM','F31',(65,-14.5,158),'LisseF31Terminal')
    # Commandes MAIN : lisses communes aux traverses et guides parallèles
    # aux diagonales entre peigne haut et descentes vers les quatre bras.
    bar('LisseF04Avant',(-78,-58,113.5),(93,-58,113.5))
    for x in (-65,-25,15,55,85):station('F04_1_AV_'+str(x),'F04_1',(x,-58,116),'LisseF04Avant')
    bar('LisseF04ArriereDroite',(80,58,113.5),(96,58,113.5))
    station('F04_2_AR','F04_2',(88,58,116),'LisseF04ArriereDroite')
    bar('LisseF04Arriere',(-70,66,113.5),(99,66,113.5))
    for x in (-50,40):
        bar('RepriseF04ArriereY'+str(x),(x,55,112),(x,66,111))
        bar('RepriseF04ArriereZ'+str(x),(x,66,111),(x,66,113.5))
    for x in (-60,-20,20,60,90):station('F04_3_AR_'+str(x),'F04_3',(x,66,116),'LisseF04Arriere')
    bar('LisseF04AvantDroite',(82,-66,125.5),(102,-66,125.5))
    bar('RepriseF04AvantDroite',(80,-55,127),(85,-66,125.5))
    station('F04_4_AV','F04_4',(91,-66,128),'LisseF04AvantDroite')
    diagonals=[
        ('F04_1',99,-37,163,-58,116,-40,-55,(-43,-52)),
        ('F04_2',102,-34,166,58,116,-27,51,(-20,10,40)),
        ('F04_3',105,-31,169,66,116,-24,59,(-15,20,55)),
        ('F04_4',108,-28,172,-66,128,-33,-61,(-40,-56))]
    for tag,x,y0,z0,y1,z1,ya,yb,ys in diagonals:
        def zz(y):return z0+(z1-z0)*(y-y0)/(y1-y0)
        bx=x+2.5
        bar('Diagonale'+tag,(bx,ya,zz(ya)),(bx,yb,zz(yb)))
        for y in ys:station(tag+'_DIAG_'+str(y),tag,(x,y,zz(y)),'Diagonale'+tag)
        if tag=='F04_1':
            bar('RepriseDiag'+tag+'X',(80,-55,145),(bx,-55,145))
            bar('RepriseDiag'+tag+'YZ',(bx,-55,145),(bx,-49,zz(-49)))
        elif tag=='F04_2':
            bar('RepriseDiag'+tag+'X',(80,0,145),(bx,0,135))
            bar('RepriseDiag'+tag+'Z',(bx,0,135),(bx,0,zz(0)))
        elif tag=='F04_3':
            bar('RepriseDiag'+tag+'X',(80,35,145),(bx,35,140))
            bar('RepriseDiag'+tag+'Z',(bx,35,140),(bx,35,zz(35)))
        else:
            bar('RepriseDiag'+tag+'X',(80,-55,145),(bx,-55,151))
            bar('RepriseDiag'+tag+'YZ',(bx,-55,151),(bx,-49,zz(-49)))
    # Sorties du PM08 : trois voies sur une échelle commune sous P75.
    bar('MontantEntreesPM08',(-78,-55,99),(-78,-55,69))
    bar('TraverseEntreesPM08',(-78,-55,69),(-78,-76,69))
    for tag,y,x0,x1,offset in [('F06',-62,-38,-92,3.4),('F32',-70,-28,-98,3.4),('F31',-76,-18,-104,3.2)]:
        def zz(x):return 73-(x-x0)/(x1-x0)
        bar('Entree'+tag,(x0-6,y,zz(x0-6)-offset),(x1+6,y,zz(x1+6)-offset))
        for x in (-55,-80):station(tag+'_ENT_'+str(x),tag,(x,y,zz(x)),'Entree'+tag)
    # Deux retenues rapprochées évitent la longue amorce de F24B côté est.
    bar('LisseF24BEntree',(76.9,-11,102.316),(76.9,-37,103.684))
    bar('RepriseF24BEntree',(80,-25,112),(76.9,-25,103.053))
    station('F24B_ENT','F24B',(74,-25,103.053),'LisseF24BEntree')
    bar('LisseF24BEst',(76.9,-49,119),(76.9,-61.5,119))
    bar('RepriseF24BEst',(80,-55,112),(76.9,-55,119))
    station('F24B_EST','F24B',(74,-55,119),'LisseF24BEst')
    for y in (0,-50):
        station('AIRY_PWR_O_'+str(y),'AIRY_PWR',(-88,y,124+(55-y)*4/123),'LisseAiryPwrOuest')
    station('AIRY_PWR_AV_m70','AIRY_PWR',(-70,-68,128),'LisseAiryPwrAvant')
    # Coaxiaux RP4TD : berceaux ouverts dont l'alésage reste plus grand que
    # le coaxial. Le collier ferme le berceau, sans serrage direct de gaine.
    for tag,p,direction in [('F13A',(-68.469999,18.897500,123.350000),(-.1940285,-.1455214,.9701425)),
                             ('F13B',(-71,-5,108),(0,1,0))]:
        x,y,z=p
        if tag=='F13A':
            bar('BrasRF'+tag,(-80,23.5,112),(x,23.5,z))
            bar('NezRF'+tag,(x,23.5,z),(x,y+1.7,z),2)
        else:
            bar('BrasRF'+tag,(-80,y,112),(-74,y,114))
            bar('CoudeRF'+tag,(-74,y,114),(-73,y,110),2)
            bar('NezRF'+tag,(-73,y,110),(-73,y,z),2)
        a=[p[i]-2.6*direction[i] for i in range(3)];b=[p[i]+2.6*direction[i] for i in range(3)]
        bar('Berceau'+tag,a,b,4 if tag=='F13A' else 5)
        members[-1].update({'alesage_mm':2.4,'ouverture_x_mm':x,'centre_mm':list(p)})
        if tag=='F13A':members[-1]['ouverture_axis']='Y-'
        station(tag+'_RF',tag,p,'Berceau'+tag,
                'collier autour berceau fendu ; coax libre dans alésage 2,4 mm, aucun serrage direct')
        stations[-1]['jeu_nominal_mm']=.4
    return members,stations


def extend_high(api,document,root,base):
    members,stations=layout();objects=[];by_name={}
    for m in members:
        a=A.Vector(*m['debut_mm']);delta=A.Vector(*m['fin_mm'])-a
        obj=api.cylinder(document,m['nom'],m['diametre_mm']/2,delta.Length,m['debut_mm'])
        obj.Placement.Rotation=A.Rotation(A.Vector(0,0,1),delta)
        if 'alesage_mm' in m:
            unit=delta/delta.Length;start=a-unit
            bore=api.cylinder(document,m['nom']+'Alesage',m['alesage_mm']/2,delta.Length+2,
                              (start.x,start.y,start.z))
            bore.Placement.Rotation=A.Rotation(A.Vector(0,0,1),delta)
            if m.get('ouverture_axis')=='Y-':
                opened=api.box(document,m['nom']+'Ouverture',(16,8,16),
                               (m['centre_mm'][0]-8,m['centre_mm'][1]-8,m['centre_mm'][2]-8))
            else:
                opened=api.box(document,m['nom']+'Ouverture',(8,16,16),
                               (m['ouverture_x_mm'],m['centre_mm'][1]-8,m['centre_mm'][2]-8))
            obj=api.boolean(document,root,obj,[bore,opened],m['nom']+'Fendu')
            if obj in root.Group:root.removeObject(obj)
        objects.append(obj);by_name[m['nom']]=obj
    # Unir localement ces cylindres obliques avant la grande union : OCCT
    # conserve sinon parfois la petite lisse comme solide séparé en natif.
    for name,pair in [('BrancheVentilateur',('RepriseF20','LisseF20')),
                      ('BrancheEntreeF24B',('RepriseF24BEntree','LisseF24BEntree'))]:
        union=document.addObject('Part::MultiFuse',name)
        union.Shapes=[by_name[n] for n in pair];union.Refine=False
        for obj in union.Shapes:objects.remove(obj);obj.Visibility=False
        objects.append(union)
    from CompoundTools.CompoundFilter import makeCompoundFilter
    binder=makeCompoundFilter('SolideP75AvantHautes',document)
    binder.Base=base;binder.FilterType='window-volume';binder.WindowFrom=99;binder.WindowTo=101
    document.recompute()
    result=document.addObject('Part::MultiFuse','P75AvecRetenuesHautes')
    # Refine provoque une erreur d'orientation OCCT sur les intersections
    # nombreuses des lisses. L'union brute conserve un solide valide et ses
    # limites de faces ; ne pas appliquer removeSplitter à cette sortie.
    result.Shapes=[binder]+objects;result.Refine=False
    if base in root.Group:root.removeObject(base)
    root.addObject(result);document.recompute()
    for obj in [base,binder]+objects:obj.Visibility=False
    api.color(result,(.34,.38,.43))
    spec={'stations':stations,'colliers_cables':len(stations),
          'colliers_par_largeur_mm':{'4.6':sum(s['largeur_collier_mm']==4.6 for s in stations),
                                    '2.5':sum(s['largeur_collier_mm']==2.5 for s in stations)},
          'materiau':'PA12 candidat',
          'limites':['Rigidité des longues barres, vibration, finition et serrage À valider.',
                     'Courbes et terminaisons restent libres ; colliers sur portions droites.',
                     'Qualification physique et boucles de colliers non démontrées par une absence d’intersection.'],
          'qualification':'À valider'}
    api.meta(root,'RetenuesHautes',json.dumps(spec,ensure_ascii=False))
    return result,spec
