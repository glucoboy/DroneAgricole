"""Contrôle complémentaire des références projet Pxx contre l'assemblage final.

Les collisions internes aux ensembles fabricant sont hors de ce périmètre.
Aucune intersection d'une pièce fabriquée projet n'est exemptée. Les câbles
sont contrôlés par le protocole faisceau séparé.
"""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import FreeCAD as A
from read_brep_prototype import Reader
from verify_fixations_guides_prototype import common_volume, overlap

MEC=Path(__file__).resolve().parents[1]
VER=MEC/'verification'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run():
    build=json.loads((VER/'construction_prototype.json').read_text('utf-8'))
    routes=json.loads((VER/'routes_prototype.json').read_text('utf-8'))['routes']
    files={r['fichier']:r['sha256'] for r in build['references']}
    files.update(build['sources_preservees'])
    if not build.get('finalisation_correcte') or any(sha(MEC/p)!=h for p,h in files.items()):
        raise ValueError('Construction non finalisée ou fichiers périmés')
    ids={r['id'] for r in routes}
    physical=[o for o in build['occurrences'] if o['parent'].startswith('sous_assemblages/')
        and not ('SA07_' in o['parent'] and o['occurrence'] in ids)]
    reference_files={r['fichier'] for r in build['references']
        if Path(r['fichier']).stem.startswith('P') and '/fabriquees/' in r['fichier']}
    def key(row):
        return Path(row['parent']).stem+'/'+row['occurrence']
    focus={key(r):r for r in physical if r['source'] in reference_files}
    reader=Reader(MEC)
    shapes={n:reader.occurrence(r) for n,r in focus.items()}
    report=dict(date_utc=datetime.now(timezone.utc).isoformat(),freecad=A.Version(),
        script_sha256=sha(__file__),construction_sha256=sha(VER/'construction_prototype.json'),
        natifs_sha256=files,pieces=[],collisions=[],erreurs=[],finalisation_correcte=False,
        protocole='Toutes occurrences des références projet Pxx reconstruites, solide unique valide, intersections exactes après présélection des boîtes avec tous obstacles physiques ; seuil1e-4mm³.',
        qualification='À valider')
    for n,s in shapes.items():
        valid=s.isValid();count=len(s.Solids)
        report['pieces'].append(dict(objet=n,valide=valid,solides=count))
        if not valid or count!=1:
            report['erreurs'].append(dict(objet=n,type='piece_non_unique_ou_invalide'))
    seen=set();pairs=0
    for index,row in enumerate(physical,1):
        other=key(row)
        target=shapes.get(other)
        if target is None:
            target=reader.occurrence(row)
        for n,s in shapes.items():
            pair=tuple(sorted((n,other)))
            if n==other or pair in seen:
                continue
            seen.add(pair)
            if not overlap(s.BoundBox,target.BoundBox):
                continue
            pairs+=1
            print(json.dumps(dict(paire=[n,other])),flush=True)
            volume,details=common_volume(s,target)
            if volume>1e-4:
                report['collisions'].append(dict(a=n,b=other,volume_mm3=volume,details=details))
        if index%20==0:
            print(json.dumps(dict(obstacles=index,total=len(physical),collisions=len(report['collisions']))),flush=True)
    report.update(nombre_obstacles=len(physical),paires_presel_bbox=pairs,
        fichiers_non_modifies=all(sha(MEC/p)==h for p,h in files.items()),finalisation_correcte=True)
    report['conforme']=not report['erreurs'] and not report['collisions'] and report['fichiers_non_modifies']
    (VER/'controle_pieces_prototype.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n','utf-8')
    print(json.dumps(dict(conforme=report['conforme'],pieces=len(focus),collisions=report['collisions'],erreurs=report['erreurs'])),flush=True)
    return report['conforme']


if __name__=='__main__':
    raise SystemExit(0 if run() else 1)
