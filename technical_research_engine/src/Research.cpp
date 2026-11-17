#include "Research.hpp"
#include "Sources.hpp"

#include <QCryptographicHash>
#include <QDateTime>
#include <QDir>
#include <QDirIterator>
#include <QFileInfo>
#include <QJsonArray>
#include <QJsonDocument>
#include <QLockFile>
#include <QRegularExpression>
#include <QSaveFile>
#include <QSet>
#include <QVector>

#include <algorithm>
#include <cmath>
#include <stdexcept>

using namespace Qt::StringLiterals;

namespace technical_research {
namespace {

const auto version = u"1.0.0"_s;
const QJsonValue null = QJsonValue::Null;
constexpr auto maxReportBytes = 16 * 1024 * 1024;
constexpr auto maxLocalBytes = 64 * 1024 * 1024;
constexpr auto maxSources = 32;

void require(bool condition, const QString &message)
{
    if (!condition)
        throw std::runtime_error(message.toUtf8().constData());
}

QString field(const QJsonObject &object, const QString &key)
{
    const auto value = object.value(key).toString();
    require(!value.trimmed().isEmpty(), u"Champ texte requis : "_s + key);
    return value;
}

QJsonObject objectField(const QJsonObject &object, const QString &key)
{
    require(object.value(key).isObject(), u"Objet requis : "_s + key);
    return object.value(key).toObject();
}

QJsonArray arrayField(const QJsonObject &object, const QString &key)
{
    require(object.value(key).isArray(), u"Tableau requis : "_s + key);
    return object.value(key).toArray();
}

QString choice(const QJsonObject &object, const QString &key, const QStringList &allowed)
{
    const auto value = field(object, key);
    require(allowed.contains(value), u"Valeur non reconnue pour "_s + key);
    return value;
}

void checkId(const QString &id)
{
    static const QRegularExpression pattern(u"^[A-Za-z][A-Za-z0-9_.:-]*$"_s);
    require(pattern.match(id).hasMatch(), u"Identifiant invalide : "_s + id);
}

QString unitField(const QJsonObject &object)
{
    return choice(object, u"unit"_s, {u"mm"_s, u"mm2"_s, u"mm3"_s, u"deg"_s, u"A"_s, u"V"_s,
        u"ohm"_s, u"Hz"_s, u"s"_s, u"degC"_s, u"g"_s, u"g/m"_s, u"1"_s});
}

void checkTextArray(const QJsonArray &values)
{
    require(!values.isEmpty(), u"Une liste de textes non vide est requise"_s);
    QSet<QString> seen;
    for (const auto &value : values) {
        const auto item = value.toString();
        require(!item.trimmed().isEmpty() && !seen.contains(item), u"Texte vide ou dupliqué"_s);
        seen.insert(item);
    }
}

void checkTextMap(const QJsonObject &values)
{
    for (auto it = values.constBegin(); it != values.constEnd(); ++it)
        require(!it.key().trimmed().isEmpty() && !it.value().toString().trimmed().isEmpty(),
                u"Une condition ou un attribut doit porter une valeur explicite"_s);
}

QJsonObject referenceField(const QJsonObject &object)
{
    const auto reference = objectField(object, u"reference"_s);
    require(reference.size() == 5, u"Champs de référence inattendus"_s);
    for (const auto &key : {u"manufacturer"_s, u"family"_s, u"part_number"_s})
        field(reference, key);
    if (!reference.value(u"revision"_s).isNull())
        field(reference, u"revision"_s);
    checkTextMap(objectField(reference, u"attributes"_s));
    return reference;
}

QJsonObject applicabilityField(const QJsonObject &object)
{
    const auto scope = objectField(object, u"applicability"_s);
    require(scope.size() == 2, u"Champs de domaine inattendus"_s);
    choice(scope, u"domain"_s, {u"CAD"_s, u"BENCH"_s, u"PHYSICAL"_s, u"DOCUMENT"_s});
    checkTextMap(objectField(scope, u"conditions"_s));
    return scope;
}

void checkRequest(const QJsonObject &request)
{
    require(request.size() == (request.contains(u"derivation"_s) ? 10 : 9),
            u"Champs de demande inattendus"_s);
    checkId(field(request, u"issue_id"_s));
    field(request, u"parameter"_s);
    unitField(request);
    choice(request, u"criticality"_s, {u"LOW"_s, u"MEDIUM"_s, u"HIGH"_s, u"CRITICAL"_s});
    referenceField(request);
    applicabilityField(request);
    choice(request, u"expected_authority"_s, {u"PROJECT"_s, u"MANUFACTURER"_s, u"SECONDARY"_s, u"ANY"_s});
    const auto study = objectField(request, u"study"_s);
    require(study.size() == 3, u"Champs d'étude inattendus"_s);
    field(study, u"strategy"_s);
    field(study, u"next_observation"_s);
    checkTextArray(arrayField(study, u"variables"_s));

    const auto question = objectField(request, u"question"_s);
    require(question.size() == 9, u"Champs de question L0 inattendus"_s);
    checkId(field(question, u"id"_s));
    const auto subjects = arrayField(question, u"subject_ids"_s);
    checkTextArray(subjects);
    for (const auto &subject : subjects)
        checkId(subject.toString());
    for (const auto &key : {u"question"_s, u"hypothesis"_s, u"expected_evidence"_s, u"refutation"_s,
                            u"dependent_decision"_s})
        field(question, key);
    require(field(question, u"status"_s) == u"OPEN" && arrayField(question, u"evidence_ids"_s).isEmpty(),
            u"La demande doit porter une question ouverte sans preuve déjà admise"_s);
}

QString digest(const QByteArray &bytes)
{
    return QString::fromLatin1(QCryptographicHash::hash(bytes, QCryptographicHash::Sha256).toHex());
}

QByteArray compact(const QJsonObject &object)
{
    return QJsonDocument(object).toJson(QJsonDocument::Compact);
}

QJsonObject parseObject(const QByteArray &bytes, const QString &description)
{
    QJsonParseError error;
    const auto document = QJsonDocument::fromJson(bytes, &error);
    require(document.isObject(), description + u" : "_s + error.errorString());
    return document.object();
}

QString now()
{
    return QDateTime::currentDateTimeUtc().toString(Qt::ISODate);
}

QString reportName(const QString &issue)
{
    return u"report-"_s + digest(issue.toUtf8()) + u".json"_s;
}

QJsonObject readReport(const QString &path)
{
    QFile file(path);
    if (!file.open(QIODevice::ReadOnly)) {
        require(file.exists() == false, u"Lecture du rapport impossible"_s);
        return {};
    }
    const auto bytes = file.read(maxReportBytes + 1);
    require(file.error() == QFileDevice::NoError && bytes.size() <= maxReportBytes,
            u"Lecture du rapport interrompue ou rapport trop volumineux"_s);
    const auto receipt = parseObject(bytes, u"Rapport illisible"_s);
    const auto report = objectField(receipt, u"report"_s);
    require(receipt.value(u"sha256"_s) == digest(compact(report)), u"Empreinte du rapport incohérente"_s);
    require(report.value(u"schema_version"_s) == version, u"Version de rapport incompatible"_s);
    require(!arrayField(report, u"local_inputs"_s).isEmpty(), u"Entrées du rapport manquantes"_s);
    return report;
}

void writeReport(const QString &path, const QJsonObject &report)
{
    QSaveFile file(path);
    const auto bytes = compact({{u"report"_s, report}, {u"sha256"_s, digest(compact(report))}});
    require(bytes.size() <= maxReportBytes, u"Rapport trop volumineux"_s);
    require(file.open(QIODevice::WriteOnly) && file.write(bytes) == bytes.size() && file.commit(),
            u"Publication du rapport impossible"_s);
}

struct LocalInput {
    QString path;
    SourceInput input;
};

const SourceInput &loadLocal(QVector<LocalInput> &inputs, const QString &root, const QString &path)
{
    const auto it = std::find_if(inputs.cbegin(), inputs.cend(),
        [&path](const LocalInput &entry) { return entry.path == path; });
    if (it != inputs.cend())
        return it->input;
    inputs.append({path, readLocalSource(root, path)});
    qsizetype total = 0;
    for (const auto &entry : inputs)
        total += entry.input.bytes.size();
    require(total <= maxLocalBytes, u"Entrées documentaires au-delà de 64 Mio"_s);
    return inputs.constLast().input;
}

QJsonArray fingerprints(const QVector<LocalInput> &inputs)
{
    QJsonArray result;
    for (const auto &entry : inputs)
        result.append(QJsonObject{{u"path"_s, entry.path}, {u"sha256"_s,
            entry.input.sha256.isEmpty() ? null : QJsonValue(entry.input.sha256)}});
    return result;
}

bool fresh(const QString &root, const QJsonArray &inputs)
{
    for (const auto &entry : inputs) {
        const auto object = entry.toObject();
        const auto current = readLocalSource(root, field(object, u"path"_s));
        if (current.sha256 != object.value(u"sha256"_s).toString())
            return false;
    }
    return true;
}

QJsonObject makeValue(const QString &unit, const QString &status, const QJsonValue &value,
                      const QJsonValue &revision, const QString &date, const QString &limits)
{
    return {{u"unit"_s, unit}, {u"status"_s, status}, {u"value"_s, value},
        {u"revision"_s, revision}, {u"collected_at"_s, date}, {u"limits"_s, limits},
        {u"evidence_ids"_s, QJsonArray{}}, {u"precision"_s, null}, {u"uncertainty"_s, null},
        {u"method"_s, null}, {u"input_value_refs"_s, QJsonArray{}}};
}

QString matchSource(const QJsonObject &request, const QJsonObject &source)
{
    auto requested = referenceField(request);
    auto offered = referenceField(source);
    const auto requestedRevision = requested.take(u"revision"_s);
    const auto offeredRevision = offered.take(u"revision"_s);
    if (requested != offered)
        return u"REFERENCE_MISMATCH"_s;
    if (applicabilityField(request) != applicabilityField(source) || unitField(request) != unitField(source))
        return u"SCOPE_MISMATCH"_s;
    const auto expected = field(request, u"expected_authority"_s);
    const auto authority = choice(source, u"authority"_s, {u"PROJECT"_s, u"MANUFACTURER"_s, u"SECONDARY"_s});
    if (expected != u"ANY" && authority != expected)
        return u"AUTHORITY_MISMATCH"_s;
    if (requestedRevision.isNull() || requestedRevision != offeredRevision)
        return u"REVISION_MISMATCH"_s;
    return u"EXACT"_s;
}

bool comparable(const QString &match)
{
    return match == u"EXACT" || match == u"REVISION_MISMATCH";
}

void diagnostic(QJsonArray &items, const QString &id, const QString &code, const QString &message)
{
    items.append(QJsonObject{{u"source_id"_s, id}, {u"code"_s, code}, {u"message"_s, message}});
}

void discoverLocal(const QDir &root, const QString &partNumber, const QJsonArray &declared,
                   QJsonArray &diagnostics)
{
    QSet<QString> known;
    for (const auto &item : declared)
        known.insert(item.toObject().value(u"path"_s).toString());

    static const QSet<QString> textSuffixes{u"json"_s, u"md"_s, u"txt"_s, u"csv"_s, u"html"_s,
        u"xml"_s, u"yaml"_s, u"kicad_sch"_s};
    static const QSet<QString> binarySuffixes{u"pdf"_s, u"fcstd"_s, u"step"_s, u"stp"_s};
    const QRegularExpression reference(u"(?<![A-Za-z0-9_.-])"_s +
        QRegularExpression::escape(partNumber) + u"(?![A-Za-z0-9_.-])"_s);
    int filesLeft = 5000;
    int matchesLeft = 24;
    qint64 bytesLeft = 32 * 1024 * 1024;
    const auto rootPath = QFileInfo(root.absolutePath()).canonicalFilePath();
    for (const auto &folder : {u"hardware/electronique/cartographe"_s, u"hardware/mecanique/cartographe"_s,
                               u"docs"_s, u"research"_s}) {
        const auto directory = root.filePath(folder);
        const auto canonical = QFileInfo(directory).canonicalFilePath();
        if (canonical.isEmpty() || !canonical.startsWith(rootPath + u'/'))
            continue;
        QDirIterator files(directory, QDir::Files | QDir::NoSymLinks, QDirIterator::Subdirectories);
        while (files.hasNext() && filesLeft > 0 && matchesLeft > 0) {
            const auto info = files.nextFileInfo();
            --filesLeft;
            const auto path = root.relativeFilePath(info.absoluteFilePath());
            const auto suffix = info.suffix().toLower();
            if (known.contains(path) || (!textSuffixes.contains(suffix) && !binarySuffixes.contains(suffix)))
                continue;
            bool match = reference.match(info.completeBaseName()).hasMatch();
            if (!match && textSuffixes.contains(suffix) && info.size() <= 512 * 1024 && info.size() <= bytesLeft) {
                bytesLeft -= info.size();
                const auto content = readLocalSource(root.absolutePath(), path);
                match = content.code.isEmpty() && reference.match(QString::fromUtf8(content.bytes)).hasMatch();
            }
            if (match) {
                --matchesLeft;
                diagnostic(diagnostics, u"DISCOVERY"_s, u"LOCAL_CANDIDATE"_s, path);
            }
        }
    }
    if (filesLeft == 0 || matchesLeft == 0 || bytesLeft == 0)
        diagnostic(diagnostics, u"DISCOVERY"_s, u"LOCAL_SEARCH_BUDGET"_s, u"Inventaire local borné"_s);
}

void checkEvidence(const QJsonObject &evidence)
{
    require(evidence.size() == 12, u"Champs de preuve L0 inattendus"_s);
    checkId(field(evidence, u"id"_s));
    choice(evidence, u"kind"_s, {u"SOURCE"_s, u"OBSERVATION"_s});
    choice(evidence, u"domain"_s, {u"CAD"_s, u"BENCH"_s, u"PHYSICAL"_s, u"DOCUMENT"_s});
    for (const auto &key : {u"locator"_s, u"method"_s, u"limits"_s})
        field(evidence, key);
    for (const auto &key : {u"artifact_path"_s, u"uri"_s, u"revision"_s, u"sha256"_s}) {
        if (!evidence.value(key).isNull())
            field(evidence, key);
    }
    require(!evidence.value(u"artifact_path"_s).isNull() || !evidence.value(u"uri"_s).isNull(),
            u"Preuve sans chemin ni URI"_s);
    const auto date = field(evidence, u"collected_at"_s);
    require(date.endsWith(u'Z') && QDateTime::fromString(date, Qt::ISODate).isValid(),
            u"Date de collecte UTC ISO 8601 invalide"_s);
    require(evidence.value(u"hypothetical"_s) == QJsonValue(false),
            u"Les sources du catalogue doivent être observables"_s);
    require(evidence.value(u"kind"_s) != u"OBSERVATION"_s || evidence.value(u"domain"_s) != u"DOCUMENT"_s,
            u"Une mesure exige un domaine CAO, banc ou physique"_s);
    const auto sha = evidence.value(u"sha256"_s);
    static const QRegularExpression hashPattern(u"^[0-9a-f]{64}$"_s);
    require(sha.isNull() || hashPattern.match(sha.toString()).hasMatch(), u"Empreinte SHA-256 invalide"_s);
}

struct Findings {
    QJsonArray evidence;
    QJsonArray details;
    QJsonArray diagnostics;
    bool incomplete = false;
};

void extract(const QJsonObject &request, const QJsonObject &source, const SourceInput &input,
             Findings &findings, bool remote)
{
    auto evidence = objectField(source, u"evidence"_s);
    const auto id = field(evidence, u"id"_s);
    QString match;
    try {
        match = matchSource(request, source);
        checkEvidence(evidence);
        require(evidence.value(u"domain"_s) == applicabilityField(source).value(u"domain"_s),
                u"Domaine de preuve incompatible avec son contexte"_s);
        require(!remote || (evidence.value(u"domain"_s) == u"DOCUMENT"_s &&
                            evidence.value(u"kind"_s) == u"SOURCE"_s),
                u"Une publication distante constitue une preuve documentaire"_s);
        if (!input.code.isEmpty()) {
            diagnostic(findings.diagnostics, id, input.code, input.message);
            findings.incomplete |= comparable(match);
            return;
        }
        const auto expected = evidence.value(u"sha256"_s);
        if (!expected.isNull() && expected.toString() != input.sha256) {
            diagnostic(findings.diagnostics, id, u"SOURCE_HASH_MISMATCH"_s,
                       u"Le document diffère de l'empreinte attendue"_s);
            findings.incomplete |= comparable(match);
            return;
        }

        const auto reference = referenceField(source);
        const auto value = extractSourceValue(input, objectField(source, u"extraction"_s),
                                              field(reference, u"part_number"_s));
        const auto unit = unitField(source);
        require(value.isDouble() || (unit == u"1" && (value.isString() || value.isBool())),
                u"Type de valeur incompatible avec l'unité"_s);
        const auto uncertainty = source.value(u"uncertainty"_s);
        require(uncertainty.isNull() || (value.isDouble() && uncertainty.isDouble() &&
                std::isfinite(uncertainty.toDouble()) && uncertainty.toDouble() >= 0),
                u"Incertitude absente ou invalide"_s);
        if (remote)
            evidence.insert(u"collected_at"_s, now());
        evidence.insert(u"sha256"_s, input.sha256);
        const auto status = evidence.value(u"kind"_s) == u"OBSERVATION"_s ? u"MEASURED"_s : u"SOURCED"_s;
        auto observed = makeValue(unit, status, value, reference.value(u"revision"_s),
                                  field(evidence, u"collected_at"_s), field(evidence, u"limits"_s));
        observed.insert(u"evidence_ids"_s, QJsonArray{id});
        observed.insert(u"uncertainty"_s, uncertainty);
        observed.insert(u"method"_s, evidence.value(u"method"_s));
        findings.details.append(QJsonObject{{u"evidence_id"_s, id}, {u"reference"_s, reference},
            {u"applicability"_s, applicabilityField(source)}, {u"authority"_s, source.value(u"authority"_s)},
            {u"confidence"_s, choice(source, u"confidence"_s, {u"HIGH"_s, u"MEDIUM"_s, u"LOW"_s})},
            {u"value"_s, observed}, {u"match"_s, match}});
        findings.evidence.append(evidence);
    } catch (const std::exception &error) {
        diagnostic(findings.diagnostics, id, u"EXTRACTION_REJECTED"_s, QString::fromUtf8(error.what()));
        findings.incomplete |= match.isEmpty() || comparable(match);
    }
}

struct Assessment {
    QJsonArray exact;
    QJsonArray conflicts;
};

Assessment assess(const QJsonArray &details)
{
    Assessment result;
    QJsonArray comparableDetails;
    for (const auto &item : details) {
        const auto detail = item.toObject();
        const auto match = field(detail, u"match"_s);
        if (match == u"EXACT")
            result.exact.append(detail);
        if (comparable(match))
            comparableDetails.append(detail);
    }
    for (qsizetype i = 0; i < comparableDetails.size(); ++i) {
        const auto left = comparableDetails.at(i).toObject();
        const auto leftValue = objectField(left, u"value"_s).value(u"value"_s);
        for (qsizetype j = i + 1; j < comparableDetails.size(); ++j) {
            const auto right = comparableDetails.at(j).toObject();
            if (leftValue != objectField(right, u"value"_s).value(u"value"_s))
                result.conflicts.append(QJsonArray{left.value(u"evidence_id"_s), right.value(u"evidence_id"_s)});
        }
    }
    return result;
}

QJsonObject mergeExact(const QJsonArray &exact)
{
    auto value = objectField(exact.first().toObject(), u"value"_s);
    QJsonArray ids;
    QStringList limits;
    for (const auto &item : exact) {
        const auto detail = item.toObject();
        const auto observed = objectField(detail, u"value"_s);
        ids.append(detail.value(u"evidence_id"_s));
        const auto uncertainty = observed.value(u"uncertainty"_s);
        const auto current = value.value(u"uncertainty"_s);
        if (uncertainty.isNull() || (!current.isNull() && uncertainty.toDouble() > current.toDouble()))
            value.insert(u"uncertainty"_s, uncertainty);
        limits.append(field(observed, u"limits"_s));
    }
    limits.removeDuplicates();
    value.insert(u"evidence_ids"_s, ids);
    value.insert(u"limits"_s, limits.join(u" | "_s));
    return value;
}

struct Interval {
    double nominal;
    double lower;
    double upper;
};

Interval assumedInput(const QJsonObject &raw, const QString &key, QJsonObject &inputs,
                      const QString &date, const QString &limits)
{
    const auto input = objectField(raw, key);
    require(input.size() == 3 && unitField(input) == u"mm" && input.value(u"value"_s).isDouble() &&
            input.value(u"uncertainty"_s).isDouble(), u"Longueur et incertitude requises en mm"_s);
    const auto nominal = input.value(u"value"_s).toDouble();
    const auto radius = input.value(u"uncertainty"_s).toDouble();
    require(std::isfinite(nominal) && std::isfinite(radius) && radius >= 0 &&
            nominal - radius >= 0 && std::isfinite(nominal + radius), u"Bornes de longueur invalides"_s);
    auto value = makeValue(u"mm"_s, u"ASSUMED"_s, nominal, null, date, limits);
    value.insert(u"method"_s, u"Entrée conditionnelle déclarée dans la demande"_s);
    value.insert(u"uncertainty"_s, radius);
    inputs.insert(key, value);
    return {nominal, nominal - radius, nominal + radius};
}

QJsonObject calculate(const QJsonObject &request, const QString &date, QJsonObject &value)
{
    const auto declared = objectField(request, u"derivation"_s);
    require(declared.size() == 4, u"Champs de dérivation inattendus"_s);
    const auto op = choice(declared, u"operation"_s, {u"LENGTH_DIFFERENCE"_s, u"CIRCULAR_SECTION_AREA"_s});
    const auto limits = field(declared, u"limits"_s);
    const auto assumptions = arrayField(declared, u"assumptions"_s);
    checkTextArray(assumptions);
    const auto raw = objectField(declared, u"inputs"_s);
    const auto unit = unitField(request);
    QJsonObject inputs;
    QJsonArray refs;
    QString equation;
    Interval result{};
    if (op == u"LENGTH_DIFFERENCE") {
        require(field(request, u"parameter"_s) == u"length_difference" && unit == u"mm" && raw.size() == 2,
                u"La différence de longueurs produit uniquement length_difference en mm"_s);
        const auto available = assumedInput(raw, u"available"_s, inputs, date, limits);
        const auto required = assumedInput(raw, u"required"_s, inputs, date, limits);
        result = {available.nominal - required.nominal, available.lower - required.upper,
                  available.upper - required.lower};
        equation = u"L_disponible - L_requise"_s;
        refs = {u"/derivation/inputs/available"_s, u"/derivation/inputs/required"_s};
    } else {
        require(field(request, u"parameter"_s) == u"circular_section_area" && unit == u"mm2" && raw.size() == 1,
                u"La section circulaire produit uniquement circular_section_area en mm2"_s);
        const auto diameter = assumedInput(raw, u"diameter"_s, inputs, date, limits);
        const auto area = [](double d) { return std::acos(-1.0) * (d / 2) * (d / 2); };
        result = {area(diameter.nominal), area(diameter.lower), area(diameter.upper)};
        equation = u"π × (diamètre / 2)²"_s;
        refs = {u"/derivation/inputs/diameter"_s};
    }
    const auto uncertainty = std::max(result.nominal - result.lower, result.upper - result.nominal);
    require(std::isfinite(result.nominal) && std::isfinite(result.lower) && std::isfinite(result.upper) &&
            std::isfinite(uncertainty), u"Résultat de calcul hors bornes numériques"_s);
    value = makeValue(unit, u"CALCULATED"_s, result.nominal,
        objectField(request, u"reference"_s).value(u"revision"_s), date, limits);
    value.insert(u"method"_s, equation + u" ; propagation des bornes extrêmes des entrées"_s);
    value.insert(u"uncertainty"_s, uncertainty);
    value.insert(u"input_value_refs"_s, refs);
    return {{u"operation"_s, op}, {u"equation"_s, equation}, {u"assumptions"_s, assumptions},
        {u"inputs"_s, inputs}, {u"limits"_s, limits},
        {u"bounds"_s, QJsonObject{{u"lower"_s, result.lower}, {u"upper"_s, result.upper}}}};
}

Result absent(const QString &issue, const QString &code, const QString &message)
{
    return {{{u"issue_id"_s, issue}, {u"error"_s, code}, {u"message"_s, message}}, 3};
}

} // namespace

Result submit(const QString &root, const QString &store, const QString &catalog,
              const QString &issue, bool online, bool refresh)
{
    checkId(issue);
    const QDir rootDir(root);
    require(rootDir.exists(), u"Racine documentaire absente"_s);
    const auto catalogPath = rootDir.relativeFilePath(QFileInfo(catalog).absoluteFilePath());
    QVector<LocalInput> inputs;
    const auto input = loadLocal(inputs, root, catalogPath);
    require(input.code.isEmpty(), input.message);
    const auto data = parseObject(input.bytes, u"Catalogue illisible"_s);
    require(data.size() == 4 && data.value(u"schema_version"_s) == version,
            u"Forme ou version de catalogue incompatible"_s);
    const auto configuration = field(data, u"configuration_id"_s);
    checkId(configuration);

    QJsonObject request;
    for (const auto &item : arrayField(data, u"questions"_s)) {
        if (item.toObject().value(u"issue_id"_s) == issue) {
            require(request.isEmpty(), u"Question dupliquée pour le même issue_id"_s);
            request = item.toObject();
        }
    }
    if (request.isEmpty())
        return absent(issue, u"ISSUE_NOT_FOUND"_s, u"Aucune question pour cet identifiant"_s);
    checkRequest(request);
    const auto parameter = field(request, u"parameter"_s);
    QVector<QJsonObject> sources;
    QVector<QJsonObject> remote;
    QSet<QString> seen;
    for (const auto &item : arrayField(data, u"sources"_s)) {
        const auto source = item.toObject();
        if (source.value(u"parameter"_s) != parameter)
            continue;
        const auto evidence = objectField(source, u"evidence"_s);
        const auto id = field(evidence, u"id"_s);
        require(!seen.contains(id), u"Identifiant de preuve dupliqué : "_s + id);
        seen.insert(id);
        require(seen.size() <= maxSources, u"Catalogue au-delà de 32 sources pour cette question"_s);
        const auto path = evidence.value(u"artifact_path"_s).toString();
        if (path.isEmpty()) {
            remote.append(source);
        } else {
            loadLocal(inputs, root, path);
            sources.append(source);
        }
    }
    const auto localInputs = fingerprints(inputs);
    const auto key = digest(compact({{u"version"_s, version}, {u"issue_id"_s, issue},
        {u"configuration_id"_s, configuration}, {u"online"_s, online}, {u"local_inputs"_s, localInputs}}));
    const QDir directory(store);
    require(QDir().mkpath(directory.absolutePath()), u"Création du dossier de rapports impossible"_s);
    const auto path = directory.filePath(reportName(issue));
    QLockFile lock(path + u".lock"_s);
    require(lock.tryLock(5000), u"Investigation concurrente pour cet identifiant"_s);
    if (!refresh) {
        auto previous = readReport(path);
        if (previous.value(u"cache"_s).toObject().value(u"key"_s) == key &&
            previous.value(u"issue_id"_s) == issue && fresh(root, localInputs)) {
            previous.insert(u"cache"_s, QJsonObject{{u"key"_s, key}, {u"hit"_s, true}});
            return {previous};
        }
    }

    Findings findings;
    for (const auto &source : sources) {
        const auto evidence = objectField(source, u"evidence"_s);
        const auto sourcePath = field(evidence, u"artifact_path"_s);
        extract(request, source, loadLocal(inputs, root, sourcePath), findings, false);
    }
    auto assessment = assess(findings.details);
    if (assessment.exact.isEmpty() || findings.incomplete)
        discoverLocal(rootDir, field(referenceField(request), u"part_number"_s), localInputs, findings.diagnostics);
    auto network = u"DISABLED"_s;
    if (online && (!assessment.conflicts.isEmpty() || (!assessment.exact.isEmpty() && !findings.incomplete))) {
        network = u"NOT_NEEDED"_s;
    } else if (online) {
        network = u"NO_CANDIDATES"_s;
        std::stable_partition(remote.begin(), remote.end(), [](const QJsonObject &source) {
            return source.value(u"authority"_s) == u"MANUFACTURER"_s;
        });
        int remaining = 3;
        for (const auto &source : remote) {
            const auto evidence = objectField(source, u"evidence"_s);
            const auto id = field(evidence, u"id"_s);
            QString match;
            QString uri;
            try {
                match = matchSource(request, source);
                checkEvidence(evidence);
                uri = field(evidence, u"uri"_s);
            } catch (const std::exception &error) {
                diagnostic(findings.diagnostics, id, u"EXTRACTION_REJECTED"_s, QString::fromUtf8(error.what()));
                findings.incomplete |= match.isEmpty() || comparable(match);
                continue;
            }
            if (!comparable(match)) {
                diagnostic(findings.diagnostics, id, match, u"Source HTTPS hors du périmètre de la question"_s);
                continue;
            }
            if (remaining == 0) {
                diagnostic(findings.diagnostics, id, u"NETWORK_BUDGET_EXHAUSTED"_s,
                           u"Limite de trois sources HTTPS atteinte"_s);
                findings.incomplete = true;
                continue;
            }
            --remaining;
            network = u"ATTEMPTED"_s;
            extract(request, source, readRemoteSource(uri), findings, true);
        }
        assessment = assess(findings.details);
    } else {
        for (const auto &source : remote) {
            const auto id = field(objectField(source, u"evidence"_s), u"id"_s);
            diagnostic(findings.diagnostics, id, u"NETWORK_DISABLED"_s, u"Source HTTPS non consultée"_s);
        }
    }

    auto question = objectField(request, u"question"_s);
    QJsonArray ids;
    for (const auto &evidence : findings.evidence)
        ids.append(evidence.toObject().value(u"id"_s));
    question.insert(u"evidence_ids"_s, ids);
    auto outcome = u"UNKNOWN"_s;
    auto reason = u"Aucune preuve applicable à la référence, à la révision et aux conditions demandées"_s;
    QJsonValue derivation = null;
    QJsonObject value;
    const auto date = now();
    if (!assessment.conflicts.isEmpty()) {
        outcome = u"INCONCLUSIVE"_s;
        reason = u"Valeurs divergentes pour la même référence et le même domaine ; révisions à rapprocher"_s;
    } else if (findings.incomplete && !assessment.exact.isEmpty()) {
        outcome = u"INCONCLUSIVE"_s;
        reason = u"Une autre preuve applicable n'a pas pu être vérifiée"_s;
    } else if (!assessment.exact.isEmpty()) {
        outcome = u"RESOLVED"_s;
        value = mergeExact(assessment.exact);
        question.insert(u"status"_s, u"CLOSED"_s);
        question.insert(u"evidence_ids"_s, value.value(u"evidence_ids"_s));
    } else if (request.contains(u"derivation"_s)) {
        outcome = u"CONDITIONAL"_s;
        reason = u"Résultat de calcul conditionné par les entrées supposées"_s;
        derivation = calculate(request, date, value);
    }
    if (value.isEmpty()) {
        if (findings.incomplete && outcome == u"UNKNOWN")
            reason += u" ; au moins une source candidate n'a pas pu être vérifiée"_s;
        value = makeValue(unitField(request), u"UNKNOWN"_s, null,
            objectField(request, u"reference"_s).value(u"revision"_s), date, reason);
    }
    QJsonArray unknowns;
    if (outcome != u"RESOLVED") {
        unknowns.append(QJsonObject{{u"issue_id"_s, issue}, {u"question_id"_s, question.value(u"id"_s)},
            {u"reason"_s, reason}, {u"study"_s, request.value(u"study"_s)}});
    }
    const QJsonObject report{{u"schema_version"_s, version}, {u"configuration_id"_s, configuration},
        {u"issue_id"_s, issue}, {u"request"_s, request}, {u"question"_s, question}, {u"outcome"_s, outcome},
        {u"value"_s, value}, {u"technical_evidence"_s, findings.evidence}, {u"evidence_details"_s, findings.details},
        {u"diagnostics"_s, findings.diagnostics}, {u"conflicts"_s, assessment.conflicts},
        {u"unknown_register"_s, unknowns}, {u"derivation"_s, derivation}, {u"network"_s, network},
        {u"cache"_s, QJsonObject{{u"key"_s, key}, {u"hit"_s, false}}}, {u"local_inputs"_s, localInputs}};
    if (!fresh(root, localInputs))
        return absent(issue, u"INPUTS_CHANGED"_s, u"Une entrée locale a changé pendant l'investigation"_s);
    writeReport(path, report);
    return {report};
}

Result get(const QString &root, const QString &store, const QString &issue)
{
    checkId(issue);
    require(QDir(root).exists(), u"Racine documentaire absente"_s);
    const auto report = readReport(QDir(store).filePath(reportName(issue)));
    if (report.isEmpty())
        return absent(issue, u"REPORT_NOT_FOUND"_s, u"Aucun rapport finalisé pour cet identifiant"_s);
    require(report.value(u"issue_id"_s) == issue, u"Identifiant de rapport incohérent"_s);
    if (!fresh(root, arrayField(report, u"local_inputs"_s)))
        return absent(issue, u"REPORT_STALE"_s, u"Les sources locales ont changé ; relancer submit"_s);
    return {report};
}

Result list(const QString &root, const QString &store, const QString &view)
{
    require(QDir(root).exists(), u"Racine documentaire absente"_s);
    require(view == u"reports" || view == u"evidence" || view == u"unknowns", u"Vue inconnue"_s);
    const QDir directory(store);
    QJsonArray items;
    QJsonArray stale;
    QJsonArray invalid;
    for (const auto &name : directory.entryList({u"report-*.json"_s}, QDir::Files, QDir::Name)) {
        QJsonObject report;
        try {
            report = readReport(directory.filePath(name));
        } catch (const std::exception &) {
            invalid.append(name);
            continue;
        }
        if (report.isEmpty())
            continue;
        const auto issue = field(report, u"issue_id"_s);
        require(reportName(issue) == name, u"Nom de rapport incohérent"_s);
        if (!fresh(root, arrayField(report, u"local_inputs"_s))) {
            stale.append(issue);
        } else if (view == u"reports") {
            items.append(report);
        } else if (view == u"evidence") {
            const auto evidence = arrayField(report, u"technical_evidence"_s);
            const auto details = arrayField(report, u"evidence_details"_s);
            for (qsizetype i = 0; i < evidence.size(); ++i)
                items.append(QJsonObject{{u"issue_id"_s, issue}, {u"evidence"_s, evidence.at(i)},
                                          {u"details"_s, details.at(i)}});
        } else {
            for (const auto &unknown : arrayField(report, u"unknown_register"_s))
                items.append(unknown);
        }
    }
    return {{{u"view"_s, view}, {u"items"_s, items}, {u"stale_issue_ids"_s, stale},
             {u"invalid_reports"_s, invalid}}};
}

Result invalidate(const QString &store, const QString &issue)
{
    checkId(issue);
    const QDir directory(store);
    bool removed = false;
    if (directory.exists()) {
        const auto path = directory.filePath(reportName(issue));
        QLockFile lock(path + u".lock"_s);
        require(lock.tryLock(5000), u"Investigation concurrente pour cet identifiant"_s);
        if (QFile::exists(path)) {
            require(QFile::remove(path), u"Invalidation du rapport impossible"_s);
            removed = true;
        }
    }
    return {{{u"issue_id"_s, issue}, {u"invalidated"_s, removed}}};
}

} // namespace technical_research
