#pragma once

#include <QJsonObject>
#include <QString>

namespace electromechanical::graph {

// Throws std::runtime_error on an unsupported version or an invalid graph.
void validate(const QJsonObject &graph);

// Read-only dependency closure. A hypothetical operation grants no authority.
QJsonObject impact(const QJsonObject &graph, const QString &operation, const QString &target);

// Compares signed frames against an independent reference, in millimetres and degrees.
QJsonObject compareFrames(const QJsonObject &request);

} // namespace electromechanical::graph
