"""Contrôle reproductible du préplacement mécanique CA01 sous KiCad.

Ne qualifie ni le routage, ni la fabrication, ni le montage réel. Le DRC doit
avoir été régénéré par kicad-cli avec --schematic-parity avant cette recette.
"""
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

import pcbnew as p
from build_placement import CARD, VERIFY, ORIGIN, box, intersects, write


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def groups(xml):
    return {frozenset((x.attrib['ref'], x.attrib['pin']) for x in n.findall('node'))
            for n in xml.findall('./nets/net')}


def normal(name):
    return name.replace('{slash}', '/')


def run():
    board_path = CARD / 'CA01_Avionique.kicad_pcb'
    board = p.LoadBoard(str(board_path))
    xml = ET.parse(VERIFY / 'netlist.xml')
    baseline_path = VERIFY / 'netlist_avant_empreintes_20261001.xml'
    before = ET.parse(baseline_path)
    config = read(CARD / 'placement_mecanique.json')
    fps = {f.GetReference(): f for f in board.GetFootprints()}
    components = {c.attrib['ref']: c for c in xml.findall('./components/comp')}
    problems = []
    if len(fps) != len(list(board.GetFootprints())):
        problems.append('Référence PCB dupliquée')
    modules = config.get('board_only_modules', {})
    radio_inventory = read(CARD/'empreinte_rp4td.json')
    if set(fps) != set(components) | {'H1','H2','H3','H4'} | set(modules):
        problems.append('Inventaire PCB incorrect')
    for ref, module in modules.items():
        fp = fps.get(ref)
        if fp is None:
            continue
        if not (fp.GetAttributes() & p.FP_BOARD_ONLY) or not fp.IsExcludedFromBOM() or not fp.IsExcludedFromPosFiles():
            problems.append('Attributs du module mécanique incorrects : ' + ref)
        if list(fp.Pads()):
            problems.append('Pads électriques non définis sur module mécanique : ' + ref)
        if fp.GetFPIDAsString() != module['footprint']:
            problems.append('Empreinte du module mécanique désynchronisée : ' + ref)
    aliases = config.get('schematic_ref_replacements', {})
    before_groups = {frozenset((aliases.get(ref, ref), pin) for ref, pin in group)
                     for group in groups(before)}
    if before_groups != groups(xml):
        problems.append('Topologie schématique modifiée')
    before_components = {aliases.get(c.attrib['ref'], c.attrib['ref']): c for c in before.findall('./components/comp')}
    for ref, comp in components.items():
        previous = before_components[ref].findtext('value')
        current = comp.findtext('value')
        declared = config.get('component_spec_updates', {}).get(ref, {})
        if current != previous and not (declared.get('before_value') == previous and declared.get('after_value') == current):
            problems.append('Valeur électrique modifiée sans déclaration : ' + ref)
        props = {x.attrib['name'] for x in comp.findall('property')}
        old_props = {x.attrib['name'] for x in before_components[ref].findall('property')}
        fp = fps[ref]
        if ('dnp' in props) != ('dnp' in old_props) or fp.IsDNP() != ('dnp' in props):
            problems.append('Etat DNP modifié : ' + ref)
        if fp.GetFPIDAsString() != comp.findtext('footprint'):
            problems.append('Empreinte désynchronisée : ' + ref)
        if fp.IsExcludedFromBOM() != ('exclude_from_bom' in props):
            problems.append('Exclusion BOM désynchronisée : ' + ref)
    expected = {(x.attrib['ref'], x.attrib['pin']): n.attrib['name']
                for n in xml.findall('./nets/net') for x in n.findall('node')}
    missing_electrical_pads = sorted(f'{ref}/{num}' for ref,num in expected
                                   if ref in fps and num not in {pad.GetNumber() for pad in fps[ref].Pads()})
    if missing_electrical_pads:
        problems.append('Pads électriques absents : ' + ', '.join(missing_electrical_pads))
    mechanical_pad_count = 0
    for ref, fp in fps.items():
        for pad in fp.Pads():
            num = pad.GetNumber()
            if num in ('', 'MP'):
                mechanical_pad_count += 1
                if pad.GetNetCode() != 0:
                    problems.append('Ancrage mécanique sous tension : ' + ref)
            elif ref in components:
                target = expected.get((ref, num), '')
                if normal(pad.GetNetname()) != target:
                    problems.append(f'Réseau pad incorrect : {ref}/{num}')
    if list(board.GetTracks()) or list(board.Zones()):
        problems.append('Cuivre de routage ajouté')
    bounds = {r: box(fp) for r, fp in fps.items()}
    overlaps = []
    keys = sorted(bounds)
    for i, ref in enumerate(keys):
        for other in keys[i+1:]:
            if intersects(bounds[ref], bounds[other], gap=0):
                overlaps.append([ref, other])
    if overlaps:
        problems.append('Courtyards en chevauchement')
    for ref, bb in bounds.items():
        if ref.startswith('H'):
            continue
        if min(bb[0],bb[1]) < 0.25-0.00001 or bb[2] > 125.75+0.00001 or bb[3] > 79.75+0.00001:
            problems.append('Courtyard hors enveloppe : ' + ref)
        for reserve in config['reservations']:
            if reserve.get('owner') == ref:
                continue
            if intersects(bb, reserve['bounds_mm'], gap=0):
                problems.append('Réserve occupée : ' + ref + '/' + reserve['reference'])
    for ref, pos in config['placements'].items():
        fp = fps[ref]
        actual = [p.ToMM(fp.GetPosition().x)-ORIGIN[0], p.ToMM(fp.GetPosition().y)-ORIGIN[1], fp.GetOrientationDegrees() % 360]
        if any(abs(a-b) > 0.00001 for a,b in zip(actual,pos)):
            problems.append('Position JSON différente : ' + ref)
    for ref, centre in zip(['H1','H2','H3','H4'], config['mounting_centres_mm']):
        pad = next(iter(fps[ref].Pads()))
        if abs(p.ToMM(pad.GetDrillSize().x)-3.2) > 0.00001:
            problems.append('Perçage fixation incorrect : ' + ref)
    edge = board.GetBoardEdgesBoundingBox()
    if abs(p.ToMM(edge.GetWidth())-126) > 0.051 or abs(p.ToMM(edge.GetHeight())-80) > 0.051:
        problems.append('Contour incorrect')
    model_missing = []
    models_inventory = read(CARD/'modeles_3d.json') if (CARD/'modeles_3d.json').exists() else None
    model_kind = {}
    for ref, fp in fps.items():
        if ref.startswith(('H','TP')) or ref == 'JP501':
            continue
        models = list(fp.Models())
        if not models and not fp.IsDNP():
            model_missing.append(ref + ': modèle absent')
        for model in models:
            name = model.m_Filename.replace('${KIPRJMOD}', str(CARD)).replace('${KICAD10_3DMODEL_DIR}', 'C:/Program Files/KiCad/10.0/share/kicad/3dmodels')
            if not Path(name).exists():
                model_missing.append(ref + ': ' + model.m_Filename)
            if models_inventory:
                configured = models_inventory['models_by_ref'][ref]
                model_kind[ref] = configured['kind']
                if model.m_Filename != configured['path']:
                    model_missing.append(ref + ': modèle différent du manifeste3D')
                if Path(name).exists() and sha(Path(name)) != configured['sha256']:
                    model_missing.append(ref + ': SHA256 différent du manifeste3D')
            else:
                model_kind[ref] = 'Enveloppe paramétrique candidate' if 'ca01_placement_20261001' in name else 'Modèle bibliothèque KiCad'
    if model_missing:
        problems.append('Modèles de composants indisponibles')
    drc = read(VERIFY / 'drc_placement_20261001.json')
    drc_counts = {}
    for violation in drc.get('violations', []):
        kind = violation['type']
        drc_counts[kind] = drc_counts.get(kind, 0) + 1
        if kind != 'drill_out_of_range':
            problems.append('DRC inattendu : ' + kind)
    if drc.get('schematic_parity'):
        problems.append('Parité schéma/PCB non conforme')
    result = {
        'schema_version': 1, 'date': '2026-10-01', 'toolchain': p.GetBuildVersion() + ' Windows amd64',
        'scope': 'CARTE-010 / CARTE-012 : empreintes et préplacement mécanique sans routage',
        'passed': not problems, 'problems': problems, 'schematic_components': len(components),
        'pcb_footprints': len(fps), 'mounting_holes': 4, 'outline_mm': [126,80],
        'board_only_modules': modules,
        'schematic_ref_replacements': aliases,
        'missing_electrical_pads': missing_electrical_pads,
        'incomplete_electrical_footprints': config.get('incomplete_electrical_footprints', {}),
        'candidate_electrical_footprints': config.get('candidate_electrical_footprints', {}),
        'radio_geometry_basis': radio_inventory.get('direct_mount', {}).get('geometry_basis'),
        'radio_physical_alignment_qualified': False,
        'mechanical_geometry_checks_passed': not overlaps and not model_missing and not list(board.GetTracks()) and not list(board.Zones()),
        'topology_pin_groups_preserved': len(groups(xml)), 'values_and_dnp_preserved_except_declared_updates': not any('modifi' in x.lower() for x in problems),
        'declared_component_spec_updates': config.get('component_spec_updates', {}),
        'schematic_parity_issues': len(drc.get('schematic_parity', [])), 'mechanical_pads_without_net': mechanical_pad_count,
        'courtyard_overlap_count': len(overlaps), 'courtyard_overlaps': overlaps,
        'tracks': len(list(board.GetTracks())), 'zones': len(list(board.Zones())),
        'unrouted_connections': len(drc.get('unconnected_items', [])), 'drc_violations': drc_counts,
        'open_drc': '30 trous thermiques 0,2 mm dans U201/U301, minimum projet0,3mm ; choix fabricant/PCB à fermer avant fabrication, aucune règle masquée',
        'model_missing': model_missing, 'models': model_kind,
        'qualification': 'À valider', 'manufacturing_ready': False, 'hardware_tests_executed': False,
        'limits': ['Contrôle2D des courtyards ; contrôles3D et provenance dans la preuve modeles_3d_20261001.json',
                   'Modèles nominaux de bibliothèque, auteur ou dérivés de plans ; RP4TD reste une enveloppe sans sous-face ni broches',
                   'Prises accouplées, câbles et soudures non représentés ; queues THT des modèles détaillés contrôlées séparément',
                   'Empilage, isolants, fixation, vibrations, thermique et CEM sans essai physique',
                   'Départs de puissance, protections, Ceff, boucle et séquencements restent non qualifiés',
                   'Les connexions non routées sont attendues ; ce résultat ne constitue pas un DRC de fabrication conforme'],
        'inputs': [{'path': str(file.relative_to(CARD)), 'sha256': sha(file)} for file in [
            board_path, CARD/'placement_mecanique.json', CARD/'empreintes_connecteurs.json', CARD/'empreintes_composants.json',
            CARD/'fp-lib-table', CARD/'bom_candidate.json', VERIFY/'netlist.xml', baseline_path,
            VERIFY/'drc_placement_20261001.json', Path(__file__), VERIFY/'build_placement.py', VERIFY/'apply_footprints.py']],
        'courtyard_bounds_local_mm': bounds,
    }
    result['inputs'].append({'path':'empreinte_rp4td.json','sha256':sha(CARD/'empreinte_rp4td.json')})
    if models_inventory:
        result['inputs'].append({'path':'modeles_3d.json','sha256':sha(CARD/'modeles_3d.json')})
    for module in modules.values():
        inventory = CARD / module['inventory']
        result['inputs'].append({'path': module['inventory'], 'sha256': sha(inventory)})
    write(VERIFY / 'placement_mecanique_20261001.json', result)
    print(json.dumps({k: result[k] for k in ['passed','problems','pcb_footprints','tracks','zones','drc_violations','model_missing']}, ensure_ascii=False))
    if problems:
        raise SystemExit(1)


if __name__ == '__main__':
    run()
