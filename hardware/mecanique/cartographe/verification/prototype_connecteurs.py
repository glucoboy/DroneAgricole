"""Infrastructure FreeCAD : références des connecteurs coudés de la caméra.

Appel : ``build_connectors(api, d7, r7)``. Aucune scène GUI ni sauvegarde du
sous-assemblage appelant n'est lancée ici. Les sources originales restent
dans le document, cachées et hors de l'Ensemble externe. Les Part::Cut
natifs séparent l'enveloppe extérieure des volumes engagés ; cette
séparation n'est pas une validation de l'accouplement ou du brochage.
"""
import hashlib
import json
from pathlib import Path

import FreeCAD as A
import Part


ASSETS = (
    ('usbfirewire/RR-ASMUK-XXGRHF_3dConn1.stp',
     'cfa92d8044781703fa24208723d4f4348754537516025f3f089832035e9f52c5',
     'https://www.usbfirewire.com/download?file=RR-ASMUK-XXGRHF_3dConn1.stp'),
    ('usbfirewire/RR-ASMUK-XXGRHF_TechnicalDrawing.pdf',
     'f34731833f09bde2a14c1b19b66ecb0bed85cf175cf2c6f512dde8390bb33eab',
     'https://www.usbfirewire.com/wp-content/uploads/pdfs/RR-ASMUK-XXGRHF_TechnicalDrawing.pdf'),
    ('phoenix_contact/1522341_dimensions_41886.jpg',
     'e058807591f7c5e844c3961b29861077fdc904b3a05e9f4b9588176609f9479a',
     'https://caas.phoenixcontact.com/caas/v1/stable/media/41886/full/b1500?format=jpg'),
)
MICROB_MATRIX = (0, 1, 0, 250.385, 0, 0, -1, -.525,
                 -1, 0, 0, -96.82, 0, 0, 0, 1)
TYPEA_MATRIX = (1, 0, 0, 7, 0, 1, 0, -39.35,
                0, 0, 1, 140.5, 0, 0, 0, 1)
M8_MATRIX = (1, 0, 0, 74.2, 0, 1, 0, 8.1,
             0, 0, 1, -105.455, 0, 0, 0, 1)


def _visibility(obj, visible):
    if 'Visibility' in obj.PropertiesList:
        obj.Visibility = visible
    elif obj.ViewObject is not None:
        obj.ViewObject.Visibility = visible


def _group(document, name, label):
    obj = document.addObject('App::DocumentObjectGroup', name)
    obj.Label = label
    _visibility(obj, False)
    return obj


def _root_members(root, terminal, parameters=None):
    """N'exposer que les terminaux ; les dépendances auto-groupées sont cachées."""
    wanted = list(terminal) + ([parameters] if parameters is not None else [])
    for obj in list(root.Group):
        if obj not in wanted:
            root.removeObject(obj)
    for obj in wanted:
        if obj not in root.Group:
            root.addObject(obj)
    for obj in list(root.Group):
        if obj not in terminal:
            _visibility(obj, False)
    for obj in terminal:
        _visibility(obj, True)
    if parameters is not None:
        _visibility(parameters, False)


def _cut_interface(api, d, original, halfspace, name, outside, engaged):
    cut = d.addObject('Part::Cut', name)
    cut.Base, cut.Tool = original, halfspace
    cut.Refine = True
    common = d.addObject('Part::Common', name + 'Engage')
    common.Base, common.Tool = original, halfspace
    common.Refine = True
    engaged.addObject(common)
    api.meta(common, 'Nature', 'Volume engagé conservé ; accouplement physique À valider')
    _visibility(original, False)
    _visibility(halfspace, False)
    _visibility(common, False)
    d.recompute()
    if cut.Shape.isNull() or cut.Shape.Volume < 1e-8:
        outside.addObject(cut)
        _visibility(cut, False)
        return None
    assert cut.Shape.isValid(), (d.Name, cut.Name)
    return cut


def _source_inventory(api):
    result = []
    for relative, expected, url in ASSETS:
        path = api.MEC / 'sources_fabricants' / relative
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError('Source fabricant différente : ' + str(path))
        key = api.rel(path)
        api.SOURCES[key] = actual
        result.append(dict(fichier=key, sha256=actual, url=url))
    return result


def _usb_reference(api, source, stem, label, indices, interface_axis,
                   interface_value, pose, occurrence):
    d, root = api.doc(stem, 'pieces/commerce', label)
    originals = _group(d, 'SourcesFabricant', 'Solides STEP originaux — cachés')
    empty = _group(d, 'ResultatsNonExposes', 'Résultats entièrement engagés — cachés')
    engaged = _group(d, 'VolumesEngages', 'Volumes engagés — hors contrôle extérieur')
    geometry = {}
    for index in indices:
        obj = d.addObject('Part::Feature', 'SolideFabricant' + str(index))
        obj.Shape = source.Solids[index].copy()
        originals.addObject(obj)
        api.meta(obj, 'IndiceSTEPZeroBased', index)
        _visibility(obj, False)
        geometry[index] = obj
    if interface_axis == 'X':
        tool = api.box(d, 'DemiEspaceAccouplement', (200, 400, 200),
                       (interface_value, -300, -100))
    else:
        tool = api.box(d, 'DemiEspaceAccouplement', (200, 200, 200),
                       (-100, interface_value, -100))
    originals.addObject(tool)
    api.meta(tool, 'PlanAccouplement', interface_axis + '=' + str(interface_value) + ' mm, repère STEP')
    exposed = []
    for index, obj in geometry.items():
        if index == 2:
            api.meta(obj, 'Limite', 'Segment illustratif120 mm : source conservée, jamais substituée au câble F16')
            continue
        cut = _cut_interface(api, d, obj, tool, 'ExterneSolide' + str(index), empty, engaged)
        if cut is not None:
            exposed.append(cut)
            api.color(cut, (.13, .14, .16) if index in (0, 3) else (.67, .68, .69))
    _root_members(root, exposed)
    for obj in list(originals.Group) + list(empty.Group) + list(engaged.Group):
        _visibility(obj, False)
    for group in (originals, empty, engaged):
        _visibility(group, False)
    api.meta(root, 'SourceFabricant', ASSETS[0][0])
    api.meta(root, 'SHA256Source', ASSETS[0][1])
    api.meta(root, 'SolidesSourceZeroBased', json.dumps(list(indices)))
    api.meta(root, 'ModeleExpose', 'Enveloppe externe issue de Part::Cut ; géométrie complète dans SourcesFabricant')
    api.meta(root, 'InclusionBOM', 'Fiche incluse dans le cordon ELEC-F16 ; aucune unité d’achat supplémentaire')
    note = ('USBFireWire RR-ASMUK-20GRHF. Enveloppe externe seulement ; '
            'sources et engagements conservés cachés. Sens de polarisation, '
            'engagement réel, tolérances et tenue À valider.')
    target = api.save(d, root, ['ELEC-F16'], 'commerce_fabricant_derive', note)
    return target, dict(reference=stem, occurrence=occurrence,
                        fichier=api.rel(d.FileName), objet='Ensemble',
                        matrice=list(pose), solides_source_zero_based=list(indices),
                        objets_exposes=[o.Name for o in exposed],
                        objets_engages=[o.Name for o in engaged.Group],
                        plan_local=dict(axe=interface_axis, valeur_mm=interface_value))


def _m8_reference(api):
    d, root = api.doc('EQ_Phoenix_M8_1522341_Prototype', 'pieces/commerce',
                      'M8 coudé Phoenix1522341 — enveloppe hypothétique')
    p = api.params(d, root, dict(HauteurTotale=24.8, LongueurTotale=28,
                                DiametreCorps=10, DiametreQueue=8.4,
                                Engagement=6))
    hidden = _group(d, 'ConstructionEnveloppe', 'Construction de réservation — cachée')
    engaged = _group(d, 'VolumesEngages', 'Engagement hypothétique — caché')
    empty = _group(d, 'ResultatsNonExposes', 'Résultats auxiliaires — cachés')
    body = api.cylinder(d, 'ReservationAxiale', 5, 24.8, (0, 0, -6))
    for prop, expr in [('Radius', 'Parametres.DiametreCorps/2'),
                       ('Height', 'Parametres.HauteurTotale'),
                       ('Placement.Base.z', '-Parametres.Engagement')]:
        body.setExpression(prop, expr)
    tail = api.cylinder(d, 'ReservationQueue', 4.2, 23, (0, 0, 14.6))
    tail.Placement.Rotation = A.Rotation(A.Vector(1, 0, 0), -90)
    for prop, expr in [('Radius', 'Parametres.DiametreQueue/2'),
                       ('Height', 'Parametres.LongueurTotale-Parametres.DiametreCorps/2'),
                       ('Placement.Base.z', 'Parametres.HauteurTotale-Parametres.DiametreQueue/2-Parametres.Engagement')]:
        tail.setExpression(prop, expr)
    complete = d.addObject('Part::MultiFuse', 'EnveloppeComplete')
    complete.Shapes = [body, tail]
    complete.Refine = True
    tool = api.box(d, 'DemiEspaceAccouplement', (200, 200, 100), (-100, -100, -100))
    for obj in (body, tail, complete, tool):
        hidden.addObject(obj)
    exterior = _cut_interface(api, d, complete, tool, 'EnveloppeExterne', empty, engaged)
    _root_members(root, [exterior], p)
    for obj in (body, tail, complete, tool, hidden, engaged, empty):
        _visibility(obj, False)
    api.color(exterior, (.19, .20, .22))
    api.meta(root, 'NatureModele', 'Enveloppe de réservation native ; aucune source STEP Phoenix obtenue')
    api.meta(root, 'EngagementHypothese', '6 mm, éditable dans Parametres.Engagement ; aucune cote d’accouplement fabricant disponible')
    api.meta(root, 'Fabrication', 'NON LIBÉRÉE — engagement, orientation, largeur du surmoulage et paires torsadées À valider')
    api.meta(root, 'HypothesesGeometrie', 'Diamètre10 mm étendu au corps ; queue tangentielle haute ; sortie+Y. Ces détails ne sont pas tous cotés par le plan2D.')
    api.meta(root, 'SourceDimensions', ASSETS[2][0] + ' ; SHA256=' + ASSETS[2][1])
    api.meta(root, 'InclusionBOM', 'Connecteur inclus dans ELEC-F-M8 ; aucune unité d’achat supplémentaire')
    note = ('Phoenix1522341, dimensions24,8×28 mm, Ø10 et queueØ8,4. '
            'Engagement6 mm HYPOTHÈSE ; fabrication non libérée. '
            'Blindage documenté ; paires torsadées, appairage, largeur '
            'du corps, orientation+Y et accès À valider.')
    target = api.save(d, root, ['ELEC-F-M8'], 'commerce_enveloppe', note)
    data = dict(reference=d.Name, fichier=api.rel(d.FileName), objet='Ensemble',
                occurrence='ConnecteurM8Camera', matrice=list(M8_MATRIX),
                parametres=dict(Engagement=6, HauteurTotale=24.8, LongueurTotale=28,
                                DiametreCorps=10, DiametreQueue=8.4),
                objet_externe=exterior.Name, objet_complet=complete.Name,
                fabrication_liberee=False,
                sortie_gaine_globale_mm=[74.2, 31.1, -90.855],
                dessus_global_mm=-86.655,
                degagement_P60_sans_jeu_mm=3.345,
                jeu_pack_nominal_mm=1.655)
    return target, data


def build_connectors(api, d7, r7):
    """Crée trois références commerce, lie leurs enveloppes et retourne la preuve.

    ``api`` expose les aides du constructeur principal : MEC, SOURCES,
    doc, params, box, cylinder, color, meta, save, link et rel.
    Le dictionnaire retourné est sérialisable dans les preuves du constructeur.
    """
    inventory = _source_inventory(api)
    source = Part.read(str(api.MEC / inventory[0]['fichier']))
    if len(source.Solids) != 7 or not source.isValid():
        raise ValueError('STEP USBFireWire inattendu : sept solides valides requis')
    rows = []
    for name, label, indices, axis, plane, matrix, occurrence in (
        ('EQ_USBFireWire_MicroB_Up_Prototype', 'MicroB Up USBFireWire — enveloppe externe',
         (3, 4, 5, 6), 'X', 13, MICROB_MATRIX, 'ConnecteurF16Camera'),
        ('EQ_USBFireWire_TypeA_Prototype', 'TypeA USBFireWire — enveloppe externe',
         (0, 1, 2), 'Y', 0, TYPEA_MATRIX, 'ConnecteurF16TypeA'),
    ):
        target, row = _usb_reference(api, source, name, label, indices, axis,
                                     plane, matrix, occurrence)
        api.link(d7, r7, occurrence, target, A.Placement(A.Matrix(*matrix)),
                 ['ELEC-F16'], 'Enveloppe externe ; interface cachée à valider séparément')
        rows.append(row)
    target, m8 = _m8_reference(api)
    api.link(d7, r7, m8['occurrence'], target, A.Placement(A.Matrix(*M8_MATRIX)),
             ['ELEC-F-M8'], 'HYPOTHÈSE e=6 mm ; fabrication non libérée')
    rows.append(m8)
    return dict(etat='À valider', sources_preservees=inventory, references=rows,
                sorties_gaine_mm=dict(MicroB=[109.785, -.525, -96.82],
                                      TypeA=[7, -79.95, 140.5],
                                      M8=[74.2, 31.1, -90.855]),
                limites=['Les volumes engagés cachés restent à contrôler séparément.',
                         'Une enveloppe externe libre ne valide pas l’accouplement.',
                         'M8 : engagement6 mm et sortie+Y hypothétiques ; fabrication non libérée.',
                         'USB : polarisation, longueur utile et engagement réel À valider.'])
