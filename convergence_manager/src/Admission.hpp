#pragma once

#include <QDir>
#include <QJsonObject>

namespace convergence {

QJsonObject preflight(const QDir &root, const QDir &output, const QString &mode,
                      const QString &planPath, const QString &receiptPath, int steps,
                      const QString &sourceRelease = "v2.1");

} // namespace convergence
