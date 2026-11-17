"""Vue d'ensemble et détail de la copie finale, depuis ses BRep sauvegardés."""
import hashlib
import json

import matplotlib
import numpy as np

from autonomie_cao import COPY, OUT, Reader, read, sha

matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection
from matplotlib.patches import Patch


PALETTE = {'structure':'#728596', 'câblage':'#146977', 'F16':'#7534ba', 'P73/P75':'#ca7620',
           'F38':'#128457', 'F05_NEG et F08_AVAL':'#bb374b'}


def mesh_data():
    reader = Reader(COPY)
    build = read(COPY/'verification/construction_prototype.json')['occurrences']
    routes = {r['id'] for r in read(COPY/'verification/routes_prototype.json')['routes']}
    native = read(OUT/'reouverture_faisceau_complet.json')['native_sha256']
    output = []
    hashes = {}
    for index, row in enumerate(build):
        if not row['parent'].startswith('sous_assemblages/'):
            continue
        name, source = row['occurrence'], row['source']
        if source not in hashes:
            hashes[source] = sha(COPY/source)
        if hashes[source] != native[source]:
            raise ValueError('Natif différent du modèle vérifié : '+source)
        role = 'câblage' if 'SA07_' in row['parent'] and name in routes else 'structure'
        role = {'F16':'F16','ProtectionF38':'F38','P73_Guide':'P73/P75','P75_Cadre':'P73/P75',
                'F05_NEG':'F05_NEG et F08_AVAL','F08_AVAL':'F05_NEG et F08_AVAL'}.get(name,role)
        previous = OUT/'vues'/f'mesh_{index}.npz'
        key = hashlib.sha256((hashes[source]+json.dumps(row,sort_keys=True)).encode()).hexdigest()
        triangles = None
        if role == 'structure' and previous.is_file():
            with np.load(previous) as cached:
                if str(cached['key']) == key:
                    triangles = cached['tri']
        if triangles is None:
            vertices, faces = reader.occurrence(row).tessellate(.7 if role == 'structure' else .25)
            if not faces:
                raise ValueError('Tessellation vide : '+name)
            triangles = np.array([[v.x,v.y,v.z] for v in vertices])[np.array(faces)]
        output.append((role,triangles))
    return output


def projection(azimuth, elevation):
    a,e = np.deg2rad([azimuth,elevation])
    depth = np.array([np.cos(e)*np.cos(a), np.cos(e)*np.sin(a), np.sin(e)])
    horizontal = np.cross([0,0,1],depth)
    horizontal /= np.linalg.norm(horizontal)
    return np.array([horizontal,np.cross(depth,horizontal),depth]).T


def draw(ax, meshes, view, limits=None):
    colors, all_triangles = [], []
    for role, triangles in meshes:
        flat = triangles @ view
        if limits is not None:
            (x0,x1),(y0,y1) = limits
            keep = ((flat[:,:,0].max(axis=1)>=x0)&(flat[:,:,0].min(axis=1)<=x1)&
                    (flat[:,:,1].max(axis=1)>=y0)&(flat[:,:,1].min(axis=1)<=y1))
            flat = flat[keep]
        if not len(flat):
            continue
        normal = np.cross(flat[:,1]-flat[:,0], flat[:,2]-flat[:,0])
        shade = .68 + .32*np.abs(normal[:,2])/np.maximum(np.linalg.norm(normal,axis=1),1e-12)
        color = np.array(matplotlib.colors.to_rgb(PALETTE[role]))
        alpha = .13 if role == 'structure' else .94
        colors.append(np.c_[shade[:,None]*color, np.full(len(flat),alpha)])
        all_triangles.append(flat)
    triangles = np.concatenate(all_triangles)
    order = np.argsort(triangles[:,:,2].mean(axis=1))
    ax.add_collection(PolyCollection(triangles[order,:,:2],facecolors=np.concatenate(colors)[order],edgecolors='none'))
    ax.autoscale_view()
    if limits is not None:
        ax.set_xlim(limits[0]); ax.set_ylim(limits[1])
    ax.set_aspect('equal')
    ax.set_axis_off()


def main():
    meshes = mesh_data()
    fig, (left,right) = plt.subplots(1,2,figsize=(15.6,8.1),gridspec_kw={'width_ratios':[1.06,1]},facecolor='#fafbfc')
    fig.subplots_adjust(left=.028,right=.98,top=.84,bottom=.13,wspace=.06)
    draw(left,meshes,projection(-48,26))
    view = projection(-50,12)
    draw(right,meshes,view,((-157,198),(-145,175)))
    left.set_title('Vue d’ensemble',loc='left',fontsize=13,color='#294258',fontweight='semibold')
    right.set_title('Détail du châssis central',loc='left',fontsize=13,color='#294258',fontweight='semibold')
    for name, point, offset, color in [('Boucle F16',[199,-38,-55],(-6,-24),'F16'),
                                       ('Protection F38',[23,-99,52],(-62,-25),'F38')]:
        xy = (np.array(point)@view)[:2]
        right.annotate(name,xy,xytext=offset,textcoords='offset points',ha='center',fontsize=10,
                       color=PALETTE[color],fontweight='semibold',bbox={'fc':'#fafbfc','ec':'none','pad':2},
                       arrowprops={'arrowstyle':'-','color':PALETTE[color],'lw':1.1})
    fig.text(.032,.943,'Drone cartographe · Faisceau candidat',fontsize=23,fontweight='bold',color='#142c42')
    fig.text(.033,.898,'53 parcours dans la copie FreeCAD  •  Boucle caméra, protection F38 et retenues réalignées',fontsize=11,color='#465b6e')
    fig.legend(handles=[Patch(color=c,label=k.capitalize() if k in ('structure','câblage') else k) for k,c in PALETTE.items()],
               loc='lower center',bbox_to_anchor=(.5,.07),ncol=6,frameon=False,fontsize=10)
    fig.text(.032,.035,'Structure en transparence pour rendre le câblage visible · Vue des solides sauvegardés · Candidat à valider',fontsize=9,color='#465b6e')
    dest = OUT/'vues/05_faisceau_final.png'
    fig.savefig(dest,dpi=170,facecolor=fig.get_facecolor())
    print(dest,flush=True)


if __name__ == '__main__':
    main()
