"""Injecter trois défauts sur des copies de banc C4, puis rouvrir et remesurer."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from electromechanical_engine.freecad import PROJECT, guard


PROFILE = PROJECT / "docs/electromechanical_v3/bench_b1_c4/profile.json"
MEASURER = PROJECT / "convergence_manager/native/v3_cross_measure.py"
PREDICTIONS = {
    "datum-plus-3mm": "Le datum de sortie A s’écarte de 3 mm du repère porté par l’équipement.",
    "permuted-pins": "Les contacts ma1 et ma2 portent chacun la broche de l’autre, avec leurs attaches conservées.",
    "stale-cable-brep": "La trajectoire mesurée garde sa longueur et ses bornes, la gaine sauvegardée diverge du balayage.",
}


def require(condition, reason):
    if not condition:
        raise RuntimeError(reason)


def read(path):
    return json.loads(path.read_bytes())


def write(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")


def proof(path):
    return {"path": path.relative_to(PROJECT).as_posix(), "sha256": guard.sha256(path)}


def closure(path, entry):
    return {file.relative_to(path).as_posix(): guard.sha256(file) for file in guard.dependencies(path, [entry])}


def private_path(path):
    original = path.absolute()
    result = guard.inside(PROJECT / ".runtime", original)
    require(result == original and result != PROJECT / ".runtime", "Répertoire privé canonique requis")
    current = original
    while current != PROJECT:
        reparse = getattr(current.lstat(), "st_reparse_tag", 0) if current.exists() else 0
        require(not current.is_symlink() and not reparse, f"Chemin redirigé : {current}")
        current = current.parent
    return result


def inject(path, fault, output):
    # Même amorçage Cables, sans appeler les mesures ni le constructeur.
    from convergence_manager.native.v3_cross_measure import App, native_hashes, reopen, setup_cables

    path, output = private_path(path), private_path(output)
    require(path.name == "injected-cad" and output.parent == path.parent, "Copie d’injection isolée requise")
    profile = read(PROFILE)
    entry = profile["entry"]
    before = native_hashes(path, entry)
    setup_cables()
    doc, documents, invalid = reopen(path, entry, before)
    require(not invalid, "Référence native invalide")
    try:
        if fault == "datum-plus-3mm":
            datum = doc.getObject(profile["model"]["validation"]["ports"]["port-a"]["frame"])
            offset = datum.AttachmentOffset
            offset.Base = offset.Base + App.Vector(3, 0, 0)
            datum.AttachmentOffset = offset
            doc.recompute()
        elif fault == "permuted-pins":
            peers = [obj for obj in doc.Objects if getattr(obj, "L2Id", None) in {"ma1", "ma2"}]
            require(len(peers) == 2, "Bornes ma1/ma2 introuvables")
            peers[0].PinName, peers[1].PinName = peers[1].PinName, peers[0].PinName
            doc.recompute()
        else:
            cable = doc.getObject(profile["model"]["occurrences"]["cordon"])
            stale = cable.Shape.copy()
            stale.translate(App.Vector(0, 0, 100))
            cable.Shape = stale
            cable.purgeTouched()
        doc.save()
    finally:
        for name in reversed(list(App.listDocuments())):
            App.closeDocument(name)
    after = native_hashes(path, entry)
    require(before.keys() == after.keys() and before[entry] != after[entry] and
            all(before[name] == after[name] for name in before if name != entry),
            "L’injection doit modifier le seul document principal")
    write(output, {"pid": os.getpid(), "worker_id": uuid4().hex, "fault": fault,
                   "input_sha256": before, "after_sha256": after, "documents": documents})


def call(argv, case, name):
    started = datetime.now(timezone.utc).isoformat()
    env = dict(os.environ, PYTHONUTF8="1", QT_QPA_PLATFORM="offscreen")
    result = subprocess.run([str(arg) for arg in argv], cwd=PROJECT, env=env, capture_output=True,
                            text=True, encoding="utf-8", errors="replace", timeout=60, check=False)
    trace = case / f"{name}-invocation.json"
    write(trace, {"argv": list(map(str, argv)), "started_at_utc": started, "exit_code": result.returncode,
                  "stdout": result.stdout, "stderr": result.stderr})
    require(result.returncode == 0, f"Commande non finalisée, voir {trace}")
    return proof(trace)


def measured_distance(authority, port):
    matrix = port["equipment_matrix"]
    local = authority["local_pose"]["translation_mm"]
    expected = [sum(matrix[row * 4 + col] * value for col, value in enumerate(local)) + matrix[row * 4 + 3]
                for row in range(3)]
    return math.dist(expected, port["matrix"][3:12:4])


def compare(fault, profile, reference, observed):
    tol = profile["tolerances"]
    if fault == "datum-plus-3mm":
        authority = profile["ports"]["port-a"]
        before = measured_distance(authority, reference["ports"]["port-a"])
        after = measured_distance(authority, observed["ports"]["port-a"])
        require(before <= tol["position_mm"] and abs(after - 3.0) <= tol["position_mm"],
                "Le décalage de 3 mm n’a pas été isolé")
        return {"port": "port-a", "reference_error_mm": before, "fault_error_mm": after,
                "max_error_mm": tol["position_mm"]}
    if fault == "permuted-pins":
        involved = ("ma1", "ma2")
        pinout = {name: profile["contacts"][name]["pin"] for name in involved}
        baseline = {name: reference["contacts"][name]["pin"] for name in involved}
        actual = {name: observed["contacts"][name]["pin"] for name in involved}
        require(baseline == pinout and actual == dict(zip(involved, reversed(list(pinout.values())))) and
                all(observed["contacts"][name]["mate"] == profile["contacts"][name]["receptacle"] for name in involved),
                "La permutation des broches n’a pas été isolée")
        return {"pinout": pinout, "fault_pinout": actual}
    before, after = (report["routes"]["cordon"] for report in (reference, observed))
    require(abs(before["length_mm"] - after["length_mm"]) <= tol["position_mm"] and
            all(math.dist(a, b) <= tol["position_mm"] for a, b in zip(before["endpoints_mm"], after["endpoints_mm"])) and
            before["sweep_difference_mm3"] <= tol["volume_mm3"] < after["sweep_difference_mm3"],
            "La gaine sauvegardée n’a pas divergé du parcours recomposé")
    return {"reference_sweep_difference_mm3": before["sweep_difference_mm3"],
            "fault_sweep_difference_mm3": after["sweep_difference_mm3"], "max_difference_mm3": tol["volume_mm3"],
            "reference_shape_sha256": before["saved_shape_sha256"], "fault_shape_sha256": after["saved_shape_sha256"]}


def run_suite(args):
    tx, output = private_path(args.transaction), private_path(args.output)
    candidate = tx / "cad"
    receipt = tx / "campaign.json"
    freecad = args.freecad.resolve(strict=True)
    profile = read(PROFILE)
    entry = profile["entry"]
    source = PROJECT / profile["source"]
    frozen = closure(source, entry)
    original = closure(candidate, entry)
    require(frozen == profile["dependencies"] and original == read(receipt)["native_sha256"] and
            read(receipt)["status"] == "PASS" and read(tx / "build.json")["status"] == "PASS",
            "Une transaction C4 admise et liée à son dossier natif est requise")
    output.mkdir(parents=True)
    predictions = output / "predictions.json"
    write(predictions, PREDICTIONS)
    reference_path = output / "reference.json"
    invocation = call([freecad, "-B", MEASURER, "--root", candidate, "--profile", PROFILE,
                       "--output", reference_path], output, "reference")
    reference = read(reference_path)
    cases = {}
    for fault in PREDICTIONS:
        directory = output / fault
        copy = directory / "injected-cad"
        guard.stage(candidate, entry, copy)
        for name in original:
            if name != entry:
                (copy / name).chmod(0o444)
        modified = directory / "injection.json"
        direct = call([freecad, "-B", __file__, "--inject", fault, "--root", copy,
                       "--output", modified], directory, "inject")
        measured = directory / "measurement.json"
        observed = call([freecad, "-B", MEASURER, "--root", copy, "--profile", PROFILE,
                         "--output", measured], directory, "measure")
        injected, measurement = read(modified), read(measured)
        require(injected["input_sha256"] == original and injected["after_sha256"] == measurement["inputs_sha256"] and
                measurement["status"] == "MEASURED" and measurement["copy_unchanged"] and
                measurement["sources_unchanged"] and injected["pid"] != measurement["pid"],
                f"Rapprochement de provenance non démontré : {fault}")
        values = compare(fault, profile["model"]["validation"], reference, measurement)
        cases[fault] = {"result": "DETECTED", "injection": proof(modified), "measurement": proof(measured),
                        "invocations": [direct, observed], "observations": values}
    require(closure(source, entry) == frozen and closure(candidate, entry) == original,
            "Une source ou le candidat de référence a changé")
    write(output / "adversarial.json",
          {"schema": "v3.b2.native_faults/1", "status": "PASS", "predictions": proof(predictions),
           "profile": proof(PROFILE), "measurer": proof(MEASURER), "freecad_sha256": guard.sha256(freecad),
           "reference": proof(reference_path), "reference_invocation": invocation, "constructor_receipt": proof(receipt),
           "authority_source_sha256": frozen, "original_candidate_sha256": original, "cases": cases})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--freecad", type=Path)
    parser.add_argument("--transaction", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--inject", choices=PREDICTIONS, help=argparse.SUPPRESS)
    parser.add_argument("--root", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.inject:
        inject(args.root, args.inject, args.output)
    else:
        if not args.freecad or not args.transaction:
            parser.error("--freecad et --transaction requis")
        run_suite(args)


if __name__ == "__main__":
    main()
