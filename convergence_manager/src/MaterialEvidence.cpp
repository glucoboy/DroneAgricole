#include "Files.hpp"

#include <QCommandLineParser>
#include <QCoreApplication>
#include <QDateTime>
#include <QFileInfo>
#include <QJsonArray>
#include <QJsonDocument>
#include <QMap>
#include <QSet>

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdio>
#include <limits>

namespace {

using namespace convergence;
using Matrix = std::array<double, 16>;

QString text(const QJsonObject &object, const QString &key)
{
    const auto value = object.value(key).toString();
    require(!value.trimmed().isEmpty(), "MISSING_" + key);
    return value;
}

void fields(const QJsonObject &object, std::initializer_list<QString> allowed)
{
    const QSet<QString> names(allowed);
    for (const auto &key : object.keys()) {
        require(names.contains(key), "UNEXPECTED_" + key);
    }
    require(object.size() == names.size(), "MISSING_FIELDS");
}

double number(const QJsonValue &value)
{
    require(value.isDouble() && std::isfinite(value.toDouble()), "INVALID_NUMBER");
    return value.toDouble();
}

QString evidenceFile(const QDir &root, const QJsonObject &reference)
{
    fields(reference, {"path", "sha256"});
    const auto name = text(reference, "path");
    require(name == QDir::cleanPath(name) && !name.contains('\\') && !name.contains(':') &&
            !QDir::isAbsolutePath(name), "INVALID_SOURCE_PATH");
    const auto path = root.absoluteFilePath(name);
    require(relative(root, path) == name && !hasRedirectedComponent(root, path), "REDIRECTED_SOURCE");
    const auto sha = fileDigest(fileInside(root, name));
    require(sha == text(reference, "sha256"), "SOURCE_SHA256_MISMATCH");
    return sha;
}

Matrix matrix(const QJsonValue &value)
{
    const auto items = value.toArray();
    require(items.size() == 16, "INVALID_FRAME_SIZE");
    Matrix result;
    for (int i = 0; i != 16; ++i) {
        result[i] = number(items[i]);
    }
    constexpr double epsilon = 1e-7;
    require(std::abs(result[12]) <= epsilon && std::abs(result[13]) <= epsilon &&
            std::abs(result[14]) <= epsilon && std::abs(result[15] - 1) <= epsilon,
            "INVALID_FRAME_CONVENTION");
    for (int i = 0; i != 3; ++i) {
        for (int j = i; j != 3; ++j) {
            const auto dot = result[i] * result[j] + result[4+i] * result[4+j] + result[8+i] * result[8+j];
            require(std::abs(dot - (i == j ? 1 : 0)) <= epsilon, "NON_RIGID_FRAME");
        }
    }
    const auto determinant = result[0] * (result[5]*result[10] - result[6]*result[9]) -
        result[1] * (result[4]*result[10] - result[6]*result[8]) +
        result[2] * (result[4]*result[9] - result[5]*result[8]);
    require(std::abs(determinant - 1) <= epsilon, "LEFT_HANDED_FRAME");
    return result;
}

void checkFrame(const QJsonObject &actual, const QJsonObject &expected)
{
    fields(actual, {"parent", "datum", "local_to_parent", "parent_to_local"});
    require(text(actual, "datum") == text(expected, "datum") &&
            text(actual, "parent") == text(expected, "parent"), "FRAME_BINDING_MISMATCH");
    const auto transform = matrix(actual.value("local_to_parent"));
    const auto inverse = matrix(actual.value("parent_to_local"));
    const auto reference = matrix(expected.value("local_to_parent"));
    for (int row = 0; row != 3; ++row) {
        for (int col = 0; col != 3; ++col) {
            require(std::abs(inverse[row*4+col] - transform[col*4+row]) <= 1e-7, "FRAME_INVERSE_MISMATCH");
            require(std::abs(transform[row*4+col] - reference[row*4+col]) <=
                    number(expected.value("rotation_entry_tolerance")), "FRAME_ORIENTATION_MISMATCH");
        }
        const auto inverseOffset = inverse[row*4]*transform[3] + inverse[row*4+1]*transform[7] +
            inverse[row*4+2]*transform[11] + inverse[row*4+3];
        require(std::abs(inverseOffset) <= 1e-7, "FRAME_INVERSE_MISMATCH");
    }
    const auto distance = std::hypot(transform[3] - reference[3], transform[7] - reference[7],
        transform[11] - reference[11]);
    require(distance <= number(expected.value("position_tolerance_mm")), "FRAME_OFFSET_MISMATCH");
}

QJsonObject measure(const QJsonObject &observation, const QJsonObject &check)
{
    fields(observation, {"kind", "method", "instrument", "resolution", "value", "unit", "uncertainty", "tolerance"});
    require(text(observation, "kind") == text(check, "kind"), "MEASUREMENT_KIND_MISMATCH");
    text(observation, "method");
    text(observation, "instrument");
    const auto unit = text(observation, "unit");
    const auto criterion = check.value("tolerance").toObject();
    require(observation.value("tolerance") == criterion, "TOLERANCE_AUTHORITY_MISMATCH");
    const auto referenceUnit = text(criterion, "unit");
    static const QMap<QString, double> length{{"mm", 1.0}, {"cm", 10.0}, {"in", 25.4}};
    require(unit == text(check, "input_unit"), "MEASUREMENT_UNIT_MISMATCH");
    const auto convertsLength = length.contains(unit) && length.contains(referenceUnit);
    require(convertsLength || (unit == referenceUnit && (unit == "deg" || unit == "N" || unit == "ohm")),
            "UNSUPPORTED_MEASUREMENT_UNIT");
    const auto factor = convertsLength ? length.value(unit) / length.value(referenceUnit) : 1.0;
    const auto value = number(observation.value("value")) * factor;
    const auto resolution = number(observation.value("resolution")) * factor;
    const auto uncertainty = number(observation.value("uncertainty")) * factor;
    const auto low = value - uncertainty;
    const auto high = value + uncertainty;
    require(resolution > 0 && uncertainty >= resolution / 2 && std::isfinite(low) && std::isfinite(high) &&
            value >= number(check.value("plausible_min")) && value <= number(check.value("plausible_max")),
            "INVALID_MEASUREMENT_RANGE");
    const auto limit = number(criterion.value("limit"));
    text(criterion, "source");
    const auto comparison = text(criterion, "comparison");
    require(comparison == "LE" || comparison == "GE", "INVALID_TOLERANCE_DIRECTION");
    const auto margin = std::numeric_limits<double>::epsilon() * 4 *
        std::max({1.0, std::abs(low), std::abs(high), std::abs(limit)});
    const bool pass = comparison == "LE" ? high < limit - margin : low > limit + margin;
    const bool fail = comparison == "LE" ? low > limit + margin : high < limit - margin;
    return {{"status", pass ? "PASS" : fail ? "FAIL" : "INCONCLUSIVE"}, {"unit", referenceUnit},
        {"low", low}, {"high", high}, {"limit", limit}, {"comparison", comparison}};
}

QJsonObject validateRecord(const QDir &root, const QJsonObject &record, const QJsonObject &policy)
{
    auto result = QJsonObject{{"record_id", record.value("record_id")}, {"issue", record.value("issue")},
        {"subject", record.value("subject")}, {"authority", "DENY"}};
    try {
        require(record.value("evidence_class") != "EXAMPLE_NOT_AUTHORITY", "EXAMPLE_NOT_AUTHORITY");
        fields(record, {"record_id", "evidence_class", "issue", "subject", "check_id", "identity",
            "sources", "capture", "frame", "measurement", "facts", "review"});
        identifier(record.value("record_id"));
        require(record.value("evidence_class") == "PHYSICAL_MEASURED", "INVALID_EVIDENCE_CLASS");
        const auto subject = text(record, "subject");
        const auto issue = text(record, "issue");
        require(policy.value("issues").toArray().contains(issue), "UNKNOWN_ISSUE");
        const auto identity = record.value("identity").toObject();
        fields(identity, {"manufacturer", "mpn", "variant", "revision", "lot_or_serial"});
        for (const auto &field : identity.keys()) { text(identity, field); }
        const auto capture = record.value("capture").toObject();
        fields(capture, {"author", "measured_at", "view", "orientation", "scale", "power_state", "detached"});
        for (const auto &field : {"author", "view", "orientation", "scale"}) { text(capture, field); }
        const auto date = text(capture, "measured_at");
        const auto timestamp = QDateTime::fromString(date, Qt::ISODate);
        require(date.contains('T') && timestamp.isValid() && timestamp.timeSpec() != Qt::LocalTime &&
                timestamp <= QDateTime::currentDateTimeUtc(), "INVALID_CAPTURE_DATE");
        require(capture.value("power_state") == "DEENERGIZED" && capture.value("detached").isBool() &&
                (record.value("measurement").toObject().value("kind") != "CONTINUITY" ||
                 capture.value("detached").toBool()), "UNSAFE_CAPTURE_CONTEXT");
        const auto sources = record.value("sources").toObject();
        fields(sources, {"raw", "photo", "identity_photo", "manufacturer_document", "tolerance_document",
            "manufacturer_locator", "manufacturer_revision"});
        for (const auto &field : {"raw", "photo", "identity_photo", "manufacturer_document", "tolerance_document"}) {
            evidenceFile(root, sources.value(field).toObject());
        }
        const auto trustedIdentity = policy.value("identities").toObject().value(subject).toObject();
        require(!trustedIdentity.isEmpty(), "UNCONFIRMED_LOT");
        require(identity == trustedIdentity.value("identity").toObject(), "LOT_VARIANT_OR_REVISION_MISMATCH");
        require(sources.value("identity_photo").toObject().value("sha256") == trustedIdentity.value("identity_photo_sha256"),
                "LOT_IDENTITY_SOURCE_MISMATCH");
        require(sources.value("manufacturer_document").toObject().value("sha256") ==
                trustedIdentity.value("manufacturer_sha256") &&
                text(sources, "manufacturer_revision") == text(trustedIdentity, "manufacturer_revision") &&
                text(sources, "manufacturer_locator") == text(trustedIdentity, "manufacturer_locator"),
                "MANUFACTURER_DOCUMENT_MISMATCH");
        const auto check = policy.value("checks").toObject().value(text(record, "check_id")).toObject();
        require(!check.isEmpty() && check.value("subject") == subject && check.value("issue") == issue,
                "EVIDENCE_SCOPE_MISMATCH");
        require(sources.value("tolerance_document").toObject().value("sha256") == check.value("tolerance_sha256"),
                "TOLERANCE_DOCUMENT_MISMATCH");
        require(record.value("facts").isObject() && record.value("facts") == check.value("facts"),
                "TOPOLOGY_OR_APPLICABILITY_MISMATCH");
        checkFrame(record.value("frame").toObject(), check.value("frame").toObject());
        const auto metrics = measure(record.value("measurement").toObject(), check);
        result.insert("measurement", metrics);
        result.insert("review_status", "NOT_SUBMITTED");
        if (!record.value("review").isNull()) {
            const auto review = record.value("review").toObject();
            fields(review, {"reviewer", "detached_signature"});
            require(policy.value("reviewer_ids").toArray().contains(text(review, "reviewer")),
                    "REVIEWER_NOT_CONFIGURED");
            evidenceFile(root, review.value("detached_signature").toObject());
            result.insert("review_status", "SUBMITTED_UNVERIFIED");
        }
        const auto metricStatus = metrics.value("status");
        result.insert("status", metricStatus == "PASS" ? "PENDING_AUTHORIZED_REVIEW" : metricStatus);
        result.insert("reason", metricStatus == "PASS" ? "NO_AUTHENTICATED_REVIEW_INFRASTRUCTURE" :
                      "TOLERANCE_INTERVAL");
    } catch (const std::exception &error) {
        result.insert("status", "REJECTED");
        result.insert("reason", QString::fromUtf8(error.what()));
    }
    return result;
}

QJsonObject validate(const QDir &root, const QJsonObject &packet, const QJsonObject &policy)
{
    fields(packet, {"schema", "configuration", "records"});
    require(packet.value("schema") == "v3.a4.measurement_packet/1" &&
            policy.value("schema") == "v3.a4.review_policy/1" &&
            packet.value("configuration") == policy.value("configuration") && packet.value("records").isArray(),
            "INVALID_PACKET_OR_POLICY");
    require(policy.value("issues").isArray() && policy.value("identities").isObject() &&
            policy.value("checks").isObject() && policy.value("reviewer_ids").isArray(), "INVALID_POLICY");
    QJsonArray results;
    QSet<QString> ids;
    int rejected = 0;
    for (const auto &entry : packet.value("records").toArray()) {
        const auto record = entry.toObject();
        const auto id = identifier(record.value("record_id"));
        require(!ids.contains(id), "DUPLICATE_RECORD_ID");
        ids.insert(id);
        const auto result = validateRecord(root, record, policy);
        rejected += result.value("status") == "REJECTED" ? 1 : 0;
        results.append(result);
    }
    return {{"schema", "v3.a4.evidence_validation/1"}, {"authority", "DENY"},
        {"status", results.isEmpty() ? "NOT_RUN" : "ANALYZED"}, {"rejected", rejected},
        {"validated_physical_approvals", 0}, {"records", results}};
}

} // namespace

int main(int argc, char **argv)
{
    QCoreApplication app(argc, argv);
    QCommandLineParser options;
    options.setApplicationDescription("Contrôle préliminaire de relevés V3-A.4");
    options.addHelpOption();
    const QCommandLineOption rawRoot("raw-root", "Racine des pièces brutes.", "dir");
    const QCommandLineOption packet("packet", "Dossier des relevés.", "json");
    const QCommandLineOption policy("policy", "Configuration de la revue hors dépôt des mesures.", "json");
    const QCommandLineOption sha("policy-sha256", "Empreinte connue du dossier de revue.", "sha256");
    options.addOptions({rawRoot, packet, policy, sha});
    options.process(app);
    try {
        const QFileInfo rootInfo(options.value(rawRoot));
        require(rootInfo.isDir() && !rootInfo.isSymLink() && !rootInfo.isJunction(), "INVALID_RAW_ROOT");
        const QDir root(rootInfo.canonicalFilePath());
        const QFileInfo policyInfo(options.value(policy));
        const auto policyPath = policyInfo.canonicalFilePath();
        const auto policyRelative = root.relativeFilePath(policyPath);
        require(policyInfo.isFile() && !policyInfo.isSymLink() && !policyInfo.isJunction() &&
                (QDir::isAbsolutePath(policyRelative) || policyRelative.startsWith("../")),
                "POLICY_INSIDE_SUBMISSION_OR_REDIRECTED");
        const auto policyBytes = read(policyPath);
        require(digest(policyBytes) == options.value(sha), "POLICY_SHA256_MISMATCH");
        const auto packetPath = options.value(packet);
        const auto packetBytes = read(packetPath);
        auto output = validate(root, parseUniqueObject(packetBytes, packetPath), parseUniqueObject(policyBytes, policyPath));
        output.insert("packet_sha256", digest(packetBytes));
        output.insert("policy_sha256", digest(policyBytes));
        const auto bytes = QJsonDocument(output).toJson();
        require(std::fwrite(bytes.constData(), 1, static_cast<size_t>(bytes.size()), stdout) ==
                static_cast<size_t>(bytes.size()), "OUTPUT_ERROR");
        return output.value("rejected").toInt() == 0 ? 0 : 2;
    } catch (const std::exception &error) {
        std::fprintf(stderr, "%s\n", error.what());
        return 2;
    }
}
