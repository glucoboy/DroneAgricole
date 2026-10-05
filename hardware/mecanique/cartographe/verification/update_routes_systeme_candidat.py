"""Recette CAO du faisceau courant : réservations, jamais dossier de fabrication.

Modifie exclusivement SA08, ses références EQ_Route et leur registre. Les
corps, supports et sources fabricant sont lus sans sauvegarde. Exécution :
Python FreeCAD 1.1, --check pour vérifier les candidats sans sauver les natifs.
"""
from pathlib import Path
import argparse, hashlib, json, math, time
import FreeCAD as A
import Part
from etage_batterie_helpers import save_native,meta,color,link

ROOT = Path(__file__).resolve().parents[4]
MEC = ROOT / 'hardware/mecanique/cartographe'
VER = MEC / 'verification'
RECIPE = VER / 'routes_systeme_candidat_20261003.json'
PROOF = VER / 'controle_routes_systeme_courant.json'

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def relative(p): return str(Path(p).relative_to(ROOT)).replace('\\', '/')
def dump(p, data): p.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')

def rounded(points, desired):
    """Arcs tangents mesurés ; leur rayon peut être inférieur au rayon souhaité."""
    pts = [A.Vector(*p) for p in points]
    edges, radii, last = [], [], pts[0]
    for i in range(1, len(pts)-1):
        p = pts[i]; a = pts[i-1]-p; c = pts[i+1]-p
        la, lc = a.Length, c.Length; a.normalize(); c.normalize()
        angle = math.acos(max(-1, min(1, a.dot(c))))
        if angle < 1e-5: raise ValueError('Rebroussement')
        if abs(angle-math.pi) < 1e-5: continue
        t = min(desired/math.tan(angle/2), la*.44, lc*.44)
        radius = t*math.tan(angle/2); direction = a+c; direction.normalize()
        center = p+direction*(radius/math.sin(angle/2))
        start = p+a*t; end = p+c*t; radial = p-center; radial.normalize()
        mid = center+radial*radius
        if (start-last).Length > 1e-7: edges.append(Part.makeLine(last, start))
        edges.append(Part.Arc(start, mid, end).toShape()); last = end; radii.append(radius)
    if (pts[-1]-last).Length > 1e-7: edges.append(Part.makeLine(last, pts[-1]))
    wire = Part.Wire(edges)
    return wire, radii

def candidate_recipe():
    data = json.loads(RECIPE.read_text(encoding='utf-8'))
    paths = {
      'JETI_OUT_PM': [(46,-107,-6),(85,-107,-6),(85,-150,-6),(-165,-150,-6),(-165,-62,-6),(-144,-62,-15)],
      'PM_OUT_PDB': [(-84,-62,-6),(-84,-165,-6),(120,-165,-6),(120,-100,-20)],
      'PM_POWER1': [(-146,-78,-15),(-158,-78,-15),(-158,-45,-15),(-158,-45,-53),(-69,-20,-53)],
      'PM_POWER2': [(-146,-66,-15),(-158,-66,-15),(-158,-45,-15),(-158,-45,-53),(-69,-8,-53)],
      'PM_CAN1': [(-146,-54,-15),(-158,-54,-15),(-158,-45,-15),(-158,-45,-53),(-69,5,-53)],
      'PDB_CA01': [(120,-100,-20),(170,-100,-20),(170,-45,-82),(-85,-45,-82),(-85,24.5,-82),(-85,24.5,-68.6575),(-69,24.5,-68.6575)],
      'CA01_JETSON': [(-69,1.5,-68.695),(-85,1.5,-68.695),(-85,20,-50),(-69,20,-50)],
      'AIRY_TRONC': [(-45,-38,-162),(-78,-76,-161),(-103,-83,-115),(-85,-78,-79)],
      'AIRY_12V': [(-85,-78,-79),(-85,45,-82),(4.98,45,-82),(4.98,45,-70.37)],
      'AIRY_ETH': [(-85,-78,-79),(-93,-54,-54),(-69,-25,-50)],
      'AIRY_TEMPS': [(-85,-78,-79),(-85,-48,-82),(85,-48,-82),(85,-17,-82),(85,-17,-68.24),(69,-17,-68.24)],
      'CA01_UART_RF': [(-16,-46,-68.24),(-85,-46,-68.24),(-85,-31,-50),(-69,-31,-50)],
      'COAX_RF_1': [(-69,-19.5,-50),(-85,-19.5,-50),(-85,-48,-82),(-120,72,-65)],
      'COAX_RF_2': [(-69,-19.5,-50),(-85,-19.5,-50),(-85,-48,-82),(120,-48,-82),(120,-72,-65)],
      'USB3_CAMERA': [(69,10,-45),(115,10,-45),(145,52,-113),(145,10,-115),(111,10,-107)],
      'M8_CAMERA': [(41,-46,-68.92),(85,-46,-82),(145,-48,-110),(145,-15,-110),(111,-15,-108)],
      'GNSS_CAN2': [(-69,24,-50),(-90,45,-50),(-110,60,-50),(-110,60,185),(8,218,185)],
      'ORIN_PPS': [(69,-4,-68.24),(85,-4,-68.24),(85,25,-45),(69,25,-45)],
      'ORIN_GPRMC': [(69,5,-68.24),(85,5,-68.24),(85,13,-45),(69,13,-45)],
      'ORIN_REF3V3': [(27,-46,-68.24),(85,-46,-68.24),(85,1,-45),(69,1,-45)],
      'FCU_TRIGGER': [(17,-46,-68.24),(85,-46,-68.24),(85,-21,-50),(69,-21,-50)],
      'FCU_CAPTURE': [(69,16,-68.24),(85,16,-68.24),(85,32,-50),(69,32,-50)],
      'GNSS_PPS_GPRMC': [(2,-46,-68.24),(-110,-46,-82),(-110,60,-82),(-110,60,185),(6,218,185)],
    }
    for i, (sx, sy) in enumerate([(1,-1),(1,1),(-1,1),(-1,-1)], 1):
        paths['PDB_ESC_'+str(i)] = [(157,-140+i*18,-40),(180,-140+i*18,-40),(180,-140+i*18,85),(sx*200,sy*180,85)]
        paths['ESC_PHASES_'+str(i)] = [(sx*200,sy*180,85),(sx*250,sy*180,85),(sx*266,sy*225,85)]
        paths['FCU_ESC_'+str(i)] = [(69,sy*24,-50),(85,sy*45,-50),(sx*165,sy*45,-50),(sx*165,sy*110,-50),(sx*165,sy*110,85),(sx*200,sy*180,85)]
    paths['PDB_ESC_3']=[(157,-86,-40),(180,-86,-40),(180,-86,85),(180,80,85),(-180,80,85),(-200,180,85)]
    paths['PDB_ESC_4']=[(157,-68,-40),(180,-62,-40),(180,-62,110),(-200,-62,110),(-200,-180,85)]
    paths['FCU_ESC_4']=[(69,-24,-50),(85,-45,-50),(-125,-45,-50),(-125,-170,-50),(-125,-170,85),(-200,-180,85)]
    for row in data['routes']:
        if row['id'] not in paths: continue  # diagnostic remplacé ci-dessous, rejeu stable
        row['points_mm'] = [list(p) for p in paths[row['id']]]
        row['endpoints_oem_cotes'] = False
        row['statut'] = 'À valider'
        row['limite'] = ('Réservation extérieure aux corps courants, sections et points de terminaison candidats ; '
          'les interfaces OEM, prises accouplées, bridages et rayons fournisseur restent À valider. '
          'Les rayons réellement construits sont mesurés sans réduction silencieuse du critère.')
        row['terminaisons'] = 'Accès candidat, liaison physique courte entre accès et contact OEM non représentée.'
        if row['id'].startswith(('GNSS_',)):
            row['terminaisons'] += ' Récepteur GNSS historique au mât, absent du top courant : placement et port À valider.'
        if row['id'].startswith(('ESC_PHASES_', 'PDB_ESC_', 'FCU_ESC_')):
            row['terminaisons'] += ' ESC et moteur : ports inconnus, corridor déplacé hors volumes OEM ; aucune continuité matérielle démontrée.'
    existing = {r['id'] for r in data['routes']}
    for name, group, points, diameter, radius, wires in [
      ('TE5_SIGNAL_ISOLATEUR','DIAGNOSTIC-BMS-TTL',[(-235,-20,78),(-251,-20,78),(-251,-45,78),(-251,-45,-42),(-190,-45,-42),(-190,-55,-42)],4.5,23,5),
      ('ISOLATEUR_USB_JETSON','DIAGNOSTIC-BMS-USB',[(-140,-100,-42),(-120,-100,-42),(-85,-60,-42),(-85,-46,-46.28228),(7.035,-46,-46.28228)],5,25,None),
    ]:
        row = dict(id=name,groupe=group,wxx=['W40'] if wires else ['W41'],points_mm=[list(p) for p in points],diametre_enveloppe_mm=diameter,
          rayon_reservation_mm=radius,section_cuivre_par_fil_mm2=None,nombre_fils=wires,propriete_masse='Faisceau diagnostic ajouté, masse inconnue',
          longueur_coupe_mm=None,masse_lineique_g_m=None,endpoints_oem_cotes=False,statut='À valider',
          limite='Cinq signaux groupés hors TE sans affectation de cavité ; port Waveshare/USB Jetson réservé, géométrie fabricant et harnais À valider.'
          if wires else 'USB isolateur vers accès Jetson réservé, orientation des prises et câble OEM À valider.',
          terminaisons='Réservations de passage, aucun centre de contact ni prise physique inventé.')
        if wires: row['liaisons_reservees_non_connectees']=['W42']
        if name in existing:
            data['routes'][next(i for i,r in enumerate(data['routes']) if r['id']==name)] = row
        else: data['routes'].append(row)
    data.update(date='2026-10-05',statut='À valider',repere='mm, repère global assemblage courant, liens SA08 identité',
      configuration='Integration_Stack_Revue_20261003',recette=relative(__file__))
    data['ports_reserves'] = {
      'TE5_fixe':next(r for r in data['routes'] if r['id']=='TE5_SIGNAL_ISOLATEUR')['points_mm'][0],
      'isolateur_TTL':[-190,-55,-42], 'isolateur_USB':[-140,-100,-42],
      'Jetson_USB_acces':[7.035,-46,-46.28228], 'isolateur_volume_mm':[[-235,-140,-55],[-145,-60,-29]],
      'Jetson_double_USB_A_OEM_bbox_mm':[[-0.775,-39.35118,-55.52228],[14.845,-23.65213,-37.04228]],
      'Jetson_USB_zone_acces_mm':[[-1,-61,-55.5],[15,-43,-37]],
      'Jetson_USB_affectation':'Double USB-A SUBMODEL-USB30-2-AF_PART_US01-0_ASM ; zone accessible reservée, alvéole haute/basse et disponibilité fonctionnelle À valider. Le point représente la zone, pas un axe de prise.',
      'statut':'À valider', 'presence_CA01':'W42 NC : présence réservée au contrat, aucun conducteur connecté',
      'JETI_OUT_physique_mm':[[40,-115,-16.5],[40,-99,-16.5]],
      'JETI_OUT_point_regroupe_mm':[46,-107,-6],
      'ancrages_CA01_XY_mm':{'J103':[-49,22],'J104':[-47.9,4],'J201':[3,24],'J504':[59.4,-17],'J402':[-16,-36.4],
        'J502':[41,-34.5],'J503':[2,-36.4],'J505':[59.4,-4],'J506':[59.4,5],'J509':[27,-36.4],'J507':[17,-36.4],'J508':[59.4,16]},
      'CA01_sorties_enveloppes_natives_mm':{'J103':[-62,24.5,-68.6575],'J104':[-61.95,1.5,-68.695],
        'J201':[4.98,37.4,-70.37],'J504':[61.875,-17,-68.24],'J402':[-16,-38.875,-68.24],
        'J502':[41,-39.11,-68.92],'J503':[2,-38.875,-68.24],'J505':[61.875,-4,-68.24],
        'J506':[61.875,5,-68.24],'J509':[27,-38.875,-68.24],'J507':[17,-38.875,-68.24],'J508':[61.875,16,-68.24]},
      'CA01_reference':'Sorties calculées sur faces des enveloppes natives après transformation[x−63,−y−40,−z−64.4]. Accès décalés hors PCB : X±69 ou Y−46/+45. Pas centres qualifiés des contacts ; fiches accouplées absentes.',
    }
    data['limites'] = ['Routes de réservation, jamais longueurs de coupe ni autorisation de fabrication.',
      'Les raccordements courts entre réservations et contacts/prises OEM sont non modélisés et À valider.',
      'Les terminaisons GNSS/caméra/ESC/moteurs ne sont pas cotées et peuvent nécessiter une adaptation.',
      'Rayons désirés et réels distincts ; un rayon inférieur laisse la conformité ouverte.',
      'Aucun doublon TE puissance vers JETI : les deux cordons fixes restent dans SA02A.',
      'Routage statique ; bridages, tolérances, débattement capteurs, repli des bras, CEM et thermique non qualifiés.']
    return data

def geometry(row):
    wire, radii = rounded(row['points_mm'], row['rayon_reservation_mm'])
    assert all(r>row['diametre_enveloppe_mm']/2+1e-6 for r in radii),('Coude auto-intersectant',row['id'],radii)
    section = Part.Wire(Part.makeCircle(row['diametre_enveloppe_mm']/2, A.Vector(*row['points_mm'][0]),
       wire.Edges[0].tangentAt(wire.Edges[0].FirstParameter)))
    shape = wire.makePipeShell([section], True, True)
    assert shape.isValid() and len(shape.Solids)==1, row['id']
    shape.check(True)  # isValid seul ne détecte pas les auto-intersections BOP.
    return wire, section, shape, radii

def obstacles():
    top = A.openDocument(str(MEC/'assemblages/Integration_Stack_Revue_20261003.FCStd'))
    for d in A.listDocuments().values():
        for obj in d.Objects: obj.touch()
    for _ in range(2):
        for d in A.listDocuments().values(): d.recompute()
    result = []
    for o in top.IntegrationRevue.Group:
        if o.TypeId!='App::Link' or o.Name.startswith(('Faisceau', 'SA08')): continue
        # Châssis : pièces séparées pour éviter un booléen avec un immense composé.
        if o.Name.startswith('SA01'):
            for child in o.LinkedObject.Document.Objects:
                if child.TypeId=='App::Link' and hasattr(child,'Shape') and not child.Shape.isNull():
                    result.append((o.Name+'/'+child.Name, child.Shape.copy()))
        else: result.append((o.Name, o.Shape.copy()))
    # Volume nominal diagnostic même si SA07 n'est pas encore actualisé par le parent.
    result.append(('ReservationIsolateur90x80x26',Part.makeBox(90,80,26,A.Vector(-235,-140,-55))))
    return top, result

def check_shapes(data, shapes, obs):
    rows = []
    for row in data['routes']:
        wire, section, shape, radii = shapes[row['id']]
        hits = []
        for name, obstacle in obs:
            if not shape.BoundBox.intersect(obstacle.BoundBox): continue
            volume = shape.common(obstacle).Volume
            if volume > 1e-6: hits.append(dict(objet=name, volume_mm3=volume, classification='À résoudre'))
        rows.append(dict(id=row['id'],forme_valide=shape.isValid(),solides=len(shape.Solids),longueur_route_mm=wire.Length,
          rayons_mesures_mm=radii,rayon_souhaite_mm=row['rayon_reservation_mm'],
          rayon_souhaite_respecte=all(r>=row['rayon_reservation_mm']-1e-6 for r in radii),intersections=hits))
        print(json.dumps({'route':row['id'],'intersections':hits}),flush=True)
    return rows

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--check',action='store_true'); args = ap.parse_args()
    start = time.time(); executed_recipe_sha=sha(__file__);data = candidate_recipe(); shapes = {r['id']:geometry(r) for r in data['routes']}
    top, obs = obstacles()
    before = {relative(d.FileName):sha(d.FileName) for d in A.listDocuments().values() if d.FileName}
    rows = check_shapes(data, shapes, obs)
    clear_obstacles=not any(row['intersections'] for row in rows)
    dump(VER/'controle_candidats_faisceau_bms.json',dict(date='2026-10-05',recette_sha256=executed_recipe_sha,sources_lues_sha256=before,routes=rows,collisions_restantes=[r['id'] for r in rows if r['intersections']],finalisation_correcte=clear_obstacles,limite='Candidats contrôlés avant sauvegarde ; aucune preuve de persistance native'))
    if not args.check and clear_obstacles:
        harness_path = MEC/'sous_assemblages/SA08_Faisceau_Systeme_Candidat.FCStd'
        harness = next((d for d in A.listDocuments().values() if d.FileName and Path(d.FileName)==harness_path),None) or A.openDocument(str(harness_path)); root = harness.Reference
        for row in data['routes']:
            name = 'EQ_Route_'+row['id']+'_Systeme_Candidat'; path = MEC/'pieces/commerce'/(name+'.FCStd')
            dd = next((d for d in A.listDocuments().values() if d.FileName and Path(d.FileName)==path),None)
            dd = dd or (A.openDocument(str(path)) if path.exists() else A.newDocument(name))
            rr = dd.getObject('Reference') or dd.addObject('App::Part','Reference')
            pathobj = dd.getObject('CheminArrondi') or dd.addObject('Part::Feature','CheminArrondi')
            profile = dd.getObject('SectionEnvelope') or dd.addObject('Part::Feature','SectionEnvelope')
            sweep = dd.getObject('ReservationCordon') or dd.addObject('Part::Sweep','ReservationCordon')
            for obj in (pathobj,profile,sweep):
                if obj not in rr.Group: rr.addObject(obj)
            wire, section, shape, radii = shapes[row['id']]
            pathobj.Shape=wire; profile.Shape=section
            if 'PointsEtude' not in pathobj.PropertiesList: pathobj.addProperty('App::PropertyVectorList','PointsEtude')
            pathobj.PointsEtude=[A.Vector(*p) for p in row['points_mm']]
            sweep.Sections=[profile]; sweep.Spine=(pathobj,[]); sweep.Solid=True; sweep.Frenet=True
            pathobj.Visibility=False; profile.Visibility=False; sweep.Visibility=True
            meta(rr,'ObjetFinal',sweep.Name);meta(rr,'Etat','À valider');meta(rr,'RealisationCAO','Implémenté')
            meta(rr,'GroupeFaisceau',row['groupe']);meta(rr,'Liaisons',','.join(row['wxx']));meta(rr,'Limite',row['limite'])
            meta(rr,'Recette',relative(__file__));meta(rr,'Terminaisons',row['terminaisons'])
            rgb=(.88,.15,.12) if row['id'].startswith(('JETI','PM_OUT','PDB_ESC','ESC_PHASES')) else (.95,.65,.10)
            if row['id'] in ['TE5_SIGNAL_ISOLATEUR','ISOLATEUR_USB_JETSON']: rgb=(.75,.2,.9)
            color(sweep,rgb); sweep.touch(); dd.recompute(); assert sweep.Shape.isValid() and len(sweep.Shape.Solids)==1
            sweep.Shape.check(True)
            native_difference=sweep.Shape.cut(shape).Volume+shape.cut(sweep.Shape).Volume
            assert native_difference<1e-5,('Balayage différent du candidat',row['id'],native_difference)
            save_native(dd,path if not dd.FileName else None)
            occurrence=harness.getObject(row['id']) or link(harness,root,row['id'],rr)
            occurrence.setLink(rr);occurrence.LinkTransform=False;occurrence.LinkPlacement=A.Placement();occurrence.ViewObject.OverrideMaterial=False
        access=harness.getObject('ReservationAccesUSBJetson') or harness.addObject('Part::Box','ReservationAccesUSBJetson')
        if access not in root.Group:root.addObject(access)
        access.Length=16;access.Width=18;access.Height=18.5;access.Placement.Base=A.Vector(-1,-61,-55.5)
        color(access,(.15,.5,.95));access.ViewObject.Transparency=75
        meta(access,'Etat','À valider');meta(access,'Limite',data['ports_reserves']['Jetson_USB_affectation'])
        meta(root,'Limite','Faisceau courant de réservation ; terminaisons OEM, rayons, bridages et qualification À valider.')
        save_native(harness);dump(RECIPE,data)
    after={relative(d.FileName):sha(d.FileName) for d in A.listDocuments().values() if d.FileName}
    preserved={p:h for p,h in before.items() if '/EQ_Route_' not in p and not p.endswith('/SA08_Faisceau_Systeme_Candidat.FCStd')}
    changed_external=[p for p,h in preserved.items() if after[p]!=h]
    finalisation_correcte=clear_obstacles and not changed_external
    evidence=dict(date='2026-10-05',statut='À valider',finalisation_correcte=finalisation_correcte,
       mode='candidats sans sauvegarde' if args.check or not clear_obstacles else 'natifs enregistrés',
       recette_sha256=executed_recipe_sha,version_FreeCAD=A.Version(),ports_reserves=data['ports_reserves'],routes=rows,
       sources_lues_sha256=preserved,modifications_externes_detectees=changed_external,
       sources_stables_pendant_controle=not changed_external,
       fichiers_courants_sha256={p:h for p,h in after.items() if '/EQ_Route_' in p or p.endswith('/SA08_Faisceau_Systeme_Candidat.FCStd')},
       collisions_restantes=[r['id'] for r in rows if r['intersections']],rayons_a_valider=[r['id'] for r in rows if not r['rayon_souhaite_respecte']],
       essais_non_executes=['Terminaisons et interfaces physiques','Course continue cassette avec faisceau diagnostic','Vibration, traction, thermique, CEM','Repli bras et débattement capteurs'],
       limites=data['limites'],elapsed_seconds=time.time()-start)
    dump(PROOF,evidence)
    print(json.dumps({'finalisation_correcte':finalisation_correcte,'collisions':evidence['collisions_restantes'],'elapsed_seconds':evidence['elapsed_seconds']}),flush=True)
    if not finalisation_correcte: raise RuntimeError('Preuve calculée mais obstacles présents ou sources modifiées ; relire le JSON de contrôle.')

if __name__=='__main__': main()
