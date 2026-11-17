#pragma once

#include <QByteArray>
#include <QJsonObject>
#include <QJsonValue>
#include <QString>

namespace technical_research {

struct SourceInput {
    QByteArray bytes;
    QString sha256;
    QString code;
    QString message;
};

SourceInput readLocalSource(const QString &root, const QString &relativePath);
SourceInput readRemoteSource(const QString &uri);
QJsonValue extractSourceValue(const SourceInput &input, const QJsonObject &extraction,
                              const QString &partNumber);

} // namespace technical_research
