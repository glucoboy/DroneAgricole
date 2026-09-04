#pragma once

#include "drone_agricole/core/Types.hpp"

namespace drone_agricole::core {

[[nodiscard]] ReplayData readLioTrajectory(const QString& bagDirectory, const QString& resultId);

}  // namespace drone_agricole::core
