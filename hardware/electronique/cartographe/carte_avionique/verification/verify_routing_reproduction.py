"""Comparer le routage reconstruit en copie isolée au PCB CA01 courant.

Ignore UUID et ordre de sérialisation, compare géométrie, nets et modèles.
Ne modifie aucun PCB ; produit seulement une preuve légère.
"""
import argparse
import datetime
import hashlib
import json
from pathlib import Path

import pcbnew as p

CARD = Path(__file__).resolve().parents[1]
VERIFY = CARD / 'verification'


def xy(v):
    return (round(p.ToMM(v.x),5),round(p.ToMM(v.y),5))


def signatures(board):
    footprints = {}
    for fp in board.GetFootprints():
        pads = sorted((pad.GetNumber(),pad.GetNetname(),xy(pad.GetPosition()),
                       xy(pad.GetSize()),xy(pad.GetDrillSize())) for pad in fp.Pads())
        models = sorted((m.m_Filename,tuple(getattr(m.m_Offset,k) for k in ('x','y','z')),
                         tuple(getattr(m.m_Rotation,k) for k in ('x','y','z')),
                         tuple(getattr(m.m_Scale,k) for k in ('x','y','z'))) for m in fp.Models())
        footprints[fp.GetReference()] = (fp.GetValue(),fp.GetFPIDAsString(),xy(fp.GetPosition()),
            round(fp.GetOrientationDegrees()%360,5),fp.IsDNP(),pads,models)
    vias = sorted((t.GetNetname(),xy(t.GetPosition()),t.GetWidth(p.F_Cu),t.GetDrill())
                  for t in board.GetTracks() if isinstance(t,p.PCB_VIA))
    tracks = sorted((t.GetNetname(),t.GetLayer(),xy(t.GetStart()),xy(t.GetEnd()),t.GetWidth())
                    for t in board.GetTracks() if not isinstance(t,p.PCB_VIA))
    zones = {}
    for z in board.Zones():
        outline = z.Outline()
        polygons = []
        for i in range(outline.OutlineCount()):
            outer = outline.COutline(i)
            contours = [tuple(xy(outer.CPoint(n)) for n in range(outer.PointCount()))]
            for j in range(outline.HoleCount(i)):
                hole = outline.CHole(i,j)
                contours.append(tuple(xy(hole.CPoint(n)) for n in range(hole.PointCount())))
            polygons.append(contours)
        zones[z.GetZoneName()] = (z.GetNetname(),z.GetLayer(),z.GetPadConnection(),
            z.GetAssignedPriority(),z.GetLocalClearance(),z.IsFilled(),polygons)
    return dict(copper_layers=board.GetCopperLayerCount(),thickness=board.GetDesignSettings().GetBoardThickness(),
                footprints=footprints,vias=vias,tracks=tracks,zones=zones)


def main(reconstructed):
    active = CARD/'CA01_Avionique.kicad_pcb'
    a,b = signatures(p.LoadBoard(str(active))),signatures(p.LoadBoard(str(reconstructed)))
    checks = {name:a[name]==b[name] for name in a}
    files = [active,reconstructed,CARD/'placement_mecanique.json',CARD/'routage.json',
             VERIFY/'build_placement.py',VERIFY/'start_routing.py',Path(__file__)]
    result = dict(schema_version=1,verification_date=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        toolchain=p.GetBuildVersion()+' Windows amd64',scope='Reconstruction isolée du préplacement puis du routage initial',
        passed=all(checks.values()),checks=checks,manufacturing_ready=False,qualification='À valider',
        ignored='UUID, ordre de sérialisation ; géométrie arrondie à 10 nm pour éviter bruit numérique de conversion',
        inputs=[dict(path=str(f),sha256=hashlib.sha256(f.read_bytes()).hexdigest()) for f in files])
    (VERIFY/'reproduction_routage_20261002.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'passed':result['passed'],'checks':checks},ensure_ascii=False))
    if not result['passed']:
        raise SystemExit(1)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('reconstructed',type=Path)
    main(parser.parse_args().reconstructed)
