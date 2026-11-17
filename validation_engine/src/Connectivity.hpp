#pragma once

#include "Finding.hpp"

#include <QJsonObject>

namespace electromechanical_validation {

Assessment assessConnectivity(const QJsonObject &check, const QJsonObject &reference,
                              const QJsonObject &candidate);

} // namespace electromechanical_validation
