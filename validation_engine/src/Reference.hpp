#pragma once

#include <QDir>
#include <QJsonArray>
#include <QJsonObject>
#include <QMap>

namespace electromechanical_validation {

void require(bool condition, const QString &message);
QString digest(const QByteArray &bytes);
QString fileDigest(const QString &path);
QByteArray read(const QString &path);
QJsonObject parse(const QByteArray &bytes, const QString &path);
QString writeNew(const QString &path, const QByteArray &bytes);
QString relativePath(const QDir &root, const QString &path);
QString workspaceFile(const QDir &root, const QString &path);
QJsonObject inputReference(const QString &id, const QString &path, const QString &sha256);

class Reference {
public:
    static QString seal(const QDir &root, const QString &configuration, const QString &lockPath,
                        const QString &python, const QString &freecadPython);
    Reference(const QDir &root, const QString &lockPath, const QString &expectedSha256);

    void verify() const;
    QJsonObject document(const QString &id) const;
    QString path(const QString &id) const;
    QString hash(const QString &id) const;
    QString lockHash() const;
    QJsonObject runtimes() const;
    QString runtime(const QString &role, const QString &requested) const;
    QJsonArray inputs() const;

private:
    QDir root_;
    QString lockPath_;
    QString lockHash_;
    QJsonObject lock_;
};

} // namespace electromechanical_validation
