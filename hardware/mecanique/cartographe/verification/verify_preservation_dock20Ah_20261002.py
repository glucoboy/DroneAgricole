"""Contrôle de conservation des natifs antérieurs et des câblages préexistants."""
from pathlib import Path
import json,hashlib
ROOT=Path(__file__).resolve().parents[4]
MEC=ROOT/'hardware/mecanique/cartographe'
BASE=ROOT/'.runtime/cassette20Ah_20261002/avant'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
initial=json.loads((BASE/'empreintes_natifs.json').read_text(encoding='utf-8-sig'))
rows=[]
for row in initial:
    p=Path(row['Path']);before=row['Hash'].lower()
    now=sha(p) if p.exists() else None
    rows.append({'fichier':str(p.relative_to(ROOT)).replace('\\','/'),
        'sha256_avant':before,'sha256_apres':now,'inchange':now==before})
for f in ['hardware/electronique/cartographe/cablage_global.json',
          'hardware/electronique/cartographe/cablage_global.mmd']:
    p=ROOT/f;original=BASE/f.replace('/','__')
    rows.append({'fichier':f,'sha256_avant':sha(original),'sha256_apres':sha(p),
        'inchange':sha(original)==sha(p)})
report={'date_utc':'2026-10-02','controle':'Conservation exacte des fichiers antérieurs au dock20Ah',
    'references':rows,'tous_inchanges':all(r['inchange'] for r in rows),
    'limite':'Natifs et deux câblages globaux selon instantané initial ; documentation et manifeste volontairement actualisés.'}
p=MEC/'verification/preservation_dock20Ah_20261002.json'
p.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'fichiers':len(rows),'inchanges':report['tous_inchanges'],
    'anomalies':[r['fichier'] for r in rows if not r['inchange']]}))
assert report['tous_inchanges']
