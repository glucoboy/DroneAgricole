#pragma once

#include "Files.hpp"

#include <QFileInfo>
#include <QJsonArray>

namespace admission_test {

inline const QString benchPath = "docs/electromechanical_v3/bench_a1";
inline const QString v3aPath = "docs/verification/v3/a";

inline QJsonObject benchRequest(const QDir &root, const QString &operation)
{
    const auto path = root.filePath(benchPath + "/seal.json");
    const auto seal = convergence::load(path);
    const auto action = seal.value("operations").toObject().value(operation).toObject();
    QJsonObject request{{"schema", "v3.admission_scope/1"}, {"domain", "SYNTHETIC_BENCH"}, {"operation", operation},
        {"context", "B1_CLOSED_BENCH"}, {"output", "PRIVATE_CANDIDATE"}, {"source_mode", "IMMUTABLE"},
        {"rollback", "DISCARD_PRIVATE_COPY"}, {"objective", "Vérifier la porte d'admission de B.1"},
        {"assumptions", QJsonArray{}}, {"risks", QJsonArray{"GEOMETRY_FAILURE"}},
        {"freeze_sha256", convergence::fileDigest(path)}};
    for (const auto &key : {"model_id", "model_version", "geometry_sha256", "xlink_dependencies"})
        request.insert(key, seal.value(key));
    for (const auto &key : {"occurrence", "effect", "validations", "authorities", "constraints"})
        request.insert(key, action.value(key));
    return request;
}

inline QJsonObject cartographerRequest(const QDir &root)
{
    const auto receipt = convergence::load(root.filePath(v3aPath + "/native_receipt.json"));
    return {{"schema", "v3.admission_scope/1"}, {"domain", "CARTOGRAPHER_PRIVATE_CAD"},
        {"model_id", "prototype_cartographe_sans_dock"}, {"model_version", "742a5ac4f167bba0ef03b65053412bddbde0ecc9"},
        {"freeze_sha256", "f324a2a0e2feeb1d68df906927306c25ae625b325488677dafcba73256794981"},
        {"geometry_sha256", "9e73d314b74a14ca482fed4c146e58d9e051310a9924bc41af8f09cc9b5ef79f"},
        {"occurrence", "iso"}, {"operation", "ANALYZE_IMPACT"}, {"objective", "Évaluer les dépendances du cartographe"},
        {"context", "V3_A_VIRTUAL_IMPACT"}, {"output", "IMPACT_REPORT"}, {"source_mode", "IMMUTABLE"},
        {"rollback", "NO_MUTATION"}, {"validations", QJsonArray{"V3_GRAPH_SEAL", "V3_IMPACT_ORACLE"}},
        {"effect", QJsonObject{{"hypothetical_operation", "MOVE"}}}, {"constraints", QJsonObject{}},
        {"authorities", QJsonObject{{"V3_A_IMPACT_ORACLE", "/cases"}}},
        {"assumptions", QJsonArray{}}, {"risks", QJsonArray{"GRAPH_COVERAGE_LIMIT"}},
        {"xlink_dependencies", receipt.value("inputs_sha256")}};
}

inline QDir cartographerSandbox(const QDir &root)
{
    const auto freeze = convergence::load(root.filePath(v3aPath + "/freeze.json"));
    const QFileInfo entry(root.filePath(freeze.value("reopen_copy").toString()));
    return QDir(QDir::cleanPath(entry.absolutePath() + "/.."));
}

} // namespace admission_test
