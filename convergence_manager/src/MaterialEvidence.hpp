#pragma once

#include <QDir>
#include <QJsonObject>

namespace convergence {

QJsonObject validateMaterialPacket(const QDir &root, const QJsonObject &packet, const QJsonObject &policy,
                                   const QString &evidenceClass = QStringLiteral("PHYSICAL_MEASURED"));

} // namespace convergence
