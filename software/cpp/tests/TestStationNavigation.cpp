#include "drone_agricole/ui/MainWindow.hpp"
#include "drone_agricole/composition/StationComposition.hpp"
#include <QListWidget>
#include <QStackedWidget>
#include <QComboBox>
#include <QPushButton>
#include <QTabBar>
#include <QLineEdit>
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
    QCOMPARE(navigation->count(), 6);
    QVERIFY(window.navigate(QStringLiteral("tests")));
    QCOMPARE(stack->currentWidget()->objectName(), QStringLiteral("ExecutionPage"));
    auto* simulation = window.findChild<QComboBox*>(QStringLiteral("simulationCombo"));
    simulation->setCurrentIndex(simulation->count() - 1);
    const auto selected = simulation->currentData();
    QVERIFY(window.navigate(QStringLiteral("acquisitions")));
    QCOMPARE(stack->currentWidget()->objectName(), QStringLiteral("DataPage"));
    capture(QStringLiteral("acquisitions"));
    back->click();
    QCOMPARE(stack->currentWidget()->objectName(), QStringLiteral("ExecutionPage"));
    QCOMPARE(simulation->currentData(), selected);
    QCOMPARE(navigation->currentRow(), 3);
    QVERIFY(!services.execution().active());
    capture(QStringLiteral("tests"));
    QVERIFY(window.navigate(QStringLiteral("results")));
    capture(QStringLiteral("results"));
    auto* tabs = window.findChild<QTabBar*>(QStringLiteral("sectionTabs"));
    QVERIFY(tabs);
    QCOMPARE(tabs->count(), 5);
    tabs->setCurrentIndex(0);
    QCOMPARE(stack->currentWidget()->objectName(), QStringLiteral("ExecutionPage"));
    QCOMPARE(simulation->currentData(), selected);
    const QStringList routes{QStringLiteral("overview"), QStringLiteral("recent"), QStringLiteral("favorites"),
      QStringLiteral("mission-preparation"), QStringLiteral("mission-supervision"), QStringLiteral("mission-journal"),
      QStringLiteral("data-catalogue"), QStringLiteral("acquisitions"), QStringLiteral("data-transfer"),
      QStringLiteral("bench-configuration"), QStringLiteral("tests"), QStringLiteral("results"), QStringLiteral("comparison"), QStringLiteral("bench-model"),
      QStringLiteral("analysis-maps"), QStringLiteral("analysis-trajectories"), QStringLiteral("analysis-metrics"), QStringLiteral("analysis-reports"),
      QStringLiteral("system-settings"), QStringLiteral("system-hardware"), QStringLiteral("system-diagnostics"), QStringLiteral("system-maintenance")};
    for (const auto& route : routes) {
      QVERIFY2(window.navigate(route), qPrintable(route));
      QVERIFY(stack->currentWidget());
      const auto expected = route.startsWith(QStringLiteral("mission-")) ? QStringLiteral("MissionsPage")
          : route.startsWith(QStringLiteral("data-")) || route == QStringLiteral("acquisitions") ? QStringLiteral("DataPage")
          : route.startsWith(QStringLiteral("system-")) ? QStringLiteral("SystemPage")
          : route.startsWith(QStringLiteral("analysis-")) ? QStringLiteral("AnalysisPage")
          : route == QStringLiteral("bench-model") ? QStringLiteral("GazeboModelPage")
          : route == QStringLiteral("tests") || route == QStringLiteral("bench-configuration") ? QStringLiteral("ExecutionPage")
          : route == QStringLiteral("results") ? QStringLiteral("ResultsPage")
          : route == QStringLiteral("comparison") ? QStringLiteral("ComparisonPage") : QStringLiteral("overviewPage");
      QCOMPARE(stack->currentWidget()->objectName(), expected);
      capture(route);
    }
    QVERIFY(!window.navigate(QStringLiteral("unknown")));
    QVERIFY(window.navigate(QStringLiteral("mission-preparation")));
    auto* missionName = window.findChild<QLineEdit*>(QStringLiteral("missionNameEdit"));
    QVERIFY(missionName);
    missionName->setText(QStringLiteral("Préparation précédente"));
    QVERIFY(window.navigate(QStringLiteral("overview")));
    window.findChild<QPushButton*>(QStringLiteral("createMissionButton"))->click();
    QCOMPARE(stack->currentWidget()->objectName(), QStringLiteral("MissionsPage"));
    QVERIFY(missionName->text().isEmpty());
    window.previewTheme(QStringLiteral("premium"));
    QCOMPARE(window.property("stationTheme").toString(), QStringLiteral("premium"));
    QVERIFY(window.styleSheet().contains(QStringLiteral("#397a68")));
    QVERIFY(window.navigate(QStringLiteral("overview")));
    capture(QStringLiteral("premium-overview"));
    window.previewTheme(QStringLiteral("professional"));
    QCOMPARE(window.property("stationTheme").toString(), QStringLiteral("professional"));
    QVERIFY(window.styleSheet().contains(QStringLiteral("#286a96")));
    capture(QStringLiteral("professional-overview"));
    window.resize(1200, 760);
    QCOMPARE(window.width(), 1200);
    QCOMPARE(window.height(), 760);
    QVERIFY(window.navigate(QStringLiteral("mission-preparation")));
    capture(QStringLiteral("mission-compact"));
    QVERIFY(window.navigate(QStringLiteral("tests")));
    capture(QStringLiteral("bench-compact"));
  }
};
QTEST_MAIN(TestStationNavigation)
#include "TestStationNavigation.moc"
