#include "A6Transaction.hpp"

#include "A6Journal.hpp"
#include "AuthorityReview.hpp"
#include "Files.hpp"
#include "V3Transaction.hpp"

#include <QFileInfo>
#include <QJsonDocument>
#include <QSaveFile>
#include <QTemporaryDir>
#include <QThread>
#include <cstdlib>
#include <memory>
#include <filesystem>

namespace convergence {
namespace {

constexpr auto receiptName = "admission.json";

bool faultEnabled(const QByteArray &point)
{
#ifdef V3_A6_FAULT_INJECTION
    return qgetenv("L5_A6_TEST_FAULT") == point;
#else
    Q_UNUSED(point);
    return false;
#endif
}

void crashAt(const QByteArray &point)
{
    if (faultEnabled(point))
        std::_Exit(86);
}

void publish(const QDir &output, const QByteArray &bytes)
{
    QSaveFile file(output.filePath(receiptName));
    require(file.open(QIODevice::WriteOnly), "A6_RECEIPT_OPEN_FAILED");
    if (faultEnabled("during-publication")) {
        require(file.write(bytes.left(bytes.size() / 2)) == bytes.size() / 2 && file.flush(),
                "A6_RECEIPT_WRITE_FAILED");
        std::_Exit(86);
    }
    require(file.write(bytes) == bytes.size() && file.commit(), "A6_RECEIPT_WRITE_FAILED");
}

QString checkedHash(const QDir &directory, const QString &name)
{
    const auto path = directory.filePath(name);
    require(!hasRedirectedComponent(directory, path) && fileInside(directory, name) == path &&
            std::filesystem::hard_link_count(QFileInfo(path).filesystemFilePath()) == 1,
            "A6_ARTIFACT_REDIRECTED");
    return fileDigest(path);
}

QJsonObject sealEvidence(const QDir &attempt, const QJsonObject &native)
{
    const QDir transaction(attempt.filePath("transaction"));
    require(transaction.canonicalPath() == transaction.absolutePath() &&
            !hasRedirectedComponent(attempt, transaction.absolutePath()), "A6_PRIVATE_EVIDENCE_UNAVAILABLE");
    const auto nativeHashes = native.value("native_sha256").toObject();
    require(!nativeHashes.isEmpty(), "A6_EMPTY_NATIVE_EVIDENCE");
    QJsonObject result;
    for (auto it = nativeHashes.begin(); it != nativeHashes.end(); ++it) {
        const auto name = "cad/" + it.key();
        const auto hash = checkedHash(transaction, name);
        require(hash == it.value(), "A6_NATIVE_ARTIFACT_CHANGED");
        result.insert(name, hash);
    }
    for (const auto &name : {"campaign.json", "build.json", "candidate-validation.json", "t0_run_manifest.json",
                             "t0_metrics.json", "events.jsonl", "artifacts.json", "t0-crosscheck.json",
                             "build-job.json", "candidate-job.json", "mutation-plan.json", "baseline-job.json",
                             "baseline-validation.json", "journal.json", "run_request.json"}) {
        result.insert(name, checkedHash(transaction, name));
    }
    return result;
}

} // namespace

int runAuthorizedTransaction(const QDir &root, const QDir &sandbox, const QDir &output,
                             const QString &requestPath, const QByteArray &requestBytes, const QJsonObject &request,
                             const QString &trustPath, const QString &trustSha256)
{
    const auto requestHash = digest(requestBytes);
    const auto freecad = QStringLiteral(V3_A6_FREECAD);
    const auto t0 = QStringLiteral(V3_A6_T0);
    std::unique_ptr<A6Journal> journal;
    AuthorizedReview authorized;
    bool reservationStarted = false;
    const auto initialRegistry = [&](const AuthorizedReview &review, const QJsonArray &events,
                                     const QDateTime &now, const QString &denial) {
        journal = std::make_unique<A6Journal>(review.trusted, review.journalKeySha256, now);
        journal->observeRegistry(events, now);
        authorized = review;
        if (!denial.isEmpty())
            return;
        require(QDir(root).canonicalPath() == QStringLiteral(V3_A6_CHECKOUT) &&
                QFileInfo(freecad).isExecutable() && QFileInfo(t0).isExecutable(),
                "A6_NATIVE_TOOLS_NOT_CONFIGURED");
        require(journal->state(review.decisionId).isEmpty(), "DECISION_ALREADY_USED");
        reservationStarted = true;
        journal->reserve(review.decisionId, review.reviewSha256, review.requestSha256);
    };
    auto report = verifyAuthorityReview(root, sandbox, request, requestHash, trustPath, trustSha256, true,
                                        initialRegistry);
    const auto admission = report.value("admission").toObject();
    const auto state = [&] { return journal ? journal->state(authorized.decisionId) : QString(); };
    const auto quarantine = [&](const QString &reason) {
        const auto previous = state();
        if (reservationStarted && !previous.isEmpty() && previous != "COMMITTED_PRIVATE" &&
                previous != "QUARANTINED" && previous != "ABORTED") {
            journal->transition(authorized.decisionId, "QUARANTINED", {{"reason", reason}});
        }
    };
    if (admission.value("decision") != "ALLOW") {
        quarantine(report.value("reason").toString());
        report.insert("transaction_state", state().isEmpty() ? "NOT_RESERVED" : state());
        write(output.filePath(receiptName), report);
        return 2;
    }

    const auto preliminary = report;
    QJsonObject native;
    try {
        require(reservationStarted && state() == "AUTHORIZED_RESERVED", "A6_RESERVATION_MISSING");
        crashAt("before-launch");
        if (faultEnabled("hold-after-reserve"))
            QThread::msleep(4000);

        QTemporaryDir storage(output.filePath(".private-XXXXXX"));
        require(storage.isValid(), "A6_PRIVATE_WORKSPACE_UNAVAILABLE");
        storage.setAutoRemove(false);
        const QDir attempt(storage.path());
        const auto checkpoint = [&](const QString &next, const QJsonObject &detail) {
            journal->transition(authorized.decisionId, next, detail);
            if (next == "BUILT")
                crashAt("after-build");
        };
        native = runV3AuthorizedNative(root, sandbox, attempt, authorized, freecad, t0,
                                       checkpoint, faultEnabled("during-native-save"));
        require(native.value("status") == "PASS" && state() == "INDEPENDENTLY_VALIDATED",
                "A6_INDEPENDENT_VALIDATION_INCOMPLETE");
        const auto evidence = sealEvidence(attempt, native);

        QByteArray receipt;
        const auto finalizeRegistry = [&](const AuthorizedReview &review, const QJsonArray &events,
                                          const QDateTime &now, const QString &denial) {
            require(review.reviewSha256 == authorized.reviewSha256 && review.decisionId == authorized.decisionId &&
                    review.trustSha256 == authorized.trustSha256 && review.requestSha256 == authorized.requestSha256,
                    "A6_AUTHORITY_CHANGED_AFTER_RESERVATION");
            journal->observeRegistry(events, now);
            if (!denial.isEmpty())
                return;
            require(checkedHash(root, relative(root, requestPath)) == requestHash, "A6_REQUEST_CHANGED_BEFORE_COMMIT");
            require(sealEvidence(attempt, native) == evidence, "A6_EVIDENCE_CHANGED_BEFORE_COMMIT");
            require(review.expiresAt > QDateTime::currentDateTimeUtc(), "A6_REVIEW_EXPIRED_BEFORE_COMMIT");
            report.insert("transaction_state", "COMMITTED_PRIVATE");
            report.insert("candidate_transactions", 1);
            report.insert("construction_result", "PASS");
            report.insert("native_validation", "PASS");
            report.insert("registry_sha256", review.registrySha256);
            report.insert("publication", QJsonObject{{"schema", "v3.a6.private_evidence/1"},
                {"directory", relative(output, attempt.filePath("transaction"))}, {"sha256", evidence}});
            receipt = QJsonDocument(report).toJson(QJsonDocument::Indented);
            journal->transition(authorized.decisionId, "COMMITTED_PRIVATE",
                                {{"receipt_sha256", digest(receipt)}, {"receipt", report}});
        };
        const auto finalAuthority = verifyAuthorityReview(root, sandbox, request, requestHash, trustPath, trustSha256,
                                                           true, finalizeRegistry, true);
        require(finalAuthority.value("admission").toObject().value("decision") == "ALLOW" &&
                !receipt.isEmpty() && state() == "COMMITTED_PRIVATE",
                "A6_FINAL_AUTHORITY_DENIED/" + finalAuthority.value("reason").toString());
        publish(output, receipt);
        return 0;
    } catch (const std::exception &error) {
        if (state() == "COMMITTED_PRIVATE")
            throw;
        const auto reason = QString::fromUtf8(error.what());
        quarantine(reason);
        report = preliminary;
        report.insert("authority_decision", admission);
        report.insert("authority", "DENY");
        report.insert("admission", QJsonObject{{"decision", "DENY"}, {"execution_scope", "READ_ONLY_IMPACT"}});
        report.insert("reason", reason);
        report.insert("transaction_state", state());
        report.insert("construction_result", native.value("construction_result").toString(
            state() == "QUARANTINED" ? "INCONCLUSIVE" : "NOT_RUN"));
        if (native.contains("reason"))
            report.insert("native_reason", native.value("reason"));
        write(output.filePath(receiptName), report);
        return 2;
    }
}

} // namespace convergence
