"""Contrôle des BRep sauvegardés et vues comparatives, sans écrire les sources."""
from pathlib import Path
import hashlib, json, math, sys
import FreeCAD as A
import Part
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
HERE=Path(__file__).resolve().parent
MEC=HERE.parents[1]; VER=MEC/'verification'
sys.path.insert(0,str(VER))
from read_brep_prototype import Reader

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def gap(a,b):
    return math.sqrt(sum(max(getattr(a,k+'Min')-getattr(b,k+'Max'),getattr(b,k+'Min')-getattr(a,k+'Max'),0)**2 for k in 'XYZ'))
reader=Reader(MEC)
build=json.loads((VER/'construction_prototype.json').read_text('utf8'))
route=json.loads((VER/'routes_prototype.json').read_text('utf8'))['routes']
ids={r['id'] for r in route}
src='pieces/commerce/W_F16_Prototype.FCStd'
shapes={'initial':reader.shape(src,'Cable'), 'courbe':reader.shape(HERE/'F16_copie.FCStd','Cable')}
paths={'initial':reader.shape(src,'Wire'), 'courbe':reader.shape(HERE/'F16_copie.FCStd','Wire')}
report={'construction_sha256':sha(VER/'construction_prototype.json'),
        'routes_sha256':sha(VER/'routes_prototype.json'), 'source_sha256':sha(MEC/src),
        'copie_sha256':sha(HERE/'F16_copie.FCStd'), 'tol_volume_mm3':1e-4,
        'occurrences':0,'obstacles_examines':0,'hors_boite':0,'erreurs':[],
        'avant':[],'apres':[],'sources_sha256':{},'limites':[
            'Périmètre : occurrences du registre de construction ; les occurrences non répertoriées sont exclues.',
            'Les matrices du registre sont confrontées aux parents sauvegardés ; pas de contrôle des occurrences non liées.',
            'Volume positif uniquement ; un contact ou une distance nulle sans volume ne prouve pas un jeu suffisant.',
            'Boîte élargie de 25 mm : obstacles éloignés exclus des vues et distances, mais présélection conservatrice pour intersections.',
            'Formes nominales sauvegardées ; pas de tolérances, flexion, usure, ni montage réel.']}
scene=[]
rows=[o for o in build['occurrences'] if o['parent'].startswith('sous_assemblages/') and o['occurrence']!='F16']
for index,row in enumerate(rows):
    report['occurrences']+=1
    name=row['parent']+'#'+row['occurrence']
    try:
        parent=MEC/row['parent']; source=MEC/row['source']
        for p in (parent,source): report['sources_sha256'][str(p.relative_to(MEC))]=sha(p)
        _,objs=reader.xml(row['parent']); props=objs[row['occurrence']]
        if props['LinkTransform'].find('Bool').get('value')!='false': raise ValueError('LinkTransform non pris en charge')
        actual=reader.placement(row['parent'],row['occurrence']).toMatrix().A
        if max(abs(x-y) for x,y in zip(actual,row['matrice']))>1e-6: raise ValueError('placement divergent du registre')
        obstacle=reader.occurrence(row)
        if obstacle is None or obstacle.isNull(): raise ValueError('forme absente')
        report['obstacles_examines']+=1
        if min(gap(s.BoundBox,obstacle.BoundBox) for s in shapes.values())>25:
            report['hors_boite']+=1; continue
        scene.append((name,obstacle))
        for mode,key in [('initial','avant'),('courbe','apres')]:
            if gap(shapes[mode].BoundBox,obstacle.BoundBox)>0: continue
            common=shapes[mode].common(obstacle)
            if common.Volume>1e-4:
                report[key].append(dict(obstacle=name,volume_mm3=common.Volume))
    except Exception as exc:
        report['erreurs'].append(dict(occurrence=name,erreur=str(exc)))
    if index%40==0: print('occurrences',index,'/',len(rows),flush=True)

for n,shape in shapes.items():
    values=[]
    for name,obstacle in scene:
        try:
            if gap(shape.BoundBox,obstacle.BoundBox)<25:
                values.append((shape.distToShape(obstacle)[0],name))
        except Exception as exc: report['erreurs'].append(dict(distance=name,erreur=str(exc)))
    values.sort()
    report[n+'_distances_mm']=[dict(distance_mm=x,obstacle=y) for x,y in values[:10]]

fig=plt.figure(figsize=(16,8))
for index,(name,path) in enumerate(paths.items(),1):
    ax=fig.add_subplot(1,2,index,projection='3d'); ax.set_proj_type('ortho')
    for label,shape in scene:
        # Vue limitée aux obstacles à 8 mm d'une boîte de câble : c'est une coupe visuelle, pas le contrôle.
        if gap(shapes[name].BoundBox,shape.BoundBox)>8: continue
        verts,tris=shape.tessellate(1.5)
        if tris:
            pts=np.array([[p.x,p.y,p.z] for p in verts]); faces=pts[np.array(tris)]
            ax.add_collection3d(Poly3DCollection(faces,facecolors=(.5,.55,.6,.10),edgecolors='none'))
    for edge in path.Edges:
        pts=edge.discretize(Number=100)
        ax.plot([p.x for p in pts],[p.y for p in pts],[p.z for p in pts],color='#e75a20',linewidth=3)
    b=shapes[name].BoundBox
    for func,lo,hi in [(ax.set_xlim,b.XMin,b.XMax),(ax.set_ylim,b.YMin,b.YMax),(ax.set_zlim,b.ZMin,b.ZMax)]:
        func(lo-15,hi+15)
    ax.set_box_aspect((b.XLength+30,b.YLength+30,b.ZLength+30)); ax.view_init(23,-58)
    ax.set_xlabel('X mm');ax.set_ylabel('Y mm');ax.set_zlabel('Z mm');ax.set_title('Initial' if name=='initial' else 'Copie : BSpline_P')
fig.suptitle('F16 — axes de gaine et obstacles nominaux proches ; vue partielle')
fig.tight_layout();fig.savefig(HERE/'comparaison_3d.png',dpi=160);plt.close(fig)
report['source_inchangee']=sha(MEC/src)==report['source_sha256']
report['sources_inchangees']=all(sha(MEC/p)==v for p,v in report['sources_sha256'].items())
report['finalisation_correcte']=not report['erreurs'] and report['sources_inchangees'] and report['source_inchangee']
(HERE/'comparaison.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print(json.dumps({k:report[k] for k in ['occurrences','obstacles_examines','hors_boite','avant','apres','erreurs','finalisation_correcte']},ensure_ascii=False),flush=True)
