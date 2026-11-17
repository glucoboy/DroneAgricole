"""Exercise V4 on editable cables measured from a saved native candidate."""

import os
from pathlib import Path
import tempfile
import unittest

from electromechanical_engine.freecad import FreeCADAdapter, guard


def route(offset, end_y, radius=5):
    return {'points_mm': [[0, 0, 10], [20, 0, 10], [20, offset, 10], [80, offset, 10],
                          [80, end_y, 10], [100, end_y, 10]], 'bend_radius_mm': radius}


def scenario():
    moved = {'ports': {'P1': {'position_mm': [100, 5, 10], 'tangent': [-1, 0, 0]}}}
    states = {'clear': moved | {'boxes': {'barrier': {'translation_mm': [0, -5, 0]}}},
              'blocked': moved | {'boxes': {'barrier': {'translation_mm': [0, 17.5, 0]}}},
              'stretched': moved, 'wrong_end': moved, 'missing': moved}
    return {
        'system': {
            'ports': [{'id': 'P0', 'position_mm': [0, 0, 10], 'tangent': [1, 0, 0]},
                      {'id': 'P1', 'position_mm': [100, 0, 10], 'tangent': [-1, 0, 0]}],
            'links': [{'id': 'L0', 'source': 'P0', 'target': 'P1', 'mobile': True}],
            'geometry': {'boxes': [{'id': 'barrier', 'origin_mm': [42, -2, 8], 'size_mm': [16, 4, 4]}],
                         'motion_states': states},
        },
        'requirements': {'links': {'L0': {'diameter_mm': 2, 'min_radius_mm': 4.9,
                                         'min_dynamic_radius_mm': 4.9, 'min_reserve_mm': 20,
                                         'motion_length_tolerance_mm': 0.01,
                                         'required_motion_states': list(states)}},
                         'clearance_mm': 1},
        'candidate': {'routes': {'L0': route(15, 0)},
                      'motion_routes': {'clear': {'L0': route(17.5, 5)}, 'blocked': {'L0': route(17.5, 5)},
                                        'stretched': {'L0': route(20, 5, 4)}, 'wrong_end': {'L0': route(15, 0)}}},
    }


def second_cable(plan):
    system, rules, candidate = (plan[key] for key in ('system', 'requirements', 'candidate'))
    system['ports'].extend([{'id': 'P2', 'position_mm': [0, 60, 10], 'tangent': [1, 0, 0]},
                            {'id': 'P3', 'position_mm': [100, 60, 10], 'tangent': [-1, 0, 0]}])
    system['links'].append({'id': 'L1', 'source': 'P2', 'target': 'P3', 'mobile': True})
    rules['links']['L1'] = rules['links']['L0'].copy()
    candidate['routes']['L1'] = {'points_mm': [[x, y + 60, z] for x, y, z in route(15, 0)['points_mm']],
                                 'bend_radius_mm': 5}
    for state, spec in system['geometry']['motion_states'].items():
        spec['ports']['P3'] = {'position_mm': [100, 65, 10], 'tangent': [-1, 0, 0]}
        poses = candidate['motion_routes'].setdefault(state, {})
        poses['L1'] = {'points_mm': [[x, y + 60, z] for x, y, z in route(17.5, 5)['points_mm']],
                       'bend_radius_mm': 5}


@unittest.skipUnless(os.environ.get('ELECTROMECHANICAL_FREECAD_PYTHON'), 'FreeCAD integration not requested')
class NativeMotionTests(unittest.TestCase):
    def test_native_discrete_states_pass_fail_and_remain_unknown(self):
        adapter = FreeCADAdapter(os.environ['ELECTROMECHANICAL_FREECAD_PYTHON'])
        plan = scenario()
        second_cable(plan)
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'candidate'
            observed = adapter.build(plan, target)
            self.assertTrue(observed['reopened'])
            self.assertNotEqual(observed['saved_worker_id'], observed['worker_id'])
            self.assertTrue(observed['collision_complete'])
            self.assertTrue(all(pair['status'] == 'pass' for pair in observed['collisions']))
            states = observed['motion']['L0']
            clear, blocked, stretched = (states[state] for state in ('clear', 'blocked', 'stretched'))
            self.assertTrue(clear['clearance_ok'])
            self.assertTrue(clear['solid_valid'])
            self.assertTrue(clear['rebuild_evidence']['cache_cleared'])
            self.assertTrue(clear['diameter_ok'])
            self.assertTrue(clear['continuity_ok'])
            self.assertTrue(clear['endpoints_ok'])
            self.assertTrue(clear['tangency_ok'])
            self.assertTrue(clear['length_ok'])
            self.assertAlmostEqual(clear['length_delta_mm'], 0)
            self.assertAlmostEqual(clear['chord_mm'], (100 ** 2 + 5 ** 2) ** 0.5)
            self.assertGreater(clear['reserve_mm'], 20)
            self.assertTrue(clear['radius_certified'])
            self.assertAlmostEqual(clear['min_radius_mm'], 5)
            self.assertEqual(clear['obstacle_translations_mm']['barrier'], [0, -5, 0])
            self.assertTrue(all(pair['clearance_mm'] > 1 for pair in clear['clearance_pairs']))
            self.assertNotEqual(clear['native_object'], blocked['native_object'])
            self.assertTrue(blocked['length_ok'])
            self.assertFalse(blocked['clearance_ok'])
            self.assertGreater(max(pair['intersection_mm3'] for pair in blocked['clearance_pairs']), 1)
            self.assertFalse(stretched['length_ok'])
            self.assertIsNone(stretched['reserve_mm'])
            self.assertAlmostEqual(stretched['min_radius_mm'], 4)
            self.assertFalse(states['wrong_end']['endpoints_ok'])
            self.assertIsNone(states['wrong_end']['reserve_mm'])
            self.assertIsNone(states['missing']['clearance_ok'])
            self.assertEqual(states['missing']['missing_shapes'], ['L0'])
            other_states = observed['motion']['L1']
            self.assertTrue(other_states['blocked']['clearance_ok'])
            self.assertIsNone(other_states['missing']['clearance_ok'])
            self.assertTrue(any(pair['status'] == 'unknown' and {pair['a'], pair['b']} == {'L0', 'L1'}
                                for pair in other_states['missing']['clearance_pairs']))
            native_hash = guard.sha256(target / 'candidate.FCStd')
            independent = adapter.inspect(target, plan)
            self.assertEqual(independent['motion'], observed['motion'])
            self.assertNotEqual(independent['worker_id'], observed['worker_id'])
            self.assertEqual(guard.sha256(target / 'candidate.FCStd'), native_hash)
