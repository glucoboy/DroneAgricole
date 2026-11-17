"""Compare a finished XLink replay with the frozen L2 and native reference files."""

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path


def load(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def verify(workspace, run, graph_path, closure_path):
    report = load(run / 'campaign.json')
    configuration = load(workspace / 'validation_engine/fixtures/xlink_cartographe.json')
    inventory = load(run / 'inventory.result.json')
    before = load(closure_path)
    graph = load(graph_path)
    electrical = report['electrical']
    closure = report['closure']
    geometry = report['geometry']

    assert report['finalized'] and report['verdict'] == 'V21_XLINK_CONDITIONAL'
    assert report['criteria'] == configuration['criteria']
    assert report['pins']['electrical'] == digest(graph_path)
    assert all(digest(workspace / path) == value for path, value in graph['source_sha256'].items())
    assert len(before) == 137 and closure['source_sha256'] == before
    source = workspace / configuration['source']
    assert all(digest(source / path) == value for path, value in before.items())
    saved = closure['saved_sha256']
    assert saved.keys() == before.keys()
    assert all(digest(run.parent / 'copy' / path) == value for path, value in saved.items())
    assert closure['integrity']['sources_unchanged'] and closure['reopened']
    assert closure['reopened_worker'] == inventory['worker_id'] != closure['saved_worker']
    assert closure['reopened_pid'] == inventory['pid'] != closure['saved_pid']

    lines = {line['id']: line for line in graph['lines']}
    routed = {key: line for key, line in lines.items() if line['path']}
    report_lines = electrical['lines']
    off_axis = {key: row for key, row in report_lines.items() if row['status'] == 'NOT_RUN'}
    assert len(lines) == 71 and len(routed) == 50 and len(off_axis) == 21
    assert report_lines.keys() == lines.keys()
    assert set(lines) - set(routed) == set(off_axis)
    assert set(electrical['interfaces']) == {line + side for line in lines for side in ('/A', '/B')}
    assert len(electrical['interfaces']) == 142
    for key, row in report_lines.items():
        line = lines[key]
        assert row['scope'] == line['scope'] and row['class'] == line['class']
        assert row['path'] == line['path']
        if key in off_axis:
            assert row['reason'] == line['scope_reason'] and row['path'] == []

    joins = electrical['axes']
    reverse = electrical['reverse']['axes']
    occurrences = inventory['occurrences']

    def check_resolution(resolution):
        native = occurrences[resolution['occurrence']]
        assert native['status'] == 'PASS' and native['visible']
        assert all(native[key] == value for key, value in resolution['observed'].items())
        assert len(native['matrix']) == 16 and all(map(math.isfinite, native['matrix']))
        assert native['document_sha256'] == saved[native['object'].split('#')[0]]
        assert native['definition_sha256'] == saved[native['definition'].split('#')[0]]

    assert len(joins) == len(reverse) == 53 and joins.keys() == graph['axes'].keys()
    associations = Counter(segment['sense'] for line in routed.values() for segment in line['path'])
    assert associations.total() == 56
    for axis, join in joins.items():
        assert join['status'] == 'PASS'
        expected_lines = {key for key, line in routed.items()
                          if any(segment['route_id'] == axis for segment in line['path'])}
        assert set(join['line_ids']) == expected_lines == set(graph['axes'][axis]['line_ids'])
        component = join['occurrence']['occurrence']
        cable = join['cable']['occurrence']
        assert reverse[component] == {'axis': axis, 'line_ids': join['line_ids']}
        assert cable.startswith(component + '/') and occurrences[cable]['terminal_shape']
        check_resolution(join['occurrence'])
        check_resolution(join['cable'])

    equipment_index = defaultdict(set)
    for key, row in electrical['interfaces'].items():
        source_port = graph['interfaces'][key]
        assert row['port']['port_record_id'] == source_port['port_record_id']
        assert row['port']['functional_port'] == source_port['functional_port']
        assert row['equipment_id'] == source_port['equipment_id']
        equipment = row['equipment']
        if equipment['status'] == 'PASS':
            check_resolution(equipment)
            equipment_index[equipment['occurrence']].add(key)
        assert row['contacts'] == [] and not row['contact_coverage_known']
    assert equipment_index == {key: set(value) for key, value in electrical['reverse']['equipment'].items()}
    assert electrical['status'] == 'INCONCLUSIVE' and electrical['summary']['contacts_bound'] == 0
    assert electrical['reverse']['contacts'] == {} and electrical['unmatched_native_routes'] == []

    assert geometry['solid_occurrences'] == 565 and geometry['route_occurrences'] == 53
    assert geometry['expected_pairs'] == 28514 and geometry['possible_brep_pairs'] == 1609
    assert geometry['pairs_screened_out'] == 26905 and geometry['exclusions']
    assert geometry['pairs_examined'] > 0 and geometry['pairs_not_run'] > 0
    measured_pids = set()
    measured = 0
    not_run = 0
    for row in geometry['checks']:
        evidence = row['native_evidence']
        if evidence:
            assert evidence['cache_key'] == closure['cache_key'] and evidence['task'] == row['task']
            measured_pids.add(evidence['worker_pid'])
        if row['task']['kind'] == 'pair' and row['status'] == 'NOT_RUN':
            assert evidence is None
            not_run += 1
        if row['task']['kind'] == 'pair' and evidence:
            observation = evidence['observation']
            measured += int('intersection_mm3' in observation and 'clearance_mm' in observation)
            assert row['status'] != 'PASS'  # The frozen prototype policy treats this as screening.
    assert measured == geometry['pairs_examined'] and not_run == geometry['pairs_not_run']
    assert not measured_pids & {closure['saved_pid'], closure['reopened_pid']}
    assert Counter(row['status'] for row in geometry['checks']) == Counter(geometry['counts'])
    assert geometry['pairs_attempted'] + not_run == geometry['possible_brep_pairs']
    assert geometry['pairs_attempted'] - measured == geometry['pairs_unmeasurable']
    assert report['open_checks'] == configuration['open_checks']
    open_checks = {row['id']: row for row in report['open_checks']}
    assert sum(row['status'] == 'NOT_RUN' for row in open_checks.values()) == 4
    assert open_checks['geometry-approximations']['status'] == 'INCONCLUSIVE'
    for path in open_checks['geometry-approximations']['sources']:
        assert (workspace / path).is_file()
    print(json.dumps({
        'native_files': len(before), 'off_axis_categories': Counter(row['scope'] for row in off_axis.values()),
        'associations_in_l2_by_sense': associations, 'occurrences': len(occurrences),
        'equipment_bindings': sum(map(len, equipment_index.values())),
        'measured_pids': sorted(measured_pids), 'pairs_examined': measured, 'pairs_not_run': not_run,
        'exclusions_by_reason': Counter(geometry['exclusions'].values()), 'open_checks': open_checks,
    }, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run', type=Path)
    parser.add_argument('graph', type=Path)
    parser.add_argument('closure', type=Path)
    args = parser.parse_args()
    verify(Path(__file__).resolve().parents[2], args.run, args.graph, args.closure)
