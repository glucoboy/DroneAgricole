#include "Exploration.hpp"

#include <QJsonArray>
#include <QMap>
#include <QRegularExpression>
#include <QSet>
#include <algorithm>
#include <cmath>
#include <limits>
#include <stdexcept>

namespace architecture_decision {
namespace {

const QString pass = "PASS", fail = "FAIL", unknown = "INCONCLUSIVE";

void require(bool condition, const QString &message)
{
    if (!condition) {
        throw std::runtime_error(message.toStdString());
    }
}

QString id(const QJsonValue &value)
{
    const auto text = value.toString();
    static const QRegularExpression pattern("^[a-z][a-z0-9_-]{0,63}$");
    require(pattern.match(text).hasMatch(), "Identifiant L3 invalide : " + text);
    return text;
}

double number(const QJsonValue &value)
{
    require(value.isDouble() && std::isfinite(value.toDouble()), "Valeur numérique finie attendue");
    return value.toDouble();
}

int budget(const QJsonValue &value)
{
    const auto n = number(value);
    require(n >= 1 && n <= 100 && std::floor(n) == n, "Budget L3 hors de [1, 100]");
    return static_cast<int>(n);
}

QString aggregate(const QString &a, const QString &b)
{
    if (a == fail || b == fail) {
        return fail;
    }
    return a == pass && b == pass ? pass : unknown;
}

QJsonObject apply(const QJsonObject &baseline, const QJsonObject &changes)
{
    auto result = baseline;
    for (auto it = changes.begin(); it != changes.end(); ++it) {
        require(result.contains(it.key()), "Paramètre L3 inconnu : " + it.key());
        const auto before = result.value(it.key());
        require(it.value().isNull() || before.isNull() || before.type() == it.value().type(),
                "Type de paramètre incompatible : " + it.key());
        result.insert(it.key(), it.value());
    }
    return result;
}

QJsonValue affine(const QJsonObject &expression, const QJsonObject &parameters)
{
    auto result = number(expression.value("constant"));
    const auto terms = expression.value("terms").toObject();
    for (auto it = terms.begin(); it != terms.end(); ++it) {
        const auto coefficient = number(it.value());
        const auto v = parameters.value(it.key());
        require(!v.isUndefined(), "Terme hors des paramètres : " + it.key());
        if (v.isNull()) {
            return QJsonValue::Null;
        }
        result += coefficient * number(v);
    }
    require(std::isfinite(result), "Résultat numérique non fini");
    return result;
}

QJsonArray linksAffected(const QJsonArray &links, const QJsonObject &changes, const QJsonObject &owners)
{
    QSet<QString> subjects;
    for (const auto &parameter : changes.keys()) {
        const auto owner = owners.value(parameter).toArray();
        require(!owner.isEmpty(), "Paramètre sans propriétaire : " + parameter);
        for (const auto &subject : owner) {
            subjects.insert(subject.toString());
        }
    }
    QJsonArray affected;
    for (const auto &entry : links) {
        const auto link = entry.toObject();
        const auto endpoints = link.value("subjects").toArray();
        if (subjects.contains(link.value("id").toString()) ||
            std::any_of(endpoints.begin(), endpoints.end(),
                        [&subjects](const auto &e) { return subjects.contains(e.toString()); })) {
            affected.append(link.value("id"));
        }
    }
    return affected;
}

bool reaches(const QJsonArray &edges, const QString &start, const QString &end, const QString &signal)
{
    require(!start.isEmpty() && !end.isEmpty() && !signal.isEmpty(), "Fonction sans extrémités ou signal");
    QSet<QString> visited{start};
    QStringList pending{start};
    while (!pending.isEmpty()) {
        const auto from = pending.takeLast();
        if (from == end) {
            return true;
        }
        for (const auto &item : edges) {
            const auto edge = item.toObject();
            const auto to = edge.value("to").toString();
            if (edge.value("signal") == signal && edge.value("from") == from && !to.isEmpty() &&
                !visited.contains(to)) {
                visited.insert(to);
                pending.append(to);
            }
        }
    }
    return false;
}

bool sameGraph(const QJsonArray &observed, const QJsonArray &expected)
{
    if (observed.size() != expected.size()) {
        return false;
    }
    auto unmatched = expected;
    for (const auto &edge : observed) {
        qsizetype position = 0;
        while (position < unmatched.size() && unmatched.at(position) != edge) {
            ++position;
        }
        if (position == unmatched.size()) {
            return false;
        }
        unmatched.removeAt(position);
    }
    return true;
}

QJsonObject evaluateCheck(const QJsonObject &rule, const QJsonObject &parameters,
                          const QJsonObject &interconnection)
{
    const auto check = rule.value("check").toObject();
    const auto requirement = rule.value("requirement").toObject();
    const auto kind = check.value("kind").toString();
    const auto criterion = requirement.value("criterion").toObject();
    const auto limit = criterion.value("value");
    const auto op = requirement.value("operator");
    QString status = unknown;
    QString reason = "Couverture ou donnée applicable insuffisante";
    QJsonValue measured = QJsonValue::Null;
    QJsonValue margin = QJsonValue::Null;
    auto unit = criterion.value("unit");
    const auto applicable = requirement.value("applicability");
    require(applicable == "APPLICABLE" || applicable == "NOT_APPLICABLE" || applicable == "UNKNOWN",
            "Applicabilité L0 invalide");
    if (applicable != "APPLICABLE") {
        status = applicable == "NOT_APPLICABLE" ? "NOT_APPLICABLE" : unknown;
        reason = applicable == "NOT_APPLICABLE" ? "Exigence hors du périmètre déclaré" :
                                                  "Applicabilité de l’exigence inconnue";
    } else if (kind == "AFFINE") {
        measured = affine(check, parameters);
        require(op == "GE" || op == "LE", "Opérateur numérique non pris en charge");
        if (!measured.isNull() && !limit.isNull()) {
            const auto m = (number(measured) - number(limit)) * (op == "GE" ? 1 : -1);
            require(std::isfinite(m), "Marge non finie");
            margin = m;
            status = m >= 0 ? pass : fail;
            reason = "Marge signée par rapport au critère gelé";
        }
    } else if (kind == "L2_FINDING") {
        require(op == "TRUE" && (limit == true || limit.isNull()), "Critère booléen L2 non pris en charge");
        const auto report = interconnection.value("report").toObject();
        const auto findings = report.value("findings").toArray();
        for (const auto &item : findings) {
            const auto finding = item.toObject();
            if (finding.value("code") == check.value("code") &&
                finding.value("subject_id") == check.value("subject_id")) {
                status = finding.value("status").toString();
                reason = finding.value("reason").toString();
                break;
            }
        }
        const auto service = interconnection.value("service_checks").toObject()
            .value(check.value("service").toString()).toObject();
        if (service.value("minimum_margin_mm").isDouble()) {
            margin = service.value("minimum_margin_mm");
            unit = "mm";
        }
    } else if (kind == "L2_ROUTE") {
        require(op == "GE", "Le dégagement L2 utilise une borne minimale");
        const auto route = interconnection.value("route_checks").toObject();
        if (route.value("signed_clearance_mm").isDouble() && !limit.isNull()) {
            measured = route.value("signed_clearance_mm");
            margin = number(measured) - number(limit);
            status = number(margin) >= 0 ? pass : fail;
        }
        reason = "Séparation signée entre la réservation du cordon et les boîtes du banc";
    } else if (kind == "L2_LENGTH_RESERVE") {
        require(op == "GE", "La réserve de longueur utilise une borne minimale");
        measured = interconnection.value("route_checks").toObject().value("length_margin_mm");
        if (measured.isDouble() && !limit.isNull()) {
            margin = number(measured) - number(limit);
            status = number(margin) >= 0 ? pass : fail;
        }
        reason = "Longueur disponible moins longueur développée de l’axe synthétique";
    } else if (kind == "L2_DOMAIN") {
        require(op == "TRUE" && (limit == true || limit.isNull()), "Critère booléen L2 non pris en charge");
        const auto report = interconnection.value("report").toObject();
        status = report.value(check.value("domain").toString()).toString(unknown);
        reason = "Verdict de domaine du validateur L2";
    } else if (kind == "FUNCTION_PATH") {
        require(op == "TRUE" && (limit == true || limit.isNull()), "Critère de conservation invalide");
        const auto edges = parameters.value(check.value("parameter").toString());
        require(edges.isArray(), "Graphe de fonctions manquant");
        const auto linked = reaches(edges.toArray(), check.value("from").toString(),
                                    check.value("to").toString(), check.value("signal").toString());
        measured = linked;
        status = linked ? pass : fail;
        reason = linked ? "Chemin du signal exigé vérifié" : "Fonction exigée interrompue";
    } else if (kind == "ELECTRICAL_CONTRACT") {
        require(op == "TRUE" && (limit == true || limit.isNull()), "Critère électrique invalide");
        const auto selected = parameters.value(check.value("parameter").toString()).toString();
        const auto contracts = check.value("contracts").toObject();
        const auto contract = contracts.value(selected).toObject();
        const auto edges = parameters.value(check.value("graph_parameter").toString()).toArray();
        if (selected == "DIRECT") {
            const auto reference = check.value("direct_connections").toArray();
            require(!reference.isEmpty(), "Contrat direct de référence absent");
            const auto matches = sameGraph(edges, reference);
            status = matches ? pass : fail;
            reason = matches ? "Interface électrique du banc conservée" :
                               "Le graphe direct diverge du contrat de référence";
        } else if (!contract.isEmpty()) {
            const auto required = check.value("signals").toArray();
            const auto connections = contract.value("connections").toArray();
            bool matches = !required.isEmpty() && !contract.value("id").toString().isEmpty() &&
                !contract.value("revision").toString().isEmpty() && !connections.isEmpty() &&
                sameGraph(edges, connections);
            for (const auto &signal : required) {
                const auto s = signal.toString();
                const auto n = contract.value("interface_node").toString();
                matches &= reaches(connections, "controller", n, s) &&
                           reaches(connections, n, "service", s);
            }
            if (!matches) {
                status = fail;
                reason = "Le contrat de l’interface est incompatible avec le graphe déclaré";
            } else if (contract.value("kind") == "PASSIVE_BENCH") {
                status = pass;
                reason = "Continuité et signaux de l’interface passive synthétique vérifiés";
            } else {
                reason = "Preuve électrique du composant actif absente";
            }
        } else {
            reason = "Contrat électrique distinct manquant pour l’interface";
        }
    } else {
        require(false, "Type de contrôle L3 inconnu : " + kind);
    }
    require(status == pass || status == fail || status == unknown || status == "NOT_APPLICABLE",
            "Verdict de contrôle inconnu");
    if (limit.isNull() && status == pass) {
        status = unknown;
        reason = "Seuil applicable inconnu";
    }
    return {{"requirement_id", requirement.value("id")}, {"requirement_revision", requirement.value("revision")},
            {"subjects", requirement.value("subject_ids")}, {"method", requirement.value("method")},
            {"classification", requirement.value("classification")}, {"status", status},
            {"observed", measured.isUndefined() ? QJsonValue(QJsonValue::Null) : measured},
            {"criterion", criterion}, {"margin", margin}, {"margin_unit", unit}, {"reason", reason}};
}

double cableLength(const QJsonArray &points)
{
    double total = 0;
    for (qsizetype index = 1; index < points.size(); ++index) {
        const auto a = points.at(index - 1).toArray(), b = points.at(index).toArray();
        require(a.size() == 3 && b.size() == 3, "Point d’axe L2 incomplet");
        total += std::hypot(number(a.at(0)) - number(b.at(0)),
                            number(a.at(1)) - number(b.at(1)), number(a.at(2)) - number(b.at(2)));
    }
    return total;
}

QJsonObject objectives(const QJsonArray &definitions, const QJsonObject &parameters,
                       const QJsonObject &interconnection)
{
    QJsonObject values;
    for (const auto &item : definitions) {
        const auto metric = item.toObject();
        const auto name = id(metric.value("id"));
        require(!values.contains(name) && (metric.value("direction") == "MIN" ||
                metric.value("direction") == "MAX") && !metric.value("unit").toString().isEmpty(),
                "Objectif invalide ou dupliqué : " + name);
        QJsonValue value = QJsonValue::Null;
        const auto method = metric.value("method");
        if (method == "AFFINE") {
            value = affine(metric.value("expression").toObject(), parameters);
        } else if (method == "L2_AXIS") {
            const auto plan = interconnection.value("report").toObject().value("native_plan").toObject();
            for (const auto &entry : plan.value("cables").toArray()) {
                const auto cable = entry.toObject();
                const auto points = cable.value("points_mm").toArray();
                if (cable.value("id") == metric.value("cable_id") && points.size() >= 2) {
                    value = cableLength(points);
                    break;
                }
            }
        } else if (method == "L2_SERVICE") {
            const auto services = interconnection.value("service_checks").toObject();
            const auto service = services.value(metric.value("service").toString()).toObject();
            if (service.value("minimum_margin_mm").isDouble()) {
                value = service.value("minimum_margin_mm");
            }
        } else {
            require(method == "UNAVAILABLE", "Méthode de mesure inconnue");
        }
        auto observed = metric;
        observed.insert("value", value);
        values.insert(name, observed);
    }
    return values;
}

QJsonArray diagnostic(const QJsonArray &rules, const QJsonArray &findings, const QJsonObject &parameters)
{
    QJsonArray conflicts;
    for (qsizetype i = 0; i < rules.size(); ++i) {
        const auto finding = findings.at(i).toObject();
        if (finding.value("status") == pass || finding.value("status") == "NOT_APPLICABLE") {
            continue;
        }
        const auto rule = rules.at(i).toObject();
        const auto cause = rule.value("diagnostic").toObject();
        QJsonArray variables;
        const auto ranges = cause.value("ranges").toObject();
        auto low = parameters, high = parameters;
        const auto check = rule.value("check").toObject();
        const auto terms = check.value("terms").toObject();
        for (auto it = ranges.begin(); it != ranges.end(); ++it) {
            const auto range = it.value().toArray();
            require(parameters.contains(it.key()) && range.size() == 2, "Intervalle hors paramètres");
            const double a = number(range.at(0)), b = number(range.at(1));
            require(a <= b, "Intervalle inversé");
            const bool increasing = terms.value(it.key()).toDouble() >= 0;
            low.insert(it.key(), increasing ? a : b);
            high.insert(it.key(), increasing ? b : a);
            variables.append(QJsonObject{{"parameter_id", it.key()}, {"range", range}});
        }
        QJsonValue envelope = QJsonValue::Null;
        QString conclusion = finding.value("status") == fail ? "OBSERVED_FAILURE" : "INSUFFICIENT_EVIDENCE";
        if (check.value("kind") == "AFFINE" && !ranges.isEmpty()) {
            const auto first = evaluateCheck(rule, low, {}).value("margin");
            const auto last = evaluateCheck(rule, high, {}).value("margin");
            if (first.isDouble() && last.isDouble()) {
                const double minimum = std::min(first.toDouble(), last.toDouble());
                const double maximum = std::max(first.toDouble(), last.toDouble());
                envelope = QJsonObject{{"minimum", minimum}, {"maximum", maximum},
                                       {"unit", finding.value("margin_unit")}};
                conclusion = maximum < 0 ? "CONTRADICTORY_IN_DECLARED_DOMAIN" :
                    minimum >= 0 ? "FEASIBLE_IN_DECLARED_DOMAIN" : "BOUNDARY_IN_DECLARED_DOMAIN";
            }
        }
        QJsonValue hypothesis = cause.value("cause");
        if (hypothesis.isUndefined()) {
            hypothesis = QJsonValue::Null;
        }
        conflicts.append(QJsonObject{{"requirement_id", finding.value("requirement_id")},
            {"object_ids", finding.value("subjects")}, {"observed_status", finding.value("status")},
            {"observed_margin", finding.value("margin")}, {"margin_unit", finding.value("margin_unit")},
            {"cause_hypothesis", hypothesis},
            {"adjustable_variables", variables}, {"unknowns", cause.value("unknowns").toArray()},
            {"hard_constraint", finding.value("classification") == "MANDATORY"},
            {"margin_range", envelope}, {"conclusion", conclusion}});
    }
    return conflicts;
}

struct Evaluator {
    const QJsonObject &bench;
    const QJsonObject &criteria;
    const QString &baselineSha;
    const QString &requirementsSha;
    const Interconnection &interconnection;
    const Publish &publish;
    QJsonObject researchEvidence;
    QJsonArray researchReports;

    QJsonObject evaluate(const QString &candidateId, const QJsonObject &definition,
                         const QJsonObject &parameters, const QJsonObject &changes) const
    {
        QJsonObject l2;
        QJsonArray evidence;
        if (bench.value("interconnection") == true) {
            l2 = interconnection(parameters, researchReports);
            const auto path = "candidates/" + candidateId + "-l2.json";
            evidence.append(QJsonObject{{"path", path}, {"sha256", publish(path, l2)}});
        }
        const auto affected = linksAffected(bench.value("links").toArray(), changes,
                                            bench.value("parameter_subjects").toObject());
        const auto rules = criteria.value("rules").toArray();
        require(!rules.isEmpty(), "Aucune exigence gelée pour le banc");
        QJsonArray findings, checked;
        QSet<QString> requirements;
        QString verdict = pass;
        for (const auto &item : rules) {
            const auto rule = item.toObject();
            auto finding = evaluateCheck(rule, parameters, l2);
            const auto req = finding.value("requirement_id").toString();
            require(!req.isEmpty() && !requirements.contains(req), "Exigence vide ou dupliquée : " + req);
            requirements.insert(req);
            const auto classification = finding.value("classification");
            require(classification == "MANDATORY" || classification == "MODIFIABLE" ||
                    classification == "INHERITED" || classification == "UNKNOWN", "Classification L0 invalide");
            if (finding.value("status") != "NOT_APPLICABLE") {
                if (classification == "MANDATORY") {
                    verdict = aggregate(verdict, finding.value("status").toString());
                } else if (classification == "UNKNOWN") {
                    verdict = aggregate(verdict, unknown);
                }
            }
            for (const auto &link : affected) {
                if (finding.value("status") != "NOT_APPLICABLE" &&
                    finding.value("subjects").toArray().contains(link) && !checked.contains(link)) {
                    checked.append(link);
                }
            }
            findings.append(finding);
        }
        for (const auto &link : affected) {
            if (!checked.contains(link)) {
                verdict = aggregate(verdict, unknown);
            }
        }
        return {{"id", candidateId}, {"bench_id", bench.value("id")}, {"scope", "SYNTHETIC_BENCH"},
            {"baseline_sha256", baselineSha}, {"requirements_sha256", requirementsSha},
            {"family", definition.value("family")}, {"topology", definition.value("topology")},
            {"status", verdict}, {"parameters", parameters}, {"changes", changes},
            {"impacted_links", affected}, {"reevaluated_links", checked}, {"findings", findings},
            {"conflict_graph", diagnostic(rules, findings, parameters)},
            {"objectives", objectives(criteria.value("objectives").toArray(), parameters, l2)},
            {"validation_evidence", evidence}};
    }
};

bool activeFailure(const QJsonObject &report, const QJsonArray &ids)
{
    const auto findings = report.value("findings").toArray();
    return std::any_of(findings.begin(), findings.end(), [&ids](const auto &entry) {
        const auto f = entry.toObject();
        return ids.contains(f.value("requirement_id")) &&
            (f.value("status") == fail || f.value("status") == unknown);
    });
}

QJsonObject sensitivity(const QJsonObject &study, const QJsonObject &parameters,
                        const Interconnection &interconnection, const QJsonArray &research)
{
    const auto name = study.value("parameter").toString();
    const auto original = parameters.value(name);
    const auto range = study.value("range").toArray();
    require(original.isNull() && range.size() == 2, "Sensibilité réservée à une inconnue explicite");
    const auto low = number(range.at(0)), high = number(range.at(1));
    require(low < high, "Plage de sensibilité invalide");
    const auto service = study.value("l2_service").toString();
    require(service == "extraction" || service == "tool", "Contrôle L2 de sensibilité inconnu");
    QJsonArray samples;
    for (double sample : {low, low + (high - low) / 2, high}) {
        auto test = parameters;
        test.insert(name, sample);
        const auto evaluation = interconnection(test, research);
        const auto check = evaluation.value("service_checks").toObject().value(service).toObject();
        const auto report = evaluation.value("report").toObject();
        const auto margin = check.value("minimum_margin_mm");
        require(margin.isDouble(), "Mesure L2 de sensibilité absente");
        samples.append(QJsonObject{{"value_mm", sample}, {"margin_mm", margin},
            {"limiting_obstacle_id", check.value("obstacle_id")}, {"compatibility", report.value("compatibility")},
            {"geometry", report.value("geometry")}});
    }
    QJsonArray brackets;
    for (qsizetype index = 1; index < samples.size(); ++index) {
        const auto a = samples.at(index - 1).toObject(), b = samples.at(index).toObject();
        if ((a.value("margin_mm").toDouble() >= 0) != (b.value("margin_mm").toDouble() >= 0)) {
            brackets.append(QJsonArray{a.value("value_mm"), b.value("value_mm")});
        }
    }
    return {{"parameter", name}, {"range_mm", range}, {"samples", samples},
            {"sampled_transition_brackets_mm", brackets}, {"scope", "HYPOTHETICAL_BENCH_SENSITIVITY"}};
}

QJsonObject compare(const QMap<QString, QJsonObject> &evaluations, const QJsonArray &definitions)
{
    QMap<QString, QJsonObject> admitted;
    QJsonArray excluded, missing, used, frontier;
    QJsonObject dominated;
    for (auto it = evaluations.begin(); it != evaluations.end(); ++it) {
        if (it.value().value("status") == pass) {
            admitted.insert(it.key(), it.value().value("objectives").toObject());
        } else {
            excluded.append(QJsonObject{{"id", it.key()}, {"status", it.value().value("status")}});
        }
    }
    for (const auto &entry : definitions) {
        const auto def = entry.toObject();
        const auto metric = id(def.value("id"));
        QJsonArray absent;
        for (auto it = admitted.begin(); it != admitted.end(); ++it) {
            if (!it.value().value(metric).toObject().value("value").isDouble()) {
                absent.append(it.key());
            }
        }
        if (absent.isEmpty() && !admitted.isEmpty()) {
            used.append(def);
        } else {
            missing.append(QJsonObject{{"id", metric}, {"missing_for", absent}});
        }
    }
    for (auto candidate = admitted.begin(); candidate != admitted.end(); ++candidate) {
        QJsonArray winners;
        for (auto other = admitted.begin(); other != admitted.end(); ++other) {
            bool noWorse = true, better = false;
            for (const auto &entry : used) {
                const auto def = entry.toObject();
                const auto metric = def.value("id").toString();
                const auto a = number(candidate.value().value(metric).toObject().value("value"));
                const auto b = number(other.value().value(metric).toObject().value("value"));
                const auto delta = (a - b) * (def.value("direction") == "MIN" ? 1 : -1);
                noWorse &= delta >= 0;
                better |= delta > 0;
            }
            if (noWorse && better) {
                winners.append(other.key());
            }
        }
        if (!winners.isEmpty()) {
            dominated.insert(candidate.key(), winners);
        } else if (!used.isEmpty()) {
            frontier.append(candidate.key());
        }
    }
    return {{"method", "PARETO_COMMON_NUMERIC_OBJECTIVES"}, {"frontier", frontier},
            {"dominated_by", dominated}, {"objectives_used", used}, {"objectives_unavailable", missing},
            {"excluded", excluded}};
}

} // namespace

QJsonObject explore(const QJsonObject &bench, const QJsonObject &requirements,
                    const QString &baselineSha, const QString &requirementsSha,
                    const Interconnection &interconnection, const Research &research,
                    const Publish &publish)
{
    const auto benchId = id(bench.value("id"));
    require(bench.value("id") == requirements.value("id"), "Banc et exigences hors du même périmètre");
    Evaluator evaluator{bench, requirements, baselineSha, requirementsSha, interconnection, publish, {}, {}};
    const auto base = bench.value("parameters").toObject();
    const auto baseline = evaluator.evaluate(benchId + "-baseline",
        {{"family", "BASELINE"}, {"topology", bench.value("baseline_topology")}}, base, {});
    const auto baselinePath = "candidates/" + benchId + "-baseline.json";
    const QJsonObject baselineRef{{"path", baselinePath}, {"sha256", publish(baselinePath, baseline)}};
    const auto localBudget = budget(bench.value("local_budget"));
    const auto totalBudget = budget(bench.value("candidate_budget"));
    require(localBudget <= totalBudget, "Budget local supérieur au budget global");
    QMap<QString, QJsonObject> reports, definitions;
    QJsonArray attempts, candidates, decisions, portfolios;
    QSet<QString> identifiers{baseline.value("id").toString()};
    const auto variants = bench.value("alternatives").toArray();
    const QSet<QString> families{"ROUTING", "CONNECTOR", "PLACEMENT", "FUNCTIONAL_ARCHITECTURE"};
    QSet<QString> variantIds;
    for (const auto &item : variants) {
        const auto variant = item.toObject();
        const auto variantId = id(variant.value("id"));
        require(!identifiers.contains(variantId) && families.contains(variant.value("family").toString()) &&
                !variant.value("topology").toString().isEmpty() && !variant.value("changes").toObject().isEmpty(),
                "Variante invalide ou dupliquée : " + variantId);
        identifiers.insert(variantId);
        variantIds.insert(variantId);
    }
    for (const auto &item : variants) {
        const auto variant = item.toObject();
        for (const auto &field : {"dependencies", "incompatibilities"}) {
            for (const auto &reference : variant.value(field).toArray()) {
                require(reference != variant.value("id") && variantIds.contains(id(reference)),
                        "Référence de décision invalide");
            }
        }
        if (variant.contains("superseded_by")) {
            const auto successor = id(variant.value("superseded_by"));
            require(successor != variant.value("id") && variantIds.contains(successor),
                    "Successeur de décision invalide");
        }
    }
    int localUsed = 0;
    bool localPassed = false;
    const bool requireLocal = bench.value("require_local_exhaustion") == true;
    for (const auto &item : variants) {
        const auto variant = item.toObject();
        const auto variantId = id(variant.value("id"));
        const bool local = variant.value("family") == "ROUTING";
        QString skip;
        if (baseline.value("status") == pass || !activeFailure(baseline, variant.value("triggers").toArray())) {
            skip = "NO_MATCHING_BASELINE_CONFLICT";
        } else if (!local && requireLocal && localPassed) {
            skip = "LOCAL_REPAIR_SUFFICIENT";
        } else if (!local && requireLocal && localUsed < localBudget) {
            skip = "LOCAL_BUDGET_NOT_EXERCISED";
        } else if (reports.size() >= totalBudget || (local && localUsed >= localBudget)) {
            skip = "BUDGET_EXHAUSTED";
        }
        if (!skip.isEmpty()) {
            attempts.append(QJsonObject{{"id", variantId}, {"state", "PROPOSED"}, {"reason", skip}});
            continue;
        }
        evaluator.researchReports = {};
        QJsonValue evidence = QJsonValue::Null, study = QJsonValue::Null;
        auto changes = variant.value("changes").toObject();
        auto parameters = apply(base, changes);
        const auto question = variant.value("research").toObject();
        if (!question.isEmpty()) {
            const auto issue = question.value("issue_id").toString();
            require(!issue.isEmpty(), "Question L1 sans identifiant");
            if (!evaluator.researchEvidence.contains(issue)) {
                auto response = research(issue);
                const auto path = "candidates/" + variantId + "-research.json";
                response.insert("path", path);
                response.insert("artifact_sha256", publish(path, response.value("report").toObject()));
                evaluator.researchEvidence.insert(issue, response);
            }
            const auto response = evaluator.researchEvidence.value(issue).toObject();
            const auto report = response.value("report").toObject();
            evaluator.researchReports.append(report);
            evidence = QJsonObject{{"path", response.value("path")},
                                   {"sha256", response.value("artifact_sha256")},
                                   {"l1_stdout_sha256", response.value("sha256")},
                                   {"question", report.value("question")}, {"outcome", report.value("outcome")}};
            if (report.value("outcome") != "RESOLVED") {
                study = sensitivity(question.value("sensitivity").toObject(), parameters,
                                    interconnection, evaluator.researchReports);
            }
        }
        auto result = evaluator.evaluate(variantId, variant, parameters, changes);
        if (!evidence.isNull()) {
            result.insert("research_evidence", evidence);
            result.insert("parametric_study", study);
            result.insert("status", aggregate(result.value("status").toString(), unknown));
            result.insert("research_limit", "La qualification de la référence et la projection applicable restent requises");
        }
        reports.insert(variantId, result);
        definitions.insert(variantId, variant);
        attempts.append(QJsonObject{{"id", variantId}, {"state", "TESTED"}, {"status", result.value("status")},
            {"trigger_requirement_ids", variant.value("triggers")}});
        if (local) {
            ++localUsed;
            localPassed |= result.value("status") == pass;
        }
    }

    const auto ranking = compare(reports, requirements.value("objectives").toArray());
    const auto frontier = ranking.value("frontier").toArray();
    for (const auto &item : variants) {
        const auto variant = item.toObject();
        const auto variantId = id(variant.value("id"));
        const auto report = reports.value(variantId);
        const auto candidatePath = "candidates/" + variantId + ".json";
        QJsonArray evidence{baselineRef};
        QJsonValue state = "PROPOSED";
        QJsonValue successor = QJsonValue::Null;
        if (!report.isEmpty()) {
            const auto digest = publish(candidatePath, report);
            const QJsonObject ref{{"id", variantId}, {"path", candidatePath}, {"sha256", digest},
                                 {"status", report.value("status")}};
            candidates.append(ref);
            evidence.append(ref);
            state = report.value("status") == fail ? "REJECTED" :
                frontier.size() == 1 && frontier.contains(variantId) &&
                variant.value("dependencies").toArray().isEmpty() ? "SELECTED" : "TESTED";
            const auto requested = variant.value("superseded_by");
            if (ranking.value("dominated_by").toObject().value(variantId).toArray().contains(requested)) {
                state = "SUPERSEDED";
                successor = requested;
            }
        }
        const auto causes = baseline.value("conflict_graph").toArray();
        QJsonArray relevant;
        for (const auto &entry : causes) {
            if (variant.value("triggers").toArray().contains(entry.toObject().value("requirement_id"))) {
                relevant.append(entry);
            }
        }
        decisions.append(QJsonObject{{"id", "decision-" + variantId}, {"state", state}, {"scope", "SYNTHETIC_BENCH"},
            {"objective", bench.value("objective")}, {"causes", relevant}, {"variants_studied", QJsonArray{variantId}},
            {"family", variant.value("family")}, {"evidence_refs", evidence},
            {"impacted_parameters", variant.value("changes")}, {"tradeoffs", variant.value("tradeoffs")},
            {"dependencies", variant.value("dependencies").toArray()},
            {"incompatibilities", variant.value("incompatibilities").toArray()},
            {"validation_actions", variant.value("validation_actions")}, {"superseded_by", successor}});
    }
    const auto portfolioDefinitions = bench.value("portfolios").toArray();
    require(portfolioDefinitions.size() <= 100, "Trop de consolidations demandées");
    for (const auto &item : portfolioDefinitions) {
        const auto portfolio = item.toObject();
        const auto portfolioId = id(portfolio.value("id"));
        require(!identifiers.contains(portfolioId), "Identifiant de consolidation dupliqué");
        identifiers.insert(portfolioId);
        const auto members = portfolio.value("members").toArray();
        require(members.size() >= 2, "Consolidation : deux décisions ou plus attendues");
        QSet<QString> selected;
        for (const auto &member : members) {
            const auto key = id(member);
            require(!selected.contains(key), "Décision répétée dans la consolidation");
            selected.insert(key);
        }
        QJsonObject combined;
        QJsonArray conflicts;
        for (const auto &member : members) {
            const auto key = member.toString();
            require(variantIds.contains(key), "Décision de consolidation inconnue");
            if (reports.value(key).value("status") != pass) {
                conflicts.append(QJsonObject{{"code", "INDIVIDUAL_NOT_ADMISSIBLE"}, {"member", member}});
                continue;
            }
            const auto definition = definitions.value(key);
            for (const auto &dep : definition.value("dependencies").toArray()) {
                if (!selected.contains(dep.toString())) {
                    conflicts.append(QJsonObject{{"code", "MISSING_DEPENDENCY"}, {"member", member}, {"other", dep}});
                }
            }
            for (const auto &other : definition.value("incompatibilities").toArray()) {
                if (selected.contains(other.toString())) {
                    conflicts.append(QJsonObject{{"code", "DECLARED_INCOMPATIBILITY"}, {"member", member}, {"other", other}});
                }
            }
            const auto patch = definition.value("changes").toObject();
            for (auto it = patch.begin(); it != patch.end(); ++it) {
                if (combined.contains(it.key()) && combined.value(it.key()) != it.value()) {
                    conflicts.append(QJsonObject{{"code", "CONFLICTING_ASSIGNMENTS"}, {"parameter", it.key()},
                                                {"first", combined.value(it.key())}, {"second", it.value()}});
                } else {
                    combined.insert(it.key(), it.value());
                }
            }
        }
        QJsonObject joint;
        if (conflicts.isEmpty()) {
            evaluator.researchReports = {};
            joint = evaluator.evaluate(portfolioId, {{"family", "COMBINATION"}, {"topology", "JOINT_REEVALUATION"}},
                                       apply(base, combined), combined);
        }
        const auto status = conflicts.isEmpty() ? joint.value("status") : QJsonValue(fail);
        for (const auto &finding : joint.value("findings").toArray()) {
            if (finding.toObject().value("status") == fail &&
                finding.toObject().value("classification") == "MANDATORY") {
                conflicts.append(QJsonObject{{"code", "JOINT_CONSTRAINT_VIOLATION"},
                    {"requirement_id", finding.toObject().value("requirement_id")}});
            }
        }
        const auto path = "candidates/" + portfolioId + ".json";
        const QJsonObject detail{{"id", portfolioId}, {"members", members}, {"status", status},
            {"conflicts", conflicts}, {"joint_evaluation", joint}};
        portfolios.append(QJsonObject{{"id", portfolioId}, {"path", path}, {"status", status},
                                     {"sha256", publish(path, detail)}, {"members", members}});
    }
    for (qsizetype position = 0; position < decisions.size(); ++position) {
        auto decision = decisions.at(position).toObject();
        const auto variant = decision.value("variants_studied").toArray().first();
        QJsonArray rejectedCombinations;
        for (const auto &entry : portfolios) {
            const auto portfolio = entry.toObject();
            if (portfolio.value("status") == fail && portfolio.value("members").toArray().contains(variant)) {
                rejectedCombinations.append(portfolio);
            }
        }
        decision.insert("rejected_combinations", rejectedCombinations);
        decisions.replace(position, decision);
    }
    return {{"id", benchId}, {"baseline", baselineRef}, {"baseline_status", baseline.value("status")},
            {"attempts", attempts}, {"local_attempts", localUsed}, {"candidate_budget", totalBudget},
            {"candidates", candidates}, {"comparison", ranking}, {"decisions", decisions}, {"portfolios", portfolios}};
}

} // namespace architecture_decision
