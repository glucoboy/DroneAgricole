"""Infrastructure de vérification en lecture seule du routage CA01 courant.
Exécuter la DRC CLI avec parité et remplissage avant cette recette.
La sortie consigne des contrôles de CAO ; aucune qualification physique.
"""
import collections, hashlib, json
from pathlib import Path
import pcbnew as p

CARD=Path(__file__).resolve().parents[1]
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path):return json.loads(path.read_text(encoding='utf-8-sig'))
pcb=CARD/'CA01_Avionique.kicad_pcb';b=p.LoadBoard(str(pcb))
fps={f.GetReference():f for f in b.GetFootprints()};tracks=list(b.GetTracks());zones=list(b.Zones())
xy=lambda v:[round(p.ToMM(v.x)-50,6),round(p.ToMM(v.y)-50,6)]
pad=lambda ref,num:next(q for q in fps[ref].Pads() if q.GetNumber()==str(num))
checks=[]
def check(code,ok,details):checks.append(dict(id=code,passed=bool(ok),details=details))
drc_path=CARD/'verification/drc_routage_complet_20261002.json';drc=read(drc_path)
check('DRC_PARITE_CONNECTIVITE',not any(drc.get(k,[]) for k in ['violations','unconnected_items','schematic_parity']),{k:len(drc.get(k,[])) for k in ['violations','unconnected_items','schematic_parity']})
check('STACK_QUATRE_COUCHES',b.GetCopperLayerCount()==4 and b.GetDesignSettings().GetBoardThickness()==1600000,'F/In1/In2/B, 1.6 mm nominal')
check('PLANS_DISTINCTS',any(z.GetNetname()=='GND' and z.GetLayer()==p.In1_Cu for z in zones) and any(z.GetNetname()=='VIN_PAYLOAD_PROT' and z.GetLayer()==p.In2_Cu for z in zones),'GND In1 et batterie protégée In2')
check('COUCHES_INTERNES_SANS_PISTE',all(isinstance(t,p.PCB_VIA) or t.GetLayer() in [p.F_Cu,p.B_Cu] for t in tracks),'Plans internes réservés au cuivre de zone')
expected={'U102':'GND','U201':'GND','U301':'GND','Q101':'Net-(Q101-D)','Q102':'Net-(Q101-D)','Q103':'VIN_PAYLOAD_PROT','Q104':'Net-(Q104-D)'}
check('POTENTIELS_THERMIQUES',all(pad(r,21 if r=='U102' else 31 if r in ['U201','U301'] else 5).GetNetname()==n for r,n in expected.items()),expected)
check('U101_EP_FLOTTANT', 'RTN_FLOAT' in pad('U101',13).GetNetname() and not any(isinstance(t,p.PCB_VIA) and 'RTN_FLOAT' in t.GetNetname() for t in tracks),'EP13 sans via ni GND')
ep={r:sum(q.GetNumber()=='31' and q.GetDrillSize().x==300000 for q in fps[r].Pads()) for r in ['U201','U301']}
check('TROUS_EP',ep=={'U201':15,'U301':15},ep)
check('VIAS_TRAVERSANTS',all(t.GetDrill()==300000 and t.GetWidth(p.F_Cu)==600000 for t in tracks if isinstance(t,p.PCB_VIA)),'.6/.3 mm nominal ; procédé non qualifié')
check('PAD_SHUNT_JUMPER',fps['R116'].GetDuplicatePadNumbersAreJumpers() and len(list(fps['R116'].Pads()))==4,'Deux bornes internes I/E ; aucune liaison PCB force/sense au pad')
r=fps['R116'];r.SetDuplicatePadNumbersAreJumpers(False);b.BuildConnectivity();cn=b.GetConnectivity()
key=lambda i:i.m_Uuid.AsString()
term=sorted(r.Pads(),key=lambda q:(q.GetNumber(),q.GetPosition().y))
cluster=lambda q:{key(i) for i in cn.GetConnectedItems(q)}
check('KELVIN_HAUT_SEPARE',not (cluster(term[0])&cluster(term[1])) and key(pad('R115',2)) in cluster(term[0]),'E1 vers R115 ; I1 vers sources Q104 ; jumper désactivé seulement en mémoire')
e2=term[2].GetPosition()
check('E2_ISOLE_DES_PLANS',all(not z.GetFilledPolysList(z.GetLayer()).Contains(e2) for z in zones if not z.GetIsRuleArea() and z.GetNetname()=='GND' and z.GetLayer() in [p.F_Cu,p.In1_Cu,p.B_Cu]),'Prise E2 et via exclus du remplissage GND ; jonction au bout PGND')
check('KELVIN_BAS_VERS_PGND',key(pad('U102',12)) in cluster(term[2]),'E2 vers PGND12 ; contrôle de jonction unique dans revue indépendante')
models=read(CARD/'modeles_3d.json');changed=[]
for ref,entry in models['models_by_ref'].items():
    paths=[m.m_Filename for m in fps[ref].Models()]
    if entry['path'] is None and paths or entry['path'] is not None and entry['path'] not in paths:changed.append(ref)
check('ASSOCIATIONS_MODELES_3D',not changed,{'changed':changed,'mechanical_exports_placements_current':False})
audit_path=CARD/'verification/drc_controles_reactives_20261002.json';audit=read(audit_path)
check('DRC_CONTROLES_REACTIVES',not any(audit.get(k,[]) for k in ['violations','unconnected_items','ignored_checks']),'Copie isolée : cinq catégories ignore réactivées en warning, projet courant préservé')
review_path=CARD/'verification/revue_routage_complet_20261002.json';review=read(review_path)
check('REVUE_INDEPENDANTE',review['passed'] and next(v for k,v in review['inputs_sha256'].items() if k.endswith('.kicad_pcb'))==sha(pcb),'28 contrôles, SHA PCB courant')
counts={'footprints':len(fps),'segments':sum(not isinstance(t,p.PCB_VIA) for t in tracks),'vias':sum(isinstance(t,p.PCB_VIA) for t in tracks),'copper_zones':sum(not z.GetIsRuleArea() for z in zones),'rule_areas':sum(z.GetIsRuleArea() for z in zones),'thermal_ep_holes':sum(ep.values()),'unconnected':len(drc['unconnected_items'])}
snapshot={'schema_version':1,'date':'2026-10-02','origin_mm':[50,50],'source_sha256':sha(pcb),'placements':{r:xy(f.GetPosition())+[round(f.GetOrientationDegrees(),6)] for r,f in sorted(fps.items())},'tracks':[{'net':t.GetNetname(),'layer':b.GetLayerName(t.GetLayer()),'start_mm':xy(t.GetStart()),'end_mm':xy(t.GetEnd()),'width_mm':p.ToMM(t.GetWidth()),'locked':t.IsLocked(),'uuid':key(t)} for t in tracks if not isinstance(t,p.PCB_VIA)],'vias':[{'net':t.GetNetname(),'position_mm':xy(t.GetPosition()),'diameter_mm':p.ToMM(t.GetWidth(p.F_Cu)),'drill_mm':p.ToMM(t.GetDrill()),'locked':t.IsLocked(),'uuid':key(t)} for t in tracks if isinstance(t,p.PCB_VIA)],'zone_contours':[]}
for z in zones:
    o=z.Outline();contours=[]
    for n in range(o.OutlineCount()):
        line=o.COutline(n);contours.append({'outline':[xy(line.CPoint(j)) for j in range(line.PointCount())],'holes':[[xy(o.CHole(n,h).CPoint(j)) for j in range(o.CHole(n,h).PointCount())] for h in range(o.HoleCount(n))]})
    snapshot['zone_contours'].append({'name':z.GetZoneName(),'net':z.GetNetname(),'layer':b.GetLayerName(z.GetLayer()),'rule_area':z.GetIsRuleArea(),'contours':contours})
out=CARD/'verification/routage_geometrie_20261002.json';out.write_text(json.dumps(snapshot,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
proof={'schema_version':1,'date':'2026-10-02','status':'Implémenté','qualification':'À valider','conclusion':'conforme' if all(c['passed'] for c in checks) else 'non conforme','scope':'CAO et contrôles statiques Windows amd64 KiCad 10.0.6 uniquement','manufacturing_ready':False,'physical_tests_executed':0,'inputs_sha256':{str(f.relative_to(CARD)):sha(f) for f in [pcb,CARD/'CA01_Avionique.kicad_pro',CARD/'modeles_3d.json',drc_path,audit_path,review_path,out,Path(__file__)]},'counts':counts,'checks':checks,'ignored_drc_checks':drc.get('ignored_checks',[]),'drills_native':dict(collections.Counter(str(p.ToMM(q.GetDrillSize().x)) for f in fps.values() for q in f.Pads() if q.GetDrillSize().x)),'limitations':['TVS/fusible/Icc/SOA/Ceff ouverts','Cotes RP4TD photographiques à mesurer','Tolérances stack/perçage/via-in-pad et assemblage à confirmer','Mesures électriques, thermiques et CEM non exécutées','Les valeurs de largeur ne qualifient pas le courant admissible']}
(CARD/'verification/routage_complet_20261002.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'conclusion':proof['conclusion'],'counts':counts,'failed':[c['id'] for c in checks if not c['passed']]},ensure_ascii=False))
if proof['conclusion']!='conforme':raise SystemExit(1)
