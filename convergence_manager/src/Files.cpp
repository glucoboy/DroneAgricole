#include "Files.hpp"

#include <QCryptographicHash>
#include <QFile>
#include <QFileInfo>
#include <QJsonArray>
#include <QJsonDocument>
#include <QRegularExpression>
#include <QSaveFile>
#include <QSet>
#include <stdexcept>

namespace convergence {

void require(bool valid, const QString &message)
{
    if (!valid) {
        throw std::runtime_error(message.toStdString());
    }
}

QByteArray read(const QString &path)
{
    QFile file(path);
    require(file.open(QIODevice::ReadOnly), "Lecture impossible : " + path);
    const auto bytes = file.readAll();
    require(file.error() == QFileDevice::NoError, "Lecture incomplète : " + path);
    return bytes;
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

QJsonObject parse(const QByteArray &bytes, const QString &source)
{
    QJsonParseError error;
    const auto document = QJsonDocument::fromJson(bytes, &error);
    require(document.isObject(), "Objet JSON attendu : " + source + " (" + error.errorString() + ')');
    return document.object();
}

QJsonObject parseUniqueObject(const QByteArray &bytes, const QString &source)
{
    const auto object = parse(bytes, source);
    QList<QSet<QString>> memberNames;
    // Qt has validated the syntax and retained only one value for each name.
    // Scan the original tokens to check uniqueness within every object.
    for (qsizetype index = 0; index < bytes.size(); ++index) {
        const auto token = bytes.at(index);
        if (token == '{') {
            memberNames.emplaceBack();
        } else if (token == '}') {
            memberNames.removeLast();
        } else if (token == '"') {
            const auto start = index++;
            while (bytes.at(index) != '"') {
                index += bytes.at(index) == '\\' ? 2 : 1;
            }
            auto next = index + 1;
            while (next < bytes.size() && QByteArrayView(" \t\r\n").contains(bytes.at(next))) {
                ++next;
            }
            if (next < bytes.size() && bytes.at(next) == ':') {
                const auto nameToken = bytes.sliced(start, index - start + 1);
                const auto name = QJsonDocument::fromJson('[' + nameToken + ']').array().at(0).toString();
                auto &names = memberNames.last();
                require(!names.contains(name), "Champ JSON dupliqué : " + name);
                names.insert(name);
            }
        }
    }
    return object;
}

QJsonObject load(const QString &path)
{
    return parse(read(path), path);
}

QString write(const QString &path, const QByteArray &bytes)
{
    QSaveFile file(path);
    require(file.open(QIODevice::WriteOnly) && file.write(bytes) == bytes.size() && file.commit(),
            "Sauvegarde atomique impossible : " + path);
    return digest(bytes);
}

QString write(const QString &path, const QJsonObject &object)
{
    return write(path, QJsonDocument(object).toJson(QJsonDocument::Indented));
}

QString relative(const QDir &root, const QString &path)
{
    const auto name = root.relativeFilePath(path);
    require(!name.isEmpty() && name != "." && name != ".." && !name.startsWith("../") &&
            !QDir::isAbsolutePath(name), "Chemin hors périmètre : " + path);
    return name;
}

bool hasRedirectedComponent(const QDir &root, const QString &absolutePath)
{
    auto path = root.absolutePath();
    for (const auto &part : relative(root, absolutePath).split('/')) {
#ifdef Q_OS_WIN
        if (part.endsWith('.') || part.endsWith(' ') || part.contains(':')) {
            return true;
        }
#endif
        path += '/' + part;
        const QFileInfo info(path);
        if (info.isSymLink() || info.isJunction()) {
            return true;
        }
    }
    return false;
}

QString fileInside(const QDir &root, const QString &path)
{
    const QFileInfo info(root.absoluteFilePath(path));
    const auto canonical = info.canonicalFilePath();
    require(info.isFile() && !canonical.isEmpty(), "Fichier absent : " + path);
    relative(root, canonical);
    return canonical;
}

QString identifier(const QJsonValue &value)
{
    static const QRegularExpression pattern("^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$");
    const auto id = value.toString();
    require(pattern.match(id).hasMatch(), "Identifiant invalide : " + id);
    return id;
}

} // namespace convergence
