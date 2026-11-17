"""Réception L1 sur le binaire C++17 indiqué par TECHNICAL_RESEARCH_CORE."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from technical_research_engine import ResearchEngine, ResearchEngineError


REPOSITORY = Path(__file__).resolve().parents[2]
CARTOGRAPHE_CATALOG = REPOSITORY / "docs/electromechanical_v2/L1_CARTOGRAPHE.json"
SOURCE_DATE = "2026-11-12T10:00:00Z"


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reference(part_number="FC-06-R", revision="R2"):
    return {
        "manufacturer": "Fabricant synthétique",
        "family": "FC",
        "part_number": part_number,
        "revision": revision,
        "attributes": {"ways": "6", "orientation": "right", "end": "out"},
    }


def applicability(mode="STATIC"):
    return {
        "domain": "DOCUMENT",
        "conditions": {
            "configuration": "banc_synthetique",
            "mode": mode,
            "temperature": "20 degC",
        },
    }


def question(issue_id="BENCH.BEND", parameter="bend_radius", unit="mm"):
    return {
        "issue_id": issue_id,
        "question": {
            "id": f"Q.{issue_id}",
            "subject_ids": ["Banc.FC"],
            "status": "OPEN",
            "question": f"Quelle valeur pour {parameter} ?",
            "hypothesis": "La variante du banc dispose d'une fiche révisée.",
            "expected_evidence": "Fiche du fabricant pour la variante et la révision.",
            "refutation": "Étiquette ou valeur incompatible sur la fiche applicable.",
            "dependent_decision": "Définir le domaine du calcul du banc.",
            "evidence_ids": [],
        },
        "parameter": parameter,
        "unit": unit,
        "criticality": "HIGH",
        "reference": reference(),
        "applicability": applicability(),
        "expected_authority": "MANUFACTURER",
        "study": {
            "strategy": "Étudier les jeux sur les poses du banc.",
            "variables": ["rayon", "pose"],
            "next_observation": "Relever la révision du cordon et la limite applicable.",
        },
    }


class PythonClientTests(unittest.TestCase):
    def test_submission_forwards_options_and_preserves_unknown(self):
        engine = ResearchEngine("project", "reports", "core", "catalog.json")
        response = {"issue_id": "BENCH.BEND", "outcome": "UNKNOWN"}
        process = subprocess.CompletedProcess([], 0, json.dumps(response).encode("utf-8"), b"")
        with patch("technical_research_engine.subprocess.run", return_value=process) as run:
            self.assertEqual(engine.submit_issue("BENCH.BEND", online=True, refresh=True), response)
        self.assertEqual(run.call_args.args[0], [
            "core", "submit", "--store", "reports", "--root", "project",
            "--catalog", "catalog.json", "--issue", "BENCH.BEND", "--online", "--refresh",
        ])

    def test_missing_issue_propagates_the_structured_native_error(self):
        engine = ResearchEngine("project", "reports", "core")
        response = {"issue_id": "BENCH.BEND", "error": "REPORT_NOT_FOUND"}
        process = subprocess.CompletedProcess([], 3, json.dumps(response).encode("utf-8"), b"")
        with patch("technical_research_engine.subprocess.run", return_value=process):
            with self.assertRaises(ResearchEngineError) as error:
                engine.get_issue("BENCH.BEND")
        self.assertEqual(error.exception.returncode, 3)
        self.assertEqual(error.exception.response, response)


class NativeResearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        binary = os.environ.get("TECHNICAL_RESEARCH_CORE")
        if not binary:
            raise RuntimeError("Définir TECHNICAL_RESEARCH_CORE vers le binaire L1 compilé.")
        cls.binary = Path(binary).resolve(strict=True)

    def setUp(self):
        temporary = self.enterContext(tempfile.TemporaryDirectory(prefix="l1 research "))
        self.workspace = Path(temporary)
        self.root = self.workspace / "sources"
        self.root.mkdir()
        self.store = self.workspace / "reports"
        self.catalog = self.root / "catalog.json"
        self.request = question()
        self.sources = []

    def local(self, source_id, value=22, *, source_reference=None, scope=None,
              authority="MANUFACTURER", page=7, artifact_id=None, pin=True):
        identity = source_reference or reference()
        path = f"documents/{source_id}.json"
        checksum = write_json(
            self.root / path,
            {"id": artifact_id or identity["part_number"], "measurement": value},
        )
        source = {
            "parameter": self.request["parameter"],
            "reference": identity,
            "applicability": scope or applicability(),
            "authority": authority,
            "confidence": "HIGH",
            "unit": self.request["unit"],
            "uncertainty": None,
            "evidence": {
                "id": source_id,
                "kind": "SOURCE",
                "domain": "DOCUMENT",
                "artifact_path": path,
                "uri": None,
                "sha256": checksum if pin else None,
                "locator": f"p. {page}, /measurement",
                "revision": "Fiche A1",
                "collected_at": SOURCE_DATE,
                "method": "Lecture d'une valeur et contrôle du MPN au pointeur JSON.",
                "hypothetical": False,
                "limits": "Banc synthétique, température et mode indiqués.",
            },
            "extraction": {
                "format": "JSON_POINTER",
                "value": "/measurement",
                "checks": {"/id": identity["part_number"]},
            },
        }
        self.sources.append(source)
        return source

    def remote(self):
        source = self.local("E.remote")
        source["evidence"].update(
            artifact_path=None,
            uri="https://l1-test.invalid/document",
            sha256=None,
            limits="Fiche à consulter. La référence ne sera vérifiée qu'après lecture.",
        )
        source["extraction"] = {
            "format": "TEXT_REGEX",
            "pattern": r"FC-06-R\s*\nRadius: (\d+) mm",
            "markers": [source["reference"]["part_number"]],
            "value_type": "NUMBER",
        }

    def publish_catalog(self, *other_requests):
        write_json(self.catalog, {
            "schema_version": "1.0.0",
            "configuration_id": "banc_synthetique",
            "questions": [self.request, *other_requests],
            "sources": self.sources,
        })

    def native(self, verb, *flags, status=0):
        command = [str(self.binary), verb, "--store", str(self.store)]
        if verb != "invalidate":
            command.extend(["--root", str(self.root)])
        if verb == "submit":
            command.extend(["--catalog", str(self.catalog)])
        completed = subprocess.run(
            [*command, *flags], capture_output=True, encoding="utf-8", timeout=30,
            cwd=REPOSITORY, check=False,
        )
        self.assertEqual(completed.returncode, status, completed.stdout + completed.stderr)
        return json.loads(completed.stdout)

    def submit(self, *flags, issue=None, status=0):
        return self.native("submit", "--issue", issue or self.request["issue_id"],
                           *flags, status=status)

    def assert_unknown(self, report, outcome="UNKNOWN"):
        self.assertEqual(report["outcome"], outcome)
        self.assertEqual(report["question"]["status"], "OPEN")
        self.assertEqual(report["value"]["status"], "UNKNOWN")
        self.assertIsNone(report["value"]["value"])
        self.assertIsNone(report["value"]["uncertainty"])
        self.assertIsNone(report["value"]["precision"])
        [entry] = report["unknown_register"]
        self.assertEqual(entry["issue_id"], report["issue_id"])
        self.assertEqual(entry["question_id"], report["question"]["id"])
        self.assertTrue(entry["reason"])
        self.assertTrue(entry["study"]["next_observation"])

    def test_local_value_preserves_file_page_and_document_revision(self):
        source = self.local("E.sheet", 22.5)
        path = self.root / "documents/E.sheet.txt"
        path.write_text("Extract from page 7\nFC-06-R\nRadius: 22.5 mm\n", encoding="utf-8")
        source["evidence"].update(
            artifact_path="documents/E.sheet.txt",
            sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            locator="p. 7, ligne Radius",
            method="Transcription du relevé local de la page 7.",
        )
        source["extraction"] = {
            "format": "TEXT_REGEX",
            "pattern": r"FC-06-R\s*\nRadius: ([0-9.]+) mm",
            "markers": ["FC-06-R"],
            "value_type": "NUMBER",
        }
        self.publish_catalog()
        report = self.submit()
        self.assertEqual(report["outcome"], "RESOLVED")
        self.assertEqual(report["question"]["status"], "CLOSED")
        self.assertEqual(report["value"]["status"], "SOURCED")
        self.assertEqual(report["value"]["value"], 22.5)
        self.assertEqual(report["value"]["unit"], "mm")
        self.assertEqual(report["value"]["evidence_ids"], ["E.sheet"])
        self.assertEqual(report["question"]["evidence_ids"], ["E.sheet"])
        [evidence] = report["technical_evidence"]
        self.assertEqual(evidence["artifact_path"], "documents/E.sheet.txt")
        self.assertEqual(evidence["locator"], "p. 7, ligne Radius")
        self.assertEqual(evidence["sha256"], source["evidence"]["sha256"])
        self.assertEqual(evidence["revision"], "Fiche A1")
        self.assertEqual(evidence["collected_at"], SOURCE_DATE)
        [detail] = report["evidence_details"]
        self.assertEqual(detail["reference"], reference())
        self.assertEqual(detail["applicability"], applicability())
        self.assertEqual(detail["match"], "EXACT")
        self.assertEqual(detail["confidence"], "HIGH")
        self.assertEqual(report["unknown_register"], [])
        self.assertEqual(report["network"], "DISABLED")

    def test_nearby_references_and_qualifiers_never_supply_the_answer(self):
        suffix = reference(part_number="FC-06-L")
        family = {**reference(), "family": "FC2"}
        manufacturer = {**reference(), "manufacturer": "Autre fabricant"}
        self.local("E.suffix", source_reference=suffix)
        self.local("E.family", source_reference=family)
        self.local("E.manufacturer", source_reference=manufacturer)
        for name, changed_value in (("ways", "8"), ("orientation", "left"), ("end", "in")):
            variant = reference()
            variant["attributes"][name] = changed_value
            self.local(f"E.{name}", source_reference=variant)
        self.publish_catalog()
        report = self.submit()
        self.assert_unknown(report)
        self.assertFalse(report["value"]["evidence_ids"])
        self.assertEqual(
            {entry["match"] for entry in report["evidence_details"]},
            {"REFERENCE_MISMATCH"},
        )
        self.assertEqual(len(report["technical_evidence"]), 6)

    def test_static_radius_does_not_answer_a_dynamic_question(self):
        self.request["applicability"] = applicability(mode="DYNAMIC")
        self.local("E.static")
        self.publish_catalog()
        report = self.submit()
        self.assert_unknown(report)
        self.assertEqual(report["evidence_details"][0]["match"], "SCOPE_MISMATCH")

    def test_conflicting_documents_preserve_both_values_and_revisions(self):
        for revision in ("R1", "R2"):
            with self.subTest(revision=revision):
                self.sources.clear()
                self.local("E.current", 22)
                self.local("E.other", 48, source_reference=reference(revision=revision))
                self.publish_catalog()
                report = self.submit("--refresh")
                self.assert_unknown(report, "INCONCLUSIVE")
                self.assertIn({"E.current", "E.other"}, [set(pair) for pair in report["conflicts"]])
                self.assertEqual({e["id"] for e in report["technical_evidence"]},
                                 {"E.current", "E.other"})
                values = {d["evidence_id"]: d for d in report["evidence_details"]}
                self.assertEqual(values["E.current"]["value"]["value"], 22)
                self.assertEqual(values["E.other"]["value"]["value"], 48)
                self.assertEqual(values["E.other"]["reference"]["revision"], revision)

    def test_manufacturer_unavailable_offline_with_secondary_source(self):
        self.remote()
        self.local("E.secondary", authority="SECONDARY")
        self.publish_catalog()
        report = self.submit()
        self.assert_unknown(report)
        self.assertEqual(report["network"], "DISABLED")
        self.assertEqual([e["id"] for e in report["technical_evidence"]], ["E.secondary"])
        self.assertEqual(report["evidence_details"][0]["match"], "AUTHORITY_MISMATCH")
        self.assertFalse(report["value"]["evidence_ids"])

    def test_online_permission_still_prefers_a_conclusive_local_source(self):
        self.remote()
        self.local("E.local")
        self.publish_catalog()
        report = self.submit("--online")
        self.assertEqual(report["outcome"], "RESOLVED")
        self.assertEqual(report["network"], "NOT_NEEDED")
        self.assertEqual(report["value"]["evidence_ids"], ["E.local"])
        self.assertEqual([e["id"] for e in report["technical_evidence"]], ["E.local"])

    def test_catalog_claim_cannot_override_the_identifier_in_the_artifact(self):
        self.local("E.mislabelled", artifact_id="FC-06-R2")
        self.publish_catalog()
        report = self.submit()
        self.assert_unknown(report)
        self.assertFalse(report["technical_evidence"])
        self.assertIn("E.mislabelled", {item["source_id"] for item in report["diagnostics"]})

    def test_identifier_in_another_json_record_cannot_attest_a_value(self):
        source = self.local("E.crossedJson")
        source["evidence"]["sha256"] = write_json(
            self.root / source["evidence"]["artifact_path"],
            [{"id": "FC-06-R"}, {"id": "FC-06-L", "measurement": 38}],
        )
        source["extraction"].update(value="/1/measurement", checks={"/0/id": "FC-06-R"})
        self.publish_catalog()
        report = self.submit()
        self.assert_unknown(report)
        self.assertFalse(report["technical_evidence"])

    def test_identifier_on_another_text_row_cannot_attest_a_value(self):
        source = self.local("E.crossedText")
        path = self.root / "documents/E.crossedText.txt"
        path.write_text("FC-06-R: n.d.\nFC-06-L: 38 mm\n", encoding="utf-8")
        source["evidence"].update(
            artifact_path="documents/E.crossedText.txt",
            sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        )
        source["extraction"] = {
            "format": "TEXT_REGEX",
            "pattern": r"FC-06-L: (\d+) mm",
            "markers": ["FC-06-R"],
            "value_type": "NUMBER",
        }
        self.publish_catalog()
        report = self.submit()
        self.assert_unknown(report)
        self.assertFalse(report["technical_evidence"])

    def test_pinned_artifact_mismatch_never_yields_a_sourced_value(self):
        source = self.local("E.pinned")
        self.publish_catalog()
        write_json(self.root / source["evidence"]["artifact_path"],
                   {"id": "FC-06-R", "measurement": 24})
        report = self.submit()
        self.assert_unknown(report)
        self.assertFalse(report["technical_evidence"])
        self.assertIn("E.pinned", {item["source_id"] for item in report["diagnostics"]})

    def test_invalid_collection_date_cannot_produce_documentary_proof(self):
        source = self.local("E.invalidDate")
        source["evidence"]["collected_at"] = "2026-02-30T10:00:00Z"
        self.publish_catalog()
        report = self.submit()
        self.assert_unknown(report)
        self.assertFalse(report["technical_evidence"])
        self.assertIn("E.invalidDate", {item["source_id"] for item in report["diagnostics"]})

    def test_numeric_value_with_a_different_unit_cannot_resolve_the_issue(self):
        source = self.local("E.current", 22)
        source["unit"] = "A"
        self.publish_catalog()
        report = self.submit()
        self.assert_unknown(report)
        self.assertEqual(report["evidence_details"][0]["match"], "SCOPE_MISMATCH")

    def test_hypothetical_source_cannot_resolve_the_issue(self):
        source = self.local("E.hypothetical")
        source["evidence"]["hypothetical"] = True
        self.publish_catalog()
        report = self.submit()
        self.assert_unknown(report)
        self.assertFalse(report["technical_evidence"])

    def test_local_path_cannot_escape_the_source_root(self):
        source = self.local("E.outside")
        source["evidence"]["artifact_path"] = "../outside.json"
        source["evidence"]["sha256"] = write_json(
            self.workspace / "outside.json", {"id": "FC-06-R", "measurement": 91},
        )
        self.publish_catalog()
        report = self.submit()
        self.assert_unknown(report)
        self.assertFalse(report["technical_evidence"])
        self.assertIn("E.outside", {item["source_id"] for item in report["diagnostics"]})

    def test_conditional_derivation_has_bounds_and_recalculates(self):
        self.request = question(parameter="length_difference")
        derivation = {
            "operation": "LENGTH_DIFFERENCE",
            "inputs": {
                "available": {"value": 110, "unit": "mm", "uncertainty": 2},
                "required": {"value": 100, "unit": "mm", "uncertainty": 3},
            },
            "assumptions": ["Les deux longueurs portent sur le même trajet nominal."],
            "limits": "Le calcul du jeu projeté ne couvre ni effort ni fatigue.",
        }
        self.request["derivation"] = derivation
        self.publish_catalog()
        original = self.submit()
        self.assertEqual(original["outcome"], "CONDITIONAL")
        self.assertEqual(original["question"]["status"], "OPEN")
        self.assertEqual(original["value"]["status"], "CALCULATED")
        self.assertEqual(original["value"]["value"], 10)
        self.assertEqual(original["value"]["unit"], "mm")
        self.assertEqual(original["value"]["uncertainty"], 5)
        self.assertTrue(original["value"]["method"])
        self.assertTrue(original["value"]["input_value_refs"])
        self.assertTrue(original["value"]["limits"])
        self.assertTrue(original["unknown_register"])
        self.assertEqual(original["derivation"]["bounds"], {"lower": 5, "upper": 15})
        self.assertTrue(original["derivation"]["equation"])
        for pointer in original["value"]["input_value_refs"]:
            value = original
            for token in pointer.lstrip("/").split("/"):
                value = value[token.replace("~1", "/").replace("~0", "~")]
            self.assertEqual(value["status"], "ASSUMED")
            self.assertEqual(value["unit"], "mm")
        derivation["inputs"]["available"]["value"] = 105
        derivation["assumptions"] = ["La butée est avancée de 5 mm."]
        self.publish_catalog()
        modified = self.submit()
        self.assertEqual(modified["value"]["value"], 5)
        self.assertEqual(modified["value"]["uncertainty"], 5)
        self.assertNotEqual(modified["cache"]["key"], original["cache"]["key"])
        self.assertFalse(modified["cache"]["hit"])

    def test_repeat_uses_cache_and_changed_source_requires_reinvestigation(self):
        source = self.local("E.mutable", pin=False)
        self.publish_catalog()
        first = self.submit()
        second = self.submit()
        self.assertEqual(first["outcome"], "RESOLVED")
        self.assertFalse(first["cache"]["hit"])
        self.assertTrue(second["cache"]["hit"])
        self.assertEqual(first["cache"]["key"], second["cache"]["key"])
        self.assertEqual(first["technical_evidence"], second["technical_evidence"])
        refreshed = self.submit("--refresh")
        self.assertFalse(refreshed["cache"]["hit"])
        self.assertEqual(first["cache"]["key"], refreshed["cache"]["key"])
        issue = self.request["issue_id"]
        recalled = self.native("get", "--issue", issue)
        self.assertEqual(recalled["value"], second["value"])
        write_json(self.root / source["evidence"]["artifact_path"],
                   {"id": "FC-06-R", "measurement": 40})
        self.native("get", "--issue", issue, status=3)
        updated = self.submit()
        self.assertEqual(updated["value"]["value"], 40)
        self.assertFalse(updated["cache"]["hit"])
        self.assertNotEqual(updated["cache"]["key"], second["cache"]["key"])

    def test_component_revision_change_invalidates_cached_conclusion(self):
        self.local("E.oldRevision")
        self.publish_catalog()
        original = self.submit()
        self.request["reference"]["revision"] = "R3"
        self.publish_catalog()
        issue = self.request["issue_id"]
        self.native("get", "--issue", issue, status=3)
        listing = self.native("list", "--view", "reports")
        self.assertEqual(listing["items"], [])
        self.assertEqual(listing["stale_issue_ids"], [issue])
        updated = self.submit()
        self.assert_unknown(updated)
        self.assertEqual(updated["evidence_details"][0]["match"], "REVISION_MISMATCH")
        self.assertNotEqual(original["cache"]["key"], updated["cache"]["key"])

    def test_changed_cache_cannot_be_read_as_an_authentic_report(self):
        self.local("E.cached")
        self.publish_catalog()
        original = self.submit()
        issue = self.request["issue_id"]
        [path] = self.store.glob("report-*.json")
        receipt = json.loads(path.read_text(encoding="utf-8"))
        receipt["report"]["value"]["value"] = 99
        write_json(path, receipt)
        rejected = self.native("get", "--issue", issue, status=1)
        self.assertTrue(rejected["error"])
        restored = self.submit("--refresh")
        self.assertEqual(restored["value"]["value"], original["value"]["value"])
        self.assertFalse(restored["cache"]["hit"])

    def test_unknown_issue_does_not_block_a_separate_issue(self):
        issue = self.request["issue_id"]
        self.local("E.independent")
        second_request = question("BENCH.FATIGUE", parameter="fatigue_life", unit="1")
        second_issue = second_request["issue_id"]
        self.publish_catalog(second_request)
        self.assert_unknown(self.submit(issue=second_issue))
        self.assertEqual(self.submit()["outcome"], "RESOLVED")
        self.native("invalidate", "--issue", second_issue)
        self.native("get", "--issue", second_issue, status=3)
        self.assertEqual(self.native("get", "--issue", issue)["outcome"], "RESOLVED")

    def test_python_api_submits_lists_and_recalls_by_issue_id(self):
        self.local("E.recall")
        second = question("BENCH.CURRENT", parameter="current_limit", unit="A")
        self.publish_catalog(second)
        issue = self.request["issue_id"]
        engine = ResearchEngine(self.root, self.store, self.binary, self.catalog)
        submitted = engine.submit_issue(issue)
        self.assert_unknown(engine.submit_issue(second["issue_id"]))
        recalled = engine.get_issue(issue)
        self.assertEqual(recalled["issue_id"], issue)
        self.assertEqual(recalled["question"], submitted["question"])
        self.assertEqual(recalled["technical_evidence"], submitted["technical_evidence"])
        self.assertEqual({entry["issue_id"] for entry in engine.list_reports()["items"]},
                         {issue, second["issue_id"]})
        self.assertEqual(len(engine.list_evidence()["items"]), 1)
        self.assertEqual([entry["issue_id"] for entry in engine.list_unknowns()["items"]],
                         [second["issue_id"]])
        engine.invalidate_issue(issue)
        with self.assertRaises(ResearchEngineError) as error:
            engine.get_issue(issue)
        self.assertEqual(error.exception.returncode, 3)

    def test_python_cli_exports_finalized_json_and_reopens_it_by_issue_id(self):
        self.local("E.cli")
        self.publish_catalog()
        issue = self.request["issue_id"]
        output = self.workspace / "rapport F16.json"
        command = [
            sys.executable, "-B", "-m", "technical_research_engine",
            "--executable", str(self.binary), "--root", str(self.root),
            "--store", str(self.store), "--catalog", str(self.catalog),
        ]
        submitted = subprocess.run(
            [*command, "submit", issue, "--output", str(output)], check=True,
            cwd=REPOSITORY, timeout=30, capture_output=True, encoding="utf-8",
        )
        self.assertEqual(json.loads(submitted.stdout), json.loads(output.read_text("utf-8")))
        published = output.read_bytes()
        duplicate = subprocess.run(
            [*command, "submit", issue, "--output", str(output)], check=False,
            cwd=REPOSITORY, timeout=30, capture_output=True, encoding="utf-8",
        )
        self.assertEqual(duplicate.returncode, 1)
        self.assertTrue(json.loads(duplicate.stdout)["error"])
        self.assertEqual(output.read_bytes(), published)
        recalled = subprocess.run(
            [*command, "get", issue], check=True, cwd=REPOSITORY, timeout=30,
            capture_output=True, encoding="utf-8",
        )
        self.assertEqual(json.loads(recalled.stdout)["value"]["value"], 22)

    def test_real_f16_catalog_distinguishes_cad_and_installed_cable(self):
        self.root = REPOSITORY
        self.catalog = CARTOGRAPHE_CATALOG
        route = self.submit(issue="F16-AXIS-ACTIVE")
        self.assertEqual(route["outcome"], "RESOLVED")
        self.assertAlmostEqual(route["value"]["value"], 425.17384217864503)
        self.assertEqual(route["value"]["unit"], "mm")
        [evidence] = [entry for entry in route["technical_evidence"]
                      if entry["id"] in route["value"]["evidence_ids"]]
        self.assertEqual(
            evidence["artifact_path"],
            "hardware/mecanique/cartographe/verification/routes_prototype.json",
        )
        self.assertEqual(evidence["locator"], "/routes/35/longueur_courbe_mm")
        self.assertEqual(evidence["sha256"],
                         "20227cdd9a875d0573e8b85346f3268cc18ad6e243da21efa046d482d52e11ae")
        self.assert_unknown(self.submit(issue="F16-MOUNTED-BEND-RADIUS"))


if __name__ == "__main__":
    unittest.main()
