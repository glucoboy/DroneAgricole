#include "AdmissionScopeFixture.hpp"
#include "Files.hpp"

#include <QCoreApplication>
#include <QFile>
#include <QFileInfo>
#include <QJsonArray>
#include <QProcess>
#include <QTemporaryDir>
#include <cstdio>

namespace {

using namespace convergence;
using admission_test::benchRequest;
using admission_test::cartographerRequest;
using admission_test::cartographerSandbox;

const auto writePermissions = QFileDevice::WriteOwner | QFileDevice::WriteUser |
    QFileDevice::WriteGroup | QFileDevice::WriteOther;

class BenchCopy {
public:
    BenchCopy(const QDir &directory, const QDir &source, const QJsonObject &dependencies)
        : directory_(directory), dependencies_(dependencies)
    {
        for (auto it = dependencies_.constBegin(); it != dependencies_.constEnd(); ++it) {
            const auto path = directory_.filePath(it.key());
            require(directory_.mkpath(QFileInfo(it.key()).path()) && QFile::copy(source.filePath(it.key()), path),
                    "Copie XLink du banc inaccessible : " + it.key());
            require(QFile::setPermissions(path, QFile::permissions(path) & ~writePermissions),
                    "Source du banc impossible à sceller : " + it.key());
        }
        verify();
    }

    ~BenchCopy()
    {
        for (const auto &name : dependencies_.keys()) {
            const auto path = directory_.filePath(name);
            QFile::setPermissions(path, QFile::permissions(path) | QFileDevice::WriteOwner);
        }
    }

    const QDir &directory() const { return directory_; }

    void verify() const
    {
        for (auto it = dependencies_.constBegin(); it != dependencies_.constEnd(); ++it) {
            require(fileDigest(directory_.filePath(it.key())) == it.value(), "Source du banc divergente : " + it.key());
        }
    }

private:
    QDir directory_;
    QJsonObject dependencies_;
};

struct ProcessResult {
    int code;
    QString diagnostic;
};

ProcessResult execute(const QString &executable, const QStringList &arguments)
{
    QProcess process;
    process.start(executable, arguments);
    const auto started = process.waitForStarted();
    require(started, "Démarrage impossible : " + executable + " / " + process.errorString());
    require(process.state() == QProcess::NotRunning || process.waitForFinished(),
            "Processus non terminé : " + executable + " / " + process.errorString());
    const auto diagnostic = QString::fromUtf8(process.readAllStandardOutput()) + ' ' +
        QString::fromLocal8Bit(process.readAllStandardError());
    require(process.exitStatus() == QProcess::NormalExit, "Processus interrompu : " + executable + diagnostic);
    return {process.exitCode(), diagnostic};
}

void invoke(const QString &executable, const QStringList &arguments, int expectedCode)
{
    const auto result = execute(executable, arguments);
    require(result.code == expectedCode, QString("Code L5 attendu %1, obtenu %2 : %3")
            .arg(expectedCode).arg(result.code).arg(result.diagnostic));
}

class AdmissionRun {
public:
    AdmissionRun(QString executable, QDir root, QDir workspace)
        : executable_(std::move(executable)), root_(std::move(root)), workspace_(std::move(workspace)) {}

    QStringList arguments(const QString &request, const QDir &sandbox, const QString &output) const
    {
        return {"v3-admission", "--root", root_.absolutePath(), "--request", request,
                "--sandbox", sandbox.absolutePath(), "--output", output};
    }

    QJsonObject check(const QString &name, const QJsonObject &request, const QDir &sandbox,
                      int code, const QString &decision, const QString &status)
    {
        const auto requestPath = workspace_.filePath(name + ".json");
        const auto sha = write(requestPath, request);
        const QDir output(workspace_.filePath(name));
        invoke(executable_, arguments(requestPath, sandbox, output.absolutePath()), code);
        const auto receiptPath = output.filePath("admission.json");
        const auto report = load(receiptPath);
        const auto verdict = report.value("admission").toObject();
        require(report.value("schema") == "v3.l5_admission_receipt/1" && report.value("request_sha256") == sha &&
                verdict.value("decision") == decision && report.value("dispatch_status") == status &&
                report.value("candidate_transactions") == 0 && report.value("construction_result") == "NOT_RUN",
                "Reçu L5 incohérent : " + name + " / " + verdict.value("reason").toString());
        require(output.entryList(QDir::AllEntries | QDir::System | QDir::Hidden | QDir::NoDotAndDotDot) ==
                QStringList{"admission.json"}, "Le dispatcher V3 a écrit une sortie de construction");
        std::printf("%s %s %s %s\n", name.toLatin1().constData(), decision.toLatin1().constData(),
                    verdict.value("reason").toString().toLatin1().constData(), status.toLatin1().constData());
        trace_.append(QJsonObject{{"case", name}, {"exit_code", code}, {"receipt_sha256", fileDigest(receiptPath)},
            {"dispatch_status", status}, {"candidate_transactions", report.value("candidate_transactions")},
            {"construction_result", report.value("construction_result")}, {"decision", decision},
            {"reason", verdict.value("reason")}, {"context_sha256", verdict.value("context_sha256")}});
        return report;
    }

    const QJsonArray &trace() const { return trace_; }

private:
    QString executable_;
    QDir root_, workspace_;
    QJsonArray trace_;
};

QJsonObject testEntry(const QString &executable)
{
    const QDir root(QDir::current().canonicalPath());
    require(root.mkpath(".runtime"), "Dossier de preuves local inaccessible");
    QTemporaryDir temporary(root.filePath(".runtime/l5-v3-entry-XXXXXX"));
    require(temporary.isValid(), "Impossible d'isoler l'essai L5");
    const QDir work(temporary.path());
    const QDir fixture(root.filePath("docs/electromechanical_v3/bench_a1"));
    const auto request = benchRequest(root, "REPOSITION_DEVICE");
    const auto dependencies = request.value("xlink_dependencies").toObject();
    const BenchCopy first(QDir(work.filePath("bench-a")), fixture, dependencies);
    const BenchCopy second(QDir(work.filePath("bench-b")), fixture, dependencies);
    AdmissionRun run(executable, root, work);

    const auto valid = run.check("allow", request, first.directory(), 3, "ALLOW", "NOT_IMPLEMENTED");
    require(run.check("transfer", request, second.directory(), 3, "ALLOW", "NOT_IMPLEMENTED") == valid,
            "La décision L5 a changé entre deux copies à octets identiques");
    for (const auto &operation : {"REROUTE_HARNESS", "RELOCATE_SUPPORT", "CREATE_SUPPORT"}) {
        run.check(operation, benchRequest(root, operation), first.directory(), 3, "ALLOW", "NOT_IMPLEMENTED");
    }

    auto forgedRequest = request;
    forgedRequest.insert("allowed", true);
    run.check("auto-attestation", forgedRequest, first.directory(), 2, "DENY", "BLOCKED");

    auto forgedReport = valid;
    auto forgedAdmission = forgedReport.value("admission").toObject();
    forgedAdmission.insert("allowed", true);
    forgedReport.insert("admission", forgedAdmission);
    write(work.filePath("allow/admission.json"), forgedReport);
    invoke(executable, run.arguments(work.filePath("allow.json"), first.directory(), work.filePath("allow")), 1);
    require(load(work.filePath("allow/admission.json")) == forgedReport, "Un reçu altéré a été utilisé à la reprise");
    run.check("receipt-as-request", forgedReport, first.directory(), 2, "UNSUPPORTED", "BLOCKED");

    const auto cartographer = cartographerSandbox(root);
    if (cartographer.exists()) {
        run.check("virtual-impact", cartographerRequest(root), cartographer, 0, "ALLOW", "READ_ONLY");
    }

    const auto approvedRequest = work.filePath("allow.json");
    const auto forbidden = first.directory().filePath("redirect");
    QString junctionStatus = "NOT_APPLICABLE";
    QString junctionDiagnostic;
    invoke(executable, run.arguments(approvedRequest, first.directory(), forbidden), 1);
    invoke(executable, run.arguments(approvedRequest, first.directory(), first.directory().filePath("../bench-a/redirect")), 1);
    invoke(executable, run.arguments(approvedRequest, first.directory(), work.absolutePath()), 1);
#ifdef Q_OS_WIN
    invoke(executable, run.arguments(approvedRequest, first.directory(),
        first.directory().absolutePath() + "./redirect"), 1);
    invoke(executable, run.arguments(approvedRequest, first.directory(),
        first.directory().absolutePath() + " /redirect"), 1);
    const auto junction = work.filePath("bench-junction");
    const auto created = execute(QString::fromLocal8Bit(qgetenv("ComSpec")),
        {"/d", "/c", "mklink", "/J", QDir::toNativeSeparators(junction),
         QDir::toNativeSeparators(first.directory().absolutePath())});
    if (created.code == 0) {
        temporary.setAutoRemove(false);
        try {
            require(QFileInfo(junction).isJunction(), "La jonction d'essai doit exister");
            invoke(executable, run.arguments(approvedRequest, first.directory(), junction + "/redirect"), 1);
            invoke(executable, run.arguments(approvedRequest, first.directory(), junction), 1);
            invoke(executable, run.arguments(approvedRequest, QDir(junction), work.filePath("aliased-sandbox")), 1);
        } catch (...) {
            if (work.rmdir("bench-junction")) {
                temporary.setAutoRemove(true);
            }
            throw;
        }
        require(work.rmdir("bench-junction"), "Suppression de la jonction d'essai impossible");
        temporary.setAutoRemove(true);
        junctionStatus = "PASS";
        std::puts("junction-redirections PASS");
    } else {
        require(!QFileInfo::exists(junction), "Jonction partiellement créée");
        junctionStatus = "NOT_RUN";
        junctionDiagnostic = created.diagnostic.trimmed();
        std::printf("junction-redirections NOT_RUN (%s)\n", junctionDiagnostic.toUtf8().constData());
    }
#endif
    require(!QFileInfo::exists(forbidden), "Le sandbox XLink a reçu un dossier de campagne");
    const auto legacyOutput = work.filePath("legacy");
    invoke(executable, {"run", "--root", root.absolutePath(), "--config", approvedRequest,
                        "--output", legacyOutput}, 1);
    require(!QFileInfo::exists(legacyOutput), "Une demande V3 a atteint la campagne historique");

    first.verify();
    second.verify();
    return {{"schema", "v3.l5_admission_entry_trace/1"}, {"cases", run.trace()},
        {"tampered_receipt_reuse", "BLOCKED"}, {"legacy_configuration", "BLOCKED"},
        {"sandbox_output_redirections", "BLOCKED"}, {"junction_redirections", junctionStatus},
        {"junction_diagnostic", junctionDiagnostic}, {"source_bytes_unchanged", true}};
}

} // namespace

int main(int argc, char **argv)
{
    const QCoreApplication app(argc, argv);
    try {
        require(app.arguments().size() == 3, "Exécutable L5 et destination de la trace requis");
        write(app.arguments().at(2), testEntry(app.arguments().at(1)));
        return 0;
    } catch (const std::exception &error) {
        std::fprintf(stderr, "%s\n", error.what());
        return 1;
    }
}
