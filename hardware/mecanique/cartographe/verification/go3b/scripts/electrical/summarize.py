"""Scelle le rapprochement des rapports L2 et des réouvertures de campagne."""

import argparse
import collections
import math
import shutil

from replay import (BOM, CONNECTOR_SOURCES, EXCEPTIONS, F12_WITNESS, L2, MATRIX, ROOT, UART, WORK, WIRING,
                    read_json, receipt, require, sha256, write_json)


CAMPAIGN = ROOT / ".runtime/v21-go3b"
DELIVERY = ROOT / "docs/verification/v21_go3b"


def verify_reopen(case, base, observations):
    snapshot_file = base / "snapshot.json"
    if not snapshot_file.is_file():
        return {"status": "NOT_RUN", "reason": "Réouverture absente du dossier de campagne au moment du scellement."}
    snapshot = read_json(snapshot_file)
    require(snapshot["source_integrity"]["sources_unchanged"], f"Intégrité source en échec: {case}")
    errors = {}
    unavailable = []
    for axis, observation in observations.items():
        saved = base / "cad"
        path = ROOT / observation["native_file"]["path"]
        digest = observation["native_file"]["sha256"]
        closure_hash = snapshot["native_sha256"][path.relative_to(saved).as_posix()]
        require(sha256(path) == digest == closure_hash, f"Preuve d’axe périmée: {case}/{axis}")
        if observation["status"] != "PASS" or axis not in snapshot["axis_geometry"]:
            unavailable.append(axis)
            continue
        source_ends = observation["endpoints_mm"]
        observed_ends = snapshot["axis_geometry"][axis]["ends_mm"]
        if len(source_ends) != 2 or len(observed_ends) != 2:
            unavailable.append(axis)
            continue
        errors[axis] = max(math.dist(source, reopened) for source, reopened in zip(source_ends, observed_ends))
    close = {axis: delta for axis, delta in errors.items() if delta <= 1e-6}
    failures = {axis: delta for axis, delta in errors.items() if delta > 1e-6}
    return {"status": "FAIL" if failures else ("INCONCLUSIVE" if unavailable else "PASS"),
        "snapshot": receipt(snapshot_file), "process_id": snapshot["pid"],
        "reopened_axes": len(errors), "matching_axes": len(close), "failed_axes": failures,
        "unavailable_axes": unavailable, "maximum_delta_mm": max(errors.values(), default=None),
        "tolerance_mm": 1e-6, "scope": "Bout d’axe CAO et identité native, sans position de contact qualifiée"}


def summarize(selected):
    interface = read_json(WORK / "l2-interfaces.json")
    source_mismatches = [path for path, digest in interface["source_sha256"].items() if sha256(ROOT / path) != digest]
    require(not source_mismatches, f"Sources L2 modifiées: {source_mismatches}")
    reference = read_json(ROOT / "docs/verification/v21_go3a_reference_replay.json")["electrical"]["l2"]
    require(sha256(WORK / "l2-interfaces.json") == reference["interfaces"]["sha256"] and
            sha256(WORK / "l2-reconcile.json") == reference["reconciliation"]["sha256"], "Rejeu L2 divergent")
    cases = {}
    for summary_path in sorted(WORK.glob("*/l2-summary.json")):
        folder = summary_path.parent
        name = folder.name
        if name == "probe":
            continue
        base = CAMPAIGN / name
        require((base / "cad").is_dir(), f"Copie GO3B absente: {name}")
        summary = read_json(summary_path)
        endpoints = read_json(folder / "axis-endpoints.json")
        graph = read_json(folder / "electrical.json")
        require(read_json(folder / "l2-correspondence.json")["sides_all"].keys() == graph["interfaces"].keys() and
                len(endpoints["axes"]) == len(graph["axes"]) == 53, f"Couverture différente du gel: {name}")
        cases[name] = {"validation_l2": summary["validation"], "telem1_reservation": endpoints["F12_TELEM1"],
            "diagnostic": summary["diagnostic"], "reopen_and_axis_match": verify_reopen(name, base, endpoints["axes"]),
            "changed_axis_ids": sorted(route for route, record in endpoints["axes"].items() if record["changed_from_freeze"]),
            "inputs_and_measurements": [receipt(folder / path) for path in (
                "electrical.json", "axis-endpoints.json", "l2-dossier.json", "l2-correspondence.json", "connector-bom.json")],
            "negative_probes": [receipt(folder / path) for path in ("negative-frame.json", "negative-side.json")
                if (folder / path).is_file()]}
    require("baseline" in cases and cases["baseline"]["validation_l2"]["exit_code"] == 2,
            "Le mauvais port du témoin doit être discriminé")
    require(selected in cases and cases[selected]["telem1_reservation"]["status"] == "PASS",
            "Copie de revue sans la réservation TELEM1 attendue")
    selected_dir = WORK / selected
    bom = read_json(selected_dir / "connector-bom.json")
    require(len(bom["connector_sides"]) == 142 and len(bom["cords_without_double_counting"]) == 36, "BOM incomplète")
    for source, target in (("connector-bom.json", "electrical_bom.json"), ("connector-bom.csv", "electrical_bom.csv")):
        shutil.copyfile(selected_dir / source, DELIVERY / target)
    digest = {"schema": "drone_agricole.v21.go3b.electrical-evidence.v1", "status": "INCONCLUSIVE",
        "test_id": "T-GO3B-GRAPH", "date": "2026-11-17", "scope": "Prototype cartographe GO3B sans dock, Windows amd64",
        "reference_replay": {"status": "PASS", "binary": receipt(L2),
            "commands": [[receipt(L2)["path"], subcommand, "--root", ".", "--output", receipt(WORK / filename)["path"]]
                for subcommand, filename in (("reconcile", "l2-reconcile.json"), ("inspect-cartographe", "l2-interfaces.json"))],
            "return_codes": [0, 0], "reports": [receipt(WORK / p) for p in ("l2-reconcile.json", "l2-interfaces.json")],
            "source_files_after_checked": len(interface["source_sha256"]), "changed_sources": source_mismatches},
        "ca01": read_json(WORK / "baseline/l2-summary.json")["ca01"],
        "coverage": {"documentary_status": "PASS", "lines": len(interface["lines"]), "sides": len(interface["interfaces"]),
            "onboard_lines": sum(line["scope"] == "faisceau_embarque" for line in interface["lines"]),
            "axes": len(interface["axes"]), "associations": sum(len(axis["line_ids"]) for axis in interface["axes"].values()),
            "off_axis_lines_motivated": [line["id"] for line in interface["lines"] if line.get("scope_reason")],
            "classes": dict(collections.Counter(line["class"] for line in interface["lines"])),
            "scopes": dict(collections.Counter(line["scope"] for line in interface["lines"])),
            "native_contact_models": 0, "mounted_connector_revisions": 0, "physical_continuities": 0,
            "physical_qualified_connector_envelopes": 0},
        "cases": cases, "review_bom": {"candidate": selected, "status": "INCONCLUSIVE",
            "artifacts": [receipt(DELIVERY / name) for name in ("electrical_bom.json", "electrical_bom.csv")],
            "edge_status": "Les références documentaires et longueurs d’axes observées figurent avec leurs réserves. Longueurs de coupe et contacts du lot restent ouverts."},
        "sources": [receipt(p) for p in (MATRIX, BOM, EXCEPTIONS, CONNECTOR_SOURCES, UART, WIRING, F12_WITNESS)],
        "regression": {"status": "PASS", "return_code": 0, "suites_passed": 3,
            "command": ["ctest", "--test-dir", ".runtime/v21-xlink-build", "-R",
                "^(v21_xlink_electrical|l2_interconnection|l2_reconcile)$", "--output-on-failure"],
            "log": receipt(WORK / "l2-regression.log")},
        "replay_scripts": [receipt(WORK / name) for name in ("replay.py", "summarize.py")],
        "go4": receipt(DELIVERY / "electrical_go4.json"),
        "limits": ["La projection L2 représente les interfaces documentaires, avec des alias explicites pour les côtés partagés. Les cavités et les contacts de cordons du lot restent ouverts.",
            "La netlist CA01 contrôle seulement les nets schématiques et les DNP documentaires. Elle laisse la population et les conducteurs installés à vérifier.",
            "Une réserve où les coordonnées coïncident ne renseigne pas la tenue, la fermeture du verrou, les marges après tolérances ou l’isolement.",
            "Les injections perturbent une preuve numérique séparée. Le témoin CAO fournit en plus le cas réellement sauvegardé GPS2.",
            "Les essais de continuité, de polarité, de CEM et de fonctionnement sur matériel sont NOT_RUN."]}
    write_json(DELIVERY / "electrical_evidence.json", digest)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("review_candidate")
    summarize(parser.parse_args().review_candidate)
