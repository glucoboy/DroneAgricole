#include "Reference.hpp"

#include <QCoreApplication>
#include <QCryptographicHash>
#include <QDateTime>
#include <QFile>
#include <QFileInfo>
#include <QJsonDocument>
#include <QRegularExpression>
#include <QSaveFile>
#include <QSet>
#include <QStandardPaths>
#include <stdexcept>

namespace electromechanical_validation {
namespace {

constexpr auto lockSchema = "drone_agricole.electromechanical_reference.v1";

QString binaryHash()
{
    return fileDigest(QCoreApplication::applicationFilePath());
}

QString resolveExecutable(const QString &name)
{
    const auto found = QDir::isAbsolutePath(name) ? name : QStandardPaths::findExecutable(name);
    const QFileInfo info(found);
    require(!found.isEmpty() && info.isFile() && info.isExecutable(), "Interpréteur introuvable : " + name);
    return info.canonicalFilePath();
}

QString expectedPath(const QDir &root, const QString &path)
{
    const QFileInfo info(root.absoluteFilePath(path));
    const auto parent = info.absoluteDir().canonicalPath();
    require(!parent.isEmpty(), "Répertoire parent absent : " + path);
    const auto result = QDir(parent).filePath(info.fileName());
    relativePath(root, result);
    return result;
}

} // namespace

void require(bool condition, const QString &message)
{
    if (!condition) {
        throw std::runtime_error(message.toStdString());
    }
}

QString digest(const QByteArray &bytes)
{
    return QString::fromLatin1(QCryptographicHash::hash(bytes, QCryptographicHash::Sha256).toHex());
}

QString fileDigest(const QString &path)
{
    QFile file(path);
    QCryptographicHash hash(QCryptographicHash::Sha256);
    require(file.open(QIODevice::ReadOnly) && hash.addData(&file), "Empreinte impossible : " + path);
    return QString::fromLatin1(hash.result().toHex());
}

QByteArray read(const QString &path)
{
    QFile file(path);
    require(file.open(QIODevice::ReadOnly), "Lecture impossible : " + path);
    const auto bytes = file.readAll();
    require(file.error() == QFileDevice::NoError, "Lecture incomplète : " + path);
    return bytes;
}

QJsonObject parse(const QByteArray &bytes, const QString &path)
{
    QJsonParseError error;
    const auto document = QJsonDocument::fromJson(bytes, &error);
    require(document.isObject(), "Objet JSON attendu : " + path + " (" + error.errorString() + ')');
    return document.object();
}

QString writeNew(const QString &path, const QByteArray &bytes)
{
    QSaveFile file(path);
    require(!QFileInfo::exists(path) && file.open(QIODevice::WriteOnly) &&
            file.write(bytes) == bytes.size() && file.commit(), "Publication impossible : " + path);
    return digest(bytes);
}

QString relativePath(const QDir &root, const QString &path)
{
    const auto relative = root.relativeFilePath(path);
    require(!relative.isEmpty() && relative != "." && relative != ".." && !relative.startsWith("../") &&
            !QDir::isAbsolutePath(relative), "Chemin hors espace de travail : " + path);
    return relative;
}

QString workspaceFile(const QDir &root, const QString &path)
{
    const QFileInfo info(root.absoluteFilePath(path));
    const auto canonical = info.canonicalFilePath();
    require(info.isFile() && !canonical.isEmpty(), "Fichier absent : " + path);
    relativePath(root, canonical);
    return canonical;
}

QJsonObject inputReference(const QString &id, const QString &path, const QString &sha256)
{
    return {{"input_id", id}, {"kind", "other"}, {"reference", QJsonObject{{"path", path}}},
            {"checksums", QJsonObject{{"sha256", sha256}}}};
}

QString Reference::seal(const QDir &root, const QString &configuration, const QString &lockPath,
                        const QString &python, const QString &freecadPython)
{
    QJsonObject entries;
    const auto capture = [&](const QString &id, const QString &name) {
        require(!entries.contains(id) && !name.isEmpty(), "Identifiant ou fichier de référence invalide : " + id);
        const auto path = workspaceFile(root, name);
        entries.insert(id, QJsonObject{{"path", relativePath(root, path)}, {"sha256", fileDigest(path)}});
        return path;
    };
    const auto configPath = capture("configuration", configuration);
    const auto config = parse(read(configPath), configPath);
    require(config.value("schema_version") == 1 && config.value("files").isObject(), "Configuration L4 inconnue");
    const auto files = config.value("files").toObject();
    static const QRegularExpression idPattern("^[a-z][a-z0-9_-]*$");
    for (auto it = files.begin(); it != files.end(); ++it) {
        require(idPattern.match(it.key()).hasMatch() && !it.key().startsWith("native-source-"),
                "Identifiant de référence invalide : " + it.key());
        capture(it.key(), it.value().toString());
    }
    for (const auto &required : {"acceptance", "connectivity", "mechanical", "native", "l0-schema", "l2", "l3"}) {
        require(entries.contains(required), QString("Référence obligatoire absente : ") + required);
    }
    const auto nativePath = workspaceFile(root, files.value("native").toString());
    const auto native = parse(read(nativePath), nativePath);
    for (const auto &entry : native.value("cases").toObject()) {
        const auto nativeCase = entry.toObject();
        if (!nativeCase.contains("frozen_model")) {
            continue;
        }
        const auto model = nativeCase.value("frozen_model").toObject();
        require(nativeCase.value("mode") == "candidate" && model.size() == 2,
                "Un modèle externe exige un cas de relecture de candidat et deux fichiers gelés");
        for (const auto *key : {"system", "requirements"}) {
            const auto path = model.value(key);
            require(path.isString() && path == files.value(QString("model-") + key),
                    QString("Fichier du modèle absent du gel : ") + key);
        }
    }
    qsizetype sourceIndex = 0;
    for (const auto &entry : native.value("source_files").toArray()) {
        capture("native-source-" + QString::number(++sourceIndex), entry.toString());
    }
    QJsonObject runtimes;
    if (!freecadPython.isEmpty()) {
        for (const auto &binding : {qMakePair(QString("python"), python), qMakePair(QString("freecad"), freecadPython)}) {
            const auto path = resolveExecutable(binding.second);
            runtimes.insert(binding.first, QJsonObject{{"path", path}, {"sha256", fileDigest(path)}});
        }
    }
    const QJsonObject lock{{"schema", lockSchema}, {"validator_version", VALIDATOR_VERSION},
        {"validator_sha256", binaryHash()}, {"frozen_at_utc", QDateTime::currentDateTimeUtc().toString(Qt::ISODateWithMs)},
        {"files", entries}, {"runtimes", runtimes}};
    for (const auto &entry : entries) {
        const auto item = entry.toObject();
        require(fileDigest(workspaceFile(root, item.value("path").toString())) == item.value("sha256"),
                "Référence modifiée pendant le gel : " + item.value("path").toString());
    }
    return writeNew(expectedPath(root, lockPath), QJsonDocument(lock).toJson());
}

Reference::Reference(const QDir &root, const QString &lockPath, const QString &expectedSha256)
    : root_(root), lockPath_(workspaceFile(root, lockPath))
{
    const auto bytes = read(lockPath_);
    lockHash_ = digest(bytes);
    require(lockHash_ == expectedSha256, "Empreinte externe du référentiel divergente");
    lock_ = parse(bytes, lockPath_);
    require(lock_.value("schema") == lockSchema && lock_.value("validator_version") == VALIDATOR_VERSION &&
            lock_.value("files").isObject(), "Version du référentiel ou du validateur incompatible");
    verify();
}

void Reference::verify() const
{
    require(fileDigest(lockPath_) == lockHash_ && binaryHash() == lock_.value("validator_sha256"),
            "Référentiel ou exécutable différent du gel");
    const auto files = lock_.value("files").toObject();
    for (auto it = files.begin(); it != files.end(); ++it) {
        require(fileDigest(path(it.key())) == hash(it.key()), "Référence modifiée depuis le gel : " + it.key());
    }
}

QJsonObject Reference::document(const QString &id) const
{
    const auto name = path(id);
    const auto bytes = read(name);
    require(digest(bytes) == hash(id), "Référence modifiée depuis le gel : " + id);
    return parse(bytes, name);
}

QString Reference::path(const QString &id) const
{
    const auto file = lock_.value("files").toObject().value(id).toObject().value("path").toString();
    require(!file.isEmpty(), "Fichier absent du gel : " + id);
    return workspaceFile(root_, file);
}

QString Reference::hash(const QString &id) const
{
    return lock_.value("files").toObject().value(id).toObject().value("sha256").toString();
}

QString Reference::lockHash() const
{
    return lockHash_;
}

QJsonObject Reference::runtimes() const
{
    return lock_.value("runtimes").toObject();
}

QString Reference::runtime(const QString &role, const QString &requested) const
{
    const auto binding = runtimes().value(role).toObject();
    const auto expected = binding.value("path").toString();
    require(!expected.isEmpty(), "Aucun interpréteur gelé pour : " + role);
    const auto actual = requested.isEmpty() ? resolveExecutable(expected) : resolveExecutable(requested);
    require(actual == expected && fileDigest(actual) == binding.value("sha256"),
            "Interpréteur différent du gel : " + role);
    return actual;
}

QJsonArray Reference::inputs() const
{
    QJsonArray result{inputReference("reference-lock", relativePath(root_, lockPath_), lockHash_)};
    const auto files = lock_.value("files").toObject();
    for (auto it = files.begin(); it != files.end(); ++it) {
        result.append(inputReference(it.key(), relativePath(root_, path(it.key())), hash(it.key())));
    }
    return result;
}

} // namespace electromechanical_validation
