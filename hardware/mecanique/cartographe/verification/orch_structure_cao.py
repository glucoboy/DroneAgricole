"""Infrastructure FreeCAD ORCH-CAO-MASSE-1 : extraction OEM et preuve structure.

Exécuter avec le Python livré par FreeCAD 1.1, depuis le workspace :
  & 'C:/Program Files/FreeCAD 1.1/bin/python.exe' .../orch_structure_cao.py
  & 'C:/Program Files/FreeCAD 1.1/bin/python.exe' .../orch_structure_cao.py --verify

La recette lit les natifs sauvegardés et les originaux conservés, sans modifier
la CAO. Elle écrit uniquement orch_cao_masse_structure.json. Les données de
masse ci-dessous sont des observations documentaires déclaratives ; aucun
total, densité, centrage ou calcul d'inertie physique n'est calculé ici.
Les quatre géométries insuffisantes restent bloquées faute de plan applicable.
"""
from pathlib import Path
from collections import Counter
from datetime import datetime, timezone
import argparse
import hashlib
import json
import os
import platform
import sys
import xml.etree.ElementTree as ET
import zipfile

import FreeCAD as App

ROOT = Path(__file__).resolve().parents[4]
MEC = ROOT / 'hardware/mecanique/cartographe'
BASELINE = ROOT / '.runtime/orch-cao-masse-1/baseline'
OUTPUT = MEC / 'verification/orch_cao_masse_structure.json'
DAY = '2026-10-25'
SOURCE_PART = 'pieces/commerce/EQ_Chassis_X650.FCStd'
PARENT = 'sous_assemblages/SA01_Prototype_Structure.FCStd'
EXPECTED = {
    'EQ_Gemfan1555_CW.FCStd': '2a19739a716240440d13cd416982658af875564595b155a13891d8479daef904',
    'EQ_Gemfan1555_CCW.FCStd': '4bd64807b0f2ad6d93e39a9bc110daf07de147ba500641eea271256c086d3528',
    'EQ_Tekko32_45A_Prototype.FCStd': 'd003ea5d326959df6d38c3209352d0fee45af22f9112d8a7179dfea4305657e4',
    'EQ_X650_Colonne90_Prototype.FCStd': 'a2fb5afc1c7a300f2ee84b65c69d63680026a66feb3e64b60569f33062dadb24',
    'EQ_Chassis_X650.FCStd': '1e88f157939f7c3ede7ac39751d8ec33949a2dffda32246963c6fb113baa0909',
}
RIGHTS = 'Original public conservé inchangé ; aucune licence explicite de réutilisation du modèle identifiée dans la source consultée.'
SPARE_URL = 'https://holybro.com/products/spare-parts-x650-kit'
DOWNLOAD_URL = 'https://docs.holybro.com/drone-development-kit/x650-development-kit/download'
TMOTOR_URL = 'https://store.tmotor.com/product/mn4014-kv330-motor-navigator-type.html'
GEMFAN_URL = 'https://www.gemfanhobby.com/carbon-fiber-props.html'
T_TYPE_URL = 'https://www.gemfanhobby.com/t-type-carbon-fiber-props.html'
GUIDE_URL = 'https://2367252986-files.gitbook.io/~/files/v0/b/gitbook-x-prod.appspot.com/o/spaces%2FLIgtGDAvVGkCKGOJb1bR%2Fuploads%2FYJkB7PciJcyE7S8ID7z7%2FHolybro_X650_Assembly_Guide_V1.1.pdf?alt=media&token=9dbcfed5-59a2-4924-b5b5-27e747121183'
ESC_PDF_URL = 'https://cdn.shopifycdn.net/s/files/1/0604/5905/7341/files/Holybro_Tekko32_F4_45A_ESC_SPEC_V1.1.pdf?v=1721112993'
FLYING_URL = 'https://www.flyingtech.co.uk/product/holybro-x650-tekko32-f4-45a-esc-speed-controller-2-6s/'
PREMIUM_URL = 'https://www.premium-modellbau.de/en/holybro-x650-spare-parts-tekko32-f4-45a-esc-1pc-31230'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def relative(path):
    return Path(path).relative_to(ROOT).as_posix()


def source(sid, url, filename=None, revision=None, faits=None, nature='fabricant'):
    path = MEC / filename if filename else None
    if path:
        assert path.is_file(), str(path)
    return {'id': sid, 'url': url, 'fichier': relative(path) if path else None,
            'sha256': sha(path) if path else None, 'revision': revision,
            'date_consultation': DAY, 'droits': RIGHTS, 'nature': nature,
            'faits_verifies': faits,
            'limite_capture': None if path else 'Consulté par outil web ; téléchargement direct refusé/local_rate_limited ou HTTP 429. Aucun faux original reconstruit.'}


def sources():
    prefix = 'sources_fabricants/orch_structure/'
    return [
        source('STR-S01', DOWNLOAD_URL, 'sources_fabricants/origine_v01/x650-frame-2025-0825.stp',
               'Export Creo 2025-08-25T09:34:18 ; noms de pièces 2024 dans la source',
               'Original OEM X650, 25 393 107 octets, modèle source des feuilles conservées.'),
        source('STR-S02', DOWNLOAD_URL, 'sources_fabricants/origine_v01/holybro_x650.html', None,
               'Page de téléchargement OEM préservée antérieurement ; liens vers STEP et guide. Date de capture initiale non établie ; référence revérifiée par web le 25 octobre.'),
        source('STR-S03', GUIDE_URL, prefix+'Holybro_X650_Assembly_Guide_V1.1_original.pdf', 'V1.1',
               'Guide deux pages : colonnes aluminium M3×90 et M3×50, chacune quatre ; diffuseur Light Diffuser ; références de pièces et visserie.'),
        source('STR-S04', SPARE_URL, None, None,
               'Catalogue OEM : 510248 une jambe ; paire hélices520095 ; moteurs31228 CW/31229 CCW ; ESC X65031230 ; tube510241 ; articulation510254 ; base moteur510235 ; plateaux510245/510246/510247. Métadonnées Shopify weight non utilisables comme masses nettes.'),
        source('STR-S05', TMOTOR_URL, prefix+'TMotor_MN4014_KV330_original.html', 'Rapport MN.00026 KV330',
               '150 g hors fils ;171 g avec fils600 mm18AWG ; pas de tolérance publiée ; contenu adaptateur et variante OEM non démontrés.'),
        source('STR-S06', 'https://store.tmotor.com/images/202606/MN4014-draw-0603-v1.jpg',
               prefix+'TMotor_MN4014_draw_0603_v1_original.jpg', 'MN4014-draw-0603-v1',
               'Plan interfaces MN4014 et adaptateurs : diamètre44,7 ; longueur42,9 sur dessin, distincte de34,5 du tableau ; variante exacte OEM à réconcilier.'),
        source('STR-S07', ESC_PDF_URL, prefix+'Holybro_Tekko32_F4_45A_ESC_SPEC_V1.1_original.pdf', 'V1.1 ;31104/20156 ; AM32',
               'ESC simple 34,3×17,3×4,5 mm,5,8 g ; condensateur330µF35V et cinq fils100 mm énumérés séparément. Ne décrit pas la masse nette du31230 précâblé.'),
        source('STR-S08', GEMFAN_URL, prefix+'Gemfan_carbon_fiber_original.html', None,
               'Plusieurs familles1555L ; aucune masse ni plan de la variante OEM520095.'),
        source('STR-S09', T_TYPE_URL, prefix+'Gemfan_t_type_original.html', None,
               '1555L T-Type listée, sans démonstration de correspondance au520095 ni dessin coté.'),
        source('STR-S10', 'https://img03.71360.com/w3/5p3560/20251117/50ffa18f7578335345b42f12d991fd78.pdf?dl=1&dlf=2025+Gemfan+Product+Catalog.pdf',
               prefix+'Gemfan_2025_Product_Catalog_original.pdf', 'Catalogue2025,43 pages',
               'Catalogue lié depuis les pages fabricant : aucune entrée textuelle1555/1555L. Pages finales ailes fixes sans plan applicable à520095. Les dimensions des modèles FPV voisins ne sont pas transposées.'),
        source('STR-S11', 'https://holybro.com/cdn/shop/files/520095.jpg?v=1720166565', prefix+'Holybro_520095_original.jpg',
               'Image CDN520095, v1720166565', 'Deux hélices et trois trous visibles par moyeu ; aucune cote ni masse tirée de la photographie.'),
        source('STR-S12', 'https://holybro.com/cdn/shop/files/Tekko32_F4_45A_ESC_1P.jpg?v=1720170904', prefix+'Holybro_31230_original.jpg',
               'Image CDN31230, v1720170904', 'ESC gainé/précâblé, prises puissance/moteur et fil commande visibles ; géométrie sous gaine et longueurs non cotées.'),
        source('STR-S13', FLYING_URL, prefix+'FlyingTech_31230_original.html', None,
               'Distributeur : ESC31230, câblage long, MR30/XT30 ; reprend5,8 g sans périmètre installé. Pas de plan3D exact.', 'distributeur, statut officiel non démontré dans la page conservée'),
        source('STR-S14', PREMIUM_URL, prefix+'PremiumModellbau_31230_original.html', None,
               'Distributeur : référence31230 et fabricant ; pas de masse nette ou modèle3D.', 'distributeur/importateur identifié'),
        source('STR-S15', 'https://newbeedrone.com/products/holybro-spare-parts-x650-kit-1', None, None,
               'Distributeur : barcode520095, pas de plan ni masse nette trouvés ; conservation directe refusée HTTP429.', 'distributeur'),
    ]


def search_log():
    return [
        {'id': 'STR-R01', 'classe': 'locale', 'bom_ids': ['MEC-OEM-PLATEAUX','MEC-OEM-BRAS','MEC-OEM-TRAIN','MEC-OEM-COLONNES','MEC-OEM-FIXATIONS','MEC-MOTEUR','KIT-LED'],
         'sources': ['STR-S01','STR-S02','STR-S03'], 'requetes': ['sources_fabricants origine_v01 ; XML Document.xml du natif OEM ; BOM et manifeste actifs ; build_prototype.py en lecture seule'],
         'resultat': '200 feuilles géométriques OEM actives identifiées. Les modèles OEM ne portent pas de densité physique documentée ; matériau générique ShapeMaterial partagé non utilisé. Colonnes90 remplacées par réservation ; pas de masse nette OEM conservée.'},
        {'id': 'STR-R02', 'classe': 'fabricant', 'bom_ids': ['MEC-OEM-PLATEAUX','MEC-OEM-BRAS','MEC-OEM-TRAIN','MEC-OEM-COLONNES','MEC-OEM-FIXATIONS','MEC-FIXATION-HELICES','KIT-LED'],
         'sources': ['STR-S03','STR-S04'], 'requetes': ['Holybro X650 spare parts net weight landing gear510248 tube510241 plate510245510246510247 arm connector510254 motor base510235 ; HUAZHU-LV-M3-50/90'],
         'resultat': 'Références et contenu mécanique partiellement documentés ; aucune masse nette composant utilisable ni composition précise des matériaux. Valeur kit2000 g et poids Shopify explicitement rejetés. Deux tentatives téléchargement catalogue officiel .js/HTML ont retourné local_rate_limited ; lecture web primaire réussie.'},
        {'id': 'STR-R03', 'classe': 'fabricant', 'bom_ids': ['MEC-MOTEUR','MEC-FIXATION-HELICES'],
         'sources': ['STR-S04','STR-S05','STR-S06'], 'requetes': ['MN4014 KV330 mass excluding cables including cables technical drawing exact Holybro31228/31229'],
         'resultat': '150/171 g documentaires et plan v1 obtenus ; condition600 mm fils du modèle catalogue non applicable sans vérification aux câbles OEM conservés. Masse des adaptateurs/écrous et inclusion dans150 g non démontrées.'},
        {'id': 'STR-R04', 'classe': 'fabricant', 'bom_ids': ['MEC-ESC'],
         'sources': ['STR-S04','STR-S07','STR-S12'], 'requetes': ['Holybro31230 X650-Tekko32 F4 45A 3D CAD net weight ; downloads ESC'],
         'resultat': 'Fiche simple31104/20156 et photo exacte31230 obtenues, mais aucun STEP ni plan coté du31230 monté sous gaine. F3,4en1,Metal,BigFET et autres modèles exclus.5,8 g ne devient pas masse du31230 installé.'},
        {'id': 'STR-R05', 'classe': 'fabricant', 'bom_ids': ['MEC-HELICE-CW','MEC-HELICE-CCW'],
         'sources': ['STR-S04','STR-S08','STR-S09','STR-S10','STR-S11'], 'requetes': ['site.gemfanhobby.com1555 weight drawing STEP ; Holybro520095 propeller1555'],
         'resultat': 'Photo exacte trois trous et plusieurs famillesGemfan obtenues. Catalogue primaire43pages consulté ; aucun plan/moyeu/profil/matériau chiffré ou masse applicable. Le diamètre393,7 du natif reste une hypothèse non documentée, contradictoire avec15pouces381 du dossier.'},
        {'id': 'STR-R06', 'classe': 'distributeur', 'bom_ids': ['MEC-ESC','MEC-HELICE-CW','MEC-HELICE-CCW','MEC-OEM-TRAIN'],
         'sources': ['STR-S13','STR-S14','STR-S15'], 'requetes': [FLYING_URL,PREMIUM_URL,'NewBeeDrone520095 ; Premium-Modellbau510248'],
         'resultat': 'Pas de plan3D/masse nette exacte supplémentaire. FlyingTech identifieMR30/XT30 mais répète5,8 g non ventilés. Aucun poids voisin Foxtech,Tarot ou Gemfan variante différente retenu.'},
        {'id': 'STR-R07', 'classe': 'bibliotheque_tracable', 'bom_ids': ['MEC-ESC','MEC-HELICE-CW','MEC-HELICE-CCW','MEC-OEM-COLONNES'],
         'sources': [], 'requetes': ['site.grabcad.com "Gemfan" "1555"','site.3dcontentcentral.com "Tekko32"','site.snapeda.com "31230" Holybro','"Gemfan1555" "step"','"Tekko32 F4 45A" "CAD"','"HUAZHU-LV-M3-90"'],
         'resultat': 'Aucun modèle exact traçable trouvé dans les résultats consultés ; absence de résultat de recherche, pas démonstration universelle d’inexistence. Aucun modèle voisin ou non sourcé importé.'},
    ]


def global_shape(obj):
    shape = obj.Shape.copy()
    shape.Placement = obj.getGlobalPlacement().multiply(obj.Placement.inverse()).multiply(shape.Placement)
    return shape


def shape_record(obj, transform=False):
    shape = global_shape(obj) if transform else obj.Shape
    b = shape.BoundBox
    return {'solides': len(shape.Solids), 'valide': shape.isValid(), 'volume_brut_mm3': shape.Volume,
            'bbox_mm': [b.XMin,b.YMin,b.ZMin,b.XMax,b.YMax,b.ZMax],
            'centre_volume_mm': list(shape.CenterOfMass) if hasattr(shape,'CenterOfMass') else None,
            'solides_bruts': [{'volume_mm3':s.Volume,'centre_volume_mm':list(s.CenterOfMass)} for s in shape.Solids],
            'matrice_placement_global': list(obj.getGlobalPlacement().toMatrix().A),
            'masse_physique_g': None, 'densite_g_cm3': None,
            'limite': 'Volume et centre géométriques, sans attribution de masse ni distribution interne physique.'}


def all_paths(doc, name, prefix=()):
    obj = doc.getObject(name)
    group = getattr(obj, 'Group', [])
    route = prefix + (name,)
    if group:
        result = []
        for child in group:
            result.extend(all_paths(doc, child.Name, route))
        return result
    return [route]


def attribution(number, label):
    if number <= 31:
        return ['MEC-OEM-TRAIN'], 'conservé', None
    if number in [309,310,311,312]:
        return ['MEC-OEM-PLATEAUX'], 'conservé', None
    if number in range(84,88):
        return ['MEC-OEM-COLONNES'], 'conservé', None
    if number in [184,216,248,280]:
        return ['MEC-MOTEUR'], 'conservé', 'Solide OEM regroupé ; fixation d’hélice susceptible d’être intégrée au solide, périmètre matériel non séparé.'
    if number in [185,217,249,281]:
        return ['KIT-LED'], 'inclusion à confirmer', 'Diffuseur identifié par le guide ; inclusion dans la masse du module LED à fixer, sans second compte dans bras.'
    if number in [212,244,276,308]:
        return [], 'non attribué', 'Petit solide OEM voisin du diffuseur ; désignation00/001/002/003 insuffisante pour identifier fonction, matériau et ligneBOM. Candidat KIT-LED non imposé.'
    if 181 <= number <= 308:
        return ['MEC-OEM-BRAS'], 'conservé', 'Visserie propre au bras et à la base moteur incluse dans ce périmètre ; ne pas ajouter à la quincaillerie résiduelle.'
    if number in [76,77]:
        return ['MEC-OEM-FIXATIONS'], 'fonction à confirmer', 'Supports intermédiaires OEM conservés ; utilité après retrait rails à justifier avant retrait ou calcul.'
    return ['MEC-OEM-FIXATIONS'], 'conservé', None


def baseline_check():
    records = []
    for name, expected in EXPECTED.items():
        path = MEC / 'pieces/commerce' / name
        base = BASELINE / relative(path)
        observed = sha(path)
        assert observed == expected, f'Empreinte inattendue {name}: {observed}'
        assert base.is_file() and sha(base) == expected, f'Baseline absente/différente {base}'
        records.append({'fichier': relative(path), 'sha256_t0': expected, 'sha256_courant': observed, 'baseline_conforme': True})
    assert sha(MEC/'sources_fabricants/origine_v01/x650-frame-2025-0825.stp') == '62cf031a85c59a7f023c2b525115497dfb0821de9c964c1a5cf905c549d156f7'
    return records


def mapping(manifest):
    doc = App.openDocument(str(MEC/SOURCE_PART))
    occurrences = [o for o in manifest['prototype_cartographe']['occurrences'] if o['parent'] == PARENT and o['source'] == SOURCE_PART]
    assert len(occurrences) == 73, len(occurrences)
    rows, seen = [], set()
    for occurrence in occurrences:
        leaves = []
        for route in all_paths(doc, occurrence['objet_source']):
            name = route[-1]
            assert name not in seen, f'Feuille géométrique comptée deux fois : {name}'
            seen.add(name)
            obj = doc.getObject(name)
            number = int(name.replace('Part__Feature','') or '0')
            bom_ids, status, limits = attribution(number, obj.Label)
            leaves.append({'objet_source': name, 'designation_source': obj.Label,
                           'chemin_source': SOURCE_PART+'#'+'/'.join(route),
                           'chemin_occurrence': PARENT+'#'+occurrence['occurrence']+'/'+('/'.join(route[1:]) if len(route)>1 else name),
                           'bom_ids': bom_ids, 'quantite_feuille_conservee': 1,
                           'quantite_statut': 'Définition géométrique du prototype ; présence matérielle non inventoriée',
                           'quantite_physique_relevee': None,
                           'statut_rattachement': status, 'limites': limits,
                           'geometrie': shape_record(obj, True)})
        rows.append({'parent': occurrence['parent'], 'occurrence': occurrence['occurrence'], 'objet_source': occurrence['objet_source'],
                     'source': occurrence['source'], 'bom_ids_actuels': occurrence.get('bom_ids',[]), 'feuilles': leaves,
                     'compte_masse_du_parent': False, 'regle_comptage': 'Seules les lignesBOM/leurs inclusions déclarées portent une masse. Le lien OEM et ses feuilles ne s’additionnent jamais.'})
    assert len(seen) == 200, len(seen)
    columns = [shape_record(doc.getObject('Part__Feature%03d'%i), True) for i in range(80,88)]
    App.closeDocument(doc.Name)
    return rows, columns


def geometry_records():
    rows = []
    descriptions = {
        'EQ_Gemfan1555_CW.FCStd': (['MEC-HELICE-CW'], 'Enveloppe conservée, remplacement bloqué', ['STR-S04','STR-S08','STR-S09','STR-S10','STR-S11'],
            'Profil, épaisseur et moyeu non documentés ; modèle actuel un seul alésage contre trois trous visibles sur photo520095 ; diamètre393,7 non justifié. Aucun modèle exact substitué.'),
        'EQ_Gemfan1555_CCW.FCStd': (['MEC-HELICE-CCW'], 'Enveloppe conservée, remplacement bloqué', ['STR-S04','STR-S08','STR-S09','STR-S10','STR-S11'],
            'Même réserve queCW ; ne pas confondre variante de profil, sens aérodynamique et sens du filetage moteur.'),
        'EQ_Tekko32_45A_Prototype.FCStd': (['MEC-ESC'], 'Enveloppe de réservation conservée, remplacement bloqué', ['STR-S04','STR-S07','STR-S12','STR-S13','STR-S14'],
            '48×25×10 réservés ; référence retenue31230 précâblée, et non31104 nue. Dimensions/implantation sous gaine, fils, prises et condensateur exacts inconnus. Pas de faux remplacement par31104.'),
        'EQ_X650_Colonne90_Prototype.FCStd': (['MEC-OEM-FIXATIONS'], 'Reconstruction de réservation conservée, définition à terminer', ['STR-S01','STR-S03'],
            'Quatre colonnes M3×90 aluminium sont documentées, nuance/densité et interface de taraudage inconnues. Anneau actuel Ø5/passageØ2,5 ne décrit pas les filetages. Volume distinct de l’OEM invalide ; aucune équivalence massique revendiquée.'),
    }
    for name,(ids, treatment, source_ids, limits) in descriptions.items():
        path = MEC/'pieces/commerce'/name
        doc = App.openDocument(str(path))
        root = doc.getObject('Ensemble')
        assert root is not None
        before = shape_record(root)
        doc.recompute()
        after = shape_record(root)
        assert after['valide'] and after['solides'] > 0, name
        assert abs(after['volume_brut_mm3']-before['volume_brut_mm3']) < 1e-7, name
        assert all(abs(a-b)<1e-7 for a,b in zip(after['bbox_mm'],before['bbox_mm'])), name
        rows.append({'reference': name[:-6], 'fichier': relative(path), 'bom_ids': ids, 'traitement': treatment,
                     'limites': limits, 'source_ids': source_ids, 'sha256': sha(path), 'modifie': False,
                     'arbre_natif_conserve': [{'objet':o.Name,'type':o.TypeId} for o in doc.Objects],
                     'geometrie': after, 'controle_recalcul_sans_sauvegarde': 'conforme',
                     'apparences_preservees': 'Toutes les entréesZIP sont inchangées par empreinte complète du natif.'})
        App.closeDocument(doc.Name)
        assert sha(path) == EXPECTED[name], name
    return rows


def mass_records():
    definitions = [
        ('MEC-OEM-PLATEAUX',1,'jeu','Quatre plateaux OEM, hors rails/plateforme déportée.', ['STR-S01','STR-S03','STR-S04']),
        ('MEC-OEM-BRAS',4,'jeu','Tube, articulation, base moteur et visserie propre ; moteurs,LED et ESC séparés.', ['STR-S01','STR-S03','STR-S04']),
        ('MEC-OEM-TRAIN',1,'jeu','Deux jambes510248 avec raccords,patins et fixations propres.', ['STR-S01','STR-S03','STR-S04']),
        ('MEC-OEM-COLONNES',4,'piece','Colonnes50 mm uniquement ; les quatre90 mm sont dans le résiduel.', ['STR-S01','STR-S03']),
        ('MEC-OEM-FIXATIONS',1,'jeu','Colonnes90 et quincaillerie résiduelle ; exclure vis des bras/train/hélices et les composants retirés.', ['STR-S01','STR-S03','STR-S04']),
        ('MEC-MOTEUR',4,'piece','MN4014 KV330 OEM, câbles et adaptateurs à délimiter ; deuxCW31228 et deuxCCW31229 documentaires, affectation de chaque occurrence à confirmer.', ['STR-S04','STR-S05','STR-S06']),
        ('MEC-ESC',4,'piece','X650-Tekko32 F4 45A31230 précâblé, gaine et accessoires exacts à délimiter face aux faisceaux.', ['STR-S04','STR-S07','STR-S12','STR-S13','STR-S14']),
        ('MEC-HELICE-CW',2,'piece','HélicesCW de deux pairesOEM520095, sans rechanges.', ['STR-S04','STR-S08','STR-S09','STR-S10','STR-S11','STR-S15']),
        ('MEC-HELICE-CCW',2,'piece','HélicesCCW des mêmes deux pairesOEM520095.', ['STR-S04','STR-S08','STR-S09','STR-S10','STR-S11','STR-S15']),
        ('MEC-FIXATION-HELICES',4,'jeu','Adaptateurs,moyeux,écrous et vis propres ; inclusion éventuelle dans masse moteur inconnue.', ['STR-S01','STR-S03','STR-S04','STR-S06']),
        ('KIT-LED',4,'piece','ModulesWS2812, diffuseurs, câbles et vis propres à délimiter ; quatre petits solides sans nom à identifier.', ['STR-S01','STR-S03','STR-S04']),
    ]
    records = []
    for bid,q,u,scope,sids in definitions:
        row = {'bom_id':bid,'quantite':q,'unite':u,
               'quantite_statut':'Quantité de définition, pas inventaire physique',
               'quantite_physique_relevee':None,'masse_unitaire_g':None,'contribution_g':None,
               'qualificatif':'Masse installée inconnue','nature':'inconnue','source_ids':sids,
               'conditions':scope,'inclusions':[],'exclusions':['Emballage,expédition,stock et kit complet2000 g.'],
               'incertitude_g':None,'masse_incluse_dans':None,'valeurs_documentaires_conditionnelles':[]}
        if bid == 'MEC-MOTEUR':
            row['valeurs_documentaires_conditionnelles'] = [
                {'valeur_g':150,'nature':'fabricant nominale','source_id':'STR-S05','condition':'MN4014 KV330 catalogue hors fils ; adaptateurs/visserie non explicités ; pas masse installée OEM.', 'incertitude_g':None},
                {'valeur_g':171,'nature':'fabricant nominale','source_id':'STR-S05','condition':'MN4014 KV330 catalogue avec fils600 mm18AWG ; longueur/câble/prise du montageOEM non établis ; ne pas ajouter ces fils aux faisceaux une seconde fois.', 'incertitude_g':None}]
        if bid == 'MEC-ESC':
            row['valeurs_documentaires_conditionnelles'] = [
                {'valeur_g':5.8,'nature':'fabricant nominale, autre périmètre','source_id':'STR-S07','condition':'31104/20156 simple ; pas preuve de masse du31230 précâblé. Condensateur et cinq fils sont énumérés séparément ; inclusion exacte non attestée.', 'incertitude_g':None}]
        records.append(row)
    return records


def blockages():
    return [
        {'id':'STR-B01','bom_ids':['MEC-HELICE-CW','MEC-HELICE-CCW'],
         'information_necessaire':'Plan3D/plan coté exact Holybro520095/GemfanOEM : diamètre,pas,profil,épaisseur,moyeu,entraxe/alésages,sens ; masse nette unitaire et tolérance. Identification de la familleGemfan et révision.',
         'recherches':['STR-R05','STR-R06','STR-R07'],'impact':'Les quatre hélices restent enveloppes insuffisantes ; masse,interfaces et inertie de rotor non démontrées.'},
        {'id':'STR-B02','bom_ids':['MEC-ESC'],
         'information_necessaire':'31230 : révision de carte,plan monté sous gaine,longueurs/sections des câbles,références prises,condensateur/protections inclus,masse nette du périmètre conservé.',
         'recherches':['STR-R04','STR-R06','STR-R07'],'impact':'Quatre enveloppes48×25×10 conservées ;5,8 g n’est pas une masse installée. Recouvrement avec faisceaux doit être ventilé.'},
        {'id':'STR-B03','bom_ids':['MEC-OEM-PLATEAUX','MEC-OEM-BRAS','MEC-OEM-TRAIN','MEC-OEM-COLONNES','MEC-OEM-FIXATIONS'],
         'information_necessaire':'Masse nette par pièce ou ensemble exactement conservé,nuance/densité du carbone stratifié,polymères et aluminium,finition et tolérances ; lots et révisions OEM.',
         'recherches':['STR-R01','STR-R02','STR-R06'],'impact':'Géométrie OEM disponible mais volumes seuls insuffisants pour calculer masse complète ; kit2000 g non transféré.'},
        {'id':'STR-B04','bom_ids':['MEC-OEM-FIXATIONS'],
         'information_necessaire':'Plan et matière exacte des colonnesM3×90 ; diamètre/forme,profondeurs taraudées et masse nette. Rapprocher géométrie OEM invalide et anneau de réservation actuel.',
         'recherches':['STR-R01','STR-R02','STR-R07'],'impact':'Quatre colonnes reconstruites géométriquement valides mais définition non exacte. Ne pas appliquer densité d’alliage supposé.'},
        {'id':'STR-B05','bom_ids':['MEC-MOTEUR','MEC-FIXATION-HELICES'],
         'information_necessaire':'Correspondance variantesOEM31228/31229 aux natifs et à MN.00026, contenu exact adaptateur/écrou/vis inclus dans150/171 g,longueurs et prises de fils réellement conservées.',
         'recherches':['STR-R01','STR-R03'],'impact':'Quatre solides moteur présents ; masse installée et fixation hélices non ventilées. Les deux masses catalogue restent conditionnelles.'},
        {'id':'STR-B06','bom_ids':['KIT-LED','MEC-OEM-BRAS','MEC-OEM-FIXATIONS'],
         'information_necessaire':'Identifier feuilles00/001/002/003212/244/276/308, carteWS2812 et câblage ; fixer périmètre du diffuseur et de ses vis dansLED ; justifier supports076/077 après retrait rails.',
         'recherches':['STR-R01','STR-R02'],'impact':'Quatre feuilles actives sans rattachementBOM démontré ; deux supports conservés de fonction incertaine ; clôture bidirectionnelle impossible en l’état.'},
    ]


def build():
    baseline = baseline_check()
    # Le cliché T0 est intentionnel : le propriétaire unique consolide le
    # manifeste partagé pendant la production de cette preuve indépendante.
    mpath = BASELINE/'hardware/mecanique/cartographe/manifest.json'
    manifest = json.loads(mpath.read_text('utf-8'))
    mapped, columns = mapping(manifest)
    geometries = geometry_records()
    leaves = [leaf for row in mapped for leaf in row['feuilles']]
    counts = Counter(bid for leaf in leaves for bid in leaf['bom_ids'])
    unknown = [leaf['chemin_source'] for leaf in leaves if not leaf['bom_ids']]
    bad = [leaf['chemin_source'] for leaf in leaves if not leaf['geometrie']['valide']]
    return {
        'schema_version':1,'lot':'ORCH-CAO-MASSE-1','reference':'PREUVE-STRUCTURE-PROPULSION-ORCH',
        'date':DAY,'statut':'Implémenté','qualification':'À valider','conclusion':'préliminaire',
        'finalisation_correcte':True,'cloture_perimetre':False,
        'cadrage':{'probleme':'Réconcilier géométrie et masses des élémentsOEM conservés et de propulsion du prototype sans dock.',
                   'action':'Recherche bornée sources fabricant,distributeurs,bibliothèques puis extraction exhaustive du modèleOEM ; ne pas inventer un remplacement exact.',
                   'arret':'Pistes identifiées consultées sans plan applicable ; blocage local documenté sans interrompre autres sous-systèmes.',
                   'interdits':'Achat,fabrication,contact fabricant,essai matériel,raccordement drone et campagne simulation exclus.'},
        'environnement':{'os':platform.platform(),'architecture':platform.machine(),'freecad':list(App.Version()),'python':sys.version,'pid':os.getpid()},
        'entrees_t0':{'manifeste':relative(mpath),'sha256':sha(mpath),'configuration':'prototype_cartographe sans dock','baseline_natifs':baseline},
        'sources':sources(),'recherches':search_log(),'geometries':geometries,'masses':mass_records(),
        'mapping_oem':mapped,
        'colonnes_etages':{'source_objets_080_a_087':columns,
                          'conclusion':'Aucun doublon :90 mm en basZ−90..0,50 mm en hautZ33..83. Les080..083 originaux ne sont pas parmi les200 feuilles actives ; quatre occurrences indépendantes de la réservation90 les remplacent.'},
        'synthese_couverture':{'liens_oem':len(mapped),'feuilles_oem':len(leaves),'feuilles_par_bom':dict(sorted(counts.items())),
                              'feuilles_sans_bom':unknown,'feuilles_invalides':bad,'feuilles_doubles':[],
                              'colonnes90_reconstruites_occurrences':4,'enveloppes_helices_occurrences':4,'enveloppes_esc_occurrences':4,
                              'geometries_remplacees':0,'geometries_nouvellement_exactes':0,
                              'masse_installee_complete_connue':False,'total_masse_g':None,
                              'limite':'Un rattachementBOM indique le périmètre logique ; il ne démontre ni matériau,ni masse,ni exactitude de montage physique.'},
        'regles_comptage':[
            'MEC-X650-KIT : achat uniquement, aucune contribution massique embarquée.',
            'Les200 feuilles servent à décomposer les73 liens ; jamais additionner parentCAO et feuilles.',
            'Les quatre moteurs/LED sont géométriquement dans les groupesbras mais leurs masses restent horsMEC-OEM-BRAS.',
            'Les vis propres auxbras et au train restent dans ces ensembles ; quincaillerie résiduelle séparée.',
            'Les quatre colonnes90 sont dansMEC-OEM-FIXATIONS ; les quatre50 dansMEC-OEM-COLONNES.',
            'Paire520095 :1CW+1CCW ; deux paires donnent2CW+2CCW sans rechange embarquée.',
            'Fils,connecteurs,condensateurs,gaines et adaptateurs nécessitent une inclusion unique entre moteurs,ESC,faisceaux et fixationhélice.',
            'Masse nulleinconnue représentée parnull ; aucune métadonnéeShopify,masse kit ou densité générique appliquée.'
        ],
        'blocages':blockages(),
        'controles':[
            {'id':'STR-C01','protocole':'Vérifier SHA256 des cinq natifs contre baseline récupérable et attentesT0.','resultat':'conforme'},
            {'id':'STR-C02','protocole':'Développer récursivement les73 liens source actifs,200 feuilles uniques ; chemin source et occurrence conservés.','resultat':'conforme'},
            {'id':'STR-C03','protocole':'Ouvrir les quatre natifs assignés dans nouveauprocessusFreeCAD,recalculer,contrôler volumes/bbox/solides valides et refermer sans sauvegarde.','resultat':'conforme','limite':'Aucun remplacement géométrique possible démontré ; aucune sauvegarde native produite par cette recette.'},
            {'id':'STR-C04','protocole':'Inspecter validité de chaque feuilleOEM active,matrice globale,volume brut et dimensions.','resultat':'conforme' if not bad else 'non conforme','anomalies':bad},
            {'id':'STR-C05','protocole':'Contrôler couverture inverseBOM et contenus matériels.','resultat':'non conforme','motif':'Quatre petits solides non attribués ; exactitudeLED,fixationshélices et supports076/077 à résoudre.'},
            {'id':'STR-C06','protocole':'Calcul de masse installée,centrage et inerties physiques.','resultat':'non exécuté','motif':'Données indispensables inconnues ; calcul de masse métier réservé àC++ par intégrateur.'},
            {'id':'STR-C07','protocole':'Sauvegarde/fermeture/réouverture des natifs remplacés.','resultat':'sans objet','motif':'Aucun natif changé ; absence de plan applicable enregistrée comme blocage, pas comme remplacement.'},
        ],
        'fichiers_natifs_modifies':[],
        'limites':['Aucune qualification physique déduite.','Contrôle assemblage complet,interférences,rotors,liens et exports après intégration à réaliser par propriétaire unique.',
                   'Les preuves historiques et exportsGazebo ne sont ni régénérés ni attribués à une nouvelle géométrie par cette passe.']
    }


def verify(saved, observed):
    assert saved['entrees_t0'] == observed['entrees_t0'], 'EntréesT0 différentes'
    assert saved['sources'] == observed['sources'], 'Source modifiée'
    assert saved['mapping_oem'] == observed['mapping_oem'], 'Extraction géométrique non reproductible'
    assert saved['geometries'] == observed['geometries'], 'Natifs ou recalcul différents'
    assert saved['masses'] == observed['masses'], 'Valeurs déclaratives différentes'
    assert saved['synthese_couverture'] == observed['synthese_couverture'], 'Couverture différente'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify',action='store_true')
    args = parser.parse_args()
    evidence = build()
    if args.verify:
        saved = json.loads(OUTPUT.read_text('utf-8'))
        verify(saved,evidence)
        saved['verification_processus_independant'] = {'resultat':'conforme','date_utc':datetime.now(timezone.utc).isoformat(),
            'pid':os.getpid(),'pid_extraction_initiale':saved['environnement']['pid'],
            'perimetre':'SHA256,extraction200feuilles,quatre natifs recalculés ; reproductibilité volumes/bbox/placements/validité sans changement des fichiers.'}
        assert saved['environnement']['pid'] != os.getpid()
        saved['recette_sha256'] = sha(__file__)
        OUTPUT.write_text(json.dumps(saved,ensure_ascii=False,indent=2)+'\n','utf-8')
    else:
        evidence['recette_sha256'] = sha(__file__)
        OUTPUT.write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n','utf-8')
    print(json.dumps({'preuve':relative(OUTPUT),'verification':args.verify,'liens_oem':73,'feuilles_oem':200,
                      'natifs_modifies':0,'cloture':False,'feuilles_sans_bom':len(evidence['synthese_couverture']['feuilles_sans_bom'])},ensure_ascii=False))


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
