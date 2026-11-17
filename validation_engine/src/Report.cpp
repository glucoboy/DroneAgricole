#include "Report.hpp"

#include <QJsonDocument>
#include <QSet>

namespace electromechanical_validation {
namespace {

const QSet<QString> l0Units{"mm", "mm2", "mm3", "deg", "A", "V", "ohm", "Hz", "s", "degC", "g", "g/m", "1"};

QJsonValue observedValue(const Assessment &result, const QString &method, const QJsonArray &evidenceIds,
                         const QString &timestamp, const QString &scope)
{
    if (result.status == "NOT_RUN" || result.value.isUndefined() || result.value.isNull() || evidenceIds.isEmpty()) {
        return QJsonValue::Null;
    }
    auto value = result.value;
    // L0 Value is scalar. Structured observations remain in the L4 finding.
    if (value.isObject() || value.isArray()) {
        return QJsonValue::Null;
    }
    const auto status = scope == "DOCUMENT" ? "SOURCED" : "MEASURED";
    return QJsonObject{{"value", value}, {"unit", l0Units.contains(result.unit) ? result.unit : "1"},
        {"status", status}, {"evidence_ids", evidenceIds}, {"revision", QJsonValue::Null},
        {"collected_at", timestamp}, {"precision", QJsonValue::Null}, {"uncertainty", QJsonValue::Null},
        {"method", method}, {"input_value_refs", QJsonArray{}}, {"limits", result.reason}};
}

} // namespace

QJsonObject makeFinding(const QString &caseId, const QJsonObject &check, const Assessment &result,
                       const QString &evidenceId, const QString &timestamp, const QString &scope)
{
    const auto key = check.value("key").toString();
    const auto id = "finding-" + caseId + '-' + key;
    const auto method = check.value("method").toString();
    const auto family = check.value("family").toString();
    const auto subjects = check.value("subjects").toArray();
    const auto state = check.value("state_id").toString("S-NOMINAL");
    const auto revision = check.value("requirement_revision").toString("1");
    const auto requirement = check.value("requirement_id").toString("L4-" + family + '-' + method);
    const auto evidence = evidenceId.isEmpty() ? QJsonArray{} : QJsonArray{evidenceId};
    const QJsonObject finding{{"id", id}, {"requirement_id", requirement}, {"requirement_revision", revision},
        {"method", method}, {"subject_ids", subjects}, {"state_id", state}, {"status", result.status},
        {"observed", observedValue(result, method, evidence, timestamp, scope)},
        {"reason", result.reason}, {"evidence_ids", evidence}};
    return {{"finding_id", id}, {"key", key}, {"family", family}, {"scope", scope},
            {"requirement_id", requirement}, {"objects", subjects}, {"method", method},
            {"mandatory", check.value("mandatory").toBool(true)},
            {"tolerance", check.value("tolerance").isUndefined() ? QJsonValue::Null : check.value("tolerance")},
            {"criterion", check.value("parameters").toObject()},
            {"value", result.value.isUndefined() ? QJsonValue::Null : result.value},
            {"unit", result.unit.isEmpty() ? "1" : result.unit}, {"evidence_ids", evidence},
            {"status", result.status}, {"reason", result.reason}, {"l0", finding}};
}

QJsonObject makeReport(const QString &caseId, const QString &candidateId, const QString &scope,
                      const QJsonObject &fingerprints, const QJsonObject &environment,
                      const QJsonArray &findings, const QJsonArray &evidence,
                      const QString &nativeEvidenceId)
{
    QJsonArray expected, findingIds, l0Findings, evidenceIds, trace;
    QJsonObject counts{{"PASS", 0}, {"FAIL", 0}, {"INCONCLUSIVE", 0}, {"NOT_RUN", 0}};
    QJsonObject coverage;
    bool failed = false;
    bool open = false;
    bool executed = false;
    for (const auto &entry : findings) {
        const auto detail = entry.toObject();
        const auto finding = detail.value("l0").toObject();
        const auto status = finding.value("status").toString();
        const auto family = detail.value("family").toString();
        const auto mandatory = detail.value("mandatory").toBool();
        const auto id = finding.value("id");
        counts[status] = counts.value(status).toInt() + 1;
        auto familyCounts = coverage.value(family).toObject();
        familyCounts[status] = familyCounts.value(status).toInt() + 1;
        coverage[family] = familyCounts;
        executed |= status != "NOT_RUN";
        failed |= mandatory && status == "FAIL";
        open |= mandatory && status != "PASS";
        findingIds.append(id);
        l0Findings.append(finding);
        expected.append(QJsonObject{{"requirement_id", finding.value("requirement_id")},
            {"requirement_revision", finding.value("requirement_revision")}, {"method", finding.value("method")},
            {"state_id", finding.value("state_id")}, {"subject_ids", finding.value("subject_ids")}, {"mandatory", mandatory}});
        trace.append(QJsonObject{{"requirement_id", finding.value("requirement_id")},
            {"evidence_ids", finding.value("evidence_ids")}, {"finding_id", id}});
    }
    for (const auto &item : evidence) {
        evidenceIds.append(item.toObject().value("id"));
    }
    const auto verdict = !executed ? "NOT_RUN" : failed ? "FAIL" : open ? "INCONCLUSIVE" : "PASS";
    const auto id = "report-" + caseId;
    const QJsonObject report{{"id", id}, {"candidate_id", candidateId},
        {"baseline_sha256", fingerprints.value("reference_sha256")},
        {"requirements_sha256", fingerprints.value("requirements_sha256")},
        {"native_evidence_id", nativeEvidenceId.isEmpty() ? QJsonValue::Null : QJsonValue(nativeEvidenceId)},
        {"domain", scope}, {"environment", environment}, {"expected_checks", expected},
        {"finding_ids", findingIds}, {"verdict", verdict}, {"finalized", true}, {"evidence_ids", evidenceIds}};
    return {{"schema_version", 1}, {"case_id", caseId}, {"scope", scope}, {"verdict", verdict},
            {"finalized", true}, {"fingerprints", fingerprints}, {"coverage", coverage}, {"counts", counts},
            {"findings", findings}, {"traceability", trace}, {"validation_report", report},
            {"validation_findings", l0Findings}, {"technical_evidence", evidence}};
}

QJsonObject makeEvidence(const QString &id, const QString &path, const QString &sha256,
                         const QString &scope, const QString &method, const QString &timestamp)
{
    return {{"id", id}, {"kind", "OBSERVATION"}, {"domain", scope}, {"artifact_path", path},
            {"uri", QJsonValue::Null}, {"sha256", sha256}, {"locator", QJsonValue::Null},
            {"revision", QJsonValue::Null}, {"collected_at", timestamp}, {"method", method},
            {"hypothetical", false}, {"limits", "Périmètre du contrôle et du référentiel gelé"}};
}

} // namespace electromechanical_validation
