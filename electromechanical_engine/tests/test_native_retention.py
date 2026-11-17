"""Native V3 regression on an axis and supports saved before measurement."""

import json
import math
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from electromechanical_engine.validation import _assembly


FREECAD = os.environ.get('ELECTROMECHANICAL_FREECAD_PYTHON')

CREATE = r'''
import sys
import FreeCAD as App
import Part

vector = App.Vector
start, arc_mid, arc_end = vector(0, 0, 10), vector(10, 10, 10), vector(20, 0, 10)
end = vector(20, -20, 10)
doc = App.newDocument('RetentionFixture')
axis = Part.Wire([Part.Arc(start, arc_mid, arc_end).toShape(), Part.makeLine(arc_end, end)])
profile = Part.Wire([Part.makeCircle(1, start, vector(0, 1, 0))])
doc.addObject('Part::Feature', 'Axis').Shape = axis
doc.addObject('Part::Feature', 'Cable').Shape = axis.makePipeShell([profile], True, False)
doc.addObject('Part::Feature', 'Deck').Shape = Part.makeBox(24, 26, 4, vector(-2, -12, 0))
for name, x, y, direction in (('Clip1', 10, 10, vector(1, 0, 0)), ('Clip2', 20, -10, vector(0, 1, 0))):
    body = Part.makeBox(4, 4, 8, vector(x - 2, y - 2, 4))
    bore = Part.makeCylinder(1, 6, vector(x, y, 10) - direction * 3, direction)
    doc.addObject('Part::Feature', name).Shape = body.cut(bore)
doc.recompute()
doc.saveAs(sys.argv[1])
App.closeDocument(doc.Name)
'''

MEASURE = r'''
from copy import deepcopy
import json
from pathlib import Path
import sys
import FreeCAD as App
import Part
from electromechanical_engine.freecad import SKILL_SCRIPTS, load_helper
from electromechanical_engine.native_retention import measure

doc = App.openDocument(sys.argv[1])
doc.recompute()
wire = doc.Axis.Shape.Wires[0]
geometry = load_helper(SKILL_SCRIPTS / 'freecad_geometry.py')
start, end = [0, 0, 10], [20, -20, 10]
tangent = [0, 1, 0]
axis = geometry.inspect_route(wire, 4, tangent, tangent, start_position=start, end_position=end)
assert not axis['failures'], axis
route = {'solid_valid': geometry.inspect_solid(doc.Cable.Shape)['status'] == 'pass',
         'continuity_ok': not axis['failures'], 'tangency_ok': not axis['failures'],
         'endpoints_ok': not axis['failures'], 'diameter_mm': 2.0}
ports = {key: {'id': key, 'status': 'DOCUMENTEE', 'retained_endpoint': True,
               'position_mm': point, 'tangent': tangent}
         for key, point in (('source', start), ('target', end))}
link = {'id': 'L', 'source': 'source', 'target': 'target'}
shapes = {name: doc.getObject(name).Shape for name in ('Deck', 'Clip1', 'Clip2', 'Cable')}
stations, anchors, supports = [], {}, {}
for identity, obj, x, y in (('R1', 'Clip1', 10, 10), ('R2', 'Clip2', 20, -10)):
    clip = shapes[obj]
    tool = Part.makeBox(2, 2, 2, App.Vector(x - 1, y - 1, 13))
    anchors[identity] = {'anchor': 'Deck', 'attached': clip.distToShape(shapes['Deck'])[0] <= 1e-5,
                         'access_clear': all(tool.distToShape(shape)[0] > 0.5 for shape in shapes.values())}
    supports[identity] = {'id': identity, 'anchor': 'Deck'}
    stations.append({'support': identity, 'object': obj, 'link': 'L', 'point_mm': [x, y, 10],
                     'enclosure': {'origin_mm': [x - 2, y - 2, 8], 'size_mm': [4, 4, 4]},
                     'capture_wall_mm': 0.25,
                     'source': 'Geometrie nominale du banc V3'})

def observe(stations=stations, anchors=anchors, ports=ports, shapes=shapes):
    return measure(wire, route, link, ports, stations, anchors, supports, supports, shapes, 1e-5,
                   require_station=True)

cases = {'nominal': observe(), 'no_station': observe(stations=[]), 'anchors': anchors}
displaced = dict(shapes)
displaced['Clip1'] = Part.makeBox(2, 2, 5, App.Vector(9, 17, 4))
cases['no_contact'] = observe(shapes=displaced)
open_shelf = dict(shapes)
open_shelf['Clip1'] = Part.makeBox(4, 4, 5, App.Vector(8, 8, 4))
cases['open_shelf'] = observe(shapes=open_shelf)
penetrating = dict(shapes)
penetrating['Clip1'] = Part.makeBox(2, 2, 5.2, App.Vector(9, 9, 4))
cases['penetrating_contact'] = observe(shapes=penetrating)
unverified = deepcopy(anchors)
unverified['R1']['access_clear'] = False
cases['blocked_access'] = observe(anchors=unverified)
unverified_port = deepcopy(ports)
unverified_port['target']['retained_endpoint'] = False
cases['free_end'] = observe(ports=unverified_port)
small_enclosure = deepcopy(stations)
small_enclosure[0]['enclosure']['origin_mm'][2] = 9.75
cases['no_enclosure'] = observe(stations=small_enclosure)
Path(sys.argv[2]).write_text(json.dumps(cases, allow_nan=False), encoding='utf-8')
'''


@unittest.skipUnless(FREECAD, 'FreeCAD integration not requested')
class NativeRetentionTests(unittest.TestCase):
    def test_saved_arc_retention_observes_both_end_gaps_and_threshold(self):
        with tempfile.TemporaryDirectory() as directory:
            native = Path(directory) / 'Retentions.FCStd'
            output = Path(directory) / 'observations.json'
            subprocess.run([FREECAD, '-B', '-c', CREATE, str(native)], check=True, timeout=25)
            original = native.read_bytes()
            subprocess.run([FREECAD, '-B', '-c', MEASURE, str(native), str(output)], check=True, timeout=25)
            self.assertEqual(native.read_bytes(), original)
            cases = json.loads(output.read_text(encoding='utf-8'))

        nominal = cases['nominal']
        expected_gaps = [5 * math.pi, 5 * math.pi + 10, 10]
        for actual, expected in zip(nominal['retention_evidence']['gaps_mm'], expected_gaps, strict=True):
            self.assertAlmostEqual(actual, expected, places=5)
        self.assertAlmostEqual(nominal['unsupported_span_mm'], max(expected_gaps), places=5)
        self.assertAlmostEqual(nominal['unsupported_length_mm'], sum(expected_gaps), places=5)
        for station in nominal['retention_evidence']['stations']:
            self.assertAlmostEqual(station['capture_area_mm2'], math.pi * (1.25 ** 2 - 1), places=5)
            self.assertLessEqual(station['capture_uncovered_mm2'], station['capture_area_tolerance_mm2'])
        shelf = cases['open_shelf']['retention_evidence']['stations'][0]
        self.assertEqual(shelf['reason'], 'native_capture_wall_incomplete')
        self.assertGreater(shelf['capture_uncovered_mm2'], 1)
        supports = [{'id': identity, 'anchor': 'Deck'} for identity in cases['anchors']]
        for maximum, expected in ((26, 'pass'), (25, 'fail')):
            with self.subTest(maximum=maximum):
                requirements = {'links': {'L': {'max_unsupported_mm': maximum}}, 'supports': supports}
                findings = list(_assembly(requirements, {'supports': supports},
                                          {'route_metrics': {'L': nominal}, 'anchor_valid': cases['anchors']}))
                span = next(finding for finding in findings if finding['code'] == 'V3.UNSUPPORTED_SPAN')
                self.assertEqual(span['status'], expected)
        for case in ('no_station', 'no_contact', 'open_shelf', 'penetrating_contact',
                     'blocked_access', 'free_end', 'no_enclosure'):
            with self.subTest(case=case):
                self.assertIsNone(cases[case]['unsupported_span_mm'])
                self.assertIsNone(cases[case]['unsupported_length_mm'])
                self.assertEqual(cases[case]['retention_evidence']['status'], 'unknown')
