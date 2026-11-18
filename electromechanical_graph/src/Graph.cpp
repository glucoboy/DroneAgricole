#include "Graph.hpp"

#include <QDir>
#include <QJsonArray>
#include <QMap>
#include <QRegularExpression>
#include <QSet>
#include <QStringList>
#include <algorithm>
#include <cmath>
#include <stdexcept>

namespace electromechanical::graph {
namespace {

const QSet<QString> kinds{
    "DEVICE", "PORT", "RECEPTACLE", "PLUG", "CONTACT", "CONDUCTOR", "HARNESS_SEGMENT",
    "JUNCTION", "BUNDLE", "SUPPORT", "ANCHOR", "FASTENER", "STRUCTURE", "KEEP_OUT",
    "MOTION_DOMAIN", "SERVICE_ENVELOPE", "CONTROL", "OBSERVATION", "ELECTRICAL_LINK"
};
const QSet<QString> relations{
    "MATES", "ELECTRICAL", "WIRE_EXIT", "ROUTING", "CONTAINS", "FASTENS", "RETAINS",
    "MEMBER_OF", "TRANSFORMS", "DEPENDS_ON", "ACCESS", "MOTION", "OBSERVES", "VERIFIES"
};
const QSet<QString> policies{"HARD_FIXED", "HARD_REQUIREMENT", "SOFT_OBJECTIVE", "DESIGN_VARIABLE", "UNKNOWN"};
const QSet<QString> operations{"MOVE", "RETENTION", "FRAME"};
const QSet<QString> directions{"FORWARD", "REVERSE", "BOTH", "NONE"};
const QSet<QString> facts{"DOCUMENTED", "MEASURED", "ASSUMED", "UNKNOWN"};
const QSet<QString> receptions{"PASS", "FAIL", "INCONCLUSIVE", "NOT_RUN"};

void require(bool ok, const QString &reason)
{
    if (!ok)
        throw std::runtime_error(reason.toStdString());
}

QString field(const QJsonObject &object, const QString &key)
{
    const auto value = object.value(key).toString();
    require(!value.trimmed().isEmpty(), "Champ texte obligatoire : " + key);
    return value;
}

QJsonArray array(const QJsonObject &object, const QString &key)
{
    require(object.value(key).isArray(), "Tableau obligatoire : " + key);
    return object.value(key).toArray();
}

QJsonObject object(const QJsonObject &parent, const QString &key)
{
    require(parent.value(key).isObject(), "Objet obligatoire : " + key);
    return parent.value(key).toObject();
}

bool sha256(const QString &value)
{
    static const QRegularExpression pattern("^[a-f0-9]{64}$");
    return pattern.match(value).hasMatch();
}

void evidence(const QJsonObject &record, const QJsonObject &sources)
{
    const auto proof = object(record, "evidence");
    const auto state = field(proof, "state");
    require(facts.contains(state), "État de preuve inconnu : " + state);
    require(sources.contains(field(proof, "source")), "Autorité absente du graphe");
    field(proof, "locator");
    field(proof, "scope");
    require(proof.contains("unit") && (proof.value("unit").isNull() || proof.value("unit").isString()),
            "Unité de preuve absente");
    const auto reception = field(proof, "reception");
    require(receptions.contains(reception) &&
            ((state != "ASSUMED" && state != "UNKNOWN") || reception != "PASS"),
            "Réception incompatible avec la preuve");
}

QMap<QString, QJsonObject> index(const QJsonArray &entries)
{
    QMap<QString, QJsonObject> result;
    for (const auto &entry : entries) {
        const auto record = entry.toObject();
        const auto id = field(record, "id");
        require(!result.contains(id), "Identité dupliquée : " + id);
        result.insert(id, record);
    }
    return result;
}

QJsonArray sorted(const QSet<QString> &values)
{
    auto keys = values.values();
    std::sort(keys.begin(), keys.end());
    return QJsonArray::fromStringList(keys);
}

void subjects(const QJsonObject &record, const QMap<QString, QJsonObject> &nodes)
{
    const auto values = array(record, "subjects");
    require(!values.isEmpty(), "Portée sans nœud : " + field(record, "id"));
    QSet<QString> seen;
    for (const auto &subject : values) {
        const auto id = subject.toString();
        require(nodes.contains(id) && !seen.contains(id), "Sujet absent ou dupliqué : " + id);
        seen.insert(id);
    }
}

double number(const QJsonValue &value)
{
    require(value.isDouble() && std::isfinite(value.toDouble()), "Nombre fini attendu");
    return value.toDouble();
}

void matrix(const QJsonValue &value)
{
    if (value.isNull())
        return;
    const auto elements = value.toArray();
    require(elements.size() == 16, "Matrice 4×4 attendue");
    for (const auto &element : elements)
        number(element);
    require(std::abs(elements.at(12).toDouble()) < 1e-9 && std::abs(elements.at(13).toDouble()) < 1e-9
            && std::abs(elements.at(14).toDouble()) < 1e-9 && std::abs(elements.at(15).toDouble() - 1) < 1e-9,
            "Dernière ligne homogène invalide");
}

struct Vector {
    double x, y, z;
};

Vector vector(const QJsonObject &frame, const QString &key)
{
    const auto values = array(frame, key);
    require(values.size() == 3, "Vecteur 3D attendu");
    return {number(values[0]), number(values[1]), number(values[2])};
}

double dot(const Vector &a, const Vector &b)
{
    return a.x * b.x + a.y * b.y + a.z * b.z;
}

} // namespace

void validate(const QJsonObject &graph)
{
    require(graph.value("schema") == "v3.graph/1", "Version de graphe non prise en charge");
    field(graph, "configuration");
    const auto sources = object(graph, "sources");
    for (auto it = sources.begin(); it != sources.end(); ++it) {
        const auto source = it.value().toObject();
        const auto path = field(source, "path");
        require(QDir::isRelativePath(path) && QDir::cleanPath(path) == path &&
                !path.startsWith("../") && path != ".." && !path.contains('\\') && !path.contains(':'),
                "Chemin de source invalide : " + path);
        require(sha256(field(source, "sha256")), "Empreinte de source invalide : " + path);
    }
    const auto nodes = index(array(graph, "nodes"));
    require(!nodes.isEmpty(), "Graphe vide");
    QSet<QString> occurrences;
    for (const auto &node : nodes) {
        require(kinds.contains(field(node, "kind")), "Type de nœud inconnu");
        require(node.value("version") == 1, "Version de nœud non prise en charge");
        evidence(node, sources);
        QSet<QString> keys;
        for (const auto &entry : array(node, "claims")) {
            const auto claim = entry.toObject();
            const auto key = field(claim, "key");
            require(!keys.contains(key) && claim.contains("value"), "Assertion invalide : " + key);
            keys.insert(key);
            evidence(claim, sources);
            if (claim.value("evidence").toObject().value("state") == "UNKNOWN")
                require(claim.value("value").isNull(), "Inconnue dotée d'une valeur : " + key);
            if (key.endsWith("_frame") && !claim.value("value").isNull()) {
                const auto frame = object(claim, "value");
                if (key == "device_mount_frame") {
                    matrix(object(frame, "valeur").value("matrice_4x4_lignes"));
                } else {
                    const auto origin = field(frame, "origin_role");
                    require(origin == "NATIVE_FACE" || origin == "FIXTURE_DATUM",
                            "Un repère de port indépendant est requis : " + key);
                    field(frame, "frame");
                    vector(frame, "origin_mm");
                    const auto direction = vector(frame, "direction");
                    require(std::abs(dot(direction, direction) - 1) < 1e-7,
                            "Tangente signée non unitaire : " + key);
                }
            }
        }
        if (node.value("kind") == "PORT" && !graph.value("reconciliation").toObject().isEmpty()) {
            for (const auto *key : {"inventory", "device_mount_frame", "receptacle_frame",
                                    "mating_frame", "plug_frame", "wire_exit_frame"})
                require(keys.contains(key), "Inventaire de port incomplet : " + field(node, "id") + '/' + key);
        }
        if (!node.contains("occurrence"))
            continue;
        const auto occurrence = object(node, "occurrence");
        const auto identity = field(occurrence, "id");
        require(!occurrences.contains(identity), "Occurrence ambiguë : " + identity);
        occurrences.insert(identity);
        field(occurrence, "object");
        field(occurrence, "definition");
        require(occurrence.value("visible").isBool() && occurrence.contains("matrix") &&
                occurrence.contains("local_matrix"), "Occurrence incomplète : " + identity);
        matrix(occurrence.value("matrix"));
        matrix(occurrence.value("local_matrix"));
    }
    const auto edges = index(array(graph, "edges"));
    QSet<QString> relationships;
    for (const auto &edge : edges) {
        require(relations.contains(field(edge, "kind")) && directions.contains(field(edge, "impact")),
                "Relation ou sens d'impact non reconnu");
        const auto from = field(edge, "from");
        const auto to = field(edge, "to");
        require(nodes.contains(from) && nodes.contains(to) && from != to, "Relation sans nœuds distincts : " + from + " / " + to);
        require(!edge.contains("terminal") || edge.value("terminal").isBool(), "Propagation terminale invalide");
        evidence(edge, sources);
        relationships.insert(field(edge, "kind") + ':' + from + "->" + to);
    }
    for (const auto &node : nodes) {
        if (node.value("kind") != "ELECTRICAL_LINK")
            continue;
        bool hasTopology = false;
        for (const auto &entry : node.value("claims").toArray()) {
            const auto claim = entry.toObject();
            if (claim.value("key") != "topology")
                continue;
            hasTopology = true;
            const auto row = object(claim, "value");
            const auto line = field(row, "id");
            const auto id = field(node, "id");
            auto requireRelation = [&relationships, &id](const QString &key) {
                require(relationships.contains(key), "Relation d'autorité absente : " + id + ' ' + key);
            };
            requireRelation("ELECTRICAL:port:" + line + "/A->" + id);
            requireRelation("ELECTRICAL:port:" + line + "/B->" + id);
            const auto path = array(row, "path");
            require(!path.isEmpty() || row.value("scope_reason").isString(), "Liaison sans axe non motivée : " + line);
            int order = 0;
            for (const auto &entry : path) {
                const auto step = entry.toObject();
                const auto axis = field(step, "route_id");
                const auto key = "ROUTING:" + id + "->axis:" + axis;
                requireRelation(key);
                const auto edge = edges.value(key);
                require(edge.value("order") == order++ && edge.value("sense") == step.value("sense"),
                        "Ordre ou sens de cheminement divergent : " + key);
            }
            for (const auto &junction : array(row, "junction_ids"))
                requireRelation("ELECTRICAL:" + id + "->junction:" + junction.toString());
            for (const auto &cord : array(row, "cord_ids"))
                requireRelation("MEMBER_OF:" + id + "->cord:" + cord.toString());
        }
        require(hasTopology, "Topologie obligatoire : " + field(node, "id"));
    }
    for (const auto &constraint : index(array(graph, "constraints"))) {
        subjects(constraint, nodes);
        evidence(constraint, sources);
        const auto policy = field(constraint, "policy");
        const auto state = field(constraint, "state");
        static const QSet<QString> states{"NOMINAL", "SERVICE", "MOBILE"};
        require(policies.contains(policy) && states.contains(state), "Contrainte incompatible");
        field(constraint, "criticality");
        const auto authority = field(constraint, "authority");
        require(sources.contains(authority), "Autorité de contrainte absente : " + authority);
        require(constraint.contains("threshold") && constraint.contains("tolerance") &&
                (constraint.value("unit").isString() || constraint.value("unit").isNull()), "Seuil, unité ou tolérance absents");
        const auto proof = constraint.value("evidence").toObject();
        if (policy.startsWith("HARD_") || policy == "DESIGN_VARIABLE") {
            require(proof.value("state") == "DOCUMENTED" && proof.value("source") == authority,
                    "Une exigence ou permission requiert une autorité documentée");
        }
        if (policy.startsWith("HARD_") && constraint.value("threshold").isNull())
            field(constraint, "condition");
        if (policy == "DESIGN_VARIABLE")
            require(constraint.value("threshold").isObject() && !constraint.value("threshold").toObject().isEmpty(),
                    "Domaine de modification absent");
    }
    for (const auto &issue : index(array(graph, "issues"))) {
        subjects(issue, nodes);
        evidence(issue, sources);
        field(issue, "severity");
        field(issue, "detail");
    }
}

QJsonObject impact(const QJsonObject &graph, const QString &operation, const QString &target)
{
    validate(graph);
    require(operations.contains(operation), "Opération inconnue : " + operation);
    const auto nodes = index(array(graph, "nodes"));
    require(nodes.contains(target), "Cible absente : " + target);
    const auto targetKind = nodes.value(target).value("kind").toString();
    if (operation == "RETENTION") {
        static const QSet<QString> eligible{"SUPPORT", "ANCHOR", "FASTENER"};
        require(eligible.contains(targetKind), "Cible sans fonction de retenue : " + target);
    } else if (operation == "FRAME") {
        static const QSet<QString> eligible{"PORT", "RECEPTACLE", "PLUG", "CONTACT", "OBSERVATION"};
        require(eligible.contains(targetKind), "Cible sans repère d'interface ou d'observation : " + target);
    } else {
        static const QSet<QString> eligible{"DEVICE", "STRUCTURE", "SUPPORT", "ANCHOR", "FASTENER",
                                           "KEEP_OUT", "SERVICE_ENVELOPE", "MOTION_DOMAIN"};
        require(eligible.contains(targetKind), "Cible sans implantation recomposable : " + target);
    }
    const auto edges = index(array(graph, "edges"));
    QMultiMap<QString, QPair<QString, QString>> dependencies;
    for (const auto &edge : edges) {
        const auto from = edge.value("from").toString();
        const auto to = edge.value("to").toString();
        const auto id = edge.value("id").toString();
        const auto direction = edge.value("impact").toString();
        if (direction == "FORWARD" || direction == "BOTH")
            dependencies.insert(from, {to, id});
        if (direction == "REVERSE" || direction == "BOTH")
            dependencies.insert(to, {from, id});
    }
    QStringList pending{target};
    QSet<QString> expanded{target}, reached{target}, traversed;
    while (!pending.isEmpty()) {
        const auto current = pending.takeLast();
        for (const auto &step : dependencies.values(current)) {
            reached.insert(step.first);
            traversed.insert(step.second);
            if (!edges.value(step.second).value("terminal").toBool() && !expanded.contains(step.first)) {
                expanded.insert(step.first);
                pending.append(step.first);
            }
        }
    }
    QSet<QString> checks, observations, cables, interfaces, volumes, supports, constraints, issues;
    for (const auto &id : reached) {
        const auto kind = nodes.value(id).value("kind").toString();
        if (kind == "CONTROL")
            checks.insert(id);
        if (kind == "OBSERVATION")
            observations.insert(id);
        if (kind == "HARNESS_SEGMENT" || kind == "BUNDLE" || kind == "CONDUCTOR")
            cables.insert(id);
        if (kind == "PORT" || kind == "RECEPTACLE" || kind == "PLUG" || kind == "CONTACT")
            interfaces.insert(id);
        if (kind == "KEEP_OUT" || kind == "SERVICE_ENVELOPE" || kind == "MOTION_DOMAIN")
            volumes.insert(id);
        if (kind == "SUPPORT" || kind == "ANCHOR" || kind == "FASTENER")
            supports.insert(id);
    }
    auto impactedRecords = [&reached](const QJsonArray &records, QSet<QString> &result) {
        for (const auto &entry : records) {
            const auto record = entry.toObject();
            const auto subjects = record.value("subjects").toArray();
            if (std::any_of(subjects.cbegin(), subjects.cend(), [&reached](const auto &subject) {
                return reached.contains(subject.toString());
            }))
                result.insert(record.value("id").toString());
        }
    };
    impactedRecords(array(graph, "constraints"), constraints);
    impactedRecords(array(graph, "issues"), issues);
    return {{"schema", "v3.impact/1"}, {"operation", operation}, {"target", target},
            {"nodes", sorted(reached)}, {"edges", sorted(traversed)}, {"checks", sorted(checks)},
            {"invalidate_observations", sorted(observations)}, {"rebuild_cables", sorted(cables)},
            {"recompose_interfaces", sorted(interfaces)}, {"recompose_volumes", sorted(volumes)},
            {"review_supports", sorted(supports)}, {"review_constraints", sorted(constraints)},
            {"review_issues", sorted(issues)}, {"applied", false}};
}

QJsonObject compareFrames(const QJsonObject &request)
{
    require(request.value("schema") == "v3.frame_comparison/1", "Version de comparaison non prise en charge");
    const auto expected = object(request, "reference");
    const auto observed = object(request, "observed");
    const auto axis = object(request, "axis");
    const auto role = field(expected, "origin_role");
    require(role == "NATIVE_FACE" || role == "FIXTURE_DATUM", "Référence indépendante requise");
    const auto reference = field(expected, "artifact_sha256");
    const auto candidate = field(observed, "artifact_sha256");
    const auto axisDigest = field(axis, "artifact_sha256");
    require(sha256(reference) && sha256(candidate) && sha256(axisDigest) &&
            reference != candidate && reference != axisDigest, "Identités de preuve incompatibles");
    require(field(expected, "frame") == field(observed, "frame") && field(expected, "frame") == field(axis, "frame"),
            "Convention de repère différente");
    const auto a = vector(expected, "origin_mm");
    const auto b = vector(observed, "origin_mm");
    const auto c = vector(axis, "origin_mm");
    const auto da = vector(expected, "direction");
    const auto db = vector(observed, "direction");
    require(std::abs(dot(da, da) - 1) < 1e-7 && std::abs(dot(db, db) - 1) < 1e-7,
            "Tangentes signées unitaires attendues");
    const auto distance = std::hypot(a.x - b.x, a.y - b.y, a.z - b.z);
    const auto angle = std::acos(std::clamp(dot(da, db), -1.0, 1.0)) * 180 / std::acos(-1.0);
    const auto positionTolerance = number(request.value("position_tolerance_mm"));
    const auto angleTolerance = number(request.value("angle_tolerance_deg"));
    require(positionTolerance >= 0 && angleTolerance >= 0 && angleTolerance <= 180, "Tolérance invalide");
    return {{"status", distance <= positionTolerance && angle <= angleTolerance ? "PASS" : "FAIL"},
            {"position_error_mm", distance}, {"signed_direction_error_deg", angle},
            {"axis_to_observed_mm", std::hypot(b.x - c.x, b.y - c.y, b.z - c.z)}};
}

} // namespace electromechanical::graph
