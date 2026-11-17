"""Assembler les preuves et empreintes, sans modifier la conception active."""
from pathlib import Path
import hashlib
import json
import shutil
from datetime import datetime, timezone

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[4]
COPY=ROOT/'hardware/mecanique/cartographe_faisceaux'
def read(path):return json.loads(Path(path).read_text('utf-8'))
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path,data):Path(path).write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')

receipt=read(COPY/'experiment.json')
preservation=[]
for name,digest in receipt['inputs_sha256'].items():
    source=Path(receipt['source_root'])/name;copy=COPY/name
    preservation.append({'file':name,'sha256':digest,'source_unchanged':sha(source)==digest,'copy_unchanged':sha(copy)==digest})
assert all(p['source_unchanged'] and p['copy_unchanged'] for p in preservation)
extra={}
for filename in ['analyse_connectivite.json','analyse_mecanique_f16.json']:
    for record in read(OUT/filename)['sources']:
        path=record.get('path',record.get('file'))
        assert sha(ROOT/path)==record['sha256'],path
        extra[path]=record['sha256']
n=read(OUT/'recalcul_natif.json');eq=read(OUT/'equivalence_solides.json')
b=read(OUT/'baseline_volumes.json');f=read(OUT/'comparaison_f16.json')
assert n['complete'] and eq['complete'] and b['complete'] and f['volumes_complete']
refine=read(OUT/'affinage_volumes.json')
assert refine['complete'] and refine['baseline_sha256']==sha(OUT/'baseline_volumes.json')
refined={tuple(p['pair']):p for p in refine['refined_pairs']}
unresolved=[p for p in b['unknown_pairs'] if tuple(p.get('pair',[])) not in refined]
unresolved += [p for p in refine['refined_pairs'] if p['status']=='unknown']
refined_collisions=[p for p in refine['refined_pairs'] if p.get('intersection_volume_mm3',0)>1e-4]
assert len(refined)==len(b['unknown_pairs'])
length=sum(r['route']['length_mm'] for r in n['routes'])
minimum=min(r['route']['minimum_radius_mm'] for r in n['routes'] if r['route']['minimum_radius_mm'] is not None)
test_source=ROOT/'.runtime/reconstruction-faisceaux/freecad-tests.json'
shutil.copyfile(test_source,OUT/'tests_freecad_skill.json')
result={
 'schema':'cartographe.reconstruction.bilan.v1','date_utc':datetime.now(timezone.utc).isoformat(),
 'status':'NON_VERIFIE','maturity':'À valider','mission_complete':False,
 'decision':'F16 initial conservé dans assemblage copie ; candidat séparé ; phase D non engagée',
 'preservation':{'files':preservation,'additional_sources_sha256':extra,'all_originals_unchanged':True},
 'environment':n['environment'],
 'phases':{'offline':'executed_unresolved','generation':'executed_F16_only','recompute':'passed_53_plus_candidate',
    'saved_reopened':'passed','global_reconstruction':'not_executed_F16_and_compatibility_gate',
    'interactive':'not_executed','physical':'not_executed'},
 'comparison_global':{'scope':'Initial versus identical isolated assembly; prototype candidate excluded from cable sum',
   'cad_routes':{'before':53,'after':53},'logical_active_connections':{'before':None,'after':None},
   'physical_harnesses':{'before':None,'after':None},'common_sleeves':{'before':None,'after':None,'new_created':0},
   'cable_axis_length_mm':{'before':length,'after':length},'shared_physical_length_mm':{'before':None,'after':None},
   'branches':{'before':None,'after':None},'mounted_fixations':{'before':None,'after':None},
   'minimum_analytic_radius_mm':{'before':minimum,'after':minimum,'supplier_compliance':None},
   'valid_cable_solids':{'before':53,'after':53},'complete_mass_g':{'before':None,'after':None},
   'clearance_compliance':None,'all_forbidden_collisions_absent':None},
 'validation':{'skill_tests_passed':19,'fresh_baseline_cables':len(n['routes']),
   'volume_equivalence_passed':sum(r['pass_equivalence'] for r in eq['routes']),
   'identity_poses_verified':len(eq['placements']),'global_pairs_considered':b['pair_checks'],
   'initial_timeout_pairs':len(b['unknown_pairs']),'refined_pairs':len(refined),'remaining_unknown_pairs':unresolved,
   'raw_airy_envelope_intersections':b['collisions'],'additional_intersections':refined_collisions,
   'airy_local_zone_checks':refine['airy_junctions'],
   'global_interpretation':'Absence d’intersection hors réserves seulement selon preuves ; intérieur jonction Airy, jeux, mouvements et seuils physiques non qualifiés'},
 'f16':{'baseline':{k:f['candidates'][0][k] for k in ['route','stations','length_reserve_mm','collision_count','unknown_count','minimum_clearance_mm']},
   'candidate':{k:f['candidates'][1][k] for k in ['route','stations','length_reserve_mm','collision_count','unknown_count','minimum_clearance_mm']},
   'accepted_for_global_reconstruction':False,'condition_48mm':'Application aux mouvements caméra à confirmer ; chemins testés insuffisants si applicable'},
 'unknowns_and_next_decisions':[
   'Confirmer les axes et engagements des prises sur la variante exacte, la longueur utile du cordon USB et la course de suspension caméra.',
   'Établir la condition de flexion applicable puis router une boucle et des retenues compatibles, ou revoir référence/longueur du cordon.',
   'Justifier courant, retours, blindages, thermique et indépendance fonctionnelle de chaque gaine ; conserver unknown jusque-là.',
   'Choisir protections et parois, reprendre guides/retours et définir points de dérivation et retenues accessibles.',
   'Mesurer extraction des connecteurs, accès outil, débattements bras/caméra et zones hélices/ventilation, confirmer tolérances et montage.',
   'Établir modèle de jonction OEM Airy et compter composants physiques/fixations sans confondre postes BOM, conducteurs et objets CAO.'],
 'original_files_modified':[],
 'living_documents_modified':['docs/architecture/ARCHITECTURE_MECANIQUE.md','docs/architecture/ARCHITECTURE_ELECTRIQUE_RESEAUX.md','docs/VALIDATION_QUALIFICATION.md'],
 'recipe':[
  'workspace_guard.py stage : reçu experiment.json, copie nouvelle, dépendances XLink et extras explicités',
  'Python FreeCAD -B mesurer_copie.py native puis assembly',
  'Planificateur C++17 plan entree_planificateur.json resultat_planificateur.json .runtime/reconstruction-faisceaux/resultat_planificateur.md',
  'Python FreeCAD -B prototype_f16.py run puis reopen puis volumes (run refuse un candidat déjà existant)',
  'Python FreeCAD -B mesurer_copie.py equivalence',
  'Python FreeCAD -B terminer_volumes.py run : reprendre checkpoint incomplet, sans reconstruire les sources',
  'Python FreeCAD -B affiner_volumes.py : reprendre uniquement contrôle incomplet, ne pas écraser preuve terminée',
  'C++17 dimensionnement_gaines.cpp : binaire et entrées empreintés dans dimensionnement_gaines.json',
  'Rendu render_vues.py ; consulter manifest.json des vues ; finaliser_preuves.py agrège les preuves'
 ]}
result['evidence_sha256']={p.relative_to(ROOT).as_posix():sha(p) for p in OUT.iterdir() if p.is_file() and p.name not in ['bilan.json','revue_reconstruction.json']}
for path in [OUT/'vues/manifest.json',ROOT/'.agents/skills/electromechanical-integration/scripts/freecad_geometry.py',ROOT/'.agents/skills/electromechanical-integration/scripts/workspace_guard.py']:
    result['evidence_sha256'][path.relative_to(ROOT).as_posix()]=sha(path)
result['output_native_sha256']={p.relative_to(COPY).as_posix():sha(p) for p in (COPY/'verification/candidats').glob('*.FCStd')}
result['living_document_sha256']={name:sha(ROOT/name) for name in result['living_documents_modified']}
write(OUT/'bilan.json',result)
write(COPY/'manifest_essai.json',{'status':'NON_VERIFIE','assembly':'assemblages/Prototype_Cartographe.FCStd',
 'configuration':'copie_isolee_baseline_conservee','source_receipt':'experiment.json','global_reconstruction':False,
 'candidate_files':result['output_native_sha256'],'evidence':'../cartographe/verification/reconstruction_faisceaux/bilan.json',
 'evidence_sha256':sha(OUT/'bilan.json'),'note':'Le manifeste original copié reste un document de baseline ; aucun changement de configuration active.'})
print(json.dumps({'preserved_files':len(preservation),'remaining_unknown_pairs':len(unresolved),'new_collisions':len(refined_collisions),'evidence':str(OUT/'bilan.json')}))
