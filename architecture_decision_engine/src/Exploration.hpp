#pragma once

#include <QJsonObject>
#include <functional>

namespace architecture_decision {

using Interconnection = std::function<QJsonObject(const QJsonObject &, const QJsonArray &)>;
using Research = std::function<QJsonObject(const QString &)>;
using Publish = std::function<QString(const QString &, const QJsonObject &)>;

QJsonObject explore(const QJsonObject &bench, const QJsonObject &requirements,
                    const QString &baselineSha, const QString &requirementsSha,
                    const Interconnection &interconnection, const Research &research,
                    const Publish &publish);

} // namespace architecture_decision
