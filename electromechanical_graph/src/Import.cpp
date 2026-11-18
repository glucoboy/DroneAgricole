#include "Import.hpp"
#include "Graph.hpp"
#include "Reconcile.hpp"

#include <QCryptographicHash>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QJsonArray>
#include <QJsonDocument>
#include <QMap>
#include <QSet>
#include <QStringList>
#include <stdexcept>

namespace electromechanical::graph {
namespace {

const QString l2Model = "docs/verification/go3a/GO3A_SYSTEM_MODEL.json";
const QString inventory = "hardware/mecanique/cartographe/verification/refonte_faisceaux/inventaire.json";
const QString connectors = "docs/verification/v21_connector_inventory.csv";

void require(bool ok, const QString &message)
{
    if (!ok)
        throw std::runtime_error(message.toStdString());
}

QByteArray read(const QString &root, const QString &relative)
{
    const auto directory = QDir(root).canonicalPath();
    require(!directory.isEmpty() && !relative.isEmpty() && QDir::isRelativePath(relative)
            && relative == QDir::cleanPath(relative) && !relative.startsWith("../")
            && !relative.contains(':') && !relative.contains('\\'), "Chemin de source invalide : " + relative);
    const auto path = QFileInfo(QDir(directory).filePath(relative)).canonicalFilePath();
    require(path.startsWith(directory + '/'), "Source absente ou hors dépôt : " + relative);
    QFile file(path);
    require(file.open(QIODevice::ReadOnly), "Source illisible : " + relative);
    const auto bytes = file.readAll();
    require(file.error() == QFileDevice::NoError, "Lecture interrompue : " + relative);
    return bytes;
}

QString hash(const QByteArray &bytes)
{
    return QString::fromLatin1(QCryptographicHash::hash(bytes, QCryptographicHash::Sha256).toHex());
}

QJsonObject json(const QByteArray &bytes)
{
    QJsonParseError error;
    const auto document = QJsonDocument::fromJson(bytes, &error);
    require(error.error == QJsonParseError::NoError && document.isObject(), "Objet JSON attendu : " + error.errorString());
    return document.object();
}

QJsonObject proof(const QString &state, const QString &source, const QString &locator, const QString &scope,
                  const QString &reception = "INCONCLUSIVE", const QJsonValue &unit = QJsonValue::Null)
{
    return {{"state", state}, {"source", source}, {"locator", locator}, {"scope", scope},
            {"unit", unit}, {"reception", reception}};
}

QString documentOf(const QString &object)
{
    return object.section('#', 0, 0);
}

QStringList splitRow(const QString &row)
{
    QStringList fields;
    QString field;
    bool quoted = false;
    for (qsizetype i = 0; i < row.size(); ++i) {
        const auto ch = row.at(i);
        if (ch == '"' && quoted && i + 1 < row.size() && row.at(i + 1) == '"') {
            field += ch;
            ++i;
        } else if (ch == '"') {
            quoted = !quoted;
        } else if (ch == ',' && !quoted) {
            fields.append(field);
            field.clear();
        } else {
            field += ch;
        }
    }
    require(!quoted, "Ligne CSV de connectique non terminée");
    fields.append(field);
    return fields;
}

QMap<QString, QJsonObject> connectorRows(const QByteArray &content)
{
    auto rows = QString::fromUtf8(content).split('\n', Qt::SkipEmptyParts);
    require(!rows.isEmpty(), "Inventaire de connectique vide");
    const auto header = splitRow(rows.takeFirst().trimmed());
    require(header.contains("cle_interface"), "Inventaire de connectique incompatible");
    QMap<QString, QJsonObject> result;
    for (const auto &row : rows) {
        const auto fields = splitRow(row.endsWith('\r') ? row.chopped(1) : row);
        require(fields.size() == header.size(), "Longueur de ligne CSV incohérente");
        QJsonObject record;
        for (qsizetype i = 0; i < fields.size(); ++i) {
            if (!fields.at(i).isEmpty())
                record.insert(header.at(i), fields.at(i));
        }
        const auto key = record.value("cle_interface").toString();
        require(!key.isEmpty() && !result.contains(key), "Côté CSV absent ou dupliqué : " + key);
        result.insert(key, record);
    }
    return result;
}

class Projection {
public:
    explicit Projection(QString root) : root_(std::move(root)) {}

    QByteArray source(const QString &id, const QString &path, const QString &expected = {})
    {
        const auto bytes = read(root_, path);
        const auto digest = hash(bytes);
        require(expected.isEmpty() || digest == expected, "Empreinte divergente : " + path);
        const QJsonObject record{{"path", path}, {"sha256", digest}};
        require(!sources.contains(id) || sources.value(id) == record, "Source en conflit : " + id);
        sources.insert(id, record);
        return bytes;
    }

    void node(const QString &id, const QString &kind, const QJsonObject &evidence, const QJsonObject &occurrence = {})
    {
        require(!id.isEmpty() && !nodes.contains(id), "Nœud dupliqué ou vide : " + id);
        QJsonObject record{{"id", id}, {"kind", kind}, {"version", 1},
                           {"claims", QJsonArray{}}, {"evidence", evidence}};
        if (!occurrence.isEmpty())
            record.insert("occurrence", occurrence);
        nodes.insert(id, record);
    }

    void claims(const QString &id, const QJsonArray &additional)
    {
        require(nodes.contains(id), "Nœud absent : " + id);
        auto &record = nodes[id];
        auto claims = record.value("claims").toArray();
        for (const auto &claim : additional)
            claims.append(claim);
        record.insert("claims", claims);
    }

    void claim(const QString &id, const QString &key, const QJsonValue &value, const QJsonObject &evidence)
    {
        claims(id, QJsonArray{QJsonObject{{"key", key}, {"value", value}, {"evidence", evidence}}});
    }

    void edge(const QString &kind, const QString &from, const QString &to, const QString &direction,
              const QJsonObject &evidence, const QJsonObject &properties = {})
    {
        auto result = properties;
        result.insert("id", kind + ':' + from + "->" + to);
        result.insert("kind", kind);
        result.insert("from", from);
        result.insert("to", to);
        result.insert("impact", direction);
        result.insert("evidence", evidence);
        edges.append(result);
    }

    const QString root_;
    QJsonObject sources;
    QMap<QString, QJsonObject> nodes;
    QJsonArray edges;
    QJsonArray issues;
    QMap<QString, QString> nativeIds;
    QMap<QString, QStringList> bySelector;
    QJsonObject reconciliation;
};

QString uniqueOccurrence(const Projection &out, const QString &selector)
{
    const auto matches = out.bySelector.value(selector);
    require(matches.size() == 1, "Sélecteur natif absent ou ambigu : " + selector +
            " (" + QString::number(matches.size()) + ")");
    return matches.first();
}

void addNative(Projection &out, const QJsonObject &native, const QJsonObject &bindings)
{
    require(native.value("schema") == "v3.native/1", "Version d'inventaire XLink non prise en charge");
    require(native.value("finalized") == true && native.value("status") == "PASS" &&
            native.value("recompute_ok") == true && native.value("inventory_complete") == true &&
            native.value("save_performed") == false && native.value("before_sha256") == native.value("after_sha256")
            && native.value("transfer").toObject().value("status") == "PASS"
            && native.value("transfer").toObject().value("separate_processes") == true
            && native.value("broken_links") == QJsonArray{} && native.value("invalid_objects") == QJsonArray{}
            && native.value("broken_serialized_links") == QJsonArray{}
            && native.value("unavailable_definitions") == QJsonArray{},
            "Inventaire XLink incomplet");
    const auto prefix = native.value("source_prefix").toString();
    const auto documents = native.value("documents").toObject();
    const auto occurrences = native.value("occurrences").toObject();
    const auto boxes = native.value("boxes").toObject();
    require(!documents.isEmpty() && !occurrences.isEmpty(), "Inventaire XLink vide");
    for (auto it = documents.begin(); it != documents.end(); ++it) {
        const auto digest = it.value().toObject().value("sha256").toString();
        require(!digest.isEmpty(), "Document natif sans empreinte : " + it.key());
        const auto path = prefix.isEmpty() ? it.key() : prefix + '/' + it.key();
        out.source("native:" + it.key(), path, digest);
    }
    const auto inputs = native.value("before_sha256").toObject();
    for (auto it = inputs.begin(); it != inputs.end(); ++it) {
        if (!documents.contains(it.key())) {
            const auto path = prefix.isEmpty() ? it.key() : prefix + '/' + it.key();
            out.source("native:" + it.key(), path, it.value().toString());
        }
    }
    for (auto it = occurrences.begin(); it != occurrences.end(); ++it) {
        const auto record = it.value().toObject();
        const auto object = record.value("object").toString();
        const auto definition = record.value("definition").toString();
        require(!object.isEmpty() && !definition.isEmpty(),
                "Identité native non résolue : " + it.key());
        require(record.value("placement_check").toObject().value("status") == "PASS" &&
                record.value("status") == "PASS",
                "Placement XLink non résolu : " + it.key());
        out.bySelector[object].append(it.key());
        if (object != definition)
            out.bySelector[definition].append(it.key());
    }
    QMap<QString, QJsonObject> resolved;
    for (auto it = bindings.begin(); it != bindings.end(); ++it) {
        const auto key = occurrences.contains(it.key()) ? it.key() : uniqueOccurrence(out, it.key());
        require(!resolved.contains(key), "Double qualification d'occurrence : " + key);
        resolved.insert(key, it.value().toObject());
    }
    for (auto it = occurrences.begin(); it != occurrences.end(); ++it) {
        auto record = it.value().toObject();
        const auto binding = resolved.value(it.key());
        const auto id = binding.value("alias").toString("occ:" + it.key());
        const auto kind = binding.value("kind").toString("STRUCTURE");
        const auto source = "native:" + documentOf(record.value("object").toString());
        const auto definition = "native:" + documentOf(record.value("definition").toString());
        require(out.sources.contains(source) && out.sources.contains(definition),
                "Occurrence extérieure à la fermeture : " + it.key());
        record.insert("id", it.key());
        record.insert("object_source", source);
        record.insert("definition_source", definition);
        if (!record.contains("matrix"))
            record.insert("matrix", QJsonValue::Null);
        if (!record.contains("local_matrix"))
            record.insert("local_matrix", QJsonValue::Null);
        const bool resolvedPlacement = record.value("status") == "PASS" && !record.value("matrix").isNull();
        const auto evidence = proof("MEASURED", source, it.key(), "Géométrie et placement de la représentation CAO",
                                    resolvedPlacement ? "PASS" : "INCONCLUSIVE", "mm");
        out.node(id, kind, evidence, record);
        if (boxes.contains(it.key()))
            out.claim(id, "native_faces", boxes.value(it.key()),
                      proof("MEASURED", definition, record.value("definition").toString(),
                            "Faces indépendantes de la représentation, portée CAO", "PASS", "mm"));
        out.nativeIds.insert(it.key(), id);
        if (!resolvedPlacement)
            out.issues.append(QJsonObject{{"id", "placement:" + id}, {"severity", "OPEN"},
                {"subjects", QJsonArray{id}}, {"detail", "Placement ou géométrie native à instruire."},
                {"evidence", evidence}});
    }
    for (auto it = occurrences.begin(); it != occurrences.end(); ++it) {
        const auto parent = it.value().toObject().value("parent").toString();
        if (parent.isEmpty())
            continue;
        require(out.nativeIds.contains(parent), "Parent d'occurrence absent : " + parent);
        const auto id = out.nativeIds.value(it.key());
        out.edge("TRANSFORMS", out.nativeIds.value(parent), id, "FORWARD",
                 out.nodes.value(id).value("evidence").toObject());
    }
}

void addL2(Projection &out, const QJsonObject &native)
{
    const auto l2 = interconnection::inspectCartographeInterfacesV3(out.root_);
    require(l2.value("schema") == "drone-agricole.l2.cartographe-interfaces.v1", "Contrat L2 non migrable");
    const auto sourceHashes = l2.value("source_sha256").toObject();
    for (auto it = sourceHashes.begin(); it != sourceHashes.end(); ++it)
        out.source(it.key(), it.key(), it.value().toString());
    const auto model = json(out.source(l2Model, l2Model));
    require(model.value("version") == 1, "Version du modèle système incompatible");
    const auto csv = connectorRows(out.source(connectors, connectors));
    const auto interfaces = l2.value("interfaces").toObject();
    const auto nativeOccurrences = native.value("occurrences").toObject();
    const auto axisMeasurements = native.value("axes").toObject();
    QMap<QString, QJsonObject> axisDefinitions;
    for (const auto &entry : model.value("axes_cao").toArray())
        axisDefinitions.insert(entry.toObject().value("id").toString(), entry.toObject());

    const auto axes = l2.value("axes").toObject();
    for (auto it = axes.begin(); it != axes.end(); ++it) {
        const auto row = it.value().toObject();
        const auto selector = row.value("assembly_occurrence").toString();
        const auto occurrence = uniqueOccurrence(out, selector);
        const auto representation = nativeOccurrences.value(occurrence).toObject();
        const auto expected = row.value("native_file").toObject();
        const auto def = representation.value("definition").toString();
        require(native.value("source_prefix").toString() + '/' + documentOf(def) == expected.value("path") &&
                out.sources.value("native:" + documentOf(def)).toObject().value("sha256") == expected.value("sha256"),
                "Axe natif différent de la définition L2 : " + it.key());
        const auto id = "axis:" + it.key();
        const auto evidence = proof("DOCUMENTED", l2Model, "/axes_cao/" + it.key(), "Association d'axe CAO et liaison L2");
        out.node(id, "HARNESS_SEGMENT", evidence);
        out.claim(id, "l2_axis", axisDefinitions.value(it.key()), evidence);
        out.claim(id, "native_occurrence", occurrence, evidence);
        QJsonObject positions;
        int matches = 0;
        for (auto m = axisMeasurements.begin(); m != axisMeasurements.end(); ++m) {
            if (m.key() != occurrence && !m.key().startsWith(occurrence + '/'))
                continue;
            const auto axisObject = nativeOccurrences.value(m.key()).toObject().value("definition").toString();
            if (axisObject == documentOf(def) + '#' + row.value("native_object").toString()) {
                positions = m.value().toObject();
                ++matches;
            }
        }
        require(matches == 1, "Objet Cables ambigu ou absent : " + it.key());
        require(positions.value("scope") == "AXIS_RESERVATION_ONLY" &&
                positions.value("endpoints_mm").toArray().size() == 2, "Géométrie d'axe non résolue : " + it.key());
        out.claim(id, "axis_reservation", positions,
                  proof("MEASURED", "native:" + documentOf(def), occurrence,
                        "Mesure de l'axe en CAO, aucune preuve de repère port", "PASS", "mm"));
        out.edge("ROUTING", out.nativeIds.value(occurrence), id, "FORWARD", evidence);
        out.claim(id, "dimensions_de_service", QJsonValue::Null,
                  proof("UNKNOWN", l2Model, "/axes_cao/" + it.key(), "Réserve utile, rayon dynamique et dimensions installées"));
    }
    for (const auto &entry : model.value("jonctions_documentaires").toArray()) {
        const auto row = entry.toObject();
        const auto key = row.value("id").toString();
        const auto evidence = proof("DOCUMENTED", inventory, "/junctions/" + key, "Jonction documentaire");
        out.node("junction:" + key, "JUNCTION", evidence);
        out.claim("junction:" + key, "l2_junction", row, evidence);
    }
    for (const auto &entry : model.value("cordons_documentaires").toArray()) {
        const auto row = entry.toObject();
        const auto key = row.value("id").toString();
        const auto evidence = proof("DOCUMENTED", inventory, "/harnesses/" + key, "Cordon documentaire");
        out.node("cord:" + key, "BUNDLE", evidence);
        out.claim("cord:" + key, "l2_cord", row, evidence);
    }
    QSet<QString> coveredSides;
    for (const auto &entry : l2.value("lines").toArray()) {
        const auto row = entry.toObject();
        const auto line = row.value("id").toString();
        const auto id = "link:" + line;
        const auto pointer = row.value("authority").toObject().value("pointer").toString();
        const auto evidence = proof("DOCUMENTED", inventory, pointer, "Topologie électrique d'autorité");
        out.node(id, "ELECTRICAL_LINK", evidence);
        out.claim(id, "topology", row, evidence);
        for (const auto &side : {QString("A"), QString("B")}) {
            const auto key = line + '/' + side;
            const auto port = "port:" + key;
            const auto csvRow = csv.value(key);
            const auto l2Port = interfaces.value(key).toObject();
            require(!csvRow.isEmpty() && !l2Port.isEmpty() && csvRow.value("liaison_id") == line &&
                    csvRow.value("extremite") == side, "Côté L2 ou inventaire incohérent : " + key);
            coveredSides.insert(key);
            const auto csvEvidence = proof("DOCUMENTED", connectors, key, "Inventaire d'interface, réception physique distincte");
            out.node(port, "PORT", csvEvidence);
            out.claim(port, "l2", l2Port, evidence);
            out.claim(port, "inventory", csvRow, csvEvidence);
            out.edge("ELECTRICAL", port, id, "BOTH", evidence);
            for (const auto &field : {"device_mount_frame", "receptacle_frame", "mating_frame", "plug_frame", "wire_exit_frame"}) {
                const auto bytes = csvRow.value(field).toString().toUtf8();
                out.claim(port, field, bytes.isEmpty() ? QJsonValue(QJsonValue::Null) : QJsonValue(json(bytes)),
                          bytes.isEmpty() ? proof("UNKNOWN", connectors, key + '/' + field, "Repère port indépendant à établir")
                                          : csvEvidence);
            }
            const auto selector = csvRow.value("occurrence_cao").toString();
            if (!selector.isEmpty() && out.bySelector.value(selector).size() == 1)
                out.edge("DEPENDS_ON", out.nativeIds.value(uniqueOccurrence(out, selector)), port, "FORWARD", csvEvidence);
        }
        int order = 0;
        for (const auto &step : row.value("path").toArray()) {
            const auto path = step.toObject();
            out.edge("ROUTING", id, "axis:" + path.value("route_id").toString(), "BOTH", evidence,
                     {{"order", order++}, {"sense", path.value("sense")}});
        }
        for (const auto &junction : row.value("junction_ids").toArray())
            out.edge("ELECTRICAL", id, "junction:" + junction.toString(), "BOTH", evidence);
        for (const auto &cord : row.value("cord_ids").toArray())
            out.edge("MEMBER_OF", id, "cord:" + cord.toString(), "BOTH", evidence);
    }
    require(coveredSides.size() == csv.size() && coveredSides.size() == interfaces.size(),
            "Des côtés L2 ou connectique restent sans statut");
    out.reconciliation = l2.value("summary").toObject();
    out.reconciliation.insert("line_endings", l2.value("line_endings"));
}

} // namespace

void verifySources(const QString &root, const QJsonObject &sources)
{
    for (const auto &entry : sources) {
        const auto record = entry.toObject();
        const auto path = record.value("path").toString();
        require(hash(read(root, path)) == record.value("sha256"), "Source modifiée : " + path);
    }
}

QJsonObject importGraph(const QString &root, const QJsonObject &native, const QString &authorityPath,
                        bool cartographeL2)
{
    Projection out(root);
    const auto authority = json(out.source("overlay", authorityPath));
    require(authority.value("schema") == "v3.authorities/1", "Version d'autorités non prise en charge");
    const auto sources = authority.value("sources").toObject();
    for (auto it = sources.begin(); it != sources.end(); ++it)
        out.source(it.key(), it.value().toString());
    addNative(out, native, authority.value("bindings").toObject());
    if (cartographeL2)
        addL2(out, native);
    for (const auto &entry : authority.value("nodes").toArray()) {
        const auto record = entry.toObject();
        const auto id = record.value("id").toString();
        const auto kind = record.value("kind").toString();
        const auto claims = record.value("claims").toArray();
        if (!out.nodes.contains(id)) {
            const auto evidence = record.value("evidence").toObject();
            require(!evidence.isEmpty() || !claims.isEmpty(), "Preuve d'autorité absente : " + id);
            out.node(id, kind, evidence.isEmpty() ? claims.first().toObject().value("evidence").toObject() : evidence);
        }
        require(out.nodes.value(id).value("kind") == kind, "Type d'autorité incompatible : " + id);
        out.claims(id, claims);
    }
    for (const auto &edge : authority.value("edges").toArray())
        out.edges.append(edge);
    for (const auto &issue : authority.value("issues").toArray())
        out.issues.append(issue);
    QJsonArray nodes;
    for (const auto &node : out.nodes)
        nodes.append(node);
    const auto configuration = authority.value("configuration").toString(native.value("entry").toString());
    const QJsonObject graph{{"schema", "v3.graph/1"}, {"configuration", configuration},
                           {"sources", out.sources}, {"nodes", nodes}, {"edges", out.edges},
                           {"constraints", authority.value("constraints").toArray()}, {"issues", out.issues},
                           {"reconciliation", out.reconciliation}};
    validate(graph);
    verifySources(root, out.sources);
    return graph;
}

} // namespace electromechanical::graph
