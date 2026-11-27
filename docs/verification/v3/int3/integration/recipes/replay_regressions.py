import hashlib
import json
import os
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory


RUN = Path(__file__).resolve().parent
CHECKOUT = RUN.parents[1]
WORKSPACE = CHECKOUT.parents[1]
HISTORIC_L2 = WORKSPACE / ".runtime/v3-b2/historical/l2-sealed"
HISTORIC_XLINK = WORKSPACE / ".runtime/v3-a/native-20261118-065605213/staged"
BASE = "27144abf9841ba6502d29f2f76b15ff33092d186"
LEGACY = "551db0d9c9cda8a7717aa4aa99b407b2861417b8"
sys.path[:0] = [str(CHECKOUT), str(CHECKOUT / "tools")]
from electromechanical_engine.freecad import guard
from replay_sealed_test import l1_command, l2_command, stage_sealed


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def sha(path):
    return digest(Path(path).read_bytes())


def read(path):
    return json.loads(path.read_bytes())


def write(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def git(root, *argv):
    return subprocess.check_output(["git", "-C", root, *argv]).decode("utf-8").strip()


def record(name, args, cwd=CHECKOUT, env=None, timeout=90):
    argv = list(map(str, args))
    started = now()
    result = subprocess.run(argv, cwd=cwd, env=os.environ if env is None else env,
                            capture_output=True, timeout=timeout)
    log = RUN / "logs" / f"{name}.log"
    log.write_bytes(result.stdout + result.stderr)
    receipt = {"argv": argv, "cwd": str(cwd), "started_utc": started, "finished_utc": now(),
               "exit_code": result.returncode, "stdout_sha256": digest(result.stdout),
               "stdout_bytes": len(result.stdout), "stderr_sha256": digest(result.stderr),
               "log": log.relative_to(CHECKOUT).as_posix(), "log_sha256": sha(log)}
    write(log.with_suffix(".command.json"), receipt)
    return result, receipt


def capture_reference_data():
    historic = read(CHECKOUT / "docs/verification/v3/int21/integrity.json")
    sha_receipt_path = historic["receipt"]
    freeze = read(CHECKOUT / "docs/verification/v3/a/freeze.json")
    wanted_receipt = next(row["sha256"] for row in freeze["artifacts"] if row["path"] == sha_receipt_path)
    assert sha(CHECKOUT / sha_receipt_path) == wanted_receipt == historic["receipt_sha256"]
    seal = read(CHECKOUT / sha_receipt_path)
    expected = seal["inputs_sha256"]
    prefix = seal["source_prefix"]
    entry = Path(seal["entry"]).relative_to(prefix)
    native = {name for name in expected if name.lower().endswith(".fcstd")}
    assert len(expected) == 142 and len(native) == 137
    assert git(WORKSPACE, "rev-parse", "HEAD") == LEGACY
    results = {}
    protected = [str(Path(prefix) / name) for name in expected] + [
        "docs/electromechanical_v2", "docs/verification/go3a", "docs/verification/go3b",
        "docs/verification/v3/a", "docs/verification/v3/int21",
    ]
    protected_diffs = git(CHECKOUT, "diff", "--name-only", BASE, "--", *protected).splitlines()
    assert protected_diffs == [], protected_diffs
    sources = (("integrated_checkout", CHECKOUT / prefix, "checkout_a"),
               ("historical_v3_d", WORKSPACE / prefix, "V3_D"),
               ("historical_v3_a_sealed", HISTORIC_XLINK, "V3_A_scelle"))
    for label, base, historic_label in sources:
        base = base.resolve(strict=True)
        closure = {path.relative_to(base).as_posix() for path in guard.dependencies(base, [entry])}
        assert closure == native, f"Fermeture XLink différente : {label}"
        observed = {path: sha(base / path) for path in sorted(expected)}
        differences = {}
        for path, wanted in expected.items():
            if observed[path] == wanted:
                continue
            assert path not in native
            sealed = (HISTORIC_XLINK / path).read_bytes()
            assert digest(sealed) == wanted
            assert (base / path).read_bytes() == sealed.replace(b"\r\n", b"\n")
            differences[path] = {"checkout_sha256": observed[path], "historical_sha256": wanted,
                                 "cause": "CRLF_TO_LF"}
        results[label] = {
            "entries": len(observed), "native_xlink_entries": len(closure),
            "matches_sealed": len(observed) - len(differences),
            "sha256_sorted_map": digest(json.dumps(observed, sort_keys=True, separators=(",", ":")).encode()),
            "differences": differences,
        }
        assert results[label] == historic["protected_bytes"][historic_label], label
        if label == "integrated_checkout":
            results[label]["observed_sha256"] = observed
    return {"tested_commit": git(CHECKOUT, "rev-parse", "HEAD"), "base_commit": BASE,
            "historical_v3_d_commit": LEGACY, "receipt": sha_receipt_path,
            "receipt_sha256": wanted_receipt, "protected_diff_against_base": protected_diffs,
            "protected_bytes": results}


def integrity(stage):
    data = capture_reference_data()
    write(RUN / f"reference-{stage}.json", {"observed_utc": now(), "data": data})
    if stage == "before":
        print("Références avant campagnes : 142 entrées et 137 XLink, carte conforme aux scellés.")
        return
    before = read(RUN / "reference-before.json")
    after = read(RUN / "reference-after.json")
    assert before["data"] == after["data"]
    target = RUN / "reference_integrity.json"
    write(target, {"schema": "v3.int3.reference_integrity/1", "status": "PASS",
                   "same_before_and_after": True,
                   "before": {"path": ".runtime/r/reference-before.json",
                              "observed_utc": before["observed_utc"],
                              "snapshot_sha256": sha(RUN / "reference-before.json")},
                   "after": {"path": ".runtime/r/reference-after.json",
                             "observed_utc": after["observed_utc"],
                             "snapshot_sha256": sha(RUN / "reference-after.json")},
                   "comparison": {"inputs": "142 entrées du reçu natif V3-A épinglé par freeze.json",
                                  "closure": "electromechanical_engine.freecad.guard.dependencies",
                                  "source_byte_comparison": "SHA-256 pour chaque entrée et carte triée",
                                  "eol": "Trois écarts CRLF→LF documentés par INT.2.1, réconciliés en mémoire"},
                   **data})
    print("Références après campagnes : les 142 entrées sont identiques aux empreintes avant.")


def sealed_replays(l1, l2):
    suite_tool = CHECKOUT / "tools/replay_sealed_test.py"
    pinned_proof = read(HISTORIC_L2 / "docs/electromechanical_v2/L2_RECONCILIATION.json")
    old = read(CHECKOUT / "docs/verification/v3/int21/sealed-replays.json")
    assert sha(HISTORIC_L2 / "docs/electromechanical_v2/L2_RECONCILIATION.json") == old["historical_L2_receipt_sha256"]
    base_env = os.environ.copy()
    base_env["TMP"] = base_env["TEMP"] = str(RUN / "tmp")
    result, l1_sealed = record("sealed-l1-pinned", [sys.executable, "-B", suite_tool, "l1", WORKSPACE, l1], env=base_env)
    assert result.returncode == 0 and b"Ran 24 tests" in result.stderr and b"skipped=" not in result.stderr
    l1_deposit, l1_checkout = record("sealed-l1-checkout", [sys.executable, "-B", suite_tool, "l1", CHECKOUT, l1],
                                    env=base_env)
    assert l1_deposit.returncode == 0 and b"Ran 24 tests" in l1_deposit.stderr and b"skipped=" not in l1_deposit.stderr
    result, l2_sealed = record("sealed-l2-integrated", [sys.executable, "-B", suite_tool, "l2", CHECKOUT, l2], env=base_env)
    assert result.returncode == 0 and b"Ran 7 tests" in result.stderr and b"skipped=" not in result.stderr
    result, l2_sealed_history = record("sealed-l2-pinned", [sys.executable, "-B",
                                HISTORIC_L2 / "interconnection_engine/tests/test_reconcile.py", l2, "-v"],
                                      cwd=HISTORIC_L2, env=base_env)
    assert result.returncode == 0 and b"Ran 7 tests" in result.stderr and b"skipped=" not in result.stderr
    with TemporaryDirectory(prefix="l2-compare-", dir=RUN / "tmp") as tmp:
        target = Path(tmp).resolve()
        staged_command = l2_command(CHECKOUT, target, l2)
        staged = sorted(path.relative_to(target) for path in target.rglob("*") if path.is_file())
        staged.remove(staged_command[2].relative_to(target))
        assert len(staged) == 115
        for name in staged:
            assert (target / name).read_bytes() == (HISTORIC_L2 / name).read_bytes(), name
        matrix = {}
        for scenario in ("reconcile", "inspect-cartographe"):
            original, reference = record(f"l2-{scenario}-pinned", [l2, scenario, "--root", HISTORIC_L2], cwd=HISTORIC_L2)
            copy, reconstruction = record(f"l2-{scenario}-staged", [l2, scenario, "--root", target], cwd=target)
            assert original.returncode == copy.returncode == 0
            assert original.stdout == copy.stdout and original.stderr == copy.stderr
            matched = {"sha256": digest(copy.stdout), "bytes": len(copy.stdout)}
            assert matched == old["runs"]["A"]["l2_cli_outputs"][scenario]
            if scenario == "reconcile":
                assert json.loads(copy.stdout) == pinned_proof
            matrix[scenario] = {"status": "PASS", "matches_bytes_int21": True, **matched,
                                "historical": reference, "reconstructed": reconstruction}
        strict, raw = record("l2-raw-checkout", [l2, "reconcile", "--root", CHECKOUT])
        assert strict.returncode != 0 and b"SHA-256" in strict.stderr
        changed_name = "docs/verification/cartographe_action3_interconnexions.json"
        negative_source = target / "negative" / changed_name
        raw_data = (CHECKOUT / changed_name).read_bytes()
        negative_source.parent.mkdir(parents=True)
        negative_source.write_bytes(raw_data.replace(b"W12", b"Z12", 1))
        assert negative_source.read_bytes() != raw_data
        try:
            stage_sealed(target / "negative", target / "reject", changed_name, pinned_proof["source_sha256"][changed_name])
        except ValueError as error:
            assert "Source scellée divergente" in str(error)
        else:
            raise AssertionError("Fixture sémantiquement altérée acceptée")
        assert not (target / "reject" / changed_name).exists()
    l1_source = read(WORKSPACE / "docs/electromechanical_v2/L1_CARTOGRAPHE.json")
    manufacturer = next(source["evidence"] for source in l1_source["sources"]
                        if source["evidence"]["id"] == "E.F16.RADIUS.LOCAL")
    artifact = manufacturer["artifact_path"]
    assert sha(WORKSPACE / artifact) == manufacturer["sha256"] and not (CHECKOUT / artifact).exists()
    write(RUN / "sealed-replays.json", {
        "status": "PASS", "tested_commit": git(CHECKOUT, "rev-parse", "HEAD"),
        "historical_v3_d_commit": LEGACY, "replay_tool_sha256": sha(suite_tool),
        "l1": {"unittests": 24, "binary_sha256": sha(l1), "pinned_historical_source": l1_sealed,
               "integrated_checkout_source": l1_checkout, "historic_off_git_manufacturer": {
                   "path": artifact, "sha256": manufacturer["sha256"], "used_in_pinned_replay": True,
                   "present_in_integrated_checkout": False}},
        "l2": {"unittests": 7, "binary_sha256": sha(l2), "reconstructed_source": l2_sealed,
               "pinned_historical_source": l2_sealed_history, "identical_staged_files": len(staged),
               "pinned_receipt_sha256": old["historical_L2_receipt_sha256"], "matrix": matrix,
               "raw_checkout_rejected_sha256": raw, "mutated_fixture": "REJECTED_SHA256_BEFORE_TEST"},
    })
    print("L1 24/24, L2 7/7, 115 fichiers identiques, matrices L2 conformes octet à octet.")


def f16_control(binary):
    historical = read(CHECKOUT / "docs/verification/v3/int21/l1-experiment.json")
    relative_route = "hardware/mecanique/cartographe/verification/routes_prototype.json"
    catalog_path = "docs/electromechanical_v2/L1_CARTOGRAPHE.json"
    results = {}
    with TemporaryDirectory(prefix="l1-f16-", dir=RUN / "tmp") as tmp:
        private = Path(tmp).resolve()
        fixture = private / "fixture"
        l1_command(CHECKOUT, fixture)
        route = fixture / relative_route
        catalog = fixture / catalog_path
        sealed = route.read_bytes()
        current = (CHECKOUT / relative_route).read_bytes()
        assert current == sealed.replace(b"\r\n", b"\n") and sealed != current
        runs = []
        for label, data in (("checkout_lf", current), ("sealed_crlf", sealed)):
            route.write_bytes(data)
            result = {"route_sha256": digest(data), "route_bytes": len(data), "passes": []}
            for directory, cwd in (("checkout", CHECKOUT), ("secondaire", private)):
                issues = {}
                for issue in ("F16-AXIS-ACTIVE", "F16-MOUNTED-BEND-RADIUS"):
                    identity = f"l1-f16-recheck-{label}-{directory}-{issue}"
                    invocation = [binary, "submit", "--root", fixture, "--store", private / identity,
                                  "--catalog", catalog, "--issue", issue]
                    process, command = record(identity, invocation, cwd=cwd, timeout=30)
                    assert process.returncode == 0
                    report = json.loads(process.stdout)
                    issues[issue] = {"outcome": report["outcome"], "value": report.get("value"),
                                     "source_hash_mismatch": b"SOURCE_HASH_MISMATCH" in process.stdout,
                                     "network": report.get("network"), "exit_code": process.returncode}
                    runs.append(command)
                result["passes"].append({"cwd": directory, "issues": issues})
            results[label] = result
        def compared_observations(values):
            comparable = deepcopy(values)
            for encoding in comparable.values():
                for run in encoding["passes"]:
                    for issue in run["issues"].values():
                        if issue["outcome"] == "UNKNOWN":
                            del issue["value"]["collected_at"]
            return comparable

        assert compared_observations(results) == compared_observations(historical["results"])
        assert sha(catalog) == historical["catalog_sha256"]
        write(RUN / "l1-f16-control.json", {"status": "PASS", "binary_sha256": sha(binary),
              "catalog_sha256": sha(catalog), "fixture_network": "OFFLINE_DEFAULT",
              "comparison_excludes": "collected_at des réponses UNKNOWN, horodatage de chaque nouveau calcul",
              "preliminary_comparison": {"status": "FAIL", "exit_code": 1,
                   "reason": "Comparaison stricte du champ horodaté collected_at des réponses UNKNOWN",
                   "commands": [read(path) for path in (RUN / "logs").glob("l1-*-F16-*.command.json")
                                if "recheck-" not in path.name]},
              "same_criteria_as_int21": True, "results": results, "commands": runs})
    print("F16 conforme au contrôle historique, deux fins de ligne et deux répertoires de lancement.")


if __name__ == "__main__":
    phase = sys.argv[1]
    if phase in ("before", "after"):
        integrity(phase)
    elif phase == "sealed":
        sealed_replays(*(Path(arg).resolve(strict=True) for arg in sys.argv[2:]))
    elif phase == "f16":
        f16_control(Path(sys.argv[2]).resolve(strict=True))
