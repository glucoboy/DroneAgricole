#pragma once

#include "drone_agricole/core/Types.hpp"

#include <QJsonObject>

namespace drone_agricole::core {

[[nodiscard]] QJsonObject runVineyardMapping(const QJsonObject& options);
[[nodiscard]] ReplayData readVineyardMapReplay(const QString& path, const QString& resultId);

}  // namespace drone_agricole::core
