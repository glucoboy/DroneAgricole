"""Execute the sealed V3 reference, transfer, bench and rejection checks."""

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
from uuid import uuid4


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def digest(path):
    with path.open('rb') as input_file:
        return hashlib.file_digest(input_file, 'sha256').hexdigest()


def write(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as output:
        json.dump(value, output, ensure_ascii=False, indent=2, sort_keys=True)
        output.write('\n')


def run(core, *args, expected=0):
    command = [value.as_posix() if isinstance(value, Path) else value for value in (core, *args)]
    result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8')
    if result.returncode != expected:
        raise RuntimeError(f'{args}: {result.returncode} instead of {expected}: {result.stderr}')
    return result.stderr.strip() if expected else result.stdout.strip()


def utc():
    return datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')


def start_evidence(output, inputs):
    run_id = 'electromechanical_v3_a_' + uuid4().hex
    references = [{'input_id': name, 'kind': 'other',
                   'reference': {'path': path.resolve().relative_to(Path.cwd()).as_posix()},
                   'checksums': {'sha256': digest(path)}} for name, path in inputs.items()]
    request = {'schema': 'drone_agricole.run_request.v1', 'request_id': run_id + '_request',
               'simulation_id': 'electromechanical_v3_a', 'variant_id': 'reference',
               'requested_at_utc': utc(), 'inputs': references, 'parameters': {'operations': ['MOVE', 'RETENTION', 'FRAME']}}
    write(output / 'run_request.json', request)
    return run_id, request, utc()


def finalize_evidence(output, context, results, graphs, validator):
    run_id, request, started = context
    paths = {'request': 'run_request.json', 'metrics': 't0_metrics.json', 'artefacts': 'artifacts.json',
             'events': 'events.jsonl', 'checks': 'checks.json'}
    manifest = {key: request[key] for key in ('request_id', 'simulation_id', 'variant_id', 'inputs', 'parameters')}
    finished = utc()
    manifest.update(schema='drone_agricole.run_manifest.v1', run_id=run_id, runner_id='electromechanical_graph_core',
                    domain='electromechanical', state='completed', created_at_utc=request['requested_at_utc'],
                    started_at_utc=started, finished_at_utc=finished, files=paths,
                    software={'validator_sha256': digest(validator)},
                    compatibility={'comparison_group': 'electromechanical_v3_a', 'result_contract_version': 1})
    write(output / paths['metrics'], {'schema': 'drone_agricole.metrics.v1', 'run_id': run_id,
                                       'simulation_id': request['simulation_id'], 'status': 'complete', 'summary': [],
                                       'groups': {'impact': results}})
    with (output / paths['events']).open('x', encoding='utf-8') as events:
        for sequence, (event, state, when) in enumerate((('campaign_started', 'running', started),
                                                         ('campaign_finalized', 'completed', finished))):
            events.write(json.dumps({'schema': 'drone_agricole.event.v1', 'run_id': run_id, 'sequence': sequence,
                                     'timestamp_utc': when, 'event_type': event, 'severity': 'info',
                                     'message': 'Vérification du graphe et des oracles V3-A', 'state': state,
                                     'data': {}}) + '\n')
    paths_to_seal = [paths[k] for k in ('request', 'metrics', 'events', 'checks')]
    paths_to_seal += [path.name for path in graphs.values()]
    paths_to_seal += [case['artifact'] for cases in results.values() for case in cases]
    artifacts = [{'artifact_id': 'proof-' + str(i), 'kind': 'events' if path.endswith('.jsonl') else 'report',
                  'label': path, 'path': path, 'media_type': 'application/x-ndjson' if path.endswith('.jsonl') else 'application/json',
                  'role': 'output', 'replayable': True, 'checksum_sha256': digest(output / path)}
                 for i, path in enumerate(paths_to_seal)]
    write(output / paths['artefacts'], {'schema': 'drone_agricole.artifacts.v1', 'run_id': run_id, 'items': artifacts})
    write(output / 't0_run_manifest.json', manifest)
    print(run(validator, 'validate', output, '.'))


def run_cases(core, graph, oracle, output, label):
    result = []
    for case in read(oracle)['cases']:
        operation, target = case['operation'], case['target']
        path = output / f'{label}-{operation.lower()}.json'
        run(core, 'impact', graph, operation, target, '--graph-sha256', digest(graph), '--output', path)
        impact = read(path)
        nodes, checks = set(impact['nodes']), set(impact['checks'])
        missing = sorted(set(case['required_nodes']) - nodes)
        missing_checks = sorted(set(case['required_checks']) - checks)
        forbidden = sorted(set(case['forbidden_nodes']) & nodes)
        if missing or missing_checks or forbidden or impact['applied']:
            raise RuntimeError(f'{label} {operation}: {missing=}, {missing_checks=}, {forbidden=}')
        result.append({'operation': operation, 'target': target, 'artifact': path.name, 'sha256': digest(path),
                       'required_nodes_found': len(case['required_nodes']),
                       'required_checks_found': len(case['required_checks']),
                       'additional_nodes': len(nodes - set(case['required_nodes'])),
                       'status': 'PASS'})
    return result


def negatives(core, native, graph, overlay, output):
    originals = {path: digest(path) for path in (native, graph, overlay)}
    errors = {}
    errors['forbidden_operation_subject'] = run(core, 'impact', graph, 'RETENTION', 'port:W40/A', expected=1)
    errors['existing_output'] = run(core, 'validate', graph, '--output', graph, expected=1)
    modified_native = read(native)
    modified_native['transfer']['status'] = 'FAIL'
    bad_native = output / 'invalid-native.json'
    write(bad_native, modified_native)
    errors['altered_native_sha256'] = run(core, 'import', '.', bad_native, overlay, '--cartographe-l2',
                                         '--native-sha256', originals[native], expected=1)
    errors['failed_transfer'] = run(core, 'import', '.', bad_native, overlay, '--cartographe-l2',
                                    '--native-sha256', digest(bad_native), expected=1)
    value = read(graph)
    link = next(node for node in value['nodes'] if node['id'] == 'link:W40')
    port = next(node for node in value['nodes'] if node['id'] == 'port:W40/B')
    all_values = deepcopy(value)
    value['edges'] = [edge for edge in value['edges'] if edge['id'] != 'ROUTING:link:W40->axis:F40']
    tests = {'missing_route': deepcopy(value)}
    link['claims'] = []
    tests['missing_topology'] = deepcopy(value)
    value = deepcopy(all_values)
    value['nodes'] = [node for node in value['nodes'] if node['id'] != 'anchor:iso-carrier']
    tests['missing_anchor'] = value
    value = all_values
    port = next(node for node in value['nodes'] if node['id'] == port['id'])
    claim = next(claim for claim in port['claims'] if claim['key'] == 'mating_frame')
    port['claims'].remove(claim)
    tests['incomplete_connector'] = deepcopy(value)
    claim['value'] = {'origin_role': 'ROUTE_AXIS'}
    claim['evidence'].update(state='DOCUMENTED', reception='PASS', locator='/does-not-exist')
    port['claims'].append(claim)
    tests['axis_as_port_authority'] = deepcopy(value)
    for label, model in tests.items():
        path = output / f'invalid-{label}.json'
        write(path, model)
        errors[label] = run(core, 'validate', path, expected=1)
    errors['altered_graph_sha256'] = run(core, 'validate', output / 'invalid-missing_anchor.json',
                                        '--graph-sha256', originals[graph], expected=1)
    if any(digest(path) != checksum for path, checksum in originals.items()):
        raise RuntimeError('A qualification input was modified')
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('core', 'native', 'transfer-report', 'bench-native', 'out', 't0-validator'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    output = args.out
    output.mkdir(parents=True)
    overlay = Path('docs/electromechanical_v3/cartographe.json')
    oracle = Path('docs/verification/v3/a/impact_oracle.json')
    bench_oracle = Path('electromechanical_graph/tests/bench_oracle.json')
    bench_overlay = Path('electromechanical_graph/tests/bench_authorities.json')
    args.core = args.core.resolve()
    context = start_evidence(output, {'core': args.core, 'native': args.native, 'transfer': args.transfer_report,
                                      'bench_native': args.bench_native, 'overlay': overlay, 'bench_overlay': bench_overlay,
                                      'oracle': oracle, 'bench_oracle': bench_oracle})
    original = read(args.native)
    transferred = read(args.transfer_report)
    if original['transfer']['native_report_sha256'] != digest(args.transfer_report):
        raise RuntimeError('The transferred report differs from the independent receipt')
    for key in ('source_prefix', 'source_immutability', 'entry_repository', 'transfer'):
        transferred[key] = original[key]
    transferred_path = output / 'transfer-input.json'
    write(transferred_path, transferred)
    graphs = {}
    for label, source, authority, l2 in (
        ('cartographe', args.native, overlay, ['--cartographe-l2']),
        ('transfer', transferred_path, overlay, ['--cartographe-l2']),
        ('bench', args.bench_native, bench_overlay, []),
    ):
        path = output / f'{label}-graph.json'
        run(args.core, 'import', '.', source, authority, *l2, '--native-sha256', digest(source), '--output', path)
        run(args.core, 'validate', path, '--root', '.', '--graph-sha256', digest(path))
        graphs[label] = path
    if digest(graphs['cartographe']) != digest(graphs['transfer']):
        raise RuntimeError('The transferred graph is not byte-identical')
    results = {label: run_cases(args.core, graph, bench_oracle if label == 'bench' else oracle, output, label)
               for label, graph in graphs.items()}
    errors = negatives(args.core, args.native, graphs['cartographe'], overlay, output)
    write(output / 'checks.json', {'schema': 'v3.reference-checks/1', 'status': 'PASS',
                                  'oracle_sha256': digest(oracle), 'bench_oracle_sha256': digest(bench_oracle),
                                  'graph_sha256': {label: digest(path) for label, path in graphs.items()},
                                  'cases': results, 'rejected': errors})
    finalize_evidence(output, context, results, graphs, args.t0_validator.resolve())


if __name__ == '__main__':
    main()
