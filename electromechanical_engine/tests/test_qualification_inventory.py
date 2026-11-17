"""Adversarial check of the solid inventory on a reopened native candidate."""

import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from electromechanical_engine.freecad import FreeCADAdapter, FreeCADError, guard
from electromechanical_engine.tests.test_freecad import scenario


@unittest.skipUnless(os.environ.get("ELECTROMECHANICAL_FREECAD_PYTHON"), "FreeCAD integration not requested")
class NativeQualificationInventoryTest(unittest.TestCase):
    def assert_obstacle_rejected(self, scope, diagnostic):
        adapter = FreeCADAdapter(os.environ["ELECTROMECHANICAL_FREECAD_PYTHON"])
        plan = scenario([[0, 0, 10], [20, 0, 10], [20, 15, 10], [80, 15, 10],
                         [80, 0, 10], [100, 0, 10]], 5)
        with tempfile.TemporaryDirectory() as directory:
            candidate = Path(directory) / "candidate"
            baseline = adapter.build(plan, candidate)
            self.assertTrue(baseline["collision_complete"])
            self.assertTrue(all(pair["status"] == "pass" for pair in baseline["collisions"]))
            native = candidate / "candidate.FCStd"
            inject = """
from pathlib import Path
import sys
from electromechanical_engine.freecad_worker import cables_environment
cables_environment(gui=True)
import FreeCAD as App
import Part

doc = App.openDocument(sys.argv[1])
reference = next(obj for obj in doc.Objects if getattr(obj, 'EngineId', '') == 'far')
external = sys.argv[2] == 'external'
owner = App.newDocument('ExternalFixture') if external else doc
obstacle = owner.addObject('Part::Feature', 'HiddenObstacle')
obstacle.Shape = Part.makeBox(4, 4, 4, App.Vector(48, 13, 8))
if external:
    owner.recompute()
    owner.saveAs(str(Path(sys.argv[1]).with_name('obstacle.FCStd')))
reference.addProperty('App::PropertyXLink' if external else 'App::PropertyLink', 'ExtraFixture')
reference.ExtraFixture = obstacle
doc.recompute()
cable = next(obj for obj in doc.Objects if getattr(obj, 'EngineId', '') == 'L0')
assert abs(cable.Shape.common(obstacle.Shape).Volume - 12.566370614359172) < 1e-6
doc.save()
"""
            subprocess.run([str(adapter.python), "-B", "-c", inject, str(native), scope], check=True,
                           env=dict(os.environ, QT_QPA_PLATFORM="offscreen"), timeout=30,
                           capture_output=True)
            files = guard.dependencies(candidate, [native.name])
            self.assertEqual({path.name for path in files},
                             {"candidate.FCStd", "obstacle.FCStd"} if scope == "external" else {"candidate.FCStd"})
            before = {path: guard.sha256(path) for path in files}
            with self.assertRaisesRegex(FreeCADError, diagnostic):
                adapter.inspect(candidate, plan)
            self.assertEqual({path: guard.sha256(path) for path in files}, before)

    def test_linked_untagged_obstacle_cannot_be_hidden_from_pair_inventory(self):
        self.assert_obstacle_rejected("local", "outside the declared inventory.*HiddenObstacle")

    def test_xlink_cannot_hide_an_obstacle_in_an_external_document(self):
        self.assert_obstacle_rejected("external", "Native candidate inventory requires a single document without XLinks")
