"""Contrôle d'infrastructure : conservation électrique et conventions graphiques CA01."""
import re
import hashlib
import json
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE / 'netlist_avant_reprise_energie_power_20261001.xml'
CURRENT = HERE / 'netlist.xml'
before = ET.parse(BASE).getroot()
after = ET.parse(CURRENT).getroot()


def components(tree):
    return {c.attrib['ref']: c for c in tree.findall('./components/comp')}


def pin_groups(tree):
    return {frozenset((node.attrib['ref'], node.attrib['pin'])
                     for node in net.findall('node'))
            for net in tree.findall('./nets/net')}


def electrical_fields(component):
    return (component.findtext('value'), component.findtext('footprint'),
            component.findtext('datasheet'), component.findtext('tstamps'),
            sorted((f.attrib['name'], f.text or '')
                   for f in component.findall('./fields/field')),
            sorted((p.attrib['name'], p.attrib.get('value', ''))
                   for p in component.findall('property')))


old, new = components(before), components(after)
old_groups, new_groups = pin_groups(before), pin_groups(after)
changed = sorted(ref for ref in old.keys() & new.keys()
                 if electrical_fields(old[ref]) != electrical_fields(new[ref]))
rail_names={'GND','VBAT_PAYLOAD','VIN_PAYLOAD_PROT','5V_AUX','5V_RADIO','12V_COMPUTE','12V_LIDAR','5V_SYNC','3V3_SYNC','3V3_ORIN_IO_REF','5V_AIRY_IO'}
rail_labels=[]; symbols=[]
for sheet in sorted(HERE.parent.glob('*.kicad_sch')):
    source=sheet.read_text(encoding='utf-8-sig')
    rail_labels.extend((sheet.name,n) for n in re.findall(r'\((?:global_label|label) \"([^\"]+)\"',source) if n in rail_names)
    symbols.extend((sheet.name,m.group(1),float(m.group(4))) for m in re.finditer(r'\(lib_id \"(power:GND|CA01_Fonctions:Alimentation_Barre)\"\)\s*\(at ([-+0-9.]+) ([-+0-9.]+) ([-+0-9.]+)\)',source))
checks = [
    {'id': 'all_components_preserved', 'passed': old.keys() == new.keys(),
     'count': len(new)},
    {'id': 'all_pin_groups_identical', 'passed': old_groups == new_groups,
     'count': len(new_groups),
     'removed': [sorted(group) for group in old_groups - new_groups],
     'added': [sorted(group) for group in new_groups - old_groups]},
    {'id': 'all_electrical_fields_and_identities_preserved',
     'passed': not changed, 'modified': changed},
]
checks.extend([{'id':'rail_labels_replaced','passed':not rail_labels,'remaining':rail_labels},
               {'id':'power_symbols_upright','passed':bool(symbols) and all(angle==0 for _,_,angle in symbols),'count':len(symbols)}])
proof = {
    'schema_version': 1,
    'date_utc': datetime.now(timezone.utc).isoformat(),
    'scope': 'Reprise graphique page 2 et symboles alimentation/GND ; comparaison des six feuilles CA01',
    'platform': 'Windows amd64 ; KiCad 10.0.6',
    'checks': checks,
    'passed': all(check['passed'] for check in checks),
    'inputs': [{'file': path.name,
                'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
               for path in (BASE, CURRENT, HERE.parent/'01_energie_pm.kicad_sch', HERE.parent/'CA01_Design.kicad_sym', HERE.parent/'CA01_Fonctions.kicad_sym')],
    'allowed_graphical_changes': [
        'Positions et orientations des symboles, fils et textes ; U102 agrandi sans modification du brochage',
        'Labels de rails remplacés par symboles power global ; GND standard, alimentations à barre orientée vers le haut',
    ],
    'visual_recipe': 'Exporter le PDF avec KiCad puis inspecter la page 2 et toutes les feuilles affectées ; ce contrôle graphique est manuel',
    'hardware_tests_executed': False,
    'qualification': 'À valider',
    'limits': ['Comparaison statique des broches et champs électriques ; aucun essai matériel ni simulation électrique'],
}
(HERE / 'reprise_energie_power_20261001.json').write_text(
    json.dumps(proof, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(f"{sum(check['passed'] for check in checks)}/{len(checks)} contrôles de conservation conformes")
if not proof['passed']:
    raise SystemExit(1)
