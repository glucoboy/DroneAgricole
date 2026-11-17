"""Adaptateur FreeCAD: integrer_autonomie.py install|verify.
P73 est adapté séparément avant les contrôles de collision finaux.
"""
from autonomie_cao import *
from workspace_guard import verify_sources, dependencies
import copy
import math

SA='sous_assemblages/SA07_Prototype_Faisceaux.FCStd'
MAIN='assemblages/Prototype_Cartographe.FCStd'
BUILD='verification/construction_prototype.json'
ROUTES='verification/routes_prototype.json'

def require(condition,message):
 if not condition:raise RuntimeError(message)

def local(relative):
 p=(COPY/relative).resolve()
 require(p.is_relative_to(COPY.resolve()),'Chemin hors copie '+str(relative))
 return p

def relative(path):return str(Path(path).resolve().relative_to(COPY.resolve())).replace('\\','/')

def isolation():
 for d in App.listDocuments().values():
  require(bool(d.FileName),'Document temporaire inattendu '+d.Name)
  local(d.FileName)

def preserve():
 return {'original':verify_sources(read(ROOT/'hardware/mecanique/cartographe_faisceaux/experiment.json')),'baseline':verify_sources(read(COPY/'experiment.json'))}

def errors():
 return [(d.Name,o.Name,list(o.State)) for d in App.listDocuments().values() for o in d.Objects if any(s in ('Error','Invalid') for s in o.State)]

def file_hashes():
 isolation()
 return {relative(p):sha(p) for p in dependencies(COPY,[MAIN])}

def route_map(routes):
 rows=routes['routes'];ids=[r['id'] for r in rows]
 require(len(ids)==53 and len(set(ids))==53 and 'F16' in ids,'53 routes uniques attendues')
 return {r['id']:r for r in rows}

def occurrences(build,ids):
 rows=[r for r in build['occurrences'] if r['parent']==SA and r['occurrence'] in ids]
 require(len(rows)==53 and {r['occurrence'] for r in rows}==set(ids),'Bijection 53 routes/occurrences absente')
 return {r['occurrence']:r for r in rows}

def scene_gate(proof,selection=None):
 # Les empreintes sont produites au contrôle, jamais ajoutées après coup.
 evidence=proof.get('scene_sources_sha256') or (selection or {}).get('scene_sources_sha256')
 expected={relative(local(r['source'])) for r in read(COPY/BUILD)['occurrences'] if r['parent'].startswith('sous_assemblages/') and r['occurrence']!='F16'}
 if evidence:
  supplied={relative(local(p)) for p in evidence}
  require(expected<=supplied,'Preuve scène incomplète')
  for p,h in evidence.items():require(sha(local(p))==h,'Preuve scène périmée: '+p)
  return {'method':'scene_sources_sha256','sources':evidence}
 digest=proof.get('scene_digest');require(bool(digest),'Empreinte scène absente dans preuve collision')
 inputs=read(COPY/'experiment.json')['inputs_sha256']
 actual=hashlib.sha256(json.dumps({p:sha(local(p)) for p in sorted(inputs) if p.endswith('.FCStd')},sort_keys=True).encode()).hexdigest()
 require(actual==digest,'Preuve collision périmée après changement scène')
 require(expected<={relative(local(p)) for p in inputs},'Fermeture initiale ne couvre pas nouvelles sources')
 return {'method':'scene_digest','digest':digest}

def gate_f16(selected,f):
 require(f.get('id')==selected['id'] and f.get('parameters')==selected,'Sélection F16 différente des paramètres vérifiés')
 require(f.get('complete') is True and f.get('generation')=='passed','Génération F16 incomplète')
 require(sha(local(f['file']))==f['sha256'],'Natif F16 différent de la preuve')
 for key in ['fresh','mobile','fixed','whole']:require(f.get(key,{}).get('status')=='pass','Preuve F16 non conforme: '+key)
 collision=f.get('collision',{})
 require(collision.get('complete') is True and collision.get('collisions')==0 and collision.get('unknown')==0,'Collision F16 non résolue')
 require(collision.get('object_cable')==f.get('object_cable','Cable002'),'Collision sur mauvais objet F16')
 require(abs(collision.get('path_length_verified_mm',-1)-f['length_mm'])<1e-5,'Longueur collision différente')
 return scene_gate(collision)

def gate_protection(selection):
 require('selected_id' in selection,'Choix protection absent; null explicite autorisé')
 if selection['selected_id'] is None:return None,None
 p=read(OUT/('protection_'+selection['selected_id']+'.json'))
 require(p['id']==selection['selected_id'] and p.get('complete') is True,'Preuve protection incomplète')
 require(sha(local(p['file']))==p['sha256'],'Natif protection différent de la preuve')
 require(p.get('solid',{}).get('status')=='pass' and p.get('collisions')==0 and p.get('unknown')==0,'Protection non conforme')
 members=p['parameters']['members'];inc=p.get('inclusion',[])
 require(len(inc)==len(members) and {r['member'] for r in inc}==set(members),'Inclusion membres incomplète')
 for r in inc:
  require(all(math.isfinite(r[k]) for k in ['section_volume_mm3','outside_inner_mm3','wall_intersection_mm3']),'Inclusion non finie')
  require(r['section_volume_mm3']>1e-4 and abs(r['outside_inner_mm3'])<=1e-4 and abs(r['wall_intersection_mm3'])<=1e-4,'Inclusion non conforme')
 return p,scene_gate(p,selection)

def equivalent(before,after):
 vals=[]
 for s in [before.cut(after),after.cut(before)]:
  require(s.isNull() or s.isValid(),'Différence booléenne invalide')
  require(math.isfinite(s.Volume) and abs(s.Volume)<=1e-4,'Forme fraîche différente de la preuve')
  vals.append(s.Volume)
 return {'removed_mm3':vals[0],'added_mm3':vals[1]}

def fresh_f16(target,selected,f):
 require(target is not None and target.Name==f.get('object_cable','Cable002'),'Câble complet absent')
 require(target.Base.Name==f.get('object_path','CompoundPath') and len(target.Base.Links)==2,'Parcours composé absent')
 saved=target.Shape.copy()
 for w in target.Base.Links:w.touch()
 fresh=rebuild_cable_in_isolated_document(target.Document,target)
 require(fresh['status']=='pass','Reconstruction F16 échouée')
 low,top=target.Base.Links
 checks={
  'mobile':inspect_route(low.Shape.Wires[0],minimum_radius_mm=48,start_axis=selected['start_axis'],end_axis=[0,0,-1],start_position=selected['lower_points_mm'][0],end_position=[96,-54,75]),
  'fixed':inspect_route(top.Shape.Wires[0],minimum_radius_mm=22,start_axis=[0,0,1],end_axis=[0,-1,0],start_position=[96,-54,75],end_position=[7,-79.95,140.5]),
  'whole':inspect_route(target.Base.Shape.Wires[0],minimum_radius_mm=22,start_axis=selected['start_axis'],end_axis=[0,-1,0],start_position=selected['lower_points_mm'][0],end_position=[7,-79.95,140.5])}
 for key,value in checks.items():require(value['status']=='pass','Parcours frais invalide '+key)
 require(abs(target.Base.Shape.Length-f['length_mm'])<1e-5,'Longueur fraîche différente')
 return {'fresh':fresh,**checks,'delta':equivalent(saved,target.Shape),'length_mm':target.Base.Shape.Length}

def fresh_protection(obj):
 saved=obj.Shape.copy()
 for feature in obj.Document.Objects:
  if hasattr(feature,'Shape'):
   feature.Shape=Part.Shape();feature.touch()
 require(bool(obj.Document.recompute()),'Recalcul protection échoué')
 solid=inspect_solid(obj.Shape);require(solid['status']=='pass','Solide protection invalide')
 return {'solid':solid,'delta':equivalent(saved,obj.Shape)}

def snapshot_reference(obj,file,reference,type_,bom_ids):
 require(obj is not None,'Objet référence absent '+reference)
 s=obj.Shape if hasattr(obj,'Shape') else None
 if s is None or s.isNull():s=Reader(COPY).shape(file,obj.Name)
 require(s is not None and not s.isNull() and s.isValid(),'Référence géométrique invalide '+reference)
 b=s.BoundBox
 return {'reference':reference,'fichier':file,'objet':obj.Name,'bom_ids':bom_ids,'type':type_,'statut':'Implémenté','qualification':'À valider','limites':'Candidat conditionnel; validation physique non exécutée.','sha256':sha(local(file)),'bbox_mm':[b.XMin,b.YMin,b.ZMin,b.XMax,b.YMax,b.ZMax],'compose_valide':True}

def install():
 selected=read(OUT/'selection_f16.json');f=read(report(selected));sleeve=read(OUT/'selection_protection.json')
 preservation_before=preserve();fgate=gate_f16(selected,f);pr,pgate=gate_protection(sleeve)
 build=read(COPY/BUILD);routes=read(COPY/ROUTES);manifest=read(COPY/'manifest.json')
 oldroutes=copy.deepcopy(route_map(routes));oldocc=copy.deepcopy(occurrences(build,oldroutes))
 gui();main=App.openDocument(str(local(MAIN)));isolation();print('Assemblage ouvert',flush=True)
 sa=next(d for d in App.listDocuments().values() if Path(d.FileName).resolve()==local(SA))
 candidate=App.openDocument(str(local(f['file'])));target=candidate.getObject(f.get('object_cable','Cable002'))
 ffresh=fresh_f16(target,selected,f);installed=[];pfresh=None;po=None
 if pr:
  pd=App.openDocument(str(local(pr['file'])));po=pd.getObject(pr['object']);require(po is not None,'Protection absente');pfresh=fresh_protection(po)
 print('Formes candidates recalculées',flush=True)
 isolation();require(not errors(),'Erreurs avant intégration '+str(errors()))
 link=sa.getObject('F16');require(link is not None,'Occurrence F16 absente');before=str(link.LinkedObject)
 link.LinkedObject=target;link.LinkTransform=False;link.Placement=target.getGlobalPlacement()
 if pr:
  pl=sa.getObject('ProtectionF38') or sa.addObject('App::Link','ProtectionF38');pl.LinkedObject=po;pl.LinkTransform=False;pl.Placement=po.getGlobalPlacement();sa.getObject('Ensemble').addObject(pl);pl.Visibility=True
  installed.append({'id':'ProtectionF38','source':relative(po.Document.FileName),'object':po.Name,'placement':pl.Placement.toMatrix().A})
 else:require(sa.getObject('ProtectionF38') is None,'Protection déjà installée mais sélection null')
 sa.getObject('Ensemble').touch();main.getObject('Ensemble').touch()
 require(bool(sa.recompute()) and bool(main.recompute()),'Recalcul assemblage échoué');isolation();require(not errors(),'Assemblage en erreur '+str(errors()))
 for id,row in oldocc.items():
  if id=='F16':continue
  o=sa.getObject(id);require(o is not None and o.LinkedObject is not None,'Lien absent '+id)
  require(Path(o.LinkedObject.Document.FileName).resolve()==local(row['source']) and o.LinkedObject.Name==row['objet_source'],'Lien modifié '+id)
  require(max(abs(a-b) for a,b in zip(o.Placement.toMatrix().A,row['matrice']))<1e-8,'Placement modifié '+id)
 sa.save();main.save();print('Natifs sauvegardés',flush=True)
 occurrences(build,oldroutes)['F16'].update(source=relative(target.Document.FileName),objet_source=target.Name,matrice=link.Placement.toMatrix().A)
 for item in installed:
  build['occurrences']=[r for r in build['occurrences'] if not(r['parent']==SA and r['occurrence']==item['id'])]
  build['occurrences'].append({'parent':SA,'occurrence':item['id'],'source':item['source'],'objet_source':item['object'],'matrice':item['placement'],'bom_ids':[],'statut':'À valider','note':'Protection ouvrable candidate; aucune nouvelle liaison électrique'})
 route=route_map(routes)['F16']
 for key in ['rayon_demande_mm','rayons_arcs_mm','longueur_addon_mm','volume_mm3','solides','solide_valide','continuite','parcours_valide','erreurs','route_proxy']:route.pop(key,None)
 route.update(fichier=relative(target.Document.FileName),objet_cable=target.Name,objet_parcours=target.Base.Name,points_mm=selected['lower_points_mm']+selected['upper_points_mm'][1:],rayon_courbure_mm=None,longueur_courbe_mm=ffresh['length_mm'],longueur_trace_mm=ffresh['length_mm'],longueur_addon_mm=ffresh['length_mm'],longueur_catalogue_mm=None,longueur_gaine_utile_min_mm=None,reference_candidate='Cordon USBFireWire sur mesure, connecteurs Up conservés, validation fabricant requise',statut='À valider',route_proxy=type(target.Base.Proxy).__module__+'.'+type(target.Base.Proxy).__name__,volume_mm3=target.Shape.Volume,solides=len(target.Shape.Solids),solide_valide=target.Shape.isValid(),continuite=True,parcours_valide=True,erreurs=[],segments=[{'id':'mobile','radius_mm':selected['radius_mobile_mm'],'measured':ffresh['mobile']},{'id':'fixed','radius_mm':selected['radius_fixed_mm'],'measured':ffresh['fixed']}])
 route['rayons_arcs_mm']=[e['minimum_radius_mm'] for e in ffresh['whole']['edge_measurements'] if e.get('method')=='analytic_circle']
 route['supports']=['P73','P75']
 route['stations_actives']=['F16_V_75','USB3_I_70','USB3_I_88','USB3_T_67','USB3_T_36']
 newroutes=route_map(routes);newocc=occurrences(build,newroutes)
 require(set(newroutes)==set(oldroutes),'IDs routes changés')
 require(all(newroutes[k]==oldroutes[k] and newocc[k]==oldocc[k] for k in oldroutes if k!='F16'),'52 routes/occurrences modifiées')
 result={'candidate':selected['id'],'source_f16':relative(target.Document.FileName),'object_f16':target.Name,'previous_link':before,'installed_protections':installed,'proof_gates':{'f16':fgate,'protection':pgate},'f16_fresh':ffresh,'protection_fresh':pfresh,'preservation_before':preservation_before,'preservation':preserve(),'entry':MAIN,'errors':errors(),'routes_count':53,'other_routes_unchanged':52,'mass_complete_g':None,'status':'CANDIDAT_CONDITIONNEL','physical':'not_executed','native_sha256':file_hashes()}
 print('Fermeture native empreintée',flush=True)
 proto=manifest['prototype_cartographe'];proto['occurrences']=copy.deepcopy(build['occurrences'])
 refs=proto['references'];current_files={relative(local(r['fichier'])) for r in refs}
 changed_files={MAIN,SA,'pieces/fabriquees/P73_Guide_Faisceau_Droit_Prototype.FCStd'}
 for d in App.listDocuments().values():
  rel=relative(d.FileName)
  if rel not in changed_files:continue
  for collection in [refs,proto.get('assemblages',[])]:
   for r in collection:
    if relative(local(r['fichier']))==rel:
     r['sha256']=result['native_sha256'][rel]
     r['qualification']='À valider'
     if rel in (MAIN,SA):
      r['bbox_mm']=None
      r['compose_valide']=None
     else:
      updated=snapshot_reference(d.getObject(r.get('objet','Ensemble')),rel,r['reference'],r.get('type','pièce'),r.get('bom_ids',[]))
      updated['limites']=r.get('limites','');r.update(updated)
 if relative(target.Document.FileName) not in current_files:refs.append(snapshot_reference(target,relative(target.Document.FileName),selected['id'],'faisceau_cable_workbench',['ELEC-F16']))
 if pr and relative(po.Document.FileName) not in current_files:refs.append(snapshot_reference(po,relative(po.Document.FileName),pr['id'],'protection_textile_enveloppe',[]))
 for r in refs:
  if r['reference']=='W_F16_Prototype':r['role']='historique_remplace';r['remplace_par']=selected['id']
 build['references']=copy.deepcopy(refs)
 proto['integration_autonome']=result;proto['qualification']='À valider';manifest['integration_autonome']=result
 build['integration_autonome']={'candidate':selected['id'],'status':'CANDIDAT_CONDITIONNEL'}
 write(COPY/BUILD,build);write(COPY/ROUTES,routes);write(COPY/'manifest.json',manifest)
 result['registry_sha256']={p:sha(COPY/p) for p in [BUILD,ROUTES,'manifest.json']}
 write(OUT/'integration_autonomie.json',result)

def verify():
 receipt=read(OUT/'integration_autonomie.json');selected=read(OUT/'selection_f16.json');f=read(report(selected))
 require(receipt['candidate']==selected['id'],'Sélection changée après intégration')
 for p,h in {**receipt['native_sha256'],**receipt['registry_sha256']}.items():require(sha(local(p))==h,'Fichier modifié depuis intégration '+p)
 before={p:sha(local(p)) for p in receipt['native_sha256']}
 gui()
 # Ouvrir les natifs à reconstruire intégralement avant les XLink du parent.
 App.openDocument(str(local(receipt['source_f16'])))
 for item in receipt['installed_protections']:App.openDocument(str(local(item['source'])))
 main=App.openDocument(str(local(MAIN)));isolation()
 sa=next(d for d in App.listDocuments().values() if Path(d.FileName).resolve()==local(SA));link=sa.getObject('F16');target=link.LinkedObject
 require(relative(target.Document.FileName)==receipt['source_f16'] and target.Name==receipt['object_f16'],'Lien F16 incorrect à réouverture')
 result={'entry':MAIN,'preservation_before':preserve(),'f16_fresh':fresh_f16(target,selected,f),'protections':[]}
 for item in receipt['installed_protections']:
  po=sa.getObject(item['id']).LinkedObject
  require(relative(po.Document.FileName)==item['source'] and po.Name==item['object'],'Lien protection incorrect')
  result['protections'].append({'id':item['id'],'fresh':fresh_protection(po)})
 sa.getObject('Ensemble').touch();main.getObject('Ensemble').touch()
 require(bool(sa.recompute()) and bool(main.recompute()),'Recalcul réouverture échoué');isolation();require(not errors(),'Erreurs après reconstruction '+str(errors()))
 after=file_hashes();require(set(after)==set(before),'Fermeture de documents différente');require(after==before,'Natifs sauvegardés modifiés pendant vérification')
 routes=route_map(read(COPY/ROUTES));occurrences(read(COPY/BUILD),routes)
 result.update(documents=[{'file':relative(d.FileName),'errors':[]} for d in App.listDocuments().values()],native_sha256_before=before,native_sha256_after=after,all_resolved_inside_copy=True,saved_files_not_modified=after==before,preservation=preserve(),routes_count=53,errors=errors(),status='CANDIDAT_CONDITIONNEL')
 write(OUT/'reouverture_autonomie.json',result)

if __name__=='__main__':
 try:
  require(len(sys.argv)==2 and sys.argv[1] in ('install','verify'),'Usage: integrer_autonomie.py install|verify')
  globals()[sys.argv[1]]();sys.stdout.flush();sys.stderr.flush();os._exit(0)
 except Exception:traceback.print_exc();sys.stdout.flush();sys.stderr.flush();os._exit(2)
