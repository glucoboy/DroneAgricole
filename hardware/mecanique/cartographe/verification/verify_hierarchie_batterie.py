"""Réouverture native, conservation des pièces et extraction de la batterie seule."""
from hierarchie_batterie_helpers import *
from etage_batterie_helpers import G

def main():
    proof = read(VER/'decoupage_sous_assemblages_batterie.json')
    assert proof['sauvegarde_native_terminee']
    top = A.openDocument(str(TOP))
    recompute_all()
    checks = check_tree(top)
    current = affected(top)
    assert signature(current) == signature(proof['occurrences_avant'])
    assert appearance_signature(current) == appearance_signature(proof['occurrences_avant'])
    for p,h in proof['sources_avant_sha256'].items():
        if p not in proof['natifs_modifies']:
            assert sha(ROOT/p) == h, p
    for p,h in proof['sources_apres_sha256'].items():
        assert sha(ROOT/p) == h, p
    for p,h in proof['preuves_geometrie_anterieures_sha256'].items():
        assert sha(VER/p) == h, p
    envelope = bbox(top.IntegrationRevue.Shape)
    assert max(abs(a-b) for a,b in zip(envelope,proof['enveloppe_principal_avant'])) < 1e-6
    battery = top.SA02_Cassette20Ah_Coulissante.LinkedObject.Document
    cell = battery.Parametres.getCellFromAlias('ExtractionX')
    initial = A.Units.Quantity(str(battery.Parametres.ExtractionX)).Value
    frozen = native_sources()
    scenarios = []
    for amount in (0,50,500):
        battery.Parametres.set(cell, str(amount)+' mm')
        battery.recompute(); top.recompute()
        expected = []
        delta = top.SA02_Cassette20Ah_Coulissante.LinkPlacement.Rotation.multVec(A.Vector(amount-initial,0,0))
        for r in current:
            q = dict(r, matrice_monde=list(r['matrice_monde']))
            if r['parent'] == rel(BAT):
                for idx,value in zip((3,7,11),(delta.x,delta.y,delta.z)):
                    q['matrice_monde'][idx] += value
            expected.append(q)
        assert signature(affected(top)) == signature(expected), amount
        checks_now = check_tree(top)
        scenarios.append(dict(extraction_mm=amount, mobiles_deplaces_une_fois=67,
                              recepteur_fixe=72, pieces_directes_fixes=6, routes_fixes=37,
                              liens_resolus=not checks_now['liens_non_resolus']))
    battery.Parametres.set(cell,str(initial)+' mm'); battery.recompute(); top.recompute()
    assert native_sources() == frozen, 'Le contrôle ne doit pas sauvegarder les natifs'
    result = dict(date='2026-10-05', controle_arbre=checks, enveloppe_principal=envelope,
                  occurrences_conservees=149, references_et_poses_identiques=True,
                  apparences_conservees=True, extraction=scenarios, sources_sha256=frozen,
                  preuves_anterieures_inchangees=True, natifs_non_modifies=True,
                  qualification='À valider', finalisation_correcte=True)
    dump(VER/'controle_hierarchie_batterie.json',result)
    proof.update(controle_frais='controle_hierarchie_batterie.json',
                 controle_frais_sha256=sha(VER/'controle_hierarchie_batterie.json'),
                 extraction_verifiee=scenarios, apparences_conservees=True,
                 sources_reouvertes_sha256=frozen, finalisation_correcte=True)
    dump(VER/'decoupage_sous_assemblages_batterie.json',proof)
    print(json.dumps(result,ensure_ascii=False),flush=True)

if __name__ == '__main__':
    main()
