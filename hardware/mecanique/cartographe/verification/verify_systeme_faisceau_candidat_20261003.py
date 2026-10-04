"""Infrastructure de vérification BRep, masse partielle et préservation des sources.

Lecture seule des natifs. Une finalisation de preuve n’est pas une conformité.
"""
from pathlib import Path
from collections import Counter
import hashlib,json,time,itertools
import FreeCAD as A
import Part

ROOT=Path(__file__).resolve().parents[4];MEC=ROOT/'hardware/mecanique/cartographe';VER=MEC/'verification'
start=time.time()
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def write(p,data):Path(p).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
construction=read(VER/'construction_systeme_faisceau_20261003.json')
sources=construction['sources_preservees_sha256']
assert all(sha(ROOT/f)==h for f,h in sources.items()),'Source existante modifiée'
assert all(sha(ROOT/r['fichier'])==r['sha256'] for r in construction['nouveaux_fichiers']), 'Natif candidat changé depuis construction'
top=A.openDocument(str(MEC/'assemblages/Drone_Cartographe_Systeme_Candidat.FCStd'))
for d in list(A.listDocuments().values()):d.recompute()
errors=[{'document':d.Name,'objet':o.Name,'etat':list(o.State)} for d in A.listDocuments().values() for o in d.Objects if 'Invalid' in o.State]
assert not errors,errors
root=top.getObject('Reference')
shapes={o.Name:o.Shape.copy() for o in root.Group if o.TypeId=='App::Link' and o.Name!='Faisceau_Systeme'}
body_pairs=[]
for a,b in itertools.combinations(shapes,2):
    # On contrôle les nouveaux équipements face aux trois sous-systèmes conservés.
    if not ({a,b}&{'Stack_Holybro_CA01','Distribution_PM_PDB','GNSS_Helical'}):continue
    sa,sb=shapes[a],shapes[b]
    volume=sa.common(sb).Volume if sa.BoundBox.intersect(sb.BoundBox) else 0
    body_pairs.append({'a':a,'b':b,'intersection_mm3':volume})
print(json.dumps({'phase':'equipements','interferences':[r for r in body_pairs if r['intersection_mm3']>1e-6]}),flush=True)
hdoc=next(d for d in A.listDocuments().values() if d.Name=='SA08_Faisceau_Systeme_Candidat')
route_results=[]
for route in construction['routes']:
    link=hdoc.getObject(route['id']);assert link and link.LinkedObject
    shape=link.Shape;assert shape.isValid() and len(shape.Solids)==1,route['id']
    collisions=[]
    for name,s in shapes.items():
        if not shape.BoundBox.intersect(s.BoundBox):continue
        volume=shape.common(s).Volume
        if volume>1e-6:collisions.append({'equipement':name,'volume_mm3':volume})
    route_results.append({'id':route['id'],'forme_valide':True,
        'intersections_nominales':collisions,'rayon_reservation_respecte':route['rayon_reservation_respecte'],
        'qualification_passage':'À valider',
        'interpretation':'Intersection brute, y compris départs nominaux non cotés. Aucune exclusion automatique d’interface.'})
    print(json.dumps({'phase':'route','id':route['id'],'intersections':len(collisions)}),flush=True)

# Couverture fonctionnelle distincte de la couverture géométrique.
reg=read(ROOT/'hardware/electronique/cartographe/faisceau_systeme_cible_20261003.json')
cab=read(ROOT/reg['source_liaisons']);expected={c['id'] for c in cab['connections']}
counts=Counter(w for g in reg['groupes'] for w in g['wxx'])
assert set(counts)==expected and all(n==1 for n in counts.values()),'Couverture Wxx incorrecte'
route_groups={r['groupe'] for r in construction['routes']}
physical={g['id'] for g in reg['groupes'] if g['classe']=='faisceau_physique'}
unknown=sorted(physical-route_groups-{'F01-ENERGIE-AMONT'})
assert unknown==['F20-REFROIDISSEMENT','F25-ACCESSOIRES-VOL'],unknown

# Complément arithmétique indépendant de la masse totale cible inconnue.
rho=reg['budget_cuivre']['densite_cuivre_hypothese_g_cm3']
dock_copper=sum(x['section_mm2']*x['longueur_route_mm']/1000*rho for x in reg['budget_cuivre']['segments_dock_mesurables'])
dock=read(VER/'bom_dock20Ah_20261002.json')
historical=dock['bilan_masse_partiel'] if 'bilan_masse_partiel' in dock else dock['bilan_masse']
known=historical['sous_total_plus_TE_EPDM_commerces_connus_kg']
mass={'statut':'À valider','conclusion':'préliminaire',
    'budget_historique_partiel_kg':known,'cuivre_nominal_4_fils_ajoutes_dock_g':dock_copper,
    'budget_historique_plus_cuivre_nominal_kg':[m+dock_copper/1000 for m in known],
    'interpretation':'Complément du budget historique : cuivre nominal seul, pas masse du faisceau ni de la cible.',
    'masse_totale_cible_kg':None,'masse_totale_faisceau_g':None,
    'cuivre_reservations_routes_systeme_g':sum(r['masse_cuivre_hypothese_g'] or 0 for r in construction['routes']),
    'routes_cuivre_non_calculable':[r['id'] for r in construction['routes'] if r['masse_cuivre_hypothese_g'] is None],
    'regle':'Le dernier chiffre est un indicateur de géométrie, pas une addition au budget : il contient des fils OEM inclus et des doublons potentiels JETI/PM/kit.',
    'inconnues':['Isolants/étamage/blindage, fiches/contacts/protections/retenues',
                 'Loquet/gâche, matière et densité réellement fabriquées',
                 'Kit OEM réellement conservé après retrait de l’ancienne avionique',
                 'PDB nette, CA01 équipée, supports nouveaux, optique, SSD et accessoires',
                 'Périmètre masses PM08, pack, JETI et ensemble Holybro et tolérance pack ±20g'],
    'centrage_qualifie':False,'limite_X650_publiee_kg':6.3,
    'marge_demontree':False,'formule':'mCu[g]=section[mm²] × longueur[mm]/1000 × 8,96[g/cm³]'}
assert all(sha(ROOT/f)==h for f,h in sources.items()),'Source existante modifiée par contrôle'
write(VER/'bilan_masse_systeme_candidat_20261003.json',mass)
result={'date':'2026-10-03','configuration':construction['configuration'],
    'statut':'À valider','conclusion':'préliminaire','finalisation_correcte':True,
    'script_sha256':sha(__file__),'construction_sha256':sha(VER/'construction_systeme_faisceau_20261003.json'),
    'version_FreeCAD':A.Version(),'environnement':'Windows, Python FreeCAD 1.1.3, CAO candidate',
    'sources_preservees':len(sources),'sources_preservees_sha256':sources,
    'reouverture_recalcul_sans_erreur':not errors,'erreurs':errors,
    'couverture_Wxx':{'attendues':len(expected),'couvertes':len(counts),'doublons':[],'manquantes':[]},
    'routes_natives':len(route_results),'groupes_physiques_non_routes':unknown+['F-LED-KIT'],
    'equipements_intersections':body_pairs,'routes':route_results,
    'rayons_insuffisants':[r['id'] for r in route_results if not r['rayon_reservation_respecte']],
    'routes_avec_intersections':[r['id'] for r in route_results if r['intersections_nominales']],
    'fixations_completes':False,'faisceau_complet':False,'passages_valides':False,
    'essais_non_executes':['Accouplement/traction/rayons mesurés sur matériel','Tolérances et repli des bras',
        'Course continue cassette avec faisceau cible','Mouvement réel bloc capteurs',
        'Isolement/continuité/précharge/thermique/CEM','Pesée et centrage','Vol'],
    'limites':['Seuls équipements représentés, pose statique ; aucune nouvelle fixation démontrée.',
        'Sorties OEM, fiches accouplées et genres non cotés : pas d’approbation de fabrication.',
        'Contacts de fin de route et collisions véritables restent à classifier sur modèles exacts.',
        'Pas de contrôle inter-cordons, d’accès outil, d’enveloppes hélices ni de débattement dynamique.',
        'Une exécution réussie finalise cette preuve, pas la conception.'],
    'elapsed_seconds':time.time()-start}
write(VER/'controle_systeme_faisceau_20261003.json',result)
print(json.dumps({'finalisation_correcte':True,'routes':len(route_results),
    'intersections_routes':len(result['routes_avec_intersections']),
    'equipements_interferences':len([r for r in body_pairs if r['intersection_mm3']>1e-6]),
    'cuivre_dock_g':dock_copper,'budget_historique_plus_cuivre_kg':mass['budget_historique_plus_cuivre_nominal_kg']},ensure_ascii=False),flush=True)
