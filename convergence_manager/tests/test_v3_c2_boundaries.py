"""Vérifie les gardes du contrat C.2 sur des copies de banc privées."""

import argparse
from copy import deepcopy
from pathlib import Path
import stat

from replay_v3_b1 import ROOT, digest, load, setup, write
from replay_v3_b2 import artifact, closure, invoke
from replay_v3_c2 import authority


def refused(args, case, profile, plan, fault):
    private = setup(case, profile, plan)
    if fault in ("XLink manquant", "XLink corrompu"):
        linked = next(name for name in sorted(profile["dependencies"]) if name != profile["entry"])
        file = private / linked
        file.chmod(stat.S_IREAD | stat.S_IWRITE)
        if fault == "XLink manquant":
            file.unlink()
        else:
            with file.open("ab") as stream:
                stream.write(b"invalid digest fixture")
    output = case / "output"
    argv = [args.core, "v3-build", "--root", ROOT, "--request", case / "plan.json",
            "--sandbox", private, "--output", output, "--freecad-python", args.freecad,
            "--t0-validator", args.t0]
    result = invoke(case, "build", list(map(str, argv)))
    receipt = output / "refusal.json"
    assert result.returncode in (2, 3) and receipt.is_file(), (fault, result.returncode, result.stderr)
    report = load(receipt)
    assert report["candidate_transactions"] == 0 and report["construction_result"] == "NOT_RUN", report
    assert not (output / "transaction").exists(), output
    return {"fault": fault, "exit_code": result.returncode, "status": report["status"], "reason": report["reason"],
            "construction_result": report["construction_result"], "candidate_transactions": report["candidate_transactions"],
            "receipt": artifact(receipt), "invocation": artifact(case / "build-invocation.json")}


def budget_refused(args, area, domain, profile, t1):
    area.mkdir()
    source = load(t1 / "T1-request.json")
    source["budget"]["max_counterchecks"] = source["budget"]["max_native"] + 1
    request, output = area / "request.json", area / "problem.json"
    write(request, source)
    model = ROOT / profile["source"] / profile["entry"]
    argv = [args.l3, "v3-problem", "--root", ROOT, "--request", request, "--output", output,
            "--domain", domain, "--model", model, "--observation", t1 / "reference-observation.json"]
    result = invoke(area, "budget", list(map(str, argv)))
    assert result.returncode != 0 and not output.is_file(), (result.returncode, result.stdout, result.stderr)
    return {"fault": "max_counterchecks supérieur à max_native", "exit_code": result.returncode,
            "stderr": result.stderr, "candidate_transactions": 0, "construction_result": "NOT_RUN",
            "invocation": artifact(area / "budget-invocation.json")}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("core", "l3", "freecad", "t0", "t1", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    area = args.output.resolve()
    t1 = args.t1.resolve(strict=True)
    assert area.is_relative_to(ROOT / ".runtime") and t1.is_relative_to(ROOT / ".runtime")
    area.mkdir(parents=True, exist_ok=False)
    domain_path, _, _, profile = authority("T1")
    seal = digest(domain_path)
    retained = load(t1 / "summary.json")["retained"]
    assert retained and len(retained["values"]["harnesses"]) == 2
    values = retained["values"]
    second = sorted(values["harnesses"])[-1]
    cases = {
        "cartographer-injection": ("Domaine cartographe fourni avec un sceau synthétique", {"domain": "CARTOGRAPHER_PRIVATE_CAD"}, {}),
        "foreign-lot": ("Lot fourni dans un plan de banc", {"lot_sha256": "1" * 64}, {}),
        "foreign-authority": ("Sceau d’un autre domaine", {"authority_sha256": "0" * 64}, {}),
        "missing-harness": ("Second câble absent", {}, {"harnesses": {name: row for name, row in values["harnesses"].items() if name != second}}),
        "support-outside-catalog": ("Ancrage hors du domaine scellé", {}, {"support_option": "unlisted"}),
        "radius-below-limit": ("Rayon du second câble inférieur à la limite", {}, {
            "harnesses": {**values["harnesses"], second: {**values["harnesses"][second], "bend_radius_mm": 0.01}}}),
        "broken-xlink": ("XLink manquant", {}, {}),
        "corrupted-xlink": ("XLink corrompu", {}, {}),
    }
    results = {}
    for name, (fault, fields, changed_values) in cases.items():
        plan = {"schema": "v3.mutation_plan/3", "domain": "SYNTHETIC_BENCH", "plan_id": name,
                "authority_sha256": seal, "domain_sha256": seal, "values": deepcopy(values) | changed_values}
        results[name] = refused(args, area / name, profile, plan | fields, fault)
    results["countercheck-budget"] = budget_refused(args, area / "countercheck-budget", domain_path, profile, t1)
    closure(ROOT / profile["source"], profile["dependencies"])
    write(area / "adversarial.json", {"schema": "v3.c2.admission_boundaries/1", "status": "PASS", "cases": results})
    print(f"{len(results)} refus C.2 contrôlés")


if __name__ == "__main__":
    main()
