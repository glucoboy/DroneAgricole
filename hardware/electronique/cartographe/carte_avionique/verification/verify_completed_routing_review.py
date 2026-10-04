"""Independent read-only CA01 geometry/connectivity review. Run with KiCad Python."""
import hashlib,json,platform,subprocess,sys,tempfile
import xml.etree.ElementTree as ET
from datetime import datetime,timezone
from pathlib import Path
import pcbnew as p

here=Path(__file__).resolve().parent
source=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else here.parent/'CA01_Avionique.kicad_pcb'
output=Path(sys.argv[2]).resolve() if len(sys.argv)>2 else here/'revue_routage_complet_20261002.json'
netlist=source.parent/'verification/netlist.xml'
sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
inputs=[source,source.with_suffix('.kicad_pro'),netlist,here/'review_completed_kelvin.py',here/'review_completed_power_path.py',Path(__file__).resolve()]
hashes={str(x):sha(x) for x in inputs}
b=p.LoadBoard(str(source)); b.BuildConnectivity()
footprints=list(b.GetFootprints()); fs={f.GetReference():f for f in footprints}
tracks=[t for t in b.GetTracks() if not isinstance(t,p.PCB_VIA)]
vias=[t for t in b.GetTracks() if isinstance(t,p.PCB_VIA)]
zones=[z for z in b.Zones() if not z.GetIsRuleArea()]
areas=[z for z in b.Zones() if z.GetIsRuleArea()]
checks=[]
def check(code,passed,details): checks.append(dict(id=code,passed=bool(passed),details=details))
expected={}
for n in ET.parse(netlist).getroot().findall('./nets/net'):
    for node in n.findall('node'): expected[(node.attrib['ref'],node.attrib['pin'])]=n.attrib['name']
actual={}
escaped_slash_nodes=[]
for f in footprints:
    for q in f.Pads():
        if q.GetNumber() and q.GetNetCode():
            actual[(f.GetReference(),q.GetNumber())]=q.GetNetname().replace('{slash}','/')
            if '{slash}' in q.GetNetname(): escaped_slash_nodes.append(dict(ref=f.GetReference(),pin=q.GetNumber(),pcb_net=q.GetNetname(),xml_net=actual[(f.GetReference(),q.GetNumber())]))
mismatch=[dict(ref=k[0],pin=k[1],expected=expected.get(k),actual=actual.get(k)) for k in sorted(set(expected)|set(actual)) if expected.get(k)!=actual.get(k)]
check('NETLIST_PADS_PRESERVED',not mismatch,dict(expected_nodes=len(expected),pcb_nodes=len(actual),mismatches=mismatch,encoding_conversion='KiCad PCB literal {slash} decoded to / for XML comparison; all conversions listed',converted_nodes=escaped_slash_nodes))
netpads={}
for f in footprints:
    for q in f.Pads():
        if q.GetNetCode() and q.GetNumber(): netpads.setdefault(q.GetNetname(),[]).append(q)
disconnected=[]
for net,pads in netpads.items():
    group={x.m_Uuid.AsString() for x in b.GetConnectivity().GetConnectedItems(pads[0])}
    if any(q.m_Uuid.AsString() not in group for q in pads): disconnected.append(net)
check('ALL_SIGNAL_PAD_GROUPS_CONNECTED',not disconnected,dict(nets=len(netpads),disconnected=disconnected,method='Declared component internal duplicate-pad jumpers enabled; Kelvin checked separately with jumpers disabled'))
ground_planes=[z for z in zones if z.GetNetname()=='GND' and z.GetLayer()==p.In1_Cu]
check('GND_REFERENCE_PLANE_PRESENT',bool(ground_planes) and all(z.GetFilledPolysList(p.In1_Cu).OutlineCount()>0 for z in ground_planes),[z.GetZoneName() for z in ground_planes])
check('INTERNAL_PLANES_WITHOUT_TRACES',not any(t.GetLayer() in [p.In1_Cu,p.In2_Cu] for t in tracks),'No trace on In1/In2; vias retained, In1 GND and In2 protected battery copper zones')
check('STACK_FOUR_LAYERS',b.GetCopperLayerCount()==4 and abs(p.ToMM(b.GetDesignSettings().GetBoardThickness())-1.6)<1e-6,dict(layers=b.GetCopperLayerCount(),thickness_mm=p.ToMM(b.GetDesignSettings().GetBoardThickness())))
counts=dict(footprints=len(footprints),segments=len(tracks),vias=len(vias),copper_zones=len(zones),rule_areas=len(areas))
check('GEOMETRY_COUNTS',counts==dict(footprints=155,segments=1255,vias=251,copper_zones=10,rule_areas=7),counts)
specs=[('12V_COMPUTE',1.8,'L101','2','J104','1'),('12V_LIDAR',1.8,'L201','2','J201','1'),('5V_AUX',1.8,'L301','2','J301','1'),('5V_AUX',0.6,'L301','2','F102','1'),('5V_RADIO',0.6,'F102','2','MOD401','1'),('Net-(U101-A)',1.5,'F101','2','Q101','1'),('Net-(Q101-D)',1.5,'Q101','5','Q102','5'),('Net-(Q104-D)',1.5,'Q104','5','L101','1')]
with tempfile.TemporaryDirectory(prefix='review_tmp_',dir=output.parent) as folder:
    folder=Path(folder)
    def run_recipe(recipe,args,path):
        run=subprocess.run([sys.executable,str(here/recipe),*args,str(path)],capture_output=True,text=True)
        if run.returncode: raise RuntimeError(run.stderr or run.stdout)
        return json.loads(path.read_text(encoding='utf-8'))
    kelvin=run_recipe('review_completed_kelvin.py',[str(source)],folder/'kelvin.json')
    for item in kelvin['checks']: checks.append(item)
    for i,spec in enumerate(specs):
        result=run_recipe('review_completed_power_path.py',[str(source),*[str(x) for x in spec]],folder/f'path_{i}.json')
        check(f'POWER_PATH_{i+1}',result['passed'] and result['source_unchanged'],result)
    drcfile=folder/'drc.json'
    cli=Path(sys.executable).parent/'kicad-cli.exe'
    drcrun=subprocess.run([str(cli),'pcb','drc','--format','json','--schematic-parity','--exit-code-violations','-o',str(drcfile),str(source)],capture_output=True,text=True)
    drc=json.loads(drcfile.read_text(encoding='utf-8'))
    durable_drc=output.with_name(output.stem+'_drc.json')
    durable_drc.write_bytes(drcfile.read_bytes())
    drc_counts={x:len(drc[x]) for x in ['violations','unconnected_items','schematic_parity']}
    check('INDEPENDENT_NATIVE_DRC_PARITY',drcrun.returncode==0 and not any(drc_counts.values()),dict(returncode=drcrun.returncode,counts=drc_counts,ignored_checks=drc.get('ignored_checks'),configuration='Project severities unchanged; five pre-existing ignored checks remain explicitly listed',report=str(durable_drc),report_sha256=sha(durable_drc)))
check('SOURCE_INPUTS_UNCHANGED',all(sha(x)==hashes[str(x)] for x in inputs),'PCB, project, netlist and recipes retain their initial hashes; no SaveBoard')
passed=all(x['passed'] for x in checks)
result=dict(schema_version=1,date=datetime.now(timezone.utc).isoformat(),conclusion='conforme' if passed else 'non conforme',status='Implémenté',qualification='À valider',manufacturing_ready=False,passed=passed,scope='Independent Windows amd64 KiCad static review; no PCB/project edits',requirement_refs=['CARTE-003','CARTE-004','CARTE-005','CARTE-006','CARTE-011','CARTE-012'],environment=dict(os=platform.platform(),machine=platform.machine(),kicad=p.GetBuildVersion(),python=sys.version,executable=sys.executable),inputs_sha256=hashes,protocol='Fresh process per width-removal test; thresholds are candidate geometry checks, not qualified current capacity. Native physical clusters and filled planes, netlist pad mapping, Kelvin isolation after in-memory terminal cut, native DRC with project severities.',checks=checks,counts=counts,limitations=['All current, temperature, load, stability, efficiency, startup, transient, EMC and manufacturer DFM tests remain unexecuted.','Via current capacity, short MOSFET source necks, LM76003 fanouts and thermal rise remain À valider.','No proof of fabrication readiness or qualification on hardware.','DRC uses unchanged project severities including five ignored checks; separate audit required for those ignored checks.'],references=['https://www.ti.com/lit/ds/symlink/lm5146-q1.pdf'],t0_applicability='Hardware CAO static proof; dataset, calibration, simulation and flight T0 contracts not applicable.',physical_tests_executed=0)
output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(passed=passed,checks=len(checks),failed=[x['id'] for x in checks if not x['passed']],source_sha256=hashes[str(source)],output=str(output)),indent=2))
sys.exit(0 if passed else 1)
