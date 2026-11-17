"""Vérification en lecture seule des feuilles OEM X650 du prototype.

Exécution : "C:/Program Files/FreeCAD 1.1/bin/python.exe" \
  hardware/mecanique/cartographe/verification/orch_verifier_interferences_oem.py
Les sources natives ne sont jamais sauvegardées. Le JSON produit est une preuve
technique distincte ; il ne modifie pas la proposition massique ou la BOM.
"""
from pathlib import Path
import hashlib
import json
import os
import sys
import FreeCAD as A

ROOT = Path(__file__).resolve().parents[4]
VER = Path(__file__).resolve().parent
NATIF = ROOT / 'hardware/mecanique/cartographe/pieces/commerce/EQ_Chassis_X650.FCStd'
PROPOSITION = VER / 'orch_reprise_kit_aluminium.json'
EXTRACTION = VER / 'orch_cao_masse_structure.json'
DENSITES = VER / 'orch_reprise_kit_densites.json'
SORTIE = VER / 'orch_verifier_interferences_oem.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run():
    avant = sha(NATIF)
    proposition = json.loads(PROPOSITION.read_text(encoding='utf-8'))
    if avant != proposition['preuve_geometrie']['natif_sha256']:
        raise ValueError('Natif différent de la proposition : refaire la comparaison')
    extraction = json.loads(EXTRACTION.read_text(encoding='utf-8'))
    feuilles = {leaf['objet_source']: leaf for group in extraction['mapping_oem']
                for leaf in group['feuilles']}
    doc = A.openDocument(str(NATIF))
    offsets = (0, 32, 64, 96)
    formes = {}
    for number in sorted({i + offset for offset in offsets for i in range(181, 213)}):
        obj = doc.getObject('Part__Feature' + str(number))
        if obj is None or obj.Shape.isNull() or not obj.Shape.isValid():
            raise ValueError('Feuille absente ou invalide : ' + str(number))
        shape = obj.Shape.copy()
        geo = feuilles[obj.Name]['geometrie']
        shape.Placement = A.Placement(A.Matrix(*geo['matrice_placement_global']))
        center = shape.CenterOfMass
        expected = geo['centre_volume_mm']
        if max(abs(x-y) for x,y in zip((center.x, center.y, center.z), expected)) > 1e-5:
            raise ValueError('Placement global non conforme : ' + str(number))
        formes[number] = shape

    hits = []
    erreurs = []
    reprises_repere_local = []
    groupes = []
    for offset in offsets:
        selected = [x + offset for x in (182, 183, 186, 187, 188, 189)]
        all_ids = [x + offset for x in range(181, 213)]
        tests = 0
        for n in selected:
            a = formes[n]
            for m in all_ids:
                if m == n or (m in selected and m < n):
                    continue
                b = formes[m]
                if not a.BoundBox.intersect(b.BoundBox):
                    continue
                tests += 1
                try:
                    common = a.common(b)
                except Exception as error:
                    # Une rotation rigide commune ne change pas les volumes et
                    # évite parfois une instabilité OCCT aux coordonnées globales.
                    try:
                        inverse = a.Placement.inverse()
                        aa, bb = a.copy(), b.copy()
                        aa.Placement = inverse.multiply(a.Placement)
                        bb.Placement = inverse.multiply(b.Placement)
                        common = aa.common(bb)
                        reprises_repere_local.append(dict(bras=1 + offset // 32,
                            objet_a='Part__Feature' + str(n), objet_b='Part__Feature' + str(m),
                            erreur_globale=str(error), volume_commun_mm3=common.Volume))
                    except Exception as retry_error:
                        erreurs.append(dict(bras=1 + offset // 32,
                            objet_a='Part__Feature' + str(n), objet_b='Part__Feature' + str(m),
                            erreur=str(error), erreur_reprise=str(retry_error)))
                        continue
                if common.Volume > 1e-6:
                    hits.append(dict(bras=1 + offset // 32,
                                     objet_a='Part__Feature' + str(n),
                                     objet_b='Part__Feature' + str(m),
                                     volume_commun_mm3=common.Volume))
        groupes.append(dict(bras=1 + offset // 32, paires_apres_filtre=tests))

    candidats = sorted(int(x['objet'].replace('Part__Feature', ''))
                       for x in proposition['pieces_candidats'])
    if len(candidats) != 12 or len(set(candidats)) != 12:
        raise ValueError('La sélection doit contenir 12 feuilles distinctes')
    entre_candidats = []
    erreurs_candidats = []
    testes_candidats = 0
    for i, n in enumerate(candidats):
        for m in candidats[i + 1:]:
            a, b = formes[n], formes[m]
            if not a.BoundBox.intersect(b.BoundBox):
                continue
            testes_candidats += 1
            try:
                common = a.common(b)
            except Exception as error:
                erreurs_candidats.append(dict(objet_a='Part__Feature' + str(n),
                                               objet_b='Part__Feature' + str(m), erreur=str(error)))
                continue
            if common.Volume > 1e-6:
                entre_candidats.append(dict(objet_a='Part__Feature' + str(n),
                                             objet_b='Part__Feature' + str(m),
                                             volume_commun_mm3=common.Volume))

    densites = json.loads(DENSITES.read_text(encoding='utf-8'))
    tubes = sorted(int(x['objet_source'].replace('Part__Feature', ''))
                   for x in densites['pieces'] if x['bom_id'] == 'MEC-OEM-BRAS')
    if tubes != [181, 213, 245, 277]:
        raise ValueError('Sélection inattendue des tubes carbone')
    entre_tubes = []
    erreurs_tubes = []
    testes_tubes = 0
    for n in candidats:
        for m in tubes:
            a, b = formes[n], formes[m]
            if not a.BoundBox.intersect(b.BoundBox):
                continue
            testes_tubes += 1
            try:
                common = a.common(b)
            except Exception as error:
                erreurs_tubes.append(dict(objet_a='Part__Feature' + str(n),
                                           objet_b='Part__Feature' + str(m), erreur=str(error)))
                continue
            if common.Volume > 1e-6:
                entre_tubes.append(dict(objet_a='Part__Feature' + str(n),
                                        objet_b='Part__Feature' + str(m),
                                        volume_commun_mm3=common.Volume))

    if sha(NATIF) != avant:
        raise ValueError('Natif modifié pendant le contrôle')
    resultat = dict(
        schema_version=1, date='2026-10-26', statut='Implémenté',
        qualification='À valider',
        protocole='Feuilles actives du natif OEM avec application de la matrice '
                  'globale et contrôle du centre de volume : six formes par bras contre '
                  'les feuilles de ce bras, filtre boîtes englobantes, '
                  'intersection BRep Shape.common, seuil strict > 1e-6 mm³.',
        commande='"C:/Program Files/FreeCAD 1.1/bin/python.exe" '
                 'hardware/mecanique/cartographe/verification/orch_verifier_interferences_oem.py',
        script_sha256=sha(Path(__file__)), natif=str(NATIF.relative_to(ROOT)).replace('\\', '/'),
        natif_sha256=avant, proposition=str(PROPOSITION.relative_to(ROOT)).replace('\\', '/'),
        proposition_sha256=sha(PROPOSITION),
        extraction_sha256=sha(EXTRACTION),
        densites_sha256=sha(DENSITES),
        groupes=groupes, nombre_paires=sum(x['paires_apres_filtre'] for x in groupes),
        nombre_intersections=len(hits), intersections=hits, erreurs=erreurs,
        reprises_repere_local=reprises_repere_local,
        candidats=dict(nombre=len(candidats), paires_possibles=len(candidats)*(len(candidats)-1)//2,
                       paires_apres_filtre=testes_candidats,
                       intersections=entre_candidats, erreurs=erreurs_candidats),
        candidats_contre_tubes=dict(nombre_tubes=len(tubes),
                       paires_possibles=len(candidats)*len(tubes),
                       paires_apres_filtre=testes_tubes,
                       intersections=entre_tubes, erreurs=erreurs_tubes),
        conclusion='Intersections positives constatées sur les éléments exclus et '
                   'sur certains éléments candidats ; leur caractère voulu reste à établir. '
                   'Les contacts sans volume et la qualification physique ne sont pas évalués.',
        finalisation_correcte=not erreurs and not erreurs_candidats and not erreurs_tubes)
    SORTIE.write_text(json.dumps(resultat, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(paires=resultat['nombre_paires'], intersections=len(hits),
                          candidat_intersections=len(entre_candidats),
                          tube_intersections=len(entre_tubes), erreurs_tubes=len(erreurs_tubes),
                          erreurs=len(erreurs), erreurs_candidats=len(erreurs_candidats),
                          preuve=str(SORTIE), preuve_sha256=sha(SORTIE)),
                     ensure_ascii=False), flush=True)


try:
    run()
except Exception as error:
    import traceback
    traceback.print_exc()
    print('ÉCHEC : ' + str(error), file=sys.stderr, flush=True)
    os._exit(1)
os._exit(0)
