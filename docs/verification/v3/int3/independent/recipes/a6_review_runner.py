"""Revue V3-A.6 sur copies Workholding privées et signatures de banc neuves."""

import argparse
from base64 import b64decode
from datetime import datetime, timezone
from pathlib import Path
import json
import math
import os
import secrets
import shutil
import subprocess
import sys


def utc():
    return datetime.now(timezone.utc).isoformat()


def write(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read(path):
    return json.loads(path.read_bytes())


def digest(path):
    from hashlib import sha256

    return sha256(path.read_bytes()).hexdigest()


def measure(root, case, output):
    """Mesure OCCT directe depuis le candidat sauvegardé et la pose signée."""
    sys.path.insert(0, str(root))
    from electromechanical_engine import freecad_worker as native

    app, part = native.App, native.Part
    environment = native.cables_environment(False)
    nominal = read(root / "docs/electromechanical_v3/bench_b1_workholding/profile.json")
    names = nominal["model"]["occurrences"]
    criteria = nominal["model"]["validation"]
    tol = criteria["tolerances"]["position_mm"]
    requirement = criteria["supports"]["plate-new"]
    closure = case / "cad"
    effect = read(case / "effect.json")
    expected = read(case / "candidate-job.json")["dependencies"]
    assert {key: digest(closure / key) for key in expected} == expected
    assert not app.listDocuments()
    doc = app.openDocument(str(closure / nominal["entry"]))
    try:
        native.complete_dependencies(doc, closure)
        opened = {Path(item.FileName).resolve().relative_to(closure).as_posix()
                  for item in app.listDocuments().values() if not item.Partial}
        assert opened == expected.keys()

        def occurrence(key):
            head, *children = names[key].split("/")
            tail = ".".join(children) + "." if children else ""
            top = doc.getObject(head)
            obj, matrix = top.getSubObject(tail, 1, app.Matrix(), True)
            return top, tail, obj, app.Placement(matrix)

        def solid(key):
            top, tail, _, _ = occurrence(key)
            return part.getShape(top, tail)

        _, _, support, saved_pose = occurrence("plate-new")
        _, _, anchor, anchor_pose = occurrence("anchor-new")
        _, _, carrier, _ = occurrence("carrier")
        _, _, cordon, _ = occurrence("cordon")
        _, _, stud, _ = occurrence("stud-new")
        assert support.TypeId == "Part::Cut" and support.Visibility
        assert support.B1_Anchor == anchor and support.B1_Carrier == carrier
        assert support.B1_Retains == [cordon] and support.B1_Fasteners == [stud]
        expected_pose = anchor_pose.multiply(app.Placement(app.Vector(*effect["translation_mm"]),
                                                         app.Rotation(*effect["rotation_xyzw"])))
        delta = expected_pose.inverse().multiply(saved_pose)
        direction_error = abs(math.remainder(math.degrees(delta.Rotation.Angle), 360.0))
        assert delta.Base.Length <= tol and direction_error <= criteria["tolerances"]["direction_deg"]
        shape, base, pin = solid("plate-new"), solid("carrier"), solid("stud-new")
        box = shape.BoundBox
        dimensions = [box.XLength, box.YLength, box.ZLength]
        assert shape.isValid() and len(shape.Solids) == 1
        assert all(abs(measured - signed) <= tol for measured, signed in zip(dimensions, effect["size_mm"], strict=True))
        bearing_gap = shape.distToShape(base)[0]
        retained_gap = shape.distToShape(solid("cordon"))[0]
        bearing_area = sum(a.common(b).Area for a in shape.Faces for b in base.Faces
                           if isinstance(a.Surface, part.Plane) and isinstance(b.Surface, part.Plane)
                           and a.distToShape(b)[0] <= tol)
        engagement = pin.common(base).Volume
        pin_gap = pin.distToShape(shape)[0]
        assert bearing_gap <= tol and bearing_area >= requirement["min_contact_area_mm2"]
        assert retained_gap <= requirement["retention_max_gap_mm"]
        assert pin_gap <= tol and engagement > criteria["tolerances"]["volume_mm3"]
        result = {"status": "PASS", "pid": os.getpid(), "opened": sorted(opened),
                  "environment": {"FreeCAD": ".".join(app.Version()[:3]), "OCCT": part.OCC_VERSION,
                                  "Cables": environment},
                  "world_origin_mm": list(saved_pose.Base), "anchor_origin_mm": list(anchor_pose.Base),
                  "local_origin_mm": list(anchor_pose.inverse().multiply(saved_pose).Base),
                  "dimensions_mm": dimensions, "position_error_mm": delta.Base.Length,
                  "rotation_error_deg": direction_error, "bearing_area_mm2": bearing_area,
                  "bearing_gap_mm": bearing_gap, "retention_gap_mm": retained_gap,
                  "fastener_engagement_mm3": engagement, "fastener_gap_mm": pin_gap,
                  "persisted_native_links": True, "input_sha256": expected}
    finally:
        for name in reversed(list(app.listDocuments())):
            app.closeDocument(name)
    assert not app.listDocuments()
    assert {key: digest(closure / key) for key in expected} == expected
    write(output, {**result, "documents_closed": True})


def recover(root, case, output):
    """Restitution hors transaction du reçu dont la publication a été interrompue."""
    from hashlib import sha256
    import hmac
    from PySide6.QtCore import QJsonDocument, qVersion

    trusted = case / "trusted"
    key = (trusted / "a6-journal.key").read_bytes()
    assert sha256(key).hexdigest() == read(trusted / "trust.json")["journal_key_sha256"]
    journal = trusted / "a6-journal.jsonl"
    contents = journal.read_bytes()
    assert contents.endswith(b"\n")
    previous_mac = "0" * 64
    last_date = ""
    commits = []
    for position, line in enumerate(contents.splitlines()):
        envelope = json.loads(line)
        payload = b64decode(envelope["event_b64"], validate=True)
        assert hmac.compare_digest(envelope["mac"], hmac.digest(key, payload, sha256).hex())
        event = json.loads(payload)
        assert event["sequence"] == position and event["previous_mac"] == previous_mac and event["at_utc"] >= last_date
        previous_mac, last_date = envelope["mac"], event["at_utc"]
        if event["state"] == "COMMITTED_PRIVATE":
            commits.append(event)
    assert len(commits) == 1
    committed = commits[0]
    detail = committed["detail"]
    receipt = detail["receipt"]
    after_fault = case / "result-interrupted"
    assert not (after_fault / "admission.json").exists()
    private = (after_fault / receipt["publication"]["directory"]).resolve()
    assert private.is_relative_to(after_fault)
    for name, expected in receipt["publication"]["sha256"].items():
        path = (private / name).resolve()
        assert path.is_relative_to(private) and path.stat().st_nlink == 1 and digest(path) == expected
    recovered = bytes(QJsonDocument.fromVariant(receipt).toJson(QJsonDocument.Indented))
    assert sha256(recovered).hexdigest() == detail["receipt_sha256"]
    output.parent.mkdir()
    target = output.parent / "admission.json"
    target.write_bytes(recovered)
    assert digest(target) == detail["receipt_sha256"] and digest(journal) == sha256(contents).hexdigest()
    assert not (after_fault / "admission.json").exists()
    write(output, {"status": "PASS", "qt_version": qVersion(), "journal_sha256": digest(journal),
                   "journal_event_count": len(contents.splitlines()), "commit_sequence": committed["sequence"],
                   "restored_receipt": target.relative_to(root).as_posix(), "receipt_sha256": digest(target),
                   "artifacts_verified": len(receipt["publication"]["sha256"]), "original_receipt_absent": True})


def campaign(root, work, build, openssl, freecad, phase):
    tests = root / "convergence_manager/tests"
    sys.path.insert(0, str(tests))
    from test_v3_a6_transactions import A6Fixture, MODEL, PROFILE, SigningFixtures, assert_denied, check_commit, fault_cases
    from test_v3_a6_adversarial import exercise

    proofs = work / "logs"
    proofs.mkdir(parents=True)
    executables = {name: build / name / "convergence_core.exe" for name in ("l5", "l5-faults", "l5-no-crypto")}
    t0 = build / "t0/cartographe-evidence.exe"
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1")
    env["PATH"] = str(openssl.parent) + os.pathsep + env["PATH"]
    env.pop("L5_A6_TEST_FAULT", None)
    os.environ.update(env)

    def call(label, command, fault=None, timeout=210):
        argv = [str(item) for item in command]
        started = utc()
        settings = {**env, "L5_A6_TEST_FAULT": fault} if fault else env
        result = subprocess.run(argv, cwd=root, env=settings, capture_output=True, timeout=timeout)
        files = {}
        for stream in ("stdout", "stderr"):
            path = proofs / f"{label}.{stream}.log"
            path.write_bytes(getattr(result, stream))
            files[stream] = {"path": path.relative_to(root).as_posix(), "sha256": digest(path)}
        record = {"argv": argv, "cwd": ".", "started_utc": started, "finished_utc": utc(),
                  "exit_code": result.returncode, "fault": fault, **files}
        write(proofs / f"{label}.json", record)
        return result, record

    class LoggedFixture(A6Fixture):
        def invoke(self, name, request=None, *, fault=None, **options):
            cmd, output = self.command(name, request, **options)
            entry = {}
            for path in (Path(cmd[cmd.index("--request") + 1]), self.packet, self.review, self.registry, self.trust_path):
                if path.is_file():
                    entry[path.name] = digest(path)
            label = f"{self.work.name}--{name}"
            observed, trace = call(label, cmd, fault=fault)
            receipt = output / "admission.json"
            trace.update(input_sha256=entry, receipt_sha256=digest(receipt) if receipt.is_file() else None)
            write(proofs / f"{label}.json", trace)
            return {"code": observed.returncode, "report": read(receipt) if receipt.is_file() else None,
                    "stdout": observed.stdout.decode(errors="replace"),
                    "stderr": observed.stderr.decode(errors="replace"), "output": output}

    def signing(folder):
        folder.mkdir()
        return SigningFixtures(openssl, folder)

    def verify_signatures(fixture, case):
        case.mkdir()
        trust = read(fixture.trust_path)
        assert trust["reviewer_public_key_hex"] != trust["registry_public_key_hex"]
        assert not fixture.trust_path.is_relative_to(fixture.raw)
        envelopes = {}
        payloads = {}
        for role, field, envelope in (("review", "reviewer_public_key_hex", fixture.review),
                                      ("registry", "registry_public_key_hex", fixture.registry)):
            signed = read(envelope)
            payload = b64decode(signed["payload_b64"], validate=True)
            signature = b64decode(signed["signature_b64"], validate=True)
            message, sig, public = (case / f"{role}.{suffix}" for suffix in ("payload", "signature", "pub.der"))
            message.write_bytes(payload)
            sig.write_bytes(signature)
            public.write_bytes(bytes.fromhex("302a300506032b6570032100" + trust[field]))
            verified, trace = call(f"{fixture.work.name}-verify-{role}",
                                   [openssl, "pkeyutl", "-verify", "-pubin", "-keyform", "DER", "-rawin",
                                    "-inkey", public, "-in", message, "-sigfile", sig], timeout=15)
            assert verified.returncode == 0, trace
            payloads[role] = json.loads(payload)
            envelopes[role] = {"envelope_sha256": digest(envelope), "payload_sha256": digest(message),
                               "signature_sha256": digest(sig), "public_key_der_sha256": digest(public)}
        review, registry = payloads["review"], payloads["registry"]
        assert review["authorized_effect"] == fixture.request["effect"]
        assert review["trust_sha256"] == fixture.trust_sha == digest(fixture.trust_path)
        assert review["policy_sha256"] == digest(fixture.policy)
        assert review["packet_sha256"] == digest(fixture.packet)
        assert review["bindings"] == fixture.request["bindings"] == trust["bindings"]
        assert trust["source_root"] == MODEL["source"] and digest(fixture.profile) == digest(PROFILE)
        assert fixture.snapshot() == MODEL["dependencies"] == {
            name: digest(fixture.sandbox / name) for name in MODEL["dependencies"]}
        policy = read(fixture.policy)
        from test_v3_a5_authority import data, sha

        assert sha(data(policy["identities"])) == review["bindings"]["lot_sha256"]
        lot = policy["identities"][review["bindings"]["occurrence"]]["identity"]
        row = read(fixture.packet)["records"][0]
        assert row["identity"] == lot and row["facts"]["carrier"] == review["authorized_effect"]["carrier"]
        assert registry["events"][0]["id"] == review["id"]
        assert registry["events"][0]["review_sha256"] == digest(fixture.review)
        return {"decision_id": review["id"], "issued_at_utc": review["issued_at_utc"],
                "expires_at_utc": review["expires_at_utc"], "lot": lot, "lot_sha256": review["bindings"]["lot_sha256"],
                "signed_effect": review["authorized_effect"], "trust_external_to_submission": True,
                "source_root": trust["source_root"], "profile_sha256": digest(fixture.profile), **envelopes}

    def native_recheck(label, fixture, invocation, proof_dir, signed):
        receipt = invocation["report"]
        source = invocation["output"] / receipt["publication"]["directory"]
        plan = read(source / "mutation-plan.json")
        build_job = read(source / "build-job.json")
        candidate_job = read(source / "candidate-job.json")
        effect = signed["signed_effect"]
        actual_effect = plan["actions"][0]["parameters"]
        assert plan["authorized_effect"] == build_job["authorized_effect"] == candidate_job["authorized_effect"] == effect
        assert actual_effect["size_mm"] == effect["size_mm"]
        assert actual_effect["placement"] == {field: effect[field] for field in ("translation_mm", "rotation_xyzw")}
        assert plan["plan_id"] == signed["decision_id"] and plan["review_sha256"] == signed["review"]["envelope_sha256"]
        assert plan["request_sha256"] == digest(fixture.work / "first.json")
        independent = proof_dir / "native"
        independent.mkdir()
        shutil.copytree(fixture.sandbox, independent / "baseline-cad")
        shutil.copytree(source / "cad", independent / "cad")
        write(independent / "effect.json", effect)
        verifier = root / "convergence_manager/native/v3_verify.py"
        baseline_job = independent / "baseline-job.json"
        shutil.copyfile(source / "baseline-job.json", baseline_job)
        baseline = independent / "baseline.json"
        result, trace = call(f"{label}-independent-baseline", [freecad, "-I", "-B", "-X", "utf8", verifier,
            "--root", independent / "baseline-cad", "--job", baseline_job, "--output", baseline], timeout=120)
        assert result.returncode == 0 and read(baseline)["documents_closed"], trace
        candidate_job["baseline"] = read(baseline)
        work_job = independent / "candidate-job.json"
        write(work_job, candidate_job)
        recheck = independent / "recheck.json"
        result, trace = call(f"{label}-independent-candidate", [freecad, "-I", "-B", "-X", "utf8", verifier,
            "--root", independent / "cad", "--job", work_job, "--output", recheck], timeout=120)
        assert result.returncode == 0, trace
        observed = read(recheck)
        assert observed["status"] == "PASS" and observed["documents_closed"]
        published = read(source / "candidate-validation.json")
        assert observed["pid"] != published["pid"] and observed["worker_id"] != published["worker_id"]
        # L'ordre de restauration de deux dépendances indépendantes varie selon le processus.
        def comparable(checks):
            return {check["id"]: (check["status"],
                    {**check["details"], "documents": sorted(check["details"]["documents"])}
                    if check["id"] == "REOPEN_XLINK" else check["details"]) for check in checks}

        assert comparable(observed["checks"]) == comparable(published["checks"])
        outline = independent / "occt-direct.json"
        result, trace = call(f"{label}-independent-occt", [freecad, "-I", "-B", "-X", "utf8", Path(__file__).resolve(),
            "measure", "--root", root, "--work", independent, "--report", outline], timeout=120)
        assert result.returncode == 0 and read(outline)["status"] == "PASS", trace
        run, t0_trace = call(f"{label}-independent-t0", [t0, "validate", source, root], timeout=40)
        assert run.returncode == 0, t0_trace
        checks = {check["id"]: check["status"] for check in observed["checks"]}
        return {"checks": checks, "t0_exit_code": run.returncode, "direct_occt": read(outline),
                "baseline_sha256": digest(baseline), "native_recheck_sha256": digest(recheck),
                "direct_occt_sha256": digest(outline), "validated_native_job_sha256": digest(work_job),
                "sealed_publication_sha256": receipt["publication"]["sha256"]}

    source_before = {name: digest(root / MODEL["source"] / name) for name in MODEL["dependencies"]}
    assert source_before == MODEL["dependencies"]
    result = {"phase": phase, "sources_before": source_before,
              "binaries_sha256": {**{name: digest(exe) for name, exe in executables.items()}, "t0": digest(t0)}}
    write(work / "evidence.json", result)
    if phase == "positive":
        result["transactions"] = cases = {}
        for label, translation, size in (("nominal", (0, 0, 0), (8, 8, 3)),
                                         ("modified", (-0.375, 0, 0), (7.93, 8, 3))):
            fixture = LoggedFixture(executables["l5"], work / label, signing(work / f"{label}-keys"), translation, size)
            fixture.prepare(id=f"int3-independent-{label}-{secrets.token_hex(8)}")
            separate = work / f"{label}-countercheck"
            signed = verify_signatures(fixture, separate)
            invocation = fixture.invoke("first")
            transaction, validation = check_commit(fixture, invocation)
            cases[label] = {"signature_verification": signed, "transaction": transaction,
                            "validation_at_build": validation, "journal_sha256": digest(fixture.journal),
                            "private_location": invocation["output"].relative_to(root).as_posix()}
            write(work / "evidence.json", result)
            cases[label]["independent_validation"] = native_recheck(label, fixture, invocation, separate, signed)
            write(work / "evidence.json", result)
        nominal = cases["nominal"]["independent_validation"]["direct_occt"]
        modified = cases["modified"]["independent_validation"]["direct_occt"]
        result["measured_delta"] = {key: [b - a for a, b in zip(nominal[key], modified[key], strict=True)]
                                    for key in ("world_origin_mm", "dimensions_mm")}
        assert math.isclose(result["measured_delta"]["world_origin_mm"][0], -0.375, abs_tol=1e-6)
        assert math.isclose(result["measured_delta"]["dimensions_mm"][0], -0.07, abs_tol=1e-6)
        assert nominal["input_sha256"][MODEL["entry"]] != modified["input_sha256"][MODEL["entry"]]
    else:
        keys = signing(work / "keys")
        core = executables["l5-faults"] if phase == "faults" else executables["l5"]

        def factory(name, **kwargs):
            return LoggedFixture(core, work / name, keys, **kwargs)

        if phase == "faults":
            result["cases"] = fault_cases(factory)
            assert len(result["cases"]) == 7
        elif phase == "refusals":
            result["cases"] = exercise(factory, executables["l5-no-crypto"])
            assert len(result["cases"]) == 32
        else:
            result["cases"] = cases = {}
            fixture = factory("post-signature-mutations")
            packet = fixture.packet.read_bytes()
            fixture.packet.write_bytes(packet + b"\n")
            denied = assert_denied(fixture.invoke("packet-bytes"), "SIGNED_REVIEW_BINDING_MISMATCH")
            assert denied["construction_result"] == "NOT_RUN" and not fixture.journal_states()
            cases["packet-bytes"] = {"status": "PASS", "reason": denied["reason"], "construction": "NOT_RUN"}
            fixture.packet.write_bytes(packet)
            raw_measurement = fixture.raw / fixture.record["sources"]["raw"]["path"]
            raw_measurement.write_bytes(raw_measurement.read_bytes() + b"synthetic alteration\n")
            denied = assert_denied(fixture.invoke("changed-measurement"), "TECHNICAL_REVIEW_REJECTED")
            assert denied["construction_result"] == "NOT_RUN" and not fixture.journal_states()
            cases["changed-measurement"] = {"status": "PASS", "reason": denied["reason"],
                                            "technical": denied["technical"]["records"][0]["reason"],
                                            "construction": "NOT_RUN"}
            fixture = factory("authenticated-journal")
            envelope = read(fixture.journal)
            envelope["mac"] = "1" * 64
            # Le format JSONL exige une seule ligne pour atteindre le contrôle HMAC.
            fixture.journal.write_text(json.dumps(envelope, separators=(",", ":")) + "\n", encoding="utf-8")
            before = digest(fixture.journal)
            denied = assert_denied(fixture.invoke("rewritten"), "A6_JOURNAL_AUTHENTICATION_FAILED")
            assert denied["construction_result"] == "NOT_RUN" and digest(fixture.journal) == before
            cases["rewritten-journal"] = {"status": "PASS", "reason": denied["reason"], "journal_sha256": before,
                                          "construction": "NOT_RUN"}
    result["sources_after"] = {name: digest(root / MODEL["source"] / name) for name in MODEL["dependencies"]}
    assert result["sources_after"] == result["sources_before"]
    result["status"] = "PASS"
    write(work / "evidence.json", result)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("positive", "refusals", "faults", "independent-refusals", "measure", "recover"))
    for argument in ("root", "work", "build", "report", "openssl", "freecad"):
        parser.add_argument("--" + argument, type=Path)
    args = parser.parse_args()
    root, work = args.root.resolve(), args.work.resolve()
    assert work.is_relative_to(root / ".runtime")
    if args.phase == "measure":
        measure(root, work, args.report.resolve())
    elif args.phase == "recover":
        recover(root, work, args.report.resolve())
    else:
        campaign(root, work, args.build.resolve(), args.openssl.resolve(), args.freecad.resolve(), args.phase)
