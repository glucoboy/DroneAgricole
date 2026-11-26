#pragma once

#include <QJsonObject>
#include <QString>
#include <QStringList>

namespace convergence {

QStringList v3SpatialStrategies();

QJsonObject generateV3Proposals(const QJsonObject &domain, const QJsonObject &baseline,
                               const QJsonObject &problem, int seed, const QString &family = {},
                               int routeAlternative = 0);

} // namespace convergence
