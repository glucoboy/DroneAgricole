"""Synthetic FreeCAD/BRep tests. Never opens a project model.

Run using FreeCAD's Python with --output under an isolated runtime directory.
Optional --builder reuses the supplied project's native cable constructor.
"""
import argparse
import importlib.util
import json
import math
import os
from pathlib import Path
import sys
import unittest

import FreeCAD as App
import Part
from freecad_geometry import (inspect_pair, inspect_route,
                              inspect_solid, rebuild_cable_in_isolated_document)

EVIDENCE = {}
BUILDER = None


def line(a=(0, 0, 0), b=(100, 0, 0)):
    return Part.Wire([Part.makeLine(App.Vector(*a), App.Vector(*b))])


class ReadingOverride:
    """Inject an invalid kernel reading while retaining a real BRep elsewhere."""
    def __init__(self, wrapped, **readings):
        self.wrapped, self.readings = wrapped, readings

    def __getattr__(self, name):
        return self.readings[name] if name in self.readings else getattr(self.wrapped, name)


class GeometryTests(unittest.TestCase):
    def test_nonfinite_connector_vectors_never_pass(self):
        for value in (float('nan'), float('inf'), -float('inf')):
            for field in ('start_axis', 'end_axis', 'start_position', 'end_position', 'waypoints'):
                with self.subTest(field=field, value=value):
                    args = dict(minimum_radius_mm=22, start_axis=(1, 0, 0), end_axis=(-1, 0, 0),
                                start_position=(0, 0, 0), end_position=(100, 0, 0))
                    args[field] = [(value, 0, 0)] if field == 'waypoints' else (value, 0, 0)
                    measured = inspect_route(line(), **args)
                    self.assertEqual(measured['status'], 'fail')
                    self.assertIn('route_measurement_error', measured['failures'])
                    json.dumps(measured, allow_nan=False)

    def test_nonfinite_kernel_measurements_never_pass(self):
        for value in (float('nan'), float('inf'), -float('inf')):
            with self.subTest(value=value):
                route = inspect_route(ReadingOverride(line(), Length=value), 22)
                self.assertEqual(route['status'], 'fail')
                solid = inspect_solid(ReadingOverride(Part.makeBox(1, 1, 1), Volume=value))
                self.assertEqual(solid['status'], 'fail')
                base = Part.makeBox(1, 1, 1)
                bad_intersection = ReadingOverride(base, common=lambda other: ReadingOverride(base, Volume=value))
                overlap = inspect_pair(bad_intersection, base, 'A', 'B')
                self.assertEqual(overlap['status'], 'unknown')
                bad_distance = ReadingOverride(base, distToShape=lambda other: (value, [], []))
                distance = inspect_pair(bad_distance, base, 'A', 'B')
                self.assertEqual(distance['status'], 'unknown')
                json.dumps([route, solid, overlap, distance], allow_nan=False)

    def test_subdivision_budget_requires_integers(self):
        for budget in (True, 1.5, float('nan'), float('inf')):
            with self.assertRaises(ValueError):
                inspect_route(line(), 22, min_depth=budget)

    def test_radius_below_requirement(self):
        arc = Part.makeCircle(10, App.Vector(), App.Vector(0, 0, 1), 0, 90)
        measured = inspect_route(Part.Wire([arc]), 22, (0, 1, 0), (1, 0, 0))
        self.assertEqual(measured['status'], 'fail')
        self.assertAlmostEqual(measured['minimum_radius_mm'], 10)
        self.assertIn('bend_radius_below_requirement', measured['failures'])
        EVIDENCE['radius_nonconforming'] = measured

    def test_straight_route_and_connector_directions(self):
        good = inspect_route(line(), 22, (1, 0, 0), (-1, 0, 0), [(50, 0, 0)], start_position=(0, 0, 0), end_position=(100, 0, 0))
        self.assertEqual(good['status'], 'pass')
        self.assertTrue(good['straight_radius_infinite'])
        bad = inspect_route(line(), 22, (1, 0, 0), (1, 0, 0))
        self.assertIn('end_axis_mismatch', bad['failures'])
        self.assertAlmostEqual(bad['end_axis_error_deg'], 180)

    def test_terminal_positions(self):
        measured = inspect_route(line(), 22, (1, 0, 0), (-1, 0, 0), start_position=(1, 0, 0), end_position=(100, 0, 0))
        self.assertIn('start_position_mismatch', measured['failures'])
        self.assertAlmostEqual(measured['start_position_error_mm'], 1)

    def test_reversed_edge_direction(self):
        edge = Part.makeLine(App.Vector(100, 0, 0), App.Vector(0, 0, 0))
        edge.reverse()
        measured = inspect_route(Part.Wire([edge]), 22, (1, 0, 0), (-1, 0, 0), start_position=(0, 0, 0), end_position=(100, 0, 0))
        self.assertEqual(measured['status'], 'pass')

    def test_join_tangency_and_waypoint(self):
        wire = Part.makePolygon([App.Vector(0, 0, 0), App.Vector(30, 0, 0), App.Vector(30, 30, 0)])
        measured = inspect_route(wire, 22, (1, 0, 0), (0, -1, 0), [(15, 5, 0)])
        self.assertIn('non_tangent_join', measured['failures'])
        self.assertIn('required_waypoint_missing', measured['failures'])
        self.assertAlmostEqual(measured['join_angles_deg'][0], 90)

    def test_spline_samples_never_certify_global_radius(self):
        spline = Part.BSplineCurve()
        spline.buildFromPoles([App.Vector(0, 0, 0), App.Vector(30, 0, 0), App.Vector(30, 30, 0), App.Vector(60, 30, 0)])
        measured = inspect_route(Part.Wire([spline.toShape()]), .01, (1, 0, 0), (-1, 0, 0), min_depth=3, max_depth=8)
        self.assertEqual(measured['status'], 'unknown')
        self.assertIn('global_curvature_bound_not_proven', measured['unknowns'])
        self.assertGreater(measured['edge_measurements'][0]['samples'], 10)
        EVIDENCE['adaptive_spline'] = measured

    def test_missing_supplier_radius(self):
        measured = inspect_route(line(), None, (1, 0, 0), (-1, 0, 0))
        self.assertEqual(measured['status'], 'unknown')
        self.assertIn('minimum_radius_requirement_missing', measured['unknowns'])

    def test_real_obstacle_collision(self):
        cable = Part.makeCylinder(2, 100, App.Vector(), App.Vector(1, 0, 0))
        obstacle = Part.makeBox(10, 10, 10, App.Vector(40, -5, -5))
        measured = inspect_pair(cable, obstacle, 'C1', 'OB1')
        self.assertEqual(measured['status'], 'fail')
        self.assertGreater(measured['intersection_volume_mm3'], 100)
        EVIDENCE['obstacle_collision'] = measured

    def test_explicit_conduit_envelope_inclusion(self):
        cable = Part.makeCylinder(2, 100)
        envelope = Part.makeCylinder(5, 100)
        relation = {'kind': 'cable_in_conduit_envelope', 'inner_id': 'C1', 'outer_id': 'G1',
                    'outer_representation': 'occupancy_envelope',
                    'justification': 'Synthetic declared cable occupancy in the reserved conduit bore.'}
        allowed = inspect_pair(cable, envelope, 'C1', 'G1', relation=relation)
        self.assertEqual(allowed['status'], 'pass')
        self.assertTrue(allowed['authorized_relation'])
        self.assertGreater(allowed['intersection_volume_mm3'], 0)
        self.assertEqual(inspect_pair(cable, envelope, 'C1', 'G2', relation=relation)['status'], 'fail')
        self.assertEqual(inspect_pair(cable, envelope, 'C1', 'G1')['status'], 'fail')
        EVIDENCE['intentional_envelope_inclusion'] = allowed

    def test_conduit_material_not_exempted(self):
        cable = Part.makeCylinder(2, 100)
        sleeve = Part.makeCylinder(5, 100).cut(Part.makeCylinder(2, 100))
        contact = {'kind': 'functional_contact', 'pair': ['C1', 'G1'], 'justification': 'Synthetic radial contact at bore.'}
        measured = inspect_pair(cable, sleeve, 'C1', 'G1', relation=contact)
        self.assertEqual(measured['status'], 'pass')
        self.assertLessEqual(measured['intersection_volume_mm3'], 1e-7)
        offset = Part.makeCylinder(2, 100, App.Vector(1, 0, 0))
        self.assertEqual(inspect_pair(offset, sleeve, 'C1', 'G1', relation=contact)['status'], 'fail')

    def test_clearance_and_uncompleted_boolean(self):
        a, b = Part.makeBox(1, 1, 1), Part.makeBox(1, 1, 1, App.Vector(1.5, 0, 0))
        self.assertEqual(inspect_pair(a, b, 'A', 'B', clearance_mm=1)['status'], 'fail')
        self.assertEqual(inspect_pair(a, b, 'A', 'B', clearance_mm=.4)['status'], 'pass')
        self.assertEqual(inspect_pair(a, Part.Shape(), 'A', 'B')['status'], 'unknown')

    def test_null_and_non_solid_generation(self):
        self.assertEqual(inspect_solid(Part.Shape())['status'], 'fail')
        self.assertEqual(inspect_solid(line())['status'], 'fail')
        self.assertEqual(inspect_solid(Part.makeBox(1, 2, 3))['status'], 'pass')


class NativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if BUILDER is None:
            raise unittest.SkipTest('Native tests require --builder')
        os.environ['QT_QPA_PLATFORM'] = 'offscreen'
        import FreeCADGui as Gui
        Gui.showMainWindow()
        Gui.getMainWindow().hide()
        spec = importlib.util.spec_from_file_location('existing_cable_builder', BUILDER)
        cls.builder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.builder)
        EVIDENCE['environment'] = cls.builder.bootstrap_paths()

    def setUp(self):
        self.doc = App.newDocument('SyntheticElectromechanical')

    def tearDown(self):
        App.closeDocument(self.doc.Name)

    def test_native_wireflex_archcable_rebuild(self):
        cable, route = self.builder.make_native_cable(self.doc, None, 'Synthetic', [(0, 0, 0), (60, 0, 0), (60, 60, 0)], 4, 10)
        self.assertNotIn('MinimumRadius', route.PropertiesList)
        self.assertEqual(route.getEnumerationsOfProperty('PathType'), ['Wire', 'BSpline_P', 'BSpline_K'])
        measured = rebuild_cable_in_isolated_document(self.doc, cable)
        self.assertEqual(measured['status'], 'pass')
        self.assertEqual(measured['solid_count'], 1)
        route_measure = inspect_route(cable.Base.Shape.Wires[0], 10, (1, 0, 0), (0, -1, 0), start_position=(0, 0, 0), end_position=(60, 60, 0))
        self.assertEqual(route_measure['status'], 'pass')
        EVIDENCE['native_archcable'] = measured
        EVIDENCE['native_route'] = route_measure

    def test_failed_native_generation_does_not_reuse_old_solid(self):
        cable, route = self.builder.make_native_cable(self.doc, None, 'Synthetic', [(0, 0, 0), (50, 0, 0)], 4, 10)
        self.assertEqual(inspect_solid(cable.Shape)['status'], 'pass')
        original = cable.Proxy.makeMainShape
        # Reproduce the addon's observed failure contract: catch OCC error, return None.
        cable.Proxy.makeMainShape = lambda obj: None
        try:
            measured = rebuild_cable_in_isolated_document(self.doc, cable)
            self.assertEqual(measured['status'], 'fail')
            self.assertTrue(measured['null'])
            EVIDENCE['native_failed_generation_injected'] = measured
        finally:
            cable.Proxy.makeMainShape = original

    def test_recompute_false_never_passes(self):
        cable, route = self.builder.make_native_cable(self.doc, None, 'Synthetic', [(0, 0, 0), (50, 0, 0)], 4, 10)
        def failed_recompute():
            self.doc.recompute()
            return False
        measured = rebuild_cable_in_isolated_document(ReadingOverride(self.doc, recompute=failed_recompute), cable)
        self.assertTrue(measured['valid'])
        self.assertEqual(measured['status'], 'fail')
        self.assertIn('freecad_recompute_failed', measured['failures'])
        EVIDENCE['recompute_false_injected'] = measured

    def test_native_compoundpath_and_conduit(self):
        from freecad.cables import wireFlex, compoundPath, archCableConduit
        a = wireFlex.make_wireflex_from_vectors([App.Vector(0, 0, 0), App.Vector(50, 0, 0)])
        b = wireFlex.make_wireflex_from_vectors([App.Vector(50, 0, 0), App.Vector(100, 0, 0)])
        self.doc.recompute()
        path = compoundPath.make_compoundpath([a, b])
        self.doc.recompute()
        self.assertTrue(path.Shape.isValid())
        self.assertAlmostEqual(path.Shape.Length, 100)
        conduit = archCableConduit.makeCableConduit(selectlist=[path], name='SyntheticConduit')
        conduit.Diameter = 10
        conduit.WallThickness = 1
        self.doc.recompute()
        measured = inspect_solid(conduit.Shape)
        self.assertEqual(measured['status'], 'pass')
        EVIDENCE['native_compoundpath_conduit'] = {'path_type': path.PathType, 'length_mm': path.Shape.Length,
                                                  'conduit': measured, 'subconduits': len(conduit.SubConduits)}


def main():
    global BUILDER
    parser = argparse.ArgumentParser()
    parser.add_argument('--builder', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    BUILDER = args.builder.resolve() if args.builder else None
    suite = unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromTestCase(GeometryTests),
                               unittest.defaultTestLoader.loadTestsFromTestCase(NativeTests)])
    outcome = unittest.TextTestRunner(verbosity=2).run(suite)
    EVIDENCE.update(tests_run=outcome.testsRun, failures=len(outcome.failures), errors=len(outcome.errors),
                    skipped=[{'test': str(test), 'reason': reason} for test, reason in outcome.skipped],
                    geometry_stage='executed', interactive_stage='not_executed', physical_stage='not_executed')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(EVIDENCE, indent=2, ensure_ascii=False, allow_nan=False)+'\n', encoding='utf-8')
    print(json.dumps({'tests_run': outcome.testsRun, 'successful': outcome.wasSuccessful(), 'report': str(args.output)}), flush=True)
    return 0 if outcome.wasSuccessful() else 1


if __name__ == '__main__':
    code = main()
    # The dedicated GUI process can hang during Python/Qt shutdown on Windows.
    # Reports and console are flushed before terminating this process only.
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(code)
