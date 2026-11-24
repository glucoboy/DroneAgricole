"""Rejoue I, B.1, B.2 et C sans écrire dans leurs dossiers de preuve."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
import subprocess

from replay_v3_b1 import ROOT, digest, write
from replay_v3_b2 import artifact, invoke


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("core", "l3", "freecad", "python", "t0", "ctest", "build-l3", "build-l5", "output"):
        parser.add_argument("--" + key, type=Path, required=True)
    parser.add_argument("--historical-root", type=Path, required=True,
                        help="Extraction avec les octets A.2 scellés et la fermeture locale V3-A")
    args = parser.parse_args()
    area = args.output.resolve()
    if area.exists() or not area.is_relative_to(ROOT / ".runtime"):
        parser.error("Choisir une sortie neuve sous .runtime")
    area.mkdir(parents=True)
    python, core, l3, fc, t0, ctest = map(lambda p: str(p.resolve(strict=True)),
                                        (args.python, args.core, args.l3, args.freecad, args.t0, args.ctest))
    tests = ROOT / "convergence_manager/tests"
    bench = ROOT / "docs/electromechanical_v3"
    common = ["--core", core, "--freecad", fc, "--t0", t0]
    historical = args.historical_root.resolve(strict=True)
    historical_tests = historical / "convergence_manager/tests"
    if not area.is_relative_to(historical / ".runtime"):
        parser.error("Le dossier de résultats doit aussi rester sous .runtime du dépôt historique")

    def recorded(name, argv, result, prerequisite=True):
        if not prerequisite:
            return {"status": "NOT_RUN", "reason": "Le rejeu préalable a échoué."}
        started = datetime.now(timezone.utc)
        try:
            process = invoke(area, name, list(map(str, argv)), timeout=1200)
        except subprocess.TimeoutExpired:
            return {"status": "INCONCLUSIVE", "reason": "Expiration", "argv": list(map(str, argv)),
                    "started_utc": started.isoformat()}
        completed = datetime.now(timezone.utc)
        row = {"status": "PASS" if process.returncode == 0 and result.is_file() else "FAIL",
               "exit_code": process.returncode, "invocation": artifact(area / f"{name}-invocation.json"),
               "started_utc": started.isoformat(), "completed_utc": completed.isoformat(),
               "duration_seconds": (completed - started).total_seconds(),
               "result": artifact(result) if result.is_file() else None}
        print(name, row["status"], row["exit_code"], flush=True)
        return row

    def native_runs():
        b1, b2 = area / "b1", area / "b2"
        plans = [bench / name for name in ("bench_b1_c4/profile.json", "bench_b1_workholding/profile.json",
                                           "bench_b2_variations.json")]
        first = recorded("B.1", [python, "-B", tests / "replay_v3_b1.py", *common,
                                *[item for plan in plans for item in ("--profile", plan)], "--output", b1],
                         b1 / "replay.json")
        second = recorded("B.2", [python, "-B", tests / "replay_v3_b2.py", "--replay", b1 / "replay.json",
                                 "--freecad", fc, "--t0", t0, "--output", b2],
                          b2 / "index.json", first["status"] == "PASS")
        return {"B.1": first, "B.2": second}

    def scope_and_guards():
        a2, scope, guards = area / "a2", area / "i", area / "b1-boundary"
        first = recorded("A.2", [python, "-B", historical_tests / "verify_v3_a2_evidence.py", "--core", core, "--out", a2],
                         a2 / "integrity.json")
        second = recorded("V3-I", [python, "-B", historical_tests / "test_v3_i_scope.py", "--core", core, "--integrity", a2,
                                   "--out", scope], scope / "scope_checks.json", first["status"] == "PASS")
        third = recorded("B.1-guards", [python, "-B", tests / "test_v3_b1_boundary.py", *common, "--output", guards],
                         guards / "checks.json")
        return {"A.2": first, "I": second, "B.1-guards": third}

    with ThreadPoolExecutor(max_workers=3) as pool:
        b = pool.submit(native_runs)
        i = pool.submit(scope_and_guards)
        c_results = area / "historical-c"
        c = pool.submit(recorded, "V3-C", [python, "-B", tests / "replay_v3_c.py", *common,
                                          "--l3", l3, "--python", python, "--output", c_results],
                        c_results / "generalization.json")
        junit_l3, junit_l5 = area / "l3.xml", area / "l5.xml"
        l3_test = recorded("L3", [ctest, "--test-dir", args.build_l3.resolve(), "--output-on-failure",
                                  "--output-junit", junit_l3], junit_l3)
        l5_test = recorded("L5", [ctest, "--test-dir", args.build_l5.resolve(), "-R", "^(l5_|v3_graph_contract|l2_interconnection)",
                                  "--output-on-failure", "--output-junit", junit_l5], junit_l5)
        results = {"L3": l3_test, "L5": l5_test, **b.result(), **i.result(), "C": c.result()}
    inputs = {str(path): digest(Path(path)) for path in (python, core, l3, fc, t0, ctest)}
    write(area / "regressions.json", {"schema": "v3.c1.regressions/1", "tools_sha256": inputs, "tests": results})
    return 0 if all(row["status"] == "PASS" for row in results.values()) else 4


if __name__ == "__main__":
    raise SystemExit(main())
