#include "XLinkElectrical.hpp"

#include <QJsonArray>
#include <QTextStream>

#include <stdexcept>

namespace {

using electromechanical_validation::joinXLinkElectrical;

const QString root = QStringLiteral("root.FCStd#Assembly/");
const QString instanceA = root + "MountA/Device";
const QString instanceB = root + "MountB/Device";
const QString contactA = root + "MountA/Device/Terminal";
const QString contactB = root + "MountB/Device/Terminal";
const QString axis = root + "CableLink";

QJsonObject graph()
{
    const auto end = [](const QString &line, const QString &side) {
        return QJsonObject{{"line_id", line}, {"side", side}, {"equipment_id", "Equipment-" + side},
                           {"port_record_id", line + '-' + side}, {"functional_port", "Port-" + side}};
    };
    return {{"schema", "drone-agricole.l2.cartographe-interfaces.v1"},
        {"interfaces", QJsonObject{{"W01/A", end("W01", "A")}, {"W01/B", end("W01", "B")},
                                  {"RF/A", end("RF", "A")}, {"RF/B", end("RF", "B")}}},
        {"line_interfaces", QJsonObject{{"W01", QJsonArray{"W01/A", "W01/B"}}, {"RF", QJsonArray{"RF/A", "RF/B"}}}},
        {"lines", QJsonArray{QJsonObject{{"id", "W01"}, {"scope", "faisceau_embarque"},
                                        {"path", QJsonArray{QJsonObject{{"route_id", "F01"}, {"sense", "inverse"}}}}},
                             QJsonObject{{"id", "RF"}, {"scope", "sans_fil"}, {"path", QJsonArray{}},
                                         {"scope_reason", "Liaison radio"}}}},
        {"axes", QJsonObject{{"F01", QJsonObject{{"assembly_occurrence", "root.FCStd#CableLink"},
            {"native_file", QJsonObject{{"path", "prototype/parts/cable.FCStd"}, {"sha256", "cable-v1"}}},
            {"native_object", "Cable"}, {"line_ids", QJsonArray{"W01"}}}}}}};
}

QJsonObject mapping(const QString &selected = instanceA)
{
    const auto terminal = [](const QString &occurrence, const QString &port) {
        return QJsonArray{QJsonObject{{"id", "pin1"}, {"object", "parts/device.FCStd#Terminal"},
                                     {"port", port}, {"occurrence", occurrence}}};
    };
    return {{"native_root", "prototype"}, {"equipment", QJsonObject{
                {"W01/A", QJsonObject{{"object", "parts/device.FCStd#Device"}, {"occurrence", selected}}},
                {"W01/B", QJsonObject{{"object", "parts/device.FCStd#Device"}, {"occurrence", instanceB}}}}},
            {"contacts", QJsonObject{{"W01/A", terminal(contactA, "W01-A")}, {"W01/B", terminal(contactB, "W01-B")}}}};
}

QJsonObject occurrence(const QString &object, const QString &definition, const QString &objectHash,
                       const QString &definitionHash, double x)
{
    return {{"status", "PASS"}, {"object", object}, {"definition", definition}, {"label", "common-label"},
        {"document_sha256", objectHash}, {"definition_sha256", definitionHash},
        {"matrix", QJsonArray{1, 0, 0, x, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1}}};
}

QJsonObject inventory(const QString &secondPort = QStringLiteral("Port-B"))
{
    const auto device = [](double x) {
        return occurrence("parts/device.FCStd#Device", "parts/device.FCStd#Device", "device-v1", "device-v1", x);
    };
    const auto terminal = [](double x, const QString &equipment, const QString &port) {
        auto object = occurrence("parts/device.FCStd#Terminal", "parts/device.FCStd#Terminal", "device-v1", "device-v1", x);
        object.insert("contact", QJsonObject{{"id", "pin1"}, {"port", port}, {"equipment_occurrence", equipment}});
        return object;
    };
    auto cable = occurrence("parts/cable.FCStd#Cable", "parts/cable.FCStd#Cable", "cable-v1", "cable-v1", 10);
    cable.insert("route", QJsonObject{{"object", "parts/cable.FCStd#Cable"}});
    return {{"root", "root.FCStd"}, {"documents", QJsonObject{{"root.FCStd", "root-copy"}, {"parts/cable.FCStd", "cable-v1"},
                                      {"parts/device.FCStd", "device-v1"}}},
        {"occurrences", QJsonObject{{instanceA, device(10)}, {instanceB, device(40)},
            {contactA, terminal(10, instanceA, "Port-A")}, {contactB, terminal(40, instanceB, secondPort)},
            {axis, occurrence("root.FCStd#CableLink", "parts/cable.FCStd#Ensemble", "root-copy", "cable-v1", 10)},
            {axis + "/Cable", cable}}}};
}

const QJsonObject sourceHashes{{"root.FCStd", "root-source"}, {"parts/cable.FCStd", "cable-v1"},
                              {"parts/device.FCStd", "device-v1"}};

void expect(bool condition, const QString &message, int &failures)
{
    if (!condition) {
        QTextStream(stderr) << message << '\n';
        ++failures;
    }
}

QJsonObject entry(const QJsonObject &report, const QString &section, const QString &key)
{
    return report.value(section).toObject().value(key).toObject();
}

}

int main()
{
    int failures = 0;
    const auto nominal = joinXLinkElectrical(graph(), mapping(), inventory(), sourceHashes);
    const auto sideA = entry(nominal, "interfaces", "W01/A").value("equipment").toObject();
    const auto sideB = entry(nominal, "interfaces", "W01/B").value("equipment").toObject();
    expect(nominal.value("status") == "PASS" && sideA.value("occurrence") == instanceA && sideB.value("occurrence") == instanceB,
           "Deux instances du même document et du même nom restent distinctes", failures);
    expect(entry(nominal, "lines", "RF").value("status") == "NOT_RUN" &&
           entry(nominal, "lines", "RF").value("reason") == "Liaison radio",
           "Le périmètre hors axe conserve le motif sans PASS", failures);
    const auto reverse = nominal.value("reverse").toObject();
    expect(reverse.value("contacts").toObject().size() == 2 && reverse.value("axes").toObject().contains(axis),
           "La jointure inverse conserve contacts et axes", failures);

    const auto ambiguous = joinXLinkElectrical(graph(), mapping(QString{}), inventory(), sourceHashes);
    expect(ambiguous.value("status") == "INCONCLUSIVE" &&
           entry(ambiguous, "interfaces", "W01/A").value("equipment").toObject().value("candidate_occurrences").toArray().size() == 2,
           "Une occurrence répétée sans chemin explicite reste ambiguë", failures);
    const auto wrongContact = joinXLinkElectrical(graph(), mapping(), inventory("wrong-port"), sourceHashes);
    expect(wrongContact.value("status") == "FAIL" && entry(wrongContact, "interfaces", "W01/B").value("status") == "FAIL",
           "Le port natif divergent est détecté", failures);
    auto unknownPort = graph();
    auto interfaces = unknownPort.value("interfaces").toObject();
    auto side = interfaces.value("W01/B").toObject();
    side.insert("functional_port", "UNKNOWN");
    interfaces.insert("W01/B", side);
    unknownPort.insert("interfaces", interfaces);
    const auto unresolved = joinXLinkElectrical(unknownPort, mapping(), inventory(), sourceHashes);
    expect(unresolved.value("status") == "INCONCLUSIVE" && entry(unresolved, "interfaces", "W01/B").value("status") == "INCONCLUSIVE",
           "Un identifiant d'enregistrement ne remplace pas un port inconnu", failures);

    auto changedHashes = sourceHashes;
    changedHashes.insert("parts/cable.FCStd", "cable-v2");
    const auto stale = joinXLinkElectrical(graph(), mapping(), inventory(), changedHashes);
    expect(stale.value("status") == "FAIL" && entry(stale, "axes", "F01").value("status") == "FAIL",
           "Une dépendance décalée réfute la jointure même avec la même racine", failures);
    auto otherCopy = mapping();
    otherCopy.insert("native_root", "another-copy");
    const auto mixed = joinXLinkElectrical(graph(), otherCopy, inventory(), sourceHashes);
    expect(mixed.value("status") == "FAIL" && entry(mixed, "axes", "F01").value("status") == "FAIL",
           "Une copie portant des dépendances identiques mais provenant d’un autre périmètre est détectée", failures);

    auto broken = inventory();
    auto occurrences = broken.value("occurrences").toObject();
    auto lost = occurrences.value(instanceB).toObject();
    lost.insert("status", "INCONCLUSIVE");
    lost.insert("definition", QJsonValue::Null);
    occurrences.insert(instanceB, lost);
    broken.insert("occurrences", occurrences);
    expect(joinXLinkElectrical(graph(), mapping(), broken, sourceHashes).value("status") == "INCONCLUSIVE",
           "Un lien rompu reste visible dans la jointure", failures);

    auto orphaned = graph();
    orphaned.insert("line_interfaces", QJsonObject{{"W01", QJsonArray{"W01/A", "W01/A"}}});
    bool rejected = false;
    try {
        joinXLinkElectrical(orphaned, mapping(), inventory(), sourceHashes);
    } catch (const std::invalid_argument &) {
        rejected = true;
    }
    expect(rejected, "Le graphe comportant un doublon d'extrémité est rejeté", failures);
    return failures == 0 ? 0 : 1;
}
