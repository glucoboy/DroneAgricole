"""Extensions natives candidates des guides pour les portées de puissance.

Appel après construction du guide existant : extend_low(api,d,root,base,side).
Les rubans hauts de 8 mm évitent les longues tiges rondes en porte-à-faux.
Les stations sont des interfaces de colliers ; résistance et serrage à valider.
"""
import json
import math
import FreeCAD as A


def extend_low(api,document,root,base,side):
    """side='left' pour P72, 'right' pour P73 ; coordonnées globales.

    Appeler après définition du Placement du groupe (demi-tour pour P73).
    Les coordonnées globales des extensions sont converties dans son repère
    local ; le résultat natif existant et son placement restent conservés.
    """
    if side not in ('left','right'):raise ValueError('side doit être left ou right')
    members=[];stations=[]
    def beam(name,a,b,width=4,height=8):
        if abs(a[2]-b[2])>1e-6:raise ValueError('Ruban horizontal requis')
        dx=b[0]-a[0];dy=b[1]-a[1];length=math.hypot(dx,dy)
        theta=math.atan2(dy,dx)
        o=api.box(document,name,(length,width,height),(a[0]+width/2*math.sin(theta),a[1]-width/2*math.cos(theta),a[2]-height/2))
        o.Placement.Rotation=A.Rotation(A.Vector(0,0,1),math.degrees(theta));members.append(o);return o
    def bar(name,a,b,diameter=3):
        delta=A.Vector(*b)-A.Vector(*a)
        o=api.cylinder(document,name,diameter/2,delta.Length,a);o.Placement.Rotation=A.Rotation(A.Vector(0,0,1),delta)
        members.append(o);return o
    def station(id,cable,point,support):
        stations.append({'id':id,'cable':cable,'point_mm':list(point),'support':support,'collier_largeur_mm':4.6,
                         'montage':'collier autour du ruban ou de la barre et du conducteur ; serrage sans écrasement'})
    if side=='left':
        # Reprise gauche du grand ruban F01 : au-dessus de F01_NEG, hors BMS.
        beam('RepriseGaucheF01',(-112.5,56,-6.5),(-112.5,-38,-6.5))
        beam('JonctionMontantF01',(-112.5,56,-6.5),(-88,56,-6.5))
        beam('RetourF01Gauche',(-112.5,-38,-6.5),(-88,-38,-6.5),4,4)
        members.append(api.box(document,'TalonF01Gauche',(4,4,8),(-90,-42,-16.5)))
        # Les deux faces de contact entre guides seront retenues par colliers.
        beam('RepriseGaucheF38',(-91,56,64.5),(-91,-106,64.5),4,4)
        beam('JonctionGaucheF38',(-91,56,64.5),(-88,56,64.5),4,4)
        # Appui F40 parallèle au câble vertical ; profil renforcé 5,2×4.
        p=api.box(document,'LongeF40',(5.2,4,68),(-102.9,-36,-4));members.append(p)
        bar('LiaisonF40Basse',(-100.3,-34,-2),(-112.5,-34,-6.5),3)
        beam('LiaisonF40Haute',(-100.3,-34,64),(-88,56,64),4,4)
        for z in (5,50):station('F40_'+str(z),'F40',(-96,-34,z),'LongeF40')
    else:
        beam('RubanF01Pos',(-98,-44,-12.5),(88,-44,-12.5))
        beam('RepriseDroiteF01',(88,-44,-12.5),(88,-56,-12.5))
        for x in (-90,-45,0,15):station('F01_POS_'+str(x),'F01_POS',(x,-44,-5),'RubanF01Pos')
        for suffix,y in [('Pos',-94),('Neg',-104)]:
            beam('RubanF38'+suffix,(-89,y,59.5),(98,y,59.5))
            for x in (-50,-5,40,82):station('F38_'+suffix+'_'+str(x),'F38_'+suffix.upper(),(x,y,52),'RubanF38'+suffix)
        beam('RepriseDroiteF38',(88,-56,59.5),(88,-104,59.5))
        # Deux montantes courtes proches de P73, diamètre 3 pour préserver les coudes.
        for suffix,x,y in [('Pos',93,-66),('Neg',101,-79)]:
            bar('MontanteF38'+suffix,(x,y,-9),(x,y,47),3)
            for z in (-5,35):station('F38_M_'+suffix+'_'+str(z),'F38_'+suffix.upper(),(x+5,y,z),'MontanteF38'+suffix)
            for label,z in [('Bas',-9),('Haut',47)]:
                if suffix=='Neg':
                    bar('Appui'+label+'F38NegA',(88,-56,z),(88,y,z),3)
                    bar('Appui'+label+'F38NegB',(88,y,z),(x,y,z),3)
                else:bar('Appui'+label+'F38Pos',(88,-56,z),(x,y,z),3)
        beam('RubanF37Pos',(123,-78,-40),(123,32,-40),3,8)
        bar('AppuiF37PosAvantBas',(88,-64,-66),(123,-64,-66),4)
        bar('AppuiF37PosAvantRetour',(123,-64,-66),(123,-64,-40),3)
        bar('AppuiF37PosArriereHaut',(88,-59,-5),(123,-59,-5),4)
        bar('AppuiF37PosArriere',(123,-59,-5),(123,15,-40),3)
        for y in (-65,-20,25):station('F37_POS_'+str(y),'F37_POS',(128,y,-40),'RubanF37Pos')
        beam('AppuiF37NegHorizontal',(77,20,-20.5),(105,20,-20.5),4,2)
        beam('RepriseF37Neg',(88,-56,-20.5),(88,20,-20.5),4,2)
        bar('AppuiF37NegVertical',(113,25,-43),(113,25,-28),3)
        bar('JonctionF37Neg',(105,20,-20.5),(113,25,-30),3)
        station('F37_NEG_H','F37_NEG',(86,20,-16),'AppuiF37NegHorizontal')
        station('F37_NEG_V','F37_NEG',(118,25,-32),'AppuiF37NegVertical')
    inverse=root.getGlobalPlacement().inverse()
    for item in members:item.Placement=inverse.multiply(item.Placement)
    union=document.addObject('Part::MultiFuse','GuideAvecRetenuesPuissance');union.Shapes=[base]+members;union.Refine=True
    if base in root.Group:root.removeObject(base)
    root.addObject(union);document.recompute()
    for item in [base]+members:item.Visibility=False
    union.Visibility=True;api.color(union,(.34,.38,.43))
    spec={'cote':side,'stations':stations,'colliers_cables':len(stations),
          'colliers_liaison_guides':3 if side=='left' else 0,'vis_supplementaires':0,
          'entraxe_cible_colliers_mm':50,'matiere_candidate':'PA12',
          'limites':['Profil de ruban 4×8 mm pour les grandes traversées ; rigidité et fatigue vibratoire non qualifiées.',
                     'Colliers 4,6 mm à poser sur chaque station avant mise en service ; leur géométrie souple est hors de cette fonction.',
                     'F01_NEG ne présente pas de grande droite >50 mm ; sa retenue locale reste à contrôler dans l’ensemble.',
                     'Le rayon constructeur des conducteurs et leurs terminaisons restent À valider sur le lot réel.'],
          'statut':'À valider'}
    api.meta(root,'RetenuesPuissance',json.dumps(spec,ensure_ascii=False))
    return union,spec
