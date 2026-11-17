"""Retenues natives des deux cordons caméra, sans déplacer leurs sorties.

Les stations désignent des passages de colliers démontables. Elles ne valent
pas validation de serrage, d'antiflexion ou de tenue vibratoire.
"""
import json
import FreeCAD as A


def extend_camera_usb_support(api, document, root, base):
    """Reprendre la traverse USB3 sur les deux traverses du cadre P75."""
    members=[]
    def bar(name,start,end):
        delta=A.Vector(*end)-A.Vector(*start)
        obj=api.cylinder(document,name,2,delta.Length,start)
        obj.Placement.Rotation=A.Rotation(A.Vector(0,0,1),delta)
        members.append(obj)
    # USB3 Ø5,5 : axe Y−105, appui Ø4 à 4,95 mm, jeu nominal 0,2.
    # La barre reste entre les deux arcs R22 du parcours.
    bar('TraverseUSB3',(29,-100.05,140.5),(74,-100.05,140.5))
    for x in (36,67):
        bar('RepriseUSB3',(x,-55,145),(x,-100.05,140.5))
    # Deux retenues sur la partie droite inclinée, entre les congés R22.
    def rise(y): return 90+(-54-y)*50.5/51
    bar('LongeUSB3Inclinee',(91.05,-65,rise(-65)),(91.05,-89,rise(-89)))
    bar('RepriseUSB3InclineeBasse',(80,-55,112),(91.05,-70,rise(-70)))
    bar('RepriseUSB3InclineeHaute',(67,-100.05,140.5),(91.05,-88,rise(-88)))
    document.recompute()
    # Les booléens de P75 peuvent livrer un Compound à un seul solide.
    # Le filtre de composé standard de FreeCAD expose le solide à OCCT en
    # conservant le lien paramétrique ; SubShapeBinder conserve un Compound.
    if len(base.Shape.Solids) != 1:
        raise ValueError('P75 doit avoir exactement un solide avant retenue USB3')
    from CompoundTools.CompoundFilter import makeCompoundFilter
    binder=makeCompoundFilter('SolideP75AvantUSB3',document)
    binder.Base=base
    binder.FilterType='window-volume'
    binder.WindowFrom=99
    binder.WindowTo=101
    document.recompute()
    result=document.addObject('Part::MultiFuse','P75AvecRetenueUSB3')
    result.Shapes=[binder]+members;result.Refine=True
    if base in root.Group:root.removeObject(base)
    root.addObject(result);document.recompute()
    for obj in [base,binder]+members:obj.Visibility=False
    api.color(result,(.34,.38,.43))
    spec={'stations':[{'id':'USB3_T_'+str(x),'cables':['F16'],
        'point_mm':[x,-105,140.5],'support':'P75/TraverseUSB3',
        'type':'collier autour barre et gaine','largeur_collier_mm':4.6}
        for x in (36,67)]+[{'id':'USB3_I_'+str(abs(y)),'cables':['F16'],
        'point_mm':[96,y,rise(y)],'support':'P75/LongeUSB3Inclinee',
        'type':'collier autour barre et gaine','largeur_collier_mm':4.6}
        for y in (-70,-88)],'jeu_nominal_mm':.2,'colliers_cables':4,
        'limites':['Parties courbes R22 libres ; retenue de gaine sans écrasement.',
                   'Rigidité PA12, tolérances et vibration À valider.'],
        'qualification':'À valider'}
    api.meta(root,'RetenueCameraUSB',json.dumps(spec,ensure_ascii=False))
    return result,spec


def build_camera_m8_support(api, document, root):
    """Selle arrière fixée sur P64 par deux colliers, hors suspension caméra."""
    members=[api.box(document,'PiedP64',(15.5,16,2.6),(78.5,72,39)),
             api.box(document,'RebordP64',(13,2,5.4),(81,88,36.2)),
             api.box(document,'AmeM8',(8,4,84),(68.5,99.2,-32))]
    for name,start,end in [
        ('PiedBrasM8',(84,86,40),(84,86,44.5)),
        ('PiedContreficheM8',(88,86,40),(88,86,44.5)),
        ('BrasM8',(84,86,44.5),(72.5,101.2,44.5)),
        ('ContreficheM8Haute',(88,86,44.5),(88,106,44.5)),
        ('ContreficheM8Basse',(88,106,44.5),(72.5,101,-20)),
        ('MontantM8Retour',(74.5,101.2,45),(71.331538,92.929951,86.576951)),
        ('AppuiM8Retour',(71.331538,92.929951,86.576951),(68.141796,86.550465,93.564075)),
        ('ContreficheM8Retour',(88,86,44.5),(68.141796,86.550465,93.564075))]:
        delta=A.Vector(*end)-A.Vector(*start)
        o=api.cylinder(document,name,2,delta.Length,start)
        o.Placement.Rotation=A.Rotation(A.Vector(0,0,1),delta)
        members.append(o)
    union=document.addObject('Part::MultiFuse','BrutRetenueM8')
    union.Shapes=members;union.Refine=True
    cuts=[api.box(document,'PassageCollierP64',(1.6,4.8,5),(x-.8,76.2,38))
          for x in (84,)]
    # Retour vers le bord X94 du plateau : la bande passe sous LED_2 dans une
    # gorge du pied, sans rencontrer les deux jambes à Y86. La couche restante
    # du pied vaut 1,2 mm ; sa tenue reste à vérifier sur pièce réelle.
    cuts.append(api.box(document,'GorgeRetourCollierP64',(11.8,4.8,2.4),(83.2,76.2,40.2)))
    result=api.boolean(document,root,union,cuts,'RetenueM8')
    document.recompute()
    for obj in members+[union]:obj.Visibility=False
    api.color(result,(.34,.38,.43))
    spec={'reference':'P78_Retenue_Camera_M8_Prototype',
        'stations':[{'id':'M8_V_'+str(z),'cables':['F_M8'],
            'point_mm':[72.5,106,z],'support':'P78/AmeM8',
            'type':'collier autour âme et gaine','largeur_collier_mm':4.6}
            for z in (-20,15,45)]+[{'id':'M8_RETOUR','cables':['F_M8'],
            'point_mm':[65.518588,92.037177,90.242099],'support':'P78/AppuiM8Retour',
            'type':'collier autour barre et gaine','largeur_collier_mm':4.6}],
        'fixation':{'support':'P64','colliers':1,'axes_lumieres_mm':[[84,78.6]],
            'passage':'Sous P64 dans le jeu Z33..36,2 ; retour autour du bord X94, bande dans la gorge Z40,3..41,5 sous LED_2. Rebord antirotation conservé. Aucun perçage OEM.',
            'lumiere_P64_reutilisee_mm':[84,78.6,6,4.8],
            'gorge_pied_mm':[83.2,76.2,40.2,11.8,4.8,1.4],
            'epaisseur_residuelle_pied_mm':1.2},
        'colliers_cables':4,'jeu_nominal_mm':.2,
        'limites':['PA12 candidat ; tenue du collier de pied et du rebord, rigidité, vibration et abrasion À valider.',
                   'La portion inférieure en arc R52 reste souple pour découpler la suspension caméra.',
                   'Engagement M8 e=6 mm est une hypothèse de montage, sans qualification électrique.'],
        'qualification':'À valider'}
    api.meta(root,'RetenueCameraM8',json.dumps(spec,ensure_ascii=False))
    return result,spec
