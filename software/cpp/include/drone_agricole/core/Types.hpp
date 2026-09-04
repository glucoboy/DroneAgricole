#pragma once

#include <QDateTime>
#include <QHash>
#include <QJsonArray>
#include <QJsonObject>
#include <QList>
#include <QMetaType>
#include <QPointF>
#include <QVector3D>

namespace drone_agricole::core {

struct DatasetSequence {
  QString datasetId;
  QString datasetLabel;
  QString sequenceId;
  QString sequenceLabel;
  QString status;
  double durationSeconds{0.0};
  bool recommended{false};
  QSet<QString> capabilities;
  QJsonArray resources;
};

struct ParameterDefinition {
  QString id;
  QString runnerKey;
  QString label;
  QString description;
  QString type;
  QString unit;
  QString group;
  QString safetyClass;
  QJsonValue defaultValue;
  QJsonValue minimum;
  QJsonValue maximum;
  QJsonValue step;
};

struct VariantDefinition {
  QString id;
  QString label;
  QString description;
  QString runnerId;
  bool available{false};
  QSet<QString> requiredCapabilities;
  QList<ParameterDefinition> parameters;
  QJsonObject raw;
};

struct SimulationDefinition {
  QString id;
  QString version;
  QString label;
  QString description;
  QString domain;
  QString runnerId;
  QString safetyClass;
  QString comparisonGroup;
  QList<VariantDefinition> variants;
  QList<ParameterDefinition> parameters;
  QJsonArray selectors;
  QJsonArray profiles;
  QJsonObject raw;
};

struct NormalizedResult {
  QString sourceKind;
  QString directory;
  QJsonObject manifest;
  QJsonObject metrics;
  QJsonObject artifacts;
  QJsonArray events;
};

struct ResultSummary {
  QString resultId;
  QString runId;
  QString relativeDirectory;
  QString sourceKind;
  QString simulationId;
  QString variantId;
  QString runnerId;
  QString domain;
  QString state;
  QString datasetId;
  QString sequenceId;
  QString scenarioId;
  QString comparisonGroup;
  QString metricsStatus;
  QDateTime createdAtUtc;
  QDateTime finishedAtUtc;
  QStringList tags;
  QJsonArray metricPreview;
  qsizetype eventCount{0};
  qsizetype artifactCount{0};
  bool replayAvailable{false};
  bool duplicateAvailable{false};

  [[nodiscard]] QJsonObject toJson() const;
};

struct ResultDetail {
  ResultSummary summary;
  QJsonObject manifest;
  QJsonObject metrics;
  QJsonObject legacyMetrics;
  QJsonObject artifacts;
  QJsonArray events;
  QJsonObject duplicateRequest;
};

struct SearchFilters {
  QString domain;
  QString datasetId;
  QString scenarioId;
  QString algorithmId;
  QString state;
  QString tag;
  QDate dateFrom;
  QDate dateTo;
};

struct ReplayData {
  QString resultId;
  QString domain;
  QList<QVector3D> estimate;
  QList<QVector3D> truth;
  QList<QVector3D> px4Path;
  QList<QPointF> curve;
  QString curveId;
  QString curveLabel;
  QString curveUnit;
  QStringList notes;
};

struct ComparisonResult {
  QJsonObject preview;
  QString markdownReport;
};

struct PreparedRun {
  QString runId;
  QString simulationId;
  QString variantId;
  QString runnerId;
  QString program;
  QStringList arguments;
  QString workingDirectory;
  QString resultDirectory;
  QJsonObject request;
  QString stopProgram;
  QStringList stopArguments;
};

}  // namespace drone_agricole::core

Q_DECLARE_METATYPE(drone_agricole::core::ResultSummary)
