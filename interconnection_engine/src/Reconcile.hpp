#pragma once

#include <QJsonObject>
#include <QString>

namespace interconnection {

// Read-only projection of the frozen L0 cartographe inputs. Throws on integrity errors.
QJsonObject reconcileInterconnections(const QString &root);
QJsonObject inspectCartographeInterfaces(const QString &root);

} // namespace interconnection
