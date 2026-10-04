"""Infrastructure de preuve KiCad: variante thermique LM76003, sans modification du PCB."""
from pathlib import Path
import hashlib,json,math,re,xml.etree.ElementTree as ET
import pcbnew as p
CARD=Path(__file__).resolve().parents[1]
NAME='TI_LM76003_RNP_ThermalVias_D0p3'
OLD='Texas_RNP0030B_WQFN-30-1EP_4x6mm_P0.5mm_EP1.8x4.5mm_ThermalVias'
LIBS=Path(p.__file__).resolve().parents[3]/'share/kicad/footprints'
SOURCE=LIBS/'Package_DFN_QFN.pretty'/f'{OLD}.kicad_mod'
VARIANT=CARD/'CA01_Mecanique.pretty'/f'{NAME}.kicad_mod'
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def norm(text): return re.sub(r'\(descr "[^"\n]+"\)','(descr "normalized")',text).replace(NAME,OLD).replace('(drill 0.3)','(drill 0.2)')
def nets(path):
    root=ET.parse(path).getroot()
    return sorted(tuple(sorted((n.attrib['ref'],n.attrib['pin']) for n in net.findall('node'))) for net in root.findall('./nets/net'))
def comps(path):
    return {x.attrib['ref']:{'value':x.findtext('value'),'footprint':x.findtext('footprint'),'dnp':any(y.attrib.get('name')=='dnp' for y in x.findall('property'))} for x in ET.parse(path).getroot().findall('./components/comp')}
f=p.FootprintLoad(str(VARIANT.parent),NAME)
assert f is not None
holes=[x for x in f.Pads() if x.GetDrillSize().x>0]
pitches=[math.hypot(p.ToMM(a.GetPosition().x-b.GetPosition().x),p.ToMM(a.GetPosition().y-b.GetPosition().y)) for i,a in enumerate(holes) for b in holes[i+1:]]
before=CARD/'verification/netlist_avant_percages_thermiques_20261001.xml'
after=CARD/'verification/netlist.xml'
cb,ca=comps(before),comps(after)
changes={ref:{'before':cb[ref],'after':ca[ref]} for ref in cb if cb[ref]!=ca[ref]}
checks={
 'library_geometry_only_declared_changes':norm(SOURCE.read_text(encoding='utf-8'))==norm(VARIANT.read_text(encoding='utf-8')),
 'fifteen_pad31_holes':len(holes)==15 and all(x.GetNumber()=='31' for x in holes),
 'drill03_pad05':all(x.GetDrillSize().x==p.FromMM(.3) and x.GetDrillSize().y==p.FromMM(.3) and x.GetSize().x==p.FromMM(.5) and x.GetSize().y==p.FromMM(.5) for x in holes),
 'hole_to_hole_min025':min(pitches)-.3>=.25-1e-9,
 'annular_min01':all((p.ToMM(x.GetSize().x)-.3)/2>=.1-1e-9 for x in holes),
 'topology_preserved':nets(before)==nets(after),
 'only_expected_instance_footprints_changed':set(changes)=={'U201','U301'} and all(cb[r]['value']==ca[r]['value'] and cb[r]['dnp']==ca[r]['dnp'] and ca[r]['footprint']=='CA01_Mecanique:'+NAME for r in changes),
 'schematic_invariants_pass':json.loads((CARD/'verification/controle_statique.json').read_text(encoding='utf-8-sig'))['connectivity_passed'],
 'erc_zero_errors_warnings':json.loads((CARD/'verification/controle_statique.json').read_text(encoding='utf-8-sig'))['erc']['passed'],
}
result={'schema_version':1,'date':'2026-10-01','toolchain':p.GetBuildVersion()+' Windows amd64','scope':'Variante locale U201/U301: 15 perçages thermiques Ø0,3 chacun, sans changement de cuivre/XY/topologie','status':'Implémenté','qualification':'À valider','passed':all(checks.values()),'checks':checks,'footprint':'CA01_Mecanique:'+NAME,'min_hole_pitch_mm':min(pitches),'nominal_hole_to_hole_mm':min(pitches)-.3,'nominal_annular_ring_mm':.1,'instance_changes':changes,'input_sha256':{str(path.relative_to(CARD)):sha(path) for path in [VARIANT,before,after,CARD/'02_buck_12v_capteurs.kicad_sch',CARD/'03_buck_5v_aux.kicad_sch',CARD/'empreintes_composants.json',CARD/'bom_candidate.json']},'base_library':{'path':str(SOURCE),'sha256':sha(SOURCE)},'manufacturing_ready':False,'hardware_tests_executed':False,'limits':['Anneau annulaire nominal au minimum projet; tolérances fabricant et process assembleur à valider','Compatibilité remplissage/bouchage des trous et brasure à fermer','Aucune qualification électrique ou thermique de la carte']}
out=CARD/'verification/variante_lm76003_percages_20261001.json'
out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'passed':result['passed'],'checks':checks,'report':str(out)},ensure_ascii=False,indent=2))
if not result['passed']: raise SystemExit(1)
