"""Teste la publication d'un problème V3 et la restriction stricte T2."""

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
MODEL = ROOT / 'docs/electromechanical_v3/bench_b1_workholding/model/Banc_Interconnexion.FCStd'
CORE = Path(sys.argv.pop(1)).resolve()


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, data):
    path.write_text(json.dumps(data), encoding='utf-8')


class ProblemSpec(unittest.TestCase):
    def setUp(self):
        runtime = ROOT / '.runtime'
        runtime.mkdir(exist_ok=True)
        self.area = Path(self.enterContext(tempfile.TemporaryDirectory(prefix='l3-problem-', dir=runtime)))
        self.domain_path = self.area / 'domain.json'
        self.domain = {
            'schema': 'v3.parametric_domain/1', 'domain': 'SYNTHETIC_BENCH',
            'placement': {'translation_min_mm': [-10, -5, 0], 'translation_max_mm': [10, 5, 0]},
            'supports': [{'anchor': 'a'}, {'anchor': 'b'}],
        }
        write(self.domain_path, self.domain)
        self.observation_path = self.area / 'observation.json'
        write(self.observation_path, {'fixture': 'observation de forme synthétique'})
        self.request = {
            'schema': 'v3.problem_spec/1', 'phase': 'T1',
            'domain_sha256': digest(self.domain_path), 'model_sha256': digest(MODEL),
            'observation_sha256': digest(self.observation_path), 'seed': 2147483647,
            'budget': {'max_proposals': 21, 'max_native': 3},
            'narrowing': {'translation_mm': {'min': [-10, -3, 0], 'max': [7, 5, 0]}},
            'objectives': [{'metric': 'route_length_mm', 'direction': 'MIN'},
                           {'metric': 'service_clearance_mm', 'direction': 'MAX'}],
        }

    def invoke(self, request, name, expected_error=None, base=None):
        source = self.area / f'{name}-request.json'
        output = self.area / f'{name}-spec.json'
        if isinstance(request, str):
            source.write_text(request, encoding='utf-8')
        else:
            write(source, request)
        argv = [str(CORE), 'v3-problem', '--root', str(ROOT), '--request', str(source),
                '--domain', str(self.domain_path), '--model', str(MODEL),
                '--observation', str(self.observation_path), '--output', str(output)]
        if base:
            argv += ['--base-problem', str(base)]
        result = subprocess.run(argv, cwd=ROOT, capture_output=True, encoding='utf-8', errors='replace', timeout=20)
        if expected_error:
            self.assertEqual(result.returncode, 1, result.stdout)
            self.assertIn(expected_error, result.stderr)
            self.assertFalse(output.exists())
        else:
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(output.read_bytes()), request)
            self.assertEqual(result.stdout.strip(), digest(output))
        self.assertFalse(output.with_suffix('.json.lock').exists())
        return output

    def test_deterministic_and_phase_labels(self):
        first = self.invoke(self.request, 't1')
        second = self.invoke(self.request, 't1-repeat')
        self.assertEqual(digest(first), digest(second))
        self.invoke({**self.request, 'phase': 'T0'}, 't0')
        self.invoke({**self.request, 'phase': 'T3'}, 't3')

    def test_t2_can_reduce_translation_or_zones(self):
        base = self.invoke(self.request, 't1')
        restriction = {**deepcopy(self.request), 'phase': 'T2', 'base_problem_sha256': digest(base)}
        self.invoke(restriction, 'no-change', 'restriction stricte', base)
        restriction['narrowing']['translation_mm']['min'][0] = -2
        self.invoke(restriction, 'translation', base=base)
        restriction['narrowing']['translation_mm']['max'][0] = 8
        self.invoke(restriction, 'outside-base', 'hors p', base)
        restriction['narrowing'] = {**self.request['narrowing'], 'support_zones': ['b']}
        self.invoke(restriction, 'support-zone', base=base)
        self.invoke({**restriction, 'seed': 7}, 'changed-seed', 'modifi', base)
        self.invoke({**restriction, 'objectives': restriction['objectives'][::-1]}, 'changed-objective-order',
                    'modifi', base)
        self.invoke({**restriction, 'base_problem_sha256': '0' * 64}, 'unbound-base', 'T1 exacte', base)
        self.invoke(restriction, 'missing-base-file', 'Fichier de r')

    def test_refuses_hash_changes_and_forged_domains(self):
        for field in ('domain_sha256', 'model_sha256', 'observation_sha256'):
            self.invoke({**self.request, field: '0' * 64}, field, 'divergente')
        self.domain['domain'] = 'CARTOGRAPHER_PRIVATE_CAD'
        write(self.domain_path, self.domain)
        self.invoke({**self.request, 'domain_sha256': digest(self.domain_path)}, 'cartographer', 'de banc requis')

    def test_refuses_malformed_or_unbounded_inputs(self):
        self.invoke({**self.request, 'seed': 0.5}, 'seed', 'hors limites')
        self.invoke({**self.request, 'budget': {'max_proposals': 3, 'max_native': 5}}, 'budget', 'max_native')
        self.invoke({**self.request, 'objectives': [{'metric': 'support_count', 'direction': 'MAX'}]},
                    'direction', 'Objectif Pareto')
        self.invoke({**self.request, 'narrowing': {'translation_mm': {'min': [-11, -3, 0], 'max': [7, 5, 0]}}},
                    'widen-domain', 'hors domaine')
        self.invoke({**self.request, 'narrowing': {**self.request['narrowing'], 'support_zones': ['forged']}},
                    'invent-zone', 'Ancrage non autoris')
        bytes_with_duplicate = json.dumps(self.request).replace('"seed":', r'"s\u0065ed": 0, "seed":')
        self.invoke(bytes_with_duplicate, 'duplicate-key', 'dupliqu')


if __name__ == '__main__':
    unittest.main()
