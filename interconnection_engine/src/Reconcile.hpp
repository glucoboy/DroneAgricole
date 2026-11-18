#pragma once

#include <QJsonObject>
#include <QString>

namespace interconnection {

// Read-only projection of the frozen L0 cartographe inputs. Throws on integrity errors.
QJsonObject reconcileInterconnections(const QString &root);
QJsonObject inspectCartographeInterfaces(const QString &root);
// V3 records both digests for the current LF mechanical manifest and its frozen CRLF form.
QJsonObject inspectCartographeInterfacesV3(const QString &root);

} // namespace interconnection
