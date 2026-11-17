"""Adaptation native paramétrique locale, exclusivement dans la copie autorisée."""
from autonomie_cao import *
from workspace_guard import verify_sources
import math
CFG=OUT/'adaptation_f38.json'
GUIDE='pieces/fabriquees/P73_Guide_Faisceau_Droit_Prototype.FCStd'

def box(doc,name,values):
 x,y,z,l,w,h=values;o=doc.addObject('Part::Box',name);o.Length=l;o.Width=w;o.Height=h;o.Placement.Base=App.Vector(x,y,z);return o

def capsule(doc,name,r,c):
 x=c['points'][0][0];z=c['center_z_mm'];ys=c['centers_y_mm'];length=c['length_mm'];objs=[]
 for i,y in enumerate(ys):
  o=doc.addObject('Part::Cylinder',name+'Bout'+str(i));o.Radius=r;o.Height=length;o.Placement=App.Placement(App.Vector(x,y,z),App.Rotation(App.Vector(0,0,1),App.Vector(1,0,0)));objs.append(o)
 objs.append(box(doc,name+'Milieu',[x,ys[0],z-r,length,ys[1]-ys[0],2*r]))
 f=doc.addObject('Part::MultiFuse',name);f.Shapes=objs;f.Refine=True;return f

def preservation():
 return {'original':verify_sources(read(ROOT/'hardware/mecanique/cartographe_faisceaux/experiment.json')),'baseline':verify_sources(read(COPY/'experiment.json'))}

def guide():
 gui();c=read(CFG);target=COPY/GUIDE;before=sha(target);doc=App.openDocument(str(target));root=doc.getObject('Ensemble');fusion=doc.getObject('GuideAvecRetenuesLocales');final=doc.getObject('ResultatPassagesReprise');saved=final.Shape.copy()
 if doc.getObject('PontF38Pos'):raise RuntimeError('Adaptation déjà appliquée')
 removed=['DoigtUSB3Ajoure','DoigtUSB3Ajoure001','DoigtUSB33'];fusion.Shapes=[o for o in fusion.Shapes if o.Name not in removed]
 for n in removed:doc.getObject(n).Visibility=False
 power=doc.getObject('GuideAvecRetenuesPuissance');replacement={}
 for n,y in zip(['RubanF38Pos','RubanF38Neg'],c['guide_bridge_y_local_mm']):
  cut=box(doc,'Degagement'+n,c['guide_cut_local']);sub=doc.addObject('Part::Cut','RailOuvert'+n);sub.Base=doc.getObject(n);sub.Tool=cut
  bridge=box(doc,'Pont'+n,[c['guide_bridge_x_local_mm'],y,c['guide_bridge_bottom_z_mm'],c['guide_bridge_length_mm'],c['guide_bridge_width_mm'],c['guide_bridge_height_mm']])
  f=doc.addObject('Part::MultiFuse','PontF38'+('Pos' if n.endswith('Pos') else 'Neg'));f.Shapes=[sub,bridge];f.Refine=True;replacement[n]=f
  for o in [cut,sub,bridge,f]:root.addObject(o);o.Visibility=False
 power.Shapes=[replacement.get(o.Name,o) for o in power.Shapes]
 spec=json.loads(root.RetenuesLocales);spec['stations']=[s for s in spec['stations'] if s['id']=='F16_V_75'];spec['colliers_cables']=1;spec['stations_liberees']=['F16_V_-45','F16_V_0','F16_V_35'];spec['limites'].append('Boucle F16 R50 sous station75; retenue/efforts physiques à valider');root.RetenuesLocales=json.dumps(spec,ensure_ascii=False)
 root.addProperty('App::PropertyString','AdaptationF38','Conception');root.AdaptationF38=json.dumps(c,ensure_ascii=False)
 ok=doc.recompute();solid=inspect_solid(final.Shape);errors=[o.Name for o in doc.Objects if any(s in ('Error','Invalid') for s in o.State)]
 if not ok or final.Shape.isNull() or not final.Shape.isValid() or len(final.Shape.Solids)!=1 or errors:raise RuntimeError('Guide invalide '+str(solid)+str(errors))
 for o in doc.Objects:
  if hasattr(o,'Shape') and o!=final:o.Visibility=False
 final.Visibility=True;root.Visibility=True;doc.recompute();doc.save()
 write(OUT/'guide_autonomie.json',{'file':GUIDE,'before_sha256':before,'after_sha256':sha(target),'parameters':c,'recompute':ok,'solid':solid,'errors':errors,'removed_stations':spec['stations_liberees'],'preservation':preservation(),'added_local_volume_mm3':final.Shape.cut(saved).Volume,'removed_local_volume_mm3':saved.cut(final.Shape).Volume,'status':'CANDIDAT_CONDITIONNEL'})

def generate():
 gui();c=read(CFG);doc=App.newDocument(c['id']);outer=capsule(doc,'Exterieur',c['inner_radius_mm']+c['wall_mm'],c);inner=capsule(doc,'Interieur',c['inner_radius_mm'],c);wall=doc.addObject('Part::Cut','Protection');wall.Base=outer;wall.Tool=inner;wall.Refine=True
 wall.addProperty('App::PropertyString','Hypotheses','Conception');wall.Hypotheses=json.dumps(c,ensure_ascii=False);ok=doc.recompute()
 for o in doc.Objects:o.Visibility=False
 wall.Visibility=True;wall.ViewObject.ShapeColor=(.2,.7,.3);p=COPY/'verification/candidats'/(c['id']+'.FCStd');doc.saveAs(str(p))
 write(OUT/('protection_'+c['id']+'.json'),{'id':c['id'],'parameters':c,'file':str(p.relative_to(COPY)),'object':wall.Name,'sha256':sha(p),'parameters_sha256':sha(CFG),'recompute_return':ok,'solid':inspect_solid(wall.Shape),'complete':False,'representation':'Paroi capsule paramétrique par primitives Part natives, pas conduit circulaire CableConduit; profil textile hypothétique'})

def check():
 c=read(CFG);r=read(OUT/('protection_'+c['id']+'.json'));reader=Reader(COPY);wall=reader.shape(r['file'],r['object']);inner=reader.shape(r['file'],'Interieur');axial=Part.makeBox(c['length_mm'],2000,2000,App.Vector(c['points'][0][0],-1000,-1000));rows=read(COPY/'verification/construction_prototype.json')['occurrences'];pairs=[];inc=[]
 for row in rows:
  if not row['parent'].startswith('sous_assemblages/') or row['occurrence']=='ProtectionF38':continue
  s=reader.occurrence(row)
  if row['occurrence']=='F16':
   f=read(report(read(OUT/'selection_f16.json')));s=reader.shape(f['file'],f.get('object_cable','Cable002'))
  if row['occurrence'] not in c['members'] and gap(wall.BoundBox,s.BoundBox)>3:continue
  if s.isNull() or not s.isValid() or not s.Solids:raise RuntimeError('Obstacle invalide '+row['occurrence'])
  if row['occurrence'] in c['members']:
   if s.BoundBox.YMin<=-1000 or s.BoundBox.YMax>=1000 or s.BoundBox.ZMin<=-1000 or s.BoundBox.ZMax>=1000:raise RuntimeError('Tranche insuffisante')
   section=s.common(axial);outside=section.cut(inner);contact=s.common(wall)
   if section.isNull() or not section.isValid() or section.Volume<=0 or not math.isfinite(outside.Volume) or (not outside.isNull() and not outside.isValid()):raise RuntimeError('Inclusion indéterminée')
   inc.append({'member':row['occurrence'],'section_volume_mm3':section.Volume,'outside_inner_mm3':outside.Volume,'wall_intersection_mm3':contact.Volume,'wall_distance_mm':s.distToShape(wall)[0]})
  p=measured_pair(wall,s);p['obstacle']=row['parent']+'#'+row['occurrence'];pairs.append(p)
 if {x['member'] for x in inc}!=set(c['members']):raise RuntimeError('Membre absent')
 sources={x['source'] for x in rows};sources.add('verification/candidats/F16_R50_X200_Z0.FCStd');r.update(pairs=pairs,inclusion=inc,complete=True,collisions=sum(x['volume_mm3']>1e-4 for x in pairs),unknown=0,scene_sources_sha256={s:sha(COPY/s) for s in sorted(sources)},scope='Paroi contre toutes occurrences sauf F16 baseline remplacé par candidat; inclusion des deux conducteurs dans tranche axiale réelle. Tolérances et colliers non représentés.')
 write(OUT/('protection_'+c['id']+'.json'),r);print('PROTECTION',r['collisions'],inc,flush=True)

def verify_guide():
 reader=Reader(COPY);baseline=Reader(ROOT/'hardware/mecanique/cartographe_faisceaux');new=reader.shape(GUIDE,'Ensemble');old=baseline.shape(GUIDE,'Ensemble');added=new.cut(old)
 if not added.isValid():raise RuntimeError('Différence guide invalide')
 rows=read(COPY/'verification/construction_prototype.json')['occurrences'];pairs=[]
 for row in rows:
  if not row['parent'].startswith('sous_assemblages/') or row['occurrence']=='P73_Guide':continue
  s=reader.occurrence(row)
  if gap(added.BoundBox,s.BoundBox)>1e-6:continue
  p=measured_pair(added,s);p['obstacle']=row['parent']+'#'+row['occurrence'];pairs.append(p)
 result=read(OUT/'guide_autonomie.json');result['added_material_check']={'volume_mm3':added.Volume,'pairs':pairs,'collisions':sum(x['volume_mm3']>1e-4 for x in pairs),'scope':'Ajout de matière seulement contre toutes occurrences; retrait ne peut ajouter de collision. F16 candidat contrôlé séparément.'};write(OUT/'guide_autonomie.json',result);print(result['added_material_check'],flush=True)

def reopen():
 gui();c=read(CFG);r=read(OUT/('protection_'+c['id']+'.json'));doc=App.openDocument(str(COPY/r['file']));wall=doc.getObject(r['object']);saved=wall.Shape.copy()
 for o in doc.Objects:
  if hasattr(o,'Shape'):o.Shape=Part.Shape();o.touch()
 ok=doc.recompute();r['reopened']={'recompute':ok,'solid':inspect_solid(wall.Shape),'removed_mm3':saved.cut(wall.Shape).Volume,'added_mm3':wall.Shape.cut(saved).Volume,'errors':[o.Name for o in doc.Objects if any(s in ('Error','Invalid') for s in o.State)]};write(OUT/('protection_'+c['id']+'.json'),r)
 doc=App.openDocument(str(COPY/GUIDE));final=doc.getObject('ResultatPassagesReprise');saved=final.Shape.copy()
 for o in doc.Objects:o.touch()
 ok=doc.recompute();r=read(OUT/'guide_autonomie.json');r['reopened']={'recompute':ok,'solid':inspect_solid(final.Shape),'removed_mm3':saved.cut(final.Shape).Volume,'added_mm3':final.Shape.cut(saved).Volume,'errors':[o.Name for o in doc.Objects if any(s in ('Error','Invalid') for s in o.State)]};write(OUT/'guide_autonomie.json',r)

def delta_poses():
 """Contrôle conservateur des seuls obstacles nouveaux dans les 27 poses."""
 reader=Reader(COPY)
 base=Reader(ROOT/'hardware/mecanique/cartographe_faisceaux')
 old=base.shape(GUIDE,'Ensemble')
 new=reader.shape(GUIDE,'Ensemble')
 added=new.cut(old)
 if added.isNull() or not added.isValid() or not math.isfinite(added.Volume):
  raise RuntimeError('Ajout P73 non mesurable')
 cfg=read(CFG)
 protection=read(OUT/('protection_'+cfg['id']+'.json'))
 wall=reader.shape(protection['file'],protection['object'])
 obstacles={'P73_matiere_ajoutee':added,'ProtectionF38':wall}
 build=read(COPY/'verification/construction_prototype.json')
 kin=read(OUT/'recherche_suspension.json')['kinematics']
 mobile=[]
 for row in build['occurrences']:
  parent=row['parent'];name=row['occurrence']
  if ('SA04' in parent and name in kin['mobile_sa04_occurrences']) or ('SA07' in parent and name in kin['mobile_sa07_occurrences']):
   mobile.append((name,reader.occurrence(row)))
 if len(mobile)!=31 or any(s.isNull() or not s.isValid() or not s.Solids for _,s in mobile):
  raise RuntimeError('Liste des solides rigides mobiles invalide')
 receipt=read(COPY/'experiment.json')['inputs_sha256']
 original_digest=hashlib.sha256(json.dumps({p:h for p,h in sorted(receipt.items()) if p.endswith('.FCStd')},sort_keys=True).encode()).hexdigest()
 changed={p for p,h in receipt.items() if p.endswith('.FCStd') and sha(COPY/p)!=h}
 if not changed<={GUIDE,'assemblages/Prototype_Cartographe.FCStd','sous_assemblages/SA07_Prototype_Faisceaux.FCStd'}:
  raise RuntimeError('Autres formes natives modifiées: '+str(changed))
 rows=[]
 for pose in read(OUT/'poses_autonomie.json')['candidates']:
  f=read(report(pose))
  if f['collision']['scene_digest']!=original_digest or sha(COPY/f['file'])!=f['sha256'] or not f['collision']['partition_verified']:
   raise RuntimeError('Preuve de pose non rattachée à la scène initiale')
  cables=[(name,reader.shape(f['file'],f.get('object_'+name,default))) for name,default in [('mobile','Cable'),('fixed','Cable001')]]
  rigid=[]
  for name,source in mobile:
   s=source.copy();s.Placement=transform(pose).multiply(s.Placement);rigid.append((name,s))
  result={'id':pose['id'],'f16_sha256':f['sha256'],'bbox_disjoint_pairs':0,'brep_pairs':[]}
  for name,s in cables+rigid:
   for other,t in obstacles.items():
    if gap(s.BoundBox,t.BoundBox)>1e-6:result['bbox_disjoint_pairs']+=1
    else:result['brep_pairs'].append({'pair':[name,other],**measured_pair(s,t)})
  result['collisions']=sum(p['volume_mm3']>1e-4 for p in result['brep_pairs']);rows.append(result)
 write(OUT/'delta_poses_autonomie.json',{'poses':rows,'baseline_digest':original_digest,'new_obstacles_sha256':{p:sha(COPY/p) for p in [GUIDE,protection['file']]},'collisions':sum(r['collisions'] for r in rows),'rigid_solids_count':len(mobile),'scope':'Absence de nouvelles intersections aux 27 poses, par différence P73 et contrôle paroi F38. Le retrait de matière peut réduire une intersection, sans en créer. Aucun contrôle continu.'})

if __name__=='__main__':
 try:globals()[sys.argv[1]]();sys.stdout.flush();sys.stderr.flush();os._exit(0)
 except Exception:traceback.print_exc();sys.stdout.flush();sys.stderr.flush();os._exit(2)
