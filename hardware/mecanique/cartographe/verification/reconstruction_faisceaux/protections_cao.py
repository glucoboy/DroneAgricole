"""Adaptateur natif Cables pour protections déclaratives et contrôle de parois."""
from autonomie_cao import *
def run(index):
 params=read(OUT/'protections_autonomie.json')['candidates'][index];builder,env=gui()
 from freecad.cables import wireFlex,archCableConduit
 doc=App.newDocument(params['id']);wire=wireFlex.make_wireflex_from_vectors([App.Vector(*p) for p in params['points']]);doc.recompute()
 conduit=archCableConduit.makeCableConduit(selectlist=[wire],name=params['id']);conduit.Diameter=params['inner_mm']+2*params['wall_mm'];conduit.WallThickness=params['wall_mm'];conduit.Shape=Part.Shape();conduit.touch();ok=doc.recompute()
 result={'id':params['id'],'parameters':params,'parameters_sha256':sha(OUT/'protections_autonomie.json'),'environment':env,'recompute_return':ok,'solid':inspect_solid(conduit.Shape),'complete':False}
 conduit.addProperty('App::PropertyString','Limites','Conception');conduit.Limites='Enveloppe candidate textile ouvrable, couture/recouvrement/rigidité non représentés; À valider'
 wire.Visibility=False;conduit.Visibility=True;conduit.ViewObject.ShapeColor=(.2,.65,.3)
 target=COPY/'verification/candidats'/(params['id']+'.FCStd');doc.saveAs(str(target));result.update(file=str(target.relative_to(COPY)),object=conduit.Name,sha256=sha(target))
 write(OUT/('protection_'+params['id']+'.json'),result)
def check_sleeve(index):
 params=read(OUT/'protections_autonomie.json')['candidates'][index];result=read(OUT/('protection_'+params['id']+'.json'))
 reader=Reader(COPY);wall=reader.shape(result['file'],result['object']);rows=read(COPY/'verification/construction_prototype.json')['occurrences'];pairs=[];count=0
 a,b=[App.Vector(*p) for p in params['points']];axis=b-a
 inner=Part.makeCylinder(params['inner_mm']/2,axis.Length,a,axis)
 frame=App.Placement(a,App.Rotation(App.Vector(0,0,1),axis))
 axial=Part.makeBox(2000,2000,axis.Length,App.Vector(-1000,-1000,0));axial.Placement=frame.multiply(axial.Placement)
 inclusion=[]
 for row in rows:
  if not row['parent'].startswith('sous_assemblages/'):continue
  shape=reader.occurrence(row);count+=1
  if row['occurrence'] in params['members']:
   local=shape.copy();local.Placement=frame.inverse().multiply(local.Placement)
   if local.BoundBox.XMin<=-1000 or local.BoundBox.XMax>=1000 or local.BoundBox.YMin<=-1000 or local.BoundBox.YMax>=1000:raise RuntimeError('Tranche axiale insuffisante')
   section=shape.common(axial);outside=section.cut(inner)
   if section.isNull() or not section.isValid() or section.Volume<=1e-4 or (not outside.isNull() and not outside.isValid()):raise RuntimeError('Section absente ou booléen invalide')
   inclusion.append({'member':row['occurrence'],'section_volume_mm3':section.Volume,'outside_inner_mm3':outside.Volume,'wall_intersection_mm3':shape.common(wall).Volume,'wall_distance_mm':shape.distToShape(wall)[0]})
  if gap(wall.BoundBox,shape.BoundBox)>1e-6:continue
  try:p=measured_pair(wall,shape);p['obstacle']=row['parent']+'#'+row['occurrence'];pairs.append(p)
  except Exception as e:pairs.append({'obstacle':row['occurrence'],'error':str(e)})
 if set(p['member'] for p in inclusion)!=set(params['members']):raise RuntimeError('Membre de protection absent')
 result.update(pairs=pairs,inclusion=inclusion,occurrences=count,collisions=sum(p.get('volume_mm3',0)>1e-4 for p in pairs),unknown=sum('error'in p for p in pairs),complete=True)
 write(OUT/('protection_'+params['id']+'.json'),result);print(result['id'],result['collisions'],flush=True)
def reopen_sleeve(index):
 params=read(OUT/'protections_autonomie.json')['candidates'][index];result=read(OUT/('protection_'+params['id']+'.json'));gui();doc=App.openDocument(str(COPY/result['file']));c=doc.getObject(result['object']);saved=c.Shape.copy();c.Shape=Part.Shape();c.Base.touch();c.touch();ok=doc.recompute()
 result['reopened']={'recompute':ok,'solid':inspect_solid(c.Shape),'removed_mm3':saved.cut(c.Shape).Volume,'added_mm3':c.Shape.cut(saved).Volume,'errors':[o.Name for o in doc.Objects if any(s in ('Error','Invalid') for s in o.State)]};write(OUT/('protection_'+params['id']+'.json'),result)
if __name__=='__main__':
 try:globals()[sys.argv[1]](int(sys.argv[2]));sys.stdout.flush();sys.stderr.flush();os._exit(0)
 except Exception:traceback.print_exc();sys.stdout.flush();sys.stderr.flush();os._exit(2)
