"""Comparaison reproductible de résultats historiques compatibles."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import math
from typing import Any, Mapping, Sequence


class ComparisonError(ValueError):
    """Erreur publique liée à une demande de comparaison."""


PALETTE = ("#53d8d2", "#d98cff", "#71e391", "#ff7aa8")


def _text(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _scalar(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _run_label(detail: Mapping[str, Any]) -> str:
    summary = detail["summary"]
    return f"{summary['variant_id']} · {summary['run_id']}"


def _metric_map(detail: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    metrics = detail.get("metrics", {}).get("summary", [])
    return {
        str(metric["metric_id"]): metric
        for metric in metrics
        if isinstance(metric, Mapping) and metric.get("metric_id")
    }


def _best_result_ids(values: Sequence[tuple[str, Any]], direction: str) -> list[str]:
    numeric = [
        (result_id, float(value))
        for result_id, value in values
        if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))
    ]
    if not numeric or direction not in {"lower", "higher"}:
        return []
    best = min(value for _, value in numeric) if direction == "lower" else max(value for _, value in numeric)
    tolerance = max(abs(best), 1.0) * 1e-12
    return [result_id for result_id, value in numeric if abs(value - best) <= tolerance]


class ComparisonService:
    """Construit matrices, superpositions et rapports à partir du dépôt T0.3."""

    def __init__(self, repository: Any) -> None:
        self.repository = repository

    @staticmethod
    def validate_result_ids(result_ids: Any) -> list[str]:
        if not isinstance(result_ids, list):
            raise ComparisonError("result_ids doit être une liste.")
        values = [_text(value) for value in result_ids]
        if any(not value for value in values):
            raise ComparisonError("Chaque identifiant de résultat doit être renseigné.")
        if len(values) < 2 or len(values) > 4:
            raise ComparisonError("Sélectionnez entre 2 et 4 résultats.")
        if len(set(values)) != len(values):
            raise ComparisonError("Un résultat ne peut être sélectionné qu’une seule fois.")
        return values

    def _details(self, result_ids: Any) -> list[Mapping[str, Any]]:
        return [self.repository.detail(value) for value in self.validate_result_ids(result_ids)]

    @staticmethod
    def _compatibility(details: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
        summaries = [detail["summary"] for detail in details]
        reasons: list[str] = []

        def require_same(field: str, label: str, *, required: bool = True) -> None:
            values = {_text(summary.get(field)) for summary in summaries}
            if required and "" in values:
                reasons.append(f"{label} absent sur au moins un résultat.")
            if len(values) > 1:
                reasons.append(f"{label} diffère entre les résultats.")

        require_same("domain", "Domaine")
        require_same("simulation_id", "Simulation")
        require_same("comparison_group", "Groupe de comparaison")
        if any(summary.get("state") != "completed" for summary in summaries):
            reasons.append("Tous les résultats doivent être terminés avec le statut completed.")

        domain = summaries[0].get("domain")
        if domain == "localization":
            require_same("dataset_id", "Dataset")
            require_same("sequence_id", "Séquence")
        elif domain == "flight_simulation":
            require_same("scenario_id", "Scénario")
        else:
            reasons.append(f"Le domaine {_text(domain) or 'inconnu'} n’est pas comparable par T0.4.")

        metric_maps = [_metric_map(detail) for detail in details]
        common_metric_ids = set(metric_maps[0]) if metric_maps else set()
        for metrics in metric_maps[1:]:
            common_metric_ids &= set(metrics)
        consistent_common = []
        for metric_id in sorted(common_metric_ids):
            signatures = {
                (_text(metrics[metric_id].get("unit")), _text(metrics[metric_id].get("direction")))
                for metrics in metric_maps
            }
            if len(signatures) == 1:
                consistent_common.append(metric_id)
        if not consistent_common:
            reasons.append("Aucune métrique commune avec unité et sens de comparaison cohérents.")

        overlay_missing = [summary["result_id"] for summary in summaries if not summary.get("replay_available")]
        return {
            "compatible": not reasons,
            "reasons": reasons,
            "comparison_group": summaries[0].get("comparison_group"),
            "domain": domain,
            "dataset_id": summaries[0].get("dataset_id"),
            "sequence_id": summaries[0].get("sequence_id"),
            "scenario_id": summaries[0].get("scenario_id"),
            "common_metric_ids": consistent_common,
            "overlay_available": not overlay_missing,
            "overlay_missing_result_ids": overlay_missing,
        }

    @staticmethod
    def _runs(details: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
        runs = []
        for index, detail in enumerate(details):
            summary = detail["summary"]
            runs.append({
                "result_id": summary["result_id"],
                "run_id": summary["run_id"],
                "label": _run_label(detail),
                "color": PALETTE[index],
                "simulation_id": summary["simulation_id"],
                "variant_id": summary["variant_id"],
                "runner_id": summary["runner_id"],
                "domain": summary["domain"],
                "state": summary["state"],
                "created_at_utc": summary.get("created_at_utc"),
                "dataset_id": summary.get("dataset_id"),
                "sequence_id": summary.get("sequence_id"),
                "scenario_id": summary.get("scenario_id"),
                "source_kind": summary.get("source_kind"),
                "relative_directory": summary.get("relative_directory"),
            })
        return runs

    @staticmethod
    def _metrics(details: Sequence[Mapping[str, Any]], runs: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
        maps = [_metric_map(detail) for detail in details]
        metric_ids = sorted(set().union(*(set(metrics) for metrics in maps)))
        rows: list[dict[str, Any]] = []
        for metric_id in metric_ids:
            present = [metrics.get(metric_id) for metrics in maps]
            definitions = [metric for metric in present if metric is not None]
            signatures = {(_text(metric.get("unit")), _text(metric.get("direction"))) for metric in definitions}
            comparable = len(definitions) == len(details) and len(signatures) == 1
            exemplar = definitions[0]
            values = [
                {"result_id": run["result_id"], "value": metric.get("value") if metric else None, "status": metric.get("status") if metric else "unavailable"}
                for run, metric in zip(runs, present)
            ]
            direction = _text(exemplar.get("direction"))
            rows.append({
                "metric_id": metric_id,
                "label": exemplar.get("label") or metric_id,
                "unit": exemplar.get("unit") or "",
                "direction": direction,
                "comparable": comparable,
                "best_result_ids": _best_result_ids(
                    [(value["result_id"], value["value"]) for value in values], direction
                ) if comparable else [],
                "values": values,
            })
        return rows

    @staticmethod
    def _parameters(details: Sequence[Mapping[str, Any]], runs: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
        parameter_maps = [detail.get("manifest", {}).get("parameters", {}) for detail in details]
        names = sorted(set().union(*(set(values) for values in parameter_maps if isinstance(values, Mapping))))
        rows = []
        for name in names:
            values = [
                {"result_id": run["result_id"], "value": _scalar(parameters.get(name)) if isinstance(parameters, Mapping) else None}
                for run, parameters in zip(runs, parameter_maps)
            ]
            serialized = {json.dumps(value["value"], ensure_ascii=False, sort_keys=True) for value in values}
            rows.append({"parameter_id": name, "same_for_all": len(serialized) == 1, "values": values})
        return rows

    @staticmethod
    def _versions(details: Sequence[Mapping[str, Any]], runs: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
        rows = []
        for detail, run in zip(details, runs):
            manifest = detail.get("manifest", {})
            software = manifest.get("software", {}) if isinstance(manifest.get("software"), Mapping) else {}
            process = software.get("mapping_process", {}) if isinstance(software.get("mapping_process"), Mapping) else {}
            compatibility = manifest.get("compatibility", {}) if isinstance(manifest.get("compatibility"), Mapping) else {}
            rows.append({
                "result_id": run["result_id"],
                "source_kind": run["source_kind"],
                "runner_id": run["runner_id"],
                "algorithm": software.get("legacy_algorithm") or run["variant_id"],
                "result_contract_version": compatibility.get("result_contract_version"),
                "process_schema_version": process.get("schema_version"),
                "process_exit_code": process.get("exit_code"),
            })
        return rows

    def preview(self, result_ids: Any) -> dict[str, Any]:
        details = self._details(result_ids)
        runs = self._runs(details)
        return {
            "schema": "drone_agricole.result_comparison.v1",
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "compatibility": self._compatibility(details),
            "runs": runs,
            "metrics": self._metrics(details, runs),
            "parameters": self._parameters(details, runs),
            "versions": self._versions(details, runs),
        }

    def replay(self, result_ids: Any) -> dict[str, Any]:
        preview = self.preview(result_ids)
        compatibility = preview["compatibility"]
        if not compatibility["compatible"]:
            raise ComparisonError("Comparaison incompatible : " + " ".join(compatibility["reasons"]))
        if not compatibility["overlay_available"]:
            raise ComparisonError("Une ou plusieurs trajectoires ne sont pas rechargeables.")
        ids = [run["result_id"] for run in preview["runs"]]
        # Les rosbags complets sont lus séquentiellement : trois lecteurs en
        # parallèle dépassent la mémoire allouée au conteneur Docker Desktop.
        replays = [self.repository.replay(result_id) for result_id in ids]
        domain = compatibility["domain"]
        comparison_paths = []
        comparison_curves = []
        truth: list[list[float]] = []
        for run, replay in zip(preview["runs"], replays):
            scene = replay.get("scene", {})
            points = scene.get("estimate", []) if domain == "localization" else scene.get("px4_path", [])
            comparison_paths.append({
                "result_id": run["result_id"],
                "label": run["label"],
                "color": run["color"],
                "points": points,
            })
            if domain == "localization" and not truth:
                truth = scene.get("truth", [])
            curve = replay.get("curves", [None])[0] if replay.get("curves") else None
            if curve:
                comparison_curves.append({
                    "result_id": run["result_id"],
                    "label": run["label"],
                    "color": run["color"],
                    "curve_id": curve.get("curve_id"),
                    "unit": curve.get("unit", ""),
                    "values": curve.get("values", []),
                })
        return {
            "schema": "drone_agricole.comparison_replay.v1",
            "comparison": preview,
            "scene": {
                "cloud": [],
                "estimate": [],
                "truth": truth,
                "px4_path": [],
                "px4_pose": None,
                "comparison_paths": comparison_paths,
            },
            "curves": comparison_curves,
            "notes": [
                "Trajectoires relues depuis les artefacts enregistrés, sans relancer les algorithmes.",
                "Chaque trajectoire est alignée selon la règle de son rejeu historique.",
            ],
        }

    def report(self, result_ids: Any) -> str:
        comparison = self.preview(result_ids)
        return render_markdown_report(comparison)


def _markdown_value(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        rendered = f"{value:.6g}"
    else:
        rendered = str(value)
    return rendered.replace("|", "\\|").replace("\n", " ")


def _matrix_table(headers: Sequence[str], rows: Sequence[Sequence[Any]]) -> list[str]:
    escaped_headers = [_markdown_value(value) for value in headers]
    lines = ["| " + " | ".join(escaped_headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    lines.extend("| " + " | ".join(_markdown_value(value) for value in row) + " |" for row in rows)
    return lines


def render_markdown_report(comparison: Mapping[str, Any]) -> str:
    """Produit un rapport Markdown autonome et versionnable."""

    compatibility = comparison["compatibility"]
    runs = comparison["runs"]
    lines = [
        "# Rapport de comparaison T0.4",
        "",
        f"Généré le : {comparison['generated_at_utc']}",
        f"Compatibilité : **{'validée' if compatibility['compatible'] else 'refusée'}**",
        "",
    ]
    if compatibility["reasons"]:
        lines.extend(["## Motifs", "", *[f"- {reason}" for reason in compatibility["reasons"]], ""])
    lines.extend(["## Exécutions", ""])
    lines.extend(_matrix_table(
        ["Algorithme / scénario", "Run", "État", "Dataset", "Séquence", "Source"],
        [[run["variant_id"], run["run_id"], run["state"], run["dataset_id"], run["sequence_id"], run["source_kind"]] for run in runs],
    ))
    lines.extend(["", "## Métriques", ""])
    metric_rows = []
    for metric in comparison["metrics"]:
        values = []
        for value in metric["values"]:
            rendered = _markdown_value(value["value"])
            if value["result_id"] in metric["best_result_ids"]:
                rendered += " ★"
            values.append(rendered)
        metric_rows.append([metric["label"], metric["unit"], *values])
    lines.extend(_matrix_table(["Métrique", "Unité", *[run["label"] for run in runs]], metric_rows))
    lines.extend(["", "★ meilleure valeur selon le sens déclaré par la métrique.", "", "## Paramètres", ""])
    parameter_rows = []
    for parameter in comparison["parameters"]:
        values = [value["value"] for value in parameter["values"]]
        parameter_rows.append([parameter["parameter_id"], "oui" if parameter["same_for_all"] else "non", *values])
    lines.extend(_matrix_table(["Paramètre", "Identique", *[run["label"] for run in runs]], parameter_rows))
    lines.extend(["", "## Versions et sources", ""])
    version_by_id = {value["result_id"]: value for value in comparison["versions"]}
    lines.extend(_matrix_table(
        ["Exécution", "Runner", "Algorithme", "Source", "Contrat", "Schéma processus", "Code sortie"],
        [[run["label"], version_by_id[run["result_id"]]["runner_id"], version_by_id[run["result_id"]]["algorithm"], version_by_id[run["result_id"]]["source_kind"], version_by_id[run["result_id"]]["result_contract_version"], version_by_id[run["result_id"]]["process_schema_version"], version_by_id[run["result_id"]]["process_exit_code"]] for run in runs],
    ))
    lines.extend([
        "",
        "## Limites d’interprétation",
        "",
        "- Ce rapport compare les artefacts archivés ; il ne relance aucune simulation.",
        "- Une étoile désigne le meilleur résultat mesuré, pas un choix d’architecture définitif.",
        "- Toute valeur ou version absente reste explicitement indiquée par « — ».",
        "",
    ])
    return "\n".join(lines)
