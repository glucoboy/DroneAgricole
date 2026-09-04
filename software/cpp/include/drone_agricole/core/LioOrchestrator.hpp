#pragma once

#include <QJsonObject>

namespace drone_agricole::core {

int runLioBenchmark(const QJsonObject& options);
int runFastLioCampaign(const QJsonObject& options);

}  // namespace drone_agricole::core
