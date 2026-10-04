"""Infrastructure de bilan conditionnel, sans modification des documents CAO."""
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parents[4]
VER = ROOT / 'hardware/mecanique/cartographe/verification'

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def read(name):
    return json.loads((VER / name).read_text(encoding='utf-8'))

inventory = read('inventaire_systeme_20261003.json')
volumes = read('bilan_masse_volumes_20261002.json')
budget = read('bilan_masse_systeme_candidat_20261003.json')
chassis = 'hardware/mecanique/cartographe/pieces/commerce/EQ_Chassis_X650.FCStd'
assert sha(ROOT / chassis) == inventory['sources_sha256'][chassis]
rows = {o['objet']: o for o in inventory['occurrences']
        if o['reference'] == 'EQ_Chassis_X650'}
families = [
    ('ferrures', [146, 148], 'aluminium hypothétique', 2.7),
    ('tube', [147], 'composite carbone hypothétique', 1.6),
    ('vis_ecrous', [149, 150, 152, 153], 'acier hypothétique', 7.85),
    ('raccord_SMA', [151, 155, 156], 'laiton hypothétique', 8.5),
    ('EVA', [154], 'mousse hypothétique', 0.1),
]
parts = []
for name, numbers, material, density in families:
    volume = sum(rows[f'Part__Feature{i}']['volume_unitaire_mm3'] for i in numbers)
    parts.append(dict(famille=name, objets=[f'Part__Feature{i}' for i in numbers],
                      volume_mm3=volume, matiere_hypothese=material,
                      densite_hypothese_g_cm3=density, masse_provision_g=volume / 1000 * density))
arm = sum(p['masse_provision_g'] for p in parts)
arm_polymer = arm - parts[0]['volume_mm3'] / 1000 * (2.7 - 1.25)
printed = []
for row in volumes['references_actives_non_metalliques']:
    if row['reference'].startswith(('P07_', 'P08_', 'P09_')):
        p = ROOT / 'hardware/mecanique/cartographe' / row['fichier']
        assert sha(p) == row['sha256_fcstd']
        printed.append(row)
assert len(printed) == 3
printed_mass = sum(p['masse_pleine_hypothese_g'] for p in printed)
gross = arm + printed_mass
historical = budget['budget_historique_plus_cuivre_nominal_kg']
out = {
    'date': '2026-10-04', 'statut': 'À valider',
    'controle': 'T-CARTO-GNSS-MAS-01', 'besoin': 'MEC-MAS-001',
    'perimetre': 'Calcul conditionnel sur volumes CAO déjà vérifiés ; aucun placement ou natif modifié.',
    'plateau_radio_hypothese': 'Bras OEM opposé -Y conservé, interprétation non confirmée par utilisateur.',
    'bras_retire': 'OEM +Y Part__Feature146–156, actuellement sous interface antenne P09.',
    'bras_conserve': 'OEM -Y Part__Feature157–167 ; aucun crédit de masse pour ce bras.',
    'detail_bras': parts, 'bras_alu_carbone_g': arm, 'bras_ferrures_polymere_g': arm_polymer,
    'supports_RTK_historiques': printed,
    'supports_RTK_historiques_g': printed_mass,
    'retrait_brut_historique_tous_supports_alu_g': gross,
    'retrait_brut_historique_tous_supports_polymere_g': arm_polymer + printed_mass,
    'budget_historique_partiel_avant_kg': historical,
    'budget_historique_partiel_apres_retrait_alu_kg': [m - gross / 1000 for m in historical],
    'budget_historique_partiel_apres_retrait_polymere_kg': [m - (arm_polymer + printed_mass) / 1000 for m in historical],
    'formule_cible': 'M_apres = M_avant_cible - M_bras_OEM + M_nouveaux_supports_et_coax - M_supports_cible_effectivement_supprimes + delta_autres_cables',
    'regle_cible': 'P07–P09 absents de la maquette Helical candidate : aucun second crédit de 39,711 g sur cette maquette. Le budget historique contient encore ces supports.',
    'masse_totale_cible_kg': None, 'gain_net_cible_g': None,
    'masses_nouveaux_coax_supports_g': None,
    'GNSS': {'variante': 'H-RTK F9P DroneCAN Helical STM32G4 candidat',
             'masse_groupe_publiee_g': 58,
             'masse_separee_recepteur_g': None, 'masse_separee_antenne_g': None,
             'montage': 'Antenne supérieure séparée par SMA, récepteur inférieur ; compas reste dans récepteur.'},
    'radio': {'module': 'RP4TD conservé sur CA01', 'antennes_deportees': 2,
              'interface': 'U.FL ; distincte du SMA GNSS', 'gain_par_deplacement_seul_g': 0},
    'sources_primaires': [
        'https://docs.holybro.com/gps-and-rtk-system/f9p-h-rtk-series/dronecan-f9p/specification',
        'https://docs.holybro.com/gps-and-rtk-system/f9p-h-rtk-series/dronecan-f9p/overview',
        'https://www.radiomasterrc.com/products/rp4td-expresslrs-2-4ghz-diversity-receiver',
        'https://docs.px4.io/main/en/gps_compass/'],
    'limites': [
        'Densités et matériaux de bras hypothétiques ; alternatives non assimilables à des bornes physiques garanties.',
        'Conserver ou réutiliser P07/P08/P09 impose de déduire uniquement les pièces réellement retirées.',
        'Les 41,1 g supposent le retrait du bras complet avec raccord SMA, vis et EVA ; tout accessoire réutilisé reste compté embarqué.',
        'Les sous-totaux historiques ne réconcilient pas le kit OEM, la nouvelle stack, PM08/PDB, le faisceau complet et les autres postes ouverts.',
        'Nouveau coaxial GNSS et supports antenne/récepteur/radio non définis ; masses inconnues, non supposées nulles.',
        'Aucune qualification RF, magnétique, mécanique, centrage, thermique, montage ou vol.'],
    'sources_sha256': {str(p.relative_to(ROOT)).replace('\\', '/'): sha(p)
                       for p in [VER / 'inventaire_systeme_20261003.json',
                                 VER / 'bilan_masse_volumes_20261002.json',
                                 VER / 'bilan_masse_systeme_candidat_20261003.json',
                                 ROOT / chassis, Path(__file__).resolve()]},
    'sources_natives_inchangees': True,
}
target = VER / 'scenario_gnss_plateaux_20261004.json'
target.write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
assert json.loads(target.read_text(encoding='utf-8')) == out
print(json.dumps({k: out[k] for k in ['bras_alu_carbone_g', 'bras_ferrures_polymere_g',
                 'supports_RTK_historiques_g', 'retrait_brut_historique_tous_supports_alu_g',
                 'budget_historique_partiel_apres_retrait_alu_kg', 'masse_totale_cible_kg']}, ensure_ascii=False))
