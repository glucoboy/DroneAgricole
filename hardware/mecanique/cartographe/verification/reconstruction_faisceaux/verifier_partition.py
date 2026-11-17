"""Contrôle BRep de la partition du câble complet et cache des paires invariantes.
Le cache porte les formes sérialisées réelles, jamais seulement leurs volumes.
"""
from autonomie_cao import *
import math,inspect,zipfile
def check_partition(c):
 reader=Reader(COPY);result=read(report(c));file=result['file'];full=reader.shape(file,result.get('object_cable','Cable002'))
 low=reader.shape(file,result.get('object_mobile','Cable'));top=reader.shape(file,result.get('object_fixed','Cable001'))
 for s in (full,low,top):
  if s.isNull() or not s.isValid() or len(s.Solids)!=1 or not math.isfinite(s.Volume) or s.Volume<=0:raise RuntimeError('Solide de partition invalide')
 props=reader.xml(file)[1][result.get('object_cable','Cable002')];base=props['Base'].find('Link').get('value');actual_length=reader.shape(file,base).Length
 if base!=result.get('object_path','CompoundPath') or abs(actual_length-result['length_mm'])>1e-5:raise RuntimeError('Mauvais câble complet')
 union=Part.makeCompound([low,top]);removed=full.cut(union);added=union.cut(full)
 if not all(math.isfinite(v) for v in (removed.Volume,added.Volume)) or (not removed.isNull() and not removed.isValid()) or (not added.isNull() and not added.isValid()) or removed.Volume>1e-4 or added.Volume>1e-4:raise RuntimeError('Partition non équivalente au câble complet')
 overlap_shape=low.common(top)
 if not overlap_shape.isNull() and not overlap_shape.isValid():raise RuntimeError('Intersection interne invalide')
 overlap=overlap_shape.Volume
 if not math.isfinite(overlap):raise RuntimeError('Volume non fini')
 if overlap>1e-4:raise RuntimeError('Partition double compte du volume')
 result['partition']={'full_object':result.get('object_cable','Cable002'),'mobile_object':result.get('object_mobile','Cable'),'fixed_object':result.get('object_fixed','Cable001'),'removed_mm3':removed.Volume,'added_mm3':added.Volume,'internal_overlap_mm3':overlap,'method':'Différences volumiques bilatérales des BRep nominaux; pas borne de Hausdorff ni couverture continue de mouvement'}
 cachefile=OUT/'cache_paires_fixes.json';cache=read(cachefile) if cachefile.exists() else {};cache_hits=0
 method=hashlib.sha256((inspect.getsource(measured_pair)+inspect.getsource(Reader)+inspect.getsource(transform)+str(App.Version())+str(Part.OCC_VERSION)).encode()).hexdigest()
 shapeentry=reader.xml(file)[1][result.get('object_fixed','Cable001')]['Shape'].find('Part').get('file')
 with zipfile.ZipFile(COPY/file) as archive:topkey=method+':'+hashlib.sha256(archive.read(shapeentry)).hexdigest()
 # OCCT réordonne parfois une sérialisation en mémoire. Les BRep sauvegardés
 # et la fermeture native empreintée sont les entrées exactes de Reader.
 inputs=set(read(COPY/'experiment.json')['inputs_sha256'])
 inputs.update(r['source'] for r in read(COPY/'verification/construction_prototype.json')['occurrences'])
 pending=list(inputs)
 while pending:
  f=pending.pop()
  if not f.endswith('.FCStd'):continue
  _,objects=reader.xml(f)
  for props in objects.values():
   link=props.get('LinkedObject')
   if link is None:continue
   x=link.find('XLink')
   if x is None or not x.get('file'):continue
   target=((COPY/f).parent/x.get('file')).resolve()
   if not target.is_relative_to(COPY):raise RuntimeError('XLink hors copie')
   rel=target.relative_to(COPY).as_posix()
   if rel not in inputs:inputs.add(rel);pending.append(rel)
 scene_sources={p:sha(COPY/p) for p in sorted(inputs) if p.endswith('.FCStd')}
 scene=hashlib.sha256(json.dumps(scene_sources,sort_keys=True).encode()).hexdigest()
 build=read(COPY/'verification/construction_prototype.json');kin=read(OUT/'recherche_suspension.json')['kinematics'];pose=transform(c)
 checks=[];minimum=None;noncontact=None;count=0;bb=0
 for row in build['occurrences']:
  if not row['parent'].startswith('sous_assemblages/') or row['occurrence']=='F16':continue
  name=row['occurrence'];s=reader.occurrence(row);count+=1
  moving=('SA04' in row['parent'] and name in kin['mobile_sa04_occurrences']) or ('SA07' in row['parent'] and name in kin['mobile_sa07_occurrences'])
  if moving:s.Placement=pose.multiply(s.Placement)
  lower=gap(full.BoundBox,s.BoundBox)
  if lower>0:bb+=1
  if lower>1e-6 and noncontact is not None and lower>noncontact+1e-6:continue
  try:
   key=topkey+':'+hashlib.sha256((scene+json.dumps(row,sort_keys=True)+(json.dumps({'t':c['translation_mm'],'r':c['rotation_xyz_deg'],'p':c['rotation_center_mm']},sort_keys=True) if moving else '')).encode()).hexdigest()
   if key in cache:pt=cache[key];cache_hits+=1
   else:pt=measured_pair(top,s);cache[key]=pt
   pl=measured_pair(low,s)
   p={'obstacle':row['parent']+'#'+name,'moving':moving,'volume_mm3':pt['volume_mm3']+pl['volume_mm3'],'distance_mm':min(pt['distance_mm'],pl['distance_mm']),'segments':{'mobile':pl,'fixed':pt}}
   minimum=min(minimum if minimum is not None else 1e99,p['distance_mm'])
   if name not in ('ConnecteurF16Camera','ConnecteurF16TypeA'):noncontact=min(noncontact if noncontact is not None else 1e99,p['distance_mm'])
   checks.append(p)
  except Exception as ex:checks.append({'obstacle':name,'error':str(ex)})
 result['collision']={'complete':True,'object_cable':result.get('object_cable','Cable002'),'partition_verified':True,'cache_hits':cache_hits,'path_length_verified_mm':result['length_mm'],'occurrences':count,'bbox_disjoint':bb,'pairs':checks,'collisions':sum(p.get('volume_mm3',0)>1e-4 for p in checks),'unknown':sum('error'in p for p in checks),'minimum_mm':minimum,'non_connector_minimum_mm':noncontact,'tolerance_volume_mm3':1e-4,'clearance_acceptance_mm':None,'scope':'Câble entier par partition BRep équivalente. Obstacles mobiles transformés; autres câbles inchangés. Cache de paires fixes par empreintes exactes BRep des deux formes.'}
 result['collision']['scene_digest']=scene;result['collision']['cache_method']=method
 result['collision']['scene_sources_sha256']=scene_sources
 result['collision']['scope']='Câble entier par partition BRep équivalente. Obstacles mobiles transformés; autres câbles inchangés. Cache par BRep fixe sauvegardé, fermeture native complète empreintée, occurrence et pose exacte.'
 write(cachefile,cache);write(report(c),result);print(c['id'],result['collision']['collisions'],'cache',cache_hits,flush=True)
if __name__=='__main__':
 try:check_partition(read(sys.argv[1])['candidates'][int(sys.argv[2])]);sys.stdout.flush();sys.stderr.flush();os._exit(0)
 except Exception:traceback.print_exc();sys.stdout.flush();sys.stderr.flush();os._exit(2)
