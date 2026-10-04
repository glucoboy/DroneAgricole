#!/usr/bin/env python3
"""Recette arithmétique R116 ; aucune qualification matérielle ni sélection de MPN.

Exécution : python verification/verify_shunt_thermique.py
Les entrées électriques existantes viennent de dimensionnement.json. Les paramètres
de revue absents de ce fichier restent explicitement des hypothèses candidates.
La preuve contient le SHA256 du fichier lu et de cette recette.
"""

import hashlib
import itertools
import json
import math
from pathlib import Path


BASE = Path(__file__).resolve().parents[1]
INPUT = BASE / "dimensionnement.json"
OUTPUT = BASE / "verification" / "shunt_thermique_20261001.json"


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bounds(nominal, tolerance, tcr_ppm, delta_k):
    drift = tcr_ppm * 1e-6 * delta_k
    return [nominal * (1 - tolerance) * (1 - drift),
            nominal * (1 + tolerance) * (1 + drift)]


def ccm(vin, vout, inductance, frequency, resistance, output_current):
    duty = vout / vin
    ripple = vout * (1 - duty) / (inductance * frequency)
    mean_square = (1 - duty) * (output_current**2 + ripple**2 / 12)
    return {"vin_v": vin, "vout_v": vout, "l_h": inductance,
            "frequency_hz": frequency, "r_shunt_ohm": resistance,
            "duty": duty, "iout_a": output_current, "ripple_pp_a": ripple,
            "valley_a": output_current - ripple / 2,
            "peak_a": output_current + ripple / 2,
            "shunt_rms_a": math.sqrt(mean_square),
            "shunt_power_w": resistance * mean_square}


def derating_w(rating_w, ambient_c):
    # Courbe VPG : 100 % jusqu'à 70 °C, droite vers 0 % à 170 °C.
    return rating_w * max(0, min(1, (170 - ambient_c) / 100))


def main():
    data = json.loads(INPUT.read_text(encoding="utf-8-sig"))
    entry = data["entry_compute"]
    buck = entry["compute_buck"]
    shunt = entry["current_limit_shunt"]
    requested_spec = data.get("shunt_requested_specification", {})
    replacement = data.get("shunt_replacement_candidate", {})
    # Paramètres de recette, surchargeables uniquement par ce bloc déclaratif.
    defaults = {"requested_tolerance_fraction": 0.001,
                "requested_tcr_ppm_per_k": 25,
                "delta_temperature_k": 100,
                "local_ambient_candidate_max_c": 125,
                "inductance_nominal_h": 6.8e-6,
                "inductance_tolerance_fraction": 0.20,
                "rt_tolerance_fraction": 0.01,
                "rt_tcr_unapproved_ppm_per_k": 100,
                "rilim_tolerance_fraction": 0.01,
                "rilim_tcr_assumed_ppm_per_k": 100,
                "feedback_resistor_tolerance_fraction": 0.001,
                "feedback_reference_tolerance_fraction": 0.01,
                "stress_constant_current_a": 13.09}
    if requested_spec:
        defaults["requested_tolerance_fraction"] = requested_spec["initial_tolerance_fraction"]
        defaults["requested_tcr_ppm_per_k"] = requested_spec["tcr_max_abs_ppm_per_k"]
    overrides = shunt.get("thermal_review_inputs", {})
    unknown = set(overrides) - set(defaults)
    if unknown:
        raise ValueError(f"Entrées de revue inconnues : {sorted(unknown)}")
    p = dict(defaults, **overrides)
    rs = shunt["r_shunt_ohm"]
    if not math.isclose(rs, 0.010, abs_tol=1e-12):
        raise ValueError("Cette comparaison VPG porte exactement sur 10 mΩ.")
    if requested_spec and not math.isclose(requested_spec["resistance_ohm"], rs, abs_tol=1e-12):
        raise ValueError("Résistance demandée différente du shunt configuré.")
    vin = entry["assumptions"]["vin_working_v"]
    current = entry["assumptions"]["rail_capacities_w"][0] / buck["vout_typ_v"]
    rt = buck["rt_ohm"]
    ri = shunt["r_ilim_ohm"]
    irs = shunt["i_ilim_min_typ_max_a"]
    offset = shunt["offset_min_max_v"]
    top, bottom = buck["feedback_ohm"]
    fbtol = p["feedback_resistor_tolerance_fraction"]
    vfbtol = p["feedback_reference_tolerance_fraction"]
    vfb = buck["feedback_vfb_v"]
    vout = [vfb * (1 - vfbtol) * (1 + top * (1 - fbtol) / (bottom * (1 + fbtol))),
            vfb * (1 + vfbtol) * (1 + top * (1 + fbtol) / (bottom * (1 - fbtol)))]
    lnom = p["inductance_nominal_h"]
    inductances = [lnom * (1 - p["inductance_tolerance_fraction"]),
                   lnom * (1 + p["inductance_tolerance_fraction"])]
    frequencies = [380000 * 25000 / (rt * (1 + p["rt_tolerance_fraction"])),
                   420000 * 25000 / (rt * (1 - p["rt_tolerance_fraction"]))]
    rt_drift = p["rt_tcr_unapproved_ppm_per_k"] * 1e-6 * p["delta_temperature_k"]
    unapproved_frequencies = [frequencies[0] / (1 + rt_drift),
                              frequencies[1] / (1 - rt_drift)]
    ri_bounds = bounds(ri, p["rilim_tolerance_fraction"],
                       p["rilim_tcr_assumed_ppm_per_k"], p["delta_temperature_k"])

    def evaluate(tolerance, tcr, freq):
        rs_bounds = bounds(rs, tolerance, tcr, p["delta_temperature_k"])
        normal = [ccm(vi, vo, li, fi, r, current)
                  for vi, vo, li, fi, r in itertools.product(vin, vout, inductances, freq, rs_bounds)]
        limited = []
        for vi, vo, li, fi, r in itertools.product(vin, vout, inductances, freq, rs_bounds):
            valley = (irs[2] * ri_bounds[1] - offset[0]) / r
            ripple = vo * (1 - vo / vi) / (li * fi)
            limited.append(ccm(vi, vo, li, fi, r, valley + ripple / 2))
        valley_min = (irs[0] * ri_bounds[0] - offset[1]) / rs_bounds[1]
        valley_min_symmetric = (irs[0] * ri_bounds[0] - max(abs(x) for x in offset)) / rs_bounds[1]
        valley_max = (irs[2] * ri_bounds[1] - offset[0]) / rs_bounds[0]
        min_headroom = min(row["ripple_pp_a"] / 2 + valley_min - current for row in normal)
        min_conservative_headroom = min(row["ripple_pp_a"] / 2 + valley_min_symmetric - current for row in normal)
        return {"r_shunt_bounds_ohm": rs_bounds,
                "normal_corner_count": len(normal),
                "normal_max_power": max(normal, key=lambda row: row["shunt_power_w"]),
                "normal_max_peak": max(normal, key=lambda row: row["peak_a"]),
                "valley_limit_min_max_a": [valley_min, valley_max],
                "valley_min_symmetric_offset_conservative_a": valley_min_symmetric,
                "min_output_limit_margin_above_load_a": min_headroom,
                "min_output_limit_margin_symmetric_offset_a": min_conservative_headroom,
                "limit_max_power": max(limited, key=lambda row: row["shunt_power_w"]),
                "limit_max_peak": max(limited, key=lambda row: row["peak_a"]),
                "constant_current_stress_power_w": p["stress_constant_current_a"]**2 * rs_bounds[1]}

    requested = evaluate(p["requested_tolerance_fraction"], p["requested_tcr_ppm_per_k"], frequencies)
    historical_request = evaluate(0.0005, 25, frequencies)
    hypothetical_rt = evaluate(p["requested_tolerance_fraction"], p["requested_tcr_ppm_per_k"], unapproved_frequencies)
    standard = evaluate(0.001, 15, frequencies)
    legacy = evaluate(0.005, 75, frequencies)
    nominal = [ccm(vi, buck["vout_typ_v"], lnom, buck["frequency_hz"], rs, current) for vi in vin]
    candidates = []
    for family, rating in [("CSM2512", 1), ("CSM3637", 3)]:
        allowed = derating_w(rating, p["local_ambient_candidate_max_c"])
        normal_power = standard["normal_max_power"]["shunt_power_w"]
        limit_power = standard["limit_max_power"]["shunt_power_w"]
        tolerance_met = 0.001 <= p["requested_tolerance_fraction"]
        tcr_met = 15 <= p["requested_tcr_ppm_per_k"]
        candidates.append({"family": family, "nominal_ohm": 0.010,
                           "rating_at_70c_w": rating,
                           "allowed_at_candidate_ambient_w": allowed,
                           "catalogue_best_tolerance_fraction": 0.001,
                           "catalogue_tcr_max_ppm_per_k": 15,
                           "tcr_temperature_domain_c": [-55, 125],
                           "tcr_reference_c": 25,
                           "requested_initial_tolerance_met": tolerance_met,
                           "requested_tcr_met_within_catalogue_domain": tcr_met,
                           "catalogue_conforms_to_current_request": tolerance_met and tcr_met,
                           "historical_0_05percent_request_met": False,
                           "normal_6a_analytical_power_within_derating": normal_power <= allowed,
                           "continuous_upper_valley_limit_power_within_derating": limit_power <= allowed,
                           "constant_13_09a_stress_within_derating": standard["constant_current_stress_power_w"] <= allowed,
                           "normal_power_margin_w": allowed - normal_power,
                           "upper_limit_power_margin_w": allowed - limit_power,
                           "maximum_local_ambient_from_upper_limit_power_c": 170 - 100 * limit_power / rating,
                           "availability": "Famille et résistance catalogue ; aucun stock ni délai garanti par cette preuve.",
                           "selection_status": ("Conforme à la demande actuelle sur tolérance et TCR catalogue ; thermique et pulses À valider."
                                                if tolerance_met and tcr_met else
                                                "Non conforme à la demande actuelle sur tolérance et/ou TCR catalogue ; offre spéciale à confirmer.")})

    selected_mpn = next((replacement.get(key) for key in
                         ("manufacturer_mpn", "mpn", "selected_mpn", "catalog_mpn", "custom_mpn")
                         if replacement.get(key)), None)
    catalogue_conforms = all(c["catalogue_conforms_to_current_request"] for c in candidates)

    checks = {
        "low_side_nominal_18v_reference": math.isclose(nominal[0]["shunt_power_w"], 0.12060073048827377, rel_tol=1e-10),
        "low_side_nominal_25_2v_reference": math.isclose(nominal[1]["shunt_power_w"], 0.19090254309006513, rel_tol=1e-10),
        "frequency_rt_24_9k_one_percent_reference": math.isclose(frequencies[0], 377748.6182353175, rel_tol=1e-10),
        "derating_2512_125c": math.isclose(derating_w(1, 125), 0.45),
        "derating_3637_125c": math.isclose(derating_w(3, 125), 1.35),
        "derating_zero_170c": derating_w(3, 170) == 0,
        "normal_ccm_all_corners": requested["normal_max_peak"]["valley_a"] > 0,
        "requested_bounds_bracket_nominal": requested["r_shunt_bounds_ohm"][0] < rs < requested["r_shunt_bounds_ohm"][1],
        "catalogue_conformity_matches_current_request": all(
            c["requested_initial_tolerance_met"] == (c["catalogue_best_tolerance_fraction"] <= p["requested_tolerance_fraction"])
            and c["requested_tcr_met_within_catalogue_domain"] == (c["catalogue_tcr_max_ppm_per_k"] <= p["requested_tcr_ppm_per_k"])
            for c in candidates),
        "historical_0_05percent_catalogue_comparison": all(not c["historical_0_05percent_request_met"] for c in candidates)}
    proof = {
        "schema_version": 2, "date": "2026-10-01", "component": "R116",
        "status": "À valider", "arithmetic_passed": all(checks.values()),
        "hardware_tests_executed": False,
        "input": {"path": str(INPUT.relative_to(BASE)), "sha256": sha256(INPUT),
                  "recipe_path": str(Path(__file__).resolve().relative_to(BASE)),
                  "recipe_sha256": sha256(Path(__file__)),
                  "configuration_declared_shunt": shunt,
                  "requested_specification": requested_spec,
                  "replacement_candidate": replacement},
        "review_parameters": p,
        "review_parameters_from_configuration": sorted(overrides),
        "review_parameters_defaults_candidate": sorted(set(defaults) - set(overrides)),
        "electrical_inputs": {"normal_load_a": current, "vin_v": vin, "vout_bounds_v": vout,
                              "inductance_bounds_h": inductances, "frequency_rt_tolerance_bounds_hz": frequencies,
                              "rt_temperature_unapproved_frequency_bounds_hz": unapproved_frequencies,
                              "rilim_bounds_ohm": ri_bounds, "irs_min_typ_max_a": irs,
                              "offset_min_max_v": offset},
        "model": {"topology": "Shunt source MOSFET bas, courant uniquement pendant 1-D en CCM établi idéal.",
                  "duty": "D=VOUT/VIN",
                  "ripple": "deltaI=VOUT*(1-D)/(L*f)",
                  "rms": "Irms_shunt^2=(1-D)*(Iout^2+deltaI^2/12)",
                  "valley_limit": "Ivalley=(IRS*Rilim-VILIM_TH)/Rshunt",
                  "at_valley_limit": "Iout=Ivalley+deltaI/2 ; P=Rshunt*(1-D)*(Ivalley^2+Ivalley*deltaI+deltaI^2/3)",
                  "frequency_model": "TI 380..420kHz à RT=25kΩ, proportion inverse RT ; RT24,9k±1 %.",
                  "correlated_resistance": "Le même Rshunt est utilisé pour seuil et puissance à chaque coin ; ne pas combiner seuil Rmin et pertes Rmax.",
                  "limitations": "Pas de chute MOSFET/shunt/DCR, dead-time, retard OCP, bias/température L, saturation ni commande hiccup dans le modèle CCM."},
        "normal_nominal": nominal,
        "current_requested_specification_envelope": requested,
        "historical_0_05percent_25ppm_envelope": historical_request,
        "rt_temperature_unapproved_separate_envelope": hypothetical_rt,
        "vpg_standard_0_1percent_15ppm_envelope": standard,
        "historical_legacy_0_5percent_75ppm_envelope": {
            "basis": "Ancienne sélection WSLT2512R0100DEA ; 75ppm/100K est l'hypothèse historique, pas une confirmation fabricant supplémentaire ni l'état PCB actuel.",
            "calculated": legacy,
            "requested_initial_tolerance_met": 0.005 <= p["requested_tolerance_fraction"],
            "requested_tcr_met_by_historical_assumption": 75 <= p["requested_tcr_ppm_per_k"]},
        "selected_reference_interpretation": {
            "configured_mpn": selected_mpn,
            "expected_manufacturer_mpn_for_csm3637_10mohm_0_1percent_leadfree_reel": "Y14880R01000B9R",
            "ordering_code": {"Y1488": "CSM3637", "0R01000": "0,01000 Ω", "B": "±0,1 %", "9": "sans plomb", "R": "bande et bobine"},
            "configured_mpn_matches_ordering_code": selected_mpn == "Y14880R01000B9R",
            "catalogue_conforms_to_current_request": catalogue_conforms,
            "special_order_required_by_current_request": not catalogue_conforms,
            "hardware_qualification": False},
        "vpg_candidate_comparison": candidates,
        "thermal_interpretation": {
            "candidate_ambient_c": p["local_ambient_candidate_max_c"],
            "derating_curve": "Pautorisé=P70*clamp((170-Tambient)/100,0,1)",
            "ambient_approval": "125 °C est une enveloppe de comparaison candidate, pas l'ambiance carte mesurée/approuvée.",
            "temperature_distinction": "Le déclassement utilise l'ambiance locale ; le TCR utilise la température résistive. À ambiance 125 °C, l'autoéchauffement peut sortir du domaine TCR garanti jusqu'à 125 °C.",
            "theta_ja_c_per_w": None, "airflow_lfm": None, "temperature_rise_c": None,
            "thermal_qualification": False,
            "precision": (f"±{100 * p['requested_tolerance_fraction']:g} % initial ne garantit pas cette précision globale : "
                          f"{p['requested_tcr_ppm_per_k']:g} ppm/K sur {p['delta_temperature_k']:g} K ajoute jusqu'à "
                          f"{p['requested_tcr_ppm_per_k'] * p['delta_temperature_k'] * 0.0001:g} %. "
                          "Stabilité de vie, soudure et connexions Kelvin non incluses."),
            "catalogue_15ppm_drift_over_delta_temperature_fraction": 15e-6 * p["delta_temperature_k"]},
        "current_limit_interpretation": {
            "simplified_typical_valley_a": irs[1] * ri / rs,
            "typical_valley_including_ti_minus2mv_a": (irs[1] * ri + 0.002) / rs,
            "warning": "7,5 A est la vallée simplifiée, ni le courant de sortie moyen ni le pic. 13,09 A est un stress DC imposé, pas une borne calculée de protection.",
            "sensitivity_at_10mohm": {"minus8mv_offset_current_a": 0.008 / rs,
                                      "plus3_5mv_offset_current_a": 0.0035 / rs,
                                      "irs_ten_percent_typical_current_span_a": 0.1 * irs[1] * ri / rs}},
        "faults_not_qualified": {
            "ti_hiccup_cycles": {"consecutive_limit_events": 128, "off_cycles": 8192},
            "illustrative_timing_from_frequency_bounds": [{"frequency_hz": f,
                "128_cycles_s": 128 / f, "8192_cycles_s": 8192 / f,
                "constant_stress_energy_in_128_cycles_j": requested["constant_current_stress_power_w"] * 128 / f} for f in frequencies],
            "not_a_waveform_bound": True,
            "open": ["Court-circuit : VOUT chute, D et conduction bas changent ; le modèle12V CCM ne borne pas la faute.",
                     "Mesurer pics, retards OCP, courant bas, queue inductive, skips, soft-start et répétition hiccup.",
                     "Obtenir limite pulse/I²t répétitif fabricant et dérive après faute ; essai surcharge5s catalogue ne qualifie pas la forme d'onde CA01.",
                     "Valider dissipation PCB/câbles/capacités, saturation L et sécurité MOSFET/fusible sous défaut."]},
        "sources": [
            {"url": "https://www.ti.com/lit/ds/symlink/lm5146-q1.pdf", "document": "LM5146-Q1, RevB", "sections": "Table électrique FSW/IRS/VILIM_TH ; 8.3.5,8.3.10,8.3.11"},
            {"url": "https://vpgfoilresistors.com/products/current-sense-resistors/csm2512/datasheet", "document": "VPG CSM Series 4138-EN, Rev8-July-2025", "sections": "p1 ratings/TCR/tolérance ; p2 courbe puissance ; p3 surcharge/stabilité ; p4 codification"}],
        "checks": checks,
        "conclusion": ("Recette arithmétique seulement. À 125 °C candidat, CSM2512 couvre 6 A mais pas la limite haute continue ; "
                       "CSM3637 couvre les deux dans le modèle. "
                       + ("Les offres standard ±0,1 % / 15 ppm/K répondent à la demande actuelle sur tolérance et TCR. "
                          if catalogue_conforms else
                          "Les offres standard ±0,1 % / 15 ppm/K ne répondent pas à la demande actuelle sur tolérance et/ou TCR. ")
                       + "La cible ±0,05 % historique reste distincte et non satisfaite en catalogue standard. "
                       "Aucune qualification thermique réelle ni pulse obtenue.")}
    OUTPUT.write_text(json.dumps(proof, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUTPUT), "arithmetic_passed": proof["arithmetic_passed"],
                      "requested_normal_max_power_w": requested["normal_max_power"]["shunt_power_w"],
                      "requested_limit_max_power_w": requested["limit_max_power"]["shunt_power_w"],
                      "standard_normal_max_power_w": standard["normal_max_power"]["shunt_power_w"],
                      "standard_limit_max_power_w": standard["limit_max_power"]["shunt_power_w"],
                      "qualified": False}, ensure_ascii=False))
    if not proof["arithmetic_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
