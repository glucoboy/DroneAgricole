import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / 'validation_engine' / 'fixtures'
EXECUTABLE = Path(sys.argv.pop(1)).resolve()


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        runtime = ROOT / '.runtime'
        runtime.mkdir(exist_ok=True)
        cls.temporary = tempfile.TemporaryDirectory(prefix='l4-contract-', dir=runtime)
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.work = Path(cls.temporary.name)
        cls.lock = cls.work / 'reference_lock.json'
        cls.candidates = cls.work / 'electrical'
        subprocess.run([sys.executable, '-B', str(Path(__file__).with_name('connectivity_cases.py')),
                        '--output', str(cls.candidates)], cwd=ROOT, check=True)
        result = cls.run_cli('seal', '--lock', cls.lock)
        if result.returncode:
            raise RuntimeError(result.stderr)
        cls.lock_sha = result.stdout.strip()

    @staticmethod
    def run_cli(*args):
        return subprocess.run([str(EXECUTABLE), *map(str, args)], cwd=ROOT,
                              capture_output=True, text=True, encoding='utf-8', timeout=35)

    def invoke(self, command, output, *args):
        return self.run_cli(command, '--lock', self.lock, '--lock-sha256', self.lock_sha,
                            '--output', self.work / output, *args)

    def test_campaign_separates_unavailable_native_checks_from_candidate_failures(self):
        result = self.invoke('campaign', 'without-native', '--candidates', self.candidates, '--skip-native')
        self.assertEqual(result.returncode, 3, result.stderr)
        path = self.work / 'without-native'
        campaign = load(path / 'campaign.json')
        self.assertEqual(campaign['verdict'], 'L4_CONDITIONAL')
        self.assertTrue(campaign['finalized'])
        self.assertEqual(campaign['cases']['native-nominal']['verdict'], 'NOT_RUN')
        self.assertEqual(campaign['cases']['native-l2']['verdict'], 'INCONCLUSIVE')
        self.assertEqual(campaign['cases']['diagnostic-nominal']['verdict'], 'PASS')
        self.assertEqual(campaign['cases']['f12-wrong-port']['verdict'], 'FAIL')
        self.assertEqual(campaign['cases']['f24a-unidentified']['verdict'], 'INCONCLUSIVE')
        self.assertEqual(campaign['cases']['electrical-matrix-tampered']['verdict'], 'FAIL')
        self.assertEqual(campaign['cases']['diagnostic-missing-return']['verdict'], 'FAIL')
        artifacts = load(path / 'artifacts.json')
        for artifact in artifacts['items']:
            self.assertEqual(sha256(path / artifact['path']), artifact['checksum_sha256'])

    def test_refuses_candidate_override_and_reused_output(self):
        candidate = load(self.candidates / 'f12-wrong-port.json')
        candidate.update(status='PASS', findings={'f12-port': 'PASS'}, requirements={'required_port_id': 'GPS2'})
        forged = self.work / 'forged.json'
        forged.write_text(json.dumps(candidate), encoding='utf-8')
        args = ('--case', 'f12-wrong-port', '--candidate', forged, '--candidate-id', 'test-f12')
        result = self.invoke('validate', 'forged-verdict', *args)
        self.assertEqual(result.returncode, 2, result.stderr)
        path = self.work / 'forged-verdict' / 'cases' / 'f12-wrong-port.json'
        report = load(path)
        self.assertEqual(report['verdict'], 'FAIL')
        self.assertEqual(report['validation_report']['candidate_id'], 'test-f12')
        self.assertEqual(report['candidate_sha256'], sha256(forged))
        self.assertEqual(self.invoke('validate', 'forged-verdict', *args).returncode, 1)
        self.assertEqual(load(path), report)

    def test_port_name_cannot_establish_an_unidentified_gpio(self):
        candidate = load(self.candidates / 'electrical-nominal.json')
        dossier = candidate['dossier']
        records = dossier['model']['records']
        records['ports'][0]['id'] = 'GPIO'
        records['connector_receptacles'][0]['port_id'] = 'GPIO'
        dossier['interfaces'][0]['required_port_id'] = 'GPIO'
        path = self.work / 'claimed-gpio.json'
        path.write_text(json.dumps(candidate), encoding='utf-8')
        result = self.invoke('validate', 'claimed-gpio', '--case', 'f24a-unidentified', '--candidate', path)
        self.assertEqual(result.returncode, 3, result.stderr)
        report = load(self.work / 'claimed-gpio' / 'cases' / 'f24a-unidentified.json')
        self.assertEqual(report['findings'][0]['status'], 'INCONCLUSIVE')

    def test_cable_rating_must_meet_the_frozen_demand_and_match_the_reference(self):
        for name, rating, code, status in (('undersized', 0.1, 2, 'FAIL'),
                                           ('inflated', 20, 3, 'INCONCLUSIVE')):
            with self.subTest(rating=rating):
                candidate = load(self.candidates / 'electrical-nominal.json')
                interface = candidate['dossier']['interfaces'][0]
                interface['requirements']['current_A']['value'] = 0.01
                cord = candidate['dossier']['cable_parts']['cordon']
                cord['specifications']['current_A']['value'] = rating
                path = self.work / f'{name}.json'
                path.write_text(json.dumps(candidate), encoding='utf-8')
                result = self.invoke('validate', name, '--case', 'electrical-nominal', '--candidate', path)
                self.assertEqual(result.returncode, code, result.stderr)
                report = load(self.work / name / 'cases' / 'electrical-nominal.json')
                findings = {finding['key']: finding for finding in report['findings']}
                self.assertEqual(findings['compatibility']['status'], status)
                self.assertEqual(findings['continuity']['status'], 'PASS')

    def test_refuses_lock_and_criterion_byte_mutations(self):
        bad_lock = self.work / 'bad_lock.json'
        bad_lock.write_bytes(self.lock.read_bytes() + b'\n')
        result = self.run_cli('validate', '--lock', bad_lock, '--lock-sha256', self.lock_sha,
                              '--case', 'f12-wrong-port', '--output', self.work / 'bad-lock-output')
        self.assertEqual(result.returncode, 1)
        self.assertFalse((self.work / 'bad-lock-output').exists())

        config = load(FIXTURES / 'reference.json')
        criterion = self.work / 'acceptance.json'
        criterion.write_bytes((FIXTURES / 'acceptance.json').read_bytes())
        config['files']['acceptance'] = criterion.relative_to(ROOT).as_posix()
        config_path = self.work / 'reference.json'
        config_path.write_text(json.dumps(config), encoding='utf-8')
        lock = self.work / 'criterion_lock.json'
        sealed = self.run_cli('seal', '--lock', lock, '--configuration', config_path)
        self.assertEqual(sealed.returncode, 0, sealed.stderr)
        criterion.write_bytes(criterion.read_bytes() + b'\n')
        result = self.run_cli('validate', '--lock', lock, '--lock-sha256', sealed.stdout.strip(),
                              '--case', 'f12-wrong-port', '--output', self.work / 'mutated-output')
        self.assertEqual(result.returncode, 1)
        self.assertFalse((self.work / 'mutated-output').exists())

    def test_inconclusive_from_missing_observations(self):
        result = self.invoke('validate', 'without-dossier', '--case', 'electrical-nominal')
        self.assertEqual(result.returncode, 3, result.stderr)
        report = load(self.work / 'without-dossier' / 'cases' / 'electrical-nominal.json')
        self.assertEqual(report['counts'], {'PASS': 0, 'FAIL': 0, 'INCONCLUSIVE': 4, 'NOT_RUN': 0})


if __name__ == '__main__':
    unittest.main()
