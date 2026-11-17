"""Replay pinned XLink tasks through the existing FreeCAD worker protocol."""

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, FIRST_COMPLETED, wait
from contextlib import contextmanager
import ctypes
from ctypes import wintypes
import hashlib
import json
import os
from pathlib import Path
import subprocess
import threading
import time
from uuid import uuid4


def read(path):
    return json.loads(path.read_bytes())


def sha(data):
    return hashlib.sha256(data).hexdigest()


def write(path, value):
    data = json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(',', ':')).encode()
    temporary = path.with_name(path.name + '.tmp')
    with temporary.open('wb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)
    return sha(data)


def checked(root, reference):
    path = root / reference['path']
    if sha(path.read_bytes()) != reference['sha256']:
        raise ValueError(f'Changed authority input: {path}')
    return path


@contextmanager
def exclusive_run(path):
    with path.open('a+b') as lock:
        lock.seek(0)
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


class Memory(ctypes.Structure):
    _fields_ = [('size', wintypes.DWORD), ('faults', wintypes.DWORD)] + [
        (name, ctypes.c_size_t) for name in
        ('peak', 'working', 'peak_paged', 'paged', 'peak_nonpaged', 'nonpaged', 'pagefile', 'peak_pagefile')]


def peak_memory(process):
    if os.name != 'nt':
        return None
    query = ctypes.windll.psapi.GetProcessMemoryInfo
    query.argtypes = [wintypes.HANDLE, ctypes.POINTER(Memory), wintypes.DWORD]
    counters = Memory()
    counters.size = ctypes.sizeof(counters)
    if query(int(process._handle), ctypes.byref(counters), counters.size):
        return counters.peak
    return None


def run_batch(workspace, output, freecad, template, tasks, limit, number, worker_script=None):
    prefix = f'lot-{number:04}'
    request_path = output / f'{prefix}.request.json'
    result_path = output / f'{prefix}.result.json'
    log_path = output / f'{prefix}.log'
    summary_path = output / f'{prefix}.json'
    request = dict(template, tasks=tasks)
    request_sha = write(request_path, request)
    channel = f'DRONE_XLINK:{uuid4()}:'
    environment = dict(os.environ, DRONE_XLINK_RESULT_CHANNEL=channel,
                       DRONE_XLINK_REQUEST_SHA256=request_sha, QT_QPA_PLATFORM='offscreen', PYTHONUTF8='1')
    entry = [str(worker_script)] if worker_script else ['-m', 'electromechanical_engine.xlink_native']
    command = [freecad, '-B', *entry, str(request_path), str(result_path)]
    began = time.monotonic()
    ids = {task['id'] for task in tasks}
    starts, responses = {}, []
    with subprocess.Popen(command, cwd=workspace, env=environment, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace') as process:
        def record():
            with log_path.open('w', encoding='utf-8') as log:
                for line in process.stdout:
                    elapsed = time.monotonic() - began
                    if line.startswith(channel):
                        responses.append((elapsed, line[len(channel):]))
                        continue
                    log.write(f'{elapsed:.6f} {line}')
                    log.flush()
                    candidate = line.partition(': ')[0]
                    if candidate in ids:
                        starts[candidate] = elapsed

        reader = threading.Thread(target=record)
        reader.start()
        timed_out, memory = False, None
        while process.poll() is None:
            sample = peak_memory(process)
            if sample is not None:
                memory = max(sample, memory or 0)
            remaining = limit - (time.monotonic() - began)
            if remaining <= 0:
                timed_out = True
                process.kill()
                process.wait()
                break
            try:
                process.wait(timeout=min(remaining, 1))
            except subprocess.TimeoutExpired:
                continue
        reader.join()
        exit_code, pid = process.returncode, process.pid
    elapsed = time.monotonic() - began
    malformed = False
    try:
        result = json.loads(responses[0][1]) if len(responses) == 1 and not timed_out else {}
        if not isinstance(result, dict):
            raise ValueError('Expected a response object')
    except ValueError:
        result, malformed = {}, True
    rows = result.get('observations', [])
    problem = None
    if result.get('finalized') is True:
        same_state = (result['request_sha256'] == request_sha == sha(request_path.read_bytes())
                      and result['pid'] == pid and result['worker_id']
                      and result['before_sha256'] == result['after_sha256'] == request['native_sha256']
                      and result['environment'] == request['environment']
                      and result['measurement_identity_sha256'] == request['measurement_identity_sha256']
                      and result['inventory_complete'] and result['recompute_ok']
                      and not result['broken_links'] and not result['invalid_objects'])
        same_tasks = len(rows) == len(tasks) and all(
            row['task'] == task and row['cache_key'] == request['cache_key'] and row['worker_pid'] == pid
            for row, task in zip(rows, tasks))
        if exit_code != 0 or not same_state or not same_tasks or result_path.exists():
            raise ValueError(f'Invalid response provenance: {prefix}')
    else:
        rows = []
        if timed_out:
            problem = 'NATIVE_TIMEOUT'
        elif malformed:
            problem = 'NATIVE_INVALID_FRAME'
        else:
            problem = result.get('reason', 'NATIVE_CRASH_OR_NO_RESPONSE')
    result_sha = write(result_path, result) if result else None
    ordered_times = list(starts.items())
    timings = {task: ordered_times[index + 1][1] - start
               for index, (task, start) in enumerate(ordered_times[:-1])}
    if rows and ordered_times:
        task, start = ordered_times[-1]
        timings[task] = responses[0][0] - start
    summary = dict(batch=number, command=command, requested=[task['id'] for task in tasks], started=list(starts),
                   observed=[row['task']['id'] for row in rows], request_sha256=request_sha,
                   result_sha256=result_sha, log_sha256=sha(log_path.read_bytes()), pid=pid,
                   worker_id=result.get('worker_id'), exit_code=exit_code, timeout_s=limit, elapsed_s=elapsed,
                   first_task_s=next(iter(starts.values()), None), between_task_starts_s=timings,
                   peak_working_set_bytes=memory, error=problem,
                   worker_script_sha256=sha(worker_script.read_bytes()) if worker_script else None)
    write(summary_path, summary)
    return summary, rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('workspace', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('freecad')
    parser.add_argument('--size', type=int, default=48)
    parser.add_argument('--workers', type=int, default=4)
    parser.add_argument('--timeout', type=int, default=150)
    parser.add_argument('--progress-sha256', help='Latest progress seal from the separate supervisor log')
    parser.add_argument('--retry-oem', action='store_true')
    parser.add_argument('--task-list', type=Path, help='JSON array of pending pair IDs for a targeted retry')
    parser.add_argument('--component-worker', type=Path, help='Pinned alternate worker for a targeted retry')
    parser.add_argument('--reserved', type=int, default=0,
                        help='Tasks reserved for a simultaneous run of the pinned CLI')
    args = parser.parse_args()
    workspace, output = args.workspace.resolve(), args.output.resolve()
    if not output.is_relative_to(workspace / '.runtime') or min(args.size, args.workers, args.timeout) < 1:
        parser.error('Output and positive budgets must be scoped to the isolated campaign')
    if args.component_worker and not args.task_list:
        parser.error('An alternate worker requires a targeted list of pair IDs')
    output.mkdir(parents=True, exist_ok=True)
    with exclusive_run(output / 'execution.lock'):
        replay(workspace, output, args)


def replay(workspace, output, args):
    authority = read(workspace / 'docs/verification/v21_fix_b_coverage.json')
    prior = authority['attempts'][-1]
    campaign = read(checked(workspace, prior['proof']['campaign']))
    parent = checked(workspace, prior['checkpoint'])
    baseline = read(parent)
    for item in (authority['validator'], authority['worker'], authority['frozen_source_sha256'],
                 authority['electrical_input'], prior['proof']['inventory']):
        checked(workspace, item)
    template = read(parent.with_name('batch.request.json'))
    template.pop('tasks')
    inventory = read(checked(workspace, prior['proof']['inventory']))
    if not (template['action'] == 'measure'
            and Path(template['copy']).resolve(strict=True) == (parent.parent.parent / 'copy').resolve(strict=True)
            and template['cache_key'] == baseline['measurement_key'] == campaign['closure']['cache_key']
            and template['criteria'] == campaign['criteria']
            and template['native_sha256'] == campaign['closure']['saved_sha256'] == inventory['before_sha256']
            and template['environment'] == inventory['environment']
            and template['measurement_identity_sha256'] == campaign['closure']['measurement_identity_sha256']
            == inventory['measurement_identity_sha256']
            and sha(Path(args.freecad).read_bytes()) == campaign['pins']['freecad_python']):
        raise ValueError('Divergent measurement context')
    for file, expected in campaign['pins'].items():
        if '/' in file and sha((workspace / file).read_bytes()) != expected:
            raise ValueError(f'Changed pinned adapter: {file}')
    pending = [row['task'] for row in campaign['geometry']['checks']
               if row['task']['kind'] == 'pair' and row['status'] == 'NOT_RUN']
    earlier = Counter()
    for attempt in authority['attempts']:
        run = checked(workspace, attempt['checkpoint']).parent
        schedule = read(run / 'scheduled.json')
        if schedule['cache_key'] != template['cache_key']:
            raise ValueError(f'Divergent schedule: {run}')
        earlier.update(schedule['ids'])
    pending.sort(key=lambda task: earlier[task['id']])
    worker_script = args.component_worker.resolve(strict=True) if args.component_worker else None
    if args.retry_oem:
        worker_script = Path(__file__).with_name('replay_xlink_oem_worker.py').resolve()
    requested = set(read(args.task_list)) if args.task_list else None
    if requested is not None and not requested <= {task['id'] for task in pending}:
        raise ValueError('Targeted retry includes an ID outside the pending plan')
    selected = {task['id']: task for task in pending[args.reserved:]
                if (task['id'] in requested if requested is not None
                    else not args.retry_oem or task['b'].endswith('/FabricantSansRefroidissement'))}
    plan = dict(checkpoint=prior['checkpoint'], measurement_key=baseline['measurement_key'],
                selected=list(selected), reserved=[task['id'] for task in pending if task['id'] not in selected])
    if worker_script:
        plan['worker_script_sha256'] = sha(worker_script.read_bytes())
    plan_path = output / 'plan.json'
    if plan_path.exists() and read(plan_path) != plan:
        raise ValueError('Cannot resume against a different task plan')
    write(plan_path, plan)
    snapshots = output / 'checkpoints'
    snapshots.mkdir(exist_ok=True)
    seals_path = output / 'supervisor.log'
    if args.progress_sha256:
        candidates = [path for path in snapshots.glob('*.json') if sha(path.read_bytes()) == args.progress_sha256]
        if len(candidates) != 1 or args.progress_sha256 not in seals_path.read_text(encoding='utf-8'):
            raise ValueError('Resuming requires the last progress seal from the supervisor log')
        progress = read(candidates[0])
    else:
        if any(snapshots.glob('*.json')):
            raise ValueError('Select a sealed progress checkpoint before resuming')
        progress = dict(lots=[], observations={}, exhausted={})
    for proof in progress['lots']:
        for suffix, key in (('.request.json', 'request_sha256'), ('.log', 'log_sha256'),
                            ('.result.json', 'result_sha256')):
            path = output / f"lot-{proof['batch']:04}{suffix}"
            if proof[key] is not None and sha(path.read_bytes()) != proof[key]:
                raise ValueError(f'Changed completed lot: {path}')
    sequence = max([0] + [int(path.name.split('.')[0].split('-')[1]) for path in output.glob('lot-*.request.json')])
    single_attempts = Counter(proof['requested'][0] for proof in progress['lots'] if len(proof['requested']) == 1)
    remaining = [task for id_, task in selected.items()
                 if id_ not in progress['observations'] and id_ not in progress['exhausted']]
    heavy = [task for task in remaining if worker_script is None and task['b'].endswith('/FabricantSansRefroidissement')]
    regular = [task for task in remaining if task not in heavy]
    queue = [(regular[start:start + args.size], 0) for start in range(0, len(regular), args.size)]
    queue.extend(([task], single_attempts[task['id']]) for task in heavy)
    queue.extend(([row['task']], single_attempts[id_]) for id_, row in progress['observations'].items()
                 if row['observation']['status'] == 'unknown' and single_attempts[id_] < 2)
    active = {}
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        while queue or active:
            while queue and len(active) < args.workers:
                tasks, retries = queue.pop(0)
                sequence += 1
                limit = args.timeout if len(tasks) > 1 else args.timeout * (retries + 1)
                future = executor.submit(run_batch, workspace, output, args.freecad, template, tasks, limit,
                                         sequence, worker_script)
                active[future] = (tasks, retries)
            done, _ = wait(active, timeout=10, return_when=FIRST_COMPLETED)
            for future in done:
                tasks, retries = active.pop(future)
                summary, rows = future.result()
                progress['lots'].append(summary)
                for row in rows:
                    id_ = row['task']['id']
                    progress['observations'][id_] = row
                    if row['observation']['status'] == 'unknown' and retries < 2:
                        queue.append(([row['task']], retries + 1))
                if not rows and len(tasks) > 1:
                    middle = len(summary['started']) - 1 if summary['started'] else len(tasks) // 2
                    groups = (tasks[:middle], tasks[middle:middle + 1], tasks[middle + 1:])
                    queue.extend((group, retries) for group in groups if group)
                if not rows and len(tasks) == 1:
                    if retries < 2:
                        queue.append((tasks, retries + 1))
                    else:
                        progress['exhausted'][tasks[0]['id']] = summary
                snapshot = snapshots / f"after-{summary['batch']:04}.json"
                seal = write(snapshot, progress)
                line = (f"lot={summary['batch']} rows={len(rows)} seconds={summary['elapsed_s']:.1f} "
                        f"covered={len(progress['observations'])}/{len(selected)} seal={seal} "
                        f"checkpoint={snapshot.name} failure={summary['error']}")
                with seals_path.open('a', encoding='utf-8') as log:
                    log.write(line + '\n')
                    log.flush()
                    os.fsync(log.fileno())
                print(line, flush=True)


if __name__ == '__main__':
    main()
