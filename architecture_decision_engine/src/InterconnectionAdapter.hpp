#pragma once

#include <QJsonArray>
#include <QJsonObject>

namespace architecture_decision {

QJsonObject validateInterconnection(const QJsonObject &dossier, const QJsonObject &parameters,
                                    const QJsonObject &projection, const QJsonArray &research);

} // namespace architecture_decision
