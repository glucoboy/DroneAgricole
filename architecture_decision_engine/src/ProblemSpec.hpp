#pragma once

#include <QJsonObject>
#include <optional>

namespace architecture_decision {

struct ProblemSources {
    QJsonObject domain;
    QString domainSha256;
    QString modelSha256;
    QString observationSha256;
};

struct BaseProblem {
    QJsonObject spec;
    QString sha256;
};

QJsonObject parseProblemObject(const QByteArray &bytes, const QString &source);
QJsonObject validateProblemSpec(const QJsonObject &request, const ProblemSources &sources,
                                const std::optional<BaseProblem> &base);

} // namespace architecture_decision
