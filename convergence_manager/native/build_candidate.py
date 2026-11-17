"""Adapt a complete static L5 construction plan to the existing FreeCAD builder."""

import argparse
import hashlib
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from electromechanical_engine.contracts import (
    decode, number, path_points, require, validate_requirements, validate_system, write,
)
from electromechanical_engine.freecad import FreeCADAdapter, FreeCADError, PROJECT, guard
from electromechanical_engine.metrics import measure
from electromechanical_engine.search import _connections
from electromechanical_engine.validation import validate


def build(plan_path, output, interpreter, timeout):
    source = plan_path.read_bytes()
    plan = decode(plan_path.name, source)
    system, requirements, candidate = (plan[key] for key in ('system', 'requirements', 'candidate'))
    validate_system(system)
    validate_requirements(system, requirements)
    require(isinstance(candidate, dict) and isinstance(candidate.get('routes'), dict),
            'Plan sans routes natives.')
    require(set(candidate['routes']) == set(requirements['links']),
            'Le plan doit couvrir toutes les liaisons gelées.')
    for key, route in candidate['routes'].items():
        require(isinstance(route, dict) and route.get('link', key) == key, f'Route invalide : {key}')
        path_points(route.get('points_mm'), key)
        number(route.get('bend_radius_mm'), f'{key}.bend_radius_mm', 0)

    # The static bench has fixed port identities. Proposed electrical changes
    # are admitted upstream and may supply a separate declared connection table.
    candidate.setdefault('connections', _connections(system))
    observed = FreeCADAdapter(interpreter, timeout).build(plan, output)
    report = validate(system, requirements, candidate, observed)
    findings = []
    for entry in report['findings']:
        subject = entry['object']
        findings.append({'code': entry['code'], 'subjects': subject if isinstance(subject, list) else [subject],
                         'state': entry['evidence'].get('state', 'S-NOMINAL'),
                         'status': entry['status'].upper(), 'reason': entry['reason'],
                         'evidence': entry['evidence']})
    status = {'VALIDE_GEOMETRIQUEMENT': 'PASS', 'NON_CONFORME': 'FAIL'}.get(report['status'], 'CONDITIONAL')
    metrics = measure(system, requirements, observed, candidate)['values']
    receipt = {key: observed[key] for key in ('native_sha256', 'native_inputs_sha256', 'reopened',
               'save_performed', 'freecad', 'python', 'cables', 'saved_process', 'saved_worker_id', 'pid', 'worker_id')}
    receipt.update(schema_version=1, plan_sha256=hashlib.sha256(source).hexdigest(),
                   status=status, findings=findings, validation_physique=report['validation_physique'],
                   metrics={key: metrics[key] for key in ('total_length_mm', 'max_cable_z_mm')})
    pending = output / 'build_receipt.pending.json'
    write(pending, receipt)
    pending.rename(output / 'build_receipt.json')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--freecad-python', type=Path, required=True)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--timeout', type=int, default=30)
    args = parser.parse_args()
    try:
        plan_path, output = (guard.inside(PROJECT, path) for path in (args.plan, args.output))
        require(1 <= args.timeout <= 300, 'Délai par processus hors bornes (1–300 s).')
        require(output.parent.is_dir() and not output.exists(), f'Dossier de construction neuf requis : {output}')
        build(plan_path, output, args.freecad_python, args.timeout)
    except (FreeCADError, OSError, ValueError, KeyError, TypeError) as error:
        print(f'Construction FreeCAD non finalisée : {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
