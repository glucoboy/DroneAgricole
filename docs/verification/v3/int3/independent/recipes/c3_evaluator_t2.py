"""Évaluation indépendante d’une boîte OCCT après gel C.3 T1."""

from datetime import datetime, timezone
from pathlib import Path
import os
import shutil
import subprocess

from a6_review_runner import digest, read, write


root = Path.cwd().resolve()
output = root / ".runtime/c3-evaluator"
handoff_path = root / ".runtime/c3-review/T2-HANDOFF.json"
handoff = read(handoff_path)


def verify(record):
    path = (root / record["path"]).resolve(strict=True)
    assert path.is_relative_to(root / ".runtime/c3-review") and path.stat().st_nlink == 1
    assert digest(path) == record["sha256"]
    return path


freeze_path = verify(handoff["freeze"])
freeze = read(freeze_path)
entries = {name: verify(reference) for name, reference in freeze["t1"].items()}
assert all(handoff[name] == reference for name, reference in freeze["t1"].items())
assert len(freeze["inputs"]["files_sha256"]) > 0
summary = read(entries["summary"])
assert summary["phase_pass"] and summary["finalized"]
route = read(entries["routes"])["routes"]["cordon"]
edge = next(row for row in route["edges"] if row["type"] == "Line" and
            row["start_mm"][0] > 34.0 and row["end_mm"][0] < 46.0 and
            abs(row["start_mm"][2] - route["vertex_departure_mm"]) < 1e-6)
fraction = 0.56
center = [start + fraction * (end - start) for start, end in zip(edge["start_mm"], edge["end_mm"], strict=True)]
half_extents = [0.8, 0.54, 0.42]
obstacle = {"id": "Int3ReviewUpperStraightBlock", "min_mm": [round(c - h, 3) for c, h in zip(center, half_extents, strict=True)],
            "max_mm": [round(c + h, 3) for c, h in zip(center, half_extents, strict=True)]}
output.mkdir(exist_ok=False)
copy = output / "closure"
candidate = entries["candidate"]
closure = summary["retained"]["native_sha256"]
assert closure[candidate.name] == digest(candidate)
for filename, expected in closure.items():
    original = (candidate.parent / filename).resolve(strict=True)
    assert original.is_relative_to(candidate.parent) and original.stat().st_nlink == 1 and digest(original) == expected
    target = copy / filename
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(original, target)
    assert digest(target) == expected and target.stat().st_nlink == 1
box_file = output / "obstacle.json"
write(box_file, obstacle)
observation = output / "reopened-collision.json"
profile = root / "docs/electromechanical_v3/bench_c3_spatial/profile.json"
assert digest(profile) == freeze["inputs"]["files_sha256"][str(profile)]
freecad = Path("C:/Program Files/FreeCAD 1.1/bin/python.exe").resolve(strict=True)
measurer = root / "convergence_manager/native/v3_cross_measure.py"
assert digest(measurer) == freeze["inputs"]["files_sha256"][str(measurer)]
argv = [freecad, "-I", "-B", "-X", "utf8", measurer, "--root", copy, "--profile", profile, "--output", observation,
        "--external-obstacle", box_file, "--expected-entry-sha256", digest(candidate), "--require-absent"]
argv = list(map(str, argv))
started = datetime.now(timezone.utc)
proc = subprocess.run(argv, cwd=root, env={**os.environ, "QT_QPA_PLATFORM": "offscreen"},
                      capture_output=True, timeout=120)
finished = datetime.now(timezone.utc)
for stream in ("stdout", "stderr"):
    (output / f"{stream}.log").write_bytes(getattr(proc, stream))
write(output / "collision.command.json", {"argv": argv, "cwd": str(root), "exit_code": proc.returncode,
      "started_at_utc": started.isoformat(), "finished_at_utc": finished.isoformat()})
assert proc.returncode == 0, proc.stderr.decode(errors="replace")
measured = read(observation)
details = measured["external_obstacle"]
tolerance = read(profile)["model"]["validation"]["tolerances"]["volume_mm3"]
volumes = {name: row["intersection_mm3"] for name, row in details["harnesses"].items()}
assert measured["status"] == "MEASURED" and measured["copy_unchanged"] and measured["documents_closed"]
assert details["presence"] == "HYPOTHETICAL" and measured["inputs_sha256"] == closure
assert measured["external_sha256"] == digest(box_file) and set(volumes) == {"cordon", "cordon-b"}
assert volumes["cordon"] > tolerance and volumes["cordon-b"] <= tolerance
assert {name: digest(copy / name) for name in closure} == closure
assert {name: digest(candidate.parent / name) for name in closure} == closure
assert started > datetime.fromisoformat(freeze["frozen_at_utc"])
for reference in (handoff["freeze"], *freeze["t1"].values()):
    verify(reference)
request = {"schema": "v3.c3.external_perturbation/1", "issued_at_utc": datetime.now(timezone.utc).isoformat(),
           "evaluator": "V3-INT.3 revue indépendante, évaluateur A.6 distinct du pilote C.3",
           "freeze_sha256": digest(freeze_path), "t1_root_sha256": digest(candidate),
           "t1_problem_sha256": digest(entries["problem"]), "obstacle": obstacle}
perturbation = output / "perturbation.json"
write(perturbation, request)


def record(path):
    return {"path": path.relative_to(root).as_posix(), "sha256": digest(path), "bytes": path.stat().st_size}


write(output / "evaluator-receipt.json", {
    "schema": "v3.int3.independent_c3_perturbation/1", "status": "PASS", "request": request,
    "mandate_after_freeze": True, "frozen_at_utc": freeze["frozen_at_utc"], "handoff": record(handoff_path),
    "perturbation": record(perturbation), "obstacle": record(box_file), "observation": record(observation),
    "command": record(output / "collision.command.json"), "stdout": record(output / "stdout.log"),
    "stderr": record(output / "stderr.log"), "freecad": {"binary_sha256": digest(freecad), "environment": measured["environment"]},
    "geometry": {"target": "cordon", "edge": edge, "fraction_on_edge": fraction, "center_mm": center,
                 "half_extents_mm": half_extents, "volume_tolerance_mm3": tolerance, "intersection_mm3": volumes},
    "closure_sha256": closure, "closure_unchanged": True, "copy_unchanged": True,
})
print(record(perturbation), volumes, flush=True)
