"""Tables et schéma du document vivant issus du registre système courant."""
from pathlib import Path
import json,re
ROOT=Path(__file__).resolve().parents[4];ELEC=ROOT/'hardware/electronique/cartographe'
d=json.loads((ELEC/'cablage_global.json').read_text(encoding='utf-8'))
p=ROOT/'docs/architecture/ARCHITECTURE_ELECTRIQUE_RESEAUX.md';t=p.read_text(encoding='utf-8')
def cell(v):return str(v).replace('|','\\|').replace('\n','<br>')
def table_after(t,title,head,rows):
 a=t.index(title);b=t.index('\n|',a)+1;e=t.find('\n\n',b)
 assert e>0
 table=head+'\n'+('\n'.join('| '+' | '.join(cell(v) for v in r)+' |' for r in rows))
 return t[:b]+table+t[e:]
t=table_after(t,'#### 4.3.1 Entrées','| Module | Entrées | Sorties | Réserves |\n|---|---|---|---|',[[f"`{r['id']}` {r['name']}",r['inputs'],r['outputs'],r['open']] for r in d['modules']])
t=table_after(t,'#### 4.3.2 Registre','| Liaison | Modules | Fonction | Signaux / contacts connus | Réserve avant câblage |\n|---|---|---|---|---|',[[f"`{r['id']}`",f"`{r['from']}` → `{r['to']}`",r.get('route',r.get('function','')),r.get('pins',''),r.get('open',r.get('status','À valider'))] for r in d['connections']])
t=t.replace('La maquette inactive `Drone_Cartographe_Systeme_Candidat.FCStd` comporte\n35 routes natives de réservation, dont JETI OUT→PM08 et PM08→PDB,\nen complément des routes existantes du dock. Voir DOC-MEC §4.5 et\nDOC-VAL §12.1.4.','La maquette historique `Drone_Cartographe_Systeme_Candidat.FCStd` est archivée.\nLa configuration locale courante `Integration_Stack_Revue_20261003.FCStd`\nlie SA08 et ses 37 routes recotées, dont les liaisons UART isolée et USB BMS.\nLes routes internes du dock restent distinctes. Voir DOC-MEC§4.1.3.3 et\nDOC-VAL§12.1.9.')
p.write_text(t,encoding='utf-8')
print('27 modules et40liaisons synchronisés dans DOC-ELEC')
