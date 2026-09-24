#include "drone_agricole/core/DatasetAdapter.hpp"

#include "drone_agricole/core/JsonUtils.hpp"

namespace drone_agricole::core {

QJsonObject prepareBotanicGarden(const QJsonObject&) {
  throw ContractError(QStringLiteral("La préparation rosbag2 BotanicGarden requiert la construction ROS 2"));
}

QJsonObject prepareFriulBot(const QJsonObject&) {
  throw ContractError(QStringLiteral("La préparation rosbag2 FriûlBot requiert la construction ROS 2"));
}

}  // namespace drone_agricole::core
