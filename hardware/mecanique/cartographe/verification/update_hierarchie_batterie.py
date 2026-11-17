"""Séparer batterie/récepteur et promouvoir les équipements dans le principal."""
from hierarchie_batterie_helpers import *
from etage_batterie_helpers import save_native, meta


def copy_link(doc, root, source, name, pose=None):
    o = doc.addObject('App::Link', name)
    root.addObject(o)
    o.setLink(source.LinkedObject)
    o.LinkTransform = source.LinkTransform
    o.LinkPlacement = pose or source.LinkPlacement
    o.Label = source.Label
    for p in source.PropertiesList:
        if p not in o.PropertiesList and not p.startswith('_'):
            kind = source.getTypeIdOfProperty(p)
            assert kind.startswith('App::Property') and 'Link' not in kind, (source.Name, p)
            o.addProperty(kind, p)
            setattr(o, p, getattr(source, p))
    o.ViewObject.OverrideMaterial = source.ViewObject.OverrideMaterial
    for p in ('ShapeMaterial','MaterialList','OverrideColorList','OverrideMaterialList',
              'DrawStyle','LineWidth','PointSize'):
        setattr(o.ViewObject,p,getattr(source.ViewObject,p))
    o.Visibility = source.Visibility
    return o


def main():
    top = A.openDocument(str(TOP))
    if getattr(top.IntegrationRevue, 'DecoupageFonctionnel', '') == MARKER:
        check_tree(top)
        print('Hiérarchie déjà installée ; aucune sauvegarde. Relancer verify_hierarchie_batterie.py.')
        return
    dock = top.SA02A_Dock20Ah.LinkedObject.Document
    dist = top.SA07_Distribution_Systeme_Candidat.LinkedObject.Document
    bat = next((d for d in A.listDocuments().values() if Path(d.FileName)==BAT), None) or A.openDocument(str(BAT))
    recompute_all()
    prior = read(VER/'controle_bms_cassette.json')
    assert prior['finalisation_correcte']
    for filename, digest in prior['sources_sha256'].items():
        assert sha(ROOT/filename) == digest, ('Source modifiée depuis contrôle précédent', filename)
    before = affected(top)
    assert len(before) == 149
    mobile = [o for o in links(dock.Ensemble) if getattr(o, 'Mobile', 'non') == 'oui']
    fixed = [o for o in links(dock.Ensemble) if o not in mobile]
    assert len(mobile) == 67 and len(fixed) == 72
    source_before = native_sources()
    proof = dict(date='2026-10-05', reference_git='396c64e7dca75ff46a293334361ecdbbd5bc2956',
                 recette_sha256=sha(__file__), sources_avant_sha256=source_before,
                 occurrences_avant=before, enveloppe_principal_avant=bbox(top.IntegrationRevue.Shape),
                 preuves_geometrie_anterieures_sha256={name:sha(VER/name) for name in
                     ['controle_bms_cassette.json','controle_faisceau_natif_bms.json','controle_routes_systeme_courant.json']},
                 finalisation_correcte=False, qualification='À valider')
    dump(VER/'decoupage_sous_assemblages_batterie.json', proof)
    assert identity(bat.Reference.Placement)
    for o in list(bat.Objects):
        if o.TypeId == 'App::Link':
            bat.removeObject(o.Name)
    extraction = A.Units.Quantity(str(dock.Parametres.ExtractionX)).Value
    bat.Parametres.set(bat.Parametres.getCellFromAlias('ExtractionX'), str(extraction)+' mm')
    migration = []
    for src in mobile:
        name = src.Name[5:] if src.Name.startswith('Cass_') else src.Name
        dst = copy_link(bat, bat.Reference, src, name)
        for path, expression in src.ExpressionEngine:
            assert 'Parametres.ExtractionX' in expression, (src.Name, expression)
            dst.setExpression(path, expression)
        migration.append(dict(ancien_parent=rel(REC), ancien_nom=src.Name,
                              nouveau_parent=rel(BAT), nouveau_nom=dst.Name))
    for src in mobile:
        dock.removeObject(src.Name)
    for o in fixed:
        meta(o, 'Mobile', 'non')
    battery_occ = top.addObject('App::Link', 'SA02_Cassette20Ah_Coulissante')
    top.IntegrationRevue.addObject(battery_occ)
    battery_occ.setLink(bat.Reference)
    battery_occ.LinkTransform = False
    battery_occ.LinkPlacement = top.SA02A_Dock20Ah.LinkPlacement
    battery_occ.ViewObject.OverrideMaterial = False
    battery_occ.Visibility = True
    dist_pose = top.SA07_Distribution_Systeme_Candidat.LinkPlacement
    assert identity(dist.Reference.Placement)
    for name in DIRECT:
        src = dist.getObject(name)
        copy_link(top, top.IntegrationRevue, src, name, dist_pose.multiply(src.LinkPlacement))
    top.removeObject('SA07_Distribution_Systeme_Candidat')
    bat.Reference.Label = battery_occ.Label = 'Batterie 20 Ah'
    dock.Ensemble.Label = top.SA02A_Dock20Ah.Label = 'Récepteur de batterie 20 Ah'
    top.IntegrationRevue.Label = 'Assemblage principal Cartographe'
    for r, role in [(bat.Reference,'Batterie mobile'), (dock.Ensemble,'Récepteur fixe'),
                    (top.IntegrationRevue,'Principal, équipements directs')]:
        meta(r, 'DecoupageFonctionnel', MARKER)
        meta(r, 'RoleFonctionnel', role)
        meta(r, 'Etat', 'Implémenté en CAO ; physique À valider')
    meta(dock.Ensemble, 'BMSIntegre', 'BMS embarqué dans SA02_Cassette20Ah_Coulissante ; récepteur fixe uniquement')
    meta(top.IntegrationRevue, 'Configuration', 'Batterie et récepteur séparés ; JETI, PM08, distribution, plateau et accessoires directement assemblés dans le principal. Géométries et poses conservées.')
    meta(bat.Reference, 'BMSIntegre', 'BMS au-dessus du pack ; raccord TE compact conservé')
    meta(bat.Reference, 'ExtractionPilote', 'Parametres.ExtractionX ; appliquée une seule fois aux 67 pièces mobiles')
    recompute_all()
    checks = check_tree(top)
    after = affected(top)
    assert signature(before) == signature(after), 'Référence ou pose mondiale modifiée'
    assert appearance_signature(before) == appearance_signature(after), 'Apparence modifiée'
    for d in [bat, dock, top]:
        save_native(d)
    source_after = native_sources()
    changed = [p for p,h in source_before.items() if sha(ROOT/p) != h]
    assert set(changed) == {rel(BAT),rel(REC),rel(TOP)}, changed
    assert sha(DIST) == source_before[rel(DIST)]
    proof.update(migration=migration, occurrences_apres=after, controle_arbre=checks,
                 sources_apres_sha256=source_after, natifs_modifies=changed,
                 pieces_et_faisceau_sources_inchanges=True, poses_monde_conservees=True,
                 sauvegarde_native_terminee=True,
                 limites=['Séparation de parentage CAO ; aucune nouvelle qualification matérielle',
                          'Les contrôles géométriques antérieurs restent liés à leurs anciennes empreintes ; transfert par identité des références et poses'],
                 finalisation_correcte=False)
    dump(VER/'decoupage_sous_assemblages_batterie.json', proof)
    print(json.dumps(checks,ensure_ascii=False),flush=True)


if __name__ == '__main__':
    main()
