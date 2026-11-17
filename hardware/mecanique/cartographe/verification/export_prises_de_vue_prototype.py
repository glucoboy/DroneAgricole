"""Exporter des prises de vue du prototype final, sans écriture des natifs.

Les vues d'ensemble sont complètes. Les détails existants sont repris par
identité d'empreinte avec leurs indications de transparence ou de masquage.
"""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import html
import json
import shutil
import FreeCAD as App
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection
from read_brep_prototype import Reader

MEC=Path(__file__).resolve().parents[1]
ROOT=MEC.parents[2]
VER=MEC/'verification'
OUT=MEC/'exports/prototype/prises_de_vue'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text('utf-8'))


def run():
    build=read(VER/'construction_prototype.json')
    assert build['finalisation_correcte']
    native={r['fichier']:r['sha256'] for r in build['references']}
    native.update(build['sources_preservees'])
    assert all(sha(MEC/p)==h for p,h in native.items()),'Natifs différents des fichiers vérifiés'
    OUT.mkdir(parents=True,exist_ok=True)
    reader=Reader(MEC)
    cable_ids={r['id'] for r in read(VER/'routes_prototype.json')['routes']}
    scene=[]
    bounds=App.BoundBox()
    rows=[r for r in build['occurrences'] if r['parent'].startswith('sous_assemblages/')]
    light=np.array([-.4,-.5,.76]);light/=np.linalg.norm(light)
    for index,row in enumerate(rows,1):
        shape=reader.occurrence(row)
        if shape.isNull():continue
        bounds.add(shape.BoundBox)
        vertices,triangles=shape.tessellate(.8)
        if not triangles:continue
        points=np.array([[p.x,p.y,p.z] for p in vertices])
        faces=points[np.array(triangles)]
        normals=np.cross(faces[:,1]-faces[:,0],faces[:,2]-faces[:,0])
        norms=np.linalg.norm(normals,axis=1);norms[norms==0]=1
        normals/=norms[:,None]
        tint=((.88,.26,.08) if row['occurrence'] in cable_ids or row['occurrence'].startswith('Collier')
              else (.20,.40,.70) if '/fabriquees/' in row['source'] else (.53,.56,.60))
        colors=np.array(tint)[None,:]*(.52+.48*np.abs(normals@light))[:,None]
        scene.append((faces,colors))
        if index%50==0:print(json.dumps(dict(geometries_lues=index,total=len(rows))),flush=True)
    definitions=[('ensemble_1','Vue d’ensemble — trois quarts',26,-58),
        ('ensemble_2','Vue d’ensemble — côté opposé',24,122),
        ('cote_x','Vue suivant X',0,0),('cote_y','Vue suivant Y',0,90),
        ('dessus','Vue de dessus',90,-90),('dessous','Vue de dessous',-90,-90)]
    images=[]
    faces=np.concatenate([mesh for mesh,colors in scene])
    colors=np.concatenate([colors for mesh,colors in scene])
    centre=np.array([(bounds.XMin+bounds.XMax)/2,(bounds.YMin+bounds.YMax)/2,
        (bounds.ZMin+bounds.ZMax)/2])
    faces-=centre
    del scene
    print(json.dumps(dict(triangles=len(faces),projections=6)),flush=True)
    for stem,title,elev,azim in definitions:
        elevation,azimut=np.radians([elev,azim])
        regard=np.array([np.cos(elevation)*np.cos(azimut),np.cos(elevation)*np.sin(azimut),np.sin(elevation)])
        droite=np.array([-np.sin(azimut),np.cos(azimut),0])
        haut=np.cross(regard,droite)
        projected=np.stack([faces@droite,faces@haut],axis=-1)
        order=np.argsort(np.mean(faces@regard,axis=1),kind='stable')
        figure=plt.figure(figsize=(24,17),dpi=100)
        axes=figure.add_subplot();axes.set_aspect('equal')
        axes.add_collection(PolyCollection(projected[order],facecolors=colors[order],
            edgecolors='none',antialiaseds=False))
        low=projected.min(axis=(0,1));high=projected.max(axis=(0,1))
        margin=(high-low)*.045
        axes.set_xlim(low[0]-margin[0],high[0]+margin[0])
        axes.set_ylim(low[1]-margin[1],high[1]+margin[1]);axes.set_axis_off()
        figure.subplots_adjust(left=.035,right=.965,bottom=.07,top=.92)
        figure.text(.035,.957,title,fontsize=22,color='#24364b')
        figure.text(.035,.025,'Prototype final · Projection orthographique · Bleu : pièces projet · Orange : faisceaux / colliers',fontsize=14,color='#42556a')
        path=OUT/(stem+'.png')
        figure.savefig(path,dpi=100,facecolor='white');plt.close(figure)
        images.append(dict(fichier=path.name,titre=title,sha256=sha(path),type='ensemble',
            elevation_deg=elev,azimut_deg=azim))
        print(json.dumps(dict(image=stem)),flush=True)
    verified=read(VER/'rendu_prototype.json')
    assert verified['construction_sha256']==sha(VER/'construction_prototype.json')
    proof_images={Path(r['fichier']).name:r for r in verified['vues']}
    selected=[('connexions_camera.png','Caméra et prises coudées'),
        ('departs_bras.png','Départs des bras'),('bras_selles.png','Cheminement sur un bras'),
        ('connexions_avionique.png','Connexions avioniques')]
    for filename,title in selected:
        record=proof_images[filename];source=MEC/record['fichier']
        assert sha(source)==record['sha256']
        target=OUT/('detail_'+filename);shutil.copyfile(source,target)
        images.append(dict(fichier=target.name,titre=title,sha256=sha(target),type='detail',
            source=source.relative_to(ROOT).as_posix(),note='Vue de détail ; éléments masqués ou transparents pour exposer les interfaces.'))
    collar_views=read(ROOT/'.runtime/colliers_usb/rendus_colliers.json')
    assert collar_views['finalisation_correcte']
    assert collar_views['preuve_sha256']==sha(VER/'controle_colliers_prototype.json')
    collar_sources={Path(r['fichier'].replace('\\','/')).name:r for r in collar_views['images']}
    for filename,title in [('usb_oblique.png','Réserve USB et ses colliers'),
            ('liaisons_p75.png','Liaisons entre supports'),('qs8_commun.png','Retenue commune du QS8'),
            ('antenne_rf0.png','Retenue de l’antenne RF0'),('antenne_rf1.png','Retenue de l’antenne RF1')]:
        record=collar_sources[filename];source=ROOT/record['fichier'].replace('\\','/')
        assert sha(source)==record['sha256']
        target=OUT/('detail_'+filename);shutil.copyfile(source,target)
        images.append(dict(fichier=target.name,titre=title,sha256=sha(target),type='detail',
            source=source.relative_to(ROOT).as_posix(),note='Vue de contrôle avec pièces masquées ou transparentes.'))
    cards=[]
    for item in images:
        cards.append('<figure><a href="'+html.escape(item['fichier'])+'"><img loading="lazy" src="'+
            html.escape(item['fichier'])+'" alt="'+html.escape(item['titre'])+'"></a><figcaption><strong>'+
            html.escape(item['titre'])+'</strong><p>'+html.escape(item.get('note','Assemblage complet, sans masquage.'))+
            '</p><a href="'+html.escape(item['fichier'])+'" download>Télécharger le PNG</a></figcaption></figure>')
    page='''<!doctype html><html lang="fr"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Prototype cartographe — prises de vue</title><style>
body{font:16px/1.5 system-ui,sans-serif;background:#eef2f6;color:#213248;margin:0}main{max-width:1500px;margin:auto;padding:32px}
h1{margin-bottom:8px}header{margin-bottom:30px}a{color:#245c9b}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(350px,1fr));gap:24px}
figure{margin:0;background:white;border-radius:12px;overflow:hidden;box-shadow:0 2px 12px #22334412}img{display:block;width:100%;aspect-ratio:24/17;object-fit:contain}figcaption{padding:18px}p{margin:8px 0;color:#526478}
@media(max-width:500px){main{padding:16px}.grid{grid-template-columns:1fr}}
</style><main><header><h1>Prototype cartographe</h1><p>Six angles d’ensemble et neuf gros plans du modèle final vérifié.</p>
<p>Les vues d’ensemble montrent la géométrie complète. Les détails utilisent des masquages ou transparences pour rendre les retenues et connexions visibles. Cliquer sur une image pour l’ouvrir en grand.</p></header><div class="grid">'''+''.join(cards)+'</div></main></html>'
    (OUT/'galerie.html').write_text(page,'utf-8')
    unchanged=all(sha(MEC/p)==h for p,h in native.items())
    assert unchanged,'Un natif a changé pendant l’export'
    report=dict(date_utc=datetime.now(timezone.utc).isoformat(),script_sha256=sha(__file__),
        construction_sha256=sha(VER/'construction_prototype.json'),
        natifs_sha256=native,natifs_non_modifies=unchanged,images=images,
        galerie_sha256=sha(OUT/'galerie.html'),finalisation_correcte=True)
    (OUT/'index.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n','utf-8')
    print(json.dumps(dict(images=len(images),natifs_non_modifies=unchanged,galerie=str(OUT/'galerie.html'))),flush=True)


if __name__=='__main__':
    run()
