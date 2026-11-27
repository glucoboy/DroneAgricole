#pragma once

#include <QDir>
#include <QJsonArray>
#include <QJsonObject>

#include <stdexcept>

namespace convergence {

inline constexpr auto v3ParametricPlanSchema = "v3.mutation_plan/2";
inline constexpr auto v3MultiHarnessPlanSchema = "v3.mutation_plan/3";
inline constexpr auto v3SpatialPlanSchema = "v3.mutation_plan/4";
inline constexpr auto v3SixDofPlanSchema = "v3.mutation_plan/5";
inline constexpr auto v3SpatialDomainSchema = "v3.parametric_domain/3";
inline constexpr auto v3SixDofDomainSchema = "v3.parametric_domain/4";
inline constexpr auto v3MultiHarnessDomainSchema = "v3.parametric_domain/2";
inline constexpr auto v3NativePortMode = "NATIVE_PORT";

inline bool isV3ParametricPlan(const QJsonValue &schema)
{
    return schema == v3ParametricPlanSchema || schema == v3MultiHarnessPlanSchema ||
           schema == v3SpatialPlanSchema || schema == v3SixDofPlanSchema;
}

inline bool isV3SpatialDomain(const QJsonValue &schema)
{
    return schema == v3SpatialDomainSchema || schema == v3SixDofDomainSchema;
}

inline bool isV3MultiHarnessDomain(const QJsonValue &schema)
{
    return schema == v3MultiHarnessDomainSchema || isV3SpatialDomain(schema);
}

void validateV3ExternalObstacle(const QJsonObject &obstacle);

// The coupled route solver supports translation with a locked orientation.
struct V3UnsupportedPose : std::runtime_error {
    V3UnsupportedPose() : std::runtime_error("ROTATION_DOMAIN_UNSUPPORTED") {}
};

QString v3DomainPath(const QString &sha);
QString v3BaseProfilePath(const QJsonObject &domain);
QJsonObject loadV3Domain(const QDir &root, const QString &sha);
QJsonObject makeV3Plan(const QString &planId, const QString &domainSha, const QJsonObject &values,
                       bool spatial = false, const QJsonObject &externalObstacle = {});
QJsonObject validateV3Plan(const QJsonObject &domain, const QJsonObject &profile, const QString &domainSha,
                          const QJsonObject &plan);

struct V3ParametricAdmission {
    QJsonObject profile;
    QJsonObject expandedPlan;
    QJsonArray decisions;
};

V3ParametricAdmission admitV3Plan(const QDir &root, const QDir &sandbox, const QJsonObject &plan);

} // namespace convergence
