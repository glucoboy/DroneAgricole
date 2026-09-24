#include "drone_agricole/ui/MainWindow.hpp"
#include "drone_agricole/composition/StationComposition.hpp"
#include <QListWidget>
#include <QStackedWidget>
#include <QComboBox>
#include <QPushButton>
#include <QDir>
#include <QtTest>
using namespace drone_agricole;
class TestStationNavigation : public QObject {
  Q_OBJECT
 private slots:
  void routesAreRegisteredAndPreserveContext() {
    ui::NavigationModel navigation;
    navigation.registerPage(QStringLiteral("results"), QStringLiteral("Résultats"));
    navigation.registerPage(QStringLiteral("result"), QStringLiteral("Archive"));
    QVERIFY(!navigation.navigate(QStringLiteral("unknown")));
    QVERIFY(navigation.navigate(QStringLiteral("results")));
    QVERIFY(navigation.navigate(QStringLiteral("result"), QStringLiteral("id-42")));
    QCOMPARE(navigation.current().object, QStringLiteral("id-42"));
    navigation.back();
    QCOMPARE(navigation.current().page, QStringLiteral("results"));
    QVERIFY(!navigation.canGoBack());
    QVERIFY_EXCEPTION_THROWN(navigation.registerPage(QStringLiteral("results"), {}), std::invalid_argument);
  }
  void sidebarAndBackPreserveConfiguration() {
    composition::StationComposition services(QStringLiteral(DRONE_AGRICOLE_TEST_WORKSPACE));
    ui::MainWindow window(services);
    const auto screenshotDirectory = qEnvironmentVariable("DRONE_AGRICOLE_NAVIGATION_SCREENSHOTS");
    if (!screenshotDirectory.isEmpty()) window.show();
    const auto capture = [&](const QString& name) {
      if (screenshotDirectory.isEmpty()) return;
      QTest::qWait(150);
      QVERIFY(window.grab().save(QDir(screenshotDirectory).filePath(name + QStringLiteral(".png")), "PNG"));
    };
    auto* navigation = window.findChild<QListWidget*>(QStringLiteral("navigationList"));
    auto* stack = window.findChild<QStackedWidget*>(QStringLiteral("pageStack"));
    auto* back = window.findChild<QPushButton*>(QStringLiteral("backButton"));
    QVERIFY(navigation); QVERIFY(stack); QVERIFY(back);
    QCOMPARE(stack->currentWidget()->objectName(), QStringLiteral("overviewPage"));
    capture(QStringLiteral("overview"));
    navigation->setCurrentRow(2);
    QCOMPARE(stack->currentWidget()->objectName(), QStringLiteral("ExecutionPage"));
    auto* simulation = window.findChild<QComboBox*>(QStringLiteral("simulationCombo"));
    simulation->setCurrentIndex(simulation->count() - 1);
    const auto selected = simulation->currentData();
    navigation->setCurrentRow(1);
    QCOMPARE(stack->currentWidget()->objectName(), QStringLiteral("acquisitionsPage"));
    capture(QStringLiteral("acquisitions"));
    back->click();
    QCOMPARE(stack->currentWidget()->objectName(), QStringLiteral("ExecutionPage"));
    QCOMPARE(simulation->currentData(), selected);
    QCOMPARE(navigation->currentRow(), 2);
    QVERIFY(!services.execution().active());
    capture(QStringLiteral("tests"));
    navigation->setCurrentRow(3);
    capture(QStringLiteral("results"));
  }
};
QTEST_MAIN(TestStationNavigation)
#include "TestStationNavigation.moc"
