import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CLI = Path(sys.argv.pop(1)).resolve()
BASELINE = "docs/electromechanical_v2/BASELINE_MANIFEST.json"
MATRIX = "docs/verification/cartographe_action3_interconnexions.json"
PROOF = ROOT / "docs/electromechanical_v2/L2_RECONCILIATION.json"


def run_converter(root, command="reconcile"):
    return subprocess.run(
        [CLI, command, "--root", root], check=False, capture_output=True,
        encoding="utf-8", timeout=30,
    )


class ReconciliationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        result = run_converter(ROOT)
        if result.returncode != 0:
            raise RuntimeError(f"Échec de reconciliation : {result.stdout} {result.stderr}")
        cls.report = json.loads(result.stdout)
        cls.lines = {row["id"]: row for row in cls.report["lines"]}
        cls.axes = {row["id"]: row for row in cls.report["axes"]}
        cls.cords = {row["id"]: row for row in cls.report["cords"]}

    def copy_sources(self, destination):
        for name in self.report["source_sha256"]:
            target = destination / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, target)

    def test_scope_and_categorization(self):
        summary = self.report["summary"]
        self.assertEqual(self.report["status"], "RECONCILED")
        self.assertEqual((len(self.lines), len(self.axes), len(self.cords)), (71, 53, 36))
        self.assertEqual(summary["by_class"], {
            "BUS": 2, "CONDUCTEUR": 4, "CORDON": 7, "FONCTION": 37, "HORS_PERIMETRE": 21,
        })
        self.assertEqual(self.lines["W21"]["class"], "BUS")
        self.assertEqual(self.lines["W01.NEG"]["class"], "CONDUCTEUR")
        self.assertEqual(self.lines["W16"]["class"], "CORDON")
        self.assertEqual(self.lines["W18"]["class"], "FONCTION")
        direct = self.lines["W22"]
        self.assertEqual((direct["scope"], direct["class"], direct["path"]),
                         ("interface_directe", "HORS_PERIMETRE", []))
        self.assertTrue(direct["scope_reason"])

    def test_bidirectional_many_to_many_preserves_paths_and_cords(self):
        forward = {(row["id"], edge["route_id"]) for row in self.lines.values() for edge in row["path"]}
        reverse = {(line, axis["id"]) for axis in self.axes.values() for line in axis["line_ids"]}
        self.assertEqual(forward, reverse)
        self.assertEqual(len(forward), 56)
        self.assertEqual(self.axes["AIRY"]["line_ids"], ["W10", "W15", "W23"])
        self.assertEqual(self.cords["ELEC-F-AIRY"]["line_ids"], ["W10", "W15", "W23"])
        self.assertEqual(self.axes["F_M8"]["line_ids"], ["W18", "W34"])
        self.assertEqual(self.lines["W10"]["path"], [
            {"route_id": "AIRY_PWR", "sense": "inverse"}, {"route_id": "AIRY", "sense": "inverse"},
        ])
        self.assertEqual(self.lines["W38"]["path_kind"], "conducteurs_paralleles")
        self.assertEqual({edge["route_id"] for edge in self.lines["W38"]["path"]}, {"F38_POS", "F38_NEG"})
        self.assertEqual(
            {(line["id"], cord) for line in self.lines.values() for cord in line["cord_ids"]},
            {(line, cord["id"]) for cord in self.cords.values() for line in cord["line_ids"]},
        )

    def test_historical_observations_are_not_converted_to_qualification(self):
        self.assertEqual(self.lines["W12"]["geometry_status"], "FAIL")
        self.assertEqual(self.lines["W12"]["compatibility_status"], "INCONCLUSIVE")
        self.assertIn("GPS2", self.lines["W12"]["finding"]["observation"])
        self.assertEqual(self.lines["W16"]["geometry_status"], "INCONCLUSIVE")
        summary = self.report["summary"]
        self.assertEqual(summary["active_axis_hashes_differing_from_november_8_copy"], ["F16"])
        self.assertEqual(summary["unresolved_onboard_lines_in_november_8_copy"], [
            "W16", "W20", "W24.C", "W25", "W40", "W-LED-KIT.1", "W-LED-KIT.2", "W-LED-KIT.3", "W-LED-KIT.4",
        ])

    def test_reproducible_evidence(self):
        self.assertEqual(self.report, json.loads(PROOF.read_bytes()))
        for key in ("matrix_sources_verified", "inventory_sources_verified", "ca01_schematic_sources_verified",
                    "active_native_axes_verified"):
            self.assertGreater(self.report["summary"][key], 0)

    def test_cartographe_interface_trace_go3b(self):
        result = run_converter(ROOT, "inspect-cartographe")
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["status"], "INCONCLUSIVE")
        self.assertEqual(len(report["interfaces"]), 142)
        self.assertEqual(len(report["line_interfaces"]), 71)
        self.assertEqual(len(report["axes"]), 53)
        self.assertEqual(sum(len(axis["line_ids"]) for axis in report["axes"].values()), 56)
        self.assertEqual(sum("scope_reason" in line for line in report["lines"]), 21)
        for line, endpoints in report["line_interfaces"].items():
            self.assertEqual(endpoints, [f"{line}/A", f"{line}/B"])
            for endpoint in endpoints:
                interface = report["interfaces"][endpoint]
                self.assertEqual(interface["line_id"], line)
                self.assertTrue(interface["connector_record"].endswith(f"#{endpoint}"))
                self.assertEqual(interface["reception"], "INCONCLUSIVE")
                self.assertIsNone(interface["native_interface"])
        self.assertEqual(report["axes"]["AIRY"]["line_ids"], ["W10", "W15", "W23"])
        self.assertEqual(report["axes"]["F12"]["assembly_occurrence"].split("#")[-1], "F12")
        cases = {"W12/B": "TELEM1", "W24.A/B": "GPIO", "W31/A": "PM08", "W31/B": "CAN1",
                 "W16/B": "USB3 Micro-B", "W40/B": "TTL", "W41/A": "USB Type B", "W24.C/A": "CSI"}
        for endpoint, label in cases.items():
            self.assertIn(label, report["interfaces"][endpoint]["functional_port"])
        w12 = next(line for line in report["lines"] if line["id"] == "W12")
        self.assertIn("GPS2", w12["finding"]["observation"])
        self.assertEqual(w12["compatibility_status"], "INCONCLUSIVE")

    def test_tampered_native_refused(self):
        with tempfile.TemporaryDirectory(prefix="l2-reconcile-") as temporary:
            root = Path(temporary)
            self.copy_sources(root)
            axis = root / self.axes["F12"]["active_native"]["path"]
            with axis.open("ab") as destination:
                destination.write(b"mutation")
            result = run_converter(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("SHA-256", result.stdout + result.stderr)

    def test_matrix_disagreeing_with_inventory_refused_even_if_rehashed(self):
        with tempfile.TemporaryDirectory(prefix="l2-reconcile-") as temporary:
            root = Path(temporary)
            self.copy_sources(root)
            matrix_path = root / MATRIX
            matrix = json.loads(matrix_path.read_bytes())
            line = next(row for row in matrix["interconnexions"] if row["id"] == "W12")
            line["route_ids"] = ["F16"]
            payload = json.dumps(matrix, ensure_ascii=False).encode("utf-8")
            matrix_path.write_bytes(payload)
            baseline_path = root / BASELINE
            baseline = json.loads(baseline_path.read_bytes())
            evidence = next(reference for group in baseline["references"].values() for reference in group
                            if reference["path"] == MATRIX)
            evidence["sha256"] = hashlib.sha256(payload).hexdigest()
            baseline_path.write_text(json.dumps(baseline, ensure_ascii=False), encoding="utf-8")
            result = run_converter(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("W12/route_ids", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
