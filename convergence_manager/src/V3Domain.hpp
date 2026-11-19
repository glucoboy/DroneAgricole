#pragma once

#include <QDir>
#include <QJsonArray>
#include <QJsonObject>

namespace convergence {

inline constexpr auto v3ParametricPlanSchema = "v3.mutation_plan/2";

QString v3DomainPath(const QString &sha);
QString v3BaseProfilePath(const QJsonObject &domain);
QJsonObject loadV3Domain(const QDir &root, const QString &sha);
QJsonObject makeV3Plan(const QString &planId, const QString &domainSha, const QJsonObject &values);
QJsonObject validateV3Plan(const QJsonObject &domain, const QJsonObject &profile, const QString &domainSha,
                          const QJsonObject &plan);

struct V3ParametricAdmission {
    QJsonObject profile;
    QJsonObject expandedPlan;
    QJsonArray decisions;
};

V3ParametricAdmission admitV3Plan(const QDir &root, const QDir &sandbox, const QJsonObject &plan);

} // namespace convergence
