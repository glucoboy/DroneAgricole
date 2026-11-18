#pragma once

#include <QDir>
#include <QJsonObject>

namespace convergence {

// The root supplies the shipped policy evidence. The sandbox is a private input copy.
// The decision is for the evaluated request only and never certifies a result.
QJsonObject evaluateAdmissionScope(const QDir &root, const QDir &sandbox, const QJsonObject &request);

} // namespace convergence
