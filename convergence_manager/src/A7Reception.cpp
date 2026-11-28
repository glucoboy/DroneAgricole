#include "Files.hpp"
#include "MaterialEvidence.hpp"

#include <QCommandLineParser>
#include <QCoreApplication>
#include <QFileInfo>
#include <QJsonArray>
#include <QJsonDocument>
#include <QMap>
#include <QSet>

#include <array>
#include <cmath>
#include <cstdio>

namespace {

using namespace convergence;
using Vector = std::array<double, 3>;
constexpr double numericalTolerance = 1e-7;
const QString example = QStringLiteral("EXAMPLE_NOT_AUTHORITY");
const QString unreviewed = QStringLiteral("OPERATOR_SUBMISSION_UNREVIEWED");

void fields(const QJsonObject &object, const QStringList &names, const QString &reason)
{
    require(object.size() == names.size(), reason);
    for (const auto &name : names) {
        require(object.contains(name), reason);
    }
}

QString ordinaryPath(const QFileInfo &info, bool directory, const QString &reason)
{
    const auto path = info.canonicalFilePath();
    require((directory ? info.isDir() : info.isFile()) && !info.isSymLink() && !info.isJunction() &&
            !path.isEmpty() && path == QDir::cleanPath(info.absoluteFilePath()), reason);
    return path;
}

QString submissionFile(const QDir &root, const QString &name)
{
    require(!name.isEmpty() && QDir::cleanPath(name) == name && !name.contains('\\') &&
            !name.contains(':') && !QDir::isAbsolutePath(name) &&
            name != ".." && !name.startsWith("../"), "INVALID_SOURCE_PATH");
    const auto absolute = root.absoluteFilePath(name);
    require(!hasRedirectedComponent(root, absolute), "REDIRECTED_SOURCE");
    const auto path = ordinaryPath(QFileInfo(absolute), false, "A7_SOURCE_MISSING_OR_REDIRECTED");
    require(relative(root, path) == name, "REDIRECTED_SOURCE");
    return path;
}

QString sourceDigest(const QDir &root, const QJsonObject &source)
{
    fields(source, {"path", "sha256"}, "INVALID_SOURCE_REFERENCE");
    const auto observed = fileDigest(submissionFile(root, source.value("path").toString()));
    require(observed == source.value("sha256"), "SOURCE_SHA256_MISMATCH");
    return observed;
}

Vector vector(const QJsonValue &value)
{
    const auto array = value.toArray();
    require(array.size() == 3, "INVALID_DATUM_VECTOR");
    Vector result;
    for (int axis = 0; axis != 3; ++axis) {
        const auto component = array.at(axis);
        require(component.isDouble() && std::isfinite(component.toDouble()), "INVALID_DATUM_VECTOR");
        result[axis] = component.toDouble();
    }
    return result;
}

Vector unit(Vector value, const QString &reason)
{
    const auto length = std::hypot(value[0], value[1], value[2]);
    require(std::isfinite(length) && length > numericalTolerance, reason);
    for (auto &component : value) {
        component /= length;
    }
    return value;
}

void datum(const QJsonObject &detail, const QJsonObject &frame)
{
    const auto origin = vector(detail.value("origin_mm"));
    const auto x = unit(vector(detail.value("x_direction")), "INVALID_DATUM_DIRECTION");
    auto y = unit(vector(detail.value("y_direction")), "INVALID_DATUM_DIRECTION");
    const auto projection = x[0] * y[0] + x[1] * y[1] + x[2] * y[2];
    for (int axis = 0; axis != 3; ++axis) {
        y[axis] -= projection * x[axis];
    }
    y = unit(y, "COLLINEAR_DATUM_DIRECTIONS");
    const Vector z{x[1] * y[2] - x[2] * y[1], x[2] * y[0] - x[0] * y[2],
                   x[0] * y[1] - x[1] * y[0]};
    const auto normal = unit(vector(detail.value("observed_normal")), "INVALID_DATUM_NORMAL");
    const auto sign = detail.value("normal_sign").toDouble();
    require(sign == 1 || sign == -1, "INVALID_NORMAL_SIGN");
    const auto matrix = frame.value("local_to_parent").toArray();
    // A.4 has already checked rigidity, inverse and agreement with the scoped policy.
    for (int row = 0; row != 3; ++row) {
        require(std::abs(sign * normal[row] - z[row]) <= numericalTolerance, "DATUM_NORMAL_MISMATCH");
        require(std::abs(matrix.at(row * 4).toDouble() - x[row]) <= numericalTolerance &&
                std::abs(matrix.at(row * 4 + 1).toDouble() - y[row]) <= numericalTolerance &&
                std::abs(matrix.at(row * 4 + 2).toDouble() - z[row]) <= numericalTolerance &&
                std::abs(matrix.at(row * 4 + 3).toDouble() - origin[row]) <= numericalTolerance,
                "DATUM_OBSERVATION_MISMATCH");
    }
}

void validateScope(const QJsonObject &record, const QJsonObject &check, const QJsonObject &submission,
                   const QString &parent, const QString &classification)
{
    QString expectedClass = "PHYSICAL_MEASURED"; // The incoming A.4 declaration, never an A.7 result.
    if (classification == example) {
        expectedClass = example;
    }
    require(record.value("evidence_class") == expectedClass, "A7_EVIDENCE_CLASS_MISMATCH");
    require(record.value("review").isNull(), "A7_REVIEW_MUST_USE_AUTHORIZED_CHANNEL");
    require(record.value("issue") == check.value("issue") && record.value("subject") == check.value("subject"),
            "A7_CHECK_SCOPE_MISMATCH");
    const auto facts = record.value("facts").toObject();
    require(facts.value("carrier") == submission.value("carrier") &&
            facts.value("assembly_id") == submission.value("assembly_id"), "A7_MIXED_ASSEMBLY_OR_CARRIER");
    const auto constrainedFacts = check.value("facts").toObject();
    for (auto it = constrainedFacts.begin(); it != constrainedFacts.end(); ++it) {
        require(it.value().toArray().contains(facts.value(it.key())), "A7_CONFLICTING_FACT_" + it.key());
    }
    require(record.value("frame").toObject().value("parent") == parent, "A7_XLINK_PARENT_MISMATCH");
    const auto capture = record.value("capture").toObject();
    require(capture.value("detached") == QJsonValue(true), "A7_CORDS_MUST_BE_DETACHED");
    const auto tolerance = record.value("measurement").toObject().value("tolerance").toObject();
    require(record.value("measurement").toObject().value("kind") == check.value("kind") &&
            tolerance.value("unit") == check.value("unit") &&
            tolerance.value("comparison") == check.value("comparison"), "A7_CHECK_QUANTITY_MISMATCH");
}

QJsonObject inspectRecord(const QDir &root, const QJsonObject &record, const QJsonObject &detail,
                          const QJsonObject &imported, const QJsonObject &check)
{
    auto output = QJsonObject{{"check_id", check.value("id")}, {"record_id", record.value("record_id")}};
    if (imported.value("status") == "REJECTED") {
        output.insert("status", "FAIL");
        output.insert("reason", imported.value("reason"));
        return output;
    }
    try {
        fields(detail, {"origin_mm", "x_direction", "y_direction", "observed_normal", "normal_sign",
                        "calibration", "artifacts"}, "MISSING_DATUM_DETAILS");
        datum(detail, record.value("frame").toObject());
        if (!detail.value("calibration").isNull()) {
            sourceDigest(root, detail.value("calibration").toObject());
        }
        const auto artifacts = detail.value("artifacts").toObject();
        QStringList required;
        for (const auto &name : check.value("artifacts").toArray()) {
            required.append(name.toString());
        }
        fields(artifacts, required, "A7_ARTIFACT_SET_MISMATCH");
        QSet<QString> hashes;
        for (const auto &name : required) {
            const auto hash = sourceDigest(root, artifacts.value(name).toObject());
            require(!hashes.contains(hash), "A7_NON_DISTINCT_ARTIFACTS");
            hashes.insert(hash);
        }
        const auto measurement = imported.value("measurement").toObject();
        const auto limit = measurement.value("limit").toDouble();
        const auto margin = measurement.value("comparison") == "GE"
            ? measurement.value("low").toDouble() - limit : limit - measurement.value("high").toDouble();
        const auto technicalPass = imported.value("status") == "PENDING_AUTHORIZED_REVIEW";
        output.insert("status", technicalPass ? "PASS" : "FAIL");
        output.insert("reason", technicalPass ? "TECHNICALLY_COMPLETE" : "A7_INSUFFICIENT_CONSERVATIVE_MARGIN");
        output.insert("conservative_margin", margin);
        output.insert("limit_unit", measurement.value("unit"));
        output.insert("measurement_interval", QJsonArray{measurement.value("low"), measurement.value("high")});
    } catch (const std::exception &error) {
        output.insert("status", "FAIL");
        output.insert("reason", QString::fromUtf8(error.what()));
    }
    return output;
}

QMap<QString, QJsonObject> matrixChecks(const QJsonObject &matrix)
{
    QMap<QString, QJsonObject> result;
    for (const auto &entry : matrix.value("requirements").toArray()) {
        const auto requirement = entry.toObject();
        for (const auto &entryCheck : requirement.value("checks").toArray()) {
            auto check = entryCheck.toObject();
            check.insert("issue", requirement.value("id"));
            result.insert(check.value("id").toString(), check);
        }
    }
    return result;
}

QJsonObject worksheet(const QJsonObject &matrix, const QString &carrier)
{
    const auto parent = matrix.value("carriers").toObject().value(carrier);
    require(parent.isString(), "A7_UNKNOWN_CARRIER");
    QJsonArray entries;
    for (const auto &check : matrixChecks(matrix)) {
        entries.append(QJsonObject{{"check_id", check.value("id")}, {"issue", check.value("issue")},
            {"subject", check.value("subject")}, {"measurement_kind", check.value("kind")},
            {"limit_unit", check.value("unit")}, {"comparison", check.value("comparison")},
            {"required_artifact_roles", check.value("artifacts")}, {"record_id", QJsonValue()},
            {"observation_status", "MISSING"}});
    }
    return {{"schema", "v3.a7.operator_worksheet/1"}, {"classification", "EMPTY_OPERATOR_TEMPLATE"},
        {"carrier", carrier}, {"carrier_parent", parent}, {"carrier_identity", QJsonValue()},
        {"configuration", matrix.value("configuration")}, {"assembly_id", QJsonValue()},
        {"operation", matrix.value("operation")}, {"occurrence", matrix.value("occurrence")},
        {"measurement_packet_schema", "v3.a4.measurement_packet/1"}, {"entries", entries}};
}

void printJson(const QJsonObject &object)
{
    const auto bytes = QJsonDocument(object).toJson();
    require(std::fwrite(bytes.constData(), 1, static_cast<size_t>(bytes.size()), stdout) ==
            static_cast<size_t>(bytes.size()), "OUTPUT_ERROR");
}

QJsonArray completeness(const QJsonObject &matrix, const QString &activeCarrier,
                        const QMap<QString, QJsonObject> &observations)
{
    QJsonArray carriers;
    const auto parents = matrix.value("carriers").toObject();
    for (const auto &carrier : parents.keys()) {
        QJsonArray requirements;
        for (const auto &entry : matrix.value("requirements").toArray()) {
            const auto requirement = entry.toObject();
            const auto id = requirement.value("id").toString();
            const auto checks = requirement.value("checks").toArray();
            auto status = QStringLiteral("PASS");
            QJsonArray details;
            for (const auto &check : checks) {
                const auto key = check.toObject().value("id").toString();
                auto observed = QJsonObject{{"check_id", key}, {"status", "MISSING"},
                                            {"reason", "OPERATOR_RECORD_REQUIRED"}};
                if (carrier == activeCarrier && observations.contains(key)) {
                    observed = observations.value(key);
                }
                if (observed.value("status") == "FAIL") {
                    status = "FAIL";
                } else if (observed.value("status") == "MISSING" && status != "FAIL") {
                    status = "MISSING";
                }
                details.append(observed);
            }
            if (id == "AUTHORIZED_REVIEW") {
                status = "PENDING_AUTHORIZED_REVIEW";
            } else if (id == "PRODUCTION_TRUST") {
                status = "NOT_RUN";
            }
            requirements.append(QJsonObject{{"id", id}, {"source", requirement.value("source")},
                {"status", status}, {"checks", details}, {"blocking", status != "PASS"}});
        }
        carriers.append(QJsonObject{{"carrier", carrier}, {"parent", parents.value(carrier)},
            {"operation", matrix.value("operation")}, {"occurrence", matrix.value("occurrence")},
            {"requirements", requirements}, {"decision", "DENY"}});
    }
    return carriers;
}

QMap<QString, QJsonObject> import(const QDir &root, const QJsonObject &matrix, const QJsonObject &submission,
                                 QJsonObject packet, const QJsonObject &policy)
{
    const auto classification = submission.value("classification").toString();
    const auto details = submission.value("details").toObject();
    const auto parent = matrix.value("carriers").toObject().value(submission.value("carrier").toString()).toString();
    const auto checks = matrixChecks(matrix);
    require(packet.value("records").isArray() && packet.value("configuration") == matrix.value("configuration"),
            "A7_PACKET_SCOPE_MISMATCH");
    auto records = packet.value("records").toArray();
    require(details.size() == records.size(), "A7_DETAIL_RECORD_SET_MISMATCH");
    QSet<QString> seen;
    for (int index = 0; index < records.size(); ++index) {
        const auto record = records.at(index).toObject();
        const auto recordId = identifier(record.value("record_id"));
        const auto checkId = identifier(record.value("check_id"));
        require(!seen.contains(checkId), "A7_DUPLICATE_CHECK");
        seen.insert(checkId);
        require(checks.contains(checkId), "A7_UNKNOWN_CHECK");
        require(details.value(recordId).isObject(), "A7_DETAIL_RECORD_SET_MISMATCH");
        validateScope(record, checks.value(checkId), submission, parent, classification);
        if (classification == example) {
            auto fixture = record;
            fixture.insert("evidence_class", "TEST_ONLY");
            records.replace(index, fixture);
        }
    }
    const auto firstDatum = QStringLiteral("mount-datum-1");
    const auto secondDatum = QStringLiteral("mount-datum-2");
    if (seen.contains(firstDatum) && seen.contains(secondDatum)) {
        QMap<QString, QJsonObject> datums;
        for (const auto &entry : records) {
            const auto row = entry.toObject();
            datums.insert(row.value("check_id").toString(), row);
        }
        const auto first = datums.value(firstDatum);
        const auto second = datums.value(secondDatum);
        require(first.value("frame").toObject().value("datum") != second.value("frame").toObject().value("datum") &&
                first.value("sources").toObject().value("raw").toObject().value("sha256") !=
                second.value("sources").toObject().value("raw").toObject().value("sha256"),
                "A7_DATUMS_NOT_INDEPENDENT");
    }
    packet.insert("records", records);
    const auto evidenceClass = classification == example ? QStringLiteral("TEST_ONLY") : QStringLiteral("PHYSICAL_MEASURED");
    const auto imported = validateMaterialPacket(root, packet, policy, evidenceClass).value("records").toArray();
    QMap<QString, QJsonObject> observations;
    for (int index = 0; index < records.size(); ++index) {
        const auto record = records.at(index).toObject();
        const auto key = record.value("check_id").toString();
        observations.insert(key, inspectRecord(root, record, details.value(record.value("record_id").toString()).toObject(),
                                              imported.at(index).toObject(), checks.value(key)));
    }
    return observations;
}

} // namespace

int main(int argc, char **argv)
{
    QCoreApplication app(argc, argv);
    QCommandLineParser cli;
    cli.setApplicationDescription("Complétude documentaire V3-A.7 (lecture seule).");
    cli.addHelpOption();
    const QCommandLineOption matrix("matrix", "Matrice V3-A.7 ayant servi au build.", "json");
    const QCommandLineOption raw("raw-root", "Racine privée contenant les pièces brutes.", "dir");
    const QCommandLineOption submission("submission", "Dépôt V3-A.7, chemin relatif à raw-root.", "json");
    const QCommandLineOption current("current-sha256", "Empreinte du dépôt courant transmise séparément.", "sha256");
    const QCommandLineOption policy("policy", "Politique A.4 indépendante du répertoire privé de soumission.", "json");
    const QCommandLineOption policySha("policy-sha256", "Empreinte de la politique transmise séparément.", "sha256");
    const QCommandLineOption operatorTemplate("operator-template", "Créer une fiche de préparation vierge.", "P64|P66");
    cli.addOptions({matrix, raw, submission, current, policy, policySha, operatorTemplate});
    cli.process(app);
    try {
        require(cli.isSet(matrix) && cli.positionalArguments().isEmpty(), "A7_INVALID_ARGUMENTS");
        const auto matrixBytes = read(cli.value(matrix));
        const auto matrixSha = digest(matrixBytes);
        require(matrixSha == QStringLiteral(V3_A7_MATRIX_SHA256), "A7_MATRIX_SHA256_MISMATCH");
        const auto profile = parseUniqueObject(matrixBytes, "matrix");
        const auto hasSubmission = cli.isSet(raw) || cli.isSet(submission) || cli.isSet(current) ||
                                   cli.isSet(policy) || cli.isSet(policySha);
        if (cli.isSet(operatorTemplate)) {
            require(!hasSubmission, "A7_TEMPLATE_WITH_SUBMISSION");
            printJson(worksheet(profile, cli.value(operatorTemplate)));
            return 0;
        }
        auto output = QJsonObject{{"schema", "v3.a7.completeness/1"}, {"authority", "DENY"},
            {"construction", "NOT_RUN"}, {"physical_reception", "NOT_RUN"},
            {"physical_admission", "PHYSICAL_ADMISSION_NOT_CONFIGURED"}, {"inspected_lots_by_tool", 0},
            {"cartographer_candidate_count", 0}, {"cartographer_mutation", "DENY"},
            {"production_trust_pin", "EMPTY"}, {"matrix_sha256", matrixSha}};
        QString activeCarrier;
        QMap<QString, QJsonObject> observations;
        if (hasSubmission) {
            require(cli.isSet(raw) && cli.isSet(submission) && cli.isSet(current) &&
                    cli.isSet(policy) && cli.isSet(policySha), "A7_INCOMPLETE_ARGUMENTS");
            const QDir root(ordinaryPath(QFileInfo(cli.value(raw)), true, "INVALID_RAW_ROOT"));
            const auto policyPath = ordinaryPath(QFileInfo(cli.value(policy)), false, "POLICY_MISSING_OR_REDIRECTED");
            const auto policyRelative = root.relativeFilePath(policyPath);
            require(QDir::isAbsolutePath(policyRelative) || policyRelative.startsWith("../"),
                    "POLICY_INSIDE_SUBMISSION_OR_REDIRECTED");
            const auto envelope = read(submissionFile(root, cli.value(submission)));
            const auto envelopeSha = digest(envelope);
            require(envelopeSha == cli.value(current), "A7_STALE_OR_ALTERED_SUBMISSION");
            const auto a7 = parseUniqueObject(envelope, "submission");
            fields(a7, {"schema", "classification", "assembly_id", "carrier", "packet", "details"},
                   "A7_INVALID_SUBMISSION_FIELDS");
            activeCarrier = a7.value("carrier").toString();
            const auto classification = a7.value("classification").toString();
            require(a7.value("schema") == "v3.a7.submission/1" &&
                    (classification == unreviewed || classification == example) &&
                    profile.value("carriers").toObject().contains(activeCarrier) && a7.value("details").isObject(),
                    "A7_INVALID_SUBMISSION");
            identifier(a7.value("assembly_id"));
            const auto policyBytes = read(policyPath);
            require(digest(policyBytes) == cli.value(policySha), "POLICY_SHA256_MISMATCH");
            const auto reference = a7.value("packet").toObject();
            fields(reference, {"path", "sha256"}, "INVALID_SOURCE_REFERENCE");
            const auto packetBytes = read(submissionFile(root, reference.value("path").toString()));
            const auto packetSha = digest(packetBytes);
            require(packetSha == reference.value("sha256"), "A7_PACKET_SHA256_MISMATCH");
            observations = import(root, profile, a7, parseUniqueObject(packetBytes, "packet"),
                                  parseUniqueObject(policyBytes, "policy"));
            output.insert("submission_sha256", envelopeSha);
            output.insert("packet_sha256", packetSha);
            output.insert("policy_sha256", cli.value(policySha));
            output.insert("classification", classification);
        }
        int failures = 0;
        for (const auto &observation : observations) {
            failures += observation.value("status") == "FAIL";
        }
        output.insert("status", failures ? "FAIL" : observations.isEmpty() ? "NOT_RUN" : "ANALYZED");
        output.insert("failed_checks", failures);
        output.insert("carriers", completeness(profile, activeCarrier, observations));
        printJson(output);
        return failures ? 2 : 0;
    } catch (const std::exception &error) {
        std::fprintf(stderr, "%s\n", error.what());
        return 2;
    }
}
