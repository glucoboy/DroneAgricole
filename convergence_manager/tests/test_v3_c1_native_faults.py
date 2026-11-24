"""Réouvrir un banc C.1 sauvegardé après injection de défauts de couplage."""

import argparse
from copy import deepcopy
import os
from pathlib import Path
from uuid import uuid4

from test_v3_b2_native_faults import PROJECT, call, closure, guard, private_path, proof, read, require, write


VERIFIER = PROJECT / "convergence_manager/native/v3_verify.py"
FAULTS = {
    "mobile-port-stale-cable": {"L2_TOPOLOGY", "L4_DYNAMIC_BEND_RADIUS"},
    "wire-end-datum": {"L2_TOPOLOGY"},
    "floating-support": {"L4_SUPPORT_ANCHOR"},
    "wrong-carrier-face": {"L4_SUPPORT_ANCHOR"},
    "fastener-no-engagement": {"L4_SUPPORT_ANCHOR"},
}
NATIVE_FAULTS = {"mobile-port-stale-cable", "floating-support", "fastener-no-engagement"}


def inject(fault, source, job_path, output):
    from convergence_manager.native.v3_cross_measure import App, reopen, setup_cables

    source, job_path, output = map(private_path, (source, job_path, output))
    require(source.name == "injected-cad" and job_path.parent == output.parent == source.parent,
            "Copie d’injection distincte requise")
    job = read(job_path)
    entry = job["entry"]
    before = closure(source, entry)
    require(job["dependencies"] == before, "Empreintes divergentes avant injection")
    setup_cables()
    doc, _, invalid = reopen(source, entry, before)
    require(not invalid, "Le candidat initial contient des objets invalides")
    occurrences = job["model"]["occurrences"]
    try:
        if fault == "mobile-port-stale-cable":
            item = doc.getObject(occurrences["payload"].split("/")[-1])
            require(item.TypeId == "App::Link", "L’occurrence mobile doit rester un XLink")
            value = item.LinkPlacement
            value.Base += App.Vector(0, 3, 0)
            item.LinkPlacement = value
        else:
            name = "plate" if fault == "floating-support" else "stud"
            item = doc.getObject(occurrences[name].split("/")[-1])
            value = item.Placement
            value.Base += App.Vector(0, 0, 0.3 if name == "plate" else 3)
            item.Placement = value
        doc.recompute()
        doc.save()
    finally:
        for name in reversed(list(App.listDocuments())):
            App.closeDocument(name)
    after = closure(source, entry)
    require(after.keys() == before.keys() and before[entry] != after[entry] and
            all(before[name] == after[name] for name in before if name != entry),
            "L’injection doit modifier le seul document principal")
    write(output, {"pid": os.getpid(), "worker_id": uuid4().hex, "fault": fault,
                   "before_sha256": before, "after_sha256": after})


def check_fault(args, job, candidate, area, fault):
    copy = area / "injected-cad"
    guard.stage(candidate, job["entry"], copy)
    job = deepcopy(job)
    injected = None
    invocations = []
    if fault in NATIVE_FAULTS:
        initial_job = area / "initial-job.json"
        write(initial_job, job)
        injected = area / "injection.json"
        invocations.append(call(
            [args.freecad, "-B", __file__, "--inject", fault, "--root", copy,
             "--job", initial_job, "--output", injected], area, "inject"))
        job["dependencies"] = read(injected)["after_sha256"]
    else:
        rules = job["model"]["validation"]
        if fault == "wire-end-datum":
            port = rules["ports"]["port-a"]
            port["datum"] = port["frame"]
        else:
            rules["supports"]["plate"]["carrier_face"] = "Face5"
    injected_job, measured = area / "job.json", area / "measurement.json"
    write(injected_job, job)
    invocations.append(call([args.freecad, "-B", VERIFIER, "--root", copy, "--job", injected_job,
                             "--output", measured], area, "measure"))
    observation = read(measured)
    checks = {row["id"]: row for row in observation["checks"]}
    require(observation["status"] == "FAIL" and observation["reopened"] and observation["documents_closed"]
            and observation["inputs_sha256"] == job["dependencies"]
            and all(checks[name]["status"] == "FAIL" for name in FAULTS[fault]),
            f"{fault} non détecté après réouverture : {measured}")
    if injected:
        require(observation["pid"] != read(injected)["pid"], "Mesure non indépendante de l’injection")
    return {"result": "DETECTED", "injection": proof(injected) if injected else proof(injected_job),
            "measurement": proof(measured), "invocations": invocations,
            "checks": {name: checks[name] for name in sorted(FAULTS[fault])}}


def run_suite(args):
    tx, area = private_path(args.transaction), private_path(args.output)
    args.freecad = args.freecad.resolve(strict=True)
    job = read(tx / "candidate-job.json")
    candidate = tx / "cad"
    receipt, prior_verification = read(tx / "campaign.json"), read(tx / "candidate-validation.json")
    before = closure(candidate, job["entry"])
    require(receipt["status"] == prior_verification["status"] == "PASS" and job["stage"] == "candidate"
            and before == job["dependencies"] == receipt["native_sha256"]
            and all("datum" in rule for rule in job["model"]["validation"]["ports"].values()),
            "Un candidat couplé accepté est requis")
    area.mkdir(parents=True)
    cases = {fault: check_fault(args, job, candidate, area / fault, fault) for fault in FAULTS}
    require(closure(candidate, job["entry"]) == before, "Le candidat de référence a changé")
    write(area / "adversarial.json", {
        "schema": "v3.c1.native_faults/1", "status": "PASS", "cases": cases,
        "transaction": proof(tx / "campaign.json"), "verifier": proof(VERIFIER),
        "candidate_sha256": before, "freecad_sha256": guard.sha256(args.freecad),
    })


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for option in ("freecad", "transaction", "root", "job"):
        parser.add_argument(f"--{option}", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--inject", choices=sorted(NATIVE_FAULTS), help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.inject:
        inject(args.inject, args.root, args.job, args.output)
    else:
        if not args.freecad or not args.transaction:
            parser.error("--freecad et --transaction requis")
        run_suite(args)


if __name__ == "__main__":
    main()
