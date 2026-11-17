#include "Reconcile.hpp"

#include <QCryptographicHash>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QJsonArray>
#include <QJsonDocument>
#include <QMap>
#include <QSet>

#include <stdexcept>

using namespace Qt::StringLiterals;

namespace interconnection {
namespace {

const auto baselinePath = u"docs/electromechanical_v2/BASELINE_MANIFEST.json"_s;
const auto matrixPath = u"docs/verification/cartographe_action3_interconnexions.json"_s;
const auto mechanicalRoot = u"hardware/mecanique/cartographe"_s;
const auto bomPath = mechanicalRoot + u"/nomenclature_prototype.json";
const auto routesPath = mechanicalRoot + u"/verification/routes_prototype.json";
const auto inventoryFolder = mechanicalRoot + u"/verification/refonte_faisceaux";
const auto inventoryPath = inventoryFolder + u"/inventaire.json";
const auto netlistPath = inventoryFolder + u"/inventaire_netlist_ca01.json";
const auto wiringPath = u"hardware/electronique/cartographe/cablage_global.json"_s;
const auto onboard = u"faisceau_embarque"_s;
const auto configuration = u"prototype_cartographe_sans_dock"_s;

void require(bool condition, const QString &context)
{
    if (!condition)
        throw std::runtime_error(context.toUtf8().constData());
}

QString string(const QJsonObject &object, const QString &key)
{
    const auto value = object.value(key).toString();
    require(!value.trimmed().isEmpty(), u"Champ texte manquant : "_s + key);
    return value;
}

QJsonArray array(const QJsonObject &object, const QString &key)
{
    require(object.value(key).isArray(), u"Tableau manquant : "_s + key);
    return object.value(key).toArray();
}

QJsonObject object(const QJsonObject &parent, const QString &key)
{
    require(parent.value(key).isObject(), u"Objet manquant : "_s + key);
    return parent.value(key).toObject();
}

class Sources {
public:
    explicit Sources(const QString &root) : root_(QDir(root).canonicalPath())
    {
        require(!root.isEmpty() && !root_.isEmpty(), u"Racine du projet introuvable"_s);
    }

    QByteArray read(const QString &relativePath) const
    {
        require(QDir::isRelativePath(relativePath) && relativePath == QDir::cleanPath(relativePath)
                && !relativePath.contains(u'\\') && !relativePath.contains(u':')
                && !relativePath.startsWith(u"../") && relativePath != u"..",
                u"Chemin source non relatif au référentiel : "_s + relativePath);
        const QFileInfo fileInfo(QDir(root_).filePath(relativePath));
        const auto canonicalPath = fileInfo.canonicalFilePath();
        require(fileInfo.isFile() && canonicalPath.startsWith(root_ + u'/'),
                u"Source absente ou hors du référentiel : "_s + relativePath);
        QFile file(canonicalPath);
        require(file.open(QIODevice::ReadOnly), u"Source inaccessible : "_s + relativePath);
        const auto bytes = file.readAll();
        require(file.error() == QFile::NoError, u"Lecture incomplète : "_s + relativePath);
        return bytes;
    }

    QString hash(const QString &path, const QByteArray &bytes)
    {
        const auto digest = QString::fromLatin1(QCryptographicHash::hash(bytes, QCryptographicHash::Sha256).toHex());
        require(!hashes_.contains(path) || hashes_.value(path) == digest,
                u"Source modifiée pendant le rapprochement : "_s + path);
        hashes_.insert(path, digest);
        return digest;
    }

    QJsonObject json(const QString &path)
    {
        const auto bytes = read(path);
        hash(path, bytes);
        QJsonParseError error;
        const auto document = QJsonDocument::fromJson(bytes, &error);
        require(error.error == QJsonParseError::NoError && document.isObject(),
                u"Document JSON invalide : "_s + path);
        return document.object();
    }

    void verify(const QString &path, const QString &expectedHash)
    {
        if (!hashes_.contains(path))
            hash(path, read(path));
        require(hashes_.value(path) == expectedHash, u"Empreinte SHA-256 divergente : "_s + path);
    }

    void verify(const QJsonObject &reference)
    {
        verify(string(reference, u"path"_s), string(reference, u"sha256"_s));
    }

    QJsonObject manifest() const { return hashes_; }

private:
    QString root_;
    QJsonObject hashes_;
};

struct IndexedRecord {
    QJsonObject value;
    qsizetype index;
};

using Index = QMap<QString, IndexedRecord>;

Index indexById(const QJsonArray &records)
{
    Index indexed;
    for (qsizetype index = 0; index < records.size(); ++index) {
        const auto entry = records.at(index).toObject();
        const auto id = string(entry, u"id"_s);
        require(!indexed.contains(id), u"Identifiant dupliqué : "_s + id);
        indexed.insert(id, {entry, index});
    }
    return indexed;
}

QSet<QString> ids(const QJsonArray &values, const QString &subject)
{
    QSet<QString> result;
    for (const auto &value : values) {
        const auto id = value.toString();
        require(!id.trimmed().isEmpty() && !result.contains(id), u"Identifiant invalide ou dupliqué : "_s + subject);
        result.insert(id);
    }
    return result;
}

void requireCoverage(const Index &authority, const QSet<QString> &referenced)
{
    for (auto it = authority.begin(); it != authority.end(); ++it)
        require(referenced.contains(it.key()), u"Identifiant source non couvert : "_s + it.key());
}

void requireSameIndex(const Index &authority, const Index &reference)
{
    require(authority.keys() == reference.keys(), u"Couverture des identifiants divergente"_s);
}

QJsonObject pointer(const QString &path, const QString &collection, qsizetype index)
{
    return {{u"path"_s, path}, {u"pointer"_s, u"/"_s + collection + u'/' + QString::number(index)}};
}

QString classify(const QString &id, const QString &scope)
{
    static const QSet<QString> outOfScope = {
        u"au_sol"_s, u"interface_directe"_s, u"interne_oem"_s, u"interne_pcb"_s,
        u"reserve_non_montee"_s, u"retire"_s, u"sans_fil"_s, u"transport_reutilise"_s
    };
    static const QSet<QString> conductors = {u"W01.NEG"_s, u"W01.POS"_s, u"W37.NEG"_s, u"W37.POS"_s};
    static const QSet<QString> buses = {u"W21"_s, u"W31"_s};
    static const QSet<QString> cords = {
        u"W13.A"_s, u"W13.B"_s, u"W16"_s, u"W20"_s, u"W25"_s, u"W41"_s, u"W-CELLULES"_s
    };
    if (scope != onboard) {
        require(outOfScope.contains(scope), u"Périmètre électrique inconnu : "_s + scope);
        return u"HORS_PERIMETRE"_s;
    }
    if (conductors.contains(id))
        return u"CONDUCTEUR"_s;
    if (buses.contains(id))
        return u"BUS"_s;
    if (cords.contains(id))
        return u"CORDON"_s;
    return u"FONCTION"_s;
}

QJsonObject counts(const QMap<QString, int> &values)
{
    QJsonObject result;
    for (auto it = values.begin(); it != values.end(); ++it)
        result.insert(it.key(), it.value());
    return result;
}

} // namespace

QJsonObject reconcileInterconnections(const QString &root)
{
    Sources sources(root);
    const auto baseline = sources.json(baselinePath);
    require(baseline.value(u"schema_version"_s).toInt() == 1
            && baseline.value(u"configuration_id"_s) == u"prototype_cartographe"_s
            && baseline.value(u"dock"_s) == QJsonValue(false), u"Référentiel L0 incompatible"_s);
    QMap<QString, QString> frozen;
    const auto baselineReferences = object(baseline, u"references"_s);
    for (const auto &entries : baselineReferences) {
        for (const auto &entry : entries.toArray()) {
            const auto reference = entry.toObject();
            const auto path = string(reference, u"path"_s);
            const auto digest = string(reference, u"sha256"_s);
            require(!frozen.contains(path) || frozen.value(path) == digest, u"Gel contradictoire : "_s + path);
            frozen.insert(path, digest);
        }
    }
    for (const auto &path : {matrixPath, inventoryPath, routesPath, bomPath, wiringPath, netlistPath})
        sources.verify(path, frozen.value(path));

    const auto matrix = sources.json(matrixPath);
    const auto inventory = sources.json(inventoryPath);
    const auto routeRegistry = sources.json(routesPath);
    require(matrix.value(u"schema"_s) == u"cartographe.action3.interconnexions.v1"_s
            && inventory.value(u"schema"_s) == u"cartographe.refonte_faisceaux.inventaire.v1"_s
            && matrix.value(u"configuration"_s) == configuration
            && inventory.value(u"configuration"_s) == configuration, u"Registres de configuration incompatibles"_s);

    const auto matrixSources = object(matrix, u"sources"_s);
    const auto inventorySources = array(inventory, u"sources"_s);
    for (const auto &reference : matrixSources)
        sources.verify(reference.toObject());
    for (const auto &reference : inventorySources)
        sources.verify(reference.toObject());
    const auto netlist = sources.json(netlistPath);
    const auto schematics = array(netlist, u"scheme_sources"_s);
    for (const auto &reference : schematics)
        sources.verify(reference.toObject());
    require(netlist.value(u"candidate_ca01_netlist_pins"_s) == inventory.value(u"candidate_ca01_netlist_pins"_s)
            && array(object(netlist, u"compare_selected_ports"_s), u"differences"_s).isEmpty(),
            u"Broches CA01 divergentes dans les preuves historiques"_s);

    const auto sourceRows = array(inventory, u"connections"_s);
    const auto sourceAxes = array(inventory, u"routes"_s);
    const auto matrixRows = array(matrix, u"interconnexions"_s);
    const auto matrixAxes = array(matrix, u"axes_actifs"_s);
    const auto activeRoutes = array(routeRegistry, u"routes"_s);
    const auto rows = indexById(sourceRows);
    const auto axes = indexById(activeRoutes);
    const auto historicalAxes = indexById(sourceAxes);
    const auto bom = sources.json(bomPath);
    const auto bomWires = indexById(array(bom, u"liaisons"_s));
    const auto bomItems = indexById(array(bom, u"items"_s));
    const auto historicalWires = indexById(array(sources.json(wiringPath), u"connections"_s));
    const auto cordRecords = array(inventory, u"harnesses"_s);
    const auto cords = indexById(cordRecords);
    const auto junctions = indexById(array(inventory, u"junctions"_s));
    requireSameIndex(rows, indexById(matrixRows));
    requireSameIndex(axes, indexById(matrixAxes));
    requireSameIndex(axes, historicalAxes);

    const auto targets = object(matrix, u"revue_ciblee"_s);
    const auto f12Review = object(targets, u"W12"_s);
    sources.verify(object(f12Review, u"natif_A"_s));
    sources.verify(object(f12Review, u"natif_faces"_s));
    const auto f12Comparison = object(object(f12Review, u"corroboration_repere_rc02"_s), u"comparaison"_s);
    for (const auto &branch : f12Comparison) {
        sources.verify(object(branch.toObject(), u"registre_construction"_s));
        sources.verify(object(branch.toObject(), u"natif_porteuse"_s));
    }

    QJsonObject closureHashes;
    for (const auto &entry : array(baseline, u"native_closures"_s)) {
        const auto closure = entry.toObject();
        if (closure.value(u"role"_s) == u"REFERENCE_ACTIVE"_s && closure.value(u"root"_s) == mechanicalRoot)
            closureHashes = object(closure, u"files_sha256"_s);
    }
    require(!closureHashes.isEmpty(), u"Fermeture native active absente du référentiel L0"_s);

    QSet<QString> coveredSourceIds;
    QMap<QString, QSet<QString>> axisLines;
    QMap<QString, QSet<QString>> cordLines;
    QMap<QString, QSet<QString>> cordAxes;
    QMap<QString, int> scopeCounts;
    QMap<QString, int> classCounts;
    QJsonArray resultRows;
    QJsonArray unresolvedCopy;
    QJsonArray multiAxisRows;
    int associations = 0;
    for (qsizetype index = 0; index < matrixRows.size(); ++index) {
        const auto row = matrixRows.at(index).toObject();
        const auto id = string(row, u"id"_s);
        const auto source = rows.value(id);
        require(row.value(u"authority_index"_s).toInteger(-1) == source.index,
                u"Index de ligne divergent : "_s + id);
        for (const auto &field : {u"source_ids"_s, u"sources"_s, u"scope"_s, u"origin"_s, u"destination"_s,
                u"function"_s, u"conductors_or_pins"_s, u"cable_ids"_s, u"route_ids"_s, u"path"_s,
                u"path_kind"_s, u"junctions"_s, u"reason"_s}) {
            require(row.contains(field) && row.value(field) == source.value.value(field),
                    u"Divergence d'autorité : "_s + id + u'/' + field);
        }
        const auto scope = string(row, u"scope"_s);
        const auto classification = classify(id, scope);
        ++scopeCounts[scope];
        ++classCounts[classification];
        const auto sourceIds = array(row, u"source_ids"_s);
        coveredSourceIds.unite(ids(sourceIds, id));
        const auto path = array(row, u"path"_s);
        const auto routeIds = array(row, u"route_ids"_s);
        const auto routeSet = ids(routeIds, id);
        require(path.size() == routeIds.size() && (scope == onboard) == !path.isEmpty(),
                u"Périmètre ou couverture d'axe incohérents : "_s + id);
        for (qsizetype position = 0; position < path.size(); ++position) {
            const auto element = path.at(position).toObject();
            const auto axis = string(element, u"route_id"_s);
            const auto sense = string(element, u"sense"_s);
            require(routeIds.at(position) == axis && axes.contains(axis) && (sense == u"direct" || sense == u"inverse"),
                    u"Chemin d'axe invalide : "_s + id);
            axisLines[axis].insert(id);
            ++associations;
        }
        if (path.size() > 1)
            multiAxisRows.append(id);
        const auto cordIds = array(row, u"cable_ids"_s);
        require(scope != onboard || !cordIds.isEmpty(), u"Cordon embarqué non identifié : "_s + id);
        for (const auto &cord : ids(cordIds, id)) {
            require(cords.contains(cord) && bomItems.contains(cord), u"Cordon sans source BOM : "_s + cord);
            cordLines[cord].insert(id);
            cordAxes[cord].unite(routeSet);
        }
        const auto junctionIds = array(row, u"junctions"_s);
        for (const auto &junction : ids(junctionIds, id))
            require(junctions.contains(junction), u"Jonction non référencée : "_s + junction);

        const auto copyState = string(row, u"integration_copie_8_novembre"_s);
        require(copyState == string(source.value, u"baseline_integration"_s), u"État de copie divergent : "_s + id);
        if (scope == onboard && copyState == u"non_resolue")
            unresolvedCopy.append(id);
        const auto documentaryState = string(row, u"etat_action3"_s);
        const bool knownGeometryFailure = documentaryState == u"NON_CONFORME_GEOMETRIE_RC02";
        QJsonObject resultRow{
            {u"id"_s, id}, {u"class"_s, classification}, {u"scope"_s, scope},
            {u"axis_status"_s, scope == onboard ? u"DOCUMENTARY_LINK"_s : u"OUT_OF_SCOPE"_s},
            {u"geometry_status"_s, knownGeometryFailure ? u"FAIL"_s : u"INCONCLUSIVE"_s},
            {u"compatibility_status"_s, u"INCONCLUSIVE"_s},
            {u"action3_status"_s, documentaryState}, {u"november_8_copy_status"_s, copyState},
            {u"path_kind"_s, row.value(u"path_kind"_s)}, {u"path"_s, path},
            {u"cord_ids"_s, cordIds}, {u"junction_ids"_s, junctionIds},
            {u"source_ids"_s, sourceIds},
            {u"authority"_s, pointer(inventoryPath, u"connections"_s, source.index)},
            {u"action3"_s, pointer(matrixPath, u"interconnexions"_s, index)}
        };
        if (scope != onboard)
            resultRow.insert(u"scope_reason"_s, string(row, u"reason"_s));
        if (targets.contains(id)) {
            const auto finding = object(targets, id);
            require(finding.value(u"etat_action3"_s) == documentaryState, u"État d'anomalie divergent : "_s + id);
            resultRow.insert(u"finding"_s, QJsonObject{
                {u"observation"_s, string(finding, u"constat"_s)},
                {u"open_check"_s, string(finding, u"a_verifier"_s)},
                {u"source"_s, QJsonObject{{u"path"_s, matrixPath}, {u"pointer"_s, u"/revue_ciblee/"_s + id}}}
            });
        }
        resultRows.append(resultRow);
    }
    requireCoverage(bomWires, coveredSourceIds);
    requireCoverage(historicalWires, coveredSourceIds);

    QJsonArray resultAxes;
    QJsonArray sharedAxes;
    QJsonArray divergingAxes;
    for (const auto &entry : matrixAxes) {
        const auto axis = entry.toObject();
        const auto id = string(axis, u"id"_s);
        const auto registry = axes.value(id);
        const auto historical = historicalAxes.value(id);
        const auto lineIds = array(axis, u"connection_ids"_s);
        require(axis.value(u"registry_index"_s).toInteger(-1) == registry.index
                && !lineIds.isEmpty() && ids(lineIds, id) == axisLines.value(id)
                && ids(array(historical.value, u"connection_ids"_s), id) == axisLines.value(id),
                u"Index ou sens inverse divergent pour l'axe : "_s + id);
        const auto native = object(axis, u"natif_actif"_s);
        const auto relative = string(registry.value, u"fichier"_s);
        const auto nativeHash = string(native, u"sha256"_s);
        const auto nativeObject = string(axis, u"objet"_s);
        require(string(native, u"path"_s) == mechanicalRoot + u'/' + relative
                && nativeHash == string(closureHashes, relative)
                && nativeObject == string(registry.value, u"objet_cable"_s),
                u"Ancrage natif divergent : "_s + id);
        sources.verify(native);
        if (id == u"F12") {
            require(nativeHash == string(object(f12Review, u"natif_A"_s), u"sha256"_s),
                    u"La preuve de destination GPS2 ne correspond plus à l'axe F12 actif"_s);
        }
        const auto copyHash = string(axis, u"empreinte_copie_8_novembre"_s);
        const bool identical = nativeHash == copyHash;
        require(copyHash == string(historical.value, u"baseline_native_sha256"_s)
                && axis.value(u"natif_identique_copie_8_novembre"_s) == QJsonValue(identical),
                u"Empreinte historique divergente : "_s + id);
        if (!identical)
            divergingAxes.append(id);
        if (lineIds.size() > 1)
            sharedAxes.append(id);
        resultAxes.append(QJsonObject{
            {u"id"_s, id}, {u"line_ids"_s, lineIds}, {u"active_native"_s, native}, {u"native_object"_s, nativeObject},
            {u"november_8_copy_sha256"_s, copyHash}, {u"same_bytes_as_november_8_copy"_s, identical},
            {u"active_registry"_s, pointer(routesPath, u"routes"_s, registry.index)}
        });
    }

    QJsonArray resultCords;
    for (qsizetype index = 0; index < cordRecords.size(); ++index) {
        const auto cord = cordRecords.at(index).toObject();
        const auto id = string(cord, u"id"_s);
        const auto lineIds = array(cord, u"connection_ids"_s);
        const auto routeIds = array(cord, u"route_ids"_s);
        require(bomItems.contains(id) && !lineIds.isEmpty() && ids(lineIds, id) == cordLines.value(id)
                && ids(routeIds, id) == cordAxes.value(id), u"Couverture inverse de cordon divergente : "_s + id);
        resultCords.append(QJsonObject{
            {u"id"_s, id}, {u"line_ids"_s, lineIds}, {u"route_ids"_s, routeIds},
            {u"authority"_s, pointer(inventoryPath, u"harnesses"_s, index)},
            {u"bom_item"_s, pointer(bomPath, u"items"_s, bomItems.value(id).index)}
        });
    }

    return {
        {u"schema"_s, u"drone-agricole.l2.reconciliation.v1"_s},
        {u"configuration_id"_s, configuration},
        {u"status"_s, u"RECONCILED"_s},
        {u"limits"_s, QJsonArray{
            u"Rapprochement documentaire et empreintes de l'actif. La continuité, l'accouplement et le montage physiques restent à vérifier."_s,
            u"Une ligne désigne la fonction source, une paire désigne une association et un axe désigne une occurrence CAO."_s,
            u"Une empreinte de copie désigne la référence historique du 8 novembre dans le registre de refonte."_s
        }},
        {u"classification_rules"_s, QJsonObject{
            {u"CONDUCTEUR"_s, u"Ligne affectée à un seul potentiel, explicitement identifié."_s},
            {u"FONCTION"_s, u"Fonction ou sous-fonction embarquée, parfois multiconducteur ou transportée par un cordon partagé."_s},
            {u"BUS"_s, u"Ligne de bus CAN H/L identifiée, avec alimentation et retour si prévus."_s},
            {u"CORDON"_s, u"Ligne désignant un cordon, un coaxial OEM ou un adaptateur individualisé, y compris candidat."_s},
            {u"HORS_PERIMETRE"_s, u"Ligne hors du registre des axes du faisceau embarqué. Le motif provient de la ligne source."_s}
        }},
        {u"summary"_s, QJsonObject{
            {u"lines"_s, matrixRows.size()}, {u"active_axes"_s, matrixAxes.size()}, {u"line_axis_pairs"_s, associations},
            {u"bom_connection_ids_covered"_s, bomWires.size()}, {u"historical_wiring_ids_covered"_s, historicalWires.size()},
            {u"matrix_sources_verified"_s, matrixSources.size()}, {u"inventory_sources_verified"_s, inventorySources.size()},
            {u"ca01_schematic_sources_verified"_s, schematics.size()}, {u"active_native_axes_verified"_s, resultAxes.size()},
            {u"by_scope"_s, counts(scopeCounts)}, {u"by_class"_s, counts(classCounts)},
            {u"multi_axis_lines"_s, multiAxisRows}, {u"shared_axes"_s, sharedAxes},
            {u"active_axis_hashes_differing_from_november_8_copy"_s, divergingAxes},
            {u"unresolved_onboard_lines_in_november_8_copy"_s, unresolvedCopy}
        }},
        {u"source_sha256"_s, sources.manifest()},
        {u"lines"_s, resultRows}, {u"axes"_s, resultAxes}, {u"cords"_s, resultCords}
    };
}

QJsonObject inspectCartographeInterfaces(const QString &root)
{
    const auto reconciled = reconcileInterconnections(root);
    Sources sources(root);
    const auto go3a = u"docs/verification/go3a/"_s;
    const auto go3b = u"docs/verification/go3b/"_s;
    const auto modelPath = go3a + u"GO3A_SYSTEM_MODEL.json";
    const auto connectorPath = go3a + u"GO3A_CONNECTOR_BOM.csv";
    const auto frozen = object(sources.json(go3b + u"GO3B_SOURCE_MANIFEST.json"), u"files"_s);
    for (const auto &path : {modelPath, connectorPath, go3a + u"GO3A_INTERCONNECTION_MATRIX.csv"})
        sources.verify(path, string(frozen, path));
    const auto coverage = object(object(sources.json(go3b + u"GO3B_ADMISSION.json"),
                                        u"controles_admission"_s), u"couverture"_s);
    sources.verify(go3b + u"GO3B_INTERCONNECTION_COVERAGE.csv", string(coverage, u"sha256"_s));

    const auto model = sources.json(modelPath);
    const auto config = object(model, u"configuration"_s);
    require(config.value(u"baseline"_s) == u"prototype_cartographe"_s &&
            config.value(u"dock"_s) == QJsonValue(false), u"Périmètre GO3A incompatible"_s);
    const auto lines = indexById(array(reconciled, u"lines"_s));
    const auto axes = indexById(array(reconciled, u"axes"_s));
    const auto links = indexById(array(model, u"links"_s));
    const auto nativeAxes = indexById(array(model, u"axes_cao"_s));
    const auto ports = indexById(array(model, u"ports"_s));
    const auto equipment = indexById(array(model, u"equipment"_s));
    requireSameIndex(lines, links);
    requireSameIndex(axes, nativeAxes);

    QJsonObject interfaces;
    QJsonObject lineInterfaces;
    QMap<QString, QSet<QString>> equipmentInterfaces;
    QSet<QString> usedPorts;
    qsizetype offAxis = 0;
    for (auto it = lines.cbegin(); it != lines.cend(); ++it) {
        const auto id = it.key();
        const auto line = it.value().value;
        const auto link = links.value(id).value;
        require(line.value(u"class"_s) == link.value(u"family"_s) &&
                line.value(u"scope"_s) == link.value(u"scope"_s) &&
                line.value(u"path"_s) == link.value(u"path"_s) &&
                line.value(u"path_kind"_s) == link.value(u"path_kind"_s) &&
                line.value(u"cord_ids"_s) == link.value(u"cable_ids"_s) &&
                line.value(u"junction_ids"_s) == link.value(u"junction_ids"_s),
                u"Topologie GO3A divergente du rapprochement L2 : "_s + id);
        offAxis += line.contains(u"scope_reason"_s);
        QJsonArray endpoints;
        for (const auto &side : {qMakePair(u"A"_s, u"source"_s), qMakePair(u"B"_s, u"target"_s)}) {
            const auto key = id + u'/' + side.first;
            const auto portId = string(link, side.second);
            const auto port = ports.value(portId).value;
            const auto equipmentId = string(port, u"equipment"_s);
            const auto bom = object(port, u"bom_connecteur"_s);
            require(equipment.contains(equipmentId) && !usedPorts.contains(portId) &&
                    bom.value(u"path"_s) == u"GO3A_CONNECTOR_BOM.csv"_s &&
                    bom.value(u"liaison_id"_s) == id && bom.value(u"extremite"_s) == side.first,
                    u"Ancrage d’interface GO3A invalide : "_s + key);
            usedPorts.insert(portId);
            equipmentInterfaces[equipmentId].insert(key);
            endpoints.append(key);
            interfaces.insert(key, QJsonObject{
                {u"line_id"_s, id}, {u"side"_s, side.first}, {u"port_record_id"_s, portId},
                {u"functional_port"_s, port.value(u"interface"_s)}, {u"equipment_id"_s, equipmentId},
                {u"equipment_reference_documentary"_s, equipment.value(equipmentId).value.value(u"reference_definition"_s)},
                {u"reception"_s, u"INCONCLUSIVE"_s}, {u"native_interface"_s, QJsonValue::Null},
                {u"port_geometry_evidence"_s, port.value(u"statut_etude_geometrique"_s)},
                {u"research_issue"_s, link.value(u"recherche"_s)},
                {u"electrical_sources"_s, port.value(u"source_electrique"_s)},
                {u"connector_record"_s, connectorPath + u'#' + key},
                {u"port_record"_s, pointer(modelPath, u"ports"_s, ports.value(portId).index)}
            });
        }
        lineInterfaces.insert(id, endpoints);
    }
    requireCoverage(ports, usedPorts);
    for (auto it = equipment.cbegin(); it != equipment.cend(); ++it)
        require(equipmentInterfaces.value(it.key()) == ids(array(it.value().value, u"liaisons_et_cotes"_s), it.key()),
                u"Couverture inverse équipement divergente : "_s + it.key());

    QJsonObject axisInterfaces;
    for (auto it = axes.cbegin(); it != axes.cend(); ++it) {
        const auto axis = it.value().value;
        const auto native = nativeAxes.value(it.key()).value;
        const auto path = object(axis, u"active_native"_s);
        require(path.value(u"path"_s) == mechanicalRoot + u'/' + string(native, u"chemin_natif_actif"_s) &&
                path.value(u"sha256"_s) == native.value(u"sha256_natif_actif"_s) &&
                axis.value(u"native_object"_s) == native.value(u"objet_natif"_s) &&
                ids(array(axis, u"line_ids"_s), it.key()) == ids(array(native, u"line_ids"_s), it.key()),
                u"Association inverse axe ↔ liaison GO3A divergente : "_s + it.key());
        axisInterfaces.insert(it.key(), QJsonObject{
            {u"line_ids"_s, axis.value(u"line_ids"_s)}, {u"native_file"_s, path},
            {u"native_object"_s, axis.value(u"native_object"_s)},
            {u"assembly_occurrence"_s, native.value(u"occurrence_assemblage"_s)},
            {u"binding_kind"_s, u"DOCUMENTARY_AXIS"_s}
        });
    }
    const auto summary = object(reconciled, u"summary"_s);
    require(coverage.value(u"lignes"_s) == lines.size() && coverage.value(u"axes"_s) == axes.size() &&
            coverage.value(u"associations_bidirectionnelles"_s) == summary.value(u"line_axis_pairs"_s) &&
            coverage.value(u"lignes_sans_axe_avec_motif"_s) == offAxis &&
            coverage.value(u"extremites_a_b"_s) == interfaces.size(), u"Couverture GO3B divergente"_s);
    auto hashes = object(reconciled, u"source_sha256"_s);
    const auto added = sources.manifest();
    for (auto it = added.begin(); it != added.end(); ++it)
        hashes.insert(it.key(), it.value());
    return {{u"schema"_s, u"drone-agricole.l2.cartographe-interfaces.v1"_s},
            {u"configuration_id"_s, configuration}, {u"status"_s, u"INCONCLUSIVE"_s},
            {u"summary"_s, coverage}, {u"interfaces"_s, interfaces}, {u"line_interfaces"_s, lineInterfaces},
            {u"lines"_s, reconciled.value(u"lines"_s)}, {u"axes"_s, axisInterfaces}, {u"source_sha256"_s, hashes}};
}

} // namespace interconnection
