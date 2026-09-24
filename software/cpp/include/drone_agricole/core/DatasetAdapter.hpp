#pragma once

#include <QJsonObject>
#include <QStringList>

namespace drone_agricole::core {

[[nodiscard]] QJsonObject inspectRos1Bags(const QStringList& paths, bool includeHash = false);
[[nodiscard]] QJsonObject exportGroundTruthTum(const QString& groundTruthBag, const QString& outputPath);
[[nodiscard]] QJsonObject prepareBotanicGarden(const QJsonObject& options);
[[nodiscard]] QJsonObject prepareFriulBot(const QJsonObject& options);

}  // namespace drone_agricole::core
