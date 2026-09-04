#include "drone_agricole/core/BenchmarkSupport.hpp"

#include <QDir>
#include <QFile>
#include <QJsonDocument>
#include <QTemporaryDir>
#include <QtTest>

using namespace drone_agricole::core;

class TestBenchmarkSupport final : public QObject {
  Q_OBJECT

 private slots:
  void readsRosbagMetadata() {
    QTemporaryDir temporary;
    QVERIFY(temporary.isValid());
    QFile metadata(QDir(temporary.path()).filePath(QStringLiteral("metadata.yaml")));
    QVERIFY(metadata.open(QIODevice::WriteOnly | QIODevice::Text));
    metadata.write("rosbag2_bagfile_information:\n"
                   "  duration: {nanoseconds: 5000000000}\n"
                   "  message_count: 30\n"
                   "  topics_with_message_count:\n"
                   "    - message_count: 12\n"
                   "      topic_metadata: {name: /velodyne_points}\n"
                   "    - message_count: 18\n"
                   "      topic_metadata: {name: /imu/data}\n");
    metadata.close();
    const auto result = readBagMetadata(temporary.path());
    QCOMPARE(result.durationSeconds, 5.0);
    QCOMPARE(result.messageCount, 30);
    QCOMPARE(bagTopicCount(temporary.path(), QStringLiteral("/velodyne_points")), 12);
  }

  void accountsPipeline() {
    const auto result = pipelineAccounting({
        {QStringLiteral("scans_received"), 100},
        {QStringLiteral("scans_preprocessed"), 100},
        {QStringLiteral("scans_synchronized"), 96},
        {QStringLiteral("scans_initialization"), 1},
        {QStringLiteral("scans_rejected_undistort_empty"), 2},
        {QStringLiteral("scans_map_initialization"), 1},
        {QStringLiteral("scans_rejected_downsample"), 0},
        {QStringLiteral("state_updates"), 92},
        {QStringLiteral("odometry_published"), 92},
    });
    QCOMPARE(result.value(QStringLiteral("preprocessed_minus_synchronized")).toInt(), 4);
    QCOMPARE(result.value(QStringLiteral("unaccounted_synchronized_scans")).toInt(), 0);
    QCOMPARE(result.value(QStringLiteral("state_updates_minus_odometry")).toInt(), 0);
    QCOMPARE(result.value(QStringLiteral("ratios_percent")).toObject()
                 .value(QStringLiteral("odometry_over_received"))
                 .toDouble(),
             92.0);
  }

  void estimatesPlaybackProgress() {
    QCOMPARE(playbackProgressPercent(0.0, 100.0, 1.0, 1.0), 5);
    QCOMPARE(playbackProgressPercent(51.0, 100.0, 1.0, 1.0), 48);
    QCOMPARE(playbackProgressPercent(101.0, 100.0, 1.0, 1.0), 90);
    QCOMPARE(playbackProgressPercent(26.0, 100.0, 2.0, 1.0), 48);
    QCOMPARE(playbackProgressPercent(10.0, 0.0, 1.0, 1.0), 5);
  }

  void computesSampleStatistics() {
    const auto result = numericStatistics({1.0, 2.0, 3.0});
    QCOMPARE(result.value(QStringLiteral("n")).toInt(), 3);
    QCOMPARE(result.value(QStringLiteral("mean")).toDouble(), 2.0);
    QCOMPARE(result.value(QStringLiteral("sample_stdev")).toDouble(), 1.0);
  }
};

QTEST_APPLESS_MAIN(TestBenchmarkSupport)
#include "TestBenchmarkSupport.moc"
