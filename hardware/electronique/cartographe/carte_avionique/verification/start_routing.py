"""Infrastructure KiCad : première étape de routage CA01, pilotée par JSON.

Ne remplace pas le PCB par un préplacement. Refuse les cuivres déjà présents
afin de préserver tout travail manuel ultérieur. Exécuter avec Python KiCad.
"""
import argparse
import hashlib
import json
from pathlib import Path

import pcbnew as p

CARD = Path(__file__).resolve().parents[1]
VERIFY = CARD / 'verification'
BOARD = CARD / 'CA01_Avionique.kicad_pcb'
CONFIG = CARD / 'routage.json'
ORIGIN = (50, 50)


def point(x, y):
    return p.VECTOR2I(round((x + ORIGIN[0])*1_000_000), round((y + ORIGIN[1])*1_000_000))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def serialize_stackup(output, config):
    # L'API SWIG ne publie pas BOARD_STACKUP. Sérialiser les champs natifs
    # puis relire par KiCad dans verify_routing.py, sans valeurs d'impédance.
    stack = config['stackup']
    entries = ['\t\t(stackup']
    copper = stack['copper_thickness_um']
    dielectric = stack['dielectric_thickness_mm']
    for i, layer in enumerate(['F.Cu', 'In1.Cu', 'In2.Cu', 'B.Cu']):
        entries.append(f'\t\t\t(layer "{layer}" (type "copper") (thickness {copper[i]/1000}))')
        if i < 3:
            material = 'core' if i == 1 else 'prepreg'
            entries.append(f'\t\t\t(layer "dielectric {i+1}" (type "{material}") (thickness {dielectric[i]}) (material "FR4"))')
    entries.extend(['\t\t\t(copper_finish "None")', '\t\t\t(dielectric_constraints no)', '\t\t)'])
    contents = output.read_text(encoding='utf-8')
    if '(stackup' in contents:
        raise RuntimeError('Stackup source existant inattendu : préserver et examiner avant édition')
    contents = contents.replace('\t(setup\n', '\t(setup\n' + '\n'.join(entries) + '\n', 1)
    output.write_text(contents, encoding='utf-8')


def run(source, output, proof):
    config = json.loads(CONFIG.read_text(encoding='utf-8-sig'))
    board = p.LoadBoard(str(source))
    if list(board.GetTracks()) or list(board.Zones()):
        raise RuntimeError('PCB déjà routé : refus de remplacer les pistes/vias/zones existants')
    source_sha = digest(source)
    project = CARD / 'CA01_Avionique.kicad_pro'
    project_bytes = project.read_bytes()
    board.SetCopperLayerCount(4)
    nets = {n.GetNetname(): n for n in board.GetNetsByNetcode().values()}
    for item in config['zones']:
        zone = p.ZONE(board)
        zone.SetLayer(board.GetLayerID(item['layer']))
        zone.SetNet(nets[item['net']])
        zone.SetZoneName(item['name'])
        zone.SetAssignedPriority(item.get('priority', 0))
        zone.SetLocalClearance(p.FromMM(item.get('clearance_mm', 0.25)))
        zone.SetMinThickness(p.FromMM(0.2))
        zone.SetPadConnection(p.ZONE_CONNECTION_FULL)
        zone.SetIslandRemovalMode(p.ISLAND_REMOVAL_MODE_ALWAYS)
        outline = zone.Outline()
        outline.NewOutline()
        for x, y in item['polygon_mm']:
            v = point(x, y)
            outline.Append(v.x, v.y)
        for hole in item.get('holes_mm', []):
            hole_index = outline.NewHole()
            for x, y in hole:
                v = point(x, y)
                outline.Append(v.x, v.y, 0, hole_index)
        if outline.HoleCount(0) != len(item.get('holes_mm', [])):
            raise RuntimeError('Exclusions de zone perdues : ' + item['name'])
        board.Add(zone)
    for item in config['vias']:
        via = p.PCB_VIA(board)
        via.SetPosition(point(*item['position_mm']))
        via.SetWidth(p.FromMM(item.get('diameter_mm', 0.6)))
        via.SetDrill(p.FromMM(item.get('drill_mm', 0.3)))
        via.SetViaType(p.VIATYPE_THROUGH)
        via.SetLayerPair(p.F_Cu, p.B_Cu)
        via.SetNet(nets[item['net']])
        board.Add(via)
    for item in config['routes']:
        for a, b in zip(item['points_mm'], item['points_mm'][1:]):
            track = p.PCB_TRACK(board)
            track.SetStart(point(*a))
            track.SetEnd(point(*b))
            track.SetWidth(p.FromMM(item['width_mm']))
            track.SetLayer(board.GetLayerID(item['layer']))
            track.SetNet(nets[item['net']])
            board.Add(track)
    for fp in board.GetFootprints():
        update = config.get('thermal_footprint_updates', {}).get(fp.GetReference())
        if update:
            fp.SetFPID(p.LIB_ID(*update['footprint'].split(':', 1)))
            for pad in fp.Pads():
                if pad.GetNumber() == '31' and pad.GetDrillSize().x:
                    pad.SetDrillSize(p.VECTOR2I(p.FromMM(0.3), p.FromMM(0.3)))
    for drawing in board.GetDrawings():
        if isinstance(drawing, p.PCB_TEXT) and 'PREPLACEMENT MECANIQUE - SANS ROUTAGE' in drawing.GetText():
            drawing.SetText('CA01 - ROUTAGE INITIAL 4 COUCHES - NON FABRICABLE')
    board.BuildConnectivity()
    if not p.ZONE_FILLER(board).Fill(board.Zones()):
        raise RuntimeError('Remplissage des zones échoué')
    try:
        p.SaveBoard(str(output), board)
    finally:
        if project.read_bytes() != project_bytes:
            project.write_bytes(project_bytes)
    serialize_stackup(output, config)
    save_json(proof, {
        'date': '2026-10-01', 'toolchain': p.GetBuildVersion() + ' Windows amd64',
        'scope': 'Routage initial uniquement ; connexions restantes à terminer',
        'source': str(source), 'source_sha256': source_sha,
        'configuration_sha256': digest(CONFIG), 'recipe_sha256': digest(Path(__file__)),
        'output': str(output), 'output_sha256': digest(output),
        'copper_layers': board.GetCopperLayerCount(),
        'track_segments': sum(not isinstance(t, p.PCB_VIA) for t in board.GetTracks()),
        'vias': sum(isinstance(t, p.PCB_VIA) for t in board.GetTracks()),
        'zones': len(list(board.Zones())), 'filled': all(z.IsFilled() for z in board.Zones()),
        'qualification': 'À valider', 'manufacturing_ready': False})


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, default=BOARD)
    parser.add_argument('--output', type=Path, default=BOARD)
    parser.add_argument('--proof', type=Path, default=VERIFY / 'construction_routage_20261001.json')
    args = parser.parse_args()
    run(args.source, args.output, args.proof)
