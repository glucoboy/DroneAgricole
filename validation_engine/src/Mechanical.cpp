#include "Mechanical.hpp"

#include <QJsonArray>
#include <QRegularExpression>
#include <QSet>

#include <algorithm>
#include <cmath>
#include <limits>
#include <optional>

namespace electromechanical_validation {
namespace {

using Number = std::optional<double>;

Assessment pass(QJsonValue value, QString unit, QString reason)
{
    return {QStringLiteral("PASS"), value, unit, reason};
}

Assessment fail(QJsonValue value, QString unit, QString reason)
{
    return {QStringLiteral("FAIL"), value, unit, reason};
}

Assessment unknown(QString reason, QJsonValue value = QJsonValue::Null, QString unit = QStringLiteral("1"))
{
    return {QStringLiteral("INCONCLUSIVE"), value, unit, reason};
}

Assessment notRun(QString reason)
{
    return {QStringLiteral("NOT_RUN"), QJsonValue::Null, QStringLiteral("1"), reason};
}

Number number(const QJsonValue &value)
{
    if (value.isDouble() && std::isfinite(value.toDouble())) {
        return value.toDouble();
    }
    return std::nullopt;
}

Number nonnegative(const QJsonValue &value)
{
    const auto result = number(value);
    return result && *result >= 0.0 ? result : std::nullopt;
}

QString subject(const QJsonObject &check, int index = 0)
{
    return check.value("subjects").toArray().at(index).toString();
}

QJsonObject parameters(const QJsonObject &check)
{
    return check.value("parameters").toObject();
}

double tolerance(const QJsonObject &check)
{
    return nonnegative(check.value("tolerance")).value_or(0.0);
}

QJsonArray pairIds(const QString &a, const QString &b)
{
    return a < b ? QJsonArray{a, b} : QJsonArray{b, a};
}

QString pairKey(const QString &a, const QString &b)
{
    return a < b ? a + QChar::Null + b : b + QChar::Null + a;
}

QString pairKey(const QJsonObject &pair)
{
    return pairKey(pair.value("a").toString(), pair.value("b").toString());
}

std::optional<QSet<QString>> stringSet(const QJsonValue &value)
{
    if (!value.isArray()) {
        return std::nullopt;
    }
    QSet<QString> result;
    for (const auto &entry : value.toArray()) {
        const auto id = entry.toString();
        if (id.isEmpty() || result.contains(id)) {
            return std::nullopt;
        }
        result.insert(id);
    }
    return result;
}

QJsonArray sorted(const QSet<QString> &ids)
{
    auto ordered = ids.values();
    std::sort(ordered.begin(), ordered.end());
    return QJsonArray::fromStringList(ordered);
}

QJsonValue nullable(const QJsonValue &value)
{
    return value.isUndefined() ? QJsonValue::Null : value;
}

Assessment nativeIntegrity(const QJsonObject &observation)
{
    QJsonObject actual;
    bool complete = true;
    bool adverse = false;
    for (const auto *key : {"inventory_complete", "reopened", "recompute_ok"}) {
        const auto value = observation.value(key);
        actual.insert(key, nullable(value));
        complete = complete && value.isBool();
        adverse = adverse || (value.isBool() && !value.toBool());
    }
    for (const auto *key : {"partial_documents", "invalid_objects", "broken_links"}) {
        const auto value = observation.value(key);
        actual.insert(key, nullable(value));
        complete = complete && value.isArray();
        adverse = adverse || !value.toArray().isEmpty();
    }
    if (adverse) {
        return fail(actual, "1", "Le chargement, le recalcul ou l’intégrité de la fermeture native échoue.");
    }
    if (!complete) {
        return unknown("La preuve de réouverture ou d’intégrité de la fermeture est incomplète.", actual);
    }
    return pass(actual, "1", "Fermeture inventoriée, rouverte et recalculée dans le processus de mesure.");
}

QJsonObject routeFor(const QJsonObject &check, const QJsonObject &observation)
{
    const auto route = subject(check);
    const auto state = check.value("state_id").toString();
    if (state.isEmpty()) {
        return observation.value("route_metrics").toObject().value(route).toObject();
    }
    return observation.value("motion").toObject().value(route).toObject().value(state).toObject();
}

Assessment solid(const QJsonObject &route)
{
    const auto observed = route.value("solid_valid");
    if (!observed.isBool()) {
        return unknown("La gaine n’a pas de preuve de validité après régénération.");
    }
    QJsonObject value{{"valid", observed}, {"measurement", nullable(route.value("solid_measurement"))}};
    return observed.toBool()
        ? pass(value, "1", "Le solide de gaine a été vérifié.")
        : fail(value, "1", "Le solide de gaine est invalide après la mesure indépendante.");
}

Assessment routeGeometry(const QJsonObject &check, const QJsonObject &route)
{
    QJsonObject value;
    bool complete = true;
    bool adverse = false;
    for (const auto *key : {"solid_valid", "continuity_ok", "tangency_ok", "endpoints_ok"}) {
        const auto observed = route.value(key);
        value.insert(key, nullable(observed));
        complete = complete && observed.isBool();
        adverse = adverse || (observed.isBool() && !observed.toBool());
    }
    const auto length = nonnegative(route.value("length_mm"));
    const auto diameter = nonnegative(route.value("diameter_mm"));
    const auto expectedDiameter = nonnegative(parameters(check).value("required_diameter_mm"));
    value.insert("length_mm", nullable(route.value("length_mm")));
    value.insert("diameter_mm", nullable(route.value("diameter_mm")));
    value.insert("expected_diameter_mm", nullable(parameters(check).value("required_diameter_mm")));
    adverse = adverse || (length && *length == 0.0);
    if (expectedDiameter && diameter) {
        adverse = adverse || std::abs(*diameter - *expectedDiameter) > tolerance(check);
    }
    if (adverse) {
        return fail(value, "1", "Défaut du solide, de l’axe, du raccordement ou du diamètre.");
    }
    if (!(complete && length && expectedDiameter && diameter && *expectedDiameter > 0.0)) {
        return unknown("Mesures d’axe, de solide ou de diamètre incomplètes.", value);
    }
    return pass(value, "1", "Solide, continuité, tangences, extrémités et diamètre conformes.");
}

Assessment bendRadius(const QJsonObject &check, const QJsonObject &route)
{
    const auto expected = nonnegative(parameters(check).value("minimum_mm"));
    const auto observed = nonnegative(route.value("min_radius_mm"));
    auto method = route.value("radius_evidence").toString();
    if (method.isEmpty()) {
        method = route.value("measurement").toObject().value("radius_evidence").toString();
    }
    const bool analytic = route.value("radius_certified") == QJsonValue(true)
        && method == QStringLiteral("analytic_lines_circles");
    const bool bounded = route.value("radius_certified") == QJsonValue(true)
        && method == QStringLiteral("certified_curvature_bound");
    const bool sampled = method == QStringLiteral("sampled_upper_bound_on_true_minimum_radius");
    const bool straight = analytic && route.value("min_radius_mm").isNull()
        && (route.value("measurement").toObject().value("straight_radius_infinite") == QJsonValue(true)
            || route.value("straight_radius_infinite") == QJsonValue(true));
    if (!expected || *expected == 0.0 || !(analytic || bounded || sampled)) {
        return unknown("Rayon requis ou méthode de mesure absents.", nullable(route.value("min_radius_mm")), "mm");
    }
    const auto lower = bounded ? nonnegative(route.value("radius_lower_bound_mm")) : observed;
    const auto witness = bounded ? nonnegative(route.value("radius_witness_mm")) : observed;
    const double numericTolerance = analytic ? tolerance(check) : 0.0;
    if (witness && *witness + numericTolerance < *expected) {
        return fail(*witness, "mm", "Témoin de courbure inférieur au rayon minimal gelé.");
    }
    if (straight) {
        return pass(QStringLiteral("infinite_straight"), "mm", "Courbure nulle sur tous les segments analytiques.");
    }
    if ((analytic || bounded) && lower && *lower + numericTolerance >= *expected) {
        return pass(*lower, "mm", "Le rayon analytique ou la borne inférieure respecte le seuil gelé.");
    }
    return unknown("Les échantillons de courbure ne bornent pas le minimum global.",
                   nullable(route.value("min_radius_mm")), "mm");
}

QJsonObject contactFor(const QJsonObject &criteria, const QString &key)
{
    for (const auto &entry : criteria.value("contacts").toArray()) {
        if (const auto contact = entry.toObject(); pairKey(contact) == key) {
            return contact;
        }
    }
    return {};
}

Assessment pairAssessment(const QJsonObject &pair, const QJsonObject &criteria, double distanceTolerance,
                          const QJsonObject &contact, bool filtered = false)
{
    const auto volumeTolerance = nonnegative(criteria.value("volume_tolerance_mm3"));
    const auto clearance = nonnegative(criteria.value("clearance_mm"));
    const auto relation = contact.value("relation").toString();
    const bool justified = !contact.value("justification").toString().trimmed().isEmpty();
    if (!volumeTolerance || !clearance || (!relation.isEmpty() && !justified)) {
        return unknown("Seuils ou justification du contact absents du référentiel.", pair);
    }
    if (filtered) {
        const auto lower = nonnegative(pair.value("clearance_lower_bound_mm"));
        if (lower && relation.isEmpty() && *lower > *clearance + distanceTolerance) {
            return pass(pair, "1", "Exclusion par borne inférieure conservatrice des boîtes englobantes.");
        }
        return unknown("La borne ne suffit pas pour exclure la paire du contrôle BRep.", pair);
    }
    const auto volume = nonnegative(pair.value("intersection_mm3"));
    const auto distance = nonnegative(pair.value("clearance_mm"));
    if (!volume) {
        return unknown("Intersection volumique non mesurée.", pair);
    }
    if (relation == QStringLiteral("cable_in_conduit_envelope")) {
        const auto outside = nonnegative(pair.value("outside_envelope_volume_mm3"));
        const bool representation = contact.value("outer_representation") == QJsonValue("occupancy_envelope")
            && pair.value("outer_representation") == QJsonValue("occupancy_envelope")
            && pair.value("a") == contact.value("a") && pair.value("b") == contact.value("b");
        if (!outside || !representation) {
            return unknown("La contenance et l’orientation de l’enveloppe ne sont pas établies.", pair);
        }
        return *outside <= *volumeTolerance
            ? pass(pair, "1", "Gaine contenue dans l’enveloppe d’occupation autorisée.")
            : fail(pair, "1", "La gaine dépasse de l’enveloppe autorisée.");
    }
    if (*volume > *volumeTolerance) {
        return fail(pair, "1", "Intersection volumique supérieure à la tolérance gelée.");
    }
    if (!distance) {
        return unknown("Distance entre solides non mesurée.", pair);
    }
    if (*distance <= distanceTolerance) {
        return relation == QStringLiteral("functional_contact")
            ? pass(pair, "1", "Contact fonctionnel autorisé pour cette paire, sans recouvrement significatif.")
            : fail(pair, "1", "Contact géométrique sans autorisation applicable.");
    }
    if (*distance + distanceTolerance < *clearance) {
        return fail(pair, "1", "Garde inférieure à la distance minimale gelée.");
    }
    return pass(pair, "1", "Distance et volume d’intersection conformes.");
}

Assessment singlePair(const QJsonObject &check, const QJsonObject &observation)
{
    const auto a = subject(check);
    const auto b = subject(check, 1);
    const auto criteria = parameters(check);
    const auto key = pairKey(a, b);
    const auto contact = contactFor(criteria, key);
    QJsonObject match;
    bool filtered = false;
    for (const auto *field : {"collisions", "collision_filtered_evidence"}) {
        for (const auto &entry : observation.value(field).toArray()) {
            if (const auto pair = entry.toObject(); pairKey(pair) == key) {
                if (!match.isEmpty()) {
                    return unknown("Plusieurs mesures concurrentes pour la même paire.");
                }
                match = pair;
                filtered = QString::fromLatin1(field) == QStringLiteral("collision_filtered_evidence");
            }
        }
    }
    if (match.isEmpty() || a.isEmpty() || b.isEmpty() || a == b) {
        return unknown("Mesure de la paire absente.");
    }
    return pairAssessment(match, criteria, tolerance(check), contact, filtered);
}

struct PairCoverage {
    QSet<QString> remaining;
    QJsonArray measured;
    QJsonArray unexpected;
    bool unavailable = false;
    bool adverse = false;
};

void comparePairs(PairCoverage &coverage, const QJsonArray &measurements, const QJsonObject &criteria,
                  double distanceTolerance, bool filtered = false)
{
    for (const auto &entry : measurements) {
        const auto pair = entry.toObject();
        const auto key = pairKey(pair);
        if (!coverage.remaining.remove(key)) {
            coverage.unexpected.append(pair);
            continue;
        }
        const auto contact = contactFor(criteria, key);
        const auto assessment = pairAssessment(pair, criteria, distanceTolerance, contact, filtered);
        coverage.adverse = coverage.adverse || assessment.status == QStringLiteral("FAIL");
        coverage.unavailable = coverage.unavailable || assessment.status == QStringLiteral("INCONCLUSIVE");
        coverage.measured.append(QJsonObject{{"pair", pairIds(pair.value("a").toString(), pair.value("b").toString())},
                                             {"geometry", pair}, {"filtered", filtered}, {"contact", contact},
                                             {"status", assessment.status}, {"reason", assessment.reason}});
    }
}

Assessment coverResult(const PairCoverage &coverage, QJsonObject evidence, QString success, QString failure)
{
    QJsonArray missing;
    for (const auto &key : sorted(coverage.remaining)) {
        const auto ids = key.toString().split(QChar::Null);
        missing.append(QJsonArray{ids.value(0), ids.value(1)});
    }
    evidence.insert("missing_pairs", missing);
    evidence.insert("unexpected_or_duplicate_pairs", coverage.unexpected);
    evidence.insert("evaluations", coverage.measured);
    if (coverage.adverse) {
        return fail(evidence, "1", failure);
    }
    if (!coverage.unexpected.isEmpty() || coverage.unavailable || !coverage.remaining.isEmpty()
        || coverage.measured.isEmpty()) {
        return unknown("Périmètre de paires ou mesures incomplets.", evidence);
    }
    return pass(evidence, "1", success);
}

Assessment allPairs(const QJsonObject &check, const QJsonObject &observation)
{
    const auto criteria = parameters(check);
    const auto inventory = stringSet(criteria.value("inventory_ids"));
    if (!inventory || inventory->size() < 2) {
        return unknown("Inventaire des solides à comparer indisponible.");
    }
    PairCoverage coverage;
    for (const auto &a : *inventory) {
        for (const auto &b : *inventory) {
            if (a < b) {
                coverage.remaining.insert(pairKey(a, b));
            }
        }
    }
    comparePairs(coverage, observation.value("collisions").toArray(), criteria, tolerance(check));
    comparePairs(coverage, observation.value("collision_filtered_evidence").toArray(), criteria,
                 tolerance(check), true);
    return coverResult(coverage, {{"inventory_ids", sorted(*inventory)}},
                       "Toutes les paires de l’inventaire sont contrôlées ou écartées par borne conservatrice.",
                       "Au moins une paire de l’inventaire présente une interférence ou une garde insuffisante.");
}

Assessment sweptVolume(const QJsonObject &check, const QJsonObject &volume)
{
    const auto criteria = parameters(check);
    const auto obstacles = stringSet(criteria.value("obstacle_ids"));
    const auto ignored = stringSet(criteria.value("ignored_ids"));
    const auto actualIgnored = stringSet(volume.value("ignored_ids"));
    const auto unavailable = stringSet(volume.value("unavailable_ids"));
    if (!obstacles || !ignored || !actualIgnored || !unavailable || obstacles->isEmpty()) {
        return unknown("Le volume d’accès ou le périmètre des obstacles n’est pas établi.");
    }
    PairCoverage coverage;
    for (const auto &id : *obstacles) {
        coverage.remaining.insert(pairKey(QStringLiteral("approach_volume"), id));
    }
    coverage.unavailable = !unavailable->isEmpty() || *ignored != *actualIgnored
        || !(*obstacles & *ignored).isEmpty();
    comparePairs(coverage, volume.value("measurements").toArray(), criteria, tolerance(check));
    return coverResult(coverage, {{"excluded_ids", sorted(*actualIgnored)}, {"unavailable_ids", sorted(*unavailable)},
                                  {"bounds_mm", volume.value("bounds_mm")}},
                       "Volume balayé du banc dégagé sur tout le périmètre gelé.",
                       "Obstacle dans le volume balayé du banc.");
}

Assessment anchor(const QJsonObject &check, const QJsonObject &observation)
{
    const auto criteria = parameters(check);
    const auto data = observation.value("anchor_valid").toObject().value(subject(check)).toObject();
    const auto expected = criteria.value("anchor_id").toString();
    const auto actual = data.value("anchor").toString();
    if (actual.isEmpty() || expected.isEmpty()) {
        return unknown("L’identité de la pièce porteuse n’est pas établie.");
    }
    const auto attachment = data.value("attachment_measurement").toObject();
    const auto distance = nonnegative(attachment.value("clearance_mm"));
    const auto overlap = nonnegative(attachment.value("intersection_mm3"));
    const auto maxOverlap = nonnegative(criteria.value("volume_tolerance_mm3"));
    if (actual != expected || (distance && *distance > tolerance(check))
        || (overlap && maxOverlap && *overlap > *maxOverlap)) {
        return fail(data, "1", "Retenue détachée, sur un mauvais porteur ou en recouvrement excessif.");
    }
    if (!distance || !overlap || !maxOverlap || attachment.value("b") != QJsonValue(expected)
        || attachment.value("a") != criteria.value("support_object_id")) {
        return unknown("Le contact géométrique avec le porteur n’est pas mesuré pour les deux objets.", data);
    }
    const auto access = sweptVolume(check, data.value("access_evidence").toObject());
    if (access.status == QStringLiteral("FAIL")) {
        return fail(data, "1", "Le porteur est en contact mais le volume de pose ou dépose est obstrué.");
    }
    if (access.status != QStringLiteral("PASS")) {
        return unknown("Le contact est mesuré, avec accès ou démontage encore ouvert.", data);
    }
    return pass(data, "1", "Contact avec la pièce porteuse et accès géométrique du banc contrôlés.");
}

Assessment matePose(const QJsonObject &check, const QJsonObject &observation)
{
    const auto expected = parameters(check).value("frames").toObject();
    const auto observed = observation.value("mate_poses").toObject().value(subject(check)).toObject();
    QJsonObject errors;
    bool incomplete = expected.isEmpty();
    bool adverse = false;
    for (auto it = expected.begin(); it != expected.end(); ++it) {
        const auto reference = it.value().toArray();
        const auto matrix = observed.value(it.key()).toArray();
        if (reference.size() != 16 || matrix.size() != 16) {
            incomplete = true;
            continue;
        }
        double error = 0.0;
        for (qsizetype i = 0; i < reference.size(); ++i) {
            const auto measured = number(matrix[i]);
            const auto nominal = number(reference[i]);
            if (!measured || !nominal) {
                incomplete = true;
                continue;
            }
            error = std::max(error, std::abs(*measured - *nominal));
        }
        errors.insert(it.key(), error);
        adverse = adverse || error > tolerance(check);
    }
    if (adverse) {
        return fail(errors, "1", "Un repère de pose, d’accouplement ou de sortie est hors tolérance.");
    }
    if (incomplete) {
        return unknown("Repères d’interface attendus ou mesurés incomplets.", errors);
    }
    return pass(errors, "1", "Repères d’interface comparés composante par composante.");
}

Assessment motionState(const QJsonObject &check, const QJsonObject &observation)
{
    const auto criteria = parameters(check);
    const auto route = routeFor(check, observation);
    if (route.isEmpty()) {
        return unknown("La pose gelée du câble n’a pas de mesure.");
    }
    const auto nominal = observation.value("route_metrics").toObject().value(subject(check)).toObject();
    const auto originalLength = nonnegative(nominal.value("length_mm"));
    const auto stateLength = nonnegative(route.value("length_mm"));
    const auto lengthTolerance = nonnegative(criteria.value("length_tolerance_mm"));
    const auto reserve = nonnegative(route.value("reserve_mm"));
    const auto requiredReserve = nonnegative(criteria.value("min_reserve_mm"));
    const auto geometry = routeGeometry(check, route);
    const auto radius = bendRadius(check, route);
    PairCoverage coverage;
    for (const auto &entry : criteria.value("pairs").toArray()) {
        const auto ids = entry.toArray();
        if (ids.size() == 2 && ids.at(0).isString() && ids.at(1).isString()
            && ids.at(0) != ids.at(1)) {
            coverage.remaining.insert(pairKey(ids.at(0).toString(), ids.at(1).toString()));
        } else {
            coverage.unavailable = true;
        }
    }
    const auto missingShapes = stringSet(route.value("missing_shapes"));
    coverage.unavailable = coverage.unavailable || !missingShapes || !missingShapes->isEmpty();
    comparePairs(coverage, route.value("clearance_pairs").toArray(), criteria, tolerance(check));
    const auto clearance = coverResult(coverage, {}, "Paires requises vérifiées à cette pose.",
                                       "Interférence à la pose mesurée.");
    QJsonObject details{{"state_id", check.value("state_id")}, {"length_mm", route.value("length_mm")},
                        {"nominal_length_mm", nominal.value("length_mm")}, {"reserve_mm", route.value("reserve_mm")},
                        {"geometry", geometry.value}, {"radius_mm", radius.value}, {"clearance", clearance.value}};
    const bool lengthKnown = originalLength && stateLength && lengthTolerance;
    const bool reserveKnown = reserve && requiredReserve
        && route.value("reserve_method") == QJsonValue("developed_length_minus_frozen_endpoint_chord");
    if ((lengthKnown && std::abs(*originalLength - *stateLength) > *lengthTolerance)
        || (reserveKnown && *reserve < *requiredReserve)) {
        return fail(details, "1", "Écart de longueur développée ou réserve géométrique insuffisante.");
    }
    for (const auto &assessment : {geometry, radius, clearance}) {
        if (assessment.status == QStringLiteral("FAIL")) {
            return fail(details, "1", assessment.reason);
        }
    }
    if (!lengthKnown || !reserveKnown || geometry.status != QStringLiteral("PASS")
        || radius.status != QStringLiteral("PASS") || clearance.status != QStringLiteral("PASS")) {
        return unknown("Les mesures ou les paires attendues pour cette pose sont incomplètes.", details);
    }
    return pass(details, "1", "Longueur, rayon, réserve et garde contrôlés à cette pose discrète.");
}

Assessment motionEnvelope(const QJsonObject &check, const QJsonObject &observation)
{
    const auto criteria = parameters(check);
    const auto proof = observation.value("motion_envelopes").toObject().value(subject(check)).toObject();
    const auto required = nonnegative(criteria.value("minimum_clearance_mm"));
    const auto lower = nonnegative(proof.value("clearance_lower_bound_mm"));
    const auto method = criteria.value("bound_method").toString();
    const auto covered = stringSet(proof.value("covered_intervals"));
    const auto expected = stringSet(criteria.value("interval_ids"));
    const auto witness = nonnegative(proof.value("clearance_witness_mm"));
    if (required && witness && proof.value("witness_in_domain") == QJsonValue(true)
        && *witness < *required) {
        return fail(*witness, "mm", "Témoin d’insuffisance de garde dans le domaine cinématique.");
    }
    if (!required || !lower || method.isEmpty() || proof.value("bound_method") != QJsonValue(method)
        || !covered || !expected || expected->isEmpty() || *covered != *expected) {
        return unknown("Les poses discrètes ne fournissent pas de borne sur le domaine cinématique continu.");
    }
    if (*lower < *required) {
        return unknown("La borne calculée ne suffit pas pour certifier la garde continue.", *lower, "mm");
    }
    return pass(*lower, "mm", "Borne de garde démontrée sur chacun des intervalles gelés.");
}

Assessment metric(const QJsonObject &check, const QJsonObject &observation)
{
    const auto criteria = parameters(check);
    const auto name = criteria.value("metric").toString();
    const auto data = observation.value("architecture_metrics").toObject().value(name).toObject();
    const auto unit = criteria.value("unit").toString();
    const auto maximum = number(criteria.value("maximum"));
    const auto minimum = number(criteria.value("minimum"));
    const auto value = number(data.value("value"));
    const auto lower = number(data.value("lower_bound"));
    const auto upper = number(data.value("upper_bound"));
    const bool hasBounds = data.contains("lower_bound") || data.contains("upper_bound");
    const auto measured = value ? QJsonValue(*value) : QJsonValue(QJsonObject{
        {"lower_bound", nullable(data.value("lower_bound"))}, {"upper_bound", nullable(data.value("upper_bound"))}});
    if (unit.isEmpty() || data.value("unit") != QJsonValue(unit) || (!value && !hasBounds)
        || (!maximum && !minimum) || (minimum && maximum && *minimum > *maximum)) {
        return unknown("Mesure, unité ou limite d’architecture indisponible.");
    }
    if (const auto scope = criteria.value("metric_scope"); !scope.isUndefined() && scope != data.value("scope")) {
        return unknown("Le périmètre de la mesure diffère du périmètre gelé.", measured, unit);
    }
    if (const auto count = criteria.value("axis_count"); !count.isUndefined() && count != observation.value("axis_count")) {
        return unknown("Le nombre d’axes observés diffère de celui de l’archive.", measured, unit);
    }
    if (hasBounds && (!lower || !upper || *lower > *upper || (value && (*lower > *value || *value > *upper)))) {
        return unknown("Intervalle d’incertitude incomplet ou incohérent.", measured, unit);
    }
    const auto replayMethod = criteria.value("replay_method").toString();
    const bool archiveReplay = !replayMethod.isEmpty() && data.value("method") == QJsonValue(replayMethod);
    if ((!replayMethod.isEmpty() && !archiveReplay)
        || (data.value("certified") == QJsonValue(false) && !hasBounds && !archiveReplay)) {
        return unknown("La mesure approximative ne fournit pas de borne ou de rejeu comparable.", measured, unit);
    }
    const double lo = lower ? *lower : *value;
    const double hi = upper ? *upper : *value;
    const auto limit = tolerance(check);
    if ((maximum && lo > *maximum + limit) || (minimum && hi < *minimum - limit)) {
        return fail(measured, unit, "La mesure et son intervalle dépassent la limite gelée de cette métrique.");
    }
    if ((maximum && hi > *maximum + limit) || (minimum && lo < *minimum - limit)) {
        return unknown("L’intervalle d’incertitude recoupe la limite gelée.", measured, unit);
    }
    return pass(measured, unit, archiveReplay ? "La mesure reproduit l’observation archivée dans la tolérance de rejeu."
                                             : "La métrique respecte sa limite dans le périmètre gelé.");
}

Assessment inspectHypothesis(const QJsonObject &inspection, const QJsonObject &observation)
{
    const auto method = inspection.value("method").toString();
    if (method == QStringLiteral("pair")) {
        return singlePair(inspection, observation);
    }
    if (method == QStringLiteral("extraction")) {
        const auto measured = observation.value("extraction_evidence").toObject().value(subject(inspection)).toObject();
        return sweptVolume(inspection, measured);
    }
    if (method == QStringLiteral("anchor")) {
        return anchor(inspection, observation);
    }
    if (method == QStringLiteral("mate-pose")) {
        return matePose(inspection, observation);
    }
    return unknown("L’hypothèse de la revue n’est reliée à aucune mesure géométrique supportée.");
}

Assessment criticalReview(const QJsonObject &check, const QJsonObject &observation)
{
    const auto criteria = parameters(check);
    const auto views = observation.value("views").toObject();
    const auto required = stringSet(criteria.value("required_views"));
    const auto frame = criteria.value("frame_id").toString();
    if (views.isEmpty()) {
        return notRun("Les vues de revue critique sont indisponibles.");
    }
    if (!required || required->isEmpty() || frame.isEmpty() || observation.value("view_frame_id") != QJsonValue(frame)) {
        return unknown("Les vues ne sont pas liées au repère de comparaison gelé.");
    }
    const QRegularExpression sha256(QStringLiteral("^[0-9a-f]{64}$"));
    QJsonObject selected;
    for (const auto &name : *required) {
        const auto view = views.value(name).toObject();
        if (view.value("artifact_path").toString().isEmpty()
            || !sha256.match(view.value("sha256").toString()).hasMatch()) {
            return unknown("Une vue de revue requise n’est pas référencée avec son empreinte.");
        }
        selected.insert(name, view);
    }
    if (criteria.value("hypothesis").toString().isEmpty()) {
        return unknown("La revue n’identifie pas d’hypothèse à inspecter.", selected);
    }
    const auto inspection = criteria.value("inspection").toObject();
    const auto assessment = inspectHypothesis(inspection, observation);
    QJsonObject evidence{{"views", selected}, {"frame_id", frame}, {"hypothesis", criteria.value("hypothesis")},
                         {"inspection", assessment.value}, {"inspection_reason", assessment.reason}};
    if (assessment.status == QStringLiteral("FAIL")) {
        return fail(evidence, "1", "Anomalie de revue confirmée par la mesure géométrique.");
    }
    if (assessment.status == QStringLiteral("PASS")) {
        return pass(evidence, "1", "Hypothèse de défaut écartée par la mesure géométrique ciblée.");
    }
    return unknown("Hypothèse de revue ouverte en attente de mesure concluante.", evidence);
}

} // namespace

Assessment assessMechanical(const QJsonObject &check, const QJsonObject &observation)
{
    const auto method = check.value("method").toString();
    if (method == QStringLiteral("native-integrity")) {
        return nativeIntegrity(observation);
    }
    if (method == QStringLiteral("route-geometry")) {
        return routeGeometry(check, routeFor(check, observation));
    }
    if (method == QStringLiteral("solid")) {
        return solid(routeFor(check, observation));
    }
    if (method == QStringLiteral("bend-radius")) {
        return bendRadius(check, routeFor(check, observation));
    }
    if (method == QStringLiteral("pair")) {
        return singlePair(check, observation);
    }
    if (method == QStringLiteral("pair-coverage")) {
        return allPairs(check, observation);
    }
    if (method == QStringLiteral("extraction")) {
        return sweptVolume(check, observation.value("extraction_evidence").toObject().value(subject(check)).toObject());
    }
    if (method == QStringLiteral("anchor")) {
        return anchor(check, observation);
    }
    if (method == QStringLiteral("mate-pose")) {
        return matePose(check, observation);
    }
    if (method == QStringLiteral("motion-state")) {
        return motionState(check, observation);
    }
    if (method == QStringLiteral("motion-envelope")) {
        return motionEnvelope(check, observation);
    }
    if (method == QStringLiteral("architecture-metric")) {
        return metric(check, observation);
    }
    if (method == QStringLiteral("critical-review")) {
        return criticalReview(check, observation);
    }
    return notRun("Méthode de validation mécanique indisponible.");
}

} // namespace electromechanical_validation
