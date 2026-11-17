#include "ResearchAdapter.hpp"

#include <QCryptographicHash>
#include <QDir>
#include <QJsonArray>
#include <QJsonDocument>
#include <QProcess>
#include <QStringList>

#include <stdexcept>

namespace architecture_decision {
namespace {

[[noreturn]] void fail(const QString &message)
{
    throw std::runtime_error(message.toStdString());
}

} // namespace

QJsonObject researchIssue(const QString &executable, const QString &root, const QString &store,
                          const QString &catalog, const QString &issueId)
{
    if (executable.isEmpty() || root.isEmpty() || store.isEmpty() || catalog.isEmpty() || issueId.isEmpty()) {
        fail(QStringLiteral("Exécutable, racine, registre, catalogue et identifiant L1 requis"));
    }

    const QDir directory(root);
    QProcess process;
    process.start(directory.absoluteFilePath(executable), {
        QStringLiteral("submit"),
        QStringLiteral("--root"), directory.absolutePath(),
        QStringLiteral("--store"), directory.absoluteFilePath(store),
        QStringLiteral("--catalog"), directory.absoluteFilePath(catalog),
        QStringLiteral("--issue"), issueId,
    });
    if (!process.waitForStarted(5000)) {
        fail(QStringLiteral("Démarrage de L1 impossible : %1").arg(process.errorString()));
    }
    if (process.state() != QProcess::NotRunning && !process.waitForFinished(30000)) {
        process.kill();
        process.waitForFinished(5000);
        fail(QStringLiteral("L1 n’a pas finalisé la recherche dans le délai : %1").arg(issueId));
    }

    const auto bytes = process.readAllStandardOutput();
    QJsonParseError parseError;
    const auto document = QJsonDocument::fromJson(bytes, &parseError);
    const auto report = document.object();
    if (process.exitStatus() != QProcess::NormalExit || process.exitCode() != 0) {
        auto detail = report.value(QStringLiteral("message")).toString();
        if (detail.isEmpty()) {
            detail = QString::fromUtf8(process.readAllStandardError().left(4096)).trimmed();
        }
        fail(QStringLiteral("Recherche L1 %1 interrompue (code %2) : %3")
                 .arg(issueId).arg(process.exitCode()).arg(detail));
    }

    const QStringList outcomes{QStringLiteral("RESOLVED"), QStringLiteral("UNKNOWN"),
                               QStringLiteral("INCONCLUSIVE"), QStringLiteral("CONDITIONAL")};
    if (parseError.error != QJsonParseError::NoError || !document.isObject()
        || report.value(QStringLiteral("schema_version")) != QStringLiteral("1.0.0")
        || report.value(QStringLiteral("issue_id")) != issueId
        || !outcomes.contains(report.value(QStringLiteral("outcome")).toString())
        || !report.value(QStringLiteral("question")).isObject()
        || !report.value(QStringLiteral("value")).isObject()
        || !report.value(QStringLiteral("local_inputs")).isArray()
        || report.value(QStringLiteral("local_inputs")).toArray().isEmpty()
        || !report.value(QStringLiteral("technical_evidence")).isArray()
        || !report.value(QStringLiteral("unknown_register")).isArray()) {
        fail(QStringLiteral("Rapport L1 incomplet ou hors demande : %1").arg(issueId));
    }

    const auto digest = QCryptographicHash::hash(bytes, QCryptographicHash::Sha256).toHex();
    return {{QStringLiteral("report"), report}, {QStringLiteral("sha256"), QString::fromLatin1(digest)}};
}

} // namespace architecture_decision
