"""Contrôles CA01 du routage initial, sans qualification de fabrication.

Exécuter après un DRC KiCad neuf avec --schematic-parity. Contrôle les nets,
les cuivres remplis au droit des vias, le contour, les placements et la parité.
"""
import hashlib
import datetime
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

import pcbnew as p

CARD = Path(__file__).resolve().parents[1]
VERIFY = CARD / 'verification'


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run():
    board_path = CARD / 'CA01_Avionique.kicad_pcb'
    board = p.LoadBoard(str(board_path))
    config = read(CARD / 'routage.json')
    placement = read(CARD / 'placement_mecanique.json')
    models = read(CARD / 'modeles_3d.json')
    drc = read(VERIFY / 'drc_routage_20261001.json')
    xml = ET.parse(VERIFY / 'netlist.xml')
    fps = {fp.GetReference(): fp for fp in board.GetFootprints()}
    problems = []
    checks = []

    def check(name, success, detail=None):
        checks.append(dict(name=name, passed=bool(success), detail=detail))
        if not success:
            problems.append(name)

    check('4 couches cuivre', board.GetCopperLayerCount() == 4)
    check('Inventaire et fixations conservés', set(fps) == set(placement['placements']) and len(fps) == 155)
    offsets = []
    model_changes = []
    for ref, pos in placement['placements'].items():
        fp = fps[ref]
        actual = [p.ToMM(fp.GetPosition().x)-50, p.ToMM(fp.GetPosition().y)-50, fp.GetOrientationDegrees() % 360]
        if any(abs(a-b) > .00001 for a,b in zip(actual,pos)):
            offsets.append(ref)
        if ref in models['models_by_ref']:
            expected = models['models_by_ref'][ref]['path']
            if (expected is None and list(fp.Models())) or (expected is not None and not any(m.m_Filename == expected for m in fp.Models())):
                model_changes.append(ref)
    check('Positions mécaniques conservées', not offsets, offsets)
    check('Affectations modèles 3D conservées', not model_changes, model_changes)
    edge = board.GetBoardEdgesBoundingBox()
    check('Contour 126x80 mm et épaisseur 1.6 mm',
          abs(p.ToMM(edge.GetWidth())-126) <= .051 and abs(p.ToMM(edge.GetHeight())-80) <= .051
          and abs(p.ToMM(board.GetDesignSettings().GetBoardThickness())-1.6) < .00001)
    expected_nets = {(x.attrib['ref'],x.attrib['pin']):n.attrib['name'] for n in xml.findall('./nets/net') for x in n.findall('node')}
    errors = []
    for ref, fp in fps.items():
        for pad in fp.Pads():
            if pad.GetNumber() in ('', 'MP'):
                if pad.GetNetCode():
                    errors.append(ref+'/ancrage')
            elif ref not in ('H1','H2','H3','H4'):
                target = expected_nets.get((ref,pad.GetNumber()), '')
                if pad.GetNetname().replace('{slash}','/') != target:
                    errors.append(ref+'/'+pad.GetNumber())
    check('Tous réseaux pads conformes à la netlist', not errors, errors)
    components = {c.attrib['ref']:c for c in xml.findall('./components/comp')}
    check('Valeurs, DNP et références empreintes synchronisés', all(
        fps[r].GetValue() == c.findtext('value') and fps[r].GetFPIDAsString() == c.findtext('footprint')
        and fps[r].IsDNP() == any(x.attrib['name']=='dnp' for x in c.findall('property'))
        for r,c in components.items()))
    zones = {z.GetZoneName():z for z in board.Zones()}
    check('10 zones remplies, raccord plein', len(zones)==10 and all(z.IsFilled() and z.GetPadConnection()==p.ZONE_CONNECTION_FULL for z in zones.values()))
    check('Définition des plans et îlots au potentiel attendu', all(
        item['name'] in zones and zones[item['name']].GetNetname()==item['net']
        and board.GetLayerName(zones[item['name']].GetLayer())==item['layer'] for item in config['zones']))
    check('Exclusions Kelvin et SW sérialisées comme trous de zones', all(
        zones[item['name']].Outline().HoleCount(0)==len(item.get('holes_mm',[])) for item in config['zones']))
    for item in config['zones']:
        zone = zones[item['name']]
        for i,hole in enumerate(item.get('holes_mm',[])):
            x = sum(v[0] for v in hole)/len(hole)
            y = sum(v[1] for v in hole)/len(hole)
            point = p.VECTOR2I(p.FromMM(x+50),p.FromMM(y+50))
            check('Centre de l’exclusion sans cuivre : '+item['name']+'/'+str(i),
                  not zone.HitTestFilledArea(zone.GetLayer(),point))
    vias = [t for t in board.GetTracks() if isinstance(t,p.PCB_VIA)]
    tracks = [t for t in board.GetTracks() if not isinstance(t,p.PCB_VIA)]
    check('111 vias traversants 0.6/0.3 mm', len(vias)==len(config['vias'])==111 and all(
        abs(p.ToMM(v.GetWidth(p.F_Cu))-.6)<.00001 and abs(p.ToMM(v.GetDrill())-.3)<.00001 for v in vias))
    by_pos = {(round(p.ToMM(v.GetPosition().x)-50,6),round(p.ToMM(v.GetPosition().y)-50,6)):v for v in vias}
    check('Réseaux et centres de chaque via', all(
        tuple(v['position_mm']) in by_pos and by_pos[tuple(v['position_mm'])].GetNetname()==v['net'] for v in config['vias']))
    thermal_connections = []
    for item in config['vias']:
        via = by_pos.get(tuple(item['position_mm']))
        if via is None:
            continue
        target = None
        layer = p.B_Cu
        if item['net']=='GND':
            target,layer = 'CA01_GND_In1.Cu',p.In1_Cu
        elif item['net']=='VIN_PAYLOAD_PROT':
            target,layer = 'CA01_BATTERIE_PROTEGEE',p.In2_Cu
        elif item['net']=='Net-(Q101-D)':
            target,layer = 'CA01_DRAIN_PROTECTION_B.Cu',p.B_Cu
        elif item['net']=='Net-(Q104-D)':
            target,layer = 'CA01_Q104_SW_COMPACT_B.Cu',p.B_Cu
        if not target or not zones[target].HitTestFilledArea(layer,via.GetPosition()):
            thermal_connections.append(item['name'])
    check('Chaque via rejoint le cuivre rempli de son réseau', not thermal_connections, thermal_connections)
    drilled = [s for ref in ('U201','U301') for s in fps[ref].Pads() if s.GetDrillSize().x]
    check('30 trous thermiques 0.3 mm intégrés EP GND', len(drilled)==30 and all(
        s.GetNetname()=='GND' and abs(p.ToMM(s.GetDrillSize().x)-.3)<.00001
        and zones['CA01_GND_In1.Cu'].HitTestFilledArea(p.In1_Cu,s.GetPosition()) for s in drilled))
    check('U101 EP13 flottant sans via ajouté', all(
        s.GetNetname()=='unconnected-(U101-RTN_FLOAT-Pad13)' and not any(
            abs(v.GetPosition().x-s.GetPosition().x)<s.GetSize().x/2 and abs(v.GetPosition().y-s.GetPosition().y)<s.GetSize().y/2 for v in vias)
        for s in fps['U101'].Pads() if s.GetNumber()=='13'))
    sense = [s for s in fps['R116'].Pads() if p.ToMM(s.GetSize().y)<2]
    check('Prises sense R116 exclues du remplissage GND avant routage Kelvin', len(sense)==2 and all(
        not zones['CA01_GND_F.Cu'].HitTestFilledArea(p.F_Cu,s.GetPosition()) for s in sense))
    check('4 segments : entrée fusible et drains communs', len(tracks)==4 and
          {t.GetNetname() for t in tracks}=={'VBAT_PAYLOAD','Net-(Q101-D)'})
    contents = board_path.read_text(encoding='utf-8')
    check('Cuivre et diélectriques natifs totalisent 1.6 mm', all(
        re.search(r'\(layer "'+re.escape(layer)+r'"\s+\(type "copper"\)\s+\(thickness '+value+r'\)', contents)
        for layer,value in [('F.Cu','0.07'),('In1.Cu','0.035'),('In2.Cu','0.035'),('B.Cu','0.07')])
        and abs(sum(config['stackup']['dielectric_thickness_mm'])+sum(config['stackup']['copper_thickness_um'])/1000-1.6)<.00001)
    check('DRC zéro violation et parité zéro', not drc['violations'] and not drc['schematic_parity'])
    check('Routage explicitement incomplet et non fabricable', bool(drc['unconnected_items']) and not config['manufacturing_ready'])
    inputs = [board_path,CARD/'CA01_Avionique.kicad_pro',CARD/'routage.json',CARD/'placement_mecanique.json',
              CARD/'modeles_3d.json',VERIFY/'netlist.xml',VERIFY/'drc_routage_20261001.json',
              Path(__file__),VERIFY/'start_routing.py',VERIFY/'variante_lm76003_percages_20261001.json']
    result = dict(schema_version=1,date='2026-10-01',verification_date=datetime.datetime.now(datetime.timezone.utc).isoformat(),toolchain=p.GetBuildVersion()+' Windows amd64',
        requirements=config['requirements'],scope='CA01 : routage initial, géométrie et réseaux, hors qualification matériel',
        passed=not problems,conclusion='préliminaire' if not problems else 'non conforme',qualification='À valider',
        manufacturing_ready=False,checks=checks,problems=problems,pcb_footprints=len(fps),copper_layers=4,
        track_segments=len(tracks),vias=len(vias),thermal_holes_in_footprints=len(drilled),zones=len(zones),
        unrouted_connections=len(drc['unconnected_items']),drc_violations=len(drc['violations']),schematic_parity=len(drc['schematic_parity']),
        hardware_tests_executed=False,remaining=config['remaining'],
        inputs=[dict(path=str(f.relative_to(CARD)),sha256=sha(f)) for f in inputs])
    (VERIFY/'routage_initial_20261001.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:result[k] for k in ['passed','problems','track_segments','vias','zones','unrouted_connections']},ensure_ascii=False))
    if problems:
        raise SystemExit(1)


if __name__=='__main__':
    run()
