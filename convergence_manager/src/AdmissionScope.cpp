#include "AdmissionScope.hpp"
#include "Files.hpp"

#include <QFile>
#include <QFileInfo>
#include <QJsonArray>
#include <QJsonDocument>
#include <QRegularExpression>
#include <QSet>
#include <filesystem>

namespace convergence {
namespace {

const QString version = "v3.admission_scope/1";
const QString benchDirectory = "docs/electromechanical_v3/bench_a1/";
const QString benchSealSha = "cf321988adf7169e122de0523c013079e0e3892891475ea5e7710290702e3db8";
const QString v3aDirectory = "docs/verification/v3/a/";
const QString freezeSha = "f324a2a0e2feeb1d68df906927306c25ae625b325488677dafcba73256794981";
const QString acceptanceSha = "9d8bba426e3e62970f4d6206b06f7fd2b2ffa2ae5be1bf4320c987a2c7039b31";
const QString graphSha = "9e73d314b74a14ca482fed4c146e58d9e051310a9924bc41af8f09cc9b5ef79f";
const QString cartographeAuthoritySha = "5beef44e6816117dea2630e24edbff0762b5d38b3177bc0de332858f5a500d4d";
const QString nativeReceiptSha = "f7b4d421f301cb62b4c59dadc900d4dad535af6788efdc8a1a335e9a2e30e7b8";
const QString oracleSha = "298df30d6bdb1acceb6906d20bc0cf617aafa83ee69b30fb9fc547daa1d821a8";
const QString cartographeId = "prototype_cartographe_sans_dock";
const QString cartographeVersion = "742a5ac4f167bba0ef03b65053412bddbde0ecc9";
const QString benchDomain = "SYNTHETIC_BENCH";
const QString copyDomain = "CARTOGRAPHER_PRIVATE_CAD";
const QString designDomain = "CARTOGRAPHER_DESIGN_ADMISSION";
const QString physicalDomain = "PHYSICAL_RECEPTION";
const QString analysis = "ANALYZE_IMPACT";

const QSet<QString> domains{benchDomain, copyDomain, designDomain, physicalDomain};
const QSet<QString> operations{analysis, "REPOSITION_DEVICE", "REROUTE_HARNESS", "RELOCATE_SUPPORT",
    "CREATE_SUPPORT", "CHANGE_CONNECTOR_VARIANT", "CHANGE_INTERFACE_TOPOLOGY", "RECEIVE_PHYSICAL"};
const QSet<QString> mandatoryConstraints{"BMS_USB_STRUCTURE_ISOLATION", "NC", "TX_RX", "PROTECTIONS",
    "PINOUT", "INDEPENDENT_FRAMES", "GEOMETRY", "SUPPORT_ANCHOR", "SERVICE", "IMMUTABLE_SOURCES",
    "DYNAMIC_BEND_RADIUS"};
const QStringList textFields{"schema", "domain", "model_id", "model_version", "freeze_sha256",
    "geometry_sha256", "occurrence", "operation", "objective", "context", "output", "source_mode", "rollback"};
const QStringList objectFields{"xlink_dependencies", "effect", "authorities", "constraints"};
const QStringList arrayFields{"validations", "assumptions", "risks"};

bool sha256(const QString &value)
{
    static const QRegularExpression pattern("\\A[0-9a-f]{64}\\z");
    return pattern.match(value).hasMatch();
}

bool canonicalRelative(const QString &path)
{
    const auto segments = path.split('/');
    for (const auto &segment : segments) {
        if (segment.isEmpty() || segment.endsWith('.') || segment.endsWith(' '))
            return false;
    }
    return QDir::isRelativePath(path) && QDir::cleanPath(path) == path &&
        !path.contains('\\') && !path.contains(':') && !path.contains(QChar::Null);
}

QString exactFile(const QDir &root, const QString &name)
{
    require(canonicalRelative(name), "Chemin de preuve non canonique : " + name);
    const auto expected = root.absoluteFilePath(name);
    const QFileInfo info(expected);
    require(info.isFile() && !hasRedirectedComponent(root, expected) &&
        info.canonicalFilePath() == expected, "Preuve absente ou redirigée : " + name);
    return expected;
}

QJsonObject sealedObject(const QDir &root, const QString &path, const QString &sha)
{
    const auto bytes = read(exactFile(root, path));
    require(digest(bytes) == sha, "Empreinte de preuve divergente : " + path);
    return parse(bytes, path);
}

bool stringArray(const QJsonValue &value)
{
    if (!value.isArray())
        return false;
    QSet<QString> seen;
    for (const auto &entry : value.toArray()) {
        const auto string = entry.toString();
        if (string.trimmed().isEmpty() || seen.contains(string))
            return false;
        seen.insert(string);
    }
    return true;
}

bool validShape(const QJsonObject &request)
{
    if (request.size() != textFields.size() + objectFields.size() + arrayFields.size())
        return false;
    for (const auto &key : textFields)
        if (request.value(key).toString().trimmed().isEmpty())
            return false;
    for (const auto &key : objectFields)
        if (!request.value(key).isObject())
            return false;
    for (const auto &key : arrayFields)
        if (!stringArray(request.value(key)))
            return false;
    const auto authorities = request.value("authorities").toObject();
    for (auto it = authorities.begin(); it != authorities.end(); ++it)
        if (!it.value().toString().startsWith('/'))
            return false;
    return sha256(request.value("freeze_sha256").toString()) &&
        sha256(request.value("geometry_sha256").toString()) && !request.value("risks").toArray().isEmpty();
}

bool validDependencies(const QJsonObject &dependencies)
{
    for (auto it = dependencies.begin(); it != dependencies.end(); ++it)
        if (!canonicalRelative(it.key()) || !sha256(it.value().toString()))
            return false;
    return true;
}

bool privateSandbox(const QDir &root, const QDir &sandbox)
{
    const auto name = root.relativeFilePath(sandbox.absolutePath());
    return (name.startsWith(".runtime/") || name.startsWith("results/")) &&
        canonicalRelative(name) && !hasRedirectedComponent(root, sandbox.absolutePath()) &&
        sandbox.canonicalPath() == sandbox.absolutePath();
}

void verifyDependencies(const QDir &sandbox, const QJsonObject &dependencies, bool readOnly = false)
{
    for (auto it = dependencies.begin(); it != dependencies.end(); ++it) {
        const auto path = exactFile(sandbox, it.key());
        const QFileInfo info(path);
        const auto writeBits = QFile::WriteOwner | QFile::WriteGroup | QFile::WriteOther;
        require(!readOnly || !(info.permissions() & writeBits), "Entrée XLink ouverte en écriture : " + it.key());
        require(std::filesystem::hard_link_count(info.filesystemFilePath()) == 1, "Dépendance XLink partagée : " + it.key());
        require(fileDigest(path) == it.value(), "Dépendance XLink altérée : " + it.key());
    }
}

QJsonValue authorityObservation(const QJsonObject &authority, const QString &locator)
{
    if (!locator.startsWith('/'))
        return {};
    QJsonValue value(authority);
    for (const auto &field : locator.mid(1).split('/'))
        value = value.toObject().value(field);
    return value;
}

QJsonObject ref(const QString &path, const QString &sha, const QString &locator = {})
{
    return {{"path", path}, {"sha256", sha}, {"locator", locator}};
}

class Decision {
public:
    explicit Decision(const QJsonObject &request) : request_(request) {}

    void verified(const QString &check) { verified_.append(check); }
    void controls(const QJsonArray &checks) { controls_ = checks; }
    void bind(const QString &key, const QJsonObject &proof) { proofs_.insert(key, proof); }
    void issues(const QJsonArray &issues) { issues_ = issues; }

    QJsonObject allow(const QString &reason, const QString &scope) const
    {
        return result("ALLOW", reason, scope, {});
    }

    QJsonObject stop(const QString &reason, const QJsonArray &unmet = {},
                     const QString &decision = "DENY") const
    {
        return result(decision, reason, "NONE", unmet.isEmpty() ? QJsonArray{reason} : unmet);
    }

private:
    QJsonObject result(const QString &decision, const QString &reason, const QString &scope,
                       const QJsonArray &unmet) const
    {
        const auto operation = request_.value("operation").toString();
        const QJsonArray action = operation.isEmpty() ? QJsonArray{} : QJsonArray{operation};
        const auto reportedStrings = [&](const QString &key) {
            const auto value = request_.value(key);
            return stringArray(value) ? value.toArray() : QJsonArray{};
        };
        const QJsonObject context{{"policy", version}, {"request", request_}, {"resolved_authorities", proofs_},
            {"verified_preconditions", verified_}, {"unmet_preconditions", unmet}, {"decision", decision}, {"reason", reason}};
        return {{"schema", version}, {"decision", decision}, {"reason", reason}, {"execution_scope", scope},
            {"domain", request_.value("domain").toString()}, {"model_id", request_.value("model_id").toString()},
            {"operation", operation}, {"occurrence", request_.value("occurrence").toString()},
            {"verified_preconditions", verified_}, {"unmet_preconditions", unmet},
            {"assumptions", reportedStrings("assumptions")}, {"risks", reportedStrings("risks")},
            {"allowed_operations", decision == "ALLOW" ? action : QJsonArray{}},
            {"blocked_operations", decision == "ALLOW" ? QJsonArray{} : action}, {"mandatory_checks", controls_},
            {"resolved_authorities", proofs_}, {"open_issues", issues_},
            {"context_sha256", digest(QJsonDocument(context).toJson(QJsonDocument::Compact))}};
    }

    const QJsonObject &request_;
    QJsonObject proofs_;
    QJsonArray verified_;
    QJsonArray controls_;
    QJsonArray issues_;
};

QJsonObject evaluateBench(const QDir &root, const QDir &sandbox, const QJsonObject &request, Decision &result)
{
    if (request.value("freeze_sha256") != benchSealSha)
        return result.stop("FREEZE_SHA_MISMATCH");
    QJsonObject seal;
    QJsonObject authority;
    QString authorityPath;
    QString authoritySha;
    try {
        seal = sealedObject(root, benchDirectory + "seal.json", benchSealSha);
        require(seal.value("schema") == "v3.admission_bench_seal/1", "Version de sceau incompatible");
        authorityPath = benchDirectory + seal.value("authority").toObject().value("path").toString();
        authoritySha = seal.value("authority").toObject().value("sha256").toString();
        authority = sealedObject(root, authorityPath, authoritySha);
        sealedObject(root, benchDirectory + "geometry.json", seal.value("geometry_sha256").toString());
    } catch (const std::exception &) {
        return result.stop("TRUSTED_BENCH_EVIDENCE_MISMATCH");
    }
    result.bind("BENCH_SEAL", ref(benchDirectory + "seal.json", benchSealSha));
    result.bind("BENCH_GEOMETRY", ref(benchDirectory + "geometry.json", seal.value("geometry_sha256").toString()));
    result.verified("BENCH_EVIDENCE_SEALED");
    if (request.value("model_id") != seal.value("model_id") || request.value("model_version") != seal.value("model_version"))
        return result.stop("MODEL_ID_OR_VERSION_MISMATCH");
    if (request.value("geometry_sha256") != seal.value("geometry_sha256"))
        return result.stop("GEOMETRY_SIGNATURE_MISMATCH");
    if (request.value("context") != "B1_CLOSED_BENCH" || request.value("output") != "PRIVATE_CANDIDATE" ||
        request.value("rollback") != "DISCARD_PRIVATE_COPY" || !request.value("assumptions").toArray().isEmpty())
        return result.stop("BENCH_SCOPE_MISMATCH");
    const auto operation = seal.value("operations").toObject().value(request.value("operation").toString()).toObject();
    if (operation.isEmpty())
        return result.stop("BENCH_OPERATION_UNSUPPORTED", {}, "UNSUPPORTED");
    result.controls(operation.value("validations").toArray());
    if (request.value("occurrence") != operation.value("occurrence") || request.value("effect") != operation.value("effect"))
        return result.stop("OCCURRENCE_OR_EFFECT_MISMATCH");
    if (request.value("validations") != operation.value("validations"))
        return result.stop("VALIDATION_SET_MISMATCH");
    if (request.value("constraints") != operation.value("constraints"))
        return result.stop("CONSTRAINT_SET_MISMATCH");
    if (request.value("authorities") != operation.value("authorities"))
        return result.stop("AUTHORITY_SET_MISMATCH");
    const auto constraints = operation.value("constraints").toObject();
    const auto locators = operation.value("authorities").toObject();
    const auto authorityConstraints = authority.value("constraints").toObject();
    for (const auto &id : mandatoryConstraints) {
        const auto observation = authorityObservation(authority, constraints.value(id).toObject().value("evidence").toString());
        if (!constraints.value(id).isObject() || constraints.value(id) != authorityConstraints.value(id) ||
            locators.value(id) != ("/constraints/" + id) || observation.isUndefined() || observation.isNull())
            return result.stop("BENCH_CONSTRAINT_UNPROVEN", {id});
        result.bind(id, ref(authorityPath, authoritySha, locators.value(id).toString()));
    }
    result.verified("OPERATION_TARGET_EFFECT_BOUND");
    result.verified("NON_RELAXABLE_CONSTRAINTS_BOUND");
    result.verified("VALIDATION_AND_ROLLBACK_BOUND");
    const auto dependencies = seal.value("xlink_dependencies").toObject();
    if (request.value("xlink_dependencies") != dependencies || !dependencies.contains(seal.value("entry").toString()))
        return result.stop("XLINK_CLOSURE_MISMATCH");
    if (!privateSandbox(root, sandbox))
        return result.stop("PRIVATE_COPY_REQUIRED");
    try {
        verifyDependencies(QDir(root.filePath(benchDirectory)), dependencies);
    } catch (const std::exception &) {
        return result.stop("BENCH_SOURCE_DEPENDENCY_MISMATCH");
    }
    result.verified("BENCH_SOURCE_BYTES_VERIFIED");
    try {
        verifyDependencies(sandbox, dependencies, true);
    } catch (const std::exception &) {
        return result.stop("XLINK_DEPENDENCY_MISMATCH");
    }
    result.verified("PRIVATE_XLINK_COPY_VERIFIED");
    return result.allow("SEALED_SYNTHETIC_BENCH", "BENCH_TEST_ONLY");
}

QJsonArray cartographerBlockers(const QJsonObject &request, const QJsonObject &authority)
{
    const auto target = request.value("occurrence").toString();
    const auto operation = request.value("operation").toString();
    QJsonArray blockers{"V3_A_NATIVE_MUTATION_NOT_AUTHORIZED"};
    for (const auto &entry : authority.value("constraints").toArray()) {
        const auto constraint = entry.toObject();
        if (constraint.value("policy") == "UNKNOWN" && constraint.value("subjects").toArray().contains(target))
            blockers.append(constraint.value("id"));
    }
    if (operation == "CREATE_SUPPORT")
        blockers.append("VERIFIED_SUPPORT_ANCHOR_REQUIRED");
    if (operation == "CHANGE_CONNECTOR_VARIANT" || operation == "CHANGE_INTERFACE_TOPOLOGY") {
        blockers.append("CONNECTOR_PROVENANCE_REQUIRED");
        blockers.append("PINOUT_AND_ISOLATION_REQUIRED");
    }
    if (operation == "REROUTE_HARNESS") {
        blockers.append("BEND_RADIUS_REQUIRED");
        blockers.append("DYNAMIC_SERVICE_CONSTRAINTS_REQUIRED");
    }
    return blockers;
}

QJsonObject evaluateCartographer(const QDir &root, const QDir &sandbox, const QJsonObject &request, Decision &result)
{
    if (request.value("freeze_sha256") != freezeSha)
        return result.stop("FREEZE_SHA_MISMATCH");
    QJsonObject gate;
    QJsonObject authority;
    const QString authorityPath = "docs/electromechanical_v3/cartographe.json";
    try {
        sealedObject(root, v3aDirectory + "freeze.json", freezeSha);
        gate = sealedObject(root, v3aDirectory + "acceptance.json", acceptanceSha);
        authority = sealedObject(root, authorityPath, cartographeAuthoritySha);
    } catch (const std::exception &) {
        return result.stop("TRUSTED_V3_A_EVIDENCE_MISMATCH");
    }
    result.bind("V3_A_FREEZE", ref(v3aDirectory + "freeze.json", freezeSha));
    result.bind("V3_A_GATE", ref(v3aDirectory + "acceptance.json", acceptanceSha, "/next_gate"));
    result.bind("V3_A_AUTHORITIES", ref(authorityPath, cartographeAuthoritySha));
    QJsonArray issues;
    for (const auto &entry : gate.value("open").toArray())
        issues.append(entry.toObject().value("id"));
    result.issues(issues);
    result.verified("V3_A_EVIDENCE_SEALED");
    if (request.value("model_id") != cartographeId || request.value("model_version") != cartographeVersion)
        return result.stop("MODEL_ID_OR_VERSION_MISMATCH");
    if (request.value("geometry_sha256") != graphSha)
        return result.stop("GEOMETRY_SIGNATURE_MISMATCH");
    if (request.value("domain") != copyDomain || request.value("operation") != analysis)
        return result.stop("CARTOGRAPHER_AUTHORITIES_UNRESOLVED", cartographerBlockers(request, authority));

    const QJsonArray checks{"V3_GRAPH_SEAL", "V3_IMPACT_ORACLE"};
    result.controls(checks);
    if (request.value("context") != "V3_A_VIRTUAL_IMPACT" || request.value("output") != "IMPACT_REPORT" ||
        request.value("rollback") != "NO_MUTATION" || request.value("validations") != checks ||
        request.value("constraints") != QJsonObject{} ||
        request.value("authorities") != QJsonObject{{"V3_A_IMPACT_ORACLE", "/cases"}} ||
        !request.value("assumptions").toArray().isEmpty())
        return result.stop("VIRTUAL_IMPACT_SCOPE_MISMATCH");
    QJsonObject oracle;
    QJsonObject native;
    const QString graphPath = ".runtime/v3-a/sealed/cartographe-graph.json";
    try {
        sealedObject(root, graphPath, graphSha);
        oracle = sealedObject(root, v3aDirectory + "impact_oracle.json", oracleSha);
        native = sealedObject(root, v3aDirectory + "native_receipt.json", nativeReceiptSha);
    } catch (const std::exception &) {
        return result.stop("TRUSTED_VIRTUAL_EVIDENCE_MISMATCH");
    }
    const auto dependencies = native.value("inputs_sha256").toObject();
    if (request.value("xlink_dependencies") != dependencies || dependencies.isEmpty())
        return result.stop("XLINK_CLOSURE_MISMATCH");
    if (!privateSandbox(root, sandbox))
        return result.stop("PRIVATE_COPY_REQUIRED");
    try {
        verifyDependencies(sandbox, dependencies);
    } catch (const std::exception &) {
        return result.stop("XLINK_DEPENDENCY_MISMATCH");
    }
    for (const auto &entry : oracle.value("cases").toArray()) {
        const auto item = entry.toObject();
        if (request.value("occurrence") == item.value("target") &&
            request.value("effect") == QJsonObject{{"hypothetical_operation", item.value("operation")}}) {
            result.bind("V3_A_IMPACT_ORACLE", ref(v3aDirectory + "impact_oracle.json", oracleSha, "/cases"));
            result.bind("V3_A_NATIVE_RECEIPT", ref(v3aDirectory + "native_receipt.json", nativeReceiptSha));
            result.bind("V3_A_GRAPH", ref(graphPath, graphSha));
            result.verified("PRIVATE_XLINK_COPY_VERIFIED");
            result.verified("VIRTUAL_ORACLE_CASE_BOUND");
            return result.allow("FROZEN_VIRTUAL_IMPACT", "READ_ONLY_IMPACT");
        }
    }
    return result.stop("VIRTUAL_CASE_UNSUPPORTED", {}, "UNSUPPORTED");
}

} // namespace

QJsonObject evaluateAdmissionScope(const QDir &root, const QDir &sandbox, const QJsonObject &request)
{
    Decision result(request);
    if (request.value("schema") != version)
        return result.stop("CONTRACT_VERSION_UNSUPPORTED", {}, "UNSUPPORTED");
    if (!validShape(request))
        return result.stop("INVALID_REQUEST");
    const auto domain = request.value("domain").toString();
    const auto operation = request.value("operation").toString();
    if (!domains.contains(domain) || !operations.contains(operation))
        return result.stop("DOMAIN_OR_OPERATION_UNSUPPORTED", {}, "UNSUPPORTED");
    if (request.value("source_mode") != "IMMUTABLE")
        return result.stop("SOURCE_WRITE_FORBIDDEN");
    if (!validDependencies(request.value("xlink_dependencies").toObject()))
        return result.stop("INVALID_XLINK_PATH_OR_HASH");
    result.verified("REQUEST_SHAPE");
    result.verified("IMMUTABLE_SOURCE_MODE");
    if (domain == physicalDomain || operation == "RECEIVE_PHYSICAL")
        return result.stop("PHYSICAL_RECEPTION_NOT_RUN", {"GO4_HARDWARE_EVIDENCE_REQUIRED"});
    if (domain == benchDomain)
        return evaluateBench(root, sandbox, request, result);
    return evaluateCartographer(root, sandbox, request, result);
}

} // namespace convergence
