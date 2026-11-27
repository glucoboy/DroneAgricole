"""Contre-mesure de l'obstacle C.3 sur des copies d'évaluation séparées."""
import argparse
from datetime import datetime
from pathlib import Path
from shutil import copyfile
import sys

from regressions import CHECKOUT, RUN, now, read, record, sha, write


OUTPUT = RUN / "review-c3"
FREECAD = Path("C:/Program Files/FreeCAD 1.1/bin/python.exe").resolve(strict=True)
MEASURER = CHECKOUT / "convergence_manager/native/v3_cross_measure.py"
PROFILE = CHECKOUT / "docs/electromechanical_v3/bench_c3_spatial/profile.json"


def artifact(path):
    return {"path": path.relative_to(CHECKOUT).as_posix(), "sha256": sha(path), "bytes": path.stat().st_size}


def verified(reference):
    path = (CHECKOUT / reference["path"]).resolve(strict=True)
    assert path.is_relative_to(CHECKOUT / ".runtime") and sha(path) == reference["sha256"], path
    return path


def measure(phase, candidate, dependencies, obstacle, expect_absent):
    work = OUTPUT / phase
    private = work / "copy"
    for name, expected in dependencies.items():
        origin = (candidate.parent / name).resolve(strict=True)
        assert origin.is_relative_to(candidate.parent) and sha(origin) == expected
        destination = private / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        copyfile(origin, destination)
        assert sha(destination) == expected
    entry = read(PROFILE)["entry"]
    assert candidate.name == entry and (private / entry).is_file()
    result = work / "observation.json"
    argv = [FREECAD, "-B", MEASURER, "--root", private, "--profile", PROFILE, "--output", result,
            "--external-obstacle", obstacle, "--expected-entry-sha256", sha(candidate)]
    if expect_absent:
        argv.append("--require-absent")
    process, command = record(f"c3-review-{phase}", argv, timeout=180)
    if process.returncode != 0:
        sys.stderr.buffer.write(process.stderr)
        raise RuntimeError(f"Contre-mesure FreeCAD {phase} terminée avec code {process.returncode}")
    observed = read(result)
    assert observed["status"] == "MEASURED"
    assert observed["copy_unchanged"] and observed["documents_closed"]
    assert observed["inputs_sha256"] == dependencies and observed["external_sha256"] == sha(obstacle)
    assert all(sha(candidate.parent / name) == sha(private / name) == expected
               for name, expected in dependencies.items())
    return observed, {"observation": artifact(result), "command": command, "source": artifact(candidate)}


def initial(handoff_path, lower, upper, reason):
    handoff_path = handoff_path.resolve(strict=True)
    handoff = read(handoff_path)
    freeze_path = verified(handoff["freeze"])
    freeze = read(freeze_path)
    summaries = ("summary", "candidate", "problem", "routes")
    assert all(handoff[name] == freeze["t1"][name] for name in summaries)
    summary = read(verified(handoff["summary"]))
    candidate = verified(handoff["candidate"])
    verified(handoff["problem"])
    verified(handoff["routes"])
    OUTPUT.mkdir(exist_ok=False)
    obstacle = {"id": "Int3IndependentC3Block", "min_mm": lower, "max_mm": upper}
    obstacle_path = OUTPUT / "obstacle.json"
    write(obstacle_path, obstacle)
    observed, proof = measure("t1", candidate, summary["retained"]["native_sha256"], obstacle_path, True)
    external = observed["external_obstacle"]
    tolerance = read(PROFILE)["model"]["validation"]["tolerances"]["volume_mm3"]
    assert external["presence"] == "HYPOTHETICAL"
    volumes = {name: row["intersection_mm3"] for name, row in external["harnesses"].items()}
    affected = sorted(name for name, volume in volumes.items() if volume > tolerance)
    assert affected, "Aucun câble T1 intersecté"
    issued = now()
    assert datetime.fromisoformat(issued) > datetime.fromisoformat(freeze["frozen_at_utc"])
    assert sha(freeze_path) == handoff["freeze"]["sha256"] and sha(candidate) == handoff["candidate"]["sha256"]
    payload = {"schema": "v3.c3.external_perturbation/1", "freeze_sha256": sha(freeze_path),
               "t1_root_sha256": sha(candidate), "t1_problem_sha256": handoff["problem"]["sha256"],
               "evaluator": "Agent indépendant des régressions V3-INT.3", "issued_at_utc": issued, "obstacle": obstacle}
    entry = OUTPUT / "perturbation.json"
    write(entry, payload)
    proof.update(handoff=artifact(handoff_path), perturbation=artifact(entry),
                 verified_payload=payload, geometry_reason=reason,
                 collision_mm3=volumes, volume_tolerance_mm3=tolerance, collision_harnesses=affected,
                 independent_reopening="PASS", same_closure=True)
    write(OUTPUT / "t1-receipt.json", proof)
    print(proof["perturbation"], volumes, flush=True)


def countercheck(summary_path, candidate):
    summary_path = summary_path.resolve(strict=True)
    summary = read(summary_path)
    candidate = candidate.resolve(strict=True)
    previous = read(OUTPUT / "t1-receipt.json")
    assert summary["phase"] == "T2" and summary["phase_pass"] and summary["finalized"]
    assert candidate == verified(summary["candidate"])
    verified(summary["routes"])
    assert sha(candidate) != previous["verified_payload"]["t1_root_sha256"]
    assert summary["external_perturbation"]["input"]["sha256"] == previous["perturbation"]["sha256"]
    observed, proof = measure("t2", candidate, summary["retained"]["native_sha256"],
                              OUTPUT / "obstacle.json", False)
    external = observed["external_obstacle"]
    assert external["presence"] == "SAVED_NATIVE"
    volumes = {name: row["intersection_mm3"] for name, row in external["harnesses"].items()}
    assert set(volumes) == set(previous["collision_mm3"])
    assert all(vol <= previous["volume_tolerance_mm3"] for vol in volumes.values())
    proof.update(summary=artifact(summary_path), perturbation=previous["perturbation"],
                 collision_mm3=volumes, collision_harnesses=[],
                 independent_reopening="PASS", same_closure=True)
    write(OUTPUT / "t2-receipt.json", proof)
    print(proof["observation"], volumes, flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest="phase", required=True)
    t1 = subs.add_parser("t1")
    t1.add_argument("handoff", type=Path)
    t1.add_argument("--lower", required=True, nargs=3, type=float)
    t1.add_argument("--upper", required=True, nargs=3, type=float)
    t1.add_argument("--reason", required=True)
    t2 = subs.add_parser("t2")
    t2.add_argument("summary", type=Path)
    t2.add_argument("candidate", type=Path)
    args = parser.parse_args()
    if args.phase == "t1":
        initial(args.handoff, args.lower, args.upper, args.reason)
    else:
        countercheck(args.summary, args.candidate)
