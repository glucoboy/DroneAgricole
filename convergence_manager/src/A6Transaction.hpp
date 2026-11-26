#pragma once

#include <QByteArray>
#include <QDir>
#include <QJsonObject>

namespace convergence {

int runAuthorizedTransaction(const QDir &root, const QDir &sandbox, const QDir &output,
                             const QString &requestPath, const QByteArray &requestBytes, const QJsonObject &request,
                             const QString &trustPath, const QString &trustSha256);

} // namespace convergence
