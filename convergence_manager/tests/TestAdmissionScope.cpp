#include "AdmissionScope.hpp"
#include "AdmissionScopeFixture.hpp"

#include <QCoreApplication>
#include <QFile>
#include <QTemporaryDir>
#include <cstdio>
#include <filesystem>

namespace {

using namespace convergence;
using namespace admission_test;

QJsonObject change(QJsonObject object, const QString &key, const QJsonValue &value)
{
    object.insert(key, value);
    return object;
}

void copyFile(const QDir &source, const QDir &destination, const QString &path)
{
    require(destination.mkpath(QFileInfo(path).path()), "Création du dossier de copie impossible");
    require(QFile::copy(source.filePath(path), destination.filePath(path)), "Copie impossible : " + path);
}

void readOnly(const QString &path, bool enabled = true)
{
    auto permissions = QFile::ReadOwner | QFile::ReadGroup | QFile::ReadOther;
    if (!enabled)
        permissions |= QFile::WriteOwner;
    require(QFile::setPermissions(path, permissions), "Attribut lecture seule impossible : " + path);
}

class Suite {
public:
    QJsonObject check(const QString &id, const QDir &root, const QDir &copy, const QJsonObject &request,
                      const QString &expectedDecision, const QString &expectedReason, const QString &blocker = {})
    {
        const auto response = evaluateAdmissionScope(root, copy, request);
        require(response.value("decision") == expectedDecision && response.value("reason") == expectedReason,
                id + " : " + response.value("decision").toString() + '/' + response.value("reason").toString());
        const auto expectedScope = expectedDecision != "ALLOW" ? "NONE" :
            (request.value("operation") == "ANALYZE_IMPACT" ? "READ_ONLY_IMPACT" : "BENCH_TEST_ONLY");
        require(response.value("execution_scope") == expectedScope, id + " : portée inattendue");
        const QJsonArray action{request.value("operation")};
        const auto allowed = response.value("allowed_operations").toArray();
        const auto blocked = response.value("blocked_operations").toArray();
        require(expectedDecision == "ALLOW" ? (allowed == action && blocked.isEmpty()) :
            (allowed.isEmpty() && blocked == action), id + " : opérations incompatibles avec la décision");
        if (!blocker.isEmpty())
            require(response.value("unmet_preconditions").toArray().contains(blocker), id + " : précondition absente");
        entries.append(QJsonObject{{"id", id}, {"status", "PASS"}, {"expected", expectedDecision}, {"response", response}});
        return response;
    }

    void notRun(const QString &id, const QString &reason)
    {
        entries.append(QJsonObject{{"id", id}, {"status", "NOT_RUN"}, {"reason", reason}});
    }

    QJsonArray entries;
};

void testCartographer(Suite &suite, const QDir &root, const QDir &bench, const QJsonObject &benchMove,
                      const QDir &staging)
{
    const auto virtualRequest = cartographerRequest(root);
    const auto witness = cartographerSandbox(root);
    if (witness.exists() && QFileInfo::exists(root.filePath(".runtime/v3-a/sealed/cartographe-graph.json"))) {
        suite.check("VIRTUAL_MOVE_ISO", root, witness, virtualRequest, "ALLOW", "FROZEN_VIRTUAL_IMPACT");
        suite.check("VIRTUAL_RETENTION_P72", root, witness, change(change(virtualRequest, "occurrence", "p72"),
            "effect", QJsonObject{{"hypothetical_operation", "RETENTION"}}), "ALLOW", "FROZEN_VIRTUAL_IMPACT");
        suite.check("VIRTUAL_FRAME_TTL", root, witness, change(change(virtualRequest, "occurrence", "ttl-reference"),
            "effect", QJsonObject{{"hypothetical_operation", "FRAME"}}), "ALLOW", "FROZEN_VIRTUAL_IMPACT");
    } else {
        suite.notRun("VIRTUAL_ORACLES", "Copie et graphe V3-A historiques à reproduire");
    }

    const auto mutation = change(change(virtualRequest, "output", "PRIVATE_CANDIDATE"),
        "rollback", "DISCARD_PRIVATE_COPY");
    const QJsonArray issues{"UART-TOP-001", "UART-JBD-001", "UART-ISO-001", "UART-AXIS-001",
        "UART-MOUNT-001", "UART-ACCESS-001", "UART-HOST-001", "UART-GUIDES-001"};
    const auto reject = [&](const QString &id, const QString &operation, const QString &occurrence, const QString &blocker) {
        auto request = change(change(mutation, "operation", operation), "occurrence", occurrence);
        if (operation == "CHANGE_CONNECTOR_VARIANT" || operation == "CHANGE_INTERFACE_TOPOLOGY")
            request.insert("effect", QJsonObject{{"variant", "J2/J3"}});
        const auto response = suite.check(id, root, witness, request, "DENY", "CARTOGRAPHER_AUTHORITIES_UNRESOLVED", blocker);
        require(response.value("open_issues") == issues, "Les huit issues UART doivent rester visibles");
    };
    reject("CARTOGRAPHER_MOVE_ISO", "REPOSITION_DEVICE", "iso", "isolation-module-design-pose");
    reject("CARTOGRAPHER_MOVE_P72", "RELOCATE_SUPPORT", "p72", "guide-design-domain");
    reject("CARTOGRAPHER_MOVE_P73", "RELOCATE_SUPPORT", "p73", "guide-design-domain");
    reject("CARTOGRAPHER_SUPPORT_UNANCHORED", "CREATE_SUPPORT", "iso-native-plate", "VERIFIED_SUPPORT_ANCHOR_REQUIRED");
    reject("CARTOGRAPHER_CONNECT_J2_J3", "CHANGE_INTERFACE_TOPOLOGY", "receptacle:bms-uart", "CONNECTOR_PROVENANCE_REQUIRED");
    reject("CARTOGRAPHER_VARIANT_WITHOUT_PINOUT", "CHANGE_CONNECTOR_VARIANT", "plug:bms-uart", "PINOUT_AND_ISOLATION_REQUIRED");
    reject("CARTOGRAPHER_REROUTE_F16", "REROUTE_HARNESS", "axis:F16", "DYNAMIC_SERVICE_CONSTRAINTS_REQUIRED");
    suite.check("CARTOGRAPHER_DESIGN_INDEPENDENT", root, witness, change(virtualRequest, "domain",
        "CARTOGRAPHER_DESIGN_ADMISSION"), "DENY", "CARTOGRAPHER_AUTHORITIES_UNRESOLVED");
    suite.check("BENCH_AFTER_CARTOGRAPHER_DENY", root, bench, benchMove, "ALLOW", "SEALED_SYNTHETIC_BENCH");
    suite.check("PHYSICAL_NO_GO4_DATA", root, witness, change(change(mutation, "domain", "PHYSICAL_RECEPTION"),
        "operation", "RECEIVE_PHYSICAL"), "DENY", "PHYSICAL_RECEPTION_NOT_RUN", "GO4_HARDWARE_EVIDENCE_REQUIRED");

    const auto freezeName = v3aPath + "/freeze.json";
    require(staging.mkpath(v3aPath), "Dossier du gel de contre-épreuve inaccessible");
    write(staging.filePath(freezeName), read(root.filePath(freezeName)) + "\n");
    suite.check("V3_A_FREEZE_BYTES_ALTERED", staging, witness, virtualRequest, "DENY", "TRUSTED_V3_A_EVIDENCE_MISMATCH");
}

QJsonArray run(const QDir &root)
{
    require(root.mkpath(".runtime"), "Dossier de tests privé inaccessible");
    QTemporaryDir temporary(root.filePath(".runtime/a1-policy-XXXXXX"));
    require(temporary.isValid(), "Dossier de tests privé impossible");
    const QDir stage(temporary.path());
    const QDir source(root.filePath(benchPath));
    const QDir copyA(stage.filePath("model-copy-a")), copyB(stage.filePath("model-copy-b"));
    const auto move = benchRequest(root, "REPOSITION_DEVICE");
    const auto deps = move.value("xlink_dependencies").toObject();
    for (const auto &name : deps.keys()) {
        copyFile(source, copyA, name);
        copyFile(source, copyB, name);
        readOnly(copyA.filePath(name));
        readOnly(copyB.filePath(name));
    }
    Suite suite;
    for (const auto &op : {"REPOSITION_DEVICE", "REROUTE_HARNESS", "RELOCATE_SUPPORT", "CREATE_SUPPORT"}) {
        const auto request = benchRequest(root, op);
        const auto decision = suite.check("BENCH_" + QString(op), root, copyA, request, "ALLOW", "SEALED_SYNTHETIC_BENCH");
        require(decision.value("mandatory_checks") == request.value("validations") &&
            decision.value("resolved_authorities").toObject().size() == request.value("authorities").toObject().size() + 2,
            "Contrôles et preuves évalués incomplets");
    }
    const auto second = suite.check("SECOND_IDENTICAL_XLINK_COPY", root, copyB, move, "ALLOW", "SEALED_SYNTHETIC_BENCH");
    require(second == evaluateAdmissionScope(root, copyA, move), "La décision dépend de l’emplacement de copie");
    suite.check("MODEL_VERSION_CHANGED", root, copyB, change(move, "model_version", "2"), "DENY", "MODEL_ID_OR_VERSION_MISMATCH");
    suite.check("GEOMETRY_SIGNATURE_CHANGED", root, copyB, change(move, "geometry_sha256", QString(64, '0')),
        "DENY", "GEOMETRY_SIGNATURE_MISMATCH");

    const auto deny = [&](const QString &id, const QString &field, const QJsonValue &value, const QString &reason) {
        suite.check(id, root, copyA, change(move, field, value), "DENY", reason);
    };
    deny("OUTSIDE_XLINK_PATH", "xlink_dependencies", change(deps, "../outside.FCStd", QString(64, '0')),
        "INVALID_XLINK_PATH_OR_HASH");
    auto incompleteClosure = deps;
    incompleteClosure.remove(deps.keys().first());
    deny("INCOMPLETE_XLINK_CLOSURE", "xlink_dependencies", incompleteClosure, "XLINK_CLOSURE_MISMATCH");
    deny("WINDOWS_ALTERNATE_STREAM", "xlink_dependencies", change(deps, "model/a.FCStd:other", QString(64, '0')),
        "INVALID_XLINK_PATH_OR_HASH");
    deny("SOURCE_WRITE_REQUEST", "source_mode", "WRITE_SOURCE", "SOURCE_WRITE_FORBIDDEN");
    deny("FORGED_FREEZE_SHA256", "freeze_sha256", QString(64, '0'), "FREEZE_SHA_MISMATCH");
    deny("FOREIGN_MODEL_UNDER_BENCH_DOMAIN", "model_id", "prototype_cartographe_sans_dock", "MODEL_ID_OR_VERSION_MISMATCH");
    deny("PROTECTED_VALIDATION_REMOVED", "validations", QJsonArray{"REOPEN_XLINK"}, "VALIDATION_SET_MISMATCH");
    deny("ROLLBACK_REMOVED", "rollback", "NO_MUTATION", "BENCH_SCOPE_MISMATCH");
    deny("FAKE_VENDOR_AUTHORITY", "authorities", change(move.value("authorities").toObject(), "PINOUT", "/vendor/self-signed"),
        "AUTHORITY_SET_MISMATCH");
    auto constraints = move.value("constraints").toObject();
    auto frame = constraints.value("INDEPENDENT_FRAMES").toObject();
    frame.insert("position_tolerance_mm", 3.1);
    deny("RELAXED_TOLERANCE", "constraints", change(constraints, "INDEPENDENT_FRAMES", frame), "CONSTRAINT_SET_MISMATCH");
    constraints.remove("BMS_USB_STRUCTURE_ISOLATION");
    deny("ISOLATION_CONSTRAINT_REMOVED", "constraints", constraints, "CONSTRAINT_SET_MISMATCH");
    deny("FRAME_PLUS_3_MM", "effect", QJsonObject{{"placement_mm", QJsonArray{24, 20, 7}}}, "OCCURRENCE_OR_EFFECT_MISMATCH");
    deny("CONNECTIVITY_HIDDEN_IN_EFFECT", "effect", change(move.value("effect").toObject(), "bridge_nc", "USB"),
        "OCCURRENCE_OR_EFFECT_MISMATCH");
    deny("COMPOSITE_EFFECT", "effect", change(move.value("effect").toObject(), "subactions", QJsonArray{"CREATE_SUPPORT"}),
        "OCCURRENCE_OR_EFFECT_MISMATCH");
    deny("PREVIOUS_RECEIPT_AS_ALLOW_FLAG", "allowed", true, "INVALID_REQUEST");
    deny("MALFORMED_ASSUMPTION", "assumptions", QJsonArray{QJsonObject{{"changed", true}}}, "INVALID_REQUEST");
    suite.check("UNSUPPORTED_COMPOSITE", root, copyA, change(move, "operation", "COMPOSITE"),
        "UNSUPPORTED", "DOMAIN_OR_OPERATION_UNSUPPORTED");
    suite.check("UNSUPPORTED_TOPOLOGY_ON_BENCH", root, copyA, change(move, "operation", "CHANGE_INTERFACE_TOPOLOGY"),
        "UNSUPPORTED", "BENCH_OPERATION_UNSUPPORTED");
    suite.check("CANONICAL_SOURCE_AS_SANDBOX", root, source, move, "DENY", "PRIVATE_COPY_REQUIRED");

    const auto dependency = deps.keys().first();
    readOnly(copyB.filePath(dependency), false);
    suite.check("WRITABLE_INPUT_FILE", root, copyB, move, "DENY", "XLINK_DEPENDENCY_MISMATCH");
    write(copyB.filePath(dependency), read(copyB.filePath(dependency)) + "changed");
    readOnly(copyB.filePath(dependency));
    suite.check("NATIVE_GEOMETRY_BYTES_CHANGED", root, copyB, move, "DENY", "XLINK_DEPENDENCY_MISMATCH");
    const auto hardlink = copyB.filePath(dependency);
    readOnly(hardlink, false);
    require(QFile::remove(hardlink), "Suppression de la copie modifiée impossible");
    const QDir external(stage.filePath("external"));
    copyFile(source, external, dependency);
    std::error_code linkError;
    std::filesystem::create_hard_link(QFileInfo(external.filePath(dependency)).filesystemFilePath(),
        QFileInfo(hardlink).filesystemFilePath(), linkError);
    if (!linkError) {
        readOnly(hardlink);
        suite.check("HARD_LINK_TO_SOURCE", root, copyB, move, "DENY", "XLINK_DEPENDENCY_MISMATCH");
        readOnly(hardlink, false);
        require(QFile::remove(hardlink), "Dépose du lien de l’essai impossible");
    } else {
        suite.notRun("HARD_LINK_TO_SOURCE", QString::fromStdString(linkError.message()));
    }

    require(stage.mkpath(benchPath), "Dossier du sceau de contre-épreuve inaccessible");
    const auto fakeSeal = stage.filePath(benchPath + "/seal.json");
    const auto fakeDigest = write(fakeSeal, change(load(source.filePath("seal.json")), "model_version", "9"));
    suite.check("SEALED_BENCH_MANIFEST_TAMPERED", stage, copyA, move, "DENY", "TRUSTED_BENCH_EVIDENCE_MISMATCH");
    suite.check("TAMPERER_REHASHED_BENCH_MANIFEST", stage, copyA, change(move, "freeze_sha256", fakeDigest),
        "DENY", "FREEZE_SHA_MISMATCH");
    write(fakeSeal, read(source.filePath("seal.json")));
    for (const auto &name : {"authority.json", "geometry.json"})
        copyFile(source, QDir(stage.filePath(benchPath)), name);
    const QDir privateCopy(stage.filePath(".runtime/private"));
    for (const auto &name : deps.keys()) {
        copyFile(source, privateCopy, name);
        readOnly(privateCopy.filePath(name));
        copyFile(source, QDir(stage.filePath(benchPath)), name);
    }
    const auto authority = stage.filePath(benchPath + "/authority.json");
    write(authority, change(load(authority), "independent_frames", QJsonObject{{"origin_offset_mm", QJsonArray{3, 0, 0}}}));
    suite.check("FORGED_INDEPENDENT_FRAME_PLUS_3_MM", stage, privateCopy, move, "DENY", "TRUSTED_BENCH_EVIDENCE_MISMATCH");
    write(authority, read(source.filePath("authority.json")));
    const auto damagedSource = stage.filePath(benchPath + '/' + dependency);
    write(damagedSource, read(damagedSource) + "changed");
    suite.check("SEALED_BENCH_SOURCE_ALTERED", stage, privateCopy, move, "DENY", "BENCH_SOURCE_DEPENDENCY_MISMATCH");
    testCartographer(suite, root, copyA, move, stage);
    for (const auto &name : deps.keys()) {
        readOnly(copyA.filePath(name), false);
        readOnly(privateCopy.filePath(name), false);
        if (QFileInfo::exists(copyB.filePath(name)))
            readOnly(copyB.filePath(name), false);
    }
    return suite.entries;
}

} // namespace

int main(int argc, char **argv)
{
    const QCoreApplication app(argc, argv);
    try {
        require(app.arguments().size() == 3, "Racine de test et chemin de trace requis");
        const auto cases = run(QDir(QDir(app.arguments().at(1)).canonicalPath()));
        write(app.arguments().at(2), QJsonObject{{"schema", "v3.a1.adversarial_policy_trace/1"}, {"cases", cases}});
        return 0;
    } catch (const std::exception &error) {
        std::fprintf(stderr, "%s\n", error.what());
        return 1;
    }
}
