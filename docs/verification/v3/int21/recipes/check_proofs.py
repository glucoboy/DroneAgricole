import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

workspace = Path.cwd()
first = workspace / ".runtime/i21a"
second = workspace / ".runtime/i21b"
run = first / ".runtime/run"
ref_l2 = workspace / ".runtime/v3-b2/historical/l2-sealed"
ref_xlink = workspace / ".runtime/v3-a/native-20261118-065605213/staged"
sys.path[:0] = [str(first), str(first / "tools")]
from electromechanical_engine.freecad import guard
from replay_sealed_test import l2_command, stage_sealed


def digest(data):
    return hashlib.sha256(data).hexdigest()


def load(path):
    return json.loads(path.read_bytes())


def sha(path):
    return digest(path.read_bytes())


def git(root, *args):
    return subprocess.check_output(["git", "-C", root, *args]).decode("utf-8").strip()


def compact_sha(values):
    return digest(json.dumps(values, sort_keys=True, separators=(",", ":")).encode("utf-8"))


def write(path, payload):
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def integrity(stage):
    seal_file = first / "docs/verification/v3/a/native_receipt.json"
    freeze = load(first / "docs/verification/v3/a/freeze.json")
    expected_receipt_hash = next(row["sha256"] for row in freeze["artifacts"]
                                 if row["path"] == "docs/verification/v3/a/native_receipt.json")
    assert sha(seal_file) == expected_receipt_hash
    seal = load(seal_file)
    expected = seal["inputs_sha256"]
    prefix = seal["source_prefix"]
    entry = Path(seal["entry"]).relative_to(prefix)
    native = {name for name in expected if name.lower().endswith(".fcstd")}
    assert len(expected) == 142 and len(native) == 137
    results = {}
    for name, root in (("checkout_a", first), ("checkout_b", second), ("V3_D", workspace), ("V3_A_scelle", ref_xlink)):
        base = (root if root == ref_xlink else root / prefix).resolve()
        closure = {path.relative_to(base).as_posix() for path in guard.dependencies(base, [entry])}
        assert closure == native
        observed = {path: sha(base / path) for path in expected}
        differences = {}
        for path, wanted in expected.items():
            if observed[path] == wanted:
                continue
            assert path not in native
            sealed = (ref_xlink / path).read_bytes()
            assert digest(sealed) == wanted
            assert (base / path).read_bytes() == sealed.replace(b"\r\n", b"\n")
            differences[path] = {"checkout_sha256": observed[path], "historical_sha256": wanted, "cause": "CRLF_TO_LF"}
        results[name] = {"entries": len(observed), "native_xlink_entries": len(closure),
                         "matches_sealed": len(observed) - len(differences),
                         "sha256_sorted_map": compact_sha(observed), "differences": differences}
    assert results["V3_D"] == results["V3_A_scelle"] and results["V3_D"]["matches_sealed"] == 142
    assert results["checkout_a"] == results["checkout_b"] and results["checkout_a"]["matches_sealed"] == 139
    base_revision = "07a65330360f58104d8cf3ffc1161017eac908b8"
    for checkout in (first, second):
        assert git(checkout, "diff", "--name-only", base_revision, "--", "hardware", "docs/verification",
                   "docs/electromechanical_v2", "docs/electromechanical_v3") == ""
    payload = {"receipt": "docs/verification/v3/a/native_receipt.json", "receipt_sha256": sha(seal_file),
               "checkout_git_base": base_revision, "protected_diff_against_base": [],
               "protected_bytes": results}
    if stage == "after":
        assert payload == load(run / "integrity-before.json"), "Une entrée protégée a changé"
        payload.update(status="PASS", same_before_and_after=True)
    write(run / f"integrity-{stage}.json", payload)
    print({name: value["matches_sealed"] for name, value in results.items()})


def run_command(args, cwd, log=None, env=None):
    result = subprocess.run(args, cwd=cwd, env=env, capture_output=True, check=False, timeout=90)
    if log:
        log.write_bytes(result.stdout + result.stderr)
    return result


def sealed_replays():
    proof = load(first / "docs/electromechanical_v2/L2_RECONCILIATION.json")
    logs = run / "logs"
    results = {}
    for label, checkout in (("A", first), ("B", second)):
        built = checkout / ".runtime/run/l3"
        l2 = built / "interconnection/interconnection_core.exe"
        l1 = built / "research/technical_research_core.exe"
        with TemporaryDirectory(prefix="int21-l2-") as tmp:
            target = Path(tmp)
            staged_command = l2_command(checkout, target, l2)
            staged_paths = sorted(path.relative_to(target) for path in target.rglob("*") if path.is_file())
            staged_paths.remove(staged_command[2].relative_to(target))
            assert len(staged_paths) == 115
            for name in staged_paths:
                assert (target / name).read_bytes() == (ref_l2 / name).read_bytes(), name
            replays = {}
            for scenario in ("reconcile", "inspect-cartographe"):
                original = run_command([l2, scenario, "--root", ref_l2], ref_l2)
                reconstructed = run_command([l2, scenario, "--root", target], target)
                assert original.returncode == reconstructed.returncode == 0
                assert original.stdout == reconstructed.stdout and original.stderr == reconstructed.stderr
                replays[scenario] = {"sha256": digest(original.stdout), "bytes": len(original.stdout)}
            assert json.loads(run_command([l2, "reconcile", "--root", target], target).stdout) == proof
            strict_checkout = run_command([l2, "reconcile", "--root", checkout], checkout)
            assert strict_checkout.returncode != 0 and b"SHA-256" in strict_checkout.stderr
            changed_name = "docs/verification/cartographe_action3_interconnexions.json"
            negative_source = target / "negative" / changed_name
            negative_source.parent.mkdir(parents=True)
            negative_source.write_bytes((checkout / changed_name).read_bytes().replace(b"W12", b"Z12", 1))
            assert negative_source.read_bytes() != (checkout / changed_name).read_bytes()
            try:
                stage_sealed(target / "negative", target / "reject", changed_name, proof["source_sha256"][changed_name])
            except ValueError as error:
                assert "Source scellée divergente" in str(error)
            else:
                raise AssertionError("Fixture sémantiquement altérée acceptée")
            assert not (target / "reject" / changed_name).exists()
        l2_commandline = [sys.executable, "-B", ref_l2 / "interconnection_engine/tests/test_reconcile.py", l2, "-v"]
        l2_result = run_command(l2_commandline, ref_l2, logs / f"sealed-l2-{label}.log")
        assert l2_result.returncode == 0 and b"Ran 7 tests" in l2_result.stderr
        l1_commandline = [sys.executable, "-B", "-m", "unittest", "discover", "-s", "technical_research_engine/tests", "-v"]
        l1_result = run_command(l1_commandline, workspace, logs / f"sealed-l1-{label}.log",
                                {**os.environ, "TECHNICAL_RESEARCH_CORE": str(l1)})
        assert l1_result.returncode == 0 and b"Ran 24 tests" in l1_result.stderr
        results[label] = {"revision": git(checkout, "rev-parse", "HEAD"),
                          "identical_staged_files": len(staged_paths), "l2_cli_outputs": replays,
                          "raw_l2_checkout": "REJECTED_SHA256", "mutated_fixture": "REJECTED_SHA256_BEFORE_TEST",
                          "l2_sealed": {"argv": list(map(str, l2_commandline)), "cwd": str(ref_l2), "binary_sha256": sha(l2), "unittests": 7, "exit_code": 0},
                          "l1_sealed": {"argv": l1_commandline, "cwd": str(workspace), "core_path": str(l1), "binary_sha256": sha(l1), "unittests": 24, "exit_code": 0}}
    write(run / "sealed-replays.json", {"status": "PASS", "V3_D_revision": git(workspace, "rev-parse", "HEAD"),
                                      "historical_L2_receipt_sha256": sha(ref_l2 / "docs/electromechanical_v2/L2_RECONCILIATION.json"),
                                      "runs": results})
    print("Sealed L2 7/7 & L1 24/24 on both rebuilt binaries")


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in {"before", "sealed", "after"}:
        raise SystemExit("Usage : check_proofs.py before|sealed|after")
    if sys.argv[1] == "sealed":
        sealed_replays()
    else:
        integrity(sys.argv[1])
