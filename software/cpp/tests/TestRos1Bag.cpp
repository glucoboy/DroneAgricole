#include "drone_agricole/core/DatasetAdapter.hpp"
#include "drone_agricole/core/Ros1Bag.hpp"

#include <QDir>
#include <QFileInfo>
#include <QTemporaryDir>
#include <QtTest>

using namespace drone_agricole::core;

class TestRos1Bag final : public QObject {
  Q_OBJECT

 private slots:
  void readsBotanicGardenGroundTruthIndexAndMessages() {
    const auto path = QDir(QStringLiteral(DRONE_AGRICOLE_TEST_WORKSPACE))
                          .filePath(QStringLiteral("datasets/public/botanicgarden/1006-03/ground_truth/gt_1006_03_qnew.bag"));
    if (!QFileInfo::exists(path)) {
      QSKIP("Rosbag terrain BotanicGarden absent de cette machine");
    }
    Ros1Bag bag(path);
    bag.open();
    QVERIFY(bag.messageCount() > 0);
    QVERIFY(std::any_of(bag.connections().cbegin(), bag.connections().cend(), [](const auto& connection) {
      return connection.topic == QStringLiteral("/gt_poses");
    }));
    QTemporaryDir temporary;
    QVERIFY(temporary.isValid());
    const auto output = QDir(temporary.path()).filePath(QStringLiteral("truth.tum"));
    const auto result = exportGroundTruthTum(path, output);
    QVERIFY(result.value(QStringLiteral("poses")).toInt() > 0);
    QVERIFY(QFileInfo(output).size() > 100);
  }
};

QTEST_APPLESS_MAIN(TestRos1Bag)
#include "TestRos1Bag.moc"
