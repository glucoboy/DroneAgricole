"""Infrastructure : vérifier l'instantané fabricant candidat, sans libération.
À exécuter après les exports CLI et vérifications du PCB courant.
"""
import collections,csv,hashlib,json,re
from pathlib import Path
import pcbnew as p
C=Path(__file__).resolve().parents[1];F=C/'fabrication';E=F/'exports_provisoires_20261002'
read=lambda f:json.loads(f.read_text(encoding='utf-8-sig'))
sha=lambda f:hashlib.sha256(f.read_bytes()).hexdigest()
def write(f,v):f.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
b=p.LoadBoard(str(C/'CA01_Avionique.kicad_pcb'));fps={f.GetReference():f for f in b.GetFootprints()};checks=[]
def check(code,ok,details):checks.append({'id':code,'passed':bool(ok),'details':details})
job=read(E/'gerber/CA01_Avionique-job.gbrjob')
check('GERBER_COUCHES',len(job['FilesAttributes'])==11 and job['GeneralSpecs']['LayerNumber']==4 and job['GeneralSpecs']['BoardThickness']==1.6 and all((E/'gerber'/v['Path']).is_file() for v in job['FilesAttributes']),{'plot_files':len(job['FilesAttributes']),'layers':job['GeneralSpecs']['LayerNumber'],'bbox_including_edge_line_mm':job['GeneralSpecs']['Size'],'nominal_outline_centreline_mm':[126,80],'finish_in_job':job['GeneralSpecs']['Finish']})
native={'PTH':[],'NPTH':[]}
for t in b.GetTracks():
    if isinstance(t,p.PCB_VIA):native['PTH'].append((p.ToMM(t.GetPosition().x)-50,50-p.ToMM(t.GetPosition().y),p.ToMM(t.GetDrill())))
for f in fps.values():
    for q in f.Pads():
        if not q.GetDrillSize().x:continue
        assert q.GetDrillSize().x==q.GetDrillSize().y,'Slot à traiter explicitement'
        kind='NPTH' if q.GetAttribute()==p.PAD_ATTRIB_NPTH else 'PTH'
        native[kind].append((p.ToMM(q.GetPosition().x)-50,50-p.ToMM(q.GetPosition().y),p.ToMM(q.GetDrillSize().x)))
tool_table=[]
for kind in ['PTH','NPTH']:
    lines=(E/'percages'/('CA01_Avionique-'+kind+'.drl')).read_text().splitlines();tools={};records=[];selected=None;counts=collections.Counter()
    for line in lines:
        m=re.fullmatch(r'T(\d+)C([\d.]+)',line)
        if m:tools[m[1]]=float(m[2]);continue
        m=re.fullmatch(r'T(\d+)',line)
        if m:selected=m[1];continue
        m=re.fullmatch(r'X([+-]?[\d.]+)Y([+-]?[\d.]+)',line)
        if m:records.append((float(m[1]),float(m[2]),tools[selected]));counts[selected]+=1
    normalize=lambda rows:collections.Counter(tuple(round(v,4) for v in row) for row in rows)
    precision=max(len(v.split('.')[1]) if '.' in v else 0 for line in lines for v in re.findall(r'[XY]([+-]?[\d.]+)',line));resolution=10**(-precision)
    remaining=list(native[kind]); unmatched=[];max_error=0
    for row in records:
        matches=[(i,max(abs(row[0]-q[0]),abs(row[1]-q[1]))) for i,q in enumerate(remaining) if abs(row[2]-q[2])<1e-6 and max(abs(row[0]-q[0]),abs(row[1]-q[1]))<=resolution/2+1e-9]
        if not matches:unmatched.append(row);continue
        i,error=min(matches,key=lambda v:v[1]);max_error=max(max_error,error);remaining.pop(i)
    check('EXCELLON_'+kind,not unmatched and not remaining and 'METRIC' in lines,{'count':len(records),'metric':'METRIC' in lines,'max_coordinate_rounding_mm':max_error,'observed_export_resolution_mm':resolution,'comparison_tolerance_mm':resolution/2,'unmatched_export':unmatched[:10],'unmatched_native':remaining[:10],'local_export_axes':'X droite, Y opposé au Y CAO, origine auxiliaire(50,50) de CAO'})
    tool_table.extend({'file':kind,'tool':'T'+k,'nominal_cao_hole_mm':d,'count':counts[k],'production_tool_diameter_mm':None,'finished_hole_tolerance_mm':None} for k,d in tools.items())
with (F/'bom_assemblage_candidate.csv').open(encoding='utf-8-sig',newline='') as f:bom=list(csv.DictReader(f))
mounted={v['reference'] for v in bom if v['quantite_candidate']=='1'}
smd={v['reference'] for v in bom if v['quantite_candidate']=='1' and v['type_assemblage']=='SMD'}
for name,expected in [('positions_smd_candidates.csv',smd),('positions_toutes_candidates.csv',mounted)]:
    with (E/'assemblage'/name).open(encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
    errors=[]
    for row in rows:
        f=fps[row['Ref']];q=f.GetPosition()
        if abs(float(row['PosX'])-(p.ToMM(q.x)-50))>1e-5 or abs(float(row['PosY'])-(50-p.ToMM(q.y)))>1e-5 or abs((float(row['Rot'])-f.GetOrientationDegrees())%360)>1e-5:errors.append(row['Ref'])
    check('CPL_'+name,{r['Ref'] for r in rows}==expected and len(rows)==len(expected) and not errors,{'count':len(rows),'mismatches':errors,'rotations_pin1_assembly_approval':'À valider assembleur ; cohérence native CAO seulement'})
for row in bom:
    ref=row['reference'];f=fps[ref]
    assert row['empreinte_pcb']==str(f.GetFPID().GetLibNickname())+':'+str(f.GetFPID().GetLibItemName()),ref
    assert (row['dnp_pcb']=='true')==f.IsDNP(),ref
check('BOM_ET_DNP',len(bom)==151 and len(mounted)==141 and len(smd)==136,{'rows':len(bom),'mounted':len(mounted),'smd':len(smd),'tht':len(mounted)-len(smd),'mounted_missing_mpn':sum(v['reference'] in mounted and not v['mpn_bom'] for v in bom)})
# IPC names are abbreviated by the native exporter. Preserve an unambiguous alias map.
pad_nets={(f.GetReference(),q.GetNumber()):q.GetNetname() for f in fps.values() for q in f.Pads()}
aliases=collections.defaultdict(set);ipc=(E/'CA01_Avionique_candidate.d356').read_text().splitlines()
for line in ipc:
    if line.startswith(('317','327')) and line[20:26].strip()!='VIA':
        key=(line[20:26].strip(),line[27:31].strip())
        if key in pad_nets:aliases[line[3:17].strip()].add(pad_nets[key])
check('IPC_ALIASES_UNIQUES',ipc[-1]=='999' and all(len(v)==1 for v in aliases.values()),{'alias_count':len(aliases),'units_header':'P  UNITS CUST 0','coordinate_unit_mm':.00254,'origin':'auxiliaire CAO, Y inversé ; enregistrement IPC en0,0001inch','alias_mapping':'ipc_aliases_candidates.csv'})
with (E/'ipc_aliases_candidates.csv').open('w',encoding='utf-8',newline='') as f:
    w=csv.writer(f);w.writerow(['alias_ipc','net_kicad_complet'])
    for alias,names in sorted(aliases.items()):w.writerow([alias,' | '.join(sorted(names))])
for name in ['drc_routage_complet_20261002.json','drc_controles_reactives_20261002.json']:
    d=read(C/'verification'/name);check(name,not d['violations'] and not d['unconnected_items'],{'violations':len(d['violations']),'unconnected':len(d['unconnected_items']),'ignored_checks':len(d.get('ignored_checks',[]))})
review=read(C/'verification/revue_routage_complet_20261002.json');check('REVUE_INDEPENDANTE',review['passed'] and next(v for k,v in review['inputs_sha256'].items() if k.endswith('.kicad_pcb'))==sha(C/'CA01_Avionique.kicad_pcb'),'28 contrôles, SHA PCB courant')
a=read(F/'assemblage_candidate.json');a['inputs_sha256']['CA01_Avionique.kicad_pcb']=sha(C/'CA01_Avionique.kicad_pcb')
for k in a['inputs_sha256']:
    if k.replace('\\','/')=='verification/netlist.xml':a['inputs_sha256'][k]=sha(C/'verification/netlist.xml')
a['snapshot_note']='Instantané final candidat de comparaison BOM/empreintes/DNP/face ; positions dans CPL exports_provisoires_20261002. Aucune release fabricant.';a['declarative_verification']['final_pcb_and_cpl_checked']=True;write(F/'assemblage_candidate.json',a)
c=read(F/'contraintes_fabrication.json');c['drilling']['tool_inventory_final']=tool_table
for family in c['drilling']['known_families']:
    if family['kind']=='PTH via':family['count']=251
    if family['kind']=='PTH connecteurs autres':family.update(count=12,candidate_hole_mm=[1.0,1.7,1.9],note='Quatre trous de chaque diamètre nominal, ronds dans cette version ; diamètres/tolérances et pièces reçues à valider.')
c['board']['reference_origin']='Origine auxiliaire CAO(50,50)mm ; Gerber/Excellon/CPL en repère local X droite/Y opposé au Y CAO. NPTH vérifiés(3,-3),(123,-3),(123,-77),(3,-77).'
c['release_snapshot'].update(date='2026-10-02',status='Brouillon candidat, non libéré',pcb_sha256=sha(C/'CA01_Avionique.kicad_pcb'),config_sha256=sha(C/'routage.json'),export_manifest='export_manifest.json',tool_inventory=tool_table,drc='../verification/drc_routage_complet_20261002.json',erc='../verification/erc.json',unrouted_connections=0,inspection='Contrôles numériques et vues CAO ; DFM/inspection fabricant non exécutés')
write(F/'contraintes_fabrication.json',c)
files=[C/'CA01_Avionique.kicad_pcb',C/'CA01_Avionique.kicad_pro',C/'routage.json',C/'placement_mecanique.json',C/'validation_electrique_thermique_cem.json',C/'verification/routage_complet_20261002.json',C/'verification/revue_routage_complet_20261002.json',C/'verification/erc.json',C/'verification/netlist.xml',C/'verification/drc_controles_reactives_20261002.json',F/'bom_assemblage_candidate.csv',F/'assemblage_candidate.json',F/'contraintes_fabrication.json',Path(__file__)]
manifest={'schema_version':1,'date':'2026-10-02','reference':'CA01','revision':'0.5-pre','status':'Implémenté','qualification':'À valider','release_status':'Exports provisoires, non libérés pour commande','manufacturing_ready':False,'order_placed':False,'assembly_executed':False,'conclusion':'conforme' if all(v['passed'] for v in checks) else 'non conforme','checks':checks,'export_folder':'exports_provisoires_20261002','source_sha256':{str(f.relative_to(C)):sha(f) for f in files},'export_sha256':{str(f.relative_to(F)):sha(f) for f in sorted(E.rglob('*')) if f.is_file()},'tool_table':tool_table,'hole_counts':{k:len(v) for k,v in native.items()},'notes':['Gerber job bounding box126.05×80.05 inclut traitEdgeCuts. Contour nominal centreligne126×80.','Finish None et Revision rev? du job natif ne fixent pas finition/révision industrielle ; candidature ENIG et révision0.5-pre dans les contraintes/manifeste à approuver.','Excellon diamètres CAO nominaux : outils production et diamètres finis compensés/tolérances à confirmer fabricant.','136positionsSMD dont U201/U301 avec trous EP ;141positions totales dont5THT. Pas de DNP/TP/fixations dans CPL.','BOM141pièces dont44MPNmanquants ; aucune commande ni montage autorisé par ces exports.','Comparaison numérique et aperçu de couches ; contrôle fabricant CAM/DFM, coupons/contrôle électrique bare-board et qualification thermique/CEM restent ouverts.']}
write(F/'export_manifest.json',manifest)
print(json.dumps({'conclusion':manifest['conclusion'],'checks':len(checks),'holes':manifest['hole_counts'],'exports':len(manifest['export_sha256']),'failed':[v['id'] for v in checks if not v['passed']]},ensure_ascii=False))
if manifest['conclusion']!='conforme':raise SystemExit(1)
