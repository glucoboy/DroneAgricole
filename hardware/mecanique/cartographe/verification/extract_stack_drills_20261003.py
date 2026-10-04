"""Infrastructure de lecture seule, exécuter avec le Python KiCad."""
from pathlib import Path
import json,hashlib
import pcbnew as p
ROOT=Path(__file__).resolve().parents[4]
source=ROOT/'hardware/electronique/cartographe/carte_avionique/CA01_Avionique.kicad_pcb'
before=source.read_bytes();board=p.LoadBoard(str(source))
holes=[{'ref':f.GetReference(),'pad':x.GetNumber(),
        'xy_mm':[p.ToMM(x.GetPosition().x)-50,-(p.ToMM(x.GetPosition().y)-50)],
        'drill_mm':[p.ToMM(x.GetDrillSize().x),p.ToMM(x.GetDrillSize().y)],
        'angle_deg':x.GetOrientationDegrees()}
       for f in board.GetFootprints() for x in f.Pads() if x.GetDrillSize().x>0]
assert source.read_bytes()==before
out=ROOT/'hardware/mecanique/cartographe/verification/percages_ca01_stack_20261003.json'
out.write_text(json.dumps({'pcb_sha256':hashlib.sha256(before).hexdigest(),
    'vias_hors_geometrie':True,'holes':holes},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'perçages_pads':len(holes),'PCB_inchange':True}))
