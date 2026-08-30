#!/usr/bin/env python3
"""Valide le registre T0.1 et normalise des résultats historiques à la volée."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _workspace_from_script() -> Path:
    return Path(__file__).resolve().parents[2]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=_workspace_from_script())
    parser.add_argument("--result", action="append", type=Path, default=[], help="Répertoire de résultat historique à valider (répétable).")
    parser.add_argument("--json", action="store_true", help="Produit un rapport JSON lisible par une machine.")
    args = parser.parse_args()

    workspace = args.workspace.resolve()
    if str(workspace) not in sys.path:
        sys.path.insert(0, str(workspace))

    from software.visualization.contracts import ContractError, DefinitionRegistry, load_schema_documents
    from software.visualization.result_adapters import normalize_result_directory

    report: dict[str, object] = {"workspace": str(workspace), "valid": False, "errors": []}
    try:
        schemas = load_schema_documents(workspace / "configs" / "visualization" / "schemas")
        registry = DefinitionRegistry.load(
            workspace / "configs" / "visualization" / "datasets",
            workspace / "configs" / "visualization" / "simulations",
        )
        compatibility = {
            simulation_id: {
                variant["variant_id"]: registry.compatible_dataset_sequences(simulation_id, variant["variant_id"])
                for variant in simulation["variants"]
            }
            for simulation_id, simulation in registry.simulations.items()
        }
        normalized_results = []
        for result_path in args.result:
            result = normalize_result_directory(result_path)
            normalized_results.append(
                {
                    "path": str(result.source_directory),
                    "source_kind": result.source_kind,
                    "run_id": result.manifest["run_id"],
                    "simulation_id": result.manifest["simulation_id"],
                    "variant_id": result.manifest["variant_id"],
                    "state": result.manifest["state"],
                    "metric_count": len(result.metrics["summary"]),
                    "artifact_count": len(result.artifacts["items"]),
                    "event_count": len(result.events),
                }
            )
        report.update(
            {
                "valid": True,
                "schema_documents": len(schemas),
                "datasets": sorted(registry.datasets),
                "simulations": sorted(registry.simulations),
                "compatibility": compatibility,
                "normalized_results": normalized_results,
            }
        )
    except (ContractError, OSError, ValueError) as exc:
        report["errors"] = [str(exc)]

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    elif report["valid"]:
        print(f"T0.1 valide : {report['schema_documents']} schémas, {len(report['datasets'])} dataset(s), {len(report['simulations'])} simulation(s).")
        for result in report["normalized_results"]:
            print(
                f"- {result['source_kind']} · {result['variant_id']} · {result['state']} · "
                f"{result['metric_count']} métriques · {result['artifact_count']} artefacts · {result['event_count']} événements"
            )
    else:
        print(f"T0.1 invalide : {report['errors'][0]}", file=sys.stderr)
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
