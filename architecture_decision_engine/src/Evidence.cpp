#include "Evidence.hpp"

#include <QCryptographicHash>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QJsonDocument>
#include <QSaveFile>
#include <QUuid>
#include <stdexcept>

namespace architecture_decision {
namespace {

const QString requestFile = "run_request.json";
const QString manifestFile = "t0_run_manifest.json";
const QString metricsFile = "t0_metrics.json";
const QString eventsFile = "events.jsonl";
const QString artifactsFile = "artifacts.json";
const QString campaignFile = "campaign.json";

QString digest(const QByteArray &bytes)
{
    return QString::fromLatin1(QCryptographicHash::hash(bytes, QCryptographicHash::Sha256).toHex());
}

QString fileDigest(const QString &path)
{
    QFile input(path);
    QCryptographicHash hash(QCryptographicHash::Sha256);
    if (!input.open(QIODevice::ReadOnly) || !hash.addData(&input)) {
        throw std::runtime_error(("Lecture T0 impossible : " + path).toStdString());
    }
    return QString::fromLatin1(hash.result().toHex());
}

QString writeNew(const QDir &output, const QString &name, const QByteArray &bytes)
{
    const auto path = output.filePath(name);
    QSaveFile file(path);
    if (QFileInfo::exists(path) || !file.open(QIODevice::WriteOnly) ||
        file.write(bytes) != bytes.size() || !file.commit()) {
        throw std::runtime_error(("Publication T0 impossible : " + path).toStdString());
    }
    return digest(bytes);
}

QString stamp(const QDateTime &time)
{
    return time.toString(Qt::ISODateWithMs);
}

QJsonObject artifact(const QString &id, const QString &path, const QString &kind, const QString &role,
                     const QString &mediaType, const QString &sha256)
{
    return {{"artifact_id", id}, {"kind", kind}, {"label", path}, {"path", path},
            {"media_type", mediaType}, {"role", role}, {"replayable", true}, {"checksum_sha256", sha256}};
}

} // namespace

Evidence::Evidence(const QString &output, const QJsonArray &inputs, const QJsonObject &parameters,
                   const QJsonObject &software, const EvidenceContext &context)
    : output_(QDir(output).canonicalPath()),
      runId_(context.lot + '-' + QUuid::createUuid().toString(QUuid::WithoutBraces)),
      software_(software), context_(context)
{
    if (output_.isEmpty()) {
        throw std::runtime_error("Répertoire d’exécution T0 introuvable");
    }
    request_ = {{"schema", "drone_agricole.run_request.v1"}, {"request_id", runId_ + "-request"},
                {"simulation_id", "electromechanical_" + context_.lot}, {"variant_id", context_.variant},
                {"requested_at_utc", stamp(QDateTime::currentDateTimeUtc())},
                {"inputs", inputs}, {"parameters", parameters}};
    requestDigest_ = writeNew(QDir(output_), requestFile, QJsonDocument(request_).toJson());
    startedAt_ = QDateTime::currentDateTimeUtc();
}

void Evidence::finalize(const QJsonObject &campaign, const QMap<QString, QString> &published)
{
    const auto verdict = campaign.value("verdict").toString();
    const auto lot = context_.lot.toUpper();
    const auto pass = lot + "_PASS";
    const auto fail = context_.failedVerdict.isEmpty() ? lot + "_FAIL" : context_.failedVerdict;
    if (campaign.value("finalized") != true ||
        !QStringList{pass, lot + "_CONDITIONAL", fail}.contains(verdict) ||
        !published.contains(campaignFile)) {
        throw std::runtime_error("Résultat de campagne incomplet pour la finalisation T0");
    }
    const QDir output(output_);
    if (fileDigest(output.filePath(requestFile)) != requestDigest_) {
        throw std::runtime_error("Requête T0 modifiée durant l’exécution");
    }
    QFile campaignInput(output.filePath(campaignFile));
    if (!campaignInput.open(QIODevice::ReadOnly) ||
        QJsonDocument::fromJson(campaignInput.readAll()).object() != campaign) {
        throw std::runtime_error("Campagne publiée différente du résultat final");
    }

    QJsonArray items{artifact("request", requestFile, "configuration", "input", "application/json", requestDigest_)};
    qsizetype proofNumber = 0;
    const QStringList reserved{requestFile, manifestFile, metricsFile, eventsFile, artifactsFile};
    for (auto it = published.cbegin(); it != published.cend(); ++it) {
        const auto path = it.key();
        const auto canonical = QFileInfo(output.filePath(path)).canonicalFilePath();
        if (path.isEmpty() || path.contains('\\') || path.contains(':') || QDir::isAbsolutePath(path) ||
            path != QDir::cleanPath(path) || reserved.contains(path, Qt::CaseInsensitive) ||
            !canonical.startsWith(output_ + "/") || fileDigest(canonical) != it.value()) {
            throw std::runtime_error(("Artefact invalide ou modifié : " + path).toStdString());
        }
        const auto id = "proof-" + QString::number(++proofNumber);
        const auto isView = path.endsWith(".svg");
        const auto isNative = path.endsWith(".FCStd", Qt::CaseInsensitive);
        const auto mediaType = isView ? "image/svg+xml" : isNative ? "application/zip" :
            path.endsWith(".md") ? "text/markdown" :
            path.endsWith(".jsonl") ? "application/x-ndjson" : "application/json";
        items.append(artifact(id, path, isView ? "image" : isNative ? "model" : "report", isView ? "visualization" : "output",
                              mediaType, it.value()));
    }

    const auto finishedAt = QDateTime::currentDateTimeUtc();
    const QJsonObject metrics{{"schema", "drone_agricole.metrics.v1"}, {"run_id", runId_},
        {"simulation_id", request_.value("simulation_id")}, {"status", "complete"},
        {"summary", QJsonArray{QJsonObject{{"metric_id", context_.lot + "_verdict"}, {"label", "Verdict " + lot},
            {"value", verdict}, {"unit", ""}, {"direction", "neutral"},
            {"status", verdict == pass ? "good" : verdict == fail ? "error" : "warning"}}}},
        {"groups", QJsonObject{}}, {"source", QJsonObject{{"path", campaignFile}}}};
    items.append(artifact("metrics", metricsFile, "metrics", "output", "application/json",
                          writeNew(output, metricsFile, QJsonDocument(metrics).toJson())));

    const QJsonObject started{{"schema", "drone_agricole.event.v1"}, {"run_id", runId_},
        {"sequence", 0}, {"timestamp_utc", stamp(startedAt_)}, {"event_type", "campaign_started"},
        {"severity", "info"}, {"state", "running"}, {"message", context_.startedMessage},
        {"data", QJsonObject{}}};
    const QJsonObject finished{{"schema", "drone_agricole.event.v1"}, {"run_id", runId_},
        {"sequence", 1}, {"timestamp_utc", stamp(finishedAt)}, {"event_type", "campaign_finalized"},
        {"severity", "info"}, {"state", "completed"}, {"message", context_.finishedMessage},
        {"data", QJsonObject{{"verdict", verdict}, {"campaign_sha256", published.value(campaignFile)}}}};
    const auto events = QJsonDocument(started).toJson(QJsonDocument::Compact) + '\n' +
        QJsonDocument(finished).toJson(QJsonDocument::Compact) + '\n';
    items.append(artifact("events", eventsFile, "events", "diagnostic", "application/x-ndjson",
                          writeNew(output, eventsFile, events)));

    const QJsonObject artifacts{{"schema", "drone_agricole.artifacts.v1"}, {"run_id", runId_}, {"items", items}};
    writeNew(output, artifactsFile, QJsonDocument(artifacts).toJson());

    const QJsonObject manifest{{"schema", "drone_agricole.run_manifest.v1"}, {"run_id", runId_},
        {"request_id", request_.value("request_id")}, {"simulation_id", request_.value("simulation_id")},
        {"variant_id", request_.value("variant_id")}, {"runner_id", context_.runner},
        {"domain", "electromechanical"}, {"state", "completed"},
        {"created_at_utc", request_.value("requested_at_utc")}, {"started_at_utc", stamp(startedAt_)},
        {"finished_at_utc", stamp(finishedAt)}, {"inputs", request_.value("inputs")},
        {"parameters", request_.value("parameters")}, {"software", software_},
        {"files", QJsonObject{{"request", requestFile}, {"campaign", campaignFile}, {"metrics", metricsFile},
                              {"events", eventsFile}, {"artifacts", artifactsFile}}},
        {"compatibility", QJsonObject{{"comparison_group", "electromechanical_" + context_.lot + "_" + context_.variant},
                                      {"result_contract_version", 1}}},
        {"metadata", QJsonObject{{"verdict", verdict}, {"evidence_domain", context_.domain},
                                 {"conclusion", verdict == pass ? "conforme" :
                                                verdict == fail ? "non conforme" : "préliminaire"}}}};
    writeNew(output, manifestFile, QJsonDocument(manifest).toJson());
}

} // namespace architecture_decision
