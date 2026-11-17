#pragma once

#include <QJsonArray>
#include <QJsonObject>

#include "Finding.hpp"

namespace electromechanical_validation {

QJsonObject makeFinding(const QString &caseId, const QJsonObject &check, const Assessment &result,
                       const QString &evidenceId, const QString &timestamp, const QString &scope);
QJsonObject makeReport(const QString &caseId, const QString &candidateId, const QString &scope,
                      const QJsonObject &fingerprints, const QJsonObject &environment,
                      const QJsonArray &findings, const QJsonArray &evidence,
                      const QString &nativeEvidenceId);
QJsonObject makeEvidence(const QString &id, const QString &path, const QString &sha256,
                         const QString &scope, const QString &method, const QString &timestamp);

} // namespace electromechanical_validation
