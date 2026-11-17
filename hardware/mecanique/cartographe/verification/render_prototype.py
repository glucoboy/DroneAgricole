"""Vues de contrôle des natifs finaux, sans sauvegarde ou modification CAO.

Les vues locales exposent les pièces habituellement masquées. Les formes sont
lues dans les FCStd empreintés et leurs matrices d'occurrence sont appliquées.
Les couleurs de contrôle ne modifient ni la géométrie ni les fichiers sources.
"""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import FreeCAD as A
import Part
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from read_brep_prototype import Reader

MEC = Path(__file__).resolve().parents[1]
VER = MEC/'verification'
OUT = MEC/'exports/prototype'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run():
    build = json.loads((VER/'construction_prototype.json').read_text('utf-8'))
    routes = json.loads((VER/'routes_prototype.json').read_text('utf-8'))['routes']
    if not build.get('finalisation_correcte'):
        raise ValueError('Construction non finalisée')
    files = {r['fichier']:r['sha256'] for r in build['references']}
    files.update(build['sources_preservees'])
    if any(sha(MEC/p) != h for p,h in files.items()):
        raise ValueError('Natifs différents de la construction')
    reader = Reader(MEC)
    cable_ids = {r['id'] for r in routes}
    occurrences = [r for r in build['occurrences'] if r['parent'].startswith('sous_assemblages/')]
    OUT.mkdir(exist_ok=True, parents=True)
    report = dict(date_utc=datetime.now(timezone.utc).isoformat(),
        script_sha256=sha(__file__), lecteur_sha256=sha(VER/'read_brep_prototype.py'),
        construction_sha256=sha(VER/'construction_prototype.json'),
        routes_sha256=sha(VER/'routes_prototype.json'), natifs_sha256=files,
        methode='Formes BRep sauvegardées, matrices natives, tessellation OCCT et projection orthographique Matplotlib ; masquage et sections locales pour exposer les interfaces ; aucun natif écrit.',
        vues=[], finalisation_correcte=False,
        limites=['Les vues locales sont des vues démontées de contrôle, pas une autre configuration.',
                 'Inspection visuelle et contrôle nominal ; accès des doigts/outils, tolérances et montage physique À valider.'])
    definitions = [
        ('ensemble_brep', 'viewAxonometric', lambda r: True),
        ('reserve_usb', 'viewAxonometric', lambda r: r['occurrence'] in
            {'F41','P77_BerceauReserveUSB','OEM__07190001_ASM'}),
        ('departs_bras', 'viewTop', lambda r:
            r['occurrence'] in {'Isolation','P72_Guide','P73_Guide'} or
            r['occurrence'].startswith(('F02_','F04_','LED_','SelleBras'))),
        ('bras_selles', 'viewAxonometric', lambda r:
            r['occurrence'] in {'OEM_X650_ZHEDIE_JIBI_2024_ASM001','ESC_2',
                'F02_2','F03_2','F04_2','LED_2','SelleBras2_1','SelleBras2_2','SelleBras2_3'}),
        ('connexions_camera', 'viewAxonometric', lambda r:
            r['occurrence'] in {'EQ_Basler_Occurrence','Semelle','Pad1',
                'ConnecteurF16Camera','ConnecteurM8Camera','F16','F_M8'}),
        ('guides_distribution', 'viewAxonometric', lambda r:
            r['occurrence'] in {'P72_Guide','P73_Guide','P75_Cadre','P78_RetenueCameraM8','Isolation'}),
        ('connexions_avionique', 'viewAxonometric', lambda r:
            r['occurrence'] in {'Holybro6XOrin','CA01','P75_Cadre','ConnecteurF16TypeA'} or
            (r['occurrence'] in cable_ids and not r['occurrence'].startswith(('F01','F02','F03','F37','F38','LED','BALANCE','NTC')))),
    ]
    for name, method, select in definitions:
        selected = []
        scene=[]
        section = {'reserve_usb':(-80,-35,-3,20,35,31),
                   'connexions_camera':(50,-70,-150,145,60,-70)}.get(name)
        for row in occurrences:
            if not select(row):
                continue
            shape = reader.occurrence(row)
            if name=='reserve_usb' and row['occurrence']=='OEM__07190001_ASM':
                # Le plateau supérieur est masqué dans cette vue démontée.
                shape=Part.makeCompound([s for s in shape.Solids
                    if abs(s.BoundBox.ZMin)<1e-3 and abs(s.BoundBox.ZMax-2)<1e-3])
            if section and row['occurrence'] in cable_ids:
                x,y,z,X,Y,Z = section
                shape = shape.common(Part.makeBox(X-x,Y-y,Z-z,A.Vector(x,y,z)))
            tint = ((.88,.26,.08) if row['occurrence'] in cable_ids else
                (.20,.40,.70) if '/fabriquees/' in row['source'] else (.53,.56,.60))
            alpha=.30 if name=='connexions_camera' and row['occurrence']=='Semelle' else 1
            if name=='reserve_usb' and row['occurrence']=='OEM__07190001_ASM':alpha=.20
            scene.append((shape,tint,alpha))
            selected.append(row['parent']+'#'+row['occurrence'])
        if not selected:
            raise ValueError('Vue sans objets : '+name)
        figure=plt.figure(figsize=(18,13),dpi=100)
        axes=figure.add_subplot(projection='3d');axes.set_proj_type('ortho')
        bounds=A.BoundBox()
        for shape,tint,alpha in scene:
            if shape.isNull():continue
            bounds.add(shape.BoundBox)
            vertices,triangles=shape.tessellate(1.0 if name=='ensemble_brep' else .35)
            if not triangles:continue
            points=np.array([[p.x,p.y,p.z] for p in vertices]);faces=points[np.array(triangles)]
            normals=np.cross(faces[:,1]-faces[:,0],faces[:,2]-faces[:,0])
            sizes=np.linalg.norm(normals,axis=1);sizes[sizes==0]=1
            normals/=sizes[:,None]
            light=np.array([-.4,-.5,.76]);light/=np.linalg.norm(light)
            colors=np.array(tint)[None,:]*(.52+.48*np.abs(normals@light))[:,None]
            axes.add_collection3d(Poly3DCollection(faces,facecolors=colors,edgecolors='none',alpha=alpha,zsort='average'))
        axes.set_xlim(bounds.XMin,bounds.XMax);axes.set_ylim(bounds.YMin,bounds.YMax);axes.set_zlim(bounds.ZMin,bounds.ZMax)
        axes.set_box_aspect([max(bounds.XLength,1),max(bounds.YLength,1),max(bounds.ZLength,1)])
        axes.set_axis_off()
        elev,azim={'viewTop':(90,-90),'viewRight':(0,0)}.get(method,(26,-58))
        if name=='connexions_camera':elev,azim=18,35
        axes.view_init(elev=elev,azim=azim)
        figure.subplots_adjust(left=0,right=1,bottom=.04,top=.96)
        figure.text(.04,.96,name.replace('_',' '),fontsize=16,color='#24364b')
        figure.text(.04,.025,'BRep natifs tessellés · Orange : faisceaux · Bleu : pièces projet · Vue de contrôle démontée',fontsize=11,color='#42556a')
        path = OUT/(name+'.png')
        figure.savefig(path,dpi=100,facecolor='white');plt.close(figure)
        report['vues'].append(dict(fichier=path.relative_to(MEC).as_posix(), sha256=sha(path),
            projection=method, occurrences=selected,section_cables_mm=section))
    report['fichiers_non_modifies'] = all(sha(MEC/p)==h for p,h in files.items())
    report['finalisation_correcte'] = report['fichiers_non_modifies']
    (VER/'rendu_prototype.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n','utf-8')
    print(json.dumps(dict(vues=len(report['vues']),fichiers_non_modifies=report['fichiers_non_modifies'])),flush=True)


if __name__ == '__main__':
    run()
    os._exit(0)
