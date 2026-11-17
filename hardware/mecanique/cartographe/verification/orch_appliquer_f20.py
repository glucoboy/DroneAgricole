"""Application bornée de la proposition F20 indépendante, sans coupe de cordon réel."""
from pathlib import Path
from datetime import datetime,timezone
import json,hashlib,sys,os
ARGS=sys.argv[1:];sys.argv=[sys.executable]
import FreeCAD as A
from cable_workbench_prototype import bootstrap_paths,cable_geometry
from orch_integrate_cao import save_assembly
bootstrap_paths()
import Draft
from draftviewproviders.view_wire import ViewProviderWire
Draft.ViewProviderWire=ViewProviderWire
from freecad.cables import wireFlex,archCable
ROOT=Path(__file__).resolve().parents[4];MEC=ROOT/'hardware/mecanique/cartographe';VER=MEC/'verification'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
path=MEC/'pieces/commerce/W_F20_Prototype.FCStd';before=sha(path)
doc=A.openDocument(str(path));w=doc.Wire;c=doc.Cable
assert w.Proxy is not None and c.Proxy is not None
points=list(w.Points);global_first=w.Placement.multVec(points[0]);target=A.Vector(-52,29.1,150)
assert (global_first-A.Vector(-52,27.5,150)).Length<1e-7 or (global_first-target).Length<1e-7
points[0]=w.Placement.inverse().multVec(target);w.Points=points;w.touch();c.touch();doc.recompute(None,True,True)
check=cable_geometry(c);assert check['solide_valide'] and check['continuite'] and not check['erreurs']
save_assembly(doc)
proof={'lot':'ORCH-CAO-MASSE-1','application_root':True,'date_utc':datetime.now(timezone.utc).isoformat(),'script_sha256':sha(__file__),
 'proposition':'verification/orch_reprise_f20.json','proposition_sha256':sha(VER/'orch_reprise_f20.json'),'fichier':path.relative_to(MEC).as_posix(),
 'sha256_avant':before,'sha256_apres':sha(path),'premier_point_mm':list(target),'controle':check,'finalisation_correcte':True,
 'qualification':'À valider','limite':'Borne de réservation extérieure au carter ; port et segment de raccord réels inconnus, aucune coupe OEM ni réduction de masse attribuée.'}
(VER/'orch_reprise_f20_application.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n','utf-8')
print(json.dumps(proof),flush=True);os._exit(0)
