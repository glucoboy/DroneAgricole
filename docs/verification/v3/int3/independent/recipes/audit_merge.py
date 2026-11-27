"""Recalcule les identités de la remise INT.3, en lecture seule pour Git."""

from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import subprocess
import sys


ROOT = Path.cwd().resolve()
WORKSPACE = ROOT.parents[1]
ARCHIVE = ROOT.parent / "int3-i"
PROOF = Path("docs/verification/v3/int3/integration")
OUTPUT = Path(".runtime/git-review")
PUBLICATION = "60790ca713bd3e243b1a2581014927b5e7169ac4"
TESTED = "558b40fce8a33cb97b28d98418fb258585836873"
C3_MERGE = "6e5fd7176ddbb26f5a1df0dd368032af2a803079"
BASE = "27144abf9841ba6502d29f2f76b15ff33092d186"
SOURCES = {
    "int21": ("v3-int21-regression-recovery", BASE, "f8c5922c0fe2a4c5975d792edafd4d8221ad1ce4"),
    "c3": ("v3-c3-3d-generalization", "08ec9c4baba84d9486e7d1df3a356c0d35583646",
           "5bf6b11eec6dc5b323daa1d67edc0957ffeb7c20"),
    "a6": ("v3-a6-authorized-native-transaction", "6461198f341af9e1f79aef061cb65d6fa531b283",
           "da8908e7120a896122b655d2e3f241776cc7c64b"),
}
BOUNDARY_SCRIPT = "convergence_manager/tests/test_v3_int3_a6_boundaries.py"
REMOTE_REFS = {
    "refs/heads/codex/v3-int3-integration": PUBLICATION,
    **{f"refs/heads/codex/{name}": tip for name, tip, _ in SOURCES.values()},
    "refs/heads/integration": "cbf125f717f3c483c23d49ebd7ef4705df7f21dd",
    "refs/heads/master": "8e26b680af9cf4c15ec7a6bc98c71557837f2191",
}


def digest(data):
    return sha256(data).hexdigest()


def read(path):
    return json.loads(path.read_bytes())


def git(*args):
    return subprocess.check_output(["git", "--no-optional-locks", *args])


def git_text(*args):
    return git(*args).decode("utf-8").strip()


def blob(commit, path):
    return git("show", f"{commit}:{Path(path).as_posix()}")


def diff(old, new, *paths):
    raw = git("diff", "--no-renames", "--name-status", "-z", old, new, "--", *paths)
    tokens = raw.decode("utf-8").split("\0")[:-1]
    return {path: status for status, path in zip(tokens[::2], tokens[1::2], strict=True)}


def commit_info(commit):
    full, parents, recorded, tree, title = git_text("show", "-s", "--format=%H|%P|%cI|%T|%s", commit).split("|", 4)
    return {"commit": full, "parents": parents.split(), "committer_time": recorded, "tree": tree, "subject": title}


def ref_fingerprint(commit, path, expected):
    payload = blob(commit, path)
    observed = digest(payload)
    assert observed == expected["sha256"] and len(payload) == expected["bytes"], (commit, path, expected, observed)
    return {"path": Path(path).as_posix(), "sha256": observed, "bytes": len(payload)}


def graph_review(manifest, acceptance):
    assert git_text("rev-parse", "HEAD") == git_text("rev-parse", "origin/codex/v3-int3-integration") == PUBLICATION
    assert acceptance["verdict"] == "V3_INT3_INTEGRATION_READY_FOR_REVIEW"
    assert acceptance["tested_commit"] == manifest["test_commit"] == TESTED and manifest["base"] == BASE
    publication = commit_info(PUBLICATION)
    c3 = commit_info(C3_MERGE)
    tested = commit_info(TESTED)
    assert publication["parents"] == [TESTED]
    assert c3["parents"] == [BASE, SOURCES["c3"][1]]
    assert tested["parents"] == [C3_MERGE, SOURCES["a6"][1]] == acceptance["merge_parents"]
    for row in manifest["merges"]:
        assert commit_info(row["commit"])["parents"] == row["parents"]
        assert git_text("merge-base", *row["parents"]) == row["merge_base"] == BASE
    assert not diff(SOURCES["c3"][1], C3_MERGE)
    sources = {}
    for name, (branch, tip, tested_source) in SOURCES.items():
        row = manifest["sources"][name]
        assert row["tip"] == tip == git_text("rev-parse", f"origin/codex/{branch}")
        assert row["tested_commit_receipt"] == tested_source
        git("merge-base", "--is-ancestor", tip, TESTED)
        git("merge-base", "--is-ancestor", tested_source, tip)
        assert git_text("merge-base", BASE, tip) == BASE
        path = Path(row["receipt"])
        original = blob(tip, path)
        receipt = json.loads(original)
        assert receipt["tested_commit"] == tested_source
        assert digest(original) == row["receipt_blob_sha256"]
        assert not diff(tip, PUBLICATION, path.parent.as_posix())
        receipts = []
        for ev in receipt["evidence"] + receipt.get("executed_recipes", []):
            target = Path(ev["path"])
            if not target.is_file():
                target = path.parent / target
            receipts.append(ref_fingerprint(tip, target, ev))
        supplements = []
        for item in git_text("rev-list", "--reverse", f"{tested_source}..{tip}").splitlines():
            revision = commit_info(item)
            revision["delta"] = diff(revision["parents"][0], item)
            assert all(p.startswith("docs/") or name == "a6" and (
                p == ".gitattributes" or p.startswith("convergence_manager/tests/test_v3_a6_"))
                for p in revision["delta"])
            supplements.append(revision)
        assert diff(tested_source, tip) == row["between_tested_source_and_tip"]
        assert diff(BASE, tip) == row["between_base_and_tip"]
        sources[name] = {"branch": f"codex/{branch}", "tip": commit_info(tip), "tested_commit": tested_source,
                         "receipt": path.as_posix(), "receipt_sha256": digest(original),
                         "receipt_blob_unchanged": True, "receipt_support_files": receipts,
                         "proof_commits_after_tested_commit": supplements}
    return {"schema": "v3.int3.git_history_review/1", "status": "PASS", "tested_commit": TESTED,
            "publication": publication, "merges": [c3, tested], "base": commit_info(BASE),
            "checkout_initial_status": git_text("status", "--porcelain=v1", "--branch"),
            "git_version": git_text("version"), "remote_refs_reported_by_review_coordinator": REMOTE_REFS,
            "github_acceptance_blob": git_text("rev-parse", f"{PUBLICATION}:{PROOF.as_posix()}/acceptance.json"),
            "sources": sources,
            "commands": ["git ls-remote origin <références explicitement listées>",
                         "git rev-parse HEAD origin/codex/v3-int3-integration",
                         "git show -s --format=%H|%P|%cI|%T|%s <commit>",
                         "git merge-base --is-ancestor <ancêtre> <descendant>",
                         "git merge-base <branche1> <branche2>",
                         "git rev-list --reverse <tested_commit>..<source_head>",
                         "git diff --no-renames --name-status -z <ancien> <nouveau> --",
                         "git show <commit>:<chemin>"]}


def walk_references(node, pointer=""):
    if isinstance(node, dict):
        if isinstance(node.get("path"), str) and ("sha256" in node or "snapshot_sha256" in node):
            yield pointer, node
        for key, value in node.items():
            yield from walk_references(value, f"{pointer}/{key}")
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from walk_references(value, f"{pointer}/{index}")


def resolve_reference(receipt, path, pointer):
    if path.is_absolute():
        return "ABSOLUTE", path
    if path.parts[0] == ".runtime":
        return "INTEGRATOR_GENERATED_ARCHIVE", ARCHIVE / path
    if pointer.endswith("/historic_off_git_manufacturer"):
        return "HISTORICAL_INPUT_OFF_GIT", WORKSPACE / path
    if path.is_file() and not receipt.name == "acceptance.json":
        return "PUBLISHED", path
    candidate = (receipt.parent / path).resolve()
    assert candidate.is_relative_to(ROOT)
    return "PUBLISHED", candidate.relative_to(ROOT)


def reference_review():
    observed = []
    for receipt in sorted(PROOF.rglob("*.json")):
        for pointer, row in walk_references(read(receipt)):
            scope, candidate = resolve_reference(receipt, Path(row["path"]), pointer)
            actual = candidate.read_bytes() if candidate.is_file() else None
            sha = row.get("sha256", row.get("snapshot_sha256"))
            status = "ABSENT" if actual is None else "PASS" if (
                digest(actual) == sha and ("bytes" not in row or len(actual) == row["bytes"])
            ) else "REFUSED_HASH_MISMATCH"
            record = {"receipt": receipt.relative_to(PROOF).as_posix(), "pointer": pointer, "path": row["path"],
                      "scope": scope, "status": status, "expected_sha256": sha}
            if actual is not None:
                record.update(observed_sha256=digest(actual), observed_bytes=len(actual))
            if scope == "PUBLISHED":
                tracked = blob(PUBLICATION, candidate)
                assert actual is not None
                if tracked != actual:
                    assert tracked == actual.replace(b"\r\n", b"\n"), candidate
                    record.update(git_blob_sha256=digest(tracked), checkout_transformation="LF_TO_CRLF")
            observed.append(record)
    counts = Counter((row["scope"], row["status"]) for row in observed)
    return {"counts": {scope: {status: number for (key, status), number in counts.items() if key == scope}
                       for scope, _ in counts},
            "by_receipt": {name: dict(Counter(row["status"] for row in observed if row["receipt"] == name))
                           for name in sorted({row["receipt"] for row in observed})},
            "line_ending_differences": [row for row in observed if "checkout_transformation" in row],
            "refused_references": [row for row in observed if row["status"] != "PASS"],
            "archive_scope": "Les 266 références vers .runtime désignent les sorties de l’intégrateur, confrontées aux octets de l’archive locale. Ce contrôle d’identité précède nos rejeux indépendants. Les commandes absolues historiques décrivent l’environnement d’exécution et sont relocalisées par les recettes. L’entrée historique hors Git référencée avec empreinte dans les reçus INT.3 est la fiche F16 déclarée, retrouvée dans le workspace historique.",
            "wrong_recipe_disposition": "La référence /recipes/3 du reçu adversarial est refusée. Elle associe l’empreinte de la première exécution au chemin Git de la recette finale. Cela affecte la traçabilité de l’essai intermédiaire. L’empreinte finale est liée séparément par acceptance.json et par /boundary_replay/runtime_recipe. Le rejeu final doit être produit séparément de ce contrôle d’identité."}


def model_review():
    benches = ("bench_b1_workholding", "bench_c2_multiharness", "bench_c2_multiharness_secondary",
               "bench_c3_spatial", "bench_c3_spatial_secondary")
    result = {}
    for bench in benches:
        folder = Path("docs/electromechanical_v3") / bench
        commit = SOURCES["c3"][1] if bench.startswith("bench_c3") else BASE
        assert not diff(commit, TESTED, folder.as_posix())
        assert not diff(TESTED, PUBLICATION, folder.as_posix())
        prof = read(folder / "profile.json")
        graph = Path(prof["graph"])
        assert digest(graph.read_bytes()) == prof["graph_sha256"]
        source = Path(prof["source"])
        observed = {name.relative_to(source).as_posix(): digest(name.read_bytes())
                    for name in sorted(source.rglob("*.FCStd"))}
        assert observed == prof["dependencies"]
        result[bench] = {"profile_sha256": digest((folder / "profile.json").read_bytes()),
                         "graph_sha256": prof["graph_sha256"], "native_sha256": observed, "reference_commit": commit}
    return result


def seal_review():
    seal_path = Path("docs/verification/v3/a/freeze.json")
    seal = read(seal_path)
    authority = Path("docs/verification/v3/a/native_receipt.json")
    receipt = read(authority)
    wanted = next(row["sha256"] for row in seal["artifacts"] if row["path"] == authority.as_posix())
    assert digest(authority.read_bytes()) == wanted
    assert not diff(BASE, PUBLICATION, seal_path.parent.as_posix(), receipt["source_prefix"])
    names = receipt["inputs_sha256"]
    native = {name for name in names if name.endswith(".FCStd")}
    assert len(names) == 142 and len(native) == 137
    prefix = Path(receipt["source_prefix"])
    historical = WORKSPACE / ".runtime/v3-a/native-20261118-065605213/staged"
    from electromechanical_engine.freecad import guard

    entry = Path(receipt["entry"]).relative_to(prefix)
    matching = {}
    observed_checkout = {}
    for name, expected in sorted(names.items()):
        sealed = (historical / name).read_bytes()
        checkout = (prefix / name).read_bytes()
        assert digest(sealed) == expected
        observed_checkout[name] = digest(checkout)
        if checkout != sealed:
            assert name not in native and checkout == sealed.replace(b"\r\n", b"\n"), name
            matching[name] = {"sealed_sha256": expected, "checkout_sha256": digest(checkout)}
    for root in (prefix.resolve(), historical):
        closure = {member.relative_to(root).as_posix() for member in guard.dependencies(root, [entry])}
        assert closure == native
    inventory = lambda hashes: digest(json.dumps(hashes, sort_keys=True, separators=(",", ":")).encode())
    return {"freeze_path": seal_path.as_posix(), "freeze_sha256": digest(seal_path.read_bytes()),
            "sealed_at_utc": seal["sealed_at_utc"], "receipt_path": authority.as_posix(), "receipt_sha256": wanted,
            "entries": len(names), "serialized_xlink_entries": len(native),
            "historical_matches": len(names), "checkout_matches": len(names) - len(matching),
            "checkout_eol_differences": matching, "sealed_inventory_sha256": inventory(names),
            "checkout_inventory_sha256": inventory(observed_checkout)}


def freeze_review():
    native = read(PROOF / "native_c3.json")
    regression = read(PROOF / "regressions.json")
    commands = {"c2": regression["historical_regressions"]["c2"]["phases"]["T1"]["command"]["finished_utc"],
                "c3": native["phases"]["T1"]["ended_utc"]}
    result = {}
    for label, path in (("c2", ".runtime/r/c2/freeze.json"), ("c3", ".runtime/int3-c3/freeze.json")):
        raw = (ARCHIVE / path).read_bytes()
        source = PROOF / "inputs" / f"{label}-t2-perturbation.json"
        perturbation = read(source)
        seal = json.loads(raw)
        assert perturbation["freeze_sha256"] == digest(raw)
        inputs = seal.get("inputs") or seal
        assert inputs["source_commit"] == TESTED
        traced_paths = Counter()
        for name, expected in inputs["files_sha256"].items():
            path = Path(name).resolve()
            assert digest(path.read_bytes()) == expected
            if path.is_relative_to(ARCHIVE):
                relative = path.relative_to(ARCHIVE)
                if relative.parts[0] == ".runtime":
                    traced_paths["GENERATED_REBUILD_ARTIFACT"] += 1
                else:
                    assert digest(relative.read_bytes()) == expected, relative
                    traced_paths["REPO_PATH_RELOCATABLE"] += 1
            else:
                assert path.name == "python.exe"
                traced_paths["TOOLCHAIN_INTERPRETER"] += 1
        frozen = datetime.fromisoformat(seal["frozen_at_utc"])
        issued = datetime.fromisoformat(perturbation["issued_at_utc"])
        t1_completed = datetime.fromisoformat(commands[label])
        assert issued > frozen and issued > t1_completed
        result[label] = {"frozen_at_utc": seal["frozen_at_utc"], "t1_ended_utc": commands[label],
                         "absolute_archived_inputs_verified_by_role": dict(traced_paths),
                         "issued_at_utc": perturbation["issued_at_utc"], "freeze_sha256": digest(raw),
                         "published_perturbation_sha256": digest(source.read_bytes())}
    return result


def merge_review(manifest, acceptance):
    delta = diff(TESTED, PUBLICATION)
    assert set(delta) - {".gitattributes", BOUNDARY_SCRIPT, "docs/VALIDATION_QUALIFICATION.md",
        "docs/architecture/ARCHITECTURE_LOGICIELLE.md", "docs/architecture/ARCHITECTURE_MECANIQUE.md"} == {
        path for path in delta if path.startswith(PROOF.as_posix() + "/")}
    assert diff(BASE, TESTED) == manifest["divergent_files"]["base_to_merge"]
    assert diff(SOURCES["c3"][1], SOURCES["a6"][1]) == manifest["divergent_files"]["c3_to_a6"]
    assert dict((path, row["change"]) for path, row in manifest["merged_files"].items()) == diff(BASE, TESTED)
    checkout_changed = {}
    for path, entry in manifest["merged_files"].items():
        assert digest(blob(TESTED, path)) == entry["blob_sha256"]
        actual = digest(Path(path).read_bytes())
        if actual != entry["checkout_sha256"]:
            assert path in delta
            checkout_changed[path] = {"merge_checkout_sha256": entry["checkout_sha256"],
                                      "published_checkout_sha256": actual}
    assert set(checkout_changed) == {path for path, status in delta.items() if status == "M"}
    repository_formats = {}
    for path in [".gitattributes", BOUNDARY_SCRIPT, "convergence_manager/tests/replay_v3_c3.py",
                 "convergence_manager/tests/test_v3_a6_transactions.py",
                 (PROOF / "recipes/replay_builds.py").as_posix(),
                 (PROOF / "recipes/guards.ps1").as_posix(), (PROOF / "acceptance.json").as_posix()]:
        repository_formats[path] = git_text("check-attr", "text", "eol", "whitespace", "--", path).splitlines()
    old_attributes = blob(TESTED, ".gitattributes")
    new_attributes = blob(PUBLICATION, ".gitattributes")
    assert new_attributes.startswith(old_attributes)
    conflict_delta = git_text("merge-tree", BASE, C3_MERGE, SOURCES["a6"][1])
    conflict_files = []
    current = ""
    for line in conflict_delta.splitlines():
        if line.startswith("  base"):
            current = line.split(maxsplit=3)[-1]
        if line.startswith("+<<<<<<<") and current not in conflict_files:
            conflict_files.append(current)
    assert set(conflict_files) == set(manifest["conflicts"]), conflict_files
    git("diff", "--check", TESTED, PUBLICATION)
    git("diff", "--check", BASE, TESTED)
    published_assets = [ref_fingerprint(PUBLICATION, (ROOT / PROOF / row["path"]).resolve().relative_to(ROOT), row)
                        for row in acceptance["artifacts"]]
    registered = Path("convergence_manager/CMakeLists.txt")
    test_declarations = [re.findall(rb"add_test\(NAME\s+([^\s)]+)", blob(commit, registered))
                         for commit in (C3_MERGE, SOURCES["a6"][1], TESTED)]
    assert test_declarations[0] == test_declarations[1] == test_declarations[2]
    assert not any(status == "D" for status in diff(BASE, TESTED, "convergence_manager/tests").values())
    fixture_changes = diff("4600062ba7c277352c5c5914bce99782aead2f63", PUBLICATION,
                           "docs/electromechanical_v3/bench_c3_spatial",
                           "docs/electromechanical_v3/bench_c3_spatial_secondary")
    assert not fixture_changes
    return {"schema": "v3.int3.merge_integrity/1", "status": "PASS_WITH_REFUSED_REFERENCE",
            "tested_commit": TESTED, "published_commit": PUBLICATION,
            "merge_manifest_sha256": digest((PROOF / "merge_manifest.json").read_bytes()),
            "merge_manifest_files_verified": len(manifest["merged_files"]),
            "published_supports": published_assets, "publications_changes": delta,
            "test_tree_note": "Hors les preuves, trois documents vivants et les attributs qui les concernent, seul le script de refus indépendant du build a été ajouté.",
            "merge_checkout_files_superseded_by_publication": checkout_changed,
            "published_reference_review": reference_review(), "synthetic_bench_seals": model_review(),
            "protected_cartographer_seal": seal_review(), "integrator_freeze_chronology": freeze_review(),
            "repository_attributes": {"observed": repository_formats,
                                      "added_lines": new_attributes[len(old_attributes):].decode().splitlines()},
            "merge_conflicts_regenerated_read_only": sorted(conflict_files),
            "source_merge_review": {
                "declared_ctest_names_in_all_three_trees": [name.decode() for name in test_declarations[2]],
                "deleted_test_files": [],
                "reviewed_shared_files": {"convergence_manager/native/v3_mutate.py":
                    "Contrat spatial et obstacle contrôlés avant ouverture. Injection d’interruption bornée à l’effet A.6 CREATE_SUPPORT. L’admission d’une géométrie identique vise la branche spatiale pour les déplacements et reroutages.",
                    "convergence_manager/native/v3_verify.py":
                    "C.3 conserve L4_SPATIAL_CONTRACT, datums distincts, inclusion des arcs et solide obstacle. A.6 conserve la mesure des dimensions du Part::Cut et l’ancrage de l’effet signé.",
                    "convergence_manager/src/V3Transaction.cpp":
                    "authorized_effect vient du contexte A.6. La branche spatiale garde les deux faisceaux et les contrôles L4. Le chemin autorisé conserve les outils isolés et transitions journalisées.",
                    "convergence_manager/CMakeLists.txt":
                    "Même ensemble de déclarations de tests. Les outils et injections A.6 ont une configuration explicite. Les injections exigent un build de test sans confiance physique."},
                "first_spatial_fixture_commit": "4600062ba7c277352c5c5914bce99782aead2f63",
                "spatial_fixture_change_after_creation": fixture_changes}}


def run():
    assert Path(".git").is_file()
    os.environ["GIT_OPTIONAL_LOCKS"] = "0"
    sys.path.insert(0, str(ROOT))
    acceptance = read(PROOF / "acceptance.json")
    manifest = read(PROOF / "merge_manifest.json")
    output = {"git_history_review.json": graph_review(manifest, acceptance),
              "merge_integrity.json": merge_review(manifest, acceptance)}
    for name, payload in output.items():
        payload["observed_at_utc"] = datetime.now(timezone.utc).isoformat()
        (OUTPUT / name).write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8",
                                   newline="\n")
    print("Git et scellés contrôlés, détails dans .runtime/git-review.")


if __name__ == "__main__":
    run()
