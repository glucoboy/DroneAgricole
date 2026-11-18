"""Rejoue le gel Q2 de qualification avec les outils corrigés, sur copies."""

import argparse
from pathlib import Path
import subprocess
import sys

from qualify_v21_interfaces import (
    ADAPTER, ARCHIVED_NATIVE, ROOT, RETURN_CODES, digest, native_summary, read, status_for, write,
)


ORACLE_SHA256 = "d209c8e11e3f428571f689e4b385d11a881f67c57fc3e42307a6aff62b1f6d80"
HISTORICAL_QUALIFICATION_SHA256 = "2f58b1bd4e8322255588889056873c9a294557d68465d0689c769332aafef615"
MATCHED_EXIT = "matched-fictional-exit"
SPOOFED_PROVENANCE = "cad-as-supplier-proof"


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def run(argv, log):
    with log.open("xb") as stream:
        return subprocess.run(argv, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT,
                              timeout=120).returncode


def findings_match(report, expected):
    return all(set(status_for(report["findings"], code, subject)).intersection(statuses)
               for code, subject, statuses in expected)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--original", type=Path, required=True)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--freecad", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    original, output = args.original.resolve(), args.output.resolve()
    require(original != ROOT and output.is_relative_to(ROOT / ".runtime"),
            "Utiliser le dépôt d'origine en lecture et un répertoire de résultat isolé")
    qualification = original / ".runtime/v21-qualification/q2/replay-02"
    oracle_path = qualification / "oracles.json"
    previous_path = qualification / "reports/qualification.json"
    require(digest(oracle_path) == ORACLE_SHA256 and digest(previous_path) == HISTORICAL_QUALIFICATION_SHA256,
            "Oracle ou preuve historique Q2 différents du gel de qualification")
    oracle, previous = read(oracle_path), read(previous_path)
    protected = {original / name: sha for name, sha in oracle["inputs_sha256"].items()}
    protected.update({oracle_path: ORACLE_SHA256, previous_path: HISTORICAL_QUALIFICATION_SHA256})
    for name, case in oracle["cases"].items():
        protected[original / case["input"]] = case["input_sha256"]
        protected[qualification / "reports" / f"{name}.json"] = previous["observations"][name]["report_sha256"]
    protected[ARCHIVED_NATIVE] = protected[original / ARCHIVED_NATIVE.relative_to(ROOT)]
    protected[ADAPTER] = digest(ADAPTER)
    protected[args.binary.resolve()] = digest(args.binary)
    checked_before = {str(path): digest(path) for path in protected}
    require(checked_before == {str(path): sha for path, sha in protected.items()},
            "Une source Q2 ou une preuve historique a changé")

    output.mkdir(parents=True, exist_ok=False)
    observations = {}
    commands = []
    for name, case in oracle["cases"].items():
        historical_report = read(qualification / "reports" / f"{name}.json")
        target = output / f"{name}.json"
        cmd = [str(args.binary.resolve()), "validate", str(original / case["input"]), "--output", str(target)]
        commands.append(cmd)
        code = run(cmd, output / f"{name}.log")
        if not target.is_file():
            observations[name] = {"test_status": "NOT_RUN", "process_code": code}
            continue
        report = read(target)
        ok = (report["input_sha256"] == case["input_sha256"] and report["status"] in case["accepted_results"]
              and code == RETURN_CODES[report["status"]] and findings_match(report, case["required_findings"]))
        detail = {}
        if name == MATCHED_EXIT:
            ok &= findings_match(report, [["INTERFACE_REFERENCE_POSE", "interface-a", ["FAIL"]],
                                           ["WIRE_EXIT", "cordon/a", ["FAIL"]]])
            side = report["native_plan"]["interfaces"][0]["interface_reference"]
            pose = side["poses"]["mate_contact_from_exit"]
            detail = {key: pose[key][column] for key, column in
                      (("expected_local", 11), ("observed_local", 11), ("expected_world", 3), ("observed_world", 3))}
            ok &= tuple(detail.values()) == (10, 7, 14, 11)
        if name == SPOOFED_PROVENANCE:
            detail = {"before": status_for(historical_report["findings"], "PART_PROVENANCE", "interface-a"),
                      "after": status_for(report["findings"], "PART_PROVENANCE", "interface-a"),
                      "origins": {part["part_id"]: part["provenance"] for part in report["candidate_bom"]}}
            ok &= detail["before"] == ["PASS"] and detail["after"] == ["INCONCLUSIVE"]
            ok &= all(detail["origins"][part] == "LOCAL_CAD" for part in ("embase", "fiche"))
        observations[name] = {"test_status": "PASS" if ok else "FAIL", "before": historical_report["status"],
                              "after": report["status"], "process_code": code, "detail": detail,
                              "report": target.name, "report_sha256": digest(target)}

    native = {}
    for name, target in (("nominal", output / "nominal.json"),
                         (MATCHED_EXIT, qualification / "reports" / f"{MATCHED_EXIT}.json")):
        directory = output / f"native-{name}"
        cmd = [sys.executable, "-B", str(ADAPTER), "run", str(target), str(directory),
               "--freecad", str(args.freecad)]
        commands.append(cmd)
        code = run(cmd, output / f"native-{name}.log")
        receipt = directory / "native_l2.json"
        if name == "nominal":
            native_report = read(receipt) if receipt.is_file() else {}
            measures = native_summary(native_report, oracle["oracle_native"]) if native_report else {}
            void = native_report.get("phases", {}).get("reopen", {}).get("faults", {}).get(
                "withdrawal_same_bounds_missing_volume", {})
            measures["withdrawal_same_bounds_missing_volume"] = void
            ok = (code == 0 and measures.get("oracle_match") is True and void.get("status") == "FAIL"
                  and void.get("bounds_cover_required") is True and void["missing_volume_mm3"] > 0)
            evidence = {"measurements": measures, "receipt_sha256": digest(receipt) if receipt.is_file() else None}
        else:
            reopen_log = directory / "reopen.log"
            message = "interface-a/exit (world) divergent : 3 mm, 0 deg"
            reached = reopen_log.is_file() and message in reopen_log.read_text(encoding="utf-8", errors="replace")
            ok = code != 0 and (directory / "build.json").is_file() and reached and not receipt.exists()
            evidence = {"reopened_in_freecad": reached, "native_receipt_published": receipt.exists(),
                        "reopen_log_sha256": digest(reopen_log) if reopen_log.is_file() else None}
        native[name] = {"test_status": "PASS" if ok else "FAIL", "process_code": code, **evidence}
    checked_after = {str(path): digest(path) for path in protected}
    integrity = checked_before == checked_after
    passed = integrity and all(item["test_status"] == "PASS" for item in (*observations.values(), *native.values()))
    write(output / "evidence.json", {"schema": "drone_agricole.v21.fix_a.q2.v1",
          "status": "PASS" if passed else "FAIL", "oracle_sha256": ORACLE_SHA256, "observations": observations,
          "native": native, "commands": commands, "integrity": integrity,
          "protected_sha256_before": checked_before, "protected_sha256_after": checked_after})
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
