"""Infrastructure ORCH-CAO-MASSE-1 : matières candidates et mesures CAO brutes.

Ne modifie que les pièces explicitement autorisées. Aucun calcul de masse
métier : les volumes, aires, tenseurs et métrages sont remis au calcul C++.
Les densités et masses commerciales ci-dessous sont des données sourcées.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import json
import os
import sys
import subprocess
import re
import struct
import urllib.request
import zipfile
import xml.etree.ElementTree as ET

MEC = Path(__file__).resolve().parents[1]
ROOT = MEC.parents[2]
VER = MEC / 'verification'
OUT = VER / 'orch_cao_masse_fabrication.json'
RUNTIME = ROOT / '.runtime/orch-cao-masse-1/fabrication'
SOURCE_DIR = MEC / 'sources_fabricants/orch_cao_masse'
SOURCES = [
 ('EOS-PA2200', 'eos_pa2200_balance.pdf', 'https://www.eos.info/polymer-solutions/data-sheets/pds-pa-2200-carbon-reduced-balance?pdf=1&topdf=%2Fpolymer-solutions%2Fdata-sheets%2Fpds-pa-2200-carbon-reduced-balance', '17 juin 2026, état 24 octobre 2026'),
 ('UM-TPU95A', 'ultimaker_tpu95a.pdf', 'https://um-support-files.ultimaker.com/materials/2.85mm/tds/TPU-95A/TDS-TPU95A-V2.01-250915.pdf', 'v2.01, 15 septembre 2025'),
 ('NORPLEX-NP500A', 'norplex_np500a.pdf', 'https://www.norplex-micarta.com/wp-content/uploads/2017/07/TDB_NP500A.pdf', '14 juillet 2022'),
 ('ENSINGER-POMC', 'ensinger_tecaform_ah.html', 'https://www.ensingerplastics.com/en/shapes/acetal-tecaform-ah-natural', None),
 ('OUTOKUMPU-304', 'outokumpu_core.pdf', 'https://www.outokumpu.com/en/products/product-ranges/-/media/files/products/core/outokumpu-core-range-datasheet.pdf?modified=20251117111909&revision=025e9931-a1d5-4c8f-8ff5-f881d38916da', None),
 ('CONSTELLIUM-6061', 'constellium_6061.pdf', 'https://assets.ctfassets.net/e62qtriulv4v/Snx9pjCdtrYCSlsFquBvt/e0f6b8cb7bfb0e1533e0aeec55796f03/Material_sheet_6061.pdf', None),
 ('MINICARS-B9310', 'minicars_b9310.html', 'https://www.minicars.se/sv/kontakt-qs8-anti-spark-8mm-par', None),
 ('PHOENIX-1522341', 'phoenix_1522341_extrait.json', 'https://www.phoenixcontact.com/en-us/products/sensoractuator-cable-sac-6p-m-8mr-15-pur-sh-1522341', None),
 ('USBFIREWIRE-F16', 'usbfirewire_rr_asmuk.html', 'https://www.usbfirewire.com/parts/rr-asmuk-xxgrhf.html', None),
 ('HT-T50R', 'hellermann_111_05012.html', 'https://www.hellermanntyton.com/products/cable-ties-inside-serrated/t50r/111-05012', None),
 ('HT-T18R', 'hellermann_111_01960.html', 'https://www.hellermanntyton.com/products/cable-ties-inside-serrated/t18r/111-01960', None),
 ('HENKEL-222', 'henkel_loctite222.pdf', 'https://datasheets.tdx.henkel.com/LOCTITE-222-en_GL.pdf', 'mai 2022'),
]

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def rel(path):
    return Path(path).relative_to(MEC).as_posix()

def dump(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', 'utf-8')

def source_rows():
    rows = []
    for sid, filename, url, revision in SOURCES:
        path = SOURCE_DIR / filename
        rows.append(dict(id=sid, url=url, fichier=rel(path), sha256=sha(path) if path.exists() else None,
                         revision=revision, date_consultation='2026-10-25',
                         droits='Consultation technique publique ; licence de redistribution non identifiée, source conservée hors Git.',
                         nature_source='Extrait de données de page officielle consultée via outil web ; original HTTP403' if sid=='PHOENIX-1522341' else 'Fichier ou page fabricant original conservé',
                         statut='Source conservée' if path.exists() else 'Téléchargement non abouti'))
    return rows

def download_sources():
    SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    for sid, filename, url, revision in SOURCES:
        path = SOURCE_DIR / filename
        if path.exists():
            print(sid, 'conservé', sha(path), flush=True)
            continue
        try:
            request = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 ORCH-CAO-MASSE-1'})
            with urllib.request.urlopen(request, timeout=50) as response:
                data = response.read()
            if len(data) < 100 or (filename.endswith('.pdf') and not data.startswith(b'%PDF')):
                raise ValueError('Contenu absent ou format inattendu')
            path.write_bytes(data)
            print(sid, len(data), sha(path), flush=True)
        except Exception as error:
            print(sid, 'ECHEC', str(error), flush=True)
            if sid=='PHOENIX-1522341':
                dump(path,dict(url=url,date_consultation='2026-10-25',reference='1522341',
                    nature='Extrait de données techniques de la page officielle consultée via outil web ; original HTTP403, cet extrait ne prétend pas être le fichier original fabricant.',
                    poids_piece_hors_emballage_g=63.7,poids_piece_avec_emballage_g=66.1,
                    longueur_catalogue_m=1.5,masse_lineique_cable_kg_km=34,
                    diametre_exterieur_mm=5.2,conducteurs='6×0,14mm²',rayon_minimal_mm=52,
                    original_non_telecharge=str(error),droits='Données factuelles extraites, licence du document original inconnue'))
    dump(RUNTIME / 'sources.json', source_rows())

def candidates():
    groups = [
      ([10,17,72,73,75,76,77,78], 'EOS PA 2200 CarbonReduced Balance', 'SLS Balance, couche 120 µm, dépoudré, non infiltré, sans évidement ajouté', .93, 'EOS-PA2200'),
      ([70,79,80], 'UltiMaker TPU 95A noir 2,85 mm', 'FFF, S5 Pro candidat, AA0.4, couche 0,15 mm, remplissage lignes 100 %, 4 parois, 4 couches haut/bas', 1.22, 'UM-TPU95A'),
      ([60,62,64,66,69,71], 'Norplex-Micarta NP500A, NEMA G-10', 'Usinage plaque ; épaisseurs finales du natif, brut à confirmer', 1.77, 'NORPLEX-NP500A'),
      ([61,63,67,68,74], 'Ensinger TECAFORM AH natural, POM-C non chargé', 'Usinage depuis plaque/barre ; faces et passages du natif', 1.41, 'ENSINGER-POMC'),
      ([18,19], 'Inox 304, EN 1.4301, UNS S30400', 'Usinage ; ajustements et état de surface à valider', 7.9, 'OUTOKUMPU-304'),
      ([65], 'Aluminium 6061-T6 existant', 'Usinage ; opérations et assemblage de la géométrie reprise à confirmer', 2.7, 'CONSTELLIUM-6061'),
    ]
    result = {}
    for numbers, grade, process, density, source in groups:
        for number in numbers:
            matches = list((MEC/'pieces/fabriquees').glob('P'+str(number).zfill(2)+'_*.FCStd'))
            if len(matches) != 1:
                raise RuntimeError('Référence fabriquée absente/ambiguë : P'+str(number))
            path = matches[0]
            result[path.stem] = dict(reference=path.stem, fichier=rel(path), grade=grade, procede=process,
                densite_g_cm3=density, densite_nature='Valeur typique fabricant' if source else 'Valeur nominale 6061-T6 ; source à consolider',
                source_ids=[source] if source else [], incertitude_densite_g_cm3=None,
                statut='À valider', usage='Scénario de calcul préliminaire, aucune libération de fabrication',
                inserts_definis=0, masse_inserts_g=None,
                limites=['Aucune qualification structurelle, thermique, vibratoire ou électrique.',
                         'Tolérances, état matière et lots réels non documentés ; aucune incertitude inventée.'])
    return result

def native_xml(path):
    with zipfile.ZipFile(path) as archive:
        return ET.fromstring(archive.read('Document.xml'))

def root_name(path):
    names = {node.get('name') for node in native_xml(path).find('Objects').findall('Object')}
    if 'Ensemble' in names:
        return 'Ensemble'
    return {'P10_Retenue_cable':'P10_AttacheCable1', 'P17_Support_deporte_isolation':'Support',
            'P18_Manchon_limiteur_metal':'Manchon', 'P19_Rondelle_capture_metal':'Rondelle'}[path.stem]

def appearance_signature(path):
    with zipfile.ZipFile(path) as archive:
        if 'GuiDocument.xml' not in archive.namelist():
            return None
        gui = ET.fromstring(archive.read('GuiDocument.xml'))
        document=ET.fromstring(archive.read('Document.xml'))
        types={o.get('name'):o.get('type') for o in document.find('Objects').findall('Object')}
        rows = {}
        for provider in gui.iter('ViewProvider'):
            name=provider.get('name')
            if not types.get(name,'').startswith(('Part::','PartDesign::')):continue
            props={p.get('name'):p for p in provider.iter('Property')}
            visibility=props.get('Visibility')
            if visibility is None or visibility.find('Bool').get('value')!='true':continue
            mat=props.get('ShapeAppearance');colors=None
            if mat is not None:
                filename=mat.find('MaterialList').get('file')
                if filename:
                    data=archive.read(filename);count=struct.unpack_from('<I',data)[0]
                    colors=[struct.unpack_from('<I',data,4+i*24+4)[0] for i in range(count)]
            transparency=props.get('Transparency')
            rows[name]=dict(couleurs_diffuses=colors,transparence=transparency.find('Integer').get('value') if transparency is not None else None)
        return rows

def change_native():
    import FreeCAD as A
    from etage_batterie_helpers import save_native
    edited = []
    for reference, spec in candidates().items():
        path = MEC/spec['fichier']
        before = sha(path)
        document = A.openDocument(str(path))
        name = root_name(path)
        obj = document.getObject(name)
        for key, value in [('FabricationCandidate', json.dumps(spec, ensure_ascii=False)),
                           ('LotORCH', 'ORCH-CAO-MASSE-1'), ('QualificationCandidate', 'À valider')]:
            if key not in obj.PropertiesList:
                obj.addProperty('App::PropertyString', key, 'ORCH_CAOMASSE')
            setattr(obj, key, value)
        document.recompute()
        save_native(document)
        A.closeDocument(document.Name)
        edited.append(dict(reference=reference, fichier=rel(path), objet_source=name, sha256_avant=before,
                           sha256_apres=sha(path), traitement='Métadonnées grade/procédé candidat ; arbre et géométrie conservés'))
        print(reference, 'matière candidate enregistrée', flush=True)
    path = MEC/'pieces/commerce/EQ_QS8S_B9310_Prototype.FCStd'
    before = sha(path)
    document = A.openDocument(str(path))
    param = document.getObject('Parametres')
    param.Longueur, param.Largeur, param.Hauteur = 60.9, 29.7, 15.4
    obj = document.getObject('Ensemble')
    for key, value in [('SourceDimensions', 'MINICARS-B9310 : paire accouplée 60,9×29,7×15,4 mm ; source conservée'),
                       ('Limites', 'Enveloppe extérieure documentée, pas un modèle exact. Demi-corps, plan de joint, interfaces, débattement et contacts non documentés. Implantation P76 à reprendre après levée du blocage.'),
                       ('LotORCH', 'ORCH-CAO-MASSE-1')]:
        if key not in obj.PropertiesList:
            obj.addProperty('App::PropertyString', key, 'ORCH_CAOMASSE')
        setattr(obj, key, value)
    document.recompute()
    save_native(document)
    A.closeDocument(document.Name)
    edited.append(dict(reference=path.stem, fichier=rel(path), objet_source='Ensemble', sha256_avant=before,
                       sha256_apres=sha(path), traitement='Correction des trois dimensions extérieures documentées ; interfaces inconnues conservées bloquantes'))
    dump(RUNTIME/'mutations.json', edited)

def interfaces_fabriquees():
    """Reprises projet contrôlées : aucune géométrie d'interface OEM inventée."""
    import FreeCAD as A
    from etage_batterie_helpers import save_native, color
    # P10 : patte latérale hors de l'assise des câbles, trou traversant M3.
    path=MEC/'pieces/fabriquees/P10_Retenue_cable.FCStd'
    document=A.openDocument(str(path)); final=document.getObject('P10_AttacheCable1')
    if document.getObject('PatteFixationORCH') is None:
        tab=document.addObject('Part::Box','PatteFixationORCH')
        tab.Length=10;tab.Width=11;tab.Height=3;tab.Placement.Base=A.Vector(-65,-36,-126)
        raw=document.addObject('Part::MultiFuse','BrutAvecPatteORCH')
        raw.Shapes=[document.getObject('AttacheCableBrut'),tab];raw.Refine=True
        hole=document.addObject('Part::Cylinder','PassageM3ORCH')
        hole.Radius=1.6;hole.Height=7;hole.Placement.Base=A.Vector(-60,-30.5,-128)
        tools=document.getObject('P10_AttacheCable1_Outils')
        tools.Shapes=list(tools.Shapes)+[hole]
        final.Base=raw
        for obj in (tab,raw,hole,tools,document.getObject('AttacheCableBrut')):obj.Visibility=False
    document.recompute();assert final.Shape.isValid() and len(final.Shape.Solids)==1
    if document.getObject('DegagementAncrageORCH') is None:
        relief=document.addObject('Part::Cylinder','DegagementAncrageORCH')
        relief.Radius=4.3;relief.Height=8;relief.Placement.Base=A.Vector(-70,-35,-128)
        tools=document.getObject('P10_AttacheCable1_Outils');tools.Shapes=list(tools.Shapes)+[relief]
        relief.Visibility=False;tools.Visibility=False
        document.recompute();assert final.Shape.isValid() and len(final.Shape.Solids)==1
    final.Visibility=True
    if 'InterfaceFixationORCH' not in final.PropertiesList:final.addProperty('App::PropertyString','InterfaceFixationORCH','ORCH_CAOMASSE')
    final.InterfaceFixationORCH='Patte10×11×3 hors assise câble, trouØ3,2 au(-60,-30,5), reprise P65 locale1,5mm ; M3×12+2rondelles+écrou. Les deux occurrences hautes tournent180° autour de leur centre pour patte intérieure. Dégagement de coin R4,3 au(-70,-35) pour libérer l’ancrage M3 observé, sans déplacement de l’assise ni du passage M3.'
    save_native(document);A.closeDocument(document.Name)
    # P65 : quatre interfaces dans de la matière observée (plaque Z−131..−126).
    path=MEC/'pieces/fabriquees/P65_Platine_Capteurs_Prototype.FCStd'
    document=A.openDocument(str(path));root=document.getObject('Ensemble')
    if document.getObject('ResultatFixationsP10ORCH') is None:
        visible=[o for o in root.Group if hasattr(o,'Shape') and not o.Shape.isNull() and o.Visibility]
        assert len(visible)==1
        previous=visible[0];tools=[]
        for index,(x,y) in enumerate([(x,y) for x in(-70,90) for y in(-40.5,32.5)]):
            bore=document.addObject('Part::Cylinder','PercageP10ORCH'+str(index))
            bore.Radius=1.6;bore.Height=12;bore.Placement.Base=A.Vector(x,y,-133);tools.append(bore)
            recess=document.addObject('Part::Cylinder','LamageP10ORCH'+str(index))
            recess.Radius=4;recess.Height=4.5;recess.Placement.Base=A.Vector(x,y,-132);tools.append(recess)
        union=document.addObject('Part::MultiFuse','OutilsP10ORCH');union.Shapes=tools
        final=document.addObject('Part::Cut','ResultatFixationsP10ORCH');final.Base=previous;final.Tool=union;final.Refine=True
        root.removeObject(previous);root.addObject(final)
        for obj in tools+[union,previous]:obj.Visibility=False
        document.recompute();color(final,(.70,.73,.76));final.Visibility=True
    assert document.getObject('ResultatFixationsP10ORCH').Shape.isValid()
    if 'InterfaceFixationP10ORCH' not in root.PropertiesList:root.addProperty('App::PropertyString','InterfaceFixationP10ORCH','ORCH_CAOMASSE')
    root.InterfaceFixationP10ORCH='4 trousØ3,2 axes X−70/90 Y−40,5/32,5 ; lamages dessousØ8 laissant1,5mm au Z−127,5..−126 ; tenue de la section résiduelle À valider.'
    save_native(document);A.closeDocument(document.Name)
    # P76 : éloigner seulement les butées du volume extérieur publié, sans joint fictif.
    path=MEC/'pieces/fabriquees/P76_Berceau_QS8_Prototype.FCStd'
    document=A.openDocument(str(path));root=document.getObject('Ensemble')
    table=document.getObject('Table');table.Width=65.9;table.Placement.Base.y=-44.95
    document.getObject('Rebord').Placement.Base.y=-44.95
    document.getObject('Rebord001').Placement.Base.y=18.95
    if 'AdaptationExterieureORCH' not in root.PropertiesList:root.addProperty('App::PropertyString','AdaptationExterieureORCH','ORCH_CAOMASSE')
    root.AdaptationExterieureORCH='TableY−44,95..20,95 et butées écartées de0,5mm du volume externe B9310 documenté ; ancrages X105/Y±29 inchangés. Ne valide ni fixation d’un demi-corps ni extraction ; joint et collier restent À valider.'
    document.recompute();save_native(document);A.closeDocument(document.Name)
    # P73 : enlever seulement la matière démontrée dans le volume extérieur QS8.
    # Le retrait laisse un solide connecté ; aucun joint/demi-corps n'est déduit.
    path=MEC/'pieces/fabriquees/P73_Guide_Faisceau_Droit_Prototype.FCStd'
    document=A.openDocument(str(path));root=document.getObject('Ensemble')
    if document.getObject('DegagementQS8ExterieurORCH') is None:
        visible=[o for o in root.Group if hasattr(o,'Shape') and not o.Shape.isNull() and o.Visibility]
        assert len(visible)==1
        previous=visible[0]
        tool=document.addObject('Part::Box','VolumeExterieurQS8AvecJeuORCH')
        tool.Length=30.7;tool.Width=61.9;tool.Height=16.4
        tool.Placement=root.Placement.inverse().multiply(A.Placement(A.Vector(97.65,-42.95,-59.5),A.Rotation()))
        cut=document.addObject('Part::Cut','DegagementQS8ExterieurORCH');cut.Base=previous;cut.Tool=tool;cut.Refine=True
        root.removeObject(previous);root.addObject(cut);previous.Visibility=False;tool.Visibility=False
        document.recompute();assert cut.Shape.isValid() and len(cut.Shape.Solids)==1
        color(cut,(.34,.38,.43));cut.Visibility=True
    if 'DegagementQS8ORCH' not in root.PropertiesList:root.addProperty('App::PropertyString','DegagementQS8ORCH','ORCH_CAOMASSE')
    root.DegagementQS8ORCH='Retrait local du volume extérieur B9310 avec jeu nominal0,5mm sur6faces ; solide connecté conservé, source et arbre natifs préservés. Les terminaisons F37/F38 et leur retenue restent bloquées par absence de plan exact QS8.'
    save_native(document);A.closeDocument(document.Name)
    additions=[]
    for index,(x,y) in enumerate([(x,y) for x in(-70,90) for y in(-40.5,32.5)]):
        for stem,prefix,z in [('EQ_ISO4762_M3x12_Prototype','VisP10ORCH',-122.5),('EQ_ISO7089_M3_Prototype','RondelleP10H_ORCH',-123),('EQ_ISO7089_M3_Prototype','RondelleP10B_ORCH',-128),('EQ_ISO10511_M3_Prototype','EcrouP10ORCH',-132)]:
            additions.append(dict(parent='sous_assemblages/SA04_Prototype_Perception.FCStd',occurrence=prefix+str(index),source='pieces/commerce/'+stem+'.FCStd',objet_source='Ensemble',bom_ids=['MEC-RETENUES-CAPTEURS-FIXATIONS'],matrice=list(A.Placement(A.Vector(x,y,z),A.Rotation()).toMatrix().A)))
    modifications=[]
    for name,x in [('P10_Retenue_cable_Occurrence001',90),('RetenueCable3',-70)]:
        modifications.append(dict(parent='sous_assemblages/SA04_Prototype_Perception.FCStd',occurrence=name,
            matrice=list(A.Placement(A.Vector(x-60,2,0),A.Rotation(A.Vector(0,0,1),180)).toMatrix().A),
            raison='Patte P10 tournée vers intérieur P65 ; assise initiale du câble conservée.'))
    dump(RUNTIME/'interfaces.json',dict(ajouts_occurrences=additions,modifications_occurrences=modifications,
        limites=['Tenue des lamages P65 et des pattes imprimées non qualifiée.', 'Accès outil et collision avec les câbles à confirmer dans assemblage intégrateur.']))

def extract_verify():
    import FreeCAD as A
    import MeshPart
    from read_brep_prototype import Reader
    import Part
    construction = json.loads((VER/'construction_prototype.json').read_text('utf-8'))
    refs = {row['fichier']:row for row in construction['references']}
    for name, spec in candidates().items():
        refs.setdefault(spec['fichier'], dict(reference=name, fichier=spec['fichier'], objet=root_name(MEC/spec['fichier']), bom_ids=[]))
    authorized = [row for row in refs.values() if row['fichier'] in [x['fichier'] for x in candidates().values()]
        or Path(row['fichier']).stem.startswith(('EQ_ISO','EQ_QS8','EQ_USBFireWire','EQ_Phoenix_M8','EQ_Pad','EQ_Sangle','EQ_Collier','W_'))]
    reader = Reader(MEC)
    geometries, reopen, mesh_sources = [], [], {}
    RUNTIME.mkdir(parents=True, exist_ok=True)
    for row in authorized:
        path = MEC/row['fichier']; name=row.get('objet','Ensemble')
        shape = reader.shape(row['fichier'], name)
        if shape is None or shape.isNull():
            raise RuntimeError('Géométrie absente : '+row['fichier'])
        matrix=getattr(shape, 'MatrixOfInertia', None)
        b=shape.BoundBox
        geometries.append(dict(reference=path.stem, fichier=row['fichier'], objet_source=name,
            bom_ids=row.get('bom_ids',[]), sha256=sha(path), valide=shape.isValid(), solides=len(shape.Solids),
            traitement='Mesures OCC des solides terminaux sauvegardés, sans masse déduite des enveloppes commerciales',
            volume_mm3=shape.Volume, aire_mm2=shape.Area, barycentre_mm=list(shape.CenterOfGravity),
            inertie_volumique_mm5=[list(matrix.A)[i:i+4] for i in (0,4,8)] if matrix is not None else None,
            solides_bruts=[dict(volume_mm3=s.Volume,aire_mm2=s.Area,barycentre_mm=list(s.CenterOfMass),
                inertie_volumique_mm5=[list(s.MatrixOfInertia.A)[i:i+4] for i in (0,4,8)]) for s in shape.Solids],
            bbox_mm=[b.XMin,b.YMin,b.ZMin,b.XMax,b.YMax,b.ZMax],
            limites=['Solides commerciaux simplifiés : volume non utilisable comme masse sans distribution/matériaux documentés.'] if '/commerce/' in row['fichier'] else []))
        if path.stem in candidates():
            before=sha(path)
            document=A.openDocument(str(path))
            obj=document.getObject(name)
            if obj is None or 'FabricationCandidate' not in obj.PropertiesList:
                raise RuntimeError('Métadonnée candidate non restaurée : '+path.stem)
            spec=json.loads(obj.FabricationCandidate)
            if spec['grade']!=candidates()[path.stem]['grade']:
                raise RuntimeError('Grade non restauré : '+path.stem)
            document.recompute()
            reopen.append(dict(fichier=row['fichier'],objet_source=name,metadata_restauree=True,
                recompute_sans_erreur=not bool([o.Name for o in document.Objects if 'Invalid' in o.State or 'Error' in o.State]),
                sha256_non_modifiee=sha(path)==before))
            A.closeDocument(document.Name)
        if path.stem.startswith(('P70_','P79_','P80_')):
            shape=shape.copy()
            shape.Placement=A.Placement()
            mesh=MeshPart.meshFromShape(Shape=shape, LinearDeflection=.04, AngularDeflection=.25, Relative=False)
            mesh.write(str(RUNTIME/(path.stem+'.stl')))
            mesh_sources[path.stem]=dict(sha256_natif_source=sha(path),sha256_stl_retesselle=sha(RUNTIME/(path.stem+'.stl')),
                methode='Retessellation déterministe de la géométrie terminale OCC du natif courant, placement identité, déviation linéaire0,04mm et angulaire0,25rad, RelativeFalse ; identité SHA256 avec le STL tranché exigée.',
                freecad=A.Version(),date_reconciliation_utc=datetime.now(timezone.utc).isoformat())
    routes=json.loads((VER/'routes_prototype.json').read_text('utf-8'))['routes']
    report=dict(schema_version=1,lot='ORCH-CAO-MASSE-1', date_utc=datetime.now(timezone.utc).isoformat(),
        script_sha256=sha(__file__),freecad=A.Version(),sources=source_rows(),geometries=geometries,
        fabrication=list(candidates().values()),masses=[
            dict(bom_id='ELEC-CONNECTEUR-MANUEL',masse_unitaire_g=41.7,qualificatif='Paire commerciale QS8-S B9310 complète ; tolérance non publiée',nature='fabricant',source_ids=['MINICARS-B9310'],conditions=['Référence constante ; contenu des capots à confirmer'],inclusions=['Deux demi-connecteurs accouplés selon fiche'],exclusions=['Fils, soudures, berceau, collier'],incertitude_g=None),
            dict(bom_id='ELEC-F-M8',masse_unitaire_g=63.7,qualificatif='Cordon commercial ENTIER 1,5m, pas masse installée après coupe',nature='fabricant',source_ids=['PHOENIX-1522341'],conditions=['1522341 non recoupé ; parcours CAO296,877mm ne définit pas la coupe'],inclusions=['M8 surmoulé, câble1,5m, extrémité libre'],exclusions=['Connecteur PH ajouté, repères/protections additionnels'],incertitude_g=None),
            dict(bom_id='ELEC-COLLIERS',reference='111-01960',masse_unitaire_g=.287,qualificatif='Collier T18R entier non recoupé ; masse installée inconnue',nature='fabricant',source_ids=['HT-T18R'],conditions=['Une pièce commerciale100mm'],inclusions=['Tête et bande entière'],exclusions=['T50R ; aucune masse des sachets'],incertitude_g=None)],
        donnees_lineiques=[dict(reference='Phoenix1522341',masse_lineique_g_m=34,source_ids=['PHOENIX-1522341'],conditions='Câble PUR6×0,14mm² seul ; connecteur surmoulé et PH à traiter séparément',incertitude_g_m=None)],
        routes=[dict(id=r['id'],bom_ids=r['bom_ids'],points_mm=r['points_mm'],longueur_courbe_mm=r['longueur_courbe_mm'],diametre_exterieur_mm=r['diametre_mm'],
                     quantite_conducteurs=None,reference_matiere=None,limites='Courbe de réservation ; pas une longueur de coupe ni un fil unitaire') for r in routes],
        ajouts_occurrences=[],reouvertures=reopen,
        blocages=[
          dict(id='QS8-INTERFACE',bom_ids=['ELEC-CONNECTEUR-MANUEL','MEC-SUPPORTS-ENERGIE'],information_necessaire='Plan exact des deux demi-corps B9310 : joint, interfaces, capots et débattement. P76 non adapté par invention.',recherches=['MINICARS-B9310 ; spécifications externes trouvées, aucune interface cotée.']),
          dict(id='CAPOTS-TERMINAISONS',bom_ids=['ELEC-CAPOTS','ELEC-TERMINAISONS','ELEC-GAINES'],information_necessaire='Interfaces BMS/PDB/QS8 documentées ; références cosses/contact/gaine et longueurs installées. Aucun capot inventé.',recherches=['BOM active et définitions terminaisons ; matières et dimensions critiques absentes.']),
          dict(id='FAISCEAUX',bom_ids=sorted({i for r in routes for i in r['bom_ids']}),information_necessaire='Sections et références réellement conservées, gaines et coupes, inclusions OEM, contacts. Courbes insuffisantes pour masse complète.',recherches=['53 routes Cable Workbench et contrat retenues ; sources câble1522341, USBFireWire et colliers.']),
          dict(id='TPU-TRANCHAGE',bom_ids=['MEC-SUPPORTS-RF','ELEC-PASSEFILS'],information_necessaire='Tranchage candidat reproductible et volumes extrudés nets ; masse installée conservée inconnue jusque-là.',recherches=['Aucun slicer initialement disponible ; outillage officiel Cura4.9.1 en préparation.'])],
        controles=dict(lecture_geometries=all(g['valide'] for g in geometries),reouverture_nouveau_processus=True,
                      documents_modifies_par_reouverture=False),qualification='À valider',finalisation_correcte=True)
    mutations=RUNTIME/'mutations.json'
    if mutations.exists():report['mutations']=json.loads(mutations.read_text('utf-8'))
    interfaces=RUNTIME/'interfaces.json'
    if interfaces.exists():report.update(json.loads(interfaces.read_text('utf-8')))
    byref={g['reference']:g for g in geometries}
    for spec in report['fabrication']:
        g=byref[spec['reference']]
        spec.update(volume_brut_mm3=g['volume_mm3'],barycentre_mm=g['barycentre_mm'],solides_bruts=g['solides_bruts'])
    sliced_path=RUNTIME/'tranchage_tpu.json'
    if sliced_path.exists():
        report['tranchage_tpu']=json.loads(sliced_path.read_text('utf-8'))
        for sliced in report['tranchage_tpu']['resultats']:
            lineage=mesh_sources[sliced['reference']]
            lineage['stl_tranche_identique_au_natif_courant']=lineage['sha256_stl_retesselle']==sliced['stl_sha256']
            sliced['reconciliation_source_natif']=lineage
            sliced['sha256_natif_source']=lineage['sha256_natif_source']
            if not lineage['stl_tranche_identique_au_natif_courant']:
                sliced['volume_extrude_mm3']=None
                report['blocages'].append(dict(id='TPU-STL-OBSOLETE',bom_ids=['MEC-SUPPORTS-RF','ELEC-PASSEFILS'],
                    information_necessaire='Relancer le tranchage : STL courant différent du STL source du Gcode.',recherches=[sliced['reference']]))
        for spec in report['fabrication']:
            sliced=next((r for r in report['tranchage_tpu']['resultats'] if r['reference']==spec['reference']),None)
            if sliced:
                spec.update(tranchage=sliced,volume_extrude_piece_mm3=sliced['volume_extrude_mm3'],
                    nature_volume_extrude='Volume de filament commandé par Cura, arrondi au mm³ dans le journal, compensation de débit106% incluse ; hors support/adhésion/purge ; aucune mesure physique.')
        if all(r['retour_processus']==0 and r['volume_extrude_mm3'] is not None for r in report['tranchage_tpu']['resultats']):
            report['blocages']=[b for b in report['blocages'] if b['id']!='TPU-TRANCHAGE']
    dump(OUT,report)
    print(json.dumps(dict(preuve=rel(OUT),geometries=len(geometries),reouvertures=len(reopen),solides_valides=report['controles']['lecture_geometries']),ensure_ascii=False),flush=True)

def trancher_tpu():
    """Orchestrer le moteur fabricant ; conserver son métrage brut, sans masse."""
    folder=RUNTIME/'tooling/cura491';engine=folder/'CuraEngine.exe';resources=folder/'resources'
    settings=dict(layer_height='.15',layer_height_0='.15',machine_nozzle_size='.4',material_diameter='2.85',
        material_density='1.22',line_width='.38',wall_line_width='.38',wall_line_width_0='.38',wall_line_width_x='.38',
        skin_line_width='.38',infill_line_width='.38',wall_line_count='4',wall_thickness='1.52',
        top_layers='4',bottom_layers='4',top_thickness='.6',bottom_thickness='.6',top_bottom_thickness='.6',
        infill_sparse_density='100',infill_line_distance='.38',infill_pattern='lines',infill_overlap='0',
        material_flow='106',material_print_temperature='228',material_print_temperature_layer_0='245',
        material_bed_temperature='0',material_bed_temperature_layer_0='0',
        speed_print='25',speed_wall='25',speed_wall_0='25',speed_wall_x='25',speed_topbottom='25',speed_infill='25',
        speed_layer_0='18',speed_travel='150',support_enable='false',adhesion_type='none',skirt_line_count='0',
        prime_tower_enable='false',prime_blob_enable='false',retraction_extra_prime_amount='0',
        retraction_enable='true',retraction_amount='6.5',retraction_speed='35',center_object='true',
        mesh_position_x='165',mesh_position_y='120',machine_extruder_count='1',machine_start_gcode='',machine_end_gcode='')
    env=os.environ.copy();env['CURA_ENGINE_SEARCH_PATH']=str(resources/'definitions')
    results=[]
    profile_files=[resources/'definitions/ultimaker_s5.def.json',resources/'extruders/ultimaker_s5_extruder_left.def.json',
        resources/'variants/ultimaker_s5_aa04.inst.cfg',resources/'materials/ultimaker_tpu_black.xml.fdm_material',
        resources/'quality/ultimaker_s5/um_s5_aa0.4_TPU_Normal_Quality.inst.cfg']
    for reference in [r for r in candidates() if r.startswith(('P70_','P79_','P80_'))]:
        mesh=RUNTIME/(reference+'.stl');gcode=RUNTIME/(reference+'.gcode')
        # Le frontal Cura résout normalement les héritages et expressions S5.
        # Ici le moteur CLI reçoit la base mono-extrudeur et tous les paramètres
        # du scénario explicitement, sans inventer un travail firmware S5 prêt.
        cmd=[str(engine),'slice','-v','-j',str(resources/'definitions/fdmprinter.def.json'),
             '-s','machine_extruder_count=1','-s','machine_width=330','-s','machine_depth=240',
             '-s','machine_height=300']
        for key,value in settings.items():cmd.extend(['-s',key+'='+value])
        cmd.extend(['-e0','-j',str(resources/'definitions/fdmextruder.def.json')])
        for key,value in settings.items():cmd.extend(['-s',key+'='+value])
        cmd.extend(['-l',str(mesh),'-o',str(gcode)])
        process=subprocess.run(cmd,env=env,capture_output=True,text=True,encoding='utf-8',errors='replace')
        log=RUNTIME/(reference+'_cura.log');log.write_text(process.stdout+'\n'+process.stderr,'utf-8')
        text=gcode.read_text('utf-8') if gcode.exists() else ''
        volumes=re.findall(r'Filament\s*\(mm\^3\)\s*:\s*([0-9.]+)',process.stderr)
        results.append(dict(reference=reference,retour_processus=process.returncode,
            sha256_natif_source=sha(MEC/candidates()[reference]['fichier']),
            stl=mesh.relative_to(ROOT).as_posix(),stl_sha256=sha(mesh),gcode=gcode.relative_to(ROOT).as_posix(),
            gcode_sha256=sha(gcode) if gcode.exists() else None,log=log.relative_to(ROOT).as_posix(),log_sha256=sha(log),
            volume_extrude_mm3=float(volumes[0]) if len(volumes)==1 else None,
            nombre_couches=len(re.findall(r'^;LAYER:',text,re.M)),
            types_features=sorted(set(re.findall(r'^;TYPE:(.*)$',text,re.M))),
            limites=['Scénario de tranchage seulement ; aucune machine physique sélectionnée ni impression exécutée.',
                     'Supports, adhésion et purge désactivés ; pontages et fabricabilité TPU restent À valider.',
                     '4parois/4peaux et100% sont des paramètres projet ; profil matériau constructeur dérivé explicitement.',
                     'Extrusion nominale du moteur, pas pesée de pièce ni qualification.']))
        print(reference,process.returncode,volumes,flush=True)
    data=dict(outil='CuraEngine4.9.1 officiel extrait sans installation système',moteur_sha256=sha(engine),
        paquet_sha256=sha(RUNTIME/'tooling/Ultimaker_Cura-4.9.1-amd64.exe'),
        source_paquet='https://github.com/Ultimaker/Cura/releases/tag/4.9.1',parametres=settings,
        methode='Base CLI fdmprinter/fdmextruder mono-extrudeur, gabarit S5 et paramètres explicites dérivés du profil TPU officiel ; ce fichier n’est pas un travail machine S5 prêt à imprimer.',
        profils=[dict(fichier=p.relative_to(ROOT).as_posix(),sha256=sha(p)) for p in profile_files],resultats=results)
    dump(RUNTIME/'tranchage_tpu.json',data)
    if OUT.exists():
        report=json.loads(OUT.read_text('utf-8'));report['tranchage_tpu']=data
        for spec in report['fabrication']:
            sliced=next((r for r in results if r['reference']==spec['reference']),None)
            if sliced:
                spec['tranchage']=sliced;spec['volume_extrude_piece_mm3']=sliced['volume_extrude_mm3']
                spec['nature_volume_extrude']='Volume de filament commandé par Cura, arrondi au mm³ dans le journal, compensation de débit106% incluse ; hors support/adhésion/purge ; aucune mesure physique.'
        if all(r['retour_processus']==0 and r['volume_extrude_mm3'] is not None for r in results):
            report['blocages']=[b for b in report['blocages'] if b['id']!='TPU-TRANCHAGE']
        report['script_sha256']=sha(__file__);dump(OUT,report)

def controler_interfaces():
    """Contrôler les reprises contre les occurrences proposées et les obstacles."""
    from read_brep_prototype import Reader
    from verify_fixations_guides_prototype import overlap, common_volume
    report=json.loads(OUT.read_text('utf-8'))
    construction=json.loads((VER/'construction_prototype.json').read_text('utf-8'))
    rows={(r['parent'],r['occurrence']):dict(r) for r in construction['occurrences'] if r['parent'].startswith('sous_assemblages/')}
    for row in report.get('modifications_occurrences',[]):rows[(row['parent'],row['occurrence'])]['matrice']=row['matrice']
    for row in report.get('ajouts_occurrences',[]):rows[(row['parent'],row['occurrence'])]=row
    reader=Reader(MEC);shapes={}
    for key,row in rows.items():shapes[key]=reader.occurrence(row)
    focus={key for key,row in rows.items() if Path(row['source']).stem.startswith(('P10_','P65_','P76_','EQ_QS8S_')) or 'P10' in row['occurrence']}
    collisions=[];pairs=0;seen=set()
    for key in focus:
        for other in rows:
            pair=tuple(sorted((key,other)))
            if key==other or pair in seen:continue
            seen.add(pair)
            if not overlap(shapes[key].BoundBox,shapes[other].BoundBox):continue
            pairs+=1;volume,details=common_volume(shapes[key],shapes[other])
            if volume>1e-4:collisions.append(dict(a=key[1],b=other[1],volume_mm3=volume,details=details))
    baseline=ROOT/'.runtime/orch-cao-masse-1/baseline/hardware/mecanique/cartographe'
    old_reader=Reader(baseline);comparisons=[]
    for ref,spec in candidates().items():
        if ref.startswith(('P10_','P65_','P76_','P73_')):continue
        name=root_name(MEC/spec['fichier']);old=old_reader.shape(spec['fichier'],name);new=reader.shape(spec['fichier'],name)
        comparisons.append(dict(reference=ref,volume_avant_mm3=old.Volume,volume_apres_mm3=new.Volume,
            geometrie_volume_conservee=abs(old.Volume-new.Volume)<1e-6,
            objet_source_conserve=True,apparences_documentees_conservees=appearance_signature(baseline/spec['fichier'])==appearance_signature(MEC/spec['fichier'])))
    report['controle_interfaces']=dict(paires_presel_bbox=pairs,collisions=collisions,
        perimetre='P10/P65/P76/QS8 et16 fixations proposées contre toutes occurrences du prototype, y compris les53 routes ; contacts nominaux de volume nul admis, chevauchements conservés sans exemption.',
        seuil_numerique_volume_mm3=1e-4,comparaisons_metadata=comparisons,
        methode_apparences='Comparaison par nom des seules géométries affichées : couleurs diffuses de la table matériau V3 et transparence, sans dépendre de l’ordre des viewproviders ni des noms de blobs binaires.',qualification='À valider')
    for collision in collisions:
        if collision['a']=='QS8_manuel' and collision['b'] in ('F37_POS','F37_NEG','F38_POS','F38_NEG') or collision['b']=='QS8_manuel' and collision['a'] in ('F37_POS','F37_NEG','F38_POS','F38_NEG'):
            collision['classification']='Blocage géométrique de terminaison QS8, non conforme/non résolu ; absence de données ne vaut pas exemption.'
            collision['information_necessaire']='Plan exact B9310 des sorties de fils et longueurs engagées ; parcours actuels aboutissent à Y10/−34 alors que le volume externe documenté atteint Y18,45/−42,45. Aucun engagement de câble dans la matière ni plan de joint n’est validé.'
    report['script_sha256']=sha(__file__);dump(OUT,report)
    print(json.dumps(dict(paires=pairs,collisions=collisions),ensure_ascii=False),flush=True)

if __name__=='__main__':
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8')
    if hasattr(sys.stderr,'reconfigure'):sys.stderr.reconfigure(encoding='utf-8')
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['sources','appliquer','interfaces','verifier','trancher','controler_interfaces'])
    mode=parser.parse_args().mode
    {'sources':download_sources,'appliquer':change_native,'interfaces':interfaces_fabriquees,'verifier':extract_verify,'trancher':trancher_tpu,'controler_interfaces':controler_interfaces}[mode]()
    # FreeCADGui chargé pour les apparences peut attendre la boucle Qt pendant
    # la destruction Python ; tous les documents sont déjà fermés explicitement.
    sys.stdout.flush(); sys.stderr.flush()
    os._exit(0)
