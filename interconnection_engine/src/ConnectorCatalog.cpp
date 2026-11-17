#include "Interconnection.hpp"

#include <QCryptographicHash>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QRegularExpression>
#include <QSet>
#include <cmath>
#include <stdexcept>

namespace interconnection {
namespace {

const QString pass = QStringLiteral("PASS");
const QString fail = QStringLiteral("FAIL");
const QString unknown = QStringLiteral("INCONCLUSIVE");

QJsonObject attribute(const QJsonObject &part, const QString &key)
{
    return part.value("attributes").toObject().value(key).toObject();
}

bool documentedReference(const QJsonObject &reference)
{
    return !reference.value("value").toString().trimmed().isEmpty() &&
           !reference.value("revision").toString().trimmed().isEmpty() &&
           reference.value("unit") == "1";
}

bool verifiedArtifact(const QJsonObject &proof)
{
    const auto path = proof.value("artifact_path").toString();
    const auto digest = proof.value("sha256").toString();
    static const QRegularExpression sha("^[0-9a-f]{64}$");
    if (path.isEmpty() || QDir::isAbsolutePath(path) || !sha.match(digest).hasMatch()) {
        return false;
    }
    const QDir root(QDir::currentPath());
    const auto canonical = QFileInfo(root.filePath(path)).canonicalFilePath();
    if (canonical.isEmpty() || !canonical.startsWith(root.canonicalPath() + '/')) {
        return false;
    }
    QFile file(canonical);
    QCryptographicHash hash(QCryptographicHash::Sha256);
    return file.open(QIODevice::ReadOnly) && hash.addData(&file) &&
           QString::fromLatin1(hash.result().toHex()) == digest;
}

} // namespace

Index index(const QJsonValue &records, const QString &collection)
{
    if (!records.isArray()) {
        throw std::runtime_error((collection + " doit être une collection").toStdString());
    }
    Index result;
    for (const auto &entry : records.toArray()) {
        const auto record = entry.toObject();
        const auto id = record.value("id").toString();
        if (id.trimmed().isEmpty() || result.contains(id)) {
            throw std::runtime_error((collection + " : identifiant absent ou dupliqué " + id).toStdString());
        }
        result.insert(id, record);
    }
    return result;
}

bool sourced(const QJsonObject &value, const Index &evidence, bool synthetic)
{
    if (value.value("value").isUndefined() || value.value("value").isNull()) {
        return false;
    }
    const auto status = value.value("status").toString();
    for (const auto &evidenceId : value.value("evidence_ids").toArray()) {
        const auto proof = evidence.value(evidenceId.toString());
        if (proof.value("locator").toString().trimmed().isEmpty() ||
            proof.value("revision") != value.value("revision") ||
            value.value("revision").toString().trimmed().isEmpty()) {
            continue;
        }
        if (synthetic && status == "ASSUMED" && proof.value("hypothetical") == true &&
            proof.value("kind") == "ASSUMPTION" && proof.value("domain") == "BENCH") {
            return true;
        }
        if (!synthetic && status == "SOURCED" && proof.value("hypothetical") == false &&
            proof.value("kind") == "SOURCE" && proof.value("domain") == "DOCUMENT" &&
            verifiedArtifact(proof)) {
            return true;
        }
    }
    return false;
}

ConnectorCatalog::ConnectorCatalog(const QJsonObject &dossier, Index evidence, bool synthetic)
    : parts_(index(dossier.value("catalog").toObject().value("parts"), "catalog.parts")),
      evidence_(std::move(evidence)), synthetic_(synthetic)
{
    const auto pairs = dossier.value("catalog").toObject().value("pairs");
    if (!pairs.isArray()) {
        throw std::runtime_error("catalog.pairs doit être une collection");
    }
    for (const auto &entry : pairs.toArray()) {
        const auto pair = entry.toObject();
        const auto ids = qMakePair(pair.value("receptacle_part_id").toString(),
                                   pair.value("mate_part_id").toString());
        if (!parts_.contains(ids.first) || !parts_.contains(ids.second) || pairs_.contains(ids)) {
            throw std::runtime_error("catalog.pairs : référence absente ou paire dupliquée");
        }
        pairs_.insert(ids, pair);
    }
}

QJsonObject ConnectorCatalog::part(const QString &id) const
{
    return parts_.value(id);
}

QString ConnectorCatalog::contactPart(const QJsonObject &reference) const
{
    QString id;
    if (!documentedReference(reference) || !hasSource(reference)) {
        return id;
    }
    for (auto it = parts_.cbegin(); it != parts_.cend(); ++it) {
        const auto candidate = it.value().value("reference").toObject();
        if (it.value().value("role") == "CONTACT" && candidate.value("value") == reference.value("value") &&
            candidate.value("revision") == reference.value("revision") && hasSource(candidate)) {
            if (!id.isEmpty()) {
                return {};
            }
            id = it.key();
        }
    }
    return id;
}

bool ConnectorCatalog::hasSource(const QJsonObject &value) const
{
    return sourced(value, evidence_, synthetic_);
}

QJsonObject ConnectorCatalog::pair(const QString &receptacle, const QString &mate) const
{
    return pairs_.value(qMakePair(receptacle, mate));
}

Findings ConnectorCatalog::checkPair(const QString &receptacle, const QString &mate,
                                     const QJsonObject &requirements, const QString &subject) const
{
    Findings findings;
    const auto add = [&](const QString &code, const QString &status, const QString &reason) {
        findings.append({"compatibility", code, subject, status, reason});
    };
    const auto a = part(receptacle);
    const auto b = part(mate);
    const auto ra = a.value("reference").toObject();
    const auto rb = b.value("reference").toObject();
    const bool identity = documentedReference(ra) && documentedReference(rb) &&
        hasSource(ra) && hasSource(rb) &&
        (synthetic_ || (a.value("origin") == "SUPPLIER" && b.value("origin") == "SUPPLIER"));
    add("PART_PROVENANCE", identity ? pass : unknown,
        identity ? "Références et révisions documentées dans le périmètre déclaré"
                 : "Référence, révision ou preuve applicable manquante");

    for (const auto &key : {"family", "keying", "ways", "polarity", "locking", "signal_profile"}) {
        const auto av = attribute(a, key);
        const auto bv = attribute(b, key);
        const auto expected = requirements.value(key).toObject();
        if (!hasSource(av) || !hasSource(bv) || (!expected.isEmpty() && !hasSource(expected))) {
            add(key, unknown, "Attribut ou besoin sans preuve applicable");
            continue;
        }
        const auto value = av.value("value");
        const bool valid = QString(key) == "ways"
            ? value.isDouble() && value.toDouble() > 0 && value.toDouble() == std::floor(value.toDouble())
            : value.isString() && !value.toString().trimmed().isEmpty();
        const bool matches = valid && av.value("unit") == "1" && bv.value("unit") == "1" &&
            value == bv.value("value") && (expected.isEmpty() ||
                (expected.value("unit") == "1" && value == expected.value("value")));
        add(key, matches ? pass : fail, matches ? "Attribut concordant" : "Attribut incompatible");
    }

    const auto ag = attribute(a, "gender");
    const auto bg = attribute(b, "gender");
    if (hasSource(ag) && hasSource(bg)) {
        const auto ga = ag.value("value").toString();
        const auto gb = bg.value("value").toString();
        const bool genders = (ga == "FEMALE" && gb == "MALE") || (ga == "MALE" && gb == "FEMALE") ||
            (ga == "GENDERLESS" && gb == "GENDERLESS") || (ga == "PERMANENT" && gb == "PERMANENT");
        add("GENDER", genders ? pass : fail, genders ? "Genres complémentaires" : "Genres incompatibles");
    } else {
        add("GENDER", unknown, "Genre sans preuve applicable");
    }

    const auto relation = pair(receptacle, mate);
    const auto compatibility = relation.value("compatibility").toObject();
    const bool revisionsMatch = relation.value("receptacle_revision") == ra.value("revision") &&
        relation.value("mate_revision") == rb.value("revision");
    const bool proven = identity && revisionsMatch && hasSource(compatibility) &&
        compatibility.value("unit") == "1" && compatibility.value("value").isBool();
    const bool confirmed = proven && compatibility.value("value") == true;
    add("EXPLICIT_MATE", proven ? (confirmed ? pass : fail) : unknown,
        confirmed ? "Accouplement explicite des deux références et révisions"
                  : "Aucun accouplement confirmé pour cette paire exacte");

    for (const auto &key : {"current_A", "voltage_V"}) {
        const auto av = attribute(a, key);
        const auto bv = attribute(b, key);
        const auto required = requirements.value(key).toObject();
        const auto unit = QString(key).endsWith("_A") ? "A" : "V";
        if (!hasSource(av) || !hasSource(bv) || !hasSource(required)) {
            add(key, unknown, "Limite de composant ou besoin non documenté");
            continue;
        }
        const auto demand = required.value("value").toDouble(-1);
        const bool matches = demand >= 0 && av.value("unit") == unit && bv.value("unit") == unit &&
            required.value("unit") == unit && av.value("value").toDouble(-1) >= demand &&
            bv.value("value").toDouble(-1) >= demand;
        add(key, matches ? pass : fail, matches ? "Limite suffisante" : "Limite ou unité incompatible");
    }
    if (requirements.value("signal_profile").toObject().isEmpty()) {
        add("SIGNAL_REQUIREMENT", unknown, "Profil de signal attendu absent");
    }
    if (!synthetic_) {
        add("SUPPLIER_APPLICABILITY", unknown, "Applicabilité fabricant au lot monté à établir hors présélection");
    }
    return findings;
}

QJsonArray ConnectorCatalog::bom(const QMap<QString, int> &used) const
{
    QJsonArray lines;
    for (auto it = used.cbegin(); it != used.cend(); ++it) {
        const auto partRecord = part(it.key());
        const auto reference = partRecord.value("reference").toObject();
        QJsonArray sources;
        for (const auto &id : reference.value("evidence_ids").toArray()) {
            if (evidence_.contains(id.toString())) {
                sources.append(evidence_.value(id.toString()));
            }
        }
        lines.append(QJsonObject{{"part_id", it.key()}, {"quantity", it.value()},
            {"role", partRecord.value("role")}, {"reference", reference}, {"sources", sources},
            {"status", synthetic_ ? "SYNTHETIC" : "CANDIDATE"},
            {"reference_sourced", documentedReference(reference) && hasSource(reference)}});
    }
    return lines;
}

QJsonArray ConnectorCatalog::matches(const QString &receptacle) const
{
    if (!parts_.contains(receptacle)) {
        throw std::runtime_error("Référence catalogue absente");
    }
    QJsonArray result;
    for (auto it = parts_.cbegin(); it != parts_.cend(); ++it) {
        if (it.value().value("role") != "PLUG") {
            continue;
        }
        Findings findings = checkPair(receptacle, it.key(), {}, it.key());
        // Sans demande de liaison, la présélection ne peut statuer sur son usage électrique.
        QJsonArray checks;
        QString status = pass;
        for (const auto &finding : findings) {
            if (finding.code == "current_A" || finding.code == "voltage_V" ||
                finding.code == "SIGNAL_REQUIREMENT") {
                continue;
            }
            checks.append(finding.json());
            if (finding.status == fail || (finding.status == unknown && status == pass)) {
                status = finding.status;
            }
        }
        result.append(QJsonObject{{"mate_part_id", it.key()}, {"prescreen", status}, {"findings", checks}});
    }
    return result;
}

QJsonObject findCompatibleMates(const QJsonObject &dossier, const QString &receptacleId)
{
    const auto model = dossier.value("model").toObject();
    const auto records = model.value("records").toObject();
    const bool synthetic = dossier.value("mode") == "SYNTHETIC_BENCH";
    const ConnectorCatalog catalog(dossier, index(records.value("technical_evidence"), "technical_evidence"), synthetic);
    return {{"receptacle_part_id", receptacleId}, {"mode", dossier.value("mode")},
            {"candidates", catalog.matches(receptacleId)}};
}

} // namespace interconnection
