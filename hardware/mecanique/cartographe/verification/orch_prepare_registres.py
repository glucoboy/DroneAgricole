"""Synchronisation déclarative des sources du lot vers la BOM canonique.

Aucun calcul de masse : les volumes, densités et valeurs publiées restent des
entrées, consommées par l'outil C++17 cartographe-bom-mass.
"""
from pathlib import Path
import hashlib
import json

ROOT=Path(__file__).resolve().parents[4]
MEC=ROOT/'hardware/mecanique/cartographe'
VER=MEC/'verification'


def read(p): return json.loads(Path(p).read_text('utf-8-sig'))
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,v): Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n','utf-8')


def workspace_path(value):
    p=Path(value)
    if p.is_absolute():
        p=p.resolve()
    elif value.replace('\\','/').startswith(('hardware/','.runtime/','simulation/','software/')):
        p=ROOT/p
    else:
        p=MEC/p
    p=p.resolve()
    p.relative_to(ROOT)
    return p


def prepare():
    from orch_reprise_registres import refresh_geometry_labels
    refresh_geometry_labels()
    bom=read(MEC/'nomenclature_prototype.json')
    build=read(VER/'construction_prototype.json')
    proofs={name:read(VER/('orch_cao_masse_'+name+'.json')) for name in ('structure','equipements','fabrication')}
    if not all(p.get('finalisation_correcte') for p in proofs.values()):
        raise ValueError('Investigations non finalisées : vérifier les contrôles, sans transformer les blocages matériels en succès.')
    sources=[];hashes={};by_id={};geometry={};blockers=[];mass={}
    for axis,proof in proofs.items():
        name='hardware/mecanique/cartographe/verification/orch_cao_masse_'+axis+'.json'
        hashes[name]=sha(ROOT/name)
        recipe_name='hardware/mecanique/cartographe/verification/orch_'+('fabrication' if axis=='fabrication' else 'equipements' if axis=='equipements' else 'structure')+'_cao.py'
        hashes[recipe_name]=sha(ROOT/recipe_name)
        if proof.get('script_sha256') and proof['script_sha256']!=hashes[recipe_name]:raise ValueError('Recette différente de sa preuve : '+axis)
        for source in proof['sources']:
            s=dict(source)
            if s.get('fichier'):
                p=workspace_path(s['fichier']);actual=sha(p)
                if s.get('sha256') and s['sha256']!=actual: raise ValueError('Source divergente : '+str(p))
                s['fichier']=p.relative_to(ROOT).as_posix();s['sha256']=actual;hashes[s['fichier']]=actual
            if s['id'] in by_id and by_id[s['id']]!=s: raise ValueError('Identifiant source ambigu : '+s['id'])
            by_id[s['id']]=s;sources.append(s)
        blockers.extend(proof.get('blocages',[]))
        for g in proof.get('geometries',[]):
            if g.get('fichier'):
                file=workspace_path(g['fichier']);geometry[file.relative_to(MEC).as_posix()]=g
        for value in proof.get('masses',[]): mass[value['bom_id']]=value
    recipes={}
    for spec in proofs['fabrication']['fabrication']:
        r=dict(spec);r['methode']='tranchage' if 'FFF' in r['procede'] else 'volume_solide_terminal'
        file=workspace_path(r['fichier']);r['sha256_natif']=sha(file)
        recorded=geometry.get(file.relative_to(MEC).as_posix(),{}).get('sha256')
        if not recorded or recorded!=r['sha256_natif']:raise ValueError('Géométrie fabriquée modifiée après preuve : '+str(file))
        if r['methode']=='tranchage':
            sliced=r.get('tranchage',{})
            if sliced.get('sha256_natif_source')!=r['sha256_natif']:raise ValueError('Natif du tranchage différent de la recette : '+str(file))
            for field in ('stl','gcode','log'):
                if sliced.get(field):
                    p=workspace_path(sliced[field]);actual=sha(p)
                    if actual!=sliced[field+'_sha256']: raise ValueError('Tranchage périmé : '+str(p))
                    hashes[p.relative_to(ROOT).as_posix()]=actual
        recipes[file.relative_to(MEC).as_posix()]=r
    slice_info=proofs['fabrication'].get('tranchage_tpu',{})
    for profile in slice_info.get('profils',[]):
        p=workspace_path(profile['fichier'])
        if sha(p)!=profile['sha256']:raise ValueError('Profil de tranchage modifié')
        hashes[p.relative_to(ROOT).as_posix()]=profile['sha256']
    route=next(r for r in proofs['fabrication']['routes'] if r['id']=='F_M8')
    line=proofs['fabrication']['donnees_lineiques']
    if isinstance(line,list):line=next(r for r in line if r['reference']=='Phoenix1522341')
    occurrence=next(r for r in build['occurrences'] if r['occurrence']=='F_M8')
    if geometry.get(occurrence['source'],{}).get('sha256')!=sha(MEC/occurrence['source']):raise ValueError('RouteM8 modifiée depuis sa preuve de longueur')
    harness={occurrence['source']:{'methode':'masse_lineique_parcours','sha256_natif':sha(MEC/occurrence['source']),
        'longueur_parcours_mm':route['longueur_courbe_mm'],'masse_lineique_g_m':line['masse_lineique_g_m'],
        'source_ids':line['source_ids'],'incertitude_g_m':line.get('incertitude_g_m'),
        'conditions':'Segment de câble Phoenix1522341 correspondant au seul parcours CAO ; coupe et engagements non libérés.',
        'inclusions':'CâblePUR6×0,14mm² seul, conducteurs et gaine.',
        'exclusions':'SurmoulageM8, connecteurPH ajouté, contacts, longueurs internes et surlongueurs inconnues.'}}
    applicable={'ELEC-CONNECTEUR-MANUEL','SEN-LIDAR','SEN-LENS','AVI-CPU'}
    for item in bom['items']:
        if item['perimetre']!='embarque':continue
        record=mass.get(item['id'],{})
        value=record.get('masse_unitaire_g')
        qualifier='inconnue' if value is None else 'nominale'
        if record.get('relation') in ('<','<='):qualifier='maximale'
        if item['id']=='SEN-LENS':qualifier='approximative'
        for source in record.get('source_ids',[]):
            if source not in by_id: raise ValueError('Source massique inconnue : '+source)
        item['donnee_massique']={
            'nature':record.get('nature','inconnue'),'qualificatif':qualifier,
            'relation':record.get('relation'),'valeur_g':value,
            'applicable':item['id'] in applicable and value is not None,
            'incertitude_g':record.get('incertitude_g'),
            'source_ids':record.get('source_ids',[]),
            'conditions':record.get('conditions','Masse installée non documentée ; aucune assimilation à zéro.'),
            'inclusions':record.get('inclusions',[]),'exclusions':record.get('exclusions',[]),
            'valeurs_documentaires_conditionnelles':record.get('valeurs_documentaires_conditionnelles',[])}
        if 'valeur_documentaire_conditionnelle_g' in record:
            item['donnee_massique']['valeur_documentaire_conditionnelle_g']=record['valeur_documentaire_conditionnelle_g']
        item['masse_unitaire_g']=value if item['donnee_massique']['applicable'] and qualifier in ('nominale','approximative') else None
        item['masse_nature']=record.get('qualificatif','Inconnue ; voir détail de réconciliation du lot')
        if value is not None and not item['donnee_massique']['applicable']:
            item['masse_nature']+=' ; valeur documentaire '+qualifier+' conservée dans donnee_massique, masse installée inconnue'
        if record.get('masse_incluse_dans') is not None:item['masse_incluse_dans']=record['masse_incluse_dans']
        item['detail_physique_complet']=False
        item['sources_geometriques']=[dict(fichier=file,preuve='verification/orch_cao_masse_'+axis+'.json')
            for axis,proof in proofs.items() for g in proof.get('geometries',[])
            if item['id'] in g.get('bom_ids',[]) and g.get('fichier')
            for file in [workspace_path(g['fichier']).relative_to(MEC).as_posix()]]
        if item['id']=='ELEC-F16':
            item['reference_fabricant']=item['reference_fabricant'].replace('Type A coudé','Type A droit')
        if item['id']=='MEC-MOTEUR':
            item['variantes_conservees']=[{'reference_oem':'31228','rotation':'CW','quantite_absolue_drone':2},
                                          {'reference_oem':'31229','rotation':'CCW','quantite_absolue_drone':2}]
        item['source_reconciliation']='verification/controle_orch_cao_masse_1.json'
        extra=['hardware/mecanique/cartographe/verification/orch_cao_masse_'+axis+'.json'
               for axis,proof in proofs.items() if any(item['id']==value.get('bom_id') for value in proof.get('masses',[]))]
        item['sources']=list(dict.fromkeys(item.get('sources',[])+extra))
    bom['orch_cao_masse_1']={
        'lot':'ORCH-CAO-MASSE-1','statut':'Implémenté','qualification':'À valider','lot_clos':False,
        'configuration':'prototype_cartographe sans dock',
        'convention_quantites':'Tous contenus physiques exprimés en quantités absolues pour un drone.',
        'fabrications_candidates':recipes,'faisceaux_calcules_partiels':harness,'sources':sources,'preuves_sources_sha256':hashes,
        'blocages':blockers,'sources_geometriques_par_fichier':geometry,
        'priorite':'Complétude géométrique et massique avant études de vol, consommation et autonomie.',
        'campagnes_gazebo_px4_suspendues':True,
        'limites':['Données physiques inconnues, matières candidates et approximations ne deviennent pas des mesures.',
                   'Les 44 MPN CA01 manquants restent ouverts ; aucune référence arbitraire sélectionnée.',
                   'Les contrôles et rendus antérieurs sont historiques après évolution des dépendances.']}
    bom['orch_cao_masse_1']['preuves_sources_sha256']['hardware/mecanique/cartographe/verification/orch_prepare_registres.py']=sha(__file__)
    bom['date']='2026-10-25'
    for source in bom.get('sources_techniques',[]):
        if source['fichier']=='hardware/mecanique/cartographe/verification/construction_prototype.json':
            source.setdefault('sha256_precedent',source['sha256'])
            source['sha256']=sha(VER/'construction_prototype.json')
            source['portee']='Construction ORCH-CAO-MASSE-1 ; version précédente conservée dans verification/historique/orch_cao_masse_1/.'
        elif Path(source['fichier']).name in ('controle_fixations_equipements_prototype.json','controle_colliers_prototype.json'):
            original=VER/'historique/orch_cao_masse_1'/Path(source['fichier']).name
            if sha(original)!=source['sha256']:raise ValueError('Preuve historique différente : '+str(original))
            source['fichier']=original.relative_to(ROOT).as_posix()
            source['portee']='Historique22octobre, ne décrit pas les géométries ORCH modifiées.'
    if build.get('orch_cao_masse_1'):
        resolution=bom['resolution_definition']
        resolution.update(date='2026-10-25',nombre_references_cao=len(build['references']),
            nombre_occurrences_cao=len(build['occurrences']),
            statut='Inventaire ORCH-CAO-MASSE-1 rapproché ; définition géométrique et massique incomplète, blocages ouverts.',
            distinction_reserves='Les20compléments initiaux ne remplacent pas les blocages ORCH, les masses manquantes ou les non-conformités géométriques observées. Aucune libération matérielle.',
            preuve_orch='hardware/mecanique/cartographe/verification/controle_orch_cao_masse_1.json')
    from orch_reprise_registres import enrich
    enrich(bom,build)
    write(MEC/'nomenclature_prototype.json',bom)
    print(json.dumps({'sources':len(sources),'fabrications_candidates':len(recipes),'blocages_identifies':len(blockers)}))


if __name__=='__main__': prepare()
