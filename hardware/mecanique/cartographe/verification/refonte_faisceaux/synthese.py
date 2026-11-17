"""Consolide les résultats de variantes sans remplacer les contrôles natifs."""
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
RUN = ROOT / '.runtime/refonte-faisceaux'


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    variants = HERE / 'variantes.json'
    configs = load(variants)['candidats']
    install = load(HERE / 'installation.json')
    graph = load(HERE / 'graphe_physique.json')
    inventory = load(HERE / 'inventaire.json')
    route_data = {r['id']:r for r in load(ROOT/'hardware/mecanique/cartographe_faisceaux_refonte/verification/routes_prototype.json')['routes']}
    trials = []
    for config in configs:
        report = RUN/(config['id']+'.json')
        if not report.exists():
            trials.append({'parametres':config,'etat':'not_executed'})
            continue
        result = load(report)
        if result['parametres']!=config or not result['finalized']:
            raise ValueError('Preuve de variante non raccordée : '+config['id'])
        result['sha256_preuve_brute'] = sha(report)
        trials.append(result)
    sleeves = []
    for sleeve in graph['gaines']:
        a,b = sleeve['axes_bords_mm']
        span = math.dist(a,b)
        r,t = sleeve['rayon_interieur_mm'],sleeve['paroi_mm']
        area = math.pi*r*r + 2*r*span
        occupied = sum(math.pi*(route_data[cid]['diametre_mm']/2)**2 for cid in sleeve['membres'])
        sleeves.append({'occurrence':sleeve['occurrence'],'membres':sleeve['membres'],
                        'diametres_cables_mm':{cid:route_data[cid]['diametre_mm'] for cid in sleeve['membres']},
                        'longueur_mm':sleeve['longueur_mm'],'largeur_interieure_mm':span+2*r,
                        'hauteur_interieure_mm':2*r,'largeur_exterieure_mm':span+2*(r+t),
                        'hauteur_exterieure_mm':2*(r+t),'section_libre_mm2':area-occupied,
                        'taux_section_occupee':occupied/area,'masse_g':None,
                        'classe':'CALCULÉE sur enveloppe CAO candidate, tissage et passage des prises non évalués'})
    stage = ROOT/'hardware/mecanique/cartographe_faisceaux_refonte/experiment.json'
    sources = {name:sha(HERE/name) for name in ['installation.json','graphe_physique.json','architecture.json','inventaire.json','variantes.json']}
    sources['copie/experiment.json'] = sha(stage)
    report = {'schema':'cartographe.refonte-variantes.v1','finalized':True,
              'sources_sha256':sources,'essais':trials,'gaines_selectionnees':sleeves,
              'couverture':inventory['counts'],
              'comparaison':{'axes': [len(graph['routes'])]*2,
                             'gaines_communes_ajoutees_au_cordon_oem_Airy':[1,len(sleeves)],
                             'longueur_gaines_communes_mm':[80,sum(s['longueur_mm'] for s in sleeves)],
                             'nombre_axes_traversant_gaines_ajoutees_au_cordon_Airy':[2,len({m for s in sleeves for m in s['membres']})],
                             'longueur_axes_mm':install['comparaison_longueur_mm'],
                             'masse_complete_g':[None,None],
                             'coupes_guides':install['guides_modifies'],
                             'supports_existants_de_bras':[12,12]},
              'design_decisions':[
                  {'id':'D-MAIN','selection':'MAIN_4_RELIEF_L8','alternatives':['MAIN_4_RELIEF_L12','MAIN_4_RELIEF_L7','etude_corridors_variante_main_paire.json'],
                   'motif':'Longueur partagée vérifiable avec une seule branche retouchée, 12 mm de câble de moins que la variante de déplacement double, stations MAIN amont conservées.',
                   'reserve':'Serrage et tenue du guide et de la gaine courte, CEM et défaillance commune.'},
                  {'id':'D-F38','selection':'F38_RELIEF_Xm40_65','alternatives':['F38_Xm40_65','F38_Xm54_85','baseline 80 mm'],
                   'motif':'Le passage local de P73 rend utilisables 25 mm de protection supplémentaires sur un aller-retour déjà commun.',
                   'reserve':'Montabilité et résistance résiduelle, échauffement et tenue sous collier.'},
                  {'id':'D-NTC','selection':'NTC_Y35_44','alternatives':['fenêtres 6 et 10 mm','absence de gaine'],
                   'motif':'La fenêtre 9 mm passe avec une meilleure marge à la structure que la fenêtre 10 mm.',
                   'reserve':'Fourniture et anti-glissement de la protection courte, accès des deux sondes.'},
                  {'id':'D-NORD','selection':'SIGNAL_NORD_RELIEF_L30','alternatives':['SIGNAL_NORD_L18','SIGNAL_NORD_L30','SIGNAL_EST_L24'],
                   'motif':'Une gaine pour PPS et la référence 3,3 V avec leurs retours. Le PWM garde une autre enveloppe.',
                   'reserve':'Vérifier CEM, référence de retour, raccordement et extraction du module.'},
                  {'id':'D-SEPARATION','selection':'architecture.json','alternatives':['gaine GNSS 9 mm','gaine POWER1/POWER2'],
                   'motif':'Maintenir les cordons GNSS séparés pour un gain mineur et conserver les deux alimentations de vol distinctes.',
                   'reserve':'La proximité de leurs corridors doit encore être examinée contre les défauts communs.'}]}
    (HERE/'validation_variantes.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')


if __name__=='__main__':
    main()
