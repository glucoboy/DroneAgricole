"""Lecture FreeCAD et scénarios interplateaux en mémoire ; aucun FCStd sauvegardé.

Exécuter avec le Python FreeCAD 1.1. Les boîtes de batterie, rehausses et
extensions de colonnes sont des hypothèses géométriques, pas des pièces conçues.
"""
from pathlib import Path
import hashlib
import json
import math
import sys
import argparse

sys.path.insert(0, 'C:/Program Files/FreeCAD 1.1/bin')
import FreeCAD as A
import Part

ROOT = Path(__file__).resolve().parents[4]
MEC = ROOT / 'hardware/mecanique/cartographe'
OUT = MEC / 'verification/logement_interplateaux_20261002.json'
SEUIL = 1e-6


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bounds(s):
    b = s.BoundBox
    return [b.XMin, b.XMax, b.YMin, b.YMax, b.ZMin, b.ZMax]


def overlaps(a, b):
    aa, bb = bounds(a), bounds(b)
    return all(aa[2*i] <= bb[2*i+1] + 1e-7 and bb[2*i] <= aa[2*i+1] + 1e-7 for i in range(3))


def intersections(s, objects):
    answer = []
    for name, shape in objects:
        if not overlaps(s, shape):
            continue
        common = s.common(shape)
        if common.Volume > SEUIL:
            answer.append({'obstacle': name, 'volume_commun_mm3': common.Volume,
                           'bbox_intersection_mm': bounds(common)})
    return answer


def describe(obj, shape):
    return {'objet': obj.Name, 'label': obj.Label, 'bbox_mm': bounds(shape)}


def circle_groups(shape):
    data = {}
    for edge in shape.Edges:
        c = edge.Curve
        if type(c).__name__ != 'Circle':
            continue
        key = tuple(round(v, 6) for v in [c.Center.x,c.Center.y,c.Center.z,c.Radius,c.Axis.x,c.Axis.y,c.Axis.z])
        data[key] = data.get(key, 0) + edge.Length
    return [{'centre_mm': list(k[:3]), 'rayon_mm': k[3], 'axe': list(k[4:]),
             'fraction_circonference': length / (2*math.pi*k[3])} for k,length in data.items()]


def add_rotor_envelopes(result):
    radius = result['helices']['rayon_mm']
    discs = [(f'Disque_hypothetique_{i}',Part.makeCylinder(radius,.1,A.Vector(*motor['axe_XY_mm'],71.45)))
             for i,motor in enumerate(result['moteurs_OEM'],1)]
    packs = {s['batterie']:s['dimensions_mm'] for s in result['scenarios_en_memoire']}
    checks = []
    for label,dimensions in packs.items():
        length,width,height=dimensions
        for offset in [0,20,50,100,200]:
            s=Part.makeBox(length,width,height,A.Vector(offset-length/2,-width/2,40))
            checks.append({'batterie':label,'translation_X_mm':offset,
                           'collisions_disques_hypothetiques_BRep':intersections(s,discs)})
    result['helices']['enveloppes_BRep_hypothetiques']={
        'plan_Z_candidat_mm':71.5,'epaisseur_numerique_mm':.1,'rayon_mm':radius,
        'checks':checks,'limite':'PlanZ71,5 hypothétique, jamais assimilé au plan réel ; inclinaison, flexion, tolérances, guides, mains et câbles non modélisés.'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rotors-only',action='store_true',help='Compléter une preuve existante avec les disques hypothétiques sans refaire les scénarios OEM')
    args=parser.parse_args()
    if args.rotors_only:
        result=json.loads(OUT.read_text(encoding='utf-8'))
        if not all(sha(ROOT/p)==h for p,h in result['sources_CAO_sha256_apres'].items()):
            raise RuntimeError('CAO modifiée depuis la preuve initiale : reprendre le contrôle complet')
        result['protocole']['script_sha256_audit_initial']=result['protocole']['script_sha256']
        result['protocole']['script_sha256']=sha(Path(__file__))
        result['protocole']['complement_disques_apres_audit_initial']=True
        add_rotor_envelopes(result)
        OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print('Complément disques hypothétiques terminé ; sourcesCAO inchangées')
        return 0
    oem_path = MEC / 'pieces/commerce/EQ_Chassis_X650.FCStd'
    current_path = MEC / 'sous_assemblages/SA03_Avionique.FCStd'
    holy_path = MEC / 'sous_assemblages/SA03_CA01_Holybro_candidat.FCStd'
    oem = A.openDocument(str(oem_path))
    current = A.openDocument(str(current_path))
    holy = A.openDocument(str(holy_path))
    for doc in A.listDocuments().values():
        doc.recompute()
    hashes_before = {Path(d.FileName): sha(Path(d.FileName)) for d in A.listDocuments().values() if d.FileName}
    errors = [{'document':d.Name,'objet':o.Name,'etat':list(o.State)}
              for d in A.listDocuments().values() for o in d.Objects if 'Invalid' in o.State]
    exclusions = json.loads((MEC/'verification/avionique_empilee_20260916.json').read_text(encoding='utf-8'))['protocole']['exclusions_chassis']
    shapes = {}
    for obj in oem.Objects:
        if obj.TypeId == 'Part::Feature' and hasattr(obj,'Shape') and not obj.Shape.isNull():
            shape = obj.Shape.copy()
            shape.Placement = obj.getGlobalPlacement()
            shapes[obj.Name] = shape
    active_oem = [(name,s) for name,s in shapes.items() if name not in exclusions]
    upper = shapes['Part__Feature311']
    lower = shapes['Part__Feature309']
    bay = bounds(upper)[4] - bounds(lower)[5]
    plates = [describe(oem.getObject(name),shapes[name]) for name in
              ['Part__Feature310','Part__Feature309','Part__Feature311']]
    columns = [describe(oem.getObject(f'Part__Feature{i:03}'),shapes[f'Part__Feature{i:03}']) for i in range(84,88)]
    upper_fixings = [describe(oem.getObject(f'Part__Feature{i:03}'),shapes[f'Part__Feature{i:03}']) for i in range(92,96)]
    lower_fixings = [describe(oem.getObject(f'Part__Feature{i:03}'),shapes[f'Part__Feature{i:03}']) for i in range(104,108)]
    arms = [describe(oem.getObject(f'Part__Feature{i:03}'),shapes[f'Part__Feature{i:03}']) for i in [181,213,245,277,187,219,251,283,188,220,252,284]]
    motors = []
    for i in [184,216,248,280]:
        name = f'Part__Feature{i:03}'
        circles = circle_groups(shapes[name])
        rotor = next(c for c in circles if c['rayon_mm'] > 20 and abs(c['axe'][2]) > .999 and c['centre_mm'][2] > 50)
        entry = describe(oem.getObject(name),shapes[name])
        entry['axe_XY_mm'] = rotor['centre_mm'][:2]
        entry['cercles_coaxiaux_haut_moteur'] = [c for c in circles if
             abs(c['centre_mm'][0]-rotor['centre_mm'][0]) < 1e-4 and
             abs(c['centre_mm'][1]-rotor['centre_mm'][1]) < 1e-4 and c['centre_mm'][2] > 60]
        motors.append(entry)
    avionics, avionics_info = [], []
    holy_info = []
    for doc, destination, info in [(current,avionics,avionics_info),(holy,[],holy_info)]:
        for obj in doc.Objects:
            if obj.TypeId == 'App::Link' and hasattr(obj,'Shape') and not obj.Shape.isNull():
                destination.append((obj.Name,obj.Shape.copy()))
                entry = describe(obj,obj.Shape)
                entry['fichier_source'] = str(Path(obj.LinkedObject.Document.FileName).relative_to(ROOT)).replace('\\','/')
                info.append(entry)

    packs = {'16Ah_nominal':[192,76,65], '16Ah_max_fabricant':[197,78,67],
             '20Ah_nominal':[193,76,58], '20Ah_max_hypothese':[198,78,60]}
    scenarios = []
    projection_rotors = []
    radius = 190.5
    for label, dimensions in packs.items():
        length, width, height = dimensions
        pack = Part.makeBox(length,width,height,A.Vector(-length/2,-width/2,40))
        print('PACK',label,flush=True)
        occupied = intersections(pack,avionics)
        for raise_mm in [0,20,30]:
            moved_upper = upper.copy()
            moved_upper.translate(A.Vector(0,0,raise_mm))
            obstacles = [(n,moved_upper if n=='Part__Feature311' else s) for n,s in active_oem]
            # Extension cylindrique seulement illustrative, aux axes existants.
            columns_envelopes = [(f'Extension_colonne_{x}_{y}',Part.makeCylinder(2.5,raise_mm,A.Vector(x,y,83)))
                                 for x in [-52,52] for y in [-52,52]] if raise_mm else []
            positions = []
            for offset in [0,20,50,100,200]:
                s = pack.copy()
                s.translate(A.Vector(offset,0,0))
                positions.append({'translation_X_mm':offset,
                                  'collisions_OEM':intersections(s,obstacles),
                                  'collisions_extensions_illustratives':intersections(s,columns_envelopes)})
            scenarios.append({'batterie':label,'dimensions_mm':dimensions,'base_Z_mm':40,
                              'rehausse_plateau_mm':raise_mm,'dessous_plateau_Z_mm':83+raise_mm,
                              'jeu_vertical_pack_nu_mm':83+raise_mm-(40+height),
                              'collisions_avionique_actuelle_position_0':occupied,
                              'condition': 'SA03 actuelle à reloger ; variante énergie supérieure actuelle remplacée, pas cumulée',
                              'positions_extraction_X':positions,
                              'extensions_colonnes':{'nombre':len(columns_envelopes),'rayon_mm':2.5,
                                                    'longueur_nominale_totale_candidate_mm':50+raise_mm,
                                                    'limite':'Cylindres fictifs uniquement ; aucune vis, filetage ou nouvelle fixation conçue. Vis supérieures actuelles non déplacées.'}})
        for offset in [0,20,50,100,200]:
            xmin,xmax=offset-length/2,offset+length/2
            ymin,ymax=-width/2,width/2
            rotor_gaps=[]
            for motor in motors:
                x,y=motor['axe_XY_mm']
                dx=max(xmin-x,x-xmax,0)
                dy=max(ymin-y,y-ymax,0)
                rotor_gaps.append(math.hypot(dx,dy)-radius)
            projection_rotors.append({'batterie':label,'translation_X_mm':offset,
                                      'garde_min_projection_disque_15_pouces_mm':min(rotor_gaps),
                                      'limite':'ProjectionXY théorique, aucune mesure du planZ hélice ni marge de déflexion/tolérance.'})
    hashes_after = {p:sha(p) for p in hashes_before}
    result={'date':'2026-10-02','statut':'À valider',
            'protocole':{'FreeCAD':list(A.Version()),'script_sha256':sha(Path(__file__)),
                         'methode':'Processus séparé, formes copiées en placement global, hypothèses créées seulement en mémoire, aucun save',
                         'intersections':'Boîtes puis BRep.common, aucune distance agrégée',
                         'seuil_volume_mm3':SEUIL,'exclusions_OEM_historiques':exclusions},
            'sources_CAO_sha256_avant':{str(p.relative_to(ROOT)).replace('\\','/'):h for p,h in hashes_before.items()},
            'sources_CAO_sha256_apres':{str(p.relative_to(ROOT)).replace('\\','/'):h for p,h in hashes_after.items()},
            'CAO_inchangee':hashes_before==hashes_after,'erreurs_recalcul':errors,
            'plateaux_OEM':plates,'intervalle_cible_libre_face_a_face_mm':bay,
            'autre_intervalle_avionique_face_a_face_mm':29,
            'colonnes_superieures':columns,'vis_superieures_existantes':upper_fixings,'vis_inferieures_existantes':lower_fixings,
            'ancrages_plateau_superieur':{'axes_XY_mm':[[x,y]for x in[-52,52]for y in[-52,52]],
                                         'axe':'Z','cercles_feature311_aux_ancrages':[c for c in circle_groups(upper) if
                                         abs(abs(c['centre_mm'][0])-52)<1e-4 and abs(abs(c['centre_mm'][1])-52)<1e-4]},
            'passage_colonnes':{'entraxes_mm':104,'diametre_enveloppe_mm':5,'largeur_interne_Y_mm':99,
                                'garde_pack_max_Y78_mm_par_cote':10.5,
                                'limite':'GrandaxeX dépassant les colonnes autorisé géométriquement par largeurY ; soutien des porte-à-faux non dimensionné'},
            'bras_OEM':arms,'moteurs_OEM':motors,
            'helices':{'representees_dans_source_OEM':False,'plan_Z_reel_mm':None,
                        'references_officielles':['https://holybro.com/products/x650-development-kit','https://www.gemfanhobby.com/t-type-carbon-fiber-props.html'],
                        'hypothese_projection_diametre_mm':381,'rayon_mm':radius,
                        'origine_hypothese':'Gemfan1555 du kit, modèle de disque15pouces ; dimensions et profil réels à confirmer',
                        'projection_pack_par_positions':projection_rotors},
            'avionique_active':avionics_info,'pile_Holybro_CA01_candidate_repere_local':holy_info,
            'pile_candidate_limite':'Variante non intégrée au drone ; placements locaux non assimilés à un nouvel emplacement dans le bay',
            'scenarios_en_memoire':scenarios,
            'limites':['Ni implantation réelle ni rehausse de CAO effectuée.',
                       'La rehausse du seul plateau ne libère pas le volume actuellement occupé par Pixhawk et son support.',
                       'Nouvelles colonnes, vis, rondelles, écrous, rigidification et fixation des rails non conçus ni qualifiés.',
                       'Disques hélices hypothétiques en projectionXY ; planZ, conicité, flexion et mains/câbles non vérifiés.',
                       'Extraction échantillonnée uniquement ; aucune qualification de mouvement continu ou de verrouillage.',
                       'Données max20Ah tolérancées hypothétiques ; max16Ah selon dimensions constructeur.',
                       'Configuration supérieure énergie actuellement présente non cumulée avec cette hypothèse de remplacement.']}
    add_rotor_envelopes(result)
    OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'preuve':str(OUT),'scenarios':len(scenarios),'CAO_inchangee':result['CAO_inchangee'],'erreurs':len(errors)}),flush=True)
    for d in list(A.listDocuments().values()):
        A.closeDocument(d.Name)
    return 0 if result['CAO_inchangee'] and not errors else 1


if __name__=='__main__':
    raise SystemExit(main())
