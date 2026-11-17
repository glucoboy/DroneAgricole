#include "Selection.hpp"

#include <QCryptographicHash>
#include <QJsonDocument>
#include <QMap>
#include <QSet>
#include <QStringList>
#include <algorithm>
#include <array>
#include <cmath>
#include <stdexcept>

namespace convergence {
namespace {

QString digest(const QJsonObject &object)
{
    return QString::fromLatin1(QCryptographicHash::hash(
        QJsonDocument(object).toJson(QJsonDocument::Compact), QCryptographicHash::Sha256).toHex());
}

bool isNumber(const QJsonValue &value)
{
    return value.isDouble() && std::isfinite(value.toDouble());
}

bool isDimension(const QString &key)
{
    return key.endsWith("_mm") || key.endsWith("_mm2") || key.endsWith("_mm3") || key.endsWith("_deg");
}

QJsonValue snapped(const QJsonValue &value, double tolerance, bool dimension = false)
{
    if (value.isObject()) {
        QJsonObject normalized;
        const auto object = value.toObject();
        for (auto it = object.begin(); it != object.end(); ++it) {
            normalized.insert(it.key(), snapped(it.value(), tolerance, dimension || isDimension(it.key())));
        }
        return normalized;
    }
    if (value.isArray()) {
        QJsonArray normalized;
        for (const auto &item : value.toArray()) {
            normalized.append(snapped(item, tolerance, dimension));
        }
        return normalized;
    }
    if (dimension && tolerance > 0 && isNumber(value)) {
        const auto gridPosition = value.toDouble() / tolerance;
        if (!std::isfinite(gridPosition)) {
            throw std::invalid_argument("Coordonnée hors grille de déduplication");
        }
        return std::round(gridPosition);
    }
    return value;
}

bool redundantPoint(const QJsonArray &a, const QJsonArray &b, const QJsonArray &c)
{
    if (a.size() != 3 || b.size() != 3 || c.size() != 3) {
        return false;
    }
    std::array<double, 3> first{}, second{};
    for (int axis = 0; axis < 3; ++axis) {
        if (!isNumber(a.at(axis)) || !isNumber(b.at(axis)) || !isNumber(c.at(axis))) {
            return false;
        }
        first[axis] = b.at(axis).toDouble() - a.at(axis).toDouble();
        second[axis] = c.at(axis).toDouble() - b.at(axis).toDouble();
    }
    const auto dot = first[0] * second[0] + first[1] * second[1] + first[2] * second[2];
    return dot > 0 && first[0] * second[1] == first[1] * second[0]
        && first[0] * second[2] == first[2] * second[0] && first[1] * second[2] == first[2] * second[1];
}

QJsonArray straightRouteEndpoints(const QJsonArray &points)
{
    for (qsizetype index = 1; index + 1 < points.size(); ++index) {
        if (!redundantPoint(points.at(index - 1).toArray(), points.at(index).toArray(), points.at(index + 1).toArray())) {
            return points;
        }
    }
    return points.size() > 2 ? QJsonArray{points.first(), points.last()} : points;
}

QJsonArray sortedStrings(const QSet<QString> &values)
{
    auto sorted = values.values();
    sorted.sort();
    return QJsonArray::fromStringList(sorted);
}

QJsonArray subjects(const QJsonObject &finding)
{
    QSet<QString> ids;
    for (const auto &key : {"subjects", "objects", "subject_ids", "object_ids", "object"}) {
        const auto value = finding.value(key);
        if (value.isString() && !value.toString().isEmpty()) {
            ids.insert(value.toString());
        }
        for (const auto &item : value.toArray()) {
            if (item.isString() && !item.toString().isEmpty()) {
                ids.insert(item.toString());
            }
        }
    }
    return sortedStrings(ids);
}

struct Conflict {
    QJsonObject identity;
    QSet<QString> candidates;
    QJsonArray observations;
};

QJsonArray failedPairs(const QJsonObject &finding)
{
    QJsonArray failures;
    for (const auto &entry : finding.value("value").toObject().value("evaluations").toArray()) {
        const auto pair = entry.toObject();
        if (pair.value("status") == "FAIL" && pair.value("pair").toArray().size() == 2) {
            failures.append(pair);
        }
    }
    return failures;
}

struct Objective {
    QString id;
    double direction;
    double tolerance;
};

QList<Objective> readObjectives(const QJsonArray &definitions)
{
    QList<Objective> objectives;
    QSet<QString> ids;
    for (const auto &entry : definitions) {
        const auto definition = entry.toObject();
        const auto id = definition.value("id").toString();
        const auto direction = definition.value("direction").toString();
        const auto tolerance = definition.value("tolerance");
        if (id.isEmpty() || ids.contains(id) || (direction != "MIN" && direction != "MAX") ||
            !isNumber(tolerance) || tolerance.toDouble() < 0) {
            throw std::invalid_argument("Objectif de comparaison invalide");
        }
        ids.insert(id);
        objectives.append({id, direction == "MIN" ? 1.0 : -1.0, tolerance.toDouble()});
    }
    return objectives;
}

double cost(const QJsonObject &metrics, const Objective &objective)
{
    return objective.direction * metrics.value(objective.id).toDouble();
}

bool dominates(const QJsonObject &a, const QJsonObject &b, const QList<Objective> &objectives)
{
    bool improves = false;
    for (const auto &objective : objectives) {
        const auto delta = cost(a, objective) - cost(b, objective);
        if (delta > 0) {
            return false;
        }
        improves |= delta < -objective.tolerance;
    }
    return improves;
}

} // namespace

QString candidateSignature(const QJsonObject &candidate, double geometryTolerance)
{
    if (!std::isfinite(geometryTolerance) || geometryTolerance < 0 || !candidate.value("assignments").isObject()) {
        throw std::invalid_argument("Affectations appliquées ou tolérance de déduplication invalides");
    }
    auto assignments = candidate.value("assignments").toObject();
    for (const auto &key : assignments.keys()) {
        if (!key.startsWith("route:")) {
            continue;
        }
        auto route = assignments.value(key).toObject();
        if (route.isEmpty()) {
            continue;
        }
        // A corridor label or rationale can differ for identical construction inputs.
        route.remove("corridor");
        if (route.value("bend_radius_mm").isUndefined() || route.value("bend_radius_mm").isNull()) {
            route.insert("bend_radius_mm", 0);
        }
        if (route.value("bend_radius_mm").toDouble() > 0 && route.value("points_mm").isArray()) {
            route.insert("points_mm", straightRouteEndpoints(route.value("points_mm").toArray()));
        }
        assignments.insert(key, route);
    }
    const auto topology = candidate.value("topology");
    return digest({{"assignments", snapped(assignments, geometryTolerance)},
                   {"topology", topology.isUndefined() ? QJsonValue(QJsonValue::Null) : topology}});
}

QJsonArray constraintConflictAnalyzer(const QJsonArray &reports)
{
    QMap<QString, Conflict> conflicts;
    for (const auto &entry : reports) {
        const auto report = entry.toObject();
        const auto id = report.value("id").toString();
        if (id.isEmpty()) {
            continue;
        }
        for (const auto &item : report.value("findings").toArray()) {
            const auto finding = item.toObject();
            const auto status = finding.value("status").toString(report.value("status").toString());
            if (status != "FAIL" && status != "fail" && status != "NON_CONFORME") {
                continue;
            }
            const auto code = finding.value("code").toString(finding.value("requirement_id").toString());
            if (code.isEmpty()) {
                continue;
            }
            const auto state = finding.value("state").toString(finding.value("state_id").toString(
                finding.value("l0").toObject().value("state_id").toString()));
            const auto criterion = finding.value("criterion");
            const QJsonObject check{{"code", code}, {"state", state},
                {"method", finding.value("method").toString()},
                {"criterion", criterion.isUndefined() ? QJsonValue(QJsonValue::Null) : criterion}};
            const auto record = [&](const QJsonArray &affected, const QJsonObject &observation) {
                auto identity = check;
                identity.insert("subjects", affected);
                const auto signature = digest(identity);
                auto &conflict = conflicts[signature];
                conflict.identity = identity;
                conflict.candidates.insert(id);
                conflict.observations.append(QJsonObject{{"candidate_id", id}, {"finding", observation}});
            };
            const auto pairs = failedPairs(finding);
            if (pairs.isEmpty()) {
                record(subjects(finding), finding);
            }
            for (const auto &entry : pairs) {
                const auto pair = entry.toObject();
                auto detail = finding;
                detail.insert("value", pair);
                record(subjects({{"subjects", pair.value("pair")}}), detail);
            }
        }
    }
    QJsonArray result;
    for (auto it = conflicts.begin(); it != conflicts.end(); ++it) {
        auto record = it->identity;
        record.insert("signature", it.key());
        record.insert("candidate_ids", sortedStrings(it->candidates));
        record.insert("occurrences", it->candidates.size());
        record.insert("observations", it->observations);
        result.append(record);
    }
    return result;
}

QJsonObject mergeDecisions(const QJsonArray &decisions, const QJsonObject &linkSubjects)
{
    QJsonArray conflicts;
    QMap<QString, QJsonObject> members;
    for (const auto &entry : decisions) {
        const auto member = entry.toObject();
        const auto id = member.value("id").toString();
        if (id.isEmpty() || members.contains(id)) {
            conflicts.append(QJsonObject{{"code", "INVALID_DECISION_ID"}, {"member", id}});
        } else {
            members.insert(id, member);
        }
    }
    if (members.isEmpty()) {
        conflicts.append(QJsonObject{{"code", "NO_DECISION"}});
    }
    QJsonObject assignments;
    QMap<QString, QString> assignedBy;
    QSet<QString> affectedLinks;
    for (auto it = members.begin(); it != members.end(); ++it) {
        const auto id = it.key();
        const auto member = it.value();
        if (member.value("status") != "PASS") {
            conflicts.append(QJsonObject{{"code", "INDIVIDUAL_NOT_ADMISSIBLE"}, {"member", id},
                                         {"status", member.value("status").toString()}});
        }
        if (!member.value("dependencies").isArray() || !member.value("exclusions").isArray()) {
            conflicts.append(QJsonObject{{"code", "INVALID_RELATIONS"}, {"member", id}});
        }
        for (const auto &dependency : member.value("dependencies").toArray()) {
            if (!members.contains(dependency.toString()) || dependency == id) {
                conflicts.append(QJsonObject{{"code", "MISSING_DEPENDENCY"}, {"member", id}, {"other", dependency}});
            }
        }
        for (const auto &other : member.value("exclusions").toArray()) {
            if (!other.isString() || other.toString().isEmpty() || members.contains(other.toString())) {
                conflicts.append(QJsonObject{{"code", "DECLARED_INCOMPATIBILITY"}, {"member", id}, {"other", other}});
            }
        }
        const auto changes = member.value("assignments").toObject();
        if (changes.isEmpty()) {
            conflicts.append(QJsonObject{{"code", "NO_ASSIGNMENT"}, {"member", id}});
        }
        for (auto change = changes.begin(); change != changes.end(); ++change) {
            const auto key = change.key();
            const auto links = linkSubjects.value(key).toArray();
            if (links.isEmpty() || std::any_of(links.begin(), links.end(), [](const auto &link) {
                    return !link.isString() || link.toString().isEmpty();
                })) {
                conflicts.append(QJsonObject{{"code", "ASSIGNMENT_COVERAGE_UNKNOWN"}, {"member", id}, {"assignment", key}});
            }
            for (const auto &link : links) {
                affectedLinks.insert(link.toString());
            }
            if (!assignments.contains(key)) {
                assignments.insert(key, change.value());
                assignedBy.insert(key, id);
            } else if (assignments.value(key) != change.value()) {
                conflicts.append(QJsonObject{{"code", "CONFLICTING_ASSIGNMENTS"}, {"assignment", key},
                    {"first_member", assignedBy.value(key)}, {"first", assignments.value(key)},
                    {"second_member", id}, {"second", change.value()}});
            }
        }
    }
    return {{"conflicts", conflicts}, {"assignments", conflicts.isEmpty() ? assignments : QJsonObject{}},
            {"affected_links", conflicts.isEmpty() ? sortedStrings(affectedLinks) : QJsonArray{}}};
}

QJsonObject compareCandidates(const QJsonArray &reports, const QJsonArray &definitions,
                              const QString &referenceSha256)
{
    const auto objectives = readObjectives(definitions);
    QMap<QString, QJsonObject> admitted;
    QMap<QString, int> idCounts;
    QSet<QString> references;
    for (const auto &entry : reports) {
        const auto report = entry.toObject();
        ++idCounts[report.value("id").toString()];
        const auto reference = report.value("reference_sha256").toString();
        if (report.value("status") == "PASS" && !reference.isEmpty()) {
            references.insert(reference);
        }
    }
    const auto reference = referenceSha256.isEmpty() && references.size() == 1 ? *references.begin() : referenceSha256;
    QJsonArray excluded;
    for (const auto &entry : reports) {
        const auto report = entry.toObject();
        const auto id = report.value("id").toString();
        const auto metrics = report.value("metrics").toObject();
        QJsonArray missing;
        for (const auto &objective : objectives) {
            if (!isNumber(metrics.value(objective.id))) {
                missing.append(objective.id);
            }
        }
        QString reason;
        if (id.isEmpty() || idCounts.value(id) != 1) {
            reason = "INVALID_CANDIDATE_ID";
        } else if (report.value("status") != "PASS") {
            reason = "HARD_CONSTRAINTS_NOT_PROVEN";
        } else if (reference.isEmpty() || report.value("reference_sha256") != reference) {
            reason = "DIFFERENT_REFERENCE";
        } else if (objectives.isEmpty() || !missing.isEmpty()) {
            reason = "MISSING_OBJECTIVES";
        }
        if (reason.isEmpty()) {
            admitted.insert(id, metrics);
        } else {
            excluded.append(QJsonObject{{"id", id}, {"reason", reason}, {"missing_objectives", missing}});
        }
    }
    QStringList frontier;
    QJsonObject dominatedBy, measuredMetrics;
    for (auto candidate = admitted.begin(); candidate != admitted.end(); ++candidate) {
        QJsonArray winners;
        for (auto other = admitted.begin(); other != admitted.end(); ++other) {
            if (dominates(other.value(), candidate.value(), objectives)) {
                winners.append(other.key());
            }
        }
        if (winners.isEmpty()) {
            frontier.append(candidate.key());
        } else {
            dominatedBy.insert(candidate.key(), winners);
        }
        measuredMetrics.insert(candidate.key(), candidate.value());
    }
    auto finalists = frontier;
    QJsonArray tieBreaks;
    for (const auto &objective : objectives) {
        if (finalists.size() <= 1) {
            break;
        }
        double best = cost(admitted.value(finalists.first()), objective);
        for (const auto &id : finalists) {
            best = std::min(best, cost(admitted.value(id), objective));
        }
        finalists.removeIf([&](const auto &id) {
            return cost(admitted.value(id), objective) - best > objective.tolerance;
        });
        tieBreaks.append(QJsonObject{{"objective", objective.id}, {"best", objective.direction * best},
                                     {"within_tolerance", QJsonArray::fromStringList(finalists)}});
    }
    return {{"reference_sha256", reference}, {"objectives", definitions}, {"excluded", excluded},
            {"pareto", QJsonArray::fromStringList(frontier)}, {"dominated_by", dominatedBy},
            {"measured_metrics", measuredMetrics}, {"tie_breaks", tieBreaks},
            {"selection_method", "HARD_CONSTRAINTS_PARETO_OBJECTIVE_ORDER_THEN_ID"},
            {"selected", finalists.isEmpty() ? QJsonValue(QJsonValue::Null) : QJsonValue(finalists.first())}};
}

} // namespace convergence
