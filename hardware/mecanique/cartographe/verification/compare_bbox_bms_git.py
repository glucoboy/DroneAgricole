"""Comparaison isolée avec la définition arrière ; aucune mutation des CAO actuelles.

Les deux documents non suivis dans l'instantané sont reconstruits uniquement
par les cellules Longueur=70 mm et Rehausse=20 mm. Leur identité binaire avec
l'état arrière n'est pas revendiquée. Exécuter --prepare puis --measure dans
deux processus Python FreeCAD neufs.
"""
from pathlib import Path
import argparse, hashlib, json, subprocess
import datetime as task_datetime_module
import FreeCAD as A
import Part

ROOT = Path(__file__).resolve().parents[4]
MEC = ROOT / 'hardware/mecanique/cartographe'
VER = MEC / 'verification'
BASE = MEC / 'exports/comparaison_bms_arriere'
OUT = VER / 'bbox_bms_arriere_git.json'
REVIEW = VER / 'revue_bms_cassette.json'
COMMIT = '94d04d0'
TOP = Path('hardware/mecanique/cartographe/assemblages/Integration_Stack_Revue_20261003.FCStd')
REBUILD = {
    'hardware/mecanique/cartographe/pieces/fabriquees/P37_Entretoise70_6061_M3.FCStd': ('Longueur', '70 mm'),
    'hardware/mecanique/cartographe/sous_assemblages/SA01_Chassis_Stack_Revue_20261003.FCStd': ('Rehausse', '20 mm'),
}

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def relative(p): return Path(p).resolve().relative_to(ROOT).as_posix()
def read(p): return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def write(a): OUT.write_text(json.dumps(a, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
def git(*args): return subprocess.run(['git', '-C', str(ROOT), *args], capture_output=True)

def isolated_documents():
    docs = list(A.listDocuments().values())
    bad = [d.FileName for d in docs if d.FileName and not Path(d.FileName).resolve().is_relative_to(BASE.resolve())]
    assert not bad, ('Dépendance hors baseline, aucune mutation permise', bad)
    return docs

def prepare():
    assert BASE.resolve().is_relative_to((MEC/'exports').resolve())
    assert git('check-ignore', str(BASE)+'/').returncode == 0, 'La baseline doit rester ignorée par Git'
    # La revue courante peut désormais concerner l'implantation supérieure.
    # La preuve arrière fige les empreintes attendues pour les futurs rejeux.
    sources = ({r['fichier']: r['sha256_revue_arriere'] for r in read(OUT)['sources']}
               if OUT.exists() else read(REVIEW)['sources_natives_revalidees_sha256'])
    assert len(sources) == 147
    rows, payloads = [], []
    for name, expected in sources.items():
        p = ROOT/name
        result = git('show', COMMIT+':'+name)
        if result.returncode == 0:
            data = result.stdout
            assert hashlib.sha256(data).hexdigest() == expected, ('Git différent de la revue arrière', name)
            origin = 'Git '+COMMIT
        elif name in REBUILD:
            data = p.read_bytes()
            origin = 'Copie actuelle pour reconstruction paramétrique autorisée'
        else:
            data = p.read_bytes()
            assert hashlib.sha256(data).hexdigest() == expected, ('Référence hors Git modifiée', name)
            origin = 'Copie actuelle strictement identique au SHA arrière'
        row = dict(fichier=name, origine=origin, sha256_revue_arriere=expected,
                   sha256_copie_initiale=hashlib.sha256(data).hexdigest(),
                   reconstruction_parametrique=name in REBUILD and result.returncode != 0)
        rows.append(row); payloads.append((BASE/name, data))
    # Toutes les sources sont contrôlées avant toute extraction.
    for p, data in payloads:
        p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(data)
    top = A.openDocument(str(BASE/TOP))
    isolated_documents()
    for name, (alias, value) in REBUILD.items():
        d = next(d for d in A.listDocuments().values() if Path(d.FileName).resolve() == (BASE/name).resolve())
        cell = d.Parametres.getCellFromAlias(alias)
        assert cell, (name, alias)
        d.Parametres.set(cell, value)
        for o in d.Objects: o.touch()
    for _ in range(2):
        for d in isolated_documents(): d.recompute()
    for name in REBUILD:
        d = next(d for d in A.listDocuments().values() if Path(d.FileName).resolve() == (BASE/name).resolve())
        d.save()  # Seuls les deux documents dérivés dans la baseline sont sauvegardés.
    for row in rows: row['sha256_baseline'] = sha(BASE/row['fichier'])
    proof = dict(schema_version=1, date_utc=task_datetime_module.datetime.now(task_datetime_module.timezone.utc).isoformat(),
                 git_commit=git('rev-parse', COMMIT).stdout.decode().strip(),
                 reference='Reconstruction paramétrique isolée de la définition BMS arrière ; non identique aux octets du commit',
                 baseline=relative(BASE), sources=rows, sources_strictes=145,
                 reconstructions=[dict(fichier=f, alias=a, valeur=v) for f,(a,v) in REBUILD.items()],
                 preparation_correcte=True, mesure_finalisee=False, qualification='À valider',
                 limites=['Deux documents non suivis dans le commit : copie actuelle et restauration de deux cellules seulement ; identité complète de leur ancien arbre/métadonnées non démontrée.',
                          'Les 145 autres natifs sont identiques aux empreintes de la revue arrière : 119 Git et 26 sources hors Git inchangées.',
                          'Comparaison géométrique de volumes englobants ; aucune qualification de masse, thermique, rigidité, tolérances ou extraction.'])
    write(proof)
    print(json.dumps({'preparation_correcte':True,'sources':len(rows),'reconstructions':list(REBUILD)}), flush=True)

def bbox(shape):
    b=shape.BoundBox
    return [b.XMin,b.YMin,b.ZMin,b.XMax,b.YMax,b.ZMax]

def measure():
    proof=read(OUT); assert proof['preparation_correcte']
    for r in proof['sources']: assert sha(BASE/r['fichier']) == r['sha256_baseline'], r['fichier']
    top=A.openDocument(str(BASE/TOP))
    for _ in range(2):
        for d in isolated_documents():
            for o in d.Objects: o.touch()
            d.recompute()
    dock=top.SA02A_Dock20Ah.LinkedObject.Document
    dist=top.SA07_Distribution_Systeme_Candidat.LinkedObject.Document
    ch=top.SA01_Chassis_Rehausse20.LinkedObject.Document
    col=next(d for d in A.listDocuments().values() if Path(d.FileName).stem=='P37_Entretoise70_6061_M3')
    assert abs(float(col.Parametres.Longueur)-70)<1e-6
    assert abs(float(ch.Parametres.Rehausse)-20)<1e-6
    assert abs(ch.Part__Feature311.Shape.BoundBox.ZMin-103)<1e-6
    invalid=[d.Name+'.'+o.Name for d in isolated_documents() for o in d.Objects if 'Invalid' in o.State]
    broken=[d.Name+'.'+o.Name for d in isolated_documents() for o in d.Objects if o.TypeId=='App::Link' and (not o.LinkedObject or o.Shape.isNull())]
    assert not invalid and not broken,(invalid,broken)
    boxes=dict(batterie_et_energie=bbox(Part.makeCompound([dock.Ensemble.Shape,dist.Reference.Shape])),
               cassette_mobile=bbox(Part.makeCompound([o.Shape for o in dock.Objects if o.TypeId=='App::Link' and getattr(o,'Mobile','non')=='oui'])),
               integration_locale=bbox(top.IntegrationRevue.Shape))
    import math
    dimensions={k:[b[i+3]-b[i] for i in range(3)] for k,b in boxes.items()}
    proof.update(mesure_finalisee=True,processus_mesure_neuf=True,FreeCAD='.'.join(A.Version()[:3]),
                 recette_sha256=sha(__file__),date_mesure_utc=task_datetime_module.datetime.now(task_datetime_module.timezone.utc).isoformat(),
                 passes_recalcul_force=2,documents_isoles=len(isolated_documents()),erreurs_recalcul=invalid,
                 liens_non_resolus=broken,bbox_mm=boxes,dimensions_mm=dimensions,
                 volumes_englobants_mm3={k:math.prod(v) for k,v in dimensions.items()},
                 parametres_reconstruits={'P37_Longueur_mm':70,'chassis_Rehausse_mm':20,'plateau_Zmin_mm':ch.Part__Feature311.Shape.BoundBox.ZMin},
                 finalisation_correcte=True)
    write(proof);print(json.dumps({'bbox_mm':boxes,'dimensions_mm':dimensions,'finalisation_correcte':True}),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True)
    g.add_argument('--prepare',action='store_true');g.add_argument('--measure',action='store_true')
    args=p.parse_args()
    prepare() if args.prepare else measure()
