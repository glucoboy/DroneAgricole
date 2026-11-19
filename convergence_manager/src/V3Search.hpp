#pragma once

#include <QJsonObject>
#include <QString>

namespace convergence {

QJsonObject generateV3Proposals(const QJsonObject &domain, const QJsonObject &baseline,
                               const QJsonObject &problem, int seed, const QString &family = {});

} // namespace convergence
