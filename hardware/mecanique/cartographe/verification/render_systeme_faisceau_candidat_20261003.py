"""Aperçu dérivé de la CAO candidate ; aucun natif sauvegardé."""
from pathlib import Path
import json,hashlib
import FreeCAD as A
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from matplotlib.patches import Patch
import numpy as np

ROOT=Path(__file__).resolve().parents[4];MEC=ROOT/'hardware/mecanique/cartographe'
top=A.openDocument(str(MEC/'assemblages/Drone_Cartographe_Systeme_Candidat.FCStd'))
root=top.getObject('Reference')
fig=plt.figure(figsize=(16,9),facecolor='#f6f7f9')
colors={'SA01_Chassis_Rehausse20':'#9a9fa6','SA02A_Dock20Ah':'#647ca0',
        'SA05_Capteurs_Isoles':'#70927e','Stack_Holybro_CA01':'#9570a8',
        'Distribution_PM_PDB':'#ddab59','GNSS_Helical':'#70927e'}
mesh=[]
for link in root.Group:
    if link.TypeId!='App::Link' or link.Name=='Faisceau_Systeme':continue
    vertices,faces=link.Shape.tessellate(2.5)
    if faces:
        points=np.array([[v.x,v.y,v.z] for v in vertices])
        mesh.append((points[np.array(faces)],colors[link.Name]))
hdoc=next(d for d in A.listDocuments().values() if d.Name=='SA08_Faisceau_Systeme_Candidat')
construction=json.loads((MEC/'verification/construction_systeme_faisceau_20261003.json').read_text(encoding='utf-8'))
for index,(bounds,title,elev,azim) in enumerate([
    (((-340,340),(-340,340),(-205,265)),'Ensemble : distribution, capteurs et GNSS',21,-53),
    (((-170,165),(-118,115),(-199,160)),'Détail : pile Holybro / CA01 et faisceaux',14,-58)],1):
    ax=fig.add_subplot(1,2,index,projection='3d')
    for triangles,color in mesh:
        ax.add_collection3d(Poly3DCollection(triangles,facecolors=color,edgecolors=color,linewidths=0,zsort='average'))
    for route in construction['routes']:
        ref=hdoc.getObject(route['id']).LinkedObject
        points=ref.Document.getObject('CheminArrondi').Shape.discretize(Deflection=1.0)
        xyz=np.array([[p.x,p.y,p.z] for p in points])
        power=route['groupe'] in ['F01-ENERGIE-AMONT','F02-PROPULSION-DC','F03-PHASES-MOTEURS','F05-DISTRIBUTION','F08-CA01-ENTREE','F09-JETSON-ENERGIE']
        ax.plot(xyz[:,0],xyz[:,1],xyz[:,2],color='#db6547' if power else '#267ca9',linewidth=1.5 if index==1 else 2.1)
    ax.set_xlim(*bounds[0]);ax.set_ylim(*bounds[1]);ax.set_zlim(*bounds[2])
    ax.set_box_aspect([b-a for a,b in bounds]);ax.view_init(elev=elev,azim=azim)
    ax.set_axis_off();ax.set_title(title,fontsize=14);ax.set_facecolor('#f6f7f9')
fig.suptitle('Cartographe 6S 20 Ah — implantation et faisceau candidats',fontsize=21,y=.96)
fig.legend(handles=[Patch(facecolor='#9570a8',label='Holybro / CA01'),Patch(facecolor='#ddab59',label='PM08 / PDB'),
                    Patch(facecolor='#db6547',label='Puissance'),Patch(facecolor='#267ca9',label='Données / temps / RF')],
           loc='lower center',bbox_to_anchor=(.5,.10),ncol=4,frameon=False)
fig.text(.5,.045,'35 routes natives de réservation ; supports et prises accouplées à définir.\n'
         'Interférences, rayons et mouvements ouverts — passages non validés, masse totale inconnue.',ha='center',fontsize=12,color='#6b3934')
fig.subplots_adjust(left=.01,right=.99,bottom=.15,top=.89,wspace=.02)
path=MEC/'verification/systeme_faisceau_candidat_20261003.png';fig.savefig(path,dpi=120);plt.close(fig)
proof={'date':'2026-10-03','fichier':str(path.relative_to(ROOT)).replace('\\','/'),
       'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'nature':'Aperçu dérivé, lecture seule',
       'configuration':'Drone_Cartographe_Systeme_Candidat','script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
(MEC/'verification/rendu_systeme_faisceau_20261003.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(proof,ensure_ascii=False),flush=True)
