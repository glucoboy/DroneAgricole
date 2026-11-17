"""Vues de preuve : tessellation des BRep sauvegardés, lecture seule.

Exécuter avec le Python embarqué FreeCAD, -B. Aucun document GUI ouvert.
Ces vues ne remplacent pas les contrôles exacts de volumes et de dégagements.
"""
from pathlib import Path
import sys, json, hashlib, traceback, time
ROOT = Path(__file__).resolve().parents[5]
COPY = ROOT / 'hardware/mecanique/cartographe_faisceaux'
OUT = Path(__file__).resolve().parent / 'vues'
OUT.mkdir(exist_ok=True)
sys.path.insert(0, str(COPY / 'verification'))
import FreeCAD as App
import Part
from read_brep_prototype import Reader
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection
from matplotlib.patches import Patch

def read(p): return json.loads(p.read_text('utf-8'))
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
reader = Reader(COPY)
routes = read(COPY/'verification/routes_prototype.json')['routes']
build = read(COPY/'verification/construction_prototype.json')
stations = read(OUT.parent/'analyse_mecanique_f16.json')['stations_et_audit_historique']['stations']
ids = {r['id'] for r in routes}
evidence = {'schema':'vues-brep-v1','method':'Tessellation OCC des BRep sauvegardés, projection orthographique triée en profondeur ; aucune génération CAO et aucun recalcul',
            'deflection_mm':0.7,'errors':[], 'sources':{},'objects':[], 'outputs':[],
            'limitation':'Tessellation pour illustration seulement. Les transparences rendent visibles les câbles occultés ; aucune conformité ne peut être déduite du rendu.'}
meshes=[]
started=time.monotonic()
for index,row in enumerate(build['occurrences']):
    if not row['parent'].startswith('sous_assemblages/'): continue
    if row['occurrence'] in ids and 'SA07_' in row['parent']: continue
    try:
        source_hash=sha(COPY/row['source'])
        cache=OUT/('mesh_'+str(index)+'.npz')
        cache_key=hashlib.sha256((source_hash+json.dumps(row,sort_keys=True)).encode()).hexdigest()
        cached=np.load(cache) if cache.exists() else None
        if cached is not None and str(cached['key'])==cache_key:
            tri=cached['tri']
        else:
            print('tessellate',index,row['occurrence'],flush=True)
            shape=reader.occurrence(row)
            v,t=shape.tessellate(0.7)
            pts=np.array([[p.x,p.y,p.z] for p in v]); tri=pts[np.array(t)]
            np.savez_compressed(cache,tri=tri,key=cache_key)
        name=row['occurrence']; fixture='SA07_' in row['parent'] and not name.startswith('Connecteur')
        meshes.append((name,tri,'fixture' if fixture else 'body'))
        evidence['objects'].append({'occurrence':row['parent']+'#'+name,'triangles':len(tri),'role':meshes[-1][2]})
        evidence['sources'][row['source']]=source_hash
        if time.monotonic()-started>40:
            print('CACHE_PARTIEL_REPRENDRE',flush=True)
            sys.exit(75)
    except Exception as exc:
        evidence['errors'].append({'occurrence':row['parent']+'#'+row['occurrence'],'error':str(exc)})
for row in routes:
    shape=reader.shape(row['fichier'],row['objet_cable'])
    v,t=shape.tessellate(0.35)
    tri=np.array([[p.x,p.y,p.z] for p in v])[np.array(t)]
    meshes.append((row['id'],tri,'f16' if row['id']=='F16' else 'cable'))
    evidence['sources'][row['fichier']]=sha(COPY/row['fichier'])

colors={'body':'#91a0aa','fixture':'#d79531','cable':'#157c87','f16':'#cf423d','candidate':'#724ac6'}
def basis(az=-48,el=24):
    az,el=np.deg2rad([az,el]); d=np.array([np.cos(el)*np.cos(az),np.cos(el)*np.sin(az),np.sin(el)])
    u=np.cross([0,0,1],d);u/=np.linalg.norm(u);w=np.cross(d,u)
    return np.array([u,w,d]).T
def render(ax,items,projection,center=(0,0,0),clip=None,alpha=.34):
    R=projection
    triangles=[];facecolors=[]
    for name,tri,role in items:
        if clip:
            lo,hi=np.array(clip[0]),np.array(clip[1]);keep=np.all(tri.max(axis=1)>=lo,axis=1)&np.all(tri.min(axis=1)<=hi,axis=1);tri=tri[keep]
        if not len(tri):continue
        p=(tri-np.array(center))@R
        triangles.append(p)
        rgba=matplotlib.colors.to_rgba(colors[role],alpha if role=='body' else .85)
        # Face-dependent shading uses the actual tessellated surface normals.
        n=np.cross(p[:,1]-p[:,0],p[:,2]-p[:,0]);norm=np.linalg.norm(n,axis=1)
        shade=.65+.35*np.abs(n[:,2])/np.maximum(norm,1e-12)
        facecolors.append(np.c_[np.array(rgba[:3])[None,:]*shade[:,None],np.full(len(p),rgba[3])])
    tri=np.concatenate(triangles);order=np.argsort(tri[:,:,2].mean(axis=1))
    ax.add_collection(PolyCollection(tri[order,:,:2],facecolors=np.concatenate(facecolors)[order],edgecolors='none',rasterized=True))
    ax.autoscale_view();ax.set_aspect('equal');ax.set_axis_off()
    if clip:
        corners=np.array([[x,y,z] for x in [clip[0][0],clip[1][0]] for y in [clip[0][1],clip[1][1]] for z in [clip[0][2],clip[1][2]]])
        projected=(corners-np.array(center))@R
        lo,hi=projected[:,:2].min(axis=0),projected[:,:2].max(axis=0)
        ax.set_xlim(lo[0],hi[0]);ax.set_ylim(lo[1],hi[1])
    return R
def finish(fig,name,subtitle):
    fig.text(.025,.025,subtitle,fontsize=9,color='#465565')
    path=OUT/name;fig.savefig(path,dpi=175,facecolor='white');plt.close(fig)
    evidence['outputs'].append({'file':name,'sha256':sha(path)})
    print(name,flush=True)

plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10})
if '--details-only' not in sys.argv:
    fig,axes=plt.subplots(1,2,figsize=(15,8))
    for ax,title in zip(axes,['ÉTAT INITIAL — géométrie sauvegardée','COPIE CONSERVÉE — aucun remplacement retenu']):
        render(ax,meshes,basis());ax.set_title(title,fontsize=12,pad=14)
    fig.suptitle('Drone cartographe | comparaison à cadrage identique',x=.025,ha='left',fontsize=18,fontweight='bold')
    fig.legend(handles=[Patch(color=colors[k],label=s) for k,s in [('body','Équipements et structure'),('cable','Câblage existant'),('fixture','Retenues / fixations SA07'),('f16','F16')]],loc='lower center',bbox_to_anchor=(.5,.065),ncol=4,frameon=False)
    finish(fig,'01_global_initial_copie_conservee.png','Assemblage lu uniquement dans la copie isolée. Transparence de la structure pour lecture interne. Géométrie de la copie identique à la baseline ; reconstruction globale non effectuée.')
else:
    path=OUT/'01_global_initial_copie_conservee.png'
    evidence['outputs'].append({'file':path.name,'sha256':sha(path),'preserved_from_previous_render':True})

clip=([-20,-135,-115],[155,35,165]);center=(65,-50,25)
focus=[m for m in meshes if m[2]=='body' or m[0] in ('P73_Guide','P75_Cadre','ConnecteurF16Camera','ConnecteurF16TypeA','F16')]
fig,axes=plt.subplots(1,2,figsize=(15,9))
for ax,R,title in [(axes[0],basis(-62,17),'Détail oblique | obstacles et supports'),(axes[1],np.array([[0,0,1],[-1,0,0],[0,1,0]]),'Projection Y–Z | huit stations historiques')]:
    render(ax,focus,R,center,clip,.15)
    for n,station in enumerate(stations,1):
        p=(np.array(station['point_nominal_mm'])-np.array(center))@R
        ax.scatter(*p[:2],s=26,c='#101e2b',zorder=5)
        offset=(7,5) if ax==axes[0] or n<7 else ((12,-10) if n==7 else (27,10))
        ax.annotate(str(n),p[:2],xytext=offset,textcoords='offset points',fontsize=10,fontweight='bold',zorder=6,color='#101e2b',arrowprops={'arrowstyle':'-','lw':.6} if n>=7 and ax==axes[1] else None)
    ax.set_title(title,fontsize=12)
fig.suptitle('F16 conservé | stations, supports et contexte mécanique',x=.025,ha='left',fontsize=18,fontweight='bold')
station_labels=[str(i+1)+' '+s['station_id'] for i,s in enumerate(stations)]
fig.text(.025,.11,'   '.join(station_labels[:4]),fontsize=10)
fig.text(.025,.085,'   '.join(station_labels[4:]),fontsize=10)
finish(fig,'02_f16_stations_obstacles.png','F16 rouge ; guides P73/P75 orange ; obstacles gris translucides. Stations nominales : tolérance historique de projection 0,6 mm. Vue illustrative, aucune nouvelle conformité physique établie.')

candidate=COPY/'verification/candidats/F16_ARCS_R23_5.FCStd'
if candidate.exists():
    types,objs=reader.xml(candidate)
    cname=next((n for n in objs if n=='Cable'),None)
    if cname:
        shape=reader.shape(candidate,cname);v,t=shape.tessellate(.2)
        candidate_mesh=('F16_ARCS_R23_5',np.array([[p.x,p.y,p.z] for p in v])[np.array(t)],'candidate')
        evidence['sources'][str(candidate.relative_to(COPY))]=sha(candidate)
        fig,axes=plt.subplots(1,2,figsize=(15,9))
        for ax,items,title in [(axes[0],focus,'Initial conservé — F16'),(axes[1],[m for m in focus if m[0]!='F16']+[candidate_mesh],'Candidat isolé — F16_ARCS_R23_5')]:
            render(ax,items,basis(-62,17),center,clip,.15);ax.set_title(title,fontsize=13)
            for n,s in enumerate(stations,1):
                p=(np.array(s['point_nominal_mm'])-np.array(center))@basis(-62,17)
                ax.scatter(*p[:2],s=15,c='#101e2b');ax.annotate(str(n),p[:2],xytext=(7,5),textcoords='offset points',fontsize=9)
        fig.suptitle('Prototype F16 | comparaison des volumes à cadrage identique',x=.025,ha='left',fontsize=18,fontweight='bold')
        finish(fig,'03_f16_initial_candidat.png','Candidat séparé, non publié dans l’assemblage. Lire les mesures exactes de tangence, stations, rayons et collisions avant toute décision ; les vues ne prouvent pas la conformité.')
    else:evidence['errors'].append({'candidate':str(candidate),'error':'Objet Cable absent'})
else:evidence['candidate_render']='non exécuté : natif candidat absent au moment du rendu'
for path in [COPY/'verification/routes_prototype.json',COPY/'verification/construction_prototype.json',OUT.parent/'analyse_mecanique_f16.json']:
    evidence['sources'][str(path.relative_to(ROOT))]=sha(path)
receipt=read(COPY/'experiment.json')
evidence['baseline_copy_identical']=all(sha(COPY/name)==digest for name,digest in receipt['inputs_sha256'].items())
evidence['original_sources_intact']=all(sha(Path(receipt['source_root'])/name)==digest for name,digest in receipt['inputs_sha256'].items())
evidence['script_sha256']=sha(Path(__file__))
evidence['complete']=not evidence['errors'] and len(evidence['outputs'])==3
(OUT/'manifest.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')
