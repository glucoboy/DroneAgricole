"""Réception de la porte V2.1 sur le gel GO3A historique."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

CORE = str(Path(sys.argv.pop(1)).resolve())
PLAN = Path("convergence_manager/fixtures/v21_h01_exploration.json")
MANIFEST = Path("docs/verification/go3b/GO3B_SOURCE_MANIFEST.json")
ADMISSION = MANIFEST.with_name("GO3B_ADMISSION.json")


def load(path):
    return json.loads(path.read_bytes())


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


class Admission(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="v21-test-", dir=Path(".runtime"))
        self.addCleanup(self.tmp.cleanup)
        self.work = Path(self.tmp.name)

    def run_gate(self, mode, name, expected, *args, error=None):
        output = self.work / name
        run = subprocess.run(
            [CORE, "preflight", "--mode", mode, "--output", str(output), *map(str, args)],
            capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
        )
        self.assertEqual(run.returncode, expected, run.stderr + run.stdout)
        if error is not None:
            self.assertIn(error, run.stderr)
        report = output / "preflight.json"
        return load(report) if report.exists() else None

    def plan(self, **changes):
        path = self.work / "plan.json"
        path.write_text(json.dumps({**load(PLAN), **changes}), encoding="utf-8")
        return path

    def test_historical_exploration_and_final(self):
        authorities = {**load(MANIFEST)["files"], str(MANIFEST): digest(MANIFEST), str(ADMISSION): digest(ADMISSION)}
        historical = self.run_gate("historical", "history", 2)
        self.assertEqual(historical["verdict"], "NO_GO_MOTIVE")
        self.assertIs(historical["historical"]["autorisation_go3b"], False)
        self.assertEqual(historical["historical"]["built"], 0)
        self.assertEqual(historical["historical"]["build_limit"], 12)
        explore = self.run_gate("explore", "explore", 0)
        self.assertEqual(explore["verdict"], "EXPLORATION_ALLOWED")
        self.assertEqual({row["state"] for row in explore["queue"]}, {"RESEARCH_REQUIRED", "READY_ON_COPY"})
        final = self.run_gate("final", "final", 2)
        self.assertEqual(final["verdict"], "FINAL_NO_GO")
        self.assertEqual(final["evidence_gap"], explore["evidence_gap"])
        self.assertEqual({gap["status"] for gap in final["evidence_gap"].values()}, {"INCONCLUSIVE"})
        self.assertEqual(len(final["evidence_gap"]), 8)
        for path, sha in authorities.items():
            self.assertEqual(digest(Path(path)), sha, path)

    def test_unsafe_plan_variants(self):
        for index, change in enumerate((
            {"write_target": str(MANIFEST)},
            {"preserve_connectivity": False},
            {"constraints_enabled": False},
            {"unpowered": False},
            {"private_copy": None},
            {"trial": "PHYSICAL_MATING"},
        )):
            with self.subTest(change=change):
                report = self.run_gate("explore", f"unsafe-{index}", 2, "--plan", self.plan(**change))
                self.assertEqual(report["verdict"], "EXPLORATION_BLOCKED")
                self.assertTrue(report["blocks"])
                self.assertEqual(report["queue"], [])

    def test_each_evidence_status_is_preserved(self):
        for status in ("UNKNOWN", "INCONCLUSIVE", "NOT_RUN", "FAIL"):
            with self.subTest(status=status):
                report = self.run_gate("explore", status, 2 if status == "FAIL" else 0,
                                       "--plan", self.plan(trial_findings={"collision": status}))
                self.assertEqual(report["trial_findings"], {"collision": status})
                self.assertTrue(all(gap["status"] == "INCONCLUSIVE" for gap in report["evidence_gap"].values()))
                if status == "FAIL":
                    self.assertIn("KNOWN_VIOLATION:collision", report["blocks"])

    def test_pause_resume_and_identity(self):
        paused = self.run_gate("explore", "campaign", 4, "--steps", 2)
        self.assertEqual(paused["campaign_state"], "PAUSED")
        self.assertEqual(len(paused["queue"]), 2)
        self.assertEqual(self.run_gate("explore", "campaign", 4, "--steps", 0), paused)
        complete = self.run_gate("explore", "campaign", 0)
        self.assertEqual(complete["campaign_state"], "PLANNED")
        self.assertEqual(complete["queue"][:2], paused["queue"])
        self.assertEqual(len(complete["queue"]), 8)
        report = self.work / "campaign/preflight.json"
        original = report.read_bytes()
        self.assertEqual(self.run_gate("explore", "campaign", 0), complete)
        self.assertEqual(report.read_bytes(), original)
        self.assertEqual(complete["budget"]["variants_built"], 0)
        self.assertTrue(all(row["budget_spent"] == 0 for row in complete["queue"]))
        self.run_gate("explore", "campaign", 1, "--plan", self.plan(trial="RADIUS_SENSITIVITY"))
        self.assertEqual(report.read_bytes(), original)
        self.run_gate("final", "campaign", 1)
        self.assertEqual(report.read_bytes(), original)

    def test_exploration_never_substitutes_for_reception(self):
        self.run_gate("explore", "explore", 0)
        self.assertIsNone(self.run_gate("final", "bad-receipt", 1, "--receipt",
                                       self.work / "explore/preflight.json"))

    def test_known_connectivity_loss_and_collision_spend_nothing(self):
        for finding in ("connectivity_loss", "forbidden_collision"):
            with self.subTest(finding=finding):
                plan = self.plan(trial_findings={finding: "FAIL"})
                report = self.run_gate("explore", finding, 2, "--plan", plan)
                self.assertIn("KNOWN_VIOLATION:" + finding, report["blocks"])
                self.assertEqual(report["queue"], [])
                self.assertEqual(report["budget"]["variants_built"], 0)
                self.assertFalse((self.work / finding / "candidate").exists())

    def test_trial_pass_cannot_close_final_evidence(self):
        plan = self.plan(trial_findings={"envelope_clear_on_copy": "PASS"})
        explore = self.run_gate("explore", "claimed-pass", 0, "--plan", plan)
        self.assertEqual(explore["evidence_gap"]["G3A-02"]["status"], "INCONCLUSIVE")
        reception = self.run_gate("final", "final-after-claim", 2)
        self.assertEqual(reception["verdict"], "FINAL_NO_GO")
        self.assertEqual(reception["evidence_gap"], explore["evidence_gap"])

    def test_changed_historical_authority_rejected(self):
        fake = self.work / "fake"
        (fake / MANIFEST.parent).mkdir(parents=True)
        (fake / ".runtime").mkdir()
        (fake / MANIFEST).write_bytes(MANIFEST.read_bytes() + b" ")
        self.assertIsNone(self.run_gate("historical", "tampered", 1, "--root", fake,
                                       "--output", ".runtime/probe", error="GO3B_SOURCE_MANIFEST.json"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
