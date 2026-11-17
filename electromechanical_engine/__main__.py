"""Commandes du moteur. Les écritures sont réservées aux répertoires de travail."""

import argparse
import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

from .contracts import (digest, digest_value, freeze, load, open_reference,
                        require, validate_candidate, write)
from .freecad import FreeCADAdapter, FreeCADError
from .metrics import measure, render_views, view_frame
from .search import check_corridors, compare_reports, explore, run_feedback
from .validation import validate


ADMISSIBLE = "VALIDE_GEOMETRIQUEMENT"


def check_reference(project, lock):
    require(open_reference(project)[2] == lock, "référentiel modifié pendant la campagne")


def plan_for(candidate, system, requirements, lock):
    validate_candidate(candidate, lock["reference_sha256"], system, requirements)
    return {"candidate": candidate, "system": system, "requirements": requirements}


def assess(plan, observed, lock):
    candidate, system, requirements = (plan[key] for key in ("candidate", "system", "requirements"))
    report = validate(system, requirements, candidate, observed)
    native_complete = (observed.get("reopened") is True and observed.get("recompute_ok") is True
                       and observed.get("invalid_objects") == [] and observed.get("broken_links") == [])
    architecture = check_corridors(system, requirements, candidate, observed if native_complete else {})
    if (candidate["family"] != "MATERIEL_CONSTANT" or any(candidate.get("changes", {}).values())
            or candidate.get("hypotheses")):
        architecture.append({"code": "V5.ARCHITECTURE", "status": "unknown", "criticality": "reserve",
                             "object": candidate["id"], "reason": "architecture_changes_unverified",
                             "evidence": {"changes": candidate.get("changes", {}),
                                          "hypotheses": candidate.get("hypotheses", [])}})
    report["findings"].extend(architecture)
    report["domains"]["V5"] = {status: sum(row["status"] == status for row in architecture)
                              for status in ("pass", "fail", "unknown")}
    if report["domains"]["V5"]["fail"]:
        report["status"] = "NON_CONFORME"
    elif report["status"] == ADMISSIBLE and report["domains"]["V5"]["unknown"]:
        report["status"] = "CANDIDAT_CONDITIONNEL"
    report.update(version=1, candidate_id=candidate["id"], reference_sha256=lock["reference_sha256"],
                  reference_files=lock["files"], candidate_sha256=digest_value(candidate),
                  native_sha256=observed["native_sha256"],
                  metrics=measure(system, requirements, observed, candidate))
    return report


def build_one(adapter, project, candidate, target, reference):
    system, requirements, lock = reference
    plan = plan_for(candidate, system, requirements, lock)
    observed = adapter.build(plan, target)
    check_reference(project, lock)
    report = assess(plan, observed, lock)
    write(target / "candidate.json", candidate)
    write(target / "observations.json", observed)
    write(target / "candidate_report.json", report)
    return report, observed


def validate_saved(adapter, project, target, output):
    system, requirements, lock = open_reference(project)
    candidate = load(target / "candidate.json")
    receipt = load(target / "candidate_report.json")
    plan = plan_for(candidate, system, requirements, lock)
    require(receipt.get("candidate_sha256") == digest_value(candidate)
            and receipt.get("reference_sha256") == lock["reference_sha256"]
            and receipt.get("native_sha256") == digest(target / "candidate.FCStd"),
            "le candidat sauvegardé diverge de son reçu de construction")
    observed = adapter.inspect(target, plan)
    require(receipt["native_sha256"] == observed["native_sha256"], "natif modifié pendant la validation")
    check_reference(project, lock)
    report = assess(plan, observed, lock)
    if output is not None:
        output.mkdir(parents=True, exist_ok=False)
        write(output / "observations.json", observed)
        write(output / "candidate_report.json", report)
        render_views(observed, output / "views", requirements)
    return report


def publish_json(path, data):
    with TemporaryDirectory(dir=path.parent, prefix=".pending-") as staging:
        staged = Path(staging) / path.name
        write(staged, data)
        staged.replace(path)


def run_campaign(adapter, project, space_path, output):
    reference = open_reference(project)
    system, requirements, lock = reference
    space = load(space_path)
    alternatives = explore(system, space, lock["reference_sha256"], requirements)
    for candidate in alternatives["candidates"]:
        validate_candidate(candidate, lock["reference_sha256"], system, requirements)
    output.mkdir(parents=True, exist_ok=False)
    context = {"version": 1, "reference_sha256": lock["reference_sha256"], "reference_files": lock["files"],
               "design_space_sha256": digest_value(space)}
    publish_json(output / "campaign_context.json", context)
    publish_json(output / "exploration.json", alternatives)
    attempt_dir = output / "attempts"
    attempt_dir.mkdir()
    observations = {}

    def evaluate(candidate):
        check_reference(project, lock)
        try:
            report, observed = build_one(adapter, project, candidate, output / candidate["id"], reference)
        except FreeCADError as exc:
            return {"version": 1, "candidate_id": candidate["id"], "reference_sha256": lock["reference_sha256"],
                    "status": "NON_VERIFIE", "findings": [{"code": "BUILD.NATIVE", "status": "unknown",
                                                         "reason": "native_build_unverified", "criticality": "reserve",
                                                         "object": candidate["id"], "evidence": {"error": str(exc)}}]}
        observations[candidate["id"]] = observed
        return report

    def record_attempt(index, attempt):
        check_reference(project, lock)
        publish_json(attempt_dir / f"{index:03d}.json", attempt)

    result = run_feedback(alternatives, evaluate, requirements["objectives"], record_attempt)
    frame = view_frame(observations.values())
    result["views"] = {key: render_views(observed, output / key / "views", requirements, frame)
                       for key, observed in observations.items()}
    result.update(context)
    result["environment"] = adapter.probe()
    check_reference(project, lock)
    publish_json(output / "campaign_report.json", result)
    return result


def cli_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--freecad-python", default=os.environ.get("FREECAD_PYTHON"), type=Path)
    parser.add_argument("--timeout", default=60, type=int, help="secondes par processus FreeCAD")
    subparsers = parser.add_subparsers(dest="command", required=True)

    freeze_cli = subparsers.add_parser("freeze", help="copier et empreinter un référentiel indépendant")
    freeze_cli.add_argument("--project", required=True, type=Path)
    freeze_cli.add_argument("--output", required=True, type=Path)
    subparsers.add_parser("probe", help="vérifier le Python FreeCAD et Part")
    extract = subparsers.add_parser("extract", help="isoler une fermeture XLink et inspecter ses natifs")
    extract.add_argument("--project", required=True, type=Path, help="racine des fichiers natifs")
    extract.add_argument("--entry", required=True, type=Path, help="natif principal relatif à la racine")
    extract.add_argument("--extra", action="append", default=[], help="dépendance auxiliaire relative")
    extract.add_argument("--output", required=True, type=Path)
    for name in ("explore", "run"):
        command = subparsers.add_parser(name, help="explorer les variantes" if name == "explore" else "exécuter la boucle")
        command.add_argument("--project", required=True, type=Path, help="référentiel gelé")
        command.add_argument("--space", required=True, type=Path, help="design_space.json")
        command.add_argument("--output", required=True, type=Path)
    for name in ("build", "validate"):
        command = subparsers.add_parser(name, help="construire un candidat" if name == "build" else "remesurer un candidat")
        command.add_argument("--project", required=True, type=Path, help="référentiel gelé")
        command.add_argument("--candidate", required=True, type=Path)
        command.add_argument("--output", required=name == "build", type=Path)
    compare = subparsers.add_parser("compare", help="comparer deux rapports sur le même périmètre")
    compare.add_argument("--project", required=True, type=Path)
    compare.add_argument("--baseline", required=True, type=Path)
    compare.add_argument("--candidate", required=True, type=Path)
    return parser


def report_code(report):
    return {ADMISSIBLE: 0, "NON_CONFORME": 2}.get(report["status"], 3)


def dispatch(args):
    name = args.command
    if name == "freeze":
        return freeze(args.project, args.output), 0
    if name == "explore":
        system, requirements, lock = open_reference(args.project)
        result = explore(system, load(args.space), lock["reference_sha256"], requirements)
        check_reference(args.project, lock)
        for candidate in result["candidates"]:
            validate_candidate(candidate, lock["reference_sha256"], system, requirements)
        args.output.mkdir(parents=True, exist_ok=False)
        for candidate in result["candidates"]:
            write(args.output / (candidate["id"] + ".json"), candidate)
        write(args.output / "exploration.json", result)
        return result, 0 if result["candidates"] else 3
    if name == "compare":
        _, requirements, lock = open_reference(args.project)
        baseline, candidate = load(args.baseline), load(args.candidate)
        require(baseline.get("reference_sha256") == candidate.get("reference_sha256") == lock["reference_sha256"],
                "rapports d'un autre référentiel")
        result = compare_reports(baseline, candidate, requirements["objectives"])
        return result, 0 if result["admissible"] else 3

    require(args.freecad_python and 1 <= args.timeout <= 600, "indiquer --freecad-python et un timeout de 1 à 600 s")
    adapter = FreeCADAdapter(args.freecad_python, args.timeout)
    if name == "probe":
        result = adapter.probe()
        return result, 0 if result["verified"] else 1
    if name == "extract":
        result = adapter.extract(args.project, args.entry, args.output, args.extra)
        write(args.output / "extraction_report.json", result)
        return result, 0 if result.get("recompute_ok") and not result.get("invalid_objects") and not result.get("broken_links") else 2
    if name == "run":
        result = run_campaign(adapter, args.project, args.space, args.output)
        return result, 0 if result["pareto"] else 3
    if name == "build":
        reference = open_reference(args.project)
        result, observed = build_one(adapter, args.project, load(args.candidate), args.output, reference)
        render_views(observed, args.output / "views", reference[1])
    else:
        result = validate_saved(adapter, args.project, args.candidate, args.output)
    return result, report_code(result)


def main():
    args = cli_parser().parse_args()
    try:
        result, code = dispatch(args)
    except (OSError, ValueError, TypeError, KeyError, FreeCADError) as exc:
        result, code = {"status": "ERREUR", "error": str(exc)}, 1
    print(json.dumps(result, ensure_ascii=True, allow_nan=False))
    return code


if __name__ == "__main__":
    sys.exit(main())
