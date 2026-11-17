"""Rattache les contrôles indépendants aux mêmes octets natifs et à la référence."""
from collections import Counter
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def key(row):
    return tuple(sorted(row['pair']))


def envelope(occurrences):
    bounds = [r['bbox_mm'] for r in occurrences.values()]
    return [min(b[i] for b in bounds) for i in range(3)]+[max(b[i] for b in bounds) for i in range(3,6)]


def main():
    sources = {name: HERE/name for name in (
        'installation.json','controles_geometrie_delta.json','controles_reouverture.json',
        'controles_reprise_paires.json','etude_corridors_revue.json','controles_revue.json',
        'mobilite.json','mobilite_variantes_m8.json','validation_variantes.json',
        'inventaire.json','planificateur_compatible.json','planificateur_separate.json','controles_vues/sources.json')}
    sources['controle_reference'] = ROOT/'.runtime/refonte-controles/baseline-opt.json'
    data = {k:read(p) for k,p in sources.items()}
    before, delta, fresh = (data[k] for k in ('controle_reference','controles_geometrie_delta.json','controles_reouverture.json'))
    retry, review = data['controles_reprise_paires.json'],data['etude_corridors_revue.json']
    install = data['installation.json']
    route_review = data['controles_revue.json']
    assert all(r['complete'] for r in (before,delta,fresh,retry))
    assert before['inputs_sha256']==delta['reference_inputs_sha256']
    assert delta['inputs_sha256']==fresh['inputs_sha256']
    assert {k:v for k,v in fresh['inputs_sha256'].items() if k.endswith('.FCStd')}==install['modeles_natifs_sha256']
    assert retry['source_sha256']==sha(sources['controles_geometrie_delta.json'])
    assert route_review['status']=='pass' and route_review['inputs_sha256']['inventaire.json']==sha(sources['inventaire.json'])
    assert review['saved_copy_reviewed'] and review['reviewed_hashes']['installation']==sha(sources['installation.json'])

    existing = {key(row):row for row in before['pairs']['near_or_invalid_pairs']}
    updates = {key(row):row for row in retry['reprises']['pairs']}
    guides = {row['id']:row for row in review['final_guide_checks'] if row.get('matches_installation')}
    touched = set(delta['pairs']['touched'])
    volume_tol = delta['tolerances']['volume_mm3']
    rows = {k:row for k,row in existing.items() if set(k).isdisjoint(touched)}
    monotone = []
    for row in delta['pairs']['near_or_invalid_pairs']:
        k = key(row)
        selected = dict(updates[k], clearance_status=row['clearance_status']) if k in updates else row
        old = existing.get(k,{})
        if selected['intersection_status']=='unknown' and old.get('intersection_status')=='pass':
            modified = set(k)&touched
            guide = guides.get(next(iter(modified)).split('#')[-1]) if len(modified)==1 else None
            if guide:
                upper = old['overlap_bounds_mm3'][1] + abs(guide['added_mm3'])
                if upper <= volume_tol:
                    selected = dict(selected,intersection_status='pass',overlap_bounds_mm3=[0,upper],
                                    methode='Guide par retraits uniquement, borne de matière ajoutée et preuve BRep sur référence identique.')
                    monotone.append(selected)
        rows[k] = selected
    counts = dict(Counter(r['intersection_status'] for r in rows.values()))
    remote = (before['pairs']['disjoint_by_AABB_above_near_threshold']-
              delta['reference_pairs']['disjoint_by_AABB_above_near_threshold']+
              delta['pairs']['disjoint_by_AABB_above_near_threshold'])
    pairs = before['pairs']['considered_pairs']-delta['reference_pairs']['considered_pairs']+delta['pairs']['considered_pairs']
    assert remote+sum(counts.values())==pairs
    relations = [r for r in rows.values() if r.get('relation',{}).get('zone_nominale_confirmee')]
    remaining = [r for r in rows.values() if r['intersection_status']!='pass' and r not in relations]
    distances = [r['pair'] for r in rows.values() if r.get('clearance_status')=='unknown']
    motion = data['mobilite.json']
    f16 = [x for pose in motion['f16'] for x in pose['controle'].values()]
    report = {
        'schema':'cartographe.refonte.validation-geometrique.v1', 'complete':True,
        'statut':'CANDIDAT_CONDITIONNEL', 'sources':{k:{'path':p.relative_to(ROOT).as_posix(),'sha256':sha(p)} for k,p in sources.items()},
        'portee':'Paires impliquant au moins un câble, une gaine ou un guide, au nominal. Les paires structure contre structure et les seuils de montage ne relèvent pas de ce verdict.',
        'geometrie_fraiche':{'gate':fresh['gates']['fresh'],'natifs':len(fresh['fresh']['entry']['documents']),
                             'cables':len(fresh['fresh']['routes']),'gaines_guides':len(fresh['fresh']['protections']),
                             'mesures_de_stations':len(delta['stations']['measurements'])},
        'intersections':{'paires_finales':pairs,'paires_touchees':delta['pairs']['considered_pairs'],
                          'paires_reprises_reference':pairs-delta['pairs']['considered_pairs'],
                          'aabb_disjointes_distance_superieure_1_mm':remote,'statuts_paires_proches':counts,
                          'paires_justifiees_par_retrait_de_matiere':monotone,
                          'relations_airy_heritees':relations,'anomalies_ou_inconnues':remaining,
                          'distances_exactes_inconnues':distances,'tolerance_mm3':volume_tol},
        'inclusion':delta['protections'],
        'comparaison':dict(delta['comparison'],bbox_global_avant_mm=envelope(before['occurrences']),
                           bbox_global_apres_mm=envelope(delta['occurrences'])),
        'mobilite':{'f16_poses':len(motion['f16']),'f16_paires_diff':sum(x['obstacles'] for x in f16),
                    'f16_ecarts_diff':sum(bool(x['recouvrements'] or x['inconnues']) for x in f16),
                    'm8_poses':len(motion['m8']),'m8_echecs_tangence':sum(x['generation']=='fail' for x in motion['m8'])},
        'validations_physiques_restantes':[
            'Terminaisons, brochages et neuf définitions embarquées non résolues.',
            'Jeux sous tolérances, fermeture et retenue des gaines, extraction des prises et outils, pliage des bras.',
            'Résistance des guides après retrait, serrage et abrasion, quatre stations de gaine commune au nord à redéfinir.',
            'CEM, échauffement, courant et tenue en cas de dommage commun. Masse complète et réserve réelle.',
            'Course caméra, pince, traction, torsion et fatigue F16/M8. Les 27 poses F16 et le sondage M8 restent discrets.'
        ]}
    (HERE/'validation_geometrique.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print('Paires',pairs,'paires proches',counts,'Airy',len(relations),'autres anomalies',len(remaining))


if __name__=='__main__':
    main()
