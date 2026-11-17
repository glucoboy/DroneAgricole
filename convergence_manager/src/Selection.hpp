#pragma once

#include <QJsonArray>
#include <QJsonObject>
#include <QString>

namespace convergence {

// Hash applied physical assignments and the declared topology. The grid applies
// to dimensional assignments and preserves the direction of each route.
QString candidateSignature(const QJsonObject &candidate, double geometryTolerance);

// Group observations of the same failure across distinct candidate reports.
QJsonArray constraintConflictAnalyzer(const QJsonArray &reports);

// Merge only locally admitted decisions. The frozen ownership table maps every
// assignment key to all connections that must be revalidated after a change.
QJsonObject mergeDecisions(const QJsonArray &decisions, const QJsonObject &linkSubjects);

// Compare complete, hard-pass observations under the same frozen reference.
// Objective declaration order breaks tradeoffs within the Pareto frontier.
QJsonObject compareCandidates(const QJsonArray &reports, const QJsonArray &objectives,
                              const QString &referenceSha256 = {});

} // namespace convergence
