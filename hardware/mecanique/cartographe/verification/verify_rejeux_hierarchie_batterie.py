"""Les recettes monolithiques sont refusées avant mutation de la CAO ou des preuves."""
from pathlib import Path
import hashlib,json,runpy
ROOT=Path(__file__).resolve().parents[4]
VER=Path(__file__).resolve().parent

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

files=list(ROOT.glob('hardware/mecanique/cartographe/**/*.FCStd'))
files+=list(VER.glob('*.json'))
files+=list((ROOT/'docs').rglob('*.md'))
files+=list((ROOT/'hardware/electronique/cartographe').glob('*.json'))
files=[p for p in files if p.name!='controle_rejeux_hierarchie_batterie.json']
before={str(p.relative_to(ROOT)).replace('\\','/'):sha(p) for p in files}
recipes=['build_stack_revue_20261003.py','build_rehausse20_avionique_20261002.py',
         'update_docs_bms.py','build_dock20Ah_20261003.py','build_systeme_faisceau_candidat_20261003.py',
         'update_compacite_dock20Ah.py','update_raccordement_direct_batterie.py',
         'update_faisceau_etage_batterie.py','update_distribution_etage_batterie.py',
         'update_bms_cassette.py','update_bms_dessus.py','integrate_faisceau_bms.py',
         'update_registres_bms.py','verify_bms_cassette.py','verify_registres_bms.py',
         'render_bms_cassette.py','verify_rejeux_bms_dessus.py','persist_etage_batterie.py',
         'update_registres_etage_batterie.py','finalize_etage_batterie.py',
         'recompute_supports_etage_batterie.py','finalize_couleurs_dock20Ah.py',
         'update_couleurs_dock20Ah.py','finalize_compactage_bms_te.py']
rows=[]
for name in recipes:
    try:
        runpy.run_path(str(VER/name),run_name='__main__')
    except RuntimeError as ex:
        assert 'historique' in str(ex) and 'update_hierarchie_batterie.py' in str(ex),str(ex)
        rows.append(dict(recette=name,rejeu_refuse_avant_mutation=True,motif=str(ex)))
    else:
        raise AssertionError('Recette non arrêtée : '+name)
assert all(sha(ROOT/p)==h for p,h in before.items())
(VER/'controle_rejeux_hierarchie_batterie.json').write_text(json.dumps(dict(date='2026-10-05',
    recettes=rows,sources_sha256=before,natifs_docs_registres_et_preuves_inchanges=True,
    finalisation_correcte=True),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(str(len(rows))+' recettes historiques arrêtées avant mutation',flush=True)
