#pragma once

#include <QJsonObject>
#include <QString>

namespace drone_agricole::core {

[[nodiscard]] QJsonObject analyzeRosbag(const QString& bagDirectory,
                                        double maximumAssociationDeltaSeconds,
                                        double rpeDeltaSeconds,
                                        double rpeToleranceSeconds,
                                        const QString& estimateTopic = QStringLiteral("/Odometry"),
                                        const QString& groundTruthTopic = QStringLiteral("/gt_poses"),
                                        const QString& pipelineTopic = QStringLiteral("/fast_lio2/pipeline_counters"));

}  // namespace drone_agricole::core
