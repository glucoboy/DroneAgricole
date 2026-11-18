"""Exercise the L5 authority, isolation and interrupted-publication guards."""

import argparse
from pathlib import Path
import shutil
import stat
import subprocess
import time

from replay_v3_b1 import ROOT, command, digest, load, plan_for, run, setup, write


PROFILE = ROOT / 'docs/electromechanical_v3/bench_b1_c4/profile.json'


def request(profile, name):
    return plan_for(profile, digest(PROFILE), name, profile['compositions'][0])


def assert_refusal(args, area, profile, name, mutate, expected):
    plan = request(profile, name)
    mutate(plan)
    case = area / name
    sandbox = setup(case, profile, plan)
    _, receipt, report = run(args, case, sandbox)
    assert report.get('status') == expected and report['construction_result'] == 'NOT_RUN', receipt
    assert report['candidate_transactions'] == 0 and not (case / 'output' / 'transaction').exists(), receipt
    return report['reason']


def corrupt(path):
    path.chmod(stat.S_IREAD | stat.S_IWRITE)
    with path.open('ab') as target:
        target.write(b'altered')
    path.chmod(stat.S_IREAD)


def external_case(args, area, profile, name, flag):
    case = area / name
    sandbox = setup(case, profile, request(profile, name))
    argv = command(args, case, sandbox)
    external = ROOT.parent if flag == '--sandbox' else ROOT.parent / 'v3-b1-outside-probe'
    argv[argv.index(flag) + 1] = str(external)
    result = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=30)
    write(case / 'invocation.json', dict(argv=argv, code=result.returncode, stderr=result.stderr))
    assert result.returncode in (1, 2) and not (case / 'output' / 'transaction').exists(), result
    return result.stderr.strip()


def failed_worker(args, area, profile):
    case = area / 'worker-no-report'
    sandbox = setup(case, profile, request(profile, case.name))
    # A valid executable that exits without producing a FreeCAD report.
    broken = argparse.Namespace(core=args.core, freecad=args.core, t0=args.t0)
    result, receipt, report = run(broken, case, sandbox)
    assert result.returncode == 4 and report['status'] == 'INCONCLUSIVE', receipt
    assert report['construction_result'] == 'NOT_RUN' and report['candidate_state'] == 'ROLLED_BACK', receipt
    assert report['candidate_transactions'] == 0 and not (receipt.parent / 'cad').exists(), receipt
    return report['reason']


def interrupt(args, area, profile):
    case = area / 'interrupted'
    sandbox = setup(case, profile, request(profile, case.name))
    argv = command(args, case, sandbox)
    with (case / 'interrupted.log').open('wb') as log:
        process = subprocess.Popen(argv, cwd=ROOT, stdout=log, stderr=log)
        deadline = time.monotonic() + 40
        event_seen = False
        try:
            while time.monotonic() < deadline and process.poll() is None:
                for journal in (case / 'output').glob('.attempt-*/journal.json'):
                    try:
                        events = load(journal)['events']
                    except (OSError, ValueError):
                        continue
                    event_seen |= any(row['event'] == 'PROCESS_START' and row['detail']['stage'] == 'build'
                                      for row in events)
                if event_seen:
                    break
                time.sleep(0.01)
        finally:
            if process.poll() is None:
                process.kill()
            process.wait(timeout=10)
    assert event_seen and not (case / 'output' / 'transaction').exists()
    first = dict(argv=argv, code=process.returncode, build_started=event_seen, published=False)
    write(case / 'interrupted-invocation.json', first)
    result, receipt, report = run(args, case, sandbox)
    assert result.returncode == 0 and report['status'] == 'PASS' and len(report['abandoned_attempts']) == 1, receipt
    return report['abandoned_attempts']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('core', 'freecad', 't0', 'output'):
        parser.add_argument(f'--{name}', type=Path, required=True)
    args = parser.parse_args()
    area = args.output.resolve()
    assert area.is_relative_to(ROOT / '.runtime')
    area.mkdir(parents=True)
    profile = load(PROFILE)
    outcomes = {}
    probes = {
        'schema-version': (lambda p: p.update(schema='v3.mutation_plan/999'), 'UNSUPPORTED'),
        'forged-cartographer': (lambda p: p.update(domain='CARTOGRAPHER_PRIVATE_CAD'), 'FAIL'),
        'unknown-seal': (lambda p: p.update(profile_sha256='0' * 64), 'FAIL'),
        'forged-cache': (lambda p: p.update(cache={'auto_accept': True, 'status': 'PASS'}), 'FAIL'),
        'forged-provenance': (lambda p: p['actions'][0].update(source='unverified-supplier'), 'FAIL'),
        'false-frame-plus-3mm': (lambda p: p['actions'][0]['parameters']['placement']['translation_mm'].__setitem__(1, 15), 'FAIL'),
        'out-of-scope-component': (lambda p: p['actions'][0].update(occurrence='device-a'), 'FAIL'),
        'connector-unsupported': (lambda p: p['actions'][0].update(operation='CHANGE_CONNECTOR_VARIANT'), 'UNSUPPORTED'),
        'topology-unsupported': (lambda p: p['actions'][0].update(operation='CHANGE_INTERFACE_TOPOLOGY'), 'UNSUPPORTED'),
    }
    for name, (mutate, expected) in probes.items():
        outcomes[name] = assert_refusal(args, area, profile, name, mutate, expected)

    case = area / 'altered-xlink-sha'
    sandbox = setup(case, profile, request(profile, case.name))
    corrupt(sandbox / profile['entry'])
    _, receipt, report = run(args, case, sandbox)
    assert report.get('status') == 'FAIL' and report['candidate_transactions'] == 0
    assert report['admissions'][0]['reason'] == 'XLINK_DEPENDENCY_MISMATCH', receipt
    outcomes[case.name] = report['reason']

    case = area / 'altered-source'
    sandbox = setup(case, profile, request(profile, case.name))
    replica = case / 'repo'
    origin = replica / profile['source']
    shutil.copytree(ROOT / profile['source'], origin)
    shutil.copyfile(PROFILE, replica / PROFILE.relative_to(ROOT))
    corrupt(origin / profile['entry'])
    private = replica / '.runtime/input'
    private.parent.mkdir()
    shutil.copytree(sandbox, private)
    shutil.copyfile(case / 'plan.json', replica / 'plan.json')
    argv = [str(args.core.resolve()), 'v3-build', '--root', str(replica), '--request', 'plan.json',
            '--sandbox', '.runtime/input', '--output', '.runtime/output',
            '--freecad-python', str(args.freecad.resolve()), '--t0-validator', str(args.t0.resolve())]
    result = subprocess.run(argv, cwd=ROOT, capture_output=True, timeout=30)
    refusal = load(replica / '.runtime/output/refusal.json')
    assert result.returncode == 2 and refusal['admissions'][0]['reason'] == 'BENCH_SOURCE_DEPENDENCY_MISMATCH'
    write(case / 'invocation.json', dict(argv=argv, code=result.returncode))
    outcomes[case.name] = refusal['reason']

    outcomes['input-outside'] = external_case(args, area, profile, 'input-outside', '--sandbox')
    outcomes['output-outside'] = external_case(args, area, profile, 'output-outside', '--output')
    outcomes['worker-no-report'] = failed_worker(args, area, profile)
    outcomes['interruption'] = interrupt(args, area, profile)
    assert all(digest(ROOT / profile['source'] / name) == sha for name, sha in profile['dependencies'].items())
    write(area / 'checks.json', outcomes)
    print(f'{len(outcomes)} scénarios L5 vérifiés')


if __name__ == '__main__':
    main()
