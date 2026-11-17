"""Contrôle indépendant BRep des guides P72/P73/P75, du berceau P76 et des vis.

Usage : Python FreeCAD verify_fixations_guides_prototype.py [--preflight]
        [--output chemin.json]

Ne construit ni ne sauvegarde de CAO, n'importe pas FreeCADGui. Refuse une
construction périmée ou sans les nouvelles occurrences. La preuve distingue
validation géométrique nominale et qualification physique toujours À valider.
"""
from datetime import datetime, timezone
from pathlib import Path
import argparse
import hashlib
import json
import math
import sys
import traceback
import FreeCAD as App
import Part
from read_brep_prototype import Reader

MEC = Path(__file__).resolve().parents[1]
VER = MEC/'verification'
EPS = 1e-4
VOLUME_TOL = 1e-4
SA2 = 'SA02_Prototype_Batterie/'
SA3 = 'SA03_Prototype_Energie/'
SA5 = 'SA05_Prototype_Avionique/'
SA7 = 'SA07_Prototype_Faisceaux/'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def key(row):
    return Path(row['parent']).stem+'/'+row['occurrence']


def bbox(shape):
    b = shape.optimalBoundingBox()
    return [round(getattr(b, k), 6) for k in ('XMin','YMin','ZMin','XMax','YMax','ZMax')]


def overlap(a,b):
    return all(min(getattr(a,k+'Max'),getattr(b,k+'Max')) -
               max(getattr(a,k+'Min'),getattr(b,k+'Min')) > 1e-5 for k in 'XYZ')


def common_volume(a,b):
    if not overlap(a.BoundBox,b.BoundBox):
        return 0.0,[]
    parts=b.Solids if len(b.Solids)>30 else [b]
    volume,details=0.0,[]
    for i,s in enumerate(parts):
        if not overlap(a.BoundBox,s.BoundBox):continue
        # Les guides ajourés ont une grande boîte contenant le vide central.
        # La distance OCCT élimine ces paires disjointes avant le booléen,
        # sans exempter un contact ou une inclusion volumique.
        if a.distToShape(s)[0]>EPS:continue
        c=a.common(s)
        if c.Volume>VOLUME_TOL:
            volume+=c.Volume
            details.append(dict(indice_solide=i if len(parts)>1 else None,
                                volume_mm3=round(c.Volume,6),bbox_mm=bbox(c)))
    return volume,details


def stations():
    """Empilements prescrits, indépendants des fonctions de construction."""
    rows=[]
    for i,(x,y) in enumerate([(-88,43),(-96,43),(88,-43),(96,-43)]):
        guide=SA7+('P72_Guide' if x<0 else 'P73_Guide')
        rows.append(dict(id='GuideBas'+str(i),xy=[x,y],head=-83.5,direction=-1,length=12,
            screw=SA7+'VisGuideBas'+str(i),nut=SA7+'EcrouGuideBas'+str(i),tip=-95.5,
            layers=[(SA7+'EcrouGuideBas'+str(i),-94.5,-90.5,2.2),
                    (SA7+'RondelleGuideBasB'+str(i),-90.5,-90,2.2),
                    (SA2+'Semelle',-90,-87,3.3),(guide,-87,-84,3.3),
                    (SA7+'RondelleGuideBasH'+str(i),-84,-83.5,2.2)],
            bearing=SA7+'RondelleGuideBasH'+str(i),nut_bounds=[-94.5,-90.5],protrusion=1.0,
            source='EQ_ISO4762_M3x12_Prototype.FCStd'))
    for i,(x,y) in enumerate([(-80,56),(80,-56)]):
        guide=SA7+('P72_Guide' if x<0 else 'P73_Guide')
        rows.append(dict(id='GuideMilieu'+str(i),xy=[x,y],head=36.2,direction=1,length=12,
            screw=SA7+'VisGuideMilieu'+str(i),nut=SA7+'EcrouGuideMilieu'+str(i),tip=48.2,
            layers=[(SA3+'Isolation',36.2,39,3.3),(guide,39,42,3.3),
                    (SA7+'RondelleGuideMilieu'+str(i),42,42.5,2.2),
                    (SA7+'EcrouGuideMilieu'+str(i),42.5,46.5,2.2)],
            bearing=SA3+'Isolation',nut_bounds=[42.5,46.5],protrusion=1.7,
            source='EQ_ISO4762_M3x12_Prototype.FCStd'))
    for i,(x,y) in enumerate([(x,y) for x in [-66,66] for y in [-43,43]]):
        layers=[(SA5+'Interface',85,88,3.3)]
        if x*y<0:
            layers.append((SA7+('P72_Guide' if x<0 else 'P73_Guide'),88,91,3.3))
            layers.append((SA7+'P75_Cadre',91,94,3.3))
        else:layers.append((SA7+'P75_Cadre',88,94,3.3))
        layers.extend([(SA7+'RondelleGuideHaut'+str(i),94,94.5,2.2),
                       (SA7+'EcrouGuideHaut'+str(i),94.5,98.5,2.2)])
        rows.append(dict(id='GuideHaut'+str(i),xy=[x,y],head=85.12,direction=1,length=16,
            screw=SA7+'VisGuideHaut'+str(i),nut=SA7+'EcrouGuideHaut'+str(i),tip=101.12,
            layers=layers,bearing=SA5+'Interface',nut_bounds=[94.5,98.5],protrusion=2.62,
            source='EQ_ISO10642_M3x16_Prototype.FCStd'))
    for i,y in [(2,-29),(3,29)]:
        rows.append(dict(id='ButeeDroite'+str(i),xy=[105,y],head=-81.5,direction=-1,length=16,
            screw=SA2+'VisButee'+str(i),nut=SA2+'EcrouButee'+str(i),tip=-97.5,
            layers=[(SA2+'EcrouButee'+str(i),-94.5,-90.5,2.2),
                    (SA2+'RondelleButeeB'+str(i),-90.5,-90,2.2),
                    (SA2+'Semelle',-90,-87,3.3),(SA2+'Butee1',-87,-85,3.3),
                    (SA2+'BerceauQS8',-85,-82,3.3),
                    (SA2+'RondelleButeeH'+str(i),-82,-81.5,2.2)],
            bearing=SA2+'RondelleButeeH'+str(i),nut_bounds=[-94.5,-90.5],protrusion=3.0,
            source='EQ_ISO4762_M3x16_Prototype.FCStd'))
    return rows


def preflight():
    path=VER/'construction_prototype.json'
    build=json.loads(path.read_text('utf-8'))
    if not build.get('finalisation_correcte'):
        raise RuntimeError('Construction non finalisée ; contrôle non exécuté.')
    if build['script_sha256']!=sha(VER/'build_prototype.py'):
        raise RuntimeError('Recette principale modifiée depuis construction ; final périmé, contrôle non exécuté.')
    recipes=build.get('recettes_sha256',{})
    required_recipes={'prototype_guides.py','prototype_routage.py','cable_workbench_prototype.py',
                      'configuration_faisceau_haut_prototype.json','prototype_retenues.py',
                      'prototype_retenues_puissance.py','prototype_retenues_capteurs.py',
                      'prototype_retenues_locales.py','prototype_retenues_bras.py'}
    if not required_recipes.issubset(recipes):
        raise RuntimeError('Empreintes des recettes de guides/routage absentes ; contrôle non exécuté.')
    if any(sha(VER/name)!=digest for name,digest in recipes.items()):
        raise RuntimeError('Recette secondaire modifiée depuis construction ; contrôle non exécuté.')
    occurrences={key(r):r for r in build['occurrences'] if r['parent'].startswith('sous_assemblages/')}
    specs=stations()
    required={s['screw'] for s in specs}|{n for s in specs for n,_,_,_ in s['layers']}
    required|={SA7+'P72_Guide',SA7+'P73_Guide',SA7+'P75_Cadre',SA2+'BerceauQS8',SA2+'QS8_manuel',
               SA7+'P77_BerceauReserveUSB',SA7+'P78_RetenueCameraM8'}
    missing=required-set(occurrences)
    if missing:raise RuntimeError('Construction sans nouvelles fixations : '+', '.join(sorted(missing)))
    expected={r['fichier']:r['sha256'] for r in build['references']}
    expected.update(build['sources_preservees'])
    bad=[p for p,h in expected.items() if not (MEC/p).is_file() or sha(MEC/p)!=h]
    if bad:raise RuntimeError('Natifs différents de construction : '+', '.join(bad))
    return build,occurrences,expected,specs


def run(args):
    build,occurrences,before,specs=preflight()
    construction_hash=sha(VER/'construction_prototype.json')
    if args.preflight:
        print('Préconditions satisfaites ; aucun contrôle géométrique exécuté.',flush=True)
        return 0
    reader=Reader(MEC)
    errors=[]
    def error(kind,**data):errors.append(dict(type=kind,**data))
    guide_fix={n for n in occurrences if n.startswith(SA7) and
               n.split('/')[-1].startswith(('VisGuide','RondelleGuide','EcrouGuide'))}
    counts={p:sum(n.split('/')[-1].startswith(p) for n in guide_fix) for p in ('VisGuide','RondelleGuide','EcrouGuide')}
    if counts!={'VisGuide':10,'RondelleGuide':14,'EcrouGuide':10}:error('comptage_guides',observe=counts)
    right_fix={SA2+p+str(i) for i in [2,3] for p in ['VisButee','RondelleButeeH','RondelleButeeB','EcrouButee']}
    supports={SA7+'P72_Guide',SA7+'P73_Guide',SA7+'P75_Cadre',SA2+'BerceauQS8',
              SA2+'Semelle',SA3+'Isolation',SA5+'Interface',
              SA7+'P77_BerceauReserveUSB',SA7+'P78_RetenueCameraM8'}
    focus=guide_fix|right_fix|supports
    needed=focus|{n for s in specs for n,_,_,_ in s['layers']}|{SA2+'QS8_manuel'}
    shapes={n:reader.occurrence(occurrences[n]) for n in needed}
    # Les matrices contrôlées proviennent également des objets de lien sauvegardés.
    for row in build['occurrences']:
        name=key(row)
        types,objects=reader.xml(row['parent']);props=objects[row['occurrence']]
        if types[row['occurrence']]!='App::Link' or props['LinkTransform'].find('Bool').get('value')!='false':
            error('type_lien_non_pris_en_charge',objet=name);continue
        actual=reader.placement(row['parent'],row['occurrence']).toMatrix().A
        if max(abs(x-y) for x,y in zip(actual,row['matrice']))>1e-6:error('matrice_native_differente',objet=name)
        if not reader.placement(row['parent'],'Ensemble').isIdentity():error('repere_parent_non_identite',objet=name)
        if row['parent']==build['assemblage'] and not reader.placement(row['parent'],row['occurrence']).isIdentity():
            error('sous_assemblage_final_deplace',objet=name)
    report=dict(date_utc=datetime.now(timezone.utc).isoformat(),construction_sha256=construction_hash,
        freecad=App.Version(),script_sha256=sha(__file__),lecteur_sha256=sha(VER/'read_brep_prototype.py'),
        recettes_sha256=build['recettes_sha256'],natifs_sha256=before,
        qualification='À valider',finalisation_correcte=False,erreurs=errors,
        fixations_guides=counts,fixations_butee_droite=8,fixations_total=42,
        occurrences_controlees=sorted(focus),pieces_controlees=[],empilements=[],collisions=[])
    path=Path(args.output) if args.output else VER/'controle_fixations_guides_prototype.json'
    path.parent.mkdir(parents=True,exist_ok=True)
    def save():path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    for n in sorted(supports):
        s=shapes[n];valid=s.isValid();count=len(s.Solids)
        report['pieces_controlees'].append(dict(objet=n,solides=count,valide=valid,bbox_mm=bbox(s)))
        if not valid or count!=1:error('piece_non_unique_ou_invalide',objet=n,solides=count,valide=valid)
    for spec in specs:
        x,y=spec['xy'];row=occurrences[spec['screw']]
        if Path(row['source']).name!=spec['source']:error('reference_vis',station=spec['id'],observe=row['source'],attendu=spec['source'])
        pose=App.Placement(App.Matrix(*row['matrice']))
        source_pose=reader.placement(row['source'],row['objet_source'])
        shaft=reader.shape(row['source'],'Tige');head=reader.shape(row['source'],'Tete')
        transform=pose.multiply(source_pose.inverse())
        for shape in (shaft,head):shape.Placement=transform.multiply(shape.Placement)
        end0=transform.multVec(App.Vector(0,0,0));end1=transform.multVec(App.Vector(0,0,-spec['length']))
        expected_start=App.Vector(x,y,spec['head']);expected_tip=App.Vector(x,y,spec['tip'])
        if (end0-expected_start).Length>EPS or (end1-expected_tip).Length>EPS:
            error('pose_ou_longueur_prescrite',station=spec['id'],debut=list(end0),extremite=list(end1))
        actual=shaft.optimalBoundingBox();z0,z1=actual.ZMin,actual.ZMax
        length=z1-z0;expected_volume=math.pi*1.5**2*spec['length']
        if (abs(length-spec['length'])>EPS or abs(shaft.Volume-expected_volume)>EPS or
            abs((actual.XMin+actual.XMax)/2-x)>EPS or abs((actual.YMin+actual.YMax)/2-y)>EPS or
            abs(actual.XLength-3)>EPS or abs(actual.YLength-3)>EPS):
            error('tige_hors_definition',station=spec['id'],longueur=length,volume=shaft.Volume,bbox_mm=bbox(shaft))
        nut=shapes[spec['nut']];nb=nut.optimalBoundingBox()
        engagement=max(0,min(z1,nb.ZMax)-max(z0,nb.ZMin))
        protrusion=z1-nb.ZMax if spec['direction']>0 else nb.ZMin-z0
        if abs(engagement-4.0)>EPS or abs(protrusion-spec['protrusion'])>EPS:
            error('engagement_ecrou',station=spec['id'],recouvrement_mm=engagement,saillie_mm=protrusion)
        seat=head.distToShape(shapes[spec['bearing']])[0]
        if seat>EPS:error('tete_sans_appui',station=spec['id'],distance_mm=seat)
        entry=dict(id=spec['id'],xy_mm=[x,y],longueur_tige_mm=round(length,6),
            z_tete_mm=round(end0.z,6),z_pointe_mm=round(end1.z,6),
            recouvrement_ecrou_mm=round(engagement,6),saillie_mm=round(protrusion,6),
            distance_tete_portee_mm=round(seat,8),couches=[],contacts=[])
        # Une sonde annulaire complète démontre la matière autour du perçage
        # sur toute l'épaisseur prescrite ; une sonde axiale contrôle le passage.
        for name,lo,hi,inner in spec['layers']:
            height=hi-lo-2e-5;origin=App.Vector(x,y,lo+1e-5)
            annulus=Part.makeCylinder(inner+.1,height,origin).cut(Part.makeCylinder(inner,height,origin))
            fraction=annulus.common(shapes[name]).Volume/annulus.Volume
            bore=Part.makeCylinder(1.49,height,origin)
            blocked=bore.common(shapes[name]).Volume
            entry['couches'].append(dict(objet=name,z_mm=[lo,hi],fraction_appui_annulaire=fraction,obstruction_passage_mm3=blocked))
            if abs(fraction-1)>1e-4 or blocked>VOLUME_TOL:
                error('appui_local_ou_passage',station=spec['id'],objet=name,fraction_matiere=fraction,obstruction_mm3=blocked)
        for a,b in zip(spec['layers'],spec['layers'][1:]):
            distance=shapes[a[0]].distToShape(shapes[b[0]])[0]
            entry['contacts'].append(dict(a=a[0],b=b[0],distance_mm=distance))
            if distance>EPS:error('couches_non_jointives',station=spec['id'],a=a[0],b=b[0],distance_mm=distance)
        report['empilements'].append(entry);save()
    # Berceau et connecteur : pose nominale contrôlée indépendamment du routage.
    qs=shapes[SA2+'QS8_manuel'];expected_qs=[101,-33,-59,125,9,-44]
    if max(abs(a-b) for a,b in zip(bbox(qs),expected_qs))>EPS:error('pose_qs8',observe=bbox(qs),attendu=expected_qs)
    distance=qs.distToShape(shapes[SA2+'BerceauQS8'])[0]
    report['appui_qs8_mm']=distance
    if distance>EPS:error('qs8_sans_appui',distance_mm=distance)
    cable_ids={r['id'] for r in json.loads((VER/'routes_prototype.json').read_text('utf-8'))['routes']}
    physical={n:o for n,o in occurrences.items() if not (n.startswith(SA7) and o['occurrence'] in cable_ids)}
    seen=set();pairs=0
    for index,(other,row) in enumerate(physical.items(),1):
        target=shapes.get(other)
        if target is None:target=reader.occurrence(row)
        for name in sorted(focus):
            pair=tuple(sorted((name,other)))
            if name==other or pair in seen:continue
            seen.add(pair)
            if not overlap(shapes[name].BoundBox,target.BoundBox):continue
            pairs+=1
            volume,details=common_volume(shapes[name],target)
            if volume>VOLUME_TOL:
                report['collisions'].append(dict(a=name,b=other,volume_mm3=round(volume,6),details=details))
        report.update(obstacles_controles=index,paires_presel_bbox=pairs);save()
    unchanged=all(sha(MEC/p)==h for p,h in before.items()) and sha(VER/'construction_prototype.json')==construction_hash
    if not unchanged:error('fichiers_modifies_pendant_controle')
    report.update(finalisation_correcte=True,fichiers_non_modifies=unchanged,
        conclusion='Conforme aux critères géométriques déclarés' if not errors and not report['collisions'] else 'Non conforme aux critères géométriques déclarés',
        criteres={'volume_intersection_max_mm3':VOLUME_TOL,'tolerance_geometrie_mm':EPS,
            'recouvrement_ecrou_mm':4,'saillies_mm':{'P60':1,'P64':1.7,'P75':2.62,'P76':3},
            'jeu_passage_sonde':'Rayon sonde 1,49 mm, inférieur à la tige nominale 1,5 mm ; intersections tige/pièces contrôlées séparément.',
            'appuis':'Contacts locaux prescrits et matière annulaire continue autour des 12 axes ; tête fraisée posée à Z85,12.',
            'intersections':'Aucune exemption de volume positif, y compris les interfaces filetées simplifiées.'},
        limites=['Géométrie nominale seulement : aucun filetage réel, couple, précharge ou essai de tenue.',
            'Le recouvrement de 4 mm est celui de l’enveloppe d’écrou ; engagement métallique et bague frein à confirmer sur lot.',
            'Accès outil, tolérances, matériaux, fatigue et vibration non qualifiés.',
            'Les câbles sont contrôlés séparément ; ce contrôle porte sur structure, supports et fixations.'])
    save();print(json.dumps({k:report[k] for k in ('conclusion','fixations_total','paires_presel_bbox')},ensure_ascii=False),flush=True)
    return 1 if errors or report['collisions'] else 0


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--preflight',action='store_true');parser.add_argument('--output')
    try:sys.exit(run(parser.parse_args()))
    except Exception:
        traceback.print_exc();sys.exit(2)
