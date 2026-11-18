"""Regress independent B.1 observations against the sealed C4 source."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import unittest
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[2]
VERIFIER = ROOT / "convergence_manager/native/v3_verify.py"
PROFILE = ROOT / "docs/electromechanical_v3/bench_b1_c4/profile.json"


class NativeVerification(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        profile = json.loads(PROFILE.read_bytes())
        cls.output = ROOT / ".runtime/v3-b1/validator-tests" / uuid4().hex
        cls.model = cls.output / "cad"
        for path, sha in profile["dependencies"].items():
            source = ROOT / profile["source"] / path
            target = cls.model / path
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            if hashlib.sha256(target.read_bytes()).hexdigest() != sha:
                raise ValueError(f"Fixture native C4 divergente : {path}")
        cls.job = {"entry": profile["entry"], "dependencies": profile["dependencies"],
                   "model": profile["model"], "actions": profile["actions"], "stage": "baseline"}
        print(f"Preuves de mesures natives dans {cls.output}")

    def measure(self, name, mutate=None):
        job = copy.deepcopy(self.job)
        job["plan_id"] = name
        if mutate is not None:
            mutate(job)
        path = self.output / (name + "-job.json")
        report = self.output / (name + "-report.json")
        path.write_text(json.dumps(job), encoding="utf-8")
        self.invoke(str(VERIFIER), "--root", str(self.model), "--job", str(path), "--output", str(report))
        value = json.loads(report.read_bytes())
        self.assertTrue(value["finalized"] and value["reopened"] and value["documents_closed"])
        self.assertEqual(value["inputs_sha256"], job["dependencies"])
        self.assertEqual(value["job_sha256"], hashlib.sha256(path.read_bytes()).hexdigest())
        return value, {row["id"]: row for row in value["checks"]}

    def invoke(self, *args):
        result = subprocess.run([self.freecad, "-B", *args], cwd=ROOT, timeout=60, check=False,
                                env=dict(os.environ, QT_QPA_PLATFORM="offscreen", PYTHONUTF8="1"),
                                capture_output=True, text=True, encoding="utf-8", errors="replace")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_collision_measured_fresh_with_false_cached_result(self):
        def inject_forged_cache(job):
            job["cache"] = {"status": "PASS", "pairs": []}

        report, checks = self.measure("forged-cache", inject_forged_cache)
        self.assertEqual(report["status"], "FAIL")
        topology = checks["L2_TOPOLOGY"]["details"]
        self.assertEqual(checks["L2_TOPOLOGY"]["status"], "PASS")
        self.assertEqual(len(topology["contacts"]), 8)
        self.assertEqual(len(topology["conductors"]), 4)
        geometry = checks["L4_GEOMETRY"]["details"]
        self.assertEqual(geometry["cache"], "UNUSED_MEASURED_FRESH")
        collisions = [pair for pair in geometry["pairs"] if pair["status"] == "fail"]
        self.assertEqual(len(collisions), 1)
        self.assertIn("forbidden_interference", collisions[0]["failures"])
        self.assertGreater(collisions[0]["intersection_volume_mm3"], 100)

    def test_wrong_port_frame_three_millimetres(self):
        def shift_frame(job):
            job["model"]["validation"]["ports"]["port-a"]["local_pose"]["translation_mm"][2] += 3

        _, checks = self.measure("wrong-frame", shift_frame)
        self.assertEqual(checks["L2_TOPOLOGY"]["status"], "FAIL")
        fixture = checks["L2_TOPOLOGY"]["details"]["ports"]["port-a"]
        self.assertEqual(fixture["status"], "FAIL")
        self.assertAlmostEqual(fixture["measurements"][0]["position_error_mm"], 3)

    def test_wrong_pinout(self):
        def swap_pin(job):
            job["model"]["validation"]["contacts"]["ma1"]["pin"] = "pa2"

        _, checks = self.measure("wrong-pinout", swap_pin)
        self.assertEqual(checks["L2_TOPOLOGY"]["status"], "FAIL")
        terminal = checks["L2_TOPOLOGY"]["details"]["contacts"]["ma1"]
        self.assertEqual(terminal["observed_pin"], "pa1")
        self.assertEqual(terminal["errors"], ["pinout_divergent"])

    def test_support_bearing_distinguishes_a_gap_of_three_tenths(self):
        self.invoke(str(Path(__file__).resolve()), "--bearing-worker")


def bearing_worker():
    sys.path.insert(0, str(ROOT))
    from convergence_manager.native.v3_verify import Measurement
    from electromechanical_engine import freecad_worker as native

    trial = Measurement(native, None, {}, {}, {}, {
        "entry": "Test.FCStd", "model": {}, "stage": "baseline", "actions": []})
    carrier = native.Part.makeBox(10, 10, 4)
    bearing = native.Part.makeBox(2, 2, 3, native.App.Vector(2, 2, 4))
    floating = native.Part.makeBox(2, 2, 3, native.App.Vector(2, 2, 4.3))
    if abs(trial.bearing_area(bearing, carrier) - 4) > 1e-8:
        raise ValueError("Aire d’appui des faces planes divergente")
    if trial.bearing_area(floating, carrier) != 0:
        raise ValueError("Contact déclaré à travers un jeu de 0,3 mm")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--freecad")
    parser.add_argument("--bearing-worker", action="store_true", help=argparse.SUPPRESS)
    args, remaining = parser.parse_known_args()
    if args.bearing_worker:
        bearing_worker()
    else:
        if not args.freecad:
            parser.error("--freecad est requis")
        NativeVerification.freecad = args.freecad
        unittest.main(argv=[sys.argv[0], *remaining])
