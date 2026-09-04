#include "drone_agricole/core/ComparisonService.hpp"
#include "drone_agricole/core/JsonUtils.hpp"

#include <QtTest>

using namespace drone_agricole::core;

class TestComparisonService final : public QObject {
  Q_OBJECT

 private slots:
  void reproducesReferenceComparison() {
    ResultRepository repository(QStringLiteral(DRONE_AGRICOLE_TEST_WORKSPACE));
    repository.refresh();
    ComparisonService service(repository);
    const QStringList ids{QStringLiteral("616a651e56ecf7cdabc2"), QStringLiteral("71b764de730415dfd7b2"),
                          QStringLiteral("f1f0987303f73f1d51c1")};
    const auto comparison = service.preview(ids);
    QVERIFY(comparison.value(QStringLiteral("compatibility")).toObject().value(QStringLiteral("compatible")).toBool());
    QCOMPARE(comparison.value(QStringLiteral("runs")).toArray().size(), 3);
    QCOMPARE(comparison.value(QStringLiteral("metrics")).toArray().size(), 10);
    QCOMPARE(comparison.value(QStringLiteral("parameters")).toArray().size(), 14);
    const auto report = service.report(ids);
    QVERIFY(report.contains(QStringLiteral("# Rapport de comparaison T0.4")));
    QVERIFY(report.contains(QStringLiteral("Compatibilité : **validée**")));
    QVERIFY(report.contains(QStringLiteral("ATE translation RMSE")));
  }

  void rejectsBadSelections() {
    ResultRepository repository(QStringLiteral(DRONE_AGRICOLE_TEST_WORKSPACE));
    repository.refresh();
    ComparisonService service(repository);
    QVERIFY_EXCEPTION_THROWN(static_cast<void>(service.preview({QStringLiteral("one")})), ContractError);
    QVERIFY_EXCEPTION_THROWN(
        static_cast<void>(service.preview({QStringLiteral("same"), QStringLiteral("same")})), ContractError);
  }
};

QTEST_APPLESS_MAIN(TestComparisonService)
#include "TestComparisonService.moc"
