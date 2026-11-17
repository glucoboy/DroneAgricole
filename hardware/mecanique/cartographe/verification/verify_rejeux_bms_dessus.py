"""Vérification négative : les recettes historiques ne remplacent pas la rehausse."""
from garde_hierarchie_batterie import require_monolithic_layout
require_monolithic_layout('verify_rejeux_bms_dessus.py')
from etage_batterie_helpers import ROOT,MEC,VER
import runpy,json,hashlib
recipes=['build_stack_revue_20261003.py','build_rehausse20_avionique_20261002.py','update_docs_bms.py']
files=list(json.loads((VER/'controle_bms_cassette.json').read_text(encoding='utf-8'))['sources_sha256'])
files+=['docs/architecture/'+n for n in ['HLD.md','ARCHITECTURE_MECANIQUE.md','ARCHITECTURE_ELECTRIQUE_RESEAUX.md','ARCHITECTURE_LOGICIELLE.md']]+['docs/VALIDATION_QUALIFICATION.md']
def hashes():return {f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in files}
before=hashes();rows=[]
for name in recipes:
 try:runpy.run_path(str(VER/name),run_name='__main__')
 except RuntimeError as ex:
  assert 'historique' in str(ex) and 'BMS' in str(ex),str(ex)
  rows.append(dict(recette=name,rejeu_refuse=True,motif=str(ex)))
 else:raise AssertionError('La recette historique n’a pas été arrêtée : '+name)
assert hashes()==before
proof=dict(date='2026-10-05',recettes=rows,natifs_inchanges=True,sources_sha256=before,finalisation_correcte=True)
(VER/'controle_rejeux_bms_dessus.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('Trois rejeux historiques refusés avant mutation ; natifs et docs inchangés')
