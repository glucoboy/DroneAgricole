#pragma once

#include <QJsonObject>

namespace drone_agricole::core {

[[nodiscard]] QJsonObject inspectFriulBot(const QJsonObject& options);
[[nodiscard]] QJsonObject runFriulBotCaptureMapping(const QJsonObject& options);

}  // namespace drone_agricole::core
