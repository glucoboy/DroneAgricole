#include "Connectivity.hpp"

#include "Interconnection.hpp"

#include <QJsonArray>
#include <QSet>
#include <stdexcept>

namespace electromechanical_validation {
namespace {

const QString pass = QStringLiteral("PASS");
const QString fail = QStringLiteral("FAIL");
const QString unknown = QStringLiteral("INCONCLUSIVE");

QJsonObject find(const QJsonValue &records, const QJsonValue &key, const QString &field = "id")
{
    for (const auto &entry : records.toArray()) {
        const auto record = entry.toObject();
        if (record.value(field) == key) {
            return record;
        }
    }
    return {};
}

QJsonObject records(const QJsonObject &dossier)
{
    return dossier.value("model").toObject().value("records").toObject();
}

QJsonObject interfaceRecord(const QJsonObject &dossier, const QJsonValue &id)
{
    return find(dossier.value("interfaces"), id);
}

bool synthetic(const QJsonObject &reference)
{
    return reference.value("mode") == "SYNTHETIC_BENCH";
}

Assessment port(const QJsonObject &dossier, const QJsonObject &reference,
                const QJsonObject &observed, const QJsonValue &expected)
{
    const auto actual = records(dossier);
    const auto mate = find(actual.value("connector_mates"), observed.value("mate_id"));
    const auto receptacle = find(actual.value("connector_receptacles"), mate.value("receptacle_id"));
    const auto id = receptacle.value("port_id").toString();
    const auto physical = find(actual.value("ports"), id);
    const auto equipment = find(actual.value("equipment"), physical.value("equipment_id"));
    const auto authority = interconnection::index(records(reference).value("technical_evidence"), "technical_evidence");
    const auto isSynthetic = synthetic(reference);
    bool portSourced = false;
    for (const auto &proofId : physical.value("evidence_ids").toArray()) {
        const auto proof = authority.value(proofId.toString());
        const QJsonObject assertion{{"value", true}, {"status", isSynthetic ? "ASSUMED" : "SOURCED"},
            {"evidence_ids", QJsonArray{proofId}}, {"revision", proof.value("revision")}};
        portSourced |= interconnection::sourced(assertion, authority, isSynthetic);
    }
    const auto equipmentRef = equipment.value("item_reference").toObject();
    if (id.isEmpty() || expected.toString().isEmpty() || !portSourced ||
        !interconnection::sourced(equipmentRef, authority, isSynthetic) ||
        physical.value("function").toString().isEmpty() || physical.value("direction").toString().isEmpty() ||
        physical.value("direction") == "UNKNOWN") {
        return {unknown, QJsonValue::Null, "1", "Identité ou provenance du port observé insuffisante"};
    }
    const auto placement = QString("Port requis %1, port observé %2").arg(expected.toString(), id);
    if (expected != id) {
        return {fail, id, "1", placement};
    }
    const auto fixed = records(reference);
    const auto expectedPort = find(fixed.value("ports"), expected);
    if (expectedPort.isEmpty()) {
        return {unknown, id, "1", "Identifiant de port sans définition indépendante dans la référence gelée"};
    }
    const auto expectedEquipment = find(fixed.value("equipment"), expectedPort.value("equipment_id"));
    const auto expectedRef = expectedEquipment.value("item_reference").toObject();
    if (physical.value("equipment_id") != expectedPort.value("equipment_id") ||
        equipmentRef.value("value") != expectedRef.value("value") ||
        equipmentRef.value("revision") != expectedRef.value("revision") ||
        physical.value("function") != expectedPort.value("function") ||
        physical.value("direction") != expectedPort.value("direction")) {
        return {fail, id, "1", "Identifiant de port réutilisé avec un équipement, une révision ou une fonction divergente"};
    }
    return {pass, id, "1", placement};
}

Assessment revision(const QJsonObject &dossier, const QJsonObject &reference, const QJsonValue &id)
{
    const auto interface = interfaceRecord(dossier, id);
    const auto actual = records(dossier);
    const auto mate = find(actual.value("connector_mates"), interface.value("mate_id"));
    const auto receptacle = find(actual.value("connector_receptacles"), mate.value("receptacle_id"));
    const auto parts = reference.value("catalog").toObject().value("parts");
    const auto authority = interconnection::index(records(reference).value("technical_evidence"), "technical_evidence");
    QStringList revisions;
    bool missing = false;
    for (const auto &binding : {qMakePair(receptacle, interface.value("receptacle_part_id")),
                                qMakePair(mate, interface.value("mate_part_id"))}) {
        const auto declared = binding.first.value("part_reference").toObject();
        const auto documented = find(parts, binding.second).value("reference").toObject();
        const auto actualRevision = declared.value("revision").toString();
        const auto actualPart = declared.value("value").toString();
        if (actualRevision.isEmpty() || actualPart.isEmpty() || declared.value("status") == "UNKNOWN" ||
            !interconnection::sourced(documented, authority, synthetic(reference))) {
            missing = true;
            continue;
        }
        if (declared.value("value") != documented.value("value") ||
            declared.value("revision") != documented.value("revision")) {
            return {fail, actualRevision, "1", QString("Référence ou révision déclarée %1/%2 en conflit avec le catalogue gelé %3/%4")
                .arg(actualPart, actualRevision, documented.value("value").toString(), documented.value("revision").toString())};
        }
        if (!interconnection::sourced(declared, authority, synthetic(reference))) {
            missing = true;
        }
        revisions.append(actualRevision);
    }
    return missing ? Assessment{unknown, QJsonValue::Null, "1", "Référence ou révision des deux demi-connecteurs incomplète"} :
        Assessment{pass, revisions.join(" / "), "1", "Révisions déclarées cohérentes avec les références gelées"};
}

QSet<QString> pinIds(const QJsonValue &values)
{
    QSet<QString> ids;
    for (const auto &pin : values.toArray()) {
        ids.insert(pin.toString());
    }
    return ids;
}

Assessment matrix(const QJsonObject &dossier, const QJsonObject &reference)
{
    const auto expected = records(reference);
    const auto observed = records(dossier);
    const auto expectedCircuits = interconnection::index(expected.value("circuits"), "circuits gelés");
    const auto actualCircuits = interconnection::index(observed.value("circuits"), "circuits observés");
    bool missing = expectedCircuits.isEmpty();
    for (const auto &target : expectedCircuits) {
        const auto id = target.value("id").toString();
        const auto actual = actualCircuits.value(id);
        if (actual.isEmpty()) {
            missing = true;
            continue;
        }
        const auto expectedPins = pinIds(target.value("pin_ids"));
        const auto actualPins = pinIds(actual.value("pin_ids"));
        if (!(actualPins - expectedPins).isEmpty()) {
            return {fail, id, "1", "Affectation de broches contraire à la matrice gelée"};
        }
        missing |= actualPins != expectedPins;
        for (const auto &key : {"group_id", "function", "kind", "scope"}) {
            const auto value = actual.value(key);
            if (value.isUndefined() || value == "UNKNOWN" || (value.isNull() && QString(key) != "group_id")) {
                missing = true;
            } else if (value != target.value(key)) {
                return {fail, id, "1", QString("Attribut de circuit contraire à la matrice gelée : ") + key};
            }
        }
        for (const auto &pin : expectedPins) {
            const auto expectedPin = find(expected.value("pins"), pin);
            const auto actualPin = find(observed.value("pins"), pin);
            for (const auto &key : {"port_id", "number", "signal", "role"}) {
                if (actualPin.value(key).toString().isEmpty() || actualPin.value(key) == "UNKNOWN") {
                    missing = true;
                } else if (actualPin.value(key) != expectedPin.value(key)) {
                    return {fail, pin, "1", QString("Attribut de broche contraire à la matrice gelée : ") + key};
                }
            }
        }
    }
    if (missing || actualCircuits.size() != expectedCircuits.size()) {
        return {unknown, QJsonValue::Null, "1", "Périmètre des circuits de la matrice gelée incomplet ou divergent"};
    }
    return {pass, static_cast<double>(expectedCircuits.size()), "1", "Circuits et broches réconciliés avec la matrice gelée"};
}

QJsonObject lockedDossier(QJsonObject dossier, const QJsonObject &reference)
{
    for (const auto &field : {"catalog", "geometry", "signal_groups", "research_issue_ids"}) {
        dossier.insert(field, reference.value(field));
    }
    auto model = dossier.value("model").toObject();
    const auto referenceModel = reference.value("model").toObject();
    auto observed = records(dossier);
    const auto locked = records(reference);
    observed.insert("technical_evidence", locked.value("technical_evidence"));
    for (const auto &field : {"frames", "states"}) {
        model.insert(field, referenceModel.value(field));
    }
    observed.insert("routes", locked.value("routes"));
    model.insert("records", observed);
    dossier.insert("model", model);
    QJsonArray interfaces;
    for (const auto &entry : dossier.value("interfaces").toArray()) {
        auto item = entry.toObject();
        const auto rule = interfaceRecord(reference, item.value("id"));
        for (const auto &field : {"required_component_roles", "requirements"}) {
            item.insert(field, rule.value(field));
        }
        const auto expectedPort = rule.value("required_port_id");
        const auto measured = port(dossier, reference, item, expectedPort);
        item.insert("required_port_id", measured.status == unknown ? QJsonValue::Null : expectedPort);
        interfaces.append(item);
    }
    dossier.insert("interfaces", interfaces);
    return dossier;
}

bool cableSpecificationsMatch(const QJsonObject &dossier, const QJsonObject &reference)
{
    const auto expectedCables = reference.value("cable_parts").toObject();
    const auto observedCables = dossier.value("cable_parts").toObject();
    if (expectedCables.keys() != observedCables.keys()) {
        return false;
    }
    for (auto cable = expectedCables.begin(); cable != expectedCables.end(); ++cable) {
        const auto expected = cable.value().toObject();
        const auto observed = observedCables.value(cable.key()).toObject();
        if (expected.value("part_id") != observed.value("part_id")) {
            return false;
        }
        const auto expectedSpecs = expected.value("specifications").toObject();
        const auto observedSpecs = observed.value("specifications").toObject();
        for (auto specification = expectedSpecs.begin(); specification != expectedSpecs.end(); ++specification) {
            const auto expectedValue = specification.value().toObject();
            const auto observedValue = observedSpecs.value(specification.key()).toObject();
            for (const auto &key : {"value", "unit", "revision"}) {
                if (expectedValue.value(key) != observedValue.value(key)) {
                    return false;
                }
            }
        }
    }
    return true;
}

Assessment diagnose(const QJsonObject &check, const QJsonObject &reference, const QJsonObject &candidate)
{
    const auto parameters = check.value("parameters").toObject();
    const auto bench = find(reference.value("l3").toObject().value("benches"), "diagnostic");
    QJsonObject path;
    for (const auto &entry : bench.value("rules").toArray()) {
        const auto rule = entry.toObject();
        if (rule.value("requirement").toObject().value("id") == parameters.value("path_id")) {
            path = rule.value("check").toObject();
            break;
        }
    }
    const auto start = path.value("from").toString();
    const auto end = path.value("to").toString();
    const auto signal = path.value("signal").toString();
    const auto graph = candidate.value("diagnostic_graph");
    if (path.value("kind") != "FUNCTION_PATH" || start.isEmpty() || end.isEmpty() || start == end ||
        signal.isEmpty() || !graph.isArray()) {
        return {unknown, QJsonValue::Null, "1", "Chemin gelé ou graphe de diagnostic absent ou invalide"};
    }
    QMap<QString, QSet<QString>> neighbors;
    for (const auto &item : graph.toArray()) {
        const auto edge = item.toObject();
        const auto from = edge.value("from").toString();
        const auto to = edge.value("to").toString();
        const auto actualSignal = edge.value("signal").toString();
        if (from.isEmpty() || to.isEmpty() || actualSignal.isEmpty()) {
            return {unknown, QJsonValue::Null, "1", "Arête de diagnostic sans extrémités ou signal identifiés"};
        }
        if (actualSignal == signal) {
            neighbors[from].insert(to);
        }
    }
    QSet<QString> visited{start};
    QStringList pending{start};
    while (!pending.isEmpty()) {
        const auto from = pending.takeLast();
        if (from == end) {
            return {pass, true, "1", QString("Chemin %1 de %2 à %3 conservé dans le graphe du banc").arg(signal, start, end)};
        }
        const auto next = neighbors.value(from) - visited;
        visited.unite(next);
        pending.append(next.values());
    }
    return {fail, false, "1", QString("Chemin %1 de %2 à %3 interrompu dans le graphe du banc").arg(signal, start, end)};
}

Assessment archived(const QString &method, const QJsonObject &check, const QJsonObject &reference)
{
    const auto parameters = check.value("parameters").toObject();
    const auto line = find(reference.value("reconciliation").toObject().value("lines"), parameters.value("line_id"));
    const auto research = find(reference.value("research"), parameters.value("issue_id"), "issue_id");
    const auto value = research.value("value").toObject();
    const auto observation = line.value("finding").toObject();
    if (method == "L1_ARCHIVED_GEOMETRY" && research.value("configuration_id") == "prototype_cartographe" &&
        research.value("outcome") == "RESOLVED" && value.value("status") == "SOURCED" &&
        value.value("value") == "NON_CONFORME_GEOMETRIE_RC02" && value.value("value") == line.value("action3_status")) {
        return {fail, value.value("value"), "1", "Constat CAO archivé L1 recoupé par le rapprochement L2. " +
            observation.value("observation").toString()};
    }
    const auto question = research.value("question").toObject().value("expected_evidence").toString();
    const auto next = observation.value("open_check").toString();
    return {unknown, QJsonValue::Null, "1", question.isEmpty() ?
        (next.isEmpty() ? QString("Preuve d’archive applicable insuffisante") : next) : question};
}

Assessment electrical(const QString &method, const QJsonObject &check, const QJsonObject &reference,
                      const QJsonObject &candidate)
{
    const auto authority = reference.value("l2").toObject();
    const auto dossier = candidate.value("dossier").toObject();
    const auto actualConfig = dossier.value("model").toObject().value("configuration_id");
    const auto lockedConfig = authority.value("model").toObject().value("configuration_id");
    if (dossier.isEmpty() || authority.isEmpty() || actualConfig != lockedConfig ||
        dossier.value("mode") != authority.value("mode")) {
        return {unknown, QJsonValue::Null, "1", "Dossier L2 observé absent ou de configuration différente"};
    }
    const auto parameters = check.value("parameters").toObject();
    const auto id = parameters.value("interface_id");
    if (method == "L2_PORT") {
        const auto expected = parameters.value("expected_port_id");
        return port(dossier, authority, interfaceRecord(dossier, id), expected.isUndefined() ?
            interfaceRecord(authority, id).value("required_port_id") : expected);
    }
    if (method == "L2_REVISION") {
        return revision(dossier, authority, id);
    }
    const auto observed = interconnection::index(dossier.value("interfaces"), "interfaces observées");
    const auto expected = interconnection::index(authority.value("interfaces"), "interfaces gelées");
    bool portsComplete = true;
    if (method == "L2_CONTINUITY") {
        for (const auto &target : expected) {
            const auto actual = observed.value(target.value("id").toString());
            const auto measured = port(dossier, authority, actual, target.value("required_port_id"));
            if (measured.status == fail) {
                return measured;
            }
            portsComplete &= measured.status == pass;
        }
    }
    const auto projected = lockedDossier(dossier, authority);
    const auto report = interconnection::validate(projected, parameters.value("state_id").toString("nominal"),
        reference.value("l2_research").toArray());
    const auto domain = method == "L2_CONTINUITY" ? "electrical" : "compatibility";
    const auto status = report.value(domain).toString(unknown);
    const auto findings = report.value("findings").toArray();
    if (status == fail) {
        for (const auto &entry : findings) {
            const auto finding = entry.toObject();
            if (finding.value("domain") == domain && finding.value("status") == fail) {
                return {fail, finding.value("code"), "1", finding.value("reason").toString()};
            }
        }
    }
    const auto reconciliation = method == "L2_CONTINUITY" ? matrix(dossier, authority) :
        Assessment{pass, static_cast<double>(expected.size()), "1", "Compatibilité L2 vérifiée sur le catalogue gelé"};
    if (reconciliation.status != pass) {
        return reconciliation;
    }
    if (!portsComplete || observed.keys() != expected.keys() || expected.isEmpty() || status != pass) {
        return {unknown, QJsonValue::Null, "1", "Chaîne ou preuve L2 incomplète sur le périmètre gelé"};
    }
    if (method == "L2_COMPATIBILITY" && !cableSpecificationsMatch(dossier, authority)) {
        return {unknown, QJsonValue::Null, "1", "Sélection ou caractéristiques de cordon sans concordance avec la référence gelée"};
    }
    return reconciliation;
}

} // namespace

Assessment assessConnectivity(const QJsonObject &check, const QJsonObject &reference,
                              const QJsonObject &candidate)
{
    const auto method = check.value("method").toString();
    try {
        if (method == "L3_DIAGNOSTIC_PATH") {
            return diagnose(check, reference, candidate);
        }
        if (method == "L1_ARCHIVED_GEOMETRY" || method == "L1_L2_ARCHIVED_PORT") {
            return archived(method, check, reference);
        }
        if (method == "L2_PORT" || method == "L2_REVISION" || method == "L2_CONTINUITY" || method == "L2_COMPATIBILITY") {
            return electrical(method, check, reference, candidate);
        }
    } catch (const std::runtime_error &error) {
        return {unknown, QJsonValue::Null, "1", QString("Données d’interconnexion inexploitées : %1").arg(QString::fromUtf8(error.what()))};
    }
    return {"NOT_RUN", QJsonValue::Null, "1", "Méthode de connectivité non disponible"};
}

} // namespace electromechanical_validation
