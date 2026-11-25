#include "AuthorityReview.hpp"
#include "Files.hpp"
#include "MaterialEvidence.hpp"

#include <QDateTime>
#include <QFileInfo>
#include <QJsonArray>
#include <QJsonDocument>
#include <QLockFile>
#include <QRegularExpression>
#include <QSet>

#include <cmath>
#include <filesystem>
#include <memory>

#ifdef V3_A5_CRYPTO
#include <openssl/evp.h>
#endif

namespace convergence {
namespace {

const auto receivingChecks = QJsonArray::fromStringList({"REOPEN_XLINK", "L2_TOPOLOGY", "L4_GEOMETRY",
    "L4_SUPPORT_ANCHOR", "L4_SERVICE", "L4_DYNAMIC_BEND_RADIUS", "VERIFY_IMMUTABLE_SOURCES", "VALIDATE_T0"});

void requireFields(const QJsonObject &object, const QSet<QString> &allowed)
{
    const auto keys = object.keys();
    require(QSet<QString>(keys.begin(), keys.end()) == allowed, "CONTRACT_FIELDS_MISMATCH");
}

QString requiredText(const QJsonObject &object, const QString &key)
{
    const auto value = object.value(key).toString();
    require(!value.trimmed().isEmpty(), "MISSING_" + key);
    return value;
}

QString requiredSha(const QJsonValue &value)
{
    static const QRegularExpression pattern(QStringLiteral("\\A[0-9a-f]{64}\\z"));
    const auto text = value.toString();
    require(pattern.match(text).hasMatch(), "INVALID_SHA256");
    return text;
}

QString objectSha(const QJsonObject &value)
{
    return digest(QJsonDocument(value).toJson(QJsonDocument::Compact));
}

QString relativeName(const QJsonValue &value)
{
    const auto path = value.toString();
    require(!path.isEmpty() && path == QDir::cleanPath(path) && !path.contains('\\') && !path.contains(':') &&
            !QDir::isAbsolutePath(path), "INVALID_RELATIVE_PATH");
    return path;
}

QString checkedFile(const QDir &root, const QJsonValue &value)
{
    const auto name = relativeName(value);
    require(!hasRedirectedComponent(root, root.absoluteFilePath(name)), "REDIRECTED_FILE");
    const auto path = fileInside(root, name);
    require(relative(root, path) == name, "FILE_PATH_MISMATCH");
    return path;
}

QDir checkedDirectory(const QDir &root, const QJsonValue &value)
{
    const auto name = relativeName(value);
    const auto absolute = root.absoluteFilePath(name);
    const auto canonical = QDir(absolute).canonicalPath();
    require(!canonical.isEmpty() && relative(root, canonical) == name &&
            !hasRedirectedComponent(root, absolute), "INVALID_PRIVATE_DIRECTORY");
    return QDir(canonical);
}

bool within(const QDir &parent, const QString &path)
{
    const auto name = parent.relativeFilePath(path);
    return !QDir::isAbsolutePath(name) && name != ".." && !name.startsWith("../");
}

QDateTime utc(const QJsonValue &input)
{
    const auto text = input.toString();
    const auto value = QDateTime::fromString(text, Qt::ISODate);
    require(value.isValid() && text.size() == 20 && text.endsWith('Z') && value.toString(Qt::ISODate) == text,
            "INVALID_UTC_TIMESTAMP");
    return value;
}

QByteArray strictBase64(const QJsonValue &value)
{
    const auto encoded = value.toString().toLatin1();
    const auto data = QByteArray::fromBase64(encoded, QByteArray::AbortOnBase64DecodingErrors);
    require(!data.isEmpty() && data.toBase64() == encoded, "INVALID_SIGNATURE_ENCODING");
    return data;
}

QJsonObject authenticate(const QByteArray &envelopeBytes, const QString &schema, const QString &key)
{
    const auto envelope = parseUniqueObject(envelopeBytes, schema);
    requireFields(envelope, {"schema", "payload_b64", "signature_b64"});
    require(envelope.value("schema") == schema, "SIGNATURE_ENVELOPE_SCHEMA_MISMATCH");
    const auto data = strictBase64(envelope.value("payload_b64"));
    const auto signature = strictBase64(envelope.value("signature_b64"));
    require(signature.size() == 64, "INVALID_SIGNATURE_ENCODING");
#ifdef V3_A5_CRYPTO
    const auto publicKey = QByteArray::fromHex(key.toLatin1());
    const auto toUnsigned = [](const QByteArray &bytes) {
        return reinterpret_cast<const unsigned char *>(bytes.constData());
    };
    const std::unique_ptr<EVP_PKEY, decltype(&EVP_PKEY_free)> pkey(
        EVP_PKEY_new_raw_public_key(EVP_PKEY_ED25519, nullptr, toUnsigned(publicKey), publicKey.size()), EVP_PKEY_free);
    const std::unique_ptr<EVP_MD_CTX, decltype(&EVP_MD_CTX_free)> context(EVP_MD_CTX_new(), EVP_MD_CTX_free);
    require(pkey && context && EVP_DigestVerifyInit(context.get(), nullptr, nullptr, nullptr, pkey.get()) == 1 &&
            EVP_DigestVerify(context.get(), toUnsigned(signature), signature.size(), toUnsigned(data), data.size()) == 1,
            "SIGNATURE_INVALID");
#else
    Q_UNUSED(key);
    require(false, "REVIEW_NOT_CONFIGURED");
#endif
    return parseUniqueObject(data, schema + " payload");
}

QJsonArray vector(const QJsonValue &value, qsizetype size)
{
    const auto array = value.toArray();
    require(array.size() == size, "INVALID_EFFECT_VECTOR");
    for (const auto &entry : array) {
        require(entry.isDouble() && std::isfinite(entry.toDouble()), "INVALID_EFFECT_VECTOR");
    }
    return array;
}

void checkBounds(const QJsonObject &effect, const QJsonObject &signedBounds, const QJsonObject &trustedBounds)
{
    requireFields(effect, {"carrier", "translation_mm", "rotation_xyzw"});
    const QSet<QString> boundFields{"carrier", "min_translation_mm", "max_translation_mm", "rotation_xyzw"};
    requireFields(signedBounds, boundFields);
    requireFields(trustedBounds, boundFields);
    const auto carrier = requiredText(signedBounds, "carrier");
    require(carrier == trustedBounds.value("carrier") && carrier == effect.value("carrier"), "CARRIER_NOT_APPROVED");
    const auto rotation = vector(signedBounds.value("rotation_xyzw"), 4);
    double normSquared = 0.0;
    for (const auto &component : rotation) {
        normSquared += component.toDouble() * component.toDouble();
    }
    require(std::abs(normSquared - 1.0) <= 1e-7 && rotation == trustedBounds.value("rotation_xyzw").toArray() &&
            rotation == effect.value("rotation_xyzw").toArray(), "ROTATION_NOT_APPROVED");
    const auto position = vector(effect.value("translation_mm"), 3);
    const auto minimum = vector(signedBounds.value("min_translation_mm"), 3);
    const auto maximum = vector(signedBounds.value("max_translation_mm"), 3);
    const auto trustedMinimum = vector(trustedBounds.value("min_translation_mm"), 3);
    const auto trustedMaximum = vector(trustedBounds.value("max_translation_mm"), 3);
    for (qsizetype axis = 0; axis < position.size(); ++axis) {
        require(minimum[axis].toDouble() >= trustedMinimum[axis].toDouble() &&
                maximum[axis].toDouble() <= trustedMaximum[axis].toDouble() &&
                minimum[axis].toDouble() <= position[axis].toDouble() &&
                position[axis].toDouble() <= maximum[axis].toDouble(), "TRANSLATION_OUTSIDE_BOUNDED_DOMAIN");
    }
}

void checkNativeInputs(const QDir &root, const QDir &source, const QDir &sandbox, const QJsonObject &trust,
                       const QJsonObject &bindings, bool testOnly)
{
    const auto profile = checkedFile(root, trust.value("profile"));
    const auto profileBytes = read(profile);
    require(digest(profileBytes) == requiredSha(bindings.value("profile_sha256")), "NATIVE_PROFILE_SHA256_MISMATCH");
    const auto closure = bindings.value("xlink_dependencies").toObject();
    require(!closure.isEmpty(), "EMPTY_XLINK_CLOSURE");
    const auto model = parseUniqueObject(profileBytes, profile);
    if (testOnly) {
        require(model.value("schema") == "v3.b1.bench_profile/1" && model.value("dependencies") == closure &&
                model.value("model_version") == bindings.value("model_version") &&
                model.value("source") == trust.value("source_root") && closure.contains(model.value("entry").toString()),
                "SYNTHETIC_PROFILE_MISMATCH");
    } else {
        require(trust.value("profile") == "docs/verification/v3/a/native_receipt.json" &&
                model.value("schema") == "drone-agricole.v3.a.native_receipt/1" && model.value("status") == "PASS" &&
                model.value("source_prefix") == trust.value("source_root") && model.value("inputs_sha256") == closure &&
                model.value("entry") == "hardware/mecanique/cartographe/assemblages/Prototype_Cartographe.FCStd" &&
                model.value("entry_sha256") == closure.value("assemblages/Prototype_Cartographe.FCStd"),
                "CARTOGRAPHER_PROFILE_MISMATCH");
    }
    for (auto row = closure.begin(); row != closure.end(); ++row) {
        const auto sourcePath = checkedFile(source, row.key());
        const auto sandboxPath = checkedFile(sandbox, row.key());
        const auto expected = requiredSha(row.value());
        require(!std::filesystem::equivalent(QFileInfo(sourcePath).filesystemAbsoluteFilePath(),
                QFileInfo(sandboxPath).filesystemAbsoluteFilePath()), "XLINK_SOURCE_NOT_INDEPENDENT_COPY");
        require(fileDigest(sourcePath) == expected && fileDigest(sandboxPath) == expected,
                "XLINK_DEPENDENCY_SHA256_MISMATCH");
    }
}

void checkTechnical(const QDir &raw, const QJsonObject &packet, const QJsonObject &policy, const QJsonObject &trust,
                    const QJsonObject &bindings, const QString &evidenceClass, QJsonObject &report)
{
    auto technical = validateMaterialPacket(raw, packet, policy, evidenceClass);
    const auto records = technical.value("records").toArray();
    bool rejected = records.isEmpty() || technical.value("rejected").toInt() != 0;
    bool inconclusive = false;
    QSet<QString> issues;
    for (const auto &entry : records) {
        const auto row = entry.toObject();
        rejected = rejected || row.value("status") == "FAIL";
        inconclusive = inconclusive || row.value("status") == "INCONCLUSIVE";
        issues.insert(row.value("issue").toString());
    }
    technical.insert("status", rejected ? "REJECTED" : inconclusive ? "INCONCLUSIVE" : "PENDING_AUTHORIZED_REVIEW");
    report.insert("technical", technical);
    require(!rejected, "TECHNICAL_REVIEW_REJECTED");
    require(!inconclusive, "TECHNICAL_REVIEW_INCONCLUSIVE");
    require(packet.value("configuration") == bindings.value("configuration") &&
            objectSha(policy.value("identities").toObject()) == bindings.value("lot_sha256"), "LOT_BINDING_MISMATCH");
    const auto required = trust.value("required_record_checks").toArray();
    QSet<QString> expected;
    for (const auto &value : required) {
        expected.insert(identifier(value));
    }
    require(!expected.isEmpty() && expected.size() == required.size(), "INVALID_TECHNICAL_COVERAGE_POLICY");
    for (const auto &entry : packet.value("records").toArray()) {
        const auto row = entry.toObject();
        require(expected.remove(requiredText(row, "check_id")) && row.value("review").isNull(),
                "TECHNICAL_COVERAGE_OR_EMBEDDED_REVIEW_MISMATCH");
        require(row.value("capture").toObject().value("author") != trust.value("reviewer_id"), "REVIEWER_IS_SUBMITTER");
    }
    require(expected.isEmpty(), "MISSING_REQUIRED_TECHNICAL_CHECKS");
    if (evidenceClass == "PHYSICAL_MEASURED") {
        require(issues.contains(QSet<QString>{"UART-ISO-001", "UART-MOUNT-001", "UART-ACCESS-001", "UART-GUIDES-001"}),
                "MISSING_PHYSICAL_EVIDENCE");
    }
}

QJsonObject checkRegistry(const QDir &trusted, const QJsonObject &trust, const QJsonObject &review,
                         const QString &reviewSha, const QString &requestSha, bool mutation, QJsonObject &report)
{
    const auto statePath = trusted.filePath("a5-consumption.json");
    require(!hasRedirectedComponent(trusted, statePath) &&
            !hasRedirectedComponent(trusted, trusted.filePath("a5-consumption.lock")), "REDIRECTED_REPLAY_STATE");
    QLockFile lock(trusted.filePath("a5-consumption.lock"));
    lock.setStaleLockTime(0);
    require(lock.tryLock(), "AUTHORITY_STATE_BUSY");
    const auto now = QDateTime::currentDateTimeUtc();
    require(utc(review.value("expires_at_utc")) > now && utc(review.value("issued_at_utc")) <= now,
            "REVIEW_EXPIRED_OR_IN_FUTURE");
    const auto registryBytes = read(checkedFile(trusted, trust.value("registry")));
    const auto registry = authenticate(registryBytes, "v3.a5.signed_registry/1",
                                      requiredSha(trust.value("registry_public_key_hex")));
    requireFields(registry, {"schema", "evidence_class", "events"});
    require(registry.value("schema") == "v3.a5.registry/1" && registry.value("evidence_class") == trust.value("evidence_class") &&
            registry.value("events").isArray(), "REGISTRY_SCOPE_MISMATCH");
    require(QFileInfo(statePath).isFile(), "REPLAY_STATE_NOT_PROVISIONED");
    const auto state = parseUniqueObject(read(statePath), statePath);
    requireFields(state, {"schema", "registry_events", "registry_prefix_sha256", "last_seen_utc", "consumed"});
    require(state.value("schema") == "v3.a5.consumption/1" && state.value("consumed").isObject(), "INVALID_REPLAY_STATE");
    require(utc(state.value("last_seen_utc")) <= now, "CLOCK_ROLLBACK");
    auto used = state.value("consumed").toObject();
    const auto previousSize = state.value("registry_events").toInt(-1);
    require(previousSize >= 0, "INVALID_REPLAY_STATE");
    const auto previousDigest = requiredSha(state.value("registry_prefix_sha256"));
    const auto events = registry.value("events").toArray();
    require(events.size() >= previousSize, "REGISTRY_ROLLBACK");
    QJsonArray prefix;
    QJsonObject issued;
    QSet<QString> revoked;
    QDateTime previousTime;
    for (const auto &entry : events) {
        const auto event = entry.toObject();
        requireFields(event, {"kind", "id", "review_sha256", "at_utc"});
        const auto id = identifier(event.value("id"));
        const auto sha = requiredSha(event.value("review_sha256"));
        const auto at = utc(event.value("at_utc"));
        require(at <= now && (!previousTime.isValid() || at >= previousTime), "REGISTRY_TIME_INVALID");
        previousTime = at;
        if (event.value("kind") == "ISSUED") {
            require(!issued.contains(id), "DUPLICATE_DECISION_ID");
            issued.insert(id, event);
        } else {
            require(event.value("kind") == "REVOKED" && issued.value(id).toObject().value("review_sha256") == sha &&
                    !revoked.contains(id), "INVALID_REVOCATION");
            revoked.insert(id);
        }
        if (prefix.size() < previousSize) {
            prefix.append(entry);
        }
    }
    const auto eventDigest = [](const QJsonArray &array) { return digest(QJsonDocument(array).toJson(QJsonDocument::Compact)); };
    require(eventDigest(prefix) == previousDigest, "REGISTRY_HISTORY_CHANGED");
    const auto id = identifier(review.value("id"));
    const auto issue = issued.value(id).toObject();
    const auto reason = issue.value("review_sha256") != reviewSha ? "DECISION_NOT_REGISTERED" :
        revoked.contains(id) ? "DECISION_REVOKED" : used.contains(id) ? "DECISION_ALREADY_USED" : "";
    if (QString(reason).isEmpty()) {
        require(utc(issue.value("at_utc")) >= utc(review.value("issued_at_utc")), "DECISION_REGISTERED_BEFORE_REVIEW");
        if (!mutation) {
            used.insert(id, QJsonObject{{"review_sha256", reviewSha}, {"request_sha256", requestSha},
                {"consumed_at_utc", now.toString(Qt::ISODate)}});
        }
    }
    // Reserve the admission before publishing any ALLOW. Losing the receipt then
    // requires a new review ID; it cannot make an already used decision reusable.
    write(statePath, {{"schema", "v3.a5.consumption/1"}, {"registry_events", events.size()},
        {"registry_prefix_sha256", eventDigest(events)}, {"last_seen_utc", now.toString(Qt::ISODate)}, {"consumed", used}});
    report.insert("registry_sha256", digest(registryBytes));
    require(QString(reason).isEmpty(), reason);
    return {{"decision_id", id}, {"consumed", !mutation}};
}

} // namespace

QJsonObject verifyAuthorityReview(const QDir &root, const QDir &sandbox, const QJsonObject &request,
                                 const QString &requestSha, const QString &trustPath, const QString &testTrustSha256, bool mutation)
{
    QJsonObject report{{"schema", "v3.a5.admission_result/1"}, {"finalized", true}, {"authority", "DENY"},
        {"technical", QJsonObject{{"status", "NOT_RUN"}}}, {"review", QJsonObject{{"status", "NOT_RUN"}}},
        {"admission", QJsonObject{{"decision", "DENY"}, {"execution_scope", "READ_ONLY_IMPACT"}}},
        {"candidate_transactions", 0}, {"construction_result", "NOT_RUN"}, {"physical_reception", "NOT_RUN"},
        {"cartographer_mutation", "DENY"}, {"request_sha256", requestSha}};
    try {
        requireFields(request, {"schema", "evidence_class", "domain", "bindings", "effect", "submission"});
        require(request.value("schema") == a5AdmissionSchema, "CONTRACT_VERSION_UNSUPPORTED");
        const auto evidenceClass = requiredText(request, "evidence_class");
        const bool testOnly = evidenceClass == "TEST_ONLY";
        const auto domain = requiredText(request, "domain");
        require((testOnly && domain == "SYNTHETIC_BENCH") || (!testOnly && evidenceClass == "PHYSICAL_MEASURED" &&
                domain == "CARTOGRAPHER_PRIVATE_CAD"), "EVIDENCE_CLASS_OR_DOMAIN_DENIED");
        require(relative(root, sandbox.absolutePath()).startsWith(".runtime/"), "ACTIVE_REFERENCE_OR_NONPRIVATE_SANDBOX");
        const auto pin = testOnly ? testTrustSha256 : QStringLiteral(V3_A5_PHYSICAL_TRUST_SHA256);
        require(!pin.isEmpty() && !trustPath.isEmpty(), "REVIEW_NOT_CONFIGURED");
        require(testOnly || testTrustSha256.isEmpty(), "TEST_TRUST_NOT_ALLOWED_FOR_PHYSICAL");
#ifndef V3_A5_CRYPTO
        require(false, "REVIEW_NOT_CONFIGURED");
#endif
        const auto submission = request.value("submission").toObject();
        requireFields(submission, {"raw_root", "packet", "review"});
        const auto raw = checkedDirectory(root, submission.value("raw_root"));
        require(relative(root, raw.absolutePath()).startsWith(".runtime/"), "SUBMISSION_NOT_PRIVATE");
        const QFileInfo info(trustPath);
        const auto trustedPath = QDir::cleanPath(QDir::fromNativeSeparators(info.absoluteFilePath()));
        const auto canonical = info.canonicalFilePath();
        const QDir trusted(info.absolutePath());
        require(info.isFile() && canonical == trustedPath && !info.isSymLink() && !info.isJunction() &&
                !within(raw, trusted.absolutePath()) && !within(trusted, raw.absolutePath()) &&
                !within(sandbox, trusted.absolutePath()) && !within(trusted, sandbox.absolutePath()), "TRUST_INSIDE_SUBMISSION_OR_REDIRECTED");
        const auto trustBytes = read(canonical);
        require(digest(trustBytes) == requiredSha(pin), "TRUST_SHA256_MISMATCH");
        const auto trust = parseUniqueObject(trustBytes, canonical);
        requireFields(trust, {"schema", "trusted_root", "evidence_class", "domain", "bindings", "bounds", "material_policy",
            "material_policy_sha256", "profile", "source_root", "reviewer_id", "reviewer_public_key_hex", "registry",
            "registry_public_key_hex", "required_record_checks"});
        require(trust.value("schema") == "v3.a5.trust/1" && trust.value("evidence_class") == evidenceClass &&
                trust.value("domain") == domain && trust.value("trusted_root") == trusted.canonicalPath(), "TRUST_SCOPE_MISMATCH");
        const auto reviewer = identifier(trust.value("reviewer_id"));
        const auto reviewerKey = requiredSha(trust.value("reviewer_public_key_hex"));
        require(reviewerKey != requiredSha(trust.value("registry_public_key_hex")), "REVIEW_AND_REGISTRY_KEYS_NOT_DISTINCT");
        const auto bindings = request.value("bindings").toObject();
        requireFields(bindings, {"configuration", "model_version", "occurrence", "operation", "lot_sha256", "profile_sha256",
            "xlink_dependencies", "required_checks"});
        require(bindings == trust.value("bindings") && bindings.value("required_checks") == receivingChecks, "TRUST_BINDING_MISMATCH");
        require(bindings.value("operation") == "CREATE_SUPPORT", "AUTHORITY_OPERATION_UNSUPPORTED");
        requiredText(bindings, "model_version");
        requiredText(bindings, "occurrence");
        const auto source = checkedDirectory(root, trust.value("source_root"));
        require(!within(source, sandbox.absolutePath()) && !within(sandbox, source.absolutePath()), "XLINK_SOURCE_NOT_INDEPENDENT_COPY");
        if (!testOnly) {
            require(bindings.value("occurrence") == "anchor:iso-carrier" &&
                    trust.value("source_root") == "hardware/mecanique/cartographe" &&
                    QStringList{"P64", "P66"}.contains(trust.value("bounds").toObject().value("carrier").toString()),
                    "PHYSICAL_OPERATION_UNSUPPORTED");
        } else {
            require(relative(root, source.absolutePath()).startsWith("docs/electromechanical_v3/bench_"), "TEST_SOURCE_NOT_SYNTHETIC");
        }
        checkNativeInputs(root, source, sandbox, trust, bindings, testOnly);
        const auto policyPath = checkedFile(trusted, trust.value("material_policy"));
        const auto policyBytes = read(policyPath);
        const auto policySha = digest(policyBytes);
        require(policySha == requiredSha(trust.value("material_policy_sha256")), "MATERIAL_POLICY_SHA256_MISMATCH");
        const auto packetPath = checkedFile(raw, submission.value("packet"));
        const auto packetBytes = read(packetPath);
        const auto packetSha = digest(packetBytes);
        checkTechnical(raw, parseUniqueObject(packetBytes, packetPath), parseUniqueObject(policyBytes, policyPath), trust,
                       bindings, evidenceClass, report);

        report.insert("trust_sha256", pin);
        report.insert("packet_sha256", packetSha);
        report.insert("material_policy_sha256", policySha);
        require(!submission.value("review").isNull(), "SIGNED_REVIEW_REQUIRED");
        report.insert("review", QJsonObject{{"status", "REJECTED"}});
        const auto reviewBytes = read(checkedFile(raw, submission.value("review")));
        const auto reviewSha = digest(reviewBytes);
        const auto review = authenticate(reviewBytes, "v3.a5.signed_review/1", reviewerKey);
        report.insert("review", QJsonObject{{"status", "SIGNATURE_VERIFIED"}, {"reviewer_id", reviewer}, {"sha256", reviewSha},
            {"signature_algorithm", "Ed25519"}});
        requireFields(review, {"schema", "id", "reviewer_id", "evidence_class", "domain", "bindings", "packet_sha256", "policy_sha256",
            "issued_at_utc", "expires_at_utc", "disposition", "bounds"});
        require(review.value("schema") == "v3.a5.review/1" && review.value("reviewer_id") == reviewer &&
                review.value("disposition") == "APPROVE_BOUNDED_EXPERIMENT", "REVIEWER_OR_DISPOSITION_NOT_APPROVED");
        require(review.value("domain") == domain && review.value("evidence_class") == evidenceClass &&
                review.value("bindings") == bindings && review.value("packet_sha256") == packetSha &&
                review.value("policy_sha256") == policySha, "SIGNED_REVIEW_BINDING_MISMATCH");
        const auto now = QDateTime::currentDateTimeUtc();
        const auto issuedAt = utc(review.value("issued_at_utc"));
        const auto expiry = utc(review.value("expires_at_utc"));
        require(issuedAt <= now && expiry > now && expiry > issuedAt, "REVIEW_EXPIRED_OR_IN_FUTURE");
        checkBounds(request.value("effect").toObject(), review.value("bounds").toObject(), trust.value("bounds").toObject());
        auto decision = checkRegistry(trusted, trust, review, reviewSha, requestSha, mutation, report);
        require(!mutation, testOnly ? "TEST_ONLY_ADMISSION_NO_CONSTRUCTION" : "AUTHORITY_NATIVE_CONSTRUCTION_NOT_CONFIGURED");
        const auto scope = testOnly ? "TEST_ONLY" : "BOUNDED_CAD_EXPERIMENT";
        decision.insert("decision", "ALLOW");
        decision.insert("execution_scope", scope);
        decision.insert("bindings", bindings);
        decision.insert("effect", request.value("effect"));
        report.insert("admission", decision);
        report.insert("authority", scope);
    } catch (const std::exception &error) {
        const auto reason = QString::fromUtf8(error.what());
        if (reason == "REVIEW_NOT_CONFIGURED") {
            report.insert("review", QJsonObject{{"status", "REVIEW_NOT_CONFIGURED"}});
        }
        report.insert("reason", reason);
    }
    return report;
}

} // namespace convergence
