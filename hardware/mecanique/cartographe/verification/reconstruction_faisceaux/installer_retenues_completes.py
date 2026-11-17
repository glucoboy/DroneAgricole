"""Pose des guides validés dans la copie et réouverture du modèle complet."""
from copy import deepcopy
from pathlib import Path
import os
import shutil
import sys

from autonomie_cao import App, COPY, OUT, ROOT, Part, Reader, gap, gui, inspect_solid, measured_pair, read, report, sha, transform, write
from integrer_autonomie import BUILD, MAIN, ROUTES, errors, file_hashes, isolation, local, preserve


VARIANTS = ('P73_F05_F08_B','P75_F08')


def install():
    previous = read(OUT/'integration_autonomie.json')
    for name, expected in {**previous['native_sha256'],**previous['registry_sha256']}.items():
        if sha(local(name)) != expected:
            raise RuntimeError('Baseline de reprise modifiée: '+name)
    reader = Reader(COPY)
    selections = [read(OUT/('retenues_'+name+'.json')) for name in VARIANTS]
    for result in selections:
        if (result['collisions'] or result['solid']['status'] != 'pass' or sha(local(result['file'])) != result['sha256']
                or result['construction_sha256'] != sha(COPY/BUILD)
                or any(s['axis_error_mm']>.6 or not 0 < s['distance_to_guide_less_radius_mm'] <= 1 for s in result['stations'])):
            raise RuntimeError('Variante non admissible '+result['id'])
    # P75 est borné par les primitives modifiées; contrôle croisé contre P73 nouveau.
    first, second = selections
    p73 = reader.occurrence({**first['target'],'source':first['file']})
    p75_new = [reader.shape(second['file'], name) for name in ('MontanteF08Aval','RepriseF08Aval')]
    if any(gap(p73.BoundBox,s.BoundBox)<=1e-6 and p73.common(s).Volume>1e-4 for s in p75_new):
        raise RuntimeError('Interférence entre les deux guides candidats')
    build, manifest = read(COPY/BUILD),read(COPY/'manifest.json')
    targets = [x['target']['source'] for x in selections]+[BUILD,'manifest.json']
    backup = ROOT/'.runtime/reconstruction-faisceaux/avant-retenues-completes'
    for name in targets:
        path = backup/name
        path.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(local(name),path)
    try:
        changes = []
        for result in selections:
            name = result['target']['source']
            shape = reader.occurrence({**result['target'],'source':result['file']})
            bounds = shape.BoundBox
            shutil.copy2(local(result['file']),local(name))
            for ref in manifest['prototype_cartographe']['references']:
                if ref['fichier'] == name:
                    ref.update(sha256=sha(local(name)), bbox_mm=[bounds.XMin,bounds.YMin,bounds.ZMin,bounds.XMax,bounds.YMax,bounds.ZMax],
                               qualification='À valider')
            changes.append({'guide':name,'id':result['id'],'sha256':sha(local(name)),'stations':result['stations']})
        build['references']=deepcopy(manifest['prototype_cartographe']['references'])
        record = {'status':'CANDIDAT_CONDITIONNEL','guides':changes,'preservation':preserve(),
                  'native_sha256':{**previous['native_sha256'],**{x['guide']:x['sha256'] for x in changes}},
                  'routes_sha256':sha(COPY/ROUTES),'cross_check':'Primitives modifiées P75 contre P73 candidat, aucune intersection.'}
        build['reprise_retenues_faisceau_complet']={'guides':changes,'status':record['status']}
        manifest['prototype_cartographe']['reprise_retenues_faisceau_complet']=build['reprise_retenues_faisceau_complet']
        write(COPY/BUILD,build)
        write(COPY/'manifest.json',manifest)
        record['registry_sha256']={name:sha(local(name)) for name in [BUILD,ROUTES,'manifest.json']}
        write(OUT/'installation_retenues_completes.json',record)
    except BaseException:
        for name in targets:
            shutil.copy2(backup/name,local(name))
        raise


def verify():
    record = read(OUT/'installation_retenues_completes.json')
    for name, expected in {**record['native_sha256'],**record['registry_sha256']}.items():
        if sha(local(name)) != expected:
            raise RuntimeError('Fichier modifié depuis intégration: '+name)
    gui()
    guides = []
    for change in record['guides']:
        doc = App.openDocument(str(local(change['guide'])))
        final = doc.getObject('ResultatPassagesReprise')
        # Ces guides n'ont aucun XLink. Forcer le recalcul du natif complet en mémoire.
        before = final.Shape.Volume
        final.Shape = Part.Shape()
        for obj in doc.Objects:
            obj.touch()
        status = doc.recompute()
        inspected = inspect_solid(final.Shape)
        if not status or inspected['status'] != 'pass' or abs(inspected['volume_mm3']-before)>1e-4:
            raise RuntimeError('Écart de recalcul '+change['guide'])
        guides.append({'guide':change['guide'],'fresh':inspected,'volume_delta_mm3':inspected['volume_mm3']-before})
    main = App.openDocument(str(local(MAIN)))
    isolation()
    main.getObject('Ensemble').touch()
    if not main.recompute() or errors() or file_hashes() != record['native_sha256']:
        raise RuntimeError('Échec de la réouverture finale '+str(errors()))
    write(OUT/'reouverture_faisceau_complet.json',{'entry':MAIN,'guides':guides,'documents_count':len(App.listDocuments()),
          'native_sha256':file_hashes(),'all_resolved_inside_copy':True,'disk_files_unchanged_during_reopen':True,
          'errors':[],'preservation':preserve()})


def motion():
    record = read(OUT/'installation_retenues_completes.json')
    previous = read(OUT/'integration_autonomie.json')
    baseline = Reader(ROOT/'.runtime/reconstruction-faisceaux/avant-retenues-completes')
    reader = Reader(COPY)
    f73,f75 = [g['guide'] for g in record['guides']]
    if sha(baseline.base/f73) != previous['native_sha256'][f73]:
        raise RuntimeError('Ancien P73 différent de la preuve')
    p73_add = reader.shape(f73,'Ensemble').cut(baseline.shape(f73,'Ensemble'))
    additions = {'P73':p73_add, 'P75_borne':Part.makeCompound([reader.shape(f75,name) for name in ('MontanteF08Aval','RepriseF08Aval')])}
    if any(x.isNull() or not x.isValid() for x in additions.values()):
        raise RuntimeError('Volume ajouté invalide')
    kin = read(OUT/'recherche_suspension.json')['kinematics']
    moving = []
    for row in read(COPY/BUILD)['occurrences']:
        if (('SA04' in row['parent'] and row['occurrence'] in kin['mobile_sa04_occurrences']) or
                ('SA07' in row['parent'] and row['occurrence'] in kin['mobile_sa07_occurrences'])):
            moving.append((row['occurrence'],reader.occurrence(row)))
    if len(moving)!=31:
        raise RuntimeError('Bloc mobile incomplet')
    results = []
    for pose in read(OUT/'poses_autonomie.json')['candidates']:
        f16 = read(report(pose))
        if sha(COPY/f16['file']) != f16['sha256']:
            raise RuntimeError('Pose modifiée')
        parts = [(name, reader.shape(f16['file'],f16.get('object_'+name,default)))
                 for name,default in [('mobile','Cable'),('fixed','Cable001')]]
        for name,source in moving:
            shape = source.copy()
            shape.Placement = transform(pose).multiply(shape.Placement)
            parts.append((name,shape))
        disjoint, measured = 0, []
        for name,shape in parts:
            for group,new in additions.items():
                if gap(shape.BoundBox,new.BoundBox)>1e-6:
                    disjoint+=1
                else:
                    measured.append({'pair':[name,group], **measured_pair(shape,new)})
        results.append({'id':pose['id'],'aabb_disjoint':disjoint,'brep':measured})
    write(OUT/'mouvement_retenues_completes.json',{'poses':results,'guide_sha256':{p:sha(COPY/p) for p in (f73,f75)},
          'intersection_count':sum(p['volume_mm3']>1e-4 for r in results for p in r['brep']),
          'scope':'Seuls nouveaux volumes P73/P75, 27 poses précédentes. Autres câbles mobiles et déformations non couverts.'})


if __name__ == '__main__':
    {'install':install,'verify':verify,'motion':motion}[sys.argv[1]]()
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0)
