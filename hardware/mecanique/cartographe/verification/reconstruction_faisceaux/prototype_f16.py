"""Essai CAO F16 borné, sur fichiers candidats séparés, sans remplacer la baseline."""
from mesurer_copie import *
from freecad_geometry import shape_sha256

def run():
    if not (OUT/'analyse_connectivite.json').is_file():
        raise RuntimeError('Topologie globale préalable requise')
    import FreeCADGui as Gui
    Gui.showMainWindow();Gui.getMainWindow().hide()
    import cable_workbench_prototype as builder
    provenance=builder.bootstrap_paths()
    audit=read(OUT/'analyse_mecanique_f16.json')
    destinations=COPY/'verification/candidats';destinations.mkdir(parents=True,exist_ok=True)
    result={'environment':provenance,'topology_sha256':sha(OUT/'analyse_connectivite.json'),
      'audit_sha256':sha(OUT/'analyse_mecanique_f16.json'),'candidates':[], 'complete':False,
      'sources_before':verify_sources(read(COPY/'experiment.json')),
      'scope':'Essais de marge statique ; aucune preuve de mouvement ni de compatibilité de gaine'}
    base=next(r for r in read(COPY/'verification/routes_prototype.json')['routes'] if r['id']=='F16')
    for strategy in audit['strategies']:
        if 'points_mm' not in strategy: continue
        if strategy['id']=='F16_BASELINE':
            doc=App.openDocument(str(COPY/base['fichier']));cable=doc.getObject('Cable')
        else:
            path=destinations/(strategy['id']+'.FCStd')
            if path.exists():raise RuntimeError('Ne pas écraser un candidat existant')
            doc=App.newDocument(strategy['id'])
            cable,wire=builder.make_native_cable(doc,None,'Cable',strategy['points_mm'],5.5,strategy['radius_mm'])
        assert_copy(doc)
        fresh=rebuild_cable_in_isolated_document(doc,cable)
        measure=inspect_route(cable.Base.Shape.Wires[0],minimum_radius_mm=22,start_axis=[1,0,0],end_axis=[0,-1,0],
          start_position=base['points_mm'][0],end_position=base['points_mm'][-1])
        stations=[]
        for s in audit['stations_et_audit_historique']['stations']:
            distance=cable.Base.Shape.distToShape(Part.Vertex(App.Vector(*s['point_nominal_mm'])))[0]
            stations.append({'id':s['station_id'],'distance_mm':distance,'tolerance_mm':s['tolerance_projection_mm'],
              'pass':distance<=s['tolerance_projection_mm']})
        row={'id':strategy['id'],'fresh':fresh,'route':measure,'stations':stations,
          'connector_axes_confidence':'candidate_derived_from_baseline_not_independent_measurement',
          'useful_length_limit_mm':428.5,'useful_length_pass':cable.Base.Shape.Length<=428.5,
          'length_reserve_mm':428.5-cable.Base.Shape.Length,
          'continuous_flexion_48mm':'not_satisfied_if_applied_to_camera_flexible_section',
          'dynamic_motion_envelope':'NON_VERIFIE'}
        if strategy['id']!='F16_BASELINE':
            doc.saveAs(str(path));row['file']=path.relative_to(COPY).as_posix();row['sha256']=sha(path)
            row['saved']=True;row['saved_shape_sha256']=shape_sha256(cable.Shape)
        else:row['file']=base['fichier'];row['sha256']=sha(COPY/base['fichier']);row['saved']=False
        result['candidates'].append(row)
        App.closeDocument(doc.Name)
    vectors=[App.Vector(*p) for p in base['points_mm']]
    try:
        builder._check_polyline(vectors,5.5,48)
        result['unchanged_points_R48']={'status':'unexpected_feasible'}
    except Exception as exc:result['unchanged_points_R48']={'status':'NON_CONFORME','error':str(exc),'generation_executed':False}
    result['complete']=True;result['sources_after']=verify_sources(read(COPY/'experiment.json'))
    write('prototype_f16.json',result)

def reopen():
    import FreeCADGui as Gui
    Gui.showMainWindow();Gui.getMainWindow().hide()
    import cable_workbench_prototype as builder
    builder.bootstrap_paths()
    result=read(OUT/'prototype_f16.json')
    for row in result['candidates']:
        doc=App.openDocument(str(COPY/row['file']));assert_copy(doc)
        cable=next(o for o in doc.Objects if hasattr(o,'ProfilExterieur'))
        row['reopened']={'saved_shape':inspect_solid(cable.Shape), 'shape_sha256':shape_sha256(cable.Shape),
          'length_mm':cable.Base.Shape.Length,'fresh':rebuild_cable_in_isolated_document(doc,cable)}
        App.closeDocument(doc.Name)
    write('prototype_f16_reouverture.json',result)

def volumes():
    result=read(OUT/'prototype_f16_reouverture.json');reader=Reader(COPY)
    build=read(COPY/'verification/construction_prototype.json')
    rows=[o for o in build['occurrences'] if o['parent'].startswith('sous_assemblages/') and o['occurrence']!='F16']
    candidates={r['id']:reader.shape(r['file'],'Cable') for r in result['candidates']}
    result['collision_scope']={'occurrences':len(rows),'volume_tolerance_mm3':1e-4,'clearance_acceptance_mm':None,
        'note':'Minimum exact des volumes nominaux ; seuil physique de dégagement non défini, aucune exemption'}
    for row in result['candidates']:row.update(pairs=[],collision_count=0,unknown_count=0,minimum_clearance_mm=None)
    for i,obstacle in enumerate(rows):
        name=obstacle['parent']+'#'+obstacle['occurrence'];shape=reader.occurrence(obstacle)
        for row in result['candidates']:
            a=candidates[row['id']];lower=gap(a.BoundBox,shape.BoundBox)
            if lower>1e-6 and row['minimum_clearance_mm'] is not None and lower>row['minimum_clearance_mm']+1e-6:continue
            check=inspect_pair(a,shape,row['id'],name,volume_tolerance_mm3=1e-4)
            row['pairs'].append(check)
            row['collision_count']+=int(check.get('intersection_volume_mm3',0)>1e-4)
            row['unknown_count']+=int(check['status']=='unknown')
            dist=check.get('clearance_mm')
            if dist is not None and (row['minimum_clearance_mm'] is None or dist<row['minimum_clearance_mm']):row['minimum_clearance_mm']=dist
        if i%20==0:
            result['volumes_progress']=i;write('comparaison_f16.json',result);print('F16 obstacle',i,flush=True)
    result['volumes_complete']=True
    result['decision']='F16 initial conservé dans assemblage copie ; aucun candidat admis pour reconstruction globale'
    result['sources_after']=verify_sources(read(COPY/'experiment.json'));write('comparaison_f16.json',result)

if __name__=='__main__':
    try:
        globals()[sys.argv[1]]();sys.stdout.flush();sys.stderr.flush();os._exit(0)
    except Exception:
        traceback.print_exc();sys.stdout.flush();sys.stderr.flush();os._exit(2)
