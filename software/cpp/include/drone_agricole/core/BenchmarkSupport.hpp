#pragma once

#include <QJsonObject>
#include <QString>
#include <QStringList>

namespace drone_agricole::core {

struct BagMetadata {
  double durationSeconds{0.0};
  qint64 messageCount{0};
  QJsonObject topicMessageCounts;
};

[[nodiscard]] BagMetadata readBagMetadata(const QString& bagDirectory);
[[nodiscard]] qint64 bagTopicCount(const QString& bagDirectory, const QString& topic);
[[nodiscard]] int playbackProgressPercent(double elapsedWallSeconds,
                                          double bagDurationSeconds,
                                          double playbackRate,
                                          double playbackDelaySeconds);
[[nodiscard]] QJsonObject pipelineAccounting(const QJsonObject& counters);
[[nodiscard]] QJsonObject numericStatistics(const QList<double>& values);
[[nodiscard]] QJsonObject loadCampaignRun(const QString& directory, const QString& campaignRoot);

void summarizeRun(const QJsonObject& options);
void summarizeSensitivity(const QJsonObject& options);
void summarizeCampaign(const QJsonObject& options);
void compareRuns(const QJsonObject& options);
void comparePlaybackRates(const QJsonObject& options);

}  // namespace drone_agricole::core
