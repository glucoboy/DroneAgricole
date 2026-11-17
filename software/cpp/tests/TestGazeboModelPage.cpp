#include "drone_agricole/ui/GazeboModelPage.hpp"
#include <QCheckBox>
#include <QLabel>
#include <QPushButton>
#include <QtTest>
#include <stdexcept>
using namespace drone_agricole;
class Backend final:public application::IGazeboExportBackend {
 public:QJsonObject inspect()const override{return {{QStringLiteral("source"),QStringLiteral("Prototype_Cartographe.FCStd")},{QStringLiteral("source_available"),true}};}
 QJsonObject execute(const application::GazeboExportRequest&,const std::atomic_bool& cancel,Progress progress)override{progress(20,QStringLiteral("Conversion"));for(int i=0;i<50;++i){QThread::msleep(5);if(cancel)throw std::runtime_error("cancelled");}return {{QStringLiteral("directory"),QStringLiteral("/fixture/cartographe")}};}
};
class TestGazeboModelPage:public QObject {
 Q_OBJECT
 private slots:
 void controlsAndCancel(){Backend b;application::GazeboExportService s(b);ui::GazeboModelPage page(s);page.show();auto* start=page.findChild<QPushButton*>(QStringLiteral("exportButton"));auto* stop=page.findChild<QPushButton*>(QStringLiteral("cancelExportButton"));QVERIFY(start);QVERIFY(stop);QVERIFY(start->isEnabled());QVERIFY(!stop->isEnabled());QVERIFY(page.findChild<QCheckBox*>(QStringLiteral("regenerateCheck"))->isChecked());start->click();QVERIFY(!start->isEnabled());QVERIFY(stop->isEnabled());stop->click();QTRY_COMPARE(s.state(),QStringLiteral("cancelled"));QVERIFY(start->isEnabled());QVERIFY(!page.findChild<QPushButton*>(QStringLiteral("openPackageButton"))->isEnabled());}
 void finalized(){Backend b;application::GazeboExportService s(b);ui::GazeboModelPage page(s);page.findChild<QPushButton*>(QStringLiteral("exportButton"))->click();QTRY_COMPARE(s.state(),QStringLiteral("completed"));QVERIFY(page.findChild<QPushButton*>(QStringLiteral("openPackageButton"))->isEnabled());QCOMPARE(page.findChild<QLabel*>(QStringLiteral("outputLabel"))->text(),QStringLiteral("/fixture/cartographe"));}
};
QTEST_MAIN(TestGazeboModelPage)
#include "TestGazeboModelPage.moc"
