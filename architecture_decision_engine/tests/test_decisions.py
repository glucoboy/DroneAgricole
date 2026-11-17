import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path.cwd()
CORE, L1 = map(lambda path: Path(path).resolve(), sys.argv[1:3])
FIXTURES = ROOT / "architecture_decision_engine" / "fixtures"
sys.argv[1:] = []


def load(path):
    return json.loads(path.read_bytes())


def semantic(value):
    if isinstance(value, list):
        return [semantic(item) for item in value]
    if isinstance(value, dict):
        return {key: semantic(item) for key, item in value.items()
                if key not in {"sha256", "l1_stdout_sha256", "decisions_sha256", "collected_at"}}
    return value


class ArchitectureDecisions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        runtime = ROOT / ".runtime"
        runtime.mkdir(exist_ok=True)
        cls.work = tempfile.TemporaryDirectory(prefix="l3-test-", dir=runtime)
        cls.addClassCleanup(cls.work.cleanup)
        cls.path = Path(cls.work.name)
        cls.run_dir = cls.path / "nominal"
        result = cls.invoke(cls.run_dir)
        if result.returncode != 0:
            raise RuntimeError(f"code {result.returncode}: {result.stderr}\n{result.stdout}")
        cls.campaign = load(cls.run_dir / "campaign.json")

    @staticmethod
    def invoke(output, *args, l1=L1):
        return subprocess.run(
            [CORE, "--root", ROOT, "--output", output, "--l1", l1, *args],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
        )

    def candidate(self, name):
        return load(self.run_dir / "candidates" / f"{name}.json")

    def mutate(self, name, filename, mutator, option):
        data = load(FIXTURES / filename)
        mutator(data)
        fixture = self.path / f"{name}.json"
        fixture.write_text(json.dumps(data), encoding="utf-8")
        out = self.path / name
        return self.invoke(out, option, fixture), out

    def test_f31_changes_family_when_service_remains_obstructed(self):
        self.assertEqual(self.campaign["verdict"], "L3_PASS")
        nominal = self.candidate("f31-baseline")
        over = self.candidate("f31-over-l2")
        under = self.candidate("f31-under-l2")
        shifted = self.candidate("f31-shift")
        conflicts = {c["requirement_id"]: c for c in nominal["conflict_graph"]}
        self.assertEqual(nominal["status"], "FAIL")
        self.assertAlmostEqual(conflicts["f31-extraction"]["observed_margin"], -1.6)
        for proposal in (over, under):
            self.assertEqual(proposal["route_checks"]["status"], "PASS")
            self.assertEqual(proposal["report"]["geometry"], "FAIL")
        self.assertNotEqual(over["report"]["native_plan"]["cables"], under["report"]["native_plan"]["cables"])
        self.assertEqual((shifted["family"], shifted["status"]), ("PLACEMENT", "PASS"))

    def test_real_l1_research_keeps_lateral_connector_open(self):
        lateral = self.candidate("f31-lateral")
        report = self.candidate("f31-lateral-research")
        l2 = self.candidate("f31-lateral-l2")
        self.assertEqual(lateral["status"], "INCONCLUSIVE")
        self.assertEqual(lateral["research_evidence"]["question"]["status"], "OPEN")
        self.assertEqual(report["outcome"], "UNKNOWN")
        self.assertIsNone(report["value"]["value"])
        self.assertEqual(report["evidence_details"][0]["match"], "REFERENCE_MISMATCH")
        self.assertEqual(l2["report"]["compatibility"], "INCONCLUSIVE")
        self.assertIsNone(lateral["parameters"]["lateral_exit_mm"])
        study = lateral["parametric_study"]
        self.assertEqual(study["sampled_transition_brackets_mm"], [[12, 16]])
        self.assertGreater(study["samples"][0]["margin_mm"], 0)
        self.assertLess(study["samples"][-1]["margin_mm"], 0)

    def test_diagnostic_escalation_preserves_functions_and_electrical_contract(self):
        bench = self.campaign["benches"]["diagnostic"]
        self.assertEqual(bench["local_attempts"], 2)
        self.assertEqual([a["status"] for a in bench["attempts"][:2]], ["FAIL", "FAIL"])
        baseline = self.candidate("diagnostic-baseline")
        self.assertEqual(baseline["conflict_graph"][0]["margin_range"],
                         {"minimum": -4, "maximum": -1, "unit": "mm"})
        placed = self.candidate("diag-placement")
        passive = self.candidate("diag-passive")
        active = self.candidate("diag-active")
        self.assertEqual([c["status"] for c in (placed, passive, active)], ["PASS", "PASS", "INCONCLUSIVE"])
        self.assertNotEqual(passive["parameters"]["connection_graph"], placed["parameters"]["connection_graph"])

    def test_consolidation_rechecks_implicit_conflict_and_accepts_compatible_pair(self):
        incompatible = self.candidate("diag-incompatible")
        joint = incompatible["joint_evaluation"]
        margins = {f["requirement_id"]: f["margin"] for f in joint["findings"]}
        self.assertEqual(incompatible["status"], "FAIL")
        self.assertEqual(margins["diag-shared-volume"], -3)
        self.assertEqual(self.candidate("diag-compatible")["status"], "PASS")
        assignment = self.candidate("diag-assignment-conflict")
        self.assertEqual(assignment["status"], "FAIL")
        self.assertEqual({c["code"] for c in assignment["conflicts"]}, {"CONFLICTING_ASSIGNMENTS"})

    def test_all_links_connected_to_a_moved_equipment_are_rechecked(self):
        for name, links in (("f31-shift", ["F31", "F35", "PWR1", "PWR2"]),
                            ("diag-placement", ["F40", "F41", "F24A", "COAX"])):
            report = self.candidate(name)
            self.assertEqual(report["impacted_links"], links)
            self.assertEqual(set(report["reevaluated_links"]), set(links))

    def test_pareto_and_decision_lifecycle(self):
        compare = self.campaign["benches"]["diagnostic"]["comparison"]
        self.assertEqual(compare["frontier"], ["diag-compact", "diag-passive", "diag-placement"])
        self.assertEqual(compare["dominated_by"], {"diag-placement-braced": ["diag-placement"]})
        self.assertIn({"id": "diag-active", "status": "INCONCLUSIVE"}, compare["excluded"])
        self.assertEqual(compare["objectives_unavailable"][0]["id"], "cost")
        decisions = load(self.run_dir / "decisions.json")["decisions"]
        self.assertEqual(decisions["decision-f31-shift"]["state"], "SELECTED")
        self.assertEqual(decisions["decision-f31-over"]["state"], "REJECTED")
        self.assertEqual(decisions["decision-f31-lateral"]["state"], "TESTED")
        self.assertEqual(decisions["decision-diag-placement-braced"]["state"], "SUPERSEDED")

    def test_missing_dependency_and_broken_function(self):
        def change(benches):
            variants = {a["id"]: a for a in benches["benches"][1]["alternatives"]}
            variants["diag-compact"]["dependencies"] = ["diag-passive"]
            graph = variants["diag-passive"]["changes"]["connection_graph"]
            graph.pop()

        result, out = self.mutate("broken", "benches.json", change, "--benches")
        self.assertEqual(result.returncode, 2, result.stderr)
        report = load(out / "candidates" / "diag-passive.json")
        self.assertEqual(report["status"], "FAIL")
        self.assertIn(("diag-return-path", "FAIL"), {(f["requirement_id"], f["status"]) for f in report["findings"]})
        combo = load(out / "candidates" / "diag-compatible.json")
        self.assertIn("MISSING_DEPENDENCY", {c["code"] for c in combo["conflicts"]})

    def test_electrical_contract_detects_interposed_board_and_bypass(self):
        def change(benches):
            variants = {a["id"]: a for a in benches["benches"][1]["alternatives"]}
            variants["diag-placement"]["changes"]["connection_graph"] = [
                {"from": a, "to": b, "signal": signal}
                for signal in ("DEBUG", "RETURN")
                for a, b in (("controller", "board"), ("board", "service"))
            ]
            variants["diag-passive"]["changes"]["connection_graph"].append(
                {"from": "controller", "to": "service", "signal": "DEBUG"})

        result, out = self.mutate("extra-edges", "benches.json", change, "--benches")
        self.assertEqual(result.returncode, 2, result.stderr)
        for name in ("diag-placement", "diag-passive"):
            report = load(out / "candidates" / f"{name}.json")
            by_id = {f["requirement_id"]: f["status"] for f in report["findings"]}
            self.assertEqual(by_id["diag-debug-path"], "PASS")
            self.assertEqual(by_id["diag-electrical-contract"], "FAIL")

    def test_margin_uses_frozen_threshold_and_unknown_class_blocks_admission(self):
        def change(requirements):
            rules = {r["requirement"]["id"]: r["requirement"] for r in requirements["benches"][0]["rules"]}
            rules["f31-route"]["criterion"]["value"] = 100

        result, out = self.mutate("threshold", "requirements.json", change, "--requirements")
        self.assertEqual(result.returncode, 2, result.stderr)
        shifted = load(out / "candidates" / "f31-shift.json")
        route = next(f for f in shifted["findings"] if f["requirement_id"] == "f31-route")
        self.assertEqual((route["status"], route["margin"]), ("FAIL", -95))

        def classify(requirements):
            rules = requirements["benches"][0]["rules"]
            pwr1 = next(r for r in rules if r["requirement"]["id"] == "pwr1-reserve")
            pwr1["requirement"]["classification"] = "UNKNOWN"

        result, out = self.mutate("classification", "requirements.json", classify, "--requirements")
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(load(out / "candidates" / "f31-shift.json")["status"], "INCONCLUSIVE")

    def test_budget_never_claims_an_untested_architecture(self):
        def change(benches):
            benches["benches"][1]["candidate_budget"] = 2

        result, out = self.mutate("budget", "benches.json", change, "--benches")
        self.assertEqual(result.returncode, 2, result.stderr)
        bench = load(out / "campaign.json")["benches"]["diagnostic"]
        proposed = next(a for a in bench["attempts"] if a["id"] == "diag-passive")
        self.assertEqual(proposed, {"id": "diag-passive", "reason": "BUDGET_EXHAUSTED", "state": "PROPOSED"})
        self.assertFalse((out / "candidates" / "diag-passive.json").exists())

    def test_replay_identity_and_no_overwrite(self):
        repeat = self.path / "repeat"
        self.assertEqual(self.invoke(repeat).returncode, 0)
        for path in ("baseline.json", "comparison.json"):
            self.assertEqual((repeat / path).read_bytes(), (self.run_dir / path).read_bytes())
        for path in ("campaign.json", "decisions.json", "candidates/f31-lateral.json",
                     "candidates/f31-lateral-research.json"):
            self.assertEqual(semantic(load(repeat / path)), semantic(load(self.run_dir / path)))
        for run in (self.run_dir, repeat):
            for item in load(run / "artifacts.json")["items"]:
                digest = hashlib.sha256((run / item["path"]).read_bytes()).hexdigest()
                self.assertEqual(digest, item["checksum_sha256"], item["path"])
        self.assertEqual(self.invoke(repeat).returncode, 1)
        self.assertTrue(load(repeat / "campaign.json")["finalized"])

    def test_execution_failure_is_not_a_conditional_research(self):
        out = self.path / "invalid-l1"
        result = self.invoke(out, l1=CORE)
        self.assertEqual(result.returncode, 1)
        self.assertTrue((out / "run_request.json").exists())
        self.assertFalse((out / "t0_run_manifest.json").exists())

    def test_additional_acceptance_failure_yields_conditional(self):
        def change(policy):
            policy["checks"][-1]["equals"] = []

        result, out = self.mutate("conditional", "acceptance.json", change, "--acceptance")
        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertEqual(load(out / "campaign.json")["verdict"], "L3_CONDITIONAL")


if __name__ == "__main__":
    unittest.main(verbosity=2)
