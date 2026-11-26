"""Prépare les entrées historiques de deux suites dans un répertoire de test jetable."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory


def digest(data):
    return hashlib.sha256(data).hexdigest()


def stage_sealed(checkout, workspace, name, expected):
    relative = Path(name)
    source = (checkout / relative).resolve(strict=True)
    if relative.anchor or ".." in relative.parts or not source.is_relative_to(checkout):
        raise ValueError(f"Source hors du checkout : {name}")

    data = source.read_bytes()
    observed = digest(data)
    if observed != expected:
        if relative.suffix in {".json", ".csv", ".py"}:
            lf = data.replace(b"\r\n", b"\n")
            if b"\r" not in lf:
                for representation in (lf, lf.replace(b"\n", b"\r\n")):
                    if digest(representation) == expected:
                        data = representation
                        break
        if digest(data) != expected:
            raise ValueError(f"Source scellée divergente : {name} ({observed}, attendu {expected})")
        print(f"Fins de ligne restaurées sur copie : {name} ({observed} -> {expected})", flush=True)

    target = workspace / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return target


def copy_file(checkout, workspace, name):
    target = workspace / name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(checkout / name, target)
    return target


def l2_command(checkout, workspace, binary):
    freeze = json.loads((checkout / "docs/verification/v3/a/freeze.json").read_bytes())
    go3_paths = (
        "docs/verification/go3a/GO3A_CONNECTOR_BOM.csv",
        "docs/verification/go3a/GO3A_INTERCONNECTION_MATRIX.csv",
        "docs/verification/go3a/GO3A_SYSTEM_MODEL.json",
        "docs/verification/go3b/GO3B_ADMISSION.json",
        "docs/verification/go3b/GO3B_INTERCONNECTION_COVERAGE.csv",
        "docs/verification/go3b/GO3B_SOURCE_MANIFEST.json",
    )
    for name in go3_paths:
        stage_sealed(checkout, workspace, name, freeze["input_sha256"][name])
    admission = json.loads((workspace / "docs/verification/go3b/GO3B_ADMISSION.json").read_bytes())
    proof_hash = admission["controles_admission"]["reconciliation_l2"]["sha256"]
    proof = stage_sealed(checkout, workspace, "docs/electromechanical_v2/L2_RECONCILIATION.json", proof_hash)
    sources = json.loads(proof.read_bytes())["source_sha256"]
    baseline = "docs/electromechanical_v2/BASELINE_MANIFEST.json"
    baseline_hash = next(row["sha256"] for row in freeze["historical_reports"] if row["path"] == baseline)
    if sources[baseline] != baseline_hash:
        raise ValueError(f"Les gels L2 et V3-A divergent pour {baseline}")
    for name, expected in sources.items():
        stage_sealed(checkout, workspace, name, expected)

    script = copy_file(checkout, workspace, "interconnection_engine/tests/test_reconcile.py")
    return [sys.executable, "-B", script, binary, "-v"]


def l1_command(checkout, workspace):
    proof = json.loads((checkout / "docs/verification/technical_research_l1.json").read_bytes())
    catalog_name = "docs/electromechanical_v2/L1_CARTOGRAPHE.json"
    catalog = stage_sealed(checkout, workspace, catalog_name, proof["input_sha256"][catalog_name])
    for source in json.loads(catalog.read_bytes())["sources"]:
        evidence = source["evidence"]
        name = evidence["artifact_path"]
        if name is None:
            continue
        # La fiche fabricant hors Git est présente dans le rejeu V3-D.
        if evidence["id"] == "E.F16.RADIUS.LOCAL" and not (checkout / name).exists():
            print(f"Fiche fabricant hors Git absente : {name}", flush=True)
            continue
        stage_sealed(checkout, workspace, name, evidence["sha256"])

    tests = "technical_research_engine/tests"
    shutil.copytree(checkout / tests, workspace / tests, ignore=shutil.ignore_patterns("__pycache__"))
    return [sys.executable, "-B", "-m", "unittest", "discover", "-s", "technical_research_engine/tests", "-v"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("suite", choices=("l1", "l2"))
    parser.add_argument("checkout", type=Path)
    parser.add_argument("binary", type=Path)
    args = parser.parse_args()
    checkout = args.checkout.resolve(strict=True)
    binary = args.binary.resolve(strict=True)
    with TemporaryDirectory(prefix=f"{args.suite}-sealed-") as directory:
        workspace = Path(directory)
        env = os.environ.copy()
        if args.suite == "l1":
            command = l1_command(checkout, workspace)
            python_paths = [str(checkout)]
            if env.get("PYTHONPATH"):
                python_paths.append(env["PYTHONPATH"])
            env["PYTHONPATH"] = os.pathsep.join(python_paths)
            env["TECHNICAL_RESEARCH_CORE"] = str(binary)
        else:
            command = l2_command(checkout, workspace, binary)
        print(f"Rejeu {args.suite} depuis la copie vérifiée avec {binary}", flush=True)
        return subprocess.run(command, cwd=workspace, env=env, check=False).returncode


if __name__ == "__main__":
    sys.exit(main())
