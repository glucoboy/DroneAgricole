"""Contrôle BRep de la variante20Ah et balayage continu de la course300mm."""
from pathlib import Path
import json,hashlib,itertools,time,re,math
import FreeCAD as A,Part
ROOT=Path(__file__).resolve().parents[4];MEC=ROOT/'hardware/mecanique/cartographe'
START=time.time();SCRIPT_SHA=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
CHECKPOINT=MEC/'verification/integration20Ah_checkpoint_20261003.json'
stage_data={'phase':'initialisation','finalisation_complete':False,'script_sha256':SCRIPT_SHA}
def checkpoint(phase,**values):
 stage_data.update(values);stage_data['phase']=phase;stage_data['elapsed_seconds']=time.time()-START
 CHECKPOINT.write_text(json.dumps(stage_data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(json.dumps({'phase':phase,'elapsed_seconds':round(time.time()-START,1)}),flush=True)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def inter(a,b):
 if not a.BoundBox.intersect(b.BoundBox):return 0
 result=a.common(b)
 return 0 if result.isNull()else result.Volume
checkpoint('ouverture_documents')
top=A.openDocument(str(MEC/'assemblages/Drone_Cartographe_20Ah.FCStd'))
for d in A.listDocuments().values():d.recompute()
hashes={Path(d.FileName):sha(Path(d.FileName))for d in A.listDocuments().values()if d.FileName}
cass=next((d for d in A.listDocuments().values()if Path(d.FileName).stem=='SA02A_Dock20Ah'),None)
if cass is None:cass=next(d for d in A.listDocuments().values()if Path(d.FileName).stem=='SA02_Cassette20Ah_Coulissante')
dock={'document':str(Path(cass.FileName).relative_to(ROOT)).replace('\\','/'),
      'occurrences_liees':sum(o.TypeId=='App::Link'for o in cass.Objects),
      'sha256_au_chargement':hashes[Path(cass.FileName)],
      'ExtractionX_mm':A.Units.Quantity(cass.getObject('Parametres').get('B60')).Value}
assert abs(dock['ExtractionX_mm'])<1e-8,'La vérification doit commencer à ExtractionX=0mm'
stage_data['dock']=dock
cons=json.loads((MEC/'verification/construction_cassette20Ah_20261002.json').read_text(encoding='utf-8'))
if Path(cass.FileName).stem=='SA02A_Dock20Ah':
 moving_links={o.Name:o for o in cass.Objects if o.TypeId=='App::Link'and hasattr(o,'Mobile')and str(o.Mobile).lower()in['oui','true','mobile']}
else:moving_links={o['nom']:cass.getObject(o['nom'])for o in cons['occurrences']if o['mobile']}
moving={n:o.Shape.copy()for n,o in moving_links.items()}
moving_objects={(cass.Name,n)for n in moving}
flags=MEC/'verification/mobiles_dock20Ah_20261002.json'
if flags.exists():
 data=json.loads(flags.read_text(encoding='utf-8'));data=data.get('occurrences',data)if isinstance(data,dict)else data
 for row in data:
  if not row.get('mobile',True):continue
  stem=Path(row['document']).stem
  dd=next(dd for dd in A.listDocuments().values()if Path(dd.FileName).stem==stem)
  name=row.get('occurrence',row.get('nom'));obj=dd.getObject(name)
  assert obj and obj.TypeId=='App::Link',(stem,name)
  if (dd.Name,name)in moving_objects:continue
  moving[stem+'/'+name]=obj.Shape.copy();moving_links[stem+'/'+name]=obj;moving_objects.add((dd.Name,name))
fixed={};fixed_links={}
for d in A.listDocuments().values():
 if d==top:continue
 # Chaque occurrence de feuille une seule fois, pas les arbres de fabrication.
 if 'sous_assemblages'not in Path(d.FileName).parts:continue
 for o in d.Objects:
  if o.TypeId!='App::Link'or not hasattr(o,'Shape')or o.Shape.isNull():continue
  if (d.Name,o.Name)in moving_objects:continue
  if o.LinkedObject.TypeId=='App::Part'and 'sous_assemblages'in Path(o.LinkedObject.Document.FileName).parts:continue
  fixed[d.Name+'/'+o.Name]=o.Shape.copy();fixed_links[d.Name+'/'+o.Name]=o
all_links={**moving_links,**fixed_links}
def te_kind(name):
 obj=all_links[name];stem=Path(obj.LinkedObject.Document.FileName).stem
 for number,kind in [('1648151','housing_pin'),('1648156','housing_socket'),('1766283','pin'),('6648335','socket')]:
  if stem.startswith('EQ_TE_'+number):return kind
 return None
def te_functional_pair(first,second):
 a,b=te_kind(first),te_kind(second)
 if a is None or b is None:return False
 if a.startswith('housing')and b.startswith('housing'):return a!=b
 if a.startswith('housing')or b.startswith('housing'):return True
 if {a,b}=={'pin','socket'}:
  # Ne jamais exclure une rencontre entre les deux polarités.
  pole_a=next((p for p in['39Plus','40Moins']if p in first),None)
  pole_b=next((p for p in['39Plus','40Moins']if p in second),None)
  return pole_a is not None and pole_a==pole_b
 return False
def terminal_internal_pair(first,second):
 # Classification des seules bornesM5 assemblées à demeure ; ne doit jamais
 # être utilisée pour ignorer une rencontre mobile/fixe pendant la course.
 for te_name,bolt_name in[(first,second),(second,first)]:
  kind=te_kind(te_name)
  basename=bolt_name.split('/')[-1]
  match=re.fullmatch(r'VisM5ContactMobile([01])',basename)
  if match:
   pole='39Plus'if match.group(1)=='0'else'40Moins'
   if kind=='housing_socket'or(kind=='socket'and pole in te_name):return True
  match=re.fullmatch(r'VisBorneFixe([01])',basename)
  if match:
   pole='39Plus'if match.group(1)=='0'else'40Moins'
   if kind=='housing_pin'or(kind=='pin'and pole in te_name):return True
 return False
te_pairs=[{'mobile':n,'fixe':m,'sources':[Path(moving_links[n].LinkedObject.Document.FileName).stem,Path(fixed_links[m].LinkedObject.Document.FileName).stem],
            'exclusion':'Interfaces fabricant de couplage et cavités contacts ; exclues du certificat de course, volumes bruts conservés ; accouplement physique À valider.'}
           for n in moving for m in fixed if te_functional_pair(n,m)]
te_pair_keys={(x['mobile'],x['fixe'])for x in te_pairs}
errors=[{'document':d.Name,'objet':o.Name,'etat':list(o.State)}for d in A.listDocuments().values()for o in d.Objects if 'Invalid'in o.State]
closed=[]
for n,a in moving.items():
 for m,b in fixed.items():
  v=inter(a,b)
  if v>1e-6:closed.append({'mobile':n,'fixe':m,'volume_mm3':v})
checkpoint('position_verrouillee',ferme=closed,paires_fonctionnelles_TE_exclues=te_pairs,
           ferme_hors_interfaces_TE=[x for x in closed if (x['mobile'],x['fixe'])not in te_pair_keys],
           hashes={str(p.relative_to(ROOT)).replace('\\','/'):h for p,h in hashes.items()})
dock_fixed={n:s for n,s in fixed.items()if n.startswith(('SA02_Cassette20Ah','SA02A_Dock20Ah','SA02_Contacts20Ah'))}
fixture_collisions=[]
for n,a in dock_fixed.items():
 for m,b in fixed.items():
  if m in dock_fixed or m==n:continue
  v=inter(a,b)
  if v>1e-6:fixture_collisions.append({'dock_fixe':n,'fixe_externe':m,'volume_mm3':v})
checkpoint('fixes_dock_vs_drone',fixes=fixture_collisions)
internal=[]
for (n,a),(m,b)in itertools.combinations({**moving,**dock_fixed}.items(),2):
 v=inter(a,b)
 if v>1e-6:internal.append({'a':n,'b':m,'volume_mm3':v})
checkpoint('internes_dock',internes=internal,internes_hors_interfaces_TE=[x for x in internal if not te_functional_pair(x['a'],x['b'])],
           interfaces_internes_bornes_M5_brutes=[x for x in internal if terminal_internal_pair(x['a'],x['b'])],
           internes_hors_interfaces_commerciales_et_bornes_M5=[x for x in internal if not te_functional_pair(x['a'],x['b'])and not terminal_internal_pair(x['a'],x['b'])])
print(json.dumps({'phase':'assemblage','ferme':len(closed),'fixes':len(fixture_collisions),'internes':len(internal)}),flush=True)
sweeps=[];sweep_hits=[];certified={};dense_pruned=0;dense_booleans=0
for n,s in moving.items():
 parts=[s];face_errors=[];degenerate=0;fallback_faces=[]
 for i,f in enumerate(s.Faces):
  try:
   e=f.extrude(A.Vector(300,0,0))
   if e.Volume>1e-7:
    if not e.isValid():raise ValueError('Extrusion invalide')
    parts.append(e)
   else:degenerate+=1
  except Exception as exc:
   bb=f.BoundBox
   # Cette boîte contient toute la face et sa translation, pas uniquement
   # quelques sommets ; seul un résultat nul peut certifier la paire.
   eps=1e-6
   fallback=Part.makeBox(bb.XLength+300+2*eps,max(bb.YLength,eps)+2*eps,max(bb.ZLength,eps)+2*eps,
                          A.Vector(bb.XMin-eps,bb.YMin-eps,bb.ZMin-eps))
   parts.append(fallback);fallback_faces.append({'face':i,'bbox_source_mm':[bb.XMin,bb.XMax,bb.YMin,bb.YMax,bb.ZMin,bb.ZMax]})
   face_errors.append({'face':i,'erreur':str(exc),'couverture_conservatrice_continue':'Boîte de la face étendue de300mm selon+X'})
 comp=Part.makeCompound(parts)
 row={'mobile':n,'faces':len(s.Faces),'solides_extrudes':len(parts)-1-len(fallback_faces),'faces_volume_nul':degenerate,'erreurs_faces':face_errors,'boites_faces_secours':fallback_faces,'intersections':[],
      'paires_fonctionnelles_TE_hors_certificat':[m for a,m in te_pair_keys if a==n]}
 source=moving_links[n].LinkedObject.Document
 if face_errors and Path(source.FileName).stem in['P31_CaptureCassette20Ah','P32_CapG10Capture20Ah']:
  prefixes=['Paroi','Extremite','Bossage']if Path(source.FileName).stem.startswith('P31')else['BandeLongitudinale','OreilleCap']
  conservative=[]
  for obj in source.Objects:
   if obj.TypeId!='Part::Box'or not obj.Name.startswith(tuple(prefixes)):continue
   bsh=obj.Shape.copy();bsh.Placement=moving_links[n].LinkPlacement.multiply(bsh.Placement)
   bb=bsh.BoundBox
   conservative.append(Part.makeBox(bb.XLength+300,bb.YLength,bb.ZLength,A.Vector(bb.XMin,bb.YMin,bb.ZMin)))
  comp=Part.makeCompound(conservative)
  row['couverture_continue_de_secours']={'type':'Enveloppes prismatiques de toutes primitives positives, trous soustractifs volontairement pleins','primitives':len(conservative),'conservatrice':True}
 if Path(source.FileName).stem.startswith('EQ_LeadPack8AWG_'):
  bb=s.BoundBox;clipped=[];envelopes=[];slice_rows=[];clip_errors=[]
  count=max(1,int(math.ceil(bb.XLength/5)))
  for j in range(count):
   x0=bb.XMin+min(j*5,bb.XLength);x1=bb.XMin+min((j+1)*5,bb.XLength)
   slab=Part.makeBox(x1-x0,bb.YLength+2,bb.ZLength+2,A.Vector(x0,bb.YMin-1,bb.ZMin-1))
   try:
    part=s.common(slab)
    if part.isNull()or part.Volume<1e-8:continue
    if not part.isValid():raise ValueError('TrancheBRepinvalide')
    clipped.append(part);pb=part.BoundBox
    envelope=Part.makeBox(pb.XLength+300,pb.YLength,pb.ZLength,A.Vector(pb.XMin,pb.YMin,pb.ZMin));envelopes.append(envelope)
    slice_rows.append({'intervalle_X_mm':[x0,x1],'bbox_piece_mm':[pb.XMin,pb.XMax,pb.YMin,pb.YMax,pb.ZMin,pb.ZMax],'volume_piece_mm3':part.Volume})
   except Exception as exc:clip_errors.append({'intervalle_X_mm':[x0,x1],'erreur':str(exc)})
  uncovered=s.cut(Part.makeCompound(clipped)).Volume if clipped else s.Volume
  row['decoupage_fils_BRep']={'pas_X_max_mm':5,'tranches':slice_rows,'erreurs':clip_errors,'volume_source_mm3':s.Volume,'volume_non_couvert_mm3':uncovered}
  if not clip_errors and uncovered<1e-6:
   comp=Part.makeCompound(envelopes)
   row['couverture_continue_de_secours']={'type':'Prismes des boîtes de chaque trancheBRep exacte≤5mm suivantX, prolongés300mm suivant+X','primitives':len(envelopes),'conservatrice':True}
 for m,b in fixed.items():
  if (n,m)in te_pair_keys:continue
  complete=True
  if not comp.BoundBox.intersect(b.BoundBox):
   if complete:certified[n,m]=True
   continue
  try:
   v=inter(comp,b)
   if v>1e-6:row['intersections'].append({'fixe':m,'volume_mm3':v});sweep_hits.append({'mobile':n,'fixe':m,'volume_mm3':v})
   elif complete:certified[n,m]=True
  except Exception as exc:
   fallback_errors=[];fallback_volume=0;checks=0
   # Certaines unions non fusionnées de nombreux solides provoquent un
   # échecOCC. Leur test unitaire conserve la même couverture de mouvement.
   for solid in comp.Solids:
    if not solid.BoundBox.intersect(b.BoundBox):continue
    try:
     if not solid.isValid():raise ValueError('Solide de couverture invalide')
     fallback_volume+=inter(solid,b);checks+=1
    except Exception as inner:fallback_errors.append(str(inner))
   resolved=not fallback_errors and len(comp.Solids)>0
   row.setdefault('erreurs_commons',[]).append({'fixe':m,'erreur':str(exc),'secours_solides_separes':checks,
                                             'erreurs_secours':fallback_errors,'resolu':resolved,'volume_secours_mm3':fallback_volume})
   if resolved:
    if fallback_volume>1e-6:
     row['intersections'].append({'fixe':m,'volume_mm3':fallback_volume,'mode':'Solides séparés après échecCompound'});sweep_hits.append({'mobile':n,'fixe':m,'volume_mm3':fallback_volume})
    else:certified[n,m]=True
 sweeps.append(row)
 checkpoint('balayage_continu',balayages=sweeps,intersections_balaye=sweep_hits,mobiles_balaye_completes=len(sweeps),mobiles_total=len(moving))
 print(json.dumps({'balayage':n,'intersections':len(row['intersections']),'erreurs_faces':len(face_errors)}),flush=True)
dense_hits=[]
for dx in range(301):
 for n,a in moving.items():
  sh=a.copy();sh.translate(A.Vector(dx,0,0))
  for m,b in fixed.items():
   if (n,m)in te_pair_keys:continue
   if certified.get((n,m)):
    dense_pruned+=1;continue
   if not sh.BoundBox.intersect(b.BoundBox):continue
   dense_booleans+=1
   v=inter(sh,b)
   if v>1e-6:dense_hits.append({'extraction_mm':dx,'mobile':n,'fixe':m,'volume_mm3':v})
 if dx%50==0:print(json.dumps({'pose_mm':dx,'intersections_cumulees':len(dense_hits)}),flush=True)
checkpoint('poses_1mm',intersections_poses_denses=dense_hits,poses_denses=301,pruning_certifie=dense_pruned,booleens_residuels=dense_booleans)
# Données brutes limitées aux interfaces commerciales : aucune conclusion
# d'absence de collision ni de qualification ne découle de leur exclusion.
te_raw=[]
for dx in[0,0.25,0.5,1,2,3,5,8,12,20,30,50,100,200,300]:
 for n,m in sorted(te_pair_keys):
  sh=moving[n].copy();sh.translate(A.Vector(dx,0,0));v=inter(sh,fixed[m])
  te_raw.append({'extraction_mm':dx,'mobile':n,'fixe':m,'volume_brut_mm3':v})
checkpoint('interfaces_TE_brutes',interfaces_TE_brutes=te_raw)
# Hélices absentes duSTEP : enveloppes explicites, non présentées comme pièces fabricant.
motors=[(x,y)for x in[-229.90664,229.90664]for y in[-229.90664,229.90664]]
disks={str(i):Part.makeCylinder(190.5,4,A.Vector(x,y,69.5))for i,(x,y)in enumerate(motors)}
parked={str(i):Part.makeBox(381,40,4,A.Vector(x-190.5,y-20,69.5))for i,(x,y)in enumerate(motors)}
prop_closed=[];prop_parked=[];prop_free=[]
for n,a in moving.items():
 for i,p in disks.items():
  v=inter(a,p)
  if v>1e-6:prop_closed.append({'mobile':n,'rotor':i,'volume_mm3':v})
 for dx in range(301):
  sh=a.copy();sh.translate(A.Vector(dx,0,0))
  for i,p in parked.items():
   v=inter(sh,p)
   if v>1e-6:prop_parked.append({'mobile':n,'pose_mm':dx,'rotor':i,'volume_mm3':v})
  if dx in[0,50,100,150,200,250,300]:
   for i,p in disks.items():
    v=inter(sh,p)
    if v>1e-6:prop_free.append({'mobile':n,'pose_mm':dx,'rotor':i,'volume_mm3':v})
for n,a in fixed.items():
 if not n.startswith(('SA02_Cassette20Ah','SA02A_Dock20Ah','SA02_Contacts20Ah')):continue
 for i,p in disks.items():
  v=inter(a,p)
  if v>1e-6:prop_closed.append({'fixe':n,'rotor':i,'volume_mm3':v})
checkpoint('helices',helices_verrouillees=prop_closed,helices_parquees=prop_parked,helices_orientation_libre=prop_free)
report={'date':'2026-10-02','statut':'À valider','FreeCAD':list(A.Version()),'script_sha256':sha(Path(__file__)),'fichiers_sha256':{str(p.relative_to(ROOT)).replace('\\','/'):h for p,h in hashes.items()},'erreurs_recalcul':errors,'mobiles':len(moving),'fixes':len(fixed),'insertion_course_mm':300,'intersections_position_verrouillee':closed,'intersections_fixes_dock_vs_drone':fixture_collisions,'intersections_internes_dock':internal,'balayages_frontieres_continus':sweeps,'intersections_balaye_continu':sweep_hits,'poses_denses_1mm':301,'pruning_paires_par_certificat_enveloppe_continue':dense_pruned,'booleens_poses_denses_residuels':dense_booleans,'intersections_poses_denses':dense_hits,'helices':{'source':'Diamètre nominal1555:381mm ; pales absentes duSTEP OEM','pales_parquees':'Hypothèse géométrique enveloppe381×40×4, axes parallèlesX, moteurs arrêtés ; largeur à mesurer sur pièces réelles','collisions_verrouille_rotors_tournants':prop_closed,'collisions_insertion_pales_parquees':prop_parked,'collisions_extraction_rotors_orientation_libre':prop_free},'fichiers_inchanges':all(sha(p)==h for p,h in hashes.items()),'limites':['Vérification géométrique des volumes représentés ; aucun essai physique ni qualification de vol.','Loquet commercial réduit à interfaces : ressort/cliquet/course des stages non simulés.','RTK maillé exclu des contrôles BRep ; pales stationnaires doivent être positionnées et leur largeur réelle vérifiée.','Tolérances fabrication, contacteurs, faisceaux et accessibilité selon fichiers effectivement présents ; ajout de contacts exige relance.']}
uncertified=[{'mobile':n,'fixe':m}for n in moving for m in fixed if (n,m)not in te_pair_keys and not certified.get((n,m))]
report.update({'date':'2026-10-03','script_sha256':SCRIPT_SHA,'dock':dock,'paires_fonctionnelles_TE_exclues_du_certificat':te_pairs,
               'interfaces_TE_15_poses_donnees_brutes':te_raw,
               'intersections_position_verrouillee_hors_TE':[x for x in closed if (x['mobile'],x['fixe'])not in te_pair_keys],
               'intersections_internes_dock_hors_TE':[x for x in internal if not te_functional_pair(x['a'],x['b'])],
               'interfaces_internes_bornes_M5_donnees_brutes':[x for x in internal if terminal_internal_pair(x['a'],x['b'])],
               'intersections_internes_hors_TE_et_bornes_M5':[x for x in internal if not te_functional_pair(x['a'],x['b'])and not terminal_internal_pair(x['a'],x['b'])],
               'paires_hors_TE_non_certifiees_continument':uncertified,
               'certificat_course_hors_interfaces_TE_complet':not uncertified and not errors,
               'finalisation_correcte':report['fichiers_inchanges'] and sha(Path(__file__))==SCRIPT_SHA,
               'elapsed_seconds':time.time()-START})
report['limites'] +=[
 'Les paires TE fabricant listées sont exclues du certificat de course : guides STEP et contacts internes représentés produisent des volumes bruts non nuls. Ces données ne prouvent pas un accouplement physique sans blocage.',
 'Pour chaque face OCC non extrudable, une boîte contenant la face et toute sa translation300mm assure une couverture conservatrice. Un volume nul certifie une paire ; un volume positif peut rester un faux positif et aucune qualification ne découle de301positions libres.',
 'Le rayon nominalR11,5mm et la pose des ports du faisceau stockJETI restent des hypothèses d’encombrement : les documents disponibles ne cotent pas ce trajet ni un rayon minimum autorisé. Mesurer le faisceau réel et valider torsion/courbure, efforts sur ports et courant au prototype.'
]
report['limites'].append('Les quatre liaisons permanentesM5 des contactsTE avec leurs vis produisent des chevauchements internes de représentations de filets/cavités. Les paires et volumes bruts sont séparés du bilan interne ; aucune vis ni aucun support ne sont exclus du contrôle mobile/fixe de course. Cela ne qualifie ni montage réel, ni couple, ni tenue électrique.')
report['resultats_numeriques_hors_interfaces_TE']={
 'position_verrouillee_libre':not report['intersections_position_verrouillee_hors_TE'],
 'fixes_dock_vs_drone_libres':not fixture_collisions,
 'interne_dock_libre_hors_TE_et_bornes_M5':not report['intersections_internes_hors_TE_et_bornes_M5'],
 'course_continue_certifiee':report['certificat_course_hors_interfaces_TE_complet'],
 'echantillonnage_1mm_libre':not dense_hits,
 'pales_parquees_enveloppe_etude_libres':not prop_parked,
 'rotors_position_verrouillee_libres':not prop_closed}
report['absence_obstacle_hors_interfaces_TE_dans_modeles_representes']=all(report['resultats_numeriques_hors_interfaces_TE'].values())
(MEC/'verification/integration20Ah_20261002.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
checkpoint('termine',finalisation_complete=True,finalisation_correcte=report['finalisation_correcte'],
           resultat=str((MEC/'verification/integration20Ah_20261002.json').relative_to(ROOT)).replace('\\','/'),
           certificat_course_hors_TE=report['certificat_course_hors_interfaces_TE_complet'],paires_non_certifiees=uncertified)
print(json.dumps({'ferme':len(closed),'sweep':len(sweep_hits),'dense':len(dense_hits),'parkees':len(prop_parked),'libres':len(prop_free),'erreurs':len(errors)}),flush=True)

