"""Contrôles natifs en processus neuf ; géométrie nominale, aucun essai matériel."""
from pathlib import Path
import json,hashlib,time
import FreeCAD as A
import Part
ROOT=Path(__file__).resolve().parents[4];MEC=ROOT/'hardware/mecanique/cartographe';VER=MEC/'verification'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def box(s):
    b=s.BoundBox;return [b.XMin,b.YMin,b.ZMin,b.XMax,b.YMax,b.ZMax]
start=time.time();build=read(VER/'construction_stack_revue_20261003.json')
for row in build['nouveaux_fichiers']:assert sha(ROOT/row['fichier'])==row['sha256']
for f,h in build['sources_preservees_sha256'].items():assert sha(ROOT/f)==h
t=A.openDocument(str(MEC/'assemblages/Integration_Stack_Revue_20261003.FCStd'))
for d in list(A.listDocuments().values()):d.recompute()
assert abs(t.getObject('ParametresIntegration').PoseHolybroZ.Value-build['montage']['pose_Holybro_Z_mm'])<1e-8
assert abs(t.getObject('Stack_Holybro_CA01').LinkPlacement.Base.z-build['montage']['pose_Holybro_Z_mm'])<1e-8
print('réouverture/recalcul terminé',flush=True)
errors=[{'doc':d.Name,'objet':o.Name,'etat':list(o.State)} for d in A.listDocuments().values() for o in d.Objects if 'Invalid' in o.State]
assert not errors,errors
card=next(d for d in A.listDocuments().values() if d.getObject('CarteCA01') and 'Revue' in d.Name)
s=next(d for d in A.listDocuments().values() if d.getObject('StackRevue'))
assert s.getObject('CA01').LinkedObject==card.getObject('CarteCA01')
assert s.getObject('Holybro').LinkedObject is not None
board=card.getObject('PCB');assert board.Shape.isValid()
assert sum(o.TypeId=='PartDesign::SubtractiveCylinder' for o in board.Group)==50
for row in read(VER/'percages_ca01_stack_20261003.json')['holes']:
    assert not board.Shape.isInside(A.Vector(*row['xy_mm'],.8),1e-7,True),row
comp=card.getObject('ComposantsKiCad');assert comp.Shape.isValid()
assert comp.SourceSHA256==build['step_sha256']
assert len(comp.Shape.Solids)==build['composants_solides']
holy=s.getObject('Holybro').Shape;ca=s.getObject('CA01').Shape
# Limiter les opérations booléennes aux solides dont les bboxes se croisent.
def common_filtered(a,b):
    if not a.BoundBox.intersect(b.BoundBox):return 0.0
    aa=[x for x in a.Solids if x.BoundBox.intersect(b.BoundBox)]
    bb=[x for x in b.Solids if any(x.BoundBox.intersect(y.BoundBox) for y in aa)]
    aa=[x for x in aa if any(x.BoundBox.intersect(y.BoundBox) for y in bb)]
    return sum(x.common(y).Volume for x in aa for y in bb if x.BoundBox.intersect(y.BoundBox)) if aa and bb else 0.0
internal=common_filtered(holy,ca);assert internal<1e-6
print('interne cartes terminé',flush=True)
chassis=t.getObject('SA01_Chassis_Rehausse20').LinkedObject
plate=chassis.Document.getObject('Part__Feature312').Shape
plate_xy=box(plate);assert abs(plate.BoundBox.ZMax+90)<1e-6
poses=[]
for z in build['pose_comparaison_electronique_z_mm']:
    t.getObject('ParametresIntegration').PoseHolybroZ=z;t.recompute()
    # Comparaison des seules cartes. Les fixations sont contrôlées séparément
    # dans la pose de montage ; les déplacer en bloc ne monte pas une autre pose.
    stack=Part.makeCompound([holy,ca]);stack.Placement=A.Placement(A.Vector(-63,-40,z),A.Rotation()).multiply(stack.Placement)
    hits=[];tested=0
    for o in chassis.Document.Objects:
        if o.TypeId!='App::Link' or not hasattr(o,'Shape') or o.Shape.isNull():continue
        if not stack.BoundBox.intersect(o.Shape.BoundBox):continue
        vol=common_filtered(stack,o.Shape);tested+=1
        if vol>1e-6:hits.append({'obstacle':o.Name,'volume_mm3':vol})
    others=[]
    for name in ['SA02A_Dock20Ah','SA05_Capteurs_Isoles','SA07_Distribution_Systeme_Candidat']:
        vol=common_filtered(stack,t.getObject(name).Shape)
        others.append({'obstacle':name,'volume_mm3':vol})
    global_ca=ca.copy();global_ca.Placement=A.Placement(A.Vector(-63,-40,z),A.Rotation()).multiply(global_ca.Placement)
    row={'pose_Holybro_Z_mm':z,'bbox_CA01_mm':box(global_ca),
         'ecart_Z_enveloppe_CA01_plaque_mm':global_ca.BoundBox.ZMin-plate.BoundBox.ZMax,
         'ecart_Z_face_PCB_plaque_mm':z-11.6254-plate.BoundBox.ZMax,
         'obstacles_chassis_boolean_testes':tested,'interferences_chassis':hits,
         'autres_sous_assemblages':others}
    poses.append(row);print(json.dumps(row),flush=True)
# Contrôle séparé des fixations et des appuis, hors recouvrement des filetages.
hardware=[];mount_z=build['montage']['pose_Holybro_Z_mm']
t.getObject('ParametresIntegration').PoseHolybroZ=mount_z;t.recompute()
obstacles=[(o.Name,o.Shape) for o in chassis.Document.Objects if o.TypeId=='App::Link' and not o.Shape.isNull()]
obstacles += [(name,t.getObject(name).Shape) for name in ['SA02A_Dock20Ah','SA05_Capteurs_Isoles','SA07_Distribution_Systeme_Candidat']]
for o in s.getObject('StackRevue').Group:
    if o.TypeId!='App::Link' or o.Name in ['Holybro','CA01']:continue
    q=o.Shape.copy();q.Placement=A.Placement(A.Vector(-63,-40,mount_z),A.Rotation()).multiply(q.Placement)
    hits=[]
    for name,obstacle in obstacles:
        v=common_filtered(q,obstacle)
        if v>1e-6:hits.append({'obstacle':name,'volume_mm3':v})
    cardhit=common_filtered(o.Shape,ca)
    assert cardhit<1e-6,(o.Name,cardhit)
    assert not hits,(o.Name,hits)
    hardware.append({'occurrence':o.Name,'interferences_obstacles':hits,'interference_CA01_mm3':cardhit,
        'interface_OEM':'Filetage en recouvrement intentionnel, non testé en booléen comme collision' if o.Name.startswith('Vis') else 'Appui de face'})
print('fixations terminé',flush=True)
for f,h in build['sources_preservees_sha256'].items():assert sha(ROOT/f)==h
for row in build['nouveaux_fichiers']:assert sha(ROOT/row['fichier'])==row['sha256']
proof={'date':'2026-10-03','environnement':'Windows amd64, Python FreeCAD1.1.3, processus neuf',
    'version_FreeCAD':A.Version(),'script_sha256':sha(__file__),
    'construction_sha256':sha(VER/'construction_stack_revue_20261003.json'),
    'exigences':['MEC-AVI-001','MEC-INT-001','CARTE-010'],
    'tests':['T-STACK-REVUE-NATIF','T-STACK-REVUE-GEOM'],
    'finalisation_correcte':True,'conclusion':'préliminaire','statut':'À valider',
    'reouverture_recalcul_sans_erreur':True,'erreurs':errors,'liens_externes_resolus':True,
    'substrat_perçages_pads_natifs':50,'arbre_PCB_parametrique':True,
    'interference_Holybro_CA01_mm3':internal,'poses':poses,'sources_natifs_preserves':True,
    'fixations_controlees':hardware,'montage':build['montage'],
    'montage_conforme':False,'chaine_appuis_CAO_implantee':True,'fixations_qualifiees':False,'passages_cables_valides':False,
    'conversion_STEP':build['conversion_STEP'],'elapsed_s':time.time()-start,
    'limites':['Seuls solides représentés, sans tolérances ni fiches accouplées/câbles.',
        'Écart Z de boîtes, pas mesure de passage fournisseur ni accès outil.',
        'Chaîne d’appui native candidate ; compression, fluage, préchargePCB et serrage non qualifiés.',
        'RP4TD : sous-face, broches et hauteur réelle inconnues.',
        'Cuivre et vias non détaillés ; M3 côté plan confirmé, profondeur filetée utile et révision réelle à confirmer.',
        'P16 bloque l’accès outil : déposer bloccapteurs SA05A avant montage/maintenance.',
        'Les appuis G10 ne démontrent pas l’isolement électrique des tiges dans le carbone/PCB.'],
    'essais_non_executes':['Montage et serrage','Accouplement et traction câbles','Thermique','Vibrations','Pesée','Vol']}
(VER/'controle_stack_revue_20261003.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'finalisation_correcte':True,'sources_preservees':True,'poses':len(poses)}),flush=True)
