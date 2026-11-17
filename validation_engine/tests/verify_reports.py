"""Valide les projections L0 et leurs liens dans une campagne L4 finalisée."""
import argparse
import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def checked_file(root, relative, digest):
    path = (root / relative).resolve(strict=True)
    if not path.is_relative_to(root) or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
        raise ValueError(f'Preuve hors périmètre ou modifiée : {relative}')
    return path


def verify(root, schema_path):
    schema = load(schema_path)
    Draft202012Validator.check_schema(schema)
    validators = {name: Draft202012Validator({'$defs': schema['$defs'], '$ref': f'#/$defs/{name}'},
                                            format_checker=FormatChecker())
                  for name in ('ValidationReport', 'ValidationFinding', 'TechnicalEvidence')}
    campaign = load(root / 'campaign.json')
    manifest = load(root / 't0_run_manifest.json')
    if not campaign['finalized'] or manifest['metadata']['verdict'] != campaign['verdict']:
        raise ValueError('Campagne et état terminal T0 divergents')
    matrix = []
    total_findings = 0
    for case, summary in campaign['cases'].items():
        report = load(checked_file(root, summary['report'], summary['sha256']))
        l0 = report['validation_report']
        validators['ValidationReport'].validate(l0)
        if not l0['finalized'] or report['case_id'] != case or l0['verdict'] != summary['verdict']:
            raise ValueError(f'Rapport incohérent pour {case}')
        evidence_ids = []
        for evidence in report['technical_evidence']:
            validators['TechnicalEvidence'].validate(evidence)
            checked_file(root, evidence['artifact_path'], evidence['sha256'])
            evidence_ids.append(evidence['id'])
        if evidence_ids != l0['evidence_ids'] or (l0['native_evidence_id'] is not None and
                                                   l0['native_evidence_id'] not in evidence_ids):
            raise ValueError(f'Liste de preuves incohérente pour {case}')
        findings = report['validation_findings']
        if [entry['id'] for entry in findings] != l0['finding_ids']:
            raise ValueError(f'Couverture incohérente pour {case}')
        for detail, finding, expected in zip(report['findings'], findings, l0['expected_checks'], strict=True):
            validators['ValidationFinding'].validate(finding)
            if detail['l0'] != finding or detail['finding_id'] != finding['id'] or not set(finding['evidence_ids']) <= set(evidence_ids):
                raise ValueError(f'Constat ou preuve incohérent pour {case}')
            if any(expected[key] != finding[key] for key in ('requirement_id', 'requirement_revision', 'method',
                                                             'subject_ids', 'state_id')):
                raise ValueError(f'Périmètre du contrôle divergent pour {case}')
            matrix.append({key: finding[key] for key in ('requirement_id', 'evidence_ids')} |
                          {'finding_id': finding['id']})
        total_findings += len(findings)
    if matrix != load(root / campaign['traceability'])['matrix']:
        raise ValueError('La matrice exigence, preuve et constat diverge des rapports')
    print(f"{len(campaign['cases'])} rapports L0 et {total_findings} constats validés")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('campaign', type=Path)
    parser.add_argument('--schema', type=Path, default=Path('docs/electromechanical_v2/DATA_CONTRACTS.schema.json'))
    options = parser.parse_args()
    verify(options.campaign.resolve(strict=True), options.schema)
