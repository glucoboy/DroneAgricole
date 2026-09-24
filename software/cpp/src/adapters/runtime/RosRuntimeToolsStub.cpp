#include "drone_agricole/core/RosRuntimeTools.hpp"

#include "drone_agricole/core/JsonUtils.hpp"

namespace drone_agricole::core {

QJsonObject waitForPipelineDrain(const QString&, const QString&, const QString&, double, double) {
  throw ContractError(QStringLiteral("Le contrôle de vidange requiert ROS 2"));
}

int runLioSamPipelineMonitor() {
  throw ContractError(QStringLiteral("Le moniteur LIO-SAM requiert ROS 2"));
}

}  // namespace drone_agricole::core
