#pragma once

#include "drone_agricole/core/Types.hpp"

namespace drone_agricole::core {

[[nodiscard]] QString detectResultKind(const QString& directory);
[[nodiscard]] NormalizedResult normalizeResultDirectory(const QString& directory);
void writeNativeContracts(const NormalizedResult& result, const QJsonObject& request);

}  // namespace drone_agricole::core
