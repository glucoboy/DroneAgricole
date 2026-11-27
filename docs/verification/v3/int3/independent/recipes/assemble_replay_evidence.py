"""Agrège les sorties locales réexécutées d'INT.3 sans copier les résultats de l'intégrateur."""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import xml.etree.ElementTree as ET


ROOT = Path.cwd()
RUNTIME = ROOT / ".runtime"
RUN = RUNTIME / "r"
BUILD = RUNTIME / "b"
STAGING = RUN / "review-evidence"
INTEGRATION = ROOT / "docs/verification/v3/int3/integration"


def load(path):
    return json.loads(path.read_bytes())


def artifact(path, relative_root=ROOT):
    content = path.read_bytes()
    return {"path": path.relative_to(relative_root).as_posix(),
            "sha256": hashlib.sha256(content).hexdigest(), "bytes": len(content)}


def write(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def invocation(logs, name):
    command = logs / f"{name}.command.json"
    log = logs / f"{name}.log"
    return {"command": load(command), "command_record": artifact(command), "log": artifact(log)}


def configuration(directory):
    result = {}
    allowed = {"CMAKE_CXX_STANDARD", "CMAKE_CXX_STANDARD_REQUIRED", "CMAKE_CXX_EXTENSIONS",
               "CMAKE_BUILD_TYPE", "CMAKE_GENERATOR", "CMAKE_CXX_COMPILER",
               "L5_FREECAD_PYTHON", "L5_T0_VALIDATOR", "L5_A6_FAULT_INJECTION",
               "L5_A5_PHYSICAL_TRUST_SHA256", "CMAKE_DISABLE_FIND_PACKAGE_OpenSSL"}
    for line in (directory / "CMakeCache.txt").read_text(encoding="utf-8").splitlines():
        name = line.partition(":")[0]
        if name in allowed:
            result[name] = line.partition("=")[2]
    assert result["CMAKE_CXX_STANDARD"] == "17" and result["CMAKE_CXX_STANDARD_REQUIRED"] == "ON"
    assert result["CMAKE_CXX_EXTENSIONS"] == "OFF", result
    return result


def build_evidence(identity):
    variants = {
        "t0": "cartographe-evidence.exe", "l3": "architecture_decision_core.exe", "l4": "validation_core.exe",
        "l5": "convergence_core.exe", "l5-no-crypto": "convergence_core.exe", "l5-faults": "convergence_core.exe",
    }
    builds = {}
    for name, binary in variants.items():
        directory = BUILD / name
        configure = invocation(BUILD / "logs", f"configure-{name}")
        build = invocation(BUILD / "logs", f"build-{name}")
        assert configure["command"]["exit_code"] == build["command"]["exit_code"] == 0
        options = configuration(directory)
        compile_path = directory / "compile_commands.json"
        commands = load(compile_path)
        standards = sorted({flag for row in commands for flag in re.findall(r"(?:^| )(-std=\S+)", row["command"])})
        assert not any(flag.startswith("-std=gnu") for flag in standards), standards
        result = {"configure": configure, "build": build, "cache_options": options,
                  "options_found_in_compile_commands": standards, "compile_commands": artifact(compile_path),
                  "executable": artifact(directory / binary)}
        if name.startswith("l5"):
            authority = next(row for row in commands if Path(row["file"]).name == "A6Transaction.cpp")["command"]
            assert "V3_A6_FREECAD" in authority and "V3_A6_T0" in authority and "V3_A6_CHECKOUT" in authority
            assert options["L5_FREECAD_PYTHON"] == "C:/Program Files/FreeCAD 1.1/bin/python.exe"
            assert Path(options["L5_T0_VALIDATOR"]).resolve() == (BUILD / "t0/cartographe-evidence.exe").resolve(strict=True)
            assert all(path.as_posix() in authority for path in
                       (Path(options["L5_FREECAD_PYTHON"]), Path(options["L5_T0_VALIDATOR"]), ROOT)), authority
            assert options["L5_A5_PHYSICAL_TRUST_SHA256"] == ""
            assert ("V3_A5_CRYPTO" in authority) == (name != "l5-no-crypto")
            assert ("V3_A6_FAULT_INJECTION" in authority) == (name == "l5-faults")
            result["flags_authority_confirmed"] = {"crypto": name != "l5-no-crypto", "faults": name == "l5-faults",
                                                  "tools_pinned": True, "checkout_pinned": True,
                                                  "production_trust": "EMPTY"}
        builds[name] = result
    support = [BUILD / "l3/research/technical_research_core.exe", BUILD / "l3/interconnection/interconnection_core.exe"]
    return {"schema": "v3.int3.independent_rebuild/1", "status": "PASS", **identity,
            "versions": load(RUN / "environment.json"),
            "build_driver": artifact(INTEGRATION / "recipes/replay_builds.py"),
            "initial_checkout": invocation(BUILD / "logs", "checkout"),
            "checked_out_revision": invocation(BUILD / "logs", "revision"),
            "builds": builds, "support_executables": [artifact(path) for path in support]}


def suite(name):
    logs = BUILD / "logs"
    result = invocation(logs, name)
    log_text = (logs / f"{name}.log").read_text(encoding="utf-8", errors="replace")
    junit = logs / f"{name}.xml"
    cases = []
    if junit.is_file():
        result["junit"] = artifact(junit)
        for case in ET.parse(junit).getroot().findall("testcase"):
            status = "PASS"
            if case.find("failure") is not None:
                status = "FAIL"
            if case.find("skipped") is not None:
                status = "NOT_RUN"
            cases.append({"name": case.get("name"), "status": status, "time_s": float(case.get("time"))})
    timeouts = re.findall(r"^(\d+): Test timeout computed to be: (\d+)", log_text, re.M)
    result.update(cases=cases, timeouts_s=[int(value) for _, value in timeouts],
                  timeout_reported=bool(re.search(r"\*\*\*Timeout|\(Timeout\)", log_text)))
    return result


def regression_evidence(identity):
    checks = ("ctest-l3", "ctest-l4", "ctest-l4-native", "ctest-l5", "ctest-t0", "ctest-t0-isolated-retry",
              "ctest-l5-isolated-retry", "ctest-empty-control", "ctest-historical-model")
    ctest = {name: suite(name) for name in checks if (BUILD / "logs" / (name + ".command.json")).is_file()}
    counts = {"ctest-l3": 5, "ctest-l4-native": 7, "ctest-l5": 12, "ctest-t0": 2}
    passes = {}
    for name, count in counts.items():
        last = ctest.get(name + "-isolated-retry") or ctest.get(name)
        passes[name] = bool(last and last["command"]["exit_code"] == 0 and len(last["cases"]) == count
                            and "--no-tests=error" in last["command"]["argv"]
                            and all(case["status"] == "PASS" for case in last["cases"]))
    assert ctest["ctest-t0"]["timeouts_s"] == [30, 30]
    assert ctest["ctest-empty-control"]["command"]["exit_code"] != 0 and ctest["ctest-empty-control"]["cases"] == []
    a5 = load(RUN / "a5-adversarial.json")
    crypto = load(RUN / "a5-no-crypto.json")
    assert a5["status"] == "PASS" and a5["case_count"] == len(a5["cases"])
    assert crypto["with_crypto"]["receipt"]["admission"]["decision"] == "ALLOW"
    assert crypto["without_crypto"]["receipt"]["reason"] == "REVIEW_NOT_CONFIGURED"
    assert all(crypto[key]["receipt"]["construction_result"] == "NOT_RUN" for key in crypto)
    sealed_path = RUN / "sealed-replays.json"
    sealed = load(sealed_path)
    assert sealed["status"] == "PASS" and sealed["l1"]["unittests"] == 24 and sealed["l2"]["unittests"] == 7
    f16_path = RUN / "l1-f16-control.json"
    f16 = load(f16_path)
    # Cette rubrique de la recette publiée décrit son ancienne première tentative.
    historical_first = f16.pop("preliminary_comparison")
    assert historical_first["commands"] == [], historical_first
    c2 = {}
    for label in ("t1", "t2", "t3"):
        summary_file = RUN / "c2" / label / "summary.json"
        if not summary_file.is_file():
            c2[label] = {"status": "NOT_RUN"}
            continue
        summary = load(summary_file)
        run = invocation(RUN / "logs", f"c2-{label.upper()}")
        finalized = summary["verdict"] == "V3_C_PASS" and summary["finalized"] and run["command"]["exit_code"] == 0
        assert load(RUN / "c2" / label / label.upper() / "t0-crosscheck.json")["exit_code"] == 0
        c2[label] = {"status": "PASS" if finalized else "FAIL", "summary": artifact(summary_file),
                      "command": run,
                      "proposals": summary["proposals"], "native_attempts": summary["native_attempts"],
                      "qualified_candidates": summary["qualified_candidates"], "retained": summary["retained"]}
    c2_review = RUN / "c2-review/independent_review.json"
    if c2_review.is_file():
        evaluation = load(c2_review)
        c2["final_validation"] = {"status": "PASS" if len(evaluation["checks"]) == 5 and all(evaluation["checks"].values()) else "FAIL",
                                  "checks": evaluation["checks"], "artifact": artifact(c2_review),
                                  "command": invocation(RUN / "logs", "c2-review")}
    else:
        c2["final_validation"] = {"status": "NOT_RUN"}
    for key, count in (("c2-boundaries", 9), ("c2-native-faults", 11)):
        evidence = RUN / key / "adversarial.json"
        report = load(evidence)
        target = report["cases"]
        run = invocation(RUN / "logs", key)
        assert len(target) == count and report["status"] == "PASS" and run["command"]["exit_code"] == 0
        if key == "c2-boundaries":
            for row in target.values():
                assert row["exit_code"] in (1, 2) and row["construction_result"] == "NOT_RUN"
                assert row["candidate_transactions"] == 0
        else:
            assert all(row["status"] == "DETECTED" and row["verification"] and row["invocations"]
                       for row in target.values())
        c2[key] = {"case_count": count, "status": "PASS", "artifact": artifact(evidence), "command": run}
    bridge_path = RUN / "bridge-boundaries/checks.json"
    bridge = load(bridge_path)
    bridge_run = invocation(RUN / "logs", "integration-boundaries")
    assert len(bridge) == 4 and bridge_run["command"]["exit_code"] == 0
    assert bridge["xlink_loss_after_build"]["status"] == "PASS"
    assert bridge["xlink_loss_after_build"]["result"] == "NOT_ADMITTED"
    assert bridge["xlink_loss_after_build"]["xlink_reopen"] == "NOT_RUN"
    c2["historical_XLink_refusal"] = {"command": bridge_run, "artifact": artifact(bridge_path),
                                   "xlink_loss_after_build": bridge["xlink_loss_after_build"]}
    return {"schema": "v3.int3.independent_regressions/1", **identity,
            "status": "PASS" if all(passes.values()) and all(c2[key]["status"] == "PASS"
                      for key in ("t1", "t2", "t3", "final_validation", "c2-boundaries", "c2-native-faults")) else "FAIL",
            "registered_criteria": passes, "ctest": ctest, "sealed": sealed, "sealed_evidence": artifact(sealed_path),
            "f16": {"observations": f16, "artifact": artifact(f16_path),
                    "excluded": "Ancienne comparaison préliminaire héritée dans les champs de la recette, aucune commande de cette ancienne tentative dans notre exécution."},
            "C2": c2, "C2_perturbation": artifact(RUNTIME / "c2-evaluator/perturbation.json"),
            "C2_perturbation_review": artifact(RUNTIME / "c2-evaluator/evaluation.json"),
            "A5": {"status": "PASS", "case_count": a5["case_count"],
                   "with_crypto": crypto["with_crypto"], "without_crypto": crypto["without_crypto"],
                   "adversarial": artifact(RUN / "a5-adversarial.json"),
                   "commands": [invocation(RUN / "logs", name) for name in ("a5-adversarial", "a5-no-crypto")]}}


STAGING.mkdir(exist_ok=True)
IDENTITY = {"tested_commit": load(INTEGRATION / "acceptance.json")["tested_commit"],
            "checkout_commit": git("rev-parse", "HEAD"), "observed_at_utc": datetime.now(timezone.utc).isoformat()}
write(STAGING / "independent_rebuild.json", build_evidence(IDENTITY))
write(STAGING / "regressions.json", regression_evidence(IDENTITY))
