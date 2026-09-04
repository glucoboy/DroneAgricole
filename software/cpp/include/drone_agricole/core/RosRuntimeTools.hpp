#pragma once

#include <QJsonObject>
#include <QString>

namespace drone_agricole::core {

[[nodiscard]] QJsonObject waitForPipelineDrain(const QString& bagDirectory,
                                               const QString& inputTopic,
                                               const QString& pipelineTopic,
                                               double timeoutSeconds,
                                               double stableSeconds);
int runLioSamPipelineMonitor();

}  // namespace drone_agricole::core
