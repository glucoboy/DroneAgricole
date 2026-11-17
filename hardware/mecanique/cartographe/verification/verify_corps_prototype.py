"""Contre-vérification indépendante des trois poses, depuis les BRep sauvegardés."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib,json,math,sys
import FreeCAD as A
ROOT=Path(__file__).resolve().parents[4]
MEC=ROOT/'hardware/mecanique/cartographe'
VER=MEC/'verification'
sys.path.insert(0,str(VER))
from read_brep_prototype import Reader
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
read=lambda p:json.loads(Path(p).read_text('utf-8'))
EPS=1e-4
proof=read(VER/'controle_colliers_prototype.json')
assert proof['conforme'] and len(proof['retenues_boitiers_antennes'])==3
scene=ROOT/proof['scene_fichier']
assert sha(scene)==proof['scene_sha256']
build=read(VER/'construction_prototype.json');routes=read(VER/'routes_prototype.json')
assert proof['construction_sha256']==sha(VER/'construction_prototype.json')
files={r['fichier']:r['sha256'] for r in build['references']}
files.update(build['sources_preservees'])
assert all(sha(MEC/p)==h for p,h in files.items())
reader=Reader(MEC);saved=Reader(scene.parent)
physical=[(r['parent']+'#'+r['occurrence'],reader.occurrence(r))
          for r in build['occurrences'] if r['parent'].startswith('sous_assemblages/')]
bands=[saved.shape(scene.name,'Collier'+str(i)) for i in range(1,16)]
heads=[saved.shape(scene.name,'Tete'+str(i)) for i in range(1,16)]
def overlapping(a,b):
    return all(min(getattr(a,k+'Max'),getattr(b,k+'Max'))-
        max(getattr(a,k+'Min'),getattr(b,k+'Min'))>1e-5 for k in 'XYZ')
hits=[];errors=[];measures=[];pairs=0
for index,tag in [(12,'QS8_P76'),(13,'ANTENNE_RF0'),(14,'ANTENNE_RF1')]:
    band,head=bands[index],heads[index]
    if not (band.isValid() and head.isValid() and len(band.Solids)==len(head.Solids)==1):
        errors.append(tag+': solide non valide ou multiple')
    engagement=head.common(band).Volume
    upper_perimeter=band.Volume/(4.6*1.2)
    if engagement<=EPS or abs(head.Volume-7.3*7.6*5.9)>EPS or upper_perimeter>math.pi*50:
        errors.append(tag+': engagement, enveloppe de tête ou longueur non conforme')
    reused=0
    for name,obstacle in physical:
        if tag=='ANTENNE_RF1' and name.endswith('#CollierAncrageRF1'):
            difference=band.cut(obstacle).Volume+obstacle.cut(band).Volume
            if difference>EPS:errors.append(tag+': boucle réemployée non identique')
            reused+=1
            # Le corps est la même occurrence. La tête reste contrôlée contre
            # toutes les autres géométries ; l'engagement dans cette occurrence
            # est celui de sa propre serrure, mesuré ci-dessus.
            continue
        for kind,shape in [('bande',band),('tete',head)]:
            if not overlapping(shape.BoundBox,obstacle.BoundBox):continue
            pairs+=1;volume=shape.common(obstacle).Volume
            if volume>EPS:hits.append(dict(collier=tag,forme=kind,obstacle=name,volume_mm3=volume))
    if tag=='ANTENNE_RF1' and reused!=1:errors.append(tag+': occurrence native absente ou ambiguë')
    for other_index,(other_band,other_head) in enumerate(zip(bands,heads)):
        if other_index==index:continue
        for kind,shape in [('bande',band),('tete',head)]:
            for other_kind,obstacle in [('bande',other_band),('tete',other_head)]:
                if not overlapping(shape.BoundBox,obstacle.BoundBox):continue
                pairs+=1;volume=shape.common(obstacle).Volume
                if volume>EPS:hits.append(dict(collier=tag,forme=kind,
                    obstacle=other_kind+str(other_index+1),volume_mm3=volume))
    measures.append(dict(id=tag,bande_valide=band.isValid(),tete_valide=head.isValid(),
        volume_tete_mm3=head.Volume,engagement_serrure_mm3=engagement,
        majorant_perimetre_interieur_mm=upper_perimeter,
        occurrence_native_reemployee=reused))
unchanged=sha(scene)==proof['scene_sha256'] and all(sha(MEC/p)==h for p,h in files.items())
result=dict(date_utc=datetime.now(timezone.utc).isoformat(),auteur='Agent principal, contre-vérification des propositions des autres agents',
    script_fichier=str(Path(__file__).relative_to(ROOT)).replace('\\','/'),script_sha256=sha(__file__),
    construction_sha256=sha(VER/'construction_prototype.json'),
    colliers_sha256=sha(VER/'controle_colliers_prototype.json'),scene_fichier=proof['scene_fichier'],scene_sha256=sha(scene),
    natifs_sha256=files,occurrences_controlees=len(physical),paires_bbox_exactes=pairs,mesures=measures,
    protocole='Relecture BRep indépendante du contrôleur de pose ; intersections OCCT avec toutes les occurrences et les 14 autres bandes/têtes, seuil1e-4mm³. Seule la même boucle native RF1 et l’engagement de chaque tête dans sa propre bande sont identifiés comme identités/contacts fonctionnels.',
    erreurs=errors,collisions=hits,fichiers_non_modifies=unchanged,
    conforme=not errors and not hits and unchanged,finalisation_correcte=True,qualification='À valider')
path=VER/'review_assemblage_prototype.json';review=read(path);review['contre_verification_corps']=result
path.write_text(json.dumps(review,ensure_ascii=False,indent=2)+'\n','utf-8')
print(json.dumps({k:result[k] for k in ('conforme','occurrences_controlees','paires_bbox_exactes','erreurs','collisions')}),flush=True)
raise SystemExit(0 if result['conforme'] else 1)
