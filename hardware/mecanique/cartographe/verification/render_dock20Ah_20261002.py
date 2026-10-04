"""Aperçus dérivés des natifs ; aucun document CAO sauvegardé par cette recette."""
from pathlib import Path
import json, hashlib
import FreeCAD as A
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from matplotlib.patches import Patch
import numpy as np

ROOT=Path(__file__).resolve().parents[4]
MEC=ROOT/'hardware/mecanique/cartographe'
OUT=MEC/'verification'
drone=A.openDocument(str(MEC/'assemblages/Drone_Cartographe_20Ah.FCStd'))
dock=next(d for d in A.listDocuments().values() if d.Name=='SA02A_Dock20Ah')

def color(name):
    name=name.lower()
    if 'batterie' in name or 'pack' in name: return '#3c76c5'
    if 'rail' in name: return '#315b65'
    if 'g10' in name or 'fond' in name or 'cap' in name: return '#d5ae66'
    if 'gache' in name or 'loquet' in name or 'southco' in name: return '#da7b30'
    if 'contact' in name or 'broche' in name: return '#b29b6b'
    if 'te_' in name or 'housing' in name: return '#353a44'
    if 'jeti' in name: return '#b34844'
    if 'mousse' in name: return '#53775e'
    return '#8a929e'

def draw(ax,rows,bounds,elev=23,azim=-57):
    triangles=[]; colors=[]
    for name,shape,col in rows:
        if shape.isNull(): continue
        vs,fs=shape.tessellate(1.0)
        vertices=np.array([[v.x,v.y,v.z] for v in vs])
        if len(fs):
            triangles.extend(vertices[np.array(fs)])
            colors.extend([col]*len(fs))
    if triangles:
        ax.add_collection3d(Poly3DCollection(triangles,facecolors=colors,
            edgecolors=colors,linewidths=0,shade=True,zsort='average'))
    ax.set_xlim(*bounds[0]);ax.set_ylim(*bounds[1]);ax.set_zlim(*bounds[2])
    ax.set_box_aspect([b-a for a,b in bounds]);ax.view_init(elev=elev,azim=azim)
    ax.set_axis_off();ax.set_facecolor('#f6f7f9')

proof=[]
fig=plt.figure(figsize=(15,7),facecolor='#f6f7f9')
for i,dx in enumerate((0,260),1):
    dock.Parametres.set('B60',f'{dx} mm');dock.recompute();drone.recompute()
    root=dock.getObject('Reference') or dock.getObject('Ensemble')
    rows=[(o.Name,o.Shape,color(o.Name)) for o in root.Group if o.TypeId=='App::Link' and hasattr(o,'Shape')]
    ax=fig.add_subplot(1,2,i,projection='3d')
    draw(ax,rows,((-340,215) if dx==0 else (-340,475),(-72,72),(27,240)))
    ax.set_title('Cassette à la butée' if dx==0 else 'Cassette extraite de 260 mm',fontsize=14)
fig.suptitle('Dock 6S 20 Ah — géométrie native du mécanisme',fontsize=18)
fig.text(.5,.055,'Rails captifs · retenue Southco · contacts guidés\n'
    'CAO implémentée ; verrouillage, faisceaux et fonctionnement physique à valider.',ha='center',fontsize=11)
fig.subplots_adjust(left=0,right=1,bottom=.14,top=.89,wspace=.02)
p=OUT/'dock20Ah_20261002.png';fig.savefig(p,dpi=150);plt.close(fig)
proof.append({'fichier':str(p.relative_to(MEC)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})

dock.Parametres.set('B60','0 mm');dock.recompute();drone.recompute()
root=drone.getObject('Ensemble') or drone.getObject('Reference')
rows=[(o.Name,o.Shape,'#3c76c5' if 'Dock' in o.Name or 'Cassette' in o.Name else '#828b98')
      for o in root.Group if o.TypeId=='App::Link' and hasattr(o,'Shape')]
fig=plt.figure(figsize=(10,8),facecolor='#f6f7f9');ax=fig.add_subplot(111,projection='3d')
draw(ax,rows,((-340,340),(-340,340),(-205,240)),25,-49)
ax.set_title('Intégration 20 Ah — dernier plateau rehaussé de 20 mm',fontsize=15)
fig.text(.5,.035,'Hélices absentes du modèle fabricant ; échange au sol, pales dégagées.\n'
    'La représentation ne qualifie ni la tenue mécanique, ni le vol.',ha='center',fontsize=10)
fig.subplots_adjust(left=0,right=1,bottom=.10,top=.92)
p=OUT/'drone20Ah_20261002.png';fig.savefig(p,dpi=150);plt.close(fig)
proof.append({'fichier':str(p.relative_to(MEC)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
(OUT/'rendu_dock20Ah_20261002.json').write_text(json.dumps({'date':'2026-10-02',
    'nature':'Aperçus dérivés des natifs, aucune modification sauvegardée',
    'artefacts':proof},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(proof,ensure_ascii=False))
