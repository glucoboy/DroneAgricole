"""Adaptateur FreeCAD du lot ORCH-CAO-MASSE-1, sans calcul de masse.

--integrate : recalcul et sauvegarde séquentielle des seuls assemblages projet.
--extract : lecture des BRep sauvegardés, volumes/repères et couverture physique.
Les sommes de masses sont réalisées par cartographe-bom-mass (C++17).
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import json
import os
import sys
import zipfile
import xml.etree.ElementTree as ET
# FreeCAD capture les arguments à son initialisation. Le script Python est
# piloté par argparse et ne doit pas être réinterprété comme document au GUI.
CLI_ARGUMENTS=sys.argv[1:]
sys.argv=[sys.executable]
import FreeCAD as App
from read_brep_prototype import Reader

ROOT = Path(__file__).resolve().parents[4]
MEC = ROOT/'hardware/mecanique/cartographe'
VER = MEC/'verification'
BASE = ROOT/'.runtime/orch-cao-masse-1/baseline'


def read(p):
    return json.loads(Path(p).read_text('utf-8-sig'))


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def write(p, value):
    Path(p).write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', 'utf-8')


def save_assembly(doc):
    """Sauvegarde App sans GUI en conservant les données d'apparence existantes.

    FreeCAD App seul n'écrit pas GuiDocument.xml. Ses octets et fichiers
    auxiliaires sont donc réinjectés inchangés, sans ancienne géométrie.
    Les liens ajoutés héritent par défaut de l'apparence de leur source.
    """
    path=Path(doc.FileName)
    with zipfile.ZipFile(path) as z:
        original={n:z.read(n) for n in z.namelist()}
    if 'GuiDocument.xml' not in original:raise ValueError('Apparences initiales absentes : '+str(path))
    gui=ET.fromstring(original['GuiDocument.xml'])
    auxiliaries={n.attrib['file'] for n in gui.iter() if n.attrib.get('file')}
    kept={n:original[n] for n in auxiliaries if n in original}
    kept['GuiDocument.xml']=original['GuiDocument.xml']
    doc.recompute();doc.save()
    with zipfile.ZipFile(path) as z:payload={n:z.read(n) for n in z.namelist()}
    for name,data in kept.items():
        if name in payload and payload[name]!=data:raise ValueError('Conflit données GUI/core : '+name)
        payload[name]=data
    temp=path.with_suffix('.apparence.tmp')
    with zipfile.ZipFile(temp,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for name,data in payload.items():z.writestr(name,data)
    temp.replace(path)
    with zipfile.ZipFile(path) as z:
        if any(z.read(name)!=data for name,data in kept.items()):raise ValueError('Apparence modifiée : '+str(path))
    return {'fichier':path.relative_to(MEC).as_posix(),'gui_sha256':hashlib.sha256(kept['GuiDocument.xml']).hexdigest(),
            'fichiers_gui_auxiliaires':len(kept)-1,'donnees_gui_conservees':True,
            'limite':'Les nouveaux liens utilisent les apparences source par défaut ; contrôle GUI interactif non exécuté.'}


def preserve_evidence():
    target = VER/'historique/orch_cao_masse_1'
    target.mkdir(parents=True, exist_ok=True)
    names = ['construction_prototype.json', 'controle_assemblage_prototype.json',
             'couverture_bom_cao_prototype.json', 'controle_nomenclature_prototype.json',
             'controle_registres_prototype.json', 'review_assemblage_prototype.json',
             'controle_pieces_prototype.json', 'controle_faisceaux_prototype.json',
             'controle_fixations_guides_prototype.json', 'controle_fixations_equipements_prototype.json',
             'controle_colliers_prototype.json', 'controle_retenues_faisceaux_prototype.json',
             'controle_departs_bras_prototype.json', 'controle_apparences_prototype.json',
             'rendu_prototype.json']
    for name in names:
        original = BASE/'hardware/mecanique/cartographe/verification'/name
        dest = target/name
        if dest.exists():
            if sha(dest) != sha(original):
                raise ValueError('Preuve historique divergente : '+name)
        else:
            dest.write_bytes(original.read_bytes())
    retained=[]
    views=read(BASE/'hardware/mecanique/cartographe/verification/rendu_prototype.json').get('vues',[])
    views+=read(BASE/'hardware/mecanique/cartographe/verification/construction_prototype.json').get('vues',[])
    for view in views:
        relative=Path(view['fichier'])
        dest=MEC/'exports/historique/orch_cao_masse_1'/relative.relative_to('exports')
        if not dest.exists():
            original=MEC/relative
            if sha(original)!=view['sha256']:raise ValueError('Export historique déjà remplacé : '+str(relative))
            dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(original.read_bytes())
        if sha(dest)!=view['sha256']:raise ValueError('Copie export historique différente : '+str(dest))
        retained.append(dict(chemin_initial=relative.as_posix(),fichier_conserve=dest.relative_to(MEC).as_posix(),sha256=view['sha256']))
    write(target/'index_conservation.json',{'lot':'ORCH-CAO-MASSE-1','preuves':names,'exports':retained,
        'portee':'État antérieur du 22 octobre ; les chemins initiaux peuvent maintenant désigner les exports actuels.'})


def integration():
    if App.GuiUp:raise ValueError('Processus App sans GUI requis pour cette recette isolée.')
    from cable_workbench_prototype import bootstrap_paths
    bootstrap_paths()
    import Draft
    from draftviewproviders.view_wire import ViewProviderWire
    Draft.ViewProviderWire=ViewProviderWire
    from freecad.cables import wireFlex,archCable
    preserve_evidence()
    build = read(VER/'construction_prototype.json')
    before = {p: sha(MEC/p) for p in build['sources_preservees']}
    print('Ouverture assemblage principal',flush=True)
    doc = App.openDocument(str(MEC/build['assemblage']))
    print('Documents ouverts : '+str(len(App.listDocuments())),flush=True)
    fabrication=read(VER/'orch_cao_masse_fabrication.json')
    corrections=list(fabrication.get('modifications_occurrences',[]))
    reprise_file=VER/'orch_reprise_collisions.json'
    reprise=read(reprise_file) if reprise_file.exists() else {}
    if reprise:
        if not reprise.get('application') or reprise.get('interferences_restantes') or reprise.get('interferences_nouvelles'):raise ValueError('Correction des collisions non finalisée')
        if reprise['script_sha256']!=sha(VER/'orch_reprise_collisions.py'):raise ValueError('Recette de collision périmée')
        corrections+=reprise['changements_occurrences']
    fraisures_file=VER/'orch_reprise_vis_fraisees_application.json'
    if fraisures_file.exists():
        fraisures=read(fraisures_file)
        if not fraisures['application'] or fraisures['script_sha256']!=sha(VER/'orch_appliquer_vis_fraisees.py'):raise ValueError('Reprise fraisures non finalisée')
        corrections+=fraisures['changements_occurrences']
    corrections += [dict(parent=r['parent'],occurrence=r['occurrence'],matrice=r['matrice_apres'])
        for r in read(VER/'orch_interfaces_equipements.json').get('modifications_occurrences',[])
        if r.get('applicable_sans_autre_modification')]
    for row in corrections:
        d=next(d for d in App.listDocuments().values() if Path(d.FileName).resolve()==(MEC/row['parent']).resolve())
        obj=d.getObject(row['occurrence'])
        if obj is None: raise ValueError('Occurrence à modifier absente : '+row['occurrence'])
        obj.LinkPlacement=App.Placement(App.Matrix(*row['matrice']))
        expected=next(o for o in build['occurrences'] if o['parent']==row['parent'] and o['occurrence']==row['occurrence'])
        expected['matrice']=row['matrice']
    for row in fabrication.get('ajouts_occurrences',[])+reprise.get('ajouts_occurrences',[]):
        d=next(d for d in App.listDocuments().values() if Path(d.FileName).resolve()==(MEC/row['parent']).resolve())
        source=next((s for s in App.listDocuments().values() if Path(s.FileName).resolve()==(MEC/row['source']).resolve()),None)
        if source is None: source=App.openDocument(str(MEC/row['source']))
        target=source.getObject(row['objet_source'])
        if target is None: raise ValueError('Objet source absent : '+row['source'])
        obj=d.getObject(row['occurrence']) or d.addObject('App::Link',row['occurrence'])
        d.Ensemble.addObject(obj);obj.LinkedObject=target;obj.LinkTransform=False
        obj.LinkPlacement=App.Placement(App.Matrix(*row['matrice']))
        if 'BOM_ID' not in obj.PropertiesList: obj.addProperty('App::PropertyString','BOM_ID','Definition')
        obj.BOM_ID=','.join(row['bom_ids'])
        if not any(o['parent']==row['parent'] and o['occurrence']==row['occurrence'] for o in build['occurrences']):
            build['occurrences'].append(row)
    structure=read(VER/'orch_cao_masse_structure.json')
    for mapping in structure['mapping_oem']:
        row=next(o for o in build['occurrences'] if o['parent']==mapping['parent'] and o['occurrence']==mapping['occurrence'])
        row['bom_ids']=sorted({i for leaf in mapping['feuilles'] for i in leaf['bom_ids']})
        row['detail_physique']='verification/orch_cao_masse_structure.json#mapping_oem'
        d=next(d for d in App.listDocuments().values() if Path(d.FileName).resolve()==(MEC/row['parent']).resolve())
        d.getObject(row['occurrence']).BOM_ID=','.join(row['bom_ids'])
    errors = [];appearances=[]
    documents = list(App.listDocuments().values())
    for d in documents:
        if d.FileName and Path(d.FileName).parent == MEC/'sous_assemblages':
            print('Sauvegarde '+d.Name,flush=True)
            d.recompute()
            errors += [{'document': d.Name, 'objet': o.Name, 'etat': list(o.State)}
                       for o in d.Objects if any(s in ('Invalid', 'Error') for s in o.State)]
            appearances.append(save_assembly(d))
            print('Sauvegarde terminée '+d.Name,flush=True)
    doc.recompute()
    appearances.append(save_assembly(doc))
    print('Sauvegarde principale terminée',flush=True)
    # La fermeture explicite de documents liés peut bloquer FreeCAD App après
    # les sauvegardes. Le processus dédié termine par os._exit après publication
    # des registres, puis les natifs sont rouverts dans un autre processus.
    build['orch_cao_masse_1'] = {
        'lot': 'ORCH-CAO-MASSE-1', 'integration': 'verification/orch_integrate_cao.py',
        'integration_sha256': sha(__file__), 'statut': 'Implémenté',
        'qualification': 'À valider', 'lot_clos': False,
        'historique': 'verification/historique/orch_cao_masse_1/',
        'apparences_assemblages':appearances,
        'sauvegarde':'FreeCAD App, puis réinjection byte-identique des seules apparences GUI ; aucune forme initiale réinjectée.',
        'erreurs_recalcul_integration': errors}
    reader = Reader(MEC)
    evolved = dict(build.get('sources_initiales_evoluees', {}))
    for path, state in evolved.items():
        state['sha256_courant'] = sha(MEC/path)
    references = {r['fichier']: r for r in build['references']}
    for path, old in list(build['sources_preservees'].items()):
        actual = sha(MEC/path)
        if old != actual:
            if path.startswith('sources_fabricants/'):
                raise ValueError('Original fabricant modifié : '+path)
            evolved[path] = {'sha256_initial': old, 'sha256_courant': actual}
            del build['sources_preservees'][path]
            if path not in references:
                obj = 'Ensemble'
                types, objects = reader.xml(path)
                if obj not in objects:
                    candidates = [n for n,p in objects.items() if 'Shape' in p]
                    linked = [o['objet_source'] for o in build['occurrences'] if o['source'] == path]
                    obj = linked[0] if linked else candidates[-1]
                references[path] = dict(reference=Path(path).stem, fichier=path, objet=obj,
                    bom_ids=[], type='fabriquee' if '/fabriquees/' in path else 'commerce_reconstruction_documentee',
                    statut='Implémenté', qualification='À valider', limites='Voir preuve du lot ORCH-CAO-MASSE-1.')
    for path,r in references.items():
        actual_sha=sha(MEC/path)
        if r.get('sha256')==actual_sha and r.get('bbox_mm') is not None:continue
        r['sha256'] = actual_sha
        shape = reader.shape(path, r['objet'])
        if shape is not None:
            b = shape.BoundBox
            r['bbox_mm'] = [b.XMin,b.YMin,b.ZMin,b.XMax,b.YMax,b.ZMax]
            r['compose_valide'] = shape.isValid()
    build['references'] = list(references.values())
    build['sources_initiales_evoluees'] = evolved
    if reprise:build['orch_cao_masse_1']['reprise_collisions']='verification/orch_reprise_collisions.json'
    build.setdefault('recettes_historiques_sha256',build.get('recettes_sha256',{}))
    build['recettes_sha256']={name:sha(VER/name) for name in
        ('orch_integrate_cao.py','orch_equipements_cao.py','orch_fabrication_cao.py','orch_structure_cao.py')}
    if build.get('vues'):
        build.setdefault('vues_historiques',build['vues'])
        build['vues']=[]
    build['script_fichier']='verification/orch_integrate_cao.py'
    build['script_sha256']=sha(__file__)
    build['date_utc'] = datetime.now(timezone.utc).isoformat()
    build['limites'] = list(dict.fromkeys(build.get('limites', [])+[
        'ORCH-CAO-MASSE-1 : définition et masses incomplètes ; voir les blocages du lot.',
        'Les preuves antérieures du 22 octobre ne décrivent plus les dépendances modifiées.']))
    build['finalisation_correcte'] = not errors
    write(VER/'construction_prototype.json', build)
    manifest = read(MEC/'manifest.json')
    active = manifest['prototype_cartographe']
    for key in ('references','occurrences','sources_preservees','sources_initiales_evoluees','orch_cao_masse_1'):
        active[key] = build[key]
    active['assemblages'] = [r for r in build['references'] if r['type'] in ('sous_assemblage','assemblage_final')]
    active['validation_registres'] = 'verification/controle_orch_cao_masse_1.json'
    active['revue_independante'] = 'verification/revue_orch_cao_masse_1.json'
    historical_keys=('review_fixations','validation_faisceaux','validation_fixations_guides',
        'validation_fixations_equipements','validation_retenues','validation_pieces',
        'validation_departs_bras','validation_colliers','validation_apparences',
        'rendus_inspection','contre_verification_corps','preservation_sources_initiales')
    active.setdefault('preuves_historiques_obsoletes',{})
    for key in historical_keys:
        if key in active and not active[key].startswith('verification/historique/'):
            active['preuves_historiques_obsoletes'][key]=active[key]
            del active[key]
    active['validation_interfaces_fabrication']='verification/orch_cao_masse_fabrication.json#controle_interfaces'
    active['validation_interfaces_equipements']='verification/orch_interfaces_equipements.json'
    if reprise:
        active['validation_collisions_reprise']='verification/controle_reprise_collisions.json'
        active['correction_f20']='verification/orch_reprise_f20_application.json'
        if fraisures_file.exists():active['correction_fraisures']='verification/orch_reprise_vis_fraisees_application.json'
        if (VER/'orch_reprise_tetes_chc_application.json').exists():active['correction_tetes_chc']='verification/orch_reprise_tetes_chc_application.json'
    active['exports_gazebo']={'statut':'Obsolète après ORCH-CAO-MASSE-1',
        'manifeste_geometrique':'simulation/gazebo/models/cartographe/geometry/geometry_manifest.json',
        'regeneration':'Suspendue ; conserver les exports et preuves historiques.'}
    active['limites'] = build['limites']
    manifest['date_mise_a_jour'] = datetime.now(timezone.utc).date().isoformat()
    write(MEC/'manifest.json', manifest)
    print(json.dumps({'integration': 'finalisée' if not errors else 'non conforme',
                      'references': len(references), 'erreurs': errors}, ensure_ascii=False), flush=True)


OWNER = {'P10_': 'MEC-RETENUES-CAPTEURS', 'P17_': 'MEC-SUPPORT-ISOLATION',
         'P18_': 'MEC-MANCHON', 'P19_': 'MEC-RONDELLE-CAPTURE',
         'P60_': 'MEC-BATTERIE-SUPPORT', 'P61_': 'MEC-BATTERIE-SUPPORT',
         'P62_': 'MEC-SUPPORTS-ENERGIE','P63_': 'MEC-SUPPORTS-ENERGIE',
         'P64_': 'MEC-SUPPORTS-ENERGIE','P65_': 'MEC-PLATINE-CAPTEURS',
         'P66_': 'MEC-SUPPORT-AVIONIQUE','P67_': 'MEC-SUPPORT-AVIONIQUE',
         'P68_': 'MEC-SUPPORT-AVIONIQUE','P69_': 'MEC-SUPPORT-GNSS',
         'P70_': 'MEC-SUPPORTS-RF','P71_': 'MEC-SUPPORTS-SECURITE',
         'P72_': 'ELEC-PASSEFILS','P73_': 'ELEC-PASSEFILS','P74_': 'MEC-SUPPORTS-ENERGIE',
         'P75_': 'ELEC-PASSEFILS','P76_': 'MEC-SUPPORTS-ENERGIE',
         'P77_': 'ELEC-PASSEFILS','P78_': 'ELEC-PASSEFILS',
         'P79_': 'ELEC-PASSEFILS','P80_': 'ELEC-PASSEFILS'}


def owner(source, ids):
    name = Path(source).stem
    for prefix,bom in OWNER.items():
        if name.startswith(prefix):
            return bom
    if 'Sorbothane_0510030' in name: return 'MEC-SORBOTHANE-BAS'
    if 'Sorbothane_0510010' in name: return 'MEC-SORBOTHANE-HAUT'
    if 'Vis_M2x25' in name: return 'MEC-VIS-ISOLATION'
    if 'Ecrou_frein_M2' in name: return 'MEC-ECROU-ISOLATION'
    return ids[0] if len(ids)==1 else ''


def extract():
    build = read(VER/'construction_prototype.json')
    reader = Reader(MEC)
    hashes = {r['fichier']: sha(MEC/r['fichier']) for r in build['references']}
    hashes.update({p:sha(MEC/p) for p in build['sources_preservees']})
    references = {}
    def reference(path, obj):
        key=path+'#'+obj
        if key not in references:
            shape=reader.shape(path,obj)
            if shape is None or shape.isNull(): raise ValueError('Forme absente : '+key)
            b=shape.BoundBox
            solid=shape.Solids[0] if len(shape.Solids)==1 else None
            c=solid.CenterOfMass if solid is not None else None
            references[key]={'reference':Path(path).stem,'fichier':path,'objet':obj,
                'sha256':sha(MEC/path),'valide':shape.isValid(),'solides':len(shape.Solids),
                'volume_mm3':shape.Volume,'centre_volume_mm':[c.x,c.y,c.z] if c is not None else None,
                'inertie_volumique_mm5':list(solid.MatrixOfInertia.A) if solid is not None else None,
                'bbox_mm':[b.XMin,b.YMin,b.ZMin,b.XMax,b.YMax,b.ZMax]}
        return references[key]
    physical=[]
    oem_mapping={(m['parent'],m['occurrence']):m for m in read(VER/'orch_cao_masse_structure.json')['mapping_oem']}
    def add(path,obj,identifier,ids,matrix,notes=''):
        ref=reference(path,obj)
        shape=reader.occurrence({'source':path,'objet_source':obj,'matrice':matrix})
        solid=shape.Solids[0] if len(shape.Solids)==1 else None
        centre=solid.CenterOfMass if solid is not None else None
        physical.append({'id':identifier,'source':path,'objet_source':obj,'bom_ids':ids,
            'proprietaire_masse_bom':owner(path,ids),'matrice_mm':matrix,
            'centre_volume_global_mm':[centre.x,centre.y,centre.z] if centre is not None else None,
            'inertie_volumique_globale_mm5':list(solid.MatrixOfInertia.A) if solid is not None else None,
            'valide':ref['valide'],'limites':notes})
    for index,row in enumerate(build['occurrences']):
        if row['parent']==build['assemblage']: continue
        path,obj=row['source'],row['objet_source'];identifier=row['parent']+'#'+row['occurrence']
        if path=='pieces/commerce/EQ_Chassis_X650.FCStd':
            mapping=oem_mapping[(row['parent'],row['occurrence'])]
            for leaf in mapping['feuilles']:
                data=leaf['geometrie'];reference(path,leaf['objet_source'])
                physical.append({'id':leaf['chemin_occurrence'],'source':path,
                    'objet_source':leaf['objet_source'],'bom_ids':leaf['bom_ids'],
                    'proprietaire_masse_bom':owner(path,leaf['bom_ids']),
                    'matrice_mm':data['matrice_placement_global'],
                    'valide':data['valide'],'limites':leaf.get('limites'),
                    'rattachement':leaf['statut_rattachement']})
        elif path=='sous_assemblages/SA05B_Appui_Sorbothane.FCStd':
            _,objects=reader.xml(path)
            for child in objects[obj]['Group'].find('LinkList'):
                name=child.get('value');p=objects[name]
                if 'LinkedObject' not in p: continue
                link=p['LinkedObject'].find('XLink')
                target=((MEC/path).parent/link.get('file')).resolve()
                relative=target.relative_to(MEC).as_posix();target_obj=link.get('name')
                pose=App.Placement(App.Matrix(*row['matrice'])).multiply(reader.placement(path,obj).inverse()).multiply(reader.placement(path,name))
                add(relative,target_obj,identifier+'/'+name,row['bom_ids'],list(pose.toMatrix().A))
        else:
            add(path,obj,identifier,row['bom_ids'],row['matrice'],
                'Ensemble OEM : détail géométrique interne porté par mapping_oem du lot structure.' if path.endswith('EQ_Chassis_X650.FCStd') else '')
        if index%40==0: print('Extraction géométrique '+str(index),flush=True)
    for row in build['references']:
        if row['type'] not in ('sous_assemblage','assemblage_final'):
            reference(row['fichier'],row['objet'])
    result={'lot':'ORCH-CAO-MASSE-1','date_utc':datetime.now(timezone.utc).isoformat(),
        'script_sha256':sha(__file__),'lecteur_sha256':sha(VER/'read_brep_prototype.py'),
        'environnement':{'freecad':App.Version(),'unites':'mm, mm3, mm5 ; aucun calcul de masse'},
        'references':list(references.values()),'occurrences_physiques':physical,
        'natifs_sha256':hashes,'natifs_non_modifies':all(sha(MEC/p)==h for p,h in hashes.items()),
        'finalisation_correcte':True,'qualification':'À valider',
        'limites':['Les ensembles commerciaux complexes ne sont pas homogènes.',
                   'Les géométries internes non réconciliées demeurent des blocages.']}
    write(VER/'orch_cao_masse_geometrie.json',result)
    print(json.dumps({'references_lues':len(references),'occurrences_physiques':len(physical),
                      'formes_invalides':sum(not r['valide'] for r in physical)}),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--integrate',action='store_true');parser.add_argument('--extract',action='store_true');args=parser.parse_args(CLI_ARGUMENTS)
    if args.integrate: integration()
    elif args.extract: extract()
    else: parser.error('Choisir --integrate ou --extract')
    sys.stdout.flush();sys.stderr.flush()
    os._exit(0)
