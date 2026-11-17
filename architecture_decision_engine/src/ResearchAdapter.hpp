#pragma once

#include <QJsonObject>
#include <QString>

namespace architecture_decision {

QJsonObject researchIssue(const QString &executable, const QString &root, const QString &store,
                          const QString &catalog, const QString &issueId);

} // namespace architecture_decision
