"""Synchroniser les registres après séparation batterie/récepteur, sans sauvegarde CAO.

Exécuter uniquement après stabilisation des natifs. Les preuves géométriques
antérieures restent inchangées. --check prépare et vérifie sans écrire.
"""
from pathlib import Path
from collections import Counter
from datetime import datetime, timezone
import argparse
import hashlib
import json
import FreeCAD as A

ROOT = Path(__file__).resolve().parents[4]
MEC = ROOT / 'hardware/mecanique/cartographe'
VER = MEC / 'verification'
TOP = 'Integration_Stack_Revue_20261003'
BAT = 'SA02_Cassette20Ah_Coulissante'
REC = 'SA02A_Dock20Ah'
HAR = 'SA08_Faisceau_Systeme_Candidat'
OLD = 'SA07_Distribution_Systeme_Candidat'
DIRECT_REFS = {
    'EQ_PM08_CAN_Enveloppe_Systeme_Candidat',
    'EQ_Holybro_PDB18138_Systeme_Candidat',
    'P57_PlateauEnergieInferieur',
    'EQ_JetiMainSwitch100_PortsEtude20A',
    'EQ_JetiMagneticSwitch',
    'EQ_Waveshare15817_UART_Isole',
}
LABELS = {BAT: 'Batterie 20 Ah complète', REC: 'Récepteur de batterie 20 Ah',
          OLD: 'Distribution historique non installée', TOP: 'Assemblage principal'}


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def relative(path, base=MEC):
    return Path(path).resolve().relative_to(base.resolve()).as_posix()


def links(root):
    return [o for o in root.Group if o.TypeId == 'App::Link']


def matrix(placement):
    return list(placement.toMatrix().A)


def row_for(link, parent, parent_world, top_occurrence=None, installed=True):
    assert link.LinkedObject, 'Lien non résolu : ' + link.Name
    source = link.LinkedObject
    source_file = Path(source.Document.FileName)
    parent_file = Path(parent.Document.FileName)
    # App::Link n'expose pas getGlobalPlacement dans cette installation.
    # Les racines sont contrôlées identités ; composer explicitement les
    # placements natifs permet aussi de garder leur matrice auditable.
    world = parent_world.multiply(parent.Placement).multiply(link.LinkPlacement)
    return dict(assemblage=parent_file.stem, fichier_assemblage=relative(parent_file),
                parent_objet=parent.Name, parent_occurrence_principal=top_occurrence,
                occurrence=link.Name, reference=source_file.stem,
                source_fichier=relative(source_file), source_objet=source.Name,
                placement_matrice=matrix(link.LinkPlacement),
                placement_monde_matrice=matrix(world), LinkTransform=link.LinkTransform,
                mobile=getattr(link, 'Mobile', 'non') == 'oui',
                installe_dans_principal=installed, courant_catalogue=True,
                statut='À valider')


def pose_key(row):
    return row['reference'], tuple(round(float(x), 8) for x in
                                  row.get('placement_monde_matrice', row['placement_matrice']))


def catalogue_role(row):
    ref = row.get('reference') or row.get('nom') or Path(row.get('fichier', '')).stem
    if ref in LABELS:
        row['designation'] = LABELS[ref]
    if ref in (BAT, REC):
        row.update(role='batterie_mobile' if ref == BAT else 'recepteur_batterie_fixe',
                   installe_dans_principal=True, archive_conception=False,
                   verification='verification/hierarchie_batterie_recepteur.json')
    elif ref == OLD:
        row.update(role='historique_non_installe', installe_dans_principal=False,
                   archive_conception=False)
    elif ref == 'SA02_Contacts20Ah':
        row.update(role='construction', installe_dans_principal=False)
    elif ref == TOP:
        row.update(role='principal_batterie_recepteur_equipements_directs',
                   liens_directs=12, verification='verification/hierarchie_batterie_recepteur.json')
    path = MEC / row.get('fichier', '')
    if path.is_file():
        row['sha256'] = sha(path)


def main(check=False):
    # Lire avant d'ouvrir les natifs : ce registre est la référence des poses
    # précédentes. À la seconde exécution, les nouvelles matrices monde existent.
    manifest = read(MEC / 'manifest.json')
    nomenclature_before = read(VER / 'nomenclature_etage_batterie.json')
    baseline = [r for r in manifest['occurrences'] if
                r.get('assemblage') in (REC, OLD, HAR) and
                r.get('installe_dans_principal', True)]
    if any(r.get('assemblage') == BAT and r.get('installe_dans_principal')
           for r in manifest['occurrences']):
        baseline = [r for r in manifest['occurrences'] if
                    r.get('installe_dans_principal') and
                    (r.get('assemblage') in (BAT, REC, HAR) or
                     r.get('assemblage') == TOP and r.get('reference') in DIRECT_REFS)]
    assert len(baseline) == 182, ('Inventaire précédent incomplet', len(baseline))
    top = A.openDocument(str(MEC / 'assemblages' / (TOP + '.FCStd')))
    parent = top.getObject('IntegrationRevue')
    assert parent and len(links(parent)) == 12, 'Les 12 liens du principal ne sont pas prêts'
    identity = matrix(A.Placement())
    assert all(abs(a - b) < 1e-9 for a, b in zip(matrix(parent.Placement), identity))
    top_links = links(parent)
    source_stems = Counter(Path(o.LinkedObject.Document.FileName).stem for o in top_links)
    for ref in DIRECT_REFS | {BAT, REC, HAR}:
        assert source_stems[ref] == 1, 'Occurrence unique attendue : ' + ref
    assert source_stems[OLD] == 0 and source_stems['SA02_Contacts20Ah'] == 0
    top_rows = [row_for(o, parent, A.Placement()) for o in top_links]
    scoped = [r for r in top_rows if r['reference'] in DIRECT_REFS]
    roots = {}
    for ref, expected, mobile in [(BAT, 67, True), (REC, 72, False), (HAR, 37, False)]:
        occurrence = next(o for o in top_links if Path(o.LinkedObject.Document.FileName).stem == ref)
        root = occurrence.LinkedObject
        roots[ref] = root
        assert all(abs(a - b) < 1e-9 for a, b in zip(matrix(root.Placement), identity)), 'Racine non identité : ' + ref
        children = links(root)
        assert len(children) == expected, (ref, len(children), expected)
        if ref in (BAT, REC):
            assert all((getattr(o, 'Mobile', None) == 'oui') == mobile for o in children)
            assert all(hasattr(o, 'Mobile') for o in children), 'Flag explicite requis pour chaque pièce batterie/récepteur'
        scoped += [row_for(o, root, parent.Placement.multiply(occurrence.LinkPlacement), occurrence.Name) for o in children]
    assert len(scoped) == 182 and len({r['reference'] for r in scoped}) == 115
    assert Counter(map(pose_key, baseline)) == Counter(map(pose_key, scoped)), 'Référence ou pose mondiale changée'
    counts = dict(Counter(r['reference'] for r in scoped))
    assert counts == nomenclature_before['quantites'], 'Quantités changées par la restructuration'
    source_shas = {relative(MEC / r['source_fichier'], ROOT): sha(MEC / r['source_fichier']) for r in scoped}
    native_shas = {relative(top.FileName, ROOT): sha(top.FileName)}
    native_shas.update({relative(r.Document.FileName, ROOT): sha(r.Document.FileName) for r in roots.values()})
    before_shas = {relative(MEC / p, ROOT): sha(MEC / p) for p in
                   ['manifest.json', 'configuration_cible_20261003.json',
                    'verification/nomenclature_etage_batterie.json',
                    'verification/bom_dock20Ah_20261002.json',
                    'verification/faisceau_dock20Ah_20261002.json']}
    date = datetime.now(timezone.utc).date().isoformat()
    publication = {}
    refreshed_parents = {TOP, BAT, REC, HAR}
    manifest['occurrences'] = [r for r in manifest['occurrences'] if r.get('assemblage') not in refreshed_parents] + top_rows + [r for r in scoped if r['assemblage'] != TOP]
    for r in manifest['occurrences']:
        if r.get('assemblage') in (OLD, 'SA02_Contacts20Ah'):
            r['installe_dans_principal'] = False
            r['role'] = 'historique_non_installe' if r['assemblage'] == OLD else 'construction'
    for rows in [manifest['references'], manifest['assemblages'], manifest['catalogue_courant_20261004']['selection']]:
        for r in rows:
            catalogue_role(r)
    manifest['date_mise_a_jour'] = date
    hierarchy = dict(batterie='sous_assemblages/' + BAT + '.FCStd',
                     recepteur='sous_assemblages/' + REC + '.FCStd',
                     principal='assemblages/' + TOP + '.FCStd',
                     equipements_directs=sorted(DIRECT_REFS),
                     distribution_historique='sous_assemblages/' + OLD + '.FCStd',
                     occurrences_batterie=67, occurrences_recepteur=72,
                     equipements_directs_nombre=6, routes_SA08=37,
                     liens_principal=12, occurrences_perimetre=182, references_perimetre=115,
                     placements_monde_conserves=True,
                     verification='verification/hierarchie_batterie_recepteur.json',
                     statut='Implémenté en CAO ; physique À valider')
    manifest['hierarchie_batterie_recepteur'] = hierarchy
    cat = manifest['catalogue_courant_20261004']
    cat.update(sous_assemblages_courants=10, montages_construction=1,
               sous_assemblages_historiques_non_installes=1,
               equipements_directs_principal=6, liens_principal=12)
    evolution = manifest['configuration_dock20Ah']['evolution_courante']
    evolution.update(assemblage_batterie=hierarchy['batterie'], assemblage=hierarchy['recepteur'],
                     distribution_installee=False, distribution_role='historique non installé',
                     equipements_directs_principal=sorted(DIRECT_REFS), hierarchie=hierarchy['verification'])
    publication[MEC / 'manifest.json'] = manifest
    cfg = read(MEC / 'configuration_cible_20261003.json')
    cfg['date'] = date
    cfg['hierarchie_batterie_recepteur'] = hierarchy
    cfg['configuration']['tri_sous_assemblages'] = 'Batterie et récepteur séparés ; six équipements énergie directement dans le principal ; SA07 historique non installé'
    cfg['configuration']['limite_stack_revue'] = 'Deux assemblages batterie/récepteur, six équipements directs et SA08 ; références et poses conservées. Ports, fixations, masse et thermique À valider ; GNSS non implanté.'
    for r in cfg['bom']:
        if r.get('id') == 'DOCK20':
            r.update(designation='Batterie et récepteur 6S 20 Ah ; poste de synthèse documentaire',
                     fichier_CAO=None, fichiers_CAO=[hierarchy['batterie'], hierarchy['recepteur']],
                     statut_CAO='Implémenté dans le principal local ; physique À valider',
                     comptage='Poste de synthèse sans masse additionnelle ; décomposer par la BOM référencée. Les six équipements directs et SA08 y figurent aussi : ne pas les ajouter deux fois.',
                     reserves=['Châssis, stack et capteurs exclus des 182 liens de ce périmètre. Fixations et masse physique À valider.'])
        source_ref = Path(r.get('fichier_CAO') or '').stem
        if source_ref in DIRECT_REFS:
            r['assemblage_parent_CAO'] = hierarchy['principal']
            r['occurrence_CAO'] = next(o['occurrence'] for o in scoped if o['reference'] == source_ref)
    cfg['faisceau_hors_dock']['limites'] = [s.replace('35 routes natives', '37 routes natives')
                                           for s in cfg['faisceau_hors_dock']['limites']]
    publication[MEC / 'configuration_cible_20261003.json'] = cfg
    occ = [dict(assemblage=r['fichier_assemblage'], occurrence=r['occurrence'],
                parent_objet=r['parent_objet'], parent_occurrence_principal=r['parent_occurrence_principal'],
                reference=r['reference'], source_objet=r['source_objet'],
                fichier=relative(MEC / r['source_fichier'], ROOT),
                sha256=source_shas[relative(MEC / r['source_fichier'], ROOT)],
                placement_matrice=r['placement_matrice'], placement_monde_matrice=r['placement_monde_matrice'],
                LinkTransform=r['LinkTransform'], mobile=r['mobile']) for r in scoped]
    publication[VER / 'nomenclature_etage_batterie.json'] = dict(
        date=date, scope='Batterie 67 + récepteur 72 + équipements directs 6 + SA08 37 ; exclut châssis, stack et capteurs',
        statut='À valider', quantites=counts, occurrences=occ, hierarchie=hierarchy,
        finalisation_correcte=True)
    bom = read(VER / 'bom_dock20Ah_20261002.json')
    bom.update(date_utc=date, objet='Batterie, récepteur, équipements énergie directs et faisceau SA08',
               sources_sha256=source_shas, hierarchie=hierarchy)
    bom['assemblage_inventorie'].update(fichier=relative(top.FileName, ROOT), sha256=sha(top.FileName),
         racine=parent.Name, occurrences=counts, perimetre='182 liens de pièces sur quatre parents ; châssis, stack et capteurs exclus')
    for category in ['pieces_fabriquees', 'visserie_modelee', 'composants_commerce']:
        for r in bom[category]:
            ref = Path(r.get('fichier', '')).stem or r['reference']
            r['quantite_installee'] = counts.get(ref, 0)
            r['configuration_courante'] = 'active' if counts.get(ref) else 'historique non installée'
            r['parents_installes'] = dict(Counter(o['assemblage'] for o in occ if o['reference'] == ref))
            p = ROOT / r.get('fichier', '')
            if p.is_file():
                r['sha256'] = sha(p)
    publication[VER / 'bom_dock20Ah_20261002.json'] = bom
    harness = read(VER / 'faisceau_dock20Ah_20261002.json')
    harness.update(date_utc=date, sources_sha256=source_shas, hierarchie=hierarchy,
                   objet='Faisceau embarqué dans la batterie, sorties du récepteur et faisceau système ; chaîne électrique conservée')
    harness['cible_BMS_cassette'].update(position_candidate='Au-dessus du pack, sur P58 dans P43/P44 embarqués',
        CAO_actuelle='BMS dans assemblage batterie ; contacts pin et cordons sortants dans récepteur ; isolateur directement dans principal ; SA08 système')
    by_reference = {r['reference']: r for r in occ}
    for r in harness['routes_mobiles'] + harness['segment_fixe_TE_JETI']['routes']:
        native = by_reference[r['reference']]
        r.update(assemblage_parent=native['assemblage'], occurrence=native['occurrence'],
                 placement_monde_matrice=native['placement_monde_matrice'])
    harness['segment_fixe_TE_JETI']['assemblage_parent'] = hierarchy['recepteur']
    publication[VER / 'faisceau_dock20Ah_20261002.json'] = harness
    ignore = (ROOT / '.gitignore').read_text(encoding='utf-8')
    whitelist = set(native_shas) | {p for p in source_shas if (ROOT / p).stat().st_size < 1000000}
    additions = ['!/' + p for p in sorted(whitelist) if '!/' + p not in ignore.splitlines()]
    if additions:
        ignore = ignore.rstrip() + '\n\n# Hiérarchie batterie/récepteur : petits natifs conservés en place\n' + '\n'.join(additions) + '\n'
    # Tout le calcul et les assertions précèdent la première écriture.
    proof = dict(date_utc=datetime.now(timezone.utc).isoformat(), recette=relative(__file__, ROOT),
                 recette_sha256=sha(__file__), natifs_sha256=native_shas, sources_sha256=source_shas,
                 registres_avant_sha256=before_shas, hierarchie=hierarchy, occurrences=occ,
                 controle=dict(quantites_conservees=True, references_poses_monde_conservees=True,
                               aucun_double_installation=True, preuves_anciennes_preservees=True),
                 limites=['Contrôle de structure et de traçabilité uniquement ; géométrie/extraction dans les preuves dédiées.',
                          'Fixations, ports, câbles, fabrication et qualification physique restent À valider.'],
                 finalisation_correcte=True)
    if not check:
        for p, data in publication.items():
            p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        (ROOT / '.gitignore').write_text(ignore, encoding='utf-8')
        proof['registres_apres_sha256'] = {relative(p, ROOT): sha(p) for p in publication}
        (VER / 'hierarchie_batterie_recepteur.json').write_text(json.dumps(proof, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(check=check, occurrences=len(scoped), references=len(counts),
                         liens_principal=len(top_links), finalisation_correcte=True)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    main(parser.parse_args().check)
