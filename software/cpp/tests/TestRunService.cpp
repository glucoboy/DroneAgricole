#include "drone_agricole/application/RunService.hpp"
#include <QtTest>
#include <stdexcept>
using namespace drone_agricole;
namespace {
struct Preparation : application::IRunPreparation {
  bool fail{false};
  domain::PreparedRun prepare(const QJsonObject&) override {
    if (fail) throw std::runtime_error("Invalid request");
    domain::PreparedRun run;
    run.runId = QStringLiteral("test");
    return run;
  }
};
struct Finalizer : application::IResultFinalizer {
  int calls{0}; bool fail{false};
  void finalize(const domain::PreparedRun&) override {
    ++calls;
    if (fail) throw std::runtime_error("Disk full");
  }
};
struct Backend : application::IRunBackend {
  int starts{0}; int cancels{0};
  bool confirmed{true};
  bool cancellationConfirmed() const override { return confirmed; }
  void start(const domain::PreparedRun&) override { ++starts; emit started(); }
  void cancel() override { ++cancels; }
};
}
class TestRunService : public QObject {
  Q_OBJECT
 private slots:
  void completesOnlyAfterFinalization() {
    Preparation preparation; Finalizer finalizer; Backend backend;
    application::RunService service(preparation, backend, finalizer);
    QSignalSpy done(&service, &application::RunService::completed);
    QVERIFY(service.start({}));
    QVERIFY(service.active());
    QVERIFY(!service.start({}));
    emit backend.output(QStringLiteral("MAP_PROGRESS stage=complete percent=100\n"));
    QCOMPARE(service.progress(), 99);
    emit backend.finished(0, true);
    QCOMPARE(finalizer.calls, 1);
    QCOMPARE(service.state(), domain::RunState::Completed);
    QCOMPARE(service.progress(), 100);
    QCOMPARE(done.count(), 1);
    emit backend.finished(0, true);
    QCOMPARE(done.count(), 1);
  }
  void cancellationDoesNotBecomeSuccess() {
    Preparation preparation; Finalizer finalizer; Backend backend;
    application::RunService service(preparation, backend, finalizer);
    service.start({}); service.cancel(); service.cancel();
    QCOMPARE(backend.cancels, 1);
    QVERIFY(service.active());
    emit backend.finished(0, true);
    QCOMPARE(service.state(), domain::RunState::Cancelled);
    QCOMPARE(finalizer.calls, 0);
    QVERIFY(service.start({}));
    QCOMPARE(backend.starts, 2);
  }
  void reportsArchiveFailure() {
    Preparation preparation; Finalizer finalizer; Backend backend;
    finalizer.fail = true;
    application::RunService service(preparation, backend, finalizer);
    service.start({}); emit backend.finished(0, true);
    QCOMPARE(service.state(), domain::RunState::Failed);
    QVERIFY(service.message().contains(QStringLiteral("finalisation en échec")));
    QVERIFY(service.run().has_value());
    QVERIFY(!service.active());
  }
  void remoteCancellationRequiresConfirmation() {
    Preparation preparation; Finalizer finalizer; Backend backend;
    backend.confirmed = false;
    application::RunService service(preparation, backend, finalizer);
    service.start({}); service.cancel(); emit backend.finished(0, true);
    QCOMPARE(service.state(), domain::RunState::Failed);
    QCOMPARE(finalizer.calls, 0);
    QVERIFY(service.message().contains(QStringLiteral("non confirmée")));
  }
  void rejectsInvalidPreparationAndProcessFailure() {
    Preparation preparation; Finalizer finalizer; Backend backend;
    preparation.fail = true;
    application::RunService service(preparation, backend, finalizer);
    QVERIFY(!service.start({}));
    QCOMPARE(backend.starts, 0);
    QCOMPARE(service.state(), domain::RunState::Failed);
    preparation.fail = false;
    QVERIFY(service.start({}));
    emit backend.finished(-1, false);
    QCOMPARE(finalizer.calls, 0);
    QCOMPARE(service.state(), domain::RunState::Failed);
  }
  void acceptsFragmentedProgressAndClearsItBetweenRuns() {
    Preparation preparation; Finalizer finalizer; Backend backend;
    application::RunService service(preparation, backend, finalizer);
    service.start({});
    emit backend.output(QStringLiteral("noise\nMAP_PROG"));
    emit backend.output(QStringLiteral("RESS stage=rows percent=42\n"));
    QCOMPARE(service.progress(), 42);
    emit backend.finished(1, true);
    service.start({});
    QCOMPARE(service.progress(), 0);
  }
};
QTEST_GUILESS_MAIN(TestRunService)
#include "TestRunService.moc"
