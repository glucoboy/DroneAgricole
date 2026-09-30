"""Contrôle d'infrastructure : conservation électrique de la reprise radio."""
import hashlib
import json
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE / 'netlist_avant_reprise_radio_20260930.xml'
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
proof = {
    'schema_version': 1,
    'date_utc': datetime.now(timezone.utc).isoformat(),
    'scope': 'Reprise graphique de 04_radio, page 3 du PDF ; comparaison des six feuilles CA01',
    'platform': 'Windows amd64 ; KiCad 10.0.6',
    'checks': checks,
    'passed': all(check['passed'] for check in checks),
    'inputs': [{'file': path.name,
                'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
               for path in (BASE, CURRENT)],
    'allowed_graphical_changes': [
        'Positions et orientations des symboles, fils, labels et textes',
        'Symboles J401/J402 agrandis ; noms fonctionnels des broches affichés sans renumérotation',
    ],
    'visual_check': 'Page 3 du PDF exporté inspectée après correction des champs et espacements',
    'hardware_tests_executed': False,
    'qualification': 'À valider',
    'limits': ['Comparaison statique des broches et champs électriques ; aucun essai matériel ni simulation électrique'],
}
(HERE / 'reprise_radio_20260930.json').write_text(
    json.dumps(proof, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(f"{sum(check['passed'] for check in checks)}/{len(checks)} contrôles de conservation conformes")
if not proof['passed']:
    raise SystemExit(1)
