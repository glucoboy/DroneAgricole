"""Retenues natives des transitions de réserve USB et du bas du tronc Airy.

Extension du guide fixe P72. Les parcours sont conservés ; la portion Airy
entre capteur isolé et premier collier reste souple, sans pont rigide au capteur.
"""
import json
import FreeCAD as A


def extend_reserve_supports(api, document, root, base):
    members, stations = [], []
    inverse = root.getGlobalPlacement().inverse()

    def bar(name, a, b, radius=2):
        delta=A.Vector(*b)-A.Vector(*a)
        obj=api.cylinder(document,name,radius,delta.Length,a)
        obj.Placement.Rotation=A.Rotation(A.Vector(0,0,1),delta)
        obj.Placement=inverse.multiply(obj.Placement)
        members.append(obj)
        return obj

    def station(identifier,cable,point,support):
        stations.append({'id':identifier,'cables':[cable],'point_mm':list(point),
            'support':'P72/'+support,'type':'collier autour appui et gaine',
            'largeur_collier_mm':4.6,'statut':'À valider'})

    # Première retenue du montant fixe, sous le pied P72 et hors plateau P60.
    # Le trajet depuis le capteur reste une boucle de découplage volontaire.
    bar('DescenteAppuiAiry',(-95,64,-102),(-95,64,-84))
    bar('RepriseAppuiAiry',(-95,64,-85),(-89,60,-85))
    finger=api.box(document,'DoigtAiryInferieur',(6.3,6,6),(-100.3,61,-103))
    finger.Placement=inverse.multiply(finger.Placement);members.append(finger)
    station('AIRY_BAS','AIRY',(-104,64,-100),'DoigtAiryInferieur')

    # Renfort sous le coude USB, repris sur le bras bas déjà présent dans P72.
    # Point issu de la vraie WireFlex R20, pas du sommet de la polyligne.
    bar('AppuiF41CoudeBas',(-112,36.01,3.42503),(-104,35.55,3))
    station('F41_COUDE_ENTREE','F41',(-110.902853,36.005718,8.125028),'AppuiF41CoudeBas')

    # Sortie de la réserve : longe sous la portion droite, hors volume des spires.
    bar('LongeF41SortieReserve',(-92,38,22.55),(-40,38,22.55))
    bar('RepriseF41SortieReserve',(-88,38,22.55),(-88,56,22.55))
    for x in (-48,-83):
        station('F41_SORTIE_'+str(x),'F41',(x,38,27.25),'LongeF41SortieReserve')
    # Portion droite inclinée entre deux congés : appui latéral décalé de4,7 mm.
    bar('LongeF41SortieInclinee',(-107.3,48,45.444444),(-107.3,52.5,53.631944))
    bar('RepriseF41SortieInclinee',(-107.3,50,49.083333),(-90,56,45))
    station('F41_SORTIE_INCLINEE','F41',(-112,49.964824,49.019333),'LongeF41SortieInclinee')

    result=document.addObject('Part::MultiFuse','P72AvecRetenuesReserves')
    result.Shapes=[base]+members;result.Refine=True
    if base in root.Group:root.removeObject(base)
    root.addObject(result);document.recompute()
    for obj in [base]+members:obj.Visibility=False
    result.Visibility=True;api.color(result,(.34,.38,.43))
    spec={'stations':stations,'colliers_cables':len(stations),'vis_supplementaires':0,
        'qualification':'À valider','matiere_candidate':'PA12',
        'limites':['Boucle Airy entre connecteur et première retenue fixe : découplage vibratoire à vérifier sur matériel.',
                   'Colliers sans écrasement de la gaine USB ; interfaces à adoucir.',
                   'Rigidité des longes, tête des colliers et accès de montage non qualifiés.']}
    api.meta(root,'RetenuesReserves',json.dumps(spec,ensure_ascii=False))
    return result,spec
