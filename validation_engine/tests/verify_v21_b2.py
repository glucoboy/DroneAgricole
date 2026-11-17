"""Independent evidence checks for the V2.1 B.2 XLink campaign."""
from collections import Counter
from itertools import combinations
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import time

AUTHORITY = Path("docs/verification/v21_fix_b_coverage.json")
ORIGINALS_AUTHORITY = Path(".runtime/b-originals-comparison.json")
CONFIGURATION = Path("validation_engine/fixtures/xlink_cartographe.json")
T0 = Path("../fix-a/.runtime/build-t0/cartographe-evidence.exe")
START_CHECKPOINT = "36bf8ae7206ca979f8df121cce64c55f45ca149704db590149f17f017f467292"


def unique_map(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Clé dupliquée dans la preuve JSON : {key}")
        result[key] = value
    return result


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"), object_pairs_hook=unique_map)


def file_hash(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def hash_json(value):
    canonical = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def publish(path, value):
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temp.replace(path)


def verify_authority(artifact):
    file = Path(artifact["path"])
    assert file_hash(file) == artifact["sha256"], file
    return file


def check_inventory(inventory, native, report):
    assert inventory["finalized"] and inventory["inventory_complete"] and inventory["recompute_ok"]
    assert not inventory["broken_links"] and not inventory["invalid_objects"]
    assert inventory["before_sha256"] == inventory["after_sha256"] == native
    assert inventory["worker_id"] == report["closure"]["reopened_worker"] != report["closure"]["saved_worker"]
    assert inventory["pid"] == report["closure"]["reopened_pid"]
    assert inventory["occurrence_count"] == len(inventory["occurrences"])
    assert inventory["root"] == report["closure"]["root"]
    assert set(inventory["documents"]) == set(native)
    assert all(record["sha256"] == native[name] and not record["partial"] for name, record in inventory["documents"].items())
    assert len(inventory["measurement_identity_sha256"]) == 64
    for occurrence in inventory["occurrences"].values():
        if occurrence["status"] != "PASS":
            continue
        assert len(occurrence["matrix"]) == 16 and all(map(math.isfinite, occurrence["matrix"]))
        for kind, hash_key in (("object", "document_sha256"), ("definition", "definition_sha256")):
            name = occurrence[kind].split("#", 1)[0]
            assert occurrence[hash_key] == native[name], (kind, name)


def audit_filter(run, report, inventory, pairs):
    proof_path = run / report["geometry"]["aabb_exclusion_proof"]
    proof = read(proof_path)
    assert proof["measurement_key"] == report["closure"]["cache_key"]
    assert proof["inventory_sha256"] == file_hash(run / "inventory.result.json")
    criteria = report["criteria"]
    cutoff = criteria["clearance_mm"] + criteria["distance_tolerance_mm"]
    assert proof["cutoff_mm"] == cutoff and criteria["contacts"] == []
    visible = {name: occurrence for name, occurrence in inventory["occurrences"].items()
               if occurrence["visible"] and occurrence["terminal_shape"] and occurrence["status"] == "PASS"}
    boxes = {name: row["bounds_mm"] for name, row in visible.items()}
    assert all(math.isfinite(lo) and math.isfinite(hi) and lo <= hi
               for box in boxes.values() for lo, hi in zip(*box))
    expected = set()
    exclusions = {}
    for a, b, value in proof["exclusions"]:
        key = tuple(sorted((a, b)))
        assert key not in exclusions and math.isfinite(value) and value > cutoff
        exclusions[key] = value
    min_margin = math.inf
    for a, b in combinations(sorted(visible), 2):
        if "route" not in visible[a] and "route" not in visible[b]:
            continue
        lo_a, hi_a = boxes[a]
        lo_b, hi_b = boxes[b]
        distance = math.hypot(*(max(0.0, lo - upper, lower - hi)
                                for lo, hi, lower, upper in zip(lo_a, hi_a, lo_b, hi_b)))
        key = (a, b)
        expected.add(key)
        if key in exclusions:
            value = exclusions[key]
            assert cutoff < value <= distance, (key, cutoff, value, distance)
            min_margin = min(min_margin, value - cutoff)
    candidate_keys = {tuple(sorted((row["task"]["a"], row["task"]["b"]))) for row in pairs.values()}
    assert len(candidate_keys) == len(pairs) == 1609
    assert len(expected) == 28514 and len(exclusions) == 26905
    assert expected == candidate_keys | exclusions.keys() and candidate_keys.isdisjoint(exclusions)
    return {"expected": len(expected), "candidate_pairs": len(candidate_keys), "exclusions": len(exclusions),
            "method": "Énumération indépendante des combinaisons et recalcul math.hypot des écarts entre AABB mondiales",
            "cutoff_mm": cutoff, "minimum_excluded_margin_mm": min_margin, "proof_sha256": file_hash(proof_path)}


def verify_t0(run, log):
    env = dict(os.environ)
    env["PATH"] = "C:/msys64/ucrt64/bin;" + env["PATH"]
    command = [str(T0.resolve()), "validate", str(run), "."]
    with log.open("wb") as output:
        execution = subprocess.run(command, env=env, stdout=output, stderr=subprocess.STDOUT, timeout=60, check=False)
    assert execution.returncode == 0, log
    return {"command": command, "exit_code": execution.returncode, "log_sha256": file_hash(log)}


def observations_for(run, report, inventory, t0_artifacts, fresh):
    workers = set()
    for name, digest in t0_artifacts.items():
        if not name.startswith("batch") or not name.endswith(".result.json"):
            continue
        result = read(run / name)
        request_name = name.replace(".result.", ".request.")
        request = read(run / request_name)
        assert result["request_sha256"] == t0_artifacts[request_name]
        assert request["action"] == "measure" and result["finalized"]
        assert request["criteria"] == report["criteria"] and request["cache_key"] == report["closure"]["cache_key"]
        assert result["measurement_identity_sha256"] == request["measurement_identity_sha256"] == inventory["measurement_identity_sha256"]
        assert result["environment"] == request["environment"] == inventory["environment"]
        assert result["before_sha256"] == result["after_sha256"] == request["native_sha256"] == inventory["after_sha256"]
        assert result["worker_id"] not in workers and result["worker_id"] != inventory["worker_id"]
        workers.add(result["worker_id"])
        assert len(request["tasks"]) == len(result["observations"])
        for task, row in zip(request["tasks"], result["observations"], strict=True):
            assert task == row["task"] and row["worker_pid"] == result["pid"]
            assert row["cache_key"] == request["cache_key"]
            for key in ("a", "b") if task["kind"] == "pair" else ("a",):
                occurrence = inventory["occurrences"][task[key]]
                assert occurrence["terminal_shape"] and len(occurrence["shape_sha256"]) == 64
            origin = {"batch": name, "batch_sha256": digest, "request_sha256": result["request_sha256"],
                      "worker_id": result["worker_id"], "inventory_identity_sha256": result["measurement_identity_sha256"]}
            fresh.setdefault(task["id"], []).append((row, origin))


def inspect_checkpoint(run, expected_digest, previous):
    checkpoint_path = run / "checkpoint.json"
    assert file_hash(checkpoint_path) == expected_digest
    checkpoint = read(checkpoint_path)
    assert checkpoint["schema"] == "drone-agricole.v21.xlink.checkpoint.v1"
    report = read(run / "campaign.json")
    assert report["finalized"] and report["closure"]["reopened"] and report["closure"]["integrity"]["sources_unchanged"]
    assert checkpoint["measurement_key"] == report["closure"]["cache_key"]
    assert report["checkpoint"]["sha256"] == expected_digest
    assert report["checkpoint"]["previous_sha256"] == previous
    inventory = read(run / "inventory.result.json")
    check_inventory(inventory, report["closure"]["saved_sha256"], report)
    assert report["criteria"] == read(CONFIGURATION)["criteria"]
    assert report["pins"]["configuration"] == file_hash(CONFIGURATION)
    assert report["pins"]["criteria"] == file_hash(report["criteria"]["source"])
    manifest = read(run / "artifacts.json")
    hashes = {item["path"]: item["checksum_sha256"] for item in manifest["items"]}
    assert len(hashes) == len(manifest["items"])
    assert all(file_hash(run / name) == digest for name, digest in hashes.items())
    assert hashes["checkpoint.json"] == expected_digest
    assert report["checkpoint"]["observations"] == len(checkpoint["observations"])
    checks = {row["task"]["id"]: row for row in report["geometry"]["checks"]}
    assert len(checks) == len(report["geometry"]["checks"])
    assert all(task_id == hash_json({key: value for key, value in row["task"].items() if key != "id"})
               for task_id, row in checks.items())
    pairs = {task_id: row for task_id, row in checks.items() if row["task"]["kind"] == "pair"}
    assert len(pairs) == 1609
    assert {task_id: row["native_evidence"] for task_id, row in checks.items()
            if row["native_evidence"] is not None} == checkpoint["observations"]
    return report, inventory, checkpoint, pairs, hashes


def verified_originals():
    authority = read(ORIGINALS_AUTHORITY)
    before = Path(authority["before_manifest"])
    assert file_hash(before) == authority["before_manifest_sha256"]
    originals = read(before)
    assert originals == authority["after_sha256"] and len(originals) == authority["checked"] == 202
    outside_isolated_checkout = {}
    for name, expected in originals.items():
        location = Path(name)
        if not location.is_file():
            # These historical inputs were kept only in the parent workspace.
            location = Path("../..") / location
            outside_isolated_checkout[name] = location.resolve().as_posix()
        assert file_hash(location) == expected, location
    return len(originals), outside_isolated_checkout


def audit_baseline(output, freecad):
    authority = read(AUTHORITY)
    verify_authority(authority["validator"])
    verify_authority(authority["worker"])
    frozen = read(verify_authority(authority["frozen_source_sha256"]))
    graph = read(verify_authority(authority["electrical_input"]))
    originals_count, originals_outside = verified_originals()
    assert all(file_hash(path) == value for path, value in graph["source_sha256"].items())
    previous_digest, previous_observations = "", {}
    provenance = {}
    sessions = []
    last_pairs = None
    for index, attempt in enumerate(authority["attempts"]):
        run = verify_authority(attempt["checkpoint"]).parent
        for record in attempt["proof"].values():
            verify_authority(record)
        sha = attempt["checkpoint"]["sha256"]
        report, inventory, checkpoint, pairs, hashes = inspect_checkpoint(run, sha, previous_digest)
        assert report["closure"]["source_sha256"] == frozen
        assert report["pins"]["validator"] == authority["validator"]["sha256"]
        assert report["pins"]["freecad_python"] == file_hash(freecad)
        assert report["pins"]["electrical"] == authority["electrical_input"]["sha256"]
        assert all(file_hash(path) == value for path, value in report["pins"].items() if "/" in path)
        assert all(file_hash(run.parent / "copy" / path) == value for path, value in inventory["after_sha256"].items())
        assert len(frozen) == 137
        if last_pairs is not None:
            assert last_pairs.keys() == pairs.keys()
        last_pairs = pairs
        fresh = {}
        observations_for(run, report, inventory, hashes, fresh)
        new = checkpoint["observations"]
        assert all(new.get(task_id) == row for task_id, row in previous_observations.items())
        for task_id in new.keys() - previous_observations.keys():
            matching = [rec for row, rec in fresh.get(task_id, []) if row == new[task_id]]
            assert len(matching) == 1, task_id
            provenance[task_id] = {"run": run.as_posix(), **matching[0]}
        sessions.append({"run": run.as_posix(), "checkpoint_sha256": sha, "previous_sha256": previous_digest,
                         "retained_observations": len(previous_observations),
                         "new_observations": len(new) - len(previous_observations),
                         "t0": verify_t0(run, output / f"baseline-t0-{index + 1}.log")})
        previous_digest, previous_observations = sha, new
    assert previous_digest == START_CHECKPOINT
    statuses = Counter(row["status"] for row in last_pairs.values())
    assert statuses == {"NOT_RUN": 1342, "INCONCLUSIVE": 264, "FAIL": 3}
    pending = {task_id: row["reason"] for task_id, row in last_pairs.items() if row["status"] == "NOT_RUN"}
    assert len(previous_observations) == 320 and len(pending) == 1342 and sum(key in provenance for key in last_pairs) == 267
    assert all(previous_observations[key]["observation"]["status"] == "pass" for key, row in last_pairs.items()
               if row["status"] == "INCONCLUSIVE")
    audit = {"status": "PASS", "checkpoint": str(run / "checkpoint.json"), "checkpoint_sha256": previous_digest,
             "authority_sha256": file_hash(AUTHORITY), "measurement_key": checkpoint["measurement_key"],
             "measurement_identity_sha256": inventory["measurement_identity_sha256"], "criteria": report["criteria"],
             "original_files_checked": originals_count, "historical_paths_outside_isolated_checkout": originals_outside,
             "native_documents_checked": len(frozen),
             "electrical_files_checked": len(graph["source_sha256"]), "pair_counts": dict(statuses),
             "screened_pairs_sorted_id_sha256": hash_json(sorted(last_pairs)),
             "aabb": audit_filter(run, report, inventory, last_pairs), "runs": sessions,
             "authenticated_observations": provenance, "pending_ids_and_reasons": pending}
    publish(output / "baseline.json", audit)
    print(json.dumps({key: audit[key] for key in ("status", "checkpoint_sha256", "pair_counts", "aabb", "runs")}, indent=2))


def audit_parallel(progress_path, digest, baseline, report, inventory, originals):
    assert file_hash(progress_path) == digest, progress_path
    directory = progress_path.parent.parent
    seal = f"seal={digest} checkpoint={progress_path.name}"
    assert any(seal in line for line in (directory / "supervisor.log").read_text(encoding="utf-8").splitlines())
    plan = read(directory / "plan.json")
    progress = read(progress_path)
    assert plan["checkpoint"]["sha256"] == baseline["checkpoint_sha256"]
    assert plan["measurement_key"] == baseline["measurement_key"]
    selected, reserved = set(plan["selected"]), set(plan["reserved"])
    assert len(selected) == len(plan["selected"]) and len(reserved) == len(plan["reserved"])
    assert selected.isdisjoint(reserved)
    assert selected | reserved == set(baseline["pending_ids_and_reasons"])
    origins, timeout_attempts = {}, {}
    lot_ids = set()
    for summary in progress["lots"]:
        number = summary["batch"]
        assert number not in lot_ids
        lot_ids.add(number)
        prefix = f"lot-{number:04}"
        assert read(directory / f"{prefix}.json") == summary
        if plan.get("worker_script_sha256") is not None:
            assert summary["worker_script_sha256"] == plan["worker_script_sha256"]
            assert file_hash(summary["command"][2]) == plan["worker_script_sha256"]
        else:
            assert summary.get("worker_script_sha256") is None
            assert summary["command"][2:4] == ["-m", "electromechanical_engine.xlink_native"]
        assert file_hash(summary["command"][0]) == report["pins"]["freecad_python"]
        request_path = directory / f"{prefix}.request.json"
        log_path = directory / f"{prefix}.log"
        assert file_hash(request_path) == summary["request_sha256"]
        assert file_hash(log_path) == summary["log_sha256"]
        request = read(request_path)
        assert Path(request["copy"]).resolve() == (originals.parent / "copy").resolve()
        assert request["action"] == "measure" and request["criteria"] == report["criteria"]
        assert request["cache_key"] == report["closure"]["cache_key"]
        assert request["measurement_identity_sha256"] == inventory["measurement_identity_sha256"]
        assert request["environment"] == inventory["environment"]
        assert request["native_sha256"] == inventory["after_sha256"]
        requested = [task["id"] for task in request["tasks"]]
        assert requested == summary["requested"] and set(requested) <= selected
        assert all(task["kind"] == "pair" for task in request["tasks"])
        assert len(requested) == len(set(requested))
        assert set(summary["started"]) <= set(requested)
        if summary["result_sha256"] is None:
            result = {}
        else:
            result_path = directory / f"{prefix}.result.json"
            assert file_hash(result_path) == summary["result_sha256"]
            result = read(result_path)
        if result.get("finalized") is not True:
            assert summary["error"] and not summary["observed"], summary
            if len(requested) == 1:
                timeout_attempts.setdefault(requested[0], []).append(summary)
            continue
        assert summary["exit_code"] == 0 and not summary["error"]
        assert result["request_sha256"] == summary["request_sha256"]
        assert result["worker_id"] == summary["worker_id"] and result["pid"] == summary["pid"]
        assert result["before_sha256"] == result["after_sha256"] == request["native_sha256"]
        assert result["environment"] == request["environment"]
        assert result["measurement_identity_sha256"] == request["measurement_identity_sha256"]
        assert result["inventory_complete"] and result["recompute_ok"]
        assert not result["broken_links"] and not result["invalid_objects"]
        assert summary["observed"] == requested
        for task, row in zip(request["tasks"], result["observations"], strict=True):
            assert row["task"] == task and row["cache_key"] == request["cache_key"]
            assert row["worker_pid"] == result["pid"]
            origin = {"lot": number, "directory": str(directory), "log_sha256": summary["log_sha256"],
                      "worker_script_sha256": summary.get("worker_script_sha256"),
                      "result_sha256": summary["result_sha256"], "request_sha256": summary["request_sha256"],
                      "worker_id": result["worker_id"], "inventory_identity_sha256": result["measurement_identity_sha256"]}
            origins.setdefault(task["id"], []).append((row, origin))
    assert set(progress["observations"]) | set(progress["exhausted"]) <= selected
    assert all(any(observed == row for observed, _ in origins[task_id])
               for task_id, row in progress["observations"].items())
    exhausted = progress["exhausted"]
    for task_id, summary in exhausted.items():
        attempts = timeout_attempts[task_id]
        assert len(attempts) >= 3 and summary == attempts[-1], (task_id, attempts)
    return origins, exhausted, {"progress_sha256": digest, "path": str(progress_path),
                                "plan_sha256": file_hash(directory / "plan.json"),
                                "verified_lots": len(lot_ids), "selected": len(selected), "reserved": len(reserved),
                                "observations": len(progress["observations"]), "isolated_failures": len(exhausted)}


def verify_final_provenance(output, baseline, final, final_pin, origins, progress_pins):
    run = final.parent
    report, inventory, checkpoint, pairs, manifest = inspect_checkpoint(
        run, final_pin, read(run / "campaign.json")["checkpoint"]["previous_sha256"])
    initial = Path(baseline["checkpoint"])
    assert file_hash(initial) == baseline["checkpoint_sha256"]
    prior = read(initial)
    assert checkpoint["measurement_key"] == prior["measurement_key"]
    assert report["pins"] == read(initial.parent / "campaign.json")["pins"]
    assert inventory["measurement_identity_sha256"] == baseline["measurement_identity_sha256"]
    assert all(checkpoint["observations"].get(task_id) == row for task_id, row in prior["observations"].items())
    native_by_id = {}
    serial = []
    for source, digest in [*origins, (run, final_pin)]:
        current, source_inventory, _, _, hashes = inspect_checkpoint(
            source, digest, read(source / "campaign.json")["checkpoint"]["previous_sha256"])
        assert current["closure"]["cache_key"] == checkpoint["measurement_key"]
        assert source_inventory["measurement_identity_sha256"] == inventory["measurement_identity_sha256"]
        fresh = {}
        observations_for(source, current, source_inventory, hashes, fresh)
        for task_id, results in fresh.items():
            native_by_id.setdefault(task_id, []).extend((row, {"run": source.as_posix(), **proof}) for row, proof in results)
        serial.append({"run": source.as_posix(), "checkpoint_sha256": digest, "observations": len(fresh),
                       "status": verify_t0(source, output / f"native-origin-{len(serial) + 1}.log")})
    host_by_id, exhausted, parallel = inspect_progress(progress_pins, baseline, report, inventory, initial.parent)
    reconciled, missing = {}, []
    for task_id, row in pairs.items():
        measurement = row["native_evidence"]
        assert row["status"] in {"PASS", "FAIL", "INCONCLUSIVE"} and measurement is not None
        observed = measurement["observation"]
        if observed["status"] in {"pass", "fail"}:
            volume, distance = observed["intersection_mm3"], observed["clearance_mm"]
            assert all(math.isfinite(value) and value >= 0 for value in (volume, distance))
            assert observed["a"] == row["task"]["a"] and observed["b"] == row["task"]["b"]
            assert observed["authorized_relation"] is False
            fails = (volume > report["criteria"]["volume_tolerance_mm3"] or
                     distance < report["criteria"]["clearance_mm"] - report["criteria"]["distance_tolerance_mm"])
            assert (observed["status"] == "fail") == fails
            assert row["status"] == ("FAIL" if fails else "INCONCLUSIVE" if report["criteria"]["screening_only"] else "PASS")
        else:
            assert row["status"] == "INCONCLUSIVE"
        if task_id in prior["observations"]:
            reconciled[task_id] = {"source": "point initial authentifié", **baseline["authenticated_observations"][task_id]}
            continue
        found = [("lot parallèle", origin) for native, origin in host_by_id.get(task_id, []) if native == measurement]
        found.extend(("lot du validateur", origin) for native, origin in native_by_id.get(task_id, []) if native == measurement)
        if found:
            kind, origin = found[-1]
            reconciled[task_id] = {"source": kind, **origin}
        elif task_id in exhausted and observed["status"] == "unknown":
            reconciled[task_id] = {"source": "échec d'une mesure isolée", "attempt": exhausted[task_id]}
        else:
            missing.append(task_id)
    coverage = Counter(item["source"] for item in reconciled.values())
    proof = {"status": "PASS" if not missing else "FAIL", "final_checkpoint_sha256": final_pin,
             "pairs": len(pairs), "origin_counts": coverage, "missing_provenance": missing,
             "serial_sources": serial, "parallel_source": parallel, "origins": reconciled}
    publish(output / "final-provenance.json", proof)
    print(json.dumps({key: proof[key] for key in ("status", "pairs", "origin_counts", "missing_provenance")}, indent=2))
    assert not missing, missing


def inspect_progress(sources, baseline, report, inventory, run):
    by_id, exhausted, checked = {}, {}, []
    for path, pin in sources:
        observations, failed, proof = audit_parallel(Path(path), pin, baseline, report, inventory, run)
        for task_id, candidates in observations.items():
            by_id.setdefault(task_id, []).extend(candidates)
        exhausted.update(failed)
        checked.append(proof)
    return by_id, exhausted, checked


def assemble(output, sources):
    baseline = read(output / "baseline.json")
    initial = Path(baseline["checkpoint"])
    report, inventory, checkpoint, pairs, _ = inspect_checkpoint(
        initial.parent, baseline["checkpoint_sha256"], read(initial.parent / "campaign.json")["checkpoint"]["previous_sha256"])
    results, exhausted, inputs = inspect_progress(sources, baseline, report, inventory, initial.parent)
    measurements = checkpoint["observations"]
    missing, divergences = [], []
    for task_id in baseline["pending_ids_and_reasons"]:
        candidates = results.get(task_id, [])
        concluded = [(row, proof) for row, proof in candidates if row["observation"]["status"] in ("pass", "fail")]
        if concluded:
            first, _ = concluded[0]
            reference = first["observation"]
            if any((r["observation"]["status"] != reference["status"]
                    or not math.isclose(r["observation"]["clearance_mm"], reference["clearance_mm"], rel_tol=0, abs_tol=1e-6)
                    or not math.isclose(r["observation"]["intersection_mm3"], reference["intersection_mm3"],
                                        rel_tol=1e-10, abs_tol=1e-12)) for r, _ in concluded[1:]):
                divergences.append(task_id)
                continue
            measurements[task_id] = first
        elif candidates:
            measurements[task_id] = candidates[-1][0]
        elif task_id in exhausted:
            attempt = exhausted[task_id]
            measurements[task_id] = {
                "cache_key": checkpoint["measurement_key"], "task": pairs[task_id]["task"], "worker_pid": attempt["pid"],
                "observation": {"status": "unknown", "unknowns": ["bounded_process_failure"], "reason": attempt["error"]}}
        else:
            missing.append(task_id)
    proof = {"inputs": inputs, "initial_checkpoint": str(initial), "initial_sha256": baseline["checkpoint_sha256"],
             "observations": len(measurements), "missing": missing, "divergences": divergences}
    if not missing and not divergences:
        target = initial.parent.parent / f"run-b2-authority-{time.time_ns()}" / "checkpoint.json"
        target.parent.mkdir()
        publish(target, checkpoint)
        proof.update(checkpoint=str(target), sha256=file_hash(target))
    publish(output / "assembly.json", proof)
    print(json.dumps(proof, ensure_ascii=False, indent=2))
    return 0 if not missing and not divergences else 1


def select_sample(pairs, prior):
    evaluated = {task_id: row["native_evidence"]["observation"] for task_id, row in pairs.items()
                 if row["native_evidence"] is not None}
    complete = {task_id: observation for task_id, observation in evaluated.items() if observation["status"] == "pass"}
    selected = {task_id: "collision ou jeu insuffisant" for task_id, observation in evaluated.items()
                if observation["status"] == "fail"}
    for historical in (True, False):
        group = sorted(task_id for task_id in complete if (task_id in prior) == historical)
        if group:
            basis = "historique" if historical else "nouvelle"
            selected.setdefault(group[0], f"premier SHA-256 de la strate {basis}")
            selected.setdefault(group[len(group) // 2], f"SHA-256 médian de la strate {basis}")
            extreme = min(group, key=lambda task_id: (complete[task_id]["clearance_mm"], task_id))
            selected.setdefault(extreme, f"jeu minimal de la strate {basis}")
    for reason in sorted({row.get("reason") for row in pairs.values()
                          if row["status"] == "INCONCLUSIVE" and row.get("reason")}):
        matched = sorted(task_id for task_id, row in pairs.items() if row.get("reason") == reason)
        selected.setdefault(matched[0], f"première observation indéterminée de cause {reason}")
    assert selected, "Échantillon vide."
    return selected


def worker(freecad, output, name, request, timeout, method=None):
    request_file = output / f"{name}.request.json"
    result_file = output / f"{name}.result.json"
    log = output / f"{name}.log"
    publish(request_file, request)
    assert not result_file.exists(), result_file
    entry = [str(method)] if method else ["-m", "electromechanical_engine.xlink_native"]
    argv = [str(freecad), "-B", *entry, str(request_file), str(result_file)]
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", PYTHONUTF8="1")
    env.pop("DRONE_XLINK_RESULT_CHANNEL", None)
    env.pop("DRONE_XLINK_REQUEST_SHA256", None)
    start = time.monotonic()
    try:
        with log.open("wb") as stream:
            child = subprocess.run(argv, env=env, stdout=stream, stderr=subprocess.STDOUT, timeout=timeout, check=False)
    except subprocess.TimeoutExpired:
        return None, {"command": argv, "seconds": time.monotonic() - start, "timeout": True,
                      "log_sha256": file_hash(log), "request_sha256": file_hash(request_file)}
    evidence = {"command": argv, "seconds": time.monotonic() - start, "exit_code": child.returncode,
                "log_sha256": file_hash(log), "request_sha256": file_hash(request_file)}
    if method:
        evidence["worker_script_sha256"] = file_hash(method)
    result = read(result_file) if result_file.is_file() else None
    if result is not None:
        evidence["result_sha256"] = file_hash(result_file)
        assert result["request_sha256"] == evidence["request_sha256"]
    return result, evidence


def audit_reopening(output, freecad, final_checkpoint, pin):
    run = final_checkpoint.parent
    report, saved_inventory, checkpoint, pairs, hashes = inspect_checkpoint(
        run, pin, read(run / "campaign.json")["checkpoint"]["previous_sha256"])
    baseline = read(output / "baseline.json")
    assert baseline["screened_pairs_sorted_id_sha256"] == hash_json(sorted(pairs))
    assert not any(row["status"] == "NOT_RUN" for row in pairs.values())
    verified_originals()
    native = report["closure"]["saved_sha256"]
    request = {"copy": str((run.parent / "copy").resolve()), "native_sha256": native}
    inventory, inventory_evidence = worker(freecad, output, "independent-inventory",
                                           {"action": "inventory", **request}, 180)
    assert inventory_evidence.get("exit_code") == 0 and inventory["finalized"]
    assert inventory["worker_id"] not in {saved_inventory["worker_id"], report["closure"]["saved_worker"]}
    assert inventory["measurement_identity_sha256"] == saved_inventory["measurement_identity_sha256"]
    assert inventory["occurrences"] == saved_inventory["occurrences"] and inventory["documents"] == saved_inventory["documents"]
    assert inventory["occurrence_count"] == 2772
    aabb = audit_filter(run, report, inventory, pairs)
    prior = baseline["authenticated_observations"]
    selected = select_sample(pairs, prior)
    provenance = read(output / "final-provenance.json")["origins"]
    compound = [task_id for task_id, item in provenance.items() if item.get("worker_script_sha256")
                and pairs[task_id]["native_evidence"]["observation"]["status"] == "pass"]
    if compound:
        selected.setdefault(min(compound), "premier SHA-256 parmi les reprises sur composé")
    grouped, indeterminate = {}, []
    for task_id in sorted(selected):
        row = pairs[task_id]
        observation = (row["native_evidence"] or {}).get("observation", {})
        if observation.get("status") not in {"pass", "fail"}:
            indeterminate.append(row["task"])
            continue
        origin = provenance[task_id]
        method = None
        if origin.get("worker_script_sha256"):
            source = Path(origin["directory"]) / f"lot-{origin['lot']:04}.json"
            method = Path(read(source)["command"][2])
            assert file_hash(method) == origin["worker_script_sha256"]
        grouped.setdefault(method, []).append(row["task"])
    lots = [(group[begin:begin + 12], method) for method, group in grouped.items()
            for begin in range(0, len(group), 12)] + [([task], None) for task in indeterminate]
    comparisons, results = {}, []
    historical_pids = {row["native_evidence"]["worker_pid"] for row in pairs.values() if row["native_evidence"]}
    for index, (lot, method) in enumerate(lots, 1):
        query = {**request, "action": "measure", "measurement_identity_sha256": inventory["measurement_identity_sha256"],
                 "environment": inventory["environment"], "criteria": report["criteria"],
                 "cache_key": checkpoint["measurement_key"], "tasks": lot}
        result, evidence = worker(freecad, output, f"independent-measure-{index:03d}", query, 300, method)
        results.append(evidence)
        if result is None or evidence.get("exit_code") != 0 or not result["finalized"]:
            for task in lot:
                comparisons[task["id"]] = {"status": "INCONCLUSIVE", "selection": selected[task["id"]],
                                           "cause": "Processus indépendant expiré ou en erreur", "batch": index}
            continue
        assert result["measurement_identity_sha256"] == inventory["measurement_identity_sha256"]
        assert result["worker_id"] != inventory["worker_id"] and result["pid"] not in historical_pids
        assert result["environment"] == inventory["environment"] and result["before_sha256"] == result["after_sha256"] == native
        for task, measured in zip(lot, result["observations"], strict=True):
            task_id = task["id"]
            assert measured["task"] == task and measured["cache_key"] == checkpoint["measurement_key"]
            expected = pairs[task_id]["native_evidence"]
            recorded = expected["observation"] if expected else None
            current = measured["observation"]
            # JSON numeric conversion preserves values and equality on both hosts.
            if recorded and recorded.get("unknowns") == ["bounded_process_failure"] and current["status"] == "unknown":
                status = "PASS"
            else:
                status = "PASS" if current == recorded else "DIVERGENCE"
            comparisons[task_id] = {"status": status, "selection": selected[task_id], "batch": index,
                                     "task": task, "recorded": recorded, "reopened": current}
    originals_count, originals_outside = verified_originals()
    same = sum(row["status"] == "PASS" for row in comparisons.values())
    final = {"status": "PASS" if same == len(selected) else "DIVERGENCE", "checkpoint_sha256": pin,
             "run": run.as_posix(), "fresh_worker": inventory["worker_id"], "fresh_pid": inventory["pid"],
             "measurement_identity_sha256": inventory["measurement_identity_sha256"],
             "criteria": report["criteria"], "documents": len(inventory["documents"]),
             "broken_links": inventory["broken_links"], "invalid_objects": inventory["invalid_objects"],
             "occurrences": inventory["occurrence_count"], "all_occurrences_identical": True,
             "inventory": inventory_evidence, "batches": results, "aabb": aabb,
             "repeated": len(comparisons), "same": same, "comparisons": comparisons,
             "original_files_checked_after": originals_count, "changed_originals": [],
             "historical_paths_outside_isolated_checkout": originals_outside,
             "t0": verify_t0(run, output / "final-t0.log")}
    publish(output / "independent-reopening.json", final)
    print(json.dumps({key: final[key] for key in ("status", "checkpoint_sha256", "documents", "occurrences",
                                                "repeated", "same", "original_files_checked_after")}, indent=2))
    return final["status"] == "PASS"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("freecad", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--final", type=Path)
    parser.add_argument("--final-sha256")
    parser.add_argument("--origin", nargs=2, metavar=("RUN", "SHA256"), action="append", default=[])
    parser.add_argument("--progress", nargs=2, metavar=("CHECKPOINT", "SHA256"), action="append", default=[])
    parser.add_argument("--assemble", action="store_true")
    args = parser.parse_args()
    assert bool(args.final) == bool(args.final_sha256)
    args.output.mkdir(parents=True, exist_ok=True)
    if args.assemble:
        return assemble(args.output, args.progress)
    if args.final:
        if args.progress:
            verify_final_provenance(args.output, read(args.output / "baseline.json"), args.final, args.final_sha256,
                                    [(Path(path), digest) for path, digest in args.origin],
                                    args.progress)
        return 0 if audit_reopening(args.output, args.freecad, args.final, args.final_sha256) else 1
    audit_baseline(args.output, args.freecad)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
