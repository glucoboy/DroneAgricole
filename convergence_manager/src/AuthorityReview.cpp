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

QString checkedFile(const QDir &root, const QJsonValue &value, bool unshared = false)
{
    const auto name = relativeName(value);
    require(!hasRedirectedComponent(root, root.absoluteFilePath(name)), "REDIRECTED_FILE");
    const auto path = fileInside(root, name);
    require(relative(root, path) == name, "FILE_PATH_MISMATCH");
    if (unshared) {
        require(std::filesystem::hard_link_count(QFileInfo(path).filesystemFilePath()) == 1, "SHARED_FILE");
    }
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
                       const QJsonObject &bindings, bool testOnly, bool unshared)
{
    const auto profile = checkedFile(root, trust.value("profile"), unshared);
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
        const auto sourcePath = checkedFile(source, row.key(), unshared);
        const auto sandboxPath = checkedFile(sandbox, row.key(), unshared);
        const auto expected = requiredSha(row.value());
        require(!std::filesystem::equivalent(QFileInfo(sourcePath).filesystemAbsoluteFilePath(),
                QFileInfo(sandboxPath).filesystemAbsoluteFilePath()), "XLINK_SOURCE_NOT_INDEPENDENT_COPY");
        require(fileDigest(sourcePath) == expected && fileDigest(sandboxPath) == expected,
                "XLINK_DEPENDENCY_SHA256_MISMATCH");
    }
}

void checkTechnical(const QDir &raw, const QJsonObject &packet, const QJsonObject &policy, const QJsonObject &trust,
                    const QJsonObject &bindings, const QString &evidenceClass, QJsonObject &report,
                    const QString &authorizedCarrier = {})
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
    bool mountCovered = false;
    for (const auto &entry : packet.value("records").toArray()) {
        const auto row = entry.toObject();
        require(expected.remove(requiredText(row, "check_id")) && row.value("review").isNull(),
                "TECHNICAL_COVERAGE_OR_EMBEDDED_REVIEW_MISMATCH");
        require(row.value("capture").toObject().value("author") != trust.value("reviewer_id"), "REVIEWER_IS_SUBMITTER");
        if (!authorizedCarrier.isEmpty() && row.value("issue") == "UART-MOUNT-001") {
            require(row.value("facts").toObject().value("carrier") == authorizedCarrier &&
                    row.value("subject") == bindings.value("occurrence"), "CARRIER_EVIDENCE_MISMATCH");
            mountCovered = true;
        }
    }
    require(expected.isEmpty(), "MISSING_REQUIRED_TECHNICAL_CHECKS");
    require(authorizedCarrier.isEmpty() || mountCovered, "MISSING_CARRIER_EVIDENCE");
    if (evidenceClass == "PHYSICAL_MEASURED") {
        require(issues.contains(QSet<QString>{"UART-ISO-001", "UART-MOUNT-001", "UART-ACCESS-001", "UART-GUIDES-001"}),
                "MISSING_PHYSICAL_EVIDENCE");
    }
}

QJsonObject checkRegistry(const QDir &trusted, const QJsonObject &trust, const QJsonObject &review,
                         const QString &reviewSha, const QString &requestSha, bool mutation, QJsonObject &report,
                         AuthorizedReview authorized, const AuthorityRegistryHook &hook, bool finalizing)
{
    const auto statePath = trusted.filePath("a5-consumption.json");
    require(!hasRedirectedComponent(trusted, statePath) &&
            !hasRedirectedComponent(trusted, trusted.filePath("a5-consumption.lock")), "REDIRECTED_REPLAY_STATE");
    QLockFile lock(trusted.filePath("a5-consumption.lock"));
    lock.setStaleLockTime(0);
    require(lock.tryLock(finalizing ? 3000 : 0), "AUTHORITY_STATE_BUSY");
    const auto now = QDateTime::currentDateTimeUtc();
    require(utc(review.value("expires_at_utc")) > now && utc(review.value("issued_at_utc")) <= now,
            "REVIEW_EXPIRED_OR_IN_FUTURE");
    const auto registryBytes = read(checkedFile(trusted, trust.value("registry"), bool(hook)));
    const auto registry = authenticate(registryBytes, "v3.a5.signed_registry/1",
                                      requiredSha(trust.value("registry_public_key_hex")));
    requireFields(registry, {"schema", "evidence_class", "events"});
    require(registry.value("schema") == "v3.a5.registry/1" && registry.value("evidence_class") == trust.value("evidence_class") &&
            registry.value("events").isArray(), "REGISTRY_SCOPE_MISMATCH");
    require(QFileInfo(statePath).isFile(), "REPLAY_STATE_NOT_PROVISIONED");
    if (hook) {
        checkedFile(trusted, "a5-consumption.json", true);
    }
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
    const auto prior = used.value(id).toObject();
    const bool isExactReservation = prior.value("review_sha256") == reviewSha && prior.value("request_sha256") == requestSha;
    const QString reason = issue.value("review_sha256") != reviewSha ? "DECISION_NOT_REGISTERED" :
        revoked.contains(id) ? "DECISION_REVOKED" :
        finalizing && !isExactReservation ? "AUTHORITY_RESERVATION_MISMATCH" :
        !finalizing && used.contains(id) ? "DECISION_ALREADY_USED" : "";
    if (reason.isEmpty()) {
        require(utc(issue.value("at_utc")) >= utc(review.value("issued_at_utc")), "DECISION_REGISTERED_BEFORE_REVIEW");
        if (finalizing) {
            require(utc(prior.value("consumed_at_utc")) <= now, "CLOCK_ROLLBACK");
        } else if (!mutation || hook) {
            used.insert(id, QJsonObject{{"review_sha256", reviewSha}, {"request_sha256", requestSha},
                {"consumed_at_utc", now.toString(Qt::ISODate)}});
        }
    }
    authorized.registrySha256 = digest(registryBytes);
    report.insert("registry_sha256", authorized.registrySha256);
    const QJsonObject nextState{{"schema", "v3.a5.consumption/1"}, {"registry_events", events.size()},
        {"registry_prefix_sha256", eventDigest(events)}, {"last_seen_utc", now.toString(Qt::ISODate)}, {"consumed", used}};
    if (finalizing) {
        // The last durable transaction transition runs under this lock. Refresh
        // the registry watermark first, before the hook can commit a receipt.
        write(statePath, nextState);
    }
    if (hook) {
        hook(authorized, events, now, reason);
    }
    if (!finalizing) {
        // The journal reservation precedes both this compatibility state and
        // native execution. Losing either a state write or a receipt cannot free it.
        write(statePath, nextState);
    }
    require(reason.isEmpty(), reason);
    return {{"decision_id", id}, {"consumed", !mutation || bool(hook)}};
}

} // namespace

QJsonObject verifyAuthorityReview(const QDir &root, const QDir &sandbox, const QJsonObject &request,
                                 const QString &requestSha, const QString &trustPath, const QString &testTrustSha256,
                                 bool mutation, const AuthorityRegistryHook &hook, bool finalizing)
{
    const bool nativeReview = request.value("schema") == a6AdmissionSchema;
    QJsonObject report{{"schema", nativeReview ? "v3.a6.admission_result/1" : "v3.a5.admission_result/1"},
        {"finalized", true}, {"authority", "DENY"},
        {"technical", QJsonObject{{"status", "NOT_RUN"}}}, {"review", QJsonObject{{"status", "NOT_RUN"}}},
        {"admission", QJsonObject{{"decision", "DENY"}, {"execution_scope", "READ_ONLY_IMPACT"}}},
        {"candidate_transactions", 0}, {"construction_result", "NOT_RUN"}, {"physical_reception", "NOT_RUN"},
        {"cartographer_mutation", "DENY"}, {"request_sha256", requestSha}};
    try {
        requireFields(request, {"schema", "evidence_class", "domain", "bindings", "effect", "submission"});
        require(nativeReview || request.value("schema") == a5AdmissionSchema, "CONTRACT_VERSION_UNSUPPORTED");
        const auto evidenceClass = requiredText(request, "evidence_class");
        const bool testOnly = evidenceClass == "TEST_ONLY";
        const auto domain = requiredText(request, "domain");
        require((testOnly && domain == "SYNTHETIC_BENCH") || (!testOnly && evidenceClass == "PHYSICAL_MEASURED" &&
                domain == "CARTOGRAPHER_PRIVATE_CAD"), "EVIDENCE_CLASS_OR_DOMAIN_DENIED");
        if (nativeReview) {
            require(testOnly, "PHYSICAL_ADMISSION_NOT_CONFIGURED");
            require(mutation && hook, "NATIVE_TRANSACTION_REQUIRED");
        } else {
            require(!hook && !finalizing, "NATIVE_REVIEW_REQUIRED");
        }
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
        if (nativeReview) {
            const auto name = relative(root, canonical);
            require(name.startsWith(".runtime/"), "TEST_TRUST_NOT_PRIVATE");
            checkedFile(root, name, true);
        }
        const auto trustBytes = read(canonical);
        require(digest(trustBytes) == requiredSha(pin), "TRUST_SHA256_MISMATCH");
        const auto trust = parseUniqueObject(trustBytes, canonical);
        QSet<QString> trustFields{"schema", "trusted_root", "evidence_class", "domain", "bindings", "bounds", "material_policy",
            "material_policy_sha256", "profile", "source_root", "reviewer_id", "reviewer_public_key_hex", "registry",
            "registry_public_key_hex", "required_record_checks"};
        if (nativeReview) {
            trustFields.insert("journal_key_sha256");
        }
        requireFields(trust, trustFields);
        require(trust.value("schema") == (nativeReview ? "v3.a6.trust/1" : "v3.a5.trust/1") &&
                trust.value("evidence_class") == evidenceClass &&
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
        const auto effect = request.value("effect").toObject();
        auto pose = effect;
        QString journalKeySha;
        if (nativeReview) {
            require(bindings.value("occurrence") == "anchor:iso-carrier", "AUTHORITY_OPERATION_UNSUPPORTED");
            require(QStringList{"P64", "P66"}.contains(effect.value("carrier").toString()), "CARRIER_NOT_APPROVED");
            const auto dimensions = vector(pose.take("size_mm"), 3);
            for (const auto &dimension : dimensions) {
                require(dimension.toDouble() > 0.0, "INVALID_SUPPORT_SIZE");
            }
            journalKeySha = requiredSha(trust.value("journal_key_sha256"));
        }
        checkNativeInputs(root, source, sandbox, trust, bindings, testOnly, nativeReview);
        const auto policyPath = checkedFile(trusted, trust.value("material_policy"), nativeReview);
        const auto policyBytes = read(policyPath);
        const auto policySha = digest(policyBytes);
        require(policySha == requiredSha(trust.value("material_policy_sha256")), "MATERIAL_POLICY_SHA256_MISMATCH");
        const auto packetPath = checkedFile(raw, submission.value("packet"), nativeReview);
        const auto packetBytes = read(packetPath);
        const auto packetSha = digest(packetBytes);
        checkTechnical(raw, parseUniqueObject(packetBytes, packetPath), parseUniqueObject(policyBytes, policyPath), trust,
                       bindings, evidenceClass, report, nativeReview ? effect.value("carrier").toString() : QString{});

        report.insert("trust_sha256", pin);
        report.insert("packet_sha256", packetSha);
        report.insert("material_policy_sha256", policySha);
        require(!submission.value("review").isNull(), "SIGNED_REVIEW_REQUIRED");
        report.insert("review", QJsonObject{{"status", "REJECTED"}});
        const auto reviewBytes = read(checkedFile(raw, submission.value("review"), nativeReview));
        const auto reviewSha = digest(reviewBytes);
        const auto review = authenticate(reviewBytes, "v3.a5.signed_review/1", reviewerKey);
        report.insert("review", QJsonObject{{"status", "SIGNATURE_VERIFIED"}, {"reviewer_id", reviewer}, {"sha256", reviewSha},
            {"signature_algorithm", "Ed25519"}});
        QSet<QString> reviewFields{"schema", "id", "reviewer_id", "evidence_class", "domain", "bindings", "packet_sha256", "policy_sha256",
            "issued_at_utc", "expires_at_utc", "disposition", "bounds"};
        if (nativeReview) {
            reviewFields.unite({"authorized_effect", "evidence_package", "trust_sha256"});
        }
        requireFields(review, reviewFields);
        require(review.value("schema") == (nativeReview ? "v3.a6.review/1" : "v3.a5.review/1") && review.value("reviewer_id") == reviewer &&
                review.value("disposition") == "APPROVE_BOUNDED_EXPERIMENT", "REVIEWER_OR_DISPOSITION_NOT_APPROVED");
        require(review.value("domain") == domain && review.value("evidence_class") == evidenceClass &&
                review.value("bindings") == bindings && review.value("packet_sha256") == packetSha &&
                review.value("policy_sha256") == policySha, "SIGNED_REVIEW_BINDING_MISMATCH");
        const auto now = QDateTime::currentDateTimeUtc();
        const auto issuedAt = utc(review.value("issued_at_utc"));
        const auto expiry = utc(review.value("expires_at_utc"));
        require(issuedAt <= now && expiry > now && expiry > issuedAt, "REVIEW_EXPIRED_OR_IN_FUTURE");
        if (nativeReview) {
            require(review.value("authorized_effect") == effect && review.value("trust_sha256") == pin &&
                    review.value("evidence_package") == a6EvidencePackage, "SIGNED_NATIVE_EFFECT_OR_PACKAGE_MISMATCH");
        }
        checkBounds(pose, review.value("bounds").toObject(), trust.value("bounds").toObject());
        const auto authorizedEffect = nativeReview ? review.value("authorized_effect").toObject() : effect;
        const AuthorizedReview authorized{trusted, journalKeySha, identifier(review.value("id")), reviewSha, requestSha,
            trust.value("profile").toString(), pin, bindings, authorizedEffect, expiry, {}};
        auto decision = checkRegistry(trusted, trust, review, reviewSha, requestSha, mutation, report, authorized, hook, finalizing);
        require(!mutation || nativeReview, testOnly ? "TEST_ONLY_ADMISSION_NO_CONSTRUCTION" : "AUTHORITY_NATIVE_CONSTRUCTION_NOT_CONFIGURED");
        const auto scope = testOnly ? "TEST_ONLY" : "BOUNDED_CAD_EXPERIMENT";
        decision.insert("decision", "ALLOW");
        decision.insert("execution_scope", scope);
        decision.insert("bindings", bindings);
        decision.insert("effect", effect);
        if (nativeReview) {
            decision.insert("authorized_effect", authorizedEffect);
            decision.insert("evidence_package", a6EvidencePackage);
        }
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
