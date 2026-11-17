import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
from datetime import datetime

from electromechanical_engine.freecad import guard

ROOT = Path.cwd()
RUN = ROOT / ".runtime/v21-go3b"
PORTFOLIO = ROOT / "docs/verification/v21_go3a_candidates.json"


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def preflight():
    portfolio = read(PORTFOLIO)
    reference = portfolio["reference"]
    require(portfolio["status"] == "GO3A_EXPLORATION_READY" and portfolio["exploration_authorized"],
            "Porte d'exploration non ouverte.")
    for name, entry in reference["dependencies"].items():
        require(guard.sha256(ROOT / entry["path"]) == entry["sha256"], f"Dépendance divergent : {name}")
    gate = portfolio["verification"]["preflight"]
    release = ROOT / gate["qualified_root"]
    executable = ROOT / gate["executable"]["path"]
    require(guard.sha256(executable) == gate["executable"]["sha256"], "Binaire C divergent.")
    gel = ROOT / ".runtime/go3a-ref/gel/reference_lock.json"
    lock = read(gel)
    require(lock["reference_sha256"] == reference["reference_sha256"], "Gel divergent.")
    for name, sha in lock["files"].items():
        require(guard.sha256(gel.parent / name) == sha, f"Entrée du gel divergente : {name}")
    current = ROOT / reference["mechanical_root"]
    model = read(ROOT / reference["dependencies"]["system_model"]["path"])
    replay = read(ROOT / reference["dependencies"]["reference_replay"]["path"])
    closure = model["cad"]["native_sha256"] | replay["native"]["auxiliary_files"]
    require(len(closure) == 141 and closure[reference["entrypoint"]] == reference["entrypoint_sha256"], "Périmètre inattendu.")
    for name, sha in closure.items():
        require(guard.sha256(current / name) == sha, f"Source active divergente : {name}")
    closure["verification/construction_prototype.json"] = guard.sha256(current / "verification/construction_prototype.json")
    case_root = release / ".runtime" / datetime.now().strftime("go3b-%Y%m%d-%H%M%S-%f")
    case_root.mkdir()
    env = dict(os.environ)
    env["PATH"] = "C:/msys64/ucrt64/bin;" + env["PATH"]
    records = {}
    for candidate in portfolio["candidates"]:
        family = candidate["id"]
        src = candidate["preflight"]["request"]
        source = ROOT / src["path"]
        require(guard.sha256(source) == src["sha256"], f"Demande divergente : {family}")
        request = read(source)
        construction = json.dumps(candidate["construction"], ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(construction.encode("utf-8")).hexdigest()
        require(request["portfolio_candidate_id"] == family and
                request["construction_sha256"] == digest == candidate["preflight"]["construction_sha256"],
                f"Demande non liée à la construction : {family}")
        plan = case_root / (family + ".json")
        shutil.copy2(source, plan)
        target = case_root / family
        command = [str(executable), "preflight", "--root", str(release), "--source-release", "v2.1",
                   "--mode", "explore", "--plan", str(plan), "--output", str(target)]
        result = subprocess.run(command, env=env, capture_output=True, encoding="utf-8", timeout=90)
        require(result.returncode == 0, f"Porte {family} : {result.stdout} {result.stderr}")
        path = target / "preflight.json"
        receipt = read(path)
        require(receipt["verdict"] == "EXPLORATION_ALLOWED" and receipt["campaign_state"] == "PLANNED"
                and receipt["plan_sha256"] == src["sha256"] and not receipt["blocks"]
                and receipt["reference_sha256"] == lock["reference_sha256"]
                and receipt["source_files_verified"] == 180
                and len(receipt["evidence_gap"]) == 8
                and all(x["status"] == "INCONCLUSIVE" for x in receipt["evidence_gap"].values()),
                f"Porte fermée ou non rattachée : {family}")
        records[family] = {"argv": command, "exit_code": result.returncode, "sha256": guard.sha256(path),
                           "path": path.relative_to(ROOT).as_posix(), "receipt": receipt}
        print(family, receipt["verdict"], flush=True)
    write(RUN / "preflight.json", {"portfolio_sha256": guard.sha256(PORTFOLIO), "lock": lock,
          "lock_sha256": guard.sha256(gel), "checks": records, "source_hashes": closure})
    stage("baseline")


def stage(name):
    result = read(RUN / "preflight.json")
    reference = read(PORTFOLIO)["reference"]
    if name not in {"baseline", "commun", "consolidee"}:
        allowed = {case["id"] for candidate in read(PORTFOLIO)["candidates"]
                   if candidate["id"] in result["checks"] for case in candidate["construction"]["parameter_cases"]}
        require(name.removesuffix("-reprise") in allowed, f"Cas non autorisé : {name}")
    closure = result["source_hashes"]
    extras = [entry for entry in closure if not entry.lower().endswith(".fcstd")]
    receipt = guard.stage(ROOT / reference["mechanical_root"], reference["entrypoint"], RUN / name / "cad",
                          extras, {"candidate_id": name, "reference_sha256": result["lock"]["reference_sha256"]})
    require(receipt["inputs_sha256"] == closure, "Fermeture XML différente du gel.")
    print(name, len(receipt["inputs_sha256"]), "entrées copiées et vérifiées", flush=True)


if __name__ == "__main__":
    import sys

    if len(sys.argv) == 1:
        preflight()
    else:
        for name in sys.argv[1:]:
            stage(name)
