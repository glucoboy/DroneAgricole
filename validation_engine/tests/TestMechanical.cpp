#include "Mechanical.hpp"

#include <QJsonArray>
#include <QJsonObject>
#include <QTextStream>

namespace {

using electromechanical_validation::assessMechanical;

void expect(const QString &name, const QString &expected, const QJsonObject &check,
            const QJsonObject &observation, int &failures)
{
    const auto result = assessMechanical(check, observation);
    if (result.status != expected) {
        QTextStream(stderr) << name << ": " << result.status << " (attendu " << expected
                            << "), " << result.reason << '\n';
        ++failures;
    }
}

QJsonObject rule(const QString &method, const QJsonArray &subjects, const QJsonObject &parameters = {},
                 double tolerance = 0.000001)
{
    return {{"method", method}, {"subjects", subjects}, {"parameters", parameters}, {"tolerance", tolerance}};
}

QJsonObject pair(const QString &a, const QString &b, double distance, double intersection)
{
    return {{"a", a}, {"b", b}, {"clearance_mm", distance}, {"intersection_mm3", intersection},
            {"status", "PASS"}};
}

QJsonObject radius(double measured, bool certified)
{
    const auto method = certified ? "analytic_lines_circles" : "sampled_upper_bound_on_true_minimum_radius";
    return {{"route_metrics", QJsonObject{{"F16", QJsonObject{{"min_radius_mm", measured},
                        {"radius_certified", certified}, {"radius_evidence", method}}}}}};
}

void nativeAndRouteTests(int &failures)
{
    const QJsonObject state{{"inventory_complete", true}, {"reopened", true}, {"recompute_ok", true},
                           {"invalid_objects", QJsonArray{}}, {"broken_links", QJsonArray{}},
                           {"partial_documents", QJsonArray{}}};
    const auto integrity = rule("native-integrity", {"assembly"});
    expect("fermeture complète", "PASS", integrity, state, failures);
    auto partial = state;
    partial.insert("partial_documents", QJsonArray{"dependent.FCStd"});
    expect("fichier partiellement chargé", "FAIL", integrity, partial, failures);
    expect("état de la fermeture manquant", "INCONCLUSIVE", integrity, {}, failures);

    const auto bend = rule("bend-radius", {"F16"}, {{"minimum_mm", 22}});
    expect("arc certifié", "PASS", bend, radius(22.0, true), failures);
    expect("spline F16 avec défaut local", "FAIL", bend, radius(0.005, false), failures);
    expect("spline favorable sans borne", "INCONCLUSIVE", bend, radius(40.0, false), failures);
    const auto solid = rule("solid", {"F16"});
    const QJsonObject staleGaine{{"solid_valid", false}, {"status", "PASS"}};
    expect("gaine invalide", "FAIL", solid, {{"route_metrics", QJsonObject{{"F16", staleGaine}}}}, failures);
}

void pairTests(int &failures)
{
    const QJsonObject criteria{{"clearance_mm", 0}, {"volume_tolerance_mm3", 0.000001}};
    const auto contact = rule("pair", {"F16", "Chassis"}, criteria);
    const auto touch = pair("F16", "Chassis", 0, 0);
    const QJsonObject observation{{"collisions", QJsonArray{touch}}};
    expect("contact F16/châssis non autorisé", "FAIL", contact, observation, failures);
    auto authorized = criteria;
    authorized.insert("contacts", QJsonArray{QJsonObject{{"a", "F16"}, {"b", "Chassis"},
                      {"relation", "functional_contact"}, {"justification", "appui sur le banc"}}});
    expect("contact fonctionnel local", "PASS", rule("pair", {"F16", "Chassis"}, authorized), observation, failures);
    expect("intersection malgré le contact autorisé", "FAIL", rule("pair", {"F16", "Chassis"}, authorized),
           {{"collisions", QJsonArray{pair("F16", "Chassis", 0, 2)}}}, failures);

    auto exhaustive = criteria;
    exhaustive.insert("inventory_ids", QJsonArray{"L1", "Deck", "LateObstacle"});
    const auto allPairs = rule("pair-coverage", {"assembly"}, exhaustive);
    const auto filtered = QJsonObject{{"a", "Deck"}, {"b", "LateObstacle"}, {"clearance_lower_bound_mm", 2}};
    QJsonObject coverage{{"collisions", QJsonArray{pair("L1", "Deck", 1, 0), pair("LateObstacle", "L1", 1, 0)}},
                         {"collision_filtered_evidence", QJsonArray{filtered}}};
    expect("périmètre exhaustif et borne AABB", "PASS", allPairs, coverage, failures);
    coverage.insert("collisions", QJsonArray{pair("L1", "Deck", 1, 0)});
    expect("paire tardive manquante", "INCONCLUSIVE", allPairs, coverage, failures);
    coverage.insert("collisions", QJsonArray{pair("L1", "Deck", 1, 0), pair("LateObstacle", "L1", 0, 1)});
    expect("conflit hors sélection initiale", "FAIL", allPairs, coverage, failures);
    coverage.insert("collisions", QJsonArray{pair("L1", "Deck", 1, 0), pair("LateObstacle", "L1", 1, 0),
                                              pair("L1", "LateObstacle", 1, 0)});
    expect("doublon de paire", "INCONCLUSIVE", allPairs, coverage, failures);
}

void mountingTests(int &failures)
{
    const auto extraction = rule("extraction", {"CAN1"}, {{"clearance_mm", 0.2},
                                {"volume_tolerance_mm3", 0.000001}, {"obstacle_ids", QJsonArray{"F35"}},
                                {"ignored_ids", QJsonArray{}}});
    const auto volume = [](double distance, double intersection) {
        return QJsonObject{{"extraction_evidence", QJsonObject{{"CAN1", QJsonObject{
            {"measurements", QJsonArray{pair("approach_volume", "F35", distance, intersection)}},
            {"ignored_ids", QJsonArray{}}, {"unavailable_ids", QJsonArray{}}}}}}};
    };
    expect("course CAN1 libre", "PASS", extraction, volume(1, 0), failures);
    expect("course CAN1 obstruée", "FAIL", extraction, volume(0, 0.05), failures);
    const auto anchor = rule("anchor", {"Clip", "ClipSolid", "Deck"},
                             {{"anchor_id", "Deck"}, {"support_object_id", "ClipSolid"},
                              {"volume_tolerance_mm3", 0.000001}});
    const QJsonObject floating{{"anchor_valid", QJsonObject{{"Clip", QJsonObject{{"anchor", "Deck"},
                                {"attachment_measurement", pair("ClipSolid", "Deck", 0.5, 0)}}}}}};
    expect("retenue flottante", "FAIL", anchor, floating, failures);
}

void mobilityTests(int &failures)
{
    const auto envelope = rule("motion-envelope", {"F16"}, {{"minimum_clearance_mm", 1.0},
                               {"bound_method", "interval_AABB"},
                               {"interval_ids", QJsonArray{"nominal-extreme"}}});
    const auto proof = [](const QJsonObject &measurement) {
        return QJsonObject{{"motion_envelopes", QJsonObject{{"F16", measurement}}}};
    };
    const QJsonObject sampled{{"extreme", QJsonObject{{"clearance_ok", true}}}};
    expect("poses discrètes seules", "INCONCLUSIVE", envelope,
           {{"motion", QJsonObject{{"F16", sampled}}}}, failures);
    expect("borne sur le domaine continu", "PASS", envelope,
           proof({{"clearance_lower_bound_mm", 1.5}, {"bound_method", "interval_AABB"},
                  {"covered_intervals", QJsonArray{"nominal-extreme"}}}), failures);
    expect("témoin de pincement", "FAIL", envelope,
           proof({{"witness_in_domain", true}, {"clearance_witness_mm", 0.25}}), failures);
}

void architectureAndReviewTests(int &failures)
{
    const auto quality = rule("architecture-metric", {"L1"}, {{"metric", "upper"}, {"unit", "mm"}, {"maximum", 5}});
    const auto measure = [](double length, double lower, double upper) {
        return QJsonObject{{"architecture_metrics", QJsonObject{
            {"length", QJsonObject{{"unit", "mm"}, {"value", length}}},
            {"upper", QJsonObject{{"unit", "mm"}, {"value", (lower + upper) / 2.0},
                                  {"lower_bound", lower}, {"upper_bound", upper}}}}}};
    };
    expect("dessus dégagé", "PASS", quality, measure(100, 0, 1), failures);
    expect("câble plus court et congestion supérieure", "FAIL", quality, measure(75, 7, 8), failures);
    expect("incertitude recoupant le seuil", "INCONCLUSIVE", quality, measure(75, 4, 6), failures);
    const QJsonObject boundedOnly{{"unit", "mm"}, {"value", QJsonValue::Null},
                                 {"lower_bound", 7}, {"upper_bound", 8}};
    expect("congestion bornée sans estimation ponctuelle", "FAIL", quality,
           {{"architecture_metrics", QJsonObject{{"upper", boundedOnly}}}}, failures);

    const auto pairCheck = rule("pair", {"L1", "Obstacle"}, {{"clearance_mm", 1}, {"volume_tolerance_mm3", 0.000001}});
    const auto review = rule("critical-review", {"L1", "Obstacle"},
                             {{"frame_id", "bench-xyz"}, {"required_views", QJsonArray{"top"}},
                              {"hypothesis", "contact visible possible"}, {"inspection", pairCheck}});
    QJsonObject view{{"view_frame_id", "bench-xyz"}, {"views", QJsonObject{{"top",
                     QJsonObject{{"artifact_path", "top.svg"}, {"sha256", QString(64, 'a')}}}}}};
    expect("vue seule, hypothèse ouverte", "INCONCLUSIVE", review, view, failures);
    view.insert("collisions", QJsonArray{pair("L1", "Obstacle", 2, 0)});
    expect("inspection réfute l’anomalie", "PASS", review, view, failures);
    view.insert("collisions", QJsonArray{pair("L1", "Obstacle", 0, 2)});
    expect("inspection confirme l’anomalie", "FAIL", review, view, failures);
    expect("vue absente", "NOT_RUN", review, {}, failures);
}

} // namespace

int main()
{
    int failures = 0;
    nativeAndRouteTests(failures);
    pairTests(failures);
    mountingTests(failures);
    mobilityTests(failures);
    architectureAndReviewTests(failures);
    return failures == 0 ? 0 : 1;
}
