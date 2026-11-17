"""Mesure BRep des poses discrètes du bloc suspendu contre le matériel fixe."""
from autonomie_cao import *
def run(index):
 c=read(OUT/'poses_autonomie.json')['candidates'][index];reader=Reader(COPY);kin=read(OUT/'recherche_suspension.json')['kinematics'];rows=read(COPY/'verification/construction_prototype.json')['occurrences'];routes={r['id'] for r in read(COPY/'verification/routes_prototype.json')['routes']}
 movable=[];fixed=[]
 for row in rows:
  if not row['parent'].startswith('sous_assemblages/'):continue
  name=row['occurrence'];identity=row['parent']+'#'+name
  if name in routes and 'SA07' in row['parent']:continue
  moving=('SA04' in row['parent'] and name in kin['mobile_sa04_occurrences']) or ('SA07' in row['parent'] and name in kin['mobile_sa07_occurrences'])
  if name.startswith('Appui_') and 'SA04' in row['parent']:
   source=row['source'];pose=App.Placement(App.Matrix(*row['matrice'])).multiply(reader.placement(source,row['objet_source']).inverse())
   for child in ['Support_P17','Manchon_P18','Rondelle_capture_P19','Vis_M2x25','Ecrou_frein_M2']:
    s=reader.shape(source,child);s.Placement=pose.multiply(s.Placement);fixed.append((identity+'/'+child,s))
  else:
   s=reader.occurrence(row)
   if moving:s.Placement=transform(c).multiply(s.Placement);movable.append((identity,s))
   else:fixed.append((identity,s))
 result={'id':c['id'],'parameters':c,'params_sha256':sha(OUT/'poses_autonomie.json'),'moving_count':len(movable),'fixed_count':len(fixed),'pairs_total':len(movable)*len(fixed),'pairs':[],'complete':False,'scope':'31 occurrences rigides mobiles contre fixes. Bague_porteuse/Tampon_rebond exclus nommément: déformation non simulée. Câbles exclus: suivent leurs études de flexion distinctes. Pas une enveloppe continue ni admissibilité élastomère.','distance_search_mm':3}
 if len(movable)!=31 or len({n for n,s in movable})!=31:raise RuntimeError('Liste mobile incomplète')
 for n,s in movable+fixed:
  if s is None or s.isNull() or not s.isValid() or not s.Solids:raise RuntimeError('Obstacle sans solide valide '+n)
 result['solid_inputs_validated']=True
 result['scene_sources_sha256']={f:sha(COPY/f) for f in sorted({row['source'] for row in rows})}
 for name,a in movable:
  for other,b in fixed:
   if gap(a.BoundBox,b.BoundBox)>3:continue
   try:
    p=measured_pair(a,b);p['pair']=[name,other];result['pairs'].append(p)
   except Exception as ex:result['pairs'].append({'pair':[name,other],'error':str(ex)})
 result.update(complete=True,collisions=sum(p.get('volume_mm3',0)>1e-4 for p in result['pairs']),unknown=sum('error'in p for p in result['pairs']))
 write(OUT/('suspension_'+c['id']+'.json'),result);print(c['id'],result['collisions'],flush=True)
if __name__=='__main__':
 try:run(int(sys.argv[1]));sys.stdout.flush();sys.stderr.flush();os._exit(0)
 except Exception:traceback.print_exc();sys.stdout.flush();sys.stderr.flush();os._exit(2)
