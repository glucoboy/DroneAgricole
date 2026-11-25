"""Sondes d'import V3-A.4, toutes synthétiques et sans autorité."""

import argparse
from copy import deepcopy
import csv
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import tempfile


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8", newline="\n")
    return sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def check_transaction(core, reference_root, output, freecad, t0):
    """Rejette avant construction un plan cartographe qui prétend ne garder qu'une issue ouverte."""
    native = read(reference_root / "docs/verification/v3/a/native_receipt.json")
    dependencies = native["inputs_sha256"]
    source = reference_root / native["source_prefix"]
    sandbox = output.parent / "admission/input"
    for name, expected in dependencies.items():
        assert digest(source / name) == digest(sandbox / name) == expected, name
    output.mkdir(parents=True)
    request = output / "request.json"
    plan = {
        "schema": "v3.mutation_plan/2", "domain": "CARTOGRAPHER_PRIVATE_CAD", "plan_id": "a4-one-open",
        "claimed_open_issues": ["UART-MOUNT-001"],
        "actions": [{"id": "support-iso", "occurrence": "anchor:iso-carrier", "operation": "CREATE_SUPPORT"}],
        "submitted_authority": {"signed": True, "decision": "BOUNDED_CAD_EXPERIMENT_ALLOW"},
    }
    request_sha = write(request, plan)
    transaction = output / "transaction-output"
    command = [str(core), "v3-build", "--root", str(reference_root), "--request", str(request),
               "--sandbox", str(sandbox), "--output", str(transaction),
               "--freecad-python", str(freecad), "--t0-validator", str(t0)]
    started = datetime.now(timezone.utc)
    result = subprocess.run(command, cwd=reference_root, capture_output=True, timeout=30)
    receipt_path = transaction / "refusal.json"
    assert result.returncode == 2 and receipt_path.is_file(), result.stderr
    receipt = read(receipt_path)
    assert receipt["reason"] == "MUTATION_DOMAIN_DENIED" and receipt["finalized"]
    assert receipt["plan_sha256"] == request_sha == digest(request)
    assert receipt["construction_result"] == "NOT_RUN" and receipt["candidate_transactions"] == 0
    assert list(transaction.iterdir()) == [receipt_path]
    for name, expected in dependencies.items():
        assert digest(source / name) == digest(sandbox / name) == expected, name
    return {"status": "PASS", "command": command, "exit_code": result.returncode,
            "started_at_utc": started.isoformat(), "seconds": (datetime.now(timezone.utc) - started).total_seconds(),
            "receipt_sha256": digest(receipt_path), "reason": receipt["reason"],
            "verified_sources": len(dependencies), "construction": "NOT_RUN", "candidate_transactions": 0}


def check_dossier(folder):
    """Recalcule le verdict de dossier et vérifie la couverture des preuves publiées."""
    root = folder.parents[3]
    inventory = read(folder / "lot_inventory.json")
    register = read(folder / "evidence_register.json")
    matrix = read(folder / "operation_admission.json")
    authority = read(folder / "authority_decisions.json")
    preflight = read(folder / "create_support_iso_preflight.json")
    validation = read(folder / "evidence_validation.json")
    adversarial = read(folder / "adversarial.json")
    regressions = read(folder / "regressions.json")
    manifest = read(folder / "artifacts.json")
    historical = read(folder.parent / "a3/operation_admission.json")
    prior_issues = read(folder.parent / "a3/evidence_register.json")["issues"]
    prior_pairs = {(r["occurrence"], r["operation"]) for r in historical["occurrences"]}
    verified_open = {r["id"] for r in register["issues"] if r["status"] == "OPEN"}
    assert verified_open == {r["id"] for r in prior_issues} and len(verified_open) == 8
    assert len(matrix["occurrences"]) == 12 and prior_pairs == {
        (r["occurrence"], r["operation"]) for r in matrix["occurrences"]
    }
    assert matrix["mutation"] == authority["mutation"] == preflight["decision"] == "DENY"
    assert not matrix["approved_operations"] and not authority["bounded_experiments_admitted"]
    assert all(row["decision"] == "DENY" and row["domain_bound"] is None and
               row["physical_approval"] is None and row["blocking_issues"] and
               set(row["blocking_issues"]) <= verified_open for row in matrix["occurrences"])
    assert preflight["occurrence"] == "anchor:iso-carrier" and preflight["operation"] == "CREATE_SUPPORT"
    assert validation["empty_import"]["validated_physical_approvals"] == 0 and not inventory["physical_sources"]
    assert validation["empty_import"]["status"] == "NOT_RUN"
    assert validation["example_import"]["records"][0]["reason"] == "EXAMPLE_NOT_AUTHORITY"
    assert adversarial["case_count"] == len(adversarial["cases"])
    with (folder / "measurement_form.csv").open(encoding="utf-8", newline="") as stream:
        assert {row["issue"] for row in csv.DictReader(stream)} == verified_open
    for entry in manifest["files"]:
        if entry["location"] == "checkout_A4" and not entry["path"].startswith(".runtime/"):
            assert digest(root / entry["path"]) == entry["sha256"], entry["path"]
    disposition_ready = (adversarial["status"] == "PASS" and
                         adversarial["private_cartographer_transaction"]["status"] == "PASS" and
                         all(step["status"] == "PASS" for step in regressions["required_replays"].values()))
    verdict = "V3_A4_EVIDENCE_CONDITIONAL" if disposition_ready else "V3_A4_NOT_RUN"
    expected = read(folder / "acceptance.json")
    assert expected["verdict"] == verdict and expected["finalized"] == disposition_ready
    assert all(digest(root / proof["path"]) == proof["sha256"] for proof in expected["proofs"])
    print(verdict)


def exercise(executable, folder):
    """Teste des enregistrements isolés et l'absence de droit de mutation."""
    raw = folder / "raw"
    raw.mkdir()
    references = {}
    for name in ("raw", "photo", "identity_photo", "manufacturer_document", "tolerance_document", "signature", "other"):
        path = raw / f"{name}.fixture"
        data = f"EXAMPLE_NOT_AUTHORITY {name}\n".encode()
        path.write_bytes(data)
        references[name] = {"path": path.name, "sha256": sha256(data).hexdigest()}
    measured = {
        "kind": "SERVICE_CLEARANCE", "method": "fixture hors atelier",
        "instrument": "fixture", "resolution": 0.1, "value": 3.4,
        "unit": "mm", "uncertainty": 0.2,
        "tolerance": {"comparison": "GE", "limit": 3, "unit": "mm", "source": "fixture, §1"},
    }
    facts = {
        "cavities": ["RXD", "TXD", "B_MINUS", "NC"], "port": "USB_A_HOST_1",
        "jbd_port": "J3", "isolation": "DOCUMENTED_APPLICABLE",
        "b_minus_equals_p_minus": False, "can1_5v": "NC", "measured_hole_present": True,
    }
    position = [1, 0, 0, 8, 0, 1, 0, 4, 0, 0, 1, 1, 0, 0, 0, 1]
    inverse = [1, 0, 0, -8, 0, 1, 0, -4, 0, 0, 1, -1, 0, 0, 0, 1]
    binding = {"parent": "example-parent#Part001", "datum": "fixture-hole-1"}
    identity = {
        "manufacturer": "TEST_FIXTURE", "mpn": "TEST_FIXTURE_1",
        "variant": "Li-ion", "revision": "TEST-CH343G", "lot_or_serial": "TEST-01",
    }
    base = {
        "record_id": "nominal", "evidence_class": "PHYSICAL_MEASURED", "issue": "UART-ACCESS-001",
        "subject": "anchor:iso-carrier", "check_id": "service-clearance", "identity": identity,
        "sources": {
            **{key: references[key] for key in ("raw", "photo", "identity_photo", "manufacturer_document",
                                               "tolerance_document")},
            "manufacturer_locator": "§1", "manufacturer_revision": "fixture_1",
        },
        "capture": {"author": "test", "measured_at": "2024-01-01T00:00:00Z", "view": "face",
                    "orientation": "trièdre fixture", "scale": "fixture graduée",
                    "power_state": "DEENERGIZED", "detached": True},
        "frame": {**binding, "local_to_parent": position, "parent_to_local": inverse},
        "measurement": measured, "facts": facts, "review": None,
    }
    check = {
        "subject": base["subject"], "issue": base["issue"], "kind": measured["kind"],
        "input_unit": "mm", "tolerance": measured["tolerance"], "plausible_min": 0, "plausible_max": 50,
        "tolerance_sha256": references["tolerance_document"]["sha256"], "facts": facts,
        "frame": {**binding, "local_to_parent": position, "rotation_entry_tolerance": 0.001,
                  "position_tolerance_mm": 0.1},
    }
    policy = {
        "schema": "v3.a4.review_policy/1", "configuration": "EXAMPLE_NOT_AUTHORITY",
        "issues": [base["issue"], "UART-HOST-001"], "reviewer_ids": ["test-reviewed"],
        "identities": {subject: {
            "identity": identity, "identity_photo_sha256": references["identity_photo"]["sha256"],
            "manufacturer_sha256": references["manufacturer_document"]["sha256"],
            "manufacturer_locator": "§1", "manufacturer_revision": "fixture_1",
        } for subject in (base["subject"], "port:W41/A")},
        "checks": {
            base["check_id"]: check,
            "service-seating": {**check, "kind": "GAP", "tolerance": {
                "comparison": "LE", "limit": 0.1, "unit": "mm", "source": "fixture, §2",
            }},
            "thread-engagement": {**check, "kind": "ENGAGEMENT", "tolerance": {
                "comparison": "GE", "limit": 1, "unit": "mm", "source": "fixture, §3",
            }},
            "clearance-inches": {**check, "input_unit": "in"},
        },
    }
    policy_path = folder / "policy.json"
    policy_sha = write(policy_path, policy)
    packet_path = raw / "submission.json"
    cases = []
    expectations = {}

    def case(name, status, reason=None, changes=None, omissions=()):
        row = deepcopy(base)
        row["record_id"] = name
        for section, fields in (changes or {}).items():
            if section is None:
                row.update(fields)
            else:
                row[section].update(fields)
        for scope, field in omissions:
            del row[scope][field]
        cases.append(row)
        expectations[name] = (status, reason)

    case("nominal", "PENDING_AUTHORIZED_REVIEW")
    case("declared-example", "REJECTED", "EXAMPLE_NOT_AUTHORITY", {None: {"evidence_class": "EXAMPLE_NOT_AUTHORITY"}})
    case("cad-as-physical", "REJECTED", "INVALID_EVIDENCE_CLASS", {None: {"evidence_class": "CAD_OBSERVED"}})
    for name, changes in {
        "chemistry": {"variant": "LiFePO4"}, "ft232-variant": {"revision": "FT232RNL"},
        "cord-lot": {"lot_or_serial": "TEST-02"},
    }.items():
        case(name, "REJECTED", "LOT_VARIANT_OR_REVISION_MISMATCH", {"identity": changes})
    for name, changes in {
        "cavities-reversed": {"cavities": list(reversed(facts["cavities"]))},
        "ambiguous-usb-a": {"port": "USB_A_UNKNOWN"},
        "j2-j3-conflict": {"jbd_port": "J2"}, "nc-connected": {"can1_5v": "WIRED"},
        "b-minus-p-minus": {"b_minus_equals_p_minus": True},
        "isolation-unknown": {"isolation": None}, "imaginary-hole": {"measured_hole_present": False},
    }.items():
        case(name, "REJECTED", "TOPOLOGY_OR_APPLICABILITY_MISMATCH", {"facts": changes})
    shifted, shifted_inverse = position.copy(), inverse.copy()
    shifted[3] += 3
    shifted_inverse[3] -= 3
    case("frame-plus-3mm", "REJECTED", "FRAME_OFFSET_MISMATCH",
         {"frame": {"local_to_parent": shifted, "parent_to_local": shifted_inverse}})
    flipped, flipped_inverse = position.copy(), inverse.copy()
    flipped[0] = flipped[10] = flipped_inverse[0] = flipped_inverse[10] = -1
    flipped_inverse[3], flipped_inverse[11] = 8, 1
    case("normal-reversed", "REJECTED", "FRAME_ORIENTATION_MISMATCH",
         {"frame": {"local_to_parent": flipped, "parent_to_local": flipped_inverse}})
    case("wrong-parent", "REJECTED", "FRAME_BINDING_MISMATCH", {"frame": {"parent": "other#Part001"}})
    case("wrong-inverse", "REJECTED", "FRAME_INVERSE_MISMATCH", {"frame": {"parent_to_local": position}})
    case("wrong-unit", "REJECTED", "MEASUREMENT_UNIT_MISMATCH", {"measurement": {"unit": "in"}})
    case("declared-inch-conversion", "PENDING_AUTHORIZED_REVIEW", changes={
        None: {"check_id": "clearance-inches"}, "measurement": {
            "unit": "in", "value": 0.15, "resolution": 0.004, "uncertainty": 0.005,
        }})
    case("missing-scale", "REJECTED", "MISSING_FIELDS", omissions=(("capture", "scale"),))
    case("missing-date", "REJECTED", "MISSING_FIELDS", omissions=(("capture", "measured_at"),))
    case("missing-lot", "REJECTED", "MISSING_FIELDS", omissions=(("identity", "lot_or_serial"),))
    case("missing-tolerance", "REJECTED", "MISSING_FIELDS", omissions=(("measurement", "tolerance"),))
    case("radius-unknown", "REJECTED", "INVALID_NUMBER", {"measurement": {"value": None}})
    case("clearance-touches", "INCONCLUSIVE", "TOLERANCE_INTERVAL", {"measurement": {"value": 3.2}})
    case("clearance-straddles", "INCONCLUSIVE", "TOLERANCE_INTERVAL", {"measurement": {"value": 3.1}})
    case("clearance-fails", "FAIL", "TOLERANCE_INTERVAL", {"measurement": {"value": 2.6}})
    for name, check_id, value in (("floating-0p3mm", "service-seating", 0.3),
                                  ("engagement-zero", "thread-engagement", 0)):
        selected = policy["checks"][check_id]
        case(name, "FAIL", "TOLERANCE_INTERVAL", {None: {"check_id": check_id}, "measurement": {
            "kind": selected["kind"], "tolerance": selected["tolerance"], "value": value, "uncertainty": 0.1,
        }})
    case("self-signature", "REJECTED", "UNEXPECTED_signed", {None: {"review": {"signed": True}}})
    case("unconfigured-reviewer", "REJECTED", "REVIEWER_NOT_CONFIGURED", {None: {"review": {
        "reviewer": "submitter", "detached_signature": references["signature"],
    }}})
    case("unverifiable-signature", "PENDING_AUTHORIZED_REVIEW", "NO_AUTHENTICATED_REVIEW_INFRASTRUCTURE",
         {None: {"review": {"reviewer": "test-reviewed", "detached_signature": references["signature"]}}})
    case("domain-widened", "REJECTED", "UNEXPECTED_domain_bound", {None: {"domain_bound": [-100, 100]}})
    case("raw-altered", "REJECTED", "SOURCE_SHA256_MISMATCH", {
        "sources": {"raw": {**references["raw"], "sha256": "0" * 64}},
    })
    case("raw-missing", "REJECTED", "Fichier absent : missing.bin", {
        "sources": {"raw": {**references["raw"], "path": "missing.bin"}},
    })
    case("document-other-revision", "REJECTED", "MANUFACTURER_DOCUMENT_MISMATCH", {
        "sources": {"manufacturer_document": references["other"]},
    })
    case("redirected-source", "REJECTED", changes={
        "sources": {"photo": {**references["photo"], "path": "../photo.fixture"}},
    })
    case("neighbor", "REJECTED", "EVIDENCE_SCOPE_MISMATCH", {None: {"subject": "port:W41/A"}})
    case("other-issue", "REJECTED", "EVIDENCE_SCOPE_MISMATCH", {None: {"issue": "UART-HOST-001"}})

    packet = {"configuration": policy["configuration"], "schema": "v3.a4.measurement_packet/1", "records": cases}
    before = write(packet_path, packet)
    command = [str(executable), "--raw-root", str(raw), "--packet", str(packet_path),
               "--policy", str(policy_path), "--policy-sha256", policy_sha]
    result = subprocess.run(command, capture_output=True, timeout=30)
    assert result.returncode == 2, result.stderr.decode(errors="replace")
    proof = json.loads(result.stdout)
    assert proof["authority"] == "DENY" and proof["validated_physical_approvals"] == 0, proof
    assert before == proof["packet_sha256"] and policy_sha == proof["policy_sha256"], proof
    checked = []
    assert len(proof["records"]) == len(expectations)
    for observation in proof["records"]:
        key = observation["record_id"]
        status, reason = expectations.pop(key)
        assert observation["status"] == status and observation["authority"] == "DENY", observation
        if reason is not None:
            assert observation["reason"] == reason, observation
        if key == "unverifiable-signature":
            assert observation["review_status"] == "SUBMITTED_UNVERIFIED", observation
        checked.append({"case": key, "status": "PASS", "observed": observation["status"],
                        "reason": observation["reason"]})
    assert not expectations

    bad_policy = subprocess.run([*command[:-1], "0" * 64], capture_output=True, timeout=30)
    assert bad_policy.returncode == 2 and b"POLICY_SHA256_MISMATCH" in bad_policy.stderr
    checked.append({"case": "altered-policy-sha", "status": "PASS", "observed": "REJECTED"})
    in_submission = raw / "policy.json"
    write(in_submission, policy)
    local_policy = subprocess.run([*command[:-3], "--policy", str(in_submission),
                                   "--policy-sha256", policy_sha], capture_output=True, timeout=30)
    assert local_policy.returncode == 2 and b"POLICY_INSIDE_SUBMISSION_OR_REDIRECTED" in local_policy.stderr
    checked.append({"case": "policy-in-submission", "status": "PASS", "observed": "REJECTED"})
    return {"schema": "v3.a4.adversarial/1", "status": "PASS", "evidence_class": "EXAMPLE_NOT_AUTHORITY",
            "case_count": len(checked), "cases": checked, "mutation": "DENY"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--validator", type=Path)
    mode.add_argument("--dossier", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--core", type=Path)
    parser.add_argument("--reference-root", type=Path)
    parser.add_argument("--transaction-out", type=Path)
    parser.add_argument("--freecad", type=Path)
    parser.add_argument("--t0", type=Path)
    args = parser.parse_args()
    if args.dossier:
        check_dossier(args.dossier.resolve())
        raise SystemExit(0)
    with tempfile.TemporaryDirectory() as temporary:
        test_report = exercise(args.validator.resolve(), Path(temporary))
    if args.core:
        test_report["private_cartographer_transaction"] = check_transaction(
            args.core.resolve(), args.reference_root.resolve(), args.transaction_out.resolve(),
            args.freecad, args.t0)
    if args.out:
        write(args.out, test_report)
    print(f"{test_report['case_count']} injections et témoins vérifiés")
