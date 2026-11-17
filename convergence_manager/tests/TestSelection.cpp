#include "Selection.hpp"

#include <cstdio>
#include <stdexcept>

namespace {

using namespace convergence;

void check(bool condition, const char *message)
{
    if (!condition) {
        throw std::runtime_error(message);
    }
}

QJsonObject decision(const QString &id, const QString &plug,
                     const QJsonArray &dependencies = {}, const QJsonArray &exclusions = {})
{
    return {{"id", id}, {"status", "PASS"}, {"dependencies", dependencies}, {"exclusions", exclusions},
            {"assignments", QJsonObject{{"connector:shared", plug}}}};
}

QString mergeFault(const QJsonObject &result)
{
    const auto conflicts = result.value("conflicts").toArray();
    return conflicts.isEmpty() ? QString{} : conflicts.first().toObject().value("code").toString();
}

void verifyMerge()
{
    const QJsonObject owners{{"connector:shared", QJsonArray{"L2", "L1"}}};
    const auto first = decision("d1", "A");
    const auto incompatible = mergeDecisions({first, decision("d2", "B")}, owners);
    check(mergeFault(incompatible) == "CONFLICTING_ASSIGNMENTS", "Conflit entre connecteurs admis localement");
    check(incompatible.value("assignments").toObject().isEmpty(), "Une fusion refusée ne produit aucune affectation");
    check(incompatible.value("affected_links").toArray().isEmpty(), "Une fusion refusée ne revendique aucune couverture");

    const auto second = decision("d2", "A", {"d1"});
    const auto merged = mergeDecisions({second, first}, owners);
    check(mergeFault(merged).isEmpty(), "La dépendance présente satisfait la fusion");
    check(merged.value("affected_links").toArray() == QJsonArray{"L1", "L2"}, "Le connecteur commun affecte les deux liaisons");
    check(mergeFault(mergeDecisions({second}, owners)) == "MISSING_DEPENDENCY", "Dépendance absente détectée");
    check(mergeFault(mergeDecisions({decision("d2", "A", {}, {"d1"}), first}, owners)) == "DECLARED_INCOMPATIBILITY",
          "Exclusion déclarée détectée");
    check(mergeFault(mergeDecisions({first}, {})) == "ASSIGNMENT_COVERAGE_UNKNOWN", "Propriétaire du connecteur manquant");
}

QJsonObject variant(double endpoint, const QString &label, const QString &topology)
{
    const QJsonObject route{{"points_mm", QJsonArray{QJsonArray{0, 0, 0}, QJsonArray{endpoint, 0, 0}}},
                            {"corridor", label}};
    return {{"id", label}, {"assignments", QJsonObject{{"route:L1", route}}}, {"topology", topology}};
}

void verifyDeduplication()
{
    const auto nominal = candidateSignature(variant(1, "A", "direct"), 0.1);
    check(nominal == candidateSignature(variant(1.01, "B", "direct"), 0.1), "Équivalence dans la grille de mesure");
    check(nominal != candidateSignature(variant(1.01, "B", "branched"), 0.1), "Une branche change la topologie");

    auto straight = variant(1, "A", "direct");
    auto assignments = straight.value("assignments").toObject();
    auto route = assignments.value("route:L1").toObject();
    route.insert("bend_radius_mm", 5);
    assignments.insert("route:L1", route);
    straight.insert("assignments", assignments);
    const auto endpoints = candidateSignature(straight, 0.1);
    route.insert("points_mm", QJsonArray{QJsonArray{0, 0, 0}, QJsonArray{0.5, 0, 0}, QJsonArray{1, 0, 0}});
    assignments.insert("route:L1", route);
    straight.insert("assignments", assignments);
    check(endpoints == candidateSignature(straight, 0.1), "Un point colinéaire ne crée pas une nouvelle route");
}

QJsonObject failed(const QString &id, const QJsonArray &subjects, const QString &state)
{
    const QJsonObject finding{{"code", "collision"}, {"subjects", subjects}, {"state", state}, {"status", "FAIL"}};
    return {{"id", id}, {"status", "FAIL"}, {"findings", QJsonArray{finding}}};
}

void verifyRecurrence()
{
    const auto repeated = failed("r2", {"L1", "plate"}, "nominal");
    const auto diagnostics = constraintConflictAnalyzer({failed("r1", {"plate", "L1"}, "nominal"), repeated,
        failed("r3", {"plate", "L1"}, "other"), repeated, failed("r4", {"plate", "L2"}, "nominal")});
    check(diagnostics.size() == 3, "Le regroupement conserve le sujet et l’état du défaut");
    int recurrentCount = 0;
    for (const auto &entry : diagnostics) {
        const auto diagnosis = entry.toObject();
        if (diagnosis.value("occurrences") == 2) {
            ++recurrentCount;
            check(diagnosis.value("candidate_ids") == QJsonArray{"r1", "r2"}, "Chaque candidat ne compte qu’une fois");
        }
    }
    check(recurrentCount == 1, "Un seul défaut récurrent");
}

QJsonObject report(const QString &id, const QString &status, double length, int height, const QString &reference = "seal")
{
    return {{"id", id}, {"status", status}, {"reference_sha256", reference},
            {"metrics", QJsonObject{{"length", length}, {"height", height}}}};
}

void verifyComparison()
{
    const QJsonArray objectives{QJsonObject{{"id", "length"}, {"direction", "MIN"}, {"tolerance", 0.01}},
                                QJsonObject{{"id", "height"}, {"direction", "MIN"}, {"tolerance", 0}}};
    const auto comparison = compareCandidates({
        report("clear", "PASS", 16, 5), report("short", "PASS", 10, 12), report("dominated", "PASS", 20, 15),
        report("wrong-pinout", "FAIL", 1, 1), report("open", "CONDITIONAL", 1, 1),
        report("foreign", "PASS", 1, 1, "other"),
        QJsonObject{{"id", "missing"}, {"reference_sha256", "seal"}, {"status", "PASS"}}
    }, objectives, "seal");
    check(comparison.value("pareto") == QJsonArray{"clear", "short"}, "Le front conserve les compromis admissibles");
    check(comparison.value("selected") == "short", "L’ordre des objectifs arbitre le compromis");
    check(comparison.value("excluded").toArray().size() == 4, "Défauts, inconnues et autre référence exclus du classement");
    check(comparison.value("dominated_by").toObject().value("dominated") == QJsonArray{"clear", "short"},
          "Les variantes dominantes sont identifiées");
}

} // namespace

int main()
{
    try {
        verifyMerge();
        verifyDeduplication();
        verifyRecurrence();
        verifyComparison();
    } catch (const std::exception &error) {
        std::fprintf(stderr, "%s\n", error.what());
        return 1;
    }
    return 0;
}
