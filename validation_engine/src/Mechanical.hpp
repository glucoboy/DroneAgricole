#pragma once

#include "Finding.hpp"

#include <QJsonObject>

namespace electromechanical_validation {

Assessment assessMechanical(const QJsonObject &check, const QJsonObject &observation);

} // namespace electromechanical_validation
