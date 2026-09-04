#include "drone_agricole/core/ResultRepository.hpp"
#include "drone_agricole/core/ResultAdapter.hpp"
#include "drone_agricole/core/JsonUtils.hpp"

#include <QtTest>

#include <QTemporaryDir>

#include <algorithm>

using namespace drone_agricole::core;

class TestResultRepository final : public QObject {
  Q_OBJECT

 private slots:
  void rebuildsRealIndexWithoutWriting() {
    ResultRepository repository(QStringLiteral(DRONE_AGRICOLE_TEST_WORKSPACE));
    repository.refresh();
    QVERIFY(repository.totalCount() >= 59);
    QCOMPARE(repository.invalidResultCount(), 0);
    const auto localization = repository.search(SearchFilters{QStringLiteral("localization")});
    const auto flight = repository.search(SearchFilters{QStringLiteral("flight_simulation")});
    QVERIFY(localization.size() >= 52);
    QVERIFY(flight.size() >= 7);
    QCOMPARE(repository.totalCount(), localization.size() + flight.size());
  }

  void opensReferenceResults() {
    ResultRepository repository(QStringLiteral(DRONE_AGRICOLE_TEST_WORKSPACE));
    repository.refresh();
    const auto results = repository.search(SearchFilters{QStringLiteral("localization")});
    const QHash<QString, QString> expected{
        {QStringLiteral("fast_lio2"), QStringLiteral("616a651e56ecf7cdabc2")},
        {QStringLiteral("point_lio"), QStringLiteral("71b764de730415dfd7b2")},
        {QStringLiteral("lio_sam"), QStringLiteral("f1f0987303f73f1d51c1")},
    };
    for (auto iterator = expected.cbegin(); iterator != expected.cend(); ++iterator) {
      const auto found = std::find_if(results.cbegin(), results.cend(), [&](const auto& value) {
        return value.resultId == iterator.value();
      });
      QVERIFY(found != results.cend());
      QCOMPARE(found->variantId, iterator.key());
      QCOMPARE(found->state, QStringLiteral("completed"));
      QVERIFY(found->replayAvailable);
      QCOMPARE(repository.detail(found->resultId).metrics.value(QStringLiteral("summary")).toArray().size(), 10);
    }
  }

  void linksNativeManifestToExactRequest() {
    QTemporaryDir directory;
    QVERIFY(directory.isValid());
    const QJsonObject sourceManifest{
        {QStringLiteral("schema"), QStringLiteral("drone_agricole.run_manifest.v1")},
        {QStringLiteral("run_id"), QStringLiteral("sw0_test")},
        {QStringLiteral("request_id"), QJsonValue::Null},
        {QStringLiteral("parameters"), QJsonObject{{QStringLiteral("stage_timeout_s"), 10.0}}},
    };
    const NormalizedResult result{QStringLiteral("test"), directory.path(), sourceManifest,
                                  QJsonObject{{QStringLiteral("schema"), QStringLiteral("drone_agricole.metrics.v1")}},
                                  QJsonObject{{QStringLiteral("schema"), QStringLiteral("drone_agricole.artifacts.v1")}},
                                  QJsonArray{}};
    const QJsonObject request{
        {QStringLiteral("schema"), QStringLiteral("drone_agricole.run_request.v1")},
        {QStringLiteral("request_id"), QStringLiteral("request_sw0_test")},
        {QStringLiteral("parameters"), QJsonObject{{QStringLiteral("stage_timeout_s"), 12.0}}},
    };
    writeNativeContracts(result, request);
    const auto manifest = readJsonObject(directory.filePath(QStringLiteral("t0_run_manifest.json")));
    QCOMPARE(manifest.value(QStringLiteral("request_id")).toString(), QStringLiteral("request_sw0_test"));
    QCOMPARE(manifest.value(QStringLiteral("parameters")).toObject().value(QStringLiteral("stage_timeout_s")).toDouble(),
             12.0);
  }
};

QTEST_APPLESS_MAIN(TestResultRepository)
#include "TestResultRepository.moc"
