"""Fixations réversibles sur les supports projet, sans perçage OEM.

Les plans non disponibles des modules ne sont pas remplacés par une bride sur
leurs composants. Les interfaces construites ici concernent les seuls supports
GNSS/USL, les supports d'antenne et le boîtier de protection MIDI réservé.
"""
import json
import math
import FreeCAD as A
import Part


def _fuse(api, document, root, members, name):
    result = document.addObject('Part::MultiFuse', name)
    result.Shapes = members
    result.Refine = True
    for obj in members:
        if obj in root.Group:
            root.removeObject(obj)
    root.addObject(result)
    document.recompute()
    for obj in members:
        obj.Visibility = False
    result.Visibility = True
    return result


def finish_navigation_mount(api, document, root, kind):
    """Fusionner plaque/bras et reprendre les trous M2 déjà présents sur P66."""
    if kind not in ('gnss', 'securite'):
        raise ValueError('Support navigation inconnu : ' + kind)
    # Repères des pièces : GNSS (0,110,88), sécurité (0,-100,88).
    local_y, global_y = (-81, 29) if kind == 'gnss' else (71, -29)
    # Un App::Part actif contient aussi les anciens booléens et leurs outils
    # masqués. Les réutiliser remplirait les trous et ajouterait les cylindres
    # de coupe Z-1..4 au support fini.
    members = [o for o in root.Group if hasattr(o, 'Shape') and not o.Shape.isNull() and o.Visibility]
    members.append(api.box(document, 'TraverseAncrageM2', (96, 10, 3), (-48, local_y-5, 0)))
    if kind == 'securite':
        members.append(api.box(document, 'RaccordBrasAncrage', (20, 16, 3), (-10, 60, 0)))
    raw = _fuse(api, document, root, members, 'SupportEtBrasUnis')
    holes = [api.cylinder(document, 'PassageAncrageM2', 1.1, 5, (x, local_y, -1))
             for x in (-43, 43)]
    result = api.boolean(document, root, raw, holes, 'SupportAncreM2')
    raw.Visibility = False
    document.recompute()
    for obj in root.Group:
        if obj != result and hasattr(obj,'Shape'):obj.Visibility=False
    result.Visibility=True
    api.color(result, (.34, .38, .43))
    spec = {'axes_globaux_mm': [[x, global_y] for x in (-43, 43)],
            'trous_mm': 2.2, 'epaisseur_patte_mm': 3,
            'appui_mm': [88, 91],
            'fixation': 'Deux M2 traversantes dans les perçages P66/OEM existants ; aucun perçage OEM ajouté.',
            'interface_module': 'Fixation du récepteur GNSS ou du module USL sur sa plaque selon plan/lot à confirmer.',
            'qualification': 'À valider'}
    api.meta(root, 'AncragesSupport', json.dumps(spec, ensure_ascii=False))
    return result, spec


def build_navigation_fasteners(api, document, root):
    """Quatre empilements identiques, tête sous OEM, écrou au-dessus du support."""
    ids = ['MEC-SUPPORT-GNSS', 'MEC-SUPPORTS-SECURITE']
    screw = api.bolt('EQ_ISO4762_M2x12_Prototype', 2, 12)
    washer = api.ring('EQ_ISO7089_M2_Prototype', .3, 5, 2.2, ids)
    nut = api.hexnut('EQ_ISO4032_M2_Prototype', 2, 4, 1.6)
    # Tige vers +Z après retournement de la vis dont la recette descend vers -Z.
    turn = A.Rotation(A.Vector(1, 0, 0), 180)
    rows = []
    for kind, y, item in [('GNSS', 29, ids[0]), ('Securite', -29, ids[1])]:
        for index, x in enumerate((-43, 43)):
            api.link(document, root, 'VisSupport'+kind+str(index), screw,
                     A.Placement(A.Vector(x, y, 82.7), turn), [item])
            api.at(document, root, 'RondelleSupport'+kind+'B'+str(index), washer, (x, y, 82.7), [item])
            api.at(document, root, 'RondelleSupport'+kind+'H'+str(index), washer, (x, y, 91), [item])
            api.at(document, root, 'EcrouSupport'+kind+str(index), nut, (x, y, 91.3), [item])
            rows.append({'id':kind+str(index), 'axe_mm':[x, y],
                         'couches_z_mm': [[82.7,83], [83,85], [85,88], [88,91], [91,91.3], [91.3,92.9]],
                         'appui_tete_z_mm':82.7, 'extremite_z_mm':94.7,
                         'saillie_apres_ecrou_mm':1.8,
                         'jeu_radial_tige_mm':.1})
    spec = {'vis_M2x12':4, 'rondelles_M2':8, 'ecrous_M2':4,
            'empilements':rows, 'qualification':'À valider',
            'limites':['Filetages et empreintes simplifiés ; norme, classe, couple, freinage et lot à contrôler.',
                       'Les interfaces OEM des modules GNSS/USL demeurent à confirmer.']}
    api.meta(root, 'FixationsSupportsNavigation', json.dumps(spec, ensure_ascii=False))
    return spec


def extend_radio_mount(api, document, root, base):
    """Appui sous la traverse P75 et passage d'un collier d'ancrage distinct."""
    # Pièce locale en (X=-76, Y=28/-15, Z=103). La traverse P75 occupe
    # X[-82,-78], Z[110,114]. La languette déporte le collier à Ylocal=-12,
    # entre les œillets existants Y0/35 afin de ne pas traverser leur matière.
    # Le premier enfant de Shape n'est pas nécessairement le booléen final.
    # Reprendre seulement le résultat affiché de la plaque initiale.
    visible=[o for o in root.Group if hasattr(o,'Shape') and not o.Shape.isNull() and o.Visibility]
    if len(visible)!=1:raise ValueError('Résultat visible P70 absent ou ambigu')
    base=visible[0]
    tongue = api.box(document, 'LanguetteAncrageP75', (18, 11, 3), (-9, -15, 0))
    neck = api.box(document, 'AppuiSousP75', (4, 11, 7), (-6, -15, 0))
    raw = _fuse(api, document, root, [base, tongue, neck], 'SupportRFetAppuiP75')
    slot = api.box(document, 'PassageCollierAncrageP75', (3, 4.8, 5), (3.5, -14.4, -1))
    # L'autre occurrence prend sa boucle entre le coaxial F13B (fin Y-15)
    # et F08 (axe Y-22), à Yglobal=-17,5. Prolonger seulement le passage
    # initial droit ; le positionnement de l'antenne reste inchangé.
    second_slot = api.box(document, 'PassageCollierRFHorizontal', (3, 4.8, 5), (3.5, -4.9, -1))
    result = api.boolean(document, root, raw, [slot,second_slot], 'SupportRFAncre')
    raw.Visibility = False
    document.recompute()
    for obj in root.Group:
        if obj != result and hasattr(obj,'Shape'):obj.Visibility=False
    result.Visibility=True
    api.color(result, (.16, .35, .65))
    spec = {'collier_ancrage_par_occurrence':1, 'nombre_occurrences':2,
            'collier_antenne_distinct':True, 'centres_bande_locaux_y_mm':[-12,-2.5],
            'note_passage':'RF0 dans la nouvelle lumière Y-12 ; RF1 dans le prolongement de la lumière initiale à Y-2,5, entre F13 et F08.',
            'largeur_bande_mm':4.6, 'epaisseur_bande_mm':1.2,
            'appui_global_mm':{'x':[-82,-78], 'z':110},
            'passage_local_mm':{'x':[3.5,6.5], 'y':[-14.4,-9.6]},
            'qualification':'À valider',
            'limites':['Serrage, adhérence TPU et décharge de traction coaxiale à contrôler sans écrasement du coaxial.']}
    api.meta(root, 'AncrageCadreP75', json.dumps(spec, ensure_ascii=False))
    return result, spec


def extend_midi_shelf(api, document, root, base):
    """Tablette portée par P73, sous le boîtier réservé et hors de ses bornes."""
    # P73 est tourné de 180 degrés. La géométrie est définie globalement puis
    # ramenée dans son repère pour conserver ses occurrences et ses stations.
    inverse = root.getGlobalPlacement().inverse()
    shelf = api.box(document, 'TabletteMIDI', (72.5, 30, 3), (17.5, -86, -55))
    shelf.Placement = inverse.multiply(shelf.Placement)
    result = _fuse(api, document, root, [base, shelf], 'P73AvecTabletteMIDI')
    api.color(result, (.34,.38,.43))
    spec = {'emprise_globale_mm':[17.5,-86,-55,90,-56,-52],
            'appui_boite_z_mm':-52, 'colliers':2, 'axes_colliers_x_mm':[39,63],
            'largeur_bande_mm':4.6, 'epaisseur_bande_mm':1.2,
            'fixation':'Deux boucles autour du boîtier de porte-fusible et de la tablette ; aucune fixation dans une borne.',
            'qualification':'À valider',
            'limites':['Le volume réservé représente le boîtier ; bornes, capot et lot exact à confirmer avant fabrication.']}
    api.meta(root, 'SupportProtectionMIDI', json.dumps(spec, ensure_ascii=False))
    return result, spec


def _rounded_rectangle(sketch, x0, z0, x1, z1, radius):
    """Contour natif fermé dans les coordonnées XY du sketch (X/Z du monde)."""
    v = lambda x,z: A.Vector(x,z,0)
    curves = [
        Part.LineSegment(v(x0+radius,z0),v(x1-radius,z0)),
        Part.ArcOfCircle(Part.Circle(v(x1-radius,z0+radius),A.Vector(0,0,1),radius),-math.pi/2,0),
        Part.LineSegment(v(x1,z0+radius),v(x1,z1-radius)),
        Part.ArcOfCircle(Part.Circle(v(x1-radius,z1-radius),A.Vector(0,0,1),radius),0,math.pi/2),
        Part.LineSegment(v(x1-radius,z1),v(x0+radius,z1)),
        Part.ArcOfCircle(Part.Circle(v(x0+radius,z1-radius),A.Vector(0,0,1),radius),math.pi/2,math.pi),
        Part.LineSegment(v(x0,z1-radius),v(x0,z0+radius)),
        Part.ArcOfCircle(Part.Circle(v(x0+radius,z0+radius),A.Vector(0,0,1),radius),math.pi,3*math.pi/2)]
    sketch.addGeometry(curves, False)


def collar_shape_native(document, root, name, inner_bounds, centre_axis=0, plane='xz'):
    """Bande fermée4,6×1,2 par sketch double contour et extrusion natifs."""
    x0,z0,x1,z1 = inner_bounds
    width, thickness, radius = 4.6,1.2,1.2
    sketch = document.addObject('Sketcher::SketchObject', name+'Profil')
    _rounded_rectangle(sketch,x0-thickness,z0-thickness,x1+thickness,z1+thickness,radius+thickness)
    _rounded_rectangle(sketch,x0,z0,x1,z1,radius)
    # Local XY -> monde XZ ; extrusion suivant -Y.
    pose = A.Placement(A.Vector(0,centre_axis+width/2,0),A.Rotation(A.Vector(1,0,0),90))
    if plane == 'yz':
        # Xlocal du profil devient Ymonde, normale -Y devient +X.
        pose = A.Placement(A.Vector(centre_axis-width/2,0,0),
                           A.Rotation(A.Vector(0,0,1),90).multiply(A.Rotation(A.Vector(1,0,0),90)))
    elif plane != 'xz':
        raise ValueError('Plan de collier inconnu : '+plane)
    sketch.Placement = pose
    extrusion = document.addObject('Part::Extrusion',name)
    extrusion.Base = sketch
    extrusion.DirMode = 'Normal'
    extrusion.LengthFwd = width
    extrusion.Solid = True
    root.addObject(extrusion)
    document.recompute()
    sketch.Visibility = False
    return extrusion


def build_equipment_collars(api, document, root):
    """Deux références de boucles réutilisées en quatre occurrences nominales."""
    collars = []
    for name, bounds, plane, positions in [
        ('EQ_Collier_T50R_AncrageRF_Prototype',[-85.4,102.6,-71.6,114.4],'xz',
         [('CollierAncrageRF0',16),('CollierAncrageRF1',-17.5)]),
        ('EQ_Collier_T50R_MIDI_Prototype',[-86.4,-55.4,-55.6,-27.6],'yz',
         [('CollierMIDI0',39),('CollierMIDI1',63)])]:
        d,r = api.doc(name,'pieces/commerce','T50R — boucle nominale de retenue')
        band = collar_shape_native(d,r,'BandeFermee',bounds,0,plane)
        api.color(band,(.10,.10,.10))
        api.meta(r,'DimensionsBande','4,6×1,2 mm ; rayon intérieur1,2 mm ; boucle nominale sans tête ni serrage qualifiés.')
        target = api.save(d,r,['ELEC-COLLIERS'],'commerce_enveloppe',
                          'Une boucle représente un collier du lot T50R, pas un achat supplémentaire ; montage/serrage À valider.')
        for identifier, axis in positions:
            vector = A.Vector(0,axis,0) if plane=='xz' else A.Vector(axis,0,0)
            api.link(document,root,identifier,target,A.Placement(vector,A.Rotation()),['ELEC-COLLIERS'])
            collars.append({'id':identifier, 'reference':name, 'plan':plane,
                            'axe_mm':axis, 'largeur_mm':4.6, 'epaisseur_mm':1.2})
    return {'nombre_colliers':4,'colliers':collars,'qualification':'À valider'}
