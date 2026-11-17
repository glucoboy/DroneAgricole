#include "XLinkElectrical.hpp"

#include <QJsonArray>
#include <QMap>
#include <QSet>
#include <QStringList>

#include <cmath>
#include <stdexcept>

namespace electromechanical_validation {
namespace {

const QString pass = QStringLiteral("PASS");
const QString fail = QStringLiteral("FAIL");
const QString inconclusive = QStringLiteral("INCONCLUSIVE");
const QString notRun = QStringLiteral("NOT_RUN");
const QString onboard = QStringLiteral("faisceau_embarque");

void require(bool valid, const QString &reason)
{
    if (!valid)
        throw std::invalid_argument(reason.toStdString());
}

QSet<QString> uniqueIds(const QJsonArray &array, const QString &context)
{
    QSet<QString> result;
    for (const auto &value : array) {
        const auto id = value.toString();
        require(!id.isEmpty() && !result.contains(id), QStringLiteral("Identité absente ou dupliquée : ") + context);
        result.insert(id);
    }
    return result;
}

QString documentOf(const QString &object)
{
    const auto separator = object.lastIndexOf('#');
    return separator > 0 && separator + 1 < object.size() ? object.left(separator) : QString{};
}

QString documentHash(const QJsonValue &record)
{
    return record.isString() ? record.toString() : record.toObject().value("sha256").toString();
}

QJsonObject result(const QString &status, const QString &reason = {})
{
    return {{"status", status}, {"reason", reason}};
}

struct Resolution {
    QString id;
    QStringList candidates;
    QJsonObject record;
    QString status = inconclusive;
    QString reason;
};

struct NativeIndex {
    QJsonObject occurrences;
    QJsonObject documents;
    QMap<QString, QStringList> byObject;

    explicit NativeIndex(const QJsonObject &inventory)
        : occurrences(inventory.value("occurrences").toObject()), documents(inventory.value("documents").toObject())
    {
        for (auto it = occurrences.begin(); it != occurrences.end(); ++it) {
            const auto object = it.value().toObject().value("object").toString();
            if (!object.isEmpty())
                byObject[object].append(it.key());
        }
    }

    Resolution resolve(const QString &object, const QString &explicitId = {}, const QString &ancestor = {}) const
    {
        Resolution out;
        if (documentOf(object).isEmpty()) {
            out.reason = QStringLiteral("Sélecteur natif absent ou sans document et nom interne");
            return out;
        }
        for (const auto &id : byObject.value(object)) {
            if ((!explicitId.isEmpty() && explicitId != id) ||
                (!ancestor.isEmpty() && !id.startsWith(ancestor + '/')))
                continue;
            out.candidates.append(id);
        }
        if (out.candidates.size() != 1) {
            out.reason = out.candidates.isEmpty() ? QStringLiteral("Occurrence absente du natif rouvert")
                                                   : QStringLiteral("Sélecteur natif ambigu dans la fermeture");
            return out;
        }
        out.id = out.candidates.constFirst();
        out.record = occurrences.value(out.id).toObject();
        const auto occurrenceState = out.record.value("status").toString();
        if (occurrenceState != pass) {
            out.status = occurrenceState == fail ? fail : inconclusive;
            out.reason = QStringLiteral("L’état natif de l’occurrence n’est pas résolu");
            return out;
        }
        const auto definition = documentOf(out.record.value("definition").toString());
        const auto objectHash = documentHash(documents.value(documentOf(object)));
        const auto definitionHash = documentHash(documents.value(definition));
        const auto matrix = out.record.value("matrix").toArray();
        if (objectHash.isEmpty() || definitionHash.isEmpty() || matrix.size() != 16) {
            out.reason = QStringLiteral("Version de document ou matrice native absente");
            return out;
        }
        if (out.record.value("document_sha256") != objectHash ||
            out.record.value("definition_sha256") != definitionHash) {
            out.status = fail;
            out.reason = QStringLiteral("Empreinte de l’occurrence divergente de la fermeture rouverte");
            return out;
        }
        for (const auto &value : matrix) {
            if (!value.isDouble() || !std::isfinite(value.toDouble())) {
                out.reason = QStringLiteral("Matrice native non finie");
                return out;
            }
        }
        out.status = pass;
        return out;
    }
};

QJsonObject observedResolution(const Resolution &resolution, const QString &selector)
{
    auto report = result(resolution.status, resolution.reason);
    report.insert("selector", selector);
    report.insert("candidate_occurrences", QJsonArray::fromStringList(resolution.candidates));
    report.insert("occurrence", resolution.id.isEmpty() ? QJsonValue(QJsonValue::Null) : QJsonValue(resolution.id));
    if (!resolution.record.isEmpty()) {
        QJsonObject observation;
        for (const auto field : {"object", "definition", "label", "matrix", "document_sha256", "definition_sha256"})
            observation.insert(field, resolution.record.value(field));
        report.insert("observed", observation);
    }
    return report;
}

QString matchingFile(const QString &path, const QJsonObject &files)
{
    QString result;
    for (auto it = files.constBegin(); it != files.constEnd(); ++it) {
        const auto &file = it.key();
        if (path == file || path.endsWith('/' + file)) {
            require(result.isEmpty(), QStringLiteral("Chemin d’axe ambigu dans le manifeste : ") + path);
            result = file;
        }
    }
    return result;
}

bool samePort(const QString &selector, const QJsonObject &interface)
{
    const auto port = interface.value("functional_port").toString();
    if (port.isEmpty() || port.compare("unknown", Qt::CaseInsensitive) == 0 ||
        port.compare("inconnu", Qt::CaseInsensitive) == 0 || port == "?")
        return false;
    return selector == port || selector == interface.value("port_record_id").toString();
}

void appendReverse(QJsonObject &index, const QString &occurrence, const QJsonValue &entry)
{
    auto rows = index.value(occurrence).toArray();
    rows.append(entry);
    index.insert(occurrence, rows);
}

QString combine(const QString &left, const QString &right)
{
    if (left == fail || right == fail)
        return fail;
    return left == pass && right == pass ? pass : inconclusive;
}

} // namespace

QJsonObject joinXLinkElectrical(const QJsonObject &graph, const QJsonObject &mapping,
                              const QJsonObject &inventory, const QJsonObject &sourceHashes)
{
    require(graph.value("schema") == "drone-agricole.l2.cartographe-interfaces.v1", QStringLiteral("Graphe L2 incompatible"));
    require(graph.value("interfaces").isObject() && graph.value("lines").isArray() && !graph.value("lines").toArray().isEmpty() &&
            graph.value("line_interfaces").isObject() && graph.value("axes").isObject(),
            QStringLiteral("Graphe L2 incomplet"));
    require(mapping.value("equipment").isObject() &&
            (!mapping.contains("contacts") || mapping.value("contacts").isObject()),
            QStringLiteral("Plan d’occurrences ou de contacts incomplet"));
    const auto interfaces = graph.value("interfaces").toObject();
    const auto lineInterfaces = graph.value("line_interfaces").toObject();
    const auto axes = graph.value("axes").toObject();
    const auto equipmentMapping = mapping.value("equipment").toObject();
    const auto contactMapping = mapping.value("contacts").toObject();
    const auto sourceRoot = mapping.value("native_root").toString();
    const auto savedRoot = inventory.value("root").toString();
    const NativeIndex native(inventory);
    QMap<QString, QSet<QString>> axisLines;
    QJsonObject lineReports, interfaceReports, axisReports;
    QJsonObject reverseEquipment, reverseContacts, reverseAxes;
    QSet<QString> seenInterfaces, observedAxisObjects, boundAxisOccurrences;
    qsizetype onboardSides = 0, equipmentBound = 0, onboardEquipmentBound = 0;
    qsizetype contactsDeclared = 0, contactsChecked = 0, contactsBound = 0, sidesWithoutContacts = 0;
    qsizetype offAxis = 0, associations = 0, axesBound = 0;
    QString verdict = pass;

    for (const auto &value : graph.value("lines").toArray()) {
        const auto line = value.toObject();
        const auto lineId = line.value("id").toString();
        const auto scope = line.value("scope").toString();
        const auto path = line.value("path").toArray();
        const auto reason = line.value("scope_reason").toString();
        const bool hasAxes = scope == onboard;
        require(!lineId.isEmpty() && !scope.isEmpty() && !lineReports.contains(lineId) && line.value("path").isArray() &&
                hasAxes == !path.isEmpty() && (hasAxes || !reason.isEmpty()),
                QStringLiteral("Ligne L2 dupliquée ou périmètre CAO incohérent : ") + lineId);
        offAxis += !hasAxes;
        for (const auto &value : path) {
            const auto segment = value.toObject();
            const auto axisId = segment.value("route_id").toString();
            const auto sense = segment.value("sense").toString();
            require(axes.contains(axisId) && !axisLines[axisId].contains(lineId) && (sense == "direct" || sense == "inverse"),
                    QStringLiteral("Association axe/ligne invalide : ") + lineId + '/' + axisId);
            axisLines[axisId].insert(lineId);
            ++associations;
        }
        const QJsonArray sides{lineId + "/A", lineId + "/B"};
        require(uniqueIds(lineInterfaces.value(lineId).toArray(), lineId) == uniqueIds(sides, lineId),
                QStringLiteral("Couverture des deux extrémités divergente : ") + lineId);
        auto lineReport = result(hasAxes ? pass : notRun, reason);
        lineReport.insert("scope", scope);
        lineReport.insert("class", line.value("class"));
        lineReport.insert("path", path);
        lineReport.insert("interfaces", sides);
        for (const auto &value : sides) {
            const auto key = value.toString();
            const auto interface = interfaces.value(key).toObject();
            require(!seenInterfaces.contains(key) && interface.value("line_id") == lineId &&
                    interface.value("side") == key.right(1) && !interface.value("port_record_id").toString().isEmpty(),
                    QStringLiteral("Extrémité L2 invalide : ") + key);
            seenInterfaces.insert(key);
            onboardSides += hasAxes;
            require(!equipmentMapping.contains(key) || equipmentMapping.value(key).isObject(),
                    QStringLiteral("Sélecteur d’équipement invalide : ") + key);
            const auto equipmentSpec = equipmentMapping.value(key).toObject();
            const auto equipmentSelector = equipmentSpec.value("object").toString();
            const auto equipment = native.resolve(equipmentSelector, equipmentSpec.value("occurrence").toString());
            auto equipmentReport = observedResolution(equipment, equipmentSelector);
            equipmentReport.insert("source", equipmentSpec.value("source"));
            if (equipment.status == pass) {
                ++equipmentBound;
                onboardEquipmentBound += hasAxes;
                appendReverse(reverseEquipment, equipment.id, key);
            }

            QJsonArray contactReports;
            QSet<QString> seenContacts, seenContactOccurrences;
            require(!contactMapping.contains(key) || contactMapping.value(key).isArray(),
                    QStringLiteral("Sélecteurs de contacts invalides : ") + key);
            const auto expectedContacts = contactMapping.value(key).toArray();
            QString contactsStatus = expectedContacts.isEmpty() ? inconclusive : pass;
            sidesWithoutContacts += hasAxes && expectedContacts.isEmpty();
            for (const auto &expected : expectedContacts) {
                ++contactsDeclared;
                const auto spec = expected.toObject();
                const auto contactId = spec.value("id").toString();
                const auto selector = spec.value("object").toString();
                const auto port = spec.value("port").toString();
                require(!contactId.isEmpty() && !seenContacts.contains(contactId),
                        QStringLiteral("Contact déclaré sans identité unique : ") + key);
                seenContacts.insert(contactId);
                const auto terminal = native.resolve(selector, spec.value("occurrence").toString());
                auto report = observedResolution(terminal, selector);
                report.insert("contact", contactId);
                report.insert("port", port);
                report.insert("source", spec.value("source"));
                QString status = combine(equipment.status, terminal.status);
                QString diagnosis = status == pass ? QString{} : QStringLiteral("Équipement ou terminal natif non résolu");
                if (status == pass) {
                    ++contactsChecked;
                    const auto observed = terminal.record.value("contact").toObject();
                    if (!samePort(port, interface) || observed.value("id").toString().isEmpty() ||
                        observed.value("port").toString().isEmpty() || observed.value("equipment_occurrence").toString().isEmpty()) {
                        status = inconclusive;
                        diagnosis = QStringLiteral("Port ou preuve native de rattachement du contact absent");
                    } else if (observed.value("id") != contactId || !samePort(observed.value("port").toString(), interface) ||
                               observed.value("equipment_occurrence") != equipment.id || seenContactOccurrences.contains(terminal.id)) {
                        status = fail;
                        diagnosis = QStringLiteral("Identité, port ou rattachement du contact natif divergent");
                    } else {
                        ++contactsBound;
                        seenContactOccurrences.insert(terminal.id);
                        appendReverse(reverseContacts, terminal.id, QJsonObject{{"interface", key}, {"contact", contactId}});
                    }
                    report.insert("native_contact", observed);
                }
                report.insert("status", status);
                report.insert("reason", diagnosis);
                contactReports.append(report);
                contactsStatus = combine(contactsStatus, status);
            }
            const auto interfaceStatus = combine(equipment.status, contactsStatus);
            auto portReport = result(interfaceStatus, expectedContacts.isEmpty()
                    ? QStringLiteral("Aucun contact natif défini pour ce port par le référentiel") : QString{});
            portReport.insert("functional_port", interface.value("functional_port"));
            portReport.insert("port_record_id", interface.value("port_record_id"));
            interfaceReports.insert(key, QJsonObject{{"status", interfaceStatus}, {"scope", scope},
                {"equipment_id", interface.value("equipment_id")}, {"equipment", equipmentReport},
                {"port", portReport}, {"contacts", contactReports}, {"contacts_expected", expectedContacts.size()},
                {"contact_coverage_known", !expectedContacts.isEmpty()}, {"connector_record", interface.value("connector_record")}});
            if (hasAxes)
                lineReport.insert("status", combine(lineReport.value("status").toString(), interfaceStatus));
        }
        lineReports.insert(lineId, lineReport);
    }
    require(seenInterfaces.size() == interfaces.size() && lineReports.size() == lineInterfaces.size(),
            QStringLiteral("Extrémités ou index de lignes L2 orphelins"));
    for (const auto &key : equipmentMapping.keys() + contactMapping.keys())
        require(seenInterfaces.contains(key), QStringLiteral("Sélecteur sans interface L2 : ") + key);

    for (auto it = axes.constBegin(); it != axes.constEnd(); ++it) {
        const auto axisId = it.key();
        const auto axis = it.value().toObject();
        const auto associatedLines = axis.value("line_ids").toArray();
        require(!associatedLines.isEmpty() && uniqueIds(associatedLines, axisId) == axisLines.value(axisId),
                QStringLiteral("Couverture inverse axe/ligne divergente : ") + axisId);
        const auto file = axis.value("native_file").toObject();
        const auto sourcePath = file.value("path").toString();
        const auto source = matchingFile(sourcePath, sourceHashes);
        const auto observed = matchingFile(source, native.documents);
        const auto selector = axis.value("assembly_occurrence").toString();
        const auto occurrence = native.resolve(selector);
        const auto nativeObject = observed + '#' + axis.value("native_object").toString();
        const auto route = occurrence.record.value("route");
        const auto routeObject = route.isString() ? route.toString() : route.toObject().value("object").toString();
        auto status = occurrence.status;
        auto diagnosis = occurrence.reason;
        if (!sourceRoot.isEmpty() && !sourcePath.startsWith(sourceRoot + '/')) {
            status = fail;
            diagnosis = QStringLiteral("Le graphe indépendant désigne un autre périmètre source");
        } else if (source.isEmpty()) {
            status = inconclusive;
            diagnosis = QStringLiteral("Aucun fichier d’axe dans la fermeture source");
        } else if (file.value("sha256").toString().isEmpty() || documentHash(sourceHashes.value(source)) != file.value("sha256").toString()) {
            status = fail;
            diagnosis = QStringLiteral("Empreinte source de l’axe différente du graphe indépendant");
        } else if (status == pass && (observed.isEmpty() || documentOf(occurrence.record.value("definition").toString()) != observed)) {
            status = fail;
            diagnosis = QStringLiteral("L’occurrence d’axe pointe vers un autre document natif");
        } else if (status == pass && observed != savedRoot && documentHash(native.documents.value(observed)) != file.value("sha256").toString()) {
            status = fail;
            diagnosis = QStringLiteral("L’axe de la copie rouverte ne conserve pas l’empreinte de la dépendance source");
        }
        Resolution cable;
        if (status == pass) {
            cable = native.resolve(nativeObject, {}, occurrence.id);
            const bool observedAtLink = occurrence.record.value("definition") == nativeObject || routeObject == nativeObject;
            if ((!observedAtLink || !cable.candidates.isEmpty()) && cable.status != pass) {
                status = cable.status;
                diagnosis = QStringLiteral("Le câble attendu n’est pas résolu sous cette occurrence d’axe");
            } else if (boundAxisOccurrences.contains(occurrence.id)) {
                status = fail;
                diagnosis = QStringLiteral("Plusieurs axes documentaires revendiquent la même occurrence");
            } else {
                ++axesBound;
                boundAxisOccurrences.insert(occurrence.id);
                observedAxisObjects.insert(cable.id.isEmpty() ? occurrence.id : cable.id);
                reverseAxes.insert(occurrence.id, QJsonObject{{"axis", axisId}, {"line_ids", associatedLines}});
            }
        }
        auto report = result(status, diagnosis);
        report.insert("declared_native_file", file);
        report.insert("line_ids", associatedLines);
        report.insert("occurrence", observedResolution(occurrence, selector));
        report.insert("cable", observedResolution(cable.id.isEmpty() && status == pass ? occurrence : cable, nativeObject));
        axisReports.insert(axisId, report);
        for (const auto &line : associatedLines) {
            const auto id = line.toString();
            auto row = lineReports.value(id).toObject();
            row.insert("status", combine(row.value("status").toString(), status));
            lineReports.insert(id, row);
        }
        verdict = combine(verdict, status);
    }
    QJsonArray unmatchedRoutes;
    for (auto it = native.occurrences.constBegin(); it != native.occurrences.constEnd(); ++it) {
        const auto record = it.value().toObject();
        const auto route = record.value("route");
        const auto routeObject = route.isString() ? route.toString() : route.toObject().value("object").toString();
        if (!routeObject.isEmpty() && routeObject == record.value("definition") && !observedAxisObjects.contains(it.key()))
            unmatchedRoutes.append(QJsonObject{{"occurrence", it.key()}, {"status", inconclusive},
                {"reason", QStringLiteral("Occurrence de câble native sans association dans le graphe indépendant")}});
    }
    if (!unmatchedRoutes.isEmpty())
        verdict = combine(verdict, inconclusive);
    for (auto it = lineReports.constBegin(); it != lineReports.constEnd(); ++it) {
        const auto status = it.value().toObject().value("status").toString();
        if (status != notRun)
            verdict = combine(verdict, status);
    }
    return {{"schema", "drone-agricole.v21.xlink-electrical.v1"}, {"status", verdict},
        {"summary", QJsonObject{{"lines", lineReports.size()}, {"off_axis_lines", offAxis}, {"interfaces", seenInterfaces.size()},
            {"onboard_interfaces", onboardSides}, {"equipment_bound", equipmentBound}, {"onboard_equipment_bound", onboardEquipmentBound},
            {"onboard_sides_without_contact_definition", sidesWithoutContacts}, {"contacts_expected", contactsDeclared},
            {"contacts_examined", contactsChecked}, {"contacts_bound", contactsBound}, {"line_axis_associations", associations},
            {"axes_expected", axes.size()}, {"axes_bound", axesBound}, {"native_routes_without_electrical_axis", unmatchedRoutes.size()}}},
        {"lines", lineReports}, {"interfaces", interfaceReports}, {"axes", axisReports}, {"unmatched_native_routes", unmatchedRoutes},
        {"reverse", QJsonObject{{"equipment", reverseEquipment}, {"contacts", reverseContacts}, {"axes", reverseAxes}}}};
}

} // namespace electromechanical_validation
