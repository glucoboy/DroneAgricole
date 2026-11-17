"""Vues de contrôle des colliers ; copies géométriques en mémoire uniquement."""
from pathlib import Path
import argparse
import json
import FreeCAD as A
import Part
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from read_brep_prototype import Reader
from verify_colliers_prototype import SavedReader,ROOT,MEC,VER,overlap,sha

parser=argparse.ArgumentParser();parser.add_argument('--candidats',action='store_true')
args=parser.parse_args()
OUT=ROOT/'.runtime/colliers_usb'
proof_path=OUT/'controle_colliers_prototype.json' if args.candidats else VER/'controle_colliers_prototype.json'
proof=json.loads(proof_path.read_text('utf8'))
if not proof['conforme'] or not proof['finalisation_correcte']:
    raise ValueError('Le rendu nécessite une preuve conforme')
if proof.get('scene_sha256')!=sha(OUT/'ColliersControle.FCStd'):
    raise ValueError('Scène non empreintée ou différente de la preuve ; rejouer le contrôle avec --scene')
build=json.loads((VER/'construction_prototype.json').read_text('utf8'))
routes=json.loads((VER/'routes_prototype.json').read_text('utf8'))['routes']
substitutions={}
if args.candidats:
    backup=ROOT/'.runtime/finalisation_prototype/avant/hardware/mecanique/cartographe'
    for relative in set(proof['natifs_sha256'])|{o['parent'] for o in build['occurrences']}:
        if (backup/relative).is_file():substitutions[(MEC/relative).resolve()]=backup/relative
    for ref in build['references']:
        name=ref['reference']
        if not name.startswith(('P72_','P73_','P75_','P77_','P78_')):continue
        folder='retenues_corrections' if name.startswith(('P72_','P73_')) else 'retenues_integrees'
        if name.startswith(('P77_','P78_')):folder='colliers_usb'
        path=ROOT/'.runtime'/folder/(name+'.FCStd')
        if path.is_file():substitutions[(MEC/ref['fichier']).resolve()]=path
reader=SavedReader(substitutions)
if any(sha(reader.resolve(p))!=digest for p,digest in proof['natifs_sha256'].items()):
    raise ValueError('Les natifs ont changé depuis la preuve')
scene=Reader(OUT)
all_shapes=[]
for index,row in enumerate(proof['colliers']+proof['liaisons']+proof.get('retenues_boitiers_antennes',[])):
    all_shapes.append((row['collier_id'],scene.shape('ColliersControle.FCStd','Collier'+str(index+1)),(.95,.36,.04),0))
for index,row in enumerate(proof.get('tetes',[])):
    all_shapes.append((row['collier_id']+'/Tete',scene.shape('ColliersControle.FCStd','Tete'+str(index+1)),(.80,.24,.025),0))
for row in build['occurrences']:
    if not row['parent'].startswith('sous_assemblages/'):continue
    stem=Path(row['source']).stem
    if stem.startswith(('P70_','P72_','P73_','P75_','P76_','P77_','P78_')):
        all_shapes.append((stem,reader.occurrence(row),(.30,.42,.62),0))
    elif row['occurrence'] in ('QS8_manuel','AntenneRF0','AntenneRF1'):
        all_shapes.append((row['occurrence'],reader.occurrence(row),(.66,.69,.72),20))
    elif row['occurrence']=='CollierAncrageRF0':
        all_shapes.append((row['occurrence'],reader.occurrence(row),(.26,.28,.30),0))
    elif row['occurrence']=='Isolation':
        shape=reader.occurrence(row)
        if args.candidats:shape=shape.cut(Part.makeBox(6,4.8,5,A.Vector(81,76.2,35)))
        all_shapes.append(('P64',shape,(.60,.65,.69),65))
    elif row['occurrence']=='OEM__07190001_ASM':
        all_shapes.append(('PlateauxOEM',reader.occurrence(row),(.6,.62,.65),75))
for row in routes:
    all_shapes.append((row['id'],reader.shape(row['fichier'],row['objet_cable']),
                       (.12,.68,.66) if row['id'] in ('F41','AIRY') else (.3,.32,.34),0))
zones=[
    ('usb_dessus',(-78,-32,-2,85,64,36),'top'),
    ('usb_dessous',(-78,-32,-2,85,64,36),'bottom'),
    ('usb_oblique',(-78,-32,-2,85,64,36),'axo'),
    ('p78_gorge', (77,72,33,22,20,14),'axo'),
    ('p78_face', (77,72,33,22,20,14),'front'),
    ('liaisons_p75',(-123,32,40,45,48,56),'axo'),
    ('liaisons_p72_p73',(-114,-113,41,51,66,41),'axo'),
    ('qs8_commun',(95,-28,-70,42,20,44),'axo_bas'),
    ('antenne_rf0',(-91,12,129,28,32,28),'axo'),
    ('antenne_rf1',(-92,-26,94,28,22,27),'axo_bas')]
renders=[]
for name,box,view in zones:
    clip=Part.makeBox(box[3],box[4],box[5],A.Vector(*box[:3]))
    figure=plt.figure(figsize=(16,11),dpi=100);axes=figure.add_subplot(projection='3d')
    axes.set_proj_type('ortho')
    visible=[]
    for label,shape,color,transparency in all_shapes:
        if not overlap(shape.BoundBox,clip.BoundBox):continue
        pieces=[]
        for solid in shape.Solids:
            if not overlap(solid.BoundBox,clip.BoundBox):continue
            intersection=solid.common(clip)
            if intersection.Volume>1e-5:pieces.append(intersection)
        if not pieces:continue
        vertices,triangles=Part.makeCompound(pieces).tessellate(.12)
        points=np.array([[p.x,p.y,p.z] for p in vertices]);faces=points[np.array(triangles)]
        normals=np.cross(faces[:,1]-faces[:,0],faces[:,2]-faces[:,0])
        lengths=np.linalg.norm(normals,axis=1);lengths[lengths==0]=1
        normals/=lengths[:,None]
        light=np.array([-.4,-.5,.76]);light/=np.linalg.norm(light)
        shade=.52+.48*np.abs(normals@light)
        colors=np.clip(np.array(color)[None,:]*shade[:,None],0,1)
        axes.add_collection3d(Poly3DCollection(faces,facecolors=colors,edgecolors='none',
                              alpha=1-transparency/100,zsort='average'))
        visible.append(label)
    axes.set_xlim(box[0],box[0]+box[3]);axes.set_ylim(box[1],box[1]+box[4]);axes.set_zlim(box[2],box[2]+box[5])
    axes.set_box_aspect(box[3:]);axes.set_axis_off()
    elevations={'axo':28,'axo_bas':-24,'top':90,'bottom':-90,'front':0}
    axes.view_init(elev=elevations[view],azim=-58 if view.startswith('axo') else -90)
    figure.subplots_adjust(left=0,right=1,bottom=.05,top=.95)
    figure.text(.04,.96,name.replace('_',' '),fontsize=16,color='#24364b')
    figure.text(.04,.035,'Orange : bandes 4,6 × 1,2 mm · Bleu : supports · Turquoise : F41/AIRY',fontsize=11,color='#42556a')
    figure.text(.04,.015,'Géométrie native tessellée ; cadrage coupé en mémoire. Insertion et serrage : À valider.',fontsize=10,color='#65758a')
    image=OUT/(name+'.png');figure.savefig(image,dpi=100,facecolor='white');plt.close(figure)
    renders.append(dict(fichier=str(image.relative_to(ROOT)),sha256=sha(image),objets_visibles=visible,
                        cadrage_mm=box,geometrie_coupee_pour_inspection=True))
    print(name,len(visible),image.stat().st_size,flush=True)
report=dict(finalisation_correcte=True,preuve_sha256=sha(proof_path),images=renders,
            scene_sha256=proof['scene_sha256'],
            moteur='Tessellation OCCT et projection orthographique Matplotlib',natifs_non_modifies=all(sha(reader.resolve(p))==digest for p,digest in proof['natifs_sha256'].items()),
            note='Orange : bandes et enveloppes de têtes fabricant ; bleu : supports ; turquoise : F41/AIRY. Cadrages coupés en mémoire ; plateaux transparents pour inspecter les passages. Insertion et serrage restent à valider sur matériel.')
(OUT/'rendus_colliers.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n','utf8')
print(json.dumps(dict(images=len(renders),natifs_non_modifies=report['natifs_non_modifies'])),flush=True)
