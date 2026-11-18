#pragma once

#include <QDir>
#include <QJsonObject>

namespace convergence {

QJsonObject runV3Mutation(const QDir &root, const QDir &sandbox, const QDir &output,
                          const QByteArray &planBytes, const QJsonObject &plan,
                          const QString &freecadPython, const QString &t0Validator);

} // namespace convergence
