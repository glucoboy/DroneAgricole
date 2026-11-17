"""Check native Compound validity and preservation of occurrence identity."""

import os
import subprocess
import unittest


@unittest.skipUnless(os.environ.get('ELECTROMECHANICAL_FREECAD_PYTHON'), 'FreeCAD integration not requested')
class NativeInventoryTests(unittest.TestCase):
    def test_compounds_match_native_checks_without_reusing_other_occurrences(self):
        code = '''
import FreeCAD as App
import Part
from electromechanical_engine.freecad_worker import check_native_shape

box = Part.makeBox(2, 3, 4)
occurrence = Part.Shape(box)
occurrence.Placement = App.Placement(App.Vector(11, 0, 0), App.Rotation())
invalid = Part.Solid(Part.Shell([Part.makePlane(10, 10)]))
good = Part.Compound([Part.Compound([box]), occurrence])
bad = Part.Compound([good, Part.Compound([invalid])])
assert good.isValid() and not bad.isValid()
cache = {}
checks = dict(native_checks=0, compound_checks=0, exact_cache_hits=0)
for shape in (good, bad, Part.Compound([])):
    assert check_native_shape(shape, cache, checks) == shape.isValid()

cache.clear()
for name in checks:
    checks[name] = 0
for shape in (box, occurrence, box.reversed(), Part.Shape(occurrence)):
    assert check_native_shape(shape, cache, checks) == shape.isValid()
assert checks['native_checks'] == 3 and checks['exact_cache_hits'] == 1, checks
'''
        subprocess.run([os.environ['ELECTROMECHANICAL_FREECAD_PYTHON'], '-B', '-c', code],
                       check=True, timeout=30)
