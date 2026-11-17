#include "Interconnection.hpp"

#include <QSet>
#include <stdexcept>

namespace interconnection {
namespace {

const QString pass = QStringLiteral("PASS");
const QString fail = QStringLiteral("FAIL");
const QString unknown = QStringLiteral("INCONCLUSIVE");

struct Model {
    Index equipment, ports, receptacles, mates, contacts, pins, circuits, cables, terminals;
    Index evidence;
};

Model readModel(const QJsonObject &records)
{
    return {index(records.value("equipment"), "equipment"), index(records.value("ports"), "ports"),
        index(records.value("connector_receptacles"), "connector_receptacles"),
        index(records.value("connector_mates"), "connector_mates"), index(records.value("contacts"), "contacts"),
        index(records.value("pins"), "pins"), index(records.value("circuits"), "circuits"),
        index(records.value("cables"), "cables"), index(records.value("terminals"), "terminals"),
        index(records.value("technical_evidence"), "technical_evidence")};
}

bool supportedEvidence(const QJsonObject &record, const Model &model, bool synthetic)
{
    for (const auto &id : record.value("evidence_ids").toArray()) {
        const auto proof = model.evidence.value(id.toString());
        const QJsonObject asserted{{"value", true}, {"status", synthetic ? "ASSUMED" : "SOURCED"},
            {"evidence_ids", QJsonArray{id}}, {"revision", proof.value("revision")}};
        if (sourced(asserted, model.evidence, synthetic)) {
            return true;
        }
    }
    return false;
}

void add(Findings &findings, const QString &domain, const QString &code, const QString &subject,
         const QString &status, const QString &reason)
{
    findings.append({domain, code, subject, status, reason});
}

QSet<QString> ids(const QJsonArray &array)
{
    QSet<QString> result;
    for (const auto &entry : array) {
        const auto id = entry.toString();
        if (id.isEmpty() || result.contains(id)) {
            throw std::runtime_error("Identifiant de relation vide ou dupliqué");
        }
        result.insert(id);
    }
    return result;
}

bool sameReference(const QJsonObject &a, const QJsonObject &b)
{
    return a.value("value") == b.value("value") && a.value("revision") == b.value("revision");
}

struct ContactBindings {
    QHash<QString, QString> plugToPin;
    QHash<QString, QString> plugToCable;
    QHash<QString, QString> plugToEnd;
    QHash<QString, QString> plugToReceptacle;
    QSet<QString> expectedPins;
};

QJsonArray bindContacts(const Model &model, const QJsonObject &receptacle, const QJsonObject &mate,
                        const QJsonObject &pair, const QJsonObject &pinout, const QString &cableId, const QString &endId,
                        const QJsonObject &receptaclePart, const QJsonObject &matePart,
                        const ConnectorCatalog &catalog, QMap<QString, int> &bom,
                        ContactBindings &bindings, Findings &findings, bool synthetic)
{
    QJsonArray projection;
    QSet<QString> plugCavities, receptacleCavities, matchedPlugContacts, receptaclePins;
    const auto mateId = mate.value("id").toString();
    const auto receptacleId = receptacle.value("id").toString();
    const auto portId = receptacle.value("port_id").toString();
    const auto cavityMap = pair.value("cavity_map").toObject();
    const bool pinoutSourced = pinout.value("unit") == "1" && catalog.hasSource(pinout);
    const auto physicalPins = pinout.value("value").toObject();
    for (const auto &contact : model.contacts) {
        if (contact.value("owner_id") == mateId && contact.value("owner_type") == "MATE") {
            const auto cavity = contact.value("cavity").toString();
            if (cavity.isEmpty() || plugCavities.contains(cavity)) {
                add(findings, "electrical", "CONTACT_CAVITY", mateId, fail, "Cavité de fiche vide ou dupliquée");
            }
            plugCavities.insert(cavity);
        }
        if ((contact.value("owner_id") == mateId && contact.value("owner_type") == "MATE") ||
            (contact.value("owner_id") == receptacleId && contact.value("owner_type") == "RECEPTACLE")) {
            const auto part = catalog.contactPart(contact.value("part_reference").toObject());
            if (part.isEmpty()) {
                add(findings, "compatibility", "CONTACT_REFERENCE", contact.value("id").toString(), unknown,
                    "Référence ou intégration du contact à documenter");
            } else {
                ++bom[part];
            }
        }
        if (contact.value("owner_id") != receptacleId || contact.value("owner_type") != "RECEPTACLE") {
            continue;
        }
        const auto id = contact.value("id").toString();
        const auto cavity = contact.value("cavity").toString();
        const auto pinId = contact.value("pin_id").toString();
        const auto pin = model.pins.value(pinId);
        const auto plugId = contact.value("mating_contact_id").toString();
        const auto plug = model.contacts.value(plugId);
        if (cavity.isEmpty() || receptacleCavities.contains(cavity) ||
            (!pinId.isEmpty() && receptaclePins.contains(pinId))) {
            add(findings, "electrical", "CONTACT_CAVITY", id, fail, "Cavité ou broche d’embase répétée");
        }
        receptacleCavities.insert(cavity);
        receptaclePins.insert(pinId);
        if (!synthetic || !pinout.isEmpty()) {
            const auto expected = physicalPins.value(cavity).toString();
            const auto number = pin.value("number").toString();
            if (!pinoutSourced || expected.isEmpty() || number.isEmpty() || !supportedEvidence(pin, model, synthetic)) {
                add(findings, "electrical", "PHYSICAL_PIN_NUMBER", id, unknown, "Numéro de broche de cette cavité sans preuve");
            } else if (number != expected) {
                add(findings, "electrical", "PHYSICAL_PIN_NUMBER", id, fail, "Numéro de broche différent du plan de l’embase");
            } else {
                add(findings, "electrical", "PHYSICAL_PIN_NUMBER", id, pass, "Numéro de broche conforme au plan de l’embase");
            }
        }
        if (pin.value("role") == "RESERVED" && plugId.isEmpty()) {
            continue;
        }
        if (pin.isEmpty() || plug.isEmpty()) {
            add(findings, "electrical", "CONTACT_MAPPING", id, unknown, "Broche ou contact apparié inconnu");
            continue;
        }
        if (pin.value("port_id") != portId || plug.value("owner_id") != mateId ||
            plug.value("owner_type") != "MATE" || plug.value("mating_contact_id") != id ||
            matchedPlugContacts.contains(plugId)) {
            add(findings, "electrical", "CONTACT_MAPPING", id, fail, "Contact, port ou appariement réciproque incompatible");
            continue;
        }
        const auto expected = cavityMap.value(cavity);
        if (expected.isUndefined() || !supportedEvidence(contact, model, synthetic) ||
            !supportedEvidence(plug, model, synthetic) || !supportedEvidence(pin, model, synthetic) ||
            pin.value("signal").toString().trimmed().isEmpty() || pin.value("role") == "UNKNOWN") {
            add(findings, "electrical", "CONTACT_MAPPING", id, unknown, "Affectation de cavité ou brochage sans preuve");
        } else if (expected != plug.value("cavity")) {
            add(findings, "electrical", "CONTACT_MAPPING", id, fail, "Permutation de cavités contraire au plan de la paire");
        } else {
            add(findings, "electrical", "CONTACT_MAPPING", id, pass, "Broche, cavité et contact apparié concordants");
        }
        if (bindings.plugToPin.contains(plugId)) {
            add(findings, "electrical", "CONTACT_REUSE", plugId, fail, "Contact utilisé par plusieurs extrémités");
        }
        bindings.plugToPin.insert(plugId, pinId);
        bindings.plugToCable.insert(plugId, cableId);
        bindings.plugToEnd.insert(plugId, endId);
        bindings.plugToReceptacle.insert(plugId, id);
        matchedPlugContacts.insert(plugId);
        projection.append(QJsonObject{{"receptacle_contact_id", id}, {"mate_contact_id", plugId},
            {"cavity", cavity}, {"mate_cavity", plug.value("cavity")}, {"pin_id", pinId},
            {"pin_number", pin.value("number")}, {"signal", pin.value("signal")}});
    }
    QSet<QString> pinNumbers;
    for (const auto &pin : model.pins) {
        if (pin.value("port_id") != portId) {
            continue;
        }
        const auto pinId = pin.value("id").toString();
        const auto number = pin.value("number").toString();
        if (number.isEmpty()) {
            add(findings, "electrical", "PIN_NUMBER", pinId, unknown, "Numéro de broche inconnu");
        } else if (pinNumbers.contains(number)) {
            add(findings, "electrical", "PIN_NUMBER", pinId, fail, "Numéro de broche répété pour le port");
        }
        pinNumbers.insert(number);
        if (pin.value("role") == "RESERVED") {
            continue;
        }
        bindings.expectedPins.insert(pinId);
        if (!receptaclePins.contains(pinId)) {
            add(findings, "electrical", "PIN_COVERAGE", pinId, unknown, "Broche active sans contact d’embase identifié");
        }
    }
    if (projection.isEmpty() || matchedPlugContacts.size() != plugCavities.size()) {
        add(findings, "electrical", "CONTACT_COVERAGE", mateId, unknown, "Contacts de fiche absents ou non appariés");
    }
    const auto checkWays = [&](const QJsonObject &part, qsizetype count, const QString &id) {
        const auto ways = part.value("attributes").toObject().value("ways").toObject();
        if (!catalog.hasSource(ways)) {
            return;
        }
        const auto maximum = ways.value("value").toDouble(-1);
        if (count > maximum) {
            add(findings, "compatibility", "CONTACT_COUNT", id, fail, "Le nombre de contacts excède les voies déclarées");
        } else if (count < maximum) {
            add(findings, "compatibility", "CONTACT_COUNT", id, unknown, "Voies sans affectation ou obturation documentée");
        }
    };
    checkWays(receptaclePart, receptacleCavities.size(), receptacleId);
    checkWays(matePart, plugCavities.size(), mateId);
    return projection;
}

QJsonArray bindInterfaces(const QJsonObject &dossier, const Model &model, const ConnectorCatalog &catalog,
                          ContactBindings &bindings, QMap<QString, int> &bom, Findings &findings, bool synthetic)
{
    QJsonArray projection;
    QSet<QPair<QString, QString>> ends;
    for (const auto &entry : index(dossier.value("interfaces"), "interfaces")) {
        const auto id = entry.value("id").toString();
        const auto cableId = entry.value("cable_id").toString();
        const auto endId = entry.value("end_id").toString();
        const auto mateId = entry.value("mate_id").toString();
        const auto cable = model.cables.value(cableId);
        const auto mate = model.mates.value(mateId);
        const auto receptacle = model.receptacles.value(mate.value("receptacle_id").toString());
        const auto portId = receptacle.value("port_id").toString();
        const auto port = model.ports.value(portId);
        const auto equipment = model.equipment.value(port.value("equipment_id").toString());
        if (ends.contains({cableId, endId})) {
            add(findings, "electrical", "END_IDENTITY", id, fail, "Plusieurs liaisons revendiquent la même extrémité");
        }
        ends.insert({cableId, endId});
        if (cable.isEmpty() || mate.isEmpty() || port.isEmpty() || equipment.isEmpty()) {
            add(findings, "electrical", "END_IDENTITY", id, unknown, "Équipement, port, embase, fiche ou cordon inconnu");
            continue;
        }
        if (mate.value("cable_id") != cableId || mate.value("end_id") != endId ||
            !ids(cable.value("end_ids").toArray()).contains(endId) || mate.value("assembly_state") == "UNMATED") {
            add(findings, "electrical", "END_IDENTITY", id, fail, "Fiche non accouplée ou affectée à un autre cordon");
        } else if (mate.value("assembly_state") != "MATED") {
            add(findings, "electrical", "END_IDENTITY", id, unknown, "État d’accouplement inconnu");
        }
        const auto expectedPort = entry.value("required_port_id").toString();
        const auto equipmentRef = equipment.value("item_reference").toObject();
        if (!expectedPort.isEmpty() && expectedPort != portId) {
            add(findings, "electrical", "WRONG_PORT", id, fail, "Port attendu " + expectedPort + ", observé " + portId);
        } else if (expectedPort.isEmpty() || equipmentRef.value("value").toString().isEmpty() ||
                   !catalog.hasSource(equipmentRef) || !supportedEvidence(port, model, synthetic) ||
                   port.value("function").toString().isEmpty() || port.value("direction") == "UNKNOWN") {
            add(findings, "electrical", "PORT_IDENTITY", id, unknown, "Identité, révision ou fonction du port sans preuve");
        } else {
            add(findings, "electrical", "PORT_IDENTITY", id, pass, "Équipement révisé et port attendu identifiés");
        }

        const auto receptaclePart = entry.value("receptacle_part_id").toString();
        const auto matePart = entry.value("mate_part_id").toString();
        for (const auto &part : {receptaclePart, matePart}) {
            if (!part.isEmpty()) {
                ++bom[part];
            }
        }
        QSet<QString> installedRoles;
        for (const auto &part : ids(entry.value("component_part_ids").toArray())) {
            ++bom[part];
            const auto component = catalog.part(part);
            if (!catalog.hasSource(component.value("reference").toObject())) {
                add(findings, "compatibility", "ACCESSORY_SOURCE", part, unknown, "Accessoire sans référence applicable");
            } else {
                installedRoles.insert(component.value("role").toString());
            }
        }
        for (const auto &role : ids(entry.value("required_component_roles").toArray()) - installedRoles) {
            add(findings, "compatibility", "ACCESSORY_COVERAGE", id, unknown, "Accessoire requis non documenté : " + role);
        }
        for (const auto &item : {qMakePair(receptacle, receptaclePart), qMakePair(mate, matePart)}) {
            const auto declared = item.first.value("part_reference").toObject();
            const auto selected = catalog.part(item.second).value("reference").toObject();
            if (!catalog.hasSource(declared) || !catalog.hasSource(selected)) {
                add(findings, "compatibility", "ASSEMBLY_REFERENCE", id, unknown, "Référence du graphe ou du catalogue sans preuve");
            } else if (!sameReference(declared, selected)) {
                add(findings, "compatibility", "ASSEMBLY_REFERENCE", id, fail, "Référence ou révision montée différente du catalogue");
            }
            const auto attributes = catalog.part(item.second).value("attributes").toObject();
            for (const auto &key : {"family", "keying", "locking"}) {
                const auto a = item.first.value(key).toObject();
                const auto b = attributes.value(key).toObject();
                if (catalog.hasSource(a) && catalog.hasSource(b) && a.value("value") != b.value("value")) {
                    add(findings, "compatibility", "ASSEMBLY_ATTRIBUTE", id, fail, QString("Graphe et catalogue divergents pour ") + key);
                }
            }
        }
        const auto pair = catalog.pair(receptaclePart, matePart);
        findings += catalog.checkPair(receptaclePart, matePart, entry.value("requirements").toObject(), id);
        auto native = entry;
        native.insert("equipment_id", equipment.value("id"));
        native.insert("port_id", portId);
        native.insert("receptacle_id", receptacle.value("id"));
        native.insert("contacts", bindContacts(model, receptacle, mate, pair, entry.value("receptacle_pinout").toObject(), cableId, endId,
            catalog.part(receptaclePart), catalog.part(matePart), catalog, bom, bindings, findings, synthetic));
        projection.append(native);
    }
    for (const auto &cable : model.cables) {
        const auto cableId = cable.value("id").toString();
        const auto expected = ids(cable.value("end_ids").toArray());
        if (expected.size() < 2) {
            add(findings, "electrical", "END_COVERAGE", cableId, unknown, "Cordon sans ses deux extrémités documentées");
        }
        for (const auto &end : expected) {
            if (!ends.contains({cableId, end})) {
                add(findings, "electrical", "END_COVERAGE", cableId, unknown, "Extrémité non définie " + end);
            }
        }
    }
    return projection;
}

struct Conductor {
    QSet<QString> nodes;
    QString role;
};

using ConductorKey = QPair<QString, QString>;

QMap<ConductorKey, Conductor> readConductors(const Model &model, const ContactBindings &bindings,
                                             Findings &findings, const ConnectorCatalog &catalog, bool synthetic)
{
    QMap<ConductorKey, Conductor> result;
    QSet<QString> consumedContacts;
    for (const auto &cable : model.cables) {
        const auto cableId = cable.value("id").toString();
        const auto conductors = index(cable.value("conductors"), "conductors");
        if (conductors.isEmpty()) {
            add(findings, "electrical", "CONDUCTOR_COVERAGE", cableId, unknown, "Aucun conducteur documenté");
        }
        for (const auto &conductor : conductors) {
            const auto id = conductor.value("id").toString();
            Conductor connection{{}, conductor.value("role").toString()};
            const auto section = conductor.value("section_mm2").toObject();
            if (!catalog.hasSource(section) || section.value("unit") != "mm2" || section.value("value").toDouble() <= 0) {
                add(findings, "compatibility", "CONDUCTOR_SECTION", cableId + "/" + id, unknown, "Section de conducteur non établie");
            }
            for (const auto &terminalId : ids(conductor.value("terminal_ids").toArray())) {
                const auto terminal = model.terminals.value(terminalId);
                const auto kind = terminal.value("kind");
                const auto contactId = terminal.value("contact_id").toString();
                if (!supportedEvidence(terminal, model, synthetic)) {
                    add(findings, "electrical", "TERMINAL_SOURCE", terminalId, unknown, "Terminaison sans preuve applicable");
                }
                if (kind == "JUNCTION") {
                    connection.nodes.insert("junction/" + terminalId);
                } else if (kind == "CONTACT" && bindings.plugToPin.contains(contactId)) {
                    if (bindings.plugToCable.value(contactId) != cableId ||
                        bindings.plugToEnd.value(contactId) != terminal.value("end_id").toString() ||
                        consumedContacts.contains(contactId)) {
                        add(findings, "electrical", "TERMINAL_OWNERSHIP", terminalId, fail,
                            "Contact réutilisé ou rattaché à une autre extrémité");
                    }
                    consumedContacts.insert(contactId);
                    connection.nodes.insert("pin/" + bindings.plugToPin.value(contactId));
                } else if (kind == "FREE_END" && (connection.role == "SHIELD" || connection.role == "DRAIN" || connection.role == "SPARE") &&
                           ids(cable.value("end_ids").toArray()).contains(terminal.value("end_id").toString()) &&
                           !terminal.value("evidence_ids").toArray().isEmpty()) {
                    connection.nodes.insert("free/" + terminalId);
                } else {
                    const bool generic = kind == "FREE_END" || !terminal.value("mechanical_node_id").isUndefined();
                    add(findings, "electrical", "TERMINAL_CONTACT", terminalId, generic ? fail : unknown,
                        "Conducteur sans contact ni terminaison électrique documentée");
                }
            }
            if (connection.nodes.size() < 2) {
                add(findings, "electrical", "CONDUCTOR_COVERAGE", cableId + "/" + id, unknown,
                    "Le conducteur ne possède pas deux terminaisons distinctes démontrées");
            }
            result.insert({cableId, id}, connection);
        }
    }
    for (auto it = bindings.plugToPin.cbegin(); it != bindings.plugToPin.cend(); ++it) {
        if (bindings.expectedPins.contains(it.value()) && !consumedContacts.contains(it.key())) {
            add(findings, "electrical", "PIN_COVERAGE", it.value(), unknown, "Contact actif sans conducteur");
        }
    }
    return result;
}

void checkPinMapping(const Model &model, const ContactBindings &bindings, const ConnectorCatalog &catalog,
                     Findings &findings, bool synthetic)
{
    const auto conductors = readConductors(model, bindings, findings, catalog, synthetic);
    QSet<ConductorKey> usedConductors;
    QSet<QString> usedPins, usedJunctions;
    for (const auto &circuit : model.circuits) {
        const auto id = circuit.value("id").toString();
        const auto declaredPins = ids(circuit.value("pin_ids").toArray());
        QSet<QString> actualPins;
        QHash<QString, QSet<QString>> graph;
        bool incomplete = false;
        bool conflicting = false;
        const auto role = circuit.value("kind").toString();
        for (const auto &entry : circuit.value("spans").toArray()) {
            const auto span = entry.toObject();
            const ConductorKey key{span.value("cable_id").toString(), span.value("conductor_id").toString()};
            if (!conductors.contains(key)) {
                incomplete = true;
                continue;
            }
            const auto wire = conductors.value(key);
            conflicting |= usedConductors.contains(key) || (wire.role != role && wire.role != "UNKNOWN");
            incomplete |= wire.nodes.size() < 2 || wire.role == "UNKNOWN" || wire.role.isEmpty();
            usedConductors.insert(key);
            for (const auto &node : wire.nodes) {
                graph[node].unite(wire.nodes);
                if (node.startsWith("pin/")) {
                    actualPins.insert(node.mid(4));
                }
            }
        }
        for (const auto &pin : declaredPins) {
            const auto pinRecord = model.pins.value(pin);
            conflicting |= usedPins.contains(pin) || pinRecord.value("role") == "RESERVED";
            incomplete |= pinRecord.isEmpty() || pinRecord.value("role") == "UNKNOWN";
            const auto pinRole = pinRecord.value("role").toString();
            conflicting |= !pinRole.isEmpty() && pinRole != "UNKNOWN" && pinRole != role &&
                           !(role == "DRAIN" && pinRole == "SHIELD");
            usedPins.insert(pin);
        }
        for (auto it = graph.cbegin(); it != graph.cend(); ++it) {
            if (it.key().startsWith("junction/")) {
                conflicting |= usedJunctions.contains(it.key());
                usedJunctions.insert(it.key());
            }
        }
        QSet<QString> visited;
        if (!graph.isEmpty()) {
            QList<QString> pending{graph.constBegin().key()};
            while (!pending.isEmpty()) {
                const auto node = pending.takeLast();
                if (visited.contains(node)) {
                    continue;
                }
                visited.insert(node);
                for (const auto &neighbor : graph.value(node)) {
                    if (!visited.contains(neighbor)) {
                        pending.append(neighbor);
                    }
                }
            }
        }
        const bool incompatible = conflicting || !(actualPins - declaredPins).isEmpty() ||
            (!incomplete && !graph.isEmpty() && (visited.size() != graph.size() || actualPins != declaredPins));
        const bool unknownMapping = incomplete || graph.isEmpty() || declaredPins.isEmpty() ||
            !supportedEvidence(circuit, model, synthetic);
        add(findings, "electrical", "PIN_MAPPING", id, incompatible ? fail : (unknownMapping ? unknown : pass),
            incompatible ? "Continuité, rôle ou isolation entre circuits contraire à l’affectation attendue"
                         : (unknownMapping ? "Brochage ou chemin électrique incomplet" : "Broches attendues reliées par le même circuit"));
    }
    for (const auto &pin : bindings.expectedPins - usedPins) {
        add(findings, "electrical", "PIN_COVERAGE", pin, unknown, "Broche active sans circuit attendu");
    }
    for (auto it = conductors.cbegin(); it != conductors.cend(); ++it) {
        if (it.value().role != "SPARE" && !usedConductors.contains(it.key())) {
            add(findings, "electrical", "CONDUCTOR_COVERAGE", it.key().first + "/" + it.key().second,
                unknown, "Conducteur sans circuit attendu");
        }
    }
}

QJsonArray summarizeResearch(const QJsonObject &dossier, const QJsonArray &reports, Findings &findings)
{
    const auto config = dossier.value("model").toObject().value("configuration_id");
    const auto expected = ids(dossier.value("research_issue_ids").toArray());
    QSet<QString> seen;
    QJsonArray summary;
    for (const auto &entry : reports) {
        const auto report = entry.toObject();
        const auto issue = report.value("issue_id").toString();
        const auto outcome = report.value("outcome").toString();
        const QSet<QString> outcomes{"UNKNOWN", "INCONCLUSIVE", "CONDITIONAL", "RESOLVED"};
        const auto question = report.value("question").toObject();
        const auto value = report.value("value").toObject();
        const auto unknowns = report.value("unknown_register").toArray();
        const auto evidence = report.value("technical_evidence").toArray();
        if (report.value("schema_version") != "1.0.0" || report.value("configuration_id") != config ||
            !expected.contains(issue) || seen.contains(issue) || !outcomes.contains(outcome) ||
            question.value("id").toString().isEmpty() || value.isEmpty() ||
            !report.value("unknown_register").isArray() || !report.value("technical_evidence").isArray()) {
            throw std::runtime_error("Rapport L1 hors configuration, version, question ou doublon");
        }
        if (outcome == "RESOLVED" && (question.value("status") != "CLOSED" || !unknowns.isEmpty() || evidence.isEmpty() ||
            value.value("value").isNull() || value.value("value").isUndefined() ||
            (value.value("status") != "SOURCED" && value.value("status") != "MEASURED"))) {
            throw std::runtime_error("Rapport L1 résolu sans conclusion et preuves correspondantes");
        }
        if (outcome != "RESOLVED" && unknowns.isEmpty()) {
            throw std::runtime_error("Rapport L1 ouvert sans entrée au registre des inconnues");
        }
        seen.insert(issue);
        summary.append(QJsonObject{{"issue_id", issue}, {"outcome", outcome},
            {"unknown_register", report.value("unknown_register")}, {"value", report.value("value")}});
        if (outcome != "RESOLVED") {
            add(findings, "compatibility", "RESEARCH_OPEN", issue, unknown, "Le rapport L1 garde la question ouverte");
        }
    }
    for (const auto &issue : expected - seen) {
        add(findings, "compatibility", "RESEARCH_MISSING", issue, unknown, "Rapport L1 attendu absent");
    }
    return summary;
}

void checkCables(const QJsonObject &dossier, const Model &model, const ConnectorCatalog &catalog,
                 QMap<QString, int> &bom, Findings &findings)
{
    const auto parts = dossier.value("cable_parts").toObject();
    for (const auto &cable : model.cables) {
        const auto id = cable.value("id").toString();
        const auto selection = parts.value(id).toObject();
        const auto part = selection.value("part_id").toString();
        const auto reference = catalog.part(part).value("reference").toObject();
        const auto declared = cable.value("part_reference").toObject();
        if (!part.isEmpty()) {
            ++bom[part];
        }
        if (!catalog.hasSource(reference) || !catalog.hasSource(declared)) {
            add(findings, "compatibility", "CABLE_REFERENCE", id, unknown, "Référence de cordon sans preuve applicable");
        } else if (!sameReference(reference, declared)) {
            add(findings, "compatibility", "CABLE_REFERENCE", id, fail, "Référence de cordon différente du catalogue");
        }
        const auto specifications = selection.value("specifications").toObject();
        const QList<QPair<QString, QString>> quantities{{"outer_diameter_mm", "mm"}, {"min_static_radius_mm", "mm"},
            {"min_dynamic_radius_mm", "mm"}, {"length_mm", "mm"}, {"current_A", "A"},
            {"temperature_min_C", "degC"}, {"temperature_max_C", "degC"}, {"shield", "1"}};
        for (const auto &quantity : quantities) {
            const auto value = cable.contains(quantity.first) ? cable.value(quantity.first).toObject()
                                                              : specifications.value(quantity.first).toObject();
            if (!catalog.hasSource(value) || value.value("unit") != quantity.second) {
                add(findings, "compatibility", "CABLE_SPECIFICATION", id, unknown, "Propriété non établie " + quantity.first);
            } else if ((quantity.second == "mm" || quantity.second == "A") && value.value("value").toDouble() <= 0) {
                add(findings, "compatibility", "CABLE_SPECIFICATION", id, fail, "Propriété non positive " + quantity.first);
            }
        }
        const auto current = specifications.value("current_A").toObject();
        const auto minimum = specifications.value("temperature_min_C").toObject();
        const auto maximum = specifications.value("temperature_max_C").toObject();
        if (catalog.hasSource(minimum) && catalog.hasSource(maximum) &&
            (!minimum.value("value").isDouble() || !maximum.value("value").isDouble() ||
             minimum.value("value").toDouble() > maximum.value("value").toDouble())) {
            add(findings, "compatibility", "CABLE_TEMPERATURE", id, fail, "Plage de température inversée ou invalide");
        }
        for (const auto &entry : dossier.value("interfaces").toArray()) {
            const auto interface = entry.toObject();
            const auto demand = interface.value("requirements").toObject().value("current_A").toObject();
            if (interface.value("cable_id") == id && catalog.hasSource(current) && catalog.hasSource(demand) &&
                current.value("value").toDouble(-1) < demand.value("value").toDouble(-1)) {
                add(findings, "compatibility", "CABLE_CURRENT", id, fail, "Courant requis supérieur à la limite du cordon");
            }
        }
    }
}

void checkSignalGroups(const QJsonObject &dossier, const Model &model, Findings &findings)
{
    QSet<QString> covered;
    for (const auto &group : index(dossier.value("signal_groups"), "signal_groups")) {
        const auto id = group.value("id").toString();
        const auto kind = group.value("kind");
        const auto circuits = ids(group.value("circuit_ids").toArray());
        int signalCount = 0, shieldCount = 0;
        bool consistent = !circuits.isEmpty();
        for (const auto &circuitId : circuits) {
            const auto circuit = model.circuits.value(circuitId);
            consistent &= !covered.contains(circuitId) && circuit.value("group_id") == id;
            covered.insert(circuitId);
            signalCount += circuit.value("kind") == "SIGNAL";
            shieldCount += circuit.value("kind") == "SHIELD";
        }
        const bool differential = kind == "DIFFERENTIAL" && circuits.size() == 2 && signalCount == 2;
        const bool shape = differential ||
            (kind == "COAX" && circuits.size() == 2 && signalCount == 1 && shieldCount == 1) || kind == "MULTIDROP";
        add(findings, "electrical", "SIGNAL_GROUP", id, consistent && shape ? pass : fail,
            consistent && shape ? "Circuits distincts dans le groupe déclaré" : "Groupe électrique ou affectation des circuits incohérent");
        if (consistent && differential) {
            auto member = circuits.cbegin();
            const auto first = model.circuits.value(*member++);
            const auto second = model.circuits.value(*member);
            const auto checkPolarity = [&](const QJsonObject &circuit, const QJsonObject &opposite) {
                const auto name = opposite.value("function").toString();
                if (name.isEmpty() || name == circuit.value("function").toString()) {
                    return;
                }
                for (const auto &pinId : circuit.value("pin_ids").toArray()) {
                    if (model.pins.value(pinId.toString()).value("signal") == name) {
                        add(findings, "electrical", "SIGNAL_POLARITY", pinId.toString(), fail,
                            "Broche désignée par le signal de l’autre potentiel de la paire");
                    }
                }
            };
            checkPolarity(first, second);
            checkPolarity(second, first);
        }
    }
    for (const auto &circuit : model.circuits) {
        const auto id = circuit.value("id").toString();
        if (circuit.value("group_id").isString() && !covered.contains(id)) {
            add(findings, "electrical", "SIGNAL_GROUP", id, unknown, "Groupe fonctionnel sans définition de topologie");
        }
    }
}

QString verdict(const Findings &findings, const QString &domain = {})
{
    QString result = pass;
    for (const auto &finding : findings) {
        if (!domain.isEmpty() && finding.domain != domain) {
            continue;
        }
        if (finding.status == fail) {
            return fail;
        }
        if (finding.status == unknown) {
            result = unknown;
        }
    }
    return result;
}

} // namespace

QJsonObject Finding::json() const
{
    return {{"domain", domain}, {"code", code}, {"subject_id", subject}, {"status", status}, {"reason", reason}};
}

QJsonObject validate(const QJsonObject &dossier, const QString &stateId, const QJsonArray &researchReports)
{
    const auto model = dossier.value("model").toObject();
    const auto config = model.value("configuration_id").toString();
    const bool synthetic = dossier.value("mode") == "SYNTHETIC_BENCH";
    if (dossier.value("schema_version") != "1.0.0" || model.value("schema_version") != "2.0.0" || config.isEmpty() ||
        (synthetic && model.value("scope") != "SYNTHETIC") ||
        (!synthetic && (dossier.value("mode") != "PROTOTYPE_CANDIDATE" || model.value("scope") != "CARTOGRAPHE"))) {
        throw std::runtime_error("Version, configuration ou mode L2 inconnu");
    }
    const auto records = readModel(model.value("records").toObject());
    const auto states = index(model.value("states"), "states");
    if (!states.contains(stateId)) {
        throw std::runtime_error("État de contrôle inconnu");
    }
    const ConnectorCatalog catalog(dossier, records.evidence, synthetic);
    Findings findings;
    ContactBindings bindings;
    QMap<QString, int> bom;
    const auto research = summarizeResearch(dossier, researchReports, findings);
    const auto interfaces = bindInterfaces(dossier, records, catalog, bindings, bom, findings, synthetic);
    if (records.cables.isEmpty() || interfaces.isEmpty()) {
        add(findings, "electrical", "CHAIN_COVERAGE", config, unknown, "Chaîne complète absente");
        add(findings, "compatibility", "CHAIN_COVERAGE", config, unknown, "Accouplement complet absent");
    }
    checkPinMapping(records, bindings, catalog, findings, synthetic);
    checkSignalGroups(dossier, records, findings);
    checkCables(dossier, records, catalog, bom, findings);
    const auto nativePlan = checkGeometry(dossier, states.value(stateId), interfaces, findings);
    QJsonArray continuity;
    for (const auto &circuit : records.circuits) {
        for (const auto &spanValue : circuit.value("spans").toArray()) {
            const auto span = spanValue.toObject();
            const auto cable = records.cables.value(span.value("cable_id").toString());
            for (const auto &item : cable.value("conductors").toArray()) {
                const auto conductor = item.toObject();
                if (conductor.value("id") != span.value("conductor_id")) {
                    continue;
                }
                QJsonArray endpoints;
                for (const auto &id : conductor.value("terminal_ids").toArray()) {
                    const auto terminal = records.terminals.value(id.toString());
                    const auto plug = terminal.value("contact_id").toString();
                    const auto pin = records.pins.value(bindings.plugToPin.value(plug));
                    endpoints.append(QJsonObject{{"terminal_id", id}, {"kind", terminal.value("kind")},
                        {"mate_contact_id", terminal.value("contact_id")},
                        {"receptacle_contact_id", bindings.plugToReceptacle.value(plug)},
                        {"pin_id", pin.value("id")}, {"port_id", pin.value("port_id")},
                        {"signal", pin.value("signal")}});
                }
                continuity.append(QJsonObject{{"circuit_id", circuit.value("id")}, {"cable_id", span.value("cable_id")},
                    {"conductor_id", conductor.value("id")}, {"endpoints", endpoints}});
            }
        }
    }
    QJsonArray evidence;
    for (const auto &finding : findings) {
        evidence.append(finding.json());
    }
    return {{"schema_version", "1.0.0"}, {"configuration_id", config}, {"state_id", stateId},
        {"mode", dossier.value("mode")}, {"status", verdict(findings)}, {"electrical", verdict(findings, "electrical")},
        {"compatibility", verdict(findings, "compatibility")}, {"geometry", verdict(findings, "geometry")},
        {"findings", evidence}, {"continuity", continuity}, {"candidate_bom", catalog.bom(bom)},
        {"research", research}, {"native_plan", nativePlan}};
}

} // namespace interconnection
