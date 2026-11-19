"""Vérifie le dossier A2 et rejoue ses demandes d’observation avec la porte A.1."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import stat
import subprocess


ROOT = Path(__file__).resolve().parents[2]
A = ROOT / "docs/verification/v3/a"
A2 = ROOT / "docs/verification/v3/a2"


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def unique_keys(pairs):
    value = dict(pairs)
    require(len(value) == len(pairs), "Clé JSON dupliquée")
    return value


def read(path):
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_keys)


def write(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def verify_native_receipt(path):
    report = read(path)
    require(report["schema"] == "drone_agricole.v3_a2.cad_interface_measurements/1", "Schéma du reçu natif A2")
    method = report["method"]
    require(method["source_reception_status"] == "NOT_RUN" and method["physical_revisions_confirmed"] == 0 and
            method["accepted_motion_domains"] == [] and method["support_anchor_frames"] is None,
            "Le reçu CAO ne doit pas porter d'autorité physique ou de conception")
    require(all(digest(ROOT / name) == sha for name, sha in report["tool_paths"].items()),
            "Empreinte d'un outil ou d'une autorité native divergente")
    for key in ("native_raw", "screen_raw"):
        raw = report[key]
        require(digest(ROOT / raw["path"]) == raw["sha256"], f"Sortie brute native divergente {key}")
    require(read(ROOT / report["native_raw"]["path"]) == report["cases"], "Projection des observations natives divergente")
    counts = {}
    for case, observation in report["cases"].items():
        if observation["status"] == "NOT_RUN":
            require(observation["required_inputs"], f"Entrées absentes non documentées pour {case}")
            continue
        require(observation["status"] == "MEASURED" and observation["recompute_ok"] and
                observation["copy_unchanged"] and observation["source_unchanged"] and not observation["save_performed"] and
                not any(observation[key] for key in ("broken_native_links", "broken_serialized_links", "invalid_objects")),
                f"La preuve native de {case} ne démontre pas une mesure sur fermeture intacte")
        inputs = observation["inputs"]
        authority_path = ROOT / inputs["authority_path"]
        require(digest(authority_path) == inputs["authority_sha256"], f"Autorité divergente pour {case}")
        authority = read(authority_path)
        expected = (authority["inputs_sha256"] if case == "reference" else
                    authority["archives"][case]["native_sha256"])
        staged = read(ROOT / inputs["receipt"])["inputs_sha256"]
        canonical = json.dumps(staged, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("ascii")
        require(staged == expected and len(staged) == inputs["verified_inputs_count"] and
                hashlib.sha256(canonical).hexdigest() == inputs["closure_map_sha256"] and
                staged["assemblages/Prototype_Cartographe.FCStd"] == inputs["expected_root_sha256"],
                f"Fermeture XLink divergente pour {case}")
        for origin in (inputs["source_root"], inputs["copy_root"]):
            require(all(digest(ROOT / origin / name) == sha for name, sha in staged.items()),
                    f"Octets de fermeture divergents pour {case}, {origin}")
        counts[case] = len(staged)
        require(set(observation["interfaces"]) == {"F40", "F41"}, f"Couverture des faces UART incomplète pour {case}")
        for frame in observation["interfaces"].values():
            require(frame["face_evidence_class"] == "ASSUMED" and
                    all(frame[key] is None for key in ("mating_frame", "wire_exit_frame", "tool_envelope")),
                    f"Un volume de réservation a acquis une autorité de face physique dans {case}")
    defects = report["defects"]
    require(set(defects) == {f"IF-{index:02d}" for index in range(3, 8)} and
            all(item["resolved"] is False for item in defects.values()), "Un défaut historique a été clos")
    return counts


def verify_dossier(scopes):
    gate = read(A / "acceptance.json")
    register = read(A2 / "evidence_register.json")
    require(register["schema"] == "v3.a2.evidence_register/1", "Schéma du registre A2")
    issues = {entry["id"] for entry in gate["open"]}
    rows = register["issues"]
    require(len(rows) == len(issues) == 8 and {row["id"] for row in rows} == issues,
            "Les huit issues A doivent être reprises une seule fois")
    require(all(row["status"] == "OPEN" for row in rows), "Une issue A2 a été close")
    require(register["physical_revisions_confirmed"] == 0 and register["physical_reception"] == "NOT_RUN",
            "Le registre revendique une réception matérielle")
    require(all(digest(ROOT / source["path"]) == source["sha256"] for source in register["source_inputs"]),
            "Une entrée du registre a changé depuis l'observation")
    authority = read(ROOT / "docs/electromechanical_v3/cartographe.json")
    initial_states = {item["id"]: item["evidence"]["state"] for item in authority["issues"]}
    manufacturers = {item["id"]: item for item in register["manufacturer_sources"]}
    require(all(digest(ROOT / notice["local_path"]) == notice["sha256"]
                for notice in manufacturers.values() if "local_path" in notice), "Notice locale modifiée")
    for row in rows:
        require(row["initial_state"] == initial_states[row["id"]], f"État initial divergent pour {row['id']}")
        require(set(row["manufacturer_sources"]) <= manufacturers.keys(),
                f"Source fournisseur inconnue pour {row['id']}")
        require(all((ROOT / item["path"]).is_file() and item["object"] for item in row["native_sources"]),
                f"Source native non localisable pour {row['id']}")

    require(scopes["schema"] == "v3.a2.operation_authorities/1", "Schéma du dossier A2")
    domains = scopes["domains"]
    require(domains["CARTOGRAPHER_PRIVATE_CAD"]["execution_scope"] == "READ_ONLY_IMPACT"
            and domains["CARTOGRAPHER_PRIVATE_CAD"]["conditional_experiment_operations"] == []
            and domains["CARTOGRAPHER_DESIGN_ADMISSION"]["decision"] == "DENY"
            and domains["PHYSICAL_RECEPTION"]["status"] == "NOT_RUN"
            and domains["SYNTHETIC_BENCH"]["execution_scope"] == "BENCH_TEST_ONLY", "Portées A2 incompatibles")
    a1 = read(ROOT / scopes["request_schema"])
    request_schema = a1["$defs"]["request"]
    operations = scopes["operations"]
    require(len(operations) == 6 and {item["operation"] for item in operations} ==
            set(request_schema["properties"]["operation"]["enum"]) - {"ANALYZE_IMPACT", "RECEIVE_PHYSICAL"},
            "Couverture des opérations de mutation incomplète")
    requirements = scopes["evidence_requirements"]
    for item in operations:
        region = item["design_domain"]
        require(item["decision"] == "DENY" and region["status"] == "UNKNOWN" and
                region["admissible_region"] is None and region["degree_of_freedom_bounds"] is None,
                f"Domaine sans autorité pour {item['operation']}")
        require(set(item["blocking_issues"]) <= issues and item["blocking_issues"] and
                set(item["required_evidence"]) <= requirements.keys() and
                "SIGNED_PHYSICAL_MEASUREMENT" in item["required_evidence"],
                f"Préconditions sans autorité pour {item['operation']}")

    require(requirements["LOT_DOCUMENT_MATCH"]["match"] == "EXACT_LOT_APPLICABILITY",
            "L'applicabilité au lot réel doit être prouvée")
    require(requirements["INDEPENDENT_MATING_FRAME"]["independent_of_cable_axis"] is True,
            "Un axe de câble ne constitue pas un repère d’accouplement")
    measurement = requirements["SIGNED_PHYSICAL_MEASUREMENT"]
    fields = set(measurement["required_fields"])
    require(measurement["status"] == "NOT_RUN" and fields >= {
        "signature", "operator_id", "raw_evidence_ref", "lot_evidence_ref", "hardware_revision",
        "method", "instrument", "tolerance", "coordinate_system",
    }, "Contrat de métrologie incomplet")
    fixture = dict.fromkeys(fields, "témoin synthétique de présence")
    controls = []
    for missing in ("signature", "raw_evidence_ref", "lot_evidence_ref"):
        candidate = {**fixture, missing: ""}
        refused = sorted(field for field in fields if not candidate.get(field, "").strip())
        require(refused == [missing], f"Le champ obligatoire {missing} doit empêcher la complétude")
        controls.append({"omission": missing, "missing_fields": refused, "status": "PASS"})
    require(all(fixture.get(field, "").strip() for field in fields), "Témoin de format incomplet")
    return request_schema, controls


def replay_requests(scopes, schema, core, output):
    seal = scopes["observation_xlink_dependencies"]
    path = ROOT / seal["path"]
    require(path == A / "native_receipt.json" and digest(path) == seal["sha256"] and
            seal["locator"] == "/inputs_sha256", "Reçu natif A différent")
    receipt = read(path)
    dependencies = receipt["inputs_sha256"]
    source = ROOT / receipt["source_prefix"]
    sandbox = output / "input"
    require(dependencies and all(digest(source / name) == sha for name, sha in dependencies.items()),
            "Octets sources différents du reçu natif")
    for name in dependencies:
        target = sandbox / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / name, target)
        target.chmod(stat.S_IREAD)
    common = scopes["observation_request_common"]
    oracle = read(A / "impact_oracle.json")["cases"]
    fragments = scopes["observation_requests"]
    require(len(fragments) == len(oracle) == 3 and {
        (fragment["occurrence"], fragment["effect"]["hypothetical_operation"]) for fragment in fragments
    } == {(case["target"], case["operation"]) for case in oracle}, "Observations hors oracle")

    cases = []
    for fragment in fragments:
        require(set(fragment) == {"occurrence", "effect"} and not set(fragment) & common.keys(),
                "Fragment de demande ambigu")
        request = {**common, **fragment, "xlink_dependencies": dependencies}
        require(set(request) == set(schema["required"]), "Structure de demande A.1 divergente")
        case = request["effect"]["hypothetical_operation"]
        request_path = output / f"{case}-request.json"
        response_path = output / case
        write(request_path, request)
        result = subprocess.run([str(core), "v3-admission", "--root", str(ROOT), "--request", str(request_path),
                                 "--sandbox", str(sandbox), "--output", str(response_path)],
                                capture_output=True, timeout=60)
        require(result.returncode == 0, result.stderr.decode("utf-8", errors="replace"))
        admission_path = response_path / "admission.json"
        result_receipt = read(admission_path)
        decision = result_receipt["admission"]
        require(decision["decision"] == "ALLOW" and decision["execution_scope"] == "READ_ONLY_IMPACT" and
                decision["reason"] == "FROZEN_VIRTUAL_IMPACT" and result_receipt["dispatch_status"] == "READ_ONLY" and
                result_receipt["construction_result"] == "NOT_RUN" and result_receipt["candidate_transactions"] == 0 and
                result_receipt["request_sha256"] == digest(request_path) and
                list(response_path.iterdir()) == [admission_path], f"Reçu L5 incompatible pour {case}")
        cases.append({"case": case, "occurrence": request["occurrence"], "exit_code": result.returncode,
                      "request_sha256": digest(request_path), "receipt_sha256": digest(admission_path),
                      "decision": decision["decision"], "reason": decision["reason"],
                      "execution_scope": decision["execution_scope"], "candidate_transactions": 0})
    require(all(digest(source / name) == digest(sandbox / name) == sha for name, sha in dependencies.items()),
            "Une source ou une copie a changé pendant le rejeu")
    return cases, len(dependencies)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--core", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    output = args.out.resolve()
    require(output.is_relative_to(ROOT / ".runtime"), "Sortie privée sous .runtime requise")
    scopes_path = A2 / "operation_scopes.json"
    native_path = A2 / "cad_interface_measurements.json"
    scopes = read(scopes_path)
    schema, controls = verify_dossier(scopes)
    native_counts = verify_native_receipt(native_path)
    output.mkdir(parents=True, exist_ok=False)
    cases, source_count = replay_requests(scopes, schema, args.core.resolve(strict=True), output)
    write(output / "integrity.json", {
        "schema": "v3.a2.integrity_test/1", "status": "PASS",
        "inputs_sha256": {path.relative_to(ROOT).as_posix(): digest(path)
                          for path in (scopes_path, native_path, A2 / "evidence_register.json", Path(__file__).resolve())},
        "verified_source_and_copy_files": source_count,
        "verified_register_source_refs": len(read(A2 / "evidence_register.json")["source_inputs"]),
        "verified_cad_source_and_copy_files_by_case": native_counts,
        "a1_observations": cases,
        "metrology_required_fields": {"positive_fixture_format": "PASS", "negative_cases": controls,
                                      "scope": "Complétude des champs A2, hors authentification et admission L5"},
    })


if __name__ == "__main__":
    main()
