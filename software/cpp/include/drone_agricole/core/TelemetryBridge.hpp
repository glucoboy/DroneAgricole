#pragma once

#include "drone_agricole/core/LiveTelemetry.hpp"
#include "drone_agricole/core/Types.hpp"

#include <QJsonObject>

namespace drone_agricole::core {

[[nodiscard]] QJsonObject telemetrySnapshotToJson(const LiveTelemetrySnapshot& snapshot);
[[nodiscard]] LiveTelemetrySnapshot telemetrySnapshotFromJson(const QJsonObject& payload);

[[nodiscard]] QJsonObject replayDataToJson(const ReplayData& replay);
[[nodiscard]] ReplayData replayDataFromJson(const QJsonObject& payload);

int runTelemetryServer(const QJsonObject& options);

}  // namespace drone_agricole::core
