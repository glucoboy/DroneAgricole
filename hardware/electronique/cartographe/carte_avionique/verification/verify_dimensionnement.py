"""Recette analytique CA01 ; aucune simulation ni qualification matérielle."""
import hashlib
import itertools
import json
import math
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
CARD = HERE.parent
data = json.loads((CARD / 'dimensionnement.json').read_text(encoding='utf-8-sig'))
checks = []

def check(name, computed, declared, tolerance=1e-8):
    ok = math.isclose(computed, declared, rel_tol=tolerance, abs_tol=1e-18)
    checks.append(dict(id=name, computed=computed, declared=declared, passed=ok))

def margin(name, available, required):
    checks.append(dict(id=name, available=available, required=required,
                       passed=available >= required))

for rail in data['lm76003']:
    v = 12 if rail['rail'] == '12V_LIDAR' else 5
    l, c = rail['l_nominal_h'], rail['cout_nominal_f']
    corners = []
    for vin, f, factor in itertools.product(rail['vin_range_v'], [440000, 560000], [.8, 1.2]):
        di = v * (1-v/vin) / (l*factor*f)
        r = di / rail['load_design_a']
        dp = 1-v/vin
        cmin = rail['load_design_a']/(f*r*.05*v) * ((r*r/12)*(1+dp)+dp*(1+r))
        esr = dp/(f*c*1.2)*(1/r+.5)
        corners.append((di, cmin, esr))
    prefix = rail['rail']
    check(prefix+'_delta_i', max(x[0] for x in corners), rail['ripple_max_a'])
    check(prefix+'_i_peak', rail['load_design_a']+max(x[0] for x in corners)/2, rail['peak_max_a'])
    check(prefix+'_cout_TI_eq23', max(x[1] for x in corners), rail['cout_min_for_5pct_step_max_f'])
    check(prefix+'_esr_TI_eq24', min(x[2] for x in corners), rail['esrmax_allowed_min_ohm'])
    rt, rb = rail['feedback_top_ohm'], rail['feedback_bottom_ohm']
    check(prefix+'_vout', 1.006*(1+rt/rb), rail['vout_nominal_v'])
    fx = 15.46/(v*c)
    cff = 1/(2*math.pi*fx*math.sqrt(rt*(rt*rb/(rt+rb))))
    check(prefix+'_cff_TI_eq25_26', cff, rail['cff_estimated_f'])
    margin(prefix+'_cout_margin', c*(1-rail['cout_tolerance']), max(x[1] for x in corners))
    margin(prefix+'_esr_margin', min(x[2] for x in corners), rail['cout_esrmax_ohm'])
    margin(prefix+'_limite_courant', rail['current_limit_hs_min_a'],rail['load_design_a']+max(x[0] for x in corners)/2)

entry = data['entry_compute']
assumptions = entry['assumptions']
check('capacites_total_w',sum(assumptions['rail_capacities_w']),assumptions['simultaneous_total_w'])
check('budget_entree_a',assumptions['simultaneous_total_w']/(18*assumptions['efficiency_for_input_budget']),assumptions['total_input_current_at_18v_a'])
buck=entry['compute_buck']
check('compute_vout',buck['feedback_vfb_v']*(1+buck['feedback_ohm'][0]/buck['feedback_ohm'][1]),buck['vout_typ_v'])
check('compute_delta_i',12*(1-12/25.2)/(6.8e-6*buck['frequency_hz']),entry['ripple']['delta_i_nominal_25_2_a'])
sync=data['synchronisation']
ldo=sync['rail_3v3']
check('ldo_dissipation',(ldo['vin_max_v']-ldo['vout_min_v'])*ldo['load_budget_a'],ldo['power_w'])
check('ldo_estimation_thermique_TI',ldo['power_w']*ldo['theta_ja_c_w'],ldo['rise_estimate_c'])
check('trigger_gate_peak',3.3/sync['trigger']['gate_series_ohm'],sync['trigger']['gate_peak_3v3_a'])
check('trigger_vds',sync['trigger']['line1_max_current_a']*sync['trigger']['rds_max_1v5_25c_ohm'],sync['trigger']['vds_calc_v'])
check('fusible_sync_chute',sync['f501']['load_budget_a']*sync['f501']['cold_resistance_typ_ohm'],sync['f501']['drop_nominal_v'])

# Marges du prototype de temps : conditions et bornes candidates explicites.
# Le seuil Schmitt 3.3 V et les niveaux Holybro exacts restent à mesurer.
t=sync['time_design']; tol=t['resistor_tolerance_fraction']
rs=t['input_series_ohm']*(1+tol)
rpmin=t['input_pulldown_ohm']*(1-tol)
rpmax=t['input_pulldown_ohm']*(1+tol)
high=(t['gnss_voh_min_assumed_v']-rs*t['schmitt_input_leak_max_a'])/(1+rs/rpmin)
low=(t['gnss_vol_max_assumed_v']+rs*t['schmitt_input_leak_max_a'])/(1+rs/rpmax)
check('gnss_high_candidate',high,t['input_high_candidate_v'])
check('gnss_low_candidate',low,t['input_low_candidate_v'])
margin('gnss_high_working_margin',high,t['schmitt_vtplus_working_bound_v'])
margin('gnss_low_working_margin',t['schmitt_vtminus_working_bound_v'],low)
check('gnss_off_candidate',t['schmitt_ioff_max_a']*rpmax,t['input_off_candidate_v'])
margin('gnss_off_vs_native_absmax_candidate',.5,t['input_off_candidate_v'])
margin('schmitt_to_translator_high',t['schmitt_voh_min_at100ua_v'],t['translation_vih_v'])
margin('schmitt_to_translator_low',t['translation_vil_v'],t['schmitt_vol_max_at100ua_v'])
check('orin_off_candidate',t['translator_ioff_max_a']*t['orin_output_pulldown_ohm']*(1+tol),t['orin_off_candidate_v'])
margin('ldo_3v3_min_load',t['bleeder_3v3_min_a'],.001)
a=t['airy_ldo']
p=(a['vin_max_working_v']-a['vout_min_v'])*a['load_budget_a']
check('airy_ldo_dissipation',p,a['power_estimate_w'])
check('airy_ldo_rise',p*a['theta_ja_c_w'],a['rise_estimate_c'])
margin('airy_ldo_tj_working',a['tj_max_working_c'],a['ambient_working_c']+p*a['theta_ja_c_w'])
r=t['rs232']
check('rs232_idle_candidate',a['vout_min_v']-(t['translator_ioff_max_a']+1e-6)*r['din1_pullup_ohm']*(1+tol),r['din1_idle_min_candidate_v'])
margin('rs232_idle_threshold',r['din1_idle_min_candidate_v'],r['din1_vih_max_v'])
o=t['outputs']
check('airy_pps_high_candidate',3.8-o['airy_pps_load_working_max_a']*o['R530_ohm']*(1+tol),o['airy_pps_high_candidate_v'])
margin('airy_pps_high_working',o['airy_pps_high_candidate_v'],o['airy_pps_required_min_v'])

proof=dict(schema_version=1,date_utc=datetime.now(timezone.utc).isoformat(),
           scope='Reproduction arithmétique de calculs candidats ; Windows amd64',
           checks=checks,passed=all(c['passed'] for c in checks),hardware_tests_executed=False,
           manufacturing_ready=False,qualification='À valider',
           inputs=[dict(file='../dimensionnement.json',sha256=hashlib.sha256((CARD/'dimensionnement.json').read_bytes()).hexdigest())],
           limits=['Capacités efficaces sous polarisation/température non garanties par ces formules.',
                   'Équations LM76003 aux coins de fréquence et tolérance L, hors baisse supplémentaire de L sous courant/température.',
                   'Compensation compute, SOA, pertes de commutation, TVS, sélectivité et tenue hors tension restent à vérifier.',
                   'La capacité des rails ne représente pas la consommation du drone.'])
proof['limits'].append('Temps : marges conditionnelles aux niveaux GNSS supposés, seuils Schmitt discrets utilisés comme borne candidate, charge PPS12mA et référenceOrin ; aucune garantie électrique OEM ou séquencement par ces calculs.')
(HERE/'calculs_reproduits.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(f"{sum(c['passed'] for c in checks)}/{len(checks)} contrôles arithmétiques conformes ; matériel À valider")
if not proof['passed']:
    raise SystemExit(1)
