#pragma once

#include <QJsonValue>
#include <QString>

namespace electromechanical_validation {

struct Assessment {
    QString status;
    QJsonValue value;
    QString unit;
    QString reason;
};

} // namespace electromechanical_validation
