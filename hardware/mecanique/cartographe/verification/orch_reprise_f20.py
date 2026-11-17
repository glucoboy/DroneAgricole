"""Contrôle géométrique F20 en mémoire : aucun natif ni ancien registre écrit.

Les poses viennent de construction_prototype.json avec l'overlay de reprise.
Les BREP sont les natifs sauvegardés actuels. Seule la preuve JSON voisine
est écrite. Une limite d'enveloppe ne devient jamais un connecteur physique.
"""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import math
import FreeCAD as A
import Part
from read_brep_prototype import Reader

ROOT=Path(__file__).resolve().parents[4]
MEC=ROOT/'hardware/mecanique/cartographe'
VER=MEC/'verification'
OUT=VER/'orch_reprise_f20.json'
EPS=1e-5
NEAR=.3
MARGE_GEOMETRIQUE_MM=.1


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def bb(shape):
    b=shape.BoundBox
    return [b.XMin,b.YMin,b.ZMin,b.XMax,b.YMax,b.ZMax]


def overlap(a,b,tol=0):
    return all(min(getattr(a,k+'Max'),getattr(b,k+'Max'))+tol>=
               max(getattr(a,k+'Min'),getattr(b,k+'Min')) for k in 'XYZ')


def compare(cable,other):
    if not overlap(cable.BoundBox,other.BoundBox,NEAR):return None
    solids=other.Solids if len(other.Solids)>30 else [other]
    volumes=[];distances=[]
    for index,part in enumerate(solids):
        if not overlap(cable.BoundBox,part.BoundBox,NEAR):continue
        if overlap(cable.BoundBox,part.BoundBox):
            cut=cable.common(part)
            if not cut.isNull() and cut.Volume>EPS:
                volumes.append({'solide_index':index,'intersection_mm3':cut.Volume,
                                'bbox_intersection_mm':bb(cut)})
        # Distance par solide proche : jamais au composé OEM de 2059 solides.
        if not volumes:distances.append(cable.distToShape(part)[0])
    volume=sum(x['intersection_mm3'] for x in volumes)
    distance=None if volume>EPS else min(distances,default=None)
    if volume>EPS or distance is not None and distance<=NEAR:
        return {'intersection_mm3':volume,'distance_mm':distance,'solides_intersectes':volumes}
    return None


def main():
    files={}
    def read_json(relative):
        path=MEC/relative;raw=path.read_bytes()
        files[str(path.relative_to(ROOT)).replace('\\','/')]=hashlib.sha256(raw).hexdigest()
        return json.loads(raw.decode('utf-8-sig'))
    construction=read_json('verification/construction_prototype.json')
    overlay=read_json('verification/orch_reprise_collisions.json')
    routes=read_json('verification/routes_prototype.json')
    rows={(r['parent'],r['occurrence']):dict(r) for r in construction['occurrences']
          if r['parent'].startswith('sous_assemblages/')}
    for r in overlay.get('changements_occurrences',[]):
        key=r['parent'],r['occurrence']
        assert key in rows,('Occurrence overlay absente',key)
        rows[key]['matrice']=r['matrice']
    for r in overlay.get('ajouts_occurrences',[]):rows[r['parent'],r['occurrence']]=dict(r)
    counts={}
    for r in rows.values():counts[r['occurrence']]=counts.get(r['occurrence'],0)+1
    named={(r['occurrence'] if counts[r['occurrence']]==1 else
            Path(r['parent']).stem+'/'+r['occurrence']):r for r in rows.values()}
    assert len(named)==len(rows),'Identifiants d’occurrences ambigus'
    route=next(r for r in routes['routes'] if r['id']=='F20')
    assert named['F20']['source']==route['fichier']
    # Les sources sont hachées avant lecture BREP pour détecter une écriture concurrente.
    relatives={r['source'] for r in rows.values()}
    relatives.update(['sources_fabricants/orch_cao_masse_equipements/Waveshare_Orin_FAN_PWM_dimensions.jpg',
                      'sources_fabricants/orch_reprise_masses_equipements/Waveshare_Orin_FAN_PWM.html',
                      'verification/read_brep_prototype.py','verification/orch_reprise_f20.py'])
    for p in relatives:files[str((MEC/p).relative_to(ROOT)).replace('\\','/')]=sha(MEC/p)
    reader=Reader(MEC);shapes={};errors=[]
    for key,row in named.items():
        try:shapes[key]=reader.occurrence(row)
        except Exception as e:errors.append({'occurrence':key,'lecture':str(e)})
    assert not errors,errors
    fan=shapes['OrinFan'];original=shapes['F20']
    assert len(original.Solids)==1,'F20 doit avoir un solide unique'
    cable=original.Solids[0]
    wire=reader.shape(route['fichier'],route['objet_parcours'])
    row=named['F20'];pose=A.Placement(A.Matrix(*row['matrice']))
    source_pose=reader.placement(row['source'],row['objet_source'])
    wire.Placement=pose.multiply(source_pose.inverse()).multiply(wire.Placement)
    first=wire.Edges[0]
    assert isinstance(first.Curve,Part.Line),'Le départ doit être une droite'
    start,end=[v.Point for v in first.Vertexes]
    assert abs(start.x-end.x)<1e-8 and abs(start.z-end.z)<1e-8 and end.y>start.y
    target=A.Vector(start.x,fan.BoundBox.YMax+MARGE_GEOMETRIQUE_MM,start.z)
    assert start.y-1e-8<=target.y<end.y,'Reprise au-delà du premier point de tangence'
    revised=Part.Wire([Part.makeLine(target,end)]+list(wire.Edges[1:]))
    radii=[e.Curve.Radius for e in revised.Edges if isinstance(e.Curve,Part.Circle)]
    assert all(abs(r-5)<1e-8 for r in radii),'Rayon demandé non conservé'
    radius=route.get('diametre_exterieur_mm',route['diameter_mm'])/2
    section=Part.Wire([Part.makeCircle(radius,target,A.Vector(0,1,0))])
    candidate=revised.makePipeShell([section],True,False)
    assert candidate.isValid() and len(candidate.Solids)==1,'Balayage révisé invalide'
    # Contrôle indépendant : même forme obtenue en bornant le câble existant au plan extérieur.
    box=cable.BoundBox
    tool=Part.makeBox(box.XLength+2,target.y-box.YMin+1,box.ZLength+2,
                      A.Vector(box.XMin-1,box.YMin-1,box.ZMin-1))
    bounded=cable.cut(tool)
    symmetric=candidate.cut(bounded).Volume+bounded.cut(candidate).Volume
    assert symmetric<EPS,('Reprise non équivalente à une borne extérieure',symmetric)
    before=[];after=[];new=[];checks=0
    for name,other in shapes.items():
        if name=='F20':continue
        values=[]
        for state,output in [(cable,before),(candidate,after)]:
            checks+=1
            result=compare(state,other)
            values.append(0 if result is None else result['intersection_mm3'])
            if result is not None:output.append({'occurrence':name,**result})
        if values[1]>values[0]+EPS:new.append({'occurrence':name,'augmentation_mm3':values[1]-values[0]})
    points=[list(p) for p in route['points_mm']];points[0]=list(target)
    stable=all(sha(ROOT/p)==digest for p,digest in files.items())
    collisions_after=[p for p in after if p['intersection_mm3']>EPS]
    valid=stable and not errors and not new and not collisions_after
    result={
      'schema_version':'drone-agricole.orch-reprise-f20.v1','lot':'ORCH-CAO-MASSE-1',
      'date_utc':datetime.now(timezone.utc).isoformat(),'statut':'À valider',
      'protocole':'BREP des natifs actuels ; placements construction_prototype avec overlay changements/ajouts ; contrôle F20 contre chaque occurrence physique avant/après. Aucune sauvegarde de natif.',
      'configuration':'prototype_cartographe','outils':{'FreeCAD':A.Version(),'os':'Windows','architecture':'amd64'},
      'entrees_sha256':files,'sources_inchangees_pendant_controle':stable,
      'construction_date_utc':construction.get('date_utc'),'overlay_date_utc':overlay.get('date_utc'),
      'occurrences_physiques_controlees':len(shapes),'comparaisons_occurrences_avant_apres':checks,
      'diagnostic':{'premier_segment_droit_mm':[list(start),list(end)],
        'plan_exterieur_fan_Y_nominal_mm':fan.BoundBox.YMax,
        'bbox_fan_mm':bb(fan),'bbox_cable_avant_mm':bb(cable),
        'interferences_et_contacts_avant':before,
        'interpretation':'Le départ nominal pénètre la paroi pleine du modèle de carter, sans port documenté à cet endroit.'},
      'proposition':{'occurrence':'F20','parent':row['parent'],'fichier':row['source'],
        'applicable':valid,'deja_appliquee':(target-start).Length<1e-8,
        'points_avant_mm':route['points_mm'],'points_apres_mm':points,
        'diametre_mm':2*radius,'rayon_courbure_mm':5,
        'point_exterieur_mm':list(target),'ecart_face_nominale_mm':MARGE_GEOMETRIQUE_MM,
        'retrait_geometrique_depart_mm':(target-start).Length,
        'longueur_courbe_avant_mm':wire.Length,'longueur_courbe_apres_mm':revised.Length,
        'premier_segment_droit_restant_mm':(end-target).Length,
        'endpoint_refs_conserves':route['endpoint_refs'],
        'traitement_endpoint_FAN_SORTIE':'Borne extérieure de réservation, pas position du port réel. Liaison fonctionnelle F20 maintenue ; raccord terminal manquant explicitement bloquant.',
        'modification_physique_cordon_autorisee':False,
        'justification':'Déplacer uniquement le premier point à l’extérieur du carter coté, en restant avant la tangence du premier arc ; conserver les quatre autres segments et les deux arcs de rayon5mm.'},
      'verification_apres':{'solide_unique_valide':candidate.isValid() and len(candidate.Solids)==1,
        'wire_valide':revised.isValid(),'continuite':len(revised.Wires)==1,
        'rayons_arcs_mm':radii,'bbox_mm':bb(candidate),
        'ecart_volume_symetrique_balayage_vs_borne_mm3':symmetric,
        'interferences_et_contacts':after,'interferences_nouvelles':new,
        'interferences_restantes':collisions_after,'erreurs':errors,
        'conforme_geometrie_exterieure_nominale':valid},
      'sources':[{'id':'FAN_DRAWING','url':'https://www.waveshare.com/img/devkit/accessories/Orin-FAN-PWM/Orin-FAN-PWM-details-size.jpg',
        'fichier':'hardware/mecanique/cartographe/sources_fabricants/orch_cao_masse_equipements/Waveshare_Orin_FAN_PWM_dimensions.jpg',
        'date_consultation':'2026-10-26','cotes_documentees_mm':{'longueur':[57.8,.2],'largeur':[39,.25],'hauteur':[18,.25]},
        'port_et_sortie_cordon_cotes':False,'droits':'Plan fabricant public ; licence de redistribution non établie, original conservé.'},
        {'id':'FAN_SPEC','url':'https://www.waveshare.com/product/ai/accessories/orin-fan-pwm.htm',
         'fichier':'hardware/mecanique/cartographe/sources_fabricants/orch_reprise_masses_equipements/Waveshare_Orin_FAN_PWM.html',
         'date_consultation':'2026-10-26','cordon_OEM_longueur_documentee_mm':[37,3],
         'limite':'La longueur OEM ne fournit aucune coordonnée du port ; les21,27mm/19,67mm de courbe sont des réservations géométriques.',
         'droits':'Page fabricant publique, droits réservés ; original conservé.'}],
      'problemes':[{'id':'F20-RACCORD-PORT-FAN','bom_ids':['ELEC-F20','MEC-REFROIDISSEMENT-JETSON'],
        'statut':'À valider','borne_connue_mm':list(target),'port_reel_mm':None,
        'longueur_raccord_manquant_mm':None,'masse_raccord_g':None,
        'ecart_a_face_nominale_mm':MARGE_GEOMETRIQUE_MM,
        'retrait_par_rapport_ancien_point_candidat_mm':(target-start).Length,
        'probleme_geometrique':'Segment entre la borne extérieure de réservation et le port réel non documenté ; aucun perçage fictif créé dans le carter.',
        'probleme_massique':'La portion supprimée du proxy n’est pas une coupe du cordon OEM. Sa masse, sa longueur totale37±3mm et la réserve de longueur restent dans le périmètre du cordon complet ; aucune masse déduite de la différence de volume.',
        'information_necessaire':'Coordonnées/direction de la sortie réelle, détrompage/prise fan, dégagement et cheminement/réserve du cordon OEM complet ; profondeur et géométrie terminale. Les écarts0,1 et1,6mm ne bornent pas le raccord réel inconnu.'}],
      'finalisation_correcte':valid,'qualification_physique':False,
      'interface_fan_validee':False,'absence_interferences_globale_drone_demontree':False,
      'limites':['Le contrôle de toutes les occurrences concerne F20 contre chacune ; il ne requalifie pas toutes les paires du drone.',
        'La marge0,1mm est un choix géométrique nominal ; ni une tolérance d’assemblage validée ni une localisation fabricant du port.',
        'Aucun natif, document partagé ou ancienne preuve modifié ; root possède l’application puis le contrôle du natif sauvegardé.']}
    for source in result['sources']:source['sha256']=files[source['fichier']]
    OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'preuve':str(OUT),'finalisation_correcte':valid,'comparaisons':checks,
      'avant':[(p['occurrence'],p['intersection_mm3']) for p in before],
      'apres':[(p['occurrence'],p['intersection_mm3']) for p in after]},ensure_ascii=True),flush=True)
    if not valid:raise SystemExit(1)


if __name__=='__main__':main()
