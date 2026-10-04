"""Infrastructure : affecter les choix d'empreintes CA01 sans modifier les fils.

Les deux inventaires JSON sont les entrées déclaratives. Les connecteurs
physiques remplacent les exclusions BOM/PCB des anciens connecteurs logiques.
Les états DNP et les brochages restent inchangés.
"""
import json
from pathlib import Path
import re

CARD = Path(__file__).resolve().parents[1]


def children(text):
    nodes, depth, quote, escape, start = [], 0, False, False, None
    for i, char in enumerate(text):
        if quote:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                quote = False
        elif char == '"':
            quote = True
        elif char == '(':
            depth += 1
            if depth == 2:
                start = i
        elif char == ')':
            if depth == 2:
                nodes.append((start, i + 1, text[start:i + 1]))
            depth -= 1
    return nodes


def q(value):
    return json.dumps(value, ensure_ascii=False)


def set_property(node, name, value):
    pattern = r'(\(property "' + re.escape(name) + r'" )"(?:\\.|[^"\\])*"'
    if re.search(pattern, node):
        return re.sub(pattern, lambda m: m[1] + q(value), node, count=1)
    xy = re.search(r'\(at ([\d.\-]+) ([\d.\-]+)', node)
    prop = f'\n\t\t(property {q(name)} {q(value)} (at {xy[1]} {xy[2]} 0) (effects (font (size 1.27 1.27)) hide))\n'
    return node[:-1] + prop + ')'


def run():
    connectors = json.loads((CARD / 'empreintes_connecteurs.json').read_text(encoding='utf-8-sig'))['connectors']
    parts = json.loads((CARD / 'empreintes_composants.json').read_text(encoding='utf-8-sig'))['parts']
    mapping = {x['ref']: x for x in connectors + parts}
    radio = json.loads((CARD / 'empreinte_rp4td.json').read_text(encoding='utf-8-sig'))
    if not radio.get('board_only', True):
        mapping[radio['reference']] = {'ref':radio['reference'], 'footprint':radio['footprint'],
                                     'source':radio['sources'][0]['url']}
    seen = set()
    for file in sorted(CARD.glob('*.kicad_sch')):
        original = file.read_text(encoding='utf-8-sig')
        text = original
        for start, end, node in reversed(children(original)):
            if not re.match(r'\(symbol\s', node):
                continue
            ref = re.search(r'\(property "Reference" "([^"]+)"', node)
            if not ref or ref[1] not in mapping:
                continue
            ref = ref[1]
            choice = mapping[ref]
            node = set_property(node, 'Footprint', choice['footprint'])
            if choice.get('mpn'):
                node = set_property(node, 'MPN', choice['mpn'])
            inherited = mapping.get(choice.get('same_pattern_as', ''), {})
            source = choice.get('source', inherited.get('source', ''))
            source = source[0] if isinstance(source, list) else source
            if source.startswith('https://'):
                node = set_property(node, 'Datasheet', source)
            if ref.startswith('J') and ref not in ('J501', 'JP501'):
                node = node.replace('(in_bom no)', '(in_bom yes)').replace('(on_board no)', '(on_board yes)')
            if ref.startswith('TP'):
                node = node.replace('(in_bom yes)', '(in_bom no)')
            text = text[:start] + node + text[end:]
            seen.add(ref)
        if text != original:
            file.write_text(text, encoding='utf-8')
    if seen != set(mapping):
        raise RuntimeError('Références non affectées : ' + str(set(mapping) - seen))
    path = CARD / 'bom_candidate.json'
    bom = json.loads(path.read_text(encoding='utf-8-sig'))
    bom['date'] = '2026-10-01'
    for part in bom['parts']:
        ref = part['ref']
        if ref not in mapping:
            continue
        choice = mapping[ref]
        part['footprint'] = choice['footprint']
        if choice.get('mpn'):
            part['mpn'] = choice['mpn']
        inherited = mapping.get(choice.get('same_pattern_as', ''), {})
        source = choice.get('source', inherited.get('source', ''))
        url = source[0] if isinstance(source, list) else source
        if url.startswith('https://'):
            part['datasheet'] = url
        elif not url.startswith('http') and part.get('datasheet', '').startswith('Bibliothèque'):
            part['datasheet'] = ''
        part['mechanical_selection'] = ('empreinte_rp4td.json' if ref == radio['reference'] else
                                      'empreintes_connecteurs.json' if ref in {x['ref'] for x in connectors} else 'empreintes_composants.json')
        part['status'] = 'À valider'
        part['limit'] = 'Empreinte affectée pour préplacement ; consulter l’inventaire mécanique pour sources, pinmap et limites. Qualification électrique et montage ouverts.'
        if ref == radio['reference']:
            part['limit'] = 'Montage direct Planifié : enveloppe de préplacement sans les quatre pads physiques à coter ; non soudable et non fabricable.'
        if ref.startswith('J') and ref not in ('J501', 'JP501'):
            part['excluded_from_manufacturing'] = False
        if ref.startswith('TP'):
            part['excluded_from_manufacturing'] = True
            part['limit'] = 'Pastille de test sans composant à commander ; accès sonde dans la stack à vérifier.'
    path.write_text(json.dumps(bom, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'affected_references': sorted(seen), 'connections_changed': False}, ensure_ascii=False))


if __name__ == '__main__':
    run()
