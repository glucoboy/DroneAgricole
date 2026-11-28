"""Produit un obstacle T2 indépendant à partir des seuls natifs T1 gelés."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read(path):
    return json.loads(path.read_bytes())


def write(path, payload):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def checked_file(path, parent):
    require(path.absolute() == path.resolve(strict=True) and path.is_relative_to(parent) and
            path.is_file() and path.stat().st_nlink == 1, f"Fichier hors fermeture ou partagé : {path}")
    return path


def record(path, checkout):
    return {"path": path.relative_to(checkout).as_posix(), "sha256": digest(path), "bytes": path.stat().st_size}


def choose_box(routes):
    # Choose after reading the T1 route. Aim for an interior span away from connector leads.
    harness, route = next(iter(sorted(routes.items())))
    edges = route["edges"]
    viable = [edge for edge in edges[1:-1] if edge["type"] in {"Line", "LineSegment"} and edge["length_mm"] > 2]
    require(viable, "Aucun tronçon intérieur rectiligne disponible")
    edge = max(viable, key=lambda choice: choice["length_mm"])
    fraction = 0.56
    center = [left + fraction * (right - left) for left, right in zip(edge["start_mm"], edge["end_mm"], strict=True)]
    half = (0.60, 0.42, 0.35)
    return harness, edge, fraction, center, {
        "id": "C4IndependentMidspanBlock",
        "min_mm": [round(value - step, 3) for value, step in zip(center, half, strict=True)],
        "max_mm": [round(value + step, 3) for value, step in zip(center, half, strict=True)],
    }


def evaluate(checkout, handoff_path, output, profile, freecad):
    private = checkout / ".runtime"
    checked_file(handoff_path, private)
    run = handoff_path.parent
    require(output.parent == private and not output.exists() and not output.is_relative_to(run),
            "Sortie évaluateur neuve et indépendante requise")
    handoff = read(handoff_path)

    def verify(entry):
        path = checked_file(checkout / entry["path"], run)
        require(digest(path) == entry["sha256"] and ("bytes" not in entry or path.stat().st_size == entry["bytes"]),
                f"Empreinte T1 divergente : {path.name}")
        return path

    freeze_path = verify(handoff["freeze"])
    freeze = read(freeze_path)
    frozen_at = datetime.fromisoformat(freeze["frozen_at_utc"])
    require(frozen_at.utcoffset() == timezone.utc.utcoffset(frozen_at) and frozen_at < datetime.now(timezone.utc),
            "Horodatage UTC de gel T1 invalide")
    require(all(handoff[name] == item for name, item in freeze["t1"].items()), "Passation T1 et gel divergents")
    entries = {name: verify(item) for name, item in freeze["t1"].items()}
    summary = read(entries["summary"])
    require(summary["phase_pass"] and summary["finalized"], "T1 non admissible ou inachevée")
    candidate = entries["candidate"]
    closure = summary["retained"]["native_sha256"]
    require(closure[candidate.name] == digest(candidate), "Racine candidate hors de la fermeture gelée")
    measurer = checkout / "convergence_manager/native/v3_cross_measure.py"
    inputs = freeze["inputs"]["sha256"]
    for path in (profile, measurer):
        require(digest(path) == inputs[str(path.relative_to(checkout))], f"Source de mesure hors gel : {path.name}")
    require(read(profile)["entry"] == candidate.name, "Profil de mesure et racine divergents")
    harness, edge, fraction, center, obstacle = choose_box(read(entries["observation"])["routes"])

    output.mkdir()
    copy = output / "closure"
    for relative, expected in closure.items():
        original = checked_file(candidate.parent / relative, candidate.parent)
        require(digest(original) == expected, f"Dépendance candidate divergente : {relative}")
        target = copy / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(original, target)

    box = output / "obstacle.json"
    write(box, obstacle)
    observation = output / "reopened-collision.json"
    argv = list(map(str, (freecad, "-I", "-B", "-X", "utf8", measurer, "--root", copy, "--profile", profile,
                           "--output", observation, "--external-obstacle", box, "--expected-entry-sha256",
                           digest(candidate), "--require-absent")))
    started = datetime.now(timezone.utc)
    proc = subprocess.run(argv, cwd=checkout, env={**os.environ, "QT_QPA_PLATFORM": "offscreen"},
                          capture_output=True, timeout=120)
    finished = datetime.now(timezone.utc)
    (output / "stdout.log").write_bytes(proc.stdout)
    (output / "stderr.log").write_bytes(proc.stderr)
    command = output / "command.json"
    write(command, {"argv": argv, "exit_code": proc.returncode,
                    "started_utc": started.isoformat(), "finished_utc": finished.isoformat()})
    require(proc.returncode == 0, f"La mesure FreeCAD a échoué ({proc.returncode})")
    measured = read(observation)
    details = measured["external_obstacle"]
    tolerance = read(profile)["model"]["validation"]["tolerances"]["volume_mm3"]
    volumes = {name: value["intersection_mm3"] for name, value in details["harnesses"].items()}
    require(measured["status"] == "MEASURED" and measured["documents_closed"] and measured["copy_unchanged"] and
            measured["inputs_sha256"] == closure and measured["external_sha256"] == digest(box) and
            details["presence"] == "HYPOTHETICAL", "Mesure indépendante incomplète")
    require(harness in volumes and len(volumes) >= 2 and all(math.isfinite(v) for v in volumes.values()) and
            volumes[harness] > tolerance and all(v <= tolerance for h, v in volumes.items() if h != harness),
            f"L'obstacle n'intersecte pas uniquement la liaison ciblée : {volumes}")
    require(all(digest(copy / name) == expected and digest(candidate.parent / name) == expected
                for name, expected in closure.items()), "Fermeture native modifiée pendant la mesure")
    verify(handoff["freeze"])
    for item in freeze["t1"].values():
        verify(item)
    perturbation = output / "perturbation.json"
    request = {"schema": "v3.c4.external_perturbation/1", "issued_at_utc": datetime.now(timezone.utc).isoformat(),
               "evaluator": "Revue indépendante C.4, orchestrateur distinct du constructeur T1",
               "freeze_sha256": digest(freeze_path), "t1_root_sha256": digest(candidate),
               "t1_problem_sha256": digest(entries["problem"]), "obstacle": obstacle}
    write(perturbation, request)
    receipt = output / "external_perturbation_receipt.json"
    write(receipt, {"schema": "v3.c4.independent_perturbation/1", "status": "PASS", "request": request,
                    "frozen_at_utc": frozen_at.isoformat(), "handoff": record(handoff_path, checkout),
                    "perturbation": record(perturbation, checkout), "observation": record(observation, checkout),
                    "command": record(command, checkout), "freecad": measured["environment"],
                    "geometry": {"target_harness": harness, "edge": edge, "fraction": fraction, "center_mm": center,
                                 "intersection_mm3": volumes, "volume_tolerance_mm3": tolerance},
                    "closure_sha256": closure, "closure_unchanged": True})
    print(json.dumps({"perturbation": record(perturbation, checkout), "receipt": record(receipt, checkout),
                      "intersection_mm3": volumes}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("handoff", "output", "profile", "freecad"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    evaluate(Path.cwd().resolve(), args.handoff.absolute(), args.output.absolute(),
             args.profile.resolve(strict=True), args.freecad.resolve(strict=True))
