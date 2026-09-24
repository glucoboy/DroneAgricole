#include "drone_agricole/core/ComparisonService.hpp"

#include "drone_agricole/core/JsonUtils.hpp"

#include <QJsonDocument>
#include <QSet>

#include <algorithm>
#include <cmath>
#include <limits>

namespace drone_agricole::core {
namespace {

const QStringList palette{
    QStringLiteral("#53d8d2"),
    QStringLiteral("#d98cff"),
    QStringLiteral("#71e391"),
    QStringLiteral("#ff7aa8"),
};

QHash<QString, QJsonObject> metricMap(const ResultDetail& detail) {
  QHash<QString, QJsonObject> result;
  for (const auto& value : detail.metrics.value(QStringLiteral("summary")).toArray()) {
    const auto metric = value.toObject();
    const auto id = metric.value(QStringLiteral("metric_id")).toString();
    if (!id.isEmpty()) {
      result.insert(id, metric);
    }
  }
  return result;
}

QString runLabel(const ResultSummary& summary) {
  return QStringLiteral("%1 · %2").arg(summary.variantId, summary.runId);
}

QSet<QString> jsonKeys(const QJsonObject& object) {
  QSet<QString> result;
  for (auto iterator = object.constBegin(); iterator != object.constEnd(); ++iterator) {
    result.insert(iterator.key());
  }
  return result;
}

QString jsonCanonical(const QJsonValue& value) {
  if (value.isObject()) {
    return QString::fromUtf8(QJsonDocument(value.toObject()).toJson(QJsonDocument::Compact));
  }
  if (value.isArray()) {
    return QString::fromUtf8(QJsonDocument(value.toArray()).toJson(QJsonDocument::Compact));
  }
  return scalarText(value);
}

QJsonArray bestResultIds(const QJsonArray& values, const QString& direction) {
  if (direction != QStringLiteral("lower") && direction != QStringLiteral("higher")) {
    return {};
  }
  QList<std::pair<QString, double>> numeric;
  for (const auto& value : values) {
    const auto item = value.toObject();
    const auto metricValue = item.value(QStringLiteral("value"));
    if (!metricValue.isDouble() || !std::isfinite(metricValue.toDouble())) {
      continue;
    }
    numeric.append({item.value(QStringLiteral("result_id")).toString(), metricValue.toDouble()});
  }
  if (numeric.isEmpty()) {
    return {};
  }
  auto best = numeric.front().second;
  for (const auto& value : numeric) {
    best = direction == QStringLiteral("lower") ? std::min(best, value.second) : std::max(best, value.second);
  }
  const auto tolerance = std::max(std::abs(best), 1.0) * 1e-12;
  QJsonArray result;
  for (const auto& value : numeric) {
    if (std::abs(value.second - best) <= tolerance) {
      result.append(value.first);
    }
  }
  return result;
}

QString markdownValue(const QJsonValue& value) {
  if (value.isNull() || value.isUndefined()) {
    return QStringLiteral("—");
  }
  auto rendered = scalarText(value);
  rendered.replace(QLatin1Char('|'), QStringLiteral("\\|"));
  rendered.replace(QLatin1Char('\n'), QLatin1Char(' '));
  return rendered;
}

QStringList matrixTable(const QStringList& headers, const QList<QJsonArray>& rows) {
  QStringList lines;
  lines.append(QStringLiteral("| %1 |").arg(headers.join(QStringLiteral(" | "))));
  QStringList separators;
  separators.fill(QStringLiteral("---"), headers.size());
  lines.append(QStringLiteral("| %1 |").arg(separators.join(QStringLiteral(" | "))));
  for (const auto& row : rows) {
    QStringList values;
    for (const auto& value : row) {
      values.append(markdownValue(value));
    }
    lines.append(QStringLiteral("| %1 |").arg(values.join(QStringLiteral(" | "))));
  }
  return lines;
}

}  // namespace

ComparisonService::ComparisonService(ResultRepository& repository) : repository_(repository) {}

void ComparisonService::validateResultIds(const QStringList& resultIds) {
  if (resultIds.size() < 2 || resultIds.size() > 4) {
    throw ContractError(QStringLiteral("Sélectionnez entre 2 et 4 résultats"));
  }
  QSet<QString> unique;
  for (const auto& id : resultIds) {
    if (id.trimmed().isEmpty()) {
      throw ContractError(QStringLiteral("Chaque identifiant de résultat doit être renseigné"));
    }
    unique.insert(id);
  }
  if (unique.size() != resultIds.size()) {
    throw ContractError(QStringLiteral("Un résultat ne peut être sélectionné qu'une seule fois"));
  }
}

QJsonObject ComparisonService::preview(const QStringList& resultIds) const {
  validateResultIds(resultIds);
  QList<ResultDetail> details;
  details.reserve(resultIds.size());
  for (const auto& resultId : resultIds) {
    details.append(repository_.detail(resultId));
  }

  QJsonArray reasons;
  const auto requireSame = [&](auto getter, const QString& label, const bool required = true) {
    QSet<QString> values;
    for (const auto& detail : details) {
      values.insert(getter(detail.summary));
    }
    if (required && values.contains(QString{})) {
      reasons.append(QStringLiteral("%1 absent sur au moins un résultat.").arg(label));
    }
    if (values.size() > 1) {
      reasons.append(QStringLiteral("%1 diffère entre les résultats.").arg(label));
    }
  };
  requireSame([](const auto& value) { return value.domain; }, QStringLiteral("Domaine"));
  requireSame([](const auto& value) { return value.simulationId; }, QStringLiteral("Simulation"));
  requireSame([](const auto& value) { return value.comparisonGroup; }, QStringLiteral("Groupe de comparaison"));
  if (std::any_of(details.cbegin(), details.cend(), [](const auto& value) {
        return value.summary.state != QStringLiteral("completed");
      })) {
    reasons.append(QStringLiteral("Tous les résultats doivent être terminés avec le statut completed."));
  }

  const auto domain = details.front().summary.domain;
  if (domain == QStringLiteral("localization")) {
    requireSame([](const auto& value) { return value.datasetId; }, QStringLiteral("Dataset"));
    requireSame([](const auto& value) { return value.sequenceId; }, QStringLiteral("Séquence"));
  } else if (domain == QStringLiteral("flight_simulation")) {
    requireSame([](const auto& value) { return value.scenarioId; }, QStringLiteral("Scénario"));
  } else {
    reasons.append(QStringLiteral("Le domaine %1 n'est pas comparable.").arg(domain.isEmpty() ? QStringLiteral("inconnu") : domain));
  }

  QList<QHash<QString, QJsonObject>> metricMaps;
  for (const auto& detail : details) {
    metricMaps.append(metricMap(detail));
  }
  QSet<QString> commonIds = QSet<QString>(metricMaps.front().keyBegin(), metricMaps.front().keyEnd());
  for (qsizetype index = 1; index < metricMaps.size(); ++index) {
    commonIds.intersect(QSet<QString>(metricMaps.at(index).keyBegin(), metricMaps.at(index).keyEnd()));
  }
  QStringList consistentCommon;
  auto commonList = commonIds.values();
  std::sort(commonList.begin(), commonList.end());
  for (const auto& metricId : commonList) {
    QSet<QString> signatures;
    for (const auto& values : metricMaps) {
      const auto metric = values.value(metricId);
      signatures.insert(metric.value(QStringLiteral("unit")).toString() + QLatin1Char('\x1f') +
                        metric.value(QStringLiteral("direction")).toString());
    }
    if (signatures.size() == 1) {
      consistentCommon.append(metricId);
    }
  }
  if (consistentCommon.isEmpty()) {
    reasons.append(QStringLiteral("Aucune métrique commune avec unité et sens de comparaison cohérents."));
  }

  QJsonArray runs;
  QJsonArray overlayMissing;
  for (qsizetype index = 0; index < details.size(); ++index) {
    const auto& summary = details.at(index).summary;
    runs.append(QJsonObject{
        {QStringLiteral("result_id"), summary.resultId},
        {QStringLiteral("run_id"), summary.runId},
        {QStringLiteral("label"), runLabel(summary)},
        {QStringLiteral("color"), palette.at(index)},
        {QStringLiteral("simulation_id"), summary.simulationId},
        {QStringLiteral("variant_id"), summary.variantId},
        {QStringLiteral("runner_id"), summary.runnerId},
        {QStringLiteral("domain"), summary.domain},
        {QStringLiteral("state"), summary.state},
        {QStringLiteral("created_at_utc"), summary.createdAtUtc.toString(Qt::ISODateWithMs)},
        {QStringLiteral("dataset_id"), summary.datasetId.isEmpty() ? QJsonValue::Null : QJsonValue(summary.datasetId)},
        {QStringLiteral("sequence_id"), summary.sequenceId.isEmpty() ? QJsonValue::Null : QJsonValue(summary.sequenceId)},
        {QStringLiteral("scenario_id"), summary.scenarioId.isEmpty() ? QJsonValue::Null : QJsonValue(summary.scenarioId)},
        {QStringLiteral("source_kind"), summary.sourceKind},
        {QStringLiteral("relative_directory"), summary.relativeDirectory},
    });
    if (!summary.replayAvailable) {
      overlayMissing.append(summary.resultId);
    }
  }

  QSet<QString> allMetricIds;
  for (const auto& values : metricMaps) {
    allMetricIds.unite(QSet<QString>(values.keyBegin(), values.keyEnd()));
  }
  auto orderedMetricIds = allMetricIds.values();
  std::sort(orderedMetricIds.begin(), orderedMetricIds.end());
  QJsonArray metricRows;
  for (const auto& metricId : orderedMetricIds) {
    QList<QJsonObject> definitions;
    QSet<QString> signatures;
    QJsonArray values;
    for (qsizetype index = 0; index < metricMaps.size(); ++index) {
      const auto metric = metricMaps.at(index).value(metricId);
      if (!metric.isEmpty()) {
        definitions.append(metric);
        signatures.insert(metric.value(QStringLiteral("unit")).toString() + QLatin1Char('\x1f') +
                          metric.value(QStringLiteral("direction")).toString());
      }
      values.append(QJsonObject{
          {QStringLiteral("result_id"), details.at(index).summary.resultId},
          {QStringLiteral("value"), metric.isEmpty() ? QJsonValue::Null : metric.value(QStringLiteral("value"))},
          {QStringLiteral("status"), metric.isEmpty() ? QJsonValue(QStringLiteral("unavailable"))
                                                       : metric.value(QStringLiteral("status"))},
      });
    }
    const auto comparable = definitions.size() == details.size() && signatures.size() == 1;
    const auto exemplar = definitions.front();
    const auto direction = exemplar.value(QStringLiteral("direction")).toString();
    metricRows.append(QJsonObject{
        {QStringLiteral("metric_id"), metricId},
        {QStringLiteral("label"), exemplar.value(QStringLiteral("label")).toString(metricId)},
        {QStringLiteral("unit"), exemplar.value(QStringLiteral("unit")).toString()},
        {QStringLiteral("direction"), direction},
        {QStringLiteral("comparable"), comparable},
        {QStringLiteral("best_result_ids"), comparable ? bestResultIds(values, direction) : QJsonArray{}},
        {QStringLiteral("values"), values},
    });
  }

  QSet<QString> parameterNames;
  QList<QJsonObject> parameterMaps;
  for (const auto& detail : details) {
    const auto parameters = detail.manifest.value(QStringLiteral("parameters")).toObject();
    parameterMaps.append(parameters);
    parameterNames.unite(jsonKeys(parameters));
  }
  auto orderedParameters = parameterNames.values();
  std::sort(orderedParameters.begin(), orderedParameters.end());
  QJsonArray parameterRows;
  for (const auto& name : orderedParameters) {
    QSet<QString> serialized;
    QJsonArray values;
    for (qsizetype index = 0; index < parameterMaps.size(); ++index) {
      const auto value = parameterMaps.at(index).value(name);
      serialized.insert(jsonCanonical(value));
      values.append(QJsonObject{{QStringLiteral("result_id"), details.at(index).summary.resultId},
                                {QStringLiteral("value"), value.isUndefined() ? QJsonValue::Null : value}});
    }
    parameterRows.append(QJsonObject{{QStringLiteral("parameter_id"), name},
                                     {QStringLiteral("same_for_all"), serialized.size() == 1},
                                     {QStringLiteral("values"), values}});
  }

  QJsonArray versions;
  for (const auto& detail : details) {
    const auto software = detail.manifest.value(QStringLiteral("software")).toObject();
    const auto process = software.value(QStringLiteral("mapping_process")).toObject();
    const auto compatibility = detail.manifest.value(QStringLiteral("compatibility")).toObject();
    versions.append(QJsonObject{
        {QStringLiteral("result_id"), detail.summary.resultId},
        {QStringLiteral("source_kind"), detail.summary.sourceKind},
        {QStringLiteral("runner_id"), detail.summary.runnerId},
        {QStringLiteral("algorithm"), software.value(QStringLiteral("legacy_algorithm")).toString(detail.summary.variantId)},
        {QStringLiteral("result_contract_version"), compatibility.value(QStringLiteral("result_contract_version"))},
        {QStringLiteral("process_schema_version"), process.value(QStringLiteral("schema_version"))},
        {QStringLiteral("process_exit_code"), process.value(QStringLiteral("exit_code"))},
    });
  }

  const auto compatibility = QJsonObject{
      {QStringLiteral("compatible"), reasons.isEmpty()},
      {QStringLiteral("reasons"), reasons},
      {QStringLiteral("comparison_group"), details.front().summary.comparisonGroup},
      {QStringLiteral("domain"), domain},
      {QStringLiteral("dataset_id"), details.front().summary.datasetId.isEmpty() ? QJsonValue::Null
                                                                                  : QJsonValue(details.front().summary.datasetId)},
      {QStringLiteral("sequence_id"), details.front().summary.sequenceId.isEmpty() ? QJsonValue::Null
                                                                                     : QJsonValue(details.front().summary.sequenceId)},
      {QStringLiteral("scenario_id"), details.front().summary.scenarioId.isEmpty() ? QJsonValue::Null
                                                                                     : QJsonValue(details.front().summary.scenarioId)},
      {QStringLiteral("common_metric_ids"), QJsonArray::fromStringList(consistentCommon)},
      {QStringLiteral("overlay_available"), overlayMissing.isEmpty()},
      {QStringLiteral("overlay_missing_result_ids"), overlayMissing},
  };

  return QJsonObject{
      {QStringLiteral("schema"), QStringLiteral("drone_agricole.result_comparison.v1")},
      {QStringLiteral("generated_at_utc"), QDateTime::currentDateTimeUtc().toString(Qt::ISODateWithMs)},
      {QStringLiteral("compatibility"), compatibility},
      {QStringLiteral("runs"), runs},
      {QStringLiteral("metrics"), metricRows},
      {QStringLiteral("parameters"), parameterRows},
      {QStringLiteral("versions"), versions},
  };
}

QString ComparisonService::report(const QStringList& resultIds) const { return renderMarkdownReport(preview(resultIds)); }

ComparisonResult ComparisonService::compare(const QStringList& resultIds) const {
  const auto comparison = preview(resultIds);
  return ComparisonResult{comparison, renderMarkdownReport(comparison)};
}

QString ComparisonService::renderMarkdownReport(const QJsonObject& comparison) {
  const auto compatibility = comparison.value(QStringLiteral("compatibility")).toObject();
  const auto runs = comparison.value(QStringLiteral("runs")).toArray();
  QStringList lines{
      QStringLiteral("# Rapport de comparaison T0.4"),
      QString{},
      QStringLiteral("Généré le : %1").arg(comparison.value(QStringLiteral("generated_at_utc")).toString()),
      QStringLiteral("Compatibilité : **%1**").arg(compatibility.value(QStringLiteral("compatible")).toBool()
                                                        ? QStringLiteral("validée")
                                                        : QStringLiteral("refusée")),
      QString{},
  };
  const auto reasons = compatibility.value(QStringLiteral("reasons")).toArray();
  if (!reasons.isEmpty()) {
    lines.append({QStringLiteral("## Motifs"), QString{}});
    for (const auto& reason : reasons) {
      lines.append(QStringLiteral("- %1").arg(reason.toString()));
    }
    lines.append(QString{});
  }
  lines.append({QStringLiteral("## Exécutions"), QString{}});
  QList<QJsonArray> runRows;
  for (const auto& value : runs) {
    const auto run = value.toObject();
    runRows.append(QJsonArray{run.value(QStringLiteral("variant_id")), run.value(QStringLiteral("run_id")),
                              run.value(QStringLiteral("state")), run.value(QStringLiteral("dataset_id")),
                              run.value(QStringLiteral("sequence_id")), run.value(QStringLiteral("source_kind"))});
  }
  lines.append(matrixTable({QStringLiteral("Algorithme / scénario"), QStringLiteral("Run"), QStringLiteral("État"),
                            QStringLiteral("Dataset"), QStringLiteral("Séquence"), QStringLiteral("Source")},
                           runRows));
  lines.append({QString{}, QStringLiteral("## Métriques"), QString{}});
  QStringList runLabels;
  for (const auto& value : runs) {
    runLabels.append(value.toObject().value(QStringLiteral("label")).toString());
  }
  QList<QJsonArray> metricRows;
  for (const auto& value : comparison.value(QStringLiteral("metrics")).toArray()) {
    const auto metric = value.toObject();
    QJsonArray row{metric.value(QStringLiteral("label")), metric.value(QStringLiteral("unit"))};
    const auto best = metric.value(QStringLiteral("best_result_ids")).toArray();
    for (const auto& itemValue : metric.value(QStringLiteral("values")).toArray()) {
      const auto item = itemValue.toObject();
      auto rendered = markdownValue(item.value(QStringLiteral("value")));
      if (best.contains(item.value(QStringLiteral("result_id")))) {
        rendered += QStringLiteral(" ★");
      }
      row.append(rendered);
    }
    metricRows.append(row);
  }
  auto metricHeaders = QStringList{QStringLiteral("Métrique"), QStringLiteral("Unité")};
  metricHeaders.append(runLabels);
  lines.append(matrixTable(metricHeaders, metricRows));
  lines.append({QString{}, QStringLiteral("★ meilleure valeur selon le sens déclaré par la métrique."), QString{},
                QStringLiteral("## Paramètres"), QString{}});
  QList<QJsonArray> parameterRows;
  for (const auto& value : comparison.value(QStringLiteral("parameters")).toArray()) {
    const auto parameter = value.toObject();
    QJsonArray row{parameter.value(QStringLiteral("parameter_id")),
                   parameter.value(QStringLiteral("same_for_all")).toBool() ? QJsonValue(QStringLiteral("oui"))
                                                                             : QJsonValue(QStringLiteral("non"))};
    for (const auto& item : parameter.value(QStringLiteral("values")).toArray()) {
      row.append(item.toObject().value(QStringLiteral("value")));
    }
    parameterRows.append(row);
  }
  auto parameterHeaders = QStringList{QStringLiteral("Paramètre"), QStringLiteral("Identique")};
  parameterHeaders.append(runLabels);
  lines.append(matrixTable(parameterHeaders, parameterRows));
  lines.append({QString{}, QStringLiteral("## Versions et sources"), QString{}});
  QHash<QString, QJsonObject> versions;
  for (const auto& value : comparison.value(QStringLiteral("versions")).toArray()) {
    versions.insert(value.toObject().value(QStringLiteral("result_id")).toString(), value.toObject());
  }
  QList<QJsonArray> versionRows;
  for (const auto& value : runs) {
    const auto run = value.toObject();
    const auto version = versions.value(run.value(QStringLiteral("result_id")).toString());
    versionRows.append(QJsonArray{run.value(QStringLiteral("label")), version.value(QStringLiteral("runner_id")),
                                  version.value(QStringLiteral("algorithm")), version.value(QStringLiteral("source_kind")),
                                  version.value(QStringLiteral("result_contract_version")),
                                  version.value(QStringLiteral("process_schema_version")),
                                  version.value(QStringLiteral("process_exit_code"))});
  }
  lines.append(matrixTable({QStringLiteral("Exécution"), QStringLiteral("Runner"), QStringLiteral("Algorithme"),
                            QStringLiteral("Source"), QStringLiteral("Contrat"), QStringLiteral("Schéma processus"),
                            QStringLiteral("Code sortie")},
                           versionRows));
  lines.append({QString{}, QStringLiteral("## Limites d’interprétation"), QString{},
                QStringLiteral("- Ce rapport compare les artefacts archivés ; il ne relance aucune simulation."),
                QStringLiteral("- Une étoile désigne le meilleur résultat mesuré, pas un choix d’architecture définitif."),
                QStringLiteral("- Toute valeur ou version absente reste explicitement indiquée par « — »."), QString{}});
  return lines.join(QLatin1Char('\n'));
}

}  // namespace drone_agricole::core
