"""Infrastructure : plan d'archivage miroir, aucune modification des natifs."""
from pathlib import Path
import hashlib
import json
import zipfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[4]
MEC = ROOT / 'hardware/mecanique/cartographe'
VER = MEC / 'verification'
ARCHIVE = MEC / 'archives/avant_tri_20261004'
KEEP = [
    'SA01_Chassis_Stack_Revue_20261003', 'SA02A_Dock20Ah',
    'SA03_CA01_Holybro_Revue_20261003', 'SA05_Capteurs_Isoles',
    'SA05A_Bloc_capteurs', 'SA05B_Appui_Sorbothane',
    'SA06_RTK_Helical_Systeme_Candidat', 'SA07_Distribution_Systeme_Candidat',
    'SA07_Station_sol', 'SA08_Faisceau_Systeme_Candidat',
    'SA02_Cassette20Ah_Coulissante', 'SA02_Contacts20Ah',
]
ASSEMBLY = 'Integration_Stack_Revue_20261003'

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def relative(p):
    return str(p.relative_to(MEC)).replace('\\', '/')

def xml(p):
    with zipfile.ZipFile(p) as z:
        return ET.fromstring(z.read('Document.xml'))

native = sorted(list((MEC / 'pieces').rglob('*.FCStd')) +
                list((MEC / 'sous_assemblages').glob('*.FCStd')) +
                list((MEC / 'assemblages').glob('*.FCStd')))
objects = {p.resolve(): {o.get('name') for o in xml(p).findall('./Objects/Object')}
           for p in native}
links, missing_before = [], []
for p in native:
    for x in xml(p).findall('.//XLink'):
        if not x.get('file'):
            continue
        source = (p.parent / x.get('file')).resolve()
        assert source.is_relative_to(MEC.resolve()), (p, source)
        row = {'owner': relative(p), 'source': relative(source), 'objet': x.get('name')}
        links.append(row)
        if source not in objects or x.get('name') not in objects[source]:
            missing_before.append(row)
operations = []
for p in native:
    obsolete = (p.parent.name == 'sous_assemblages' and p.stem not in KEEP or
                p.parent.name == 'assemblages' and p.stem != ASSEMBLY)
    operations.append({'operation': 'move' if obsolete else 'copy',
                       'source': str(p.resolve()), 'destination': str((ARCHIVE / relative(p)).resolve()),
                       'fichier': relative(p), 'sha256': sha(p)})
for folder in ['sous_assemblages', 'assemblages']:
    for p in sorted((MEC / folder).glob('*.FCBak')):
        operations.append({'operation': 'move', 'source': str(p.resolve()),
                           'destination': str((ARCHIVE / relative(p)).resolve()),
                           'fichier': relative(p), 'sha256': sha(p)})
for name in ['manifest.json', 'README.md', 'configuration_cible_20261003.json']:
    p = MEC / name
    operations.append({'operation': 'copy', 'source': str(p.resolve()),
                       'destination': str((ARCHIVE / name).resolve()),
                       'fichier': name, 'sha256': sha(p)})
for row in operations:
    assert not Path(row['destination']).exists(), 'Archive existe déjà : ' + row['destination']
data = {'date': '2026-10-04', 'racine': str(MEC.resolve()), 'archive': str(ARCHIVE.resolve()),
        'sous_assemblages_conserves': KEEP, 'assemblage_conserve': ASSEMBLY,
        'natifs_avant': len(native), 'liens_avant': links,
        'liens_objets_manquants_avant': missing_before, 'operations': operations,
        'principe': 'Miroir autonome à chemins relatifs identiques ; aucun natif réenregistré.'}
(VER / 'plan_tri_sous_assemblages_20261004.json').write_text(
    json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'natifs': len(native), 'sous_assemblages_courants': len(KEEP),
                  'deplacements': sum(r['operation'] == 'move' for r in operations),
                  'liens_objets_manquants_avant': missing_before}))
