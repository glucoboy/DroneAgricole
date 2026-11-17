"""Correction FreeCAD des seuls diamètres de tête CHC documentés."""
from pathlib import Path
from datetime import datetime,timezone
import json,hashlib,os,sys
import FreeCAD as App
from orch_integrate_cao import save_assembly
ROOT=Path(__file__).resolve().parents[4];MEC=ROOT/'hardware/mecanique/cartographe';VER=MEC/'verification'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
proof_path=VER/'orch_reprise_tetes_chc.json';proof=json.loads(proof_path.read_text('utf-8-sig'))
assert proof['finalisation_correcte']
check=proof['contre_verification_brep'];assert check['sources_inchangees']
assert not check['intersections_positives'],check['intersections_positives']
inputs={k.replace('\\','/'):v for k,v in check['entrees_sha256'].items()}
changed=[]
for spec in proof['corrections_proposees']:
 p=MEC/spec['source'];before=sha(p);assert before==inputs[p.relative_to(ROOT).as_posix()]
 doc=App.openDocument(str(p));head=doc.getObject(spec['objet']);shaft=doc.Tige
 assert head.TypeId==spec['type'] and abs(head.Radius.Value-spec['avant_mm'])<1e-8
 assert abs(head.Height.Value-spec['hauteur_inchangee_mm'])<1e-8 and abs(shaft.Height.Value-spec['longueur_tige_inchangee_mm'])<1e-8
 head_pose=list(head.Placement.toMatrix().A);shaft_pose=list(shaft.Placement.toMatrix().A)
 head.Radius=spec['apres_mm'];head.touch();doc.recompute(None,True,True)
 assert doc.Ensemble.Shape.isValid() and all(s.isValid() for s in doc.Ensemble.Shape.Solids)
 assert list(head.Placement.toMatrix().A)==head_pose and list(shaft.Placement.toMatrix().A)==shaft_pose
 assert not [o.Name for o in doc.Objects if any(v in ('Error','Invalid') for v in o.State)]
 if 'LimiteGeometrique' not in doc.Ensemble.PropertiesList:doc.Ensemble.addProperty('App::PropertyString','LimiteGeometrique','Provenance')
 doc.Ensemble.LimiteGeometrique='Diamètre de tête selon référence documentaire ; filet, empreinte, chanfreins et congés simplifiés. Masse fournisseur indépendante du volume. Voir verification/orch_reprise_tetes_chc.json.'
 save_assembly(doc)
 changed.append({'fichier':spec['source'],'sha256_avant':before,'sha256_apres':sha(p),'objet':'Tete','parametre':'Radius','rayon_apres_mm':head.Radius.Value,'hauteur_inchangee_mm':head.Height.Value,'longueur_tige_inchangee_mm':shaft.Height.Value,'placement_tete':head_pose,'placement_tige':shaft_pose,'solides_valides':True})
out={'lot':'ORCH-CAO-MASSE-1','date_utc':datetime.now(timezone.utc).isoformat(),'script_sha256':sha(__file__),'proposition_sha256':sha(proof_path),'application':True,'natifs_modifies':changed,'occurrences_inchangees':check['occurrences'],'finalisation_correcte':True,'qualification':'À valider','limites':proof['maintien_des_limites']}
(VER/'orch_reprise_tetes_chc_application.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n','utf-8')
print(json.dumps({'natifs':len(changed),'placements_inchanges':len(check['occurrences'])}),flush=True)
sys.stdout.flush();sys.stderr.flush();os._exit(0)
