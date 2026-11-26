import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

root = Path.cwd()
run, freecad, core = (Path(item).resolve() for item in sys.argv[1:])
case = run / "bridge-boundaries"
case.mkdir()

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def read(path):
    return json.loads(path.read_bytes())

def record(name, command):
    argv = list(map(str, command))
    process = subprocess.run(argv, cwd=root, capture_output=True, timeout=90, check=False,
                             env={**os.environ, "PYTHONUTF8": "1", "QT_QPA_PLATFORM": "offscreen"})
    log = case / f"{name}.log"
    log.write_bytes(process.stdout + process.stderr)
    return {"argv": argv, "exit_code": process.returncode, "log_sha256": sha(log),
            "log": log.relative_to(root).as_posix(), "diagnostic": (process.stdout + process.stderr).decode("utf-8")}

campaign = run / "c2/t1/T1"
winner = read(campaign / "campaign.json")["retained"]["candidate_id"]
transaction = campaign / "candidates" / winner / "construction/transaction"
source = transaction / "cad"
job = transaction / "candidate-job.json"
expected = read(job)["dependencies"]
assert all(sha(source / path) == value for path, value in expected.items())
private = case / "cad"
shutil.copytree(source, private)
assert all(sha(private / path) == value for path, value in expected.items())
job_copy = case / job.name
shutil.copyfile(job, job_copy)
removed = "parts/Obstacle.FCStd"
assert removed in expected
(private / removed).rename(case / "withheld-obstacle.FCStd")
report = case / "validation.json"
loss = record("xlink-loss", [freecad, "-B", root / "convergence_manager/native/v3_verify.py",
                            "--root", private, "--job", job_copy, "--output", report])
result = read(report)
checks = {check["id"]: check for check in result["checks"]}
assert loss["exit_code"] == 0 and result["finalized"] and result["status"] == "INCONCLUSIVE"
assert not result["reopened"] and checks["REOPEN_XLINK"]["status"] == "NOT_RUN"
fault = checks["NATIVE_MEASUREMENT"]
assert fault["status"] == "INCONCLUSIVE" and "Obstacle.FCStd" in fault["details"]
assert all(sha(source / path) == value for path, value in expected.items())
loss.update(status="PASS", result="NOT_ADMITTED", failure=fault, xlink_reopen="NOT_RUN", missing_dependency=removed,
            immutable_original=expected, receipt_sha256=sha(report))
trust = record("trust-flag-outside-admission", [core, "v3-converge", "--a5-trust-sha256", "0" * 64])
assert trust["exit_code"] == 1 and "v3-admission ou v3-build" in trust["diagnostic"]
trust.update(status="PASS", result="REJECTED_BEFORE_CAMPAIGN")
sys.path.insert(0, str(root / "convergence_manager/tests"))
from types import SimpleNamespace

from test_v3_c2_boundaries import EXPECTED_REASONS, refused
from replay_v3_b1 import setup
from replay_v3_c2 import authority

domain, _, _, profile = authority("T1")
seal = sha(domain)
values = read(run / "c2/t1/summary.json")["retained"]["values"]
second = sorted(values["harnesses"])[-1]
plan = {"schema": "v3.mutation_plan/3", "domain": "SYNTHETIC_BENCH",
        "plan_id": "int2-diameter-override", "authority_sha256": seal, "domain_sha256": seal,
        "values": {**values, "harnesses": {**values["harnesses"],
            second: {**values["harnesses"][second], "diameter_mm": 0.5}}}}
EXPECTED_REASONS["int2-diameter-override"] = "Valeurs de parcours absentes ou non reconnues"
validator = run / "t0/cartographe-evidence.exe"
diameter = refused(SimpleNamespace(core=core, freecad=freecad, t0=validator),
                   case / "int2-diameter-override", profile, plan, "Diamètre substitué dans le plan")
guard_case = case / "trust-on-bench-plan"
plan["plan_id"] = guard_case.name
plan["values"] = values
bench_copy = setup(guard_case, profile, plan)
output = guard_case / "output"
trust_on_bench = record("trust-on-bench-plan", [core, "v3-build", "--root", root,
    "--request", guard_case / "plan.json", "--sandbox", bench_copy, "--output", output,
    "--freecad-python", freecad, "--t0-validator", validator, "--a5-trust-sha256", "0" * 64])
assert trust_on_bench["exit_code"] == 1 and "Contrat d'admission A.5 requis" in trust_on_bench["diagnostic"]
assert not list(output.iterdir())
trust_on_bench.update(status="PASS", result="REJECTED_BEFORE_CONSTRUCTION", candidate_transactions=0)

(case / "checks.json").write_text(json.dumps({"xlink_loss_after_build": loss, "foreign_trust_flag": trust, "diameter_override": diameter, "trust_options_on_bench_plan": trust_on_bench}, indent=2) + "\n",
                                   encoding="utf-8")
print("PASS: pièce XLink perdue sur copie privée, option d'autorité refusée hors admission.")

