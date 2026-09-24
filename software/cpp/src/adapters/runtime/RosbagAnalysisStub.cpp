#include "drone_agricole/core/RosbagAnalysis.hpp"

#include "drone_agricole/core/JsonUtils.hpp"

namespace drone_agricole::core {

QJsonObject analyzeRosbag(const QString&,
                          double,
                          double,
                          double,
                          const QString&,
                          const QString&,
                          const QString&) {
  throw ContractError(QStringLiteral("L'analyse rosbag2 requiert la construction ROS 2 de drone-agricole-tools"));
}

}  // namespace drone_agricole::core
