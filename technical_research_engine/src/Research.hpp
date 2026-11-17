#pragma once

#include <QJsonObject>
#include <QString>

namespace technical_research {

struct Result {
    QJsonObject json;
    int exitCode = 0;
};

Result submit(const QString &root, const QString &store, const QString &catalog,
              const QString &issue, bool online, bool refresh);
Result get(const QString &root, const QString &store, const QString &issue);
Result list(const QString &root, const QString &store, const QString &view);
Result invalidate(const QString &store, const QString &issue);

} // namespace technical_research
