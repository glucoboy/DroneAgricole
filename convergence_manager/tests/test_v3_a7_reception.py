"""Témoins et injections reproductibles pour la réception documentaire V3-A.7."""

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[2]
MATRIX_PATH = ROOT / "docs/verification/v3/a7/evidence_matrix.json"
EXAMPLE = "EXAMPLE_NOT_AUTHORITY"
SOURCE_CHECK = Path(__file__).with_name("recheck_v3_a7_receipt.py")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def write(path, value):
    encoded = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode()
    path.write_bytes(encoded)
    return sha(encoded)


def private_bundle(directory, matrix, carrier):
    directory.mkdir()
    raw = directory / "raw"
    raw.mkdir()

    def source(name):
        path = raw / (name + ".fixture")
        content = f"{EXAMPLE}: {name}\n".encode()
        path.write_bytes(content)
        return {"path": path.name, "sha256": sha(content)}

    parent = matrix["carriers"][carrier]
    manufacturer_document, tolerance_document = source("manual-rev-test"), source("limits-test")
    context = {"assembly_id": "example-" + carrier, "carrier": carrier}
    envelope = {"schema": "v3.a7.submission/1", "classification": EXAMPLE, "details": {}, **context}
    configuration = matrix["configuration"]
    packet = {"schema": "v3.a4.measurement_packet/1", "configuration": configuration, "records": []}
    policy = {"schema": "v3.a4.review_policy/1", "configuration": configuration, "checks": {},
              "identities": {}, "issues": [], "reviewer_ids": []}
    for requirement in matrix["requirements"]:
        if requirement["checks"]:
            policy["issues"].append(requirement["id"])
        for row in requirement["checks"]:
            subject, key = row["subject"], row["id"]
            if subject not in policy["identities"]:
                identity = {"manufacturer": "EXAMPLE_VENDOR", "mpn": "TEST-" + subject, "variant": "TEST-VARIANT",
                            "revision": "TEST-REVISION", "lot_or_serial": "TEST-LOT-" + subject}
                identity_photo = source(key + "-identity")
                policy["identities"][subject] = {"identity": identity, "identity_photo_sha256": identity_photo["sha256"],
                                                 "manufacturer_sha256": manufacturer_document["sha256"],
                                                 "manufacturer_locator": "EXAMPLE: section 1",
                                                 "manufacturer_revision": "TEST-ONLY-1"}
            identity = policy["identities"][subject]
            identity_photo = next(root_file for root_file in raw.glob("*-identity.fixture")
                                  if sha(root_file.read_bytes()) == identity["identity_photo_sha256"])
            facts = {**context, **{name: accepted[0] for name, accepted in row.get("facts", {}).items()}}
            unit = row["unit"]
            observed_unit = "cm" if unit == "mm" else unit
            scale = 10 if observed_unit == "cm" else 1
            limit = {"unit": unit, "comparison": row["comparison"], "limit": 3 if row["comparison"] == "GE" else 6,
                     "source": "EXAMPLE: section 2"}
            # Le second témoin utilise un repère tourné de 90° autour de Z.
            t = 1 + len(packet["records"])
            if t % 2:
                direct = [1, 0, 0, t, 0, 1, 0, 2, 0, 0, 1, 3, 0, 0, 0, 1]
                inverse = [1, 0, 0, -t, 0, 1, 0, -2, 0, 0, 1, -3, 0, 0, 0, 1]
            else:
                direct = [0, -1, 0, t, 1, 0, 0, 2, 0, 0, 1, 3, 0, 0, 0, 1]
                inverse = [0, 1, 0, -2, -1, 0, 0, t, 0, 0, 1, -3, 0, 0, 0, 1]
            frame = {"parent": parent, "datum": "example." + key, "local_to_parent": direct}
            policy["checks"][key] = {"subject": subject, "issue": requirement["id"], "kind": row["kind"],
                                     "facts": facts, "tolerance": limit, "input_unit": observed_unit,
                                     "tolerance_sha256": tolerance_document["sha256"],
                                     "plausible_min": 0, "plausible_max": 100,
                                     "frame": {**frame, "position_tolerance_mm": 0.01,
                                               "rotation_entry_tolerance": 0.001}}
            record_id = "test-" + key
            packet["records"].append({
                "record_id": record_id, "evidence_class": EXAMPLE, "issue": requirement["id"], "subject": subject,
                "check_id": key, "identity": deepcopy(identity["identity"]),
                "sources": {"raw": source(key + "-raw"), "photo": source(key + "-photo"),
                            "identity_photo": {"path": identity_photo.name, "sha256": identity["identity_photo_sha256"]},
                            "manufacturer_document": manufacturer_document, "tolerance_document": tolerance_document,
                            "manufacturer_locator": identity["manufacturer_locator"],
                            "manufacturer_revision": identity["manufacturer_revision"]},
                "capture": {"author": "EXAMPLE_OPERATOR", "measured_at": "2026-01-01T10:05:00+02:00",
                            "view": "TEST_VIEW", "orientation": "TEST_AXES", "scale": "TEST_SCALE",
                            "power_state": "DEENERGIZED", "detached": True},
                "frame": {**frame, "parent_to_local": inverse},
                "measurement": {"kind": row["kind"], "resolution": 0.1 / scale, "unit": observed_unit,
                                "value": 4 / scale, "uncertainty": 0.2 / scale, "tolerance": limit,
                                "method": "EXAMPLE_METHOD", "instrument": "EXAMPLE_INSTRUMENT"},
                "facts": deepcopy(facts), "review": None,
            })
            envelope["details"][record_id] = {
                "origin_mm": [t, 2, 3], "x_direction": direct[0:9:4], "y_direction": direct[1:10:4],
                "observed_normal": [0, 0, -1], "normal_sign": -1,
                "calibration": source("test-calibration") if t == 1 else None,
                "artifacts": {tag: source(key + "-" + tag.lower()) for tag in row["artifacts"]},
            }
    return raw, packet, envelope, policy


def execute(argv):
    return subprocess.run(argv, capture_output=True, check=False, timeout=30)


def rights(receipt):
    assert receipt["authority"] == "DENY" and receipt["cartographer_mutation"] == "DENY"
    assert receipt["physical_reception"] == receipt["construction"] == "NOT_RUN"
    assert receipt["physical_admission"] == "PHYSICAL_ADMISSION_NOT_CONFIGURED"
    assert receipt["production_trust_pin"] == "EMPTY"
    assert receipt["cartographer_candidate_count"] == receipt["inspected_lots_by_tool"] == 0
    assert "ALLOW" not in json.dumps(receipt) and "PHYSICAL_MEASURED" not in json.dumps(receipt)


def campaign(tool, directory):
    matrix = json.loads(MATRIX_PATH.read_bytes())
    command = [str(tool), "--matrix", str(MATRIX_PATH)]
    published = execute(command)
    assert published.returncode == 0, published.stderr
    empty = json.loads(published.stdout)
    rights(empty)
    assert empty["status"] == "NOT_RUN" and {c["carrier"] for c in empty["carriers"]} == {"P64", "P66"}
    checks_count = sum(len(r["checks"]) for r in matrix["requirements"])
    assert sum(row["status"] == "MISSING" for c in empty["carriers"] for r in c["requirements"]
               for row in r["checks"]) == checks_count * 2
    matches = []
    cases = []
    for carrier in matrix["carriers"]:
        sheet = execute([*command, "--operator-template", carrier])
        assert sheet.returncode == 0, sheet.stderr
        worksheet = json.loads(sheet.stdout)
        assert worksheet["carrier"] == carrier and len(worksheet["entries"]) == checks_count
        assert worksheet["carrier_identity"] is None and worksheet["assembly_id"] is None
        mismatch_cases = directory / carrier
        raw, packet, envelope, policy = private_bundle(mismatch_cases, matrix, carrier)
        policy_path = mismatch_cases / "policy.json"
        policy_sha = write(policy_path, policy)

        def invoke(transforms=(), expected_sha=None, change_source=None, independent=False):
            candidate, submission = deepcopy(packet), deepcopy(envelope)
            for transform in transforms:
                transform(candidate, submission)
            submission["packet"] = {"path": "packet.json", "sha256": write(raw / "packet.json", candidate)}
            current = write(raw / "submission.json", submission)
            if change_source is not None:
                path = raw / change_source
                prior = path.read_bytes()
                path.write_bytes(b"ALTERED FIXTURE")
            try:
                args = ["--raw-root", str(raw), "--submission", "submission.json", "--current-sha256",
                        expected_sha or current, "--policy", str(policy_path), "--policy-sha256", policy_sha]
                result = execute([*command, *args])
                report = json.loads(result.stdout) if result.stdout else {}
                if report:
                    rights(report)
                if independent:
                    receipt = mismatch_cases / "receipt.json"
                    receipt.write_bytes(result.stdout)
                    confirm = execute([sys.executable, "-B", str(SOURCE_CHECK), "--matrix", str(MATRIX_PATH),
                                       "--receipt", str(receipt), *args])
                    assert confirm.returncode == 0, confirm.stderr.decode(errors="replace")
                    counter = json.loads(confirm.stdout)
                    assert counter["receipt_sha256"] == sha(result.stdout) and counter["authority"] == "DENY"
                    return result, report, counter
                return result, report
            finally:
                if change_source is not None:
                    path.write_bytes(prior)

        result, success, counter = invoke(independent=True)
        assert result.returncode == 0, result.stderr
        assert success["status"] == "ANALYZED" and success["classification"] == EXAMPLE
        assert counter["checked_measurements"] == checks_count
        matches.append({"carrier": carrier, "checks": checks_count, "worksheet_sha256": sha(sheet.stdout), **counter})
        if carrier != "P64":
            continue

        def change(check, path, value):
            def apply(bundle, submission):
                row = next(row for row in bundle["records"] if row["check_id"] == check)
                data = row if path[0] != "details" else submission["details"][row["record_id"]]
                keys = path if path[0] != "details" else path[1:]
                for key in keys[:-1]:
                    data = data[key]
                if value is None and keys[-1] in data and data[keys[-1]] is not None:
                    del data[keys[-1]]
                else:
                    data[keys[-1]] = value
            return apply

        outline = packet["records"][0]
        active = "isolator-outline"
        tests = [
            ("missing-file", "A7_SOURCE_MISSING_OR_REDIRECTED",
             [change(active, ("details", "artifacts", "FACE_BACK", "path"), "absent.fixture")]),
            ("altered-photo", "SOURCE_SHA256_MISMATCH", []),
            ("conflicting-lot", "LOT_VARIANT_OR_REVISION_MISMATCH",
             [change(active, ("identity", "lot_or_serial"), "TEST-OLDER-LOT")]),
            ("conflicting-revision", "LOT_VARIANT_OR_REVISION_MISMATCH",
             [change(active, ("identity", "revision"), "TEST-OLDER-REVISION")]),
            ("unknown-variant", "LOT_VARIANT_OR_REVISION_MISMATCH",
             [change(active, ("identity", "variant"), "TEST-UNKNOWN-VARIANT")]),
            ("manufacturer-revision", "MANUFACTURER_DOCUMENT_MISMATCH",
             [change(active, ("sources", "manufacturer_revision"), "FIXTURE-OLD-REV")]),
            ("bms-chemistry", "A7_CONFLICTING_FACT_bms_chemistry",
             [change("jbd-header", ("facts", "bms_chemistry"), "LIFEPO4")]),
            ("mixed-assembly", "A7_MIXED_ASSEMBLY_OR_CARRIER",
             [change(active, ("facts", "assembly_id"), "different-fixture")]),
            ("wrong-xlink-parent", "A7_XLINK_PARENT_MISMATCH",
             [change(active, ("frame", "parent"), matrix["carriers"]["P66"])]),
            ("nonrigid-frame", "NON_RIGID_FRAME",
             [change(active, ("frame", "local_to_parent", 0), 2)]),
            ("not-inverse", "FRAME_INVERSE_MISMATCH",
             [change(active, ("frame", "parent_to_local", 3), 7)]),
            ("noncollinear-required", "COLLINEAR_DATUM_DIRECTIONS",
             [change(active, ("details", "y_direction"), [1, 0, 0])]),
            ("source-normal", "DATUM_NORMAL_MISMATCH",
             [change(active, ("details", "normal_sign"), 1)]),
            ("datum-witness-origin", "DATUM_OBSERVATION_MISMATCH",
             [change(active, ("details", "origin_mm"), [100, 2, 3])]),
            ("incompatible-unit", "MEASUREMENT_UNIT_MISMATCH",
             [change(active, ("measurement", "unit"), "N")]),
            ("ambiguous-nc", "A7_CONFLICTING_FACT_nc_confirmed",
             [change("f40-wiring", ("facts", "nc_confirmed"), "UNKNOWN")]),
            ("no-uncertainty", "MISSING_FIELDS", [change(active, ("measurement", "uncertainty"), None)]),
            ("insufficient-margin-le", "A7_INSUFFICIENT_CONSERVATIVE_MARGIN",
             [change(active, ("measurement", "value"), 0.58)]),
            ("insufficient-margin-ge", "A7_INSUFFICIENT_CONSERVATIVE_MARGIN",
             [change("carrier-thickness", ("measurement", "value"), 0.32)]),
            ("fake-reviewer", "A7_REVIEW_MUST_USE_AUTHORIZED_CHANNEL",
             [change(active, ("review",), {"reviewer": "FAKE"})]),
            ("self-signed-test-review", "A7_REVIEW_MUST_USE_AUTHORIZED_CHANNEL",
             [change(active, ("review",), {"reviewer": "EXAMPLE_OPERATOR", "detached_signature": outline["sources"]["raw"]})]),
            ("stale-submission", "A7_STALE_OR_ALTERED_SUBMISSION",
             [change(active, ("measurement", "value"), 0.41)]),
            ("test-scope-escalation", "A7_INVALID_SUBMISSION_FIELDS",
             [lambda _packet, submission: submission.update(domain="CARTOGRAPHER_PRIVATE_CAD")]),
            ("synthetic-to-physical", "A7_EVIDENCE_CLASS_MISMATCH",
             [change(active, ("evidence_class",), "PHYSICAL_MEASURED")]),
            ("cord-still-connected", "A7_CORDS_MUST_BE_DETACHED",
             [change("f40-wiring", ("capture", "detached"), False)]),
        ]
        for name, reason, mutations in tests:
            verdict, report = invoke(mutations, expected_sha=success["submission_sha256"] if name == "stale-submission" else None,
                                     change_source=outline["sources"]["photo"]["path"] if name == "altered-photo" else None)
            assert verdict.returncode == 2, (name, verdict.stdout, verdict.stderr)
            observed = [row["reason"] for c in report.get("carriers", []) for requirement in c["requirements"]
                        for row in requirement["checks"] if row["status"] == "FAIL"]
            if observed:
                assert reason in observed, (name, reason, observed)
            else:
                assert reason in verdict.stderr.decode(errors="replace"), (name, reason, verdict.stderr)
            cases.append({"case": name, "status": "PASS", "refusal": reason, "exit_code": 2,
                          "construction": "NOT_RUN"})
    return {"schema": "v3.a7.adversarial/1", "classification": EXAMPLE, "status": "PASS", "cases": cases,
            "case_count": len(cases), "independent_receipts": matches, "empty_report_sha256": sha(published.stdout)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tool", type=Path, required=True)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="a7-") as temp:
        proof = campaign(args.tool.resolve(strict=True), Path(temp).resolve(strict=True))
    if args.out:
        write(args.out, proof)
    print(f"{proof['case_count']} refus attendus, deux porteurs et deux reçus vérifiés séparément.")
