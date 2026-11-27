"""Consigne les vérifications C.3 et réconcilie la réfutation T1/T2."""

from datetime import datetime
import math
from pathlib import Path
import runpy
import subprocess


helpers = runpy.run_path(str(Path(__file__).with_name("c3-recheck.py")))
ROOT, RUNTIME = helpers["ROOT"], helpers["RUNTIME"]
read, write, require = (helpers[key] for key in ("read", "write", "require"))
digest, artifact, verify = (helpers[key] for key in ("digest", "artifact", "verify_path"))
CAMPAIGN = RUNTIME / "c3-review"
COUNTER = RUNTIME / "c3-countermeasure"
LOGS = RUNTIME / "c3-logs"
EVALUATOR = RUNTIME / "c3-evaluator"
PLANS = ROOT / "docs/electromechanical_v3"


def result(phase):
    file = COUNTER / f"{phase.lower()}-recheck.json"
    result = read(file)
    command = LOGS / f"{phase}.command.json"
    command_log = read(command)
    require(command_log["exit_code"] == 0, f"Rejeu {phase} en échec")
    result.update(status="PASS", recheck=artifact(file), command=command_log, command_record=artifact(command),
                  log=artifact(LOGS / f"{phase}.log"))
    return result


def selected(phase):
    return next(row for row in phase["admissible"] if row["id"] == phase["retained"])


def compare_routes(first, second, impacted, domain, tolerance):
    a, b = (read(verify(row["measurement"]))["routes"] for row in (first, second))
    result = {}
    for name in impacted:
        plane = domain["harnesses"][name]["route"]["nominal_plane"]
        axis = "XYZ".index(plane["axis"])
        previous = [a[name]["edges"][0]["start_mm"], *(edge["end_mm"] for edge in a[name]["edges"])]
        vertex_distances = [(min(math.dist(edge["end_mm"], old) for old in previous), edge["end_mm"])
                            for edge in b[name]["edges"][:-1]
                            if abs(edge["end_mm"][axis] - plane["coordinate_mm"]) > tolerance]
        distance, vertex = max(vertex_distances, default=(0, None))
        require(distance > tolerance and first["geometry"][name]["axis_sha256"] != second["geometry"][name]["axis_sha256"],
                f"Adaptation spatiale non démontrée : {name}")
        result[name] = {"t1_axis_sha256": a[name]["axis_sha256"], "t2_axis_sha256": b[name]["axis_sha256"],
                        "nearest_t1_vertex_mm": distance, "t2_interior_vertex_mm": vertex,
                        "t1_length_mm": a[name]["length_mm"], "t2_length_mm": b[name]["length_mm"]}
    return result


def refutation(handoff_path, freeze_path, t1, t2, t2_phase, profile, domain):
    handoff, freeze = read(handoff_path), read(freeze_path)
    tolerances = profile["model"]["validation"]["tolerances"]
    require(verify(handoff["freeze"]) == freeze_path and all(
        handoff[name] == row and verify(row).is_file() for name, row in freeze["t1"].items()), "Gel T1 divergent")
    initial, adapted = t1["native_sha256"], t2["native_sha256"]
    require(initial.keys() == adapted.keys() and
            {name for name in initial if initial[name] != adapted[name]} == {profile["entry"]} and
            handoff["candidate"]["sha256"] == initial[profile["entry"]], "Delta de fermeture native absent ou excessif")
    perturbation = verify(t2_phase["perturbation"])
    payload = read(perturbation)
    require(datetime.fromisoformat(payload["issued_at_utc"]) >
            datetime.fromisoformat(freeze["frozen_at_utc"]) and payload["freeze_sha256"] == digest(freeze_path) and
            payload["t1_root_sha256"] == initial[profile["entry"]] and
            payload["t1_problem_sha256"] == handoff["problem"]["sha256"], "Identité temporelle du témoin T2 différente")
    archived = read(ROOT / "docs/verification/v3/int3/integration/inputs/c3-t2-perturbation.json")["obstacle"]
    obstacle = payload["obstacle"]
    require((obstacle["min_mm"], obstacle["max_mm"]) != (archived["min_mm"], archived["max_mm"]),
            "Obstacle T2 identique au témoin d’intégration")

    evaluator = EVALUATOR / "evaluator-receipt.json"
    external = read(evaluator)
    require(external["status"] == "PASS" and external["mandate_after_freeze"] and external["request"] == payload and
            verify(external["handoff"]) == handoff_path and verify(external["perturbation"]) == perturbation and
            external["closure_sha256"] == initial and external["copy_unchanged"] and external["closure_unchanged"],
            "Reçu évaluateur hors gel")
    measured = verify(external["observation"])
    require(measured.is_relative_to(EVALUATOR) and not measured.is_relative_to(CAMPAIGN), "Copie évaluateur non séparée")
    evaluated = read(measured)
    independent = evaluated["external_obstacle"]
    require(independent["presence"] == "HYPOTHETICAL" and independent["id"] == obstacle["id"] and
            independent["bounds_mm"] == [obstacle["min_mm"], obstacle["max_mm"]] and
            evaluated["inputs_sha256"] == initial and evaluated["copy_unchanged"] and evaluated["documents_closed"] and
            evaluated["status"] == "MEASURED" and read(verify(external["command"]))["exit_code"] == 0,
            "Réfutation T1 externe non attestée")
    rerun_summary = read(CAMPAIGN / "t2/summary.json")["external_perturbation"]
    rerun = read(verify(rerun_summary["collision"]))
    require(rerun["pid"] != evaluated["pid"] and rerun["inputs_sha256"] == initial and
            rerun["external_obstacle"] == independent, "Contre-mesure de la réfutation T1 divergente")
    impacted = sorted(name for name, row in independent["harnesses"].items()
                      if row["intersection_mm3"] > tolerances["volume_mm3"])
    require(impacted and impacted == rerun_summary["invalidated_harnesses"], "T1 non réfuté par le solide")
    require(t2["external"]["presence"] == "SAVED_NATIVE" and t2["external"]["bounds_mm"] == independent["bounds_mm"] and
            t2["external"]["symmetric_difference_mm3"] <= tolerances["volume_mm3"] and all(
                row["intersection_mm3"] <= tolerances["volume_mm3"] for row in t2["external"]["harnesses"].values()),
            "Le solide sauvegardé T2 est divergent ou intersecte un faisceau")

    return {"input_payload": payload, "evaluator_receipt": artifact(evaluator), "evaluator_geometry": external["geometry"],
            "evaluator_measurement": artifact(measured), "evaluator_command": read(verify(external["command"])),
            "evaluator_values": independent, "replayed_measurement": rerun_summary["collision"],
            "impacted_harnesses": impacted, "t1_native_sha256": initial, "t2_native_sha256": adapted,
            "reroute": compare_routes(t1, t2, impacted, domain, tolerances["position_mm"])}


def main():
    phases = {phase: result(phase) for phase in ("T1", "T2", "T3", "T4")}
    t1, t2, t3 = map(selected, (phases["T1"], phases["T2"], phases["T3"]))
    profile = read(PLANS / "bench_c3_spatial/profile.json")
    domain = read(PLANS / "domains/c3_spatial.json")
    tolerance = profile["model"]["validation"]["tolerances"]["position_mm"]
    require(phases["T1"]["qualified_candidates"] >= 2 and any(
        row["departure_mm"] > tolerance for row in t1["geometry"].values()), "Critère T1 absent")
    changed_datums = sorted(key for key in t3["ports"] if t3["ports"][key] != t1["ports"][key])
    require(changed_datums and t3["parents"] != t1["parents"] and any(
        row["departure_mm"] > tolerance for row in t3["geometry"].values()), "Généralisation T3 absente")
    phases["T3"]["different_native_datums"] = changed_datums
    handoff, freeze_path = CAMPAIGN / "T2-HANDOFF.json", CAMPAIGN / "freeze.json"
    phases["T2"]["refutation"] = refutation(handoff, freeze_path, t1, t2, phases["T2"], profile, domain)
    perturbation = verify(phases["T2"]["perturbation"])

    for phase in ("T1", "T2", "T3"):
        card = phases[phase]
        card["retained_detail"] = selected(card)
        card["admissible"] = [{key: row[key] for key in ("id", "measurement", "assessment", "command", "checks", "native_sha256")}
                              for row in card["admissible"]]
    probe, probe_log = LOGS / "corridor-probe.json", LOGS / "corridor-probe.command.json"
    require(read(probe)["status"] == "PASS" and read(probe_log)["exit_code"] == 0, "Sonde arc/segment absente")
    versions = t1["environment"]
    require(t2["environment"] == t3["environment"] == versions, "Versions FreeCAD divergentes")
    freeze = read(freeze_path)
    tools = freeze["inputs"]["tools"]
    hashes = {key: digest(Path(path)) for key, path in tools.items()}
    for key, value in hashes.items():
        require(value == freeze["inputs"]["files_sha256"][tools[key]], f"Binaire {key} hors gel")
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    require(head == freeze["inputs"]["source_commit"] == "60790ca713bd3e243b1a2581014927b5e7169ac4", "HEAD différent du gel")
    negative = LOGS / "T2-relative-input-refused.command.json"
    refusal = read(negative)
    require(refusal["exit_code"] != 0 and not list((CAMPAIGN / "t2-relative-input-refused").iterdir()),
            "Refus d’entrée non canonique non démontré")
    write(RUNTIME / "c3_native_recheck.json",
          {"schema": "v3.int3.c3_native_recheck/1", "status": "PASS", "checkout_commit": head,
           "tested_commit": "558b40fce8a33cb97b28d98418fb258585836873", "scope": "SYNTHETIC_BENCH",
           "phases": phases, "build_inputs_sha256": hashes, "freecad_environment": versions,
           "freeze": {**artifact(freeze_path), "utc": freeze["frozen_at_utc"]}, "handoff": artifact(handoff),
           "negative_corridor_probe": {"command": read(probe_log), "receipt": artifact(probe), "results": read(probe)},
           "negative_relative_perturbation": {"status": "PASS", "command": refusal, "record": artifact(negative),
                                              "log": artifact(LOGS / "T2-relative-input-refused.log"),
                                              "native_launched": False, "case_directory_empty": True},
           "review_recipe": {"path": "recipes/c3-recheck.py", "sha256_canonical_lf": digest(RUNTIME / "c3-recheck.py")},
           "observed_t2_input": {"path": "inputs/c3-t2-perturbation.json", "sha256": digest(perturbation)},
           "method": "Processus FreeCAD neuf par natif admissible, fermeture privée en lecture seule. "
                     "Recalcul des 17 métriques et fronts sur toute la population admise. "
                     "Intersection OCCT de chaque segment et arc avec l’union des corridors scellés.",
           "limits": ["Les réouvertures partagent FreeCAD/OCCT et le lecteur d’occurrences du projet.",
                      "Le témoin T2 est lié au gel local exact. Un rejeu neuf exige une nouvelle émission indépendante.",
                      "Réception physique, matériel, vol et mutation cartographe hors de la campagne."]})


if __name__ == "__main__":
    main()
