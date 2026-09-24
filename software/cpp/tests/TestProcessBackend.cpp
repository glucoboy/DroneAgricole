#include "drone_agricole/adapters/ProcessRunBackend.hpp"
#include <QtTest>
using namespace drone_agricole;
class TestProcessBackend : public QObject {
  Q_OBJECT
 private slots:
  void failedLaunchCompletesOnce() {
    adapters::ProcessRunBackend backend;
    QSignalSpy done(&backend, &application::IRunBackend::finished);
    domain::PreparedRun run; run.program = QStringLiteral("/nonexistent/drone-agricole-test");
    backend.start(run);
    QTRY_COMPARE(done.count(), 1);
    QVERIFY(!done.first().at(1).toBool());
  }
  void runsAndCancelsWithoutBlockingEventLoop() {
    adapters::ProcessRunBackend backend;
    QSignalSpy done(&backend, &application::IRunBackend::finished);
    QSignalSpy started(&backend, &application::IRunBackend::started);
    domain::PreparedRun run;
    run.program = QCoreApplication::applicationFilePath();
    run.arguments = {QStringLiteral("--child-wait")};
    run.stopProgram = QCoreApplication::applicationFilePath();
    run.stopArguments = {QStringLiteral("--child-success")};
    backend.start(run);
    QTRY_COMPARE(started.count(), 1);
    backend.cancel();
    QTRY_COMPARE_WITH_TIMEOUT(done.count(), 1, 20000);
    run.arguments = {QStringLiteral("--child-success")};
    backend.start(run);
    QTRY_COMPARE(done.count(), 2);
    QCOMPARE(done.last().at(0).toInt(), 0);
    QVERIFY(done.last().at(1).toBool());
  }
};
int main(int argc, char** argv) {
  QCoreApplication app(argc, argv);
  if (app.arguments().contains(QStringLiteral("--child-success"))) return 0;
  if (app.arguments().contains(QStringLiteral("--child-wait"))) return app.exec();
  TestProcessBackend test;
  return QTest::qExec(&test, argc, argv);
}
#include "TestProcessBackend.moc"
