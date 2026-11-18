"""Prepare read-only inputs and replay sealed B.1 plans through convergence_core."""

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import stat
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')


def load(path):
    return json.loads(path.read_bytes())


def plan_for(profile, profile_sha, case_id, sequence):
    actions = {row['id']: row for row in profile['actions']}
    context = '\n'.join((profile_sha, case_id, *sequence))
    return dict(schema='v3.mutation_plan/1', plan_id=case_id, domain='SYNTHETIC_BENCH',
                profile_sha256=profile_sha, actions=[deepcopy(actions[name]) for name in sequence],
                context_sha256=hashlib.sha256(context.encode()).hexdigest())


def setup(case_dir, profile, plan):
    case_dir.mkdir()
    sandbox = case_dir / 'input'
    for name, expected in profile['dependencies'].items():
        source = ROOT / profile['source'] / name
        assert digest(source) == expected, source
        target = sandbox / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        target.chmod(stat.S_IREAD)
    write(case_dir / 'plan.json', plan)
    return sandbox


def command(args, case_dir, sandbox):
    return [str(args.core.resolve()), 'v3-build', '--root', str(ROOT),
            '--request', str(case_dir / 'plan.json'), '--sandbox', str(sandbox),
            '--output', str(case_dir / 'output'), '--freecad-python', str(args.freecad.resolve()),
            '--t0-validator', str(args.t0.resolve())]


def run(args, case_dir, sandbox):
    argv = command(args, case_dir, sandbox)
    run_result = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=340)
    write(case_dir / 'invocation.json', dict(argv=argv, code=run_result.returncode,
          stdout=run_result.stdout, stderr=run_result.stderr))
    terminal = case_dir / 'output' / 'transaction' / 'campaign.json'
    refusal = case_dir / 'output' / 'refusal.json'
    receipt = terminal if terminal.is_file() else refusal
    report = load(receipt) if receipt.is_file() else {}
    print(case_dir.name, run_result.returncode, report.get('status'), report.get('reason', run_result.stderr.strip()))
    return run_result, receipt, report


def cases(args, profile_path, output, selected):
    profile = load(profile_path)
    profile_sha = digest(profile_path)
    for index, sequence in enumerate(profile['compositions'], 1):
        if selected and index not in selected:
            continue
        case_id = f"{profile['model_id']}-{index}"
        case_dir = output / case_id
        sandbox = setup(case_dir, profile, plan_for(profile, profile_sha, case_id, sequence))
        run_result, receipt, report = run(args, case_dir, sandbox)
        outputs = profile.get('replay', {}).get(str(index), {})
        expected = outputs.get('status', 'PASS')
        assert report.get('status') == expected and run_result.returncode == {'PASS': 0, 'FAIL': 2, 'INCONCLUSIVE': 4}[expected], receipt
        assert report.get('source_integrity', {}).get('status') == 'PASS', receipt
        assert report.get('construction_result') == outputs.get('construction', 'PASS'), receipt
        assert report.get('candidate_transactions') == 1, receipt
        assert all(digest(sandbox / name) == expected_hash and
                   digest(ROOT / profile['source'] / name) == expected_hash
                   for name, expected_hash in profile['dependencies'].items()), case_dir
        tx = receipt.parent
        if outputs.get('construction', 'PASS') == 'PASS':
            assert (tx / 'cad' / profile['entry']).is_file(), tx
            assert digest(tx / 'cad' / profile['entry']) != profile['dependencies'][profile['entry']], tx
            baseline, candidate, built = (load(tx / f) for f in
                                          ('baseline-validation.json', 'candidate-validation.json', 'build.json'))
            assert baseline['pid'] != candidate['pid'] and built['pid'] != candidate['pid'], tx
            assert candidate['inputs_sha256'] == report['native_sha256'], tx
        else:
            assert report['candidate_state'] == 'ROLLED_BACK' and not (tx / 'cad').exists(), tx
        assert load(tx / 't0-crosscheck.json')['exit_code'] == 0, tx
        yield dict(plan_id=case_id, status=report['status'], operations=sequence,
                   receipt=receipt.relative_to(ROOT).as_posix(), sha256=digest(receipt))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('core', 'freecad', 't0', 'output'):
        parser.add_argument(f'--{name}', type=Path, required=True)
    parser.add_argument('--profile', type=Path, required=True, action='append')
    parser.add_argument('--case', type=int, action='append')
    args = parser.parse_args()
    output = args.output.resolve()
    assert output.is_relative_to(ROOT / '.runtime')
    output.mkdir(parents=True)
    report = [receipt for profile in args.profile for receipt in cases(args, profile, output, args.case)]
    assert report
    write(output / 'replay.json', report)
    return 0


if __name__ == '__main__':
    sys.exit(main())
