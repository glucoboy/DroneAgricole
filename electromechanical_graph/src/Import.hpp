#pragma once

#include <QJsonObject>
#include <QString>

namespace electromechanical::graph {

QJsonObject importGraph(const QString &root, const QJsonObject &native, const QString &authorityPath,
                        bool cartographeL2);
void verifySources(const QString &root, const QJsonObject &sources);

} // namespace electromechanical::graph
