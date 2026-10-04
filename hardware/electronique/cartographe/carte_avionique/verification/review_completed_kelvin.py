import pcbnew as p,json,hashlib,sys
from pathlib import Path
source=Path(sys.argv[1]).resolve(); data=source.read_bytes()
b=p.LoadBoard(str(source)); fs={f.GetReference():f for f in b.GetFootprints()}
r=fs['R116']; original=r.GetDuplicatePadNumbersAreJumpers()
r.SetDuplicatePadNumbersAreJumpers(False); b.BuildConnectivity()
xy=lambda v:tuple(round(p.ToMM(k)-50,6) for k in [v.x,v.y])
key=lambda x:x.m_Uuid.AsString()
ps=sorted(r.Pads(),key=lambda q:(q.GetNumber(),q.GetPosition().y))
def group(q): return {key(x) for x in b.GetConnectivity().GetConnectedItems(q)}
def pad(ref,num): return next(q for q in fs[ref].Pads() if q.GetNumber()==str(num))
def connected(a,c): return key(c) in group(a)
def check(code,passed,details): return dict(id=code,passed=bool(passed),details=details)
corridors=[z for z in b.Zones() if z.GetIsRuleArea() and z.GetLayer()==p.B_Cu and 'KELVIN_B' in z.GetZoneName()]
inside=[v for v in b.GetTracks() if isinstance(v,p.PCB_VIA) and v.GetNetname()=='GND' and any(z.Outline().Collide(v.GetPosition()) for z in corridors)]
fills=[z for z in b.Zones() if not z.GetIsRuleArea() and z.GetNetname()=='GND']
checks=[check('DUPLICATE_JUMPERS_DECLARED',original,'Le modele represente les connexions internes du composant, aucun pont cuivre PCB ajoute'),
check('HIGH_KELVIN_PHYSICALLY_SEPARATED',not(group(ps[0])&group(ps[1])),'Jumpers desactives uniquement en memoire pour cette mesure'),
check('HIGH_SENSE_TO_R115',connected(ps[0],pad('R115',2)),'Prise sense haute vers R115'),
check('HIGH_FORCE_TO_Q104',all(connected(ps[1],pad('Q104',i)) for i in [1,2,3]),'Force haute vers les trois sources Q104'),
check('E2_NO_FILLED_GND_AT_POSITION',all(not z.HitTestFilledArea(z.GetLayer(),ps[2].GetPosition()) for z in fills),'Aucun cuivre GND rempli F/B/In1 au point E2'),
check('CORRIDOR_NATIVE_ZONE_KEEPOUTS',len(corridors)==6 and all(z.GetDoNotAllowZoneFills() for z in corridors),'Six zones natives bloquant les remplissages B'),
check('NO_ADDED_GND_VIA_IN_CORRIDOR',len(inside)==1 and xy(inside[0].GetPosition())==(46.235,48.385),[xy(v.GetPosition()) for v in inside]),
check('BOOTSTRAP_CONNECTED',connected(pad('U102',17),pad('C111',1)) and connected(pad('U102',19),pad('C111',2)),'Bootstrap local BST/SW'),
check('GATES_CONNECTED',connected(pad('U102',18),pad('Q103',4)) and connected(pad('U102',13),pad('Q104',4)),'HO et LO vers MOSFETs'),
check('IN1_WITHOUT_TRACE',not any(not isinstance(t,p.PCB_VIA) and t.GetLayer()==p.In1_Cu for t in b.GetTracks()),'Plan GND de reference intact')]
terminal=[t for t in b.GetTracks() if not isinstance(t,p.PCB_VIA) and t.GetNetname()=='GND' and t.GetLayer()==p.B_Cu and {xy(t.GetStart()),xy(t.GetEnd())}=={(29.4,43.1),(34.5,43.3)}]
checks.append(check('ONE_PGND_TERMINAL_SEGMENT',len(terminal)==1,'Segment B terminal vers via PGND34.5/43.3'))
for t in terminal: b.Remove(t)
b.BuildConnectivity()
checks.append(check('LOW_KELVIN_ISOLATED_BEFORE_PGND',len(terminal)==1 and not(group(ps[2])&group(ps[3])),{'method':'Retrait uniquement en memoire du segment terminal PGND ; aucun SaveBoard','sense_cluster_objects':len(group(ps[2])),'cluster':[{'type':x.GetClass(),'xy_mm_local':xy(x.GetPosition())} for x in b.GetConnectivity().GetConnectedItems(ps[2])]}))
result=dict(date='2026-10-02',source=str(source),source_sha256=hashlib.sha256(data).hexdigest(),source_unchanged=source.read_bytes()==data,method='Revue independante physique, sans modification de fichier PCB',checks=checks,passed=all(x['passed'] for x in checks),remaining='Relancer apres toute modification de cuivre. Capacite thermique, charges, transitoires, CEM et DFM restent A valider.',qualification='Courant, thermique, transitoires et CEM restent A valider',reference='https://www.ti.com/lit/ds/symlink/lm5146-q1.pdf ; PGND12, Table6-1, connexion directe cote masse du shunt')
Path(sys.argv[2]).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'source_sha256':result['source_sha256'],'passed':result['passed'],'checks':[{ 'id':x['id'],'passed':x['passed']} for x in checks]},indent=2))
